"""폴더 대기 측정 `collect.py --folder-wait` 시험(설계 C 3.6, D-C10).

- 차지 끝·준비 시각·합집합 셈은 `occupied`·`ready_at`·`flow_wait`·`union_minutes`를 단위로 부르고,
  측정 기록 `비고` 칸과 종료 3은 명령행으로만 보인다(설계 4절 10.6 행).
- 사례 이름의 `{가~차}`가 머리 파일 판정 기준 1의 사례다. 시각은 모두 2026-10-30, 분은 손으로 센 값이다.
"""
import itertools
import re
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



@pytest.mark.parametrize("cell, want", [
    ("a / / " + C_WAIT, "a; " + NEW_WAIT),            # 조각에 맞닿아 공백 뒤에 홀로 남은 구분자를 뗀다
    ("a ; / " + C_WAIT, "a; " + NEW_WAIT),
    ("a ; ; " + C_WAIT, "a; " + NEW_WAIT),
    ("a / / " + C_WAIT + " / b", "a; " + NEW_WAIT + "; b"),
    ("a / / " + C_WAIT + " / " + C_WAIT, "a; " + NEW_WAIT),   # 같은 흐름 조각 중복
    ("메모 a;", "메모 a;; " + NEW_WAIT),              # 조각 없는 칸: 글에 붙은 `;`·`/`는 남는다
    ("메모 a/", "메모 a/; " + NEW_WAIT),
    ("a / b / " + C_WAIT, "a / b; " + NEW_WAIT),      # B 줄 안 ` / `는 그대로
    ("/ ; /", NEW_WAIT),                              # 구분자만 있는 칸
])
def test_note_strips_lone_separator_before_wait_piece(workspace, cell, want):
    measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
    assert collect.write_note(str(measure), "dryrun", [NEW_WAIT])
    assert measure.read_text(encoding="utf-8").splitlines()[-1] == "| dryrun | 1K | " + want + " |"


# --- 비고 칸 조각 열 규칙 조합(T093): 조각 앞·뒤·사이 글 × 구분자 ------------------------------------------------
# 기대값은 put_segment를 부르지 않고 규칙대로 따로 만든다: 버리지 않은 글 조각과 새 조각을 차례대로 `; `로 잇는다.
# 단 ` / ` 하나만 사이에 두고 이웃했던 두 글 조각은 ` / `로 잇는다(B 줄 안의 ` / `, 칸 맨 앞·끝에 x를 더 둔 사례에서만 생긴다).

OLD_WAIT = (C_WAIT, "폴더 대기: context 9분 (2개) / 흐름 작성 40분")   # 같은 흐름 옛 조각 둘
D_WAIT = "폴더 대기: review 1분 (1개) / 흐름 작성 2분"   # 다른 흐름 조각
PIECES = {"none": None, "space": " ", "slash": "/", "semi": ";", "a": "a", "a-slash": "a/", "semi-a": ";a",
          "a-b": "a b"}   # 조각 앞·뒤·사이 글: 없음, 공백만, `/`, `;`, `a`, `a/`, `;a`, `a b`
SEPS = {"sl": " / ", "sc": "; "}


def kept(piece):
    """버리지 않는 글 조각이면 앞뒤 공백을 뗀 글, 버리는 조각(없음·빈 조각·`/`·`;`만)이면 None."""
    if piece is None or piece.strip() in ("", "/", ";"):
        return None
    return piece.strip()


def build(pieces, sep):
    """None이 아닌 조각만 sep로 이은 칸 글과 기대 비고(같은 흐름 옛 조각은 첫 자리만 새 조각, 둘째부터 버림.
    다른 흐름 조각 D는 그대로 두고, 같은 흐름 조각이 없으면 새 조각을 끝에 더함)."""
    present = [p for p in pieces if p is not None]
    want, placed, prev_text = [], False, False   # prev_text: 바로 앞 조각이 남긴 글 조각인가
    for p in present:
        if p in OLD_WAIT:
            if not placed:
                want.append("; " + NEW_WAIT)
                placed = True
            prev_text = False
        elif p == D_WAIT:   # 다른 흐름 조각은 그대로 둔다
            want.append("; " + p)
            prev_text = False
        elif kept(p) is not None:
            want.append((" / " if prev_text and sep == " / " else "; ") + kept(p))
            prev_text = True
        else:
            prev_text = False
    if not placed:
        want.append("; " + NEW_WAIT)
    return sep.join(present), "".join(want)[2:]


def dangling(note):
    """비고에 남은 구분자 문제: `; `·` / `로 시작·끝남, 홀로 남은 `/`·`;`가 맨 앞·끝이나 구분자 바로 뒤에 있음."""
    found = []
    if note.startswith(("; ", " / ")) or re.match(r"[/;](?:\s|$)", note):
        found.append("구분자로 시작")
    if note.endswith(("; ", " / ")) or re.search(r"(?:^|\s)[/;]$", note):
        found.append("구분자로 끝남")
    if re.search(r"(?:; | / )[/;](?=\s|$)", note):
        found.append("버린 조각 자리에 구분자가 이웃함")
    return found


def note_cases():
    cases, names = [], list(PIECES)
    for front, back, sep in itertools.product(names, names, SEPS):   # 조각 앞 글 × 조각 뒤 글
        for edge in ("", "x"):   # 칸 맨 앞·끝에 글 x를 더 둔 칸(`x / {앞 글} / {조각} / {뒤 글} / x` 꼴)
            pieces = [edge or None, PIECES[front], OLD_WAIT[0], PIECES[back], edge or None]
            cases.append(pytest.param(*build(pieces, SEPS[sep]), False,
                                      id="once-{}-{}-{}{}".format(front, back, sep, "-x" if edge else "")))
    for front, mid, back, sep in itertools.product(names, names, names, SEPS):   # 같은 흐름 조각이 두 번 든 칸
        pieces = [PIECES[front], OLD_WAIT[0], PIECES[mid], OLD_WAIT[1], PIECES[back]]
        cases.append(pytest.param(*build(pieces, SEPS[sep]), False,
                                  id="twice-{}-{}-{}-{}".format(front, mid, back, sep)))
    # 구분자 사이가 공백 하나인 꼴(rjudge-T092 권장의 탐침). D는 다른 흐름 조각이다
    d_wait = D_WAIT
    for cell, want in ((C_WAIT + " / / a", NEW_WAIT + "; a"),
                       (C_WAIT + " ; ; a", NEW_WAIT + "; a"),
                       ("a / / " + C_WAIT + " / / b", "a; " + NEW_WAIT + "; b"),
                       (d_wait + " / / x", d_wait + "; x; " + NEW_WAIT),
                       ("a ;; " + C_WAIT, "a; " + NEW_WAIT)):
        cases.append(pytest.param(cell, want, False, id="probe-" + str(len(cases))))
    return cases + glued_cases()


# 조각에 공백 없이 바로 붙은 `;`·`/` 덩어리(T094). 붙은 덩어리는 구분자라, 그것과 이어진 이웃 글 끝의 `/`·`;`까지 함께 떨어진다
GLUES = {"gsc": ";", "gsl": "/", "gmix": ";/"}


def glued_cases():
    """`{앞 글}{붙은 것}{조각}{붙은 것}{뒤 글}` 칸. 기대값은 붙은 쪽 끝의 `/`·`;`를 뗀 이웃 글로 build가 만든다.
    칸 맨 앞·끝 x는 ` / `로만 둔다(`x; ;a`처럼 글 `;a`가 `; ` 뒤에 오는 정상 사례가 생기지 않게)."""
    cases, names = [], list(PIECES)
    for front, back, g1, g2 in itertools.product(names, names, GLUES, GLUES):
        before = ((PIECES[front] or "") + GLUES[g1]).rstrip("/;")
        after = (GLUES[g2] + (PIECES[back] or "")).lstrip("/;")
        for edge in ("", "x"):
            cell = (edge + " / " if edge else "") + (PIECES[front] or "") + GLUES[g1] + OLD_WAIT[0] + GLUES[g2] \
                + (PIECES[back] or "") + (" / " + edge if edge else "")
            want = build([edge or None, before, OLD_WAIT[0], after, edge or None], " / ")[1]
            cases.append(pytest.param(cell, want, True,
                                      id="glued-{}-{}-{}-{}{}".format(front, g1, g2, back, "-x" if edge else "")))
    for front, mid, back, g in itertools.product(names, names, names, GLUES):   # 같은 흐름 조각이 두 번 든 칸
        glue = GLUES[g]
        cell = (PIECES[front] or "") + glue + OLD_WAIT[0] + glue + (PIECES[mid] or "") + glue + OLD_WAIT[1] + glue \
            + (PIECES[back] or "")
        pieces = [((PIECES[front] or "") + glue).rstrip("/;"), OLD_WAIT[0], (glue + (PIECES[mid] or "") + glue).strip("/;"),
                  OLD_WAIT[1], (glue + (PIECES[back] or "")).lstrip("/;")]
        cases.append(pytest.param(cell, build(pieces, "; ")[1], True,
                                  id="glued-twice-{}-{}-{}-{}".format(front, mid, back, g)))
    return cases


@pytest.fixture(scope="module")
def note_file(tmp_path_factory):
    return tmp_path_factory.mktemp("note") / "measure.md"


@pytest.mark.parametrize("cell, want, glued", note_cases())
def test_note_rule_over_piece_combinations(note_file, cell, want, glued):
    write(note_file, HEAD + "| dryrun | 1K | " + cell + " |\n")
    assert collect.write_note(str(note_file), "dryrun", [NEW_WAIT])
    last = note_file.read_text(encoding="utf-8").splitlines()[-1]
    note = last[len("| dryrun | 1K | "):-len(" |")]
    problems = ([] if last == "| dryrun | 1K | " + want + " |" else ["기대 {!r}".format(want)]) + dangling(note)
    if glued and ("; ;" in note or "; /" in note):   # 조각에 붙었던 `;`·`/`가 이웃 글의 글자로 남음
        problems.append("붙은 구분자가 글로 남음")
    assert not problems, "칸 {!r} → 비고 {!r}: {}".format(cell, note, ", ".join(problems))


# --- 조각에 바로 붙은 구분자와 조각 꼴 끝 경계(T094) ---------------------------------------------------------------

@pytest.mark.parametrize("cell, want", [
    (C_WAIT + ";a", NEW_WAIT + "; a"),               # 85ada6e: `{새 조각}; ;a`
    (C_WAIT + "/a", NEW_WAIT + "; a"),               # 85ada6e: `{새 조각}; /a`
    ("a/" + C_WAIT, "a; " + NEW_WAIT),               # 85ada6e: `a/; {새 조각}`
    ("a;" + C_WAIT, "a; " + NEW_WAIT),               # 85ada6e: `a;; {새 조각}`
])
def test_note_cuts_separator_glued_to_wait_piece(workspace, cell, want):
    measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
    assert collect.write_note(str(measure), "dryrun", [NEW_WAIT])
    assert measure.read_text(encoding="utf-8").splitlines()[-1] == "| dryrun | 1K | " + want + " |"


@pytest.mark.parametrize("cell, want", [
    (C_WAIT + "x / a", C_WAIT + "x / a; " + NEW_WAIT),   # 글자가 바로 이어진 조각 꼴은 글이다(85ada6e: `{새 조각}; x / a`)
    (C_WAIT + "x; a", C_WAIT + "x; a; " + NEW_WAIT),
    (C_WAIT + "0", C_WAIT + "0; " + NEW_WAIT),
    (C_WAIT, NEW_WAIT),                                # 대조: 끝이 칸 끝·공백·`;`·`/`면 조각이다
    (C_WAIT + " / a", NEW_WAIT + "; a"),
    (C_WAIT + "; a", NEW_WAIT + "; a"),
    (C_WAIT + ";a", NEW_WAIT + "; a"),
    (C_WAIT + "/a", NEW_WAIT + "; a"),
])
def test_note_wait_piece_needs_end_boundary(workspace, cell, want):
    measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
    assert collect.write_note(str(measure), "dryrun", [NEW_WAIT])
    assert measure.read_text(encoding="utf-8").splitlines()[-1] == "| dryrun | 1K | " + want + " |"


# --- 구분자 없이 붙은 조각과 멱등(T095) -----------------------------------------------------------------------------
# 조각 꼴의 끝 경계에는 다른 조각의 머리 `폴더 대기: `도 든다. 그래서 `{조각}{다른 조각}`은 각각 조각이다.

STUCK = {"C": OLD_WAIT[0], "C2": OLD_WAIT[1], "D": D_WAIT}


def stuck_cases():
    """`{앞 글}{구분자}{붙은 조각 둘·셋}{구분자}{뒤 글}` 칸과 기대 비고. 붙은 조각은 같은 흐름 C·C2와 다른 흐름 D에서 고른다."""
    cases = []
    chains = [c for n in (2, 3) for c in itertools.product(STUCK, repeat=n)]
    for front, back, sep, chain in itertools.product(PIECES, PIECES, SEPS, chains):
        pieces = [PIECES[front]] + [STUCK[k] for k in chain] + [PIECES[back]]
        cell = SEPS[sep].join(p for p in [PIECES[front], "".join(STUCK[k] for k in chain), PIECES[back]] if p is not None)
        cases.append((cell, build(pieces, SEPS[sep])[1]))
    return cases


@pytest.mark.parametrize("cell, want", [
    ("/ " + OLD_WAIT[0] + OLD_WAIT[1], NEW_WAIT),          # dc9834c: `{C}; {새 조각}`(같은 흐름 조각 둘)
    (OLD_WAIT[0] + OLD_WAIT[1], NEW_WAIT),                 # dc9834c: `{C}; {새 조각}`
    (OLD_WAIT[1] + OLD_WAIT[0], NEW_WAIT),                 # dc9834c: `{C2}; {새 조각}`
    ("a " + OLD_WAIT[0] + ";" + OLD_WAIT[1] + " b", "a; " + NEW_WAIT + "; b"),   # 대조: `;`로 붙은 칸(dc9834c와 같음)
    ("/ " + OLD_WAIT[0] + D_WAIT, NEW_WAIT + "; " + D_WAIT),   # dc9834c: `{C}; {D}; {새 조각}`
    (D_WAIT + OLD_WAIT[0], D_WAIT + "; " + NEW_WAIT),          # dc9834c는 {D}를 글로 보지만 결과 글자는 같다
])
def test_note_stuck_wait_pieces_are_each_a_piece(workspace, cell, want):
    measure = write(workspace / "measure.md", HEAD + "| dryrun | 1K | " + cell + " |\n")
    assert collect.write_note(str(measure), "dryrun", [NEW_WAIT])
    assert measure.read_text(encoding="utf-8").splitlines()[-1] == "| dryrun | 1K | " + want + " |"


def test_note_stuck_wait_piece_combinations():
    """붙은 조각 칸 전체를 한 시험에서 돌려, 기대 비고와 다른 칸을 모은다(칸마다 시험을 두지 않는다)."""
    cases = stuck_cases()
    broken = [(cell, got, want) for cell, want in cases for got in [collect.put_segment(cell, NEW_WAIT)] if got != want]
    assert not broken, "{}/{}칸이 기대와 다름, 앞 다섯: {!r}".format(len(broken), len(cases), broken[:5])


SAME_FLOW = re.compile(r"폴더 대기: context \d+분 \(\d+개\) / 흐름 작성 \d+분(?=[\s/;]|폴더 대기: |$)")


def test_put_segment_is_idempotent_with_one_same_flow_piece():
    """T093·T094의 조합 칸과 붙은 조각 칸 전체에서 (가) 두 번 넣은 결과가 한 번 넣은 결과와 같고, (나) 결과에 같은 흐름 조각이
    정확히 하나다. 깨진 칸은 모아서 앞 다섯을 보인다."""
    cells = [p.values[0] for p in note_cases()] + [cell for cell, _ in stuck_cases()]
    not_idem, not_one = [], []
    for cell in cells:
        once = collect.put_segment(cell, NEW_WAIT)
        twice = collect.put_segment(once, NEW_WAIT)
        if twice != once:
            not_idem.append((cell, once, twice))
        if len(SAME_FLOW.findall(once)) != 1 or NEW_WAIT not in once:
            not_one.append((cell, once))
    assert not not_idem and not not_one, "{}칸 중 멱등 깨짐 {}칸 {!r}, 같은 흐름 조각이 하나가 아님 {}칸 {!r}".format(
        len(cells), len(not_idem), not_idem[:5], len(not_one), not_one[:5])
