"""규칙과 검사를 묶는 시험: 판정 쪽(설계 harness-tests 4.6절 표의 R6 일곱 줄, 결정 D10)과 화면 쪽(R7 여섯 줄, 결정 D11·D12).

같은 규칙이 판정자·작성자·메인이 읽는 문서와 스크립트 상수·파서에 따로 있다. 문서를 원천으로 두고, 시험이 문서에서 글자(틀 줄의 칸
이름과 갈래 값, 괄호 목록, 상한 낱말, 절 이름, 답 꼴)를 꺼내 상수와 견주고, 틀의 자리 표시를 표본 값으로 채운 줄을 파서가 읽는지 본다.
시험 안에 문서 문장의 사본을 두지 않는다(원칙 문서 2절). 판정 쪽 문서는 고치지 않으므로 어긋나면 스크립트 쪽을 고친다.

| 규칙 | 문서 | 시험 |
|---|---|---|
| 짚음 틀 | `references/formats/judge-file.md` 「짚음」 | `test_point_template_*` |
| 주장-출처 틀 | 같은 파일 「주장-출처 대조」 | `test_point_and_claim_field_names_*`, `test_claim_template_*` |
| 통과 못 한 기준 틀 | 같은 파일 「통과 못 한 기준」 | `test_failed_item_template_*`, `test_undecided_*` |
| 하네스가 고칠 것 다섯 | `judge-file.md` 끝 문단, `references/roles/judge-points.md` 「갈래」 | `test_harness_fix_kinds_*` |
| 즉시 질문 상한과 차례 | `judge-points.md` 「깨짐」, `judge-file.md` 끝 문단 | `test_now_cap_*`, `test_now_order_*` |
| 짚음 글 예산 | `judge-points.md` 「갈래」 | `test_point_text_budget_*` |
| 사실 파일 | `references/formats/facts-file.md` | `test_facts_*` |
| 알림을 막는 성질 | `references/kinds/change/main-order.md`, `references/kinds/infra-design/main-order.md` | `test_asking_properties_*` |
| 경계 사이 kind의 알림 | 등록표 `references/registry/kinds.md` `boundary` 칸 | `test_between_kinds_*`, `test_between_kind_notice_*` |
| 글자 예산 | `references/formats/screen-cells.md` 「글자 예산」 | `test_budget_*` |
| 선택지 문장의 자리 | `references/formats/result-file.md` 「정해 주실 것」 틀 | `test_option_text_*` |
| 답 꼴 | `references/main/approval.md` 「묻는 방법」 | `test_answer_forms_*` |
| 전제 셋 이내 | `screen-cells.md` 「전제와 정한 것」 | `test_premise_cap_*` |
| 고침 답의 기록 꼴 | `references/main/approval.md` 「답의 처리」 표의 「산출물을 바꾸는 답」 행 | `test_fix_record_*` |
| 반환 전 판정 파일 검사 | `agents/read-judge.md` 「역할 고유 규칙」 | `test_check_judge_*` |
| 곳 답 없이 승인으로 가는 판본 | `references/main/approval.md` 옛 코드 확인 카드 줄, `references/kinds/verify/main-order.md` 「코드 확인」 | `test_place_answer_version_*` |
| 최종 CI 이어받음 | `references/formats/judge-run-file.md`, `references/kinds/wrap-up/run-check.md`, `references/kinds/implementation/run-check.md` | `test_inherit_*` |
"""
import re
from datetime import datetime

import pytest

import devflow_lib as lib
import judge_facts
import kinds
import plain_text
import report
import screen
import task_set
from conftest import ROOT, run_script, write
from test_boundary_report import DESIGN, V130, judged, result as screen_result
from test_domain_paths import RUN_JUDGE

JUDGE_FILE = ROOT / "references" / "formats" / "judge-file.md"
JUDGE_POINTS = ROOT / "references" / "roles" / "judge-points.md"
FACTS_FILE = ROOT / "references" / "formats" / "facts-file.md"
CHANGE_ORDER = ROOT / "references" / "kinds" / "change" / "main-order.md"
INFRA_ORDER = ROOT / "references" / "kinds" / "infra-design" / "main-order.md"
KINDS_TABLE = ROOT / "references" / "registry" / "kinds.md"
SCREEN_CELLS = ROOT / "references" / "formats" / "screen-cells.md"
RESULT_FILE = ROOT / "references" / "formats" / "result-file.md"
APPROVAL = ROOT / "references" / "main" / "approval.md"
READ_JUDGE_DEF = ROOT / "agents" / "read-judge.md"
VERIFY_ORDER = ROOT / "references" / "kinds" / "verify" / "main-order.md"

# 문서가 수를 쓰는 낱말(수 관형사 포함). 규칙 문장이 아니라 낱말 → 수 대응이다
NUMBER_WORDS = {"하나": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "넷": 4, "네": 4, "다섯": 5}
NUMBER_WORD = re.compile(r"(?<![가-힣])({})(?=으로|까지| 개| 줄|\()".format("|".join(sorted(NUMBER_WORDS, key=len, reverse=True))))
PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
TIGHT_SLASH = re.compile(r"(?<=\S)/(?=\S)")   # `{a/b/c}`처럼 붙여 쓴 갈래 값. ` / `로 띄운 것은 값 하나(길, 까닭)


def read(path):
    assert path.is_file(), "문서 없음: {}".format(path)
    return path.read_text(encoding="utf-8")


def template(path):
    """문서의 첫 ``` 울타리 안(틀)."""
    m = re.search(r"^```[^\n]*\n(.*?)^```", read(path), re.S | re.M)
    assert m, "틀 울타리 없음: {}".format(path)
    return m.group(1)


def template_item(section):
    """판정 파일 틀의 절에서 첫 `- ` 줄(항목 틀)."""
    body = lib.sections(template(JUDGE_FILE), level=2).get(section)
    assert body is not None, "judge-file.md 틀에 「{}」 절 없음".format(section)
    lines = [l for l in body.splitlines() if l.startswith("- ")]
    assert lines, "judge-file.md 틀 「{}」에 항목 줄 없음".format(section)
    return lines[0]


def fields(item):
    """`- 글 | 이름: 값 | … | 이름 없는 칸` → (글, [(이름, 값)], [이름 없는 칸])."""
    parts = item[2:].split(" | ")
    named, loose = [], []
    for part in parts[1:]:
        name, colon, value = part.partition(": ")
        (named.append((name, value)) if colon else loose.append(part))
    return parts[0], named, loose


def choices(value):
    """`{a/b/c}` → [a, b, c]. 안쪽 자리 표시(`{조건}`)는 괄호만 벗긴다."""
    inner = PLACEHOLDER.sub(lambda m: m.group(1), value)
    inner = inner[1:-1] if inner.startswith("{") and inner.endswith("}") else inner
    return TIGHT_SLASH.split(inner)


def fill(text, **values):
    """자리 표시를 채운다: 이름이 values에 있으면 그 값, 없으면 괄호만 벗긴 글(표본 값)."""
    while PLACEHOLDER.search(text):
        text = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(1)), text)
    return text


def number_words(text):
    return [NUMBER_WORDS[w] for w in NUMBER_WORD.findall(text)]


def lines_with(path, *words):
    found = [l for l in read(path).splitlines() if all(w in l for w in words)]
    assert found, "{}에 {}가 든 줄 없음".format(path.name, words)
    return found


def judge_dir(tmp_path, section, line):
    write(tmp_path / kinds.JUDGE_FILES["read"], "## {}\n{}\n".format(section, line))
    return {"_dir": str(tmp_path)}


# ---------------------------------------------------------------- 짚음 틀, 주장-출처 틀

def test_point_and_claim_field_names_are_point_fields_in_order():
    """짚음 틀의 칸 이름 + 주장-출처 틀의 칸 이름 = POINT_FIELDS(차례 포함)."""
    point = [n for n, _ in fields(template_item(lib.POINT_SECTION))[1]]
    claim = [n for n, _ in fields(template_item(lib.CLAIM_SECTION))[1]]
    assert point and claim
    assert point + claim == list(lib.POINT_FIELDS)


def test_point_template_branch_values_are_point_branches():
    named = dict(fields(template_item(lib.POINT_SECTION))[1])
    assert choices(named["갈래"]) == list(lib.POINT_BRANCHES)


def test_point_template_filled_is_read_by_judge_points_without_problem(tmp_path):
    """자리 표시를 채운 짚음 틀 줄을 judge_points가 problem 없이 읽고 칸 값을 돌려준다(갈래는 틀의 첫 값)."""
    text, named, _ = fields(template_item(lib.POINT_SECTION))
    values = {n: choices(v)[0] for n, v in named}
    line = "- {} | {}".format(fill(text), " | ".join("{}: {}".format(n, values[n]) for n, _ in named))
    points = lib.judge_points(judge_dir(tmp_path, lib.POINT_SECTION, line))
    assert len(points) == 1
    p = points[0]
    assert p["problem"] == ""
    assert p["branch"] == lib.POINT_ASK == values["갈래"]
    assert (p["text"], p["why"], p["ways"], p["effects"], p["recommend"], p["basis"]) == (
        fill(text), values["까닭"], values["길"], values["결과"], values["추천"], values["근거"])
    assert values["깨짐"].startswith("있음 ") and p["breaks"] is True
    assert p["breaks_text"] == values["깨짐"][len("있음 "):]


def test_point_template_every_branch_value_is_read(tmp_path):
    """틀의 갈래 값마다 채운 줄을 갈래를 읽지 못한 문제 없이 읽는다."""
    text, named, _ = fields(template_item(lib.POINT_SECTION))
    for i, branch in enumerate(choices(dict(named)["갈래"])):
        values = {n: (branch if n == "갈래" else choices(v)[0]) for n, v in named}
        line = "- {} | {}".format(fill(text), " | ".join("{}: {}".format(n, values[n]) for n, _ in named))
        p = lib.judge_points(judge_dir(tmp_path / str(i), lib.POINT_SECTION, line))[0]
        assert p["problem"] == "", (branch, p["problem"])
        assert p["branch"] in lib.POINT_BRANCHES


def test_claim_template_verdicts_are_claim_verdicts():
    named = dict(fields(template_item(lib.CLAIM_SECTION))[1])
    assert choices(named["대조"]) == list(lib.CLAIM_VERDICTS)


def test_claim_template_filled_is_read_by_claim_rows(tmp_path):
    text, named, loose = fields(template_item(lib.CLAIM_SECTION))
    assert len(loose) == 1   # 어긋나면 무엇이 다른지(이름 없는 끝 칸)
    for i, verdict in enumerate(choices(dict(named)["대조"])):
        values = {n: (verdict if n == "대조" else fill(v)) for n, v in named}
        line = "- {} | {} | {}".format(fill(text), " | ".join("{}: {}".format(n, values[n]) for n, _ in named), fill(loose[0]))
        rows = lib.claim_rows(judge_dir(tmp_path / str(i), lib.CLAIM_SECTION, line))
        assert rows == [{"claim": fill(text), "cite": values["인용"], "verdict": verdict, "note": fill(loose[0])}]
        assert rows[0]["verdict"] in lib.CLAIM_VERDICTS


# ---------------------------------------------------------------- 통과 못 한 기준 틀

FAILED_SECTION = "통과 못 한 기준"   # 스크립트가 judge.md에서 읽는 절 이름(task_set.failed_numbers 등)


def test_failed_item_template_head_is_read_by_item_key():
    """틀의 `- 기준 {n}:`을 채운 줄을 devflow_lib.item_key가 [n]으로 읽는다."""
    item = template_item(FAILED_SECTION)
    assert lib.item_key(fill(item, n="3")) == ("기준", [3])
    assert lib.item_key(fill(item, n="12")) == ("기준", [12])


def undecided_form():
    """틀 「통과 못 한 기준」 안의 판정불가 꼴(백틱 안 `- …`)과 꼬리표 이름 목록."""
    body = lib.sections(template(JUDGE_FILE), level=2)[FAILED_SECTION]
    forms = re.findall(r"`(- [^`]*\{[^`]*)`", body)
    assert len(forms) == 1, forms
    m = re.search(r"\(꼬리표 ((?:`[^`]+`(?:\([^()]*\))?/?)+)", body)
    assert m, "judge-file.md 틀에 꼬리표 목록 없음"
    return forms[0], re.findall(r"`([^`]+)`", m.group(1))


def test_undecided_tag_names_are_undecided_tags():
    _, tags = undecided_form()
    assert tags == list(kinds.UNDECIDED_TAGS)


def test_undecided_form_filled_is_read_by_item_key_and_undecided_tag():
    """판정불가 꼴을 꼬리표마다 채운 줄: item_key가 기준 번호를, undecided_tag가 꼬리표를 읽는다."""
    form, tags = undecided_form()
    for tag in tags:
        line = fill(form, n="4", 꼬리표=tag)
        assert lib.item_key(line) == ("기준", [4])
        assert lib.undecided_tag(line) == tag
    # 같은 꼴에 실패가 섞이면 꼬리표 없음(양성 대조와 같은 조건)
    assert lib.undecided_tag(fill(form, n="4", 꼬리표=tags[0], 이유="기준도 실패")) is None


# ---------------------------------------------------------------- 하네스가 고칠 것 다섯

def test_harness_fix_kinds_match_judge_file_parenthesis():
    """judge-file.md 「하네스 몫 {수}(…)」 괄호 목록 = HARNESS_FIX_KINDS(차례 포함), 수 낱말 = 개수."""
    found = [m for l in read(JUDGE_FILE).splitlines() for m in re.finditer(r"하네스 몫 (\S+?)\(([^)]*)\)", l)]
    assert len(found) == 1, found
    m = found[0]
    assert m.group(2).split(", ") == list(lib.HARNESS_FIX_KINDS)
    assert number_words(m.group(1) + "(") == [len(lib.HARNESS_FIX_KINDS)]


def test_harness_fix_kinds_match_judge_points_branch_rule():
    """judge-points.md 「**하네스가 고칠 것**은 {수}…: 이름(설명), …」 = HARNESS_FIX_KINDS."""
    lines = lines_with(JUDGE_POINTS, "**{}**".format(lib.POINT_FIX), ": ")
    line = lines[0]
    head, _, rest = line.partition(": ")
    names = re.sub(r"\([^()]*\)", "", rest).split(". ")[0].split(", ")
    assert names == list(lib.HARNESS_FIX_KINDS)
    assert number_words(head) == [len(lib.HARNESS_FIX_KINDS)]


# ---------------------------------------------------------------- 즉시 질문 상한과 차례

def test_now_cap_word_matches_point_now_cap_in_both_documents():
    """「즉시 질문」이 든 줄의 「{수}까지」·「{수} 개까지」 = POINT_NOW_CAP(judge-points.md 「깨짐」, judge-file.md 끝 문단)."""
    for path in (JUDGE_POINTS, JUDGE_FILE):
        words = [NUMBER_WORDS[w] for l in lines_with(path, "즉시 질문", "까지")
                 for w in re.findall(r"(?<![가-힣])(\S+?)(?: 개)?까지", l) if w in NUMBER_WORDS]
        assert words == [lib.POINT_NOW_CAP], (path.name, words)


def test_now_cap_is_what_point_places_uses():
    """문서의 상한만큼만 즉시 질문으로 간다(point_places 기본값이 상수)."""
    cap = lib.POINT_NOW_CAP
    points = [{"branch": lib.POINT_ASK, "breaks": True, "why": "(c)", "problem": ""} for _ in range(cap + 2)]
    places = lib.point_places(points)
    assert len(places["now"]) == cap and len(places["report"]) == 2


def test_now_order_groups_get_point_rank_in_order():
    """judge-points.md 「차례(a·b > c > …)」의 묶음 i의 낱말마다 point_rank가 i."""
    found = [m.group(1) for l in lines_with(JUDGE_POINTS, "즉시 질문", "차례(") for m in re.finditer(r"차례\(([^)]*)\)", l)]
    assert len(found) == 1, found
    groups = [g.split("·") for g in found[0].split(" > ")]
    assert len(groups) == len(lib.POINT_RANKS) + 1   # 마지막 묶음(그 밖)은 표에 없는 차례
    for rank, words in enumerate(groups):
        for word in words:
            assert lib.point_rank({"why": "까닭 " + word}) == rank, (word, rank)


# ---------------------------------------------------------------- 짚음 글 예산

def test_point_text_budget_matches_ask_budget():
    budgets = re.findall(r"약 ([\d,]+)자", read(JUDGE_POINTS))
    assert budgets and [int(b.replace(",", "")) for b in budgets] == [plain_text.BUDGET["ask"]]


# ---------------------------------------------------------------- 사실 파일

def test_facts_template_sections_are_sections_constant():
    names = list(lib.sections(template(FACTS_FILE), level=2))
    assert names == list(judge_facts.SECTIONS.values())


def test_facts_not_run_line_is_in_document_verbatim():
    assert "`{}`".format(judge_facts.NOT_RUN) in read(FACTS_FILE)


def cap_lines():
    """facts-file.md에서 「{수}줄까지」가 든 줄: (돌지 않는 절 줄과 같은 줄, 그 밖의 줄)."""
    found = lines_with(FACTS_FILE, "줄까지")
    with_not_run = [l for l in found if judge_facts.NOT_RUN in l]
    assert len(with_not_run) == 1 and len(found) == 2, found
    return with_not_run[0], next(l for l in found if l not in with_not_run)


def test_facts_section_line_cap_matches_line_cap():
    """돌지 않는 절의 줄과 같은 줄의 「{n}줄까지」 = LINE_CAP, 넘으면 문서의 `- 외 {n}줄` 꼴."""
    line, _ = cap_lines()
    caps = re.findall(r"(\d+)줄까지", line)
    assert [int(c) for c in caps] == [judge_facts.LINE_CAP]
    more = re.findall(r"`(- [^`]*\{n\}[^`]*)`", line)
    assert len(more) == 1
    rows = ["- {}".format(i) for i in range(judge_facts.LINE_CAP + 2)]
    capped = judge_facts._cap(rows)
    assert capped[:-1] == rows[:judge_facts.LINE_CAP]
    assert capped[-1] == fill(more[0], n="2")


def test_facts_tests_per_name_matches_tests_per_name():
    _, line = cap_lines()
    words = [NUMBER_WORDS[w] for w in re.findall(r"(?<![가-힣])(\S+) 줄까지", line) if w in NUMBER_WORDS]
    assert words == [judge_facts.TESTS_PER_NAME]


# ================================================================ 화면 쪽(R7)

def between_task(run_dir, kind, decide="- 없음", notify="- 없음"):
    """1.3.0에 시작해 자체검증을 마친 task. 판정 파일(짚음·주장-출처 대조·판단 대조), 사실 파일, 실행 판정 파일, 결과 「판단」을
    갖춰 kind마다 같은 조건이 되게 한다(코드 kind는 실행 판정과 판단 기록이 없으면 알림 전에 막힌다)."""
    run_dir.task("T001", "일", {"건드릴 파일": "- src/a.ts"}, kind=kind, block=kinds.KINDS[kind].block, status="자체검증",
                 flow="a", **V130)
    run_dir.result("T001", screen_result(decide=decide, notify=notify) + "\n## 판단\n- 없음\n")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T001", "판정자: rjudge-T001 {}\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n| 기준 | 판정 | 근거 |\n|---|---|---|\n"
                          "| 1 | 통과 | 읽음 |\n\n## 짚음\n- 없음\n\n## 주장-출처 대조\n- 없음\n\n## 판단 대조\n- 없음\n".format(now))
    run_dir.task_dir("T001").joinpath(lib.FACTS_FILE).write_text("# 사실\n", encoding="utf-8")
    write(run_dir.task_dir("T001") / "judge-run.md", RUN_JUDGE.format(now=now))


def notify_ok(run_dir):
    return screen.build(str(run_dir.path), "T001")["notify_ok"]


# ---------------------------------------------------------------- 알림을 막는 성질

PROPERTY_RUN = re.compile(r"((?:[가-힣]+·)+[가-힣]+) 표지")   # `범위·비용·… 표지`


def asking_words(path):
    """main-order 문서의 경계 사이 규칙 줄에서 「{성질·성질·…} 표지」의 성질 낱말."""
    found = [m.group(1) for l in lines_with(path, "경계 사이 규칙") for m in PROPERTY_RUN.finditer(l)]
    assert len(found) == 1, (path.name, found)
    return found[0].split("·")


ASKING_DOCS = ((CHANGE_ORDER, "change"), (INFRA_ORDER, "infra-design"))


@pytest.mark.parametrize("path", [p for p, _ in ASKING_DOCS], ids=[k for _, k in ASKING_DOCS])
def test_asking_properties_match_main_order_words(path):
    assert "·".join(asking_words(path)) == "·".join(screen.ASKING_PROPERTIES)


@pytest.mark.parametrize("path, kind", ASKING_DOCS, ids=[k for _, k in ASKING_DOCS])
def test_asking_properties_in_document_hold_back_the_notice(run_dir, path, kind):
    """문서가 적은 성질마다 「알릴 것」에 그 성질이 붙은 항목이 있으면 알림으로 지나가지 않는다. `없음`이면 지나간다(양성 대조)."""
    between_task(run_dir, kind, notify="- 이름을 규약대로 [성질: 없음]")
    assert notify_ok(run_dir) is True
    for word in asking_words(path):
        between_task(run_dir, kind, notify="- 이름을 규약대로 [성질: {}]".format(word))
        assert notify_ok(run_dir) is False, word


# ---------------------------------------------------------------- 경계 사이 kind의 알림

def table_column(path, column):
    """등록표 문서 첫 표의 {첫 칸: column 칸}."""
    rows = []
    for line in read(path).splitlines():
        if line.startswith("|"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif rows:
            break
    head = rows[0]
    assert column in head, (path.name, head)
    i = head.index(column)
    return {r[0]: r[i] for r in rows[2:] if len(r) == len(head)}


def doc_between_kinds():
    found = sorted(k for k, v in table_column(KINDS_TABLE, "boundary").items() if v == "between")
    assert found, "등록표에 boundary between 행 없음"
    return found


def test_between_kinds_are_the_registry_rows():
    assert set(doc_between_kinds()) == kinds.BETWEEN_KINDS


@pytest.mark.parametrize("kind", doc_between_kinds())
def test_between_kind_notice_screen_and_gate_agree(run_dir, kind):
    """같은 조건(1.3.0 시작, 성질 없음)에서 물을 것이 없으면 화면이 알림 가능이고 전이 관문이 받는다. 물을 것이 있으면 둘 다 거부."""
    for decide, expected in (("- 없음", True), ("- 버튼을 위에 둘지 아래에 둘지: (가) 위 / (나) 아래 [성질: 없음]", False)):
        between_task(run_dir, kind, decide=decide)
        ok, why = screen.notify_status(str(run_dir.path), "T001")
        assert ok is expected, (kind, why)
        p = run_script("task_set", run_dir.path, "T001", "--status", "완료", "--record", "알림|지나감|")
        assert run_dir.tasks()["T001"]["status"] == ("완료" if ok else "자체검증"), (kind, p.output)
        if ok:
            assert p.returncode == 0, (kind, p.output)
        else:
            assert p.returncode == 3 and "알림 불가" in p.output, (kind, p.output)


# ---------------------------------------------------------------- 글자 예산

BUDGET_PARTS = {"질문": "ask", "전제": "premise", "경계 보고": "boundary", "머리 칸": "head"}   # 문서의 글 이름 → BUDGET 열쇠(낱말 대응)


def budget_section():
    body = lib.sections(read(SCREEN_CELLS), level=3).get("글자 예산")
    assert body, "screen-cells.md에 「글자 예산」 절 없음"
    return body


def test_budget_values_match_plain_text_budget():
    """「글자 예산」 절의 「{글 이름}(하나) {n}자」 = plain_text.BUDGET(값이 있는 넷). 같은 글 이름이 다시 나와도 같은 값이다."""
    found = {}
    for name, number in re.findall(r"({})(?: 하나)? ([\d,]+)자".format("|".join(BUDGET_PARTS)), budget_section()):
        found.setdefault(BUDGET_PARTS[name], set()).add(int(number.replace(",", "")))
    assert found == {k: {v} for k, v in plain_text.BUDGET.items() if v is not None}


def test_budget_warning_name_is_on_the_screen_of_an_over_budget_question(run_dir):
    """절이 적은 경고 이름이 질문 예산을 넘긴 화면의 글자 수 경고 줄 머리에 있다. 예산 안의 같은 화면에는 글자 수 경고가 없다."""
    names = re.findall(r"`(![^`]+)`", budget_section())
    assert len(names) == 1, names

    def count_warnings(head):
        run_dir.task("T001", "설계", kind="design", block="설계", status="승인대기", **V130)
        run_dir.result("T001", screen_result(decide="- {}: (가) 위 / (나) 아래 [성질: 없음]".format(head)))
        judged(run_dir)
        p = run_script("screen", run_dir.path, "T001")
        assert p.returncode == 0, p.output
        return [l for l in p.stdout.splitlines() if "글자 수" in l]

    lines = count_warnings("버튼을 어디에 둘지 " + "가" * plain_text.BUDGET["ask"])
    assert len(lines) == 1 and lines[0].startswith(names[0]), lines
    assert "> {}".format(plain_text.BUDGET["ask"]) in lines[0]
    assert count_warnings("버튼을 어디에 둘지") == []


# ---------------------------------------------------------------- 선택지 문장의 자리

def option_forms():
    forms = re.findall(r"`(선택지 \([가-힣]\)의 [^`]*)`", read(RESULT_FILE))
    assert len(forms) == 3, forms   # (가)의 문장, (나)의 문장, (가)의 앞 정본 줄
    return forms


def test_option_text_forms_in_result_file_are_caught_by_option_text():
    """문서의 꼴을 채워 하위 줄로 쓰면 OPTION_TEXT가 잡는다(질문에서 빠짐). 같은 자리의 다른 하위 줄은 잡지 않는다."""
    for form in option_forms():
        assert report.OPTION_TEXT.match("  - " + fill(form, 파일="design/a.md", 줄="3")), form
    assert not report.OPTION_TEXT.match("  - 효과 비교: (가) 5분 / (나) 9분")


def test_option_text_note_and_unfold_are_in_result_file():
    """화면이 남기는 안내 줄(OPTION_NOTE) 글자 그대로와 「펼침」이 문서 한 줄에 있다."""
    lines = lines_with(RESULT_FILE, "`{}`".format(report.OPTION_NOTE.strip()))
    assert len(lines) == 1 and "펼침" in lines[0]


# ---------------------------------------------------------------- 답 꼴

def answer_forms():
    """approval.md 「묻는 방법」의 1.3.0 화면 줄에서 답 꼴 괄호 안의 백틱 꼴."""
    lines = lines_with(APPROVAL, "1.3.0 화면", "`진행`")
    assert len(lines) == 1, lines
    m = re.search(r"\(([^()]*`[^()]*)\)", lines[0])
    assert m, lines[0]
    forms = re.findall(r"`([^`]+)`", m.group(1))
    assert "진행" in forms and "멈춤" in forms, forms
    return forms


def test_answer_forms_in_approval_are_read_without_asking_again(run_dir):
    """꼴마다 자리 표시를 채운 답을 1.3.0 화면이 되물음 없이 푼다. 꼴 밖의 답은 되묻는다(대조)."""
    run_dir.task("T001", "사진 저장 설계", kind="design", block="설계", status="승인대기", **V130)
    run_dir.result("T001", DESIGN)
    judged(run_dir)
    p = run_script("screen", run_dir.path, "T001", "--save")
    assert p.returncode == 0, p.output
    # DESIGN 화면: 질문 1은 전1(전제), 질문 2가 (가)/(나) 결정, 「정한 것」의 결정 1.
    # 경계 보고 끝의 답(BOUNDARY_ANSWER의 꼴)은 그 답 줄의 안내대로 질문의 답을 모두 앞에 쓴다
    whole = set(boundary_forms())
    for form in answer_forms():
        text = fill(form, n="1" if form.startswith(("전", "결정")) else "2", 조건="배포는 밤에")
        text = "전1 됨, 2가, " + text if form in whole else text
        p = run_script("screen", run_dir.path, "T001", "--answer", text)
        assert p.returncode == 0 and "되물음" not in p.output, (form, text, p.output)
    assert run_script("screen", run_dir.path, "T001", "--answer", "전1 됨, 2가, 진행해").returncode == 3


def boundary_forms():
    head = report.BOUNDARY_ANSWER.split("   (")[0]
    assert head.startswith("답  "), head
    return head[len("답  "):].split(" / ")


def test_answer_forms_boundary_answer_line_is_within_document_forms():
    """경계 보고 답 줄(report.BOUNDARY_ANSWER)이 보이는 꼴은 문서의 꼴 가운데 있다."""
    shown = boundary_forms()
    assert len(shown) >= 2 and set(shown) <= set(answer_forms()), shown


# ---------------------------------------------------------------- 전제 셋 이내

def premise_cap_word():
    body = lib.sections(read(SCREEN_CELLS), level=3).get("전제와 정한 것")
    assert body, "screen-cells.md에 「전제와 정한 것」 절 없음"
    words = [w for l in body.splitlines() if "이내" in l for w in re.findall(r"(?<![가-힣])(\S+) 이내", l) if w in NUMBER_WORDS]
    assert len(words) == 1, words
    return words[0]


def test_premise_cap_word_matches_premise_cap():
    assert NUMBER_WORDS[premise_cap_word()] == lib.PREMISE_CAP


def test_premise_cap_counts_from_the_line_after_the_cap():
    """꼴이 바른 전제 줄 상한+1개: 상한까지는 problem 없음, 다음 줄은 상한 낱말이 든 problem."""
    cap = lib.PREMISE_CAP
    text = "".join("- 전{0} 물음 {0} | 막아 세움: 아니오 | 모르면: 가정 {0}\n".format(i) for i in range(1, cap + 2))
    rows = lib.premise_rows(text)
    assert [bool(r["problem"]) for r in rows] == [False] * cap + [True]
    assert premise_cap_word() in rows[-1]["problem"] and "전{}".format(cap + 1) in rows[-1]["problem"]


# ---------------------------------------------------------------- 고침 답의 기록 꼴 (HB-51)

def fix_record_form():
    """approval.md 「답의 처리」 표의 「산출물을 바꾸는 답」 행에 적힌 고침 지점의 `--record` 꼴."""
    rows = [l for l in lines_with(APPROVAL, "--record \"고침|") if l.startswith("| 산출물을 바꾸는 답")]
    assert len(rows) == 1, rows
    forms = re.findall(r"`(--record \"고침\|[^`]*)`", rows[0])
    assert len(forms) == 1, rows[0]
    return forms[0]


def test_fix_record_form_is_shown_by_the_approval_point_rejection(run_dir):
    """승인 지점에 적은 고침 답의 거부 문구가 문서의 꼴을 그대로 보이고, 그 꼴을 채운 답은 받는다."""
    form = fix_record_form()
    run_dir.task("T001", "기록 꼴", status="승인대기", started_version="1.3.0", rules="2")
    p = run_script("task_set", run_dir.path, "T001", "--record", "승인|2(가)로 고침|2가 고쳐")
    assert p.returncode == 3 and form in p.output, p.output
    assert form in task_set.FIX_ON_APPROVAL
    raw = fill(form, 결정="2(가)로 고침", 원문="2가 고쳐")[len("--record "):].strip('"')
    p = run_script("task_set", run_dir.path, "T001", "--record", raw)
    assert p.returncode == 0, p.output


# ---------------------------------------------------------------- 반환 전 판정 파일 검사 (HB-38, 설계 harness-defects 5절 C1, AC-06)

def check_judge_command():
    """read-judge 정의 「역할 고유 규칙」에 적힌 반환 전 검사 명령의 (스크립트 이름, 옵션 목록)."""
    rows = lines_with(READ_JUDGE_DEF, "반환 전", "--check-judge")
    assert len(rows) == 1, rows
    cmds = re.findall(r"`python \$\{CLAUDE_PLUGIN_ROOT\}/scripts/(\w+)\.py \{실행 폴더\} \{id\} ([^`]*)`", rows[0])
    assert len(cmds) == 1, rows[0]
    return cmds[0][0], cmds[0][1].split()


def test_check_judge_command_in_the_read_judge_definition_is_the_script_option(run_dir):
    """정의의 명령 글자가 task_set.py의 옵션 이름이고, 그 명령을 그대로 돌리면 짝이 어긋난 판정 파일에서 종료 3, 맞으면 0이다."""
    from test_judge_points import OFF_CLAIMS, OFF_POINTS, design_task, judge_text as points_judge
    script, options = check_judge_command()
    assert (script, options) == ("task_set", [task_set.CHECK_JUDGE])
    assert task_set.CHECK_JUDGE in task_set.__doc__
    design_task(run_dir, judge=points_judge(OFF_POINTS, OFF_CLAIMS))
    p = run_script(script, run_dir.path, "T001", *options)
    assert p.returncode == 3, p.output
    design_task(run_dir)
    p = run_script(script, run_dir.path, "T001", *options)
    assert p.returncode == 0, p.output


# ---------------------------------------------------------------- 곳 답 없이 승인으로 가는 판본 (HB-46, 설계 harness-defects 5절 D, D-17, AC-14)

PLACE_ANSWER_RULE = re.compile(r"(\d+\.\d+\.\d+)부터 ([^().]*곳 답[^().]*)")


def place_answer_rules(lines):
    """줄들에서 `{판본}부터 …곳 답…` 규칙 (판본, 문장)."""
    return [m.groups() for line in lines for m in PLACE_ANSWER_RULE.finditer(line)]


def test_place_answer_version_is_the_same_in_both_documents_and_the_code():
    """approval.md 옛 코드 확인 카드 줄과 verify/main-order.md 「코드 확인」이 같은 판본·같은 문장으로 말하고, 그 판본이 places.py의 문턱이다."""
    approval = place_answer_rules(lines_with(APPROVAL, "코드 확인"))
    order = place_answer_rules(lib.sections(read(VERIFY_ORDER)).get("코드 확인", "").splitlines())
    assert len(approval) == 1 and len(order) == 1, (approval, order)
    assert approval == order
    assert approval[0][0] == lib.RULES_V130


# ---------------------------------------------------------------- 최종 CI 이어받음 (D-27 (나), 설계 harness-defects 5절 H2, D-32·D-33, AC-27)

JUDGE_RUN_FILE = ROOT / "references" / "formats" / "judge-run-file.md"
WRAP_RUN_CHECK = ROOT / "references" / "kinds" / "wrap-up" / "run-check.md"
CODE_RUN_CHECK = ROOT / "references" / "kinds" / "implementation" / "run-check.md"
SCOPE_VALUE = re.compile(r"`- 범위: ([^`{}]+)`")
KEY_BEFORE_SLOT = re.compile(r"`- ([^`:{}]+): \{")


def test_inherit_scope_and_record_words_in_the_documents_are_the_script_constants():
    """judge-run-file.md·wrap-up/run-check.md가 적는 범위 값은 `전체 검증`과 `devflow_lib.INHERITED_SCOPE`뿐이고 둘 다 이어받은 범위를 적는다.
    서식의 이어받음 줄 키는 `INHERITED_CI`, 코드 task 절 제목은 `FULL_CI_RECORD`이고 코드 task 실행 판정 문서가 같은 절 이름을 쓴다."""
    for path in (JUDGE_RUN_FILE, WRAP_RUN_CHECK):
        scopes = set(SCOPE_VALUE.findall(read(path)))
        assert lib.INHERITED_SCOPE in scopes and scopes <= {lib.FULL_CI_SCOPE, lib.INHERITED_SCOPE}, (path.name, scopes)
    assert lib.INHERITED_CI in KEY_BEFORE_SLOT.findall(read(JUDGE_RUN_FILE))
    assert "`## {}`".format(lib.FULL_CI_RECORD) in read(JUDGE_RUN_FILE)
    assert "「{}」".format(lib.FULL_CI_RECORD) in read(CODE_RUN_CHECK)


def test_inherit_ci_command_in_the_wrap_up_run_check_is_the_script_option(run_dir):
    """wrap-up/run-check.md에 적힌 원천 확인 명령이 task_set.py가 받는 옵션이고, 그 명령을 그대로 돌리면 마무리에서 원천 한 줄을 찍는다."""
    from test_final_ci_inherit import WRAP, one_flow
    rows = lines_with(WRAP_RUN_CHECK, task_set.INHERIT_CI)
    cmds = [c for row in rows for c in re.findall(r"`python \$\{CLAUDE_PLUGIN_ROOT\}/scripts/(\w+)\.py \{실행 폴더\} \{id\} ([^`]*)`", row)]
    assert len(cmds) == 1, rows
    script, options = cmds[0][0], cmds[0][1].split()
    assert (script, options) == ("task_set", [task_set.INHERIT_CI])
    assert task_set.INHERIT_CI in task_set.__doc__
    one_flow(run_dir)
    p = run_script(script, run_dir.path, WRAP, *options)
    assert p.returncode == 0 and p.stdout.startswith("이어받을 CI: T011 commit "), p.output
