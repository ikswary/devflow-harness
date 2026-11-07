"""치워 두기(설계 8.2절): `task_set.py --park`·`--unpark`·`--park-drop`, 재현 패치 `repro_patch`, 재개와 폴더 대기.

- git 동작은 대역 없이 임시 폴더의 실제 git 저장소로 본다. 끊김은 그 지점의 함수가 `KeyboardInterrupt`를 내게 해서 만든다
  (`except Exception`에 잡히지 않고 프로세스가 죽는 것과 같이 그 뒤의 쓰기가 돌지 않는다).
- 끊김 시험마다 단언하는 것은 둘이다: 끊긴 자리에서 변경이 사라지지 않았고, 다시 부르면 이어서 끝난다.
"""
import os
import shutil
import subprocess

import pytest
from conftest import run_script, write

import board
import collect
import devflow_lib
import kinds
import retry_diff
import task_set

if shutil.which("git") is None:
    # 전제가 없으면 시작할 때 이유를 말하고 실패한다(test-rules ⑥)
    pytest.exit("git이 없음: 치워 두기 시험은 실제 git 저장소를 쓴다 — git을 설치하고 다시 돌린다", returncode=4)

V120 = "1.2.0-dev.1"
PASS = "판정자: {}-{} 2026-11-05 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
FAIL = "판정자: {}-{} 2026-11-05 10:00:00\n\n## 통과 못 한 기준\n- 기준 1: 재현 테스트가 실패하지 않음\n"
RUN_BODY = ("\n## 검사 입력과 독립 근거\n- 제품, 시험, 설정, lock, 명령, 환경, 판정자, 시각, 종료 코드, 로그\n"
            "\n## 남은 검사와 자원 대기\n- 없음\n")
NEW_NAME = "시험/새 재현 시험.txt"
BINARY = bytes(reversed(range(256))) + b"\0\1"


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return out.stdout


def status(repo):
    return git(repo, "status", "--porcelain", "-uall")


@pytest.fixture(name="repo")
def _repo(tmp_path):
    repo = tmp_path / "code"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "core.autocrlf", "false")
    write(repo / "a.txt", "하나\n둘\n셋\n")
    write(repo / "gone.txt", "지울 파일\n")
    (repo / "bin.dat").write_bytes(bytes(range(256)))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def dirty(repo):
    """수정, 삭제, 스테이징한 새 파일, 스테이징 안 한 한글 경로 새 파일, 바이너리 수정."""
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n")
    (repo / "gone.txt").unlink()
    write(repo / "staged.txt", "스테이징한 새 파일\n")
    git(repo, "add", "staged.txt")
    write(repo / NEW_NAME, "새 파일\n")
    (repo / "bin.dat").write_bytes(BINARY)


def assert_dirty(repo):
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(고침)\n셋\n"
    assert not (repo / "gone.txt").exists()
    assert (repo / "staged.txt").read_text(encoding="utf-8") == "스테이징한 새 파일\n"
    assert (repo / NEW_NAME).read_text(encoding="utf-8") == "새 파일\n"
    assert (repo / "bin.dat").read_bytes() == BINARY


def assert_clean(repo):
    assert status(repo) == ""
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘\n셋\n"
    assert (repo / "gone.txt").is_file()
    assert not (repo / NEW_NAME).exists() and not (repo / "staged.txt").exists()
    assert (repo / "bin.dat").read_bytes() == bytes(range(256))


def held_task(run_dir, repo, tid="T001", **meta):
    run_dir.flow("s1", dir=str(repo), status="진행")
    head = dict(kind="implementation", block="구현", status="보류", flow="s1", started_version=V120, rules="2")
    head.update(meta)
    run_dir.task(tid, "보류된 구현", **head)


def cause_task(run_dir, repo, tid="T001", status="자체검증", judge_run=PASS, **meta):
    run_dir.flow("s1", dir=str(repo), status="진행")
    run_dir.task(tid, "원인 분석", kind="root-cause", block="원인 분석", status=status, flow="s1",
                 started_version=V120, rules="2", **meta)
    run_dir.result(tid, "# 결과\n")
    run_dir.judge(tid, PASS.format("rjudge", tid))
    write(run_dir.task_dir(tid) / "judge-run.md", judge_run.format("xjudge", tid) + RUN_BODY)


def child_task(run_dir, tid="T002", parent="T001", kind="implementation", status="대기", **meta):
    run_dir.task(tid, "수정 구현", kind=kind, block="구현", status=status, flow="s1", parent=parent, **meta)


def meta(run_dir, tid):
    return run_dir.tasks()[tid]


def mark_of(run_dir, tid, key):
    return str(meta(run_dir, tid).get(key, "") or "").strip()


def park(run_dir, tid="T001"):
    r = run_script("task_set", run_dir, tid, "--park")
    assert r.returncode == 0, r.output
    return r


def call(run_dir, *args):
    return task_set.main(["task_set.py", str(run_dir)] + list(args))


def die(*_args, **_kwargs):
    raise KeyboardInterrupt("끊김")


def die_on_save(monkeypatch, nth):
    """Doc.save의 n번째 부름에서 쓰기 전에 끊는다."""
    real, seen = devflow_lib.Doc.save, []

    def save(self):
        seen.append(1)
        if len(seen) == nth:
            die()
        real(self)
    monkeypatch.setattr(devflow_lib.Doc, "save", save)


# ---------------------------------------------------------------- 치우기: 무엇을 담고 무엇을 되돌리는가

def test_park_captures_new_files_and_reverts_only_listed_files(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / ".gitignore", "*.log\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")
    dirty(repo)
    write(repo / "keep.log", "무시되는 파일\n")
    head = git(repo, "rev-parse", "HEAD").strip()

    r = park(run_dir)

    assert_clean(repo)
    assert (repo / "keep.log").read_text(encoding="utf-8") == "무시되는 파일\n"
    patch, recorded_head, digest = mark_of(run_dir, "T001", "parked").split(" ")
    assert patch == "tasks/T001/parked.patch"   # 실행 폴더 기준 상대 경로
    assert recorded_head == head and len(digest) == 16
    # 파일 목록은 `git status -z`로 읽는다. 한글 경로가 이스케이프됐다면 이 해시가 맞지 않는다
    assert digest == retry_diff.list_digest(["a.txt", "bin.dat", "gone.txt", "staged.txt", NEW_NAME])
    assert b"GIT binary patch" in (run_dir.path / patch).read_bytes()
    assert mark_of(run_dir, "T001", "parked_pending") == ""
    assert "치움" in (run_dir.path / "journal.md").read_text(encoding="utf-8")
    assert "T001" in r.stdout


def test_unpark_restores_everything_and_clears_the_mark(run_dir, repo):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)

    r = run_script("task_set", run_dir, "T001", "--unpark")

    assert r.returncode == 0, r.output
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked") == ""
    assert (run_dir.path / "tasks/T001/parked.patch").is_file()   # 패치는 task 폴더에 남는다


def test_park_and_unpark_keep_crlf_files_under_autocrlf(run_dir, repo):
    git(repo, "config", "core.autocrlf", "true")
    held_task(run_dir, repo)
    (repo / "crlf.txt").write_bytes(b"\xed\x95\x98\xeb\x82\x98\r\n\xeb\x91\x98\r\n")
    park(run_dir)
    assert status(repo) == "" and not (repo / "crlf.txt").exists()
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert (repo / "crlf.txt").read_bytes() == b"\xed\x95\x98\xeb\x82\x98\r\n\xeb\x91\x98\r\n"
    assert mark_of(run_dir, "T001", "parked") == ""


def test_park_with_nothing_to_park_leaves_no_mark(run_dir, repo):
    held_task(run_dir, repo)
    r = park(run_dir)
    assert "치울 변경 없음" in r.stdout
    assert mark_of(run_dir, "T001", "parked") == ""
    assert not (run_dir.path / "tasks/T001/parked.patch").exists()


def test_second_park_does_not_overwrite_an_earlier_patch(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "첫 변경\n")
    park(run_dir)
    first = (run_dir.path / "tasks/T001/parked.patch").read_bytes()
    r = run_script("task_set", run_dir, "T001", "--park-drop", "--record", "답|패치만 남김|패치는 두고 넘어가요")
    assert r.returncode == 0, r.output
    write(repo / "a.txt", "둘째 변경\n")
    park(run_dir)
    assert (run_dir.path / "tasks/T001/parked.patch").read_bytes() == first
    assert mark_of(run_dir, "T001", "parked").startswith("tasks/T001/parked.2.patch ")


@pytest.mark.parametrize("setup,want", [
    (dict(started_version="1.1.1"), "1.2.0"),
    (dict(status="진행"), "보류"),
    (dict(commit="abc1234"), "커밋"),
    (dict(kind="merge", stage="실행"), "치우지 않는다"),
    (dict(kind="design"), "코드 폴더"),
])
def test_park_is_refused_outside_its_cases_and_keeps_the_changes(run_dir, repo, setup, want):
    held_task(run_dir, repo, **setup)
    dirty(repo)
    before = status(repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3, r.output
    assert want in r.output
    assert status(repo) == before
    assert_dirty(repo)


def test_park_refuses_a_conflicted_folder(run_dir, repo):
    held_task(run_dir, repo)
    git(repo, "checkout", "-q", "-b", "other")
    write(repo / "a.txt", "저쪽\n")
    git(repo, "commit", "-qam", "other")
    git(repo, "checkout", "-q", "-")
    write(repo / "a.txt", "이쪽\n")
    git(repo, "commit", "-qam", "this")
    subprocess.run(["git", "-C", str(repo), "merge", "other"], capture_output=True)
    before = status(repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3, r.output
    assert status(repo) == before and "UU a.txt" in before


def test_park_refuses_a_nested_repository_it_cannot_put_in_a_patch(run_dir, repo):
    held_task(run_dir, repo)
    inner = repo / "inner"
    inner.mkdir()
    git(inner, "init", "-q")
    write(inner / "x.txt", "안쪽 저장소의 변경\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3, r.output
    assert (inner / "x.txt").is_file()


def test_park_options_do_not_mix_with_others(run_dir, repo):
    held_task(run_dir, repo)
    assert run_script("task_set", run_dir, "T001", "park_applying=x").returncode == 3
    assert run_script("task_set", run_dir, "T001", "--park", "--unpark").returncode == 3
    assert run_script("task_set", run_dir, "T001", "--park", "--status", "대기").returncode == 3
    assert run_script("task_set", run_dir, "T001", "parked=x").returncode == 3   # 스크립트가 채우는 키
    assert run_script("task_set", run_dir, "T001", "repro_patch=x").returncode == 3
    assert run_script("task_set", run_dir, "T001", "--park-drop").returncode == 3   # 표지가 없다


# ---------------------------------------------------------------- 끊겨도 되는 순서: 치우기

def test_cut_before_pending_is_written_keeps_changes_and_no_mark(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    die_on_save(monkeypatch, 1)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked_pending") == "" and mark_of(run_dir, "T001", "parked") == ""
    park(run_dir)
    assert_clean(repo)
    run_script("task_set", run_dir, "T001", "--unpark")
    assert_dirty(repo)


def test_cut_after_pending_before_revert_keeps_changes(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert_dirty(repo)
    pending = mark_of(run_dir, "T001", "parked_pending")
    assert pending.startswith("tasks/T001/parked.patch ")
    assert (run_dir.path / "tasks/T001/parked.patch").is_file()
    assert mark_of(run_dir, "T001", "parked") == ""

    park(run_dir)

    assert_clean(repo)
    assert mark_of(run_dir, "T001", "parked") == pending and mark_of(run_dir, "T001", "parked_pending") == ""
    run_script("task_set", run_dir, "T001", "--unpark")
    assert_dirty(repo)


def test_cut_in_the_middle_of_revert_resumes_and_loses_nothing(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff, "_restore_tracked", die)   # 새 파일은 지웠고 추적 파일은 아직
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert not (repo / NEW_NAME).exists()   # 반쯤 되돌린 자리다
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(고침)\n셋\n"
    assert mark_of(run_dir, "T001", "parked_pending")

    park(run_dir)

    assert_clean(repo)
    run_script("task_set", run_dir, "T001", "--unpark")
    assert_dirty(repo)


def test_cut_after_revert_before_parked_is_written(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    die_on_save(monkeypatch, 2)   # 1: parked_pending, 2: parked
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert_clean(repo)
    assert mark_of(run_dir, "T001", "parked_pending") and mark_of(run_dir, "T001", "parked") == ""

    park(run_dir)

    assert mark_of(run_dir, "T001", "parked") and mark_of(run_dir, "T001", "parked_pending") == ""
    run_script("task_set", run_dir, "T001", "--unpark")
    assert_dirty(repo)


def test_resume_after_cut_refuses_when_the_file_changed_since(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    write(repo / "a.txt", "끊긴 뒤 사람이 고침\n")   # 패치에 없는 내용이다. 되돌리면 사라진다

    r = run_script("task_set", run_dir, "T001", "--park")

    assert r.returncode == 3, r.output
    assert "어긋" in r.output
    assert (repo / "a.txt").read_text(encoding="utf-8") == "끊긴 뒤 사람이 고침\n"
    assert (repo / NEW_NAME).is_file()
    assert mark_of(run_dir, "T001", "parked_pending")   # 사람이 볼 때까지 그대로 둔다


def test_resume_after_cut_refuses_an_unrelated_new_file(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    write(repo / "other.txt", "다른 변경\n")
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 3
    assert (repo / "other.txt").is_file()


def test_revert_stops_when_a_file_changes_after_the_patch(run_dir, repo, monkeypatch):
    # 패치를 뜬 뒤 되돌리기 전에 파일이 바뀌면(도는 에이전트) 지우지 않는다
    held_task(run_dir, repo)
    dirty(repo)
    real = retry_diff.revert_parked

    def changed_first(folder, mark, patch):
        write(repo / "a.txt", "뜬 뒤에 바뀜\n")
        return real(folder, mark, patch)
    monkeypatch.setattr(retry_diff, "revert_parked", changed_first)
    assert call(run_dir.path, "T001", "--park") == 3
    assert (repo / "a.txt").read_text(encoding="utf-8") == "뜬 뒤에 바뀜\n"
    assert (repo / NEW_NAME).is_file()


# ---------------------------------------------------------------- 끊겨도 되는 순서: 붙이기

def test_cut_after_apply_before_mark_clears_does_not_apply_twice(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    die_on_save(monkeypatch, 2)   # 1: 붙이는 중, 2: 표지 비움
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--unpark")
    monkeypatch.undo()
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked")   # 표지가 남았다: 붙은 뒤로 읽어야 한다

    r = run_script("task_set", run_dir, "T001", "--unpark")

    assert r.returncode == 0, r.output
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked") == ""


def test_cut_before_apply_applies_on_the_next_call(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    monkeypatch.setattr(retry_diff, "apply_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--unpark")
    monkeypatch.undo()
    assert_clean(repo)
    assert mark_of(run_dir, "T001", "parked")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert_dirty(repo)


def test_unpark_refuses_when_other_changes_are_in_the_folder(run_dir, repo):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    write(repo / "other.txt", "다른 task의 변경\n")

    r = run_script("task_set", run_dir, "T001", "--unpark")

    assert r.returncode == 3, r.output
    assert "어긋" in r.output
    assert status(repo) == "?? other.txt\n"
    assert mark_of(run_dir, "T001", "parked")


def test_same_list_with_other_content_at_same_head_is_a_mismatch(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "치운 내용\n")
    park(run_dir)
    write(repo / "a.txt", "손으로 다르게 고친 내용\n")   # 파일 목록은 같다
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 3, r.output
    assert (repo / "a.txt").read_text(encoding="utf-8") == "손으로 다르게 고친 내용\n"
    assert mark_of(run_dir, "T001", "parked")


# ---------------------------------------------------------------- HEAD가 움직인 뒤: 3way, 충돌, 전체 실패

def test_unpark_after_head_moved_merges_with_3way(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n")
    write(repo / NEW_NAME, "새 파일\n")
    park(run_dir)
    write(repo / "b.txt", "다른 커밋\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "moved")

    r = run_script("task_set", run_dir, "T001", "--unpark")

    assert r.returncode == 0, r.output
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(고침)\n셋\n"
    assert (repo / NEW_NAME).is_file() and (repo / "b.txt").is_file()
    assert mark_of(run_dir, "T001", "parked") == ""


def conflict_sample(run_dir, repo, **more):
    held_task(run_dir, repo, **more)
    write(repo / "a.txt", "하나\n둘(치운 쪽)\n셋\n")
    park(run_dir)
    write(repo / "a.txt", "하나\n둘(커밋한 쪽)\n셋\n")
    git(repo, "commit", "-qam", "moved")


def test_conflict_leaves_markers_keeps_mark_and_next_call_finishes_after_resolve(run_dir, repo):
    conflict_sample(run_dir, repo)

    r = run_script("task_set", run_dir, "T001", "--unpark")

    assert r.returncode == 3, r.output
    assert "충돌" in r.output and "a.txt" in r.output
    assert "<<<<<<<" in (repo / "a.txt").read_text(encoding="utf-8")
    assert mark_of(run_dir, "T001", "parked")
    again = run_script("task_set", run_dir, "T001", "--unpark")   # 풀기 전: 다시 붙이지 않는다
    assert again.returncode == 3 and "충돌" in again.output

    write(repo / "a.txt", "하나\n둘(푼 쪽)\n셋\n")   # 충돌 해결 경로(code-writer와 메인의 git add)
    git(repo, "add", "a.txt")
    done = run_script("task_set", run_dir, "T001", "--unpark")

    assert done.returncode == 0, done.output
    assert mark_of(run_dir, "T001", "parked") == ""
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(푼 쪽)\n셋\n"


def test_new_file_added_by_a_commit_too_is_a_conflict(run_dir, repo):
    # 커밋이 같은 경로의 새 파일을 더하면 3way가 양쪽 추가 충돌(AA)로 남긴다. 내용은 표지와 함께 작업 트리에 있다
    held_task(run_dir, repo)
    write(repo / "new.txt", "치운 새 파일\n")
    park(run_dir)
    write(repo / "new.txt", "커밋한 같은 경로\n")
    git(repo, "add", "new.txt")
    git(repo, "commit", "-q", "-m", "same path")

    r = run_script("task_set", run_dir, "T001", "--unpark")

    assert r.returncode == 3, r.output
    assert "충돌" in r.output and "new.txt" in r.output
    assert "치운 새 파일" in (repo / "new.txt").read_text(encoding="utf-8")
    assert mark_of(run_dir, "T001", "parked")


def test_whole_patch_failure_stays_waiting_and_touches_nothing(run_dir, repo):
    # 무시되는 파일이 새 파일 경로에 있으면 고칠 표지가 작업 트리에 없다. 같은 패치의 다른 파일도 붙지 않아야 한다
    held_task(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n")
    write(repo / "new.txt", "치운 새 파일\n")
    park(run_dir)
    write(repo / ".git" / "info" / "exclude", "new.txt\n")
    write(repo / "new.txt", "무시되는 같은 경로\n")
    child = run_script("task_set", run_dir, "T001", "--status", "대기", "--record", "답|다시 엶|다시 열어요")
    assert child.returncode == 0, child.output

    r = run_script("task_set", run_dir, "T001", "--status", "진행")

    assert r.returncode == 3, r.output
    assert "tasks/T001/parked.patch" in r.output
    assert meta(run_dir, "T001")["status"] == "대기"
    assert status(repo) == ""
    assert (repo / "new.txt").read_text(encoding="utf-8") == "무시되는 같은 경로\n"
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘\n셋\n"
    assert mark_of(run_dir, "T001", "parked")

    # 사람이 답하면 패치를 남긴 채 표지만 뗀다
    assert run_script("task_set", run_dir, "T001", "--park-drop").returncode == 3
    drop = run_script("task_set", run_dir, "T001", "--park-drop", "--record", "답|패치만 남김|패치만 두세요")
    assert drop.returncode == 0, drop.output
    assert mark_of(run_dir, "T001", "parked") == ""
    assert (run_dir.path / "tasks/T001/parked.patch").is_file()
    assert "패치만 두세요" in meta(run_dir, "T001")["_sections"]["승인 기록"]


# ---------------------------------------------------------------- 보류를 다시 열 때

def test_reopened_task_gets_its_changes_back_when_it_starts(run_dir, repo):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    assert run_script("task_set", run_dir, "T001", "--status", "대기", "--record", "답|다시 엶|다시 열어요").returncode == 0
    assert mark_of(run_dir, "T001", "parked")
    tasks = run_dir.tasks()
    assert devflow_lib.settled(tasks["T001"], tasks) is False   # 치운 대기는 끝이 아니다

    r = run_script("task_set", run_dir, "T001", "--status", "진행")

    assert r.returncode == 0, r.output
    assert_dirty(repo)
    assert meta(run_dir, "T001")["status"] == "진행" and mark_of(run_dir, "T001", "parked") == ""


def test_start_is_refused_while_parking_is_cut(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert run_script("task_set", run_dir, "T001", "--status", "대기", "--record", "답|다시 엶|다시 열어요").returncode == 0
    r = run_script("task_set", run_dir, "T001", "--status", "진행")
    assert r.returncode == 3 and "--park" in r.output
    assert_dirty(repo)


def test_hold_stays_settled_with_parked_changes(run_dir, repo):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    tasks = run_dir.tasks()
    assert devflow_lib.settled(tasks["T001"], tasks) is True


# ---------------------------------------------------------------- 재현 패치

def repro(repo):
    write(repo / "tests" / "test_재현.py", "def test_재현():\n    assert False\n")


def test_cause_parks_with_repro_patch_not_parked(run_dir, repo):
    cause_task(run_dir, repo)
    repro(repo)
    park(run_dir)
    assert status(repo) == ""
    assert mark_of(run_dir, "T001", "parked") == ""
    assert mark_of(run_dir, "T001", "repro_patch").startswith("tasks/T001/repro.patch ")
    assert meta(run_dir, "T001")["status"] == "자체검증"


def test_cause_that_did_not_pass_is_not_parked(run_dir, repo):
    cause_task(run_dir, repo, judge_run=FAIL)
    repro(repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3, r.output
    assert (repo / "tests" / "test_재현.py").is_file()


def test_cause_without_judge_is_not_parked(run_dir, repo):
    cause_task(run_dir, repo)
    os.remove(run_dir.task_dir("T001") / "judge-run.md")
    repro(repo)
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 3
    assert (repo / "tests" / "test_재현.py").is_file()


def test_held_cause_uses_parked(run_dir, repo):
    cause_task(run_dir, repo, status="보류")
    repro(repo)
    park(run_dir)
    assert mark_of(run_dir, "T001", "parked").startswith("tasks/T001/parked.patch ")
    assert mark_of(run_dir, "T001", "repro_patch") == ""


def test_repro_mark_does_not_block_the_child_and_first_child_brings_the_patch(run_dir, repo):
    done_cause_with_repro(run_dir, repo)
    child_task(run_dir)
    tasks = run_dir.tasks()
    assert devflow_lib.dependency_done(tasks["T001"]) is True
    assert board.is_ready(tasks, tasks["T002"]) is True
    assert board.start_blocks(tasks, board.load_flows(str(run_dir.path)), 2, tasks["T002"]) == []

    r = run_script("task_set", run_dir, "T002", "--status", "진행")

    assert r.returncode == 0, r.output
    assert (repo / "tests" / "test_재현.py").is_file()
    assert meta(run_dir, "T002")["status"] == "진행"
    assert mark_of(run_dir, "T001", "repro_patch") == ""
    assert (run_dir.path / "tasks/T001/repro.patch").is_file()


def done_cause_with_repro(run_dir, repo):
    cause_task(run_dir, repo)
    repro(repo)
    park(run_dir)
    mark = mark_of(run_dir, "T001", "repro_patch")
    run_dir.task("T001", "원인 분석", kind="root-cause", block="원인 분석", status="완료", flow="s1",
                 started_version=V120, rules="2", repro_patch=mark)
    return mark


def test_grandchild_through_design_brings_the_patch(run_dir, repo):
    done_cause_with_repro(run_dir, repo)
    run_dir.task("T002", "큰 수정의 설계", kind="design", block="설계", status="완료", flow="", parent="T001")
    child_task(run_dir, "T003", parent="T002")
    r = run_script("task_set", run_dir, "T003", "--status", "진행")
    assert r.returncode == 0, r.output
    assert (repo / "tests" / "test_재현.py").is_file()


def test_non_code_child_does_not_bring_the_patch(run_dir, repo):
    mark = done_cause_with_repro(run_dir, repo)
    run_dir.task("T002", "큰 수정의 설계", kind="design", block="설계", status="대기", flow="", parent="T001")
    r = run_script("task_set", run_dir, "T002", "--status", "진행")
    assert r.returncode == 0, r.output
    assert status(repo) == ""
    assert mark_of(run_dir, "T001", "repro_patch") == mark


def test_second_child_finds_no_mark(run_dir, repo):
    done_cause_with_repro(run_dir, repo)
    child_task(run_dir)
    assert run_script("task_set", run_dir, "T002", "--status", "진행").returncode == 0
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "첫 구현")
    child_task(run_dir, "T003")
    assert run_script("task_set", run_dir, "T003", "--status", "진행").returncode == 0
    assert status(repo) == ""


def test_child_start_cut_after_apply_resumes_without_applying_twice(run_dir, repo, monkeypatch):
    done_cause_with_repro(run_dir, repo)
    child_task(run_dir)
    die_on_save(monkeypatch, 2)   # 원인 분석의 표지를 비우기 직전(1은 붙이는 중)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T002", "--status", "진행")
    monkeypatch.undo()
    assert (repo / "tests" / "test_재현.py").is_file()
    assert meta(run_dir, "T002")["status"] == "대기" and mark_of(run_dir, "T001", "repro_patch")

    r = run_script("task_set", run_dir, "T002", "--status", "진행")

    assert r.returncode == 0, r.output
    assert meta(run_dir, "T002")["status"] == "진행" and mark_of(run_dir, "T001", "repro_patch") == ""


def test_child_conflict_keeps_child_waiting_and_finishes_through_unpark(run_dir, repo):
    done_cause_with_repro(run_dir, repo)
    write(repo / "tests" / "test_재현.py", "커밋한 같은 경로\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "same path")
    child_task(run_dir)
    r = run_script("task_set", run_dir, "T002", "--status", "진행")
    assert r.returncode == 3, r.output
    assert meta(run_dir, "T002")["status"] == "대기" and mark_of(run_dir, "T001", "repro_patch")
    assert "<<<<<<<" in (repo / "tests" / "test_재현.py").read_text(encoding="utf-8")

    write(repo / "tests" / "test_재현.py", "푼 내용\n")
    git(repo, "add", "-A")
    assert run_script("task_set", run_dir, "T002", "--unpark").returncode == 0
    assert mark_of(run_dir, "T001", "repro_patch") == ""
    assert run_script("task_set", run_dir, "T002", "--status", "진행").returncode == 0


def test_cause_returning_to_work_gets_its_repro_back(run_dir, repo):
    cause_task(run_dir, repo)
    repro(repo)
    park(run_dir)
    assert run_script("task_set", run_dir, "T001", "--status", "승인대기").returncode == 0
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "--record", "답|다시|재현을 더 좁혀 주세요")
    assert r.returncode == 0, r.output
    assert (repo / "tests" / "test_재현.py").is_file()
    assert mark_of(run_dir, "T001", "repro_patch") == ""


def test_asking_is_refused_while_parking_is_cut(run_dir, repo, monkeypatch):
    cause_task(run_dir, repo)
    repro(repo)
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기")
    assert r.returncode == 3 and "--park" in r.output


@pytest.mark.parametrize("child_status", ["백로그", "보류"])
def test_cause_with_patch_is_finished_even_if_the_child_never_starts(run_dir, repo, child_status):
    # 패치는 task 폴더에 남고, 재현 패치는 끝남을 막지 않는다
    mark = done_cause_with_repro(run_dir, repo)
    child_task(run_dir, status=child_status)
    wrap = dict(kind="wrap-up", block="마무리", status="대기", parent="T001")
    run_dir.task("T003", "마무리", **wrap)
    tasks = run_dir.tasks()
    assert devflow_lib.settled(tasks["T001"], tasks) is True
    assert devflow_lib.dependency_done(tasks["T001"]) is True
    assert board.is_ready(tasks, tasks["T003"]) is True
    assert board.start_blocks(tasks, board.load_flows(str(run_dir.path)), 2, tasks["T003"]) == []
    assert board.flow_done(tasks, "s1", {"status": "진행"}, set()) is True
    assert mark_of(run_dir, "T001", "repro_patch") == mark
    assert (run_dir.path / "tasks/T001/repro.patch").is_file()


def test_cause_closed_as_backlog_keeps_the_patch_and_is_settled(run_dir, repo):
    mark = done_cause_with_repro(run_dir, repo)
    run_dir.task("T001", "원인 분석", kind="root-cause", block="원인 분석", status="백로그", flow="s1",
                 started_version=V120, rules="2", repro_patch=mark)
    tasks = run_dir.tasks()
    assert devflow_lib.settled(tasks["T001"], tasks) is True
    assert (run_dir.path / "tasks/T001/repro.patch").is_file()


def test_repro_patch_is_an_engine_key_and_not_an_unfinished_mark():
    assert "repro_patch" in kinds.ENGINE_KEYS and "repro_patch" in kinds.SCRIPT_KEYS
    assert "repro_patch" not in devflow_lib.UNFINISHED_KEYS
    assert kinds.REPRO_PATCH_KINDS == {"root-cause"}


# ---------------------------------------------------------------- 옛 task

def test_old_task_transitions_do_not_touch_the_folder(run_dir, repo):
    run_dir.flow("s1", dir=str(repo), status="진행")
    run_dir.task("T001", "옛 구현", kind="implementation", block="구현", status="대기", flow="s1")
    dirty(repo)
    before = status(repo)
    assert run_script("task_set", run_dir, "T001", "--status", "진행").returncode == 0
    assert status(repo) == before


# ---------------------------------------------------------------- 재개 화면

def resume_lines(run_dir):
    r = run_script("board", run_dir, "--resume")
    assert r.returncode == 0, r.output
    return r.stdout


def test_resume_shows_before_after_mismatch_and_cut(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    assert retry_diff.PARK_BEFORE in resume_lines(run_dir)
    assert "tasks/T001/parked.patch" in resume_lines(run_dir)

    assert retry_diff.apply_parked(str(repo), mark_of(run_dir, "T001", "parked").split(" ")[1],
                                   str(run_dir.path / "tasks/T001/parked.patch"))[0] is True
    assert retry_diff.PARK_AFTER in resume_lines(run_dir)

    write(repo / "other.txt", "다른 변경\n")
    assert retry_diff.PARK_MISMATCH in resume_lines(run_dir)
    os.remove(repo / "other.txt")

    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert "T001" not in resume_lines(run_dir)   # 표지가 없고 보류면 볼 것이 없다

    park(run_dir)
    run_script("task_set", run_dir, "T001", "--unpark")
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert "--park" in resume_lines(run_dir)


def test_resume_shows_a_conflict_and_the_repro_patch(run_dir, repo):
    conflict_sample(run_dir, repo)
    run_script("task_set", run_dir, "T001", "--unpark")
    assert retry_diff.PARK_CONFLICT in resume_lines(run_dir)


def test_resume_shows_repro_patch_of_a_closed_cause(run_dir, repo):
    done_cause_with_repro(run_dir, repo)
    out = resume_lines(run_dir)
    assert "T001" in out and "tasks/T001/repro.patch" in out


def test_resume_says_when_the_folder_is_gone(run_dir, repo):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    run_dir.flow("s1", dir=str(repo / "없음"), status="폴더 지움")
    assert "폴더 없음" in resume_lines(run_dir)


# ---------------------------------------------------------------- 폴더 대기: 치운 동안은 차지 구간에서 뺀다

DAY = "2026-10-30 "


def stamp(hm):
    return DAY + hm + ":00"


def wait_sample(run_dir, journal):
    pass_text = "판정자: rjudge-T 2026-10-30 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
    run_dir.task("T001", "치운 구현", kind="implementation", block="구현", flow="s1", status="완료",
                 created=stamp("09:00"), started=stamp("10:00"), approval_requested=stamp("13:00"), approved=stamp("13:30"))
    run_dir.judge("T001", pass_text)
    run_dir.task("T002", "그동안 쓴 수정", kind="fix", block="구현", flow="s1", status="완료",
                 created=stamp("10:30"), started=stamp("12:30"), approval_requested=stamp("12:50"), approved=stamp("12:55"))
    run_dir.judge("T002", pass_text)
    write(run_dir.path / "journal.md", journal)


def test_parked_time_is_not_folder_occupation(run_dir):
    wait_sample(run_dir, "# journal\n- 2026-10-30 11:00 | 치움 | T001 | tasks/T001/parked.patch\n"
                         "- 2026-10-30 12:45 | 붙임 | T001 | tasks/T001/parked.patch\n")
    wait, n, busy, skipped, unready = collect.flow_wait(run_dir.tasks(), "s1")
    # T002는 10:30부터 기다린다. T001이 차지한 구간은 10:00~11:00과 12:45~13:00이고 T002 시작이 12:30이라 겹침은 10:30~11:00
    assert (wait, n) == (30, 1)
    # 흐름 작성: 10:00~11:00, 12:30~13:00
    assert busy == 90
    assert (skipped, unready) == (0, 0)


def test_without_parking_the_span_is_whole(run_dir):
    wait_sample(run_dir, "# journal\n")
    wait, n, busy, _, _ = collect.flow_wait(run_dir.tasks(), "s1")
    assert (wait, n) == (120, 1)   # T002 준비 10:30부터 시작 12:30까지 T001이 차지
    assert busy == 180


def test_open_parking_runs_to_the_end_of_the_span(run_dir):
    wait_sample(run_dir, "- 2026-10-30 11:00 | 치움 | T001 | tasks/T001/parked.patch\n")
    wait, _, busy, _, _ = collect.flow_wait(run_dir.tasks(), "s1")
    assert wait == 30
    assert busy == 80   # 10:00~11:00, 12:30~12:50


# ---------------------------------------------------------------- 리뷰: 성공으로 보고하고 변경을 잃는 경로

ORIGINAL = b"same size original\n"
CHANGED = b"same size CHANGED!\n"


def racy_sample(run_dir, repo):
    """커밋한 파일을 그 초 안에 같은 크기로 고친 자리를 시각까지 고정해 만든다. status를 부르지 않는다."""
    held_task(run_dir, repo)
    path = repo / "racy.txt"
    path.write_bytes(ORIGINAL)
    stamp_at = int(os.stat(repo / ".git" / "index").st_mtime) - 100
    os.utime(path, (stamp_at, stamp_at))
    git(repo, "add", "racy.txt")
    git(repo, "commit", "-q", "-m", "racy")
    os.utime(repo / ".git" / "index", (stamp_at, stamp_at))
    path.write_bytes(CHANGED)
    os.utime(path, (stamp_at, stamp_at))
    return path


def test_same_size_same_second_change_without_status_is_not_lost(run_dir, repo):
    path = racy_sample(run_dir, repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    if r.returncode == 0:
        assert b"racy.txt" in (run_dir.path / "tasks/T001/parked.patch").read_bytes()
        assert path.read_bytes() == ORIGINAL
        assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert path.read_bytes() == CHANGED


def test_same_size_same_second_change_is_not_lost_when_repeated(run_dir, repo):
    # 시각을 고정하지 않은 실제 장면을 되풀이한다(앞선 status 없음)
    held_task(run_dir, repo)
    path = repo / "racy.txt"
    for n in range(8):
        old, new = b"%03d original\n" % n, b"%03d CHANGED!\n" % n
        assert len(old) == len(new)
        path.write_bytes(old)
        git(repo, "add", "racy.txt")
        git(repo, "commit", "-q", "-m", "round {}".format(n))
        path.write_bytes(new)
        r = run_script("task_set", run_dir, "T001", "--park")
        if r.returncode == 0 and mark_of(run_dir, "T001", "parked"):
            assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
        assert path.read_bytes() == new, "{}번째에 변경을 잃음: {}".format(n, r.output)
        git(repo, "checkout", "-q", "--", "racy.txt")


def test_retry_snapshot_sees_the_same_size_change_too(repo):
    held = repo / "racy.txt"
    held.write_bytes(ORIGINAL)
    stamp_at = int(os.stat(repo / ".git" / "index").st_mtime) - 100
    os.utime(held, (stamp_at, stamp_at))
    git(repo, "add", "racy.txt")
    git(repo, "commit", "-q", "-m", "racy")
    os.utime(repo / ".git" / "index", (stamp_at, stamp_at))
    held.write_bytes(CHANGED)
    os.utime(held, (stamp_at, stamp_at))
    with retry_diff.TempGit(str(repo)) as g:
        _, _, data, changed = g.capture()
    assert changed == 1 and b"racy.txt" in data


def test_even_with_a_stale_capture_only_patch_files_are_reverted(run_dir, repo, monkeypatch):
    # 뜨는 쪽이 놓쳐도(옛 복사 방식으로 되돌림) 되돌리는 쪽이 패치 밖 파일을 건드리지 않는다
    path = racy_sample(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n")
    monkeypatch.setattr(retry_diff.shutil, "copy2", shutil.copyfile)
    code = call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert code == 3
    assert path.read_bytes() == CHANGED
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(고침)\n셋\n"
    # 뜰 때 status와 견주므로 표지와 패치를 남기기 전에 멈춘다
    assert mark_of(run_dir, "T001", "parked_pending") == ""
    assert not (run_dir.path / "tasks/T001/parked.patch").exists()


def test_revert_refuses_status_entries_outside_the_patch_before_touching_anything(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n")
    write(repo / "new.txt", "새 파일\n")
    head, data, names = retry_diff.park_capture(str(repo))
    patch = write(run_dir.path / "p.patch", "").with_suffix(".patch")
    patch.write_bytes(data)
    mark = retry_diff.park_mark("p.patch", head, names)
    real = retry_diff._tree_names

    def hide_new(g, index, a, b):
        return real(g, index, a, b) - {"new.txt"}
    monkeypatch.setattr(retry_diff, "_tree_names", hide_new)   # 패치와 지금 트리 모두 new.txt를 못 본 자리
    with pytest.raises(retry_diff.GitError):
        retry_diff.revert_parked(str(repo), mark, str(patch))
    assert (repo / "new.txt").is_file()
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(고침)\n셋\n"


# ---------------------------------------------------------------- 리뷰: 도는 task의 변경을 쓸어 가지 않는다

def other_writer(run_dir, tid="T005", status="진행", **more):
    run_dir.task(tid, "다른 수정", kind="fix", block="구현", status=status, flow="s1", started="2026-11-05 10:00:00",
                 started_version=V120, rules="2", **more)


def test_cause_does_not_park_while_another_writer_runs(run_dir, repo):
    cause_task(run_dir, repo, status="승인대기")
    other_writer(run_dir)
    write(repo / "a.txt", "T005가 고치는 중\n")
    write(repo / "t005.txt", "T005의 새 파일\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3, r.output
    assert "T005" in r.output
    assert (repo / "t005.txt").is_file() and (repo / "a.txt").read_text(encoding="utf-8") == "T005가 고치는 중\n"
    assert not (run_dir.path / "tasks/T001/repro.patch").exists()


def test_hold_does_not_park_while_another_writer_runs(run_dir, repo):
    held_task(run_dir, repo)
    other_writer(run_dir, status="자체검증")
    write(repo / "t005.txt", "T005의 새 파일\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3 and "T005" in r.output
    assert (repo / "t005.txt").is_file()


def test_unpark_does_not_land_beside_a_running_writer(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "치운 변경\n")
    park(run_dir)
    other_writer(run_dir)
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 3 and "T005" in r.output
    assert status(repo) == "" and mark_of(run_dir, "T001", "parked")


def test_start_does_not_unpark_beside_a_running_writer(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "치운 변경\n")
    park(run_dir)
    assert run_script("task_set", run_dir, "T001", "--status", "대기", "--record", "답|다시 엶|다시 열어요").returncode == 0
    other_writer(run_dir)
    r = run_script("task_set", run_dir, "T001", "--status", "진행")
    assert r.returncode == 3 and "T005" in r.output
    assert status(repo) == "" and meta(run_dir, "T001")["status"] == "대기"


@pytest.mark.parametrize("holder", [
    dict(kind="implementation", status="보류"),
    dict(kind="implementation", status="승인대기"),
    dict(kind="root-cause", status="승인대기"),
])
def test_park_does_not_sweep_changes_another_task_still_holds(run_dir, repo, holder):
    # 「그대로 둠」으로 보류한 변경, 통과 못 하고 기다리는 변경이 패치에 쓸려 들어가 다음 코드 task로 옮겨 가지 않는다
    cause_task(run_dir, repo)
    repro(repo)
    run_dir.task("T003", "폴더를 쥔 task", block="구현", flow="s1", started="2026-11-05 09:00:00",
                 started_version=V120, rules="2", **holder)
    write(repo / "held.txt", "T003의 변경\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3 and "T003" in r.output
    assert (repo / "held.txt").is_file() and (repo / "tests" / "test_재현.py").is_file()


@pytest.mark.parametrize("cleared", [
    dict(commit="abc1234"), dict(no_change="true"), dict(parked="tasks/T003/parked.patch abc1234 0123456789abcdef"),
])
def test_tasks_that_hold_nothing_do_not_block_parking(run_dir, repo, cleared):
    cause_task(run_dir, repo)
    repro(repo)
    run_dir.task("T003", "쥔 것 없음", kind="implementation", block="구현", status="보류", flow="s1",
                 started="2026-11-05 09:00:00", started_version=V120, rules="2", **cleared)
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 0


def test_never_started_hold_does_not_block_parking(run_dir, repo):
    cause_task(run_dir, repo)
    repro(repo)
    run_dir.task("T003", "시작 전 보류", kind="implementation", block="구현", status="보류", flow="s1")
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 0


def test_writer_in_another_flow_does_not_block_parking(run_dir, repo):
    cause_task(run_dir, repo)
    repro(repo)
    run_dir.task("T003", "다른 흐름", kind="fix", block="구현", status="진행", flow="s2")
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 0


# ---------------------------------------------------------------- 리뷰: .gitignore는 미리 거부, 멈춘 치우기의 출구

@pytest.mark.parametrize("name", [".gitignore", "sub/.gitignore"])
def test_task_that_changed_gitignore_is_refused_before_anything(run_dir, repo, name):
    held_task(run_dir, repo)
    write(repo / name, "build/\n")
    write(repo / "build" / "out.txt", "산출물\n")
    write(repo / "a.txt", "소스 변경\n")
    before = status(repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3 and ".gitignore" in r.output
    assert status(repo) == before and (repo / name).is_file()
    assert (repo / "a.txt").read_text(encoding="utf-8") == "소스 변경\n"
    assert mark_of(run_dir, "T001", "parked_pending") == "" and not (run_dir.path / "tasks/T001/parked.patch").exists()


def test_cause_that_changed_gitignore_stays_in_the_folder_and_can_be_asked(run_dir, repo):
    cause_task(run_dir, repo)
    write(repo / ".gitignore", "build/\n")
    repro(repo)
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 3
    assert (repo / "tests" / "test_재현.py").is_file()
    assert run_script("task_set", run_dir, "T001", "--status", "승인대기").returncode == 0


def stuck_with_pending(run_dir, repo, monkeypatch, cut):
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff, cut, die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()


@pytest.mark.parametrize("cut", ["revert_parked", "_delete_new", "_restore_tracked"])
def test_cancel_puts_everything_back_from_each_stuck_point(run_dir, repo, monkeypatch, cut):
    stuck_with_pending(run_dir, repo, monkeypatch, cut)
    r = run_script("task_set", run_dir, "T001", "--park-cancel")
    assert r.returncode == 0, r.output
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked_pending") == "" and mark_of(run_dir, "T001", "parked") == ""
    assert (run_dir.path / "tasks/T001/parked.patch").is_file()


def test_cancel_after_revert_finished(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    die_on_save(monkeypatch, 2)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert_clean(repo)
    assert run_script("task_set", run_dir, "T001", "--park-cancel").returncode == 0
    assert_dirty(repo)


@pytest.mark.parametrize("cut_at", ["apply", "save"])
def test_cancel_cut_midway_can_be_called_again(run_dir, repo, monkeypatch, cut_at):
    stuck_with_pending(run_dir, repo, monkeypatch, "_restore_tracked")
    if cut_at == "apply":
        monkeypatch.setattr(retry_diff, "apply_parked", die)
    else:
        die_on_save(monkeypatch, 1)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park-cancel")
    monkeypatch.undo()
    assert mark_of(run_dir, "T001", "parked_pending")
    assert run_script("task_set", run_dir, "T001", "--park-cancel").returncode == 0
    assert_dirty(repo)


def test_cancel_refuses_when_something_outside_the_patch_remains(run_dir, repo, monkeypatch):
    stuck_with_pending(run_dir, repo, monkeypatch, "_restore_tracked")
    write(repo / "node_modules" / "x.js", "드러난 파일\n")
    r = run_script("task_set", run_dir, "T001", "--park-cancel")
    assert r.returncode == 3 and "x.js" in r.output
    assert (repo / "node_modules" / "x.js").is_file()
    assert mark_of(run_dir, "T001", "parked_pending")
    assert (run_dir.path / "tasks/T001/parked.patch").is_file()


def test_cancel_without_pending_is_refused(run_dir, repo):
    held_task(run_dir, repo)
    dirty(repo)
    assert run_script("task_set", run_dir, "T001", "--park-cancel").returncode == 3
    assert_dirty(repo)


def test_cancel_does_not_land_beside_a_running_writer(run_dir, repo, monkeypatch):
    stuck_with_pending(run_dir, repo, monkeypatch, "revert_parked")
    other_writer(run_dir)
    assert run_script("task_set", run_dir, "T001", "--park-cancel").returncode == 3
    assert_dirty(repo)


def test_leftover_after_revert_stops_without_writing_the_mark(run_dir, repo, monkeypatch):
    # 되돌린 뒤 남음 검사: 남았는데 표지를 쓰면 치운 것으로 믿고 폴더를 넘긴다
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff, "_delete_new", lambda *_a: None)
    code = call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert code == 3
    assert mark_of(run_dir, "T001", "parked") == "" and mark_of(run_dir, "T001", "parked_pending")
    assert (repo / NEW_NAME).is_file()


def long_new_file(repo):
    long_dir = str(repo) + "\\" + "\\".join(["긴폴더이름" * 4] * 12)
    prefixed = "\\\\?\\" + long_dir
    os.makedirs(prefixed)
    with open(prefixed + "\\새파일.txt", "wb") as f:
        f.write(b"long\n")
    return prefixed + "\\새파일.txt"


@pytest.mark.skipif(os.name != "nt", reason="260자 경로 제한은 Windows의 것")
def test_long_path_new_file_round_trips(run_dir, repo):
    git(repo, "config", "core.longpaths", "true")
    held_task(run_dir, repo)
    path = long_new_file(repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 0, r.output
    assert not os.path.exists(path) and status(repo) == ""
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert os.path.exists(path)


def test_tracked_folder_replaced_by_a_file_round_trips(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "dir" / "x.txt", "폴더 안 파일\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "dir")
    shutil.rmtree(repo / "dir")
    write(repo / "dir", "같은 이름의 파일\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 0, r.output
    assert (repo / "dir" / "x.txt").is_file() and status(repo) == ""
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert (repo / "dir").read_text(encoding="utf-8") == "같은 이름의 파일\n"


def test_tracked_file_replaced_by_a_folder_round_trips(run_dir, repo):
    held_task(run_dir, repo)
    (repo / "a.txt").unlink()
    write(repo / "a.txt" / "안쪽.txt", "파일이 폴더가 됨\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 0, r.output
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘\n셋\n" and status(repo) == ""
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert (repo / "a.txt" / "안쪽.txt").is_file()


# ---------------------------------------------------------------- 리뷰: 충돌을 푼 뒤의 표지, 붙이는 중 표지

def test_conflict_resolved_to_head_clears_instead_of_applying_again(run_dir, repo):
    conflict_sample(run_dir, repo)
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 3
    git(repo, "checkout", "-q", "HEAD", "--", "a.txt")   # HEAD 쪽을 택해 폴더가 깨끗해진다
    assert status(repo) == ""
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 0, r.output
    assert status(repo) == "" and mark_of(run_dir, "T001", "parked") == ""
    assert mark_of(run_dir, "T001", "park_applying") == ""


def test_conflict_resolved_with_another_file_list_clears(run_dir, repo):
    conflict_sample(run_dir, repo)
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 3
    write(repo / "a.txt", "하나\n둘(푼 쪽)\n셋\n")
    write(repo / "extra.txt", "해결에 더한 새 파일\n")
    git(repo, "add", "a.txt", "extra.txt")
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 0, r.output
    assert mark_of(run_dir, "T001", "parked") == ""
    assert (repo / "extra.txt").is_file()


def test_same_list_after_head_moved_without_applying_is_a_mismatch(run_dir, repo):
    # 붙이지 않았는데 다른 task의 같은 파일 변경을 붙은 뒤로 읽어 표지를 비우면 치운 내용이 사라진 것이 된다
    held_task(run_dir, repo)
    write(repo / "a.txt", "치운 내용\n")
    park(run_dir)
    write(repo / "b.txt", "다른 커밋\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "moved")
    write(repo / "a.txt", "다른 task의 변경\n")
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 3, r.output
    assert mark_of(run_dir, "T001", "parked")
    assert (repo / "a.txt").read_text(encoding="utf-8") == "다른 task의 변경\n"


def test_cut_after_3way_apply_is_read_as_applied_through_the_applying_mark(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(치운 쪽)\n셋\n")
    park(run_dir)
    write(repo / "b.txt", "다른 커밋\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "moved")
    die_on_save(monkeypatch, 2)   # 1: 붙이는 중, 2: 표지 비움
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--unpark")
    monkeypatch.undo()
    assert mark_of(run_dir, "T001", "park_applying") and mark_of(run_dir, "T001", "parked")
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 0, r.output
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(치운 쪽)\n셋\n"
    assert mark_of(run_dir, "T001", "park_applying") == ""


def test_cut_after_applying_mark_before_apply_applies_on_the_next_call(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    write(repo / "a.txt", "치운 내용\n")
    park(run_dir)
    monkeypatch.setattr(retry_diff, "apply_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--unpark")
    monkeypatch.undo()
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert (repo / "a.txt").read_text(encoding="utf-8") == "치운 내용\n"


def test_partly_applied_folder_is_shown_apart_from_a_mismatch(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "치운 내용\n")
    write(repo / "new.txt", "새 파일\n")
    park(run_dir)
    write(repo / "new.txt", "새 파일\n")   # 패치의 일부만 폴더에 있다
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 3 and retry_diff.PARK_PARTIAL in r.output
    assert retry_diff.PARK_PARTIAL in resume_lines(run_dir)
    assert mark_of(run_dir, "T001", "parked")


# ---------------------------------------------------------------- 리뷰: 끊긴 치우기를 잇는 길, 닫는 전이

def test_cut_park_resumes_whatever_the_status_became(run_dir, repo, monkeypatch):
    stuck_with_pending(run_dir, repo, monkeypatch, "_restore_tracked")
    assert run_script("task_set", run_dir, "T001", "--status", "대기", "--record", "답|다시 엶|다시 열어요").returncode == 0
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 0, r.output
    assert_clean(repo)
    assert mark_of(run_dir, "T001", "parked") and mark_of(run_dir, "T001", "parked_pending") == ""


def test_cut_repro_park_gets_the_repro_key_when_resumed(run_dir, repo, monkeypatch):
    cause_task(run_dir, repo)
    repro(repo)
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    pending = mark_of(run_dir, "T001", "parked_pending")
    run_dir.task("T001", "원인 분석", kind="root-cause", block="원인 분석", status="보류", flow="s1",
                 started_version=V120, rules="2", parked_pending=pending)
    assert run_script("task_set", run_dir, "T001", "--park").returncode == 0
    assert mark_of(run_dir, "T001", "repro_patch") == pending and mark_of(run_dir, "T001", "parked") == ""


@pytest.mark.parametrize("old,new,args", [
    ("승인대기", "완료", ("--record", "승인|승인|좋아요 진행해 주세요")),
    ("대기", "백로그", ("--reason", "다른 곳에서 처리")),
    ("보류", "백로그", ("--record", "답|백로그|나중에 하죠")),
])
def test_closing_transitions_are_refused_while_parking_is_cut(run_dir, repo, monkeypatch, old, new, args):
    cause_task(run_dir, repo)
    repro(repo)
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    pending = mark_of(run_dir, "T001", "parked_pending")
    run_dir.task("T001", "원인 분석", kind="root-cause", block="원인 분석", status=old, flow="s1",
                 started_version=V120, rules="2", parked_pending=pending, title_note="")
    run_dir.judge("T001", PASS.format("rjudge", "T001"))
    r = run_script("task_set", run_dir, "T001", "--status", new, *args)
    assert r.returncode == 3, r.output
    assert "--park" in r.output
    assert meta(run_dir, "T001")["status"] == old


def test_child_start_is_refused_while_the_parents_park_is_cut(run_dir, repo, monkeypatch):
    cause_task(run_dir, repo)
    repro(repo)
    monkeypatch.setattr(retry_diff, "_restore_tracked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    child_task(run_dir)
    r = run_script("task_set", run_dir, "T002", "--status", "진행")
    assert r.returncode == 3 and "T001" in r.output and "--park" in r.output
    assert meta(run_dir, "T002")["status"] == "대기"


def test_parked_task_cannot_close_as_backlog_without_dropping_the_mark(run_dir, repo):
    held_task(run_dir, repo)
    dirty(repo)
    park(run_dir)
    r = run_script("task_set", run_dir, "T001", "--status", "백로그", "--record", "답|백로그|나중에 하죠")
    assert r.returncode == 3 and "--park-drop" in r.output
    assert meta(run_dir, "T001")["status"] == "보류"
    assert "--park-drop" in resume_lines(run_dir)
    assert run_script("task_set", run_dir, "T001", "--park-drop", "--record", "답|패치만 남김|패치만 두세요").returncode == 0
    assert run_script("task_set", run_dir, "T001", "--status", "백로그", "--record", "답|백로그|나중에 하죠").returncode == 0
    tasks = run_dir.tasks()
    assert board.flow_done(tasks, "s1", {"status": "진행"}, set()) is True


def test_drop_also_works_with_the_child_id_and_clears_applying(run_dir, repo):
    done_cause_with_repro(run_dir, repo)
    write(repo / "tests" / "test_재현.py", "커밋한 같은 경로\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "same path")
    child_task(run_dir)
    assert run_script("task_set", run_dir, "T002", "--status", "진행").returncode == 3
    assert mark_of(run_dir, "T001", "park_applying")
    r = run_script("task_set", run_dir, "T002", "--park-drop", "--record", "답|패치만 남김|재현은 버려요")
    assert r.returncode == 0, r.output
    assert mark_of(run_dir, "T001", "repro_patch") == "" and mark_of(run_dir, "T001", "park_applying") == ""
    assert "재현은 버려요" in meta(run_dir, "T001")["_sections"]["승인 기록"]


# ---------------------------------------------------------------- 리뷰: 하위 폴더, 충돌 중인 폴더, 오류 줄

def test_unpark_into_a_subfolder_is_refused_not_a_silent_success(run_dir, repo):
    done_cause_with_repro(run_dir, repo)
    write(repo / "sub" / "keep.txt", "하위 폴더\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "sub")
    run_dir.flow("s2", dir=str(repo / "sub"), status="진행")
    run_dir.task("T002", "다른 흐름의 구현", kind="implementation", block="구현", status="대기", flow="s2", parent="T001")
    r = run_script("task_set", run_dir, "T002", "--status", "진행")
    assert r.returncode == 3, r.output
    assert mark_of(run_dir, "T001", "repro_patch")
    assert meta(run_dir, "T002")["status"] == "대기"


def test_other_writer_cannot_start_in_a_folder_with_unresolved_conflict(run_dir, repo):
    conflict_sample(run_dir, repo)
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 3
    run_dir.task("T005", "다른 계기의 수정", kind="fix", block="구현", status="대기", flow="s1")
    tasks = run_dir.tasks()
    why = board.start_blocks(tasks, board.load_flows(str(run_dir.path)), 2, tasks["T005"])
    assert any("충돌" in x and "a.txt" in x for x in why)
    r = run_script("task_set", run_dir, "T005", "--status", "진행")
    assert r.returncode == 3 and "충돌" in r.output
    assert meta(run_dir, "T005")["status"] == "대기"
    write(repo / "a.txt", "하나\n둘(푼 쪽)\n셋\n")
    git(repo, "add", "a.txt")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    tasks = run_dir.tasks()
    assert board.start_blocks(tasks, board.load_flows(str(run_dir.path)), 2, tasks["T005"]) == []


def test_delete_modify_failure_reports_the_real_error_line(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "new.txt", "새 파일\n")
    write(repo / "a.txt", "하나\n둘(치운 쪽)\n셋\n")
    (repo / "gone.txt").unlink()
    write(repo / "gone2.txt", "x\n")
    park(run_dir)
    git(repo, "rm", "-q", "a.txt")
    git(repo, "commit", "-q", "-m", "삭제")
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 3, r.output
    assert "cleanly" not in r.output and "a.txt" in r.output
    assert mark_of(run_dir, "T001", "parked")


def test_error_line_prefers_the_error_prefix():
    assert retry_diff.error_line(b"Applied patch to 'a.txt' cleanly.\nerror: b.txt: does not exist\n") == "error: b.txt: does not exist"
    assert retry_diff.error_line(b"warning: x\nother\n") == "warning: x"
    assert retry_diff.error_line(b"") == ""


# ---------------------------------------------------------------- 리뷰: 살아남은 변이

def test_patch_that_cannot_rebuild_the_tree_stops_before_any_mark(run_dir, repo):
    # 문맥 0줄 패치는 다시 세우지 못한다. 표지와 패치를 남기기 전에 거부한다
    held_task(run_dir, repo)
    git(repo, "config", "diff.context", "0")
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n넷\n")
    write(repo / "c.txt", "새 파일\n")
    monkeypatched_before = status(repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    if r.returncode == 0:
        pytest.skip("이 git은 문맥 0줄 패치도 붙인다")
    assert status(repo) == monkeypatched_before
    assert mark_of(run_dir, "T001", "parked_pending") == ""
    assert not (run_dir.path / "tasks/T001/parked.patch").exists()


def test_patch_that_rebuilds_another_tree_stops_before_any_mark(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    monkeypatch.setattr(retry_diff.TempGit, "tree_from_patch", lambda *_a, **_k: "0" * 40)
    code = call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert code == 3
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked_pending") == ""
    assert not (run_dir.path / "tasks/T001/parked.patch").exists()


def test_nested_repository_is_refused_for_that_reason_and_writes_nothing(run_dir, repo):
    held_task(run_dir, repo)
    inner = repo / "inner"
    inner.mkdir()
    git(inner, "init", "-q")
    write(inner / "x.txt", "안쪽 저장소의 변경\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3 and "안쪽 저장소" in r.output
    assert not (run_dir.path / "tasks/T001/parked.patch").exists()
    assert mark_of(run_dir, "T001", "parked_pending") == ""


def test_same_head_uses_plain_apply_and_leaves_nothing_staged(run_dir, repo):
    # --3way는 색인에 올리고 비원자적으로 충돌 표시를 남긴다. 같은 HEAD에서는 원래 꼴 그대로 붙어야 한다
    held_task(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n")
    write(repo / "new.txt", "새 파일\n")
    park(run_dir)
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert status(repo) == " M a.txt\n?? new.txt\n"


# ---------------------------------------------------------------- 실제 흐름의 worktree

def test_round_trip_in_a_real_worktree_with_head_moved(run_dir, repo, tmp_path):
    tree = tmp_path / "흐름 폴더"
    git(repo, "worktree", "add", "-q", "-b", "flow", str(tree))
    git(tree, "config", "user.email", "t@example.com")
    git(tree, "config", "user.name", "t")
    held_task(run_dir, tree)
    write(tree / "a.txt", "하나\n둘(고침)\n셋\n")
    write(tree / NEW_NAME, "새 파일\n")
    park(run_dir)
    assert status(tree) == ""
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert (tree / NEW_NAME).is_file()
    park(run_dir)
    write(tree / "b.txt", "다른 커밋\n")
    git(tree, "add", "b.txt")
    git(tree, "commit", "-q", "-m", "moved")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert (tree / "a.txt").read_text(encoding="utf-8") == "하나\n둘(고침)\n셋\n" and (tree / NEW_NAME).is_file()
    assert mark_of(run_dir, "T001", "parked") == ""


# ---------------------------------------------------------------- 재리뷰: 되돌리기 전에 복원 가능을 묻는다

def ignored_inside_replaced_file(repo):
    write(repo / ".gitignore", "*.log\n.env\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")
    (repo / "a.txt").unlink()
    write(repo / "a.txt" / "inside.txt", "파일이 폴더가 됨\n")
    write(repo / "a.txt" / "x.log", "무시되는 로그\n")
    write(repo / "a.txt" / ".env", "SECRET=1\n")


def test_ignored_file_inside_a_file_turned_folder_is_refused_before_anything(run_dir, repo):
    held_task(run_dir, repo)
    ignored_inside_replaced_file(repo)
    before = status(repo)
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3, r.output
    assert ".env" in r.output and "x.log" in r.output
    assert (repo / "a.txt" / ".env").read_text(encoding="utf-8") == "SECRET=1\n"
    assert (repo / "a.txt" / "x.log").is_file() and (repo / "a.txt" / "inside.txt").is_file()
    assert status(repo) == before
    assert mark_of(run_dir, "T001", "parked_pending") == "" and not (run_dir.path / "tasks/T001/parked.patch").exists()


def test_ignored_file_that_appears_after_a_cut_is_not_wiped_when_resumed(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    write(repo / ".gitignore", ".env\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")
    (repo / "a.txt").unlink()
    write(repo / "a.txt" / "inside.txt", "파일이 폴더가 됨\n")
    monkeypatch.setattr(retry_diff, "revert_parked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    write(repo / "a.txt" / ".env", "SECRET=1\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3 and ".env" in r.output
    assert (repo / "a.txt" / ".env").read_text(encoding="utf-8") == "SECRET=1\n"
    assert (repo / "a.txt" / "inside.txt").is_file()


def test_ignored_file_in_a_deleted_tracked_folder_stays(run_dir, repo):
    # 추적 파일을 지운 폴더에 남은 무시되는 파일은 되돌리기가 건드리지 않는다
    write(repo / ".gitignore", ".env\n")
    write(repo / "d" / "x.txt", "추적\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "d")
    held_task(run_dir, repo)
    (repo / "d" / "x.txt").unlink()
    write(repo / "d" / ".env", "SECRET=1\n")
    park(run_dir)
    assert (repo / "d" / ".env").read_text(encoding="utf-8") == "SECRET=1\n"
    assert (repo / "d" / "x.txt").is_file()
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0
    assert not (repo / "d" / "x.txt").exists() and (repo / "d" / ".env").is_file()


def test_not_restorable_is_one_question_over_all_paths(repo):
    write(repo / "dir" / "in.txt", "x\n")
    write(repo / "dir" / "out.txt", "x\n")
    assert retry_diff._not_restorable(str(repo), ["a.txt", "new.txt"], {"a.txt", "new.txt"}) == []
    assert retry_diff._not_restorable(str(repo), ["a.txt", "b.txt"], {"a.txt"}) == ["b.txt"]
    write(repo / ".git" / "info" / "exclude", "out.txt\n")
    assert retry_diff._not_restorable(str(repo), ["dir"], {"dir", "dir/in.txt"}) == ["dir/out.txt"]


# ---------------------------------------------------------------- 재리뷰: 취소는 되돌리지 않는다

def forbid_touching(monkeypatch):
    def fail(*_a, **_k):
        raise AssertionError("취소가 폴더를 되돌렸다")
    monkeypatch.setattr(retry_diff, "_delete_new", fail)
    monkeypatch.setattr(retry_diff, "_restore_tracked", fail)


def test_cancel_on_an_intact_folder_touches_nothing(run_dir, repo, monkeypatch):
    stuck_with_pending(run_dir, repo, monkeypatch, "revert_parked")
    before = status(repo)
    forbid_touching(monkeypatch)
    monkeypatch.setattr(retry_diff, "apply_parked", lambda *_a, **_k: pytest.fail("붙일 것이 없는데 붙였다"))
    assert call(run_dir.path, "T001", "--park-cancel") == 0
    monkeypatch.undo()
    assert status(repo) == before
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked_pending") == ""


def test_cancel_with_a_locked_file_applies_only_what_is_back_at_head(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    dirty(repo)
    locked = os.path.abspath(str(repo / NEW_NAME))
    real_remove = os.remove

    def remove(path, *a, **k):
        if os.path.abspath(str(path)).replace("\\\\?\\", "").endswith(os.path.basename(locked)):
            raise PermissionError(13, "잠김", str(path))
        return real_remove(path, *a, **k)
    monkeypatch.setattr(retry_diff.os, "remove", remove)
    assert call(run_dir.path, "T001", "--park") == 3   # staged.txt는 지웠고 잠긴 파일에서 멈췄다
    assert not (repo / "staged.txt").exists() and (repo / NEW_NAME).is_file()
    assert mark_of(run_dir, "T001", "parked_pending")
    forbid_touching(monkeypatch)   # 잠금이 그대로여도 취소는 끝나야 한다
    assert call(run_dir.path, "T001", "--park-cancel") == 0
    monkeypatch.undo()
    assert_dirty(repo)
    assert mark_of(run_dir, "T001", "parked_pending") == ""


def test_cancel_handles_glob_characters_in_paths(run_dir, repo, monkeypatch):
    held_task(run_dir, repo)
    write(repo / "tests" / "a[1]*.txt".replace("*", "별"), "새 파일\n")
    write(repo / "z.txt", "둘째 새 파일\n")
    monkeypatch.setattr(retry_diff, "_restore_tracked", die)
    with pytest.raises(KeyboardInterrupt):
        call(run_dir.path, "T001", "--park")
    monkeypatch.undo()
    assert not (repo / "z.txt").exists()
    assert run_script("task_set", run_dir, "T001", "--park-cancel").returncode == 0
    assert (repo / "tests" / "a[1]별.txt").is_file() and (repo / "z.txt").is_file()


# ---------------------------------------------------------------- 재리뷰: 끊긴 치우기가 있는 폴더

def test_other_writer_cannot_start_in_a_folder_with_a_cut_park(run_dir, repo, monkeypatch):
    stuck_with_pending(run_dir, repo, monkeypatch, "_restore_tracked")
    run_dir.task("T005", "다른 계기의 수정", kind="fix", block="구현", status="대기", flow="s1")
    run_dir.task("T006", "다른 흐름의 수정", kind="fix", block="구현", status="대기", flow="s2")
    run_dir.flow("s2", dir=str(repo), status="진행")
    tasks = run_dir.tasks()
    flows = board.load_flows(str(run_dir.path))
    assert any("T001" in x for x in board.start_blocks(tasks, flows, 2, tasks["T005"]))
    assert not any("T001" in x for x in board.start_blocks(tasks, flows, 2, tasks["T006"]))
    r = run_script("task_set", run_dir, "T005", "--status", "진행")
    assert r.returncode == 3 and "T001" in r.output
    assert meta(run_dir, "T005")["status"] == "대기"
    assert run_script("task_set", run_dir, "T001", "--park-cancel").returncode == 0
    assert run_script("task_set", run_dir, "T005", "--status", "진행").returncode == 0


# ---------------------------------------------------------------- 재리뷰: 쥔 변경

def closed_cause_left_in_folder(run_dir, repo):
    """치우기가 거부되어 재현 시험을 폴더에 둔 채 완료된 원인 분석."""
    run_dir.flow("s1", dir=str(repo), status="진행")
    run_dir.task("T001", "원인 분석", kind="root-cause", block="원인 분석", status="완료", flow="s1",
                 started="2026-11-05 09:00:00", started_version=V120, rules="2")
    repro(repo)


def test_done_cause_keeps_its_repro_from_being_swept_into_another_patch(run_dir, repo):
    closed_cause_left_in_folder(run_dir, repo)
    held_task(run_dir, repo, "T003", started="2026-11-05 09:30:00")
    r = run_script("task_set", run_dir, "T003", "--park")
    assert r.returncode == 3 and "T001" in r.output
    assert (repo / "tests" / "test_재현.py").is_file()


def test_done_cause_stops_holding_once_its_code_child_started(run_dir, repo):
    closed_cause_left_in_folder(run_dir, repo)
    run_dir.task("T002", "설계", kind="design", block="설계", status="완료", flow="", parent="T001")
    run_dir.task("T003", "구현", kind="implementation", block="구현", status="보류", flow="s1", parent="T002",
                 started="2026-11-05 10:00:00", started_version=V120, rules="2")
    assert run_script("task_set", run_dir, "T003", "--park").returncode == 0


def test_done_cause_with_nothing_to_park_holds_nothing(run_dir, repo):
    cause_task(run_dir, repo)
    r = park(run_dir)   # 재현하지 못해 변경이 없다
    assert "치울 변경 없음" in r.stdout
    pending = dict(status="완료", holds_nothing=mark_of(run_dir, "T001", "holds_nothing"))
    assert pending["holds_nothing"]
    run_dir.task("T001", "원인 분석", kind="root-cause", block="원인 분석", flow="s1", started="2026-11-05 09:00:00",
                 started_version=V120, rules="2", **pending)
    held_task(run_dir, repo, "T003", started="2026-11-05 09:30:00")
    write(repo / "a.txt", "T003의 변경\n")
    assert run_script("task_set", run_dir, "T003", "--park").returncode == 0


def test_hold_that_had_nothing_to_park_does_not_block_others(run_dir, repo):
    held_task(run_dir, repo, started="2026-11-05 09:00:00")
    assert "치울 변경 없음" in park(run_dir).stdout
    run_dir.task("T003", "다른 보류", kind="implementation", block="구현", status="보류", flow="s1",
                 started="2026-11-05 09:30:00", started_version=V120, rules="2")
    write(repo / "a.txt", "T003의 변경\n")
    assert run_script("task_set", run_dir, "T003", "--park").returncode == 0
    assert mark_of(run_dir, "T003", "parked")


def test_two_holds_on_a_clean_folder_do_not_block_each_other(run_dir, repo):
    held_task(run_dir, repo, started="2026-11-05 09:00:00")
    run_dir.task("T003", "다른 보류", kind="implementation", block="구현", status="보류", flow="s1",
                 started="2026-11-05 09:30:00", started_version=V120, rules="2")
    assert "치울 변경 없음" in park(run_dir).stdout
    assert "치울 변경 없음" in park(run_dir, "T003").stdout


def test_dropped_hold_does_not_block_others(run_dir, repo):
    held_task(run_dir, repo, started="2026-11-05 09:00:00")
    write(repo / "a.txt", "T001의 변경\n")
    park(run_dir)
    assert run_script("task_set", run_dir, "T001", "--park-drop", "--record", "답|패치만 남김|패치만 두세요").returncode == 0
    run_dir_task = dict(kind="implementation", block="구현", status="보류", flow="s1",
                        started="2026-11-05 09:30:00", started_version=V120, rules="2")
    run_dir.task("T003", "다른 보류", **run_dir_task)
    write(repo / "a.txt", "T003의 변경\n")
    assert run_script("task_set", run_dir, "T003", "--park").returncode == 0


def test_reopened_task_holds_again_when_it_starts(run_dir, repo):
    held_task(run_dir, repo, started="2026-11-05 09:00:00")
    park(run_dir)
    assert mark_of(run_dir, "T001", "holds_nothing")
    assert run_script("task_set", run_dir, "T001", "--status", "대기", "--record", "답|다시 엶|다시 열어요").returncode == 0
    assert run_script("task_set", run_dir, "T001", "--status", "진행").returncode == 0
    assert mark_of(run_dir, "T001", "holds_nothing") == ""


def test_holds_nothing_is_an_engine_key():
    assert "holds_nothing" in kinds.ENGINE_KEYS and "holds_nothing" not in devflow_lib.UNFINISHED_KEYS


# ---------------------------------------------------------------- 재리뷰: 충돌을 푼 뒤의 확인

def test_conflict_markers_left_after_git_add_are_refused(run_dir, repo):
    conflict_sample(run_dir, repo)
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 3
    git(repo, "add", "a.txt")   # 표시가 남은 채 올렸다
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 3 and "충돌 표시" in r.output and "a.txt" in r.output
    assert mark_of(run_dir, "T001", "parked")
    write(repo / "a.txt", "하나\n둘(푼 쪽)\n셋\n")
    git(repo, "add", "a.txt")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0


def test_marker_like_text_in_a_file_that_did_not_conflict_is_fine(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(치운 쪽)\n셋\n")
    write(repo / "doc.txt", "<<<<<<< 문서의 예시\n>>>>>>> 끝\n")
    park(run_dir)
    write(repo / "a.txt", "하나\n둘(커밋한 쪽)\n셋\n")
    git(repo, "commit", "-qam", "moved")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 3
    write(repo / "a.txt", "하나\n둘(푼 쪽)\n셋\n")
    git(repo, "add", "a.txt")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 0


def test_new_file_lost_after_conflict_is_warned_about(run_dir, repo):
    held_task(run_dir, repo)
    write(repo / "a.txt", "하나\n둘(치운 쪽)\n셋\n")
    write(repo / "new.txt", "함께 붙은 새 파일\n")
    park(run_dir)
    write(repo / "a.txt", "하나\n둘(커밋한 쪽)\n셋\n")
    git(repo, "commit", "-qam", "moved")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 3
    assert (repo / "new.txt").is_file()
    git(repo, "reset", "-q", "--hard")
    assert not (repo / "new.txt").exists()
    r = run_script("task_set", run_dir, "T001", "--unpark")
    assert r.returncode == 0, r.output
    assert "new.txt" in r.output and "tasks/T001/parked.patch" in r.output
    assert mark_of(run_dir, "T001", "parked") == ""


def test_cancel_that_did_not_restore_keeps_the_pending_mark(run_dir, repo, monkeypatch):
    stuck_with_pending(run_dir, repo, monkeypatch, "_restore_tracked")
    monkeypatch.setattr(retry_diff, "apply_parked", lambda *_a, **_k: (True, ""))   # 붙었다고 답했지만 붙지 않았다
    assert call(run_dir.path, "T001", "--park-cancel") == 3
    monkeypatch.undo()
    assert mark_of(run_dir, "T001", "parked_pending")
    assert run_script("task_set", run_dir, "T001", "--park-cancel").returncode == 0
    assert_dirty(repo)


# ---------------------------------------------------------------- 마지막 확인: 복원 명령이 건드리는 집합 전체

def test_ignored_file_at_a_parent_of_a_restored_path_is_refused(run_dir, repo):
    # 장면 1: 추적 파일이 있던 폴더 자리에 같은 이름의 무시되는 파일이 있으면 복원이 그 파일을 치운다
    write(repo / "d" / "x.txt", "추적\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "d")
    held_task(run_dir, repo)
    shutil.rmtree(repo / "d")
    write(repo / ".git" / "info" / "exclude", "d\n")
    write(repo / "d", "SECRET=1\n")
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3, r.output
    assert (repo / "d").read_text(encoding="utf-8") == "SECRET=1\n"
    assert mark_of(run_dir, "T001", "parked_pending") == "" and not (run_dir.path / "tasks/T001/parked.patch").exists()


@pytest.mark.parametrize("changed", [True, False])
def test_untracked_ignored_file_at_a_deleted_path_is_refused(run_dir, repo, changed):
    # 장면 2: 추적이 풀렸는데 무시 규칙에 걸린 파일은 패치에 없고 복원이 덮어쓴다
    write(repo / "cfg.local", "원래 값\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "cfg")
    write(repo / ".git" / "info" / "exclude", "cfg.local\n")
    held_task(run_dir, repo)
    git(repo, "rm", "-q", "--cached", "cfg.local")
    want = "고친 값\n" if changed else "원래 값\n"
    write(repo / "cfg.local", want)
    assert "cfg.local" in git(repo, "ls-files", "-o", "-i", "--exclude-standard")   # 이 목록에 잡힌다
    r = run_script("task_set", run_dir, "T001", "--park")
    assert r.returncode == 3 and "cfg.local" in r.output
    assert (repo / "cfg.local").read_text(encoding="utf-8") == want
    assert mark_of(run_dir, "T001", "parked_pending") == ""


def test_ignored_files_beside_restored_paths_do_not_refuse(repo):
    write(repo / "d" / ".env", "SECRET=1\n")
    write(repo / "ddd", "이름만 비슷함\n")
    write(repo / ".git" / "info" / "exclude", ".env\nddd\n")
    assert retry_diff._not_restorable(str(repo), ["d/x.txt", "dd"], {"d/x.txt", "dd"}) == []


def test_park_drop_writes_holds_nothing_only_on_a_clean_folder(run_dir, repo):
    conflict_sample(run_dir, repo, started="2026-11-05 09:00:00")
    assert run_script("task_set", run_dir, "T001", "--unpark").returncode == 3
    write(repo / "a.txt", "하나\n둘(푼 쪽)\n셋\n")
    git(repo, "add", "a.txt")
    assert run_script("task_set", run_dir, "T001", "--park-drop", "--record", "답|표지만 뗌|이대로 둘게요").returncode == 0
    assert mark_of(run_dir, "T001", "holds_nothing") == ""   # 푼 변경이 폴더에 있다
    run_dir.task("T003", "다른 보류", kind="implementation", block="구현", status="보류", flow="s1",
                 started="2026-11-05 09:30:00", started_version=V120, rules="2")
    r = run_script("task_set", run_dir, "T003", "--park")
    assert r.returncode == 3 and "T001" in r.output
    assert (repo / "a.txt").read_text(encoding="utf-8") == "하나\n둘(푼 쪽)\n셋\n"
