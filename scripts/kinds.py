"""등록표: kind 17·에이전트 8·값 집합·머리 파일 키·판본 칸의 유일한 원천.

엔진 스크립트는 이 모듈의 이름과 파생 함수만 쓴다. 이 모듈은 표준 라이브러리만 import하고 다른 스크립트를
import하지 않는다(R2). 목차 `references/core/registry.md`와 절마다 파일 `references/registry/*.md`는 이 모듈의
`--md-write` 출력이다(손으로 고치지 않는다).

사용법:
  python3 scripts/kinds.py --md-write  목차와 절 파일 아홉을 플러그인 폴더에 쓴다(UTF-8, LF).
  python3 scripts/kinds.py --md        목차를 표준 출력에 낸다(UTF-8, LF). 인수가 없거나 다르면 사용법과 종료 2.
"""
import json
import os
import sys
from typing import NamedTuple


class Kind(NamedTuple):
    """kind 하나의 속성. 값의 뜻은 `references/registry/kinds.md`(등록표 1절)."""
    block: str                  # 블록. change는 ""(고치는 산출물의 블록을 따름)
    definition: str             # references/kinds/ 파일 이름
    writers: tuple              # 작성자 에이전트 이름(또는 "main")
    read_judge: str             # always / conditional / never
    run_judge: str              # always / never
    notify: str                 # none / all_cells / by_decide / never
    stages: object              # 단계 튜플 또는 None
    writes_code_dir: bool       # 코드 폴더에 쓴다(흐름 상한·폴더 사용 중을 센다)
    auto_depends_in_flow: bool  # 같은 흐름의 앞 task에 자동 의존, flow.md 필요, machine_check
    needs_touch_files: bool     # 자식 행에 「건드릴 파일」 필수
    writes_canon: bool          # 정본(spec·ui·design)을 쓴다
    readback: bool              # 실행 판정도 result.md를 읽는다
    commit_required: object     # True / False / "rules2"(규칙 판 2 이상에서만)
    verify_family: bool         # 검증 무리
    glyph: str                  # 아스키 보드의 종류 글자
    children: tuple             # 허용 자식 kind
    engine_hooks: tuple         # 엔진 코드에 이 kind만의 분기가 있는 자리의 이름


class Agent(NamedTuple):
    """에이전트 하나. `model`·`tools`는 `agents/{이름}.md` frontmatter와 같다."""
    role: str                   # writer / judge
    model: str
    tools: tuple
    short: str                  # 인스턴스 이름 접두어(formats.md 1절)
    required_tools: tuple       # 정의 검사가 요구하는 도구
    has_def_version: bool       # 정의 본문에 판 표지 `def-version:`이 있어야 한다


MERGE_STAGES = ("실행승인", "실행", "결과승인", "끝")
DEPLOY_STAGES = ("사전조건", "직전확인", "명령", "확인", "결과승인", "브랜치", "기록", "넣기승인", "넣기", "끝")
_CODE_HOOKS = ("machine_check", "required_judges", "flow_auto_depends", "touch_files", "readback", "from_answer",
               "flow_md")

KINDS = {
    "question": Kind(
        "질문", "question.md", ("requirements-writer", "cause-writer", "design-writer"), "always", "never",
        "all_cells", None, False, False, False, True, False, False, False, "Q",
        ("req-overview", "root-cause", "design"), ()),
    "brief": Kind(
        "기획", "brief.md", ("requirements-writer",), "always", "never",
        "none", None, False, False, False, True, False, False, False, "B",
        ("req-detail", "ui-design", "design"), ()),
    "req-overview": Kind(
        "요구사항", "req-overview.md", ("requirements-writer",), "always", "never",
        "none", None, False, False, False, True, False, False, False, "Q",
        ("brief",), ()),
    "req-detail": Kind(
        "요구사항", "req-detail.md", ("requirements-writer",), "always", "never",
        "none", None, False, False, False, True, False, False, False, "Q",
        ("design",), ()),
    "root-cause": Kind(
        "원인 분석", "root-cause.md", ("cause-writer",), "always", "always",
        "none", None, True, False, False, False, False, False, False, "C",
        ("implementation", "flow-verify", "wrap-up", "design"), ("code_dir_writes",)),
    "ui-design": Kind(
        "설계", "ui-design.md", ("design-writer",), "always", "never",
        "none", None, False, False, False, True, False, False, False, "U",
        ("design",), ()),
    "design": Kind(
        "설계", "design.md", ("design-writer",), "always", "never",
        "none", None, False, False, False, True, False, False, False, "S",
        ("implementation", "flow-verify", "full-verify", "wrap-up", "deploy-plan"), ()),
    "implementation": Kind(
        "구현", "implementation.md", ("code-writer",), "conditional", "always",
        "by_decide", None, True, True, True, False, True, True, False, "",
        (), _CODE_HOOKS),
    "fix": Kind(
        "구현", "implementation.md", ("code-writer",), "always", "always",
        "by_decide", None, True, True, True, False, True, True, False, "F",
        (), ("fix_generation",) + _CODE_HOOKS),
    "change": Kind(
        "", "change.md", ("requirements-writer", "design-writer"), "always", "never",
        "by_decide", None, False, False, False, True, False, False, False, "X",
        (), ("canon_check", "replace", "from_answer")),
    "flow-verify": Kind(
        "검증", "verify.md", ("verify-writer",), "always", "never",
        "none", None, False, False, False, False, False, False, True, "V",
        ("fix", "reverify"), ("start_condition", "child_generation_zero")),
    "reverify": Kind(
        "검증", "verify.md", ("verify-writer",), "always", "never",
        "all_cells", None, False, False, False, False, False, False, True, "R",
        ("fix", "reverify"), ("start_condition", "generation_plus_one", "over_cap_backlog")),
    "merge": Kind(
        "구현", "merge.md", ("main", "code-writer"), "conditional", "always",
        "all_cells", MERGE_STAGES, True, False, False, False, False, "rules2", False, "M",
        (), ("stage_rule", "exec_points", "merge_condition", "required_judges")),
    "full-verify": Kind(
        "검증", "verify.md", ("verify-writer",), "always", "never",
        "none", None, False, False, False, False, False, False, True, "V",
        ("fix", "reverify"), ("start_condition", "generation_zero")),
    "wrap-up": Kind(
        "마무리", "wrap-up.md", ("release-writer", "main"), "always", "never",
        "none", MERGE_STAGES, False, False, False, False, False, False, False, "W",
        (), ("stage_rule", "exec_points", "exported_commit", "start_condition", "collect_input")),
    "deploy-plan": Kind(
        "배포", "deploy-plan.md", ("release-writer",), "always", "never",
        "never", None, False, False, False, False, False, False, False, "D",
        ("deploy-exec",), ("exec_reads_plan_cmd",)),
    "deploy-exec": Kind(
        "배포", "deploy-exec.md", ("main", "run-judge", "release-writer"), "conditional", "always",
        "never", DEPLOY_STAGES, False, False, False, False, False, False, False, "E",
        (), ("stage_rule", "exec_parent_plan", "deploy_outcome")),
}

_WRITER_TOOLS = ("Read", "Grep", "Glob", "Bash", "Write", "Edit")
AGENTS = {
    "requirements-writer": Agent("writer", "opus", _WRITER_TOOLS, "req", (), False),
    "cause-writer": Agent("writer", "fable", _WRITER_TOOLS, "cause", (), False),
    "design-writer": Agent("writer", "opus", _WRITER_TOOLS, "design", (), False),
    "code-writer": Agent("writer", "opus", _WRITER_TOOLS, "code", (), False),
    "verify-writer": Agent("writer", "opus", _WRITER_TOOLS, "verify", (), False),
    "release-writer": Agent("writer", "sonnet", _WRITER_TOOLS, "release", (), False),
    "read-judge": Agent("judge", "opus", ("Read", "Grep", "Glob", "Bash", "Write"), "rjudge", ("Write",), True),
    "run-judge": Agent("judge", "sonnet", ("Read", "Grep", "Glob", "Bash", "Edit", "Write"), "xjudge", ("Write",), True),
}

# ---------------------------------------------------------------------------
# 값 집합

STATUSES = ("대기", "진행", "자체검증", "승인대기", "완료", "보류", "백로그")   # 별칭 없음
OPEN_STATUSES = STATUSES[:4]
CLOSED_STATUSES = STATUSES[4:]
DONE = "완료"
BUSY_STATUSES = ("진행", "자체검증")
STATUS_GLYPH = {"완료": "v", "진행": ">", "자체검증": "~", "승인대기": "?", "대기": " ", "보류": "-", "백로그": "b"}
ASK_STAGES = frozenset({"실행승인", "결과승인", "넣기승인", "직전확인"})
EXEC_POINTS = ("실행승인", "결과승인", "넣기승인", "되돌림")
JUDGE_FILES = {"read": "judge.md", "run": "judge-run.md"}
CELLS = ("정해 주실 것", "하실 일·허용 요청", "알릴 것", "답하신 것의 반영", "확인 안 된 것", "건수만")
COUNT_CELLS = {"정해 주실 것": "n_decide", "하실 일·허용 요청": "n_todo", "알릴 것": "n_notify",
               "확인 안 된 것": "n_unverified"}
UNDECIDED_TAGS = ("환경", "지시", "대상")
FLOW_ROLES = ("feature", "fixes", "integration", "deploy")
CANON_DIRS = ("spec", "ui", "design")

# 판본 칸
RULES = 2
DEF_VERSION_MIN = "2026-10-08-bundle2"   # 판정자 정의의 판 표지 `def-version:`의 최소값
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def plugin_version(root=None):
    """`{root 또는 PLUGIN_ROOT}/.claude-plugin/plugin.json`의 `version` 문자열. 못 읽거나 문자열이 아니면 `?`."""
    path = os.path.join(root or PLUGIN_ROOT, ".claude-plugin", "plugin.json")
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f).get("version")
    except (OSError, ValueError, AttributeError):
        return "?"
    return value if isinstance(value, str) else "?"


# 머리 파일 키(formats.md 3절 표의 순서): (이름, 채우는 길, 목록 여부).
# 채우는 길: script(스크립트만) / option(전용 옵션만) / selfcheck(진행→자체검증 전이(`--status 자체검증`)와 함께서만) / kv(`키=값`)
_SCRIPT = ("started_version", "rules", "started", "approval_requested", "approved", "created", "done_via",
           "criteria_amended", "exported_commit", "origin", "fix_generation")
_OPTION = ("status", "retry", "kind")
_SELFCHECK = ("machine_check",)
_LISTS = ("depends_on", "closes_ac", "partial_ac")
_KEY_ORDER = ("id", "title", "kind", "block", "status", "parent", "depends_on", "flow", "difficulty", "closes_ac",
              "partial_ac", "one_line", "origin", "cause_task", "fix_generation", "commit", "running_agent",
              "waiting_user", "retry", "started_version", "rules", "machine_check", "done_via", "criteria_amended",
              "judge_method", "approval_mode", "n_decide", "n_todo", "n_notify", "n_unverified", "n_children",
              "split_criterion", "shrunk_reason", "awaiting_answer_apply", "external_progress", "stage",
              "exported_commit", "partial_flow", "deploy_outcome", "deployed_commit", "created", "started",
              "approval_requested", "approved")


def _fill_of(key):
    if key in _SCRIPT:
        return "script"
    if key in _OPTION:
        return "option"
    if key in _SELFCHECK:
        return "selfcheck"
    return "kv"


TASK_KEYS = tuple((k, _fill_of(k), k in _LISTS) for k in _KEY_ORDER)

# 머리 파일 본문 절 11개의 순서와 채우는 쪽: row(자식 행) / own(스크립트 전용 옵션) / main(메인)
TASK_SECTIONS = (
    ("범위", ("row",)),
    ("판정 기준", ("row", "own")),
    ("판정 기준 정정", ("own",)),
    ("재시도 범위", ("own",)),
    ("건드릴 파일", ("row",)),
    ("시그니처와 결정 번호", ("row",)),
    ("정본의 절", ("row",)),
    ("영향받는 task와 처리", ("main",)),
    ("넘길 이상 신호", ("main",)),
    ("표 밖 전이", ("own",)),
    ("승인 기록", ("own",)),
)

# run.md 머리 키(formats.md 6절)와 「이번 실행의 값」 시작값
RUN_KEYS = ("kind", "status", "project", "base_branch", "round", "integration_branch", "integration_dir",
            "harness_version", "start_task", "previous_run", "session_id")
RUN_DEFAULTS = {"동시에 도는 흐름": 2, "수정 세대 상한": 2, "자체 검증 재시도": 2, "판정불가 다시 돌림": 2}

# ---------------------------------------------------------------------------
# 파생 함수와 이름(엔진이 상수 대신 부른다)


def kinds_where(**attr):
    """속성이 모두 맞는 kind의 frozenset. 값이 호출 가능하면 그 속성 값을 넣어 참인지 보고, 아니면 같은지 본다."""
    out = set()
    for name, k in KINDS.items():
        if all(want(getattr(k, field)) if callable(want) else getattr(k, field) == want
               for field, want in attr.items()):
            out.add(name)
    return frozenset(out)


def block_of(kind):
    return KINDS[kind].block


def notify_policy(kind):
    return KINDS[kind].notify


def stages_of(kind):
    return KINDS[kind].stages


def glyph(kind):
    return KINDS[kind].glyph


def commit_kinds(rules_level):
    """완료일 때 commit이 있어야 하는 kind. merge는 규칙 판 2 이상에서만."""
    need = kinds_where(commit_required=True)
    if rules_level >= 2:
        need |= kinds_where(commit_required="rules2")
    return need


STAGE_KINDS = kinds_where(stages=lambda s: s is not None)
AUTO_DEPEND_KINDS = kinds_where(auto_depends_in_flow=True)
TOUCH_FILES_KINDS = kinds_where(needs_touch_files=True)
READBACK_KINDS = kinds_where(readback=True)
CODE_DIR_KINDS = kinds_where(writes_code_dir=True)
CANON_WRITER_KINDS = kinds_where(writes_canon=True)
VERIFY_KINDS = kinds_where(verify_family=True)
NOTIFY_BY_DECIDE_KINDS = kinds_where(notify="by_decide")
NOTIFY_KINDS = NOTIFY_BY_DECIDE_KINDS | kinds_where(notify="all_cells")
NEVER_NOTIFY_KINDS = kinds_where(notify="never")
CODE_WRITER_KINDS = kinds_where(writers=lambda w: "code-writer" in w)

SCRIPT_KEYS = frozenset(k for k, fill, _ in TASK_KEYS if fill == "script")
OPTION_KEYS = frozenset(k for k, fill, _ in TASK_KEYS if fill == "option")
SELFCHECK_KEYS = frozenset(k for k, fill, _ in TASK_KEYS if fill == "selfcheck")
LIST_KEYS = frozenset(k for k, _, is_list in TASK_KEYS if is_list)
BODY_KEYS = tuple(s for s, by in TASK_SECTIONS if "row" in by)
OWN_SECTIONS = frozenset(s for s, by in TASK_SECTIONS if "own" in by)

CHANGE_TARGETS = ("req-overview", "req-detail", "brief", "ui-design", "design")
CHANGE_INHERITS = ("하는 일", "승인 화면", "자체 검증")
EDGES = frozenset({(p, c) for p, k in KINDS.items() for c in k.children} | {("change", t) for t in CHANGE_TARGETS})

# formats 파일: (파일 이름, 형식 목차 `references/core/formats.md`의 절 번호), 절 차례. 파일은 `FORMATS_DIR/{이름}.md`.
# 한 절을 두 파일로 나눈 곳(5절)이 있다
FORMATS_DIR = "references/formats"
FORMAT_FILES = (("names", 1), ("run-folder", 2), ("task-file", 3), ("result-file", 4), ("judge-file", 5),
                ("judge-run-file", 5), ("run-files", 6), ("prompt", 7), ("return", 8))
# 독자별 formats 파일. writer = 작성자 에이전트 6
FORMATS_READERS = {
    "writer": ("task-file", "result-file", "return"),
    "read-judge": ("task-file", "judge-file", "return"),
    "run-judge": ("judge-file", "judge-run-file", "return"),
    "main": tuple(name for name, _ in FORMAT_FILES),
}

# 아스키 보드 범례: 상태 글자는 STATUS_GLYPH의 순서, 종류 글자는 아래 kind의 glyph와 낱말
_LEGEND_KINDS = ((("design",), "설계"), (("fix",), "수정"), (("flow-verify",), "검증"), (("reverify",), "재검증"),
                 (("merge",), "합치기"), (("root-cause",), "원인"), (("change",), "변경"), (("wrap-up",), "마무리"),
                 (("deploy-plan", "deploy-exec"), "배포"), (("req-overview",), "요구사항"))
LEGEND = ("상태 " + " ".join("[{}]{}".format(g, s) for s, g in STATUS_GLYPH.items()) + " | 종류 "
          + " ".join("/".join(glyph(k) for k in ks) + word for ks, word in _LEGEND_KINDS))

# ---------------------------------------------------------------------------
# 등록표 문서(`--md-write`): 목차 registry.md와 절마다 파일 references/registry/.
# 시각·절대 경로·환경 값을 넣지 않는다(바이트 대조)

MD_INDEX = "references/core/registry.md"
MD_DIR = "references/registry"
MD_SECTION_FILES = ("kinds", "edges", "agents", "values", "task-keys", "run-keys", "version", "derived",
                    "readers")  # 절 차례
MD_TITLE = "# 등록표 (생성: python3 scripts/kinds.py --md-write. 손으로 고치지 않는다)"
MD_LEAD = ("등록표 `scripts/kinds.py`를 절마다 한 파일로 낸 것의 목차다. 절 번호는 아래 표의 차례이고, "
           "\"registry.md n절\"은 이 표의 n번 파일이다.")
_NOTIFY_WORD = {"none": "승인만", "all_cells": "네 칸 모두 0", "by_decide": "「정해」「하실」 0, origin 사용자면 불가",
                "never": "불가"}
_EMPTY_WORD = {"block": "(빈 값)", "glyph": "(빈 글자)"}


def _order(items):
    """kind 이름이면 KINDS 순서, 그 밖은 글자 순서."""
    items = list(items)
    if items and all(i in KINDS for i in items):
        names = list(KINDS)
        return sorted(items, key=names.index)
    return sorted(items)


def _cell(field, value):
    if field == "notify":
        return value  # 아래 _notify_cell에서 바꿈
    if value is True:
        return "예"
    if value is False or value is None or value == ():
        return "—"
    if value == "":
        return _EMPTY_WORD.get(field, "(빈 값)")
    if isinstance(value, tuple):
        return ", ".join(value)
    return str(value)


def _notify_cell(k):
    word = "단계" if k.stages is not None else _NOTIFY_WORD[k.notify]
    return "{} (`{}`)".format(word, k.notify)


def _row(cells):
    return "| " + " | ".join(cells) + " |"


def _table(header, rows):
    return [_row(header), _row(["---"] * len(header))] + [_row(r) for r in rows]


def _join(items):
    return ", ".join("`{}`".format(i) for i in items)


def render_sections():
    """등록표 1~9절. 절마다 `## {n}. {제목}` 줄부터 다음 절 앞까지의 문자열(차례는 `MD_SECTION_FILES`)."""
    out = []
    out += ["## 1. kind {}".format(len(KINDS)), ""]
    fields = list(Kind._fields)
    rows = []
    for name, k in KINDS.items():
        rows.append([name] + [_notify_cell(k) if f == "notify" else _cell(f, getattr(k, f)) for f in fields])
    out += _table(["kind"] + fields, rows)
    out += ["", "알림 칸: 낱말은 `stages`가 있으면 단계, 없으면 `notify` 값의 낱말(괄호 안이 `notify` 값).", ""]

    names = list(KINDS)
    out += ["## 2. 간선", ""]
    out += ["- `{}` → `{}`".format(p, c) for p, c in sorted(EDGES, key=lambda e: (names.index(e[0]), names.index(e[1])))]
    out += ["- `CHANGE_TARGETS`: " + _join(CHANGE_TARGETS),
            "- `CHANGE_INHERITS`: " + _join(CHANGE_INHERITS), ""]

    out += ["## 3. 에이전트 {}".format(len(AGENTS)), ""]
    out += _table(["에이전트"] + list(Agent._fields),
                  [[name] + [_cell(f, getattr(a, f)) for f in Agent._fields] for name, a in AGENTS.items()])
    out += [""]

    out += ["## 4. 값 집합", ""]
    out += ["- `STATUSES`: " + _join(STATUSES),
            "- `OPEN_STATUSES`: " + _join(OPEN_STATUSES),
            "- `CLOSED_STATUSES`: " + _join(CLOSED_STATUSES),
            "- `DONE`: " + _join([DONE]),
            "- `BUSY_STATUSES`: " + _join(BUSY_STATUSES),
            "- `STATUS_GLYPH`: " + ", ".join("`[{}]{}`".format(g, s) for s, g in STATUS_GLYPH.items()),
            "- `ASK_STAGES`: " + _join(sorted(ASK_STAGES, key=(MERGE_STAGES + DEPLOY_STAGES).index)),
            "- `EXEC_POINTS`: " + _join(EXEC_POINTS),
            "- `JUDGE_FILES`: " + ", ".join("`{}` = `{}`".format(r, f) for r, f in JUDGE_FILES.items()),
            "- `CELLS`: " + _join(CELLS),
            "- `COUNT_CELLS`: " + ", ".join("`{}` = `{}`".format(c, n) for c, n in COUNT_CELLS.items()),
            "- `UNDECIDED_TAGS`: " + _join(UNDECIDED_TAGS),
            "- `FLOW_ROLES`: " + _join(FLOW_ROLES),
            "- `CANON_DIRS`: " + _join(CANON_DIRS), ""]

    out += ["## 5. 머리 파일 키와 본문 절", ""]
    out += _table(["키", "채우는 길", "목록"], [[k, fill, "예" if is_list else "—"] for k, fill, is_list in TASK_KEYS])
    out += [""]
    out += _table(["순서", "본문 절", "채우는 쪽"],
                  [[str(i), s, ", ".join(by)] for i, (s, by) in enumerate(TASK_SECTIONS, 1)])
    out += [""]

    out += ["## 6. run.md 키와 시작값", ""]
    out += ["- `RUN_KEYS`: " + _join(RUN_KEYS), ""]
    out += _table(["이번 실행의 값", "시작값"], [[n, str(v)] for n, v in RUN_DEFAULTS.items()])
    out += [""]

    out += ["## 7. 판본 칸", ""]
    out += ["- `RULES`: `{}`".format(RULES),
            "- `DEF_VERSION_MIN`: `{}`".format(DEF_VERSION_MIN),
            "- 플러그인 version(`plugin_version()`): `.claude-plugin/plugin.json`의 `version`", ""]

    out += ["## 8. 파생 집합", ""]
    derived = [("STAGE_KINDS", STAGE_KINDS), ("AUTO_DEPEND_KINDS", AUTO_DEPEND_KINDS),
               ("TOUCH_FILES_KINDS", TOUCH_FILES_KINDS), ("READBACK_KINDS", READBACK_KINDS),
               ("CODE_DIR_KINDS", CODE_DIR_KINDS), ("CANON_WRITER_KINDS", CANON_WRITER_KINDS),
               ("VERIFY_KINDS", VERIFY_KINDS), ("NOTIFY_KINDS", NOTIFY_KINDS),
               ("NOTIFY_BY_DECIDE_KINDS", NOTIFY_BY_DECIDE_KINDS), ("NEVER_NOTIFY_KINDS", NEVER_NOTIFY_KINDS),
               ("CODE_WRITER_KINDS", CODE_WRITER_KINDS), ("commit_kinds(1)", commit_kinds(1)),
               ("commit_kinds(2)", commit_kinds(2)), ("SCRIPT_KEYS", _ordered_keys(SCRIPT_KEYS)),
               ("OPTION_KEYS", _ordered_keys(OPTION_KEYS)),
               ("SELFCHECK_KEYS", _ordered_keys(SELFCHECK_KEYS)), ("LIST_KEYS", _ordered_keys(LIST_KEYS)),
               ("BODY_KEYS", BODY_KEYS), ("OWN_SECTIONS", _ordered_sections(OWN_SECTIONS))]
    for name, items in derived:
        shown = items if isinstance(items, tuple) else _order(items)
        out.append("- `{}`: {}".format(name, _join(shown)))
    out += ["- `LEGEND`: `{}`".format(LEGEND)]

    out += ["## 9. 독자별 formats 파일", ""]
    out += _table(["formats 파일", "formats.md 절"],
                  [["`{}`".format(_format_path(name)), "{}절".format(n)] for name, n in FORMAT_FILES])
    out += [""]
    out += _table(["독자", "읽는 formats 파일"],
                  [[who, ", ".join("`{}`".format(_format_path(f)) for f in files)]
                   for who, files in FORMATS_READERS.items()])
    starts = [i for i, line in enumerate(out) if line.startswith("## ")] + [len(out)]
    sections = ["\n".join(out[a:b]) + "\n" for a, b in zip(starts, starts[1:])]
    if len(sections) != len(MD_SECTION_FILES):
        raise ValueError("절 수({})와 MD_SECTION_FILES({})가 다름".format(len(sections), len(MD_SECTION_FILES)))
    return sections


def _format_path(name):
    return "{}/{}.md".format(FORMATS_DIR, name)


def _section_path(name):
    return "{}/{}.md".format(MD_DIR, name)


def render_index(sections=None):
    """목차 registry.md: H1, 한 문단, 절 → 파일 표(`## ` 줄 없음)."""
    sections = render_sections() if sections is None else sections
    rows = [[sec.split("\n", 1)[0][3:], "`{}`".format(_section_path(name))]
            for name, sec in zip(MD_SECTION_FILES, sections)]
    return "\n".join([MD_TITLE, "", MD_LEAD, ""] + _table(["절", "파일"], rows)) + "\n"


def md_files():
    """플러그인 폴더 기준 경로 → 내용. 목차와 절 파일 아홉."""
    sections = render_sections()
    files = {MD_INDEX: render_index(sections)}
    for name, sec in zip(MD_SECTION_FILES, sections):
        files[_section_path(name)] = sec
    return files


def write_md_files(root=None):
    """`md_files()`를 `{root 또는 PLUGIN_ROOT}` 아래에 쓴다(UTF-8, LF). 쓴 경로 목록을 돌려준다."""
    root = root or PLUGIN_ROOT
    for rel, text in md_files().items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(text.encode("utf-8"))
    return list(md_files())


def _ordered_keys(keys):
    return tuple(k for k, _, _ in TASK_KEYS if k in keys)


def _ordered_sections(sections):
    return tuple(s for s, _ in TASK_SECTIONS if s in sections)


USAGE = ("사용법: python3 scripts/kinds.py --md | --md-write\n"
         "  --md        등록표 목차(references/core/registry.md의 내용)를 표준 출력에 낸다.\n"
         "  --md-write  목차 references/core/registry.md와 절 파일 references/registry/*.md 아홉을 쓴다.\n")


def main(argv):
    if argv == ["--md"]:
        sys.stdout.buffer.write(render_index().encode("utf-8"))
        sys.stdout.buffer.flush()
        return 0
    if argv == ["--md-write"]:
        write_md_files()
        return 0
    sys.stderr.write(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
