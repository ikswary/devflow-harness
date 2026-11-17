"""시험 고르기 도구(`select_tests.py`) 시험.

- 직접 닿음: scripts 모듈 `m`마다, 원문에서 `m`을 직접 import하거나 `run_script("m")`을 부르는 시험 파일이
  모두 `select(["scripts/m.py"])`에 든다. 기대값은 도구의 ast 읽기와 따로, 시험 파일 원문을 줄 단위 정규식으로 읽어 만든다.
- 역방향 닫힘: B를 import하는 A에만 직접 닿는 시험이 `select(["scripts/B.py"])`에 든다(저장소의 실제 간선).
- 규칙 표의 줄: conftest, 시험 파일 하나, TS, 없는 파일, 문서.
- 명령행: 고른 경로를 한 줄에 하나와 종료 0, `--run`은 pytest의 종료 코드.
"""
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

from conftest import ROOT, write
from select_tests import TS_LINE, UNMATCHED_LINE, main, select
from test_imports import import_graph

TOOL = ROOT / "tests" / "py" / "select_tests.py"
TEST_FILES = sorted(ROOT.glob("tests/py/test_*.py"))
# 저장소에 없는 파일 이름. 이 시험 파일의 원문에 글자 그대로 두면 도구가 이 파일을 고르므로 이어 붙여 만든다
ABSENT = "-".join(["zz", "select", "absent.txt"])


def rel(path):
    return path.relative_to(ROOT).as_posix()


def direct_names(text):
    """원문 줄에서 직접 import한 최상위 이름과 `run_script("…")`의 글자 그대로 첫 인자."""
    out = set()
    for line in text.splitlines():
        m = re.match(r"\s*import\s+(.+)", line)
        if m:
            out.update(part.split(" as ")[0].strip().split(".")[0] for part in m.group(1).split("#")[0].split(","))
        m = re.match(r"\s*from\s+([\w]+)[\w.]*\s+import\b", line)
        if m:
            out.add(m.group(1))
    out.update(re.findall(r"""run_script\(\s*["'](\w+)["']""", text))
    return out


def direct_map():
    """{시험 파일 경로: 원문이 직접 닿는 이름}."""
    return {rel(p): direct_names(p.read_text(encoding="utf-8-sig")) for p in TEST_FILES}


def test_every_script_module_selects_tests_that_reach_it_directly():
    graph = import_graph()
    direct = direct_map()
    expected = {m: sorted(t for t, names in direct.items() if m in names) for m in graph}
    # 기대값이 비어 거저 통과하지 않는다: 직접 닿는 시험이 있는 모듈이 여럿이고 run_script로만 닿는 사례도 있다
    assert sum(1 for tests in expected.values() if tests) >= 10, expected
    assert "tests/py/test_version.py" in expected["kinds"], expected["kinds"]
    missing = {}
    for m, tests in expected.items():
        got = set(select(["scripts/{}.py".format(m)]).tests)
        lost = [t for t in tests if t not in got]
        if lost:
            missing[m] = lost
    assert missing == {}, "직접 닿는데 고르지 않은 시험: {}".format(missing)


def test_script_selects_tests_reaching_it_only_through_an_importer():
    graph = import_graph()
    direct = direct_map()
    cases = sorted((b, a, t) for a, deps in graph.items() for b in deps
                   for t, names in direct.items() if a in names and b not in names)
    assert cases, "B를 import하는 A에만 직접 닿는 시험이 저장소에 없다 — 이 시험의 전제"
    # 실제 간선 한 사례를 이름으로 고정한다: judge_facts → plain_text, test_judge_facts.py는 plain_text를 직접 부르지 않는다
    assert "plain_text" in graph["judge_facts"]
    assert ("plain_text", "judge_facts", "tests/py/test_judge_facts.py") in cases, cases[:5]
    chosen = {b: set(select(["scripts/{}.py".format(b)]).tests) for b in {b for b, _, _ in cases}}
    missing = sorted({(b, t) for b, _, t in cases if t not in chosen[b]})
    assert missing == [], "import하는 모듈을 거쳐 닿는데 고르지 않은 시험: {}".format(missing[:10])


def test_conftest_selects_every_test_file():
    sel = select(["tests/py/conftest.py"])
    assert sel.tests == [rel(p) for p in TEST_FILES]
    assert len(sel.tests) > 1 and sel.unmatched == [] and sel.ts is False


def test_test_file_selects_itself():
    sel = select(["tests/py/test_version.py"])
    assert sel.tests == ["tests/py/test_version.py"]
    assert sel.unmatched == [] and sel.ts is False


def test_ts_file_selects_no_pytest_and_flags_ts():
    sel = select(["hooks/common.ts"])
    assert sel.tests == [] and sel.ts is True and sel.unmatched == []


def test_unknown_file_is_unmatched():
    name = ABSENT
    assert not (ROOT / name).exists()
    sel = select([name])
    assert sel.unmatched == [name] and sel.tests == [] and sel.ts is False
    # 양성 대조: 같은 호출에 있는 파일은 고른다
    both = select([name, "tests/py/test_version.py"])
    assert both.unmatched == [name] and both.tests == ["tests/py/test_version.py"]


def test_reference_doc_selects_size_and_budget_tests():
    sel = select(["references/formats/judge-file.md"])
    assert {"tests/py/test_doc_size.py", "tests/py/test_read_budget.py"} <= set(sel.tests), sel.tests
    assert sel.unmatched == []


def test_command_line_prints_one_path_per_line():
    proc = subprocess.run([sys.executable, "-B", str(TOOL), "tests/py/test_version.py", "hooks/common.ts",
                           ABSENT],
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120,
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.splitlines() == ["tests/py/test_version.py", TS_LINE]
    assert proc.stderr.splitlines() == [UNMATCHED_LINE.format(ABSENT)]


def test_run_ends_with_pytest_exit_code(tmp_path, capfd, monkeypatch):
    # --run은 병렬 pytest를 띄운다: 그 python에 pytest-xdist가 있어야 한다(test-rules ⑥)
    assert importlib.util.find_spec("xdist"), (
        "pytest-xdist가 없음: {} — requirements-dev.txt대로 공용 venv에 설치한다".format(sys.executable))
    # `-n auto`의 작업자 수만 하나로 줄인다(명령은 그대로. 바깥 병렬 실행의 작업자 표지는 안쪽 pytest에 넘기지 않는다)
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "1")
    for name in ("PYTEST_XDIST_WORKER", "PYTEST_XDIST_WORKER_COUNT", "PYTEST_XDIST_TESTRUNUID"):
        monkeypatch.delenv(name, raising=False)
    write(tmp_path / "tests" / "py" / "test_fails.py", "def test_fails():\n    assert 1 == 2\n")
    code = main(["--run", "tests/py/test_fails.py"], root=tmp_path)
    out = capfd.readouterr().out
    assert code == 1, out   # pytest의 "시험 실패" 종료 코드
    assert out.splitlines()[0] == "tests/py/test_fails.py"
    assert "1 failed" in out
