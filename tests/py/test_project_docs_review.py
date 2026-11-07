"""A13 리뷰의 재현: 사람이 본 것과 넣은 것이 다른데 `승인한 그대로`로 적히거나 사용자 문서를 말없이 지우는 길, 훅과 생성 명령의 안전장치."""
import os
import sys
import time

import pytest

import devflow_lib
import project_docs
import task_set
import visual
from conftest import run_script, write
from test_project_docs import (BRIEF, NEW, _project, approved_task, commit_all, git, hook_path, insert, review, settings, started, wrap)  # noqa: F401

CHANGE = BRIEF.replace("하루 한 번", "하루 두 번")
DOC = "docs/product/brief.md"


def table(run_dir, tid="T090"):
    return (run_dir.task_dir(tid) / project_docs.INSERT_FILE).read_text(encoding="utf-8")


def read(path):
    return path.read_text(encoding="utf-8")


def first_of(joined):
    return joined.split("## 먼저 보실 것")[1].split("##")[0] if "## 먼저 보실 것" in joined else ""


# ---------------------------------------------------------------- R-C1 앞 정본 줄


def later_task(run_dir, line, tid="T020", **meta):
    record = task_set.record_line(("승인", "승인 화면", "(가)로 하세요"))
    run_dir.task(tid, "뒤 task", {"승인 기록": record}, kind="design", block="설계", status="완료", **dict(NEW, **meta))
    run_dir.result(tid, "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 가/나\n  - " + line + "\n")
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()[tid])
    return run_dir.tasks()[tid]


def test_prior_line_does_not_launder_an_unexplained_edit(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("가입한다", "몰래 고침"))
    t = later_task(run_dir, "선택지 (가)의 앞 정본 줄: spec/brief.md:3 | 지금: 하루 한 번 | 바뀜: 하루 두 번")
    assert project_docs.stamp_task(str(run_dir.path), t) == []
    wrap(run_dir)
    insert(run_dir, project)
    joined = review(run_dir)
    assert "승인 뒤 달라짐: " + DOC in joined and "승인한 그대로: " + DOC not in joined
    assert "+몰래 고침" in joined


def test_prior_line_stamps_when_the_diff_is_exactly_that_line(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF)
    write(run_dir.path / "spec" / "brief.md", CHANGE)
    t = later_task(run_dir, "선택지 (가)의 앞 정본 줄: spec/brief.md:3 | 지금: 하루 한 번 | 바뀜: 하루 두 번")
    assert project_docs.stamp_task(str(run_dir.path), t) == ["spec\\brief.md"]
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["task"] == "T020"


def test_prior_line_of_an_unchosen_option_keeps_the_notified_mark(run_dir, project):
    """R-C15: 표시를 지우지 않는다."""
    started(run_dir, project)
    approved_task(run_dir, text=CHANGE, approval_mode="알림")
    t = later_task(run_dir, "선택지 (나)의 앞 정본 줄: spec/brief.md:3 | 지금: 하루 두 번 | 바뀜: 하루 세 번")
    assert project_docs.stamp_task(str(run_dir.path), t) == []
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["via"] == project_docs.NOTIFIED


# ---------------------------------------------------------------- R-C2 승인 화면 뒤


def asked_task(run_dir, shown, result="# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n"):
    write(run_dir.path / "spec" / "brief.md", shown)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="승인대기", **NEW)
    run_dir.result("T010", result)
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()["T010"])


def test_edit_while_waiting_is_not_what_the_person_approved(run_dir, project):
    started(run_dir, project)
    asked_task(run_dir, BRIEF.replace("하루 한 번", "화면에 보인 판"))
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "화면에 없던 판"))
    project_docs.stamp_task(str(run_dir.path), run_dir.tasks()["T010"])
    wrap(run_dir)
    insert(run_dir, project)
    joined = review(run_dir)
    assert "승인 화면 뒤 달라짐: " + DOC in joined and "승인한 그대로" not in joined
    assert "-하루 화면에 보인 판"[:1] + "화면에 보인 판" in joined and "+화면에 없던 판" in joined
    assert "승인 화면 뒤 달라짐 1" in first_of(joined)


def test_deleted_line_while_waiting_is_not_explained(run_dir, project):
    started(run_dir, project)
    asked_task(run_dir, CHANGE)
    write(run_dir.path / "spec" / "brief.md", CHANGE.replace("가입한다\n", ""))
    project_docs.stamp_task(str(run_dir.path), run_dir.tasks()["T010"])
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["via"] == project_docs.AFTER_SCREEN


def test_notified_path_has_no_snapshot_to_compare(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=CHANGE, approval_mode="알림")
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["via"] == project_docs.NOTIFIED


def test_revised_file_changed_while_waiting_is_flagged_by_apply_revision(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF)
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="승인대기", **NEW)
    run_dir.result("T011", "# 결과\n")
    revised = run_dir.task_dir("T011") / "revised" / "spec" / "brief.md"
    write(revised, CHANGE)
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()["T011"])
    write(revised, BRIEF.replace("하루 한 번", "하루 아홉 번"))
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="완료", **NEW)
    assert run_script("apply_revision", run_dir, "T011").returncode == 0
    wrap(run_dir)
    insert(run_dir, project)
    joined = review(run_dir)
    assert "승인 화면 뒤 달라짐: " + DOC in joined and "+하루 아홉 번" in joined


def test_asking_transition_takes_the_snapshot(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T013", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="자체검증", **NEW)
    run_dir.result("T013", "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n")
    run_dir.judge("T013", "판정자: rjudge-T013 2026-11-06 10:00:00\n# T013 판정\n\n## 통과 못 한 기준\n- 없음\n")
    out = run_script("task_set", run_dir, "T013", "--status", "승인대기")
    assert out.returncode == 0, out.output
    assert (run_dir.path / "approved" / "asked" / "T013" / "spec" / "brief.md").is_file()


# ---------------------------------------------------------------- R-C3 겹치는 제목


REPEAT = "# 기획\n\n## 예외\n첫째\n\n## 정책\n하루 한 번\n\n## 예외\n둘째\n"


def test_repeated_titles_stop_instead_of_losing_a_section(run_dir, project):
    write(project / "docs" / "product" / "brief.md", REPEAT)
    commit_all(project)
    started(run_dir, project)
    approved_task(run_dir, text=REPEAT.replace("하루 한 번", "하루 두 번"))
    write(project / "docs" / "product" / "brief.md", REPEAT + "\n## 새 절\n프로젝트 쪽\n")
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 3
    assert "첫째" in read(project / "docs" / "product" / "brief.md")
    assert project_docs.TWO_PLACES + ": " + DOC + " " + project_docs.WHOLE_FILE in review(run_dir)
    assert insert(run_dir, project, "T090", "--take", DOC + "#(파일 전체)=프로젝트").returncode == 0
    assert "새 절" in read(project / "docs" / "product" / "brief.md")


# ---------------------------------------------------------------- R-C4 흐름 문서


FLOW = "docs/architecture/flows/pay.md"


def flow_project(project, text):
    write(project / FLOW, text)
    commit_all(project)


def test_flow_document_keeps_sections_it_does_not_insert(run_dir, project):
    base = "# 흐름\n\n## 배경\n사람이 쓴 배경\n\n## 결정\n가\n"
    flow_project(project, base)
    started(run_dir, project)
    approved_task(run_dir, "T010", "design/pay.md", "# 설계\n\n## 결정\n나\n\n## 자식 행\n- T1\n")
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 0
    text = read(project / FLOW)
    assert "사람이 쓴 배경" in text and "나" in text and "T1" not in text


def test_flow_document_keeps_subsections_it_does_not_insert(run_dir, project):
    base = "# 흐름\n\n## 제안 도면\n### 사람 메모\n남길 글\n\n### 기능 흐름도\nA\n"
    flow_project(project, base)
    started(run_dir, project)
    approved_task(run_dir, "T010", "design/pay.md", "# 설계\n\n## 제안 도면\n### 기능 흐름도\nB\n### 구조도\nC\n")
    wrap(run_dir)
    insert(run_dir, project)
    text = read(project / FLOW)
    assert "남길 글" in text and "\nB" in text and "\nC" not in text


def test_flow_with_unchanged_decisions_is_not_listed(run_dir, project):
    flow_project(project, "# 흐름\n\n## 배경\n글\n\n## 결정\n가\n")
    started(run_dir, project)
    approved_task(run_dir, "T010", "design/pay.md", "# 설계\n\n## 결정\n가\n\n## 자식 행\n- T1\n")
    wrap(run_dir)
    insert(run_dir, project)
    assert FLOW not in table(run_dir)


def test_flow_with_repeated_titles_asks_even_when_only_this_run_changed(run_dir, project):
    flow_project(project, "# 흐름\n\n## 결정\n가\n\n## 배경\n글\n\n## 결정\n다\n")
    started(run_dir, project)
    approved_task(run_dir, "T010", "design/pay.md", "# 설계\n\n## 결정\n나\n")
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 3
    assert "## 배경" in read(project / FLOW)


# ---------------------------------------------------------------- R-C5 용어집


GLOSSARY = "docs/product/glossary.md"
TERMS = "# 용어집\n\n## 결제\n- 승인: 앞 실행이 쌓은 말\n\n## 계정\n- 회원\n"


def test_overview_terms_add_to_the_glossary_without_removing(run_dir, project):
    write(project / GLOSSARY, TERMS)
    commit_all(project)
    started(run_dir, project)
    approved_task(run_dir, "T010", "spec/overview.md", "# 개요\n\n## 용어\n- 새말: 이번 실행\n")
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 0
    text = read(project / GLOSSARY)
    assert "앞 실행이 쌓은 말" in text and "- 회원" in text and "- 새말: 이번 실행" in text


def test_existing_terms_change_nothing(run_dir, project):
    write(project / GLOSSARY, TERMS)
    commit_all(project)
    started(run_dir, project)
    approved_task(run_dir, "T010", "spec/overview.md", "# 개요\n\n## 용어\n- 회원\n")
    wrap(run_dir)
    insert(run_dir, project)
    assert GLOSSARY not in table(run_dir)


def test_own_glossary_file_is_the_only_row_for_that_document(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, "T010", "spec/overview.md", "# 개요\n\n## 용어\n- 새말\n")
    approved_task(run_dir, "T011", "spec/glossary.md", "# 용어집\n\n- 승인받은 말\n")
    wrap(run_dir)
    insert(run_dir, project)
    assert table(run_dir).count(GLOSSARY) == 1
    assert "승인받은 말" in read(project / GLOSSARY)


# ---------------------------------------------------------------- R-C6 생성 명령의 안전장치


PY = '"{}"'.format(sys.executable)


def test_timeout_kills_the_whole_tree(project, monkeypatch, tmp_path):
    monkeypatch.setattr(project_docs, "GEN_TIMEOUT", 1)
    mark = tmp_path / "survived.txt"
    child = "import time;time.sleep(3);open(r'{}','w').write('x')".format(mark)
    write(project / "slow.py", "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',{!r}])\ntime.sleep(30)\n".format(child))
    began = time.monotonic()
    result = project_docs._launch("{} slow.py".format(PY), str(project))
    assert time.monotonic() - began < 15
    assert result["ok"] is False and result["text"] == "시간 초과 1초"
    time.sleep(3.5)
    assert not mark.exists()


def test_timeout_reason_does_not_carry_the_command(project, monkeypatch):
    monkeypatch.setattr(project_docs, "GEN_TIMEOUT", 1)
    write(project / "slow.py", "import time\ntime.sleep(30)\n")
    assert "slow.py" not in project_docs._launch("{} slow.py".format(PY), str(project))["text"]


def side_effect_settings(run_dir, project):
    write(project / "side.py", "open('src/side_output.py','w').write('x')\nprint('a')\n")
    settings(run_dir, "- 구조도 | {} side.py | docs/generated/s.md".format(PY))
    commit_all(project)


def test_generator_that_writes_in_the_folder_is_reported(run_dir, project):
    started(run_dir, project)
    side_effect_settings(run_dir, project)
    lines = project_docs.drawing_differences(str(run_dir.path), {"제안 도면": "### 구조도\n```\na\n```\n"}, str(project))
    assert "생성 명령이 코드 폴더를 고침: src/side_output.py (구조도)" in lines


def test_generate_and_check_report_the_folder_change_too(run_dir, project):
    started(run_dir, project)
    side_effect_settings(run_dir, project)
    wrap(run_dir)
    out = run_script("project_docs", run_dir, "T090", "--generate", project)
    assert "생성 명령이 코드 폴더를 고침: src/side_output.py" in out.output
    (project / "src" / "side_output.py").unlink()
    out = run_script("project_docs", run_dir, "T090", "--generate", project, "--check")
    assert "생성 명령이 코드 폴더를 고침: src/side_output.py" in out.output


def counting_settings(run_dir, project):
    write(project / "count.py", "import os\nopen(os.path.join(os.environ.get('TMP_COUNT','.'),'count.log'),'a').write('x')\nprint('a')\n")
    settings(run_dir, "- 구조도 | {} count.py | docs/generated/s.md".format(PY))
    write(project / ".gitignore", "count.log\n")
    commit_all(project)
    return project / "count.log"


def test_same_tip_runs_once_and_new_tip_runs_again(run_dir, project):
    started(run_dir, project)
    log = counting_settings(run_dir, project)
    opened = {"제안 도면": "### 구조도\n```\na\n```\n"}
    project_docs.drawing_differences(str(run_dir.path), opened, str(project))
    project_docs.drawing_differences(str(run_dir.path), opened, str(project))
    wrap(run_dir)
    run_script("project_docs", run_dir, "T090", "--generate", project)
    assert read(log) == "x"
    write(project / "src" / "b.py", "y\n")
    commit_all(project)
    project_docs.drawing_differences(str(run_dir.path), opened, str(project))
    assert read(log) == "xx"


def test_failure_does_not_block_generate_or_check(run_dir, project):
    started(run_dir, project)
    write(project / "boom.py", "raise SystemExit(5)\n")
    settings(run_dir, "- 구조도 | {} boom.py | docs/generated/s.md".format(PY))
    wrap(run_dir)
    for args in (["--generate", project], ["--generate", project, "--check"]):
        out = run_script("project_docs", run_dir, "T090", *args)
        assert out.returncode == 0 and "생성 실패: 구조도 (종료 코드 5)" in out.output


# ---------------------------------------------------------------- R-C19 파이프


def test_pipe_in_the_command_is_kept(run_dir, project):
    settings(run_dir, "- 구조도 | a | sort | docs/generated/s.md")
    assert project_docs.generators(str(run_dir.path)) == [("구조도", "a | sort", "docs/generated/s.md")]


def test_unreadable_generator_line_is_not_silent(run_dir, project):
    started(run_dir, project)
    settings(run_dir, "- 대상 없는 줄")
    wrap(run_dir)
    out = run_script("project_docs", run_dir, "T090", "--generate", project)
    assert "생성 명령 줄을 읽지 못함: 대상 없는 줄" in out.output
    lines = project_docs.drawing_differences(str(run_dir.path), {"제안 도면": ""}, str(project))
    assert lines == ["생성 명령 줄을 읽지 못함: 대상 없는 줄"]


# ---------------------------------------------------------------- 작성자가 낸 생성 명령


def proposing(run_dir, project):
    started(run_dir, project)
    write(project / "gen.py", "open('ran.txt','w').write('x')\nprint('a')\n")
    commit_all(project)
    run_dir.task("T090", "마무리", kind="wrap-up", block="마무리", status="승인대기", stage="실행승인", **NEW)
    run_dir.result("T090", "# 결과\n\n## 승인 화면\n### 리뷰 자료\n한 일\n### 정해 주실 것\n- 없음\n\n## 본문\n- 생성 명령 제안: 구조도 | {} gen.py | docs/generated/s.md\n".format(PY))


def test_proposed_command_is_shown_and_not_run_before_approval(run_dir, project):
    proposing(run_dir, project)
    joined = review(run_dir)
    assert "등록할 생성 명령: 구조도 | {} gen.py | docs/generated/s.md".format(PY) in joined
    assert "등록할 생성 명령 1" in first_of(joined)
    assert project_docs.generators(str(run_dir.path)) == []
    assert run_script("project_docs", run_dir, "T090", "--generate", project).returncode == 0
    assert not (project / "ran.txt").exists()


def test_non_approval_answer_does_not_register(run_dir, project):
    proposing(run_dir, project)
    run_dir.task("T090", "마무리", kind="wrap-up", block="마무리", status="진행", stage="실행", **NEW)
    task_set.after_docs_transition(str(run_dir.path), "T090", "진행", ("되물음(이해)", "", "이게 뭐죠"))
    assert project_docs.generators(str(run_dir.path)) == []


# ---------------------------------------------------------------- R-C7, R-C8 훅


def test_start_does_not_install_and_prints_a_question(run_dir, project):
    doc = devflow_lib.Doc(str(run_dir.path / "run.md"))
    doc.set("project", str(project))
    doc.set("base_branch", "dev")
    doc.save()
    out = run_script("project_docs", run_dir, "--start")
    assert out.returncode == 0 and "묻기:" in out.output and "--unhook" in out.output
    assert not hook_path(project).exists()


def test_hook_answer_is_kept_and_not_asked_again(run_dir, project):
    started(run_dir, project)
    assert run_script("project_docs", run_dir, "--hook").returncode == 0
    assert hook_path(project).is_file()
    assert "- git 훅 경고: 적용함" in read(run_dir.path.parent / devflow_lib.PROJECT_SETTINGS)
    assert "묻기:" not in run_script("project_docs", run_dir, "--start").output


def test_unhook_removes_ours_and_start_does_not_bring_it_back(run_dir, project):
    started(run_dir, project)
    run_script("project_docs", run_dir, "--hook")
    assert run_script("project_docs", run_dir, "--unhook").returncode == 0
    assert not hook_path(project).exists()
    out = run_script("project_docs", run_dir, "--start")
    assert "묻기:" not in out.output and not hook_path(project).exists()
    assert "- git 훅 경고: 안 함" in read(run_dir.path.parent / devflow_lib.PROJECT_SETTINGS)


def test_saying_no_without_a_hook_is_remembered(run_dir, project):
    started(run_dir, project)
    assert run_script("project_docs", run_dir, "--unhook").returncode == 0
    assert "묻기:" not in run_script("project_docs", run_dir, "--start").output


def test_unhook_leaves_a_user_hook_alone(run_dir, project):
    started(run_dir, project)
    raw = "#!/bin/sh\nexit 1\n".encode("utf-8")
    hook_path(project).write_bytes(raw)
    run_script("project_docs", run_dir, "--unhook")
    assert hook_path(project).read_bytes() == raw


def test_non_utf8_user_hook_is_not_overwritten(run_dir, project):
    started(run_dir, project)
    raw = "#!/bin/sh\n# 사용자 훅 주석\nexit 1\n".encode("cp949")
    hook_path(project).write_bytes(raw)
    out = run_script("project_docs", run_dir, "--hook")
    assert project_docs.HOOK_SKIPPED in out.output and hook_path(project).read_bytes() == raw


def test_broken_symlink_counts_as_a_user_hook(run_dir, project):
    started(run_dir, project)
    try:
        os.symlink(str(project / "없는 파일"), str(hook_path(project)))
    except (OSError, NotImplementedError):
        pytest.skip("이 환경에서 심볼릭 링크를 만들 수 없음")
    out = run_script("project_docs", run_dir, "--hook")
    assert project_docs.HOOK_SKIPPED in out.output and os.path.islink(hook_path(project))


def test_refused_start_when_the_hook_answer_is_on_refreshes_ours(run_dir, project):
    started(run_dir, project)
    run_script("project_docs", run_dir, "--hook")
    write(hook_path(project), "# " + project_docs.HOOK_MARK + " 옛 경로\n")
    run_script("project_docs", run_dir, "--start")
    assert "--hook-check" in read(hook_path(project))


# ---------------------------------------------------------------- R-C9 머리글, 넣지 않은 글


@pytest.mark.parametrize("spec,word", [("#(머리글)=이번 실행", "이번 실행 머리"), ("#=이번 실행", "이번 실행 머리"), ("#(머리글)=프로젝트", "프로젝트 머리")])
def test_header_conflict_can_be_answered(run_dir, project, spec, word):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("# 기획\n", "# 기획\n\n이번 실행 머리\n"))
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("# 기획\n", "# 기획\n\n프로젝트 머리\n"))
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 3
    out = insert(run_dir, project, "T090", "--take", DOC + spec)
    assert out.returncode == 0, out.output
    assert word in read(project / "docs" / "product" / "brief.md")


def test_document_without_sections_can_be_answered(run_dir, project):
    write(project / "docs" / "product" / "brief.md", "하나\n")
    commit_all(project)
    started(run_dir, project)
    approved_task(run_dir, text="둘\n")
    write(project / "docs" / "product" / "brief.md", "셋\n")
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 3
    assert insert(run_dir, project, "T090", "--take", DOC + "#(머리글)=프로젝트").returncode == 0


@pytest.mark.parametrize("take", [DOC + "#없는 절=이번 실행", DOC + "#정책=둘 다", "docs/없는 문서.md#정책=이번 실행", "꼴이 아님"])
def test_unknown_answer_is_refused_and_not_kept(run_dir, project, take):
    started(run_dir, project)
    approved_task(run_dir, text=CHANGE)
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("하루 한 번", "하루 다섯 번"))
    wrap(run_dir)
    assert insert(run_dir, project, "T090", "--take", take).returncode == 2
    assert not (run_dir.task_dir("T090") / project_docs.CHOICE_FILE).exists()


def test_approved_change_after_insert_is_not_shown_as_inserted(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "첫 판"))
    wrap(run_dir)
    insert(run_dir, project)
    commit_all(project, "문서 커밋")
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "둘째 판"))
    project_docs.stamp_file(str(run_dir.path), "spec\\brief.md", "T050")
    joined = review(run_dir)
    assert "아직 넣지 않음: " + DOC in joined and "승인한 그대로: " + DOC not in joined
    assert "아직 넣지 않음 1" in first_of(joined)


def test_unapproved_change_after_insert_says_both(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "첫 판"))
    wrap(run_dir)
    insert(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "승인 없는 판"))
    joined = review(run_dir)
    assert "아직 넣지 않음: " + DOC in joined and "승인 뒤 달라짐: " + DOC in joined


def test_review_before_any_insert_does_not_say_approved_as_is(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=CHANGE)
    wrap(run_dir)
    run_dir.flow("feat", dir=str(project), status="진행")
    joined = review(run_dir)
    assert "아직 넣지 않음: " + DOC in joined and "승인한 그대로" not in joined


# ---------------------------------------------------------------- R-C10 내보내기 관문


def conflicted(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=CHANGE)
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("하루 한 번", "하루 다섯 번"))
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 3


def to_export(run_dir, tid="T090"):
    t = run_dir.tasks()[tid]
    t["stage"] = "실행"
    ctx = {"record": ("승인", "", ""), "reason": None, "archived": False, "snapshot": False, "old_stage": "실행승인"}
    return task_set.check_transition(str(run_dir.path), t, "승인대기", "진행", ctx)


def test_unresolved_conflict_refuses_export(run_dir, project):
    conflicted(run_dir, project)
    assert "같은 절 두 곳이 풀리지 않아" in (to_export(run_dir) or "")


def test_answered_conflict_passes_the_gate(run_dir, project):
    conflicted(run_dir, project)
    insert(run_dir, project, "T090", "--take", DOC + "#정책=이번 실행")
    assert "같은 절" not in (to_export(run_dir) or "")


def test_skipping_the_document_opens_the_way_and_says_so(run_dir, project):
    conflicted(run_dir, project)
    out = insert(run_dir, project, "T090", "--take", DOC + "#(파일 전체)=뺌")
    assert out.returncode == 0, out.output
    assert "같은 절" not in (to_export(run_dir) or "")
    assert "다섯 번" in read(project / "docs" / "product" / "brief.md")
    joined = review(run_dir)
    assert "넣지 않고 뺌: " + DOC in joined and "승인한 그대로" not in joined


def test_old_wrap_up_has_no_gate(run_dir, project):
    conflicted(run_dir, project)
    wrap(run_dir, "T091", **{"started_version": "1.1.1"})
    assert "같은 절" not in (to_export(run_dir, "T091") or "")


# ---------------------------------------------------------------- R-C12 양쪽 줄


def test_conflict_lines_are_labelled_and_limited_to_the_section(run_dir, project):
    longer = BRIEF + "\n## 다른 절\n이번 실행만 고친 줄\n"
    started(run_dir, project)
    approved_task(run_dir, text=longer.replace("하루 한 번", "하루 두 번"))
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("하루 한 번", "하루 다섯 번"))
    wrap(run_dir)
    insert(run_dir, project)
    part = review(run_dir).split(project_docs.TWO_PLACES + ": " + DOC + " ## 정책")[1]
    run_side, project_side = part.split("  프로젝트:")
    assert "이번 실행:" in run_side and "+하루 두 번" in run_side and "다섯 번" not in run_side
    assert "+하루 다섯 번" in project_side and "두 번" not in project_side.split("##")[0]
    assert "이번 실행만 고친 줄" not in part.split("##")[0]


# ---------------------------------------------------------------- R-C13 넣는 폴더


def test_no_folder_writes_nothing_in_the_original_folder(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=CHANGE)
    wrap(run_dir)
    out = run_script("project_docs", run_dir, "T090", "--insert")
    assert out.returncode == 0 and project_docs.NO_FOLDER in out.output
    assert git(project, "status", "--porcelain") == ""
    assert project_docs.NOT_YET in table(run_dir)
    assert "아직 넣지 않음: " + DOC in review(run_dir)


def test_two_flows_without_integration_are_refused(run_dir, project, tmp_path):
    started(run_dir, project)
    approved_task(run_dir, text=CHANGE)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    run_dir.flow("feat-a", dir=str(a), status="진행")
    run_dir.flow("feat-b", dir=str(b), status="진행")
    wrap(run_dir)
    out = run_script("project_docs", run_dir, "T090", "--insert")
    assert out.returncode == 2 and not (a / "docs").exists() and not (b / "docs").exists()


# ---------------------------------------------------------------- R-C14 기준 브랜치


def test_missing_base_branch_stops_instead_of_saying_no_git(run_dir, project):
    doc = devflow_lib.Doc(str(run_dir.path / "run.md"))
    doc.set("project", str(project))
    doc.set("base_branch", "develop-오타")
    doc.save()
    for flag in ("--base", "--start"):
        out = run_script("project_docs", run_dir, flag)
        assert out.returncode == 3 and "develop-오타" in out.output
    assert not project_docs.base_commit(str(run_dir.path))


# ---------------------------------------------------------------- R-C15 위임


def test_delegated_change_is_labelled(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", CHANGE)
    line = task_set.record_line(("승인", "위임: 알아서", "알아서 하세요"))
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md", "승인 기록": line}, kind="brief", block="요구사항", status="완료", **NEW)
    project_docs.stamp_task(str(run_dir.path), run_dir.tasks()["T010"])
    wrap(run_dir)
    insert(run_dir, project)
    joined = review(run_dir)
    assert "승인 없이 위임으로 지나감: " + DOC in joined and "승인한 그대로" not in joined
    assert "넣을 산출물" not in first_of(joined)


# ---------------------------------------------------------------- R-C16 넣지 않는 절


def test_change_in_a_section_not_inserted_is_not_a_warning(run_dir, project):
    design = "# 흐름\n\n## 결정\n가\n\n## 자식 행\n- T1\n"
    started(run_dir, project)
    approved_task(run_dir, "T010", "design/pay.md", design)
    write(run_dir.path / "design" / "pay.md", design + "- T2\n")
    wrap(run_dir)
    insert(run_dir, project)
    joined = review(run_dir)
    assert "승인 뒤 달라짐" not in joined and "승인한 그대로: " + FLOW in joined


# ---------------------------------------------------------------- R-C17 닫힌 항목


def test_closed_item_survives_an_abandoned_run_and_leaves_after_export(run_dir, project):
    write(project / "docs" / "operations" / "unverified.md", "- 남길 것\n- 닫을 것\n")
    commit_all(project)
    started(run_dir, project)
    run_script("project_docs", run_dir, "--close", "- 닫을 것")
    wrap(run_dir)
    insert(run_dir, project)
    assert read(project / "docs" / "operations" / "unverified.md") == "- 남길 것\n"
    state = project_docs.state_path(str(run_dir.path))
    assert "- 닫을 것" in devflow_lib.read_text(state)
    tip = commit_all(project, "넣기")
    run_dir.task("T090", "마무리", kind="wrap-up", block="마무리", status="완료", stage="끝", exported_commit=tip, **NEW)
    run_script("project_docs", run_dir, "--stale")
    assert "- 닫을 것" not in devflow_lib.read_text(state)


# ---------------------------------------------------------------- R-C23, R-C11 문서


def test_old_rule_for_reopened_runs_is_still_written():
    from conftest import ROOT
    assert "앞 회차 절은 고치지 않는다" in (ROOT / "references" / "kinds" / "brief.md").read_text(encoding="utf-8")


def test_visual_sheet_is_not_blocked_by_timeout(run_dir, project, monkeypatch):
    """R-C6: 끝나지 않는 명령이 승인 앞의 한 장을 멈추지 않는다."""
    started(run_dir, project)
    monkeypatch.setattr(project_docs, "GEN_TIMEOUT", 1)
    write(project / "slow.py", "import time\ntime.sleep(60)\n")
    settings(run_dir, "- 구조도 | {} slow.py | docs/generated/s.md".format(PY))
    write(run_dir.path / "design" / "feat.md", "# 설계\n\n## 제안 도면\n### 구조도\n```\nA\n```\n")
    run_dir.flow("feat", dir=str(project), status="진행")
    run_dir.task("T030", "설계", {"건드릴 파일": "- design/feat.md"}, kind="design", block="설계", status="완료", **NEW)
    run_dir.task("T040", "검증", kind="flow-verify", block="검증", status="자체검증", flow="feat", parent="T030", **NEW)
    run_dir.result("T040", "# 결과\n\n## 승인 화면\n### 리뷰 자료\n한 일\n### 정해 주실 것\n- 없음\n")
    began = time.monotonic()
    (page, _) = visual.sheet_html(str(run_dir.path), run_dir.tasks()["T040"])
    assert time.monotonic() - began < 15 and "시간 초과 1초" in page
