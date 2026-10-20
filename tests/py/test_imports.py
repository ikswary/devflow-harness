"""스크립트 사이 import 그래프 시험.

`scripts/*.py`의 모든 `Import`·`ImportFrom` 노드 가운데 `scripts/`의 모듈을 가리키는
것으로 그래프를 만든다. 단언하는 것:
- 순환 0(실패 메시지에 고리를 `a → b → a` 꼴로 낸다).
- `scripts/kinds.py`가 있고 그 import가 표준 라이브러리뿐.
- 층 사이 import 순서: `scripts/*.py`가 모두 `LAYERS`의 한 층에 있고, 간선 a→b마다
  층(a) ≥ 층(b), 0·1층에서 나가는 간선은 아래 층으로만(같은 층 간선은 2·3층 안에서만).

`import_graph`·`find_cycles`·`layer_violations`는 판정자가 직접 불러 그래프와 고리를 볼 수 있게 모듈 수준 함수로 둔다.
"""
import ast
import sys
from pathlib import Path

from conftest import SCRIPTS, write


# 엔진 층: 0 등록표 / 1 라이브러리 / 2 검사·계산 / 3 표시
LAYERS = {
    "kinds": 0,
    "devflow_lib": 1,
    "task_set": 2, "spawn_children": 2, "exec": 2, "machine_check": 2, "apply_revision": 2, "eol_setup": 2,
    "board": 2, "screen": 2, "retry_diff": 2,
    "board_ascii": 3, "board_dash": 3, "collect": 3, "conventions": 3,
}
SAME_LAYER_FROM = 2   # 이 층부터 같은 층 간선을 허용한다(0·1층은 아래로만)


def module_names(scripts_dir):
    return {p.stem for p in Path(scripts_dir).glob("*.py")}


def imported_names(path):
    """파일 안의 모든 import가 가리키는 최상위 모듈 이름(함수 안 포함). 상대 import(`from . import x`)는 x를 센다."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"), filename=str(path))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module.split(".")[0])
            else:
                out.update(alias.name for alias in node.names)
    return out


def import_graph(scripts_dir=SCRIPTS):
    """{모듈: 그 모듈이 import하는 scripts/ 모듈의 집합}."""
    mods = module_names(scripts_dir)
    return {m: imported_names(Path(scripts_dir) / (m + ".py")) & mods for m in sorted(mods)}


def find_cycles(graph):
    """모든 단순 고리를 [a, b, …, a] 꼴로 돌려준다. 고리마다 이름이 가장 앞선 모듈에서 시작해 한 번만 낸다
    (엔진 모듈이 열몇 개라 다 따라가도 작다)."""
    cycles = []

    def walk(start, v, path):
        for w in sorted(graph.get(v, ())):
            if w == start:
                cycles.append(path + [start])
            elif w > start and w not in path:
                walk(start, w, path + [w])

    for start in sorted(graph):
        walk(start, start, [start])
    return sorted(cycles)


def format_cycles(cycles):
    return "\n".join(" → ".join(c) for c in cycles)


def outside_stdlib(path, scripts_dir=SCRIPTS):
    """파일의 import 가운데 표준 라이브러리가 아닌 이름(scripts/ 모듈 포함)."""
    names = imported_names(path)
    return sorted(n for n in names if n in module_names(scripts_dir) or n not in sys.stdlib_module_names)


def layer_violations(graph, layers):
    """층 순서를 거스르는 간선 [(a, b), …]: 층(a) < 층(b), 또는 a가 0·1층이고 층(a) == 층(b)."""
    out = []
    for a in sorted(graph):
        for b in sorted(graph[a]):
            la, lb = layers[a], layers[b]
            if la < lb or (la == lb and la < SAME_LAYER_FROM):
                out.append((a, b))
    return out


def format_edges(edges, layers):
    return "\n".join("{}({}층) → {}({}층)".format(a, layers[a], b, layers[b]) for a, b in edges)


def test_every_script_has_one_layer():
    mods = module_names(SCRIPTS)
    assert mods, "scripts/*.py가 없다"
    assert sorted(mods - set(LAYERS)) == [], "층 표 LAYERS에 없는 모듈 — LAYERS의 층에 넣는다"
    assert sorted(set(LAYERS) - mods) == [], "층 표 LAYERS에만 있고 scripts/에 없는 모듈"
    assert set(LAYERS.values()) <= {0, 1, 2, 3}


def test_scripts_follow_layer_order():
    graph = import_graph()
    # 그래프가 실제로 읽혔는지(빈 그래프면 거저 통과한다): 2층→1층, 3층→2층, 2층 안의 간선(5.2의 두 같은 층 간선)
    assert "devflow_lib" in graph["task_set"] and "board" in graph["board_ascii"], graph
    assert "screen" in graph["task_set"] and "board" in graph["exec"], graph
    bad = layer_violations(graph, LAYERS)
    assert bad == [], "층 순서를 거스르는 import:\n" + format_edges(bad, LAYERS)


def test_layer_violations_reports_upward_and_low_same_layer_edges(tmp_path):
    # 검출기 자체의 양성 대조: 3층 모듈을 2층 모듈이(함수 안에서) import하면 거스름, 1층 안의 간선도 거스름.
    # 2층 안의 간선과 아래로 가는 간선은 거스르지 않는다
    write(tmp_path / "base.py", "")
    write(tmp_path / "lib.py", "import base\nimport lib2\n")
    write(tmp_path / "lib2.py", "import base\n")
    write(tmp_path / "calc.py", "import lib\ndef f():\n    import view\n    import calc2\n")
    write(tmp_path / "calc2.py", "import lib\n")
    write(tmp_path / "view.py", "import calc\nimport base\n")
    layers = {"base": 0, "lib": 1, "lib2": 1, "calc": 2, "calc2": 2, "view": 3}
    graph = import_graph(tmp_path)
    assert graph["calc"] == {"lib", "view", "calc2"}, graph
    bad = layer_violations(graph, layers)
    assert bad == [("calc", "view"), ("lib", "lib2")]
    assert format_edges(bad, layers) == "calc(2층) → view(3층)\nlib(1층) → lib2(1층)"


def test_scripts_have_no_import_cycles():
    graph = import_graph()
    # 그래프가 실제로 읽혔는지(빈 그래프면 순환 0이 거저 통과한다): 모든 엔진이 쓰는 라이브러리로 가는 간선
    assert "devflow_lib" in graph["task_set"] and "board" in graph["board_ascii"], graph
    cycles = find_cycles(graph)
    assert cycles == [], "scripts/ 사이 import 고리:\n" + format_cycles(cycles)


def test_graph_counts_late_imports_and_reports_cycle(tmp_path):
    # 검출기 자체의 양성 대조: 함수 안 지연 import도 간선이고, 한 묶음에 고리가 둘이면 둘 다 낸다
    write(tmp_path / "a.py", "import os\nimport b\n")
    write(tmp_path / "b.py", "def f():\n    from c import x\n    import a\n    return x\n")
    write(tmp_path / "c.py", "def g():\n    import a as alias\n    return alias\n")
    write(tmp_path / "d.py", "import c\nfrom os import path\n")
    graph = import_graph(tmp_path)
    assert graph == {"a": {"b"}, "b": {"a", "c"}, "c": {"a"}, "d": {"c"}}
    assert find_cycles(graph) == [["a", "b", "a"], ["a", "b", "c", "a"]]
    assert format_cycles(find_cycles(graph)) == "a → b → a\na → b → c → a"


def test_outside_stdlib_flags_script_and_third_party(tmp_path):
    write(tmp_path / "board.py", "")
    write(tmp_path / "k.py", "import re\nfrom dataclasses import dataclass\n\ndef f():\n    import board\n    import yaml\n")
    assert outside_stdlib(tmp_path / "k.py", tmp_path) == ["board", "yaml"]


def test_kinds_imports_only_stdlib():
    path = SCRIPTS / "kinds.py"
    assert path.is_file(), "scripts/kinds.py 없음 — 등록표가 있어야 한다"
    assert outside_stdlib(path) == [], "kinds.py는 표준 라이브러리만 import한다(등록표가 엔진에 기대지 않게)"
