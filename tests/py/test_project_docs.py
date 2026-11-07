"""1.2.0 A13: 프로젝트 산출물(설계 7.5절). 대응표, 기준본, 승인 해시, 절 단위 넣기, 생성 명령, 도면 대조, 낡음."""
import os
import subprocess
import sys

import pytest

import devflow_lib
import project_docs
import task_set
import visual
from conftest import run_script, write

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}
BRIEF = "# 기획\n\n## 여정\n가입한다\n\n## 정책\n하루 한 번\n"


def git(folder, *args):
    proc = subprocess.run(["git", "-C", str(folder)] + list(args), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def commit_all(folder, message="커밋"):
    git(folder, "add", "-A")
    git(folder, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", message)
    return git(folder, "rev-parse", "HEAD")


@pytest.fixture(name="project")
def _project(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "config", "core.autocrlf", "false")
    write(repo / "docs" / "product" / "brief.md", BRIEF)
    write(repo / "src" / "a.py", "x = 1\n")
    commit_all(repo)
    return repo


def started(run_dir, project):
    """실행 시작: run.md에 프로젝트를 적고 기준본을 뜬다."""
    doc = devflow_lib.Doc(str(run_dir.path / "run.md"))
    doc.set("project", str(project))
    doc.set("base_branch", "dev")
    doc.save()
    done = run_script("project_docs", run_dir, "--base")
    assert done.returncode == 0, done.output
    return run_dir


def approved_task(run_dir, tid="T010", rel="spec/brief.md", text=None, **meta):
    """정본을 쓴 task 하나를 만들고 완료 관문이 찍는 해시를 찍는다."""
    write(run_dir.path / rel, BRIEF if text is None else text)
    run_dir.task(tid, "기획", {"건드릴 파일": "- " + rel}, kind="brief", block="요구사항", status="완료", **dict(NEW, **meta))
    t = run_dir.tasks()[tid]
    project_docs.snapshot_asked(str(run_dir.path), t)
    assert project_docs.stamp_task(str(run_dir.path), t) == [rel.replace("/", "\\")]


def wrap(run_dir, tid="T090", **meta):
    run_dir.task(tid, "마무리", kind="wrap-up", block="마무리", status="자체검증", stage="실행승인", **dict(NEW, **meta))
    run_dir.result(tid, "# 결과\n\n## 승인 화면\n### 리뷰 자료\n한 일\n### 정해 주실 것\n- 없음\n")
    return tid


def insert(run_dir, folder, tid="T090", *rest):
    return run_script("project_docs", run_dir, tid, "--insert", folder, *rest)


def review(run_dir, tid="T090"):
    return "\n".join(visual.review_lines(str(run_dir.path), tid))


# ---------------------------------------------------------------- 대응표


@pytest.mark.parametrize("rel,dest", [
    ("spec\\brief.md", "docs/product/brief.md"),
    ("spec\\overview.md", "docs/product/requirements/overview.md"),
    ("spec\\billing.md", "docs/product/requirements/billing.md"),
    ("spec\\glossary.md", "docs/product/glossary.md"),
    ("ui\\billing.md", "docs/screens/billing.md"),
    ("ui\\wireframes\\billing.html", "docs/screens/wireframes/billing.html"),
    ("design\\feat.md", "docs/architecture/flows/feat.md"),
    ("design\\infra.md", "docs/architecture/infra.md"),
])
def test_map_table(rel, dest):
    assert project_docs.project_path(rel) == dest


@pytest.mark.parametrize("rel", ["ui\\capture.png", "tasks\\T001\\result.md", "spec\\a\\b.md", "design\\a\\b.md"])
def test_outside_the_table_is_not_inserted(rel):
    assert project_docs.project_path(rel) is None


def test_design_keeps_only_flow_chart_and_decisions_and_drops_history():
    text = ("# 설계\n\n## 결정 지도\n| 결정 |\n\n## 제안 도면\n### 기능 흐름도\n```mermaid\nA-->B\n```\n### 구조도\nC\n\n"
            "## 자식 목록\n| T1 | 구현 |\n\n## 변경 이력\n- T009 고침\n")
    out = project_docs.projection("design\\feat.md", text)
    assert "A-->B" in out and "| 결정 |" in out
    assert "T1" not in out and "T009" not in out and "### 구조도" not in out


def test_history_is_dropped_on_the_way_into_the_project():
    assert "T009" not in project_docs.projection("spec\\brief.md", "# 기획\n\n## 여정\n가입\n\n## 변경 이력\n- T009 고침\n")


def test_overview_terms_also_feed_the_glossary():
    out = project_docs.projections("spec\\overview.md", "# 개요\n\n## 범위\n가\n\n## 용어\n- 계정: 쓰는 사람\n")
    assert dict(out)["docs/product/glossary.md"].strip().endswith("- 계정: 쓰는 사람")
    assert "docs/product/requirements/overview.md" in dict(out)


# ---------------------------------------------------------------- 기준본


def test_base_copies_project_docs_at_the_start_commit(run_dir, project):
    write(project / "docs" / "product" / "brief.md", "커밋 안 한 글\n")   # 커밋한 판을 뜬다
    tip = git(project, "rev-parse", "dev")
    started(run_dir, project)
    assert (run_dir.path / "base" / "docs" / "product" / "brief.md").read_text(encoding="utf-8") == BRIEF
    assert devflow_lib.run_meta(str(run_dir.path))["docs_base_commit"] == tip


def test_base_on_a_project_without_docs_is_empty_but_recorded(run_dir, tmp_path):
    repo = tmp_path / "bare"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "dev")
    write(repo / "a.txt", "a\n")
    commit_all(repo)
    started(run_dir, repo)
    assert devflow_lib.run_meta(str(run_dir.path))["docs_base_commit"]
    assert (run_dir.path / "base").is_dir()


def test_base_outside_git_writes_no_commit_and_insert_is_skipped(run_dir, tmp_path):
    folder = tmp_path / "plain"
    write(folder / "docs" / "product" / "brief.md", BRIEF)
    started(run_dir, folder)
    assert devflow_lib.run_meta(str(run_dir.path))["docs_base_commit"] == project_docs.NO_GIT
    approved_task(run_dir, text=BRIEF + "\n## 지표\n가\n")
    wrap(run_dir)
    out = insert(run_dir, folder)
    assert out.returncode == 0 and project_docs.NO_GIT in out.output
    assert "## 지표" not in (folder / "docs" / "product" / "brief.md").read_text(encoding="utf-8")


def test_sheet_diffs_the_first_revision_against_base(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    t = run_dir.tasks()["T010"]
    (rel, before, after), = visual.changed_documents(str(run_dir.path), t)
    assert before == BRIEF and "두 번" in after


def test_run_without_base_diffs_against_nothing(run_dir):
    approved_task_without_stamp(run_dir)
    (rel, before, after), = visual.changed_documents(str(run_dir.path), run_dir.tasks()["T010"])
    assert before is None


def approved_task_without_stamp(run_dir):
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="완료", **NEW)


# ---------------------------------------------------------------- 승인 해시


def test_stamp_after_approval_then_edit_is_approved_then_changed(run_dir, project):
    """승인 뒤 달라짐: 찍은 뒤 고치면 달라진 줄이 그대로 나온다."""
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    insert(run_dir, project)
    assert "승인한 그대로: docs/product/brief.md" in review(run_dir)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 세 번"))
    insert(run_dir, project)
    out = review(run_dir)
    assert "승인 뒤 달라짐: docs/product/brief.md" in out
    assert "-하루 두 번" in out and "+하루 세 번" in out
    assert "넣을 산출물: 승인 뒤 달라짐 1" in out.split("## 먼저 보실 것")[1].split("##")[0]


def test_line_endings_alone_are_not_a_change(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    (run_dir.path / "spec" / "brief.md").write_bytes(BRIEF.replace("하루 한 번", "하루 두 번").replace("\n", "\r\n").encode("utf-8"))
    wrap(run_dir)
    insert(run_dir, project)
    assert "승인 뒤 달라짐" not in review(run_dir)


def test_writer_copy_without_a_stamp_is_inserted_without_approval(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 네 번"))
    wrap(run_dir)
    insert(run_dir, project)
    out = review(run_dir)
    assert "승인 없이 들어감: docs/product/brief.md" in out and "+하루 네 번" in out


def test_apply_revision_stamps_after_it_adds_the_history_line(run_dir, project):
    """정상 경로가 달라짐으로 뜨지 않는다: 이력 줄을 붙인 뒤에 찍는다."""
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="완료", **NEW)
    write(run_dir.task_dir("T011") / "revised" / "spec" / "brief.md", BRIEF.replace("하루 한 번", "하루 세 번"))
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()["T011"])
    assert run_script("apply_revision", run_dir, "T011").returncode == 0
    wrap(run_dir)
    insert(run_dir, project)
    out = review(run_dir)
    assert "승인한 그대로: docs/product/brief.md" in out and "승인 뒤 달라짐" not in out
    assert "변경 이력" not in (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8")


def test_dry_run_and_old_tasks_stamp_nothing(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T011", "변경", kind="change", block="요구사항", status="완료", **OLD)
    write(run_dir.task_dir("T011") / "revised" / "spec" / "brief.md", BRIEF + "\n더함\n")
    assert run_script("apply_revision", run_dir, "T011").returncode == 0
    assert not (run_dir.path / "approved").exists()


def test_old_run_gets_no_stamp_even_for_a_new_task(run_dir):
    approved_task_without_stamp(run_dir)
    assert project_docs.stamp_task(str(run_dir.path), run_dir.tasks()["T010"]) == []
    assert not (run_dir.path / "approved").exists()


def test_notified_change_is_labelled(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"), approval_mode="알림")
    wrap(run_dir)
    insert(run_dir, project)
    assert "승인 없이 알림으로 지나감: docs/product/brief.md" in review(run_dir)


def test_done_transition_stamps_written_and_prior_canon(run_dir, project):
    """완료 전이가 찍는다: 쓴 정본과, 고른 선택지가 Edit한 앞 정본 줄의 파일."""
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "가"))
    write(run_dir.path / "spec" / "brief.md", BRIEF.replace("하루 한 번", "나"))
    write(run_dir.path / "design" / "feat.md", "# 설계\n")
    run_dir.task("T012", "설계", {"건드릴 파일": "- design/feat.md", "승인 기록": task_set.record_line(("승인", "승인 화면", "(가)로 하세요"))},
                 kind="design", block="설계", status="승인대기", **NEW)
    run_dir.result("T012", "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 가\n  - 선택지 (가)의 앞 정본 줄: spec/brief.md:3 | 지금: 가 | 바뀜: 나\n")
    project_docs.snapshot_asked(str(run_dir.path), run_dir.tasks()["T012"])
    stamped = project_docs.stamp_task(str(run_dir.path), run_dir.tasks()["T012"])
    assert stamped == ["design\\feat.md", "spec\\brief.md"]
    rows = project_docs.stamps(str(run_dir.path))
    assert rows["spec\\brief.md"]["task"] == "T012"


def test_done_transition_calls_the_stamp(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T013", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="승인대기", **NEW)
    run_dir.result("T013", "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n")
    run_dir.judge("T013", "판정자: rjudge-T013 2026-11-06 10:00:00\n# T013 판정\n\n## 통과 못 한 기준\n- 없음\n")
    out = run_script("task_set", run_dir, "T013", "--status", "완료", "--unlisted", "시험", "--record", "승인|승인|좋습니다")
    assert out.returncode == 0, out.output
    assert "spec\\brief.md" in project_docs.stamps(str(run_dir.path))


# ---------------------------------------------------------------- 넣기: 절 단위


def test_clean_insert_writes_the_run_version_and_the_table(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    out = insert(run_dir, project)
    assert out.returncode == 0, out.output
    assert "두 번" in (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8")
    table = (run_dir.task_dir("T090") / project_docs.INSERT_FILE).read_text(encoding="utf-8")
    assert "docs/product/brief.md" in table and "승인한 그대로" in table


def test_second_insert_is_idempotent(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    insert(run_dir, project)
    before = (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8")
    assert insert(run_dir, project).returncode == 0
    assert (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8") == before


def test_other_section_changed_in_the_project_is_merged(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("가입한다", "가입하고 확인한다"))
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 0
    text = (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8")
    assert "가입하고 확인한다" in text and "두 번" in text


def test_same_section_changed_in_two_places_stops_that_file(run_dir, project):
    """같은 절 두 곳 고침: 넣지 않고 표에 올리며 종료 3이다. 다른 파일은 넣는다."""
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    write(run_dir.path / "ui" / "billing.md", "# 화면\n")
    approved_task(run_dir, "T011", "ui/billing.md", "# 화면\n")
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("하루 한 번", "하루 다섯 번"))
    wrap(run_dir)
    out = insert(run_dir, project)
    assert out.returncode == 3, out.output
    assert "다섯 번" in (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8")
    assert (project / "docs" / "screens" / "billing.md").is_file()
    table = (run_dir.task_dir("T090") / project_docs.INSERT_FILE).read_text(encoding="utf-8")
    assert "같은 절 두 곳" in table and "## 정책" in table
    joined = review(run_dir)
    assert "같은 절 두 곳: docs/product/brief.md ## 정책" in joined
    assert "넣을 산출물: 같은 절 두 곳 1" in joined.split("## 먼저 보실 것")[1].split("##")[0]
    assert "+하루 두 번" in joined and "+하루 다섯 번" in joined


def test_same_section_changed_on_the_base_branch_by_another_run(run_dir, project):
    """나란히 돈 실행이 개발 기준 브랜치에 먼저 넣은 경우: 코드 폴더가 아직 받지 않았어도 잡는다."""
    started(run_dir, project)
    folder = project.parent / "wt"
    git(project, "worktree", "add", "-q", "-b", "harness/feat", str(folder), "dev")
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("하루 한 번", "하루 일곱 번"))
    commit_all(project, "다른 실행")
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    assert insert(run_dir, folder).returncode == 3


def test_same_change_in_both_places_is_not_a_conflict(run_dir, project):
    started(run_dir, project)
    new = BRIEF.replace("하루 한 번", "하루 두 번")
    approved_task(run_dir, text=new)
    write(project / "docs" / "product" / "brief.md", new)
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 0
    assert "같은 절" not in review(run_dir)


@pytest.mark.parametrize("side,word", [("이번 실행", "두 번"), ("프로젝트", "다섯 번")])
def test_answer_takes_one_side_of_the_section(run_dir, project, side, word):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    write(project / "docs" / "product" / "brief.md", BRIEF.replace("하루 한 번", "하루 다섯 번").replace("가입한다", "가입하고 확인한다"))
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 3
    out = insert(run_dir, project, "T090", "--take", "docs/product/brief.md#정책=" + side)
    assert out.returncode == 0, out.output
    text = (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8")
    assert word in text and "가입하고 확인한다" in text
    assert "같은 절 두 곳" not in review(run_dir)


def test_deleted_on_one_side_changed_on_the_other_is_a_conflict():
    base = "## 가\n하나\n\n## 나\n둘\n"
    merged, conflicts = project_docs.merge_sections(base, "## 가\n고침\n\n## 나\n둘\n", "## 나\n둘\n")
    assert merged is None and conflicts == ["## 가"]


def test_deleted_on_one_side_only_stays_deleted():
    base = "## 가\n하나\n\n## 나\n둘\n"
    merged, conflicts = project_docs.merge_sections(base, base, "## 나\n둘\n")
    assert not conflicts and "## 가" not in merged


def test_html_is_one_section(run_dir, project):
    write(project / "docs" / "screens" / "wireframes" / "a.html", "<p>가</p>\n")
    commit_all(project)
    started(run_dir, project)
    approved_task(run_dir, "T011", "ui/wireframes/a.html", "<p>나</p>\n")
    write(project / "docs" / "screens" / "wireframes" / "a.html", "<p>다</p>\n")
    wrap(run_dir)
    assert insert(run_dir, project).returncode == 3


def test_hand_edit_after_insert_is_flagged(run_dir, project):
    """읽기 판정자가 표와 실제 변경을 대조할 근거: 넣은 뒤 문서를 고치면 표에 드러난다."""
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    insert(run_dir, project)
    path = project / "docs" / "product" / "brief.md"
    write(path, path.read_text(encoding="utf-8").replace("가입한다", "손으로 고침"))
    joined = review(run_dir)
    assert "넣은 뒤 달라짐: docs/product/brief.md" in joined and "+손으로 고침" in joined


def test_doc_outside_the_table_is_shown(run_dir, project):
    started(run_dir, project)
    write(project / "docs" / "notes.md", "표 밖 글\n")
    wrap(run_dir)
    insert(run_dir, project)
    joined = review(run_dir)
    assert "승인 없이 들어감: docs/notes.md (표 밖)" in joined and "+표 밖 글" in joined


def test_decision_title_and_list_count_and_generated_change(run_dir, project):
    started(run_dir, project)
    write(project / "docs" / "decisions" / "0001-저장소.md", "# 저장소를 나눈다\n\n본문\n")
    write(project / "docs" / "operations" / "unverified.md", "- 틀리면 다운 [성질: 위험]\n- 배포 뒤 확인\n")
    write(project / "docs" / "generated" / "structure.md", "a\nb\n")
    wrap(run_dir)
    insert(run_dir, project)
    joined = review(run_dir)
    assert "결정 기록: 저장소를 나눈다" in joined
    assert "위험·미확인 목록: 2건" in joined
    assert "생성물: docs/generated/structure.md" in joined
    assert "본문" not in joined and "틀리면 다운" not in joined


def test_already_on_the_base_branch_is_not_listed_again(run_dir, project):
    """뒤 회차의 마무리에는 앞 회차가 넣은 문서를 다시 싣지 않는다."""
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    insert(run_dir, project)
    commit_all(project, "넣기")
    assert "docs/product/brief.md" not in review(run_dir)


def test_old_wrap_up_review_has_no_section(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir, **{"started_version": "1.1.1"})
    assert "넣을 산출물" not in review(run_dir)
    out = insert(run_dir, project)
    assert out.returncode == 0 and project_docs.NOT_APPLIED in out.output
    assert "두 번" not in (project / "docs" / "product" / "brief.md").read_text(encoding="utf-8")


def test_new_wrap_up_in_a_run_without_base_has_no_section(run_dir):
    wrap(run_dir)
    assert "넣을 산출물" not in review(run_dir)


def test_map_counts_inserted_documents(run_dir, project):
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    insert(run_dir, project)
    assert ("넣은 산출물", ["- 문서 1개"]) in visual.map_sections(str(run_dir.path))


# ---------------------------------------------------------------- 위험·미확인의 닫힌 항목, 테스트 지도


def test_closed_item_waits_in_state_and_next_insert_removes_it(run_dir, project):
    write(project / "docs" / "operations" / "unverified.md", "- 남길 것\n- 닫을 것\n")
    commit_all(project)
    started(run_dir, project)
    assert run_script("project_docs", run_dir, "--close", "- 닫을 것").returncode == 0
    state = devflow_lib.read_text(project_docs.state_path(str(run_dir.path)))
    assert "- 닫을 것" in state
    wrap(run_dir)
    insert(run_dir, project)
    assert (project / "docs" / "operations" / "unverified.md").read_text(encoding="utf-8") == "- 남길 것\n"


def code_task(run_dir, tid, lines):
    run_dir.task(tid, "구현", kind="implementation", block="구현", status="완료", flow="feat", **NEW)
    run_dir.result(tid, "# 결과\n\n## 변이 확인 지시\n" + "\n".join(lines) + "\n")


def test_test_map_adds_this_runs_rows_and_drops_only_vanished_files(run_dir, project):
    write(project / "tests" / "test_old.py", "x\n")
    write(project / "tests" / "test_gone.py", "x\n")
    write(project / "tests" / "test_new.py", "x\n")
    write(project / "docs" / "generated" / "test-map.md",
          "| 인수 기준 | 시험 파일 |\n|---|---|\n| AC-1 | tests/test_old.py |\n| AC-2 | tests/test_gone.py |\n")
    commit_all(project)
    (project / "tests" / "test_gone.py").unlink()
    started(run_dir, project)
    code_task(run_dir, "T020", ["- src/a.py:3을 바꾸면 tests/test_new.py가 실패한다(AC-3). 효과 근거: 값 대조. 명령: pytest",
                                "- 시험 파일을 적지 않은 줄"])
    wrap(run_dir)
    insert(run_dir, project)
    text = (project / "docs" / "generated" / "test-map.md").read_text(encoding="utf-8")
    assert "| AC-1 | tests/test_old.py |" in text and "| AC-3 | tests/test_new.py |" in text
    assert "test_gone" not in text
    assert "연결을 못 읽은 줄 1" in review(run_dir)


# ---------------------------------------------------------------- 생성 명령


def settings(run_dir, *lines):
    write(run_dir.path.parent / devflow_lib.PROJECT_SETTINGS, "# 프로젝트 설정\n\n## 생성 명령\n" + "\n".join(lines) + "\n")


def gen_line(name, target, body, repo):
    script = write(repo / "gen_{}.py".format(name), "print({!r})\n".format(body))
    return "- {} | \"{}\" {} | {}".format(name, sys.executable, script.name, target)


def test_generate_writes_stdout_and_check_compares(run_dir, project):
    started(run_dir, project)
    settings(run_dir, gen_line("구조도", "docs/generated/structure.md", "A-->B", project))
    wrap(run_dir)
    assert run_script("project_docs", run_dir, "T090", "--generate", project).returncode == 0
    target = project / "docs" / "generated" / "structure.md"
    assert target.read_text(encoding="utf-8").strip() == "A-->B"
    assert run_script("project_docs", run_dir, "T090", "--generate", project, "--check").returncode == 0
    write(target, "손으로 고침\n")
    out = run_script("project_docs", run_dir, "T090", "--generate", project, "--check")
    assert out.returncode == 3 and "structure.md" in out.output
    assert target.read_text(encoding="utf-8") == "손으로 고침\n"


def test_generate_without_commands_says_so(run_dir, project):
    started(run_dir, project)
    wrap(run_dir)
    out = run_script("project_docs", run_dir, "T090", "--generate", project)
    assert out.returncode == 0 and project_docs.NO_GENERATOR in out.output


def test_failing_generator_keeps_the_file_and_reports(run_dir, project):
    started(run_dir, project)
    write(project / "boom.py", "raise SystemExit(5)\n")
    settings(run_dir, "- 구조도 | \"{}\" boom.py | docs/generated/structure.md".format(sys.executable))
    wrap(run_dir)
    out = run_script("project_docs", run_dir, "T090", "--generate", project)
    assert out.returncode == 0 and "생성 실패: 구조도" in out.output
    assert not (project / "docs" / "generated" / "structure.md").exists()


# ---------------------------------------------------------------- 제안 도면과 생성본


def flow_review_task(run_dir, project, proposal, name="구조도"):
    settings(run_dir, gen_line(name, "docs/generated/structure.md", "A-->B\nB-->C", project))
    write(run_dir.path / "design" / "feat.md", "# 설계\n\n## 제안 도면\n### {}\n```mermaid\n{}\n```\n\n## 시험 표\n| 표 |\n".format(name, proposal))
    run_dir.flow("feat", dir=str(project), status="진행")
    run_dir.task("T030", "설계", {"건드릴 파일": "- design/feat.md"}, kind="design", block="설계", status="완료", **NEW)
    run_dir.task("T040", "검증", kind="flow-verify", block="검증", status="자체검증", flow="feat", parent="T030", **NEW)
    run_dir.result("T040", "# 결과\n\n## 승인 화면\n### 리뷰 자료\n한 일\n### 정해 주실 것\n- 없음\n")


def test_drawing_diff_lists_only_the_different_lines(run_dir, project):
    flow_review_task(run_dir, project, "A-->B\nA-->D")
    (page, _) = visual.sheet_html(str(run_dir.path), run_dir.tasks()["T040"])
    assert "설계와 달라진 점" in page
    assert "제안에만: A--&gt;D" in page and "생성본에만: B--&gt;C" in page
    assert "제안에만: A--&gt;B" not in page


def test_matching_drawing_shows_no_block_and_is_not_a_failure(run_dir, project):
    flow_review_task(run_dir, project, "A-->B\nB-->C")
    (page, _) = visual.sheet_html(str(run_dir.path), run_dir.tasks()["T040"])
    assert "설계와 달라진 점" not in page


def test_proposal_stays_as_source_text_on_the_sheet(run_dir, project):
    flow_review_task(run_dir, project, "A-->D")
    (page, _) = visual.sheet_html(str(run_dir.path), run_dir.tasks()["T040"])
    assert "```mermaid" in page and "<script" not in page and "<svg" not in page


def test_no_generator_says_it_could_not_compare(run_dir, project):
    flow_review_task(run_dir, project, "A-->D", name="없는 도면")
    write(run_dir.path.parent / devflow_lib.PROJECT_SETTINGS, "# 프로젝트 설정\n")
    (page, _) = visual.sheet_html(str(run_dir.path), run_dir.tasks()["T040"])
    assert project_docs.NO_GENERATOR in page


def test_broken_generator_does_not_block_the_sheet(run_dir, project):
    flow_review_task(run_dir, project, "A-->D")
    write(project / "gen_구조도.py", "raise SystemExit(5)\n")
    (page, _) = visual.sheet_html(str(run_dir.path), run_dir.tasks()["T040"])
    assert "설계와 달라진 점" in page and "돌리지 못함" in page


# ---------------------------------------------------------------- 낡음


def inserted_run(run_dir, project):
    """문서 하나를 지키는 경로와 함께 넣고 내보낸 실행."""
    started(run_dir, project)
    approved_task(run_dir, text=BRIEF.replace("하루 한 번", "하루 두 번"))
    wrap(run_dir)
    run_dir.result("T090", "# 결과\n\n## 승인 화면\n### 리뷰 자료\n한 일\n### 정해 주실 것\n- 없음\n\n"
                           "## 본문\n- 지키는 경로: docs/product/brief.md | src/**\n")
    insert(run_dir, project)
    tip = commit_all(project, "넣기")
    run_dir.task("T090", "마무리", kind="wrap-up", block="마무리", status="완료", stage="끝", exported_commit=tip, **NEW)
    assert run_script("project_docs", run_dir, "--stale").returncode == 0


def test_state_lives_under_workspace_policies(run_dir):
    assert project_docs.state_path(str(run_dir.path)) == os.path.join(str(run_dir.path.parent), "policies", "docs-state.md")


def test_stale_marks_a_document_when_a_guarded_path_moves(run_dir, project):
    inserted_run(run_dir, project)
    quiet = run_script("project_docs", run_dir, "--stale")
    assert quiet.returncode == 0 and "확인 필요" not in quiet.output
    assert "| docs/product/brief.md | src/** |" in devflow_lib.read_text(project_docs.state_path(str(run_dir.path)))
    write(project / "src" / "a.py", "x = 2\n")
    commit_all(project)
    out = run_script("project_docs", run_dir, "--stale")
    assert out.returncode == 0 and "확인 필요: docs/product/brief.md | src/a.py" in out.output
    assert "확인 필요" in devflow_lib.read_text(project_docs.state_path(str(run_dir.path)))


def test_unguarded_change_is_not_stale(run_dir, project):
    inserted_run(run_dir, project)
    write(project / "other.py", "y\n")
    commit_all(project)
    assert "확인 필요" not in run_script("project_docs", run_dir, "--stale").output


def test_ok_answer_moves_the_base_commit(run_dir, project):
    inserted_run(run_dir, project)
    write(project / "src" / "a.py", "x = 2\n")
    commit_all(project)
    run_script("project_docs", run_dir, "--stale")
    assert run_script("project_docs", run_dir, "--stale", "--ok", "docs/product/brief.md").returncode == 0
    assert "확인 필요" not in run_script("project_docs", run_dir, "--stale").output


def test_missing_base_commit_is_needs_check_not_silent(run_dir, project):
    inserted_run(run_dir, project)
    path = project_docs.state_path(str(run_dir.path))
    text = devflow_lib.read_text(path)
    tip = git(project, "rev-parse", "dev")
    write(path, text.replace(tip, "0" * 40))
    out = run_script("project_docs", run_dir, "--stale")
    assert "확인 필요: docs/product/brief.md | 기준 커밋을 읽지 못함" in out.output


def test_running_stale_writes_nothing_in_the_project(run_dir, project):
    inserted_run(run_dir, project)
    run_script("project_docs", run_dir, "--stale")
    assert git(project, "status", "--porcelain") == ""


# ---------------------------------------------------------------- git 훅


def hook_path(project):
    return project / ".git" / "hooks" / "pre-commit"


def test_hook_warns_and_never_blocks(run_dir, project):
    inserted_run(run_dir, project)
    assert run_script("project_docs", run_dir, "--hook").returncode == 0
    assert project_docs.HOOK_MARK in hook_path(project).read_text(encoding="utf-8")
    write(project / "src" / "a.py", "x = 3\n")
    git(project, "add", "-A")
    out = run_script("project_docs", "--hook-check", run_dir.path.parent, cwd=project)
    assert out.returncode == 0 and "docs/product/brief.md" in out.output


def test_hook_is_quiet_when_the_document_is_staged_too(run_dir, project):
    inserted_run(run_dir, project)
    write(project / "src" / "a.py", "x = 3\n")
    write(project / "docs" / "product" / "brief.md", "고침\n")
    git(project, "add", "-A")
    out = run_script("project_docs", "--hook-check", run_dir.path.parent, cwd=project)
    assert out.returncode == 0 and "docs/product/brief.md" not in out.output


def test_hook_does_not_replace_someone_elses_hook(run_dir, project):
    started(run_dir, project)
    write(hook_path(project), "#!/bin/sh\necho mine\n")
    out = run_script("project_docs", run_dir, "--hook")
    assert out.returncode == 0 and project_docs.HOOK_SKIPPED in out.output
    assert hook_path(project).read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"


def test_hook_does_not_install_under_a_custom_hooks_path(run_dir, project):
    started(run_dir, project)
    git(project, "config", "core.hooksPath", ".husky")
    out = run_script("project_docs", run_dir, "--hook")
    assert project_docs.HOOK_SKIPPED in out.output and not (project / ".husky").exists()


def test_start_runs_base_and_stale_and_stays_quiet_about_nothing(run_dir, project):
    doc = devflow_lib.Doc(str(run_dir.path / "run.md"))
    doc.set("project", str(project))
    doc.set("base_branch", "dev")
    doc.save()
    out = run_script("project_docs", run_dir, "--start")
    assert out.returncode == 0, out.output
    assert (run_dir.path / "base" / "docs" / "product" / "brief.md").is_file()
    assert not hook_path(project).exists()
    assert "확인 필요" not in out.output


def test_task_set_module_is_unaffected_for_old_task(run_dir, project):
    """옛 task의 완료는 표지를 만들지 않는다(전이를 실제로 돌린다)."""
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T014", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="승인대기", **OLD)
    run_dir.result("T014", "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n")
    run_dir.judge("T014", "판정자: rjudge-T014 2026-11-06 10:00:00\n# T014 판정\n\n## 통과 못 한 기준\n- 없음\n")
    assert task_set.main(["task_set.py", str(run_dir.path), "T014", "--status", "완료", "--unlisted", "시험", "--record", "승인|승인|좋습니다"]) == 0
    assert project_docs.stamps(str(run_dir.path)) == {}
