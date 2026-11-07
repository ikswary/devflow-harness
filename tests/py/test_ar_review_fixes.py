"""A-R 화면 수정 리뷰의 재현(B1~B4, I1~I6).

- 「하실 일」을 옮겨도 알림으로 지나가지 않고, 판정자가 올린 항목과 명령 항목은 옮기지 않는다.
- 자료는 이 판의 한 장을 올린 표지가 있을 때만 접는다.
- 기준선의 `실패 없음` 뒤 글은 화면에 그대로 싣는다. 옛 실행은 예전 동작이다.
- 받아오기 접기는 출처에서 닿는 병합만이고, 우리 쪽이 기준 뒤에 고친 파일은 접지 않는다.
- 값은 마지막 행을 읽어 허락을 거둘 수 있다.
"""
import re
from pathlib import Path

import pytest

import collect  # noqa: F401
import devflow_lib as lib
import flow_review
import machine_check
import places
import screen
import visual
from conftest import run_script, write
from test_ar_screen import SPEC, WEAK, git, merge, merging, resolve, rows_of, sha  # noqa: F401
from test_review_contract import NEW, code_task, notifies
from test_sheet import page_of, screen_of, sheet_of, task
from test_sheet_upload import allow

ROOT = Path(__file__).resolve().parents[2]
LINK = "https://claude.ai/code/artifact/00000000"
HEADINGS = "#### 문제\n되돌림이 멈춥니다\n#### 원인\n검사가 막음\n#### 고치는 법\n키 형식으로 정함"


# ---------------------------------------------------------------- 「하실 일」은 옮기지 않는다

@pytest.mark.parametrize("todo", [
    "- 직접 확인하시려면 `npm test`를 돌리면 됩니다",
    "- 직접 확인하시려면 운영 콘솔에서 비밀값을 넣어 주세요. 넣지 않으면 배포가 막힙니다",
    "- 운영 DB에 마이그레이션을 적용해 주세요. 필수 확인은 아닙니다.",
])
def test_todo_is_counted_and_never_passes_by_notice(run_dir, todo):
    code_task(run_dir, cells={"todo": todo})
    ok, _, out = notifies(run_dir)
    assert ok is False and "n_todo=1" in out and "n_notify=0" in out and "■ 하실 일·허용 요청 (1)" in out


def test_delegation_does_not_close_a_direct_check_todo(run_dir):
    code_task(run_dir, cells={"todo": "- 직접 확인하시려면 `npm test`를 돌리면 됩니다"})
    assert not hasattr(screen, "move_optional_todo")
    status = screen.delegation_status(str(run_dir.path), "T001")
    assert status["closable"] is False


# ---------------------------------------------------------------- B2 접기

def sent(run_dir):
    assert run_script("visual", run_dir.path, "T001", "--sheet-sent", LINK).returncode == 0


def test_material_stays_open_with_a_local_sheet_only(run_dir):
    task(run_dir, kind="root-cause", material=HEADINGS, decide="- 고를 것 (가) 예", notify="- 근본 원인")
    sheet_of(run_dir)
    assert "키 형식으로 정함" in screen_of(run_dir)


def test_material_folds_after_this_sheet_is_sent_and_shows_the_link(run_dir):
    material = "문제와 고치는 법\n\n" + HEADINGS
    task(run_dir, material=material, decide="- 고를 것 (가) 예")
    sheet_of(run_dir)
    sent(run_dir)
    out = screen_of(run_dir)
    assert "키 형식으로 정함" not in out and "  문제와 고치는 법" in out and LINK in out


def test_failure_after_send_opens_the_material_again(run_dir):
    task(run_dir, material="앞\n\n" + HEADINGS, decide="- 고를 것 (가) 예")
    sheet_of(run_dir)
    sent(run_dir)
    assert run_script("visual", run_dir.path, "T001", "--sheet-failed", "도구가 거부함").returncode == 0
    assert "키 형식으로 정함" in screen_of(run_dir)


def test_new_version_of_the_sheet_needs_a_new_mark(run_dir):
    task(run_dir, material="앞\n\n" + HEADINGS, decide="- 고를 것 (가) 예")
    sheet_of(run_dir)
    sent(run_dir)
    path = run_dir.task_dir("T001") / "sheet.html"
    write(path, path.read_text(encoding="utf-8") + "<!-- 다음 판 -->")
    assert "키 형식으로 정함" in screen_of(run_dir)


def test_withdrawn_value_opens_the_material_even_with_the_mark(run_dir):
    task(run_dir, material="앞\n\n" + HEADINGS, decide="- 고를 것 (가) 예")
    allow(run_dir, "허용")
    sheet_of(run_dir)
    sent(run_dir)
    out = screen_of(run_dir)
    assert "키 형식으로 정함" not in out and LINK in out
    allow(run_dir, "허용")   # allow는 앞에 넣으므로 뒤에 온 행이 마지막 행이다
    path = run_dir.path / "run.md"
    write(path, path.read_text(encoding="utf-8").replace("| 한 장 올리기 | 허용 |\n| 한 장 올리기 | 허용 |\n", "| 한 장 올리기 | 허용 |\n| 한 장 올리기 | 없음 |\n", 1))
    assert lib.sheet_upload(str(run_dir.path)) == "없음"
    out = screen_of(run_dir)
    assert "키 형식으로 정함" in out and LINK not in out


def test_one_time_upload_folds_only_until_the_answer(run_dir):
    task(run_dir, material="앞\n\n" + HEADINGS, decide="- 고를 것 (가) 예")
    sheet_of(run_dir)
    sent(run_dir)
    assert "키 형식으로 정함" not in screen_of(run_dir)   # 값이 `없음`이어도 이 답의 일회 올리기다
    path = run_dir.task_dir("T001") / "task.md"
    write(path, path.read_text(encoding="utf-8").rstrip("\n") + '\n\n## 승인 기록\n- 2026-01-01 00:00:00 | 되물음(이해) | 물음 | 원문: "무엇인가요"\n')
    assert len(lib.record_lines(run_dir.tasks()["T001"])) == 1
    assert "키 형식으로 정함" in screen_of(run_dir)


def test_mark_without_a_sheet_does_not_fold(run_dir):
    task(run_dir, material="앞\n\n" + HEADINGS, decide="- 고를 것 (가) 예")
    sent(run_dir)
    assert "키 형식으로 정함" in screen_of(run_dir)


def test_upload_doc_puts_the_mark_before_save():
    doc = (ROOT / "references" / "main" / "sheet-upload.md").read_text(encoding="utf-8")
    assert doc.index("--sheet-sent") < doc.index("--save")


# ---------------------------------------------------------------- B3 기준선

def baseline(run_dir, body, version="1.2.0-dev.1"):
    path = run_dir.path / "run.md"
    write(path, re.sub(r"harness_version:.*", "harness_version: " + version, path.read_text(encoding="utf-8"), count=1))
    write(run_dir.path / "baseline-run.md", "판정자: j 2026-01-01 00:00:00\n" + body + "\n")
    return run_script("screen", run_dir.path, "--baseline")


@pytest.mark.parametrize("body,words", [
    ("실패 없음 (e2e 3건 실패는 무시함)", "e2e 3건 실패는 무시함"),
    ("- 실패 없음 (브라우저 시험은 돌지 못함)", "브라우저 시험은 돌지 못함"),
    ("실패 없음（11개 중 9개만 돌림）.", "11개 중 9개만 돌림"),
])
def test_text_after_clean_is_shown_as_written(run_dir, body, words):
    p = baseline(run_dir, body)
    assert p.returncode == 0 and "! 판정자가 적은 글: " + words in p.stdout


def test_plain_clean_has_no_note(run_dir):
    p = baseline(run_dir, "실패 없음")
    assert p.returncode == 0 and "판정자가 적은 글" not in p.stdout


@pytest.mark.parametrize("body,rc", [("- 실패 없음", 3), ("실패 없음 (11개 명령 rc=0)", 3), ("실패 없음", 0)])
def test_old_run_keeps_the_old_reading(run_dir, body, rc):
    assert baseline(run_dir, body, "1.1.1").returncode == rc


def test_old_run_keeps_clean_with_a_row(run_dir):
    assert baseline(run_dir, "실패 없음\n- 돌지 못함: e2e | 환경 없음", "1.1.1").returncode == 0


# ---------------------------------------------------------------- B4 질문

def test_question_says_captures_are_not_masked_and_documents_go_up():
    doc = (ROOT / "references" / "main" / "sheet-upload.md").read_text(encoding="utf-8")
    for words in ("이 실행에서 승인을 물을 때마다", "설계·요구사항 문서", "화면 캡처는 전혀 가리지 않습니다", "이름·주소·업무 내용은 그대로"):
        assert words in doc, words


# ---------------------------------------------------------------- I1 답 반영

def test_only_lines_the_verify_writer_covered_fold(run_dir, monkeypatch):
    run_dir.flow("reading", status="폴더 있음", base_commit="abc")
    run_dir.task("T090", "검증", kind="flow-verify", block="검증", flow="reading", **NEW)
    tasks = run_dir.tasks()
    cells = {"T003": "- 수정안 (가)대로 도우미로 고쳤습니다\n- 범위는 로컬 시험까지입니다. push 없음", "T006": "- 「지금 받아옴」: 충돌만 고침"}
    monkeypatch.setattr(lib, "result_cells", lambda o: {"답하신 것의 반영": cells[o["id"]]})
    monkeypatch.setattr(places, "check_tasks", lambda *_: [{"id": "T003"}, {"id": "T006"}])
    written = "- 수정안 (가)대로 고쳐졌음을 확인했습니다\n- 범위는 로컬 시험까지입니다. 이 검증도 같음"
    got = flow_review.answered_items(tasks, tasks["T090"], written)
    assert got == ["- 코드 task가 옮긴 같은 답 2건: T003 2(각 task 결과 「답하신 것의 반영」)", "- [T006] 「지금 받아옴」: 충돌만 고침"]


# ---------------------------------------------------------------- I2, I3 받아오기

def test_self_merge_of_a_side_branch_is_not_folded(tmp_path):
    repo = tmp_path / "code"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "flow")
    write(repo / "a.test.ts", SPEC)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = sha(repo)
    git(repo, "checkout", "-qb", "tmp")
    write(repo / "a.test.ts", WEAK)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "weak")
    git(repo, "checkout", "-q", "flow")
    git(repo, "merge", "--no-ff", "-qm", "m", "tmp")
    rows = machine_check.find_test_changes(str(repo), lib.test_change_settings(str(repo)), base, None, ("dev", "flow-source"))
    assert [r for r in rows if r["change"] == "단언 약화"]
    assert any(r["change"] == lib.TEST_PULLED and "가려내지 못함" in r["basis"] for r in rows)


def test_no_known_source_folds_nothing(merging):
    base = sha(merging)
    merge(merging)
    resolve(merging)
    rows = machine_check.find_test_changes(str(merging), lib.test_change_settings(str(merging)), base)
    assert [r for r in rows if r["change"] == "단언 약화" and "b.test.ts" in r["place"]]


def test_fold_line_names_the_files(merging):
    base = sha(merging)
    merge(merging)
    resolve(merging)
    fold = [r for r in rows_of(merging, base) if r["change"] == lib.TEST_PULLED]
    assert "b.test.ts" in fold[0]["basis"]


@pytest.mark.parametrize("value,kept,dropped", [
    ("integration@7252f0f → 5b1f2c5", {"integration", "7252f0f"}, {"5b1f2c5", "→"}),
    ("integration@7252f0f -> 5b1f2c5", {"integration", "7252f0f"}, {"5b1f2c5", "->"}),
    ("integration@7252f0f (결과 5b1f2c5)", {"integration", "7252f0f"}, {"5b1f2c5", "결과"}),
    ("[a@111, b@222 → 333]", {"a", "111", "b", "222"}, {"333"}),
])
def test_merge_result_is_not_a_source(run_dir, value, kept, dropped):
    run_dir.flow("reading", status="폴더 있음", base_commit="abc", synced_to=value)
    run_dir.task("T006", "받아오기", kind="fix", block="구현", flow="reading", **NEW)
    got = set(machine_check.pull_sources(run_dir.tasks()["T006"]))
    assert kept <= got and not (dropped & got)


def test_sources_come_from_the_run_and_flow(run_dir):
    run_dir.flow("reading", status="폴더 있음", base_commit="abc", sync_pending="[feature/a@1234567]", synced_to="fixes@7654321")
    path = run_dir.path / "run.md"
    write(path, path.read_text(encoding="utf-8").replace("start_task:", "base_branch: dev\nintegration_branch: integ\nstart_task:", 1))
    run_dir.task("T006", "받아오기", kind="fix", block="구현", flow="reading", **NEW)
    assert set(machine_check.pull_sources(run_dir.tasks()["T006"])) == {"dev", "integ", "feature/a", "1234567", "fixes", "7654321"}


def test_own_commit_after_the_base_is_not_folded(tmp_path):
    repo = tmp_path / "code"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "flow")
    write(repo / "a.test.ts", SPEC)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = sha(repo)
    git(repo, "checkout", "-qb", "dev")
    write(repo / "a.test.ts", WEAK + "// dev\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "dev")
    git(repo, "checkout", "-q", "flow")
    write(repo / "a.test.ts", SPEC + 'it("mine", () => { expect(1).toBe(1) })\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "own")
    import subprocess
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "merge", "--no-commit", "dev"], capture_output=True)
    git(repo, "checkout", "--theirs", "a.test.ts")
    git(repo, "add", "a.test.ts")
    assert [r for r in rows_of(repo, base) if r["change"] == "단언 약화"]


# ---------------------------------------------------------------- I4 항목 앞 글

def plain_cells(run_dir):
    run_dir.task("T001", "시험", kind="design", block="설계", status="승인대기", **NEW)
    run_dir.result("T001", "# 결과\n\n## 승인 화면\n### 리뷰 자료\n한 일\n### 정해 주실 것\n- 없음\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n- 없음\n"
                           "### 답하신 것의 반영\n앞 답의 반영: 범위를 줄임\n- 첫째\n- 둘째\n### 확인 안 된 것\n- 없음\n### 건수만\n통과 12, 건너뜀 3\n")


def test_text_before_items_is_kept_on_screen_and_sheet(run_dir):
    plain_cells(run_dir)
    out = run_script("screen", run_dir.path, "T001").stdout
    assert "건너뜀 3" in out and "범위를 줄임" in out
    page = page_of(run_dir)
    assert "건너뜀 3" in page and "범위를 줄임" in page


# ---------------------------------------------------------------- I5 일회 올리기

def test_once_names_the_file_without_changing_the_value(run_dir):
    task(run_dir, material="한 일")
    p = run_script("visual", run_dir.path, "T001", "--sheet", "--once")
    assert p.returncode == 0 and "올릴 파일: " in p.stdout and lib.sheet_upload(str(run_dir.path)) == "없음"


def test_once_still_checks_the_size(run_dir, monkeypatch, capsys):
    task(run_dir, material="한 일")
    monkeypatch.setattr(visual, "UPLOAD_LIMIT", 10)
    visual.sheet(str(run_dir.path), "T001", once=True)
    out = capsys.readouterr().out
    assert "올리지 못함: " in out and "올릴 파일:" not in out


def test_upload_doc_shows_the_question_before_a_one_time_upload():
    doc = (ROOT / "references" / "main" / "sheet-upload.md").read_text(encoding="utf-8")
    assert "--sheet --once" in doc and "질문의 문장" in doc


# ---------------------------------------------------------------- I6 거두기

@pytest.mark.parametrize("rows,want", [
    (("허용", "없음"), "없음"), (("없음", "허용"), "허용"), (("허용", "모름"), "없음"), (("허용",), "허용"),
])
def test_last_row_wins(run_dir, rows, want):
    for value in reversed(rows):
        allow(run_dir, value)
    assert lib.sheet_upload(str(run_dir.path)) == want


def test_upload_doc_says_how_to_withdraw():
    doc = (ROOT / "references" / "main" / "sheet-upload.md").read_text(encoding="utf-8")
    assert "거두" in doc and "이미 올린 페이지" in doc


# ---------------------------------------------------------------- R5, R6

def test_weakened_sentences_are_back():
    assert "2. 재현. 가능하면 실패하는 테스트로" in (ROOT / "references" / "kinds" / "root-cause.md").read_text(encoding="utf-8")
    assert "그 파일이 없으면 표 머리만" in (ROOT / "references" / "main" / "start.md").read_text(encoding="utf-8")
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "받아온 변경" in log
