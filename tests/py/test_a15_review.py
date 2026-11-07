"""A15 리뷰의 재현을 옮긴 시험. 칸의 실패 경로, 배포만 실행의 닫는 범위, 일반 메시지 승인, 재개, 측정의 없는 값."""

import pytest

import collect
import devflow_lib as lib
import slots
import task_set
from conftest import ROOT, RunDir, run_script, write
from test_a15_returns import RISK_ANSWER, deploy_only, prepared, resume, settle
from test_deploy_identity import OTHER, SHA, deploy, gate, proof
from test_sheet import task
from test_slots import RECON, V120, code, git, place, ready, values, work  # noqa: F401  place는 fixture다


def conflict(run_dir, place):
    """T001이 먼저 들어가 T002가 충돌하고, 수정 T003을 기다린다."""
    code(run_dir, "T001", "- shared.txt", status="승인대기")
    code(run_dir, "T002", "- shared.txt", status="승인대기")
    work(run_dir, place, "T001", "1", "shared.txt", "가\n")
    work(run_dir, place, "T002", "2", "shared.txt", "나\n")
    run_script("slots", run_dir, "T001", "--insert")
    assert run_script("slots", run_dir, "T002", "--insert").returncode == 3
    code(run_dir, "T003", "- shared.txt", kind="fix", origin="넣기 T002")
    assert run_script("slots", run_dir, "T002", "--insert-failed", "T003").returncode == 0


def check_failed(run_dir, place):
    """T002가 cherry-pick으로 들어갔고 넣은 뒤 확인이 실패해 수정 T003을 기다린다."""
    code(run_dir, "T001", "- a.txt")
    code(run_dir, "T002", "- b.txt")
    work(run_dir, place, "T001", "1", "a.txt", "a\n")
    work(run_dir, place, "T002", "2", "b.txt", "b\n")
    run_script("slots", run_dir, "T001", "--insert")
    run_script("slots", run_dir, "T002", "--insert")
    check = run_dir.path / "flows" / "f" / "insert-checks" / "T002.md"
    write(check, "x\n\n## 통과 못 한 기준\n- 기준 1: 흔들림\n")
    assert run_script("slots", run_dir, "T002", "--checked").returncode == 3
    code(run_dir, "T003", "- b.txt", kind="fix", origin="넣기 T002")
    assert run_script("slots", run_dir, "T002", "--insert-failed", "T003").returncode == 0
    return check


# ---------------------------------------------------------------- R-COR1 사슬

def test_chain_of_fixes_releases_every_task(run_dir, place):
    conflict(run_dir, place)
    work(run_dir, place, "T003", "2", "shared.txt", "다\n")
    write(str(place) + "/shared.txt", "딴\n")   # 그 사이 흐름 끝이 움직인다
    git(place, "add", "-A")
    git(place, "commit", "-qm", "딴")
    assert run_script("slots", run_dir, "T003", "--insert").returncode == 3
    code(run_dir, "T004", "- shared.txt", kind="fix", origin="넣기 T003")
    assert run_script("slots", run_dir, "T003", "--insert-failed", "T004").returncode == 0
    work(run_dir, place, "T004", "1", "shared.txt", "라\n")
    assert run_script("slots", run_dir, "T004", "--insert").returncode == 0
    tasks = run_dir.tasks()
    assert tasks["T003"].get("commit_via") == "T004" and tasks["T002"].get("commit_via") == "T003"
    assert not lib.unfinished_mark(tasks["T002"]) and not lib.unfinished_mark(tasks["T003"])


# ---------------------------------------------------------------- R-COR2 코드를 남기지 않는 수정

def test_fix_without_code_lets_the_check_close(run_dir, place):
    check = check_failed(run_dir, place)
    assert run_script("task_set", run_dir, "T003", "no_change=true").returncode == 0
    assert not run_dir.tasks()["T002"].get("insert_failed")
    write(check, "x\n\n## 통과 못 한 기준\n- 없음\n")
    assert run_script("slots", run_dir, "T002", "--checked").returncode == 0
    assert not lib.unfinished_mark(run_dir.tasks()["T002"])


def test_held_fix_lets_the_insert_be_called_again(run_dir, place):
    conflict(run_dir, place)
    assert run_script("task_set", run_dir, "T003", "--status", "보류", "--reason", "미룸").returncode == 0
    t = run_dir.tasks()["T002"]
    assert not t.get("insert_failed") and t.get("insert_pending")
    assert run_script("slots", run_dir, "T002", "--insert").returncode == 3   # 또 충돌이면 새 수정을 적는다


def test_checked_pass_clears_its_own_fix_mark(run_dir, place):
    check = check_failed(run_dir, place)
    write(check, "x\n\n## 통과 못 한 기준\n- 없음\n")
    assert run_script("slots", run_dir, "T002", "--checked").returncode == 0
    assert not lib.unfinished_mark(run_dir.tasks()["T002"])


def test_held_task_with_a_commit_does_not_keep_the_slot(run_dir):
    t = dict(id="T1", slot="1", status="보류", insert_pending="abc")
    assert slots.holds_slot(t) is False


# ---------------------------------------------------------------- R-COR3 받아오기 수정

def test_sync_fix_runs_in_the_flow_folder(run_dir, place):
    code(run_dir, "T005", "- shared.txt", kind="fix", origin="받아오기 충돌")
    assert "[칸" not in ready(run_dir)
    proc = run_script("task_set", run_dir, "T005", "--status", "진행", "running_agent=w")
    assert proc.returncode == 0, proc.output
    write(str(place) + "/shared.txt", "고침\n")
    git(place, "add", "-A")
    git(place, "commit", "-qm", "받아오기 고침")
    assert run_script("task_set", run_dir, "T005", "commit=" + git(place, "rev-parse", "HEAD")).returncode == 0


def test_sync_fix_waits_like_today_for_the_folder(run_dir, place):
    code(run_dir, "T005", "- shared.txt", kind="fix", origin="받아오기 충돌")
    code(run_dir, "T006", "- other.txt", status="진행", running_agent="w", slot="1")
    assert "폴더 사용 중" in ready(run_dir)


# ---------------------------------------------------------------- R-COR4 배포만 실행

def test_risk_answer_keeps_the_deploy_side_checks(run_dir):
    t = deploy_only(run_dir, answers=RISK_ANSWER)
    (run_dir.task_dir(t["id"]) / "judge-run.md").unlink()
    assert "배포 대상 동일성 근거 없음" in gate(run_dir, run_dir.tasks()[t["id"]])


def test_risk_answer_refuses_a_wrong_deployed_commit(run_dir):
    t = deploy(run_dir, proof(deployed="틀린값"), answers=RISK_ANSWER)
    assert "전체 해시" in gate(run_dir, t)


def test_risk_answer_refuses_other_deployed_commit(run_dir):
    t = deploy(run_dir, proof(deployed=SHA), deployed=OTHER, answers=RISK_ANSWER)
    assert "deployed_commit" in gate(run_dir, t)


def test_risk_answer_refuses_a_dirty_folder(run_dir):
    assert gate(run_dir, deploy(run_dir, proof(), rows=(("./deploy.sh", SHA, "2"),), answers=RISK_ANSWER))


def test_risk_answer_refuses_a_build_of_another_commit(run_dir):
    why = gate(run_dir, deploy(run_dir, proof(build=OTHER[:12] + "-20261106"), answers=RISK_ANSWER))
    assert "빌드 식별자" in why


def test_missing_build_needs_its_own_answer_too(run_dir):
    assert "빌드 식별자" in gate(run_dir, deploy(run_dir, proof(build=None), answers=RISK_ANSWER))
    both = RISK_ANSWER + '- 2026-10-15 11:00:01 | 승인 | 위험 수용 빌드 식별자 | 원문: "빌드도"\n'
    assert gate(run_dir, deploy(run_dir, proof(build=None), answers=both)) is None


def test_screen_splits_the_risk_from_the_deploy_side(run_dir):
    t = deploy_only(run_dir, answers=RISK_ANSWER)
    lines = task_set.identity_lines(str(run_dir), t)
    assert "- 배포 대상 동일성: 위험 수용(최종 CI 없음). 배포 쪽 대조: 통과" in lines
    assert not any("답이 필요합니다" in l for l in lines)
    t = deploy_only(run_dir)
    assert any("답이 필요합니다" in l for l in task_set.identity_lines(str(run_dir), t))


# ---------------------------------------------------------------- R-COR5 일반 메시지 승인

def asked(run_dir, value="허용", **cells):
    p = run_dir.path / "run.md"
    write(p, p.read_text(encoding="utf-8") + "| 한 장 올리기 | {} |\n".format(value))
    task(run_dir, material="문제", decide="- 고를 것 (가) 예 (나) 아니오", status="승인대기", **cells)
    assert run_script("screen", run_dir, "T001", "--save").returncode == 0


def test_bare_approval_is_asked_again_when_a_choice_is_open(run_dir):
    asked(run_dir)
    proc = run_script("screen", run_dir, "T001", "--answer", "승인")
    assert proc.returncode == 3 and "되물음: 항목" in proc.output and "고르지 않음" in proc.output


@pytest.mark.parametrize("text,line", [("2 (가)", "항목 2:"), ("2 가", "항목 2:"), ("2 가, 승인", "항목 2:")])
def test_answers_that_choose_pass(run_dir, text, line):
    asked(run_dir)
    proc = run_script("screen", run_dir, "T001", "--answer", text)
    assert proc.returncode == 0 and line in proc.output, proc.output


def plain_asked(run_dir, decide):
    """선택지 없는 항목. 판정이 없어 맨 앞에 기록 점검 줄이 끼어도 고를 것으로 세지 않는다."""
    p = run_dir.path / "run.md"
    write(p, p.read_text(encoding="utf-8") + "| 한 장 올리기 | 허용 |\n")
    task(run_dir, kind="deploy-plan", material="문제", decide=decide, status="승인대기")
    assert run_script("screen", run_dir, "T001", "--save").returncode == 0


@pytest.mark.parametrize("decide", ["- 명령 목록\n  ```cmd\n  ./deploy.sh dev\n  ```", "- [판정 기준 정정] 기준 3을 실제 값으로 고칩니다"])
def test_items_without_a_choice_close_with_approval(run_dir, decide):
    plain_asked(run_dir, decide)
    proc = run_script("screen", run_dir, "T001", "--answer", "승인")
    assert proc.returncode == 0 and "전체: 승인" in proc.output, proc.output


def test_choice_among_plain_items_is_still_asked(run_dir):
    plain_asked(run_dir, "- 명령 목록\n- 고를 것 (가) 예 (나) 아니오")
    proc = run_script("screen", run_dir, "T001", "--answer", "승인")
    assert proc.returncode == 3 and "고르지 않음" in proc.output


def test_whole_answers_other_than_approval_pass(run_dir):
    asked(run_dir)
    assert run_script("screen", run_dir, "T001", "--answer", "보류").returncode == 0


def test_record_check_rows_are_not_choices(run_dir):
    asked(run_dir)
    proc = run_script("screen", run_dir, "T001", "--answer", "승인")
    assert "항목 2을 고르지 않음" in proc.output


def test_tool_run_is_as_before(run_dir):
    asked(run_dir, value="없음")
    assert run_script("screen", run_dir, "T001", "--answer", "승인").returncode == 0


@pytest.mark.parametrize("record", ["2|(가)|2 가", "항목 2|(가)|2 가", "승인|2 (가)|2 가", "항목 2: (가)|고를 것|2 가", "2번|예|2 가", "정해 주실 것 2|예|2 가", "선택|(가)|2 가"])
def test_earlier_answer_counts(run_dir, record):
    asked(run_dir)
    assert run_script("task_set", run_dir, "T001", "--record", record).returncode == 0
    assert run_script("screen", run_dir, "T001", "--save").returncode == 0
    proc = run_script("screen", run_dir, "T001", "--answer", "승인")
    assert proc.returncode == 0, proc.output


@pytest.mark.parametrize("record", ["되물음(이해)|항목 2|무슨 뜻인가요", "답|T002 확인|알겠습니다", "고칠 것|3개 파일|고쳐 주세요", "선택|(다)|다른 것"])
def test_earlier_lines_that_do_not_choose_do_not_count(run_dir, record):
    asked(run_dir)
    assert run_script("task_set", run_dir, "T001", "--record", record).returncode == 0
    assert run_script("screen", run_dir, "T001", "--save").returncode == 0
    assert run_script("screen", run_dir, "T001", "--answer", "승인").returncode == 3


def test_a_letter_without_a_number_closes_only_an_unambiguous_item(run_dir):
    p = run_dir.path / "run.md"
    write(p, p.read_text(encoding="utf-8") + "| 한 장 올리기 | 허용 |\n")
    task(run_dir, material="문제", decide="- 고를 것 (가) 예 (나) 아니오\n- 또 고를 것 (가) 예 (나) 아니오", status="승인대기")
    assert run_script("task_set", run_dir, "T001", "--record", "선택|(가)|가").returncode == 0
    assert run_script("screen", run_dir, "T001", "--save").returncode == 0
    assert run_script("screen", run_dir, "T001", "--answer", "승인").returncode == 3


# ---------------------------------------------------------------- R-COR6, R-COR14 재개

def test_one_open_run_resumes_with_only_a_warning(tmp_path):
    run = prepared(tmp_path)
    run.task("T004", "도는 중", kind="flow-verify", status="진행", running_agent="verify-T004", **V120)
    proc = resume(run)
    assert proc.returncode == 0 and "! 다른 세션" in proc.output
    assert "| 재개 | - | 시작" in (run.path / "journal.md").read_text(encoding="utf-8")


def test_changed_session_alone_is_silent(tmp_path):
    run = prepared(tmp_path)
    run.task("T001", "끝남", status="완료", **V120)
    settle(run)
    proc = resume(run)
    assert proc.returncode == 0 and "!" not in proc.output


def test_open_runs_with_a_name_pass_with_a_warning(tmp_path):
    run = prepared(tmp_path)
    run.task("T004", "도는 중", kind="flow-verify", status="진행", running_agent="verify-T004", **V120)
    prepared(tmp_path, "2026-11-06-b").task("T001", "끝남", status="완료", **V120)
    assert resume(run).returncode == 3
    proc = resume(run, said="2026-11-06-a 이어서")
    assert proc.returncode == 0 and "! 다른 세션" in proc.output


@pytest.mark.parametrize("said,code_want", [("2026-11-06-fix-2 이어서", 3), ("2026-11-06-fix 이어서", 0), ("2026-11-06-fix를 이어서", 0), ("이어서", 3)])
def test_run_name_must_match_whole(tmp_path, said, code_want):
    a = RunDir(tmp_path / "_workspace" / "2026-11-06-fix")
    b = RunDir(tmp_path / "_workspace" / "2026-11-06-fix-2")
    a.task("T001", "x", kind="design", status="완료", **V120)
    b.task("T001", "x", kind="design", status="완료", **V120)
    assert resume(a, session="s", said=said).returncode == code_want


def test_longer_korean_name_of_another_run_does_not_pass(tmp_path):
    a = RunDir(tmp_path / "_workspace" / "2026-11-06-화면")
    b = RunDir(tmp_path / "_workspace" / "2026-11-06-화면고침")
    a.task("T001", "x", kind="design", status="완료", **V120)
    b.task("T001", "x", kind="design", status="완료", **V120)
    assert resume(a, session="s", said="2026-11-06-화면고침 이어서").returncode == 3


# ---------------------------------------------------------------- R-COR7 넣은 뒤 확인 중의 넣기

def test_insert_waits_while_a_check_runs(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    code(run_dir, "T002", "- b.txt")
    code(run_dir, "T003", "- c.txt")
    work(run_dir, place, "T001", "1", "a.txt", "a\n")
    work(run_dir, place, "T002", "2", "b.txt", "b\n")
    run_script("slots", run_dir, "T001", "--insert")
    run_script("slots", run_dir, "T002", "--insert")
    work(run_dir, place, "T003", "1", "c.txt", "c\n")
    head = git(place, "rev-parse", "HEAD")
    proc = run_script("slots", run_dir, "T003", "--insert")
    assert proc.returncode == 3 and "T002" in proc.output and git(place, "rev-parse", "HEAD") == head


def test_failed_check_does_not_stop_the_fix_insert(run_dir, place):
    check_failed(run_dir, place)
    work(run_dir, place, "T003", "1", "b.txt", "고침\n")
    assert run_script("slots", run_dir, "T003", "--insert").returncode == 0


def test_ready_holds_sync_while_a_check_runs(run_dir, place):
    run_dir.flow("f", dir=str(place), branch="harness/f", status="진행", sync_pending="[x@1]")
    code(run_dir, "T002", "- b.txt", status="완료", commit="abc", insert_pending="def", slot="1")
    assert "받아오기 보류(넣은 뒤 확인 중): f" in ready(run_dir)


# ---------------------------------------------------------------- R-COR8 첫 task

def test_first_task_of_a_new_run_already_uses_slots(run_dir, tmp_path):
    run_dir.flow("f", dir=str(tmp_path), branch="b", status="진행")
    values(run_dir, 2)
    write(run_dir.path / "recon.md", RECON)
    code(run_dir, "T001", "- a.py", started_version="")
    code(run_dir, "T002", "- b.py", started_version="")
    assert slots.slot_count(str(run_dir)) == 2
    assert "[칸 1]" in ready(run_dir)
    assert run_script("task_set", run_dir, "T001", "--status", "진행", "running_agent=w").returncode == 3


# ---------------------------------------------------------------- R-COR9 남의 칸

def test_restart_refuses_a_slot_someone_else_holds(run_dir, place):
    code(run_dir, "T001", "- a.txt", slot="1", slot_base="abc")
    code(run_dir, "T002", "- b.txt", status="승인대기", slot="1", slot_base="abc")
    proc = run_script("task_set", run_dir, "T001", "--status", "진행", "running_agent=w")
    assert proc.returncode == 3 and "T002" in proc.output


def test_retry_in_its_own_slot_passes(run_dir, place):
    code(run_dir, "T001", "- a.txt", status="자체검증", slot="1", slot_base="abc")
    run_dir.result("T001", "# 결과\n")
    write(run_dir.task_dir("T001") / "judge.md", "판정자: rjudge-T001 2026-11-06 10:00:00\n\n## 통과 못 한 기준\n- 기준 1\n")
    proc = run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge", "running_agent=w")
    assert proc.returncode == 0, proc.output
    assert str(run_dir.tasks()["T001"].get("slot")) == "1"


def test_park_gives_the_slot_back(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    assert run_script("slots", run_dir, "T001", "--open", "1").returncode == 0
    write("{}-s1/a.txt".format(place), "가\n")
    assert run_script("task_set", run_dir, "T001", "--status", "진행", "running_agent=w").returncode == 0
    assert run_script("task_set", run_dir, "T001", "--status", "보류", "--reason", "미룸").returncode == 0
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 0
    t = run_dir.tasks()["T001"]
    assert not t.get("slot") and not t.get("slot_base") and t.get("parked")


# ---------------------------------------------------------------- R-COR10 표지

@pytest.mark.parametrize("line,want", [("- 런타임: 폴더별", 2), ("- 런타임: 폴더별(tools/plan.ts)", 2), ("런타임 : 폴더별 (tools/plan.ts)", 2),
                                       ("- 런타임: 폴더별 아님(포트 공유)", 1), ("- 런타임: 폴더별로 나누지 않음", 1), ("- 런타임: 공유", 1)])
def test_mark_is_compared_as_a_whole_value(run_dir, line, want):
    values(run_dir, 2)
    write(run_dir.path / "recon.md", line + "\n")
    run_dir.task("T000", "x", kind="design", status="완료", **V120)
    assert slots.slot_count(str(run_dir)) == want


def test_set_and_count_show_the_mark_line(run_dir):
    write(run_dir.path / "recon.md", RECON)
    proc = run_script("slots", run_dir, "--set", "2", "칸 둘")
    assert proc.returncode == 0 and "- 런타임: 폴더별" in proc.output
    assert "- 런타임: 폴더별" in run_script("slots", run_dir, "--count").output


# ---------------------------------------------------------------- R-COR11 실행 판정자

def test_run_judge_may_write_the_insert_check_and_skips_mutation():
    text = (ROOT / "agents" / "run-judge.md").read_text(encoding="utf-8")
    assert "insert-checks" in text and "넣은 뒤 확인" in text
    fmt = (ROOT / "references" / "formats" / "judge-run-file.md").read_text(encoding="utf-8")
    assert "변이 확인을 하지 않" in fmt


# ---------------------------------------------------------------- R-COR12 수정이 담은 것

def test_fix_commit_missing_a_file_of_the_original_is_signalled(run_dir, place):
    code(run_dir, "T001", "- shared.txt")
    code(run_dir, "T002", "- shared.txt, - extra.txt", sections={"넘길 이상 신호": "(없음)"})
    work(run_dir, place, "T001", "1", "shared.txt", "가\n")
    run_script("slots", run_dir, "T002", "--open", "2")
    folder = "{}-s2".format(place)
    write(folder + "/shared.txt", "나\n")
    write(folder + "/extra.txt", "더\n")
    git(folder, "add", "-A")
    git(folder, "commit", "-qm", "T002")
    run_script("slots", run_dir, "T002", "--pending", git(folder, "rev-parse", "HEAD"))
    run_script("slots", run_dir, "T001", "--insert")
    assert run_script("slots", run_dir, "T002", "--insert").returncode == 3
    code(run_dir, "T003", "- shared.txt", kind="fix", origin="넣기 T002")
    run_script("slots", run_dir, "T002", "--insert-failed", "T003")
    work(run_dir, place, "T003", "2", "shared.txt", "다\n")   # extra.txt를 빠뜨렸다
    proc = run_script("slots", run_dir, "T003", "--insert")
    assert proc.returncode == 0 and "! 넣기 수정에 빠진 파일: extra.txt" in proc.output
    assert "넣기 수정에 빠진 파일: extra.txt" in run_dir.tasks()["T002"]["_sections"]["넘길 이상 신호"]


def test_fix_commit_with_all_files_says_nothing(run_dir, place):
    conflict(run_dir, place)
    work(run_dir, place, "T003", "2", "shared.txt", "다\n")
    assert "빠진 파일" not in run_script("slots", run_dir, "T003", "--insert").output


# ---------------------------------------------------------------- R-COR13 없는 값

def test_old_run_measures_are_unmeasured_not_zero(run_dir):
    run_dir.task("T001", "옛", kind="implementation", status="완료", flow="f", commit="abc", started_version="1.1.1")
    got = {l.split(":")[0]: l for l in collect.approval_measure(str(run_dir), run_dir.tasks())}
    for head in ("- 직접 내린 판단", "- 한 장 이의", "- 시험 변화", "- 설계 뿌리 결함"):
        assert "재지 못함" in got[head], got[head]


def test_new_run_without_a_closed_verify_has_no_root_count(run_dir):
    run_dir.task("T001", "구현", kind="implementation", status="완료", **V120)
    run_dir.task("T002", "검증", kind="flow-verify", status="진행", **V120)
    assert "재지 못함" in collect.design_root_line(run_dir.tasks())
