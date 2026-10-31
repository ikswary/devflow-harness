"""폴더 대기 측정 `collect.py --folder-wait` 시험(설계 C 3.6, D-C10).

- 차지 끝·준비 시각·합집합 셈은 `occupied`·`ready_at`·`flow_wait`·`union_minutes`를 단위로 부르고,
  측정 기록 `비고` 칸과 종료 3은 명령행으로만 보인다(설계 4절 10.6 행).
- 사례 이름의 `{가~차}`가 머리 파일 판정 기준 1의 사례다. 시각은 모두 2026-10-30, 분은 손으로 센 값이다.
"""
from datetime import datetime

import pytest
from conftest import run_script, write

import collect

DAY = "2026-10-30 "
PASS = "판정자: rjudge-T 2026-10-30 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
FAIL = "판정자: rjudge-T 2026-10-30 10:00:00\n\n## 통과 못 한 기준\n- 기준 2: 변이에서 시험이 실패하지 않음\n"


def at(hm):
    return datetime.strptime(DAY + hm, "%Y-%m-%d %H:%M").timestamp()


def code_task(run_dir, tid, created, started, asked="", approved="", judge=None, judge_run=None, **meta):
    """흐름 context의 구현 task. 시각은 `HH:MM`(빈 값은 키를 비움)."""
    stamp = lambda hm: DAY + hm + ":00" if hm else ""   # noqa: E731
    meta.setdefault("status", "완료")
    run_dir.task(tid, "구현 " + tid, kind="implementation", block="구현", flow="context",
                 created=stamp(created), started=stamp(started), approval_requested=stamp(asked),
                 approved=stamp(approved), **meta)
    if judge is not None:
        run_dir.judge(tid, judge)
    if judge_run is not None:
        write(run_dir.task_dir(tid) / "judge-run.md", judge_run)


# --- (가)~(라) 차지 구간의 끝 -------------------------------------------------------------------------------

def test_ga_passed_task_ends_at_approval_requested(run_dir):
    code_task(run_dir, "T001", "09:00", "10:00", asked="10:30", approved="11:00", judge=PASS, judge_run=PASS)
    assert collect.occupied(run_dir.tasks()["T001"]) == (at("10:00"), at("10:30"))


def test_na_failed_task_ends_at_approved(run_dir):
    code_task(run_dir, "T001", "09:00", "10:00", asked="10:30", approved="11:00", judge=FAIL, judge_run=PASS)
    code_task(run_dir, "T002", "09:00", "10:00", asked="10:30", approved="11:20", judge=PASS, judge_run=FAIL)
    tasks = run_dir.tasks()
    assert collect.occupied(tasks["T001"]) == (at("10:00"), at("11:00"))
    assert collect.occupied(tasks["T002"]) == (at("10:00"), at("11:20"))   # 실행 판정 쪽 실패도 같다


def test_da_notified_task_without_approval_requested_ends_at_approved(run_dir):
    code_task(run_dir, "T001", "09:00", "10:00", approved="10:40", judge=PASS)
    assert collect.occupied(run_dir.tasks()["T001"]) == (at("10:00"), at("10:40"))


def test_ra_no_change_task_ends_at_approval_requested(run_dir):
    # 통과 못 한 기준이 있어도 no_change면 커밋 대기로 폴더를 막지 않는다
    code_task(run_dir, "T001", "09:00", "10:00", asked="10:15", approved="11:00", judge=FAIL, no_change="true")
    assert collect.occupied(run_dir.tasks()["T001"]) == (at("10:00"), at("10:15"))


# --- (마) 준비 시각 ---------------------------------------------------------------------------------------

def test_ma_ready_at_created_or_latest_dependency_approved(run_dir):
    code_task(run_dir, "T001", "09:00", "09:10", asked="09:40", approved="10:05")
    code_task(run_dir, "T002", "09:00", "09:10", asked="09:30", approved="10:20")
    code_task(run_dir, "T003", "09:05", "10:30", asked="10:50", approved="11:00", depends_on=["T001", "T002"])
    tasks = run_dir.tasks()
    assert collect.ready_at(tasks["T001"], tasks) == at("09:00")
    assert collect.ready_at(tasks["T003"], tasks) == at("10:20")


# --- (바) 겹치는 차지 구간 둘 → 합집합 --------------------------------------------------------------------------

def overlap_flow(run_dir):
    """A 10:00~10:30, B 10:20~10:50 차지. C는 10:10에 준비되어 10:40에 시작(10:40~11:00 차지).
    C 대기 [10:10, 10:40]과 A∪B [10:00, 10:50]의 겹침 30분(단순 합은 20 + 20 = 40분), 흐름 작성 10:00~11:00 60분."""
    code_task(run_dir, "T001", "10:00", "10:00", asked="10:30", approved="12:00")
    code_task(run_dir, "T002", "10:20", "10:20", asked="10:50", approved="12:00")
    code_task(run_dir, "T003", "10:10", "10:40", asked="11:00", approved="12:00")


def test_ba_overlapping_spans_counted_as_union(run_dir):
    overlap_flow(run_dir)
    assert collect.flow_wait(run_dir.tasks(), "context") == (30, 1, 60, 0, 0)
    assert collect.union_minutes([(at("10:00"), at("10:30")), (at("10:20"), at("10:50"))]) == 50


# --- (사) 겹침 없는 task → 0분, task 수에 들지 않음 ----------------------------------------------------------------

def test_sa_task_without_overlap_is_not_counted(run_dir):
    # A 10:00~10:30. C 대기 [10:10, 10:30] 20분이 A와 겹침. D 대기 [10:50, 11:00]은 누구와도 겹치지 않음
    code_task(run_dir, "T001", "10:00", "10:00", asked="10:30", approved="12:00")
    code_task(run_dir, "T002", "10:10", "10:30", asked="10:45", approved="12:00")
    code_task(run_dir, "T003", "10:50", "11:00", asked="11:10", approved="12:00")
    # 흐름 작성 [10:00, 10:45] 45분 + [11:00, 11:10] 10분
    assert collect.flow_wait(run_dir.tasks(), "context") == (20, 1, 55, 0, 0)


# --- (아) 끝이 없는 열린 task는 빠짐 ---------------------------------------------------------------------------

def test_a_open_task_is_left_out(run_dir):
    code_task(run_dir, "T001", "10:00", "10:00", asked="10:30", approved="12:00")
    code_task(run_dir, "T002", "10:10", "10:30", asked="10:45", approved="12:00")
    # 09:00부터 열려 있는 task: 셌다면 T002의 대기 20분 전부와 겹치고 흐름 작성도 09:00부터가 된다
    code_task(run_dir, "T009", "08:50", "09:00", status="진행")
    tasks = run_dir.tasks()
    assert collect.occupied(tasks["T009"]) is None
    assert collect.flow_wait(tasks, "context") == (20, 1, 45, 1, 0)


# --- (자)·(차) 명령행: 측정 기록의 비고 칸 ----------------------------------------------------------------------

HEAD = "| 실행 | 메인 컨텍스트 최대 | 비고 |\n|---|---|---|\n"


def test_ja_cli_appends_note_and_replaces_same_flow(run_dir, workspace):
    overlap_flow(run_dir)
    measure = write(workspace / "measure.md", HEAD + "| dryrun | 100K | 앞 구간 |\n| 2026-10-01-x | 90K | - |\n"
                    "| dryrun | 200K | 다시 연 구간 |\n")
    r = run_script("collect", run_dir, "--folder-wait")
    assert r.returncode == 0, r.output
    line = "폴더 대기: context 30분 (1개) / 흐름 작성 60분"
    assert r.stdout.splitlines()[0] == line
    rows = measure.read_text(encoding="utf-8").splitlines()
    assert rows[-1] == "| dryrun | 200K | 다시 연 구간; {} |".format(line)
    assert rows[2:4] == ["| dryrun | 100K | 앞 구간 |", "| 2026-10-01-x | 90K | - |"]   # 마지막 행만 바뀐다

    # 다시 돌리면 같은 흐름 조각을 바꾼다(C가 10:30에 시작했다면 대기 [10:10, 10:30] 20분, 흐름 작성 10:00~11:00 60분)
    code_task(run_dir, "T003", "10:10", "10:30", asked="11:00", approved="12:00")
    r = run_script("collect", run_dir, "--folder-wait")
    assert r.returncode == 0, r.output
    last = measure.read_text(encoding="utf-8").splitlines()[-1]
    assert last == "| dryrun | 200K | 다시 연 구간; 폴더 대기: context 20분 (1개) / 흐름 작성 60분 |"
    assert last.count("폴더 대기: context") == 1


def test_note_replaces_only_wait_piece_and_keeps_other_text(workspace):
    other = "결정 0 승인: flow-design 1(한 마디 0) / 관점 지적: 보안 1"
    measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | 폴더 대기: review 0분 (0개) / 흐름 작성 69분; "
                    + other + " |\n")
    assert collect.write_note(str(measure), "dryrun", ["폴더 대기: review 5분 (1개) / 흐름 작성 70분"])
    assert measure.read_text(encoding="utf-8").splitlines()[-1] == (
        "| dryrun | 1K | 폴더 대기: review 5분 (1개) / 흐름 작성 70분; " + other + " |")
    # 다른 흐름은 덧붙이고, 같은 글은 그대로 둔다
    assert collect.write_note(str(measure), "dryrun", ["폴더 대기: context 1분 (1개) / 흐름 작성 2분"])
    assert measure.read_text(encoding="utf-8").splitlines()[-1].endswith(other + "; 폴더 대기: context 1분 (1개) / 흐름 작성 2분 |")


def test_note_keeps_b_lines_and_dedups_same_flow_pieces(workspace):
    b = ["결정 0 승인: flow-design 1(한 마디 0)", "관점 지적: 보안 1"]
    c = "폴더 대기: context 5분 (1개) / 흐름 작성 30분"
    new = "폴더 대기: context 7분 (1개) / 흐름 작성 31분"
    cases = (("{}; {}; {}".format(c, *b), "{}; {}; {}".format(new, *b)),
             ("{}; {}; {}".format(*b, c), "{}; {}; {}".format(*b, new)),
             ("{}; {} / {}".format(c, *b), "{}; {} / {}".format(new, *b)),
             ("{}; {}; {}".format(b[0], c, b[1]), "{}; {}; {}".format(b[0], new, b[1])),
             ("{} / {} / {}".format(c, *b), "{}; {} / {}".format(new, *b)))   # 옛 꼴: 조각 앞뒤 구분자만 바뀐다
    for cell, want in cases:
        measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
        assert collect.write_note(str(measure), "dryrun", [new])
        last = measure.read_text(encoding="utf-8").splitlines()[-1]
        assert last == "| dryrun | 1K | " + want + " |", last


def test_note_same_flow_duplicates_leave_no_empty_separator(workspace):
    c1 = "폴더 대기: context 5분 (1개) / 흐름 작성 30분"
    c2 = "폴더 대기: context 9분 (2개) / 흐름 작성 40분"
    new = "폴더 대기: context 1분 (1개) / 흐름 작성 2분"
    for cell, want in ((c1 + "; " + c2, new), (c1 + "; x; " + c2, new + "; x"), ("x; " + c1 + "; " + c2, "x; " + new),
                       (c1 + "; " + c2 + "; x", new + "; x")):
        measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
        assert collect.write_note(str(measure), "dryrun", [new])
        last = measure.read_text(encoding="utf-8").splitlines()[-1]
        assert last == "| dryrun | 1K | " + want + " |", last
        assert ";;" not in last and "; ;" not in last


def test_cha_cli_without_run_row_exits_3_and_keeps_file(run_dir, workspace):
    overlap_flow(run_dir)
    measure = write(workspace / "measure.md", HEAD + "| 2026-10-01-x | 90K | - |\n")
    before = measure.read_bytes()
    r = run_script("collect", run_dir, "--folder-wait")
    assert r.returncode == 3, r.output
    assert r.stdout.splitlines()[0] == "폴더 대기: context 30분 (1개) / 흐름 작성 60분"
    assert measure.read_bytes() == before
    # 대조: 행이 있으면 0이고 파일이 바뀐다
    write(measure, HEAD + "| dryrun | 90K | - |\n")
    assert run_script("collect", run_dir, "--folder-wait").returncode == 0
    assert measure.read_text(encoding="utf-8").splitlines()[-1].endswith("흐름 작성 60분 |")


# --- 준비 시각을 못 정한 task (V-02) ---------------------------------------------------------------------------

UNREADY = "  준비 시각이 없어 대기를 못 잰 task 1개"


def test_unready_task_is_reported_separately(run_dir):
    # T002는 의존도 created도 없어 준비 시각이 None이다. 대기 0분이어도 못 잰 것으로 따로 센다
    code_task(run_dir, "T001", "10:00", "10:00", asked="10:30", approved="12:00")
    code_task(run_dir, "T002", "", "10:40", asked="11:00", approved="12:00")
    assert collect.flow_wait(run_dir.tasks(), "context") == (0, 0, 50, 0, 1)
    r = run_script("collect", run_dir, "--folder-wait")
    assert UNREADY in r.stdout.splitlines()
    # 대조: created를 채우면 그 줄이 없다
    code_task(run_dir, "T002", "10:35", "10:40", asked="11:00", approved="12:00")
    r = run_script("collect", run_dir, "--folder-wait")
    assert UNREADY not in r.stdout.splitlines()
    assert collect.flow_wait(run_dir.tasks(), "context")[4] == 0


# --- spawn_children의 created (V-02 (나)) ----------------------------------------------------------------------

def test_spawn_children_stamps_created_without_now(run_dir):
    from test_scenarios import child_row, children_section, screen_result
    run_dir.task("T001", "부모", status="완료")
    run_dir.result("T001", screen_result("T001", children=children_section(child_row("자식 가"))))
    r = run_script("spawn_children", run_dir, "T001")
    assert r.returncode == 0, r.output
    created = run_dir.tasks()["T002"]["created"]
    assert created and datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
    # 대조: --now를 주면 그 값이다
    run_dir.task("T003", "부모", status="완료")
    run_dir.result("T003", screen_result("T003", children=children_section(child_row("자식 나"))))
    r = run_script("spawn_children", run_dir, "T003", "--now", "2026-10-30 10:00:00")
    assert r.returncode == 0, r.output
    assert run_dir.tasks()["T004"]["created"] == "2026-10-30 10:00:00"


def test_note_keeps_slash_and_semicolon_of_other_text(workspace):
    c = "폴더 대기: context 5분 (1개) / 흐름 작성 30분"
    new = "폴더 대기: context 7분 (1개) / 흐름 작성 31분"
    cases = (("메모 a/ / " + c, "메모 a/; " + new),          # 글 끝 `/`는 남고 구분자 ` / `만 바뀐다
             ("메모 a;; " + c, "메모 a;; " + new),           # 글 끝 `;`는 남는다
             ("메모 a;; " + c + " / 메모 b;", "메모 a;; " + new + "; 메모 b;"),
             ("a/b 3/4 " + c, "a/b 3/4; " + new),             # 글 안 ` / `가 없는 `/`
             (c + " / /x", new + "; /x"))
    for cell, want in cases:
        measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
        assert collect.write_note(str(measure), "dryrun", [new])
        last = measure.read_text(encoding="utf-8").splitlines()[-1]
        assert last == "| dryrun | 1K | " + want + " |", last


C_WAIT = "폴더 대기: context 5분 (1개) / 흐름 작성 30분"
NEW_WAIT = "폴더 대기: context 7분 (1개) / 흐름 작성 31분"


@pytest.mark.parametrize("cell, want", [
    ("/ " + C_WAIT, NEW_WAIT),                       # 칸 맨 앞 글 없는 `/`
    ("; " + C_WAIT, NEW_WAIT),                       # 칸 맨 앞 글 없는 `;`
    (C_WAIT + " / ", NEW_WAIT),                      # 칸 끝 글 없는 구분자
    (C_WAIT + " ;", NEW_WAIT),
    (C_WAIT + " /", NEW_WAIT),
    ("/ " + C_WAIT + " / x", NEW_WAIT + "; x"),
    ("/", NEW_WAIT),                                 # 구분자 하나뿐인 칸
    ("메모 a /", "메모 a; " + NEW_WAIT),              # 글 뒤 글 없는 구분자
    (C_WAIT + "/", NEW_WAIT),                        # 조각 바로 뒤 구분자 하나뿐인 글
    ("/ 메모 / " + C_WAIT, "메모; " + NEW_WAIT),       # 칸 맨 앞 글 없는 `/` 뒤 글
    ("; 메모", "메모; " + NEW_WAIT),
    (";메모 / " + C_WAIT, ";메모; " + NEW_WAIT),       # 칸 맨 앞 글에 붙은 `;`·`/`는 남김
    (";메모", ";메모; " + NEW_WAIT),
    ("/메모 / " + C_WAIT, "/메모; " + NEW_WAIT),
    ("-", NEW_WAIT),                                 # 빈 칸
    ("", NEW_WAIT),
])
def test_note_leaves_no_dangling_separator(workspace, cell, want):
    measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
    assert collect.write_note(str(measure), "dryrun", [NEW_WAIT])
    assert measure.read_text(encoding="utf-8").splitlines()[-1] == "| dryrun | 1K | " + want + " |"

