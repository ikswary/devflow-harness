"""승인 화면의 메인용 요약·재개 바닥 알림·커밋 대기의 no_change·재개 화면의 판정 표지 시험(설계 C 3.4, D-C4·D-C6·D-C9·D-C11).

- 화면 출력과 `screen-main.md`·journal이 산출물이라 `screen.py`·`board.py`를 명령행으로 돌려 출력 줄과 파일을 본다.
  `commit_waiting`의 분기만 단위로 함께 본다(설계 4절 10.5 행).
- 사례 이름의 `c{가~바}`가 머리 파일 판정 기준 1의 사례다.
"""
from conftest import run_script, write

import board
import screen

JUDGE_OK = ("판정자: rjudge-T001 2026-10-30 10:00:00\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n"
            "| 기준 | 판정 | 근거 |\n|---|---|---|\n| 1 | 통과 | 읽음 |\n")
JUDGE_FAILED = ("판정자: rjudge-T001 2026-10-30 10:00:00\n\n## 통과 못 한 기준\n- 기준 1: 시험이 실패함\n\n## 판정 표\n"
                "| 기준 | 판정 | 근거 |\n|---|---|---|\n| 1 | 실패 | 시험 실패 |\n")
RESULT = ("# T001 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n- 없음\n"
          "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 설계대로 한 작업 1\n\n"
          "## 스스로 줄임\n없음\n\n## 본문\n본문\n")
MAIN_PATH = "tasks\\T001\\screen-main.md"
LONG = "판정자를 띄우는 명령이 권한 거부됨: " + "가" * 120   # 앞 100자로 잘려야 하는 처리할 항목
SIGNALS = "- 화면 정본의 필드 이름이 요구사항과 한 곳 다름\n- " + LONG + "\n  하위 설명 줄"
METHOD = "원본 전부 대조 1 · 기록만 확인 1\n실행함 2"
MARK = "2026-10-30 10:00:00 rjudge-T001"
SIGNALS_PREFIX = screen.SIGNALS_HEAD.split("{}")[0]
METHOD_PREFIX = screen.METHOD_HEAD.split("{}")[0]


def screen_lines(run_dir, tid="T001"):
    r = run_script("screen", run_dir, tid)
    assert r.returncode == 0, r.output
    return r.stdout.splitlines()


def counts_index(lines):
    return next(i for i, l in enumerate(lines) if l.startswith("counts:"))


# --- (가) 두 블록이 있으면 한 줄씩과 screen-main.md -------------------------------------------------------------

def test_c_ga_two_blocks_become_summary_lines_and_file(run_dir, lib):
    run_dir.task("T001", "요약 시험", sections={"넘길 이상 신호": SIGNALS}, status="승인대기")
    run_dir.result("T001", RESULT)
    run_dir.judge("T001", JUDGE_OK + "\n## 확인 방법 요약\n" + METHOD + "\n")

    lines = screen_lines(run_dir)

    head = screen.SIGNALS_HEAD.format(2, 1, MAIN_PATH)
    assert head in lines
    under = lines[lines.index(head) + 1]
    assert under == "  " + LONG[:screen.SUMMARY_CHARS] and len(under.strip()) <= 100
    assert [l for l in lines if l.startswith(METHOD_PREFIX)] == [screen.METHOD_HEAD.format("원본 전부 대조 1 · 기록만 확인 1")]
    # 원래 블록의 항목 줄과 머리 줄은 화면에 없다
    assert "- 화면 정본의 필드 이름이 요구사항과 한 곳 다름" not in lines and "- " + LONG not in lines
    assert SIGNALS_PREFIX.strip() not in lines and "실행함 2" not in lines

    saved = lib.sections((run_dir.task_dir("T001") / "screen-main.md").read_text(encoding="utf-8"), level=2)
    t = run_dir.tasks()["T001"]
    judge = lib.sections((run_dir.task_dir("T001") / "judge.md").read_text(encoding="utf-8"), level=2)
    assert saved["이상 신호"] == t["_sections"]["넘길 이상 신호"]
    assert saved["자체 검증의 확인 방법"] == judge["확인 방법 요약"]


# --- (가-2) [전제 바뀜] 항목 전부, 이어서 처리할 항목 전부를 요약 줄 아래에(T015 V-01 안 (다)) ------------------------

def premise(tid):
    return screen.PREMISE_MARK + " 이 task의 전제가 바뀌었다(변경 task {})".format(tid)


def test_c_ga2_premise_items_then_all_todo_items_under_summary(run_dir):
    signals = "\n".join("- " + s for s in (premise("T050"), premise("T051"), "잠금이 남음: PID 1234",
                                             "자원 대기: dev DB", "그 밖의 메모"))
    run_dir.task("T001", "요약 시험", sections={"넘길 이상 신호": signals}, status="승인대기")
    run_dir.result("T001", RESULT)
    run_dir.judge("T001", JUDGE_OK)

    lines = screen_lines(run_dir)

    head = screen.SIGNALS_HEAD.format(5, 2, MAIN_PATH)
    assert head in lines
    i = lines.index(head)
    assert lines[i + 1:i + 5] == ["  " + premise("T050"), "  " + premise("T051"),
                                  "  잠금이 남음: PID 1234", "  자원 대기: dev DB"]
    assert not [l for l in lines if "그 밖의 메모" in l]


def test_c_ga2_premise_item_is_not_cut_and_shown_once(run_dir):
    long_premise = premise("T050") + " " + "나" * 120 + " 잠금"   # 처리할 낱말도 든 긴 전제 변경 줄
    run_dir.task("T001", "요약 시험", sections={"넘길 이상 신호": "- " + long_premise}, status="승인대기")
    run_dir.result("T001", RESULT)
    run_dir.judge("T001", JUDGE_OK)

    lines = screen_lines(run_dir)

    head = screen.SIGNALS_HEAD.format(1, 1, MAIN_PATH)
    assert head in lines
    assert lines[lines.index(head) + 1] == "  " + long_premise   # 앞 SUMMARY_CHARS자로 자르지 않는다
    assert len([l for l in lines if screen.PREMISE_MARK in l]) == 1   # 처리할 것 무리에 다시 내지 않는다


def test_c_ga2_started_prefix_is_skipped_to_see_premise_mark(run_dir):
    signals = "- " + screen.STARTED_PREFIX + premise("T050") + "\n- 그 밖의 메모"
    run_dir.task("T001", "요약 시험", sections={"넘길 이상 신호": signals}, status="승인대기")
    run_dir.result("T001", RESULT)
    run_dir.judge("T001", JUDGE_OK)

    lines = screen_lines(run_dir)

    head = screen.SIGNALS_HEAD.format(2, 0, MAIN_PATH)
    assert head in lines
    assert lines[lines.index(head) + 1] == "  " + premise("T050")   # 접두를 뺀 글
    assert not [l for l in lines if "그 밖의 메모" in l or screen.STARTED_PREFIX in l]


# --- (나) 둘 다 비면 줄도 파일도 없다 -------------------------------------------------------------------------

def test_c_na_no_blocks_no_lines_no_file(run_dir):
    run_dir.task("T001", "요약 시험", status="승인대기")
    run_dir.result("T001", RESULT)
    run_dir.judge("T001", JUDGE_OK)

    lines = screen_lines(run_dir)

    assert counts_index(lines) > 0   # 화면은 끝까지 나왔다(양성 대조)
    assert not [l for l in lines if l.startswith((SIGNALS_PREFIX, METHOD_PREFIX))]
    assert not (run_dir.task_dir("T001") / "screen-main.md").exists()


# --- (다) 통과 못 한 코드 task의 커밋 안내 -----------------------------------------------------------------------

def failed_code_task(run_dir, **meta):
    run_dir.task("T001", "통과 못 한 구현", kind="implementation", block="구현", flow="s1", status="승인대기", **meta)
    run_dir.result("T001", RESULT)
    run_dir.judge("T001", JUDGE_FAILED)


def test_c_da_no_change_task_has_no_commit_hint(run_dir):
    failed_code_task(run_dir, no_change="true")

    lines = screen_lines(run_dir)

    assert screen.FAILED_HEAD in lines   # 통과 못 한 task다(양성 대조)
    assert "  " + screen.COMMIT_HINT not in lines


def test_c_da_control_without_no_change_has_commit_hint(run_dir):
    failed_code_task(run_dir)

    lines = screen_lines(run_dir)

    assert screen.FAILED_HEAD in lines
    assert "  " + screen.COMMIT_HINT in lines


# --- (라) 커밋 대기에서 no_change task를 뺀다 ------------------------------------------------------------------

def waiting_flow(run_dir, **meta):
    run_dir.task("T001", "통과 못 한 구현", kind="implementation", block="구현", flow="s1", status="승인대기", **meta)
    run_dir.task("T002", "다음 구현", kind="implementation", block="구현", flow="s1", status="대기")


def test_c_ra_no_change_task_is_not_commit_waiting(run_dir):
    waiting_flow(run_dir, no_change="true")

    assert board.commit_waiting(run_dir.tasks(), "s1") == []
    r = run_script("board", run_dir, "--ready")
    assert r.returncode == 0, r.output
    assert "T002" in r.stdout   # 다음 쓰는 task가 출력에 있다(양성 대조)
    assert board.COMMIT_WAIT.split("{}")[0] not in r.stdout


def test_c_ra_control_without_no_change_is_commit_waiting(run_dir):
    waiting_flow(run_dir)

    assert board.commit_waiting(run_dir.tasks(), "s1") == ["T001"]
    r = run_script("board", run_dir, "--ready")
    assert r.returncode == 0, r.output
    assert board.COMMIT_WAIT.format("T001") in r.stdout


# --- (마) 재개 바닥 알림은 재개마다 한 번 -----------------------------------------------------------------------

def floor_run(run_dir, floor):
    run_dir.task("T001", "바닥 시험", status="승인대기")
    run_dir.result("T001", RESULT)
    run_dir.judge("T001", JUDGE_OK)
    return write(run_dir.path / "journal.md", "- 2026-10-30 10:00:00 | 재개 | - | 시작\n"
                 "- 2026-10-30 10:05:00 | 메모 | - | 재개 바닥 {}K\n".format(floor))


def floor_lines(lines):
    return [l for l in lines if l.startswith(screen.FLOOR_ALERT.split("{}")[0])]


def test_c_ma_floor_alert_once_per_resume(run_dir):
    journal = floor_run(run_dir, 160)

    lines = screen_lines(run_dir)
    alert = floor_lines(lines)
    assert alert == [screen.FLOOR_ALERT.format(160, 150)]
    assert lines.index(alert[0]) < counts_index(lines)
    assert journal.read_text(encoding="utf-8").splitlines()[-1].endswith("| 메모 | T001 | " + screen.FLOOR_NOTED.format(160))

    second = screen_lines(run_dir)
    assert counts_index(second) > 0 and floor_lines(second) == []

    with open(journal, "a", encoding="utf-8", newline="\n") as f:
        f.write("- 2026-10-30 11:00:00 | 재개 | - | 시작\n- 2026-10-30 11:05:00 | 메모 | - | 재개 바닥 170K\n")
    again = floor_lines(screen_lines(run_dir))
    assert again == [screen.FLOOR_ALERT.format(170, 150)]


def test_c_ma_floor_below_threshold_no_alert(run_dir):
    journal = floor_run(run_dir, 140)
    before = journal.read_text(encoding="utf-8")

    lines = screen_lines(run_dir)

    assert counts_index(lines) > 0 and floor_lines(lines) == []
    assert journal.read_text(encoding="utf-8") == before


# --- (바) 재개 화면의 판정 표지 메모 ---------------------------------------------------------------------------

def marked_task(run_dir):
    run_dir.task("T001", "표지 시험", status="자체검증", started_version="1.1.0", rules="2", judge_started=MARK)


def resume_line(run_dir):
    r = run_script("board", run_dir, "--resume")
    assert r.returncode == 0, r.output
    return next(l for l in r.stdout.splitlines() if l.startswith("- T001 "))


def test_c_ba_mark_without_judge_files_is_shown_on_resume(run_dir):
    marked_task(run_dir)

    line = resume_line(run_dir)

    assert board.MARK_NOTE.format(MARK) in line


def test_c_ba_mark_with_required_judge_files_is_not_shown(run_dir):
    marked_task(run_dir)
    run_dir.judge("T001", JUDGE_OK)   # 설계 task에 필요한 판정은 읽기 판정 하나

    line = resume_line(run_dir)

    assert board.RESUME_STATUS.format("자체검증") in line   # 같은 task 줄이 나왔다(양성 대조)
    assert board.MARK_NOTE.split("{}")[0] not in line
