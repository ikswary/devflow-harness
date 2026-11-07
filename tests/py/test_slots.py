"""작업 칸(설계 8.3절). 칸 수 1이면 지금과 같고, 2 이상은 폴더별 런타임이 확인된 1.2.0 실행에서만 쓴다.

- `--ready`는 칸을 순서대로 배정하며 점유를 누적한다.
- 칸의 커밋은 앞감기나 cherry-pick으로 흐름 브랜치에 들어가고, 확인이 끝날 때까지 끝나지 않은 것으로 센다.
- 충돌은 중단해 되돌리고 수정 task를 따라간다. 원래 task의 commit을 덮지 않는다.
"""
import subprocess

import pytest

import board
import devflow_lib as lib
import slots
import task_set
from conftest import run_script, write

V120 = {"started_version": "1.2.0-dev.1"}
RECON = "# 정찰\n\n- 런타임: 폴더별\n"


def git(folder, *args):
    out = subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"] + list(args),
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def values(run_dir, count):
    path = run_dir.path / "run.md"
    write(path, path.read_text(encoding="utf-8") + "| 작업 칸 수 | {} |\n".format(count))


def code(run_dir, tid, touch, status="대기", flow="f", **meta):
    run_dir.task(tid, tid, kind=meta.pop("kind", "implementation"), status=status, flow=flow,
                 sections=dict({"건드릴 파일": touch}, **meta.pop("sections", {})), **dict(V120, **meta))


def slotted(run_dir, count=2):
    values(run_dir, count)
    write(run_dir.path / "recon.md", RECON)


def ready(run_dir):
    proc = run_script("board", run_dir, "--ready")
    assert proc.returncode == 0, proc.output
    return proc.output


# ---------------------------------------------------------------- 칸 수

def test_default_is_one_and_ready_is_as_today(run_dir):
    run_dir.flow("f")
    code(run_dir, "T001", "- a.py", status="진행", running_agent="w")
    code(run_dir, "T002", "- b.py")
    assert slots.slot_count(str(run_dir)) == 1
    assert "폴더 사용 중" in ready(run_dir)


def test_two_slots_need_the_recon_mark(run_dir):
    run_dir.flow("f")
    code(run_dir, "T001", "- a.py", status="진행", running_agent="w")
    code(run_dir, "T002", "- b.py")
    values(run_dir, 2)
    assert slots.slot_count(str(run_dir)) == 1
    out = ready(run_dir)
    assert "폴더 사용 중" in out and "「런타임: 폴더별」이 없어 1로 돈다" in out


def test_old_run_stays_one_even_with_the_value(run_dir):
    run_dir.flow("f")
    slotted(run_dir)
    code(run_dir, "T001", "- a.py", status="진행", running_agent="w", started_version="1.1.1")
    code(run_dir, "T002", "- b.py")
    assert slots.slot_count(str(run_dir)) == 1


def test_set_needs_the_mark_and_no_running_code_task(run_dir):
    code(run_dir, "T001", "- a.py", status="완료")
    assert run_script("slots", run_dir, "--set", "2", "칸 둘").returncode == 3
    write(run_dir.path / "recon.md", RECON)
    code(run_dir, "T002", "- b.py", status="진행", running_agent="w", flow="f")
    proc = run_script("slots", run_dir, "--set", "2", "칸 둘")
    assert proc.returncode == 3 and "T002" in proc.output
    code(run_dir, "T002", "- b.py", status="완료", flow="f")
    assert run_script("slots", run_dir, "--set", "2", "칸 둘").returncode == 0
    assert slots.slot_count(str(run_dir)) == 2


# ---------------------------------------------------------------- 칸 배정

def test_ready_does_not_give_the_same_slot_twice(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 3)
    code(run_dir, "T000", "- x.py", status="완료")
    code(run_dir, "T001", "- a.py")
    code(run_dir, "T002", "- b.py")
    out = ready(run_dir)
    assert "T001 T001 [implementation] (코드 폴더 필요: 흐름 f) [칸 1]" in out
    assert "T002 T002 [implementation] (코드 폴더 필요: 흐름 f) [칸 2]" in out


def test_overlap_and_full_slots_wait(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 2)
    code(run_dir, "T001", "- src/a.py", status="진행", running_agent="w", slot="1")
    code(run_dir, "T002", "- src/a.py")
    code(run_dir, "T003", "- b.py")
    code(run_dir, "T004", "- c.py")
    out = ready(run_dir)
    assert "건드릴 파일 겹침: T001" in out and "[칸 2]" in out and "칸 없음" in out


@pytest.mark.parametrize("left,right,want", [
    ("src/a.py", "src/a.py", True), ("src/*", "src/a/b.py", True), ("src/a/", "src/a/b.py", True),
    ("src/ab.py", "src/a", False), ("a.py", "b.py", False), ("src/**/*.ts", "lib/x.ts", False)])
def test_paths_overlap(left, right, want):
    assert slots.paths_overlap(left, right) is want


def test_dep_list_and_empty_touch_overlap_everything(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 3)
    code(run_dir, "T001", "- src/a.py", status="진행", running_agent="w", slot="1")
    code(run_dir, "T002", "- package-lock.json")
    code(run_dir, "T003", "(없음)")
    out = ready(run_dir)
    assert out.count("건드릴 파일 겹침: T001") == 2


def test_convention_row_runs_alone_both_ways(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 3)
    named = {"시그니처와 결정 번호": "- newName(x) [계약]"}
    code(run_dir, "T001", "- a.py", status="진행", running_agent="w", slot="1")
    code(run_dir, "T002", "- b.py", sections=named)
    code(run_dir, "T003", "- db/migrations/001.sql")
    out = ready(run_dir)
    assert out.count("규약 행은 다른 칸이 빌 때: T001") == 2
    code(run_dir, "T001", "- a.py", status="진행", running_agent="w", slot="1", sections=named)
    code(run_dir, "T002", "- b.py")
    code(run_dir, "T003", "- c.py")
    assert ready(run_dir).count("규약 행 도는 중: T001") == 2


def test_empty_sign_section_is_not_a_convention_row(run_dir):
    code(run_dir, "T001", "- a.py", sections={"시그니처와 결정 번호": "- 없음"})
    assert not slots.convention_row(run_dir.tasks()["T001"])


def test_fix_gets_the_slot_first(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 2)
    code(run_dir, "T001", "- x.py", status="진행", running_agent="w", slot="1")
    code(run_dir, "T002", "- a.py")
    code(run_dir, "T003", "- b.py", kind="fix")
    out = ready(run_dir)
    assert "T003 T003 [fix] (코드 폴더 필요: 흐름 f) [칸 2]" in out and "칸 없음" in out


def test_commit_wait_blocks_only_that_slot(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 2)
    code(run_dir, "T001", "- a.py", status="승인대기", slot="1")
    code(run_dir, "T002", "- b.py")
    out = ready(run_dir)
    assert "커밋 대기" not in out and "[칸 2]" in out


@pytest.mark.parametrize("meta,held", [
    ({"status": "진행"}, True), ({"status": "완료", "commit": "abc"}, False),
    ({"status": "완료", "commit": "abc", "insert_pending": "abc"}, True), ({"status": "완료", "insert_failed": "T9"}, True),
    ({"status": "승인대기"}, True), ({"status": "승인대기", "repro_patch": "p h x"}, False),
    ({"status": "보류"}, True), ({"status": "보류", "parked": "p h x"}, False), ({"status": "보류", "holds_nothing": "true"}, False),
    ({"status": "승인대기", "no_change": "true"}, False)])
def test_holds_slot(meta, held):
    assert slots.holds_slot(dict(meta, slot="1", id="T1")) is held


def test_unfinished_keys_still_block_dependents(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 2)
    code(run_dir, "T001", "- a.py", status="완료", commit="abc", insert_pending="abc", slot="1")
    code(run_dir, "T002", "- b.py", depends_on=["T001"])
    assert "[칸" not in ready(run_dir)


def test_start_refuses_without_a_slot_in_slot_mode(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 2)
    code(run_dir, "T000", "- x.py", status="완료")
    code(run_dir, "T001", "- a.py")
    proc = run_script("task_set", run_dir, "T001", "--status", "진행", "running_agent=w")
    assert proc.returncode == 3 and "slots.py" in proc.output


def test_code_dir_follows_the_slot(run_dir, tmp_path):
    base = tmp_path / "code"
    (tmp_path / "code-s2").mkdir(parents=True)
    base.mkdir()
    run_dir.flow("f", dir=str(base))
    code(run_dir, "T001", "- a.py", slot="2")
    assert task_set.code_dir(str(run_dir), run_dir.tasks()["T001"]) == str(base) + "-s2"


def test_park_guard_ignores_other_slots(run_dir):
    code(run_dir, "T001", "- a.py", status="진행", slot="1")
    code(run_dir, "T002", "- b.py", status="진행", slot="2")
    tasks = run_dir.tasks()
    assert task_set.same_flow_writers(tasks, tasks["T001"]) == []


# ---------------------------------------------------------------- 넣기

@pytest.fixture
def place(run_dir, tmp_path):
    """흐름 폴더와 칸 둘. 1.2.0 시작 표지를 위해 끝난 task 하나를 둔다."""
    base = tmp_path / "code"
    base.mkdir()
    git(base, "init", "-q", "-b", "harness/f")
    git(base, "config", "user.name", "t")
    git(base, "config", "user.email", "t@t")
    git(base, "config", "commit.gpgsign", "false")
    write(base / "shared.txt", "하나\n")
    git(base, "add", "-A")
    git(base, "commit", "-qm", "시작")
    for n in (1, 2):
        git(base, "worktree", "add", "-q", "--detach", "{}-s{}".format(base, n))
    run_dir.flow("f", dir=str(base), branch="harness/f", status="진행")
    slotted(run_dir, 2)
    code(run_dir, "T000", "- x.py", status="완료")
    return base


def work(run_dir, base, tid, n, name, text):
    """칸을 열고 파일을 고쳐 칸에서 커밋한 뒤 `insert_pending`을 적는다."""
    assert run_script("slots", run_dir, tid, "--open", n).returncode == 0
    folder = "{}-s{}".format(base, n)
    write("{}/{}".format(folder, name), text)
    git(folder, "add", "-A")
    git(folder, "commit", "-qm", tid + " 변경")
    sha = git(folder, "rev-parse", "HEAD")
    assert run_script("slots", run_dir, tid, "--pending", sha).returncode == 0
    return sha


def test_open_records_slot_and_base(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    assert run_script("slots", run_dir, "T001", "--open", "1").returncode == 0
    t = run_dir.tasks()["T001"]
    assert t.get("slot") == 1 or str(t.get("slot")) == "1"
    assert t.get("slot_base") == git(place, "rev-parse", "HEAD")


def test_open_refuses_dirty_and_taken_slots(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    code(run_dir, "T002", "- b.txt", status="진행", slot="1")
    proc = run_script("slots", run_dir, "T001", "--open", "1")
    assert proc.returncode == 3 and "T002" in proc.output
    write("{}-s2/left.txt".format(place), "남음\n")
    assert run_script("slots", run_dir, "T001", "--open", "2").returncode == 3


def test_fast_forward_keeps_the_judged_hash(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    sha = work(run_dir, place, "T001", "1", "a.txt", "가\n")
    proc = run_script("slots", run_dir, "T001", "--insert")
    assert proc.returncode == 0 and "앞감기" in proc.output
    t = run_dir.tasks()["T001"]
    assert t.get("commit") == sha and not t.get("insert_pending")
    assert git(place, "rev-parse", "HEAD") == sha


def test_cherry_pick_keeps_pending_until_checked(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    code(run_dir, "T002", "- b.txt")
    first = work(run_dir, place, "T001", "1", "a.txt", "가\n")
    second = work(run_dir, place, "T002", "2", "b.txt", "나\n")
    run_script("slots", run_dir, "T001", "--insert")
    proc = run_script("slots", run_dir, "T002", "--insert")
    assert proc.returncode == 0 and "넣은 뒤 확인" in proc.output
    t = run_dir.tasks()["T002"]
    assert t.get("commit") == git(place, "rev-parse", "HEAD") != second and t.get("insert_pending") == second
    assert lib.unfinished_mark(t)
    assert run_script("slots", run_dir, "T002", "--checked").returncode == 3   # 파일이 아직 없다
    check = run_dir.path / "flows" / "f" / "insert-checks" / "T002.md"
    write(check, "판정자: x\n\n## 통과 못 한 기준\n- 시험 1\n")
    assert run_script("slots", run_dir, "T002", "--checked").returncode == 3
    assert run_dir.tasks()["T002"].get("insert_pending")
    write(check, "판정자: x\n\n## 통과 못 한 기준\n- 없음\n")
    assert run_script("slots", run_dir, "T002", "--checked").returncode == 0
    assert not run_dir.tasks()["T002"].get("insert_pending") and first != second


def test_conflict_aborts_and_follows_the_fix(run_dir, place):
    code(run_dir, "T001", "- shared.txt")
    code(run_dir, "T002", "- shared.txt")
    work(run_dir, place, "T001", "1", "shared.txt", "가\n")
    work(run_dir, place, "T002", "2", "shared.txt", "나\n")
    run_script("slots", run_dir, "T001", "--insert")
    tip = git(place, "rev-parse", "HEAD")
    proc = run_script("slots", run_dir, "T002", "--insert")
    assert proc.returncode == 3 and "넣기 충돌" in proc.output
    assert git(place, "rev-parse", "HEAD") == tip and git(place, "status", "--porcelain") == ""
    code(run_dir, "T003", "- shared.txt", kind="fix", origin="넣기 T002")
    assert run_script("slots", run_dir, "T002", "--insert-failed", "T003").returncode == 0
    assert lib.unfinished_mark(run_dir.tasks()["T002"])
    sha = work(run_dir, place, "T003", "2", "shared.txt", "다\n")
    assert run_script("slots", run_dir, "T003", "--insert").returncode == 0
    tasks = run_dir.tasks()
    assert tasks["T003"].get("commit") == sha and tasks["T002"].get("commit_via") == "T003"
    assert not tasks["T002"].get("commit") and not tasks["T002"].get("insert_failed") and not tasks["T002"].get("insert_pending")


def test_insert_failed_needs_a_fix_task(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    work(run_dir, place, "T001", "1", "a.txt", "가\n")
    code(run_dir, "T002", "- b.txt")
    assert run_script("slots", run_dir, "T001", "--insert-failed", "T002").returncode == 3


def test_cut_insert_is_found_again(run_dir, place):
    """cherry-pick 뒤 머리 파일을 쓰기 전에 끊겼으면 다시 넣지 않는다."""
    code(run_dir, "T001", "- a.txt")
    code(run_dir, "T002", "- b.txt")
    work(run_dir, place, "T001", "1", "a.txt", "가\n")
    second = work(run_dir, place, "T002", "2", "b.txt", "나\n")
    run_script("slots", run_dir, "T001", "--insert")
    git(place, "cherry-pick", second)
    tip = git(place, "rev-parse", "HEAD")
    assert run_script("slots", run_dir, "T002", "--insert").returncode == 0
    assert run_dir.tasks()["T002"].get("commit") == tip and git(place, "rev-parse", "HEAD") == tip


def test_cut_cherry_pick_in_progress_is_aborted_and_redone(run_dir, place):
    code(run_dir, "T001", "- shared.txt")
    code(run_dir, "T002", "- other.txt")
    work(run_dir, place, "T001", "1", "shared.txt", "가\n")
    sha = work(run_dir, place, "T002", "2", "shared.txt", "나\n")
    run_script("slots", run_dir, "T001", "--insert")
    subprocess.run(["git", "-C", str(place), "cherry-pick", sha], capture_output=True)
    proc = run_script("slots", run_dir, "T002", "--insert")
    assert proc.returncode == 3 and "넣기 충돌" in proc.output
    assert git(place, "status", "--porcelain") == ""


def test_overlap_of_the_real_commit_widens_the_check(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    code(run_dir, "T002", "- b.txt")
    work(run_dir, place, "T001", "1", "a.txt", "가\n")
    work(run_dir, place, "T002", "2", "z.txt", "나\n")   # 계획 밖 파일
    run_script("slots", run_dir, "T001", "--insert")
    code(run_dir, "T004", "- z.txt", status="진행", slot="1")
    proc = run_script("slots", run_dir, "T002", "--insert")
    assert proc.returncode == 0 and "겹침으로 넓힘: T004" in proc.output


def test_resume_shows_left_inserts(run_dir, place):
    code(run_dir, "T001", "- a.txt")
    work(run_dir, place, "T001", "1", "a.txt", "가\n")
    assert "넣기 남음 T001" in run_script("board", run_dir, "--resume").output
    assert "넣기 남음 T001" in ready(run_dir)


def test_made_records_the_folder(run_dir, place):
    assert run_script("slots", run_dir, "--made", "f", "1").returncode == 0
    assert run_script("slots", run_dir, "--made", "f", "1").returncode == 0
    flows = board.load_flows(str(run_dir))
    have = flows["f"]["slots"]
    assert have == ["{}-s1".format(place)] or str(place) in str(have)


def test_insert_fix_inherits_the_slot_of_the_task_it_fixes(run_dir):
    run_dir.flow("f")
    slotted(run_dir, 2)
    code(run_dir, "T001", "- shared.txt", status="완료", slot="1", insert_pending="abc", insert_failed="T003")
    code(run_dir, "T002", "- other.txt", status="진행", running_agent="w", slot="2")
    code(run_dir, "T003", "- shared.txt", kind="fix", origin="넣기 T001")
    assert "T003 T003 [fix] (코드 폴더 필요: 흐름 f) [칸 1]" in ready(run_dir)


def test_slot_mark_is_dropped_when_the_run_went_back_to_one(run_dir):
    run_dir.flow("f")
    code(run_dir, "T000", "- x.py", status="완료")
    code(run_dir, "T001", "- a.py", slot="2", slot_base="abc")
    proc = run_script("task_set", run_dir, "T001", "--status", "진행", "running_agent=w")
    assert proc.returncode == 0, proc.output
    assert not run_dir.tasks()["T001"].get("slot")
