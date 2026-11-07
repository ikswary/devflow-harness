"""A13 R-C11: 넣기 뒤에 문서가 바뀌었을 때 `project-docs.md` 4절의 차례대로 돌면 새 끝이 나간다. 실제 전이와 얼림을 돌린다."""
import time
from datetime import datetime

import devflow_lib
import project_docs
from conftest import run_script, write
from test_owned_commands import cells, final_ci, git, merge_run, run_judge_text, INTEG, NEW  # noqa: F401


def waiting(run_dir, integ):
    """넣기가 있는 마무리가 실행 승인을 묻는 상태. 코드 폴더는 통합 폴더다."""
    repo = integ.parent / "proj"
    doc = devflow_lib.Doc(str(run_dir.path / "run.md"))
    doc.set(project_docs.BASE_KEY, git(repo, "rev-parse", "HEAD"))
    doc.set("integration_dir", str(integ))
    doc.save()
    (run_dir.path / "base").mkdir(exist_ok=True)
    write(run_dir.path / "spec" / "brief.md", "# 기획\n\n## 정책\n첫 판\n")
    project_docs.stamp_file(str(run_dir.path), "spec\\brief.md", "T001")
    run_dir.task("T002", "마무리", kind="wrap-up", block="마무리", status="자체검증", stage="실행승인", **NEW)
    run_dir.result("T002", cells(decide="- 넣습니다\n```cmd\ngit merge --ff-only {}\n```".format(INTEG)))
    return commit_and_ask(run_dir, integ, "처음")


def commit_and_ask(run_dir, integ, message):
    assert run_script("project_docs", run_dir, "T002", "--insert", integ).returncode == 0
    git(integ, "add", "-A")
    git(integ, "commit", "-q", "-m", "문서 " + message)
    sha = git(integ, "rev-parse", "HEAD")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T002", "판정자: rjudge-T002 {}\n\n## 통과 못 한 기준\n- 없음\n".format(now))
    write(run_dir.task_dir("T002") / "judge-run.md", run_judge_text("T002", tail=final_ci(sha)))
    time.sleep(1.1)
    assert run_script("visual", run_dir, "T002", "--wrap-review").returncode == 0
    asked = run_script("task_set", run_dir, "T002", "--status", "승인대기", "stage=실행승인", "external_progress=")
    assert asked.returncode == 0, asked.output
    return sha


def again(run_dir, integ):
    write(run_dir.path / "spec" / "brief.md", "# 기획\n\n## 정책\n둘째 판\n")
    project_docs.stamp_file(str(run_dir.path), "spec\\brief.md", "T003")
    back = run_script("task_set", run_dir, "T002", "--status", "자체검증", "--archive-judge", "--unlisted", "다시 넣기")
    assert back.returncode == 0, back.output
    return commit_and_ask(run_dir, integ, "다시")


def test_screen_says_not_inserted_then_the_loop_clears_it(merge_run):
    run_dir, integ = merge_run
    waiting(run_dir, integ)
    write(run_dir.path / "spec" / "brief.md", "# 기획\n\n## 정책\n둘째 판\n")
    assert project_docs.NOT_YET in "\n".join(project_docs.review_lines(str(run_dir.path), run_dir.tasks()["T002"])[0])
    again(run_dir, integ)
    assert project_docs.NOT_YET not in "\n".join(project_docs.review_lines(str(run_dir.path), run_dir.tasks()["T002"])[0])


def test_loop_before_the_answer_freezes_the_new_tip(merge_run):
    run_dir, integ = merge_run
    repo = integ.parent / "proj"
    waiting(run_dir, integ)
    new = again(run_dir, integ)
    answer = run_script("task_set", run_dir, "T002", "--status", "진행", "stage=실행", "--record", "승인|실행 승인|넣으세요")
    assert answer.returncode == 0, answer.output
    step = run_script("exec", run_dir, "T002", "--step", "실행승인:1")
    assert step.returncode == 0, step.output
    assert git(repo, "rev-parse", "HEAD") == new


def test_loop_after_the_answer_needs_a_new_answer_and_refreeze(merge_run):
    run_dir, integ = merge_run
    repo = integ.parent / "proj"
    old = waiting(run_dir, integ)
    answer = run_script("task_set", run_dir, "T002", "--status", "진행", "stage=실행", "--record", "승인|실행 승인|넣으세요")
    assert answer.returncode == 0, answer.output
    new = again(run_dir, integ)
    answer = run_script("task_set", run_dir, "T002", "--status", "진행", "stage=실행", "--record", "승인|실행 승인|다시 넣으세요")
    assert answer.returncode == 0, answer.output
    run_script("exec", run_dir, "T002", "--freeze", "--point", "실행승인", "--refreeze")
    step = run_script("exec", run_dir, "T002", "--step", "실행승인:1")
    assert step.returncode == 0, step.output
    assert git(repo, "rev-parse", "HEAD") == new != old


def test_conflict_answer_can_be_recorded_while_running(merge_run):
    """CI 앞에서 묻고 답을 적는다. 상태는 그대로이고 명령을 얼리지 않는다."""
    run_dir, integ = merge_run
    write(run_dir.path / "spec" / "brief.md", "# 기획\n")
    run_dir.task("T002", "마무리", kind="wrap-up", block="마무리", status="진행", stage="실행승인", **NEW)
    run_dir.result("T002", cells(decide="- 넣습니다\n```cmd\ngit merge --ff-only {}\n```".format(INTEG)))
    out = run_script("task_set", run_dir, "T002", "--record", "같은 절 두 곳|이번 실행|이번 실행 판으로 하세요")
    assert out.returncode == 0, out.output
    t = run_dir.tasks()["T002"]
    assert t["status"] == "진행" and not devflow_lib.approval_line(devflow_lib.record_lines(t)[-1])
