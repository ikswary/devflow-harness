"""1.2.0: 재지 못한 코드 task(사용자 결정). 메인이 기록을 고쳐 다시 재고, 그래도 못 재면 사람에게 묻는다. 보안 신호와 시험 변화가 같다.

- 원인은 `커밋 값 없음`, `코드 폴더 없음`, `git 실패`로 나눠 `places.md`와 화면에 적는다.
- `--places --remeasure`는 재지 못한 task만 다시 재어 곳을 더하고, 이미 답한 곳과 키를 바꾸지 않는다.
- 재지 못함이 남으면 흐름별 검증이 완료되지 않고, 답은 task마다 한 번이다. `보류`는 받는다.
"""
import pytest

import devflow_lib as lib
import flow_review
import places
import screen
from conftest import run_script, write
from test_code_check import BODY, FV, code, commit, complete, git, make_places, repo, verify, waiting  # noqa: F401
from test_review_contract import OLD
from test_test_changes import SKIPPED

SECRET = "const password = read();\n"
TOUCH = {"건드릴 파일": "- src/a.ts\n- src/b.ts"}


def measured(run_dir, tid="T001"):
    """시험 변화는 잰 것으로 둔다. 보안 신호만 보는 장면이 쓴다."""
    write(run_dir.task_dir(tid) / lib.TEST_CHANGES, "기준: abc\n- 없음\n")


def task(run_dir, sha="", judgments="- 없음\n", tid="T001", test_measured=True, **more):
    code(run_dir, tid, judgments, sha=sha, sections=TOUCH, **more)
    if test_measured:
        measured(run_dir, tid)
    else:
        (run_dir.task_dir(tid) / lib.TEST_CHANGES).unlink(missing_ok=True)


def remeasure(run_dir, *more):
    p = run_script("screen", run_dir.path, FV, "--places", "--remeasure", *more)
    assert p.returncode == 0, p.output
    return p.stdout


def set_keys(run_dir, tid="T001", *pairs):
    p = run_script("task_set", run_dir.path, tid, *pairs)
    assert p.returncode == 0, p.output


def answer(run_dir, tid="T001", text="그 코드는 안 봐도 됩니다"):
    return run_script("task_set", run_dir.path, FV, "--record", "코드 확인 재지 못함 {}|합쳐도 됨|{}".format(tid, text))


def screen_text(run_dir):
    return run_script("screen", run_dir.path, FV).stdout


def head(run_dir):
    return (run_dir.task_dir(FV) / "places.md").read_text(encoding="utf-8").split("\n## ")[0]


# ---------------------------------------------------------------- 원인


def test_empty_commit_cause(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    assert "- 재지 못함 이유: T001 | 커밋 값 없음" in head(run_dir)
    assert "T001(커밋 값 없음)" in screen_text(run_dir)


def test_missing_folder_cause(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": SECRET}))
    verify(run_dir)
    make_places(run_dir)
    assert "- 재지 못함 이유: T001 | 코드 폴더 없음" in head(run_dir)
    assert "T001(코드 폴더 없음)" in screen_text(run_dir)


def test_git_failure_cause(run_dir, repo):
    task(run_dir, "abcdef1")
    verify(run_dir, repo)
    make_places(run_dir)
    assert "- 재지 못함 이유: T001 | git 실패" in head(run_dir)
    assert "T001(git 실패)" in screen_text(run_dir)


# ---------------------------------------------------------------- 다시 재기


def test_fixing_the_commit_and_remeasuring_makes_the_place(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    got = places.read(str(run_dir.path), FV)
    assert [p["파일"] for p in got] == [["src/a.ts"]] and got[0]["처리"] == places.WAITING and got[0]["카드"] == "1"
    assert "- 재지 못함: 없음" in head(run_dir) and "재지 못함 이유" not in head(run_dir)
    waiting(run_dir)
    assert got[0]["key"] in complete(run_dir).output


def test_remeasuring_keeps_answered_places_and_keys(run_dir, repo):
    sha = commit(repo, {"src/ok.ts": BODY})
    code(run_dir, "T002", "- 판단 [종류: 구조] [위치: src/ok.ts:3]\n", sha=sha)
    measured(run_dir, "T002")
    task(run_dir)
    verify(run_dir, repo)
    first = make_places(run_dir)
    waiting(run_dir)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|1".format(first[0]["key"]))
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    after = places.read(str(run_dir.path), FV)
    kept = places.find(after, first[0]["key"])
    assert kept["처리"] == places.ANSWERED and kept["답"] == "문제 없음" and kept["카드"] == first[0]["카드"]
    new = [p for p in after if p["key"] != first[0]["key"]]
    assert len(new) == 1 and new[0]["카드"] == "2" and new[0]["처리"] == places.WAITING


def test_only_unmeasured_tasks_are_measured_again(run_dir, repo):
    sha = commit(repo, {"src/ok.ts": BODY})
    code(run_dir, "T002", "- 없음\n", sha=sha)
    measured(run_dir, "T002")
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    # 커밋이 그대로인 task는 고정 뒤에 판단이 늘어도 다시 재지 않는다
    code(run_dir, "T002", "- 판단 [종류: 구조] [위치: src/ok.ts:3]\n", sha=sha)
    measured(run_dir, "T002")
    remeasure(run_dir)
    assert places.read(str(run_dir.path), FV) == []


def test_remeasuring_twice_adds_nothing(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    once = places.read(str(run_dir.path), FV)
    remeasure(run_dir)
    assert places.read(str(run_dir.path), FV) == once


def test_a_waiting_plain_place_rises_to_security_when_the_signal_appears(run_dir, repo):
    task(run_dir, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    key = make_places(run_dir)[0]["key"]
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    got = places.find(places.read(str(run_dir.path), FV), key)
    assert got["보안"] == "예" and got["처리"] == places.WAITING and got["신호"]


def test_a_place_left_by_the_cap_comes_back_when_the_signal_appears(run_dir, repo):
    sha = commit(repo, {"src/f{}.ts".format(i): BODY for i in range(5)})
    code(run_dir, "T002", "".join("- 판단 [종류: 트랜잭션] [위치: src/f{}.ts:3]\n".format(i) for i in range(5)), sha=sha)
    measured(run_dir, "T002")
    task(run_dir, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    left = next(p for p in make_places(run_dir) if p["task"] == "T001")
    assert left["처리"] == places.LEFT_CAP
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    got = places.find(places.read(str(run_dir.path), FV), left["key"])
    assert got["처리"] == places.WAITING and got["카드"] == "6"


def open_card(run_dir, key):
    assert run_script("task_set", run_dir.path, FV, "--card-open", key).returncode == 0


def place_answer(run_dir, key, decision, text="답합니다"):
    return run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|{}|{}".format(key, decision, text))


def point_flow(run_dir, repo):
    run_dir.flow("reading", dir=str(repo), status="폴더 있음")


def test_remeasuring_gives_a_waiting_place_its_commit_so_the_code_shows(run_dir, repo):
    task(run_dir, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    key = make_places(run_dir)[0]["key"]
    sha = commit(repo, {"src/a.ts": BODY})
    set_keys(run_dir, "T001", "commit=" + sha)
    remeasure(run_dir)
    got = places.find(places.read(str(run_dir.path), FV), key)
    assert got["커밋"] == sha and got["처리"] == places.WAITING and got["보안"] == "아니오"
    waiting(run_dir)
    open_card(run_dir, key)
    shown = run_script("screen", run_dir.path, FV, "--card").stdout
    assert "발췌 못 함" not in shown and "1 문제 없음" in shown
    assert place_answer(run_dir, key, "문제 없음").returncode == 0


def test_a_risen_security_place_shows_its_code(run_dir, repo):
    task(run_dir, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    key = make_places(run_dir)[0]["key"]
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    waiting(run_dir)
    open_card(run_dir, key)
    shown = run_script("screen", run_dir.path, FV, "--card").stdout
    assert "발췌 못 함" not in shown and "password" in shown and "보안 신호" in shown
    assert place_answer(run_dir, key, "문제 없음").returncode == 0


@pytest.mark.parametrize("decision,state", [("나머지 남김", places.LEFT_BULK), ("판단 안 됨 코드 없음", places.LEFT_UNJUDGED)])
def test_a_left_place_rises_when_the_signal_appears(run_dir, repo, decision, state):
    task(run_dir, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    key = make_places(run_dir)[0]["key"]
    waiting(run_dir)
    assert place_answer(run_dir, key, decision).returncode == 0
    assert places.find(places.read(str(run_dir.path), FV), key)["처리"] == state
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    got = places.find(places.read(str(run_dir.path), FV), key)
    assert got["처리"] == places.WAITING and got["보안"] == "예" and got["신호"] and got["답"] == ""
    assert key in complete(run_dir).output
    open_card(run_dir, key)
    assert place_answer(run_dir, key, "문제 없음").returncode == 0
    assert complete(run_dir).returncode == 0


def test_a_left_place_with_no_signal_keeps_the_answer_and_gets_the_commit(run_dir, repo):
    task(run_dir, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    key = make_places(run_dir)[0]["key"]
    waiting(run_dir)
    assert place_answer(run_dir, key, "나머지 남김").returncode == 0
    sha = commit(repo, {"src/a.ts": BODY})
    set_keys(run_dir, "T001", "commit=" + sha)
    remeasure(run_dir)
    got = places.find(places.read(str(run_dir.path), FV), key)
    assert got["처리"] == places.LEFT_BULK and got["커밋"] == sha


def test_a_left_place_rises_at_the_same_commit_when_the_folder_comes_back(run_dir, repo):
    # 폴더가 없어 신호를 못 재던 곳에 받은 `나머지 남김`은 보안 신호에 대한 답이 아니다
    sha = commit(repo, {"src/a.ts": SECRET})
    task(run_dir, sha, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir)
    key = make_places(run_dir)[0]["key"]
    waiting(run_dir)
    assert place_answer(run_dir, key, "나머지 남김").returncode == 0
    point_flow(run_dir, repo)
    remeasure(run_dir)
    got = places.find(places.read(str(run_dir.path), FV), key)
    assert got["처리"] == places.WAITING and got["보안"] == "예"


def test_a_place_answered_after_it_rose_is_not_asked_again_at_the_same_commit(run_dir, repo):
    # 다시 재면 곳을 되돌리지 않고 머리에서도 빠지므로, 같은 커밋의 재측정을 곳 단위로 직접 본다
    task(run_dir, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    key = make_places(run_dir)[0]["key"]
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    waiting(run_dir)
    assert place_answer(run_dir, key, "판단 안 됨 정책을 모름").returncode == 0
    plist = places.read(str(run_dir.path), FV)
    found = places._task_places(str(run_dir.path), run_dir.tasks()["T001"], [], [])
    places._merge_found(plist, found, False, set())
    assert places.find(plist, key)["처리"] == places.LEFT_UNJUDGED


def committed_task(run_dir, repo, text=BODY, judgments="- 없음\n", **more):
    """시험 변화를 진짜 기준 커밋에서 잰 task. 커밋을 바꾼 뒤 시험 변화도 실제로 다시 잰다."""
    base = git(repo, "rev-parse", "HEAD")
    sha = commit(repo, {"src/a.ts": text})
    task(run_dir, sha, judgments, **more)
    write(run_dir.task_dir("T001") / lib.TEST_CHANGES, "{}{}\n- 없음\n".format(lib.TEST_BASE_HEAD, base))
    return sha


def answered_place(run_dir, repo):
    committed_task(run_dir, repo, judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    verify(run_dir, repo)
    key = make_places(run_dir)[0]["key"]
    waiting(run_dir)
    open_card(run_dir, key)
    assert place_answer(run_dir, key, "문제 없음").returncode == 0
    return key


def test_an_answered_place_stays_at_the_same_commit_and_rises_on_another(run_dir, repo):
    key = answered_place(run_dir, repo)
    remeasure(run_dir)
    assert places.find(places.read(str(run_dir.path), FV), key)["처리"] == places.ANSWERED
    other = commit(repo, {"src/a.ts": SECRET})
    set_keys(run_dir, "T001", "commit=" + other)
    remeasure(run_dir)
    got = places.find(places.read(str(run_dir.path), FV), key)
    assert got["처리"] == places.WAITING and got["커밋"] == other and got["답"] == "" and got["보안"] == "예"
    assert key in complete(run_dir).output


def test_an_answered_place_with_no_signal_keeps_the_answer_on_another_commit(run_dir, repo):
    # 보안 밖의 답을 다시 묻지 않는다(사람 질문을 늘리지 않는다)
    key = answered_place(run_dir, repo)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": BODY + "// 고침\n"}))
    remeasure(run_dir)
    assert places.find(places.read(str(run_dir.path), FV), key)["처리"] == places.ANSWERED
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []
    assert complete(run_dir).returncode == 0


def test_no_change_mark_clears_it(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "no_change=true")
    remeasure(run_dir)
    assert "- 재지 못함: 없음" in head(run_dir)
    waiting(run_dir)
    assert complete(run_dir).returncode == 0


def test_remeasure_without_a_file_makes_it(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    remeasure(run_dir)
    assert (run_dir.task_dir(FV) / "places.md").is_file()


def test_test_change_measure_runs_again_for_that_commit_only(run_dir, repo):
    write(repo / "tests" / "a.test.ts", 'it("x", () => {});\n')
    write(repo / "tests" / "b.test.ts", 'it("y", () => {});\n')
    commit(repo, {"keep.txt": "x\n"})
    sha = commit(repo, {"tests/a.test.ts": SKIPPED})
    commit(repo, {"tests/b.test.ts": SKIPPED})   # 뒤 task의 변화는 이 task의 줄이 아니다
    code(run_dir, "T001", "- 없음\n", sha=sha, sections={"건드릴 파일": "- tests/a.test.ts"})
    (run_dir.task_dir("T001") / lib.TEST_CHANGES).unlink()
    verify(run_dir, repo)
    make_places(run_dir)
    tasks = run_dir.tasks()
    assert [r["change"] for r in lib.flow_test_rows(tasks[FV], tasks)] == [lib.TEST_UNMEASURED]
    remeasure(run_dir)
    tasks = run_dir.tasks()
    rows = lib.flow_test_rows(tasks[FV], tasks)
    assert [r["change"] for r in rows] == ["끄기"] and rows[0]["file"] == "tests/a.test.ts"


def test_test_change_measure_failure_says_git_failed(run_dir, repo):
    task(run_dir, "abcdef1", test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    assert "- 재지 못함 이유: T001 | git 실패" in head(run_dir)
    assert not lib.test_changes_measured(run_dir.tasks()["T001"])


def test_empty_commit_does_not_pretend_to_measure_test_changes(run_dir, repo):
    commit(repo, {"src/a.ts": BODY})
    task(run_dir, test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    assert not lib.test_changes_measured(run_dir.tasks()["T001"])


# ---------------------------------------------------------------- 가드와 답


def test_guard_blocks_while_unmeasured_and_the_answer_opens_it(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    waiting(run_dir)
    out = complete(run_dir).output
    assert "T001" in out and "커밋 값 없음" in out
    remeasure(run_dir)
    assert answer(run_dir).returncode == 0
    assert complete(run_dir).returncode == 0


def test_answer_is_refused_before_the_main_tries_again(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    waiting(run_dir)
    p = answer(run_dir)
    assert p.returncode == 3 and "--remeasure" in p.output


def test_both_kinds_of_gap_take_one_answer(run_dir, repo):
    task(run_dir, test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    waiting(run_dir)
    tasks = run_dir.tasks()
    assert lib.unanswered_test_removals(tasks[FV])
    out = screen_text(run_dir)
    remeasure(run_dir)
    assert answer(run_dir).returncode == 0
    tasks = run_dir.tasks()
    assert lib.unanswered_test_removals(tasks[FV]) == []
    assert complete(run_dir).returncode == 0
    assert "시험 변화" in out and run_dir.tasks()[FV]["_sections"]["승인 기록"].count("재지 못함") == 1


def test_test_only_gap_takes_the_same_answer(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}), test_measured=False)
    verify(run_dir)   # 코드 폴더가 없어 시험 변화도 재지 못한다
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    assert complete(run_dir).returncode == 0


@pytest.mark.parametrize("line", [
    '- 2026-11-05 10:00:00 | 코드 확인 재지 못함 T001 | 합쳐도 됨 | 원문: ""',
    '- 2026-11-05 10:00:00 | 코드 확인 재지 못함 T001 | 합쳐도 됨 | 원문: "이후 전체 자동"',
    '- 2026-11-05 10:00:00 | 코드 확인 재지 못함 T001 | 합쳐도 됨 | 원문: "위임합니다"',
    '- 2026-11-05 10:00:00 | 코드 확인 재지 못함 T001 | 몰라 | 원문: "모르겠다"',
])
def test_empty_or_delegated_answers_do_not_count(run_dir, repo, line):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    run_dir.task(FV, "흐름별 검증", {"승인 기록": line}, kind="flow-verify", block="검증", status="승인대기", flow="reading", started_version="1.2.0-dev.1", rules="2")
    assert lib.unmeasured_answers(run_dir.tasks()) == {}
    assert complete(run_dir).returncode == 3


@pytest.mark.parametrize("value,text", [("합쳐도 됨", ""), ("합쳐도 됨", "이후 전체 자동"), ("합칠까", "응")])
def test_record_refuses_empty_delegated_and_other_words(run_dir, repo, value, text):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 재지 못함 T001|{}|{}".format(value, text)).returncode == 3


def test_record_refuses_a_task_with_no_gap(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 3


def test_delegation_waits_for_it(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo, values="| 위임 | L1~L3 |\n")
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert not screen.delegation_status(str(run_dir.path), FV)["closable"]
    assert complete(run_dir).returncode == 3
    assert answer(run_dir).returncode == 0
    assert complete(run_dir).returncode == 0


def test_second_verify_does_not_ask_the_same_task_again(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []


# ---------------------------------------------------------------- 멈추지 않음


def test_hold_is_allowed(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    waiting(run_dir)
    p = run_script("task_set", run_dir.path, FV, "--status", "보류", "--record", "보류|보류|잠시 둡니다")
    assert p.returncode == 0, p.output


def test_folder_gone_for_good_still_has_a_way_out(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": SECRET}), test_measured=False)
    verify(run_dir)
    make_places(run_dir)
    waiting(run_dir)
    assert complete(run_dir).returncode == 3
    remeasure(run_dir, "--tried", "폴더를 다시 만들지 못했습니다")
    assert answer(run_dir).returncode == 0
    assert complete(run_dir).returncode == 0


def test_a_later_good_measure_after_the_answer_does_not_stop_the_flow(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    answer(run_dir)
    set_keys(run_dir, "T001", "no_change=true")
    remeasure(run_dir)
    assert complete(run_dir).returncode == 0


# ---------------------------------------------------------------- 보류로 내린 task


def lower(run_dir, tid="T001"):
    p = run_script("task_set", run_dir.path, tid, "--status", "보류", "--reason", "메인이 내림")
    assert p.returncode == 0, p.output


def lower_through_work(run_dir, tid="T001"):
    """끝나고 커밋 빈 task를 표 밖 전이로 다시 연 뒤 내린다. 곧바로 내리기는 거부되고, 이 길은 화면에 `[표 밖 전이]`로 남는다."""
    p = run_script("task_set", run_dir.path, tid, "--status", "진행", "--unlisted", "다시 작업")
    assert p.returncode == 0, p.output
    lower(run_dir, tid)


def test_lowering_to_hold_keeps_the_gap_and_asks_the_person(run_dir, repo):
    task(run_dir, test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    lower_through_work(run_dir)
    remeasure(run_dir)
    assert "- 재지 못함: T001" in head(run_dir) and "- 재지 못함 이유: T001 | 커밋 값 없음" in head(run_dir)
    waiting(run_dir)
    out = complete(run_dir)
    assert out.returncode == 3 and "T001" in out.output
    assert answer(run_dir).returncode == 0
    assert complete(run_dir).returncode == 0
    assert "T001" in places.run_left(str(run_dir.path))["where"][0]


def test_a_held_task_whose_commit_is_found_is_measured(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    lower_through_work(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    got = places.read(str(run_dir.path), FV)
    assert "- 재지 못함: 없음" in head(run_dir) and [p["파일"] for p in got] == [["src/a.ts"]] and got[0]["처리"] == places.WAITING


def test_lowering_a_committed_task_keeps_its_test_gap(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}), test_measured=False)
    verify(run_dir)
    make_places(run_dir)
    lower(run_dir)
    tasks = run_dir.tasks()
    assert [r["change"] for r in lib.flow_test_rows(tasks[FV], tasks)] == [lib.TEST_UNMEASURED]


def test_a_task_that_was_never_done_stays_out(run_dir, repo):
    # 고정 때 재지 않은 보류 task는 합치지 않는 코드다. 남은 것만 검증하는 흐름이 멈추지 않는다
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    run_dir.task("T002", "구현 T002", kind="implementation", block="구현", status="보류", flow="reading", started_version="1.2.0-dev.1")
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    assert "- 재지 못함: 없음" in head(run_dir)
    waiting(run_dir)
    assert complete(run_dir).returncode == 0


@pytest.mark.parametrize("how", [("--reason", "메인이 내림"), ("--record", "보류|보류|잠시 둡니다")])
def test_a_done_task_with_no_commit_cannot_be_lowered_before_the_freeze(run_dir, repo, how):
    commit(repo, {"src/a.ts": SECRET})
    task(run_dir)
    verify(run_dir, repo)
    p = run_script("task_set", run_dir.path, "T001", "--status", "보류", *how)
    assert p.returncode == 3 and "commit=" in p.output and "no_change=true" in p.output
    assert run_dir.tasks()["T001"]["status"] == "완료"
    make_places(run_dir)
    assert "- 재지 못함: T001" in head(run_dir)


def test_a_done_task_with_no_commit_cannot_go_to_the_backlog_outside_the_table(run_dir, repo):
    task(run_dir)
    p = run_script("task_set", run_dir.path, "T001", "--status", "백로그", "--unlisted", "나중에")
    assert p.returncode == 3 and run_dir.tasks()["T001"]["status"] == "완료"


def test_a_done_task_lowers_when_the_commit_comes_with_it(run_dir, repo):
    task(run_dir)
    sha = commit(repo, {"src/a.ts": BODY})
    verify(run_dir, repo)
    p = run_script("task_set", run_dir.path, "T001", "commit=" + sha, "--status", "보류", "--reason", "메인이 내림")
    assert p.returncode == 0, p.output
    assert make_places(run_dir) == []   # 신호 없는 코드는 묻지 않는다
    assert "T001" in places.measured_tasks(str(run_dir.path), FV)


def test_a_task_lowered_with_its_commit_still_shows_the_security_place(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    sha = commit(repo, {"src/a.ts": SECRET})
    p = run_script("task_set", run_dir.path, "T001", "commit=" + sha, "--status", "보류", "--reason", "메인이 내림")
    assert p.returncode == 0, p.output
    got = make_places(run_dir)
    assert [p["처리"] for p in got] == [places.WAITING] and got[0]["커밋"] == sha and got[0]["보안"] == "예" and got[0]["신호"]
    assert "T001" in places.measured_tasks(str(run_dir.path), FV) and "- 재지 못함: 없음" in head(run_dir)
    waiting(run_dir)
    assert got[0]["key"] in complete(run_dir).output
    open_card(run_dir, got[0]["key"])
    assert place_answer(run_dir, got[0]["key"], "문제 없음").returncode == 0
    assert complete(run_dir).returncode == 0


@pytest.mark.parametrize("status", ["보류", "백로그"])
def test_a_held_task_with_a_commit_makes_only_security_places(run_dir, repo, status):
    sha = commit(repo, {"src/a.ts": SECRET, "src/b.ts": BODY})
    task(run_dir, sha, judgments="- 도우미 [종류: 구조] [위치: src/b.ts:1]\n")
    path = run_dir.task_dir("T001") / "task.md"
    path.write_text(path.read_text(encoding="utf-8").replace("status: 완료", "status: " + status), encoding="utf-8")
    verify(run_dir, repo)
    assert [p["파일"] for p in make_places(run_dir)] == [["src/a.ts"]]


def test_a_held_task_with_no_signal_adds_no_question(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}), judgments="- 도우미 [종류: 구조] [위치: src/a.ts:1]\n")
    lower(run_dir)
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    waiting(run_dir)
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []
    assert complete(run_dir).returncode == 0


def test_a_task_lowered_after_the_freeze_is_measured_again(run_dir, repo):
    run_dir.task("T001", "구현 T001", TOUCH, kind="implementation", block="구현", status="승인대기", flow="reading", started_version="1.2.0-dev.1",
                 commit=commit(repo, {"src/a.ts": SECRET}))
    measured(run_dir)
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    lower(run_dir)
    waiting(run_dir)
    assert [r["task"] for r in places.gap_rows(str(run_dir.path), run_dir.tasks()[FV])] == ["T001"]
    assert complete(run_dir).returncode == 3
    remeasure(run_dir)
    assert [p["처리"] for p in places.read(str(run_dir.path), FV)] == [places.WAITING]
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []


def test_a_held_task_whose_commit_is_not_a_hash_stays_unmeasured(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    p = run_script("task_set", run_dir.path, "T001", "commit=HEAD", "--status", "보류", "--reason", "메인이 내림")
    assert p.returncode == 0, p.output
    make_places(run_dir)
    assert "- 재지 못함: T001" in head(run_dir) and "- 재지 못함 이유: T001 | " + places.GAP_GIT in head(run_dir)
    waiting(run_dir)
    assert complete(run_dir).returncode == 3


def test_a_parked_task_has_no_commit_and_stays_out(run_dir, repo):
    # 치우면 코드가 패치로 빠져 커밋이 없다. 합치지 않는 코드라 재지 않는다
    run_dir.flow("reading", dir=str(repo), status="폴더 있음")
    run_dir.task("T001", "구현 T001", TOUCH, kind="implementation", block="구현", status="진행", flow="reading", started_version="1.2.0-dev.1", rules="2")
    write(repo / "src" / "a.ts", SECRET)
    lower(run_dir)
    p = run_script("task_set", run_dir.path, "T001", "--park")
    assert p.returncode == 0, p.output
    t = run_dir.tasks()["T001"]
    assert str(t.get("parked", "")).strip() and not str(t.get("commit", "") or "").strip()
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    assert "T001" not in places.measured_tasks(str(run_dir.path), FV) and "- 재지 못함: 없음" in head(run_dir)
    waiting(run_dir)
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []
    assert complete(run_dir).returncode == 0


def test_old_held_task_with_a_commit_stays_out(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": SECRET}), meta=OLD)
    lower(run_dir)
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    assert "T001" not in places.measured_tasks(str(run_dir.path), FV)


def test_a_done_task_that_changed_nothing_still_lowers(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    set_keys(run_dir, "T001", "no_change=true")
    lower(run_dir)
    make_places(run_dir)
    assert "- 재지 못함: 없음" in head(run_dir)
    waiting(run_dir)
    assert complete(run_dir).returncode == 0


@pytest.mark.parametrize("status", ["진행", "자체검증", "승인대기"])
def test_a_task_that_is_not_done_still_lowers(run_dir, status):
    run_dir.task("T002", "구현 T002", kind="implementation", block="구현", status=status, flow="reading", started_version="1.2.0-dev.1")
    lower(run_dir, "T002")


def test_old_done_task_with_no_commit_still_lowers(run_dir, repo):
    task(run_dir, meta=OLD)
    lower(run_dir)


# ---------------------------------------------------------------- 메인 혼자 풀지 못함


@pytest.mark.parametrize("value", ["commit=", "commit=  ", "commit=[]", "commit=[ , ]"])
def test_a_commit_with_a_value_cannot_be_emptied(run_dir, repo, value):
    sha = commit(repo, {"src/a.ts": BODY})
    task(run_dir, sha)
    p = run_script("task_set", run_dir.path, "T001", value)
    assert p.returncode == 3 and "commit" in p.output
    assert run_dir.tasks()["T001"]["commit"] == sha


def test_emptying_the_commit_to_mark_no_change_does_not_clear_the_gap(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": SECRET}))
    verify(run_dir)
    make_places(run_dir)
    assert run_script("task_set", run_dir.path, "T001", "commit=").returncode == 3
    assert run_script("task_set", run_dir.path, "T001", "no_change=true").returncode == 3
    assert run_script("task_set", run_dir.path, "T001", "commit=", "no_change=true").returncode == 3
    remeasure(run_dir)
    assert "- 재지 못함: T001" in head(run_dir)
    waiting(run_dir)
    assert complete(run_dir).returncode == 3


def test_a_value_that_is_not_a_hash_cannot_be_emptied_either(run_dir, repo):
    # 해시를 `HEAD`로 덮고 비우는 두 단계도 같은 길이다
    task(run_dir, commit(repo, {"src/a.ts": SECRET}))
    set_keys(run_dir, "T001", "commit=HEAD")
    assert run_script("task_set", run_dir.path, "T001", "commit=").returncode == 3


def test_an_empty_commit_can_be_written_empty_again(run_dir):
    task(run_dir)
    set_keys(run_dir, "T001", "commit=")


def test_old_task_may_still_empty_its_commit(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}), meta=OLD)
    set_keys(run_dir, "T001", "commit=")


def test_no_change_is_refused_when_a_commit_exists(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": SECRET}))
    verify(run_dir)
    make_places(run_dir)
    p = run_script("task_set", run_dir.path, "T001", "no_change=true")
    assert p.returncode == 3 and "no_change" in p.output
    assert not lib.no_change(run_dir.tasks()["T001"])


def test_no_change_and_a_commit_in_one_call_is_refused(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    assert run_script("task_set", run_dir.path, "T001", "no_change=true", "commit=" + commit(repo, {"src/a.ts": SECRET})).returncode == 3


def test_old_task_may_still_mark_no_change_with_a_commit(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}), meta=OLD)
    assert run_script("task_set", run_dir.path, "T001", "no_change=true").returncode == 0


def test_a_no_change_mark_beside_a_commit_is_ignored(run_dir, repo):
    # 표시가 먼저 있고 커밋을 뒤에 찾은 task: 커밋이 있으면 코드가 있는 것이다
    task(run_dir, commit(repo, {"src/a.ts": SECRET}), test_measured=False, no_change="true")
    verify(run_dir)
    make_places(run_dir)
    assert "- 재지 못함: T001" in head(run_dir) and "코드 폴더 없음" in head(run_dir)
    remeasure(run_dir)
    tasks = run_dir.tasks()
    assert [r["change"] for r in lib.flow_test_rows(tasks[FV], tasks)] == [lib.TEST_UNMEASURED]
    waiting(run_dir)
    assert complete(run_dir).returncode == 3


@pytest.mark.parametrize("value", ["HEAD", "main", "HEAD~1"])
def test_a_commit_that_is_not_a_hash_is_git_failure(run_dir, repo, value):
    commit(repo, {"src/a.ts": SECRET})
    task(run_dir, test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + value)
    remeasure(run_dir)
    assert "- 재지 못함: T001" in head(run_dir) and "- 재지 못함 이유: T001 | git 실패" in head(run_dir)
    assert not lib.test_changes_measured(run_dir.tasks()["T001"])
    waiting(run_dir)
    assert complete(run_dir).returncode == 3


def test_a_commit_outside_the_touch_list_stays_unmeasured(run_dir, repo):
    task(run_dir, test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"docs/x.md": "글\n"}))
    remeasure(run_dir)
    assert "- 재지 못함: T001" in head(run_dir) and "- 재지 못함 이유: T001 | " + places.GAP_OFF_SCOPE in head(run_dir)
    assert not lib.test_changes_measured(run_dir.tasks()["T001"])
    waiting(run_dir)
    assert complete(run_dir).returncode == 3
    assert answer(run_dir).returncode == 0
    assert complete(run_dir).returncode == 0


def test_a_commit_with_one_file_in_the_touch_list_is_measured(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": BODY, "docs/x.md": "글\n"}))
    remeasure(run_dir)
    assert "- 재지 못함: 없음" in head(run_dir)


def test_a_glob_in_the_touch_list_counts(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sections={"건드릴 파일": "- src/**"}, test_lines="- 없음\n")
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/deep/a.ts": BODY}))
    remeasure(run_dir)
    assert "- 재지 못함: 없음" in head(run_dir)


def test_old_shape_without_a_touch_list_stays_unmeasured(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sections={"건드릴 파일": ""}, test_lines="- 없음\n")
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    assert "- 재지 못함 이유: T001 | " + places.GAP_NO_SCOPE in head(run_dir)
    waiting(run_dir)
    assert complete(run_dir).returncode == 3


# ---------------------------------------------------------------- 답은 그때의 커밋에 묶인다


def gap_lines(run_dir):
    return [line for line in lib.record_lines(run_dir.tasks()[FV]) if lib.UNMEASURED_POINT in line]


def test_the_answer_line_carries_the_commit(run_dir, repo):
    sha = commit(repo, {"src/a.ts": BODY})
    task(run_dir, sha)
    verify(run_dir)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    assert "| 코드 확인 재지 못함 T001@{} | 합쳐도 됨 |".format(sha) in gap_lines(run_dir)[0]


def test_the_answer_line_says_none_for_an_empty_commit(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    assert "T001@없음" in gap_lines(run_dir)[0]
    assert lib.unmeasured_answers(run_dir.tasks()) == {"T001": "그 코드는 안 봐도 됩니다"}


def test_an_answer_does_not_cover_a_later_commit(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    verify(run_dir)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    assert [r["task"] for r in places.gap_rows(str(run_dir.path), run_dir.tasks()[FV])] == ["T001"]
    assert complete(run_dir).returncode == 3


def test_a_changed_commit_is_measured_again_before_the_person_is_asked(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    verify(run_dir)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    p = answer(run_dir, text="다시 답합니다")
    assert p.returncode == 3 and "--remeasure" in p.output
    assert "--remeasure" in screen_text(run_dir) and "그 코드를 보지 않고 합칩니다" not in screen_text(run_dir)
    remeasure(run_dir)
    assert answer(run_dir, text="다시 답합니다").returncode == 0
    assert complete(run_dir).returncode == 0


def test_answered_then_commit_found_without_remeasuring_does_not_close(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    assert complete(run_dir).returncode == 3
    remeasure(run_dir)
    got = places.read(str(run_dir.path), FV)
    assert got and got[0]["처리"] == places.WAITING
    assert got[0]["key"] in complete(run_dir).output


def test_the_second_verify_is_not_asked_at_the_same_commit(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    assert answer(run_dir).returncode == 0
    run_dir.task("T092", "둘째 검증", kind="flow-verify", block="검증", status="승인대기", flow="reading", started_version="1.2.0-dev.1")
    assert run_script("screen", run_dir.path, "T092", "--places").returncode == 0
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()["T092"]) == []


def test_old_answer_line_without_a_commit_does_not_count(run_dir, repo):
    # 어느 코드에 받은 답인지 모르므로 다시 묻는다. 1.2.0을 내보내기 전의 꼴이다
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    line = '- 2026-11-05 10:00:00 | 코드 확인 재지 못함 T001 | 합쳐도 됨 | 원문: "그 코드는 안 봐도 됩니다"'
    run_dir.task(FV, "흐름별 검증", {"승인 기록": line}, kind="flow-verify", block="검증", status="승인대기", flow="reading", started_version="1.2.0-dev.1", rules="2")
    assert lib.unmeasured_answers(run_dir.tasks()) == {}
    assert complete(run_dir).returncode == 3


def test_a_stated_commit_that_differs_is_refused(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    verify(run_dir)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    p = run_script("task_set", run_dir.path, FV, "--record", "코드 확인 재지 못함 T001@abcdef1|합쳐도 됨|안 봐도 됩니다")
    assert p.returncode == 3


def test_the_old_test_change_answer_does_not_open_an_unmeasured_row(run_dir, repo):
    # 먼저 다시 재는 차례를 건너뛰지 않는다. 재지 못함은 코드 확인의 답으로만 푼다
    task(run_dir, commit(repo, {"src/a.ts": BODY}), test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    waiting(run_dir)
    tasks = run_dir.tasks()
    row = lib.flow_test_rows(tasks[FV], tasks)[0]
    assert row["change"] == lib.TEST_UNMEASURED
    assert run_script("task_set", run_dir.path, FV, "--record", "시험 변화|{}=받아들임|괜찮습니다".format(row["key"])).returncode == 0
    assert complete(run_dir).returncode == 3
    remeasure(run_dir)
    assert lib.test_changes_measured(run_dir.tasks()["T001"])
    assert complete(run_dir).returncode == 0


# ---------------------------------------------------------------- 고정 뒤 끝난 task


def late(run_dir, repo, text=SECRET):
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    make_places(run_dir)
    code(run_dir, "T003", "- 없음\n", sha=commit(repo, {"src/late.ts": text}), sections={"건드릴 파일": "- src/late.ts"})
    measured(run_dir, "T003")


def test_a_task_done_after_the_freeze_blocks_completion(run_dir, repo):
    late(run_dir, repo)
    waiting(run_dir)
    assert [r["task"] for r in places.gap_rows(str(run_dir.path), run_dir.tasks()[FV])] == ["T003"]
    p = complete(run_dir)
    assert p.returncode == 3 and "T003" in p.output
    assert "--remeasure" in screen_text(run_dir)


def test_the_gate_and_the_screen_name_the_same_late_task(run_dir, repo):
    late(run_dir, repo)
    tasks = run_dir.tasks()
    assert "T003" in flow_review.code_line(str(run_dir.path), tasks, tasks[FV])
    assert "T003" in places.gap_tasks(str(run_dir.path), FV, tasks)


def test_remeasuring_measures_the_late_task(run_dir, repo):
    late(run_dir, repo)
    remeasure(run_dir)
    assert "T003" in places.measured_tasks(str(run_dir.path), FV)
    got = places.read(str(run_dir.path), FV)
    assert [p["task"] for p in got] == ["T003"] and got[0]["처리"] == places.WAITING and got[0]["신호"]
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []
    tasks = run_dir.tasks()
    assert "T003" not in flow_review.code_line(str(run_dir.path), tasks, tasks[FV])


def test_a_late_task_cannot_be_answered_before_it_is_measured(run_dir, repo):
    late(run_dir, repo)
    waiting(run_dir)
    p = answer(run_dir, "T003")
    assert p.returncode == 3 and "--remeasure" in p.output


def test_a_late_task_that_cannot_be_measured_stays_for_the_person(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    make_places(run_dir)
    code(run_dir, "T003", "- 없음\n")
    measured(run_dir, "T003")
    remeasure(run_dir)
    assert "- 재지 못함: T003" in head(run_dir) and "T003" in places.measured_tasks(str(run_dir.path), FV)
    waiting(run_dir)
    assert complete(run_dir).returncode == 3
    assert answer(run_dir, "T003").returncode == 0
    assert complete(run_dir).returncode == 0


# ---------------------------------------------------------------- 잰 뒤에 바뀐 커밋


def test_the_freeze_stamps_the_measured_commit(run_dir, repo):
    sha = committed_task(run_dir, repo)
    verify(run_dir, repo)
    make_places(run_dir)
    assert "- {}: T001 | {}".format(places.MEASURED_AT, sha) in head(run_dir)


def test_a_stamp_says_none_for_an_empty_commit(run_dir, repo):
    task(run_dir, no_change="true")
    verify(run_dir, repo)
    make_places(run_dir)
    assert "- {}: T001 | {}".format(places.MEASURED_AT, lib.UNMEASURED_NO_COMMIT) in head(run_dir)


def test_an_unchanged_commit_adds_no_line_and_no_question(run_dir, repo):
    committed_task(run_dir, repo)
    verify(run_dir, repo)
    make_places(run_dir)
    waiting(run_dir)
    tasks = run_dir.tasks()
    assert places.gap_rows(str(run_dir.path), tasks[FV]) == []
    assert places.changed_tasks(str(run_dir.path), FV, tasks) == []
    assert "--remeasure" not in screen_text(run_dir) and "T001" not in flow_review.code_line(str(run_dir.path), tasks, tasks[FV])
    assert complete(run_dir).returncode == 0


def test_a_changed_commit_blocks_until_it_is_measured(run_dir, repo):
    committed_task(run_dir, repo)
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    waiting(run_dir)
    sha = commit(repo, {"src/a.ts": SECRET})
    set_keys(run_dir, "T001", "commit=" + sha)
    tasks = run_dir.tasks()
    assert [r["why"] for r in places.gap_rows(str(run_dir.path), tasks[FV])] == [places.GAP_CHANGED]
    assert "T001" in flow_review.code_line(str(run_dir.path), tasks, tasks[FV])
    assert "--remeasure" in screen_text(run_dir)
    p = complete(run_dir)
    assert p.returncode == 3 and "T001" in p.output
    assert answer(run_dir).returncode == 3
    remeasure(run_dir)
    got = places.read(str(run_dir.path), FV)
    assert [p["처리"] for p in got] == [places.WAITING] and got[0]["커밋"] == sha and got[0]["신호"]
    assert "- {}: T001 | {}".format(places.MEASURED_AT, sha) in head(run_dir) and "- 재지 못함: 없음" in head(run_dir)
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []
    assert got[0]["key"] in complete(run_dir).output
    open_card(run_dir, got[0]["key"])
    assert place_answer(run_dir, got[0]["key"], "문제 없음").returncode == 0
    assert complete(run_dir).returncode == 0


def test_a_changed_commit_is_measured_once(run_dir, repo):
    committed_task(run_dir, repo)
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    remeasure(run_dir)
    once = places.read(str(run_dir.path), FV)
    remeasure(run_dir)
    assert places.read(str(run_dir.path), FV) == once and head(run_dir).count(places.MEASURED_AT + ":") == 1


def test_a_commit_written_on_a_no_change_task_is_measured(run_dir, repo):
    task(run_dir, no_change="true")
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    waiting(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    assert complete(run_dir).returncode == 3
    remeasure(run_dir)
    got = places.read(str(run_dir.path), FV)
    assert got and got[0]["처리"] == places.WAITING
    assert got[0]["key"] in complete(run_dir).output


def test_a_changed_commit_measures_test_changes_at_the_new_commit(run_dir, repo):
    write(repo / "tests" / "a.test.ts", 'it("x", () => {});\n')
    commit(repo, {"keep.txt": "x\n"})
    committed_task(run_dir, repo)
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": BODY + "// 고침\n", "tests/a.test.ts": SKIPPED}))
    remeasure(run_dir)
    tasks = run_dir.tasks()
    assert [r["change"] for r in lib.flow_test_rows(tasks[FV], tasks)] == ["끄기"]


def test_a_commit_written_on_a_no_change_task_measures_test_changes(run_dir, repo):
    # `no_change`의 `- 없음`은 코드가 없었다는 값이라 새 커밋을 잰 것이 아니다
    write(repo / "tests" / "a.test.ts", 'it("x", () => {});\n')
    commit(repo, {"keep.txt": "x\n"})
    base = git(repo, "rev-parse", "HEAD")
    task(run_dir, no_change="true")
    write(run_dir.task_dir("T001") / lib.TEST_CHANGES, "{}{}\n- 없음\n".format(lib.TEST_BASE_HEAD, base))
    verify(run_dir, repo)
    assert make_places(run_dir) == []
    waiting(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": BODY, "tests/a.test.ts": SKIPPED}))
    remeasure(run_dir)
    tasks = run_dir.tasks()
    assert [r["change"] for r in lib.flow_test_rows(tasks[FV], tasks)] == ["끄기"]
    assert complete(run_dir).returncode == 3


def test_a_changed_commit_outside_the_touch_list_asks_the_person(run_dir, repo):
    committed_task(run_dir, repo)
    verify(run_dir, repo)
    make_places(run_dir)
    waiting(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"docs/x.md": "글\n"}))
    remeasure(run_dir)
    assert "- 재지 못함: T001" in head(run_dir) and "- 재지 못함 이유: T001 | " + places.GAP_OFF_SCOPE in head(run_dir)
    # 그 커밋의 시험 변화도 재지 못했으므로 앞 커밋의 줄을 잰 것으로 두지 않는다
    tasks = run_dir.tasks()
    assert [r["change"] for r in lib.flow_test_rows(tasks[FV], tasks)] == [lib.TEST_UNMEASURED]
    assert complete(run_dir).returncode == 3
    assert answer(run_dir).returncode == 0
    assert complete(run_dir).returncode == 0


def test_a_commit_found_for_an_empty_task_keeps_its_test_lines(run_dir, repo):
    # 빈 값을 채우는 것은 정상 복구다. 자체검증에서 잰 줄을 그대로 쓴다
    task(run_dir)
    write(run_dir.task_dir("T001") / lib.TEST_CHANGES, "기준: abc\n- 끄기 | tests/a.test.ts:1 | 기계\n")
    verify(run_dir, repo)
    make_places(run_dir)
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": BODY}))
    remeasure(run_dir)
    tasks = run_dir.tasks()
    assert "- 재지 못함: 없음" in head(run_dir) and [r["change"] for r in lib.flow_test_rows(tasks[FV], tasks)] == ["끄기"]


def test_a_head_without_stamps_is_as_before(run_dir, repo):
    committed_task(run_dir, repo)
    verify(run_dir, repo)
    make_places(run_dir)
    path = run_dir.task_dir(FV) / "places.md"
    kept = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("- {}: ".format(places.MEASURED_AT))]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    set_keys(run_dir, "T001", "commit=" + commit(repo, {"src/a.ts": SECRET}))
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []


# ---------------------------------------------------------------- 사람에게 보이는 문장


def test_the_question_says_what_why_tried_and_means(run_dir, repo):
    task(run_dir, commit(repo, {"src/a.ts": SECRET}), test_measured=False)
    verify(run_dir)
    make_places(run_dir)
    out = remeasure(run_dir, "--tried", "폴더를 다시 만들지 못했습니다")
    for part in ("T001", "구현 T001", "src/a.ts, src/b.ts", "보안 신호", "시험 변화", "폴더를 다시 만들지 못했습니다",
                 "그 코드를 보지 않고 합칩니다", "보류", '--record "코드 확인 재지 못함 T001|합쳐도 됨|{원문}"'):
        assert part in out, part
    assert "코드 폴더" in out and "추천" not in out
    assert "폴더를 다시 만들지 못했습니다" in screen_text(run_dir)


def test_before_the_retry_the_screen_tells_the_main_what_to_do(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    out = screen_text(run_dir)
    assert "--remeasure" in out and "합쳐도 됨" not in out


def test_answered_gap_is_kept_for_the_wrap_up(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    remeasure(run_dir)
    waiting(run_dir)
    answer(run_dir)
    summary = places.run_left(str(run_dir.path))
    assert summary["count"] == 1 and "T001" in summary["where"][0] and "보지 않고 합침" in summary["where"][0]


def test_secret_in_the_tried_sentence_is_masked(run_dir, repo):
    task(run_dir)
    verify(run_dir, repo)
    make_places(run_dir)
    out = remeasure(run_dir, "--tried", "token=abcd1234efgh 로 찾아봄")
    assert "abcd1234efgh" not in out and "abcd1234efgh" not in head(run_dir)


# ---------------------------------------------------------------- 옛 task


def test_old_verify_is_unchanged(run_dir, repo):
    task(run_dir, meta=OLD)
    verify(run_dir, repo, meta=OLD)
    p = run_script("screen", run_dir.path, FV, "--places", "--remeasure")
    assert p.returncode == 0 and "0곳" in p.stdout and not (run_dir.task_dir(FV) / "places.md").exists()
    waiting(run_dir)
    assert complete(run_dir).returncode == 0


def test_old_code_task_in_a_new_verify_asks_nothing(run_dir, repo):
    task(run_dir, meta=OLD, test_measured=False)
    verify(run_dir, repo)
    make_places(run_dir)
    assert places.gap_rows(str(run_dir.path), run_dir.tasks()[FV]) == []
    waiting(run_dir)
    assert complete(run_dir).returncode == 0
