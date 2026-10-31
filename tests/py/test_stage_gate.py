"""1.1.1: 묻는 stage별 판정 요구(D), 마무리 순서(C), 승인과 넣는 대상 묶기(E), 최종 CI 실패 귀속(F), 넣기 전 문서 검사(G).

- 관문은 함수 단위(`task_set.check_transition`·`stage_rule`·`archive_check`, `exec.freeze`·`pre_check`)로 부르고,
  사용자가 직접 넣은 마무리의 완료와 승인 뒤 바뀐 끝의 거부는 임시 git 저장소로 명령행에서 돌린다.
- 판본 문턱: `started_version` 1.1.1부터 stage별 요구가 걸리고(`devflow_lib.stage_judges`), 그 전 task는 kind 단위 그대로다.
"""
import os
import subprocess

import pytest

import devflow_lib
import exec as execmod
import kinds
import screen
import task_set
from conftest import run_script, write

V111 = {"started_version": "1.1.1", "rules": "2"}
V110 = {"started_version": "1.1.0", "rules": "2"}
REC_OK = ("승인", "승인", "승인")
GIT_ID = ["-c", "user.name=dryrun", "-c", "user.email=dryrun@example.invalid", "-c", "commit.gpgsign=false"]
READ_JUDGE = "판정자: rjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"


def run_judge(failed="- 없음", final_ci="", cause=""):
    return ("판정자: xjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n" + failed + "\n"
            "\n## 검사 입력과 독립 근거\n"
            "- 제품 commit/diff: abc1234 | 시험 소스: tests@abc | 설정: cfg@abc | lock/설치: lock@abc | "
            "명령: pytest -q | 환경 초기화: clean-db-7 | 판정자: xjudge-T001 | 시각: 2026-10-15 10:00:00 | "
            "종료 코드: 0 | 로그: logs/pytest.txt\n"
            "\n## 남은 검사와 자원 대기\n- 없음\n" + final_ci + cause)


def final_ci(commit="abc1234"):
    return "\n## 최종 배포 후보 CI\n- 범위: 전체 검증\n- 검증 commit: {}\n- 검증 artifact: ci-run-9\n".format(commit)


def ctx(record=None, old_stage=""):
    return {"record": record, "reason": None, "archived": False, "snapshot": False, "old_stage": old_stage}


def make(run_dir, tid="T001", judge=None, judge_run=None, **meta):
    run_dir.task(tid, "관문 시험", **meta)
    if judge:
        run_dir.judge(tid, judge)
    if judge_run:
        write(run_dir.task_dir(tid) / "judge-run.md", judge_run)
    return run_dir.tasks()[tid]


def check(run_dir, t, old, new, **kw):
    return task_set.check_transition(str(run_dir), t, old, new, ctx(**kw))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + GIT_ID + list(args), check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def posix(path):
    return str(path).replace(os.sep, "/")


def set_meta(run_dir, **kv):
    p = run_dir.path / "run.md"
    text = p.read_text(encoding="utf-8")
    write(p, text.replace("status: 진행\n", "status: 진행\n" + "".join("{}: {}\n".format(k, v) for k, v in kv.items()), 1))


# ---------------------------------------------------------------- 등록표

def test_stage_judges_table_covers_ask_stages_of_stage_kinds_except_probe():
    for (kind, stage), need in kinds.STAGE_JUDGES.items():
        assert kind in kinds.STAGE_KINDS and kind != "probe", kind
        assert stage in kinds.ASK_STAGES and stage in kinds.stages_of(kind), (kind, stage)
        assert set(need) <= {"read", "run"}
    assert kinds.STAGE_JUDGES[("wrap-up", "실행승인")] == ("read", "run")
    assert kinds.STAGE_JUDGES[("merge", "실행승인")] == ()


def test_required_judges_by_stage_and_version(run_dir):
    w = make(run_dir, "T001", kind="wrap-up", block="마무리", status="자체검증", **V111)
    m = make(run_dir, "T002", kind="merge", block="구현", status="진행", **V111)
    old = make(run_dir, "T003", kind="merge", block="구현", status="진행", **V110)
    assert devflow_lib.required_judges(w, "실행승인") == {"read", "run"}
    assert devflow_lib.required_judges(m, "실행승인") == set()
    assert devflow_lib.required_judges(m) == {"run"}                 # stage 없이는 kind 단위(완료 관문)
    assert devflow_lib.required_judges(old, "실행승인") == {"run"}   # 1.1.1 전에 시작한 task는 그대로


# ---------------------------------------------------------------- C6·D2: 관문

@pytest.mark.parametrize("old", ["자체검증", "진행"])
def test_new_wrap_up_cannot_reach_run_approval_without_run_judge(run_dir, old):
    t = make(run_dir, kind="wrap-up", block="마무리", status=old, stage="실행승인", judge=READ_JUDGE, **V111)
    why = check(run_dir, t, old, "승인대기")
    assert why == "필요한 판정이 없음: judge-run.md 없음 (stage=실행승인 앞, kinds.STAGE_JUDGES)", why
    write(run_dir.task_dir("T001") / "judge-run.md", run_judge(final_ci=final_ci()))
    assert check(run_dir, run_dir.tasks()["T001"], old, "승인대기") is None


def test_new_wrap_up_without_any_judge_cannot_skip_selfcheck(run_dir):
    # 리뷰 질문 3-1: 진행→승인대기로 판정 0개인 채 실행승인에 가던 길
    t = make(run_dir, kind="wrap-up", block="마무리", status="진행", stage="실행승인", **V111)
    assert check(run_dir, t, "진행", "승인대기").startswith("필요한 판정이 없음: judge-run.md 없음; judge.md 없음")


def test_old_wrap_up_run_to_waiting_unchanged(run_dir):
    t = make(run_dir, kind="wrap-up", block="마무리", status="진행", stage="실행승인", **V110)
    assert check(run_dir, t, "진행", "승인대기") is None


def test_new_merge_run_approval_needs_no_judge_and_screen_has_no_false_warning(run_dir):
    t = make(run_dir, kind="merge", block="구현", status="진행", stage="실행승인", **V111)
    assert check(run_dir, t, "진행", "승인대기") is None
    run_dir.result("T001", "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 합칩니다\n### 하실 일·허용 요청\n- 없음\n"
                           "### 알릴 것\n- 없음\n### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 커밋 1\n")
    b = screen.build(str(run_dir), "T001")
    assert b["judges_ok"] is True, b["judges_why"]
    old = make(run_dir, "T002", kind="merge", block="구현", status="진행", stage="실행승인", **V110)
    run_dir.result("T002", (run_dir.task_dir("T001") / "result.md").read_text(encoding="utf-8"))
    assert screen.build(str(run_dir), "T002")["judges_ok"] is False   # 옛 task는 그대로(kind 단위)
    assert old is not None


def test_new_deploy_exec_put_approval_needs_read_judge_and_doc_check(run_dir):
    t = make(run_dir, kind="deploy-exec", block="배포", status="진행", stage="넣기승인",
             judge_run=run_judge(), **V111)
    assert check(run_dir, t, "진행", "승인대기") == \
        "필요한 판정이 없음: judge.md 없음 (stage=넣기승인 앞, kinds.STAGE_JUDGES)"
    run_dir.judge("T001", READ_JUDGE)
    assert check(run_dir, run_dir.tasks()["T001"], "진행", "승인대기") is None   # recon에 문서 검사가 없음
    write(run_dir.path / "recon.md", "# 정찰\n\n## 문서를 읽는 검사\n- `npm run check:static`\n")
    why = check(run_dir, run_dir.tasks()["T001"], "진행", "승인대기")
    assert why.startswith("필요한 판정이 없음: main-run.md 「넣기 전 문서 검사」의 검증 commit·종료 코드 없음"), why
    write(run_dir.task_dir("T001") / "main-run.md",
          "## 넣기 전 문서 검사\n- 검증 commit: abc1234\n- 명령: npm run check:static\n- 종료 코드: 0\n- 로그: logs/doc.txt\n")
    assert check(run_dir, run_dir.tasks()["T001"], "진행", "승인대기") is None
    write(run_dir.path / "recon.md", "# 정찰\n\n## 문서를 읽는 검사\n없음\n")
    assert devflow_lib.doc_check_command(str(run_dir)) == ""


# ---------------------------------------------------------------- E1: 얼림의 넣는 끝

def approved(run_dir, tid="T001"):
    p = run_dir.task_dir(tid) / "task.md"
    s = p.read_text(encoding="utf-8")
    write(p, s.replace("## 승인 기록\n", "## 승인 기록\n- 2026-10-15 10:30:00 | 실행승인 | 승인 | 원문: \"넣어 주세요\"\n", 1))


CMD_RESULT = ("# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 내보냅니다\n  ```cmd\n  {}\n  ```\n### 하실 일·허용 요청\n- 없음\n"
              "### 알릴 것\n- 없음\n### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 명령 1\n")


def test_freeze_wrap_up_records_ci_commit_and_refuses_without_ci(run_dir):
    policy = {"started_version": "1.0.1", "rules": "2"}
    make(run_dir, kind="wrap-up", block="마무리", status="진행", stage="실행",
         approval_requested="2026-10-15 10:00:00", judge_run=run_judge(), **policy)
    approved(run_dir)
    run_dir.result("T001", CMD_RESULT.format("git merge --ff-only integ"))
    rc, msg = execmod.freeze(str(run_dir), "T001", "실행승인")
    assert rc == 3 and "최종 배포 후보 CI" in msg, msg
    write(run_dir.task_dir("T001") / "judge-run.md", run_judge(final_ci=final_ci("abc1234")))
    rc, msg = execmod.freeze(str(run_dir), "T001", "실행승인")
    assert rc == 0, msg
    t = run_dir.tasks()["T001"]
    assert execmod.frozen_tips(t, "실행승인") == {1: "abc1234"}
    assert execmod.read_frozen(t, "실행승인") == ["git merge --ff-only integ"]
    # 넣는 끝을 손으로 고치면 해시가 어긋난다
    p = run_dir.task_dir("T001") / "approved-cmds-실행승인.md"
    write(p, p.read_text(encoding="utf-8").replace("넣는 끝 1: abc1234", "넣는 끝 1: def5678"))
    with pytest.raises(execmod.Reject):
        execmod.read_frozen(t, "실행승인")


@pytest.fixture
def repo_run(run_dir, tmp_path):
    """원래 폴더 = 통합 폴더인 저장소: main(개발 기준), integ(통합), feat(흐름)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo / "a.txt", "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "checkout", "-q", "-b", "feat")
    write(repo / "b.txt", "b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat")
    git(repo, "checkout", "-q", "-b", "integ")
    git(repo, "checkout", "-q", "main")
    set_meta(run_dir, project=posix(repo), integration_dir=posix(repo), integration_branch="integ", base_branch="main")
    run_dir.flow("f1", branch="feat", dir=posix(repo))
    return repo


def test_step_rejects_when_source_tip_moved_after_approval(run_dir, repo_run):
    git(repo_run, "checkout", "-q", "integ")
    make(run_dir, kind="merge", block="구현", status="승인대기", stage="실행승인", flow="f1",
         approval_requested="2026-10-15 10:00:00", **V111)
    run_dir.result("T001", CMD_RESULT.format("git merge --no-edit feat"))
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "stage=실행", "--record", "승인|실행 승인|합쳐 주세요")
    assert r.returncode == 0, r.output
    tip = git(repo_run, "rev-parse", "feat")
    assert execmod.frozen_tips(run_dir.tasks()["T001"], "실행승인") == {1: tip}
    # 승인 뒤 흐름 브랜치에 커밋이 더해짐
    git(repo_run, "checkout", "-q", "feat")
    write(repo_run / "c.txt", "c\n")
    git(repo_run, "add", "-A")
    git(repo_run, "commit", "-q", "-m", "after approval")
    git(repo_run, "checkout", "-q", "integ")
    r = run_script("exec", run_dir, "T001", "--step", "실행승인:1")
    assert r.returncode == 3 and "넣는 쪽의 끝이 승인 때와 다름" in r.output, r.output
    assert not (run_dir.task_dir("T001") / "exec.md").exists()


# ---------------------------------------------------------------- E4: 사용자가 직접 넣은 마무리의 완료

def test_user_inserted_wrap_up_completes_with_exported_commit_filled_before_gate(run_dir, repo_run):
    git(repo_run, "merge", "-q", "--ff-only", "feat")   # 사용자가 직접 넣음(main = feat 끝)
    tip = git(repo_run, "rev-parse", "feat")
    run_dir.flow("f1", branch="integ", dir=posix(repo_run))
    git(repo_run, "branch", "-f", "integ", "feat")
    make(run_dir, kind="wrap-up", block="마무리", status="승인대기", stage="결과승인", judge=READ_JUDGE,
         judge_run=run_judge(final_ci=final_ci(tip[:12])), started_version="1.0.1", rules="2")
    r = run_script("task_set", run_dir, "T001", "--status", "완료", "stage=끝", "--record", "승인|결과 승인|좋습니다 끝내 주세요")
    assert r.returncode == 0, r.output
    text = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    assert "exported_commit: {}".format(tip[:12]) in text, text


# ---------------------------------------------------------------- F: 최종 CI 실패

def test_wrap_up_done_with_failed_ci_needs_risk_acceptance(run_dir):
    run_dir.flow("only", status="검증 끝남", role="feature", round="1")
    make(run_dir, kind="wrap-up", block="마무리", flow="only", status="승인대기", stage="끝", exported_commit="abc1234",
         judge=READ_JUDGE, judge_run=run_judge(failed="- 기준 5: 시험 2개 실패", final_ci=final_ci()),
         started_version="1.0.1", rules="2")
    d = run_dir.task_dir("T001")
    lines = ["echo ok"]
    write(d / "approved-cmds-실행승인.md", "해시: {}\n얼린 시각: 2026-10-15 10:00:00\n\n1. echo ok\n".format(execmod.digest(lines)))
    write(d / "exec.md", "- 2026-10-15 10:01:00 | echo ok | 종료 코드 0 | 지점 실행승인:1\n")
    t = run_dir.tasks()["T001"]
    why = task_set.stage_rule(str(run_dir), t, "승인대기", "완료", ctx(record=REC_OK, old_stage="결과승인"))
    assert why.startswith("최종 CI에 통과 못 한 기준 1개이고 승인 기록에 위험 수용 답이 없음"), why
    p = d / "task.md"
    write(p, p.read_text(encoding="utf-8").replace(
        "## 승인 기록\n", "## 승인 기록\n- 2026-10-15 10:20:00 | 실행승인 | 승인 | 원문: \"그냥 넣어요\"\n"
                         "- 2026-10-15 09:00:00 | 실행승인 | 승인: 위험 수용 | 원문: \"판정 전의 답\"\n", 1))
    t = run_dir.tasks()["T001"]
    assert devflow_lib.risk_accepted(t) is False          # 위험이 없는 승인, 판정 전의 위험 수용은 세지 않는다
    write(p, p.read_text(encoding="utf-8").replace(
        "## 승인 기록\n", "## 승인 기록\n- 2026-10-15 10:21:00 | 승인 | 위험 수용 | 원문: \"알고 넣습니다\"\n", 1))
    t = run_dir.tasks()["T001"]
    assert devflow_lib.risk_accepted(t) is True
    assert task_set.stage_rule(str(run_dir), t, "승인대기", "완료", ctx(record=REC_OK, old_stage="결과승인")) is None


def test_code_cause_ci_failure_is_not_a_writer_retry(run_dir):
    cause = "\n## 최종 CI 실패 원인\n- 원인: 코드(부모 커밋에서도 test_x 실패)\n"
    make(run_dir, kind="wrap-up", block="마무리", status="자체검증", judge=READ_JUDGE,
         judge_run=run_judge(failed="- 기준 5: test_x 실패", final_ci=final_ci(), cause=cause), **V111)
    with pytest.raises(task_set.Reject, match="최종 CI 실패 원인이 코드"):
        task_set.archive_check(str(run_dir), run_dir.tasks()["T001"])
    write(run_dir.task_dir("T001") / "judge-run.md",
          run_judge(failed="- 기준 5: doc_size 실패", final_ci=final_ci(), cause=cause.replace("코드", "문서")))
    assert task_set.archive_check(str(run_dir), run_dir.tasks()["T001"])[0] == 0


def test_step_refuses_insert_line_after_failed_ci_without_risk_acceptance(run_dir, repo_run):
    git(repo_run, "branch", "-f", "integ", "feat")
    tip = git(repo_run, "rev-parse", "feat")
    t = make(run_dir, kind="wrap-up", block="마무리", status="진행", stage="실행",
             judge_run=run_judge(failed="- 기준 5: test_x 실패", final_ci=final_ci(tip)), started_version="1.0.1", rules="2")
    tasks = run_dir.tasks()
    with pytest.raises(execmod.Reject, match="위험 수용 답이 없음"):
        execmod.pre_check(str(run_dir), tasks, t, "실행승인", posix(repo_run), "git merge --ff-only integ", tip=tip)


def test_pr_push_line_sets_exported_commit_to_pushed_tip(run_dir, repo_run, tmp_path):
    # 리뷰 F6 결과 1: push 줄은 병합 줄이 아니라 exported_commit이 비어 완료 관문에서 늘 막혔다
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True)
    git(repo_run, "remote", "add", "origin", posix(remote))
    git(repo_run, "branch", "-f", "integ", "feat")
    tip = git(repo_run, "rev-parse", "integ")
    make(run_dir, kind="wrap-up", block="마무리", status="진행", stage="실행", approval_requested="2026-10-15 10:00:00",
         judge_run=run_judge(final_ci=final_ci(tip)), started_version="1.0.1", rules="2")
    approved(run_dir)
    run_dir.result("T001", CMD_RESULT.format("git push origin integ"))
    rc, msg = execmod.freeze(str(run_dir), "T001", "실행승인")
    assert rc == 0, msg
    r = run_script("exec", run_dir, "T001", "--step", "실행승인:1")
    assert r.returncode == 0, r.output
    assert str(run_dir.tasks()["T001"].get("exported_commit")) == tip[:12]


# ---------------------------------------------------------------- 리뷰 111b

def add_record(run_dir, line, tid="T001"):
    p = run_dir.task_dir(tid) / "task.md"
    write(p, p.read_text(encoding="utf-8").replace("## 승인 기록\n", "## 승인 기록\n" + line + "\n", 1))


def test_main_result_non_ff_merge_on_wrap_up_is_mismatch(run_dir, repo_run):
    # N1(리뷰 실험 A 그대로): --ff-only 병합이 128로 실패한 뒤 메인이 병합 커밋으로 넣고 --main-result를 부르면
    # 예전에는 `이미 들어 있음`이 되어 exported_commit에 검증 commit이 적혔다(main에는 검사하지 않은 병합 커밋)
    write(repo_run / "m.txt", "main only\n")
    git(repo_run, "add", "-A")
    git(repo_run, "commit", "-q", "-m", "main moved")   # main이 갈라져 앞감기 불가
    tip = git(repo_run, "rev-parse", "integ")
    make(run_dir, kind="wrap-up", block="마무리", status="진행", stage="실행", approval_requested="2026-10-15 10:00:00",
         judge_run=run_judge(final_ci=final_ci(tip)), started_version="1.0.1", rules="2")
    approved(run_dir)
    run_dir.result("T001", CMD_RESULT.format("git merge --ff-only integ"))
    assert execmod.freeze(str(run_dir), "T001", "실행승인")[0] == 0
    r = run_script("exec", run_dir, "T001", "--step", "실행승인:1")
    assert r.returncode == 3, r.output
    assert "| 브랜치 판정 | 실행승인:1 | 실패 |" in (run_dir.task_dir("T001") / "exec.md").read_text(encoding="utf-8")
    add_record(run_dir, "- 2099-01-01 00:00:00 | 되물음 | 다른 방법 | 원문: \"병합 커밋으로 넣어 주세요\"")
    git(repo_run, "merge", "-q", "--no-edit", "integ")   # 메인이 앞감기가 아닌 병합으로 넣음
    r = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0, 출력 Merge made")
    assert r.returncode == 0, r.output
    text = (run_dir.task_dir("T001") / "exec.md").read_text(encoding="utf-8")
    assert text.splitlines()[-1].split(" | ")[3] == "불일치", text
    t = run_dir.tasks()["T001"]
    assert not str(t.get("exported_commit") or "").strip()
    ok, lines = execmod.verify(str(run_dir), t)
    assert ok is False and "브랜치 판정 불일치" in "; ".join(lines), lines


def test_main_result_ignores_check_ack_lines(run_dir, repo_run):
    # N9: `점검 확인` 줄은 사용자 답으로 세지 않는다
    git(repo_run, "checkout", "-q", "integ")
    make(run_dir, kind="merge", block="구현", status="진행", stage="실행", flow="f1",
         started_version="시험 판본", rules="2")
    lines = ["git merge --ff-only feat"]
    write(run_dir.task_dir("T001") / "approved-cmds-실행승인.md",
          "해시: {}\n얼린 시각: 2026-10-15 10:00:00\n\n1. {}\n".format(execmod.digest(lines), lines[0]))
    write(run_dir.task_dir("T001") / "exec.md",
          "- 2026-10-15 10:01:00 | git merge --ff-only feat | 종료 코드 1 | 로그 x | 지점 실행승인:1 | 폴더 {}\n".format(
              posix(repo_run)))
    add_record(run_dir, "- 2026-10-15 10:05:00 | 점검 확인 | R2 | 원문: \"확인\"")
    r = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0")
    assert r.returncode == 3 and "사용자 답이 없음" in r.output, r.output


def test_risk_accepted_needs_decision_starting_with_risk_acceptance(run_dir):
    # N4: `위험 수용 안 함`은 승인으로 세지 않는다
    make(run_dir, kind="wrap-up", block="마무리", status="승인대기", judge_run=run_judge(failed="- 기준 5: 실패"),
         started_version="1.0.1", rules="2")
    add_record(run_dir, "- 2026-10-15 10:30:00 | 승인 | 위험 수용 안 함, 고쳐 주세요 | 원문: \"고쳐요\"")
    assert devflow_lib.risk_accepted(run_dir.tasks()["T001"]) is False
    add_record(run_dir, "- 2026-10-15 10:31:00 | 승인 | 위험 회피 | 원문: \"다른 길\"")
    assert devflow_lib.risk_accepted(run_dir.tasks()["T001"]) is False
    add_record(run_dir, "- 2026-10-15 10:32:00 | 승인 | 위험 수용 | 원문: \"알고 넣어요\"")
    assert devflow_lib.risk_accepted(run_dir.tasks()["T001"]) is True


def deploy_put(run_dir, repo, code="0", commit=None):
    """넣기승인 지점의 배포 실행(1.1.1). 배포 폴더 = 통합 폴더(integ 브랜치), 배포 기록 커밋 = integ 끝."""
    write(run_dir.path / "recon.md", "# 정찰\n\n## 문서를 읽는 검사\n- `npm run check:static`\n")
    run_dir.flow("fi", branch="integ", dir=posix(repo.parent / "integ-wt"))
    make(run_dir, kind="deploy-exec", block="배포", status="진행", stage="넣기", judge=READ_JUDGE, flow="fi",
         judge_run=run_judge(), approval_requested="2026-10-15 10:00:00", **V111)
    tip = git(repo, "rev-parse", "integ")
    body = "## 넣기 전 문서 검사\n- 검증 commit: {}\n- 명령: npm run check:static\n".format(commit or tip)
    if code is not None:
        body += "- 종료 코드: {}\n".format(code)
    write(run_dir.task_dir("T001") / "main-run.md", body + "- 로그: logs/doc.txt\n")
    approved(run_dir)
    run_dir.result("T001", CMD_RESULT.format("git merge --no-edit integ"))
    return tip


def test_doc_check_needs_exit_code_and_failed_check_needs_risk_acceptance(run_dir, repo_run):
    # N2: 넣기 전 문서 검사의 종료 코드를 가드와 얼림이 본다
    git(repo_run, "worktree", "add", "-q", str(repo_run.parent / "integ-wt"), "integ")
    tip = deploy_put(run_dir, repo_run, code=None)
    t = run_dir.tasks()["T001"]
    why = check(run_dir, dict(t, stage="넣기승인"), "진행", "승인대기")
    assert why and "종료 코드 없음" in why, why
    deploy_put(run_dir, repo_run, code="1")
    t = run_dir.tasks()["T001"]
    assert check(run_dir, dict(t, stage="넣기승인"), "진행", "승인대기") is None   # 실패는 묻는다(화면 맨 위)
    rc, msg = execmod.freeze(str(run_dir), "T001", "넣기승인")
    assert rc == 3 and "종료 코드가 1" in msg, msg
    add_record(run_dir, "- 2099-01-01 00:00:00 | 승인 | 위험 수용 | 원문: \"알고 넣습니다\"")
    rc, msg = execmod.freeze(str(run_dir), "T001", "넣기승인")
    assert rc == 0, msg
    assert execmod.frozen_tips(run_dir.tasks()["T001"], "넣기승인") == {1: tip}


def test_put_lines_with_commit_are_a_problem():
    # N5(나): 배포 기록은 메인이 넣기 승인 전에 커밋한다
    t = {"kind": "deploy-exec"}
    assert execmod.line_problems(t, "넣기승인", "git add docs/deploy.md", "")
    assert execmod.line_problems(t, "넣기승인", "git commit -m \"기록\" && git merge integ", "")
    assert execmod.line_problems(t, "넣기승인", "git merge --no-edit integ", "") == []
    assert execmod.line_problems(t, "실행승인", "git commit -m x", "") == []


def test_user_inserted_wrap_up_with_merge_commit_leaves_exported_commit_empty(run_dir, repo_run):
    # N6: 사용자가 병합 커밋으로 직접 넣었으면 받는 끝은 검증한 commit이 아니다
    write(repo_run / "m.txt", "main only\n")
    git(repo_run, "add", "-A")
    git(repo_run, "commit", "-q", "-m", "main moved")
    git(repo_run, "merge", "-q", "--no-edit", "integ")
    tip = git(repo_run, "rev-parse", "integ")
    make(run_dir, kind="wrap-up", block="마무리", status="승인대기", stage="결과승인", judge=READ_JUDGE,
         judge_run=run_judge(final_ci=final_ci(tip[:12])), started_version="1.0.1", rules="2")
    assert execmod.target_tip(str(run_dir), run_dir.tasks()["T001"]) == ""
    r = run_script("task_set", run_dir, "T001", "--status", "완료", "stage=끝", "--record", "승인|결과 승인|마쳐 주세요 지금")
    assert r.returncode == 3 and "최종 배포 후보 commit이 유효한 Git SHA가 아님(없음)" in r.output, r.output


def test_refreeze_old_frozen_file_without_tips_is_same(run_dir, repo_run):
    # N8: 1.1.1 전에 넣는 끝 없이 얼린 합치기를 같은 줄로 다시 얼리면 같음으로 본다
    git(repo_run, "checkout", "-q", "integ")
    make(run_dir, kind="merge", block="구현", status="진행", stage="실행", flow="f1",
         approval_requested="2026-10-15 10:00:00", started_version="시험 판본", rules="2")
    approved(run_dir)
    run_dir.result("T001", CMD_RESULT.format("git merge --no-edit feat"))
    lines = ["git merge --no-edit feat"]
    write(run_dir.task_dir("T001") / "approved-cmds-실행승인.md",
          "해시: {}\n얼린 시각: 2026-10-15 10:40:00\n\n1. {}\n".format(execmod.digest(lines), lines[0]))
    rc, msg = execmod.freeze(str(run_dir), "T001", "실행승인")
    assert rc == 0 and "옛 얼림" in msg, msg


def test_wrap_up_end_to_end_v111_cli(run_dir, tmp_path):
    # N10: 1.1.1 마무리 하나를 명령행으로 끝까지. 자체검증 → 읽기 판정 → 문서 커밋 → 실행 판정 → 실행승인 → 얼림 →
    # --step → --verify → 결과승인 → 완료
    repo, wt = tmp_path / "proj", tmp_path / "proj-integ"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo / "README.md", "앱\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "branch", "integ")
    git(repo, "worktree", "add", "-q", str(wt), "integ")
    write(wt / "app.py", "x = 1\n")
    git(wt, "add", "-A")
    git(wt, "commit", "-q", "-m", "기능")
    set_meta(run_dir, project=posix(repo), integration_dir=posix(wt), integration_branch="integ", base_branch="main")
    make(run_dir, kind="wrap-up", block="마무리", status="자체검증", judge=READ_JUDGE, **V111)
    run_dir.result("T001", CMD_RESULT.format("git merge --ff-only integ"))
    base = git(wt, "rev-parse", "HEAD")
    write(wt / "README.md", "앱\n\n사용법 고침\n")                              # 작성자가 고친 문서
    git(wt, "add", "README.md")
    git(wt, "commit", "-q", "-m", "docs: 사용법")                               # 2. 메인이 문서 커밋
    head = git(wt, "rev-parse", "HEAD")
    assert git(wt, "status", "--porcelain") == ""

    def ts(*args):
        r = run_script("task_set", run_dir, "T001", *args)
        assert r.returncode == 0, (args, r.output)
        return r

    ts("external_progress=문서 커밋 {} 앞 끝 {}".format(head[:12], base[:12]))
    # 3 전에는 실행승인으로 갈 수 없다(판정 파일 없음)
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기", "stage=실행승인")
    assert r.returncode == 3 and "judge-run.md 없음" in r.output, r.output
    write(run_dir.task_dir("T001") / "judge-run.md", run_judge(final_ci=final_ci(head)))   # 3. 최종 CI
    ts("--status", "승인대기", "stage=실행승인", "external_progress=")                    # 4
    ts("--status", "진행", "stage=실행", "--record", "승인|실행 승인|이대로 내보내 주세요")
    assert execmod.frozen_tips(run_dir.tasks()["T001"], "실행승인") == {1: head}
    r = run_script("exec", run_dir, "T001", "--step", "실행승인:1")                       # 6
    assert r.returncode == 0, r.output
    r = run_script("exec", run_dir, "T001", "--verify")                                    # 7
    assert r.returncode == 0, r.output
    ts("--status", "승인대기", "stage=결과승인")                                           # 8
    ts("--status", "완료", "stage=끝", "--record", "승인|결과 승인|결과를 확인했습니다 끝")
    t = run_dir.tasks()["T001"]
    assert (t.get("status"), str(t.get("exported_commit"))) == ("완료", head[:12])
    assert git(repo, "rev-parse", "main") == head
