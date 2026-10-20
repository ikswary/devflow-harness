"""등록표 대조 시험 1~4.

등록표 `scripts/kinds.py`가 저장소의 다른 원천과 같은지 파일을 읽어 대조한다.
- 시험 1(a): `references/formats/task-file.md` 표의 `kind`·`block` 행 값 칸은 `references/registry/kinds.md`를 가리키고
  `KINDS`의 이름을 백틱으로 적지 않는다, `len(KINDS) == 17`
- 시험 1(b): `definition`의 집합 = `references/kinds/`의 파일 집합(양방향)
- 시험 1(c): 엔진(`scripts/*.py`, `kinds.py` 제외)의 kind 이름만으로 된 집합·목록·튜플 리터럴(2개 이상)과 kind 키만의
  사전 리터럴은 (파일 이름, 원소)가 허용 목록 `HOOK_LITERALS`에 있고, 허용 목록의 kind는 모두 훅이 있다
- 시험 1(d): 엔진의 kind 리터럴(docstring·주석 제외)마다 그 kind의 `engine_hooks`가 비어 있지 않다
- 시험 2(다): `references/formats/task-file.md` 표 첫 칸의 키 = `TASK_KEYS`의 이름(V-09. 생성 대신 대조)
- 시험 2: `writers`의 에이전트 이름 ⊆ `AGENTS`, `AGENTS` = `agents/*.md`(양방향), 이름마다 frontmatter `name`·`model`·`tools`가 같음
- 시험 2(나): 에이전트 정의 8의 틀 — frontmatter 다음 빈 줄 아닌 줄이 루트 줄 `플러그인 폴더:`, 판정자 둘은
  그다음 판 표지 `판 표지:`, 그다음 H1 `# devflow-harness:{이름} — {역할}`, `##` 차례가 「역할」·「읽을 것」·「역할 고유 규칙」·
  「반환에 덧붙일 것」, 「읽을 것」의 formats 파일 = `kinds.FORMATS_READERS`(작성자 여섯은 `writer`, 판정자는 자기 이름)
- 시험 3: `kinds.md_files()`의 파일마다(목차 `references/core/registry.md`와 절 파일 `references/registry/*.md`)
  작업 트리 바이트 = 생성 내용, `references/registry/`에 그 밖의 파일 없음
- 시험 4: TS 다섯 자리(`hooks/panel-map.ts` `WRITE_KINDS`·`FOLDED_STATES`·`STATUS_MARK` 키, `hooks/status-view.ts`
  `SHOWN_STATES`, `types/index.d.ts` `DashStatus`)와 `board_dash` 빈 counts의 `by_status` 키가 등록표와 같다.
  등록표에 순서가 있는 값(상태 튜플)과 대조하는 자리는 순서까지, 순서가 없는 자리(frozenset인 `CODE_DIR_KINDS`와 대조하는
  `WRITE_KINDS`, TS `Record`인 `STATUS_MARK`)는 중복 없는 집합으로 본다
- 시험 6(가): 공통 계약·formats(목차와 `references/formats/`)·역할 문서(`references/roles/`)에 위 층(kind 모듈·방법 문서·
  메인 단계 파일·진입·에이전트 정의)의 경로와 파일 이름이 없다
- 시험 6(라): 공통 파일(계약·formats 목차와 `references/formats/`·역할 문서·진입·`references/main/`·에이전트 정의)의
  kind 낱말 줄(`kind_terms`)이 `KIND_EXCEPTIONS`(경로, 줄 글의 일부, 예외 종류 E1~E5)로 한 줄에 한 항목씩만
  덮이고, 항목마다 꼭 한 줄을 덮으며, 예외 종류가 그 파일에 있을 수 있는 것
- 시험 7: `references/core/repeats.md` 행마다 원천 파일에 사본 문장이 있고 사본 파일에 `{사본 문장} [{사본 번호}]`가 있다
- 시험 5(가): kind 모듈 「자식 목록」 첫 줄 `자식 kind: …`의 집합 = 맡는 kind의 `children` 합집합, 모듈과 그 아래 파일이
  가리키는 다른 정의(`references/kinds/{정의}`·`{정의}.md`)는 등록표 간선(`EDGES`, 방향 없이)이 있는 짝만
- 시험 5(나): 모듈 첫 줄 `# {정의 이름} (…)`의 백틱 kind = 맡는 kind, `##` 차례가 4.4 틀, 꼬리표가 등록표 `run_judge`·`read_judge`로
  정한 것, 모듈 아래 파일은 첫 줄 `# {정의 이름}: {몫}`·다음 빈 줄 아닌 줄 `읽는 때: {조건}`
- 시험 5(다): 경우 파일(`main-order.md`·`run-check.md` 밖의 아래 파일)마다 모듈 본문에 그 경로가 있다
- 시험 6(나): kind 모듈과 그 아래 파일에 진입·단계 파일·에이전트 정의의 경로(`SKILL.md`·`skills/`·`references/main/`·`agents/`)가 없다
- 시험 6(다): 방법 문서(`references/practices/**`)에 위 층 경로(`references/kinds/`·`agents/`·`tasks/`·`tasks\\`)와 옛 어휘
  (`00_recon`·`게이트`·`결과 파일 형식`·`{요구사항|설계|구현|검증|기획} 블록`·`블록 담당자`·`뒤 블록`), frontmatter가 없다
- 방법 문서 독자 줄: `references/practices/*.md` 제목 다음 줄 `읽는 kind: …`의 백틱 kind = 그 문서를 「먼저 읽을 것」에 적은
  kind 모듈들이 맡는 kind, 적은 모듈이 없으면 `메인이 읽는다`로 시작(Q-07. 생성 대신 대조)
"""
import ast
import json
import os
import re
import subprocess
import sys

import board_dash
import kinds
from conftest import ROOT, SCRIPTS, write

FORMATS = ROOT / "references" / "core" / "formats.md"   # 목차

_KIND_NAMES = "|".join(re.escape(k) for k in sorted(kinds.KINDS, key=len, reverse=True))
KIND_TERM_RE = re.compile(
    r"(?:^|[^A-Za-z0-9_/\\.-])(?:" + _KIND_NAMES + r")(?:[^A-Za-z0-9_/\\-]|$)"
    r"|원인 분석|화면 설계|요구사항 개요|요구사항 상세|흐름별 검증|전체 검증|재검증|합치기|마무리|배포 계획|배포 실행|기획"
    r"|(?:질문|설계|구현|수정|변경|검증|배포) ?task")


def kind_terms(text):
    """kind 낱말이 든 줄의 (줄 번호, 줄 글)."""
    return [(n, line) for n, line in enumerate(text.split("\n"), 1) if KIND_TERM_RE.search(line)]


TASK_FILE = ROOT / kinds.FORMATS_DIR / "task-file.md"
REPEATS = ROOT / "references" / "core" / "repeats.md"
KIND_DIR = ROOT / "references" / "kinds"
AGENT_DIR = ROOT / "agents"
REGISTRY_DIR = ROOT / "references" / "registry"
REGEN = "python3 -B scripts/kinds.py --md-write"


def task_file_rows(key):
    """`task-file.md` 표에서 첫 칸이 `` `{key}` ``인 행들."""
    text = TASK_FILE.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.startswith("| `{}` |".format(key))]


def front_matter(path):
    """`---` 두 줄 사이의 `키: 값`(주석 줄 `#`과 빈 줄은 뺌)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", "{}: 첫 줄이 ---가 아님".format(path.name)
    end = lines.index("---", 1)
    meta = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def test_1a_formats_kind_rows_point_to_registry():
    for key in ("kind", "block"):
        rows = task_file_rows(key)
        assert len(rows) == 1, "task-file.md 표에 `{}` 행이 하나여야 함: {}".format(key, rows)
        value = rows[0].split("|")[2]
        named = sorted(k for k in kinds.KINDS if "`{}`".format(k) in value)
        assert named == [], "`{}` 행 값 칸에 kind 이름: {}".format(key, named)
        assert "`references/registry/kinds.md`" in value, "`{}` 행 값 칸이 등록표를 가리키지 않음: {}".format(key, value)
    assert len(kinds.KINDS) == 17


def test_2c_task_file_keys_are_task_keys():
    text = TASK_FILE.read_text(encoding="utf-8")
    keys = [k for line in text.splitlines() if line.startswith("| `")
            for k in re.findall(r"`([^`]+)`", line.split("|")[1])]
    names = [k for k, _, _ in kinds.TASK_KEYS]
    assert len(names) == 44
    assert sorted(keys) == sorted(names), "task-file.md 키 칸과 TASK_KEYS가 다름: {}".format(
        sorted(set(keys) ^ set(names)))


def test_1b_definitions_match_kind_files():
    entries = set(os.listdir(KIND_DIR))
    files = {e for e in entries if os.path.isfile(os.path.join(KIND_DIR, e))}
    assert len(files) == 14, sorted(files)
    definitions = {k.definition for k in kinds.KINDS.values()}
    assert definitions - files == set(), "등록표에만 있는 정의 파일"
    assert files - definitions == set(), "references/kinds/에만 있는 파일"
    # 모듈 아래 파일의 폴더(`{정의}/`)는 정의 파일 이름에서 `.md`를 뗀 것만
    folders = entries - files
    assert folders <= {d[:-len(".md")] for d in definitions}, sorted(folders - {d[:-3] for d in definitions})


def test_2_agents_match_writers_and_agent_files():
    writer_names = {w for k in kinds.KINDS.values() for w in k.writers if w != "main"}
    assert writer_names == {"requirements-writer", "cause-writer", "design-writer", "code-writer", "verify-writer",
                            "release-writer", "run-judge"}
    assert writer_names <= set(kinds.AGENTS)
    assert "read-judge" not in writer_names and "read-judge" in kinds.AGENTS

    files = {p.stem for p in AGENT_DIR.glob("*.md")}
    assert len(files) == 8, sorted(files)
    assert set(kinds.AGENTS) - files == set(), "등록표에만 있는 에이전트"
    assert files - set(kinds.AGENTS) == set(), "agents/에만 있는 정의 파일"

    for name, agent in kinds.AGENTS.items():
        meta = front_matter(AGENT_DIR / (name + ".md"))
        assert meta.get("name") == name, name
        assert meta.get("model") == agent.model, name
        assert tuple(t.strip() for t in meta.get("tools", "").split(",")) == agent.tools, name


AG_HEADINGS = ("역할", "읽을 것", "역할 고유 규칙", "반환에 덧붙일 것")   # 정본 4.5 틀의 `##` 차례
JUDGES = ("read-judge", "run-judge")
FORMAT_PATH_RE = re.compile(re.escape(kinds.FORMATS_DIR) + r"/([a-z-]+)\.md")


def ag_section(text, title):
    """`## {title}` 절의 줄들(다음 `## ` 앞까지)."""
    lines = text.splitlines()
    start = lines.index("## " + title) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def ag_problems(name, text):
    """시험 2(나)를 어긴 곳의 목록(빈 목록이면 통과)."""
    out = []
    lines = text.splitlines()
    end = lines.index("---", 1)
    rest = [line for line in lines[end + 1:] if line.strip()]
    want = ["플러그인 폴더:"] + (["판 표지:"] if name in JUDGES else []) + ["# devflow-harness:{} — ".format(name)]
    got = [line for line, head in zip(rest, want) if line.startswith(head)]
    if len(got) != len(want):
        out.append("{}: frontmatter 뒤 차례가 {}이 아님: {}".format(name, want, rest[:len(want)]))
    heads = h2(text)
    if tuple(heads) != AG_HEADINGS:
        out.append("{}: `##` 차례 {}".format(name, heads))
        return out
    named = FORMAT_PATH_RE.findall("\n".join(ag_section(text, "읽을 것")))
    reader = name if name in JUDGES else "writer"
    if sorted(named) != sorted(kinds.FORMATS_READERS[reader]):
        out.append("{}: 「읽을 것」 formats 파일 {} ≠ FORMATS_READERS[{}] {}".format(
            name, sorted(named), reader, sorted(kinds.FORMATS_READERS[reader])))
    return out


def test_2b_agent_frames_and_formats_files():
    files = sorted(AGENT_DIR.glob("*.md"))
    assert len(files) == 8, [p.name for p in files]
    assert [w for p in files for w in ag_problems(p.stem, p.read_text(encoding="utf-8"))] == []


def test_2b_detects_frame_and_formats_breaks():
    text = (AGENT_DIR / "run-judge.md").read_text(encoding="utf-8")
    assert ag_problems("run-judge", text) == []
    # 판 표지가 없는 판정자 정의
    broken = "\n".join(line for line in text.splitlines() if not line.startswith("판 표지:"))
    assert [w.split(":")[0] for w in ag_problems("run-judge", broken)] == ["run-judge"]
    # 「읽을 것」에서 formats 파일 하나를 뺌
    broken = text.replace(", `${CLAUDE_PLUGIN_ROOT}/references/formats/return.md`", "")
    assert broken != text
    assert [w for w in ag_problems("run-judge", broken) if "formats 파일" in w]
    # `##` 차례가 바뀜
    broken = text.replace("## 반환에 덧붙일 것", "## 오류 처리")
    assert [w for w in ag_problems("run-judge", broken) if "차례" in w]


def run_kinds(*args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", str(SCRIPTS / "kinds.py")] + list(args), capture_output=True,
                          cwd=ROOT, env=env, timeout=60)


def test_3_registry_files_are_generated_output():
    files = kinds.md_files()
    for rel, text in files.items():
        path = ROOT / rel
        assert path.is_file(), "{} 없음 — `{}`로 만든다".format(rel, REGEN)
        assert path.read_bytes() == text.encode("utf-8"), "{}가 생성 내용과 다름 — `{}`로 다시 만든다".format(rel, REGEN)
    extra = sorted(p.relative_to(ROOT).as_posix() for p in REGISTRY_DIR.rglob("*")
                   if p.relative_to(ROOT).as_posix() not in files)
    assert extra == [], "references/registry/에 생성하지 않은 파일: {} — 지우고 `{}`로 다시 만든다".format(extra, REGEN)


def test_3_md_prints_index():
    proc = run_kinds("--md")
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout == kinds.md_files()["references/core/registry.md"].encode("utf-8")


def test_3_no_argument_prints_usage_and_exits_2():
    proc = run_kinds()
    assert proc.returncode == 2
    assert proc.stdout == b""
    assert "사용법: python3 scripts/kinds.py --md" in proc.stderr.decode("utf-8")


def test_plugin_version_reads_manifest_or_question_mark(tmp_path):
    write(tmp_path / ".claude-plugin" / "plugin.json", json.dumps({"name": "x", "version": "9.8.7"}))
    assert kinds.plugin_version(str(tmp_path)) == "9.8.7"
    assert kinds.plugin_version(str(tmp_path / "없음")) == "?"
    write(tmp_path / "num" / ".claude-plugin" / "plugin.json", json.dumps({"version": 3}))
    assert kinds.plugin_version(str(tmp_path / "num")) == "?"


# ---------------------------------------------------------------------------
# 시험 1(c)(d): 엔진 코드의 kind 리터럴

# K-19 훅 분기의 kind 리터럴(파일 이름, 원소). 이 밖의 kind 집합 리터럴은 등록표 파생으로 바꾼다
HOOK_LITERALS = {
    ("board.py", frozenset({"wrap-up", "flow-verify"})),                                 # is_ready
    ("board.py", frozenset({"flow-verify", "reverify"})),                                # 받아오기 먼저
    ("board.py", frozenset({"wrap-up", "deploy-plan", "deploy-exec", "full-verify"})),   # 흐름별 검증의 뒤 task
    ("board.py", frozenset({"deploy-plan", "deploy-exec"})),                             # 마무리의 뒤 task
    ("board.py", frozenset({"deploy-plan", "deploy-exec", "wrap-up"})),                  # 마무리가 기다리지 않는 task
    ("board.py", frozenset({"fix", "reverify"})),                                        # 합칠 흐름의 수정·재검증
    ("devflow_lib.py", frozenset({"flow-verify", "full-verify"})),                       # 자식 수정 세대 0
    ("screen.py", frozenset({"wrap-up", "merge"})),                                      # 보류로 남김 줄
    ("spawn_children.py", frozenset({"fix", "reverify"})),                               # over-cap 백로그
    ("task_set.py", frozenset({"merge", "wrap-up", "deploy-exec"})),                     # auto_freeze 지점(사전 키)
}


def engine_files():
    files = sorted(p for p in SCRIPTS.glob("*.py") if p.name != "kinds.py")
    assert files, "scripts/*.py가 없음: {}".format(SCRIPTS)
    return files


def kind_collections(path):
    """[(줄, 원소 frozenset)]: 원소가 모두 kind 이름인 2개 이상의 집합·목록·튜플 리터럴과 키가 모두 kind 이름인 사전 리터럴."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            items = node.elts
            if len(items) < 2:
                continue
        elif isinstance(node, ast.Dict):
            items = node.keys
            if not items or any(k is None for k in items):
                continue
        else:
            continue
        if all(isinstance(e, ast.Constant) and isinstance(e.value, str) and e.value in kinds.KINDS for e in items):
            out.append((node.lineno, frozenset(e.value for e in items)))
    return out


def kind_constants(path):
    """[(줄, kind 이름)]: kind 이름과 같은 문자열 상수. 문장 자리에 홀로 선 문자열(docstring)은 뺀다(주석은 AST에 없다)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    loose = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in kinds.KINDS and id(n) not in loose]


def test_1c_engine_kind_collections_are_hook_literals_only():
    outside = ["scripts/{}:{} {}".format(p.name, line, sorted(items))
               for p in engine_files() for line, items in kind_collections(p) if (p.name, items) not in HOOK_LITERALS]
    assert outside == [], "허용 목록 밖의 kind 집합 리터럴(등록표 파생으로 바꾼다):\n" + "\n".join(outside)
    no_hooks = sorted({k for _, items in HOOK_LITERALS for k in items if not kinds.KINDS[k].engine_hooks})
    assert no_hooks == [], "허용 목록에 engine_hooks가 빈 kind: {}".format(no_hooks)


def test_1c_detects_a_kind_set_literal(tmp_path):
    # 양성 대조: 수집 함수가 집합·사전 리터럴을 실제로 찾는다(찾지 못해 빈 목록이 되는 잘못을 막는다)
    sample = tmp_path / "sample.py"
    sample.write_text('A = {"implementation", "fix"}\nB = {"merge": 1, "wrap-up": 2}\nC = ("fix",)\nD = ("fix", "x")\n',
                      encoding="utf-8")
    assert kind_collections(sample) == [(1, frozenset({"implementation", "fix"})), (2, frozenset({"merge", "wrap-up"}))]


def test_1d_every_engine_kind_literal_has_engine_hooks():
    bad = ["scripts/{}:{} {}".format(p.name, line, name)
           for p in engine_files() for line, name in kind_constants(p) if not kinds.KINDS[name].engine_hooks]
    assert bad == [], "engine_hooks가 빈 kind의 리터럴(등록표 파생으로 바꾼다):\n" + "\n".join(bad)


def test_1d_skips_docstrings_but_counts_code(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text('"""design"""\ndef f(k):\n    """question"""\n    # brief\n    return k == "design"\n',
                      encoding="utf-8")
    assert kind_constants(sample) == [(5, "design")]


# ---------------------------------------------------------------------------
# 시험 4: 대시보드 TS와 board_dash가 등록표와 같다

PANEL_MAP = ROOT / "hooks" / "panel-map.ts"
STATUS_VIEW = ROOT / "hooks" / "status-view.ts"
TYPES = ROOT / "types" / "index.d.ts"


def ts_match(path, pattern):
    """파일에서 정의 하나를 정규식으로 찾아 그 묶음을 돌려준다(없거나 둘 이상이면 이유를 말하고 실패)."""
    found = re.findall(pattern, path.read_text(encoding="utf-8"), re.M | re.S)
    assert len(found) == 1, "{}: 정의를 하나 찾아야 함(찾은 수 {}): {}".format(path.relative_to(ROOT), len(found), pattern)
    return found[0]


def quoted(text):
    return re.findall(r"'([^']*)'", text)


def test_4_panel_map_write_kinds_is_code_dir_kinds():
    values = quoted(ts_match(PANEL_MAP, r"^const WRITE_KINDS = \[([^\]]*)\]"))
    assert len(values) == len(set(values)), values
    assert set(values) == kinds.CODE_DIR_KINDS


def test_4_panel_map_folded_states_is_closed_statuses():
    values = quoted(ts_match(PANEL_MAP, r"^const FOLDED_STATES = \[([^\]]*)\]"))
    assert tuple(values) == kinds.CLOSED_STATUSES


def test_4_panel_map_status_mark_keys_are_statuses():
    body = ts_match(PANEL_MAP, r"^export const STATUS_MARK: Record<DashStatus, string> = \{(.*?)^\}")
    keys = re.findall(r"([^\s,:'{}]+)\s*:", body)
    assert len(keys) == len(set(keys)), keys
    assert set(keys) == set(kinds.STATUSES)


def test_4_status_view_shown_states_is_open_statuses():
    values = quoted(ts_match(STATUS_VIEW, r"^const SHOWN_STATES = \[([^\]]*)\]"))
    assert tuple(values) == kinds.OPEN_STATUSES


def test_4_types_dash_status_is_statuses():
    values = quoted(ts_match(TYPES, r"^export type DashStatus = ([^\n]*)$"))
    assert tuple(values) == kinds.STATUSES


def test_4_board_dash_empty_counts_by_status_keys_are_statuses():
    assert tuple(board_dash.empty_counts()["by_status"]) == kinds.STATUSES


# ---------------------------------------------------------------------------
# 시험 6(가): 공통 층(L0a·L0b·L1)은 위 층 경로·파일 이름을 쓰지 않는다

UPPER_PATHS = ("references/kinds/", "references/practices/", "references/main/", "skills/", "agents/", "SKILL.md")


def common_layer_files():
    """L0a 계약, L0b formats 목차와 절 파일, L1 역할 문서. registry·repeats·kinds.py는 데이터라 뺀다."""
    files = [ROOT / "references" / "core" / "contract.md", FORMATS]
    files += sorted((ROOT / kinds.FORMATS_DIR).glob("*.md")) + sorted((ROOT / "references" / "roles").glob("*.md"))
    return files


def upper_names():
    """kind 정의 파일 14와 방법 문서(`references/practices/`·`stacks/`)의 파일 이름."""
    names = {k.definition[:-3] for k in kinds.KINDS.values()}
    practices = ROOT / "references" / "practices"
    names |= {p.stem for p in practices.glob("*.md")} | {p.stem for p in (practices / "stacks").glob("*.md")}
    return names


def upper_refs(text, names):
    """[(줄, 걸린 글)]: 위 층 경로 조각, 또는 앞에 경로 글자(`/`·`\\`·이름 글자)가 없는 `{이름}.md`."""
    name_re = re.compile(r"(?<![A-Za-z0-9_/\\.-])(" + "|".join(sorted(map(re.escape, names))) + r")\.md\b")
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        found += [(n, p) for p in UPPER_PATHS if p in line]
        found += [(n, m.group(0)) for m in name_re.finditer(line)]
    return found


def test_6a_common_layer_has_no_upper_layer_paths():
    files = common_layer_files()
    rels = {p.relative_to(ROOT).as_posix() for p in files}
    assert {"references/core/contract.md", "references/core/formats.md", "references/roles/writer.md",
            "references/roles/agent.md"} <= rels, sorted(rels)
    assert {"{}/{}.md".format(kinds.FORMATS_DIR, n) for n, _ in kinds.FORMAT_FILES} <= rels, sorted(rels)
    names = upper_names()
    assert len(names) >= 14 + 11, sorted(names)
    hits = {p.relative_to(ROOT).as_posix(): upper_refs(p.read_text(encoding="utf-8"), names) for p in files}
    assert {k: v for k, v in hits.items() if v} == {}


def test_6a_detects_upper_layer_paths():
    names = upper_names()
    assert upper_refs("메인은 `SKILL.md` 6절", names) == [(1, "SKILL.md")]
    assert upper_refs("(`change.md`)", names) == [(1, "change.md")]
    assert upper_refs("`references/kinds/merge.md`", names) == [(1, "references/kinds/")]
    assert upper_refs("spec\\brief.md, `ui\\rules.md`, design-doc 꼴", names) == []



# ---------------------------------------------------------------------------
# 시험 6(라): 공통 파일의 kind 낱말 줄은 예외 목록으로만
#
# 예외 종류: E1 L3의 kind를 고르는 표(start.md 0절 시작 task 표와 그 덧붙임, new-task.md 5절 표) /
# E2 L3·AG의 가리킴 한 줄(kind와 모듈 파일만 말함) / E3 AG의 정체 줄(frontmatter description, H1, 「역할」의 맡는 kind 줄) /
# E4 formats의 꼴 안 한 마디(키·절·값을 쓰거나 읽는 kind를 밝히는 괄호, 2절 배치의 파일 설명, journal 「일」 값,
# 틀의 예시 값) / E5 kind 글자와 같은 다른 이름(에이전트 줄임 `design`, `--ready` 절 이름 「재검증 없는 수정」).
# 항목 = (경로, 줄 글의 일부, 예외 종류). 항목 하나는 꼭 한 줄을 덮고, kind 낱말 줄 하나는 꼭 한 항목에 덮인다.

KIND_EXCEPTIONS = [
    # E4: formats의 꼴 안 한 마디
    ("references/formats/prompt.md", "화면 설계는 「건드릴 파일」의 ui 정본과 와이어프레임", "E4"),
    ("references/formats/result-file.md", "(기획·요구사항·화면 설계·설계·원인 분석. 결정 목록", "E4"),
    ("references/formats/result-file.md", "- kind: implementation", "E4"),
    ("references/formats/result-file.md", "(원인 분석의 수정안, 검증의 「묻는다」 지적, 설계의 배포 선택지)", "E4"),
    ("references/formats/run-files.md", "{일: 합치기/재개/한도 정지/값 변경/폴더 생성/메모}", "E4"),
    # 절 이름 「합치기 관례」와 「UI 규약」 절을 읽는 kind. 읽는 kind도 꼴 안 한 마디로 받는다(task-file.md `exported_commit`은
    # T052가 kind 낱말 없이 고쳐 이 목록에 없다. T052 판정 권장 5)
    ("references/formats/run-files.md", "화면 설계 task가 읽는다", "E4"),
    ("references/formats/run-folder.md", "잠금·합치기 관례 (메인)", "E4"),
    ("references/formats/run-folder.md", "기획 정본 (개요 뒤·상세 앞", "E4"),
    ("references/formats/run-folder.md", "화면 정본 (UI 규약, 묶음별 화면 설계서", "E4"),
    ("references/formats/run-folder.md", "와이어프레임 (화면 설계 작성자", "E4"),
    ("references/formats/run-folder.md", "변경 task가 쓴 정본의 고친 판", "E4"),
    ("references/formats/task-file.md", "재검증이 낸 수정은 그 재검증이 의존하는 수정의 최대 세대", "E4"),
    ("references/formats/task-file.md", "이 task의 답을 반영하는 변경 task가 아직 안 끝남", "E4"),
    ("references/formats/task-file.md", "(합치기·마무리·배포 실행) 지금 단계", "E4"),
    ("references/formats/task-file.md", "| `exported_commit` | (`wrap-up`)", "E4"),
    ("references/formats/task-file.md", "| `partial_flow` | (`flow-verify`)", "E4"),
    ("references/formats/task-file.md", "| `deploy_outcome`, `deployed_commit` | (`deploy-exec`)", "E4"),
    # E5: kind 글자와 같은 다른 이름
    ("references/formats/names.md", "`design`(devflow-harness:design-writer)", "E5"),
    ("references/main/loop.md", "「재검증 없는 수정」이 있으면", "E5"),
    # E1: L3의 kind를 고르는 표
    ("references/main/new-task.md", "| 변경 | 계기", "E1"),
    ("references/main/new-task.md", "| 합치기 | 그 흐름 브랜치의 커밋 전부", "E1"),
    ("references/main/new-task.md", "| 원인 분석(실행 도중 원인 모르는 실패)", "E1"),
    ("references/main/new-task.md", "| 받아오기 충돌·실패의 수정(`fix`)", "E1"),
    ("references/main/new-task.md", "| 「묻는다」 지적의 수정(답을 받은 뒤)과 그 재검증", "E1"),
    ("references/main/new-task.md", "| 배포 다시 계획(`deploy-plan`, 환경마다 하나)", "E1"),
    ("references/main/new-task.md", "| 기획(`brief`, 흐름 없음)", "E1"),
    ("references/main/new-task.md", "| 화면 설계(`ui-design`)", "E1"),
    ("references/main/start.md", "| 새 기능, 기능 변경 |", "E1"),
    ("references/main/start.md", "| 버그 | 질문 → 원인 분석", "E1"),
    ("references/main/start.md", "| 배포만(올릴 커밋이 이미 개발 기준 브랜치에 있고", "E1"),
    ("references/main/start.md", "| 백로그 task 처리 |", "E1"),
    ("references/main/start.md", "- 배포만·백로그 처리는 질문 task 없이 시작한다", "E1"),
    ("references/main/start.md", "- **섞인 요청**", "E1"),
    # E3: 에이전트 정의의 정체 줄
    ("agents/cause-writer.md", "description: ", "E3"),
    ("agents/cause-writer.md", "# devflow-harness:cause-writer — 원인 분석 작성자", "E3"),
    ("agents/cause-writer.md", "- `question`(버그로 시작하는 실행)", "E3"),
    ("agents/cause-writer.md", "- `root-cause` →", "E3"),
    ("agents/code-writer.md", "description: ", "E3"),
    ("agents/code-writer.md", "- `implementation`, `fix` →", "E3"),
    ("agents/code-writer.md", "- `merge`(충돌 해결) →", "E3"),
    ("agents/design-writer.md", "description: ", "E3"),
    ("agents/design-writer.md", "- `question`(설계로 시작하는 요청의 질문", "E3"),
    ("agents/design-writer.md", "- `ui-design` →", "E3"),
    ("agents/design-writer.md", "- `design` →", "E3"),
    ("agents/design-writer.md", "- `change`(화면·설계 정본) →", "E3"),
    ("agents/release-writer.md", "description: ", "E3"),
    ("agents/release-writer.md", "- `wrap-up`: 앞 절반", "E3"),
    ("agents/release-writer.md", "- `deploy-plan`: 배포 계획 전체", "E3"),
    ("agents/release-writer.md", "- `deploy-exec`: 6번 배포 기록", "E3"),
    ("agents/requirements-writer.md", "description: ", "E3"),
    ("agents/requirements-writer.md", "- `question` →", "E3"),
    ("agents/requirements-writer.md", "- `brief` →", "E3"),
    ("agents/requirements-writer.md", "- `req-overview` →", "E3"),
    ("agents/requirements-writer.md", "- `req-detail` →", "E3"),
    ("agents/requirements-writer.md", "- `change`(기획·요구사항 정본) →", "E3"),
    ("agents/run-judge.md", "description: ", "E3"),
    ("agents/verify-writer.md", "description: ", "E3"),
    ("agents/verify-writer.md", "머리 파일이 정한 task 하나를 한다(`flow-verify`, `full-verify`, `reverify`)", "E3"),
    # E2: 가리킴 한 줄
    ("agents/run-judge.md", "- 맡은 kind의 실행 판정 파일(있으면)", "E2"),
]
_L3 = ("skills/devflow-harness/SKILL.md", "references/main/")
# 예외 종류마다 그 줄이 있을 수 있는 공통 파일. 경로 끝 `/`는 그 폴더
EXCEPTION_PLACES = {
    "E1": ("references/main/start.md", "references/main/new-task.md"),
    "E2": _L3 + ("agents/",),
    "E3": ("agents/",),
    "E4": ("references/core/formats.md", kinds.FORMATS_DIR + "/"),
    "E5": ("references/", "skills/", "agents/"),
}


def kind_common_files():
    """정본 4.9의 공통 파일: L0a, L0b(formats 목차·`references/formats/`), L1(`references/roles/`), L3(진입·
    `references/main/`), AG(`agents/`). registry·repeats·kinds.py(데이터)와 L2·L2m·docs·설계 요약은 밖."""
    rels = ["references/core/contract.md", "references/core/formats.md", "skills/devflow-harness/SKILL.md"]
    for folder in (kinds.FORMATS_DIR, "references/roles", "references/main", "agents"):
        rels += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).glob("*.md"))
    return rels


def _in_place(rel, places):
    return any(rel == p or (p.endswith("/") and rel.startswith(p)) for p in places)


def kind_exception_problems(texts, exceptions):
    """texts = {경로: 글}. kind 낱말 줄과 예외 항목의 어긋남(덮이지 않은 줄, 둘 이상에 덮인 줄, 한 줄을 덮지 않는 항목,
    종류가 E1~E5가 아니거나 그 종류가 있을 수 없는 파일의 항목)."""
    lines = {(rel, n): line for rel, text in texts.items() for n, line in kind_terms(text)}
    out = []
    covered = {}
    for i, (rel, part, kind) in enumerate(exceptions):
        if kind not in EXCEPTION_PLACES:
            out.append("항목 {} {} `{}`: 예외 종류 `{}`가 E1~E5가 아님".format(i, rel, part, kind))
        elif not _in_place(rel, EXCEPTION_PLACES[kind]):
            out.append("항목 {} {} `{}`: {}는 이 파일에 둘 수 없음".format(i, rel, part, kind))
        hit = [key for key, line in lines.items() if key[0] == rel and part in line]
        if len(hit) != 1:
            out.append("항목 {} {} `{}`: 덮는 kind 낱말 줄이 {}개(1개여야 함)".format(i, rel, part, len(hit)))
        for key in hit:
            covered.setdefault(key, []).append(i)
    for (rel, n), line in sorted(lines.items()):
        k = len(covered.get((rel, n), []))
        if k != 1:
            out.append("{}:{}: kind 낱말 줄이 예외 항목 {}개에 덮임 — {}".format(rel, n, k, line.strip()[:60]))
    return out


def test_6d_common_files_use_kind_terms_only_in_listed_exceptions():
    rels = kind_common_files()
    assert {"references/core/contract.md", "references/main/start.md", "agents/run-judge.md",
            "references/roles/judge.md", kinds.FORMATS_DIR + "/task-file.md"} <= set(rels), rels
    texts = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in rels}
    assert kind_exception_problems(texts, KIND_EXCEPTIONS) == []
    assert len({(rel, part) for rel, part, _ in KIND_EXCEPTIONS}) == len(KIND_EXCEPTIONS)


def test_6d_detects_new_kind_term_missing_entry_and_misplaced_kind():
    texts = {"references/core/contract.md": "# 계약\n본문\n", "agents/x.md": "description: \"합치기 task를 맡는다\"\n"}
    good = [("agents/x.md", "description: ", "E3")]
    assert kind_exception_problems(texts, good) == []
    texts["references/core/contract.md"] = "# 계약\n본문은 merge 뒤에\n"
    assert kind_exception_problems(texts, good) == [
        "references/core/contract.md:2: kind 낱말 줄이 예외 항목 0개에 덮임 — 본문은 merge 뒤에"]
    texts["references/core/contract.md"] = "# 계약\n본문\n"
    assert kind_exception_problems(texts, []) == [
        "agents/x.md:1: kind 낱말 줄이 예외 항목 0개에 덮임 — description: \"합치기 task를 맡는다\""]
    assert kind_exception_problems(texts, good + [("agents/x.md", "없는 글", "E3")]) == [
        "항목 1 agents/x.md `없는 글`: 덮는 kind 낱말 줄이 0개(1개여야 함)"]
    assert kind_exception_problems(texts, [("agents/x.md", "description: ", "E4")]) == [
        "항목 0 agents/x.md `description: `: E4는 이 파일에 둘 수 없음"]
    assert kind_exception_problems(texts, [("agents/x.md", "description: ", "E9")]) == [
        "항목 0 agents/x.md `description: `: 예외 종류 `E9`가 E1~E5가 아님"]
    assert kind_exception_problems(texts, good * 2)[-1] == (
        "agents/x.md:1: kind 낱말 줄이 예외 항목 2개에 덮임 — description: \"합치기 task를 맡는다\"")

# ---------------------------------------------------------------------------
# 시험 7: 반복 목록의 사본

def repeat_rows():
    """`repeats.md` 표의 (사본 번호, 원천 위치, 사본 위치, 사본 문장)."""
    rows = []
    for line in REPEATS.read_text(encoding="utf-8").splitlines():
        if line.startswith("| RP-"):
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            assert len(cells) == 4, line
            rows.append(tuple(cells))
    return rows


def test_7_repeats_copies_match_sources():
    rows = repeat_rows()
    assert rows, "repeats.md에 행이 없음"
    for rid, source, copy, sentence in rows:
        assert re.fullmatch(r"RP-\d{2}", rid) and sentence, rid
        source_text = (ROOT / source.partition("#")[0]).read_text(encoding="utf-8")
        copy_text = (ROOT / copy.partition("#")[0]).read_text(encoding="utf-8")
        assert sentence in source_text, "{}: 원천 {}에 사본 문장이 없음".format(rid, source)
        assert "{} [{}]".format(sentence, rid) in copy_text, "{}: 사본 {}에 `{{사본 문장}} [{}]`이 없음".format(
            rid, copy, rid)


# ---------------------------------------------------------------------------
# 시험 5(가)(나)(다)·6(나): kind 모듈 틀

MODULE_HEADINGS = ("먼저 읽을 것", "하는 일", "승인 화면", "자식 목록", "자식 행 계약", "자체 검증")
# 틀의 `##` 가운데 그 모듈에 없어도 되는 것. 합치기는 메인이 결과 파일을 쓰며 승인 화면을 채운다(메인 순서 2)
OPTIONAL_HEADINGS = {"merge.md": {"승인 화면"}}
SUB_EXEMPT = ("main-order.md", "run-check.md")   # 진입·에이전트 정의가 가리키는 아래 파일(4.10)
L3_AG_PATHS = ("SKILL.md", "skills/", "references/main/", "agents/")
CHILDREN_RE = re.compile(r"자식 kind: (없음|`[a-z-]+`(?:, `[a-z-]+`)*)\Z")


def module_files():
    return sorted(p for p in KIND_DIR.glob("*.md") if p.is_file())


def sub_files(definition):
    return sorted((KIND_DIR / definition[:-len(".md")]).glob("*.md"))


def kinds_of(definition):
    return [n for n, k in kinds.KINDS.items() if k.definition == definition]


def unfenced(text):
    """울타리(```) 밖의 줄들."""
    out, fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        if not fence:
            out.append(line)
    return out


def h2(text):
    return [line[3:].strip() for line in unfenced(text) if line.startswith("## ")]


def definition_name(text):
    """모듈 첫 줄 `# {정의 이름} (…)`의 정의 이름."""
    m = re.match(r"# (\S[^(:]*?) \(.*\)\Z", text.splitlines()[0])
    assert m, "첫 줄이 `# {정의 이름} (…)`이 아님: " + text.splitlines()[0]
    return m.group(1)


def expected_tag(names):
    """4.4 꼬리표: run_judge가 하나라도 always면 `실행 판정 + `, read_judge가 모두 always면 `읽기 판정`, 하나라도
    conditional이면 `읽기 판정: 조건`."""
    ks = [kinds.KINDS[n] for n in names]
    head = "실행 판정 + " if any(k.run_judge == "always" for k in ks) else ""
    if all(k.read_judge == "always" for k in ks):
        return "(" + head + "읽기 판정)"
    assert any(k.read_judge == "conditional" for k in ks), names
    return "(" + head + "읽기 판정: 조건)"


def children_line(text):
    """「자식 목록」 절의 첫 줄(빈 줄 뺌)."""
    lines = unfenced(text)
    start = lines.index("## 자식 목록") + 1
    return next(line for line in lines[start:] if line.strip())


def children_kinds(line):
    m = CHILDREN_RE.match(line)
    assert m, "「자식 목록」 첫 줄이 `자식 kind: …` 꼴이 아님: " + line
    return set() if m.group(1) == "없음" else set(re.findall(r"`([a-z-]+)`", line))


def other_definitions(text, own):
    """글이 가리키는 다른 정의 파일 이름(`references/kinds/{정의}.md`·`references/kinds/{정의}/`·`{정의}.md`)."""
    stems = sorted({k.definition[:-3] for k in kinds.KINDS.values()}, key=len, reverse=True)
    alt = "|".join(map(re.escape, stems))
    found = set(re.findall(r"references/kinds/(" + alt + r")(?:\.md|/)", text))
    found |= set(re.findall(r"(?<![A-Za-z0-9_/\\.-])(" + alt + r")\.md\b", text))
    return {s + ".md" for s in found} - {own}


def edge_between(def_a, def_b):
    a, b = set(kinds_of(def_a)), set(kinds_of(def_b))
    return any((x, y) in kinds.EDGES or (y, x) in kinds.EDGES for x in a for y in b)


def module_problems(path):
    """시험 5(가)(나)(다)·6(나)를 어긴 곳의 목록(빈 목록이면 통과)."""
    text = path.read_text(encoding="utf-8")
    definition = path.name
    names = kinds_of(definition)
    out = []
    # 5(가): 자식 목록 첫 줄 = children 합집합
    want = {c for n in names for c in kinds.KINDS[n].children}
    try:
        got = children_kinds(children_line(text))
        if got != want:
            out.append("5(가) {}: 자식 kind {} ≠ 등록표 {}".format(definition, sorted(got), sorted(want)))
    except (AssertionError, ValueError, StopIteration) as e:
        out.append("5(가) {}: {}".format(definition, e))
    # 5(나): 첫 줄, `##` 차례, 꼬리표
    try:
        name = definition_name(text)
    except AssertionError as e:
        out.append("5(나) {}: {}".format(definition, e))
        name = None
    first_kinds = set(re.findall(r"`([a-z-]+)`", text.splitlines()[0]))
    if first_kinds != set(names):
        out.append("5(나) {}: 첫 줄 kind {} ≠ 맡는 kind {}".format(definition, sorted(first_kinds), sorted(names)))
    heads = h2(text)
    tag = "자체 검증 " + expected_tag(names)
    if not heads or heads[-1] != tag:
        out.append("5(나) {}: 마지막 `##`가 `{}`가 아님: {}".format(definition, tag, heads[-1:] or "없음"))
    base = heads[:-1] + ["자체 검증"] if heads else []
    allowed = OPTIONAL_HEADINGS.get(definition, set())
    if base != [h for h in MODULE_HEADINGS if h in base] or set(MODULE_HEADINGS) - set(base) - allowed:
        out.append("5(나) {}: `##` 차례 {}".format(definition, heads))
    texts = {definition: text}
    for sub in sub_files(definition):
        rel = "references/kinds/{}/{}".format(definition[:-3], sub.name)
        sub_text = sub.read_text(encoding="utf-8")
        texts[rel] = sub_text
        lines = sub_text.splitlines()
        if name is None or not lines or not lines[0].startswith("# {}: ".format(name)):
            out.append("5(나) {}: 첫 줄이 `# {}: {{몫}}`이 아님".format(rel, name))
        rest = [line for line in lines[1:] if line.strip()]
        if not rest or not re.match(r"읽는 때: \S", rest[0]):
            out.append("5(나) {}: 첫 줄 다음 빈 줄 아닌 줄이 `읽는 때: {{조건}}`이 아님".format(rel))
        # 5(다): 경우 파일은 모듈 본문이 경로를 적는다
        if sub.name not in SUB_EXEMPT and rel not in text:
            out.append("5(다) {}: 모듈 본문에 경로가 없음".format(rel))
    for rel, body in texts.items():
        # 5(가) R4: 다른 정의는 간선이 있는 짝만
        for other in sorted(other_definitions(body, definition)):
            if not edge_between(definition, other):
                out.append("5(가) {}: 간선 밖 정의 `{}`".format(rel, other))
        # 6(나) R1: 위 층 경로 없음
        for n, line in enumerate(body.splitlines(), 1):
            out += ["6(나) {}:{}: `{}`".format(rel, n, p) for p in L3_AG_PATHS if p in line]
    return out


def all_module_problems(label):
    files = module_files()
    assert len(files) == 14, [p.name for p in files]
    subs = [s for p in files for s in sub_files(p.name)]
    assert len(subs) >= 14, subs   # main-order 아홉, 경우 파일, run-check
    return [w for p in files for w in module_problems(p) if w.startswith(label + " ")]


def test_5a_children_line_and_cross_module_names_follow_registry():
    assert all_module_problems("5(가)") == []


def test_5b_module_and_sub_file_frames():
    assert all_module_problems("5(나)") == []


def test_5c_module_points_to_each_case_file():
    assert all_module_problems("5(다)") == []


def test_6b_kind_modules_have_no_entry_main_or_agent_paths():
    assert all_module_problems("6(나)") == []


def test_5_detects_frame_breaks(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "KIND_DIR", tmp_path)
    good = ("# 배포 계획 task (`deploy-plan`)\n\n## 먼저 읽을 것\n없음\n\n## 하는 일\n경우 파일 `references/kinds/deploy-plan/x.md`.\n\n"
            "## 승인 화면\n- 없음\n\n## 자식 목록\n자식 kind: `deploy-exec`\n\n## 자식 행 계약\n없음\n\n## 자체 검증 (읽기 판정)\n1. 가\n")
    (tmp_path / "deploy-plan").mkdir()
    write(tmp_path / "deploy-plan" / "x.md", "# 배포 계획 task: 경우\n\n읽는 때: 그때.\n")
    write(tmp_path / "deploy-plan.md", good)
    assert module_problems(tmp_path / "deploy-plan.md") == []
    write(tmp_path / "deploy-plan.md", good.replace("자식 kind: `deploy-exec`", "자식 kind: `deploy-exec`, `fix`"))
    assert [w[:5] for w in module_problems(tmp_path / "deploy-plan.md")] == ["5(가) "]
    write(tmp_path / "deploy-plan.md", good.replace("## 자체 검증 (읽기 판정)", "## 자체 검증"))
    assert [w[:5] for w in module_problems(tmp_path / "deploy-plan.md")] == ["5(나) "]
    write(tmp_path / "deploy-plan.md", good.replace("1. 가", "1. `SKILL.md` 3절, `references/kinds/merge.md`"))
    assert sorted(w[:5] for w in module_problems(tmp_path / "deploy-plan.md")) == ["5(가) ", "6(나) "]
    write(tmp_path / "deploy-plan.md", good.replace("`references/kinds/deploy-plan/x.md`", "경우 파일"))
    assert [w[:5] for w in module_problems(tmp_path / "deploy-plan.md")] == ["5(다) "]
    write(tmp_path / "deploy-plan.md", good)
    write(tmp_path / "deploy-plan" / "x.md", "# 배포 계획 task: 경우\n\n그때.\n")
    assert [w[:5] for w in module_problems(tmp_path / "deploy-plan.md")] == ["5(나) "]


# ---------------------------------------------------------------------------
# 시험 6(다)·독자 줄: 방법 문서(L2m, Q-02, Q-07)

PRACTICE_DIR = ROOT / "references" / "practices"
PRACTICE_BANNED = re.compile(r"references/kinds/|agents/|tasks/|tasks\\|00_recon|게이트|결과 파일 형식"
                             r"|(?:요구사항|설계|구현|검증|기획) 블록|블록 담당자|뒤 블록")
PRACTICE_PATH_RE = re.compile(r"references/practices/([a-z-]+)\.md")


def practice_problems(path):
    """[`{경로}:{줄}: {걸린 글}`]: frontmatter(첫 줄 `---`)와 6(다)의 금지 글."""
    rel = path.relative_to(ROOT).as_posix() if ROOT in path.parents else path.name
    lines = path.read_text(encoding="utf-8").splitlines()
    out = ["{}:1: frontmatter".format(rel)] if lines[:1] == ["---"] else []
    for n, line in enumerate(lines, 1):
        out += ["{}:{}: `{}`".format(rel, n, m.group(0)) for m in PRACTICE_BANNED.finditer(line)]
    return out


def test_6c_practices_have_no_upper_paths_v1_words_or_front_matter():
    files = sorted(PRACTICE_DIR.rglob("*.md"))
    assert len(files) >= 11 + 3 + 1, [p.name for p in files]   # 방법 문서 11, stacks 3, ui-spec/rules.md
    assert [w for p in files for w in practice_problems(p)] == []


def test_6c_detects_v1_words_and_front_matter(tmp_path):
    f = tmp_path / "x.md"
    write(f, "---\nname: x\n---\n# 가\n먼저 `00_recon.md`, 게이트, 검증 블록, `agents/code-writer.md`\n")
    assert [w.split(": ", 1)[1] for w in practice_problems(f)] == [
        "frontmatter", "`00_recon`", "`게이트`", "`검증 블록`", "`agents/`"]
    write(f, "# 가\n화면 블록은 세로로, `recon.md`, 판정\n")
    assert practice_problems(f) == []


def practice_readers():
    """{방법 문서 이름: 그 문서를 「먼저 읽을 것」에 적은 kind 모듈들이 맡는 kind 집합}."""
    readers = {}
    for path in module_files():
        lines = unfenced(path.read_text(encoding="utf-8"))
        start = lines.index("## 먼저 읽을 것") + 1
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
        for name in PRACTICE_PATH_RE.findall("\n".join(lines[start:end])):
            readers.setdefault(name, set()).update(kinds_of(path.name))
    return readers


def reader_line(path):
    """제목(첫 `# ` 줄) 다음의 빈 줄 아닌 첫 줄."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# "), path.name
    return next(line for line in lines[1:] if line.strip())


def test_practice_reader_lines_match_kind_modules():
    readers = practice_readers()
    files = sorted(PRACTICE_DIR.glob("*.md"))
    assert len(files) == 11 and set(readers) <= {p.stem for p in files}, (sorted(readers), [p.name for p in files])
    for path in files:
        line = reader_line(path)
        expected = readers.get(path.stem, set())
        if not expected:
            assert line.startswith("메인이 읽는다") and "읽는 kind: 없음" in line, (path.name, line)
            continue
        assert line.startswith("읽는 kind: "), (path.name, line)
        named = {k for k in re.findall(r"`([a-z-]+)`", line) if k in kinds.KINDS}
        assert named == expected, (path.name, sorted(named), sorted(expected))
