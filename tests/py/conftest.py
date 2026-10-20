"""하네스 스크립트 시험의 공용 준비.

- 저장소의 `scripts/`를 import 경로 맨 앞에 넣고 라이브러리 모듈을 `lib`로 내준다. 시험 파일은 라이브러리를
  모듈 이름으로 import하지 않고 `lib`만 쓴다.
- 실행 폴더를 임시 폴더(`tmp_path`) 아래에 만드는 도우미(`RunDir`)와 스크립트를 명령행으로 돌리는 도우미(`run_script`).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

if not SCRIPTS.is_dir():
    # 전제가 없으면 시작할 때 이유를 말하고 실패한다(test-rules ⑥)
    pytest.exit("scripts/ 폴더가 없음: {} — 저장소 루트에 하네스 스크립트를 두고 다시 돌린다".format(SCRIPTS), returncode=4)

sys.dont_write_bytecode = True   # scripts/ 아래에 __pycache__를 남기지 않는다
sys.path.insert(0, str(SCRIPTS))
import devflow_lib as lib  # noqa: E402  라이브러리를 모듈 이름으로 부르는 유일한 줄


@pytest.fixture(name="lib")
def _lib():
    """라이브러리 모듈. 시험 파일은 이 `lib`만 쓴다."""
    return lib


def run_script(name, *args, cwd=None):
    """`python3 -B scripts/{name}.py args…`를 돌려 (종료 코드, 표준 출력+표준 오류)를 담은 결과를 돌려준다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", str(SCRIPTS / (name + ".py"))] + [str(a) for a in args],
                          capture_output=True, text=True, encoding="utf-8", cwd=cwd, env=env, timeout=120)
    proc.output = proc.stdout + proc.stderr
    return proc


def _meta_value(value):
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(value) + "]"
    return "" if value is None else str(value)


def front_matter(meta):
    lines = ["---"]
    for key, value in meta.items():
        text = _meta_value(value)
        lines.append("{}: {}".format(key, text) if text else "{}:".format(key))
    lines.append("---")
    return "\n".join(lines) + "\n"


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


TASK_DEFAULTS = {"kind": "design", "block": "설계", "status": "대기", "parent": "", "depends_on": [], "flow": "",
                 "commit": "", "running_agent": "", "n_decide": "0", "created": "2026-10-15 09:00:00", "started": ""}


class RunDir:
    """임시 실행 폴더. `run.md`, `tasks/{id}/task.md`·`result.md`·`judge.md`, `flows/{흐름}/flow.md`를 만든다."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        # run.md에는 `kind:` 줄을 두지 않는다(그 값을 읽는 스크립트는 대시보드뿐)
        write(self.path / "run.md", front_matter({"status": "진행", "round": "1", "harness_version": "", "start_task": "T001"})
              + "## 요청 원문\n마른 시험\n\n## 이번 실행의 값\n| 값 | 이번 실행 |\n|---|---|\n"
              "| 동시에 도는 흐름 | 2 |\n| 수정 세대 상한 | 2 |\n")

    def __str__(self):
        return str(self.path)

    def task_dir(self, tid):
        return self.path / "tasks" / tid

    def task(self, tid, title, sections=None, **meta):
        """머리 파일을 쓴다. sections는 {절 제목: 내용}(없으면 범위·판정 기준·건드릴 파일·승인 기록을 빈 꼴로)."""
        head = {"id": tid}
        head.update(TASK_DEFAULTS)
        head["title"] = title
        head.update(meta)
        body = {"범위": "- 마른 시험", "판정 기준": "1. 마른 시험", "건드릴 파일": "(없음)", "승인 기록": ""}
        body.update(sections or {})
        text = front_matter(head) + "\n" + "".join("## {}\n{}\n\n".format(k, v) for k, v in body.items())
        return write(self.task_dir(tid) / "task.md", text)

    def result(self, tid, text):
        return write(self.task_dir(tid) / "result.md", text)

    def judge(self, tid, text):
        return write(self.task_dir(tid) / "judge.md", text)

    def flow(self, name, **meta):
        head = {"flow": name, "role": "feature", "round": "1", "branch": "", "dir": "", "status": "폴더 없음"}
        head.update(meta)
        return write(self.path / "flows" / name / "flow.md", front_matter(head))

    def tasks(self):
        return lib.load_tasks(str(self.path))


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def run_dir(workspace):
    return RunDir(workspace / "dryrun")
