"""1.3.1 최종 CI 이어받음(D-27 (나), D-29~D-33, AC-25·AC-26): 마무리가 이어받을 앞 전체 CI를 `--inherit-ci`로 찾고,
완료 관문(`task_set.final_candidate_ci_problem`)이 `이어받은 전체 검증`을 원천과 같을 때만 받는다. 합치기는 그대로다.

- 가짜 실행 폴더 둘: 흐름 둘(`flows/{a,b}/flow.md`가 합쳐짐, 완료 merge 둘), 흐름 하나(완료 코드 task 둘).
- 판정 파일의 입력은 판정자가 쓰는 꼴(D-32) 그대로 글자로 적는다. 출력 줄은 AC-25의 꼴로 단언한다.
"""
import subprocess
from pathlib import Path

import pytest

import task_set
from conftest import run_script, write

V131 = {"started_version": "1.3.1", "rules": "2"}
HEAD = "c" * 40                    # 마무리 문서 커밋(검증 commit = 내보낸 끝)
OLD_MERGE, LAST_MERGE = "a" * 40, "b" * 40
TREE = "d" * 40
CODE_1, CODE_2 = "1" * 40, "2" * 40
WRAP = "T090"


def merge_judge_run(commit, failed="- 없음", scope="전체 검증"):
    return ("판정자: xjudge-T050 2026-11-19 10:00:00\n\n## 통과 못 한 기준\n{}\n\n"
            "## 최종 배포 후보 CI\n- 범위: {}\n- 검증 commit: {}\n- 검증 artifact: ci-run-9\n").format(failed, scope, commit)


def code_judge_run(failed="- 없음", record=True):
    text = "판정자: xjudge-T010 2026-11-19 10:00:00\n\n## 통과 못 한 기준\n{}\n".format(failed)
    if record:
        text += "\n## 전체 검증 기록\n- 범위: 전체 검증\n- 검증 tree: {}\n".format(TREE)
    return text


def wrap_judge_run(source_id, source_sha, scope="이어받은 전체 검증", head=HEAD, changed="- 그 뒤 바뀐 파일: 1개(README.md)\n"):
    return ("판정자: xjudge-T090 2026-11-19 12:00:00\n\n## 통과 못 한 기준\n- 없음\n\n"
            "## 최종 배포 후보 CI\n- 범위: {}\n- 이어받은 CI: {} {}\n{}"
            "- 검증 commit: {}\n- 검증 artifact: ci-run-9\n").format(scope, source_id, source_sha, changed, head)


def task(run_dir, tid, judge_run=None, **meta):
    run_dir.task(tid, "이어받음 시험 " + tid, **dict(V131, **meta))
    if judge_run is not None:
        write(run_dir.task_dir(tid) / "judge-run.md", judge_run)


def two_flows(run_dir, last_failed="- 없음"):
    """흐름 a·b가 모두 합쳐진 실행: 앞 합치기 T050(a), 가장 늦게 승인된 합치기 T051(b), 마무리 T090."""
    run_dir.flow("a", status="합쳐짐")
    run_dir.flow("b", status="합쳐짐")
    task(run_dir, "T050", merge_judge_run(OLD_MERGE), kind="merge", block="합치기", flow="a", status="완료",
         commit=OLD_MERGE, stage="끝", approved="2026-11-19 09:00:00")
    task(run_dir, "T051", merge_judge_run(LAST_MERGE, failed=last_failed), kind="merge", block="합치기", flow="b",
         status="완료", commit=LAST_MERGE, stage="끝", approved="2026-11-19 11:00:00")
    task(run_dir, WRAP, kind="wrap-up", block="마무리", status="자체검증", exported_commit=HEAD)


def one_flow(run_dir, last_record=True, first_record=True, last_failed="- 없음"):
    """흐름 a 하나: 앞 코드 task T010, 가장 늦게 승인된 코드 task T011, 마무리 T090."""
    run_dir.flow("a", status="합쳐짐")
    task(run_dir, "T010", code_judge_run(record=first_record), kind="implementation", block="구현", flow="a",
         status="완료", commit=CODE_1, approved="2026-11-19 09:00:00")
    task(run_dir, "T011", code_judge_run(failed=last_failed, record=last_record), kind="implementation", block="구현",
         flow="a", status="완료", commit=CODE_2, approved="2026-11-19 11:00:00")
    task(run_dir, WRAP, kind="wrap-up", block="마무리", status="자체검증", exported_commit=HEAD)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def inherit(run_dir, tid=WRAP):
    proc = run_script("task_set", run_dir, tid, "--inherit-ci")
    return proc.returncode, proc.stdout.strip()


def wrap_problem(run_dir, head=HEAD):
    t = run_dir.tasks()[WRAP]
    return task_set.final_candidate_ci_problem(str(run_dir), t, always=True, expected_commit=head)


def git(folder, *args):
    out = subprocess.run(["git", "-C", str(folder)] + list(args), check=True, capture_output=True, encoding="utf-8")
    return out.stdout.strip()


def docs_after_source(folder, *changed):
    """원천 commit(파일 둘) 위에 마무리 문서 커밋 하나(changed 파일들을 고침)를 쌓은 git 저장소 → (원천 commit, HEAD)."""
    folder.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                 ["config", "core.autocrlf", "false"]):
        git(folder, *args)
    for name in ("README.md", "scripts/x.py"):
        write(folder / name, "앞\n")
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "원천")
    source = git(folder, "rev-parse", "HEAD")
    for name in changed:
        write(folder / name, "뒤\n")
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "마무리 문서")
    return source, git(folder, "rev-parse", "HEAD")


def two_flows_in_git(run_dir, folder, *changed, listed="- 그 뒤 바뀐 파일: 1개(README.md)\n"):
    """two_flows와 같되 원천 T051의 검증 commit과 마무리 검증 commit이 흐름 b 폴더(folder)의 실제 commit이다."""
    source, head = docs_after_source(folder, *changed)
    run_dir.flow("a", status="합쳐짐")
    run_dir.flow("b", status="합쳐짐", dir=str(folder))
    task(run_dir, "T051", merge_judge_run(source), kind="merge", block="합치기", flow="b", status="완료",
         commit=source, stage="끝", approved="2026-11-19 11:00:00")
    task(run_dir, WRAP, wrap_judge_run("T051", source[:7], head=head, changed=listed), kind="wrap-up", block="마무리",
         status="자체검증", exported_commit=head)
    return head


# ---------------------------------------------------------------- AC-25 원천 찾기

def test_two_flows_inherit_the_last_approved_merge_ci_and_write_nothing(run_dir):
    two_flows(run_dir)
    before = snapshot(run_dir.path)
    rc, out = inherit(run_dir)
    assert (rc, out) == (0, "이어받을 CI: T051 commit {}".format(LAST_MERGE))
    assert snapshot(run_dir.path) == before


def test_one_flow_inherits_the_last_code_task_full_ci_record(run_dir):
    one_flow(run_dir)
    assert inherit(run_dir) == (0, "이어받을 CI: T011 commit {} tree {}".format(CODE_2, TREE))


def test_one_flow_has_no_source_when_only_an_earlier_code_task_has_the_record(run_dir):
    one_flow(run_dir, last_record=False)
    rc, out = inherit(run_dir)
    assert rc == 0 and out.startswith("이어받을 CI: 없음(") and "T011" in out and "T010" not in out, out


def test_one_flow_has_no_source_when_the_source_judge_has_a_failed_criterion(run_dir):
    one_flow(run_dir, last_failed="- 기준 1: 관련 시험 실패 1")
    rc, out = inherit(run_dir)
    assert rc == 0 and out.startswith("이어받을 CI: 없음(") and "통과 못 한 기준" in out, out


def test_inherit_ci_is_only_for_wrap_up(run_dir):
    two_flows(run_dir)
    rc, out = inherit(run_dir, "T051")
    assert rc == 3 and out == task_set.INHERIT_CI_WRAP.format("T051", "merge"), out


# ---------------------------------------------------------------- AC-26 마무리 완료 관문

def test_wrap_up_gate_accepts_inherited_scope_matching_the_source(run_dir, tmp_path):
    head = two_flows_in_git(run_dir, tmp_path / "b", "README.md")
    assert wrap_problem(run_dir, head) is None   # 원천 뒤 바뀐 파일이 적힌 목록(README.md) 안에만 있다


@pytest.mark.parametrize("listed", ["- 그 뒤 바뀐 파일: 1개(README.md)\n", ""], ids=["outside", "no-line"])
def test_wrap_up_gate_rejects_files_changed_after_the_source_outside_the_written_list(run_dir, tmp_path, listed):
    """원천 commit과 검증 commit 사이에 적힌 `- 그 뒤 바뀐 파일:` 목록 밖의 파일이 바뀌었거나 그 줄이 없으면 거부
    (AC-26, 설계 harness-defects 5절 H1·D-30, T016 답 6가, T028 답 1가)."""
    head = two_flows_in_git(run_dir, tmp_path / "b", "README.md", "scripts/x.py", listed=listed)
    why = wrap_problem(run_dir, head)
    assert why is not None, "관문이 적힌 목록 밖의 변경을 받음"
    want = task_set.INHERIT_FILES_OUTSIDE.format("scripts/x.py") if listed else task_set.INHERIT_FILES_NONE
    assert why == want, why


def test_wrap_up_gate_rejects_inherited_ci_naming_another_task(run_dir):
    two_flows(run_dir)
    write(run_dir.task_dir(WRAP) / "judge-run.md", wrap_judge_run("T050", OLD_MERGE))
    why = wrap_problem(run_dir)
    assert why == "이어받은 CI가 원천과 다름: 적힌 T050 {}, 원천 T051 {}".format(OLD_MERGE, LAST_MERGE), why


def test_wrap_up_gate_rejects_inherited_ci_with_another_sha(run_dir):
    two_flows(run_dir)
    write(run_dir.task_dir(WRAP) / "judge-run.md", wrap_judge_run("T051", "e" * 12))
    why = wrap_problem(run_dir)
    assert why == "이어받은 CI가 원천과 다름: 적힌 T051 {}, 원천 T051 {}".format("e" * 12, LAST_MERGE), why


def test_wrap_up_gate_rejects_inherited_ci_without_a_source(run_dir):
    two_flows(run_dir, last_failed="- 기준 1: 단위 시험 실패 1")
    write(run_dir.task_dir(WRAP) / "judge-run.md", wrap_judge_run("T051", LAST_MERGE))
    why = wrap_problem(run_dir)
    assert why == "이어받을 원천 없음(T051 「통과 못 한 기준」이 `- 없음`이 아님): 전체 검증을 새로 돌린다", why


def test_wrap_up_gate_still_checks_the_verified_commit_when_inherited(run_dir):
    two_flows(run_dir)
    write(run_dir.task_dir(WRAP) / "judge-run.md", wrap_judge_run("T051", LAST_MERGE).replace(HEAD, "f" * 40))
    why = wrap_problem(run_dir)
    assert why == "최종 배포 후보 CI 검증 commit({})이 후보 commit({})과 다름".format("f" * 40, HEAD), why


def test_final_merge_gate_rejects_inherited_scope(run_dir):
    run_dir.flow("a", status="합쳐짐")
    run_dir.flow("b", status="합침")
    task(run_dir, "T051", merge_judge_run(LAST_MERGE, scope="이어받은 전체 검증"), kind="merge", block="합치기",
         flow="b", status="자체검증", commit=LAST_MERGE, stage="끝")
    t = run_dir.tasks()["T051"]
    assert task_set.final_merge_candidate(str(run_dir), t)
    why = task_set.final_candidate_ci_problem(str(run_dir), t)
    assert why == "최종 배포 후보 CI 범위가 전체 검증이 아님(이어받은 전체 검증)", why
