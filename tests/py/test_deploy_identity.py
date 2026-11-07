"""배포 대상 동일성 관문: 소스를 시험한 CI(`검증 artifact: 없음(소스 시험)`)의 기계 대조.

1.2.0부터 시작한 실행에만 적용한다. 그 앞의 실행은 예전 글자 비교 그대로다."""
import subprocess

import pytest

from conftest import ROOT, run_script, write
import exec as execmod
import screen
import task_set

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}
SHA = "a" * 12 + "b" * 28
OTHER = "c" * 40
SOURCE = "없음(소스 시험)"
FACT = "빌드 결과물 자체를 시험한 것은 아닙니다. 빌드 설정과 환경 차이는 배포 뒤 확인이 잡습니다"
REC_OK = ("승인", "승인", "승인")
HEAD = "판정자: xjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
EVIDENCE = ("\n## 검사 입력과 독립 근거\n"
            "- 제품 commit/diff: abc1234 | 시험 소스: tests@abc | 설정: cfg@abc | lock/설치: lock@abc | "
            "명령: pytest -q | 환경 초기화: clean-db-7 | 판정자: xjudge-T001 | 시각: 2026-10-15 10:00:00 | "
            "종료 코드: 0 | 로그: logs/pytest.txt\n\n## 남은 검사와 자원 대기\n- 없음\n")
READ = "판정자: rjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
GIT_ID = ["-c", "user.name=dryrun", "-c", "user.email=dryrun@example.invalid", "-c", "commit.gpgsign=false"]


def ctx(record=REC_OK, old_stage=""):
    return {"record": record, "reason": None, "archived": False, "snapshot": False, "old_stage": old_stage}


def judged(section):
    return HEAD + EVIDENCE + section


def authority(run_dir, commit=SHA, artifact=SOURCE, meta=NEW, tid="T099"):
    run_dir.task(tid, "마무리", kind="wrap-up", block="마무리", status="완료", stage="끝", exported_commit=commit,
                 approved="2026-10-15 11:00:00", **meta)
    run_dir.judge(tid, READ)
    write(run_dir.task_dir(tid) / "judge-run.md", judged(
        "\n## 최종 배포 후보 CI\n- 범위: 전체 검증\n- 검증 commit: {}\n- 검증 artifact: {}\n".format(commit, artifact)))


def proof(check=SHA, deployed=SHA, artifact=SOURCE, build=SHA + "-20261106", extra=""):
    lines = ["- 검증 commit: {}".format(check), "- 검증 artifact: {}".format(artifact), "- 배포 commit: {}".format(deployed)]
    if build is not None:
        lines.append("- 빌드 식별자: {}".format(build))
    return "\n## 배포 대상 동일성\n" + "\n".join(lines) + "\n" + extra


def tree_lines(*rows):
    return "".join("- 2026-10-15 10:01:00 | {} | 종료 코드 0 | 지점 실행승인:{}\n"
                   "- 2026-10-15 10:01:00 | 배포 폴더 상태 | 실행승인:{} | HEAD {} | 변경 {}\n".format(cmd, n, n, head, dirty)
                   for n, (cmd, head, dirty) in enumerate(rows, 1))


def deploy(run_dir, section, rows=(("./deploy.sh", SHA, "0"),), deployed=SHA, meta=NEW, answers=""):
    run_dir.task("T001", "배포 실행", kind="deploy-exec", block="배포", status="진행", stage="끝", deploy_outcome="유지",
                 deployed_commit=deployed, sections={"승인 기록": answers}, **meta)
    d = run_dir.task_dir("T001")
    write(d / "judge-run.md", judged(section))
    lines = [r[0] for r in rows]
    write(d / "approved-cmds-실행승인.md", "# 얼린 명령\n\n" + "".join("{}. {}\n".format(i, x) for i, x in enumerate(lines, 1))
          + "\n해시: {}\n얼린 시각: 2026-10-15 10:00:00\n".format(execmod.digest(lines)))
    write(d / "exec.md", tree_lines(*rows))
    return run_dir.tasks()["T001"]


def gate(run_dir, t):
    return task_set.stage_rule(str(run_dir), t, "진행", "완료", ctx())


def wrap(run_dir, artifact, commit=SHA, meta=NEW):
    run_dir.flow("only", status="검증 끝남", role="feature", round="1")
    run_dir.task("T001", "마무리", kind="wrap-up", block="마무리", status="승인대기", stage="끝", exported_commit=commit, **meta)
    run_dir.judge("T001", READ)
    d = run_dir.task_dir("T001")
    write(d / "judge-run.md", judged(
        "\n## 최종 배포 후보 CI\n- 범위: 전체 검증\n- 검증 commit: {}\n- 검증 artifact:{}\n".format(
            commit, " " + artifact if artifact else "")))
    write(d / "approved-cmds-실행승인.md", "# 얼린 명령\n\n1. echo ok\n\n해시: {}\n얼린 시각: 2026-10-15 10:00:00\n".format(
        execmod.digest(["echo ok"])))
    write(d / "exec.md", "- 2026-10-15 10:01:00 | echo ok | 종료 코드 0 | 지점 실행승인:1\n")
    return run_dir.tasks()["T001"]


def wrap_gate(run_dir, t):
    return task_set.stage_rule(str(run_dir), t, "승인대기", "완료", ctx(old_stage="결과승인"))


# ------------------------------------------------------------ 마무리가 받는 값

def test_wrap_up_accepts_exact_source_tested_mark_with_full_commit(run_dir):
    assert wrap_gate(run_dir, wrap(run_dir, SOURCE)) is None


@pytest.mark.parametrize("artifact", ["ci-run-77/image@sha256:0123", "sha256:" + "0" * 64])
def test_wrap_up_accepts_a_single_identifier(run_dir, artifact):
    assert wrap_gate(run_dir, wrap(run_dir, artifact)) is None


@pytest.mark.parametrize("artifact", [
    "없음(소스 시험) 로그는 logs/ci.txt", "없음(소스 시험), 배포 때 빌드", "없음 (소스 시험)", "없음(소스시험)", "없음: 소스 시험",
    "`없음(소스 시험)`", "**없음(소스 시험)**", "소스 시험", "해당 없음", "pytest 전부 통과", "빌드 안 함", "N/A", "none", "source",
])
def test_wrap_up_rejects_free_text_artifact(run_dir, artifact):
    why = wrap_gate(run_dir, wrap(run_dir, artifact))
    assert why and "검증 artifact" in why


@pytest.mark.parametrize("artifact", ["", "없음", "(없음)"])
def test_wrap_up_rejects_empty_artifact(run_dir, artifact):
    assert "필수 값 없음: 검증 artifact" in wrap_gate(run_dir, wrap(run_dir, artifact))


def test_wrap_up_source_tested_needs_full_commit(run_dir):
    assert "40자" in wrap_gate(run_dir, wrap(run_dir, SOURCE, commit=SHA[:12]))


# ------------------------------------------------------------ 빌드 결과물을 시험한 경우는 글자 비교 그대로

def hash_proof(check="image@sha256:good1", deployed="image@sha256:good1", seen=True):
    return (("\n## 배포 뒤 확인\n- 올라간 이미지: 실제값 {}\n".format(deployed) if seen else "")
            + "\n## 배포 대상 동일성\n- 검증 commit: {0}\n- 검증 artifact: {1}\n- 배포 commit: {0}\n- 배포 artifact: {2}\n"
            ).format(SHA, check, deployed)


def test_built_artifact_not_seen_on_deploy_side_is_refused(run_dir):
    """CI 번호처럼 배포에 없는 값을 양쪽 칸에 적어 기계 대조를 비켜 가지 못한다."""
    authority(run_dir, artifact="ci-77")
    why = gate(run_dir, deploy(run_dir, hash_proof(check="ci-77", deployed="ci-77", seen=False)))
    assert "배포 근거" in why and "ci-77" in why


def test_built_artifact_seen_in_deploy_log_passes(run_dir):
    authority(run_dir, artifact="image@sha256:good1")
    t = deploy(run_dir, hash_proof(seen=False))
    write(run_dir.task_dir("T001") / "logs" / "exec-실행승인-1.log", "pushed image@sha256:good1\n")
    assert gate(run_dir, t) is None


def test_built_artifact_same_hash_passes_without_build_id(run_dir):
    authority(run_dir, artifact="image@sha256:good1")
    assert gate(run_dir, deploy(run_dir, hash_proof())) is None


def test_built_artifact_different_hash_is_refused(run_dir):
    authority(run_dir, artifact="image@sha256:good1")
    t = deploy(run_dir, hash_proof(deployed="image@sha256:other2"))
    assert "배포 artifact가 검증 artifact와 다름" in gate(run_dir, t)


def test_source_mark_cannot_replace_a_built_artifact(run_dir):
    authority(run_dir, artifact="image@sha256:good1")
    t = deploy(run_dir, hash_proof(check=SOURCE, deployed=SOURCE))
    assert "최종 CI artifact와 다름" in gate(run_dir, t)


# ------------------------------------------------------------ 소스를 시험한 경우의 기계 대조

def test_source_tested_passes_on_machine_values(run_dir):
    authority(run_dir)
    assert gate(run_dir, deploy(run_dir, proof())) is None


@pytest.mark.parametrize("build", [SHA, SHA[:12], SHA[:7], SHA[:7].upper(), SHA + "+build.5", SHA[:12] + "-20261106"])
def test_source_tested_accepts_build_id_starting_with_the_commit(run_dir, build):
    authority(run_dir)
    assert gate(run_dir, deploy(run_dir, proof(build=build))) is None


def test_source_tested_keeps_head_moving_git_line_before_deploy(run_dir):
    authority(run_dir)
    rows = (("git checkout " + SHA, OTHER, "0"), ("./deploy.sh", SHA, "0"))
    assert gate(run_dir, deploy(run_dir, proof(), rows=rows)) is None


@pytest.mark.parametrize("artifact", ["image@sha256:good1", "없음", "없음(소스 시험) 실제로는 빌드", "소스 시험"])
def test_source_tested_rejects_other_mark_in_deploy_section(run_dir, artifact):
    authority(run_dir)
    assert "검증 artifact" in gate(run_dir, deploy(run_dir, proof(artifact=artifact)))


@pytest.mark.parametrize("check,deployed", [(SHA[:12], SHA[:12]), (SHA, SHA[:12]), (SHA[:12], SHA), (SHA[:7], SHA[:7])])
def test_source_tested_rejects_partial_commit_match(run_dir, check, deployed):
    authority(run_dir)
    assert "40자" in gate(run_dir, deploy(run_dir, proof(check=check, deployed=deployed)))


def test_source_tested_rejects_different_commits(run_dir):
    authority(run_dir)
    assert "배포 commit이 검증 commit과 다름" in gate(run_dir, deploy(run_dir, proof(deployed=OTHER, build=OTHER)))


def test_source_tested_rejects_commit_other_than_final_ci(run_dir):
    authority(run_dir)
    rows = (("./deploy.sh", OTHER, "0"),)
    t = deploy(run_dir, proof(check=OTHER, deployed=OTHER, build=OTHER), rows=rows, deployed=OTHER)
    assert "최종 CI commit과 다름" in gate(run_dir, t)


def test_source_tested_requires_deployed_commit_header(run_dir):
    authority(run_dir)
    assert "deployed_commit" in gate(run_dir, deploy(run_dir, proof(), deployed=""))


@pytest.mark.parametrize("build", [
    OTHER, OTHER[:7], OTHER + "-20261106",            # 다른 커밋의 빌드 식별자
    SHA + "-dirty", SHA[:7] + "-dirty", SHA + ".dirty", SHA + "-DIRTY", SHA + "-5-dirty",   # 깨끗하지 않은 빌드
    SHA[:6], "v1.2.3-" + SHA, "build-" + SHA[:7],     # 해시로 시작하지 않음, 너무 짧음
    SHA[:7] + "g", SHA[:7] + "c", SHA + "0",          # 해시 뒤에 경계가 없음
    SHA + " 추정", "확인 안 됨", "없음(프로젝트에 없음)",   # 자유 글
])
def test_source_tested_rejects_bad_build_id(run_dir, build):
    authority(run_dir)
    assert "빌드 식별자" in gate(run_dir, deploy(run_dir, proof(build=build)))


@pytest.mark.parametrize("rows,expected", [
    ((("./deploy.sh", SHA, "2"),), "깨끗하지 않"),
    ((("./deploy.sh", SHA, "읽지 못함"),), "읽지 못"),
    ((("./deploy.sh", "읽지 못함", "0"),), "읽지 못"),
    ((("./deploy.sh", OTHER, "0"),), "배포 폴더 HEAD"),
    ((("./deploy.sh", OTHER, "0"), ("git checkout " + SHA, SHA, "0")), "배포 폴더 HEAD"),   # 다른 커밋에서 배포하고 나서 옮김
])
def test_source_tested_rejects_deploy_folder_state(run_dir, rows, expected):
    authority(run_dir)
    assert expected in gate(run_dir, deploy(run_dir, proof(), rows=rows))


def test_source_tested_rejects_missing_tree_record(run_dir):
    authority(run_dir)
    t = deploy(run_dir, proof())
    write(run_dir.task_dir("T001") / "exec.md", "- 2026-10-15 10:01:00 | ./deploy.sh | 종료 코드 0 | 지점 실행승인:1\n")
    assert "배포 폴더 상태 기록 없음" in gate(run_dir, t)


def test_source_tested_rejects_no_frozen_commands(run_dir):
    authority(run_dir)
    t = deploy(run_dir, proof())
    (run_dir.task_dir("T001") / "approved-cmds-실행승인.md").unlink()
    (run_dir.task_dir("T001") / "exec.md").unlink()
    assert "배포 폴더 상태" in gate(run_dir, t)


def test_after_keep_line_is_not_the_deploy(run_dir):
    authority(run_dir)
    rows = (("./deploy.sh", SHA, "0"), ("[유지 뒤] git update-ref refs/heads/prod " + OTHER, OTHER, "0"))
    assert task_set.deploy_target_problem(str(run_dir), deploy(run_dir, proof(), rows=rows)) is None


# ------------------------------------------------------------ 빌드 식별자가 없는 프로젝트: 위험 수용 답으로만 닫는다

ACCEPT = '- 2026-10-15 12:00:00 | 승인 | 위험 수용 빌드 식별자 | 원문: "빌드 식별자 없이 유지"'
REFUSE = '- 2026-10-15 12:00:00 | 승인 | 위험 수용 빌드 식별자 안 함 | 원문: "안 받는다"'
OTHER_RISK = '- 2026-10-15 12:00:00 | 승인 | 위험 수용 | 원문: "문서 검사 실패는 넘어가자"'
TREE_RISK = '- 2026-10-15 12:00:00 | 승인 | 위험 수용 작업 트리 | 원문: "그 순간은 못 재도 유지"'
BOTH_RISK = '- 2026-10-15 12:00:00 | 승인 | 위험 수용 빌드 식별자 작업 트리 | 원문: "둘 다 받는다"'


@pytest.mark.parametrize("build", [None, "없음", "(없음)"])
def test_no_build_id_holds_with_reason_until_risk_is_accepted(run_dir, build):
    authority(run_dir)
    why = gate(run_dir, deploy(run_dir, proof(build=build)))
    assert "빌드 식별자 없음" in why and "위험 수용" in why
    assert gate(run_dir, deploy(run_dir, proof(build=build), answers=ACCEPT)) is None


def test_blank_build_id_cell_holds(run_dir):
    authority(run_dir)
    assert "빌드 식별자 없음" in gate(run_dir, deploy(run_dir, proof(build=None, extra="- 빌드 식별자:\n")))


def test_answer_for_another_reason_does_not_close_missing_build_id(run_dir):
    authority(run_dir)
    assert "빌드 식별자 없음" in gate(run_dir, deploy(run_dir, proof(build="없음"), answers=OTHER_RISK))


def test_missing_build_id_reason_says_the_build_is_unconfirmed(run_dir):
    authority(run_dir)
    why = gate(run_dir, deploy(run_dir, proof(build="없음")))
    assert "기계로 확인하지 못했" in why and "승인|위험 수용 빌드 식별자|{원문}" in why


@pytest.mark.parametrize("build", ["v1.2.3-5-g" + SHA[:7], "1.2.3+" + SHA[:7], "20261106-" + SHA[:7], "1.2.3"])
def test_id_not_starting_with_commit_shows_the_way_out_and_closes_with_answer(run_dir, build):
    authority(run_dir)
    why = gate(run_dir, deploy(run_dir, proof(build=build)))
    assert "`없음`" in why and "커밋으로 시작하지 않" in why
    assert gate(run_dir, deploy(run_dir, proof(build="없음"), answers=ACCEPT)) is None


def test_other_commit_build_id_does_not_offer_the_way_out(run_dir):
    authority(run_dir)
    why = gate(run_dir, deploy(run_dir, proof(build=OTHER)))
    assert "다른 커밋" in why and "`없음`" not in why


def test_same_call_answer_closes_and_is_recorded(run_dir):
    authority(run_dir)
    deploy(run_dir, proof(build="없음"))
    actual = run_script("task_set", run_dir, "T001", "--status", "완료", "--record", "승인|위험 수용 빌드 식별자|빌드 식별자 없이 유지")
    assert actual.returncode == 0, actual.output
    text = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    assert "status: 완료" in text and "위험 수용 빌드 식별자" in text


@pytest.mark.parametrize("record", ["승인|위험 수용|넘어가자", "승인|위험 수용 빌드 식별자 안 함|안 받는다", "승인|위험 수용 빌드 식별자|", "승인|승인|승인"])
def test_same_call_with_unfit_answer_is_refused(run_dir, record):
    authority(run_dir)
    deploy(run_dir, proof(build="없음"))
    actual = run_script("task_set", run_dir, "T001", "--status", "완료", "--record", record)
    assert actual.returncode == 3 and "빌드 식별자 없음" in actual.stdout
    assert "status: 진행" in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")


USER_ROWS = (("[사용자 실행] ./deploy.sh", SHA, "0"),)


def user_only(run_dir, section, answers=""):
    t = deploy(run_dir, section, rows=USER_ROWS, answers=answers)
    write(run_dir.task_dir("T001") / "exec.md", "- 2026-10-15 10:01:00 | ./deploy.sh | 사용자 실행: 종료 코드 0 | 지점 실행승인:1\n")
    return run_dir.tasks()["T001"]


def test_user_run_line_is_unmeasured_until_risk_is_accepted(run_dir):
    authority(run_dir)
    why = gate(run_dir, user_only(run_dir, proof()))
    assert "실행승인:1" in why and "재지 못" in why and "승인|위험 수용 작업 트리|{원문}" in why
    assert gate(run_dir, user_only(run_dir, proof(), answers=TREE_RISK)) is None


def test_build_id_answer_does_not_close_unmeasured_user_line(run_dir):
    authority(run_dir)
    assert "재지 못" in gate(run_dir, user_only(run_dir, proof(), answers=ACCEPT))


def test_both_unmeasured_reasons_are_closed_by_one_answer_naming_both(run_dir):
    authority(run_dir)
    why = gate(run_dir, user_only(run_dir, proof(build="없음"), answers=TREE_RISK))
    assert "빌드 식별자 없음" in why and "재지 못" not in why
    assert "승인|위험 수용 빌드 식별자 작업 트리|{원문}" in gate(run_dir, user_only(run_dir, proof(build="없음")))
    assert gate(run_dir, user_only(run_dir, proof(build="없음"), answers=BOTH_RISK)) is None


def test_refused_risk_answer_does_not_close(run_dir):
    authority(run_dir)
    assert "빌드 식별자 없음" in gate(run_dir, deploy(run_dir, proof(build=None), answers=REFUSE))


@pytest.mark.parametrize("build", [OTHER, SHA + "-dirty"])
def test_risk_answer_does_not_excuse_wrong_build_id(run_dir, build):
    authority(run_dir)
    assert "빌드 식별자" in gate(run_dir, deploy(run_dir, proof(build=build), answers=ACCEPT))


def test_risk_answer_does_not_excuse_dirty_tree_or_commit(run_dir):
    authority(run_dir)
    t = deploy(run_dir, proof(build=None), rows=(("./deploy.sh", SHA, "1"),), answers=ACCEPT)
    assert "깨끗하지 않" in gate(run_dir, t)
    assert "40자" in gate(run_dir, deploy(run_dir, proof(check=SHA[:12], deployed=SHA[:12], build=None), answers=ACCEPT))


def test_script_refuses_with_reason_and_leaves_status(run_dir):
    authority(run_dir)
    deploy(run_dir, proof(build=OTHER))
    actual = run_script("task_set", run_dir, "T001", "--status", "완료", "--record", "승인|승인|승인")
    assert actual.returncode == 3
    assert "빌드 식별자" in actual.stdout
    assert "status: 진행" in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")


# ------------------------------------------------------------ 적용 범위: 1.2.0 앞에 시작한 실행은 예전 그대로

@pytest.mark.parametrize("status", ["대기", "백로그", "보류"])
def test_never_started_task_does_not_turn_run_back_to_old_rules(run_dir, lib, status):
    authority(run_dir)
    run_dir.task("T050", "시작 안 한 행", kind="implementation", status=status)
    assert lib.run_from_v120(str(run_dir)) is True
    assert "빌드 식별자" in gate(run_dir, deploy(run_dir, proof(build=OTHER)))


def test_task_moved_from_waiting_to_held_keeps_new_rules(run_dir, lib):
    authority(run_dir)
    run_dir.task("T050", "뒤 환경", kind="implementation", status="대기")
    actual = run_script("task_set", run_dir, "T050", "--status", "보류", "--reason", "앞 환경 보류")
    assert actual.returncode == 0, actual.output
    assert lib.run_from_v120(str(run_dir)) is True


@pytest.mark.parametrize("status", ["보류", "백로그", "완료"])
def test_started_old_task_keeps_run_old(run_dir, lib, status):
    authority(run_dir)
    run_dir.task("T050", "1.1.1에 시작", kind="implementation", status=status, **OLD)
    assert lib.run_from_v120(str(run_dir)) is False


def test_started_task_without_version_keeps_run_old(run_dir, lib):
    authority(run_dir)
    run_dir.task("T050", "판본 칸 이전", kind="implementation", status="완료")
    run_dir.task("T051", "판본 없이 시작", kind="implementation", status="보류", started="2026-10-15 09:00:00")
    assert lib.run_from_v120(str(run_dir)) is False


def test_old_run_hold_is_not_released(run_dir):
    """1.1.1 실행: 마무리의 값이 빌드 해시면 소스 표지로 풀리지 않는다."""
    authority(run_dir, artifact="image@sha256:good1", meta=OLD)
    t = deploy(run_dir, hash_proof(check=SOURCE, deployed=SOURCE), meta=OLD)
    assert "최종 CI artifact와 다름" in gate(run_dir, t)


def test_new_deploy_task_in_old_run_keeps_old_rule(run_dir):
    """하네스를 올린 뒤 시작한 배포 실행이어도 실행이 1.1.1부터면 기계 대조로 바뀌지 않는다."""
    authority(run_dir, artifact=SOURCE, meta=OLD)
    t = deploy(run_dir, proof())
    assert "필수 값 없음: 배포 artifact" in gate(run_dir, t)


def test_old_run_wrap_up_keeps_free_text_artifact(run_dir):
    assert wrap_gate(run_dir, wrap(run_dir, "ci 실행 77번", meta=OLD)) is None


def test_old_run_does_not_need_tree_record_or_build_id(run_dir):
    authority(run_dir, artifact="image@sha256:good1", meta=OLD)
    t = deploy(run_dir, hash_proof(seen=False), meta=OLD)
    (run_dir.task_dir("T001") / "exec.md").unlink()
    assert task_set.deploy_target_problem(str(run_dir), t) is None


# ------------------------------------------------------------ exec.py가 남기는 배포 폴더 상태

@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "deploy-folder"
    path.mkdir()
    for args in (["init", "-q"], ["config", "core.autocrlf", "false"]):
        subprocess.run(["git", "-C", str(path)] + args, check=True)
    (path / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path)] + GIT_ID + ["commit", "-qm", "first"], check=True)
    return path


def head_of(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def frozen_deploy(run_dir, repo, meta=NEW, lines=("echo deployed",)):
    run_dir.flow("only", status="합쳐짐", role="feature", round="1", dir=str(repo))
    run_dir.task("T001", "배포 실행", kind="deploy-exec", block="배포", status="진행", stage="명령", flow="only", **meta)
    write(run_dir.task_dir("T001") / "approved-cmds-실행승인.md",
          "# 얼린 명령\n\n" + "".join("{}. {}\n".format(i, x) for i, x in enumerate(lines, 1))
          + "\n해시: {}\n얼린 시각: 2026-10-15 10:00:00\n".format(execmod.digest(list(lines))))


def test_step_records_full_head_and_clean_tree(run_dir, repo):
    frozen_deploy(run_dir, repo)
    actual = run_script("exec", run_dir, "T001", "--step", "실행승인:1")
    assert actual.returncode == 0, actual.output
    text = (run_dir.task_dir("T001") / "exec.md").read_text(encoding="utf-8")
    assert "| 배포 폴더 상태 | 실행승인:1 | HEAD {} | 변경 0\n".format(head_of(repo)) in text
    t = run_dir.tasks()["T001"]
    assert execmod.verify(str(run_dir), t)[0] is True      # 상태 줄이 돈 줄로 읽히지 않는다
    assert [e["label"] for e in execmod.exec_lines(t)] == ["실행승인:1"]
    assert execmod.deploy_tree_problem(t, head_of(repo)) == ""
    assert "배포 폴더 HEAD" in execmod.deploy_tree_problem(t, OTHER)


def test_step_in_old_run_writes_no_record(run_dir, repo):
    frozen_deploy(run_dir, repo, meta=OLD)
    assert run_script("exec", run_dir, "T001", "--step", "실행승인:1").returncode == 0
    assert "배포 폴더 상태" not in (run_dir.task_dir("T001") / "exec.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("dirty_when_reported", [True, False])
def test_user_run_line_is_not_judged_by_tree_when_result_is_written(run_dir, repo, dirty_when_reported):
    """도구 캐시가 남은 거짓 거절도, 알리기 전에 지운 거짓 통과도 없다: 어느 쪽이든 재지 못함이다."""
    frozen_deploy(run_dir, repo, lines=("[사용자 실행] ./deploy.sh",))
    if dirty_when_reported:
        (repo / "b.txt").write_text("b\n", encoding="utf-8")
    actual = run_script("exec", run_dir, "T001", "--user-result", "실행승인:1", "종료 코드 0, 출력 끝")
    assert actual.returncode == 0, actual.output
    t = run_dir.tasks()["T001"]
    assert "배포 폴더 상태" not in (run_dir.task_dir("T001") / "exec.md").read_text(encoding="utf-8")
    assert execmod.deploy_tree_problem(t, head_of(repo)) == ""
    assert execmod.deploy_tree_unmeasured(t) == ["실행승인:1"]


def rerun_by_main(run_dir, repo, line="echo partial > half.out; exit 3"):
    """--step이 실패하고, 사람 답을 받아 메인이 다른 방법으로 돌린 줄."""
    frozen_deploy(run_dir, repo, lines=(line,))
    assert run_script("exec", run_dir, "T001", "--step", "실행승인:1").returncode == 3
    assert run_script("task_set", run_dir, "T001", "--record", "승인|승인|다른 방법으로 돌린다").returncode == 0


@pytest.mark.parametrize("left", ["half.out", "manual.txt"])
def test_line_rerun_by_main_is_unmeasured_and_closes_only_with_the_answer(run_dir, repo, left):
    """실패한 줄이 남긴 변경도, 다시 돌리기 전에 생긴 변경도 앞선 시도의 기록으로 통과하지 못한다."""
    commit = head_of(repo)
    authority(run_dir, commit=commit)
    rerun_by_main(run_dir, repo)
    (repo / left).write_text("x\n", encoding="utf-8")
    actual = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0, 다시 돌림")
    assert actual.returncode == 0, actual.output
    write(run_dir.task_dir("T001") / "judge-run.md", judged(proof(check=commit, deployed=commit, build=commit)))

    t = run_dir.tasks()["T001"]
    assert execmod.deploy_tree_unmeasured(t) == ["실행승인:1"]
    assert execmod.deploy_tree_problem(t, commit) == ""
    out = run_script("task_set", run_dir, "T001", "--identity").stdout
    assert "닫지 못함" in out and "다른 방법으로 실행해" in out and "재지 못" in out and "승인|위험 수용 작업 트리|{원문}" in out

    assert run_script("task_set", run_dir, "T001", "--record", "승인|위험 수용 빌드 식별자|다른 위험").returncode == 0
    assert "닫지 못함" in run_script("task_set", run_dir, "T001", "--identity").stdout
    assert run_script("task_set", run_dir, "T001", "--record", "승인|위험 수용 작업 트리|그 순간은 못 재도 유지").returncode == 0
    assert "배포 대상 동일성: 통과" in run_script("task_set", run_dir, "T001", "--identity").stdout


def test_stale_head_of_failed_try_does_not_refuse_line_rerun_by_main(run_dir, repo):
    """실패한 시도의 HEAD는 다시 돌린 순간의 값이 아니다: 답으로 닫을 길을 막지 않는다."""
    rerun_by_main(run_dir, repo)
    assert run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0, 다시 돌림").returncode == 0
    t = run_dir.tasks()["T001"]
    assert execmod.deploy_tree_problem(t, OTHER) == "" and execmod.deploy_tree_unmeasured(t) == ["실행승인:1"]


def test_failed_step_without_main_result_is_still_measured(run_dir, repo):
    rerun_by_main(run_dir, repo)
    t = run_dir.tasks()["T001"]
    assert execmod.deploy_tree_unmeasured(t) == []
    assert "배포 폴더 HEAD" in execmod.deploy_tree_problem(t, OTHER)


def test_step_line_that_dirties_the_tree_is_judged_by_state_before_it_ran(run_dir, repo):
    frozen_deploy(run_dir, repo, lines=("echo y > only.out",))
    assert run_script("exec", run_dir, "T001", "--step", "실행승인:1").returncode == 0
    t = run_dir.tasks()["T001"]
    assert execmod.deploy_tree_problem(t, head_of(repo)) == "" and execmod.deploy_tree_unmeasured(t) == []


# ------------------------------------------------------------ 사람에게 보이는 화면

def cells():
    return ("# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n- 없음\n"
            "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 없음\n\n## 본문\n- 없음\n")


def plan(run_dir, meta=NEW):
    run_dir.task("T002", "배포 계획", kind="deploy-plan", block="배포", status="승인대기", **meta)
    run_dir.result("T002", cells())


def test_plan_screen_states_what_source_test_does_not_cover(run_dir):
    authority(run_dir)
    plan(run_dir)
    assert FACT in screen.build(str(run_dir), "T002")["screen"]["알릴 것"]


def test_plan_screen_is_silent_for_built_artifact(run_dir):
    authority(run_dir, artifact="image@sha256:good1")
    plan(run_dir)
    assert FACT not in screen.build(str(run_dir), "T002")["screen"].get("알릴 것", "")


def test_old_run_screen_is_silent(run_dir):
    authority(run_dir, meta=OLD)
    plan(run_dir, meta=OLD)
    assert FACT not in screen.build(str(run_dir), "T002")["screen"].get("알릴 것", "")


def test_wrap_up_screen_states_fact(run_dir):
    wrap(run_dir, SOURCE)
    run_dir.result("T001", cells())
    assert FACT in screen.build(str(run_dir), "T001")["screen"]["알릴 것"]


def test_result_screen_material_shows_pass_or_reason(run_dir):
    authority(run_dir)
    deploy(run_dir, proof())
    good = run_script("task_set", run_dir, "T001", "--identity")
    assert good.returncode == 0
    assert FACT in good.stdout and "배포 대상 동일성: 통과" in good.stdout

    deploy(run_dir, proof(build=OTHER))
    bad = run_script("task_set", run_dir, "T001", "--identity")
    assert "배포 대상 동일성: 닫지 못함" in bad.stdout and "빌드 식별자" in bad.stdout


def test_identity_before_answer_shows_pass_without_deployed_commit(run_dir):
    authority(run_dir)
    t = deploy(run_dir, proof(), deployed="")
    actual = run_script("task_set", run_dir, "T001", "--identity")
    assert "배포 대상 동일성: 통과" in actual.stdout
    assert "deployed_commit" in gate(run_dir, t)       # 완료 관문은 그대로 거절한다


def test_identity_before_answer_asks_about_missing_build_id(run_dir):
    authority(run_dir)
    deploy(run_dir, proof(build=None), deployed="")
    out = run_script("task_set", run_dir, "T001", "--identity").stdout
    assert "빌드 식별자 없음" in out and "기계로 확인하지 못했" in out and "deployed_commit" not in out


def test_identity_still_refuses_different_deployed_commit(run_dir):
    authority(run_dir)
    deploy(run_dir, proof(), deployed=OTHER)
    assert "deployed_commit" in run_script("task_set", run_dir, "T001", "--identity").stdout


def test_result_screen_material_is_unchanged_in_old_run(run_dir):
    authority(run_dir, artifact="image@sha256:good1", meta=OLD)
    deploy(run_dir, hash_proof(), meta=OLD)
    assert "배포 대상 동일성" not in run_script("task_set", run_dir, "T001", "--identity").stdout


# ------------------------------------------------------------ 문서와 코드의 같은 글

def test_docs_carry_the_exact_mark(lib):
    for rel in ("references/formats/judge-run-file.md", "references/kinds/deploy-plan.md",
                "references/kinds/deploy-exec/main-order.md"):
        assert lib.SOURCE_TESTED in (ROOT / rel).read_text(encoding="utf-8"), rel
    order = (ROOT / "references/kinds/deploy-exec/main-order.md").read_text(encoding="utf-8")
    assert "--identity" in order and "승인|위험 수용 {이유}|{원문}" in order
    assert "`없음`" in (ROOT / "references/kinds/deploy-exec/run-check.md").read_text(encoding="utf-8")
    assert lib.SOURCE_TESTED == SOURCE and lib.SOURCE_TESTED_FACT == FACT
