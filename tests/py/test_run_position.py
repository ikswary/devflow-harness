"""1.3.0 D: 경계 보고 머리 칸 `run_position.py`(구현 설계 2절 D, 7판 규칙 4.2).

- 처음 계획은 처음 사람이 승인한 계획 task의 자식이 만들어진 시각까지 있던 task 수다(바뀌지 않는 created에서 계산).
- 늘어난 까닭의 원인별 수의 합은 늘어난 수와 같다. 원인은 사람의 말로 쓴다.
- 지금까지 방향은 decisions.md의 `[방향]` 결정(대체되지 않은 것).
"""
from datetime import datetime

import run_position
from conftest import write


def plan(run_dir):
    run_dir.task("T001", "요구사항", kind="req-overview", status="완료", approval_mode="승인",
                 approved="2026-11-10 10:00:00", created="2026-11-10 09:00:00")
    for i, kind in ((2, "design"), (3, "design")):
        run_dir.task("T00{}".format(i), "설계", kind=kind, status="완료", parent="T001", created="2026-11-10 10:01:00")


def test_first_plan_and_growth(run_dir):
    plan(run_dir)
    run_dir.task("T004", "수정", kind="fix", status="대기", parent="T003", created="2026-11-12 09:00:00")
    run_dir.task("T005", "수정", kind="fix", status="대기", parent="T003", created="2026-11-12 09:00:00")
    run_dir.task("T006", "바꿈", kind="implementation", status="대기", origin="사용자 답 T003", created="2026-11-13 09:00:00")
    run_dir.task("T007", "새 일", kind="implementation", status="완료", parent="T002", created="2026-11-13 09:00:00")
    run_dir.task("T008", "나중", kind="implementation", status="백로그", created="2026-11-13 09:00:00")
    tasks = run_dir.tasks()
    assert run_position.first_plan(tasks)[0] == 3
    causes = dict(run_position.growth(tasks, run_position.first_plan(tasks)[1]))
    assert causes == {"확인에서 나온 수정": 2, "답하신 것으로 생긴 일": 1, "「설계」에서 나온 일": 1}
    lines = run_position.head_lines(str(run_dir.path), tasks, today=datetime(2026, 11, 16))
    assert lines[0].startswith("실행 위치") and "task 7개 · 7일째 · 배포 0회" in lines[0]
    assert "남은 일 3개" in lines[1]
    assert any("처음 계획 3개 → 지금 7개" in l for l in lines)
    assert sum(int(l.rsplit("+", 1)[1]) for l in lines if l.strip().endswith(tuple("0123456789")) and "+" in l) == 4
    assert not any("T00" in l for l in lines)


def test_no_growth_line_when_the_plan_holds(run_dir):
    plan(run_dir)
    lines = run_position.head_lines(str(run_dir.path), run_dir.tasks(), today=datetime(2026, 11, 10))
    assert not any("늘어난 까닭" in l for l in lines) and "1일째" in lines[0]


def test_unapproved_plan_is_not_the_first_plan(run_dir):
    plan(run_dir)
    run_dir.task("T001", "요구사항", kind="req-overview", status="완료", approval_mode="알림",
                 approved="2026-11-10 10:00:00", created="2026-11-10 09:00:00")
    assert run_position.first_plan(run_dir.tasks()) == (None, None)


def test_directions_come_from_decisions(run_dir):
    plan(run_dir)
    write(run_dir.path / "decisions.md",
          '- 2026-11-11 10:00:00 | [방향] 사진 저장을 R2에서 Supabase로 (버림: R2 요금) | 원문: "supabase로 가자" | T002\n'
          '- 2026-11-11 11:00:00 | 기준선 질문 x T002 | 원문: "" | T002\n'
          '- 2026-11-12 10:00:00 | [방향] 옛 방향 → 대체: 2026-11-13 | 원문: "x" | T002\n')
    lines = run_position.head_lines(str(run_dir.path), run_dir.tasks(), today=datetime(2026, 11, 12))
    i = lines.index("지금까지 방향")
    assert lines[i + 1].strip() == '2026-11-11 사진 저장을 R2에서 Supabase로 (버림: R2 요금) ("supabase로 가자")'
    assert len(lines) == i + 2


def test_items_wrap_at_three_per_line():
    assert run_position._rows("가", ["a", "b", "c", "d"], cols=12) == ["가" + " " * 10 + "a · b · c", " " * 12 + "d"]
    assert run_position.width("실행 위치") == 9


def test_growth_shows_three_causes_and_folds_the_rest(run_dir):
    """목적 시험 T051: 원인 12줄이 머리 칸을 넘겼다. 큰 셋과 「그 밖」 한 줄, 합계는 그대로."""
    plan(run_dir)
    for i, title in ((4, "사진 설계"), (5, "배포 설계"), (6, "검사 설계")):
        run_dir.task("T00{}".format(i), title, kind="design", status="완료", created="2026-11-11 09:00:00")
    n = 7
    for parent, count in (("T004", 3), ("T005", 2), ("T006", 2)):
        for _ in range(count):
            run_dir.task("T{:03d}".format(n), "나눈 일", kind="implementation", status="대기", parent=parent,
                         created="2026-11-12 09:00:00")
            n += 1
    for kind in ("fix", "probe"):
        run_dir.task("T{:03d}".format(n), "더함", kind=kind, status="대기", created="2026-11-12 09:00:00")
        n += 1
    lines = run_position.head_lines(str(run_dir.path), run_dir.tasks(), today=datetime(2026, 11, 16))
    causes = [l for l in lines if l.startswith(" " * run_position.WIDTH) and "+" in l]
    assert len(causes) == 4 and causes[-1].strip().startswith("그 밖 3가지 +4"), lines
    assert sum(int(l.rsplit("+", 1)[1]) for l in causes) == 15 - 3   # 지금 15개 - 처음 계획 3개



def test_command_line_prints_head_and_growth(run_dir):
    from conftest import run_script
    plan(run_dir)
    for i in range(4, 9):
        run_dir.task("T00{}".format(i), "수정", kind="fix", status="대기", parent="T003", created="2026-11-12 09:00:00")
    p = run_script("run_position", run_dir.path)
    assert p.returncode == 0, p.output
    assert p.stdout.splitlines()[0].startswith("실행 위치") and "늘어남: 확인에서 나온 수정 +5개가 처음 계획 3개보다 큽니다" in p.stdout
