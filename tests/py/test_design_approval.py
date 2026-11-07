"""1.2.0 A8: 설계 승인과 요구사항 종합(설계 7.2절, 7.6절, 5.1절, 5.3절 4).

- 설계가 둘 이상이면 구현은 실행 전체 설계를 기다린다. 물결 밖의 뒤늦은 설계는 고친 판을 요구하고, 도는 흐름은 멈추지 않는다.
- 설계 화면은 7.2절 차례이고, `볼 곳`은 kind마다 스크립트가 센다. 한 장 머리에 판과 터미널 번호를 적는다.
- 답이나 판정자 대안 문장만 옮긴 고친 판은 자식 행과 결정 번호가 그대로면 알림이다.
- 요구사항 종합은 블록의 마지막 상세에 실리고, 그 전에는 설계를 묻지 않는다.
- 옛 판본으로 시작한 task는 지금 규칙 그대로다.
"""
import re

import pytest

import board
import devflow_lib as lib
import kinds
import places
import screen
import visual
from conftest import run_script, write
from test_review_contract import JUDGED, judged, notifies, result
from test_sheet import child_row, page_of, screen_of
from test_sheet import task as bare_task

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}
ANSWER_ORIGIN = "사용자 T009 2026-11-05 10:00:00"


def task(run_dir, **kw):
    """판정까지 끝난 묻는 task. 판정 파일이 없으면 기록 점검 항목이 번호를 먼저 가져간다."""
    bare_task(run_dir, **kw)
    judged(run_dir)


def ready_of(run_dir):
    return run_script("board", run_dir.path, "--ready").stdout


def design(run_dir, tid, flow, status="완료", meta=NEW, **more):
    run_dir.task(tid, "설계 " + flow, kind="design", block="설계", status=status, flow=flow, **dict(meta, **more))


def code(run_dir, tid, flow, parent, kind="implementation", status="대기", **more):
    run_dir.flow(flow)
    run_dir.task(tid, "구현 " + flow, kind=kind, block="구현", status=status, flow=flow, parent=parent, **more)


def run_wide(run_dir, tid, depends, status="완료", kind="design"):
    run_dir.task(tid, "설계 — 실행 전체", kind=kind, block="설계", status=status, depends_on=depends, run_wide="true", **NEW)


# ---------------------------------------------------------------- 실행 전체 설계를 기다림

def test_one_design_does_not_wait(run_dir):
    design(run_dir, "T001", "a")
    code(run_dir, "T002", "a", "T001")
    assert "- T002 구현 a [implementation]" in ready_of(run_dir)


def test_two_designs_without_run_wide_wait_and_say_so(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b", status="승인대기")
    code(run_dir, "T003", "a", "T001")
    out = ready_of(run_dir)
    assert "- T003 구현 a [implementation] (실행 전체 설계 필요" in out
    assert "실행 전체 설계 필요: T001, T002" in out


def test_code_waits_until_run_wide_is_done(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    code(run_dir, "T003", "a", "T001")
    run_wide(run_dir, "T004", ["T001", "T002"], status="승인대기")
    assert "(실행 전체 설계 기다림: T004)" in ready_of(run_dir)
    run_wide(run_dir, "T004", ["T001", "T002"])
    assert "- T003 구현 a [implementation] (코드 폴더 필요" in ready_of(run_dir)


def test_run_wide_design_itself_does_not_count_as_a_design(run_dir):
    design(run_dir, "T001", "a")
    run_wide(run_dir, "T002", ["T001"], status="대기")
    code(run_dir, "T003", "a", "T001")
    out = ready_of(run_dir)
    assert "(실행 전체 설계" not in out and "실행 전체 설계 필요" not in out


def test_closed_designs_do_not_make_a_second_design(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b", status="백로그")
    design(run_dir, "T005", "c", status="보류")
    code(run_dir, "T003", "a", "T001")
    assert "실행 전체 설계" not in ready_of(run_dir)


def test_flow_fix_waits_but_fixes_flow_and_root_cause_do_not(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    run_dir.flow("a")
    run_dir.flow("fixes", role="fixes")
    run_dir.task("T003", "흐름 수정", kind="fix", block="구현", flow="a", parent="T009")
    run_dir.task("T009", "검증", kind="flow-verify", block="검증", status="완료", flow="a", parent="T001", **NEW)
    run_dir.task("T004", "수정 흐름", kind="fix", block="구현", flow="fixes", parent="T009")
    run_dir.task("T005", "원인", kind="root-cause", block="원인 분석", flow="c")
    out = ready_of(run_dir)
    assert "- T003 흐름 수정 [fix] (실행 전체 설계 필요" in out
    assert "- T004 수정 흐름 [fix]" in out and "T004 수정 흐름 [fix] (실행" not in out
    assert "- T005 원인 [root-cause]" in out and "T005 원인 [root-cause] (실행" not in out


def test_code_of_a_root_cause_does_not_wait(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    run_dir.task("T003", "원인", kind="root-cause", block="원인 분석", status="완료", **NEW)
    code(run_dir, "T004", "c", "T003")
    assert "T004 구현 c [implementation] (실행" not in ready_of(run_dir)


def test_old_designs_keep_the_old_rule(run_dir):
    design(run_dir, "T001", "a", meta=OLD)
    design(run_dir, "T002", "b", meta=OLD)
    code(run_dir, "T003", "a", "T001")
    out = ready_of(run_dir)
    assert "실행 전체 설계" not in out and "- T003 구현 a [implementation] (코드 폴더 필요" in out


@pytest.mark.parametrize("status", ["보류", "백로그"])
def test_closed_run_wide_goes_to_the_end_question(run_dir, status):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    code(run_dir, "T003", "a", "T001")
    run_wide(run_dir, "T004", ["T001", "T002"], status=status)
    out = ready_of(run_dir)
    assert "(실행 전체 설계 닫힘: T004)" in out
    assert "! 끝 질문" in out and "T004" in out.split("! 끝 질문")[1]


def test_closed_run_wide_also_holds_the_flow_verify(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    code(run_dir, "T003", "a", "T001")
    run_dir.task("T005", "검증", kind="flow-verify", block="검증", flow="a", parent="T001")
    run_wide(run_dir, "T004", ["T001", "T002"], status="보류")
    out = ready_of(run_dir)
    assert "지금 시작할 수 있는 task 0개" in out and "! 끝 질문" in out


def three_with_one_held(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    design(run_dir, "T005", "c", status="보류")
    code(run_dir, "T003", "a", "T001")
    run_wide(run_dir, "T004", ["T001", "T002", "T005"], status="대기")


def test_held_design_blocking_run_wide_tells_the_main_what_to_do(run_dir):
    three_with_one_held(run_dir)
    assert "실행 전체 설계 T004가 닫힌 설계 T005에 막힘: depends_on에서 뺀다" in ready_of(run_dir)


def test_one_of_two_designs_held_also_tells_the_main(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T005", "c", status="보류")
    run_wide(run_dir, "T004", ["T001", "T005"], status="대기")
    assert "실행 전체 설계 T004가 닫힌 설계 T005에 막힘" in ready_of(run_dir)


def test_taking_the_held_design_out_frees_run_wide_and_says_so(run_dir):
    three_with_one_held(run_dir)
    assert run_script("task_set", run_dir.path, "T004", "depends_on=[T001, T002]").returncode == 0
    out = ready_of(run_dir)
    assert "- T004 설계 — 실행 전체 [design]" in out and "막힘" not in out
    bare_task_id = "T006"
    run_dir.task(bare_task_id, "다른 설계 화면", kind="design", block="설계", status="승인대기", flow="d", **NEW)
    run_dir.result(bare_task_id, result())
    judged(run_dir, bare_task_id)
    shown = run_script("screen", run_dir.path, bare_task_id).stdout
    assert "[T005] 보류된 설계를 실행 전체 설계 T004에서 빼고 진행합니다" in shown and "n_notify=0" in shown


def test_no_held_line_after_run_wide_is_done(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T005", "c", status="보류")
    run_wide(run_dir, "T004", ["T001"])
    task_id = "T006"
    run_dir.task(task_id, "다른 설계 화면", kind="design", block="설계", status="승인대기", flow="d", **NEW)
    run_dir.result(task_id, result())
    judged(run_dir, task_id)
    assert "빼고 진행합니다" not in run_script("screen", run_dir.path, task_id).stdout


def test_held_design_reopened_later_asks_for_a_revision(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    run_wide(run_dir, "T004", ["T001", "T002"])
    design(run_dir, "T005", "c", status="대기")
    code(run_dir, "T006", "c", "T005", status="대기")
    design(run_dir, "T005", "c", status="완료")
    out = ready_of(run_dir)
    assert "실행 전체 설계 고친 판 필요: T005" in out


def test_started_flow_is_not_stopped_by_a_covering_run_wide(run_dir):
    design(run_dir, "T001", "a")
    code(run_dir, "T002", "a", "T001", status="완료")
    code(run_dir, "T003", "a", "T001", depends_on=["T002"])
    design(run_dir, "T004", "b")
    code(run_dir, "T005", "b", "T004")
    run_wide(run_dir, "T006", ["T001", "T004"], status="대기")
    out = ready_of(run_dir)
    assert "- T003 구현 a [implementation] (코드 폴더 필요" in out
    assert "- T005 구현 b [implementation] (실행 전체 설계 기다림: T006)" in out


# ---------------------------------------------------------------- 뒤늦은 설계

def test_late_design_asks_for_a_revision_and_running_flows_keep_going(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    run_wide(run_dir, "T004", ["T001", "T002"])
    code(run_dir, "T003", "a", "T001")
    design(run_dir, "T005", "c")
    code(run_dir, "T006", "c", "T005")
    out = ready_of(run_dir)
    assert "- T003 구현 a [implementation] (코드 폴더 필요" in out
    assert "- T006 구현 c [implementation] (실행 전체 설계 고친 판 필요)" in out
    assert "실행 전체 설계 고친 판 필요: T005" in out


def test_revision_of_run_wide_closes_the_late_design(run_dir):
    design(run_dir, "T001", "a")
    design(run_dir, "T002", "b")
    run_wide(run_dir, "T004", ["T001", "T002"])
    design(run_dir, "T005", "c")
    code(run_dir, "T006", "c", "T005")
    run_wide(run_dir, "T007", ["T005"], status="승인대기", kind="change")
    assert "- T006 구현 c [implementation] (실행 전체 설계 기다림: T007)" in ready_of(run_dir)
    run_wide(run_dir, "T007", ["T005"], kind="change")
    out = ready_of(run_dir)
    assert "- T006 구현 c [implementation] (코드 폴더 필요" in out and "고친 판 필요" not in out


def test_second_design_after_the_first_started_stops_only_the_new_code(run_dir):
    design(run_dir, "T001", "a")
    code(run_dir, "T002", "a", "T001", status="완료")
    code(run_dir, "T003", "a", "T001", depends_on=["T002"])
    design(run_dir, "T004", "b")
    code(run_dir, "T005", "b", "T004")
    out = ready_of(run_dir)
    assert "- T003 구현 a [implementation] (코드 폴더 필요" in out
    assert "- T005 구현 b [implementation] (실행 전체 설계 필요" in out
    assert "실행 전체 설계 필요: T004" in out


def test_run_wide_head_says_which_code_it_frees(run_dir):
    design(run_dir, "T002", "a")
    design(run_dir, "T003", "b")
    code(run_dir, "T004", "a", "T002")
    task(run_dir, meta=dict(NEW, run_wide="true"))
    run_wide(run_dir, "T001", ["T002", "T003"], status="승인대기")
    run_dir.result("T001", result())
    assert "승인하면: 기다리던 구현 1개가 시작할 수 있습니다(T004)" in screen_of(run_dir)


def test_head_says_code_waits_for_the_run_wide_design(run_dir):
    task(run_dir, extra="\n## 자식 목록\n나눈 기준: 화면\n\n" + child_row("목록"))
    design(run_dir, "T002", "b")
    assert "구현은 실행 전체 설계 뒤에 시작합니다" in screen_of(run_dir)


# ---------------------------------------------------------------- 설계 화면 차례

def cell_order(out):
    return [m.group(1) for m in re.finditer(r"^■ ([^(\n]+?) \(", out, re.M)]


FULL = {"decide": "- 고를 것 (가) 예", "notify": "- 평범한 결정\n- 성질 붙은 결정 [성질: 비용]", "unverified": "- 운영 DB 가정"}


def test_design_screen_follows_the_order(run_dir):
    task(run_dir, material="이 설계가 한 일", **FULL)
    out = screen_of(run_dir)
    assert out.index("■ 리뷰 자료") < out.index("■ 확인 안 된 것")
    assert cell_order(out) == ["확인 안 된 것", "정해 주실 것", "알릴 것"]


def test_marked_decisions_come_first_and_numbers_follow_the_screen(run_dir):
    task(run_dir, material="한 일", **FULL)
    out = screen_of(run_dir)
    assert "- [1] 운영 DB 가정" in out and "- [2] 고를 것" in out
    assert "- [3] 성질 붙은 결정" in out and "- [4] 평범한 결정" in out


def test_answers_read_the_design_order(run_dir):
    task(run_dir, material="한 일", **FULL)
    assert run_script("screen", run_dir.path, "T001", "--save").returncode == 0
    got = run_script("screen", run_dir.path, "T001", "--answer", "2 가")
    assert got.returncode == 0, got.output
    assert "고를 것" in got.stdout


def test_design_screen_ends_with_the_question(run_dir):
    task(run_dir, material="한 일", **FULL)
    out = screen_of(run_dir)
    line = "질문: 이 접근으로 구현을 시작해도 되는가 — 승인 / 고칠 것이 있음 / 나눠서 다시 / 보류"
    assert line in out and out.index(line) < out.index("counts:")


def test_other_kinds_keep_the_cell_order(run_dir):
    task(run_dir, kind="infra-design", material="한 일", **FULL)
    out = screen_of(run_dir)
    assert cell_order(out) == ["정해 주실 것", "알릴 것", "확인 안 된 것"] and "질문:" not in out


def test_design_change_uses_the_design_order(run_dir):
    task(run_dir, kind="change", sections={"건드릴 파일": "- design/a.md"}, material="한 일", **FULL)
    assert cell_order(screen_of(run_dir)) == ["확인 안 된 것", "정해 주실 것", "알릴 것"]


def test_old_design_keeps_the_cell_order(run_dir):
    task(run_dir, meta=OLD, **FULL)
    out = screen_of(run_dir)
    assert cell_order(out)[:4] == ["정해 주실 것", "하실 일·허용 요청", "알릴 것", "답하신 것의 반영"]
    assert "질문:" not in out


def code_row(title, signature="", kind="implementation", **meta):
    extra = "".join("- {}: {}\n".format(k, v) for k, v in meta.items())
    return ("### 자식: {0}\n- kind: {1}\n- flow: a\n- depends_on: \n- difficulty: 일반\n{2}- 한 줄: 한다\n\n"
            "#### 범위\n- 범위\n#### 판정 기준\n1. 기준\n#### 건드릴 파일\n- src/a.ts\n#### 시그니처와 결정 번호\n{3}\n\n").format(title, kind, extra, signature)


def rows_of(*rows):
    import spawn_children
    return spawn_children.parse_children("## 자식 목록\n나눈 기준: 화면\n\n" + "".join(rows))[1]


def test_counts_only_cell_says_rows_and_tasks_to_read(run_dir):
    rows = code_row("목록") + code_row("권한", "`check()` [보안]") + code_row("[백로그] 나중", "[보안]")
    task(run_dir, extra="\n## 자식 목록\n나눈 기준: 화면\n\n" + rows)
    out = screen_of(run_dir)
    assert "자식 행 2, 판정 통과 뒤 코드를 볼 task 1" in out
    assert re.search(r"n_notify=0", out)


SECURE_SPEC = "- AC-1 일반\n- AC-2 권한을 지킨다 [보안]\n- AC-3 토큰 [보안]\n"


@pytest.mark.parametrize("row,want", [
    (code_row("닫음", closes_ac="AC-2"), 1),
    (code_row("일부", partial_ac="AC-3"), 1),
    (code_row("여럿", closes_ac="AC-1, AC-2"), 1),
    (code_row("일반", closes_ac="AC-1"), 0),
    (code_row("표지", "[보안]"), 1),
    (code_row("제목만 [보안]"), 0),
    (code_row("검증", kind="flow-verify", closes_ac="AC-2"), 0),
])
def test_security_tasks_read_the_rows_and_the_canon(run_dir, row, want):
    write(run_dir.path / "spec" / "a.md", SECURE_SPEC)
    assert screen.security_tasks(str(run_dir.path), rows_of(row)) == want


@pytest.mark.parametrize("meta,signature", [
    ({"closes_ac": ["AC-2"]}, ""), ({"partial_ac": ["AC-3"]}, ""), ({"closes_ac": ["AC-1"]}, ""), ({}, "[보안]"), ({}, ""),
])
def test_security_tasks_agree_with_the_code_check(run_dir, meta, signature):
    write(run_dir.path / "spec" / "a.md", SECURE_SPEC)
    row = code_row("행", signature, **{k: ", ".join(v) for k, v in meta.items()})
    t = dict(meta, _sections={"시그니처와 결정 번호": signature})
    assert screen.security_tasks(str(run_dir.path), rows_of(row)) == int(places.security_marked(str(run_dir.path), t))


def test_security_tasks_on_the_design_screen_read_the_canon(run_dir):
    write(run_dir.path / "spec" / "a.md", SECURE_SPEC)
    task(run_dir, extra="\n## 자식 목록\n나눈 기준: 화면\n\n" + code_row("닫음", closes_ac="AC-2"))
    assert "판정 통과 뒤 코드를 볼 task 1" in screen_of(run_dir)


def test_security_tasks_without_spec_read_the_row_mark_only(run_dir):
    assert screen.security_tasks(str(run_dir.path), rows_of(code_row("표지", "[보안]"), code_row("닫음", closes_ac="AC-2"))) == 1


def test_broken_spec_does_not_stop_the_design_screen(run_dir):
    (run_dir.path / "spec").mkdir(parents=True, exist_ok=True)
    (run_dir.path / "spec" / "a.md").write_bytes("- AC-2 한글 [보안]".encode("cp949"))
    task(run_dir, extra="\n## 자식 목록\n나눈 기준: 화면\n\n" + code_row("표지", "[보안]") + code_row("닫음", closes_ac="AC-2"))
    got = run_script("screen", run_dir.path, "T001")
    assert got.returncode == 0 and "판정 통과 뒤 코드를 볼 task 1" in got.stdout


def test_code_check_reads_security_marks_in_every_requirement_form(run_dir):
    write(run_dir.path / "spec" / "a.md", "- **AC-1** 굵게 [보안]\n1. AC-2 번호 [보안]\n### AC-3 제목 [보안]\n| AC-4 표 [보안] |\n- C-AC-5 앞붙이 [보안]\n| E-AC-7 | 표 앞붙이 [보안] |\n- AC-6 일반\n- AC-6 뒤에 인용 [보안]\n")
    assert places.security_acs(str(run_dir.path)) == {"AC-1", "AC-2", "AC-3", "AC-4", "C-AC-5", "E-AC-7"}
    assert places.devflow_lib.AC_HEAD_RE is lib.AC_HEAD_RE and lib.AC_HEAD_RE is not lib.AC_ROW_RE


# ---------------------------------------------------------------- 실행 전체 설계의 판단 문장

def test_run_wide_design_has_its_own_sentence(run_dir):
    task(run_dir, meta=dict(NEW, run_wide="true"), decide="- 겹침 (가) 각자 진행",
         extra="\n## 자식 목록\n나눈 기준: 관점\n\n" + child_row("보안 관점", kind="full-verify") + child_row("성능 관점", kind="full-verify"))
    out = screen_of(run_dir)
    assert "정하는 것: 흐름 나눔과 겹침, 전·후 명령을 받아들이는가" in out
    assert "질문: 흐름 나눔과 겹침, 전·후 명령을 받아들이는가" in out
    assert "볼 곳: 겹침 질문 1, 전체 검증 관점 2" in out


def test_run_wide_key_is_a_written_key():
    assert ("run_wide", "kv", False) in kinds.TASK_KEYS


# ---------------------------------------------------------------- 볼 곳

SPEC = ("# 요구사항\n\n## 기능 요구사항\n- FR-1 목록을 보인다 [담당이 채움] 20개 (P-1)\n- FR-2 정렬한다\n\n## 인수 기준\n"
        "- AC-1 (FR-1) 목록 20개가 보인다\n"
        "- AC-2 (FR-2) 최근 순이다 [바뀜: src/list.ts:12]\n"
        "  Then 이름 순이던 것이 최근 순이 된다\n"
        "- AC-3 (FR-2) 빈 목록이면 안내 문구가 보인다 [담당이 채움]\n"
        "- AC-4 (FR-1) 새 동작이다\n")


@pytest.mark.parametrize("sections,body", [
    ({"건드릴 파일": "- spec/list.md"}, "- 없음"),
    (None, "- 정본: spec/list.md (기능 요구사항, 인수 기준)"),
])
def test_req_detail_counts_from_the_document_it_wrote(run_dir, sections, body):
    write(run_dir.path / "spec" / "list.md", SPEC)
    task(run_dir, kind="req-detail", sections=sections, decide="- 고를 것 (가) 예", extra="\n## 본문\n" + body + "\n")
    assert "볼 곳: 기존 동작을 바꾸는 요구 1, 담당 값 2, 새 동작 2, 정해 주실 것 1" in screen_of(run_dir)


def test_req_detail_without_marks_counts_new_behavior(run_dir):
    write(run_dir.path / "spec" / "list.md", "- AC-1 한다\n- AC-2 한다\n")
    task(run_dir, kind="req-detail", sections={"건드릴 파일": "- spec/list.md"})
    assert "볼 곳: 기존 동작을 바꾸는 요구 0, 담당 값 0, 새 동작 2, 정해 주실 것 0" in screen_of(run_dir)


def test_ac_rows_read_block_and_skip_fences(lib):
    rows = lib.ac_rows("```\n- AC-9 울타리 안\n```\n### AC-1 제목\nGiven 값 [바뀜: a.ts:1]\n\n- AC-2 둘째\n- FR-3 다른 것 [담당이 채움]\n- AC-2 추적표의 둘째\n")
    assert [r[0] for r in rows] == ["AC-1", "AC-2"]
    assert "[바뀜: a.ts:1]" in rows[0][1] and "[담당이 채움]" not in rows[1][1]


def test_brief_counts_unbracketed_mark(run_dir):
    write(run_dir.path / "spec" / "brief.md", "- 정책 값 20 (담당이 채움)\n- 다른 줄\n")
    task(run_dir, kind="brief", sections={"건드릴 파일": "- spec/brief.md"})
    assert "볼 곳: 정해 주실 것 0, 담당 값 1, 성질 붙은 항목 0" in screen_of(run_dir)


@pytest.mark.parametrize("kind,want", [
    ("question", "볼 곳: 정해 주실 것 1"),
    ("ui-design", "볼 곳: 시안 질문 1, 확인 안 된 것 1"),
    ("infra-design", "볼 곳: 정해 주실 것 1, 하실 일 0, 확인 안 된 것 1"),
    ("design", "볼 곳: 정해 주실 것 1, 하실 일 0, 확인 안 된 것 1, 알릴 결정 0, 성질 붙은 항목 0, 자식 행 0"),
])
def test_each_kind_counts_its_own_places(run_dir, kind, want):
    task(run_dir, kind=kind, decide="- 고를 것 (가) 예", unverified="- 가정")
    out = screen_of(run_dir)
    assert want + " · 대기 중 1개\n" in out


def test_root_cause_counts_fix_options(run_dir):
    task(run_dir, kind="root-cause", extra="\n## 자식 목록\n나눈 기준: 안\n\n" + child_row("가", option="수정안/가") + child_row("나", option="수정안/나"))
    judged(run_dir, run=True)
    assert "볼 곳: 수정안 2, 정해 주실 것 0, 확인 안 된 것 0" in screen_of(run_dir)


def test_spec_change_counts_the_answers(run_dir):
    task(run_dir, kind="change", sections={"건드릴 파일": "- spec/a.md"}, notify="- T003 바뀜")
    assert "볼 곳: 정해 주실 것 0, 옮긴 답 0, 영향 줄 1" in screen_of(run_dir)


def test_every_table_row_counts_something_the_screen_knows(run_dir):
    task(run_dir)
    known = set(screen.see_values(screen.build(str(run_dir.path), "T001")))
    for rows in list(kinds.SEE_COUNTS.values()) + [kinds.SEE_DEFAULT, kinds.SEE_RUN_WIDE, kinds.SEE_SPEC_CHANGE]:
        assert {key for _, key in rows} <= known


# ---------------------------------------------------------------- 한 장: 표지, 머리, 도면

def test_screen_ac_kind_check_keeps_its_own_grammar(run_dir, lib):
    write(run_dir.path / "spec" / "a.md", "- **AC-1** 굵게 [화면: S1]\n1. AC-2 번호 [화면: S2]\n| AC-3 표 [화면: S3] |\n")
    entries, _ = lib.ac_spec_entries(str(run_dir.path))
    assert set(entries) == {"AC-1", "AC-2"}
    assert lib.AC_HEAD_RE.match("| AC-3 표") is None


@pytest.mark.parametrize("line,number", [
    ("- AC-1 목록", "AC-1"), ("- **AC-1** 굵게", "AC-1"), ("1. AC-2 번호", "AC-2"), ("| AC-3 | 표 |", "AC-3"), ("### AC-4 제목", "AC-4"),
    ("| C-AC-1 | 앞붙이 |", "C-AC-1"), ("- E-AC-1 앞붙이", "E-AC-1"), ("- AC-1-2 묶음", "AC-1-2"),
])
def test_ac_rows_read_every_grammar(lib, line, number):
    assert [r[0] for r in lib.ac_rows(line)] == [number]


def test_prefixed_fr_rows_are_collected_on_the_sheet(run_dir):
    write(run_dir.path / "spec" / "edit.md", "| E-FR-1 | 고친다 |\n| E-AC-1 | E-FR-1 값 [담당이 채움] |\n| E-AC-2 | E-FR-1 |\n")
    task(run_dir, kind="req-detail", sections={"건드릴 파일": "- spec/edit.md"})
    page = page_of(run_dir)
    assert "기능 요구사항 1개" in page and "표지가 있는 인수 기준 1개" in page and "| E-FR-1 | E-AC-1, E-AC-2 |" in page
    assert "볼 곳: 기존 동작을 바꾸는 요구 0, 담당 값 1, 새 동작 1" in screen_of(run_dir)


def test_old_visual_block_keeps_the_old_grammar(run_dir):
    assert visual.trace_rows("- C-FR-1 고친다\n") == []


def test_map_counts_prefixed_and_numbered_acs(run_dir):
    write(run_dir.path / "spec" / "a.md", "| C-AC-1 | 값 |\n1. AC-2 번호\n- **AC-3** 굵게\n")
    run_dir.task("T001", "상세", {"건드릴 파일": "- spec/a.md"}, kind="req-detail", block="요구사항", status="완료", **NEW)
    assert visual.requirement_lines(str(run_dir.path), run_dir.tasks()) == ["- 묶음 a (상세 T001, 완료): 인수 기준 3개"]


def test_legend_line_is_not_a_filled_value(lib):
    text = "표시 규칙: 채운 값에는 [담당이 채움]을 단다\n\n- FR-1 값 [담당이 채움]\n- AC-1 (FR-1) 한다\n  Then 값 [담당이 채움]\n```\n- AC-9 [담당이 채움]\n```\n"
    assert lib.spec_marks(text)["filled"] == 2


@pytest.mark.parametrize("body,want", [
    ("- spec/brief.md를 읽었다\n- 정본: spec/list.md", "담당 값 1, 새 동작 1"),
    ("- spec/brief.md를 읽었다\n- spec/list.md를 썼다\n- spec/other.md 인용", "담당 값 1, 새 동작 1"),
])
def test_cited_documents_are_not_what_the_task_wrote(run_dir, body, want):
    write(run_dir.path / "spec" / "brief.md", "- 정책 [담당이 채움]\n- 정책 [담당이 채움]\n")
    write(run_dir.path / "spec" / "other.md", "- AC-8 다른 묶음 [담당이 채움]\n")
    write(run_dir.path / "spec" / "list.md", "- AC-1 값 [담당이 채움]\n- AC-2 한다\n")
    task(run_dir, kind="req-detail", extra="\n## 본문\n" + body + "\n")
    assert want in screen_of(run_dir)


def test_design_citing_a_spec_does_not_show_it_on_the_sheet(run_dir):
    write(run_dir.path / "spec" / "x.md", "- AC-1 남의 요구사항\n")
    write(run_dir.path / "design" / "a.md", "내 설계\n")
    write(run_dir.path / "design" / "b.md", "남의 설계\n")
    task(run_dir, kind="design", material="한 일", extra="\n## 본문\n- 근거 spec/x.md\n- design/a.md를 썼다\n- 인용 design/b.md\n")
    page = page_of(run_dir)
    assert "내 설계" in page and "남의 요구사항" not in page and "남의 설계" not in page


def test_sheet_opens_every_diagram_section(run_dir):
    write(run_dir.path / "design" / "a.md", "## 제안 도면: 구성도\n첫 도면\n\n## 제안 도면: 흐름도\n둘째 도면\n\n## 다른 절\n본문\n")
    task(run_dir, sections={"건드릴 파일": "- design/a.md"})
    head = page_of(run_dir).split("<details>")[0]
    assert "<h3>제안 도면: 구성도</h3>" in head and "첫 도면" in head and "<h3>제안 도면: 흐름도</h3>" in head and "둘째 도면" in head


def test_sheet_does_not_open_the_old_test_strategy(run_dir):
    write(run_dir.path / "design" / "a.md", "## 테스트 전략\n긴 글\n")
    task(run_dir, sections={"건드릴 파일": "- design/a.md"})
    assert "긴 글" not in page_of(run_dir).split("<details>")[0]


def test_sheet_collects_marked_acs_open_and_folds_the_rest(run_dir):
    write(run_dir.path / "spec" / "list.md", SPEC)
    task(run_dir, kind="req-detail", sections={"건드릴 파일": "- spec/list.md"}, material="한 일")
    page = page_of(run_dir)
    open_part, folded = page.split("<details><summary>나머지 인수 기준 2개</summary>")
    assert "표지가 있는 인수 기준 2개" in open_part and "AC-2" in open_part and "AC-3" in open_part
    assert "기능 요구사항 2개" in open_part and "FR-2 정렬한다" in open_part
    assert "AC-4" in folded.split("</details>")[0]
    assert "번호 추적표" in folded and "| P-1 | FR-1 | AC-1, AC-4 |" in folded
    assert page.index("표지가 있는 인수 기준") < page.index("새 문서 전체")


def test_sheet_of_req_detail_finds_the_document_in_the_result(run_dir):
    write(run_dir.path / "spec" / "list.md", SPEC)
    task(run_dir, kind="req-detail", extra="\n## 본문\n- 정본: spec/list.md\n")
    assert "표지가 있는 인수 기준 2개" in page_of(run_dir)


def test_sheet_does_not_read_an_implementation_result_for_documents(run_dir):
    write(run_dir.path / "spec" / "list.md", "남이 쓴 문서\n")
    task(run_dir, kind="implementation", material="한 일", extra="\n## 본문\n- 근거 spec/list.md\n")
    assert "남이 쓴 문서" not in page_of(run_dir)


def test_sheet_escapes_and_masks_marked_rows(run_dir):
    write(run_dir.path / "spec" / "list.md", "- AC-1 <script>x</script> [담당이 채움] 010-1234-5678\n")
    task(run_dir, kind="req-detail", sections={"건드릴 파일": "- spec/list.md"})
    page = page_of(run_dir)
    assert "<script" not in page and "010-1234-5678" not in page


def test_sheet_head_has_version_and_terminal_numbers(run_dir):
    task(run_dir, meta=dict(NEW, retry="1"), material="한 일", decide="- 고를 것 (가) 예", unverified="- 가정 password=hunter2")
    page = page_of(run_dir)
    assert "판 2 · 결과 " in page.split("<h2>")[0]
    assert "[1] 가정 password=[가림]" in page and "[2] 고를 것 (가) 예" in page and "hunter2" not in page
    shown = screen_of(run_dir)
    assert "- [1] 가정" in shown and "- [2] 고를 것" in shown


def test_sheet_without_items_says_no_numbers(run_dir):
    task(run_dir, material="한 일")
    assert "터미널 번호" not in page_of(run_dir)


def test_sheet_with_unreadable_board_keeps_going(run_dir, monkeypatch, capsys):
    task(run_dir, material="한 일", decide="- 고를 것")

    def broken(*a):
        raise lib.Reject("기록을 읽지 못함")
    monkeypatch.setattr(visual.screen, "build", broken)
    assert visual.main(["visual.py", str(run_dir.path), "T001", "--sheet"]) == 0
    assert "한 장: " in capsys.readouterr().out


DIAGRAM = "## 제안 도면\n```mermaid\nflowchart LR\n  A[<script>x</script>] --> B\n```\n\n## 시험 표\n| 인수 기준 | 계층 |\n|---|---|\n| AC-1 | 단위 |\n\n## 다른 절\n본문\n"


def test_sheet_shows_proposed_diagram_as_source_and_test_table_open(run_dir):
    write(run_dir.path / "design" / "list.md", "# 설계\n\n" + DIAGRAM)
    task(run_dir, sections={"건드릴 파일": "- design/list.md"}, material="한 일")
    page = page_of(run_dir)
    head = page.split("<details>")[0]
    assert "제안 도면" in head and "flowchart LR" in head and "| AC-1 | 단위 |" in head and "다른 절" not in head
    assert "<script" not in page and "<svg" not in page


def test_sheet_shows_one_line_when_there_is_no_diagram(run_dir):
    write(run_dir.path / "design" / "list.md", "## 제안 도면\n데이터 변경 없음\n")
    task(run_dir, sections={"건드릴 파일": "- design/list.md"})
    assert "데이터 변경 없음" in page_of(run_dir).split("<details>")[0]


def test_sheet_of_run_wide_shows_flow_map(run_dir):
    write(run_dir.path / "design" / "run.md", "## 흐름 지도\n| 흐름 | 설계 |\n|---|---|\n| a | T001 |\n")
    task(run_dir, meta=dict(NEW, run_wide="true"), sections={"건드릴 파일": "- design/run.md"})
    assert "| a | T001 |" in page_of(run_dir).split("<details>")[0]


def test_sheet_of_change_shows_only_changed_design_sections(run_dir):
    write(run_dir.path / "design" / "list.md", "## 제안 도면\n옛 도면\n\n## 시험 표\n| AC-1 | 단위 |\n")
    task(run_dir, kind="change", sections={"건드릴 파일": "- design/list.md"})
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "## 제안 도면\n새 도면\n\n## 시험 표\n| AC-1 | 단위 |\n")
    page = page_of(run_dir)
    assert "<h3>바뀐 제안 도면</h3>" in page and "<h3>바뀐 시험 표</h3>" not in page


def test_sheet_of_old_task_has_no_head_numbers_or_sections(run_dir):
    write(run_dir.path / "design" / "list.md", "# 설계\n\n" + DIAGRAM)
    task(run_dir, meta=OLD, sections={"건드릴 파일": "- design/list.md"}, decide="- 고를 것")
    page = page_of(run_dir)
    assert "터미널 번호" not in page and "판 1" not in page and "<h3>제안 도면</h3>" not in page


# ---------------------------------------------------------------- 고친 판 알림

CANON = "## 결정 기록\n| D-1 | 고름 |\n| D-2 | 고름 |\n"


def revision(run_dir, origin=ANSWER_ORIGIN, criteria=JUDGED, revised="## 결정 기록\n| D-1 | 고침 |\n| D-2 | 고름 |\n", extra="", meta=NEW,
             touch="- design/list.md", canon=CANON, **cells):
    write(run_dir.path / touch[2:], canon)
    run_dir.task("T001", "설계 고친 판", {"판정 기준": criteria, "건드릴 파일": touch}, kind="change", block="설계", status="자체검증", origin=origin, **meta)
    write(run_dir.task_dir("T001") / "revised" / touch[2:], revised)
    run_dir.result("T001", result(**cells) + extra)
    judged(run_dir)


def test_revision_that_only_moved_the_answer_notifies(run_dir):
    revision(run_dir)
    ok, why, out = notifies(run_dir)
    assert ok is True, why
    assert "정하는 것:" not in out


@pytest.mark.parametrize("kw", [
    {"revised": "## 결정 기록\n| D-1 | 고침 |\n| D-2 | 고름 |\n| D-3 | 새 결정 |\n"},
    {"revised": "## 결정 기록\n| D-1 | 고침 |\n"},
    {"revised": "번호 없는 글\n", "canon": "번호 없는 글 앞\n"},
    {"extra": "\n## 자식 목록\n나눈 기준: 고침\n\n" + child_row("목록")},
    {"criteria": "1. 기준"},
    {"origin": ""},
    {"origin": "뒤 task의 지적 T009"},
    {"decide": "- 새로 생긴 결정"},
    {"todo": "- 할 일"},
    {"notify": "- 위험을 둔다 [성질: 위험]"},
    {"touch": "- design/infra.md"},
    {"touch": "- ui/list.md"},
    {"touch": "- spec/list.md", "criteria": "1. 기준"},
    {"meta": OLD, "notify": "- 볼 것", "criteria": "1. 기준"},
])
def test_revision_that_changes_more_asks(run_dir, kw):
    revision(run_dir, **kw)
    assert notifies(run_dir)[0] is False


def test_moved_revision_passes_the_transition(run_dir):
    revision(run_dir)
    got = run_script("task_set", run_dir.path, "T001", "--status", "완료", "--record", "알림|지나감|")
    assert got.returncode == 0, got.output


def test_revision_with_a_broken_canon_asks(run_dir):
    revision(run_dir)
    (run_dir.path / "design" / "list.md").write_bytes("D-1 한글".encode("cp949"))
    assert notifies(run_dir)[0] is False


REAL_CANON = "## 결정 기록\n| D-ER-1 | 고름. 공통 설계의 D-3 참조 |\n"


def test_prefixed_new_decision_asks_even_if_citations_match(run_dir):
    revision(run_dir, canon=REAL_CANON, revised=REAL_CANON + "| D-ER-2 | 답에 없던 새 결정 |\n")
    assert notifies(run_dir)[0] is False


def test_prefixed_numbers_without_citation_can_notify(run_dir):
    revision(run_dir, canon="| D-GD-1 | 고름 |\n| D-GD-2 | 고름 |\n", revised="| D-GD-1 | 고침 |\n| D-GD-2 | 고름 |\n")
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def test_citation_with_a_particle_is_not_a_decision_row(run_dir):
    revision(run_dir, canon="| D-1 | 고름 |\n", revised="| D-1 | D-3을 따른다 |\n")
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def test_decision_row_with_a_particle_is_read(lib, run_dir):
    assert screen.decision_numbers("- D-3을 고른다\n본문의 D-4 인용\n```\n| D-5 | 울타리 |\n```\n### I-2 자원\n") == {"D-3", "I-2"}


def test_file_in_revised_outside_the_touch_list_asks(run_dir):
    revision(run_dir)
    write(run_dir.task_dir("T001") / "revised" / "spec" / "login.md", "권한은 누구나\n")
    assert notifies(run_dir)[0] is False


def test_other_design_in_revised_asks(run_dir):
    revision(run_dir)
    write(run_dir.task_dir("T001") / "revised" / "design" / "other.md", "| D-1 | 고침 |\n")
    assert notifies(run_dir)[0] is False


@pytest.mark.parametrize("cells", [
    {"notify": "- 답에 없던 값을 정했다 [성질: 범위]"},
    {"notify": "- 값을 정했다 [성질: 비용]"},
    {"unverified": "- 운영 DB 가정"},
])
def test_revision_with_something_for_the_person_asks(run_dir, cells):
    revision(run_dir, **cells)
    assert notifies(run_dir)[0] is False


def test_revision_with_impact_lines_and_moved_lines_can_notify(run_dir):
    revision(run_dir, notify="- T003 그대로\n- [T012] 옮긴 줄 [성질: 범위]", unverified="- [T013] 옮긴 가정")
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def test_revision_without_revised_file_asks(run_dir):
    revision(run_dir)
    (run_dir.task_dir("T001") / "revised" / "design" / "list.md").unlink()
    assert notifies(run_dir)[0] is False


def test_design_change_from_an_answer_gets_the_criterion(run_dir, lib, monkeypatch, tmp_path):
    import task_set
    monkeypatch.setattr(lib, "harness_version", lambda: "1.2.0-dev.1")
    run_dir.task("T001", "앞", {"승인 기록": '- 2026-11-05 10:00:00 | 답 | 고침 | 원문: "정렬을 고쳐"'}, status="완료", **NEW)
    body = write(tmp_path / "body.md", "## 범위\n- 고침\n\n## 판정 기준\n1. 고친다\n\n## 건드릴 파일\n- design/a.md\n")
    assert task_set.main(["task_set.py", str(run_dir.path), "new", "--from-answer", "T001", "--title", "고침", "--body-from", str(body)]) == 0
    assert lib.answer_is_judged(run_dir.tasks()["T002"]) is True


@pytest.mark.parametrize("touch", ["design/infra.md", "ui/a.md"])
def test_other_canons_from_an_answer_get_no_criterion(run_dir, lib, monkeypatch, tmp_path, touch):
    import task_set
    monkeypatch.setattr(lib, "harness_version", lambda: "1.2.0-dev.1")
    run_dir.task("T001", "앞", {"승인 기록": '- 2026-11-05 10:00:00 | 답 | 고침 | 원문: "정렬을 고쳐"'}, status="완료", **NEW)
    body = write(tmp_path / "body.md", "## 범위\n- 고침\n\n## 판정 기준\n1. 고친다\n\n## 건드릴 파일\n- {}\n".format(touch))
    assert task_set.main(["task_set.py", str(run_dir.path), "new", "--from-answer", "T001", "--title", "고침", "--body-from", str(body)]) == 0
    assert lib.answer_is_judged(run_dir.tasks()["T002"]) is False


def notified(run_dir, tid="T005", approved="2026-11-05 11:00:00"):
    run_dir.task(tid, "설계 고친 판", {"건드릴 파일": "- design/list.md"}, kind="change", block="설계", status="완료",
                 origin=ANSWER_ORIGIN, approval_mode="알림", approved=approved, **NEW)
    run_dir.result(tid, result().replace("### 답하신 것의 반영\n- 없음", "### 답하신 것의 반영\n- 정렬 이름 순 → 최근 순"))


def test_next_asked_screen_carries_the_before_and_after_line(run_dir):
    task(run_dir, material="한 일")
    notified(run_dir)
    out = screen_of(run_dir)
    assert "[T005] 설계 고친 판(답만 옮김): 정렬 이름 순 → 최근 순" in out and "n_notify=0" in out


def test_line_is_gone_after_a_later_answer(run_dir):
    task(run_dir, material="한 일")
    notified(run_dir)
    run_dir.task("T006", "뒤에 답한 task", status="완료", approval_requested="2026-11-05 11:30:00", approved="2026-11-05 12:00:00", approval_mode="승인", **NEW)
    assert "[T005] 설계 고친 판" not in screen_of(run_dir)


def test_line_stays_when_the_later_answer_was_asked_before_the_revision(run_dir):
    task(run_dir, material="한 일")
    notified(run_dir)
    run_dir.task("T006", "먼저 물은 task", status="완료", approval_requested="2026-11-05 10:30:00", approved="2026-11-05 12:00:00", approval_mode="승인", **NEW)
    assert "[T005] 설계 고친 판" in screen_of(run_dir)


def test_line_stays_after_an_earlier_answer_or_a_later_notify(run_dir):
    task(run_dir, material="한 일")
    notified(run_dir)
    run_dir.task("T006", "앞에 답한 task", status="완료", approved="2026-11-05 10:00:00", approval_mode="승인", **NEW)
    run_dir.task("T007", "뒤에 지나간 task", status="완료", approved="2026-11-05 12:00:00", approval_mode="알림", **NEW)
    assert "[T005] 설계 고친 판" in screen_of(run_dir)


def test_old_screen_has_no_carried_line(run_dir):
    task(run_dir, meta=OLD, material="한 일")
    notified(run_dir)
    assert "[T005]" not in screen_of(run_dir)


# ---------------------------------------------------------------- 판정자 대안 문장

ALT_JUDGE = ("판정자: rjudge {now}\n# T009 판정\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n| 1 | 통과 | 실행함 | 근거 |\n\n"
             "## 칸 분류 확인\n- 없음\n\n## 권장\n{line}\n")
CORRECTED = "1. 기준\n2. {}: 표기를 고친다".format(lib.CORRECTION_CRITERION)
ALT_UNCHANGED = "- 대안 문장: \"설계 D-1의 표기를 고친다\" 뜻 바뀜: 없음 (design/list.md:3)"


def alt_source(run_dir, line=ALT_UNCHANGED, tid="T009"):
    run_dir.task(tid, "앞 task", kind="design", block="설계", status="완료", **NEW)
    run_dir.judge(tid, ALT_JUDGE.format(now="2026-11-05 09:00:00", line=line))


def test_correction_with_no_change_of_meaning_notifies(run_dir):
    alt_source(run_dir)
    revision(run_dir, origin="판정자 T009 대안 문장", criteria=CORRECTED)
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


@pytest.mark.parametrize("line", ["- 대안 문장: \"뜻을 바꾼다\" 뜻 바뀜: 있음", "- 대안 문장: \"표지 없음\""])
def test_correction_that_may_change_meaning_asks(run_dir, line):
    alt_source(run_dir, line=line)
    revision(run_dir, origin="판정자 T009 대안 문장", criteria=CORRECTED)
    assert notifies(run_dir)[0] is False


def test_correction_of_requirements_asks(run_dir):
    alt_source(run_dir)
    revision(run_dir, origin="판정자 T009 대안 문장", criteria=CORRECTED, touch="- spec/list.md")
    assert notifies(run_dir)[0] is False


@pytest.mark.parametrize("path", ["design/infra.md", "ui/list.md"])
def test_correction_of_infra_and_screen_canon_asks(run_dir, path):
    alt_source(run_dir, line="- 대안 문장: \"표기를 고친다\" 뜻 바뀜: 없음 ({}:3)".format(path))
    revision(run_dir, origin="판정자 T009 대안 문장", criteria=CORRECTED, touch="- " + path)
    assert notifies(run_dir)[0] is False


def test_correction_without_the_criterion_asks(run_dir):
    alt_source(run_dir)
    revision(run_dir, origin="판정자 T009 대안 문장", criteria="1. 기준")
    assert notifies(run_dir)[0] is False


def test_unrelated_alternative_sentence_opens_nothing(run_dir):
    alt_source(run_dir, line="- 대안 문장: \"오타를 고친다\" 뜻 바뀜: 없음 (design/other.md:3)")
    revision(run_dir, origin="판정자 T009 대안 문장", criteria=CORRECTED)
    assert notifies(run_dir)[0] is False


def test_correction_change_gets_the_sentence_as_a_criterion(run_dir, lib, monkeypatch, tmp_path):
    import task_set
    monkeypatch.setattr(lib, "harness_version", lambda: "1.2.0-dev.1")
    alt_source(run_dir, tid="T001")
    body = write(tmp_path / "body.md", "## 범위\n- 고침\n\n## 판정 기준\n1. 고친다\n\n## 건드릴 파일\n- design/list.md\n")
    assert task_set.main(["task_set.py", str(run_dir.path), "new", "--kind", "change", "--origin", "판정자 T001 대안 문장", "--title", "정정",
                          "--body-from", str(body)]) == 0
    criteria = run_dir.tasks()["T002"]["_sections"]["판정 기준"]
    assert lib.CORRECTION_CRITERION in criteria and "설계 D-1의 표기를 고친다" in criteria


def test_correction_change_of_another_file_gets_no_criterion(run_dir, lib, monkeypatch, tmp_path):
    import task_set
    monkeypatch.setattr(lib, "harness_version", lambda: "1.2.0-dev.1")
    alt_source(run_dir, tid="T001")
    body = write(tmp_path / "body.md", "## 범위\n- 고침\n\n## 판정 기준\n1. 고친다\n\n## 건드릴 파일\n- design/other.md\n")
    assert task_set.main(["task_set.py", str(run_dir.path), "new", "--kind", "change", "--origin", "판정자 T001 대안 문장", "--title", "정정",
                          "--body-from", str(body)]) == 0
    assert lib.CORRECTION_CRITERION not in run_dir.tasks()["T002"]["_sections"]["판정 기준"]


def test_correction_with_unknown_source_asks(run_dir):
    revision(run_dir, origin="판정자 T404 대안 문장", criteria=CORRECTED)
    assert notifies(run_dir)[0] is False


def corrected(run_dir, tid="T005", path="design/a.md", criteria="1. 기준"):
    run_dir.task(tid, "표기 정정", {"건드릴 파일": "- " + path, "판정 기준": criteria}, kind="change", block="설계", status="완료",
                 origin="판정자 T009 대안 문장", approval_mode="알림", approved="2026-11-05 11:00:00", **NEW)
    run_dir.result(tid, result())


def test_correction_line_goes_to_the_flow_review(run_dir):
    corrected(run_dir)
    task(run_dir, kind="flow-verify", meta=dict(NEW, flow="a"), material="한 일")
    assert "[T005] 판정자 대안 문장으로 정본을 고침(뜻 바뀜 없음): 표기 정정" in screen_of(run_dir)


def test_correction_line_is_not_on_another_flow_review(run_dir):
    corrected(run_dir)
    task(run_dir, kind="flow-verify", meta=dict(NEW, flow="b"), material="한 일")
    assert "[T005]" not in screen_of(run_dir)


def test_correction_outside_a_flow_goes_to_wrap_up(run_dir):
    corrected(run_dir, path="design/run.md")
    run_dir.task("T006", "검증", kind="flow-verify", block="검증", status="완료", flow="a", **NEW)
    task(run_dir, kind="wrap-up", meta=dict(NEW, stage="실행승인"), material="한 일")
    assert "[T005] 판정자 대안 문장" in screen_of(run_dir)


def test_correction_with_a_flow_review_does_not_go_to_wrap_up(run_dir):
    corrected(run_dir)
    run_dir.task("T006", "검증", kind="flow-verify", block="검증", status="완료", flow="a", approved="2026-11-05 12:00:00", **NEW)
    task(run_dir, kind="wrap-up", meta=dict(NEW, stage="실행승인"), material="한 일")
    assert "[T005]" not in screen_of(run_dir)


def test_correction_after_the_flow_review_goes_to_wrap_up(run_dir):
    corrected(run_dir)
    run_dir.task("T006", "검증", kind="flow-verify", block="검증", status="완료", flow="a", approved="2026-11-05 10:00:00", **NEW)
    task(run_dir, kind="wrap-up", meta=dict(NEW, stage="실행승인"), material="한 일")
    assert "[T005] 판정자 대안 문장" in screen_of(run_dir)


def test_correction_uses_the_flow_of_its_source_first(run_dir):
    run_dir.task("T009", "앞 설계", kind="design", block="설계", status="완료", flow="a", **NEW)
    corrected(run_dir, path="design/other-name.md")
    task(run_dir, kind="flow-verify", meta=dict(NEW, flow="a"), material="한 일")
    assert "[T005] 판정자 대안 문장" in screen_of(run_dir)


def test_correction_line_quotes_the_sentence(run_dir):
    corrected(run_dir, criteria=CORRECTED)
    task(run_dir, kind="flow-verify", meta=dict(NEW, flow="a"), material="한 일")
    assert "[T005] 판정자 대안 문장으로 정본을 고침(뜻 바뀜 없음): 표기를 고친다" in screen_of(run_dir)


def test_source_screen_says_the_correction_does_not_ask(run_dir):
    task(run_dir, material="한 일")
    run_dir.judge("T001", ALT_JUDGE.format(now="2026-11-05 09:00:00", line=ALT_UNCHANGED))
    assert "! 판정자 대안 문장(뜻 바뀜 없음) 1건" in screen_of(run_dir)


def test_source_screen_stays_silent_for_requirements(run_dir):
    task(run_dir, material="한 일")
    run_dir.judge("T001", ALT_JUDGE.format(now="2026-11-05 09:00:00", line="- 대안 문장: \"고친다\" 뜻 바뀜: 없음 (spec/a.md:3)"))
    assert "! 판정자 대안 문장" not in screen_of(run_dir)


# ---------------------------------------------------------------- 요구사항 종합과 대기

def detail(run_dir, tid, status, parent="T001", body="spec/x.md", spec="- AC-1 한다\n- AC-2 값 [담당이 채움] 20개\n", meta=NEW, decide="- 없음", title=None):
    write(run_dir.path / body, spec)
    run_dir.task(tid, title or "상세 " + tid, {"건드릴 파일": "- " + body}, kind="req-detail", block="요구사항", status=status, parent=parent, **meta)
    run_dir.result(tid, result(decide=decide))
    judged(run_dir, tid)


def test_summary_is_on_the_last_sibling_only(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    detail(run_dir, "T003", "승인대기", body="spec/b.md")
    assert "■ 요구사항 종합" not in run_script("screen", run_dir.path, "T002").stdout
    detail(run_dir, "T002", "완료", body="spec/a.md")
    out = run_script("screen", run_dir.path, "T003").stdout
    assert "■ 요구사항 종합 (묶음 2)" in out


def test_summary_lists_each_bundle(run_dir):
    detail(run_dir, "T002", "완료", body="spec/a.md", decide="- 고를 것", title="목록")
    detail(run_dir, "T003", "승인대기", body="spec/b.md", spec="- AC-1 [바뀜: a.ts:1]\n", title="상세")
    out = run_script("screen", run_dir.path, "T003").stdout
    summary = out.split("■ 요구사항 종합")[1].split("\n■ ")[0]
    assert "  T002 목록: 인수 기준 2(바꾸는 요구 0, 담당 값 1, 새 동작 1) | 사람이 정함 1, 작성자가 정함 1" in summary
    assert "    담당 값: - AC-2 값 [담당이 채움] 20개" in summary
    assert "  T003 상세: 인수 기준 1(바꾸는 요구 1, 담당 값 0, 새 동작 0) | 사람이 정함 0, 작성자가 정함 0" in summary


def test_summary_reports_flipped_answers(run_dir):
    detail(run_dir, "T002", "완료", body="spec/a.md")
    detail(run_dir, "T003", "승인대기", body="spec/b.md")
    run_dir.task("T004", "정렬을 바꿈", {"건드릴 파일": "- spec/a.md"}, kind="change", block="요구사항", status="완료",
                 origin="사용자 T002 2026-11-05 10:00:00", **NEW)
    out = run_script("screen", run_dir.path, "T003").stdout
    assert "  답으로 고침: T004 정렬을 바꿈(T002)" in out


def test_summary_counts_held_and_backlog_siblings_as_closed(run_dir):
    detail(run_dir, "T002", "보류", body="spec/a.md")
    detail(run_dir, "T004", "백로그", body="spec/c.md")
    detail(run_dir, "T003", "승인대기", body="spec/b.md")
    assert "■ 요구사항 종합" in run_script("screen", run_dir.path, "T003").stdout


def test_summary_survives_a_broken_sibling_document(run_dir):
    detail(run_dir, "T002", "완료", body="spec/a.md")
    detail(run_dir, "T003", "승인대기", body="spec/b.md")
    (run_dir.path / "spec" / "a.md").write_bytes("- AC-1 한글".encode("cp949"))
    got = run_script("screen", run_dir.path, "T003")
    assert got.returncode == 0 and "T002 상세 T002: 인수 기준 0" in got.stdout


def test_lone_detail_has_no_summary(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    assert "■ 요구사항 종합" not in run_script("screen", run_dir.path, "T002").stdout


def test_other_blocks_are_not_siblings(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    detail(run_dir, "T003", "승인대기", body="spec/b.md", parent="T009")
    assert "■ 요구사항 종합" not in run_script("screen", run_dir.path, "T003").stdout


def test_summary_does_not_break_the_answer_parse(run_dir):
    detail(run_dir, "T002", "완료", body="spec/a.md", spec="- AC-1 값 (나) 삭제 [담당이 채움]\n")
    detail(run_dir, "T003", "승인대기", body="spec/b.md", decide="- 고를 것 (가) 예")
    assert run_script("screen", run_dir.path, "T003", "--save").returncode == 0
    assert run_script("screen", run_dir.path, "T003", "--answer", "1 가").returncode == 0
    assert run_script("screen", run_dir.path, "T003", "--answer", "1 나").returncode == 3


def test_old_detail_has_no_summary(run_dir):
    detail(run_dir, "T002", "완료", body="spec/a.md", meta=OLD)
    detail(run_dir, "T003", "승인대기", body="spec/b.md", meta=OLD)
    assert "■ 요구사항 종합" not in run_script("screen", run_dir.path, "T003").stdout


def waiting_design(run_dir, tid="T005", meta=NEW):
    run_dir.task(tid, "설계", kind="design", block="설계", status="승인대기", flow="a", **meta)
    run_dir.result(tid, result())


def test_design_is_not_asked_until_the_block_is_closed(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    waiting_design(run_dir)
    out = run_script("board", run_dir.path, "--queue").stdout
    assert out.startswith("승인 대기 1개")
    assert "요구사항 종합을 기다림 1개(묻지 않는다): T005(← T002)" in out
    assert [t["id"] for t in board.queue(run_dir.tasks())] == ["T002"]


@pytest.mark.parametrize("status", ["완료", "보류", "백로그"])
def test_design_is_asked_once_the_block_is_closed(run_dir, status):
    detail(run_dir, "T002", status, body="spec/a.md")
    waiting_design(run_dir)
    out = run_script("board", run_dir.path, "--queue").stdout
    assert "T005" in out and "요구사항 종합을 기다림" not in out


def test_old_design_does_not_wait_for_the_block(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    waiting_design(run_dir, meta=OLD)
    assert "요구사항 종합을 기다림" not in run_script("board", run_dir.path, "--queue").stdout


def test_save_refuses_a_design_waiting_for_the_summary(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    waiting_design(run_dir)
    out = run_script("screen", run_dir.path, "T005", "--save").stdout
    assert "! --save 안 함: 요구사항 종합을 기다린다(T002)" in out
    assert not (run_dir.task_dir("T005") / "screen-shown.md").exists()
    assert "! 요구사항 종합 전" in run_script("screen", run_dir.path, "T005").stdout


def test_answer_is_refused_while_the_design_waits_for_the_summary(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    waiting_design(run_dir)
    judged(run_dir, "T005")
    got = run_script("task_set", run_dir.path, "T005", "--status", "완료", "--record", '승인|승인|"승인"')
    assert got.returncode == 3 and "요구사항 종합" in got.output


def test_waiting_design_screen_warns_instead_of_asking(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    waiting_design(run_dir)
    out = run_script("screen", run_dir.path, "T005").stdout
    assert "! 요구사항 종합 전" in out and "질문:" not in out


def test_detail_stuck_behind_a_hold_does_not_stop_the_design(run_dir):
    run_dir.task("T010", "보류된 앞 task", status="보류", **NEW)
    detail(run_dir, "T003", "대기", body="spec/a.md")
    run_dir.task("T003", "상세", {"건드릴 파일": "- spec/a.md"}, kind="req-detail", block="요구사항", status="대기", parent="T001", depends_on=["T010"], **NEW)
    waiting_design(run_dir)
    out = run_script("board", run_dir.path, "--queue").stdout
    assert out.startswith("승인 대기 1개") and "요구사항 종합을 기다림" not in out


def test_summary_treats_a_detail_stuck_behind_a_hold_as_closed(run_dir):
    run_dir.task("T010", "보류된 앞 task", status="보류", **NEW)
    run_dir.task("T002", "상세", {"건드릴 파일": "- spec/a.md"}, kind="req-detail", block="요구사항", status="대기", parent="T001", depends_on=["T010"], **NEW)
    detail(run_dir, "T003", "승인대기", body="spec/b.md")
    assert "■ 요구사항 종합" in run_script("screen", run_dir.path, "T003").stdout


def test_design_runs_while_the_block_is_open(run_dir):
    detail(run_dir, "T002", "승인대기", body="spec/a.md")
    run_dir.task("T005", "설계", kind="design", block="설계", status="대기", flow="a")
    assert "- T005 설계 [design]" in ready_of(run_dir)


# ---------------------------------------------------------------- 안내 문서

def test_design_module_points_to_the_screen_order():
    from conftest import ROOT
    text = (ROOT / "references" / "kinds" / "design" / "screen.md").read_text(encoding="utf-8")
    for word in ("이 설계가 한 일", "확인 안 된 것", "정해 주실 것", "제안 도면", "열린 질문"):
        assert word in text
    assert "references/kinds/design/screen.md" in (ROOT / "references" / "kinds" / "design.md").read_text(encoding="utf-8")


def test_documents_carry_the_rules_the_engine_relies_on():
    from conftest import ROOT
    kinds_dir = ROOT / "references" / "kinds"
    order = (kinds_dir / "design" / "main-order.md").read_text(encoding="utf-8")
    assert "실행 전체 몫 쓰지 않음" in order and "depends_on" in order and "끝 질문" in order
    assert "실행 전체 몫 쓰지 않음" in (kinds_dir / "design.md").read_text(encoding="utf-8")
    assert "| 인수 기준 묶음 | 계층 | 돌리는 곳 | 기대값 근거 | 못 보는 것 |" in (kinds_dir / "design" / "screen.md").read_text(encoding="utf-8")
    assert "테스트 전략" not in (kinds_dir / "design.md").read_text(encoding="utf-8")
    assert any("설계 고친 판" in line and "apply_revision.py" in line for line in (kinds_dir / "change" / "main-order.md").read_text(encoding="utf-8").splitlines())
    assert "공통 설계 없이 설계가 나란히" not in (ROOT / "references" / "main" / "code-folder.md").read_text(encoding="utf-8")
    judge = (ROOT / "references" / "formats" / "judge-file.md").read_text(encoding="utf-8")
    assert "뜻 바뀜: 없음" in judge and "고칠 정본" in judge


def test_run_wide_lives_in_the_board_only_for_new_tasks(lib):
    assert lib.is_run_wide({"run_wide": "true"}) and lib.is_run_wide({"run_wide": "예"})
    assert not lib.is_run_wide({"run_wide": ""}) and not lib.is_run_wide({})
