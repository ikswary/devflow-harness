"""목적 시험 준비(`tests/purpose/setup_task.py`)와 지시문 틀(`tests/purpose/prompts.md`).

- 가짜 자료(작은 코드 폴더, task 넷, 흐름 하나, 앞 실행 결정, 원래 run.md)를 `tmp_path`에 지어 스크립트를 돌린다.
- 실제 자료로 한 번 돌리는 것은 이 시험이 아니다(자료는 저장소 밖, tests/purpose/README.md).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, RunDir, front_matter, write

PURPOSE = ROOT / "tests" / "purpose"
SETUP = PURPOSE / "setup_task.py"
PROMPTS = PURPOSE / "prompts.md"
APPROVER = "결과를 모르는 승인자 지시문"
TARGET = "T002"
RUN_NAME, PRIOR_NAME = "2026-01-02-sample-run", "2026-01-01-sample-prior"
CRITERIA_ORIG = "1. 처음 판정 기준"
SOURCE_SECTIONS = {"요청 원문": "\"표본 요청\" (2026-01-02)\n\n요청 종류: 표본", "이번 실행의 값": "| 값 | 이번 실행 |\n|---|---|\n| 동시에 도는 흐름 | 2 |"}

if shutil.which("git") is None:
    # 전제가 없으면 시작할 때 이유를 말하고 실패한다(test-rules ⑥)
    pytest.exit("git을 찾지 못함 — 목적 시험 준비는 코드 사본을 시험용 git으로 만든다. git을 PATH에 두고 다시 돌린다", returncode=4)


def load_setup():
    spec = importlib.util.spec_from_file_location("purpose_setup_task", SETUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plugin_version():
    return json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def run_setup(data, out, task=TARGET):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", str(SETUP), "--data", str(data), "--task", task, "--out", str(out),
                           "--source-run-md", str(data / "source-run.md"), "--run-name", RUN_NAME,
                           "--prior-name", PRIOR_NAME],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    proc.output = proc.stdout + proc.stderr
    return proc


def git(code, *args):
    proc = subprocess.run(["git", "-C", str(code)] + list(args), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def fake_data(base):
    """가짜 자료 폴더. T001은 대상보다 먼저, T003은 늦게, T009는 머리 파일 없는 폴더."""
    data = base / "data"
    src = data / TARGET
    write(src / "code" / "app.txt", "표본 코드\n")
    run = RunDir(src / "run")
    run.task("T001", "앞 task", status="완료", created="2026-01-02 09:00:00")
    sections = {"범위": "- 표본", "판정 기준": "1. 고친 판정 기준", "판정 기준 정정": "- 정정 한 줄",
                "재시도 범위": "- 기준 1", "건드릴 파일": "(없음)", "넘길 이상 신호": "- 앞 신호",
                "승인 기록": "- 2026-01-02 11:00:00 | 승인 | 표본 | 원문: \"좋음\""}
    run.task(TARGET, "대상 task", sections=sections, status="완료", created="2026-01-02 10:00:00", retry="2",
             started_version="1.2.1", approval_mode="승인", n_decide="1", running_agent="design-T002")
    run.task("T003", "늦은 task", status="대기", created="2026-01-02 12:00:00")
    write(run.task_dir("T009") / "note.md", "머리 파일 없음\n")
    tdir = run.task_dir(TARGET)
    write(tdir / "criteria.orig.md", CRITERIA_ORIG + "\n")
    for name in ("result.md", "judge.md", "judge.r1.md", "facts.md", "screen-T002.txt", "criteria.amend1.md",
                 "main-run.md", "before.r1/result.md", "design-copy/hashes.md"):
        write(tdir / name, "지울 것\n")
    write(run.path / "approved" / "asked" / (TARGET + "-1.md"), "대상의 물음\n")
    write(run.path / "approved" / ("T001" + "-1.md"), "앞 task의 승인\n")
    write(run.path / "asked" / (TARGET + "-card"), "대상의 카드\n")
    run.flow("f1", dir="D:/old/place", status="폴더 있음")
    write(src / "prior-run" / "decisions.md", "- 앞 실행 결정\n")
    write(data / "source-run.md", front_matter({"kind": "devflow-harness", "status": "완료", "base_branch": "dev",
                                                 "harness_version": "1.2.1"})
          + "".join("## {}\n{}\n\n".format(k, v) for k, v in SOURCE_SECTIONS.items())
          + "## 시작 때 원래 폴더의 git status\n- 옮기지 않는 절\n")
    return data


@pytest.fixture
def prepared(tmp_path):
    data = fake_data(tmp_path)
    out = tmp_path / "out"
    proc = run_setup(data, out)
    assert proc.returncode == 0, proc.output
    code = out / TARGET / "code"
    return {"proc": proc, "data": data, "out": out, "code": code, "run": code / "_workspace" / RUN_NAME}


def test_later_tasks_and_target_traces_are_gone(prepared, lib):
    run = prepared["run"]
    assert sorted(os.listdir(run / "tasks")) == ["T001", TARGET]
    assert sorted(os.listdir(run / "tasks" / TARGET)) == ["criteria.orig.md", "task.md"]
    assert not (run / "approved" / "asked" / (TARGET + "-1.md")).exists()
    assert not (run / "asked" / (TARGET + "-card")).exists()
    assert (run / "approved" / "T001-1.md").is_file()   # 다른 task의 흔적은 둔다(양성 대조)


def test_target_head_is_back_to_start(prepared, lib):
    t = lib.load_tasks(str(prepared["run"]))[TARGET]
    secs = t["_sections"]
    assert secs["판정 기준"] == CRITERIA_ORIG
    assert "판정 기준 정정" not in secs and "재시도 범위" not in secs
    assert secs["넘길 이상 신호"] == "(없음)"
    assert secs["승인 기록"] == ""
    assert secs["범위"] == "- 표본"   # 다른 절은 그대로
    assert t["status"] == "진행"
    assert t["started_version"] == plugin_version()
    assert (t["retry"], t["approval_mode"], t["n_decide"], t["running_agent"]) == ("0", "", "0", "")


def test_run_md_flow_and_prior_decisions(prepared, lib):
    run, code = prepared["run"], prepared["code"]
    meta_lines, body = lib.split_front_matter(lib.read_text(str(run / "run.md")))
    meta = lib.parse_meta(meta_lines)
    assert meta["harness_version"] == plugin_version()
    assert (meta["status"], meta["project"], meta["base_branch"]) == ("진행", str(code), "dev")
    assert lib.sections(body) == SOURCE_SECTIONS
    flow = lib.Doc(str(run / "flows" / "f1" / "flow.md"))
    assert flow.get("dir") == str(code)
    assert (code / "_workspace" / PRIOR_NAME / "decisions.md").read_text(encoding="utf-8") == "- 앞 실행 결정\n"


def test_code_copy_is_one_commit_without_workspace(prepared):
    code = prepared["code"]
    assert git(code, "rev-list", "--count", "HEAD").strip() == "1"
    assert git(code, "ls-files").split() == ["app.txt"]
    assert git(code, "status", "--porcelain") == ""   # _workspace/는 제외되어 보이지 않음
    assert "_workspace/" in (code / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert (prepared["out"] / TARGET / ".purpose-sandbox").is_file()
    assert prepared["proc"].stdout.splitlines()[-1] == "준비됨: {}".format(prepared["run"])


def test_rerun_replaces_folder_with_marker(prepared):
    stray = prepared["out"] / TARGET / "stray.txt"
    stray.write_text("남은 것\n", encoding="utf-8")
    proc = run_setup(prepared["data"], prepared["out"])
    assert proc.returncode == 0, proc.output
    assert not stray.exists()
    assert (prepared["out"] / TARGET / ".purpose-sandbox").is_file()


def test_refuses_existing_folder_without_marker(tmp_path):
    data = fake_data(tmp_path)
    out = tmp_path / "out"
    keep = write(out / TARGET / "mine.txt", "사람의 파일\n")
    proc = run_setup(data, out)
    assert proc.returncode == 3, proc.output
    assert "표지 .purpose-sandbox가 없음" in proc.stderr
    assert sorted(os.listdir(out / TARGET)) == ["mine.txt"]
    assert keep.read_text(encoding="utf-8") == "사람의 파일\n"


def test_refuses_out_inside_repo_outside_workspace(tmp_path):
    data = fake_data(tmp_path)
    out = ROOT / "tests" / "purpose-out-refused"
    assert not out.exists(), "앞 실행이 남긴 폴더: {} — 지우고 다시 돌린다".format(out)
    try:
        proc = run_setup(data, out)
        assert proc.returncode == 3, proc.output
        assert "_workspace/ 밖" in proc.stderr
        assert not out.exists()
    finally:
        # 거부가 깨져 저장소 안에 폴더가 생겼으면 시험이 지운다(test-rules ⑤)
        if out.exists():
            shutil.rmtree(out, onexc=lambda func, path, _e: (os.chmod(path, 0o700), func(path)))


def test_out_rule_accepts_workspace_and_outside(tmp_path):
    module = load_setup()
    assert module.out_refusal(str(ROOT / "tests" / "x")) is not None
    assert module.out_refusal(str(ROOT)) is not None
    assert module.out_refusal(str(ROOT / "_workspace" / "purpose")) is None
    assert module.out_refusal(str(ROOT / "_workspace")) is None
    assert module.out_refusal(str(tmp_path)) is None


def _make_link(link, target):
    """디렉터리 연결(Windows는 연결점, 그 밖은 심볼릭 링크). 만들 수 없으면 None을 돌려준다."""
    if os.name == "nt":
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        return link if proc.returncode == 0 else None
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
    except OSError:
        return None
    return link


def test_out_rule_resolves_links_into_repo(tmp_path):
    module = load_setup()
    link = _make_link(tmp_path / "repo-link", ROOT)
    if link is None:
        pytest.skip("디렉터리 연결을 만들 수 없음")
    try:
        # 저장소를 가리키는 연결을 거쳐도 _workspace/ 밖이면 거부, 안이면 허용
        assert module.out_refusal(str(link / "tests" / "x")) is not None
        assert module.out_refusal(str(link / "_workspace" / "purpose")) is None
        # root가 연결 표기로 와도 같은 판단
        assert module.out_refusal(str(ROOT / "tests" / "x"), root=str(link)) is not None
    finally:
        if os.name == "nt":
            os.rmdir(str(link))   # 연결점만 지우고 대상은 남긴다
        else:
            os.unlink(str(link))


def test_refuses_data_not_in_shape(tmp_path):
    data = fake_data(tmp_path)
    shutil.rmtree(data / TARGET / "prior-run")
    proc = run_setup(data, tmp_path / "out")
    assert proc.returncode == 3, proc.output
    assert "자료 꼴이 아님" in proc.stderr
    assert not (tmp_path / "out").exists()


# --- 지시문 틀 ---

ANSWER_WORDS = re.compile(r"정답|ground|eval-|J\d")


def approver_section():
    """`## 결과를 모르는 승인자 지시문` 절 전체. 울타리 안의 `## ` 줄(승인자가 쓸 절)은 절 경계가 아니다."""
    secs = {}
    current = None
    fenced = False
    for line in PROMPTS.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if line.startswith("## ") and not fenced:
            current = line[3:].strip()
            secs[current] = []
        elif current:
            secs[current].append(line)
    assert APPROVER in secs, "prompts.md에 「{}」 절이 없음(절: {})".format(APPROVER, list(secs))
    return "\n".join(secs[APPROVER])


def test_approver_prompt_has_no_answer_key_words():
    text = approver_section()
    # 절을 끝까지 읽었는지(양성 대조): 아홉 문항의 첫 줄과 끝 줄이 든다
    assert "## 1. 답" in text and "## 9. 이 꼴로 계속 받는다면" in text
    assert ANSWER_WORDS.findall(text) == []


@pytest.mark.parametrize("word", ["정답지", "ground truth", "eval-purpose", "J03", "J21"])
def test_answer_word_pattern_catches(word):
    assert ANSWER_WORDS.search("앞 {} 뒤".format(word))


def test_pytest_does_not_collect_purpose_folder():
    names = [p.name for p in PURPOSE.rglob("*.py")]
    assert "setup_task.py" in names
    assert [n for n in names if n.startswith("test_") or n.endswith("_test.py") or n == "conftest.py"] == []
