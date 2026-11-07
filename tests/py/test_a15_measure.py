"""1.2.0 A15: 설계 10절의 남은 측정 칸. 못 읽은 값은 0이 아니라 `재지 못함`이고, 칸 1이면 작업 칸 줄이 없다."""
import collect
from conftest import write

V120 = {"started_version": "1.2.0-dev.1"}
ASKED = dict(V120, status="완료", approval_mode="승인", n_decide="0", n_todo="0",
             approval_requested="2026-11-06 10:00:00", approved="2026-11-06 10:10:00")


def answered(point, decision, said="답"):
    return {"승인 기록": '- 2026-11-06 10:10:00 | {} | {} | 원문: "{}"'.format(point, decision, said)}


def lines(run_dir):
    tasks = run_dir.tasks()
    return collect.approval_measure(str(run_dir), tasks)


def line_of(run_dir, head):
    return next(l for l in lines(run_dir) if l.startswith("- " + head))


def test_contract_review_counts_time_changes_and_stamps(run_dir):
    run_dir.task("T001", "설계", answered("승인", "승인"), kind="design", **ASKED)
    run_dir.task("T002", "설계", answered("되물음(이해)", "되물음"), kind="design", **ASKED)
    run_dir.task("T003", "설계", answered("항목 1", "(가)"), kind="design", **dict(ASKED, n_decide="1"))
    line = line_of(run_dir, "계약별 리뷰")
    assert "approach 3(시간 10분, 바꾼 답 0, 이해 되물음 1, 도장 1)" in line
    assert line_of(run_dir, "직접 내린 판단") == "- 직접 내린 판단: approach 1"


def test_no_asked_task_is_unmeasured_not_zero(run_dir):
    run_dir.task("T001", "알림", kind="fix", status="완료", approval_mode="알림", **V120)
    assert "재지 못함" in line_of(run_dir, "계약별 리뷰")
    assert "재지 못함" in line_of(run_dir, "설계 승인")


def test_design_approval_and_later_objection(run_dir):
    run_dir.task("T001", "설계", answered("되물음(이의)", "되물음"), kind="design", **ASKED)
    run_dir.task("T002", "구현", answered("되물음(이의)", "되물음"), kind="implementation", **ASKED)
    assert line_of(run_dir, "설계 승인") == "- 설계 승인: 1건, 시간 10분, 이의 1, 뒤 구현의 이의 1(접근인지 가리지 못함)"


def test_design_root_counts_only_the_design_cell(run_dir):
    run_dir.task("T001", "검증", kind="flow-verify", status="완료", **V120)
    run_dir.result("T001", "- 지적 1 뿌리: 설계\n- 지적 2 뿌리: 구현\n")
    assert line_of(run_dir, "설계 뿌리 결함") == "- 설계 뿌리 결함: 1"


def test_boundary_counts_deferred_and_says_what_it_cannot(run_dir):
    run_dir.task("T001", "검증", kind="flow-verify", status="완료", **V120)
    write(run_dir.path / "decisions.md", '- 2026-11-06 10:00:00 | [실물 확인 미룸] 화면 → 배포 뒤 확인 | 원문: "미룸" | T001\n')
    line = line_of(run_dir, "책임 경계")
    assert "미룬 실물 확인 1" in line and "재지 못함" in line


def test_slot_line_only_with_two_slots(run_dir):
    run_dir.task("T001", "구현", kind="implementation", status="완료", retry="1", **V120)
    assert not any(l.startswith("- 작업 칸") for l in lines(run_dir))
    path = run_dir.path / "run.md"
    write(path, path.read_text(encoding="utf-8") + "| 작업 칸 수 | 2 |\n")
    write(run_dir.path / "recon.md", "- 런타임: 폴더별\n")
    write(run_dir.path / "journal.md", "- 2026-11-06 10:00 | 넣기 충돌 | T001 | abc\n")
    write(run_dir.task_dir("T001") / "judge-run.md", "판정자: x\n- 기준 1: 판정불가 환경: 권한 거부\n")
    assert line_of(run_dir, "작업 칸") == "- 작업 칸: 2 · 재시도 1 · 판정불가 환경 1 · 넣기 충돌 1 · 넣은 뒤 확인 실패 0"
