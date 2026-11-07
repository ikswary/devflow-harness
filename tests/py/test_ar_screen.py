"""A-R 실제 실행에서 나온 화면 결함(1.2.0).

- 한 장과 터미널은 문제와 고치는 법을 먼저 보이고, 사람 판단에 필요 없는 줄을 접는다. 옛 task의 출력은 그대로다.
- 칸 제목의 수가 항목과 어긋나 보이지 않고, 제목이 두 번 나오지 않는다.
- 코드 의견의 백틱 안 ` | `에서 칸이 잘리지 않는다.
- 받아오기 병합은 받아온 쪽 그대로인 파일을 세지 않고, 그 task가 바꾼 시험은 놓치지 않는다.
- `[설계:]` 판단을 가리킨 `같은 판단:`은 닿지 않은 줄이 아니다.
- 기준선 파일은 안내대로 쓴 꼴을 읽고, 실패 줄을 놓칠 줄은 여전히 거부한다.
"""
import re
import subprocess

import pytest

import devflow_lib as lib
import machine_check
import places
import screen
import visual
from conftest import run_script, write
from test_flow_review import flow_verify, screen_text
from test_code_check import FV
from test_review_contract import OLD
from test_sheet import NEW, child_row, page_of, screen_of, sheet_of, task


# ---------------------------------------------------------------- 1. 차례

def test_sheet_shows_material_before_numbered_items(run_dir):
    task(run_dir, kind="root-cause", material="문제: 되돌림이 멈춥니다. 원인: 검사. 고치는 법: 키로 정합니다.", decide="- 고를 것 (가) 예", notify="- 근본 원인")
    page = page_of(run_dir)
    assert page.index("문제: 되돌림이 멈춥니다") < page.index("정하는 것:") < page.index("터미널 번호")


def test_sheet_without_material_warns(run_dir):
    write(run_dir.path / "design" / "list.md", "| 규칙 | 값 |\n|---|---|\n| 정렬 | 이름 |\n")
    task(run_dir, kind="change", sections={"건드릴 파일": "- design/list.md"}, decide="- 고를 것 (가) 예")
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "| 규칙 | 값 |\n|---|---|\n| 정렬 | 최근 |\n")
    page = page_of(run_dir)
    assert screen.MATERIAL_MISSING.split("(")[0] in page and page.index("리뷰 자료 없음") < page.index("터미널 번호")


def test_terminal_shows_material_before_main_lines(run_dir):
    task(run_dir, material="문제와 고치는 법", decide="- 고를 것 (가) 예", sections={"넘길 이상 신호": "- 그 밖의 메모"})
    write(run_dir.task_dir("T001") / "judge.md", "판정자: j 2026-01-01 00:00:00\n\n## 통과 못 한 기준\n- 없음\n\n## 확인 방법 요약\n원본 전부 대조 1\n")
    out = screen_of(run_dir)
    assert out.index("■ 리뷰 자료") < out.index("■ 정해 주실 것") < out.index("■ 이상 신호") < out.index("■ 자체 검증의 확인 방법") < out.index("counts:")


def test_premise_signal_stays_above_the_material(run_dir):
    mark = screen.PREMISE_MARK + " 전제가 바뀌었다"
    task(run_dir, material="문제와 고치는 법", decide="- 고를 것 (가) 예", sections={"넘길 이상 신호": "- " + mark})
    out = screen_of(run_dir)
    assert out.index(mark) < out.index("■ 리뷰 자료")


# ---------------------------------------------------------------- 2. 줄 수

def test_counts_only_folds_to_one_line_without_numbers(run_dir):
    task(run_dir, material="한 일", decide="- 고를 것 (가) 예")
    path = run_dir.task_dir("T001") / "result.md"
    path.write_text(path.read_text(encoding="utf-8").replace("### 건수만\n- 없음", "### 건수만\n- 기각한 가설 5건\n- 대조 시험 1건"), encoding="utf-8")
    out = screen_of(run_dir)
    assert "■ 건수만 (2): 기각한 가설 5건 · 대조 시험 1건\n" in out
    assert not re.search(r"- \[\d+\] (기각한|대조 시험)", out)


def test_head_folds_the_queue_line_into_the_see_line(run_dir):
    task(run_dir, material="한 일", decide="- 고를 것 (가) 예")
    out = screen_of(run_dir)
    assert "이 화면의 사람 판단 항목" not in out
    assert next(l for l in out.splitlines() if l.startswith("볼 곳:")).endswith("· 대기 중 1개")


def test_material_sections_fold_only_when_the_sheet_holds_them(run_dir):
    material = "문제와 고치는 법\n\n#### 고치면 보이는 모양\n- 전: 멈춤\n- 후: 되돌림"
    task(run_dir, material=material, decide="- 고를 것 (가) 예")
    assert "- 전: 멈춤" in screen_of(run_dir)   # 한 장이 없으면 다 보인다
    sheet_of(run_dir)
    assert "- 전: 멈춤" in screen_of(run_dir)   # 올리기 전에는 사람이 열 수 없다
    assert run_script("visual", run_dir.path, "T001", "--sheet-sent", "https://claude.ai/code/artifact/0").returncode == 0
    out = screen_of(run_dir)
    assert "- 전: 멈춤" not in out and "  문제와 고치는 법" in out and "나머지 3줄은 한 장" in out and "고치면 보이는 모양" in out
    assert "- 전: 멈춤" in page_of(run_dir)


def test_old_task_keeps_its_lines(run_dir):
    task(run_dir, meta=OLD, decide="- 고를 것 (가) 예", notify="- 알림")
    path = run_dir.task_dir("T001") / "result.md"
    path.write_text(path.read_text(encoding="utf-8").replace("### 건수만\n- 없음", "### 건수만\n- 기각한 가설 5건"), encoding="utf-8")
    out = screen_of(run_dir)
    assert "대기 중 1개 · 이 화면의 사람 판단 항목" in out and "■ 건수만 (1)\n- 기각한 가설 5건\n" in out


def test_test_change_rows_share_one_answer_cue(run_dir):
    flow_verify(run_dir)
    tasks = run_dir.tasks()
    rows = [{"change": "단언 약화", "place": "a.test.ts:{}".format(n), "file": "a.test.ts", "basis": "단언 -1", "why": "적지 않음", "guard": "없음",
             "key": "s{}".format(n), "ask": True, "answer": "", "quote": "", "task": "T040"} for n in range(2)]
    original = lib.flow_test_rows
    lib.flow_test_rows = lambda *_: rows
    try:
        count, lines = screen.test_change_lines(str(run_dir.path), tasks[FV], tasks)
    finally:
        lib.flow_test_rows = original
    assert count == 2 and sum("받아들임 / 되살림" in line for line in lines) == 1


def test_answered_lines_fold_when_the_verify_writer_already_wrote(run_dir, monkeypatch):
    flow_verify(run_dir)
    tasks = run_dir.tasks()
    monkeypatch.setattr(lib, "result_cells", lambda o: {"답하신 것의 반영": "- 안 가대로 고침\n- 로컬 시험까지"})
    monkeypatch.setattr(places, "check_tasks", lambda *_: [{"id": "T040"}, {"id": "T041"}])
    import flow_review
    written = "- 안 가대로 고침을 확인함\n- 로컬 시험까지 맞춘 확인"
    monkeypatch.setattr(lib, "result_cells", lambda o: {"답하신 것의 반영": "- 안 가대로 고침을 코드로\n- 로컬 시험까지 맞춘 코드"})
    same = flow_review.answered_items(tasks, tasks[FV], written)
    assert same == ["- 코드 task가 옮긴 같은 답 4건: T040 2, T041 2(각 task 결과 「답하신 것의 반영」)"]
    assert len(flow_review.answered_items(tasks, tasks[FV], "- 없음")) == 4   # 검증이 옮겨 적지 않았으면 접지 않는다


# ---------------------------------------------------------------- 3. 칸 제목의 수

def test_title_says_moved_items_apart_from_own_count(run_dir):
    task(run_dir, material="한 일", decide="- 고를 것 (가) 예", unverified="- [T002] 앞 task의 줄\n- [T003] 또 다른 줄", notify="- 이 task의 줄\n- [T002] 옮긴 줄")
    out = screen_of(run_dir)
    assert "■ 확인 안 된 것 (0, 앞 task에서 옮긴 것 2)" in out and "■ 알릴 것 (1, 앞 task에서 옮긴 것 1)" in out
    assert "n_unverified=0" in out and "n_notify=1" in out
    assert run_script("screen", run_dir.path, "T001", "--save").returncode == 0
    assert run_script("screen", run_dir.path, "T001", "--answer", "이의 3").returncode == 0   # 번호는 옮긴 줄에도 달린다


# ---------------------------------------------------------------- 4. 제목 두 번

@pytest.mark.parametrize("heading", ["#### ■ 이 흐름이 한 일", "#### 이 흐름이 한 일"])
def test_flow_title_is_not_repeated(run_dir, heading):
    flow_verify(run_dir, material=heading + "\n운영자가 칸을 적습니다.")
    out = screen_text(run_dir)
    assert out.count("이 흐름이 한 일") == 1 and "  운영자가 칸을 적습니다." in out


def test_material_heading_becomes_the_title(run_dir):
    task(run_dir, material="#### ■ 이 실행이 한 일\n한 일", decide="- 고를 것 (가) 예")
    out = screen_of(run_dir)
    assert "■ 이 실행이 한 일\n  한 일" in out and "■ 리뷰 자료" not in out and "####" not in out
    assert "<h2>이 실행이 한 일</h2>" in page_of(run_dir)


def test_cell_name_is_not_taken_as_a_material_title(run_dir):
    task(run_dir, material="#### 정해 주실 것\n한 일", decide="- 고를 것 (가) 예")
    assert "■ 리뷰 자료\n  #### 정해 주실 것" in screen_of(run_dir)


# ---------------------------------------------------------------- 5. 백틱 안의 나눔

def test_cell_split_keeps_pipes_inside_backticks():
    line = "`a.ts:54` | 일어난 일 | 지금 문제 없음 | `x | y`면 깨짐 | 다른 곳은 `ImageInfo | null`을 받음"
    assert places.split_cells(line) == ["`a.ts:54`", "일어난 일", "지금 문제 없음", "`x | y`면 깨짐", "다른 곳은 `ImageInfo | null`을 받음"]


def test_unbalanced_backtick_falls_back_to_plain_split():
    assert places.split_cells("a | `b | c") == ["a", "`b", "c"]


def test_stored_opinion_keeps_the_way_whole():
    raw = "코드 의견: `a.ts:54` | 일어난 일 | 지금 문제 없음 | 타입 검사가 잡음 | 같은 파일은 `ImageInfo | null`을 받음"
    got = places._stored_opinions({"의견 줄": [raw]})[0]
    assert got["breaks"] == "타입 검사가 잡음" and got["way"] == "같은 파일은 `ImageInfo | null`을 받음"


# ---------------------------------------------------------------- 6. 받아오기 병합의 시험 변화

SPEC = 'it("x", () => {\n  expect(f()).toBe(1);\n  expect(g()).toBe(2);\n});\n'
WEAK = 'it("x", () => {\n  expect(f()).toBe(1);\n});\n'


def git(folder, *args):
    subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t"] + list(args), check=True, capture_output=True)


def sha(folder, ref="HEAD"):
    return subprocess.run(["git", "-C", str(folder), "rev-parse", ref], check=True, capture_output=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def merging(tmp_path):
    """받아오기 앞의 흐름(ours)과 들어올 쪽(theirs). `theirs`는 `b.test.ts`의 단언을 줄이고 ours는 `own.ts`를 고쳤다."""
    repo = tmp_path / "code"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "flow")
    for name in ("a.test.ts", "b.test.ts", "both.test.ts"):
        write(repo / name, SPEC)
    write(repo / "own.ts", "1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    git(repo, "branch", "dev")
    git(repo, "checkout", "-q", "dev")
    write(repo / "b.test.ts", WEAK)
    write(repo / "both.test.ts", 'it("x", () => {\n  expect(f()).toBe(1);\n  expect(g()).toBe(2);\n  expect(h()).toBe(3);\n});\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "dev")
    git(repo, "checkout", "-q", "flow")
    write(repo / "own.ts", "2\n")
    write(repo / "both.test.ts", 'it("x", () => {\n  expect(f()).toBe(1);\n  expect(g()).toBe(2);\n  expect(k()).toBe(4);\n});\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "flow")
    return repo


def merge(repo):
    """충돌을 남긴 채 멈춘 받아오기. 충돌은 both.test.ts 하나다."""
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "merge", "--no-commit", "dev"], capture_output=True)


def rows_of(repo, base, head=None):
    return machine_check.find_test_changes(str(repo), lib.test_change_settings(str(repo)), base, head, ("dev",))


def resolve(repo, body=SPEC):
    write(repo / "both.test.ts", body)
    git(repo, "add", "both.test.ts")


def test_pulled_files_are_not_counted_during_the_merge(merging):
    base = sha(merging)
    merge(merging)
    resolve(merging)
    rows = rows_of(merging, base)
    assert not [r for r in rows if r["change"] == "단언 약화" and "b.test.ts" in r["place"]]
    fold = [r for r in rows if r["change"] == lib.TEST_PULLED]
    assert len(fold) == 1 and "시험 쪽 파일 1개" in fold[0]["basis"]


def test_pulled_files_are_not_counted_after_the_merge_commit(merging):
    base = sha(merging)
    merge(merging)
    resolve(merging)
    git(merging, "commit", "-qm", "merge")
    rows = rows_of(merging, base, sha(merging))
    assert not [r for r in rows if "b.test.ts" in r["place"]] and [r for r in rows if r["change"] == lib.TEST_PULLED]


def test_weakening_while_resolving_the_conflict_is_kept(merging):
    base = sha(merging)
    merge(merging)
    resolve(merging, WEAK)
    assert [r for r in rows_of(merging, base) if r["change"] == "단언 약화" and "both.test.ts" in r["place"]]


def test_weakening_a_pulled_file_during_the_merge_is_kept(merging):
    base = sha(merging)
    merge(merging)
    resolve(merging)
    write(merging / "a.test.ts", WEAK)   # dev가 고치지 않은 파일을 함께 약화
    write(merging / "b.test.ts", 'it("x", () => {\n});\n')   # 받아온 파일을 더 약화
    rows = rows_of(merging, base)
    assert [r for r in rows if r["change"] == "단언 약화" and "a.test.ts" in r["place"]]
    assert [r for r in rows if r["change"] == "단언 약화" and "b.test.ts" in r["place"]]


def test_taking_their_side_of_our_own_change_is_kept(merging):
    """우리 쪽도 고친 파일을 받아온 쪽 그대로 두면 우리 단언이 사라진 것이다."""
    base = sha(merging)
    merge(merging)
    git(merging, "checkout", "--theirs", "both.test.ts")
    git(merging, "add", "both.test.ts")
    assert "both.test.ts" not in machine_check.pulled_files(str(merging), base, None, base, sha(merging, "MERGE_HEAD"), ("dev",))


def test_plain_commit_has_no_pulled_row(merging):
    base = sha(merging)
    write(merging / "a.test.ts", WEAK)
    rows = rows_of(merging, base)
    assert [r for r in rows if "a.test.ts" in r["place"]] and not [r for r in rows if r["change"] == lib.TEST_PULLED]


def test_unknown_merge_shape_says_so_and_keeps_every_row(merging, monkeypatch):
    base = sha(merging)
    merge(merging)
    resolve(merging)
    monkeypatch.setattr(machine_check, "merge_bases", lambda *_: ["a", "b"])
    rows = rows_of(merging, base)
    assert [r for r in rows if r["change"] == "단언 약화" and "b.test.ts" in r["place"]]
    assert any(r["change"] == lib.TEST_PULLED and "가려내지 못함" in r["basis"] for r in rows)


def test_pulled_row_is_a_count_not_a_question(run_dir, merging):
    assert lib._test_row("T006", lib.TEST_PULLED, "전체", "시험 쪽 파일 1개")["ask"] is False


# ---------------------------------------------------------------- 8. 판정자 줄이 판단에 닿지 않음

RESULT = ("# 결과\n\n## 판단\n- `helper`를 `src/a.ts`에 두고, 문구를 고침 [설계: T002 D2, 2026-01-01 00:00:00]\n"
          "- 합 타입을 둠 [종류: 구조] [위치: src/a.ts:5]\n")


def judge_lines(run_dir, compare):
    run_dir.task("T003", "코드", kind="be-implementation", block="구현", **NEW)
    run_dir.result("T003", RESULT)
    write(run_dir.task_dir("T003") / "judge.md", "판정자: j 2026-01-01 00:00:00\n\n## 판단 대조\n" + compare)
    t = run_dir.tasks()["T003"]
    warnings = []
    places._with_judge(t, places._judgments(t), places._judge_lines(t), warnings)
    return warnings


def test_same_judgment_pointing_at_a_design_line_is_not_a_miss(run_dir):
    assert judge_lines(run_dir, "- 같은 판단: `helper`를 `src/a.ts`에 두고 | T002\n") == []


def test_same_judgment_with_no_such_line_still_warns(run_dir):
    assert judge_lines(run_dir, "- 같은 판단: 없는 문장을 인용함 | T002\n") == ["T003 같은 판단 없는 문장을 인용함"]


def test_kind_objection_on_a_design_line_still_warns(run_dir):
    """종류 이의는 그 판단을 코드로 올리는 줄이다. 곳에 들지 못하면 알려야 한다."""
    assert judge_lines(run_dir, "- 종류 이의: `helper`를 `src/a.ts`에 두고 | 구조 → 보안\n") != []


# ---------------------------------------------------------------- 10. 기준선

@pytest.fixture
def new_run(run_dir):
    path = run_dir.path / "run.md"
    write(path, re.sub(r"harness_version:.*", "harness_version: 1.2.0-dev.1", path.read_text(encoding="utf-8"), count=1))
    return run_dir


@pytest.mark.parametrize("body", [
    "판정자: j 2026-01-01 00:00:00\n실패 없음\n",
    "판정자: j 2026-01-01 00:00:00\n- 실패 없음\n",
    "\n판정자: j 2026-01-01 00:00:00\n\n실패 없음 (11개 명령 rc=0)\n",
])
def test_baseline_reads_the_shapes_a_judge_writes(new_run, body):
    write(new_run.path / "baseline-run.md", body)
    p = run_script("screen", new_run.path, "--baseline")
    assert p.returncode == 0 and "기준선 질문 없음" in p.stdout


@pytest.mark.parametrize("body", [
    "판정자: j 2026-01-01 00:00:00\n실패 2건이 있음\n",
    "판정자: j 2026-01-01 00:00:00\n실패 없음이라 하기 어려움\n",
    "판정자: j 2026-01-01 00:00:00\n실패 없음\n- a.test.ts 실패\n",
])
def test_baseline_still_refuses_what_could_hide_a_failure(new_run, body):
    write(new_run.path / "baseline-run.md", body)
    assert run_script("screen", new_run.path, "--baseline").returncode == 3
