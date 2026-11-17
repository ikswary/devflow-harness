"""바뀐 파일에서 닿는 시험 파일을 고르는 도구. 시험이 아니라 고치는 동안 쓰는 도구다(커밋 전에는 전체 병렬 시험).

시험 파일(`tests/py/test_*.py`)마다 "닿는 이름"을 정적으로 모은다.
- ast로 본 import(scripts 모듈과 `tests/py`의 모듈. `import_graph`와 같은 `imported_names`로 읽는다).
- `run_script("{m}")`의 첫 인자. 첫 인자가 글자 그대로가 아니면(`run_script(script, …)`) 그 파일의 문자열 상수 가운데
  scripts 모듈 이름과 같은 것.
- 가져온 `tests/py` 모듈(도우미와 `from test_x import`의 시험 파일)의 닿는 이름. `conftest`는 pytest가 모든 시험에
  싣으므로 모든 시험 파일이 가져온 것으로 센다.
- 원문: 시험 파일과 가져온 `tests/py` 모듈의 글.

바뀐 파일마다 규칙 표(`RULES` 차례, 처음 걸린 줄)로 고른다.
- `tests/py/conftest.py` → 모든 시험 파일.
- `tests/py/test_*.py` → 그 파일과, 그 파일을 가져오는 시험 파일. 없는 파일이면 `unmatched`.
- `tests/py/{도우미}.py` → 그 모듈을 가져오는 시험 파일.
- `scripts/{m}.py` → `m`, 또는 `m`을 거쳐 import하는 scripts 모듈(역방향 닫힘, `test_imports.import_graph`)을 닿는 이름에 가진 시험.
- `hooks/**`, `tests/*.ts(x)`, `types/**` → pytest 없음, `ts = True`.
- 그 밖 → 원문에 저장소 기준 경로, 파일 이름, 또는 첫 경로 마디가 문자열로(`"references"`, `"references/`) 든 시험.
  `tests/py/` 아래 파일(`tests/py/golden/**`)은 `tests/py/` 뒤의 첫 마디(`"golden"`)도 첫 경로 마디로 센다.
- 고른 시험이 없으면 `unmatched`.

사용법:
  python tests/py/select_tests.py [--base REV] [--run] [PATH ...]
    PATH가 없으면 `git diff --name-only REV`(기본 `HEAD`)와 `git ls-files --others --exclude-standard`.
    고른 시험 경로를 한 줄에 하나(정렬), `ts`면 `claude plugin test .` 한 줄, 못 고른 파일마다 표준 오류에
    `! 고른 시험 없음: {파일}`. 종료 0. git 오류는 표준 오류에 이유를 내고 종료 2.
    --run: 고른 시험이 있으면 `{python} -m pytest -q -p no:cacheprovider -n auto {시험…}`을 돌리고 그 종료 코드로 끝낸다.
    고른 시험이 없으면 0. TS 시험은 돌리지 않고 줄만 낸다.

`select`·`main`은 판정자가 직접 불러 볼 수 있게 모듈 수준 함수로 둔다.
"""
import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __name__ == "__main__":
    # 명령행으로 돌릴 때만 tests/py 아래에 __pycache__를 남기지 않는다(import하는 쪽의 설정은 건드리지 않는다)
    sys.dont_write_bytecode = True

from test_imports import import_graph, imported_names  # noqa: E402  그래프는 층 시험과 같은 것을 쓴다

ROOT = Path(__file__).resolve().parents[2]
PY_DIR = "tests/py/"
TS_LINE = "claude plugin test ."
TS_PATTERNS = (re.compile(r"hooks/.+"), re.compile(r"tests/[^/]+\.tsx?"), re.compile(r"types/.+"))
UNMATCHED_LINE = "! 고른 시험 없음: {}"


@dataclass
class Selection:
    tests: list[str] = field(default_factory=list)
    ts: bool = False
    unmatched: list[str] = field(default_factory=list)


@dataclass
class _Index:
    tests: list[str]                 # 저장소 기준 경로, 정렬
    names: dict[str, set[str]]       # 시험 파일 → 닿는 이름(scripts 모듈과 tests/py 모듈)
    texts: dict[str, str]            # 시험 파일 → 그 파일과 가져온 tests/py 모듈의 원문을 이은 글
    graph: dict[str, set[str]]       # scripts 모듈 → 그 모듈이 import하는 scripts 모듈


def _run_script_names(tree, script_mods):
    """`run_script("{m}")`의 첫 인자. 첫 인자가 글자 그대로가 아닌 호출이 있으면 파일의 문자열 상수 가운데 모듈 이름도."""
    out, dynamic = set(), False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "run_script":
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                out.add(first.value)
            else:
                dynamic = True
    if dynamic:
        out.update(n.value for n in ast.walk(tree)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in script_mods)
    return out & script_mods


def _own_names(path, script_mods, py_mods):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    return (imported_names(path) & (script_mods | py_mods)) | _run_script_names(tree, script_mods)


def _index(root):
    root = Path(root)
    tests_dir = root / "tests" / "py"
    scripts_dir = root / "scripts"
    graph = import_graph(scripts_dir) if scripts_dir.is_dir() else {}
    script_mods = set(graph)
    py_files = {p.stem: p for p in sorted(tests_dir.glob("*.py"))}
    py_mods = set(py_files)
    own = {m: _own_names(p, script_mods, py_mods) for m, p in py_files.items()}
    raw = {m: p.read_text(encoding="utf-8-sig") for m, p in py_files.items()}

    def reached_py(start):
        """start에서 가져오기로 닿는 tests/py 모듈(start 포함). conftest는 시험 파일마다 더한다."""
        seen, todo = set(), [start] + (["conftest"] if start.startswith("test_") and "conftest" in py_mods else [])
        while todo:
            m = todo.pop()
            if m in seen:
                continue
            seen.add(m)
            todo.extend(own[m] & py_mods)
        return seen

    tests, names, texts = [], {}, {}
    for m in sorted(py_mods):
        if not m.startswith("test_"):
            continue
        rel = "tests/py/{}.py".format(m)
        mods = reached_py(m)
        tests.append(rel)
        names[rel] = set().union(*(own[x] for x in mods)) | (mods - {m})
        texts[rel] = "\n".join(raw[x] for x in sorted(mods))
    return _Index(tests, names, texts, graph)


_CACHE: dict = {}


def _cached_index(root):
    """`_index`를 읽은 파일의 (경로, 바뀐 시각)이 같으면 다시 쓴다(한 프로세스에서 `select`를 여러 번 부를 때)."""
    root = Path(root)
    files = sorted((root / "tests" / "py").glob("*.py")) + sorted((root / "scripts").glob("*.py"))
    key = (str(root.resolve()), tuple((str(f), f.stat().st_mtime_ns) for f in files))
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = _index(root)
    return _CACHE[key]


def _importers(graph, target):
    """target과, target을 거쳐(간선을 따라) import하는 scripts 모듈."""
    out, todo = set(), [target]
    while todo:
        b = todo.pop()
        if b in out:
            continue
        out.add(b)
        todo.extend(a for a, deps in graph.items() if b in deps)
    return out


def _text_hits(text, rel):
    """원문에 rel의 경로, 파일 이름, 첫 경로 마디(따옴표 안)가 드는가. `tests/py/` 아래 파일은 시험이 자기 폴더에서
    부르므로(`Path(__file__).parent / "golden"`) `tests/py/` 뒤의 첫 마디도 첫 경로 마디로 센다."""
    name = rel.rsplit("/", 1)[-1]
    firsts = {rel.split("/", 1)[0]}
    if rel.startswith(PY_DIR) and "/" in rel[len(PY_DIR):]:
        firsts.add(rel[len(PY_DIR):].split("/", 1)[0])
    edge = r"(?<![\w.\-]){}(?![\w\-])"
    if re.search(edge.format(re.escape(rel)), text) or re.search(edge.format(re.escape(name)), text):
        return True
    return any(re.search(r"""["']{}(["']|/)""".format(re.escape(f)), text) for f in firsts)


def _normalize(path, root):
    text = str(path).replace("\\", "/")
    p = Path(text)
    if p.is_absolute():
        try:
            text = p.resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            pass
    while text.startswith("./"):
        text = text[2:]
    return text


def _pick(rel, index):
    """(고른 시험 집합, ts 여부)."""
    stem = rel[len(PY_DIR):-len(".py")] if rel.startswith(PY_DIR) and rel.endswith(".py") else None
    if stem is not None and "/" not in stem:
        if stem == "conftest":
            return set(index.tests), False
        if stem.startswith("test_"):
            if rel not in index.names:
                return set(), False
            return {rel} | {t for t in index.tests if stem in index.names[t]}, False
        return {t for t in index.tests if stem in index.names[t]}, False
    m = re.fullmatch(r"scripts/([^/]+)\.py", rel)
    if m:
        targets = _importers(index.graph, m.group(1))
        return {t for t in index.tests if index.names[t] & targets}, False
    if any(p.fullmatch(rel) for p in TS_PATTERNS):
        return set(), True
    return {t for t in index.tests if _text_hits(index.texts[t], rel)}, False


def select(changed: list[str], root: Path = ROOT) -> Selection:
    index = _cached_index(root)
    picked, ts, unmatched = set(), False, []
    for raw in changed:
        rel = _normalize(raw, root)
        tests, is_ts = _pick(rel, index)
        picked |= tests
        ts = ts or is_ts
        if not tests and not is_ts:
            unmatched.append(rel)
    return Selection(sorted(picked), ts, unmatched)


def changed_files(base, root):
    """`git diff --name-only {base}`와 추적 안 하는 파일. git이 실패하면 RuntimeError."""
    out = []
    for args in (["diff", "--name-only", base], ["ls-files", "--others", "--exclude-standard"]):
        proc = subprocess.run(["git"] + args, cwd=root, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError("git {} 실패: {}".format(" ".join(args), proc.stderr.strip()))
        out.extend(line for line in proc.stdout.splitlines() if line.strip())
    return list(dict.fromkeys(out))


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(prog="select_tests.py", description="바뀐 파일에서 닿는 시험 파일을 고른다")
    parser.add_argument("--base", default="HEAD", help="바뀐 파일을 견줄 git 판(인자 PATH가 없을 때, 기본 HEAD)")
    parser.add_argument("--run", action="store_true", help="고른 시험을 병렬 pytest로 돌리고 그 종료 코드로 끝낸다")
    parser.add_argument("paths", nargs="*", metavar="PATH")
    args = parser.parse_args(argv)
    if args.paths:
        changed = args.paths
    else:
        try:
            changed = changed_files(args.base, root)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 2
    sel = select(changed, root)
    for t in sel.tests:
        print(t)
    if sel.ts:
        print(TS_LINE)
    for f in sel.unmatched:
        print(UNMATCHED_LINE.format(f), file=sys.stderr)
    sys.stdout.flush()
    if not args.run or not sel.tests:
        return 0
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", "auto"] + sel.tests
    return subprocess.run(cmd, cwd=root).returncode


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
