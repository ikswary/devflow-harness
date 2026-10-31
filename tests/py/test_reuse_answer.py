"""승인 답 재사용 거부(B-4, 설계 B 3.5): `task_set.py --record`·`--reuse-answer`, `exec.approval_time`, `devflow_lib.short_answer`.

- 명령행 사례는 종료 코드와 머리 파일 내용을 단언한다. 거부면 머리 파일이 호출 전과 바이트까지 같다.
- task A(T001)는 더 이른 승인 줄을 가진 다른 task, task B(T002)는 지금 승인을 적는 task다.
"""
from datetime import datetime

import exec as execmod
from conftest import run_script

ELEVEN = "가나다라마 바사아자차카"       # 괄호·공백을 뺀 11글자: 견줌
TEN = "가나다라마 바사아자차 (Recommended)"   # 괄호·공백을 뺀 10글자: 한 마디 답이라 견주지 않음
A_TIME = "2026-10-30 09:00:00"
B_REQUESTED = "2026-10-30 10:00:00"
NEW = {"started_version": "1.1.0", "rules": "2"}


def approved_line(stamp, text, point="승인", decision="승인"):
    return '- {} | {} | {} | 원문: "{}"'.format(stamp, point, decision, text)


def setup(run_dir, a_text=ELEVEN, a_time=A_TIME, b_records="", **b_meta):
    run_dir.task("T001", "앞 task", {"승인 기록": approved_line(a_time, a_text)}, status="완료", **NEW)
    meta = dict(NEW, status="승인대기", approval_requested=B_REQUESTED)
    meta.update(b_meta)
    meta = {k: v for k, v in meta.items() if v is not None}
    return run_dir.task("T002", "지금 task", {"승인 기록": b_records}, **meta)


def record(run_dir, text, *extra, point="승인"):
    return run_script("task_set", run_dir, "T002", "--record", "{}|승인|{}".format(point, text), *extra)


def records(path):
    text = path.read_text(encoding="utf-8")
    return [l for l in text.split("## 승인 기록", 1)[1].splitlines() if l.startswith("- ")]


def assert_rejected_unchanged(proc, path, before):
    assert proc.returncode == 3, proc.output
    assert path.read_bytes() == before


def test_same_long_answer_from_other_task_is_rejected(run_dir):   # (가)
    path = setup(run_dir)
    before = path.read_bytes()
    proc = record(run_dir, ELEVEN)
    assert_rejected_unchanged(proc, path, before)
    assert "같은 원문 재사용: T001 {}".format(A_TIME) in proc.output


def test_answer_differing_only_in_spacing_is_rejected(run_dir):   # (나)
    path = setup(run_dir)
    before = path.read_bytes()
    proc = record(run_dir, "가나다라마   바사아자차카")
    assert_rejected_unchanged(proc, path, before)
    assert "같은 원문 재사용: T001 {}".format(A_TIME) in proc.output


def test_short_answers_are_not_compared(run_dir):   # (다) 경계: 10글자는 통과, 11글자는 (가)
    for text in ("승인 (Recommended)", TEN):
        path = setup(run_dir, a_text=text)
        proc = record(run_dir, text)
        assert proc.returncode == 0, proc.output
        assert records(path)[-1].endswith('| 승인 | 승인 | 원문: "{}"'.format(text))


def test_reuse_answer_records_reason_and_unlisted_line(run_dir):   # (라)
    path = setup(run_dir)
    proc = record(run_dir, ELEVEN, "--reuse-answer", "같은 답을 다시 씀")
    assert proc.returncode == 0, proc.output
    last = records(path)[-1]
    assert last.endswith('원문: "{}" | 재사용 답: 같은 답을 다시 씀'.format(ELEVEN))
    head = path.read_text(encoding="utf-8")
    unlisted = head.split("## 표 밖 전이", 1)[1].split("## 승인 기록", 1)[0]
    assert "| 재사용 답 | 같은 답을 다시 씀 (같은 원문: T001 {})".format(A_TIME) in unlisted
    journal = (run_dir.path / "journal.md").read_text(encoding="utf-8")
    assert "| 재사용 답 | T002 | 같은 답을 다시 씀 (같은 원문: T001 {})".format(A_TIME) in journal


def test_earliest_line_among_other_tasks_is_reported(run_dir):   # (타) 같은 원문이 둘이면 더 이른 쪽
    path = setup(run_dir)
    later = "2026-10-30 09:30:00"
    run_dir.task("T003", "또 다른 task", {"승인 기록": approved_line(later, ELEVEN)}, status="완료", **NEW)
    before = path.read_bytes()
    proc = record(run_dir, ELEVEN)
    assert_rejected_unchanged(proc, path, before)
    assert "같은 원문 재사용: T001 {}".format(A_TIME) in proc.output
    assert "T003" not in proc.output


def test_reuse_answer_without_same_line_records_plain_line(run_dir):   # (파) 재사용이 아니면 --reuse-answer는 흔적을 남기지 않음
    path = setup(run_dir, a_text="전혀 다른 앞 답입니다 길게")
    proc = record(run_dir, ELEVEN, "--reuse-answer", "같은 답을 다시 씀")
    assert proc.returncode == 0, proc.output
    last = records(path)[-1]
    assert last.endswith('| 승인 | 승인 | 원문: "{}"'.format(ELEVEN))
    assert "재사용 답:" not in last
    assert "## 표 밖 전이" not in path.read_text(encoding="utf-8")


def test_task_started_before_1_1_0_is_not_checked(run_dir):   # (마)
    path = setup(run_dir, started_version="1.0.4")
    proc = record(run_dir, ELEVEN)
    assert proc.returncode == 0, proc.output
    assert records(path)[-1].endswith('원문: "{}"'.format(ELEVEN))


def test_other_line_later_than_request_is_not_compared(run_dir):   # (바) 앞 절반
    path = setup(run_dir, a_time="2026-10-30 10:00:01")
    proc = record(run_dir, ELEVEN)
    assert proc.returncode == 0, proc.output
    assert records(path)[-1].endswith('원문: "{}"'.format(ELEVEN))


def test_without_approval_requested_now_is_the_base(run_dir):   # (바) 뒤 절반
    path = setup(run_dir, approval_requested=None)
    assert "approval_requested" not in path.read_text(encoding="utf-8")
    before = path.read_bytes()
    proc = record(run_dir, ELEVEN)
    assert_rejected_unchanged(proc, path, before)
    assert "같은 원문 재사용: T001 {}".format(A_TIME) in proc.output


def test_same_answer_on_own_earlier_line_is_not_reuse(run_dir):   # (사)
    run_dir.task("T001", "앞 task", {"승인 기록": approved_line(A_TIME, "다른 답 다른 답 다른 답")}, status="완료", **NEW)
    path = run_dir.task("T002", "지금 task", {"승인 기록": approved_line(A_TIME, ELEVEN)},
                        status="승인대기", approval_requested=B_REQUESTED, **NEW)
    proc = record(run_dir, ELEVEN)
    assert proc.returncode == 0, proc.output
    assert len(records(path)) == 2 and records(path)[-1].endswith('원문: "{}"'.format(ELEVEN))


def test_answer_point_is_not_an_approval_line(run_dir):   # (아)
    path = setup(run_dir)
    proc = run_script("task_set", run_dir, "T002", "--record", "답|D-7 고름|" + ELEVEN)
    assert proc.returncode == 0, proc.output
    assert records(path)[-1].endswith('| 답 | D-7 고름 | 원문: "{}"'.format(ELEVEN))


def test_other_task_answer_line_is_not_compared(run_dir):   # (아)의 짝: 견주는 쪽도 승인 줄만
    run_dir.task("T001", "앞 task", {"승인 기록": approved_line(A_TIME, ELEVEN, point="답", decision="D-7 고름")},
                 status="완료", **NEW)
    path = run_dir.task("T002", "지금 task", {"승인 기록": ""}, status="승인대기", approval_requested=B_REQUESTED, **NEW)
    proc = record(run_dir, ELEVEN)
    assert proc.returncode == 0, proc.output
    assert records(path)[-1].endswith('| 승인 | 승인 | 원문: "{}"'.format(ELEVEN))


def test_reuse_answer_without_record_is_rejected(run_dir):   # (자)
    path = setup(run_dir)
    before = path.read_bytes()
    proc = run_script("task_set", run_dir, "T002", "--reuse-answer", "같은 답을 다시 씀")
    assert_rejected_unchanged(proc, path, before)
    assert "--reuse-answer는 --record와 함께" in proc.output


def test_approval_time_skips_reused_answer_line(run_dir):   # (차)
    reused = approved_line("2026-10-30 10:05:00", ELEVEN) + " | 재사용 답: 같은 답을 다시 씀"
    run_dir.task("T002", "지금 task", {"승인 기록": reused}, status="승인대기", approval_requested=B_REQUESTED, **NEW)
    assert execmod.approval_time(run_dir.tasks()["T002"]) is None
    fresh = approved_line("2026-10-30 10:06:00", "새로 받은 답입니다 길게")
    run_dir.task("T002", "지금 task", {"승인 기록": reused + "\n" + fresh}, status="승인대기",
                 approval_requested=B_REQUESTED, **NEW)
    assert execmod.approval_time(run_dir.tasks()["T002"]) == datetime(2026, 10, 30, 10, 6, 0)


def test_short_answer_boundary(lib):   # (카)
    for text in ("ㅇㅋ", "승인 (Recommended)", "A·B·C + 실행 전체 (Recommended)", TEN):
        assert lib.short_answer(text) is True, text
    assert lib.short_answer(ELEVEN) is False
    assert lib.short_answer(ELEVEN + " (Recommended)") is False
