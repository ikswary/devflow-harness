"""1.3.0 B: 판정 파일 「짚음」·「주장-출처 대조」(구현 설계 2절 B, 7판 규칙 4.2·5.1·5.3).

- 짚음은 실패가 아니다. 「통과 못 한 기준」만 재시도를 부르고(`task_set.failed_numbers`), 짚음 줄의 `기준 n`은 세지 않는다.
- 갈래 셋: 물을 것 / 하네스가 고칠 것 / 그대로 둠. 하네스가 고칠 것은 다섯 종류(문서 어긋남, 셈 잘못, 빠진 줄, 인용 줄 번호,
  이유 문장)로 한정하고, 그 밖이거나 까닭에 (a)~(d)가 있으면 물을 것으로 올린다.
- 물을 것 가운데 깨지는 조건이 있는 것만 즉시 질문으로, 두 개까지(차례: 범위·비용·밖 > 보안 > 어긋남 > 그 밖). 나머지는 보고로.
- 1.3.0부터 시작한 task의 judge.md는 두 절이 있어야 하고, 사실 파일(facts.md)이 있어야 하며, 사실 파일이 판정 뒤에 바뀌면 R3이다.
"""
import os
import time
from datetime import datetime

import devflow_lib as lib
import task_set
from conftest import write

V130 = {"started_version": "1.3.0", "rules": "2"}
V121 = {"started_version": "1.2.1", "rules": "2"}

POINTS = ("- 오류 코드 `E_TIMEOUT`을 만드는 곳이 없음 | 갈래: 물을 것 | 까닭: (c) 원인이 코드 | 깨짐: 있음 시간 초과 때 빈 화면 | 근거: src/a.ts:12\n"
          "- 두 문서의 한도 값이 다름 | 갈래: 하네스가 고칠 것 | 까닭: 문서 어긋남 | 근거: design/a.md:3, spec/b.md:8\n"
          "- 이름이 길다 | 갈래: 그대로 둠 | 까닭: 관례 | 근거: src/b.ts:4\n"
          "- 시간 초과 값이 줄과 다름 | 갈래: 물을 것 | 까닭: 주장-출처 어긋남 | 근거: src/a.ts:20\n"
          "- 기존 시험이 없다는 말에 근거가 없음 | 갈래: 물을 것 | 까닭: 주장-출처 인용 없음 | 근거: 없음\n")
CLAIMS = ("- 재시도는 세 번이다 | 인용: src/retry.ts:9 | 대조: 맞음\n"
          "- 시간 초과는 30초다 | 인용: src/a.ts:20 | 대조: 어긋남 | 줄은 60초\n"
          "- 기존 시험이 없다 | 인용: 없음 | 대조: 인용 없음\n")


def judge_text(points="- 없음", claims="- 없음", now=None, extra=""):
    now = now or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return ("판정자: rjudge-T001 {}\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n| 기준 | 판정 | 근거 |\n|---|---|---|\n"
            "| 1 | 통과 | 읽음 |\n\n## 짚음\n{}\n\n## 주장-출처 대조\n{}\n{}").format(now, points, claims, extra)


def design_task(run_dir, meta=V130, judge=None, facts=True):
    run_dir.task("T001", "설계", kind="design", block="설계", status="자체검증", **meta)
    run_dir.result("T001", "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n")
    if facts:
        write(run_dir.task_dir("T001") / lib.FACTS_FILE, "# T001 미리 뽑은 사실\n")
    run_dir.judge("T001", judge if judge is not None else judge_text(POINTS, CLAIMS))
    return run_dir.tasks()["T001"]


# ---------------------------------------------------------------- 읽기

def test_points_are_read_with_their_branch_reason_breaking_and_basis(run_dir):
    t = design_task(run_dir)
    points = lib.judge_points(t)
    assert [p["branch"] for p in points][:3] == ["물을 것", "하네스가 고칠 것", "그대로 둠"]
    first = points[0]
    assert first["text"].startswith("오류 코드 `E_TIMEOUT`")
    assert first["breaks"] is True and first["breaks_text"] == "시간 초과 때 빈 화면"
    assert first["basis"] == "src/a.ts:12"
    assert points[1]["breaks"] is False and points[1]["moved"] == ""


def test_harness_fix_outside_the_five_kinds_goes_up_to_ask(run_dir):
    lines = ("- 안내 문구가 틀림 | 갈래: 하네스가 고칠 것 | 까닭: (b) 사람이 보는 문구 | 근거: src/a.ts:1\n"
             "- 함수 이름이 낡음 | 갈래: 하네스가 고칠 것 | 까닭: 이름 정리 | 근거: src/a.ts:2\n"
             "- 합계가 틀림 | 갈래: 하네스가 고칠 것 | 까닭: 셈 잘못 | 근거: design/a.md:9\n")
    points = lib.judge_points(design_task(run_dir, judge=judge_text(lines)))
    assert [p["branch"] for p in points] == ["물을 것", "물을 것", "하네스가 고칠 것"]
    assert points[0]["moved"] and points[1]["moved"] and points[2]["moved"] == ""


def test_empty_section_has_no_points(run_dir):
    assert lib.judge_points(design_task(run_dir, judge=judge_text())) == []


def test_claim_rows_are_read(run_dir):
    rows = lib.claim_rows(design_task(run_dir))
    assert [r["verdict"] for r in rows] == ["맞음", "어긋남", "인용 없음"]
    assert rows[1]["cite"] == "src/a.ts:20" and rows[1]["note"] == "줄은 60초"


# ---------------------------------------------------------------- 화면 자리

def ask(text, why, breaks=True):
    return {"text": text, "branch": "물을 것", "why": why, "breaks": breaks, "breaks_text": "x" if breaks else "",
            "basis": "a:1", "moved": ""}


def test_only_two_breaking_asks_go_now_in_rank_order():
    points = [ask("이름", "그 밖"), ask("권한 검사", "보안"), ask("월 요금", "비용"), ask("나중 일", "범위", breaks=False),
              dict(ask("숫자", "셈 잘못"), branch="하네스가 고칠 것"), dict(ask("이름 길이", "관례"), branch="그대로 둠")]
    places = lib.point_places(points)
    assert [p["text"] for p in places["now"]] == ["월 요금", "권한 검사"]
    assert [p["text"] for p in places["report"]] == ["이름", "나중 일"]
    assert [p["text"] for p in places["fix"]] == ["숫자"]
    assert [p["text"] for p in places["keep"]] == ["이름 길이"]


def test_cap_is_a_parameter():
    places = lib.point_places([ask("a", "범위"), ask("b", "범위"), ask("c", "범위")], cap=1)
    assert len(places["now"]) == 1 and len(places["report"]) == 2


# ---------------------------------------------------------------- 재시도로 세지 않음

def test_failed_numbers_ignore_points_and_claims(run_dir):
    lines = "- 기준 3과 같은 꼴이 다른 곳에도 | 갈래: 물을 것 | 까닭: (a) 길이 둘 | 근거: a:1\n"
    design_task(run_dir, judge=judge_text(lines, "- 기준 4의 근거 | 인용: a:2 | 대조: 어긋남 | x\n"))
    nums, loose = task_set.failed_numbers([str(run_dir.task_dir("T001") / "judge.md")])
    assert nums == [] and loose == []


# ---------------------------------------------------------------- 판정 파일이 갖춰졌는가

def test_new_task_needs_both_sections(run_dir):
    assert lib.judges_present(design_task(run_dir))[0] is True
    no_points = judge_text().replace("## 짚음\n- 없음\n\n", "")
    ok, why = lib.judges_present(design_task(run_dir, judge=no_points))
    assert ok is False and "짚음" in why
    no_claims = judge_text().replace("## 주장-출처 대조\n- 없음\n", "")
    ok, why = lib.judges_present(design_task(run_dir, judge=no_claims))
    assert ok is False and "주장-출처 대조" in why


def test_old_task_needs_neither_section_nor_facts(run_dir):
    old = judge_text().split("## 짚음")[0]
    assert lib.judges_present(design_task(run_dir, meta=V121, judge=old, facts=False))[0] is True


def test_point_line_without_branch_is_a_format_problem(run_dir):
    t = design_task(run_dir, judge=judge_text("- 갈래가 없는 줄 | 까닭: (a) | 근거: a:1\n"))
    ok, why = lib.judges_present(t)
    assert ok is False and "갈래" in why


def test_mismatched_claim_needs_a_point(run_dir):
    t = design_task(run_dir, judge=judge_text("- 없음", CLAIMS))
    ok, why = lib.judges_present(t)
    assert ok is False and "어긋남" in why


def test_new_task_of_a_fact_kind_needs_the_facts_file(run_dir):
    ok, why = lib.judges_present(design_task(run_dir, facts=False))
    assert ok is False and lib.FACTS_FILE in why


def test_facts_changed_after_the_judgment_is_r3(run_dir):
    past = datetime.fromtimestamp(time.time() - 600).strftime("%Y-%m-%d %H:%M:%S")
    t = design_task(run_dir, judge=judge_text(now=past))
    judge = run_dir.task_dir("T001") / "judge.md"
    os.utime(judge, (time.time() - 600, time.time() - 600))
    os.utime(run_dir.task_dir("T001") / "result.md", (time.time() - 900, time.time() - 900))
    t = dict(t, status="완료")
    codes = [code for code, msg, _ in lib.record_check(t) if lib.FACTS_FILE in msg]
    assert codes == ["R3"]


def test_text_with_bars_and_lines_starting_with_none_are_kept(run_dir):
    lines = ("- 없음 표기가 두 곳에서 다름 | 갈래: 하네스가 고칠 것 | 까닭: 문서 어긋남 | 근거: a:1\n"
             "- 유니언 `A | B` 꼴이 틀림 | 갈래: 물을 것 | 까닭: (c) 코드 | 깨짐: 없음 | 근거: a:2\n"
             "  - 근거 더: b:2\n")
    points = lib.judge_points(design_task(run_dir, judge=judge_text(lines)))
    assert [p["text"] for p in points] == ["없음 표기가 두 곳에서 다름", "유니언 `A | B` 꼴이 틀림"]
    assert points[1]["basis"].startswith("a:2") and "b:2" in points[1]["basis"]
    assert lib.point_problems(run_dir.tasks()["T001"]) == []


def test_claim_text_with_bars_and_note(run_dir):
    claims = "- 유니언 `A | B`를 받는다 | 인용: src/t.ts:3 | 대조: 맞음\n- x | 인용: a:1 | 대조: 어긋남 | 줄은 | 다른 것\n"
    lines = "- x가 다름 | 갈래: 물을 것 | 까닭: 주장-출처 어긋남 | 깨짐: 없음 | 근거: a:1\n"
    rows = lib.claim_rows(design_task(run_dir, judge=judge_text(lines, claims)))
    assert rows[0]["claim"] == "유니언 `A | B`를 받는다" and rows[0]["verdict"] == "맞음"
    assert rows[1]["note"] == "줄은 | 다른 것"


def test_each_mismatch_needs_its_own_point(run_dir):
    one = "- x가 다름 | 갈래: 물을 것 | 까닭: 주장-출처 어긋남 | 근거: a:1\n"
    ok, why = lib.judges_present(design_task(run_dir, judge=judge_text(one, CLAIMS)))
    assert ok is False and "2줄" in why


def test_breaking_without_condition_is_a_problem(run_dir):
    t = design_task(run_dir, judge=judge_text("- a | 갈래: 물을 것 | 까닭: 범위 | 깨짐: 있음 | 근거: a:1\n"))
    assert any("조건이 없음" in x for x in lib.point_problems(t))


def test_rank_reads_only_the_reason():
    a = ask("보안 헤더가 범위 밖 화면에도", "보안")
    b = ask("이름", "(a) 고치는 길이 둘 이상이고 범위가 다르다")
    c = ask("요금", "비용")
    assert [lib.point_rank(x) for x in (a, b, c)] == [1, 3, 0]


def test_archive_keeps_the_facts_the_judge_read(run_dir):
    t = design_task(run_dir, judge=judge_text().replace("## 통과 못 한 기준\n- 없음", "## 통과 못 한 기준\n- 기준 1: 틀림"))
    doc = lib.Doc(t["_path"])
    task_set.archive_judge(str(run_dir.path), t, doc)
    folder = run_dir.task_dir("T001")
    assert (folder / "facts.r1.md").is_file() and (folder / lib.FACTS_FILE).is_file()


def test_named_criterion_failure_is_not_read_as_a_number(run_dir):
    text = judge_text().replace("## 통과 못 한 기준\n- 없음", "## 통과 못 한 기준\n- 기준 성질(writer 2절): 선택지에 위험이 없음. 머리 기준 3과도 닿음")
    design_task(run_dir, judge=text)
    nums, loose = task_set.failed_numbers([str(run_dir.task_dir("T001") / "judge.md")])
    assert nums == [] and loose and loose[0].startswith("기준 성질")


def test_claim_row_with_empty_last_cell(run_dir):
    """목적 시험 T051: 판정자가 메모 칸을 비우고 `| 대조: 맞음 |`로 끝낸 줄."""
    claims = "- 결함을 남김: 쓰기 실패 | 인용: docs/d.md:67 | 대조: 맞음 |\n- y | 인용: 없음 | 대조: 인용 없음 |  \n"
    lines = "- y에 근거가 없음 | 갈래: 하네스가 고칠 것 | 까닭: 주장-출처, 인용 줄 번호 | 근거: a:1\n"
    t = design_task(run_dir, judge=judge_text(lines, claims))
    rows = lib.claim_rows(t)
    assert [r["verdict"] for r in rows] == ["맞음", "인용 없음"] and rows[0]["note"] == ""
    assert lib.point_problems(run_dir.tasks()["T001"]) == []


def test_two_ways_need_a_recommendation(run_dir):
    """목적 시험 T051(J21): 짚음 질문에 추천이 없자 승인자가 실제 이력과 반대 길을 골랐다. 7판 질문은 추천을 달았다."""
    bare = "- x가 틀림 | 갈래: 물을 것 | 까닭: (a) | 길: (가) 코드 / (나) 문구 | 깨짐: 없음 | 근거: a:1\n"
    points = lib.judge_points(design_task(run_dir, judge=judge_text(bare)))
    assert "추천" in points[0]["problem"]
    good = bare.replace(" | 깨짐:", " | 추천: (가) 원인을 고침 | 깨짐:")
    points = lib.judge_points(design_task(run_dir, judge=judge_text(good)))
    assert points[0]["problem"] == "" and points[0]["recommend"] == "(가) 원인을 고침"


def test_failure_line_reads_only_its_own_criterion(run_dir):
    """목적 시험 2회차 T004: `- 기준 6: … 탐침 정의의 기준 2를 통과할 수 없고`가 고칠 기준 2, 6이 되었다."""
    text = judge_text().replace("## 통과 못 한 기준\n- 없음", "## 통과 못 한 기준\n- 기준 6: 행이 어긋남. 탐침 정의의 기준 2(probe.md:45)를 통과할 수 없고\n- 기준 8: 관점: 보안")
    design_task(run_dir, judge=text)
    nums, loose = task_set.failed_numbers([str(run_dir.task_dir("T001") / "judge.md")])
    assert nums == [6, 8] and loose == []
