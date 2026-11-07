"""측정 집계(B-9, 설계 B 3.8): `collect.py {실행 폴더} --measure` 명령행과 `zero_decision_approvals`·`perspective_counts` 단위.

명령행 사례는 표준 출력의 줄 전체를 단언한다. 결정 0 승인은 `완료`·`approval_mode: 승인`·`n_decide` 0·`n_todo` 0인
task이고, 관점 지적은 검증 무리 task `result.md` 「본문」과 설계 블록 task 판정 파일 「통과 못 한 기준」의 `관점:` 줄이다(D-9).
"""
import json

import pytest

import collect
from conftest import run_script, write

DONE = {"status": "완료", "approval_mode": "승인", "n_decide": "0", "n_todo": "0"}
LONG = "가나다라마 바사아자차카"   # 괄호·공백을 뺀 11글자: 한 마디 답이 아님
NO_FINDING = "- 관점 지적: 보안 0(설계 판정 0) · 운영 제약 0(설계 판정 0) · 데이터 정합 0(설계 판정 0) · 정확성 0 · 시험 0 · 관례 0 · 그 밖 0"


def approved(stamp, text):
    return '- {} | 승인 | 승인 | 원문: "{}"'.format(stamp, text)


def measure_of(run_dir):
    proc = run_script("collect", run_dir, "--measure")
    assert proc.returncode == 0, proc.output
    lines = proc.stdout.splitlines()
    assert lines[2].startswith("- 멈춤: ")   # 셋째 줄의 값은 stall_line 시험이 본다
    return lines[:2]


def approvals_setup(run_dir):
    run_dir.task("T001", "한 마디 답", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **DONE)
    # 앞 줄은 한 마디 답이지만 가장 늦은 승인 줄이 긴 원문이라 한 마디로 세지 않는다
    run_dir.task("T002", "긴 답", {"승인 기록": approved("2026-10-30 09:00:00", "승인") + "\n"
                                  + approved("2026-10-30 10:00:00", LONG)}, **DONE)
    run_dir.task("T003", "결정 하나", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, n_decide="1"))
    run_dir.task("T004", "알림", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, approval_mode="알림"))


def test_zero_decision_approvals_counts_kind_and_short_answers(run_dir):   # (가) 명령행
    approvals_setup(run_dir)
    assert measure_of(run_dir) == ["- 결정 0 승인: design 2(한 마디 1)", NO_FINDING]


def test_zero_decision_approvals_unit_in_kind_order(run_dir):   # (가) 단위: kinds.KINDS 차례, n_todo가 0이 아니면 뺌
    approvals_setup(run_dir)
    run_dir.task("T005", "질문", {"승인 기록": approved("2026-10-30 09:00:00", "네 (Recommended)")}, kind="question",
                 block="질문", **DONE)
    run_dir.task("T006", "할 일 하나", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, n_todo="1"))
    got = collect.zero_decision_approvals(run_dir.tasks())
    assert got == {"question": (1, 1), "design": (2, 1)}
    assert list(got) == ["question", "design"]


def verify_setup(run_dir, extra=""):
    run_dir.task("T010", "흐름별 검증", kind="flow-verify", block="검증")
    run_dir.result("T010", "# T010 결과\n\n## 승인 화면\n### 알릴 것\n- V-01 관점: 보안\n\n## 본문\n"
                   "### V-01\n- 관점: 보안\n### V-02\n- 관점: 보안\n### V-03\n- 관점: 시험\n" + extra + "\n## 규약 추가\n없음\n")
    run_dir.task("T011", "설계")
    for name in ("judge.md", "judge.r1.md"):
        write(run_dir.task_dir("T011") / name, "판정자: rjudge-T011 2026-10-30 09:00:00\n\n## 통과 못 한 기준\n"
              "- 기준 8: 실패 — 권한 확인이 빠짐. 관점: 보안\n\n## 판정 표\n| 8 | 실패 | 관점: 보안 |\n")


def test_perspective_counts_body_and_design_judges(run_dir):   # (나) 명령행
    verify_setup(run_dir)
    assert measure_of(run_dir) == [
        "- 결정 0 승인: 없음",
        "- 관점 지적: 보안 2(설계 판정 2) · 운영 제약 0(설계 판정 0) · 데이터 정합 0(설계 판정 0) · 정확성 0 · 시험 1"
        " · 관례 0 · 그 밖 0"]


def test_perspective_outside_seven_values_is_other(run_dir):   # (다)
    verify_setup(run_dir, extra="### V-04\n- 관점: 성능\n")
    got = collect.perspective_counts(run_dir.tasks())
    assert got["그 밖"] == (1, 0)
    assert got["보안"] == (2, 2) and got["시험"] == (1, 0)   # 양성 대조: 7값은 제 이름으로 센다


def test_no_matching_task_prints_none(run_dir):   # (라)
    run_dir.task("T001", "결정 있음", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, n_decide="2"))
    assert measure_of(run_dir) == ["- 결정 0 승인: 없음", NO_FINDING]


# ================================================================ 1.2.0 M0-4 기준값(설계 10절)
def _baseline_task(run_dir, tid, records, **meta):
    meta = dict({"status": "완료", "approval_mode": "승인", "n_decide": "0", "n_todo": "0", "kind": "implementation"}, **meta)
    run_dir.task(tid, "기준값 " + tid, **meta)
    p = run_dir.task_dir(tid) / "task.md"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.rstrip("\n") + "\n\n## 승인 기록\n" + "\n".join(records) + "\n", encoding="utf-8")


def test_baseline_counts_human_answers_and_stamps(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-30 10:00:00 | 승인 | 승인 | 원문: "승인"'])
    _baseline_task(run_dir, "T002", ['- 2026-10-30 10:01:00 | 되물음(이해) | 뜻 | 원문: "뭐죠"',
                                     '- 2026-10-30 10:02:00 | 승인 | 승인 | 원문: "ㅇㅋ"'])
    _baseline_task(run_dir, "T003", ['- 2026-10-30 10:03:00 | 승인 | 승인 | 원문: "ㅇㅋ"'], kind="design", n_decide="1")
    _baseline_task(run_dir, "T004", ['- 2026-10-30 10:04:00 | 알림 | 지나감 | 원문: (알림, 답 없음)'], approval_mode="알림")
    _baseline_task(run_dir, "T005", ['- 2026-10-30 10:05:00 | 승인 | [메인] 위임 | 원문: "나머지 자동 승인"'], approval_mode="알림")
    p = run_script("collect", run_dir.path, "--baseline")
    assert p.returncode == 0, p.output
    row = json.loads(p.stdout.strip())
    assert row["tasks"] == 5
    assert row["answers"] == 4
    assert row["asked"] == 3
    assert row["stamp"] == 1
    assert row["code"] == 2
    assert row["code_stamp"] == 1


def test_stall_line_sums_notes_and_resume_gaps(run_dir):
    (run_dir.path / "journal.md").write_text(
        "- 2026-11-01 10:00:00 | 메모 | T001 | 멈춤 측정: 처리 못 한 반환 2개, 7분(T002, T003)\n"
        "- 2026-11-01 10:05:00 | 메모 | T002 | 멈춤 측정: 처리 못 한 반환 0개\n"
        "- 2026-11-01 10:30:00 | 재개 | - | 시작\n"
        "- 2026-11-01 10:40 재개(/clear 뒤, 세션 dabe19b6). 실행 중 에이전트 0\n", encoding="utf-8")
    assert collect.stall_line(str(run_dir.path)) == "- 멈춤: 잰 질문 2번, 처리 못 한 반환 2개 7분 · 재개 2번, 앞 기록과의 사이 35분"


def test_stall_line_keeps_backward_times_out_of_the_gap(run_dir):
    (run_dir.path / "journal.md").write_text(
        "- 2026-11-01 12:00 | 메모 | - | 앞\n"
        "- 2026-11-01 10:00 | 재개 | - | 시작\n"
        "- 2026-11-01 12:30 | 재개 | - | 시작\n", encoding="utf-8")
    assert collect.stall_line(str(run_dir.path)).endswith("재개 2번, 앞 기록과의 사이 30분 · 시각 거꾸로 1줄")


@pytest.mark.parametrize("line", [
    "- 2026-11-01 10:00 | 메모 | - | 재개안내: 다음에 이어서\n",
    "- 2026-11-01 10:00 재개 안전용 매핑을 적었다\n",
    "- 2026-11-01 24:10 | 재개 | - | 시각이 틀림\n",
])
def test_stall_line_does_not_count_lookalike_resumes(run_dir, line):
    (run_dir.path / "journal.md").write_text(line, encoding="utf-8")
    assert "재개 0번" in collect.stall_line(str(run_dir.path))


def test_stall_line_counts_only_the_note_itself(run_dir):
    (run_dir.path / "journal.md").write_text(
        "- 2026-11-01 10:00 | 메모 | - | 지난번 멈춤 측정: 처리 못 한 반환 9개, 90분을 봤다\n", encoding="utf-8")
    assert "잰 질문 0번" in collect.stall_line(str(run_dir.path))


def test_stall_line_without_a_journal(run_dir):
    assert collect.stall_line(str(run_dir.path)).startswith("- 멈춤: 잰 질문 0번")


def test_baseline_counts_old_form_lines_as_answers(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-06 10:41 "승인"'], approval_mode="", n_decide="", n_todo="")
    _baseline_task(run_dir, "T002", ['- 2026-10-05 22:33 예외 코드: "지금대로 둠 (Recommended)" — 변경 없음',
                                     '- (메인 보충 2026-10-07 17:54) 앞 답의 설명 "패널 옆"'], approval_mode="", kind="design")
    row = json.loads(run_script("collect", run_dir.path, "--baseline").stdout.strip())
    assert row["answers"] == 2
    assert row["asked"] == 2


def test_baseline_result_approval_with_empty_mode_is_asked(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-30 10:00:00 | 결과 승인 | 승인 | 원문: "승인"'], approval_mode="")
    _baseline_task(run_dir, "T002", ['- 2026-10-30 10:00:00 | 알림 | 지나감 | 원문: (알림, 답 없음)'], approval_mode="")
    row = json.loads(run_script("collect", run_dir.path, "--baseline").stdout.strip())
    assert (row["asked"], row["code"], row["stamp"], row["code_stamp"]) == (1, 1, 1, 1)


def test_baseline_separates_bulk_answers(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-30 10:00:00 | 결과 승인 | 승인 | 원문: "이후 전체 승인"'], approval_mode="")
    _baseline_task(run_dir, "T002", ['- 2026-10-30 10:00:00 | 승인 | 승인 | 원문: "나머지 자동 승인 → 추천 (가)"'])
    row = json.loads(run_script("collect", run_dir.path, "--baseline").stdout.strip())
    assert (row["asked"], row["bulk"], row["stamp"]) == (0, 2, 0)


def test_baseline_ignores_answers_of_unfinished_tasks(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-30 10:00:00 | 승인 | 승인 | 원문: "승인"'])
    _baseline_task(run_dir, "T002", ['- 2026-10-30 10:00:00 | 되물음(이해) | 뜻 | 원문: "뭐죠"'], status="승인대기")
    row = json.loads(run_script("collect", run_dir.path, "--baseline").stdout.strip())
    assert (row["tasks"], row["answers"]) == (1, 1)


def test_baseline_separates_plain_stamps_from_other_answers(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-30 10:00:00 | 승인 | 승인 | 원문: "승인"'])
    _baseline_task(run_dir, "T002", ['- 2026-10-30 10:00:00 | 변이 권한 거부 | 메인이 직접 돌림 | 원문: "메인이 직접 돌림"'])
    _baseline_task(run_dir, "T003", ['- 2026-10-30 10:00:00 | 승인 | 고칠 것이 있음 | 원문: "고칠 것이 있음"'])
    row = json.loads(run_script("collect", run_dir.path, "--baseline").stdout.strip())
    assert (row["code"], row["code_stamp"], row["code_plain"]) == (3, 2, 1)


def test_baseline_does_not_stamp_a_task_without_decision_counts(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-30 10:00:00 | 승인 | 승인 | 원문: "승인"'], n_decide="")
    assert json.loads(run_script("collect", run_dir.path, "--baseline").stdout.strip())["stamp"] == 0


def test_baseline_does_not_write_into_the_run(run_dir):
    _baseline_task(run_dir, "T001", ['- 2026-10-30 10:00:00 | 승인 | 승인 | 원문: "승인"'])
    before = sorted((str(f), f.stat().st_mtime) for f in run_dir.path.rglob("*") if f.is_file())
    run_script("collect", run_dir.path, "--baseline")
    assert sorted((str(f), f.stat().st_mtime) for f in run_dir.path.rglob("*") if f.is_file()) == before
