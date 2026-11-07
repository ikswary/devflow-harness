"""1.2.0 A15: `한 장 올리기`가 허용이면 승인을 일반 메시지로 묻는다(모바일에서 앞선 본문과 코드가 보이지 않는다)."""
import pytest

from conftest import run_script, write
from test_sheet import NEW, task

ASK = "묻기: 한 장 올리기 허용"


def upload(run_dir, value):
    path = run_dir.path / "run.md"
    write(path, path.read_text(encoding="utf-8") + "| 한 장 올리기 | {} |\n".format(value))


@pytest.mark.parametrize("value,shown", [("허용", True), ("없음", False)])
def test_save_says_how_to_ask(run_dir, value, shown):
    upload(run_dir, value)
    task(run_dir, material="문제와 고치는 법", decide="- 고를 것 (가) 예", status="승인대기")
    proc = run_script("screen", run_dir, "T001", "--save")
    assert proc.returncode == 0, proc.output
    assert (ASK in proc.output) is shown
    assert ASK not in (run_dir.task_dir("T001") / "screen-shown.md").read_text(encoding="utf-8")


def test_row_taken_back_returns_to_the_tool(run_dir):
    upload(run_dir, "허용")
    upload(run_dir, "없음")
    task(run_dir, material="문제와 고치는 법", status="승인대기")
    assert ASK not in run_script("screen", run_dir, "T001", "--save").output


def test_screen_body_does_not_change(run_dir):
    task(run_dir, material="문제와 고치는 법", status="승인대기")
    before = run_script("screen", run_dir, "T001").output
    upload(run_dir, "허용")
    assert before == run_script("screen", run_dir, "T001").output
    assert NEW
