"""메인 컨텍스트 문턱·재개 시각 뒤 측정·변경 없는 코드 task(설계 C-2, 결정 D-C1·D-C2·D-C11).

- `ctx_thresholds`·`main_context_line`이 run.md 「이번 실행의 값」의 문턱 행을 읽는지(10.3).
- `main_context(run_dir)`가 journal.md의 마지막 `재개` 줄 시각보다 이른 세션 기록을 건너뛰는지(10.1). 세션 기록은
  임시 홈 폴더 아래에 두고 `HOME`·`USERPROFILE`·`CLAUDE_CODE_SESSION_ID`를 바꿔 찾게 한다.
- `no_change: true`인 완료 코드 task에 R4가 걸리지 않는지(10.5), `journal_append`의 줄 꼴.
"""
import json
import re
import time
from datetime import datetime, timezone

from conftest import write

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
    assert info == "재개 뒤 기록 없음({})".format(SID[:8])


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
    assert line.startswith("메인 컨텍스트: 260K (세션 {})".format(SID[:8]))
    assert "250K 넘음" in line


def test_line_without_rows_has_no_over(lib, run_dir, monkeypatch, tmp_path):
    session(monkeypatch, tmp_path, [(time.time() - 60, 260000)])
    line = lib.main_context_line(str(run_dir))
    assert line == "메인 컨텍스트: 260K (세션 {})".format(SID[:8])
    assert "넘음" not in line


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
