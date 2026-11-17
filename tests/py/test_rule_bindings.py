"""규칙과 검사를 묶는 시험: 판정 쪽(설계 harness-tests 4.6절 표의 R6 일곱 줄, 결정 D10).

같은 규칙이 판정자가 읽는 문서와 스크립트 상수·파서에 따로 있다. 문서를 원천으로 두고, 시험이 문서에서 글자(틀 줄의 칸 이름과
갈래 값, 괄호 목록, 상한 낱말, 절 이름)를 꺼내 상수와 견주고, 틀의 자리 표시를 표본 값으로 채운 줄을 파서가 읽는지 본다.
시험 안에 문서 문장의 사본을 두지 않는다(원칙 문서 2절). 문서는 고치지 않으므로 어긋나면 스크립트 쪽을 고친다.

| 규칙 | 문서 | 시험 |
|---|---|---|
| 짚음 틀 | `references/formats/judge-file.md` 「짚음」 | `test_point_template_*` |
| 주장-출처 틀 | 같은 파일 「주장-출처 대조」 | `test_point_and_claim_field_names_*`, `test_claim_template_*` |
| 통과 못 한 기준 틀 | 같은 파일 「통과 못 한 기준」 | `test_failed_item_template_*`, `test_undecided_*` |
| 하네스가 고칠 것 다섯 | `judge-file.md` 끝 문단, `references/roles/judge-points.md` 「갈래」 | `test_harness_fix_kinds_*` |
| 즉시 질문 상한과 차례 | `judge-points.md` 「깨짐」, `judge-file.md` 끝 문단 | `test_now_cap_*`, `test_now_order_*` |
| 짚음 글 예산 | `judge-points.md` 「갈래」 | `test_point_text_budget_*` |
| 사실 파일 | `references/formats/facts-file.md` | `test_facts_*` |
"""
import re

import devflow_lib as lib
import judge_facts
import kinds
import plain_text
from conftest import ROOT, write

JUDGE_FILE = ROOT / "references" / "formats" / "judge-file.md"
JUDGE_POINTS = ROOT / "references" / "roles" / "judge-points.md"
FACTS_FILE = ROOT / "references" / "formats" / "facts-file.md"

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
