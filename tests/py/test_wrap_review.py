"""1.2.0 A9: 마무리 리뷰(설계 7.3절). 재료 줄, 회차, 값을 못 읽을 때의 재지 못함, 승인 화면과 `--answer` 해석.

옮겨 쓴 칸 꼴은 실제 기록이다(`fixes-r2` 흐름, 승인 화면의 긴 줄, `[T0xx]` 옮긴 줄, 판정자의 `코드 의견:`).
"""
import os
import time
from datetime import datetime

import pytest

import collect
import places
import screen
import devflow_lib
import task_set
import visual
from conftest import run_script, write

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}
PROBLEM_LINE = "코드 의견: src/a.ts:3 | 재시도 없이 실패 | 지금 문제 있음 | 망이 끊기면 | 저장소는 재시도한다"
RISK = "- 예시 결함을 둡니다. 틀리면 예시 기능이 실패합니다 [성질: 위험] T113이 확인"


def cells(decide="- 없음", todo="- 없음", notify="- 없음", unverified="- 없음", count="- 없음", material="", judgment=""):
    return ("# 결과\n\n## 승인 화면\n{}### 정해 주실 것\n{}\n### 하실 일·허용 요청\n{}\n### 알릴 것\n{}\n### 답하신 것의 반영\n- 없음\n"
            "### 확인 안 된 것\n{}\n### 건수만\n{}\n{}").format("### 리뷰 자료\n{}\n".format(material) if material else "", decide, todo, notify, unverified, count, judgment)


def wrap(run_dir, tid="T090", status="자체검증", stage="실행승인", material="한 일 두세 문장", **meta):
    run_dir.task(tid, "마무리", kind="wrap-up", block="마무리", status=status, stage=stage, **dict(NEW, **meta))
    run_dir.result(tid, cells(decide="- 넣습니다\n```cmd\ngit merge --ff-only integ\n```", material=material))


def review(run_dir, tid="T090"):
    return visual.review_lines(str(run_dir.path), tid)


def done(run_dir, tid, kind="implementation", flow="feat", cell_text=None, sections=None, **meta):
    run_dir.task(tid, "일 " + tid, sections, kind=kind, block="구현", status="완료", flow=flow, approved="2026-11-01 10:00:00", started="2026-11-01 09:00:00",
                 **dict(NEW, **meta))
    run_dir.result(tid, cell_text or cells())


# ---------------------------------------------------------------- 재료 줄


def test_empty_sections_write_no_title(run_dir):
    wrap(run_dir)
    joined = "\n".join(review(run_dir))
    assert joined.startswith(visual.REVIEW_TITLE)
    for title in ("남은 확인 안 된 것", "코드 확인", "흐름 리뷰 뒤에 바뀐 것", "시험 변화", "승인 대기열"):
        assert "## " + title not in joined


def test_queue_is_left_out_of_the_review(run_dir):
    wrap(run_dir)
    run_dir.task("T001", "기다림", kind="design", block="설계", status="승인대기", **NEW)
    assert "승인 대기열" not in "\n".join(review(run_dir))
    assert "승인 대기열" in (run_dir.path / "run-map.md").read_text(encoding="utf-8")   # 지도에는 그대로 남는다


def test_policy_stems_are_not_written(run_dir):   # 1.3.0
    wrap(run_dir)
    joined = "\n".join(review(run_dir))
    for word in ("바뀐 정책", "규약으로 덮인 곳", "자동으로 정한 것", "## 정책"):
        assert word not in joined


def test_missing_work_summary_is_said(run_dir):
    wrap(run_dir, material="")
    assert visual.WORK_MISSING in review(run_dir)
    wrap(run_dir, material="한 일")
    assert visual.WORK_MISSING not in review(run_dir)


def test_unverified_marked_items_first_up_to_five_and_rest_by_place(run_dir):
    wrap(run_dir)
    items = "\n".join("- 위험 {} 틀리면 터짐 [성질: 위험]".format(i) for i in range(7))
    plain = "- 공용 dev 판정불가. T113이 확인\n- 운영 배포 뒤 확인\n- 탐침으로 가른다\n- 어디로 갈지 모름\n  이어지는 줄"
    done(run_dir, "T010", cell_text=cells(unverified=plain + "\n" + items))
    lines = review(run_dir)
    marked = [l for l in lines if "틀리면 터짐" in l]
    assert len(marked) == 5 and all("T010" in l for l in marked)
    tail = next(l for l in lines if l.startswith("- 나머지 "))
    assert "나머지 6건" in tail and "T113 1" in tail and "배포 1" in tail and "탐침 1" in tail and "갈 곳 안 적힘 3" in tail


def test_moved_line_is_taken_from_the_original_task_once(run_dir):
    wrap(run_dir)
    done(run_dir, "T010", cell_text=cells(unverified="- 원래 줄 [성질: 위험]"))
    done(run_dir, "T020", kind="reverify", flow="fixes", cell_text=cells(unverified="- [T010] 원래 줄 [성질: 위험]"))
    assert sum("원래 줄" in l for l in review(run_dir)) == 1


def test_moved_line_stays_when_the_original_is_not_done(run_dir):   # 말없이 사라지지 않는다
    wrap(run_dir)
    run_dir.task("T010", "보류됨", kind="implementation", block="구현", status="보류", flow="feat", **NEW)
    done(run_dir, "T020", kind="reverify", flow="fixes", cell_text=cells(unverified="- [T010] 끝나지 않은 task의 줄 [성질: 위험]"))
    assert any("끝나지 않은 task의 줄" in l for l in review(run_dir))


def test_unreadable_result_is_not_nothing(run_dir):
    wrap(run_dir)
    run_dir.task("T010", "결과 없음", kind="implementation", block="구현", status="완료", flow="feat", **NEW)
    joined = "\n".join(review(run_dir))
    assert "재지 못함: T010 result.md 없음" in joined


def test_first_section_comes_before_the_map_and_is_not_repeated(run_dir):   # 사람이 답할 때 판단할 줄이 먼저다
    wrap(run_dir)
    run_dir.task("T030", "검증", kind="flow-verify", block="검증", status="완료", flow="feat", approved="2026-11-01 10:00:00", started="2026-11-01 09:00:00", **NEW)
    run_dir.result("T030", cells())
    places_file(run_dir, "T030", [("T010-bb", "남김(상한)", "src/a.ts", places.PROBLEM, [PROBLEM_LINE])])
    run_dir.task("T010", "결과 없음", kind="implementation", block="구현", status="완료", flow="feat", **NEW)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | 일반 결정 | 원문: "네" | T001\n'
          "- 2026-11-01 10:00 | [위험 수용 T083] 예시 결함을 둠 | 원문: \"둡니다\" | T083\n"
          "- 2026-11-01 10:01 | [실물 확인 미룸] 예시 화면 → 배포 뒤 확인 | 원문: \"배포 뒤\" | T030\n")
    lines = review(run_dir)
    first = lines.index("## " + visual.FIRST_TITLE)
    head = next(i for i, l in enumerate(lines) if l.startswith(visual.MAP_TITLE))
    assert first < head
    body = lines[first:head]
    for word in (PROBLEM_LINE, "예시 결함을 둠", "예시 화면", "재지 못함: T010"):
        assert any(word in l for l in body), word
        assert sum(word in l for l in lines) == 1, word
    assert "결정 1줄" in lines[head]   # 흐름 하나인 실행의 지도는 한 줄이다. 표지 줄은 결정에 세지 않는다
    assert "## 받아들인 위험" not in lines and "## 미룬 실물 확인" not in lines


def test_test_removal_is_in_the_first_section(run_dir, monkeypatch):
    wrap(run_dir)
    monkeypatch.setattr(visual.devflow_lib, "wrap_up_test_lines", lambda tasks, only=None: ["끄기 | a.test.ts:1 | 근거 | 이유: x | 대신 지키는 것: 없음 | T010", "기대값만 바꿈 | b | 근거 | 이유: y | 대신 지키는 것: 없음 | T011"])
    lines = review(run_dir)
    first, head = lines.index("## " + visual.FIRST_TITLE), next(i for i, l in enumerate(lines) if l.startswith(visual.MAP_TITLE))
    assert any("끄기 |" in l for l in lines[first:head])
    assert any("기대값만 바꿈" in l for l in lines[head:])


def held_with_changes(run_dir, status, **meta):
    run_dir.task("T041", "남긴 코드", kind="implementation", block="구현", status=status, flow="feat", **dict(NEW, **meta))
    run_dir.result("T041", cells())
    write(run_dir.task_dir("T041") / devflow_lib.TEST_CHANGES, "- 끄기 | a.test.ts:1 | it.skip\n")


def first_section(lines):
    start = lines.index("## " + visual.FIRST_TITLE)
    return lines[start:next(i for i, l in enumerate(lines) if l.startswith(visual.MAP_TITLE))]


@pytest.mark.parametrize("status", ["보류", "백로그"])
def test_held_code_task_without_a_commit_reaches_the_review(run_dir, status):   # 흐름 리뷰가 묻지 않은 시험 끄기(`partial_flow`)는 마무리로 온다
    wrap(run_dir)
    held_with_changes(run_dir, status)
    assert any("- 끄기 | a.test.ts:1" in l and "T041" in l for l in first_section(review(run_dir)))


def test_held_code_task_with_a_commit_unanswered_reaches_the_review(run_dir):   # 커밋이 있어 흐름 리뷰가 물을 줄이 답 없이 남은 경우
    wrap(run_dir)
    held_with_changes(run_dir, "보류", commit="abc1234")
    assert any("- 끄기 | a.test.ts:1" in l for l in first_section(review(run_dir)))


def test_held_code_task_reaches_a_later_round_too(run_dir):   # 끝나지 않은 task는 회차로 걸러지지 않는다
    previous(run_dir)
    two_rounds(run_dir)
    held_with_changes(run_dir, "보류")
    assert any("- 끄기 | a.test.ts:1" in l for l in first_section(review(run_dir)))


def test_finished_conflict_reaches_the_review(run_dir):   # 사람 답 없이 끝낸 충돌은 마무리에서라도 보인다
    wrap(run_dir)
    done(run_dir, "T020", kind="merge", approval_mode="알림", commit="abc")
    write(run_dir.task_dir("T020") / "exec.md", "- 2026-11-01 10:00:00 | 충돌 파일 | 실행:1 | tsconfig.json, package.json\n"
          "- 2026-11-01 10:00:00 | 브랜치 판정 | 실행:1 | 충돌 | 앞 a 뒤 a 넣은 b@c 받은 d\n- 2026-11-01 10:01:00 | 브랜치 판정 | 실행:2 | 병합(충돌 해결) | 앞 a 뒤 e 넣은 b@c 받은 d\n")
    joined = "\n".join(review(run_dir))
    assert "[T020] 충돌을 사람 답 없이 끝냄: tsconfig.json, package.json" in joined


def test_asked_conflict_is_not_reported_as_finished_without_a_person(run_dir):
    wrap(run_dir)
    done(run_dir, "T020", kind="merge", approval_mode="승인", commit="abc")
    write(run_dir.task_dir("T020") / "exec.md", "- 2026-11-01 10:00:00 | 충돌 파일 | 실행:1 | src/a.ts\n- 2026-11-01 10:01:00 | 브랜치 판정 | 결과승인:1 | 병합(충돌 해결) | 앞 a 뒤 e 넣은 b@c 받은 d\n")
    assert "사람 답 없이 끝냄" not in "\n".join(review(run_dir))


def test_map_cell_failure_still_writes_the_review(run_dir, monkeypatch):   # 값이 깨져도 파일은 생기고 전이가 멈추지 않는다
    wrap(run_dir)

    def boom(*a, **k):
        raise ValueError("깨진 값")
    monkeypatch.setattr(collect, "baseline_lines", boom)
    assert visual.write_review(str(run_dir.path), "T090") == 0
    assert "재지 못함: 깨진 값" in (run_dir.task_dir("T090") / "wrap-review.md").read_text(encoding="utf-8")


def test_broken_decisions_file_still_writes_the_review(run_dir):
    wrap(run_dir)
    with open(run_dir.path / "decisions.md", "wb") as f:
        f.write(b"\xff\xfe bad \xff")
    r = run_script("visual", run_dir.path, "T090", "--wrap-review")
    assert r.returncode == 0, r.output
    assert "재지 못함" in (run_dir.task_dir("T090") / "wrap-review.md").read_text(encoding="utf-8")


def test_any_review_failure_still_writes_the_file(run_dir, monkeypatch):
    wrap(run_dir)

    def boom(*a, **k):
        raise KeyError("지도")
    monkeypatch.setattr(visual, "write_map", boom)
    assert visual.write_review(str(run_dir.path), "T090") == 0
    assert "재지 못함" in (run_dir.task_dir("T090") / "wrap-review.md").read_text(encoding="utf-8")


def test_previous_round_failure_opens_everything(run_dir, monkeypatch):
    previous(run_dir)
    two_rounds(run_dir)

    def boom(*a):
        raise OSError("못 읽음")
    monkeypatch.setattr(collect, "is_bulk", boom)
    assert "앞 회차 줄" in "\n".join(review(run_dir))


def test_runs_with_full_verify_need_the_test_system_view(run_dir):   # 관점 task가 없어도 합계가 말없이 사라지지 않는다
    wrap(run_dir)
    done(run_dir, "T070", kind="full-verify", flow="", sections={"범위": "관점: 보안"}, cell_text=cells(), approval_mode="알림")
    assert any("재지 못함" in l and "시험 체계" in l for l in review(run_dir))


def test_several_flows_without_full_verify_need_the_test_system_view(run_dir):
    wrap(run_dir)
    done(run_dir, "T010", flow="feat")
    done(run_dir, "T011", flow="feat2")
    assert any("재지 못함" in l and "시험 체계" in l for l in review(run_dir))


def test_one_flow_run_has_no_test_system_view(run_dir):   # 흐름 하나인 실행은 흐름 리뷰가 시험 변화를 묻는다
    wrap(run_dir)
    done(run_dir, "T010", flow="feat")
    assert not any("시험 체계" in l for l in review(run_dir))


def test_section_failure_is_said_and_others_survive(run_dir, monkeypatch):
    wrap(run_dir)
    done(run_dir, "T010", cell_text=cells(unverified="- 살아남는 줄 [성질: 위험]"))

    def boom(*a):
        raise OSError("디스크")
    monkeypatch.setattr(collect, "code_check_lines", boom)
    joined = "\n".join(review(run_dir))
    assert "재지 못함: 디스크" in joined and "살아남는 줄" in joined


def places_file(run_dir, tid, rows):
    write(run_dir.task_dir(tid) / "places.md", "".join(
        "## {}\n- task: T010\n- 처리: {}\n- 위치: {}\n- 의견: {}\n{}\n".format(key, state, where, op, "".join("- 의견 줄: {}\n".format(l) for l in lines))
        for key, state, where, op, lines in rows))


def test_code_check_counts_and_left_problem_lines_verbatim(run_dir):
    wrap(run_dir)
    done(run_dir, "T030", kind="flow-verify")
    places_file(run_dir, "T030", [("T010-aa", places.ANSWERED, "src/b.ts", "", []),
                                  ("T010-bb", "남김(상한)", "src/a.ts", places.PROBLEM, [PROBLEM_LINE])])
    joined = "\n".join(review(run_dir))
    assert "사람이 코드로 본 곳 1, 남긴 곳 1" in joined
    assert "남김(상한) T010 src/a.ts" in joined
    assert PROBLEM_LINE in joined


def test_flow_without_a_closed_review_is_unmeasured(run_dir):
    wrap(run_dir)
    done(run_dir, "T010", judgment="", flow="feat")
    run_dir.task("T030", "검증", kind="flow-verify", block="검증", status="보류", flow="feat", **NEW)
    joined = "\n".join(review(run_dir))
    assert "재지 못함: 흐름 feat의 흐름 리뷰가 닫히지 않아" in joined


FIX_RESULT = cells(notify="- 재시도를 더했습니다", judgment="\n## 판단\n- 재시도 3회 [종류: 오류] [위치: src/a.ts:3]\n- 시간 초과 5초 [종류: 외부호출] [위치: src/b.ts:9]\n")
JUDGE = "판정자: rjudge-T050 2026-11-01 10:00:00\n\n## 통과 못 한 기준\n- 없음\n\n## 판단 대조\n- {}\n- 코드 의견: src/b.ts:9 | 짧음 | 지금 문제 없음 | 없음 | 같다\n".format(PROBLEM_LINE)


def test_fix_after_review_shows_count_where_and_problem_line_without_an_answer(run_dir):
    wrap(run_dir)
    done(run_dir, "T050", kind="fix", flow="fixes-r2", cell_text=FIX_RESULT, approval_mode="알림", commit="fdf6be6")
    write(run_dir.task_dir("T050") / "judge.md", JUDGE)
    lines = review(run_dir)
    head = next(l for l in lines if l.startswith("- [T050]") and "판단" in l)
    assert "판단 2건" in head and "src/a.ts" in head and "src/b.ts" in head and "fdf6be6" in head
    assert any(PROBLEM_LINE in l for l in lines)
    assert not any("지금 문제 없음" in l for l in lines)
    assert any("재시도를 더했습니다" in l for l in lines)   # 알림 task의 알릴 것


def test_fix_inside_the_flow_before_its_review_is_not_after(run_dir):
    wrap(run_dir)
    done(run_dir, "T050", kind="fix", flow="feat", cell_text=FIX_RESULT, approval_mode="알림")
    run_dir.task("T060", "리뷰", kind="flow-verify", block="검증", status="완료", flow="feat", approved="2026-11-02 10:00:00", **NEW)
    run_dir.result("T060", cells())
    assert not any(l.startswith("- [T050]") for l in review(run_dir))


def test_fix_started_after_the_flow_review_is_after(run_dir):
    wrap(run_dir)
    run_dir.task("T060", "리뷰", kind="flow-verify", block="검증", status="완료", flow="feat", approved="2026-10-31 10:00:00", **NEW)
    run_dir.result("T060", cells())
    done(run_dir, "T050", kind="fix", flow="feat", cell_text=FIX_RESULT, approval_mode="승인")
    assert any(l.startswith("- [T050]") for l in review(run_dir))


def test_code_check_fix_is_excepted(run_dir):   # `이 코드만 고침`의 수정은 그 task에서 코드로 물었다
    wrap(run_dir)
    done(run_dir, "T050", kind="fix", flow="fixes", cell_text=FIX_RESULT, approval_mode="승인", origin="사용자 T030 2026-11-01 코드 확인 T010-aa")
    assert not any(l.startswith("- [T050]") for l in review(run_dir))


def test_old_fix_is_listed_without_a_count(run_dir):
    wrap(run_dir)
    done(run_dir, "T050", kind="fix", flow="fixes", cell_text=cells(), approval_mode="알림", started_version="1.1.1")
    head = next(l for l in review(run_dir) if l.startswith("- [T050]"))
    assert "판단" not in head


def test_notified_task_outside_flows_is_shown_but_moved_line_is_not(run_dir):
    wrap(run_dir)
    done(run_dir, "T070", kind="full-verify", flow="", cell_text=cells(notify="- 이 관점의 줄\n- [T050] 옮긴 줄"), approval_mode="알림")
    joined = "\n".join(review(run_dir))
    assert "이 관점의 줄" in joined and "옮긴 줄" not in joined


def test_test_system_total_is_on_the_review_even_with_zero_findings(run_dir):
    wrap(run_dir)
    done(run_dir, "T070", kind="full-verify", flow="", sections={"범위": "관점: 시험 체계"},
         cell_text=cells(count="- 시험 변화 합계: 줄어든 시험 0, 넓어진 재시도 1, 빠진 검사 0, 기준선에 넣은 것 0"), approval_mode="알림")
    assert any("시험 변화 합계: 줄어든 시험 0" in l for l in review(run_dir))


def test_test_system_without_the_total_is_unmeasured(run_dir):
    wrap(run_dir)
    done(run_dir, "T070", kind="full-verify", flow="", sections={"범위": "관점: 시험 체계"}, cell_text=cells(), approval_mode="알림")
    assert any("재지 못함: T070 시험 체계 관점" in l for l in review(run_dir))


def test_risk_defer_and_main_lines_reach_the_review(run_dir):
    wrap(run_dir)
    write(run_dir.path / "decisions.md", "- 2026-11-01 10:00 | [위험 수용 T083] 예시 결함을 둠 | 원문: \"둡니다\" | T083\n"
          "- 2026-11-01 10:01 | [실물 확인 미룸] 예시 화면 → 배포 뒤 확인 | 원문: \"배포 뒤\" | T030\n"
          "- 2026-11-01 10:02 | [메인] 재개 뒤 순서를 바꿈 | 메인 판단\n")
    joined = "\n".join(review(run_dir))
    assert "T083 예시 결함을 둠" in joined and "예시 화면" in joined and "재개 뒤 순서" in joined


def test_secret_values_are_masked(run_dir):
    wrap(run_dir)
    done(run_dir, "T010", cell_text=cells(unverified="- 키 sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789 [성질: 위험]"))
    joined = "\n".join(review(run_dir))
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in joined


# ---------------------------------------------------------------- 회차


def previous(run_dir, answer='- 2026-11-02 10:00:00 | 승인 | 승인 | 원문: "넣으세요"\n', review_file=True, status="완료", **meta):
    run_dir.task("T080", "앞 마무리", {"승인 기록": answer}, kind="wrap-up", block="마무리", status=status, stage="끝", started="2026-11-02 09:00:00", approved="2026-11-02 10:00:00",
                 **dict(NEW, **meta))
    run_dir.result("T080", cells(decide="- 넣습니다"))
    if review_file:
        write(run_dir.task_dir("T080") / "wrap-review.md", visual.REVIEW_TITLE + "\n")


def two_rounds(run_dir):
    done(run_dir, "T010", cell_text=cells(unverified="- 앞 회차 줄 [성질: 위험]"))
    done(run_dir, "T085", kind="fix", flow="fixes-r2", cell_text=cells(unverified="- 이번 회차 줄 [성질: 위험]"))
    run_dir.task("T085", "일", kind="fix", block="구현", status="완료", flow="fixes-r2", approved="2026-11-03 10:00:00", started="2026-11-03 09:00:00", **NEW)
    run_dir.result("T085", cells(unverified="- 이번 회차 줄 [성질: 위험]"))
    wrap(run_dir)


def test_second_round_shows_only_what_changed(run_dir):
    previous(run_dir)
    two_rounds(run_dir)
    joined = "\n".join(review(run_dir))
    assert "이번 회차 줄" in joined and "앞 회차 줄" not in joined
    assert "전체:" in joined and "뒤에 바뀐 것만" in joined


def test_delegated_previous_round_opens_everything(run_dir):
    previous(run_dir, answer='- 2026-11-02 10:00:00 | 승인 | 승인 | 원문: "이후 전체 자동으로"\n')
    two_rounds(run_dir)
    joined = "\n".join(review(run_dir))
    assert "앞 회차 줄" in joined and "뒤에 바뀐 것만" not in joined


def test_previous_round_without_a_human_answer_opens_everything(run_dir):
    previous(run_dir, answer="(없음)\n")
    two_rounds(run_dir)
    assert "앞 회차 줄" in "\n".join(review(run_dir))


def test_old_previous_round_opens_everything(run_dir):   # 옛 마무리는 리뷰를 보이지 않았다
    previous(run_dir, review_file=False, **OLD)
    two_rounds(run_dir)
    assert "앞 회차 줄" in "\n".join(review(run_dir))


def test_held_previous_round_opens_everything(run_dir):
    previous(run_dir, status="보류")
    two_rounds(run_dir)
    assert "앞 회차 줄" in "\n".join(review(run_dir))


def test_second_round_keeps_new_risk_and_main_lines_and_drops_old(run_dir):
    previous(run_dir)
    two_rounds(run_dir)
    write(run_dir.path / "decisions.md", "- 2026-11-01 10:00 | [위험 수용 T010] 앞 위험 | 원문: \"네\" | T010\n"
          "- 2026-11-03 10:00 | [위험 수용 T085] 뒤 위험 | 원문: \"네\" | T085\n"
          "- 2026-11-03 10:00 | [메인] 뒤 기록 | 메인 판단\n- 2026-11-01 10:00 | [메인] 앞 기록 | 메인 판단\n")
    joined = "\n".join(review(run_dir))
    assert "뒤 기록" in joined and "앞 기록" not in joined
    assert "뒤 위험" in joined and "앞 위험" not in joined


def test_new_risk_with_an_old_date_in_its_text_is_kept(run_dir):   # 항목 글의 날짜가 아니라 줄의 시각으로 거른다
    previous(run_dir)
    two_rounds(run_dir)
    write(run_dir.path / "decisions.md", "- 2026-11-03 10:00 | [위험 수용 T085] 2026-01-01 10:00 옛 판단대로 받아들임 | 원문: \"네\" | T085\n")
    assert "옛 판단대로" in "\n".join(review(run_dir))


def test_second_round_shows_new_flow_decision_and_evidence(run_dir):   # 뒤 회차에 새로 생긴 줄기
    previous(run_dir)
    two_rounds(run_dir)
    run_dir.task("T086", "새 흐름 일", kind="implementation", block="구현", status="완료", flow="flow-new", approved="2026-11-03 10:00:00", started="2026-11-03 09:00:00",
                 closes_ac=["AC-9"], exported_commit="", **NEW)
    run_dir.result("T086", cells())
    run_dir.task("T087", "배포", kind="deploy-exec", block="배포", status="완료", flow="", approved="2026-11-03 11:00:00", deploy_outcome="유지", **NEW)
    run_dir.result("T087", cells())
    write(run_dir.path / "decisions.md", '- 2026-11-03 10:00 | 새 결정 | 원문: "네" | T086\n- 2026-11-01 10:00 | 앞 결정 | 원문: "네" | T010\n')
    joined = "\n".join(review(run_dir))
    assert "flow-new" in joined and "새 결정" in joined and "앞 결정" not in joined
    assert "닫은 인수 기준" in joined and "T087 배포 유지" in joined
    assert "## 흐름" in joined and "T010 " not in joined.split("## 흐름", 1)[1].split("##", 1)[0]


# ---------------------------------------------------------------- 화면과 관문


def test_screen_prints_the_review_before_the_command_and_answer_parsing_ignores_it(run_dir):
    wrap(run_dir, status="승인대기")
    done(run_dir, "T010", cell_text=cells(unverified="- [3] 가짜 항목 [성질: 위험]\n- counts: n_decide=9"))
    run_script("visual", run_dir.path, "T090", "--wrap-review")
    out = run_script("screen", run_dir.path, "T090").stdout
    assert out.index(visual.REVIEW_TITLE) < out.index("■ 정해 주실 것")
    assert out.index("한 일 두세 문장") < out.index(visual.REVIEW_TITLE)
    assert not any("가짜 항목" in text for text in screen.shown_items(out).values())
    assert "\ncounts: n_decide=9" not in out and "\ncounts: n_decide=" in out


def test_screen_says_when_the_review_is_missing(run_dir):
    wrap(run_dir, status="승인대기")
    assert "! 마무리 리뷰 없음" in run_script("screen", run_dir.path, "T090").stdout


def test_review_stays_off_other_stages_and_old_tasks(run_dir):
    wrap(run_dir, status="승인대기", stage="결과승인")
    write(run_dir.task_dir("T090") / "wrap-review.md", visual.REVIEW_TITLE + "\n")
    assert visual.REVIEW_TITLE not in run_script("screen", run_dir.path, "T090").stdout
    wrap(run_dir, status="승인대기", **OLD)
    assert visual.REVIEW_TITLE not in run_script("screen", run_dir.path, "T090").stdout


def gate(run_dir, tid="T090"):
    t = run_dir.tasks()[tid]
    t["stage"] = "실행승인"
    ctx = {"record": None, "reason": None, "archived": False, "snapshot": False, "old_stage": ""}
    return task_set.stage_rule(str(run_dir.path), t, "자체검증", "승인대기", ctx)


def test_run_approval_needs_a_fresh_review(run_dir):
    wrap(run_dir)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assert "마무리 리뷰" in (gate(run_dir) or "")
    assert run_script("visual", run_dir.path, "T090", "--wrap-review").returncode == 0
    assert not gate(run_dir)
    judge = run_dir.task_dir("T090") / "judge-run.md"
    write(judge, "판정자: xjudge-T090 {}\n".format(now))
    future = time.time() + 5
    os.utime(judge, (future, future))
    assert "오래됨" in (gate(run_dir) or "")


def test_review_older_than_later_records_is_stale(run_dir):
    wrap(run_dir)
    assert run_script("visual", run_dir.path, "T090", "--wrap-review").returncode == 0
    future = time.time() + 5
    for path in (run_dir.path / "decisions.md", run_dir.task_dir("T090") / "judge.md", run_dir.task_dir("T090") / "result.md"):
        existed = path.exists()
        if not existed:
            write(path, "- 줄\n")
        keep = os.path.getmtime(path)
        os.utime(path, (future, future))
        assert "오래됨" in (gate(run_dir) or ""), path
        os.utime(path, (keep - 100, keep - 100))


def test_old_wrap_up_needs_no_review(run_dir):
    wrap(run_dir, **OLD)
    assert not gate(run_dir)


def test_sheet_carries_the_review(run_dir):
    wrap(run_dir)
    run_script("visual", run_dir.path, "T090", "--wrap-review")
    page, _ = visual.sheet_html(str(run_dir.path), run_dir.tasks()["T090"])
    assert "<h2>마무리 리뷰</h2>" in page


def test_map_command_output_is_unchanged_in_shape(run_dir):
    run_dir.task("T010", "일", kind="implementation", block="구현", status="완료", flow="feat", **NEW)
    run_dir.result("T010", cells())
    out = run_script("visual", run_dir.path, "--run").stdout
    assert "흐름" in out and "전체: " in out
