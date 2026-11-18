"""메인 컨텍스트 문턱·재개 시각 뒤 측정·변경 없는 코드 task(설계 C-2, 결정 D-C1·D-C2·D-C11).

- `ctx_thresholds`·`main_context_line`이 run.md 「이번 실행의 값」의 문턱 행을 읽는지(10.3).
- `main_context(run_dir)`가 journal.md의 마지막 `재개` 줄 시각보다 이른 세션 기록을 건너뛰는지(10.1). 세션 기록은
  임시 홈 폴더 아래에 두고 `HOME`·`USERPROFILE`·`CLAUDE_CODE_SESSION_ID`를 바꿔 찾게 한다.
- `no_change: true`인 완료 코드 task에 R4가 걸리지 않는지(10.5), `journal_append`의 줄 꼴.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

import pytest

from conftest import run_script, write

SID = "c2c2c2c2-0000-4000-8000-000000000000"


def add_run_values(run_dir, *rows):
    p = run_dir.path / "run.md"
    p.write_text(p.read_text(encoding="utf-8") + "".join(r + "\n" for r in rows), encoding="utf-8", newline="\n")


def iso(epoch):
    """세션 기록의 꼴: UTC ISO, 밀리초, 끝이 `Z`."""
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + "000Z"


def local(epoch):
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


def session(monkeypatch, tmp_path, records):
    """records = [(epoch, 토큰 수)]. 임시 홈 아래 세션 기록을 쓰고 환경 변수가 그곳을 가리키게 한다."""
    home = tmp_path / "home"
    lines = [json.dumps({"type": "assistant", "timestamp": iso(when),
                         "message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": n - 10,
                                               "cache_creation_input_tokens": 0}}})
             for when, n in records]
    write(home / ".claude" / "projects" / "D--sample" / (SID + ".jsonl"), "\n".join(lines) + "\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)


def journal(run_dir, *lines):
    write(run_dir.path / "journal.md", "".join(l + "\n" for l in lines))


# (가) 문턱

def test_thresholds_default_without_rows(lib, run_dir):
    assert lib.ctx_thresholds(str(run_dir)) == (300000, 500000)


def test_thresholds_from_run_rows(lib, run_dir):
    add_run_values(run_dir, "| 메인 컨텍스트 권함(K) | 250K |", "| 메인 컨텍스트 멈춤(K) | 400 |")
    assert lib.ctx_thresholds(str(run_dir)) == (250000, 400000)


def test_thresholds_none_is_constants(lib, run_dir):
    add_run_values(run_dir, "| 메인 컨텍스트 권함(K) | 250K |")
    assert lib.ctx_thresholds(None) == (lib.CTX_ADVISE, lib.CTX_STOP) == (300000, 500000)
    assert lib.CTX_FLOOR_NOTE == 150_000


# (나) 재개 시각 뒤 측정

def test_only_records_before_resume(lib, run_dir, monkeypatch, tmp_path):
    now = time.time()
    session(monkeypatch, tmp_path, [(now - 360, 410000), (now - 330, 420000)])
    journal(run_dir, "- {} | 승인 | T001 | 승인".format(local(now - 400)), "- {} | 재개 | - | 시작".format(local(now - 300)))
    ctx, info = lib.main_context(str(run_dir))
    assert ctx is None
    assert info == lib.CTX_NO_RECORD_AFTER_RESUME.format(SID[:8])


def test_records_after_resume(lib, run_dir, monkeypatch, tmp_path):
    now = time.time()
    session(monkeypatch, tmp_path, [(now - 360, 410000), (now - 120, 130000), (now - 60, 140000)])
    journal(run_dir, "- {} | 재개 | - | 시작".format(local(now - 300)))
    assert lib.main_context(str(run_dir)) == (140000, SID[:8])


def test_no_resume_line_takes_last_record(lib, run_dir, monkeypatch, tmp_path):
    now = time.time()
    session(monkeypatch, tmp_path, [(now - 360, 410000), (now - 60, 420000)])
    journal(run_dir, "- {} | 승인 | T001 | 승인".format(local(now - 300)))
    assert lib.main_context(str(run_dir)) == (420000, SID[:8])


# (다) 문턱 문구

def test_line_uses_run_threshold(lib, run_dir, monkeypatch, tmp_path):
    session(monkeypatch, tmp_path, [(time.time() - 60, 260000)])
    add_run_values(run_dir, "| 메인 컨텍스트 권함(K) | 250K |")
    line = lib.main_context_line(str(run_dir))
    assert line == lib.CTX_LINE.format(260, SID[:8]) + lib.CTX_ADVISE_TAIL.format(250)


def test_line_without_rows_has_no_over(lib, run_dir, monkeypatch, tmp_path):
    session(monkeypatch, tmp_path, [(time.time() - 60, 260000)])
    line = lib.main_context_line(str(run_dir))
    assert line == lib.CTX_LINE.format(260, SID[:8])   # 문턱 행이 없으면 기본 권함(300K) 아래라 꼬리가 없다


# (라) no_change와 R4

def done_code_task(run_dir, **meta):
    run_dir.task("T002", "구현", kind="implementation", block="구현", status="완료", flow="f1", commit="",
                 started_version="시험 판본", rules="2", **meta)
    return run_dir.tasks()["T002"]


def test_no_change_skips_r4(lib, run_dir):
    t = done_code_task(run_dir, no_change="true")
    assert lib.no_change(t)
    assert "R4" not in [c for c, *_ in lib.record_check(t)]


def test_r4_without_no_change(lib, run_dir):
    t = done_code_task(run_dir)
    assert not lib.no_change(t)
    assert "R4" in [c for c, *_ in lib.record_check(t)]


# (마) journal_append

def test_journal_append_line_and_eol(lib, run_dir):
    p = run_dir.path / "journal.md"
    p.write_bytes("- 2026-10-30 09:00 | 메모 | - | 앞 줄\r\n".encode("utf-8"))
    lib.journal_append(str(run_dir), "메모", "T008", "재개 바닥 140K")
    raw = p.read_bytes().decode("utf-8")
    assert raw.startswith("- 2026-10-30 09:00 | 메모 | - | 앞 줄\r\n")
    added = raw[len("- 2026-10-30 09:00 | 메모 | - | 앞 줄\r\n"):]
    assert re.fullmatch(r"- \d{4}-\d{2}-\d{2} \d{2}:\d{2} \| 메모 \| T008 \| 재개 바닥 140K\r\n", added)


def test_journal_append_new_file_lf(lib, run_dir):
    lib.journal_append(str(run_dir), "메모", "-", "첫 줄")
    raw = (run_dir.path / "journal.md").read_bytes().decode("utf-8")
    assert re.fullmatch(r"- \d{4}-\d{2}-\d{2} \d{2}:\d{2} \| 메모 \| - \| 첫 줄\n", raw)


# (바) R3 기준 시각: 판정 파일마다 max(첫 줄 시각, `returned_at`의 그 파일 값) + 60초 (P-07, D-14, AC-08)

def r3_files(lib, t):
    """R3 줄이 가리킨 파일 이름(판정 파일·result.md)."""
    return sorted(name for code, msg, _ in lib.record_check(t) if code == "R3"
                  for name in ("judge.md", "judge-run.md", "result.md") if msg.startswith(name))


def judged(lib, run_dir, head, mtime, kind="implementation", result=None, snapshot=None, result_mtime=None, **meta):
    """첫 줄 시각 head의 judge.md(mtime)를 둔 1.3.0 task. result.md는 판정보다 앞에 바뀐 것으로 둔다."""
    run_dir.task("T003", "판정한 task", kind=kind, block="구현", status="자체검증", flow="f1",
                 started_version="1.3.0", rules="2", **meta)
    d = run_dir.task_dir("T003")
    run_dir.result("T003", result or "# 결과\n")
    if snapshot is not None:
        write(d / "result.pre-screen.md", snapshot)
    os.utime(d / "result.md", (result_mtime or head - 300,) * 2)
    run_dir.judge("T003", "판정자: rjudge-T003 {}\n\n## 통과 못 한 기준\n- 없음\n".format(local(head)))
    os.utime(d / "judge.md", (mtime, mtime))
    return run_dir.tasks()["T003"]


HEAD = int(time.time()) - 3600   # 첫 줄 시각 T(초 단위)


@pytest.mark.parametrize("returned, mtime, want", [
    ("judge.md {}".format(local(HEAD + 120)), HEAD + 90, []),                         # 반환 뒤 60초 안: 판정자가 닫은 틈
    ("judge.md {}".format(local(HEAD + 120)), HEAD + 120 + 90, ["judge.md"]),         # 반환 뒤 90초에 바뀜
    ("judge-run.md {}".format(local(HEAD + 120)), HEAD + 90, ["judge.md"]),           # 다른 판정 파일의 반환 시각은 쓰지 않음
    ("judge-run.md {}, judge.md {}".format(local(HEAD + 30), local(HEAD + 120)), HEAD + 90, []),
], ids=["return-plus-60-inside", "after-return-plus-90", "other-file-return", "both-files"])
def test_r3_base_is_the_later_of_head_and_return(lib, run_dir, returned, mtime, want):
    assert r3_files(lib, judged(lib, run_dir, HEAD, mtime, returned_at=returned)) == want


@pytest.mark.parametrize("mtime, want", [(HEAD + 90, ["judge.md"]), (HEAD + 30, [])], ids=["head-plus-90", "head-plus-30"])
def test_r3_without_return_time_keeps_the_head_base(lib, run_dir, mtime, want):
    """`returned_at`이 없으면 고치기 전과 같이 첫 줄 시각 + 60초가 기준이다(판정 기준 2)."""
    assert r3_files(lib, judged(lib, run_dir, HEAD, mtime)) == want


# (사) 단계 kind의 result.md 「실행 기록」 절은 R3 비교에서 뺀다 (P-21, AC-09)

BEFORE = "# 결과\n\n## 승인 화면\n- 없음\n\n## 본문\n- 합친 커밋 둘\n\n## 실행 기록\n- git merge 0\n"
RUN_LOG_ONLY = BEFORE + "- 합친 뒤 시험 0\n"
BODY_TOO = BEFORE.replace("합친 커밋 둘", "합친 커밋 셋")


@pytest.mark.parametrize("kind, after, want", [
    ("merge", RUN_LOG_ONLY, []),
    ("merge", BODY_TOO, ["result.md"]),
    ("implementation", RUN_LOG_ONLY, ["result.md"]),   # 단계 kind가 아니면 「실행 기록」도 그대로 본다
], ids=["merge-run-log", "merge-body", "implementation-run-log"])
def test_stage_kind_run_log_is_not_r3(lib, run_dir, kind, after, want):
    assert ("merge" in lib.kinds.STAGE_KINDS) and ("implementation" not in lib.kinds.STAGE_KINDS)
    t = judged(lib, run_dir, HEAD, HEAD, kind=kind, result=after, snapshot=BEFORE, result_mtime=HEAD + 600)
    assert r3_files(lib, t) == want


# (아) 단계 kind는 읽기 판정자의 반환이 result.md를 사본으로 떠 둔다(P-21 보강). `--screen-snapshot` 없이도 (사)가 작동한다

def judge_returns(lib, run_dir, kind, stale=None):
    """판정 뒤 `--returned rjudge-T003`. stale이면 앞 판정 때의 사본(지금 본문과 다름)을 먼저 둔다."""
    t = judged(lib, run_dir, HEAD, HEAD, kind=kind, result=BEFORE, snapshot=stale)
    proc = run_script("task_set", run_dir, "T003", "--returned", "rjudge-T003")
    assert proc.returncode == 0, proc.output
    return t


def changed(run_dir, text):
    """판정 뒤(첫 줄 시각 + 600초)에 result.md를 text로 바꾼다."""
    write(run_dir.task_dir("T003") / "result.md", text)
    os.utime(run_dir.task_dir("T003") / "result.md", (HEAD + 600,) * 2)


@pytest.mark.parametrize("after, want", [(RUN_LOG_ONLY, []), (BODY_TOO, ["result.md"])], ids=["run-log", "body"])
def test_stage_kind_judge_return_keeps_the_snapshot(lib, run_dir, after, want):
    judge_returns(lib, run_dir, "merge")
    changed(run_dir, after)
    assert r3_files(lib, run_dir.tasks()["T003"]) == want
    assert (run_dir.task_dir("T003") / "result.pre-screen.md").read_text(encoding="utf-8") == BEFORE


def test_stage_kind_judge_return_replaces_an_older_snapshot(lib, run_dir):
    """앞 판정 때 뜬 사본은 이번 판정이 본 본문이 아니다. 이번 반환이 덮어 판정 때 본 그대로와 견준다."""
    judge_returns(lib, run_dir, "merge", stale=BODY_TOO)
    changed(run_dir, RUN_LOG_ONLY)
    assert r3_files(lib, run_dir.tasks()["T003"]) == []
    assert (run_dir.task_dir("T003") / "result.pre-screen.md").read_text(encoding="utf-8") == BEFORE


def test_other_kind_judge_return_keeps_no_snapshot(lib, run_dir):
    """단계 kind가 아니면 고치기 전과 같다: 사본이 생기지 않고 「실행 기록」만 바뀌어도 R3다."""
    judge_returns(lib, run_dir, "implementation")
    assert not (run_dir.task_dir("T003") / "result.pre-screen.md").exists()
    changed(run_dir, RUN_LOG_ONLY)
    assert r3_files(lib, run_dir.tasks()["T003"]) == ["result.md"]


def test_run_judge_return_keeps_no_snapshot(lib, run_dir):
    """R3가 단계 kind의 result.md를 견주는 판정은 읽기 판정(judge.md)뿐이다. 실행 판정의 반환은 사본을 뜨지 않는다."""
    judged(lib, run_dir, HEAD, HEAD, kind="wrap-up", result=BEFORE)
    write(run_dir.task_dir("T003") / "judge-run.md", "판정자: xjudge-T003 {}\n".format(local(HEAD)))
    proc = run_script("task_set", run_dir, "T003", "--returned", "xjudge-T003")
    assert proc.returncode == 0, proc.output
    # 양성 대조: 이 반환을 실행 판정(judge-run.md)의 반환으로 알아봤다. 판정자 이름 풀이가 어긋나 result.md 갈래로 빠지면 여기서 실패한다
    assert set(lib.returned_pieces(run_dir.tasks()["T003"].get(lib.RETURNED_AT))) == {lib.kinds.JUDGE_FILES["run"]}
    assert not (run_dir.task_dir("T003") / "result.pre-screen.md").exists()
