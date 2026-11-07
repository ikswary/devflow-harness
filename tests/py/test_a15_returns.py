"""1.2.0 A15: 실제 실행에서 드러난 멈춤과 잘못된 재개, 배포만으로 시작한 실행.

- 에이전트가 결과 파일 없이 반환하면 끝난 것이 아니다. 보드에 줄이 나오고 멈춘 시간이 측정에 잡힌다.
- 다른 세션이 돌고 있을 수 있는 실행은 사람 원문이나 지정 경로 없이 재개하지 못한다. 잘못 남긴 재개 줄은 세지 않는다.
- 마무리 task가 없는 실행의 배포는 최종 CI가 없다는 사실을 보이고 사람의 위험 수용 답으로만 닫는다.
"""
import os
import time

import pytest

import collect
import devflow_lib as lib
import task_set
from conftest import RunDir, run_script, write
from test_deploy_identity import NEW, OLD, deploy, gate, proof

V120 = {"started_version": "1.2.0-dev.1"}
RISK_ANSWER = "- 2026-10-15 11:00:00 | 승인 | 위험 수용 최종 CI 없음 | 원문: \"그대로 닫아\"\n"


# ------------------------------------------------------------ 결과 없이 반환

def returned(run_dir, name="verify-T004", tid="T004"):
    return run_script("task_set", run_dir, tid, "--returned", name)


def running(run_dir, tid="T004", **meta):
    head = dict(V120, kind="flow-verify", status="진행", running_agent="verify-" + tid, started="2026-11-06 12:12:05")
    run_dir.task(tid, "흐름 검증", **dict(head, **meta))


def test_return_without_result_is_not_finished(run_dir):
    running(run_dir)
    proc = returned(run_dir)
    assert proc.returncode == 0, proc.output
    assert "! 결과 없이 반환" in proc.output and "끝나지 않았습니다" in proc.output
    t = run_dir.tasks()["T004"]
    assert t.get("status") == "진행" and not t.get("running_agent") and "verify-T004" in t.get("returned_empty")


def test_return_with_result_clears_the_agent_only(run_dir):
    running(run_dir)
    run_dir.result("T004", "# 결과\n")
    proc = returned(run_dir)
    assert proc.returncode == 0 and "결과 없이" not in proc.output
    t = run_dir.tasks()["T004"]
    assert not t.get("running_agent") and not t.get("returned_empty")
    assert not (run_dir.path / "journal.md").exists()


def test_judge_return_looks_at_its_own_file(run_dir):
    running(run_dir, status="자체검증", judge_started="2026-11-06 13:00:00 rjudge-T004")
    run_dir.result("T004", "# 결과\n")
    assert "! 결과 없이 반환" in returned(run_dir, "rjudge-T004").output
    run_dir.judge("T004", "판정자: rjudge-T004 2026-11-06 13:01:00\n")
    assert "결과 없이" not in returned(run_dir, "rjudge-T004").output
    assert not run_dir.tasks()["T004"].get("returned_empty")


def test_returned_refuses_old_tasks(run_dir):
    running(run_dir, started_version="1.1.1")
    assert returned(run_dir).returncode == 3
    assert not run_dir.tasks()["T004"].get("returned_empty")


def test_ready_and_resume_show_the_empty_return(run_dir):
    running(run_dir)
    returned(run_dir)
    for flag in ("--ready", "--resume"):
        assert "! 결과 없이 반환: T004 verify-T004" in run_script("board", run_dir, flag).output


def test_ready_finds_it_without_the_mark(run_dir):
    """메인이 표지 없이 running_agent만 비웠어도 줄이 나온다."""
    running(run_dir, running_agent="")
    assert "! 결과 없이 반환: T004" in run_script("board", run_dir, "--ready").output
    run_dir.result("T004", "# 결과\n")
    assert "결과 없이 반환" not in run_script("board", run_dir, "--ready").output


@pytest.mark.parametrize("meta", [{"started_version": "1.1.1"}, {"kind": "deploy-exec", "stage": "실행"}])
def test_ready_line_skips_old_and_main_run_tasks(run_dir, meta):
    running(run_dir, **dict({"running_agent": ""}, **meta))
    assert "결과 없이 반환" not in run_script("board", run_dir, "--ready").output


def test_new_agent_closes_the_stop(run_dir):
    running(run_dir)
    returned(run_dir)
    proc = run_script("task_set", run_dir, "T004", "running_agent=verify-T004-2")
    assert proc.returncode == 0, proc.output
    assert not run_dir.tasks()["T004"].get("returned_empty")
    assert "| 이어 씀 | T004 |" in (run_dir.path / "journal.md").read_text(encoding="utf-8")


def test_measure_counts_a_real_stop_as_time(run_dir):
    write(run_dir.path / "journal.md",
          "- 2026-11-06 12:14 | 결과 없이 반환 | T004 | verify-T004\n- 2026-11-06 13:13 | 이어 씀 | T004 | verify-T004-2\n"
          "- 2026-11-06 13:20 | 결과 없이 반환 | T005 | verify-T005\n")
    line = collect.stall_line(str(run_dir))
    assert "결과 없이 반환 2번 59분" in line and "닫히지 않음 1" in line


# ------------------------------------------------------------ 재개

def resume(run, session="new-session", said="devflow-harness 이어서"):
    return run_script("task_set", run, "resume", "--session", session, "--said", said)


def prepared(tmp_path, name="2026-11-06-a", session="old-session"):
    run = RunDir(tmp_path / "_workspace" / name)
    text = (run.path / "run.md").read_text(encoding="utf-8")
    write(run.path / "run.md", text.replace("status: 진행", "status: 진행\nsession_id: " + session))
    return run


def settle(run):
    old = time.time() - 300 * 60
    for root, _dirs, files in os.walk(run.path):
        for f in files:
            os.utime(os.path.join(root, f), (old, old))


def test_resume_writes_the_line_and_session_when_nothing_else_runs(tmp_path):
    run = prepared(tmp_path)
    run.task("T001", "끝남", status="완료", **V120)
    settle(run)
    proc = resume(run)
    assert proc.returncode == 0, proc.output
    assert "| 재개 | - | 시작" in (run.path / "journal.md").read_text(encoding="utf-8")
    assert "session_id: new-session" in (run.path / "run.md").read_text(encoding="utf-8")


def test_resume_refuses_when_two_runs_are_open_and_said_names_neither(tmp_path):
    run = prepared(tmp_path)
    run.task("T001", "끝남", status="완료", **V120)
    other = prepared(tmp_path, "2026-11-06-b")
    other.task("T001", "끝남", status="완료", **V120)
    settle(run)
    proc = resume(run)
    assert proc.returncode == 3 and "2026-11-06-b" in proc.output
    assert not (run.path / "journal.md").exists()
    assert "session_id: old-session" in (run.path / "run.md").read_text(encoding="utf-8")
    assert resume(run, said="2026-11-06-a 이어서").returncode == 0


def test_resume_warns_when_another_session_has_an_agent(tmp_path):
    run = prepared(tmp_path)
    run.task("T004", "도는 중", kind="flow-verify", status="진행", running_agent="verify-T004", **V120)
    settle(run)
    proc = resume(run)
    assert proc.returncode == 0 and "! 다른 세션" in proc.output and "verify-T004" in proc.output


def test_resume_warns_when_another_session_wrote_just_now(tmp_path):
    run = prepared(tmp_path)
    run.task("T001", "끝남", status="완료", **V120)
    proc = resume(run)
    assert proc.returncode == 0 and "! 다른 세션" in proc.output


def test_resume_of_the_same_session_passes_with_a_live_agent(tmp_path):
    run = prepared(tmp_path, session="same")
    run.task("T004", "도는 중", kind="flow-verify", status="진행", running_agent="verify-T004", **V120)
    assert resume(run, session="same").returncode == 0


def test_named_run_passes_but_warns(tmp_path):
    run = prepared(tmp_path)
    run.task("T004", "도는 중", kind="flow-verify", status="진행", running_agent="verify-T004", **V120)
    proc = resume(run, said=str(run.path) + " 이어서")
    assert proc.returncode == 0 and "! 다른 세션" in proc.output


def test_old_run_resumes_as_before(tmp_path):
    run = prepared(tmp_path)
    run.task("T004", "옛 실행", kind="flow-verify", status="진행", running_agent="verify-T004", started_version="1.1.1")
    assert resume(run).returncode == 0


def test_retracted_resume_is_not_counted(run_dir):
    write(run_dir.path / "journal.md",
          "- 2026-11-06 12:00:00 | 메모 | - | 시작\n- 2026-11-06 12:29:04 | 재개 | - | 시작\n"
          "- 2026-11-06 12:29:35 | 메모 | - | 정정: 앞의 재개 줄은 다른 세션이 남긴 것이다\n"
          "- 2026-11-06 22:49:39 | 재개 | - | 시작\n")
    assert "재개 1번" in collect.stall_line(str(run_dir))


# ------------------------------------------------------------ 배포만으로 시작한 실행

def deploy_only(run_dir, answers=""):
    return deploy(run_dir, proof(), answers=answers)


def test_deploy_only_is_stopped_with_the_fact_and_how_to_close(run_dir):
    t = deploy_only(run_dir)
    why = gate(run_dir, t)
    assert "최종 CI" in why and "승인|위험 수용 최종 CI" in why
    lines = task_set.identity_lines(str(run_dir), t)
    assert any("닫지 못함" in l and "마무리 task가 없어" in l for l in lines)


def test_deploy_only_closes_with_the_named_risk_answer(run_dir):
    assert gate(run_dir, deploy_only(run_dir, answers=RISK_ANSWER)) is None


@pytest.mark.parametrize("answer", ["- 2026-10-15 11:00:00 | 승인 | 승인 | 원문: \"승인\"\n",
                                    "- 2026-10-15 11:00:00 | 승인 | 위험 수용 | 원문: \"받아들임\"\n",
                                    "- 2026-10-15 11:00:00 | 승인 | 위험 수용 빌드 식별자 | 원문: \"받아들임\"\n",
                                    "- 2026-10-15 11:00:00 | 승인 | 위험 수용 안 함 최종 CI 없음 | 원문: \"안 함\"\n"])
def test_deploy_only_refuses_other_answers(run_dir, answer):
    assert gate(run_dir, deploy_only(run_dir, answers=answer))


def test_a_run_with_a_wrap_up_keeps_the_hard_stop(run_dir):
    """마무리가 있는데 끝나지 않았으면 위험 수용으로 넘어가지 않는다."""
    run_dir.task("T099", "마무리", kind="wrap-up", block="마무리", status="보류", **NEW)
    why = gate(run_dir, deploy_only(run_dir, answers=RISK_ANSWER))
    assert why and "완료된 1.0.1 wrap-up" in why


def test_old_run_keeps_the_old_refusal(run_dir):
    why = gate(run_dir, deploy(run_dir, proof(), meta=OLD, answers=RISK_ANSWER))
    assert why and "완료된 1.0.1 wrap-up" in why


def test_deploy_screens_say_there_is_no_final_ci_before_the_answer(run_dir):
    t = deploy_only(run_dir)
    assert any("최종 CI가 없습니다" in l for l in lib.source_tested_lines(str(run_dir), t))
    run_dir.task("T099", "마무리", kind="wrap-up", block="마무리", status="보류", **NEW)
    assert not lib.source_tested_lines(str(run_dir), t)
