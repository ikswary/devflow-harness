"""저장소에 사용자 홈 경로·개인 설치 경로와 비공개 금지 문자열이 없음.

- 대상: `git ls-files`와 `git ls-files --others --exclude-standard`의 파일. 이 시험 파일 자신은 뺀다(패턴을 담으므로).
- 일반 패턴(사용자 홈 경로의 꼴, 플러그인이 아닌 개인 설치 경로)은 이 파일 안에 둔다.
- 비공개 패턴(고객·개인 문자열)은 저장소에 두지 않고 환경 변수 `DEVFLOW_FORBIDDEN`(쉼표로 나눔)에서 받는다.
  없거나 비면 그 시험만 건너뛰고 이유를 보인다.
"""
import os
import re
import subprocess

import pytest

from conftest import ROOT

ENV_NAME = "DEVFLOW_FORBIDDEN"
SELF = "tests/py/test_strings.py"

# (보이는 이름, 정규식)
GENERAL_PATTERNS = [
    ("C:\\Users", re.escape("C:\\Users")),
    ("C:/Users", re.escape("C:/Users")),
    ("/home/", re.escape("/home/")),
    ("/Users/", re.escape("/Users/")),
    (".claude/skills", re.escape(".claude/skills")),
    (".claude/agents", re.escape(".claude/agents")),
    (".claude\\skills", re.escape(".claude\\skills")),
    (".claude\\agents", re.escape(".claude\\agents")),
]


def repo_files():
    """추적 파일과 무시되지 않은 추적 안 된 파일(저장소 루트 기준 슬래시 경로). 이 시험 파일은 뺀다."""
    names = set()
    for extra in ([], ["--others", "--exclude-standard"]):
        proc = subprocess.run(["git", "ls-files", "-z"] + extra, cwd=ROOT, capture_output=True)
        assert proc.returncode == 0, "git ls-files 실패({}): {}".format(proc.returncode, proc.stderr.decode("utf-8", "replace"))
        names.update(n for n in proc.stdout.decode("utf-8").split("\0") if n)
    names.discard(SELF)
    return sorted(n for n in names if (ROOT / n).is_file())


def scan(path, text, patterns):
    """`path:줄: 패턴` 꼴의 걸린 곳 목록."""
    hits = []
    for no, line in enumerate(text.splitlines(), 1):
        for label, regex in patterns:
            if re.search(regex, line):
                hits.append("{}:{}: {}".format(path, no, label))
    return hits


def scan_repo(patterns):
    files = repo_files()
    # 대상이 비면 무엇이든 통과하므로 알려진 파일이 대상에 드는지 먼저 본다
    for known in ("CHANGELOG.md", "scripts/devflow_lib.py", "tests/py/conftest.py"):
        assert known in files, "검사 대상에 {}가 없음(대상 {}개) — git 저장소 안에서 돌리는지 확인한다".format(known, len(files))
    hits = []
    for name in files:
        text = (ROOT / name).read_bytes().decode("utf-8", errors="replace")
        hits.extend(scan(name, text, patterns))
    return hits


def private_patterns():
    raw = os.environ.get(ENV_NAME, "")
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if not values:
        pytest.skip("환경 변수 {}가 없거나 비었음 — 비공개 금지 문자열 검사를 건너뜀".format(ENV_NAME))
    # 비공개 값을 시험 출력에 다시 쓰지 않도록 보이는 이름은 목록 안 순번으로 둔다
    return [("{} {}번째 값".format(ENV_NAME, i + 1), re.escape(v)) for i, v in enumerate(values)]


def test_no_general_patterns():
    hits = scan_repo(GENERAL_PATTERNS)
    assert hits == [], "일반 금지 패턴이 걸린 곳 {}건:\n".format(len(hits)) + "\n".join(hits)


def test_no_private_patterns():
    hits = scan_repo(private_patterns())
    assert hits == [], "{}의 값이 걸린 곳 {}건:\n".format(ENV_NAME, len(hits)) + "\n".join(hits)


# --- 검사기 자신의 양성 대조(걸려야 할 것이 걸린다) ---

@pytest.mark.parametrize("label,regex", GENERAL_PATTERNS, ids=[p[0] for p in GENERAL_PATTERNS])
def test_scan_catches_each_general_pattern(label, regex):
    sample = "앞 x {} 뒤".format(label)
    assert scan("docs/sample.md", sample, GENERAL_PATTERNS) == ["docs/sample.md:1: " + label]


def test_private_values_are_reported_by_index_only(monkeypatch):
    monkeypatch.setenv(ENV_NAME, "first, second")
    patterns = private_patterns()
    assert [label for label, _ in patterns] == ["{} 1번째 값".format(ENV_NAME), "{} 2번째 값".format(ENV_NAME)]
    assert scan("a.md", "x second y", patterns) == ["a.md:1: {} 2번째 값".format(ENV_NAME)]
