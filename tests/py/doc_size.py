"""하네스 문서 크기 도구. 경보 도구이고 시험이 아니다.

하네스 문서(`SCOPE`의 `.md`, `EXCLUDE` 뺌)마다 줄 수(LF 개수, `wc -l`)와 바이트 수(`wc -c`)를 재서 `LIMITS`와 견준다.
진입 `ENTRY`에는 줄과 진입 상한을, 그 밖의 파일에는 줄과 바이트 상한을 댄다.
`PENDING`(파일, 상한 이름, 그때 값, 「정해 주실 것」 항목)에 든 파일은 그 상한에서 그때 값 이하면 넘음으로 세지 않는다
. 넣을 때 결과 「정해 주실 것」 한 항목의 하위 줄에 파일·상한·값·줄일 후보 대응표 행을 적는다.

사용법:
  python3 tests/py/doc_size.py check [--rev REV] [PATH…]
    PATH가 없으면 범위 전부. --rev가 있으면 작업 트리 대신 `git show REV:{경로}`를 잰다.
    넘는 파일마다 `{경로} {줄}줄 {바이트}B 넘음({상한})`, `PENDING`으로 세지 않은 파일마다
    `{경로} {줄}줄 {바이트}B 보류({상한} ≤ {그때 값}: {항목})`, 끝 줄 `doc_size: 정상` 또는 `doc_size: {n}개 넘음`.
    종료 0 정상 / 1 `PENDING` 밖의 넘음이 있음 / 2 사용법·없는 경로·git 오류.

`check`는 판정자가 직접 불러 볼 수 있게 모듈 수준 함수로 둔다.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LIMITS: dict[str, int] = {"줄": 100, "바이트": 8192, "진입": 6144}
ENTRY = "skills/devflow-harness/SKILL.md"
SCOPE = ("skills/**/*.md", "references/**/*.md", "agents/*.md")
EXCLUDE = ("references/core/repeats.md",)   # 독자 없는 데이터

# (파일, 상한 이름, 그때 값, 사유). 상한을 넘는 파일을 바로 줄일 수 없을 때 넣는다
PENDING: list[tuple[str, str, int, str]] = [
    ("references/kinds/design.md", "바이트", 10665, "T055 사용자 답 2026-10-19: 설계 모듈은 다른 때 읽는 줄만 나눔"),
]


class DocSizeError(Exception):
    """없는 경로·git 오류. 명령행은 종료 2."""


def _glob_re(pattern):
    out = []
    for part in re.split(r"(\*\*/|\*)", pattern):
        if part == "**/":
            out.append("(?:.*/)?")
        elif part == "*":
            out.append("[^/]*")
        else:
            out.append(re.escape(part))
    return re.compile("".join(out) + r"\Z")


_SCOPE_RE = [_glob_re(p) for p in SCOPE]


def in_scope(rel):
    """플러그인 폴더 기준 경로(`/` 구분)가 크기 범위에 드는지."""
    return rel not in EXCLUDE and any(r.match(rel) for r in _SCOPE_RE)


def _git(args):
    proc = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True)
    if proc.returncode != 0:
        raise DocSizeError("git {} 실패: {}".format(" ".join(args), proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


def scope_files(rev=None):
    """범위의 파일(플러그인 폴더 기준 경로, 정렬). rev가 있으면 그 판의 파일."""
    if rev:
        names = _git(["ls-tree", "-r", "--name-only", "-z", rev]).decode("utf-8").split("\0")
    else:
        names = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.md") if p.is_file()]
    return sorted(n for n in names if n and in_scope(n))


def _rel(path):
    """명령행 경로(지금 폴더 기준 또는 절대)를 플러그인 폴더 기준 경로로."""
    return Path(os.path.relpath(os.path.abspath(path), ROOT)).as_posix()


def _read(rel, rev):
    if rev:
        return _git(["show", "{}:{}".format(rev, rel)])
    path = ROOT / rel
    if not path.is_file():
        raise DocSizeError("{} 없음".format(rel))
    return path.read_bytes()


def limits_of(rel):
    """그 파일에 대는 상한 이름들(차례대로)."""
    return ("줄", "진입") if rel == ENTRY else ("줄", "바이트")


def measure(rel, data):
    """(줄, 바이트, 넘는 상한 이름들, PENDING으로 세지 않는 (상한, 그때 값, 항목)들)."""
    lines, size = data.count(b"\n"), len(data)
    value = {"줄": lines, "바이트": size, "진입": size}
    over = [name for name in limits_of(rel) if value[name] > LIMITS[name]]
    held = [(name, cap, item) for f, name, cap, item in PENDING
            if f == rel and name in over and value[name] <= cap]
    return lines, size, [n for n in over if n not in {h[0] for h in held}], held


def _results(paths, rev):
    rels = [_rel(p) for p in paths] if paths else scope_files(rev)
    for rel in rels:
        yield (rel,) + measure(rel, _read(rel, rev))


def check(paths, rev=None):
    """넘는 파일마다 (경로, 줄, 바이트, 상한 이름들을 ", "로 이은 것). paths가 비면 범위 전부. `PENDING`으로 세지 않은 상한은 뺀다."""
    return [(rel, lines, size, ", ".join(over)) for rel, lines, size, over, _ in _results(paths, rev) if over]


USAGE = "사용법: python3 tests/py/doc_size.py check [--rev REV] [PATH…]\n"


def main(argv):
    if not argv or argv[0] != "check":
        sys.stderr.write(USAGE)
        return 2
    args, rev = list(argv[1:]), None
    if args[:1] == ["--rev"]:
        if len(args) < 2:
            sys.stderr.write(USAGE)
            return 2
        rev, args = args[1], args[2:]
    if any(a.startswith("-") for a in args):
        sys.stderr.write(USAGE)
        return 2
    out, n = [], 0
    try:
        for rel, lines, size, over, held in _results(args, rev):
            for name, cap, item in held:
                out.append("{} {}줄 {}B 보류({} ≤ {}: {})".format(rel, lines, size, name, cap, item))
            if over:
                n += 1
                out.append("{} {}줄 {}B 넘음({})".format(rel, lines, size, ", ".join(over)))
    except DocSizeError as e:
        sys.stderr.write("doc_size: {}\n".format(e))
        return 2
    out.append("doc_size: 정상" if n == 0 else "doc_size: {}개 넘음".format(n))
    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
