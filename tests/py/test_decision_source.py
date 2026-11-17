"""1.3.0 C: 결과 파일 「정한 것」의 결정 출처(구현 설계 2절 C, 7판 규칙 4.2).

- 1.3.0부터 시작한 task의 승인 화면 칸은 「전제」, 「정해 주실 것」, 「하실 일·허용 요청」, 「알릴 것」, 「정한 것」, 「확인 안 된 것」,
  「건수만」이다. 「정한 것」이 「답하신 것의 반영」을 대신한다(옛 task는 옛 칸 그대로).
- 결정 하나는 칸 하나다. 「정한 것」은 ◇(앞 답의 원문이 그 결정을 직접 말함, 날짜와 원문)와 ✔(담당이 근거로 정함, 버린 길)만.
- 앞 답과 다른 동작·옵션·범위를 만드는 결정(↺)은 답이 없는 사용자 결정이라 「정해 주실 것」에 `[성질: 앞 판단과 다름]`과
  `바뀌는 앞 답: {날짜} "{원문}"`을 달아 쓴다. 「정한 것」에 ↺로 쓰면 꼴 문제이고, 스크립트가 「정해 주실 것」 맨 위로 올려 보인다.
- 날짜·원문이 없는 ◇, 기호가 없는 줄, 줄 꼴이 아닌 칸은 꼴 문제다. 화면에 경고로 보이고 알림을 막는다.
"""
import devflow_lib as lib
import kinds
import screen
from datetime import datetime

V130 = {"started_version": "1.3.0", "rules": "2"}
V121 = {"started_version": "1.2.1", "rules": "2"}


def result(decided="- 없음", premise="- 없음", decide="- 없음", notify="- 없음"):
    return ("# 결과\n\n## 승인 화면\n### 전제\n{}\n### 정해 주실 것\n{}\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n{}\n"
            "### 정한 것\n{}\n### 확인 안 된 것\n- 없음\n### 건수만\n- 없음\n").format(premise, decide, notify, decided)


def judged(run_dir):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T001", "판정자: rjudge-T001 {}\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n| 기준 | 판정 | 근거 |\n|---|---|---|\n"
                          "| 1 | 통과 | 읽음 |\n\n## 짚음\n- 없음\n\n## 주장-출처 대조\n- 없음\n".format(now))
    run_dir.task_dir("T001").joinpath(lib.FACTS_FILE).write_text("# 사실\n", encoding="utf-8")


def design(run_dir, text, meta=V130):
    run_dir.task("T001", "설계", kind="design", block="설계", status="자체검증", **meta)
    run_dir.result("T001", text)
    judged(run_dir)
    return screen.build(str(run_dir.path), "T001")


ROWS = ('- ◇ 사진은 원본 그대로 둔다 | 앞 답: 2026-11-10 "원본은 건드리지 마"\n'
        '- ↺ 배포 때 DB 이전을 건너뛴다 | 바뀌는 앞 답: 2026-11-12 "DB는 늘 같이 올려"\n'
        "- ✔ 썸네일은 서버에서 만든다 | 버림: 브라우저에서 만듦\n")


def test_cells_follow_the_start_version(run_dir):
    run_dir.task("T001", "설계", kind="design", **V130)
    run_dir.task("T002", "설계", kind="design", **V121)
    tasks = run_dir.tasks()
    assert lib.cells_of(tasks["T001"]) == kinds.CELLS_V130 and lib.cells_of(tasks["T002"]) == kinds.CELLS
    assert lib.answered_cell(tasks["T001"]) == "정한 것" and lib.answered_cell(tasks["T002"]) == "답하신 것의 반영"
    assert kinds.CELLS_V130[0] == "전제" and "답하신 것의 반영" not in kinds.CELLS_V130


def test_rows_are_read_with_mark_and_source():
    rows = lib.decided_rows(ROWS)
    assert [r["mark"] for r in rows] == ["◇", "↺", "✔"]
    assert rows[0]["date"] == "2026-11-10" and rows[0]["quote"] == "원본은 건드리지 마"
    assert rows[1]["date"] == "2026-11-12" and rows[1]["quote"] == "DB는 늘 같이 올려"
    assert rows[2]["dropped"] == "브라우저에서 만듦"
    assert [bool(r["problem"]) for r in rows] == [False, True, False]   # ↺는 이 칸이 아니다
    assert "정해 주실 것" in rows[1]["problem"]


def test_missing_sources_are_problems():
    rows = lib.decided_rows("- ◇ 원본 둠\n- ◇ 이전 | 앞 답: 어제\n- 기호 없는 줄\n- ✔ 새 길\n")
    assert [bool(r["problem"]) for r in rows] == [True, True, True, False]
    assert rows[3]["warning"]   # 새로 정한 것에 버린 길이 없으면 경고만


def test_changed_decision_goes_up_to_decide(run_dir):
    b = design(run_dir, result(ROWS))
    decide = b["screen"]["정해 주실 것"]
    assert decide.startswith('- [앞 결정을 바꿈] 배포 때 DB 이전을 건너뛴다 (2026-11-12 "DB는 늘 같이 올려"과 다름)')
    assert "↺" not in b["screen"]["정한 것"] and "◇ 사진은 원본" in b["screen"]["정한 것"]
    assert b["counts"]["n_decide"] == 1 and not b["notify_ok"]
    assert any("↺" in x for x in b["sources"])   # 작성자에게 「정해 주실 것」으로 옮겨 쓰게 한다


def test_source_problems_block_notify_and_are_listed(run_dir):
    b = design(run_dir, result("- ◇ 원본 둠\n"))
    assert b["sources"] and "원본 둠" in b["sources"][0]
    assert not b["notify_ok"] and not b["missing"]


def test_clean_new_task_still_notifies(run_dir):
    b = design(run_dir, result("- ✔ 썸네일은 서버에서 | 버림: 브라우저\n"))
    assert b["sources"] == [] and b["missing"] == []


def test_new_task_needs_the_new_cells(run_dir):
    old_cells = result().replace("### 전제\n- 없음\n", "").replace("### 정한 것", "### 답하신 것의 반영")
    b = design(run_dir, old_cells)
    assert set(b["missing"]) == {"전제", "정한 것"}


def test_old_task_keeps_the_old_cells(run_dir):
    old_cells = result().replace("### 전제\n- 없음\n", "").replace("### 정한 것", "### 답하신 것의 반영")
    b = design(run_dir, old_cells, meta=V121)
    assert b["missing"] == [] and b["sources"] == []



def test_changed_decision_in_decide_needs_the_changed_answer(run_dir):
    bad = "- (가) DB 이전을 따로 / (나) 같이 [성질: 앞 판단과 다름]\n"
    good = '- (가) DB 이전을 따로 / (나) 같이 [성질: 앞 판단과 다름] | 바뀌는 앞 답: 2026-11-12 「DB는 늘 같이 올려」\n'
    assert any("바뀌는 앞 답" in x for x in design(run_dir, result(decide=bad))["sources"])
    assert design(run_dir, result(decide=good))["sources"] == []


def test_corner_quotes_are_sources():
    rows = lib.decided_rows("- ◇ 원본 둠 | 앞 답: 2026-11-10 「원본은 건드리지 마」\n- ◇ 작게 | 앞 답: 2026-11-11 '작게'\n")
    assert [r["quote"] for r in rows] == ["원본은 건드리지 마", "작게"] and not any(r["problem"] for r in rows)


def test_numbered_cells_are_problems(run_dir):
    b = design(run_dir, result("1. ↺ DB 이전을 건너뜀", premise="1. 전1 계정이 있나요 | 막아 세움: 예 | 답: 예/아니오"))
    assert any("「정한 것」 칸을" in x for x in b["sources"]) and any("「전제」 칸을" in x for x in b["sources"])


def test_premise_and_decided_cells_are_not_move_targets(run_dir):
    run_dir.task("T001", "설계", kind="design", block="설계", status="자체검증", **V130)
    run_dir.result("T001", result(notify="- 알릴 줄 하나"))
    judged(run_dir)
    judge = run_dir.task_dir("T001") / "judge.md"
    judge.write_text(judge.read_text(encoding="utf-8") + "\n## 칸 분류 확인\n- 알릴 것 → 정한 것 | 알릴 줄 하나 | 옮김\n", encoding="utf-8")
    b = screen.build(str(run_dir.path), "T001")
    assert b["move_failed"] and "알릴 줄 하나" in b["screen"]["알릴 것"]


def test_answers_moved_by_the_script_carry_the_mark(run_dir):
    t = {"started_version": "1.3.0"}
    assert screen.decided_lines(t, ["- 판정 기준을 답대로 고침(1)", "- ◇ 이미 있음"]) == ["- ◇ 판정 기준을 답대로 고침(1)", "- ◇ 이미 있음"]
    assert screen.decided_lines({"started_version": "1.2.1"}, ["- x"]) == ["- x"]


def test_answer_criterion_names_both_cells():
    assert "「정한 것」" in lib.ANSWER_CRITERION and "「답하신 것의 반영」" in lib.ANSWER_CRITERION
    old = {"_sections": {"판정 기준": "1. " + lib.OLD_ANSWER_CRITERION}}
    new = {"_sections": {"판정 기준": "1. " + lib.ANSWER_CRITERION}}
    assert lib.answer_is_judged(old) and lib.answer_is_judged(new)


def test_changed_note_goes_up_to_decide(run_dir):
    """목적 시험 2회차 T051: `--skip-db` 없앰(10-29 답과 다름)을 「알릴 것」에 [성질: 앞 판단과 다름]으로 두어 묻지 않고 지나갈 뻔했다."""
    notify = '- `--skip-db`를 없앤다 [성질: 앞 판단과 다름]\n  - 문구는 알림 2\n- 버튼 색 [성질: 없음]\n'
    b = design(run_dir, result(notify=notify))
    decide = b["screen"]["정해 주실 것"]
    assert decide.startswith("- [앞 결정을 바꿈] `--skip-db`를 없앤다") and "문구는 알림 2" in decide
    assert "skip-db" not in b["screen"]["알릴 것"] and "버튼 색" in b["screen"]["알릴 것"]
    assert any("바뀌는 앞 답" in x and "알릴 것" in x for x in b["sources"]) and not b["notify_ok"]
    sourced = notify.replace("[성질: 앞 판단과 다름]", '[성질: 앞 판단과 다름] | 바뀌는 앞 답: 2026-10-29 "운영에도 허용"')
    b = design(run_dir, result(notify=sourced))
    assert not any("알릴 것" in x for x in b["sources"])


def test_changed_decision_in_the_map_goes_up_when_not_asked(run_dir):
    """목적 시험 2회차 T051: DG-9(`--skip-db` 없앰)가 결정 지도에만 [성질: 앞 판단과 다름]이고 화면에서는 묻지 않았다."""
    text = result(notify="- `--skip-db`를 주면 종료 코드 2 [성질: 없음]\n") + (
        "\n## 결정 지도\n- DG-9 `--skip-db`를 없앰 [담당 ✔] [성질: 앞 판단과 다름]\n- DG-10 기록 형식 4 [담당 ✔] [성질: 밖]\n")
    b = design(run_dir, text)
    decide = b["screen"]["정해 주실 것"]
    assert decide.startswith("- [앞 결정을 바꿈] DG-9 `--skip-db`를 없앰") and "DG-10" not in decide
    assert any("결정 지도" in x and "DG-9" in x for x in b["sources"]) and not b["notify_ok"]
    asked = text.replace("### 정해 주실 것\n- 없음", '### 정해 주실 것\n- DG-9 옵션을 없앨지: (가) 없앰 / (나) 둠 [성질: 앞 판단과 다름] | 바뀌는 앞 답: 2026-10-29 "운영에도 허용"')
    b = design(run_dir, asked)
    assert not any("결정 지도" in x for x in b["sources"]) and b["screen"]["정해 주실 것"].count("DG-9") == 1

    noted = text.replace("### 알릴 것\n", "### 알릴 것\n- DG-9은 10-29 답의 운영 몫을 다시 정한 것이 아니라 표시가 잘못됨 [성질: 없음]\n", 1)
    b = design(run_dir, noted)
    assert not any("결정 지도" in x for x in b["sources"])
