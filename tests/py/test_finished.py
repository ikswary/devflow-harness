"""1.2.0의 "끝남" 판정(설계 8.3절)과 판본 문턱.

- 상태 `보류`는 먼저 보아 끝으로 친다. 치운 변경이 남아도 같다.
- 그 밖에 넣기·정책 대기·치움 표지가 있는 task는 끝나지 않은 것으로 센다.
- 의존 판정은 표지가 없는 `완료`만 끝으로 본다. 표지가 없는 옛 task는 지금과 같다.
"""
import pytest

import board


def task(tid, status, **meta):
    return dict({"id": tid, "kind": "implementation", "status": status, "parent": "", "depends_on": []}, **meta)


@pytest.mark.parametrize("status", ["완료", "보류", "백로그"])
def test_ga_closed_status_without_marks_is_settled(lib, status):
    t = task("T1", status)
    assert lib.settled(t, {"T1": t}) is True


@pytest.mark.parametrize("key", ["insert_pending", "insert_failed", "waiting_policy", "parked"])
def test_na_done_with_mark_is_not_settled(lib, key):
    t = task("T1", "완료", **{key: "T9"})
    assert lib.settled(t, {"T1": t}) is False


@pytest.mark.parametrize("key", ["insert_pending", "insert_failed", "waiting_policy", "parked"])
def test_da_hold_comes_first_even_with_mark(lib, key):
    t = task("T1", "보류", **{key: "T9"})
    assert lib.settled(t, {"T1": t}) is True


def test_ra_waiting_task_blocked_by_hold_with_mark_is_not_settled(lib):
    hold = task("T1", "보류")
    wait = task("T2", "대기", depends_on=["T1"], waiting_policy="T5")
    tasks = {"T1": hold, "T2": wait}
    assert lib.settled(wait, tasks) is False


def test_ma_waiting_task_blocked_by_hold_stays_settled(lib):
    hold = task("T1", "보류")
    wait = task("T2", "대기", depends_on=["T1"])
    tasks = {"T1": hold, "T2": wait}
    assert lib.settled(wait, tasks) is True


def test_ba_blank_mark_counts_as_no_mark(lib):
    t = task("T1", "완료", insert_failed="  ")
    assert lib.settled(t, {"T1": t}) is True
    assert lib.dependency_done(t) is True


@pytest.mark.parametrize("status,mark,want", [
    ("완료", {}, True),
    ("완료", {"insert_failed": "T9"}, False),
    ("완료", {"insert_pending": "1"}, False),
    ("보류", {}, False),
    ("백로그", {}, False),
    ("진행", {}, False),
])
def test_sa_dependency_done(lib, status, mark, want):
    assert lib.dependency_done(task("T1", status, **mark)) is want


def test_a_board_does_not_start_a_task_on_a_failed_insert():
    dep = task("T1", "완료", insert_failed="T9")
    t = task("T2", "대기", depends_on=["T1"])
    assert board.is_ready({"T1": dep, "T2": t}, t) is False


def test_ja_board_starts_a_task_on_a_plain_done():
    dep = task("T1", "완료")
    t = task("T2", "대기", depends_on=["T1"])
    assert board.is_ready({"T1": dep, "T2": t}, t) is True


def test_cha_flow_verify_waits_for_a_parked_dependency():
    dep = task("T1", "완료", parked="parked.patch")
    t = task("T2", "대기", kind="flow-verify", depends_on=["T1"])
    assert board.is_ready({"T1": dep, "T2": t}, t) is False


def test_pa_flow_with_a_marked_backlog_task_is_not_done():
    plain = {"T1": task("T1", "백로그", flow="a")}
    marked = {"T1": task("T1", "백로그", flow="a", parked="parked.patch")}
    assert board.flow_done(plain, "a", {"status": "진행"}, set()) is True
    assert board.flow_done(marked, "a", {"status": "진행"}, set()) is False


@pytest.mark.parametrize("mark,want", [({}, ["a"]), ({"insert_failed": "T9"}, [])])
def test_ta_flow_with_a_marked_flow_verify_is_not_mergeable(lib, monkeypatch, mark, want):
    monkeypatch.setattr(lib, "run_meta", lambda run_dir: {"integration_branch": "harness/통합"})
    tasks = {"T1": task("T1", "완료", kind="flow-verify", flow="a", **mark)}
    flows = {"a": {"status": "진행", "role": "feature", "depends_on_flows": []}}
    assert board.mergeable_flows(tasks, flows, "실행", set()) == want


@pytest.mark.parametrize("value,want", [
    ("1.2.0", True),
    ("1.2.0-dev.1", True),
    ("1.2.1", True),
    ("1.1.1", False),
    ("", False),
    ("개발", False),
])
def test_ka_rules_v120_threshold(lib, value, want):
    assert lib.version_at_least(value, lib.RULES_V120) is want
