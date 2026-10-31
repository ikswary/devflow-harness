"""명령 줄 꼴(devflow_lib.cmd_line_problems, exec.line_problems·screen_lines·pre_check, exec.py --main-result).

2026-10-31 T043: `git -C D:\\workspace\\devflow-harness merge …`가 bash에서 `D:workspacedevflow-harness`가 되어 128.
1.1.1 리뷰(_workspace/review-111.md 질문 4): 폴더 대조는 실행 전 확인이 폴더를 보는 줄에만(운영 브랜치 옮기기
`[유지 뒤] git -C {원래 폴더} update-ref`는 통과), 경로는 명령의 실행 폴더 기준, `/d/…` 꼴, 큰따옴표 안 이스케이프,
화면의 실행 폴더는 exec.py와 같은 함수, 「되돌리기」 줄도 화면에서 검사.
"""
import os
import subprocess

import pytest

import devflow_lib
import exec as execmod
from conftest import run_script, write

GIT_ID = ["-c", "user.name=dryrun", "-c", "user.email=dryrun@example.invalid", "-c", "commit.gpgsign=false"]
NEW = {"started_version": "시험 판본", "rules": "2"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + GIT_ID + list(args), check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def posix(path):
    return str(path).replace(os.sep, "/")


def gitbash(path):
    """`C:/x/y` → `/c/x/y`(Git Bash 꼴)."""
    p = posix(path)
    return "/{}{}".format(p[0].lower(), p[2:]) if len(p) > 1 and p[1] == ":" else p


def set_meta(run_dir, **kv):
    p = run_dir.path / "run.md"
    text = p.read_text(encoding="utf-8")
    add = "".join("{}: {}\n".format(k, v) for k, v in kv.items())
    write(p, text.replace("status: 진행\n", "status: 진행\n" + add, 1))


def result_with_cmd(*lines, rollback=None):
    fence = "\n".join(["- 이 명령을 실행합니다", "  ```cmd"] + ["  " + x for x in lines] + ["  ```"])
    text = ("# 결과\n\n## 승인 화면\n### 정해 주실 것\n{}\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n- 없음\n"
            "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 명령 {}\n\n## 스스로 줄임\n없음\n").format(
        fence, len(lines))
    if rollback:
        text += "\n## 되돌리기\n```cmd\n{}\n```\n".format("\n".join(rollback))
    return text


def freeze_lines(run_dir, tid, point, lines):
    write(run_dir.task_dir(tid) / "approved-cmds-{}.md".format(point),
          "# 얼린 명령\n\n해시: {}\n얼린 시각: 2026-10-15 10:00:00\n\n{}\n".format(
              execmod.digest(lines), "\n".join("{}. {}".format(i, x) for i, x in enumerate(lines, 1))))


# ---------------------------------------------------------------- 백슬래시

@pytest.mark.parametrize("line", [
    r"git -C D:\workspace\devflow-harness merge --ff-only harness/v110/integration",
    r"git merge --ff-only harness\v110\integration",
    r"[유지 뒤] copy D:\a D:\b",
])
def test_backslash_outside_quotes_is_a_problem(line):
    assert any("백슬래시" in p for p in devflow_lib.cmd_line_problems(line))


@pytest.mark.parametrize("line", [
    "git merge --ff-only harness/v110/integration",
    r'git log "D:\workspace\a"',
    r"echo 'a\b'",
    r"[사용자 실행] git -C D:\workspace\x push",
    r'git commit -m "say \"hi\""',          # 큰따옴표 안의 \" 는 이스케이프(따옴표를 닫지 않는다)
    r'git commit -m "a \\ b \$x \`y\`"',
])
def test_no_problem_for_plain_quoted_or_user_lines(line):
    assert devflow_lib.cmd_line_problems(line) == []


def test_escaped_quote_does_not_hide_a_later_backslash():
    # `\"`를 따옴표 닫기로 잘못 읽으면 뒤의 따옴표 밖 백슬래시를 따옴표 안으로 본다
    assert any("백슬래시" in p for p in devflow_lib.cmd_line_problems(r'git commit -m "a \"b\"" D:\x'))


def test_backslash_not_checked_without_bash():
    # bash가 없으면 exec.py는 cmd.exe로 돌린다: 백슬래시 규칙이 맞지 않아 보지 않는다
    assert devflow_lib.cmd_line_problems(r"git merge a\b", bash=False) == []


# ---------------------------------------------------------------- 폴더 대조

def test_git_c_to_other_folder_is_a_problem(tmp_path):
    here, other = tmp_path / "here", tmp_path / "other"
    here.mkdir()
    other.mkdir()
    line = "git -C {} merge --ff-only b".format(posix(other))
    assert any("git -C" in p for p in devflow_lib.cmd_line_problems(line, str(here)))


def test_git_c_to_same_folder_is_allowed(tmp_path):
    line = "git -C {} merge --ff-only b".format(posix(tmp_path))
    assert devflow_lib.cmd_line_problems(line, str(tmp_path)) == []
    # 실행 폴더를 모르면(screen이 못 구함) -C 대조는 하지 않는다
    assert devflow_lib.cmd_line_problems("git -C {} status".format(posix(tmp_path / "x"))) == []


@pytest.mark.parametrize("path", [".", "./", "'.'"])
def test_relative_git_c_resolves_against_command_cwd(tmp_path, path):
    # 파이썬 프로세스의 cwd가 아니라 명령의 실행 폴더 기준으로 푼다
    assert devflow_lib.cmd_line_problems("git -C {} merge --ff-only b".format(path), str(tmp_path)) == []
    assert devflow_lib.cmd_line_problems("git -C .. merge --ff-only b", str(tmp_path))


def test_git_bash_drive_path_is_same_folder(tmp_path):
    line = "git -C {} merge --ff-only b".format(gitbash(tmp_path))
    assert devflow_lib.cmd_line_problems(line, str(tmp_path)) == [], line


def test_variable_path_is_not_compared(tmp_path):
    assert devflow_lib.cmd_line_problems('git -C "$PWD" merge --ff-only b', str(tmp_path)) == []


def test_merge_line_prefixes_cd_and_dash_c_are_caught(tmp_path):
    other = posix(tmp_path / "other")
    assert devflow_lib.cmd_line_problems("cd {} && git merge x".format(other), str(tmp_path), merge=True)
    assert devflow_lib.cmd_line_problems("git -c core.x=y -C {} merge x".format(other), str(tmp_path), merge=True)
    # 같은 폴더로 cd하는 병합 줄은 통과, 병합 줄이 아니면 cd를 보지 않는다(배포 명령의 하위 폴더 cd)
    assert devflow_lib.cmd_line_problems("cd {} && git merge x".format(posix(tmp_path)), str(tmp_path), merge=True) == []
    assert devflow_lib.cmd_line_problems("cd frontend && npm run deploy", str(tmp_path)) == []


def test_prod_branch_after_keep_lines_pass(tmp_path):
    # references/kinds/deploy-plan/prod-branch.md:7: 운영 브랜치 옮기기는 배포 폴더에서 원래 폴더를 -C로 가리킨다
    deploy_dir, project = posix(tmp_path / "proj-wt" / "flow-a"), posix(tmp_path / "proj")
    t = {"kind": "deploy-exec"}
    for line in ("[유지 뒤] git -C {} update-ref refs/heads/prod {} {}".format(project, "a" * 40, "b" * 40),
                 "[유지 뒤] git -C {} push origin prod".format(project)):
        assert execmod.line_problems(t, "실행승인", line, deploy_dir) == [], line
    # update-ref·push 단독 줄은 [유지 뒤] 없이도 폴더를 대조하지 않는다(실행 전 확인이 폴더를 보지 않음)
    assert execmod.line_problems(t, "실행승인", "git -C {} push origin prod".format(project), deploy_dir) == []
    # 작업 트리를 쓰는 줄은 대조한다
    assert execmod.line_problems(t, "실행승인", "git -C {} merge x".format(project), deploy_dir)


def test_wrap_up_merge_line_needs_ff_only(tmp_path):
    t = {"kind": "wrap-up"}
    cwd = posix(tmp_path)
    assert any("--ff-only" in p for p in execmod.line_problems(t, "실행승인", "git merge integ", cwd))
    assert execmod.line_problems(t, "실행승인", "git merge --ff-only integ", cwd) == []
    assert execmod.line_problems({"kind": "merge"}, "실행승인", "git merge --no-edit feat", cwd) == []


# ---------------------------------------------------------------- 화면과 --step

def test_screen_warns_with_child_run_folder_and_rollback_lines(run_dir, tmp_path):
    # 배포 계획의 줄은 자식 배포 실행의 실행승인 폴더(흐름 폴더)에서 돈다. 원래 폴더를 cwd로 잡으면 놓친다
    project, flow_dir = tmp_path / "proj", tmp_path / "proj-wt" / "flow-a"
    flow_dir.mkdir(parents=True)
    project.mkdir()
    set_meta(run_dir, project=posix(project))
    run_dir.flow("flow-a", dir=posix(flow_dir), branch="flow-a")
    run_dir.task("T001", "배포 계획", kind="deploy-plan", block="배포", status="승인대기", flow="flow-a")
    run_dir.judge("T001", "판정자: rjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n")
    run_dir.result("T001", result_with_cmd(
        "git -C {} merge x".format(posix(project)),
        "[유지 뒤] git -C {} update-ref refs/heads/prod {} {}".format(posix(project), "a" * 40, "b" * 40),
        rollback=[r"git revert D:\x"]))
    tasks = run_dir.tasks()
    bad = [line for line, probs in execmod.screen_lines(str(run_dir), tasks, tasks["T001"]) if probs]
    assert bad == ["git -C {} merge x".format(posix(project)), r"git revert D:\x"]
    r = run_script("screen", run_dir, "T001")
    assert "! 명령 줄 꼴" in r.output, r.output
    assert "[유지 뒤]" not in r.output.split("! 명령 줄 꼴")[1], r.output


def test_step_rejects_bad_line_without_touching_exec_md_or_progress(run_dir, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    set_meta(run_dir, project=posix(project))
    run_dir.task("T001", "설계", status="완료")
    freeze_lines(run_dir, "T001", "실행승인", ["git -C .. status"])
    r = run_script("exec", run_dir, "T001", "--step", "실행승인:1")
    assert r.returncode == 3, r.output
    assert "명령 줄 꼴" in r.output and "--refreeze" in r.output, r.output
    assert not (run_dir.task_dir("T001") / "exec.md").exists()
    assert "external_progress" not in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")


def test_recovery_for_deploy_exec_points_to_new_plan(run_dir):
    run_dir.task("T001", "배포 계획", kind="deploy-plan", block="배포", status="완료")
    run_dir.task("T002", "배포 실행", kind="deploy-exec", block="배포", status="진행", parent="T001")
    tasks = run_dir.tasks()
    assert "새 배포 계획 task" in execmod.recovery(tasks, tasks["T002"], "실행승인")
    assert "--refreeze" in execmod.recovery(tasks, tasks["T002"], "넣기승인")


# ---------------------------------------------------------------- --main-result

@pytest.fixture
def failed_merge(run_dir, tmp_path):
    """흐름 브랜치 feat를 통합 브랜치 integ에 넣는 합치기. 실행승인:1이 종료 코드 128로 실패한 기록이 있다."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "integ")
    write(repo / "a.txt", "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "branch", "feat")
    git(repo, "checkout", "-q", "feat")
    write(repo / "b.txt", "b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat")
    git(repo, "checkout", "-q", "integ")
    set_meta(run_dir, project=posix(repo), integration_dir=posix(repo), integration_branch="integ")
    run_dir.flow("f1", branch="feat", dir=posix(repo))
    run_dir.task("T001", "합치기", kind="merge", block="구현", status="진행", stage="실행", flow="f1", **NEW)
    freeze_lines(run_dir, "T001", "실행승인", ["git merge --ff-only feat"])
    write(run_dir.task_dir("T001") / "exec.md",
          "- 2026-10-15 10:01:00 | git merge --ff-only feat | 종료 코드 128 | 로그 x | 지점 실행승인:1 | 폴더 {}\n".format(
              posix(repo)))
    return repo


def add_answer(run_dir, when="2026-10-15 10:05:00", text="직접 넣어 주세요"):
    p = run_dir.task_dir("T001") / "task.md"
    s = p.read_text(encoding="utf-8")
    write(p, s.replace("## 승인 기록\n", "## 승인 기록\n- {} | 되물음 | 다른 방법 | 원문: \"{}\"\n".format(when, text), 1))


def test_main_result_needs_answer_after_failure(run_dir, failed_merge):
    r = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0, 출력 Fast-forward")
    assert r.returncode == 3 and "사용자 답이 없음" in r.output, r.output
    add_answer(run_dir, when="2026-10-15 09:00:00")   # 실패 전의 답은 세지 않는다
    r = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0, 출력 Fast-forward")
    assert r.returncode == 3 and "사용자 답이 없음" in r.output, r.output


def test_main_result_records_like_step_and_judges_merge(run_dir, failed_merge):
    add_answer(run_dir)
    git(failed_merge, "merge", "-q", "--ff-only", "feat")   # 메인이 다른 방법으로 넣음
    tip = git(failed_merge, "rev-parse", "HEAD")
    r = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0, 출력 Fast-forward")
    assert r.returncode == 0, r.output
    text = (run_dir.task_dir("T001") / "exec.md").read_text(encoding="utf-8")
    assert "| 종료 코드 0 | 메인 실행: 종료 코드 0, 출력 Fast-forward | 지점 실행승인:1 |" in text
    assert "| 브랜치 판정 | 실행승인:1 | 앞감기 |" in text
    t = run_dir.tasks()["T001"]
    assert str(t.get("commit")) == tip[:12]
    assert execmod.verify(str(run_dir), t)[0] is True
    # 한 번만: 통과한 줄에는 다시 받지 않는다
    r = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0")
    assert r.returncode == 3 and "실패가 아님" in r.output, r.output


def test_main_result_rejects_line_that_did_not_fail(run_dir, failed_merge):
    write(run_dir.task_dir("T001") / "exec.md", "")
    add_answer(run_dir)
    r = run_script("exec", run_dir, "T001", "--main-result", "실행승인:1", "종료 코드 0")
    assert r.returncode == 3 and "실패가 아님" in r.output, r.output
