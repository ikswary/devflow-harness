"""목적 시험 화면 다시 그리기(`tests/purpose/rerender.py`)의 자르기 규칙(설계 5절 R, AC-21).

- 가짜 실행 폴더(task 다섯: 대상 앞에 만든 것 둘, 대상, 대상 승인 요청 뒤에 만든 것, 머리 파일 없는 폴더)를
  `tmp_path`에 지어 스크립트를 돌린다. 실제 지난 실행 사본으로 돌리는 것은 이 시험이 아니다(tests/purpose/README.md).
"""
import os
import shutil
import subprocess
import sys

import pytest

import kinds
from conftest import ROOT, RunDir, write

RERENDER = ROOT / "tests" / "purpose" / "rerender.py"
RUN_NAME = "2026-01-02-sample-run"
TARGET = "T002"
CUT = "2026-01-02 12:00:00"
BEFORE_LINE = "- 2026-01-02 11:00:00 | 되물음 | 앞 물음 | 원문: \"먼저 물음\""
AFTER_LINE = "- 2026-01-02 13:00:00 | 승인 | 표본 | 원문: \"좋음\""
AFTER_SUB = "  - 13시 답의 하위 줄"


def run_rerender(run, out, task=TARGET):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", str(RERENDER), "--run", str(run), "--task", task, "--out", str(out)],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    proc.output = proc.stdout + proc.stderr
    return proc


def fake_run(base, target_kind="design"):
    """T001은 대상 앞에 만들고 대상 승인 요청 뒤에 승인, T004는 앞에 만들고 앞에 승인, T003은 뒤에 만듦, T009는 머리 파일 없음."""
    run = RunDir(base / "src" / RUN_NAME)
    run.task("T001", "뒤에 승인한 앞 task", status="완료", created="2026-01-02 09:00:00",
             approval_requested="2026-01-02 10:00:00", approved="2026-01-02 12:30:00",
             sections={"승인 기록": "- 2026-01-02 12:30:00 | 승인 | 앞 task | 원문: \"됨\""})
    run.task(TARGET, "대상 task", kind=target_kind, status="완료", created="2026-01-02 10:00:00",
             approval_requested=CUT, approved="2026-01-02 13:00:00", approval_mode="승인", stage="기록",
             sections={"승인 기록": "\n".join([BEFORE_LINE, AFTER_LINE, AFTER_SUB])})
    run.task("T003", "뒤에 만든 task", status="대기", created="2026-01-02 12:10:00")
    run.task("T004", "앞에 승인한 task", status="완료", created="2026-01-02 09:30:00",
             approval_requested="2026-01-02 11:00:00", approved="2026-01-02 11:30:00",
             sections={"승인 기록": "- 2026-01-02 11:30:00 | 승인 | 앞 승인 | 원문: \"됨\""})
    write(run.task_dir("T009") / "note.md", "머리 파일 없음\n")
    write(run.path / "decisions.md", "- 2026-01-02 13:00:00 | 표본 결정 | 원문: \"좋음\" | T002\n")
    return run


def snapshot(folder):
    """폴더 아래 모든 파일의 {상대 경로: 바이트}."""
    out = {}
    for top, _dirs, files in os.walk(folder):
        for name in files:
            p = os.path.join(top, name)
            out[os.path.relpath(p, folder)] = open(p, "rb").read()
    return out


@pytest.fixture
def cut(tmp_path):
    run = fake_run(tmp_path)
    before = snapshot(run.path)
    out = tmp_path / "out"
    proc = run_rerender(run.path, out)
    assert proc.returncode == 0, proc.output
    return {"proc": proc, "src": run.path, "before": before, "out": out, "copy": out / RUN_NAME}


def test_later_task_is_gone_and_others_stay(cut):
    assert sorted(os.listdir(cut["copy"] / "tasks")) == ["T001", TARGET, "T004", "T009"]
    assert (cut["copy"] / "tasks" / "T009" / "note.md").is_file()   # 머리 파일 없는 폴더는 자르지 않음
    assert cut["proc"].stdout.splitlines()[-1] == "잘린 사본: {}".format(cut["copy"])


def test_task_approved_after_cut_is_back_in_progress(cut, lib):
    tasks = lib.load_tasks(str(cut["copy"]))
    t1, t4 = tasks["T001"], tasks["T004"]
    assert (t1["status"], t1["approved"]) == ("진행", "")
    assert t1["_sections"]["승인 기록"] == ""
    # 양성 대조: 자르는 시각 앞에 승인한 task는 그대로
    assert (t4["status"], t4["approved"]) == ("완료", "2026-01-02 11:30:00")
    assert t4["_sections"]["승인 기록"] == "- 2026-01-02 11:30:00 | 승인 | 앞 승인 | 원문: \"됨\""


def test_target_is_waiting_without_later_records(cut, lib):
    t = lib.load_tasks(str(cut["copy"]))[TARGET]
    assert (t["status"], t["approval_mode"], t["approved"]) == ("승인대기", "", "")
    assert t["approval_requested"] == CUT
    assert t["stage"] == "기록"   # 단계 kind가 아니면 stage를 건드리지 않음
    assert t["_sections"]["승인 기록"] == BEFORE_LINE


def test_stage_kind_target_goes_to_result_approval(tmp_path, lib):
    run = fake_run(tmp_path, target_kind="probe")
    assert "probe" in kinds.STAGE_KINDS   # 전제: probe가 단계 kind
    proc = run_rerender(run.path, tmp_path / "out")
    assert proc.returncode == 0, proc.output
    t = lib.load_tasks(str(tmp_path / "out" / RUN_NAME))[TARGET]
    assert (t["status"], t["stage"]) == ("승인대기", "결과승인")


def test_source_is_unchanged(cut):
    assert snapshot(cut["src"]) == cut["before"]
    assert cut["before"]   # 양성 대조: 원본 파일을 실제로 읽었음


def test_rerun_replaces_copy_with_marker(cut):
    stray = cut["copy"] / "stray.txt"
    stray.write_text("남은 것\n", encoding="utf-8")
    proc = run_rerender(cut["src"], cut["out"])
    assert proc.returncode == 0, proc.output
    assert not stray.exists()
    assert (cut["copy"] / ".purpose-rerender").is_file()


def test_refuses_existing_folder_without_marker(tmp_path):
    run = fake_run(tmp_path)
    out = tmp_path / "out"
    keep = write(out / RUN_NAME / "mine.txt", "사람의 파일\n")
    proc = run_rerender(run.path, out)
    assert proc.returncode == 3, proc.output
    assert "표지 .purpose-rerender가 없음" in proc.stderr
    assert sorted(os.listdir(out / RUN_NAME)) == ["mine.txt"]
    assert keep.read_text(encoding="utf-8") == "사람의 파일\n"


@pytest.mark.parametrize("where", ["inside", "parent"])
def test_refuses_out_inside_or_over_source(tmp_path, where):
    run = fake_run(tmp_path)
    before = snapshot(run.path)
    # inside: --out이 원본 안. parent: 사본 자리({out}/{원본 이름})가 원본 자체
    out = run.path / "cut" if where == "inside" else run.path.parent
    proc = run_rerender(run.path, out)
    assert proc.returncode == 3, proc.output
    assert "원본 실행 폴더" in proc.stderr
    assert snapshot(run.path) == before


def test_refuses_out_inside_repo_outside_workspace(tmp_path):
    run = fake_run(tmp_path)
    out = ROOT / "tests" / "purpose-rerender-refused"
    assert not out.exists(), "앞 실행이 남긴 폴더: {} — 지우고 다시 돌린다".format(out)
    try:
        proc = run_rerender(run.path, out)
        assert proc.returncode == 3, proc.output
        assert "_workspace/ 밖" in proc.stderr
        assert not out.exists()
    finally:
        # 거부가 깨져 저장소 안에 폴더가 생겼으면 시험이 지운다(test-rules ⑤)
        if out.exists():
            shutil.rmtree(out, onexc=lambda func, path, _e: (os.chmod(path, 0o700), func(path)))


def test_refuses_target_without_approval_request(tmp_path):
    run = fake_run(tmp_path)
    proc = run_rerender(run.path, tmp_path / "out", task="T003")
    assert proc.returncode == 3, proc.output
    assert "approval_requested가 없음" in proc.stderr
    assert not (tmp_path / "out").exists()
