"""판본 계산과 판본이 다를 때의 거부,
판정자 정의 검사의 검출과 문구.

- 판본 = 하네스 폴더의 `.claude-plugin/plugin.json`의 `version` 문자열. 읽지 못하면 `?`.
- 같음 = 둘 다 비지 않고 앞뒤 공백을 뺀 문자열이 같음.
- 판본 값과 비교는 함수 단위로, `대기`→`진행` 거부와 `board.py --ready`의 판본 줄은 명령행 한 사례씩으로 본다.
  명령행 사례는 저장소의 매니페스트를 그대로 읽는다(가정 A-5의 저장소 판).
- 정의 검사는 함수 단위(`agent_def_problems(agents_dir=임시 폴더)`)로 검출과 문구를 보고, 기본 폴더(저장소 `agents/`)는
  문제 0인 한 사례로 본다.
"""
import json

import kinds
from conftest import ROOT, run_script, write

OLD_FORM = "0.9.0"   # 지금 판본과 다른 판본 표본
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"


def repo_version():
    """저장소 매니페스트의 `version`. 없으면 시작 지점에서 이유를 말하고 실패한다(test-rules ⑥)."""
    assert MANIFEST.is_file(), "매니페스트가 없음: {} — 저장소 루트에 .claude-plugin/plugin.json을 둔다".format(MANIFEST)
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    assert isinstance(value, str) and value.strip(), "매니페스트의 version이 빈 문자열이 아님을 전제로 한다: {!r}".format(value)
    return value


def set_run_version(run_dir, value):
    p = run_dir.path / "run.md"
    text = p.read_text(encoding="utf-8")
    assert "harness_version:\n" in text
    write(p, text.replace("harness_version:\n", "harness_version: {}\n".format(value)))


def front_value(run_dir, key, tid="T001"):
    for line in (run_dir.task_dir(tid) / "task.md").read_text(encoding="utf-8").splitlines():
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


# ================================================================ 판본 값 (함수 단위)

def test_version_is_plugin_json_version(lib, tmp_path):
    write(tmp_path / ".claude-plugin" / "plugin.json", json.dumps({"name": "x", "version": "9.8.7"}))
    assert lib.harness_version(str(tmp_path)) == "9.8.7"


def test_version_default_dir_reads_repo_manifest(lib):
    assert lib.harness_version() == repo_version()


def test_version_without_plugin_json_is_question_mark(lib, tmp_path):
    (tmp_path / ".claude-plugin").mkdir()
    assert not (tmp_path / ".claude-plugin" / "plugin.json").exists()
    assert lib.harness_version(str(tmp_path)) == "?"


# ================================================================ 판본 비교 (함수 단위)

def test_old_form_differs_from_current(lib):
    now = lib.harness_version()
    assert now == repo_version()
    assert lib.same_version(now, OLD_FORM) is False
    assert lib.same_version(OLD_FORM, now) is False


def test_same_value_is_same(lib):
    now = lib.harness_version()
    assert lib.same_version(now, now) is True
    assert lib.same_version(" {} ".format(now), now + "\n") is True   # 앞뒤 공백은 빼고 비교
    assert lib.same_version(OLD_FORM, OLD_FORM) is True


def test_empty_is_never_same(lib):
    assert lib.same_version("", "") is False
    assert lib.same_version("  ", "  ") is False
    assert lib.same_version("1.0.0", "1.0.0") is True   # 같은 꼴의 비지 않은 값은 같음(양성 대조)


# ================================================================ 대기→진행 거부 (명령행 한 사례)

def test_cli_wait_to_run_rejected_for_old_form_run_version(run_dir):
    set_run_version(run_dir, OLD_FORM)
    run_dir.task("T001", "판본 시험")
    r = run_script("task_set", run_dir, "T001", "--status", "진행")
    assert r.returncode == 3, r.output
    lines = [l for l in r.stdout.splitlines() if l.startswith("거부: T001 — ")]
    assert len(lines) == 1, r.output
    assert "하네스 판본" in lines[0]
    assert "run.md 하네스 판본({})이 지금 판본({})과 다름".format(OLD_FORM, repo_version()) in lines[0]
    assert front_value(run_dir, "status") == "대기"


def test_cli_wait_to_run_allowed_for_current_run_version(run_dir):
    # 위 거부의 양성 대조: run.md 판본이 지금 판본과 같으면 같은 명령이 통과한다
    set_run_version(run_dir, repo_version())
    run_dir.task("T001", "판본 시험")
    r = run_script("task_set", run_dir, "T001", "--status", "진행")
    assert r.returncode == 0, r.output
    assert "T001: 대기→진행" in r.stdout.splitlines()
    assert front_value(run_dir, "status") == "진행"
    assert front_value(run_dir, "started_version") == repo_version()


# ================================================================ board.py --ready 판본 줄 (명령행)

def version_lines(r):
    return [l for l in r.stdout.splitlines() if l.startswith("하네스 판본:")]


def test_board_ready_version_line_same(run_dir):
    v = repo_version()
    set_run_version(run_dir, v)
    r = run_script("board", run_dir, "--ready")
    assert r.returncode == 0, r.output
    assert version_lines(r) == ["하네스 판본: 지금 {0} / run.md {0} — 같음".format(v)], r.output


def test_board_ready_version_line_differs_for_old_form(run_dir):
    v = repo_version()
    set_run_version(run_dir, OLD_FORM)
    r = run_script("board", run_dir, "--ready")
    assert r.returncode == 0, r.output
    lines = version_lines(r)
    assert len(lines) == 1, r.output
    assert lines[0].startswith("하네스 판본: 지금 {} / run.md {} — 다름".format(v, OLD_FORM)), lines[0]


# ================================================================ 판정자 정의 검사 (함수 단위)

DEF_NAMES = ("read-judge.md", "run-judge.md")
OLD_MARKER_LINE = "판 표지: `old-def: {}`"   # 이름이 다른 판 표지 표본


def marker_line(value):
    return "판 표지: `def-version: {}`".format(value)


def write_def(folder, name, marker, tools="Read, Grep, Glob, Bash, Write"):
    """판정자 정의 한 파일을 저장소 정의와 같은 꼴(frontmatter의 tools 줄, 본문의 판 표지 줄)로 쓴다."""
    write(folder / name, "---\nname: {}\ntools: {}\n---\n\n{}\n".format(name[:-3], tools, marker))


def test_def_both_present_marker_at_or_above_min_is_clean(lib, tmp_path):
    write_def(tmp_path, "read-judge.md", marker_line(kinds.DEF_VERSION_MIN))   # 최소값과 같음
    write_def(tmp_path, "run-judge.md", marker_line("2026-10-09-later"))     # 최소값보다 새것
    assert lib.agent_def_problems(str(tmp_path)) == []


def test_def_missing_file_is_reported(lib, tmp_path):
    write_def(tmp_path, "read-judge.md", marker_line(kinds.DEF_VERSION_MIN))
    assert lib.agent_def_problems(str(tmp_path)) == ["run-judge.md 없음"]


def test_def_old_marker_name_only_is_reported(lib, tmp_path):
    for name in DEF_NAMES:
        write_def(tmp_path, name, OLD_MARKER_LINE.format(kinds.DEF_VERSION_MIN))
    need = "판 표지 def-version(필요 {} 이상)".format(kinds.DEF_VERSION_MIN)
    assert lib.agent_def_problems(str(tmp_path)) == ["{}: {}".format(n, need) for n in DEF_NAMES]


def test_def_marker_older_than_min_is_reported(lib, tmp_path):
    write_def(tmp_path, "read-judge.md", marker_line(kinds.DEF_VERSION_MIN))
    write_def(tmp_path, "run-judge.md", marker_line("2026-10-07-bundle1"))
    assert lib.agent_def_problems(str(tmp_path)) == [
        "run-judge.md: 판 표지 def-version 2026-10-07-bundle1가 {}보다 옛것".format(kinds.DEF_VERSION_MIN)]


def test_def_tools_without_write_is_reported(lib, tmp_path):
    write_def(tmp_path, "read-judge.md", marker_line(kinds.DEF_VERSION_MIN), tools="Read, Grep, Glob, Bash")
    write_def(tmp_path, "run-judge.md", marker_line(kinds.DEF_VERSION_MIN))
    assert lib.agent_def_problems(str(tmp_path)) == ["read-judge.md: tools에 Write"]


def test_def_default_dir_is_repo_agents(lib, tmp_path, monkeypatch):
    # 기본 폴더는 저장소의 agents/다. 사용자 홈을 빈 임시 폴더로 바꿔도 결과가 같아야 한다(홈의 정의에 기대지 않음)
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in DEF_NAMES:
        text = (ROOT / "agents" / name).read_text(encoding="utf-8")
        assert marker_line(kinds.DEF_VERSION_MIN) in text, name   # 전제: 저장소 정의가 최소 판 표지를 가짐
    assert lib.agent_def_problems() == []
