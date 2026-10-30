"""판정 표지(`judge_started`)와 판정 전 기준 정정 시험(설계 C 3.3, D-C7·D-C8, 10.4).

- 옵션 처리가 `task_set.main`에 있어 모두 명령행(`task_set.py`)으로 돌리고 종료 코드·출력 줄·파일을 본다
  (기존 `test_transitions.py`의 명령행 사례와 같은 계층).
- 사례 이름의 `c{n}`이 머리 파일 판정 기준 1의 사례 번호다.
- 거부 문구는 `task_set`의 상수를 가져다 쓴다. 옛 task의 거부 문구는 상수가 없어 글자로 둔다.
"""
import re
import shutil

from conftest import run_script, write

import task_set

NEW = {"started_version": "1.1.0", "rules": "2"}     # 표지 판본부터 시작한 task
MARK = "2026-10-30 10:00:00 rjudge-T001"
OLD_STATUS = "판정 기준 정정은 판정자가 뜨기 전(대기·진행)에만"
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def front_value(run_dir, key, tid="T001"):
    text = (run_dir.task_dir(tid) / "task.md").read_text(encoding="utf-8")
    for line in text.split("---")[1].splitlines():
        if line.split(":", 1)[0].strip() == key:
            return line.split(":", 1)[1].strip()
    return None


def section(run_dir, title, tid="T001"):
    text = (run_dir.task_dir(tid) / "task.md").read_text(encoding="utf-8")
    m = re.search(r"^## {}\n(.*?)(?=^## |\Z)".format(re.escape(title)), text, re.S | re.M)
    return m.group(1).strip() if m else None


def judge_text(items, who="rjudge-T001"):
    return "판정자: {} 2026-10-30 10:00:00\n\n## 통과 못 한 기준\n{}\n".format(who, items)


def amend(run_dir, tmp_path):
    fixed = write(tmp_path / "criteria-new.md", "1. 고친 판정 기준\n")
    return run_script("task_set", run_dir, "T001", "--amend-criteria", fixed, "--source", "작성자 이상 신호 1")


def archive_undecided(run_dir):
    return run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge", "--undecided")


# ① 첫 표지는 시각과 이름, 다시 부르면 시각을 두고 없던 이름만 덧붙인다
def test_c1_judge_start_writes_then_appends_new_names_only(run_dir):
    run_dir.task("T001", "표지 시험", status="자체검증", **NEW)
    r = run_script("task_set", run_dir, "T001", "--judge-start", "rjudge-T001")
    assert r.returncode == 0, r.output
    first = front_value(run_dir, "judge_started").split()
    assert STAMP.match(" ".join(first[:2])) and first[2:] == ["rjudge-T001"]

    r = run_script("task_set", run_dir, "T001", "--judge-start", "xjudge-T001,rjudge-T001")
    assert r.returncode == 0, r.output
    second = front_value(run_dir, "judge_started").split()
    assert second == first[:2] + ["rjudge-T001", "xjudge-T001"]


# ② 판정자를 띄울 수 없는 상태(대기)의 표지는 거부(대조: ①의 자체검증은 받음)
def test_c2_judge_start_rejected_while_waiting(run_dir):
    run_dir.task("T001", "표지 시험", status="대기", **NEW)
    r = run_script("task_set", run_dir, "T001", "--judge-start", "rjudge-T001")
    assert r.returncode == 3, r.output
    assert "--judge-start는 진행·자체검증에서만(지금 대기)" in r.stdout
    assert front_value(run_dir, "judge_started") is None


# ③ 표지는 스크립트가 채우는 키라 키=값으로 쓰지 못한다
def test_c3_judge_started_key_value_rejected(run_dir):
    run_dir.task("T001", "표지 시험", status="자체검증", **NEW)
    r = run_script("task_set", run_dir, "T001", "judge_started=x")
    assert r.returncode == 3, r.output
    assert "judge_started는 스크립트가 채우는 키다" in r.stdout
    assert front_value(run_dir, "judge_started") is None


# ④ 1.1.0부터 시작한 task는 표지가 없으면 자체검증에서도 정정을 받는다
def test_c4_new_task_selfcheck_without_mark_accepts_amend(run_dir, tmp_path):
    run_dir.task("T001", "표지 시험", status="자체검증", **NEW)
    r = amend(run_dir, tmp_path)
    assert r.returncode == 0, r.output
    assert section(run_dir, "판정 기준") == "1. 고친 판정 기준"
    assert (run_dir.task_dir("T001") / "criteria.amend1.md").is_file()


# ⑤ 표지가 있으면 상태(자체검증·진행)와 상관없이 정정을 거부한다
def test_c5_mark_rejects_amend_in_selfcheck_and_running(run_dir, tmp_path):
    head = task_set.AMEND_MARKED.split("{}")[0]
    for status in ("자체검증", "진행"):
        run_dir.task("T001", "표지 시험", status=status, judge_started=MARK, **NEW)
        r = amend(run_dir, tmp_path)
        assert r.returncode == 3, (status, r.output)
        assert head in r.stdout and MARK in r.stdout, status
        assert section(run_dir, "판정 기준") == "1. 마른 시험"
        assert not (run_dir.task_dir("T001") / "criteria.amend1.md").exists()


# ⑥ 실패 판정을 재시도로 보관하면 표지가 비고, 그 뒤 정정을 받는다
def test_c6_retry_archive_clears_mark_then_amend_accepted(run_dir, tmp_path):
    run_dir.task("T001", "표지 시험", status="자체검증", judge_started=MARK, **NEW)
    run_dir.judge("T001", judge_text("- 기준 2: 실패 — 사례가 없음"))
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge")
    assert r.returncode == 0, r.output
    assert front_value(run_dir, "judge_started") == ""
    assert front_value(run_dir, "retry") == "1"
    r = amend(run_dir, tmp_path)
    assert r.returncode == 0, r.output
    assert section(run_dir, "판정 기준") == "1. 고친 판정 기준"


# ⑦ 1.1.0 전에 시작한 task(started_version 없음)의 자체검증 정정은 옛 문구로 거부
def test_c7_old_task_selfcheck_amend_keeps_old_rule(run_dir, tmp_path):
    run_dir.task("T001", "표지 시험", status="자체검증")
    r = amend(run_dir, tmp_path)
    assert r.returncode == 3, r.output
    assert OLD_STATUS in r.stdout
    assert task_set.AMEND_STATUS_NEW not in r.stdout
    assert not (run_dir.task_dir("T001") / "criteria.amend1.md").exists()


# ⑧ 판정불가(환경)만 있는 판정은 재시도 상한이어도 보관하고 retry·「재시도 범위」를 그대로 둔다
def test_c8_undecided_archive_keeps_retry_and_scope(run_dir):
    scope = "- 회차 2 (보관한 판정: judge.r2.md): 고칠 기준: 1."
    run_dir.task("T001", "표지 시험", sections={"재시도 범위": scope}, status="자체검증", retry="2",
                 judge_started=MARK, **NEW)
    run_dir.judge("T001", judge_text("- 기준 1: 판정불가 환경: 권한 거부(pytest)\n"
                                     "- 기준 3: 판정불가 환경: 설치 불일치"))
    r = archive_undecided(run_dir)
    assert r.returncode == 0, r.output
    assert front_value(run_dir, "retry") == "2"
    assert section(run_dir, "재시도 범위") == scope
    d = run_dir.task_dir("T001")
    assert (d / "judge.r3.md").is_file() and not (d / "judge.md").exists()
    assert front_value(run_dir, "judge_started") == ""
    assert front_value(run_dir, "status") == "진행"


def archive_failed(run_dir):
    return run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge")


def put_judge(run_dir, items):
    run_dir.judge("T001", judge_text(items))


UNDECIDED = "- 기준 1: 판정불가 환경: 권한 거부(pytest)"
FAILED = "- 기준 2: 실패 — 사례가 없음"


# ⑪ 판정불가 보관이 앞서도 「재시도 범위」 회차 줄의 사본이 실제로 뜬 사본 번호를 가리킨다.
#    보관 순서마다 (회차, 보관한 판정, 사본 번호, retry)를 본다
def test_c11_retry_scope_names_snapshot_after_undecided_archives(run_dir):
    cases = [
        ("실패만", [FAILED], (1, 1)),
        ("판정불가 뒤 실패", [UNDECIDED, FAILED], (1, 2)),
        ("판정불가가 두 번 이어진 뒤 실패", [UNDECIDED, UNDECIDED, FAILED], (1, 3)),
        ("실패 뒤 판정불가 뒤 실패", [FAILED, UNDECIDED, FAILED], (2, 3)),
        ("실패, 판정불가 둘, 실패", [FAILED, UNDECIDED, UNDECIDED, FAILED], (2, 4)),
    ]
    for label, steps, (turn, n) in cases:
        run_dir.task("T001", "표지 시험", status="자체검증", **NEW)
        d = run_dir.task_dir("T001")
        for old in d.glob("*.r*"):   # 앞 사례의 보관을 치운다
            if old.is_dir():
                shutil.rmtree(old)
            else:
                old.unlink()
        for items in steps:
            put_judge(run_dir, items)
            r = archive_undecided(run_dir) if items == UNDECIDED else archive_failed(run_dir)
            assert r.returncode == 0, (label, r.output)
        assert (d / "before.r{}".format(n)).is_dir(), label
        line = section(run_dir, "재시도 범위").splitlines()[0]
        assert line.startswith("- 회차 {} (보관한 판정: judge.r{}.md, 사본: tasks\\T001\\before.r{}):".format(turn, n, n)), (label, line)
        assert front_value(run_dir, "retry") == str(turn), label


# ⑫ 판정불가 보관은 「재시도 범위」·retry를 그대로 두므로, 그 뒤 실패 보관이 앞 회차 줄을 새 줄로 바꾼다
#    (앞 사본 번호가 남지 않는다)
def test_c12_failed_archive_after_undecided_replaces_previous_scope_line(run_dir):
    run_dir.task("T001", "표지 시험", status="자체검증", **NEW)
    put_judge(run_dir, FAILED)
    assert archive_failed(run_dir).returncode == 0
    first = section(run_dir, "재시도 범위")
    assert "before.r1)" in first
    put_judge(run_dir, UNDECIDED)
    assert archive_undecided(run_dir).returncode == 0
    assert section(run_dir, "재시도 범위") == first and front_value(run_dir, "retry") == "1"
    put_judge(run_dir, FAILED)
    assert archive_failed(run_dir).returncode == 0
    second = section(run_dir, "재시도 범위")
    assert "회차 2 (보관한 판정: judge.r3.md, 사본: tasks\\T001\\before.r3)" in second
    assert "before.r1" not in second and front_value(run_dir, "retry") == "2"


# ⑨ 판정불가 보관을 거부하는 경우(실패 섞임, 읽기 판정의 `대상`, 자원 대기, 판정불가 없음)와
#    받는 경우(실행 판정의 `대상`)
def test_c9_undecided_archive_rejects_mixed_read_target_and_resource_wait(run_dir):
    env = "- 기준 1: 판정불가 환경: 권한 거부(pytest)"
    cases = [
        ({}, env + "\n- 기준 2: 실패 — 사례가 없음", "판정불가가 아닌 항목이 있음: --undecided 없이 보관한다(재시도)"),
        ({}, "- 기준 1: 판정불가 대상: 기준선 없음 pytest", "판정불가가 아닌 항목이 있음: --undecided 없이 보관한다(재시도)"),
        ({"external_progress": "자원 대기: pytest (owner xjudge-T002)"}, env, "자원 대기라 판정불가로 보관하지 않음: 자원 대기: pytest"),
        ({}, "- 없음", "판정불가 항목이 없음: --undecided 없이 보관한다"),
    ]
    for meta, items, why in cases:
        run_dir.task("T001", "표지 시험", status="자체검증", judge_started=MARK, **dict(NEW, **meta))
        run_dir.judge("T001", judge_text(items))
        r = archive_undecided(run_dir)
        assert r.returncode == 3, (items, r.output)
        assert why in r.stdout, items
        assert (run_dir.task_dir("T001") / "judge.md").is_file()
        assert front_value(run_dir, "judge_started") == MARK

    (run_dir.task_dir("T001") / "judge.md").unlink()
    run_dir.task("T001", "표지 시험", status="자체검증", judge_started=MARK, **NEW)
    write(run_dir.task_dir("T001") / "judge-run.md",
          judge_text("- 기준 5: 판정불가 대상: 기준선 없음 pytest", who="xjudge-T001"))
    r = archive_undecided(run_dir)
    assert r.returncode == 0, r.output
    assert (run_dir.task_dir("T001") / "judge-run.r1.md").is_file()
    assert front_value(run_dir, "judge_started") == ""


# ⑩ --judge-clear: 판정 파일이 있으면 거부, 없으면 비우고 journal, 이미 비었으면 `표지 없음`
def test_c10_judge_clear(run_dir):
    journal = run_dir.path / "journal.md"
    write(journal, "- 2026-10-30 09:00 | 시작 | T001 | 진행\n")
    run_dir.task("T001", "표지 시험", status="자체검증", judge_started=MARK, **NEW)
    run_dir.judge("T001", judge_text("- 없음"))
    r = run_script("task_set", run_dir, "T001", "--judge-clear")
    assert r.returncode == 3, r.output
    assert "판정 파일이 있음(judge.md)" in r.stdout
    assert front_value(run_dir, "judge_started") == MARK

    (run_dir.task_dir("T001") / "judge.md").unlink()
    r = run_script("task_set", run_dir, "T001", "--judge-clear")
    assert r.returncode == 0, r.output
    assert front_value(run_dir, "judge_started") == ""
    last = journal.read_text(encoding="utf-8").splitlines()[-1]
    assert "| 메모 | T001 | 판정 표지 지움: " + MARK in last

    before = journal.read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "--judge-clear")
    assert r.returncode == 0, r.output
    assert "표지 없음" in r.stdout
    assert journal.read_text(encoding="utf-8") == before
