"""1.3.0 C: 결과 파일 「전제」와 막아 세우는 전제(구현 설계 2절 C, 7판 규칙 3.1).

- 줄 꼴: `- 전{n} {물음} | 막아 세움: 예/아니오 | 답: {답 꼴} | 기대는 것: {…}`, 막아 세우지 않으면 `모르면:`(가정), 기한 있는 일은 `기한:`.
- 막아 세우는 전제는 화면의 「정해 주실 것」 맨 위 `[전제 전{n}]`로 오른다. 답(`전1 됨`, `전1 예`)이 「승인 기록」에 오면 내려간다.
- 막아 세우는 전제에 긍정 답이 오기 전에는 그 task의 자손 task가 시작하지 않는다(`지금 해 보겠음`·`안 됨`·답 없음).
  상태는 머리 파일 키로 두지 않고 「승인 기록」의 답에서 계산한다(답과 키가 어긋나지 않게).
- 막아 세우지 않는 기한 있는 일은 「알릴 것」에 `[기한]` 줄로 간다.
"""
from datetime import datetime

import devflow_lib as lib
import screen
from conftest import run_script

V130 = {"started_version": "1.3.0", "rules": "2"}
PREMISES = ("- 전1 사진 저장소 계정을 지금 만들 수 있는지 해 보시고 알려 주세요 | 막아 세움: 예 | 답: 됨/안 됨/지금 해 보겠음 | 기대는 것: 사진 옮기기 구현\n"
            "- 전2 사진은 하루 100장 이하인가요 | 막아 세움: 아니오 | 모르면: 하루 100장 이하로 가정\n"
            "- 전3 도메인 연장 | 막아 세움: 아니오 | 기한: 2026-12-01 운영 배포 전\n")


def result(premise=PREMISES):
    return ("# 결과\n\n## 승인 화면\n### 전제\n{}\n### 정해 주실 것\n- 없음\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n- 없음\n"
            "### 정한 것\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 없음\n").format(premise)


def judged(run_dir, tid="T001"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge(tid, "판정자: rjudge-{} {}\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n| 기준 | 판정 | 근거 |\n|---|---|---|\n"
                       "| 1 | 통과 | 읽음 |\n\n## 짚음\n- 없음\n\n## 주장-출처 대조\n- 없음\n".format(tid, now))
    run_dir.task_dir(tid).joinpath(lib.FACTS_FILE).write_text("# 사실\n", encoding="utf-8")


def parent(run_dir, records="", status="승인대기"):
    run_dir.task("T001", "설계", {"승인 기록": records}, kind="design", block="설계", status=status, **V130)
    run_dir.result("T001", result())
    judged(run_dir)


def record(when, text):
    return '- {} | 승인 | 승인 | 원문: "{}"\n'.format(when, text)


def test_rows_are_read():
    rows = lib.premise_rows(PREMISES)
    assert [r["n"] for r in rows] == [1, 2, 3]
    assert [r["blocking"] for r in rows] == [True, False, False]
    assert rows[0]["answer"] == "됨/안 됨/지금 해 보겠음" and rows[0]["depends"] == "사진 옮기기 구현"
    assert rows[1]["assume"] == "하루 100장 이하로 가정"
    assert rows[2]["deadline"] == "2026-12-01 운영 배포 전"
    assert all(not r["problem"] for r in rows)


def test_row_problems():
    rows = lib.premise_rows("- 전1 계정 | 답: 됨/안 됨\n- 번호 없는 줄 | 막아 세움: 예\n- 전2 모름 | 막아 세움: 아니오\n"
                            "- 전3 x | 막아 세움: 예 | 답: 있음/없음\n- 전4 y | 막아 세움: 예 | 답: {됨/안 됨/지금 해 보겠음 또는 예/아니오}\n"
                            "- 전5 z | 막아 세움: 아니오 | 모르면: a\n- 전5 w | 막아 세움: 아니오 | 모르면: b\n- 전0 v | 막아 세움: 아니오 | 모르면: c\n")
    # 막아 세움 없음, 번호 없음, 모르면 없음, 답 꼴 밖, 견본 그대로, 셋을 넘음(꼴은 정상), 번호 겹침, 번호 0
    assert [bool(r["problem"]) for r in rows] == [True, True, True, True, True, True, True, True]
    assert "셋을 넘음" in rows[5]["problem"] and "전5" in rows[5]["problem"]


FOURTH = "- 전4 사진 크기 제한이 있나요 | 막아 세움: 아니오 | 모르면: 제한 없음으로 가정\n"


def test_fourth_premise_is_over_the_cap():
    """「전제」는 셋 이내(formats/screen-cells.md). 넷째 줄부터 꼴 문제, 셋이면 없음."""
    assert lib.PREMISE_CAP == 3
    rows = lib.premise_rows(PREMISES + FOURTH)
    assert [r["n"] for r in rows] == [1, 2, 3, 4]
    assert [r["problem"] for r in rows[:3]] == ["", "", ""]
    assert rows[3]["problem"] == "「전제」가 셋을 넘음(전4. screen-cells 「전제와 정한 것」)"
    assert all(not r["problem"] for r in lib.premise_rows(PREMISES))


def test_fourth_premise_warns_on_the_screen(run_dir):
    run_dir.task("T001", "설계", kind="design", block="설계", status="승인대기", **V130)
    run_dir.result("T001", result(PREMISES + FOURTH))
    judged(run_dir)
    out = run_script("screen", run_dir.path, "T001").stdout
    warn = [l for l in out.splitlines() if l.startswith("! 정한 것·전제의 꼴")]
    assert len(warn) == 1 and "셋을 넘음(전4." in warn[0]
    run_dir.result("T001", result(PREMISES))
    out = run_script("screen", run_dir.path, "T001").stdout
    assert "! 정한 것·전제의 꼴" not in out and "[전제 전1]" in out   # 같은 화면, 셋이면 경고 없음


def test_blocking_premise_is_asked_first(run_dir):
    parent(run_dir)
    b = screen.build(str(run_dir.path), "T001")
    first = b["screen"]["정해 주실 것"].splitlines()[0]
    assert first.startswith("- [전제 전1] 사진 저장소 계정을") and "답: 전1 됨 / 전1 안 됨 / 전1 지금 해 보겠음" in first
    # 막아 세우지 않는 가정 전제도 사람에게 묻는다(답이 없으면 가정으로 진행. D 리뷰 5)
    assert "- [가정] 전2 사진은 하루 100장 이하인가요 — 답이 없으면 「하루 100장 이하로 가정」로 진행합니다" in b["screen"]["정해 주실 것"]
    assert "- [기한] 2026-12-01 운영 배포 전: 도메인 연장" in b["screen"]["알릴 것"]
    assert "[가정]" not in b["screen"]["알릴 것"]
    assert b["counts"]["n_decide"] == 2


def test_open_premises_follow_the_answers(run_dir):
    parent(run_dir)
    assert lib.premise_open(run_dir.tasks()["T001"]) == [(1, "답 없음")]
    parent(run_dir, record("2026-11-16 10:00:00", "전1 지금 해 보겠음, 진행"))
    assert lib.premise_open(run_dir.tasks()["T001"]) == [(1, "지금 해 보겠음")]
    parent(run_dir, record("2026-11-16 10:00:00", "전1 지금 해 보겠음, 진행") + record("2026-11-16 11:00:00", "전1 됨"))
    assert lib.premise_open(run_dir.tasks()["T001"]) == []
    parent(run_dir, record("2026-11-16 10:00:00", "전1 안 됨"))
    assert lib.premise_open(run_dir.tasks()["T001"]) == [(1, "안 됨")]


def test_answered_premise_leaves_the_screen(run_dir):
    parent(run_dir, record("2026-11-16 11:00:00", "전1 됨"))
    assert "[전제 전1]" not in screen.build(str(run_dir.path), "T001")["screen"]["정해 주실 것"]


def test_descendants_wait_for_a_blocking_premise(run_dir):
    parent(run_dir, record("2026-11-16 10:00:00", "전1 지금 해 보겠음, 진행"), status="완료")
    run_dir.task("T002", "구현", kind="implementation", block="구현", status="대기", parent="T001", flow="a")
    run_dir.task("T003", "검증", kind="flow-verify", block="검증", status="대기", parent="T002", flow="a")
    run_dir.flow("a")
    for tid in ("T002", "T003"):
        p = run_script("task_set", run_dir.path, tid, "--status", "진행")
        assert p.returncode != 0 and "T001" in p.output and "전1" in p.output, p.output


def test_recorded_answer_on_a_closed_task_releases_the_wait(run_dir):
    parent(run_dir, record("2026-11-16 10:00:00", "전1 지금 해 보겠음, 진행"), status="완료")
    p = run_script("task_set", run_dir.path, "T001", "--record", "전제|전1 됨|전1 됨")
    assert p.returncode == 0, p.output
    assert lib.premise_open(run_dir.tasks()["T001"]) == []


def test_old_tasks_have_no_premises(run_dir):
    run_dir.task("T001", "설계", kind="design", block="설계", status="완료", started_version="1.2.1", rules="2")
    run_dir.result("T001", result())
    assert lib.premise_open(run_dir.tasks()["T001"]) == []



def test_answer_variants_and_other_tasks(run_dir):
    def opened(records):
        parent(run_dir, records)
        return lib.premise_open(run_dir.tasks()["T001"])
    stamp = "2026-11-16 10:00:00"
    for text in ("전1 됨.", "전1 됨 진행", "전1 예 (방금 만듦)", "전1: 됨", "전1됨", "T001 전1 됨"):
        assert opened(record(stamp, text)) == [], text
    assert opened(record(stamp, "T013 전1 됨")) == [(1, "답 없음")]
    mixed = '- {} | 승인 | 진행 | 원문: "전1 안 됨" | 원문 메시지: "T013 전1 안 됨 / 전1 됨"\n'.format(stamp)
    assert opened(mixed) == [(1, "안 됨")]
    quoted = '- {} | 승인 | 승인 | 원문: "전1 됨" | 원문 메시지: "전1 됨 / T013 진행"\n'.format(stamp)
    assert opened(quoted) == []
    assert opened(record(stamp, "전1 안 됨") + record("2026-11-16 11:00:00", "전1 철회")) == []


def test_an_answer_does_not_follow_a_renumbered_premise(run_dir):
    parent(run_dir, '- 2026-11-16 10:00:00 | 승인 | 승인 | 원문: "전1 됨" | 전제 문장: 1=결제 수단을 등록할 수 있는지\n')
    assert lib.premise_open(run_dir.tasks()["T001"]) == [(1, "답 없음(전제가 바뀜)")]
    parent(run_dir, '- 2026-11-16 10:00:00 | 승인 | 승인 | 원문: "전1 됨" | 전제 문장: 1=사진 저장소 계정을 지금 만들 수\n')
    assert lib.premise_open(run_dir.tasks()["T001"]) == []


def test_record_keeps_the_premise_text(run_dir):
    parent(run_dir, record("2026-11-16 10:00:00", "전1 지금 해 보겠음, 진행"), status="완료")
    assert run_script("task_set", run_dir.path, "T001", "--record", "전제|전1 됨|전1 됨").returncode == 0
    assert "전제 문장: 1=사진 저장소 계정을 지금 만들 수" in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")


def test_dependents_wait_too_and_the_board_knows(run_dir):
    import board
    parent(run_dir, record("2026-11-16 10:00:00", "전1 지금 해 보겠음, 진행"), status="완료")
    run_dir.task("T002", "설계", kind="design", block="설계", status="대기", depends_on=["T001"])
    run_dir.task("T003", "다른 일", kind="design", block="설계", status="대기")
    p = run_script("task_set", run_dir.path, "T002", "--status", "진행")
    assert p.returncode != 0 and "T001 전1" in p.output
    tasks = run_dir.tasks()
    assert not board.is_ready(tasks, tasks["T002"]) and board.is_ready(tasks, tasks["T003"])


def test_screen_answer_takes_premise_answers(run_dir):
    parent(run_dir)
    shown = run_script("screen", run_dir.path, "T001", "--save")
    assert shown.returncode == 0, shown.output
    p = run_script("screen", run_dir.path, "T001", "--answer", "전1 됨")
    assert p.returncode == 0 and "전제: 전1 됨" in p.output, p.output
    assert run_script("screen", run_dir.path, "T001", "--answer", "전9 됨").returncode == 3


def test_premise_cell_is_not_shown_as_a_cell(run_dir):
    parent(run_dir)
    shown = run_script("screen", run_dir.path, "T001").stdout
    assert "■ 전제" not in shown and "[전제 전1]" in shown
