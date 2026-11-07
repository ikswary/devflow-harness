"""1.2.0 A5: 시험 변화(설계 6.12절 「시험」).

- 기계 규칙: 변화 표의 관찰 표본을 실제 git 작업 트리로 돌린다.
- 줄의 꼴과 답: 기계 줄에 작성자 이유를 붙이고, 사람 답은 `--record "시험 변화|{키}=받아들임|{원문}"`로 남는다.
- 위임 중에도 답 없는 끄기·삭제는 흐름별 검증의 완료를 막고, 그 밖의 변화는 막지 않는다.
- 옛 판본으로 시작한 task는 지금 규칙 그대로다.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import devflow_lib as lib
import machine_check
import screen
import visual
from conftest import run_script, write
from test_review_contract import NEW, OLD, code_task, judged, result

ROOT = Path(__file__).resolve().parents[2]


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t"] + list(args),
                   check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    folder = tmp_path / "code"
    folder.mkdir()
    git(folder, "init", "-q")
    return folder


def changes(repo, base, edits=None, deletes=(), settings=None):
    """기준 커밋을 만들고 작업 트리를 고친 뒤 기계 줄을 돌려준다."""
    for path, text in dict(base, **{"keep.txt": "x\n"}).items():
        write(repo / path, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    for path, text in (edits or {}).items():
        write(repo / path, text)
    for path in deletes:
        (repo / path).unlink()
    return machine_check.find_test_changes(str(repo), settings or lib.test_change_settings(str(repo)))


def kinds_of(rows):
    return {row["change"] for row in rows}


SPEC = "a.test.ts"
PASS = 'it("x", () => {\n  expect(f()).toBe(1);\n});\n'


# ---------------------------------------------------------------- 끄기

@pytest.mark.parametrize("line", [
    'it.skip("x", () => {});', 'test.only("x", () => {});', 'describe.skip("x", () => {});', 'it.todo("x");',
    'test.fixme("x", () => {});', 'it.skipIf(ci)("x", () => {});', 'describe.runIf(ci)("x", () => {});',
])
def test_off_call_shapes_are_seen_in_a_new_file(repo, line):
    # 지금 규칙은 새 파일의 표시를 보지 못했다. 추적되지 않은 파일도 본다(mcp 관찰 표본의 꼴)
    rows = changes(repo, {}, {SPEC: line + "\n"})
    assert [r["change"] for r in rows if r["change"] == "끄기"] == ["끄기"]
    assert rows[0]["place"] == SPEC + ":1"


@pytest.mark.parametrize("path, line", [
    ("a.spec.js", "xit('x', () => {});"), ("b.spec.js", "xdescribe('x', () => {});"), ("tests/a.spec.js", "x.only(1)"),
    ("src/test/FooTest.java", "@Disabled"), ("src/test/BarTest.kt", "@Ignore"), ("test_a.py", "@pytest.mark.skip"),
    ("a_test.py", "@pytest.mark.skipif(x)"), ("a_test.go", "t.Skip()"),
])
def test_other_stack_marks_stay_in_the_union(repo, path, line):
    assert "끄기" in kinds_of(changes(repo, {}, {path: line + "\n"}))


def test_skip_marks_is_a_union_of_the_old_and_the_call_shape():
    old = ["x.skip(", "it.skip", "describe.skip", "test.skip", "xit(", "xdescribe(", "x.only(", "@Disabled", "@Ignore",
           "pytest.mark.skip", "t.Skip("]
    new = ["it.todo", "test.fixme", "it.skipIf", "describe.runIf", "test.only"]
    assert all(machine_check.SKIP_MARKS.search(s) for s in old + new)
    assert all(machine_check.OLD_SKIP_MARKS.search(s) for s in old)
    assert not any(machine_check.OLD_SKIP_MARKS.search(s) for s in ("it.todo", "test.fixme", "it.skipIf"))


@pytest.mark.parametrize("path, line", [
    ("src/q.ts", "return query.skip(10).only(['a']);"),   # 제품 칸의 skip은 거짓으로 난다
    ("src/w.ts", "const row = { skip: true };"),
])
def test_marks_in_product_files_are_not_off(repo, path, line):
    assert "끄기" not in kinds_of(changes(repo, {}, {path: line + "\n"}))


def test_off_counts_net_increase_per_file(repo):
    base = {SPEC: 'it.skip("a", () => {});\nit("b", () => {});\n'}
    assert "끄기" not in kinds_of(changes(repo, base, {SPEC: 'it("a", () => {});\nit.skip("b", () => {});\n'}))


# ---------------------------------------------------------------- 삭제

def test_deleted_test_file(repo):
    rows = changes(repo, {SPEC: PASS}, deletes=[SPEC])
    assert [(r["change"], r["place"]) for r in rows] == [("삭제", SPEC)]


def test_declaration_net_decrease_per_file(repo):
    base = {SPEC: 'it("a", () => {});\nit("b", () => {});\n'}
    row = next(r for r in changes(repo, base, {SPEC: 'it("a", () => {});\n'}) if r["change"] == "삭제")
    assert row["place"].startswith(SPEC) and "선언 -1" in row["basis"]


def test_a_rename_with_the_same_content_is_not_deleted(repo):
    assert "삭제" not in kinds_of(changes(repo, {"tests/a.test.ts": PASS}, {"tests/b.test.ts": PASS}, deletes=["tests/a.test.ts"]))


def test_it_each_row_removal_is_not_seen(repo):
    # 표의 관찰: `it.each` 행 삭제는 못 본다. 못 보는 것이 넓어지거나 좁아지면 이 시험이 알린다
    base = {SPEC: 'it.each([\n  [1],\n  [2],\n])("x", () => {});\n'}
    assert "삭제" not in kinds_of(changes(repo, base, {SPEC: 'it.each([\n  [1],\n])("x", () => {});\n'}))


# ---------------------------------------------------------------- 범위 축소, 돌리는 곳, 실패 거름

def test_runner_setting_is_range(repo):
    base = {"vitest.config.ts": "export default { test: { include: ['src/**/*.test.ts'] } };\n"}
    assert "범위 축소" in kinds_of(changes(repo, base, {"vitest.config.ts": "export default { test: { include: ['src/a/*.test.ts'] } };\n"}))


def test_other_lines_of_a_runner_config_are_not_range(repo):
    base = {"vitest.config.ts": "const a = 1;\n"}
    assert "범위 축소" not in kinds_of(changes(repo, base, {"vitest.config.ts": "const a = 2;\n"}))


def test_where_tests_run_comes_from_the_project_setting(repo):
    base = {"deploy/run.sh": "npm test\n"}
    wanted = dict(lib.test_change_settings(str(repo)), run=["deploy/**"])
    assert "시험을 돌리는 곳" in kinds_of(changes(repo, base, {"deploy/run.sh": "npm run smoke\n"}, settings=wanted))


def test_failure_filter(repo):
    base = {"vitest.config.ts": "export default { test: {} };\n"}
    assert "실패 거름" in kinds_of(changes(repo, base, {"vitest.config.ts": "export default { test: { passWithNoTests: true } };\n"}))


# ---------------------------------------------------------------- 재시도, 제한 시간

@pytest.mark.parametrize("before, after, change", [
    ("retries: 0,", "retries: 2,", "재시도"),
    ("const MAX_RETRIES = 1;", "const MAX_RETRIES = 3;", "재시도"),
    ("timeout: 5000,", "timeout: 30000,", "제한 시간과 허용 범위"),
    ("testTimeout: 5_000,", "testTimeout: 60_000,", "제한 시간과 허용 범위"),
    ("maxDiffPixels: 10,", "maxDiffPixels: 500,", "제한 시간과 허용 범위"),
])
def test_changed_definition_is_seen(repo, before, after, change):
    assert change in kinds_of(changes(repo, {"playwright.config.ts": before + "\n"}, {"playwright.config.ts": after + "\n"}))


@pytest.mark.parametrize("before, after", [
    ("const a = 1;", "const a = { retries: MAX_RETRIES, timeout: REQUEST_TIMEOUT };"),   # 이름을 그대로 쓰면 뺀다
    ("retries: 2, // old", "retries: 2, // new"),   # 값이 그대로면 뺀다
    ("setTimeout(fn, 10);", "setTimeout(fn, 20);"),   # 호출 인자의 첫 값이 숫자가 아니면 정의가 아니다
])
def test_using_the_same_name_or_value_is_not_seen(repo, before, after):
    rows = changes(repo, {SPEC: before + "\n"}, {SPEC: after + "\n"})
    assert not kinds_of(rows) & {"재시도", "제한 시간과 허용 범위"}


def test_retry_in_product_code_is_not_seen(repo):
    assert "재시도" not in kinds_of(changes(repo, {"src/a.ts": "retries: 1\n"}, {"src/a.ts": "retries: 5\n"}))


# ---------------------------------------------------------------- 단언 약화

def test_assertion_net_decrease(repo):
    base = {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n  expect(b).toBe(2);\n});\n'}
    rows = changes(repo, base, {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n});\n'})
    assert "단언 약화" in kinds_of(rows)


def test_matcher_swap_with_the_same_count(repo):
    # isolation T044의 꼴: 강한 매처 17→10, 약한 매처 6→15로 단언 수가 줄지 않았다
    strong, weak = "  expect(a).toEqual(b);\n", "  expect(a).toBeTruthy();\n"
    base = {SPEC: 'it("x", () => {\n' + strong * 17 + weak * 6 + "});\n"}
    rows = changes(repo, base, {SPEC: 'it("x", () => {\n' + strong * 10 + weak * 15 + "});\n"})
    assert "단언 약화" in kinds_of(rows)
    assert "강한 매처 -7" in next(r for r in rows if r["change"] == "단언 약화")["basis"]


def test_stronger_matchers_are_not_weakening(repo):
    base = {SPEC: 'it("x", () => {\n  expect(a).toBeTruthy();\n});\n'}
    assert "단언 약화" not in kinds_of(changes(repo, base, {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n});\n'}))


def test_assertions_moved_to_a_test_helper_are_left_out(repo):
    base = {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n  expect(b).toBe(2);\n});\n'}
    edits = {SPEC: 'it("x", () => {\n  check();\n});\n',
             "tests/helpers/check.ts": "export function check() {\n  expect(a).toBe(1);\n  expect(b).toBe(2);\n}\n"}
    assert "단언 약화" not in kinds_of(changes(repo, base, edits))


# ---------------------------------------------------------------- 정답 파일, 시험 도우미

def test_golden_change_is_seen_but_a_new_golden_is_not(repo):
    assert "정답 파일" in kinds_of(changes(repo, {"__snapshots__/a.snap": "1\n"}, {"__snapshots__/a.snap": "2\n"}))


def test_new_golden_file_is_not_a_change(repo):
    assert "정답 파일" not in kinds_of(changes(repo, {}, {"__snapshots__/a.snap": "1\n"}))


def test_golden_path_comes_from_the_project_setting(repo):
    wanted = dict(lib.test_change_settings(str(repo)), golden=["golden/**"])
    assert "정답 파일" in kinds_of(changes(repo, {"golden/a.json": "1\n"}, {"golden/a.json": "2\n"}, settings=wanted))


@pytest.mark.parametrize("path", ["tests/helpers/db.ts", "src/test-utils/render.tsx", "tests/conftest.py"])
def test_changed_test_helper(repo, path):
    assert "시험 도우미" in kinds_of(changes(repo, {path: "a\n"}, {path: "b\n"}))


def test_new_test_helper_is_not_a_change(repo):
    assert "시험 도우미" not in kinds_of(changes(repo, {}, {"tests/helpers/db.ts": "a\n"}))


def test_helper_in_product_path_is_not_a_test_helper(repo):
    assert "시험 도우미" not in kinds_of(changes(repo, {"src/helpers/a.ts": "a\n"}, {"src/helpers/a.ts": "b\n"}))


# ---------------------------------------------------------------- 표 밖의 기대값

def test_expectation_only_task(repo):
    rows = changes(repo, {SPEC: PASS, "src/a.ts": "1\n"}, {SPEC: PASS.replace("toBe(1)", "toBe(2)")})
    assert "기대값만 바꿈" in kinds_of(rows)


def test_a_product_change_is_not_expectation_only_and_the_rest_is_a_count(repo):
    rows = changes(repo, {SPEC: PASS, "src/a.ts": "1\n"}, {SPEC: PASS.replace("toBe(1)", "toBe(2)"), "src/a.ts": "2\n"})
    assert "기대값만 바꿈" not in kinds_of(rows)
    assert next(r for r in rows if r["change"] == "기대값 변경")["basis"] == "1줄"


def test_a_new_test_is_not_expectation_only(repo):
    rows = changes(repo, {SPEC: PASS}, {SPEC: PASS + 'it("y", () => {\n  expect(1).toBe(1);\n});\n'})
    assert "기대값만 바꿈" not in kinds_of(rows)


@pytest.mark.parametrize("before, after", [
    ("  version: 3,", "  version: UPDATE_REQUEST_STATUS.version + 1,"),
    ("  expect(a).toBe('대기');", "  expect(a).toBe(STATUS.WAITING);"),
])
def test_literal_to_product_reference(repo, before, after):
    head = 'it("x", () => {\n  expect(a).toEqual({\n'
    rows = changes(repo, {SPEC: head + before + "\n"}, {SPEC: head + after + "\n"})
    assert "리터럴이 제품 값으로" in kinds_of(rows)


@pytest.mark.parametrize("before, after", [
    ("  version: 3,", "  version: 4,"),
    ("  version: A.version,", "  version: B.version,"),
])
def test_other_value_changes_are_not_literal_to_reference(repo, before, after):
    rows = changes(repo, {SPEC: before + "\n"}, {SPEC: after + "\n"})
    assert "리터럴이 제품 값으로" not in kinds_of(rows)


def test_nothing_changed_in_tests(repo):
    assert changes(repo, {"src/a.ts": "1\n"}, {"src/a.ts": "2\n"}) == []


def test_korean_path_and_quoted_names_are_read(repo):
    path = "시험/가 나.test.ts"
    rows = changes(repo, {path: PASS}, {path: 'it.skip("x", () => {});\n'})
    assert "시험/가 나.test.ts:1" in {r["place"] for r in rows if r["change"] == "끄기"}


# ---------------------------------------------------------------- machine_check 명령

def machine(run_dir, repo, tid="T001", **meta):
    run_dir.task(tid, "구현", {"건드릴 파일": "- **"}, kind="implementation", block="구현", status="진행", flow="a", **meta)
    return run_script("machine_check", repo, run_dir.task_dir(tid) / "task.md")


def test_new_task_writes_lines_and_flags_off_and_removal(run_dir, repo):
    changes(repo, {"keep.test.ts": PASS}, {SPEC: 'it.skip("x", () => {});\n'}, deletes=["keep.test.ts"])
    out = machine(run_dir, repo, **NEW)
    assert out.returncode == 3 and "시험 끄기·삭제 2줄" in out.stdout
    text = (run_dir.task_dir("T001") / lib.TEST_CHANGES).read_text(encoding="utf-8")
    assert "- 끄기 | a.test.ts:1 |" in text and "- 삭제 | keep.test.ts |" in text


def test_new_task_other_changes_do_not_flag(run_dir, repo):
    base = {SPEC: "timeout: 1\n"}
    changes(repo, base, {SPEC: "timeout: 2\n"})
    out = machine(run_dir, repo, **NEW)
    assert out.returncode == 0 and "제한 시간과 허용 범위" in out.stdout


def test_new_task_with_no_change_writes_nothing_to_ask(run_dir, repo):
    changes(repo, {"src/a.ts": "1\n"}, {"src/a.ts": "2\n"})
    machine(run_dir, repo, **NEW)
    assert (run_dir.task_dir("T001") / lib.TEST_CHANGES).read_text(encoding="utf-8").strip().endswith("\n- 없음")
    assert lib.test_change_rows(run_dir.tasks()["T001"]) == []


def test_old_task_keeps_the_old_rule(run_dir, repo):
    # 옛 규칙은 새 파일의 표시와 it.todo를 보지 않고, 파일도 쓰지 않는다
    changes(repo, {SPEC: PASS}, {"b.test.ts": 'it.skip("x", () => {});\n', SPEC: PASS + 'it.todo("y");\n'})
    out = machine(run_dir, repo, **OLD)
    assert out.returncode == 0
    assert not (run_dir.task_dir("T001") / lib.TEST_CHANGES).exists()


def test_old_task_still_flags_deleted_tests(run_dir, repo):
    changes(repo, {SPEC: PASS}, deletes=[SPEC])
    assert machine(run_dir, repo, **OLD).returncode == 3


# ---------------------------------------------------------------- 줄의 꼴과 답

def lines_file(run_dir, tid, *rows):
    write(run_dir.task_dir(tid) / lib.TEST_CHANGES, "\n".join(rows) + "\n")


def with_writer(run_dir, tid, body):
    path = run_dir.task_dir(tid) / "result.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n## 시험 변화\n" + body + "\n", encoding="utf-8")


def flow(run_dir, *rows, writer=None, status="승인대기", record=()):
    """코드 task T001과 그 흐름의 검증 task T002."""
    code_task(run_dir)
    lines_file(run_dir, "T001", *rows)
    if writer:
        with_writer(run_dir, "T001", writer)
    run_dir.task("T002", "검증", {"승인 기록": "\n".join(record)}, kind="flow-verify", block="검증", status=status, flow="a", **NEW)
    run_dir.result("T002", result())
    return run_dir.tasks()


OFF = "- 끄기 | a.test.ts:3 | +1/-0"
GONE = "- 삭제 | b.test.ts | 선언 2개"
RANGE = "- 범위 축소 | vitest.config.ts:1 | include"


def test_row_takes_reason_and_guard_from_the_writer(run_dir):
    tasks = flow(run_dir, OFF, writer="- 끄기 | a.test.ts | 외부 API 점검 중 | contract.test.ts:12")
    row = lib.test_change_rows(tasks["T001"], tasks)[0]
    assert (row["why"], row["guard"], row["place"]) == ("외부 API 점검 중", "contract.test.ts:12", "a.test.ts:3")


def test_row_without_a_writer_line_says_so_and_guard_is_none(run_dir):
    tasks = flow(run_dir, OFF)
    row = lib.test_change_rows(tasks["T001"], tasks)[0]
    assert (row["why"], row["guard"]) == ("적지 않음", "없음")


def test_writer_line_the_machine_missed_is_a_row(run_dir):
    tasks = flow(run_dir, "- 없음", writer="- 삭제 | c.test.ts | it.each 행 뺌 | 없음")
    assert [(r["change"], r["place"]) for r in lib.test_change_rows(tasks["T001"], tasks)] == [("삭제", "c.test.ts")]


def test_writer_none_line_is_not_a_row(run_dir):
    tasks = flow(run_dir, "- 없음", writer="- 없음")
    assert lib.test_change_rows(tasks["T001"], tasks) == []


def test_proxy_check_comes_from_the_judge(run_dir):
    tasks = flow(run_dir, "- 없음")
    path = run_dir.task_dir("T001") / "judge.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n## 판단 대조\n- 대리 확인: AC-3 | DOM 글자 | PNG의 내용\n", encoding="utf-8")
    tasks = run_dir.tasks()
    row = lib.test_change_rows(tasks["T001"], tasks)[0]
    assert (row["change"], row["place"]) == ("대리 확인", "AC-3") and "PNG의 내용" in row["basis"]


def test_key_does_not_change_when_the_line_number_moves(run_dir):
    tasks = flow(run_dir, OFF)
    before = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    lines_file(run_dir, "T001", OFF.replace(":3", ":9"))
    assert lib.test_change_rows(tasks["T001"], tasks)[0]["key"] == before


def record(key, answer="받아들임", text="그건 괜찮아"):
    return '- 2026-11-05 10:00:00 | {} | {}={} | 원문: "{}"'.format(lib.TEST_CHANGE_POINT, key, answer, text)


def test_answered_row_carries_the_quote(run_dir):
    tasks = flow(run_dir, OFF)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    tasks = flow(run_dir, OFF, record=[record(key, "되살림")])
    row = lib.test_change_rows(tasks["T001"], tasks)[0]
    assert (row["answer"], row["quote"]) == ("되살림", "그건 괜찮아")


def test_several_keys_in_one_answer(run_dir):
    tasks = flow(run_dir, OFF, GONE)
    keys = [r["key"] for r in lib.test_change_rows(tasks["T001"], tasks)]
    tasks = flow(run_dir, OFF, GONE, record=[record(",".join(keys))])
    assert [r["answer"] for r in lib.test_change_rows(tasks["T001"], tasks)] == ["받아들임", "받아들임"]


def test_later_answer_wins(run_dir):
    tasks = flow(run_dir, OFF)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    tasks = flow(run_dir, OFF, record=[record(key), record(key, "되살림", "다시 보니 아니야")])
    assert lib.test_change_rows(tasks["T001"], tasks)[0]["answer"] == "되살림"


def test_this_record_point_is_not_a_whole_answer(run_dir):
    # 시험 변화 답은 한 지점의 답이다. 전체 승인과 원문 있는 답으로 세지 않는다
    tasks = flow(run_dir, OFF, record=[record("sabc", "받아들임", "승인")])
    assert not lib.has_quoted_answer(tasks["T002"])
    assert not lib.prior_approval(tasks["T002"])


EXPECT = "- 기대값만 바꿈 | a.test.ts:2 | 1줄"


def test_expectation_only_with_an_answer_quotes_it_and_does_not_ask(run_dir):
    tasks = flow(run_dir, EXPECT)
    t = dict(tasks["T001"], origin="사용자 T009 2026-11-05 09:00:00")
    tasks["T001"] = t
    tasks["T009"] = {"id": "T009", "_sections": {"승인 기록": '- 2026-11-05 09:00:00 | 답 | 고침 | 원문: "기대값을 2로"'}}
    row = lib.test_change_rows(t, tasks)[0]
    assert (row["answer"], row["quote"]) == ("앞선 답", "기대값을 2로")


def test_expectation_only_without_an_answer_is_an_alarm(run_dir):
    tasks = flow(run_dir, EXPECT)
    row = lib.test_change_rows(tasks["T001"], tasks)[0]
    assert row["answer"] == "" and row["ask"]
    assert "경보" in "\n".join(screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)[1])


def test_new_golden_or_count_row_does_not_ask(run_dir):
    tasks = flow(run_dir, "- 기대값 변경 | 전체 | 3줄")
    assert not lib.test_change_rows(tasks["T001"], tasks)[0]["ask"]


# ---------------------------------------------------------------- 위임 중 끄기와 삭제의 가드

def test_removals_only(run_dir):
    tasks = flow(run_dir, OFF, GONE, RANGE)
    found = lib.unanswered_test_removals(tasks["T002"])
    assert len(found) == 2 and "끄기" in found[0] and "삭제" in found[1] and "범위" not in "".join(found)


def test_answered_removal_is_not_listed(run_dir):
    tasks = flow(run_dir, OFF, GONE)
    keys = [r["key"] for r in lib.test_change_rows(tasks["T001"], tasks)]
    run_dir_tasks = flow(run_dir, OFF, GONE, record=[record(keys[0], "되살림")])
    found = lib.unanswered_test_removals(run_dir_tasks["T002"])
    assert len(found) == 1 and "삭제" in found[0]


def test_code_task_itself_lists_only_its_own(run_dir):
    tasks = flow(run_dir, OFF)
    assert len(lib.unanswered_test_removals(tasks["T001"])) == 1


def test_other_flow_is_not_counted(run_dir):
    tasks = flow(run_dir, OFF)
    run_dir.task("T003", "검증", kind="flow-verify", block="검증", status="승인대기", flow="b", **NEW)
    assert lib.unanswered_test_removals(run_dir.tasks()["T003"]) == []


def test_old_tasks_have_no_lines(run_dir):
    code_task(run_dir, meta=OLD)
    lines_file(run_dir, "T001", OFF)
    run_dir.task("T002", "검증", kind="flow-verify", block="검증", status="승인대기", flow="a", **OLD)
    tasks = run_dir.tasks()
    assert lib.test_change_rows(tasks["T001"], tasks) == [] and lib.unanswered_test_removals(tasks["T002"]) == []


def closes(run_dir, tid="T002", reply="승인|승인|좋아"):
    return run_script("task_set", run_dir.path, tid, "--status", "완료", "--record", reply)


def judged_verify(run_dir):
    judged(run_dir, "T002", run=True)


def test_flow_verify_cannot_close_with_an_unanswered_removal(run_dir):
    flow(run_dir, OFF)
    judged_verify(run_dir)
    out = closes(run_dir)
    assert out.returncode != 0 and "시험 끄기·삭제" in out.output and "끄기" in out.output
    assert run_dir.tasks()["T002"]["status"] == "승인대기"


def test_flow_verify_closes_after_the_answer_is_recorded(run_dir):
    tasks = flow(run_dir, OFF)
    judged_verify(run_dir)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    answered = run_script("task_set", run_dir.path, "T002", "--record", "{}|{}=받아들임|괜찮아".format(lib.TEST_CHANGE_POINT, key))
    assert answered.returncode == 0, answered.output
    assert lib.unanswered_test_removals(run_dir.tasks()["T002"]) == []
    out = closes(run_dir)
    assert out.returncode == 0, out.output


def test_other_changes_do_not_stop_the_flow_verify(run_dir):
    # 위임 중에도 일반 변화로는 멈추지 않는다. 흐름 리뷰와 마무리 리뷰에 남는다
    flow(run_dir, RANGE)
    judged_verify(run_dir)
    out = closes(run_dir)
    assert out.returncode == 0, out.output


# ---------------------------------------------------------------- 화면에 낼 줄, 마무리 리뷰

def test_screen_lines_have_the_four_cells_and_two_answers(run_dir):
    tasks = flow(run_dir, OFF, writer="- 끄기 | a.test.ts | 외부 점검 | 없음")
    count, lines = screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)
    text = "\n".join(lines)
    assert count == 1
    assert all(word in text for word in ("끄기", "a.test.ts:3", "이유: 외부 점검", "대신 지키는 것: 없음", "받아들임 / 되살림"))
    assert "추천" not in text


def test_screen_shows_answered_row_with_the_quote_and_does_not_ask(run_dir):
    tasks = flow(run_dir, OFF)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    tasks = flow(run_dir, OFF, record=[record(key)])
    count, lines = screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)
    assert count == 0 and '답: 받아들임 "그건 괜찮아"' in "\n".join(lines)


def test_screen_block_is_printed_on_the_flow_verify(run_dir):
    flow(run_dir, OFF)
    judged_verify(run_dir)
    out = run_script("screen", run_dir.path, "T002").stdout
    assert "■ 시험 변화 (답할 것 1)" in out


def test_screen_block_does_not_touch_the_answer_numbers(run_dir):
    flow(run_dir, OFF)
    judged_verify(run_dir)
    out = run_script("screen", run_dir.path, "T002").stdout
    assert screen.shown_items(out) == {}


def test_code_task_screen_says_the_flow_review_will_ask(run_dir):
    flow(run_dir, OFF)
    out = run_script("screen", run_dir.path, "T001").stdout
    assert "■ 시험 변화" in out and "흐름 리뷰에서 묻습니다" in out


def test_screen_has_no_block_without_lines(run_dir):
    flow(run_dir, "- 없음")
    judged_verify(run_dir)
    assert "■ 시험 변화" not in run_script("screen", run_dir.path, "T002").stdout


def test_screen_says_when_machine_check_did_not_run(run_dir):
    tasks = flow(run_dir, "- 없음")
    (run_dir.task_dir("T001") / lib.TEST_CHANGES).unlink()
    count, lines = screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)
    assert count == 1 and any("재지 못함" in line for line in lines)


def test_table_check_and_unfound_mutation_lines_are_shown(run_dir):
    code_task(run_dir, cells={"unverified": "- 변이를 찾지 못한 단언: a.test.ts:9"})
    tasks = flow_after(run_dir)
    path = run_dir.task_dir("T001") / "judge.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n## 판단 대조\n- 시험 표 대조: 표대로 3 | 낮은 계층으로 옮김 1 | 표에 없던 시험 2\n"
                    "- 기대값 근거 어긋남: 조회 AC | 정본 글자 | 제품 상수 a.test.ts:4\n", encoding="utf-8")
    text = "\n".join(screen.test_change_lines(str(run_dir.path), tasks["T002"], run_dir.tasks())[1])
    assert "표대로 3" in text and "기대값 근거 어긋남: 조회 AC" in text and "a.test.ts:9" in text


def flow_after(run_dir):
    lines_file(run_dir, "T001", "- 없음")
    run_dir.task("T002", "검증", kind="flow-verify", block="검증", status="승인대기", flow="a", **NEW)
    run_dir.result("T002", result())
    return run_dir.tasks()


def test_wrap_up_gets_unanswered_and_accepted_without_a_guard(run_dir):
    tasks = flow(run_dir, OFF, RANGE, GONE, writer="- 삭제 | b.test.ts | 옮김 | c.test.ts:1")
    rows = lib.test_change_rows(tasks["T001"], tasks)
    keys = {r["change"]: r["key"] for r in rows}
    answers = [record(",".join((keys["끄기"], keys["삭제"])))]
    tasks = flow(run_dir, OFF, RANGE, GONE, writer="- 삭제 | b.test.ts | 옮김 | c.test.ts:1", record=answers)
    found = "\n".join(lib.wrap_up_test_lines(tasks))
    assert "끄기" in found and "범위 축소" in found   # 대신 지키는 것 없이 받아들임, 답 없이 남은 일반 변화
    assert "삭제" not in found   # 대신 지키는 것이 있는 받아들임은 올리지 않는다


# ---------------------------------------------------------------- 기준선 추가

def set_baseline(run_dir, body):
    write(run_dir.path / "recon.md", "# 정찰\n\n## 기준선\n{}\n".format(body))


def test_baseline_added_after_the_first_check_is_a_row(run_dir):
    set_baseline(run_dir, "- a 실패")
    lib.note_baseline(str(run_dir.path))
    set_baseline(run_dir, "- a 실패\n- b 실패")
    tasks = flow(run_dir, "- 없음")
    rows = lib.flow_test_rows(tasks["T002"], tasks)
    assert [(r["change"], r["place"], r["basis"]) for r in rows] == [("기준선 추가", "recon.md 「기준선」", "- b 실패")]


def test_note_baseline_keeps_the_first_snapshot(run_dir):
    set_baseline(run_dir, "- a 실패")
    lib.note_baseline(str(run_dir.path))
    set_baseline(run_dir, "- a 실패\n- b 실패")
    lib.note_baseline(str(run_dir.path))
    assert lib.baseline_additions(str(run_dir.path)) == ["- b 실패"]


def test_no_snapshot_means_no_addition(run_dir):
    set_baseline(run_dir, "- a 실패")
    assert lib.baseline_additions(str(run_dir.path)) == []


# ---------------------------------------------------------------- 프로젝트 설정과 문서

def test_settings_read_three_lists_and_none(run_dir):
    write(run_dir.path.parent / lib.PROJECT_SETTINGS, "## 시험 변화 경로\n- 시험을 돌리는 곳: deploy/**, ci/run.sh\n- 정답 경로: golden/**\n- 시험 도우미 경로: 없음\n")
    got = lib.test_change_settings(str(run_dir.path))
    assert got == {"run": ["deploy/**", "ci/run.sh"], "golden": ["golden/**"], "helper": []}


def test_settings_without_a_file_are_empty(run_dir):
    assert lib.test_change_settings(str(run_dir.path)) == {"run": [], "golden": [], "helper": []}


def doc(rel):
    return (ROOT / "references" / rel).read_text(encoding="utf-8")


def test_docs_name_the_cells_the_scripts_read():
    rules, judge = doc("practices/test-rules.md"), doc("formats/judge-file.md")
    assert "- {변화} | {파일} | {이유} | {대신 지키는 것}" in rules
    settings_doc = doc("formats/run-files.md")
    assert "`## 시험 변화 경로`" in settings_doc
    assert all(label in settings_doc for label in lib.TEST_SETTING_LABELS.values())
    for cell in ("대리 확인: {AC} | 실제로 본 것 | 못 본 것", "시험 표 대조:", "기대값 근거 어긋남:"):
        assert cell in rules
    assert "대리 확인:" in judge and "test-rules" in judge


def test_docs_list_every_change_name():
    rules = doc("practices/test-rules.md")
    assert not [name for name in lib.TEST_CHANGE_NAMES if "`{}`".format(name) not in rules]


def test_design_doc_has_the_table_and_the_closed_values():
    text = doc("kinds/design/screen.md")
    assert "| 인수 기준 묶음 | 계층 | 돌리는 곳 | 기대값 근거 | 못 보는 것 |" in text
    for value in ("로컬", "공용 dev", "배포 뒤", "`정본 글자`", "`제품 상수`", "`정답 파일`", "`시험 시점 값`"):
        assert value in text
    assert re.search(r"시험 아님.*사람 확인.*낮은 계층으로 닫음.*전체 검증으로 넘김.*계층의 합", text)


def test_test_table_has_one_form_and_one_section_name():
    # 표의 꼴은 경우 파일 하나에만 있고, 정본의 절 이름은 「시험 표」다. 옛 정본을 대조하는 판정자는 「테스트 전략」도 받는다
    row = "| 인수 기준 묶음 | 계층 |"
    holders = [p.relative_to(ROOT).as_posix() for p in (ROOT / "references").rglob("*.md") if row in p.read_text(encoding="utf-8")]
    assert holders == ["references/kinds/design/screen.md"]
    assert "`## 시험 표`" in doc("kinds/design/screen.md") and "테스트 전략" not in doc("kinds/design.md")
    assert "「시험 표」" in doc("kinds/design.md")
    rules = doc("practices/test-rules.md")
    assert "`## 시험 표`" in rules and "「테스트 전략」" in rules
    # 절 이름을 글자로 읽는 스크립트는 한 장뿐이고 옛 이름에 기대지 않는다
    readers = [p.name for p in (ROOT / "scripts").glob("*.py") if "테스트 전략" in p.read_text(encoding="utf-8")]
    assert readers == [] and "시험 표" in visual.OPEN_SECTIONS


# ================================================================ 리뷰 지적의 장면

def flow_md(run_dir, repo):
    write(run_dir.path / "flows/a/flow.md", "---\ndir: {}\n---\n".format(str(repo).replace("\\", "/")))


def base_commit(repo, files):
    for path, text in dict(files, **{"keep.txt": "x\n"}).items():
        write(repo / path, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")


def started(run_dir, repo, tid="T001", kind="implementation", status="진행", **meta):
    flow_md(run_dir, repo)
    run_dir.task(tid, "구현", {"건드릴 파일": "- **", "판정 기준": "1. 기준"}, kind=kind, block="구현", status=status, flow="a", **dict(NEW, **meta))
    run_dir.result(tid, result())


def verifying(run_dir, status="승인대기", record=()):
    run_dir.task("T002", "검증", {"승인 기록": "\n".join(record)}, kind="flow-verify", block="검증", status=status, flow="a", **NEW)
    run_dir.result("T002", result())
    judged(run_dir, "T002", run=True)


def to_check(run_dir, tid="T001", *more):
    return run_script("task_set", run_dir.path, tid, "--status", "자체검증", *more)


def machine_file(run_dir, tid="T001"):
    return run_dir.task_dir(tid) / lib.TEST_CHANGES


SKIPPED = 'it.skip("x", () => {});\n'


# ---------------------------------------------------------------- 끝에서 끝까지

def test_end_to_end_from_the_transition_to_the_guard(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    write(repo / SPEC, SKIPPED)
    started(run_dir, repo)
    assert to_check(run_dir).returncode == 0
    assert str(run_dir.tasks()["T001"]["machine_check"]) == "3"
    verifying(run_dir)
    tasks = run_dir.tasks()
    found = lib.unanswered_test_removals(tasks["T002"])
    assert len(found) == 1 and "끄기" in found[0]
    refused = closes(run_dir)
    key = lib.flow_test_rows(tasks["T002"], tasks)[0]["key"]
    assert refused.returncode != 0 and "[{}]".format(key) in refused.output
    assert run_script("task_set", run_dir.path, "T002", "--record", "시험 변화|{}=받아들임|괜찮아".format(key)).returncode == 0
    out = closes(run_dir)
    assert out.returncode == 0, out.output


@pytest.mark.parametrize("kind", ["fix", "be-implementation", "fe-implementation"])
def test_lines_of_every_code_kind_reach_the_flow_verify(run_dir, repo, kind):
    base_commit(repo, {SPEC: PASS})
    write(repo / SPEC, SKIPPED)
    started(run_dir, repo, kind=kind)
    assert to_check(run_dir).returncode == 0, kind
    verifying(run_dir)
    assert len(lib.unanswered_test_removals(run_dir.tasks()["T002"])) == 1


# ---------------------------------------------------------------- 차단 1: 재지 못한 task

def test_override_value_still_measures(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    write(repo / SPEC, SKIPPED)
    started(run_dir, repo)
    assert to_check(run_dir, "T001", "machine_check=0").returncode == 0
    t = run_dir.tasks()["T001"]
    assert str(t["machine_check"]) == "0" and "- 끄기 |" in machine_file(run_dir).read_text(encoding="utf-8")
    verifying(run_dir)
    assert len(lib.unanswered_test_removals(run_dir.tasks()["T002"])) == 1
    assert closes(run_dir).returncode != 0


def test_old_task_with_override_does_not_measure(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    write(repo / SPEC, SKIPPED)
    flow_md(run_dir, repo)
    run_dir.task("T001", "구현", {"건드릴 파일": "- **"}, kind="implementation", block="구현", status="진행", flow="a", **OLD)
    run_dir.result("T001", result())
    assert to_check(run_dir, "T001", "machine_check=0").returncode == 0
    assert not machine_file(run_dir).exists()


def test_a_retry_without_a_folder_does_not_keep_the_old_file(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    write(repo / "src/a.ts", "1\n")
    started(run_dir, repo)
    assert to_check(run_dir).returncode == 0
    assert machine_file(run_dir).read_text(encoding="utf-8").strip().endswith("\n- 없음")
    judged(run_dir, "T001", run=True)
    assert run_script("task_set", run_dir.path, "T001", "--status", "진행", "--archive-judge").returncode == 0
    write(repo / SPEC, SKIPPED)
    (run_dir.path / "flows/a/flow.md").unlink()
    run_script("task_set", run_dir.path, "T001", "--status", "자체검증")
    assert not lib.test_changes_measured(run_dir.tasks()["T001"])
    verifying(run_dir)
    found = lib.unanswered_test_removals(run_dir.tasks()["T002"])
    assert len(found) == 1 and lib.TEST_UNMEASURED in found[0]


def test_a_retry_with_override_replaces_the_old_file(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    write(repo / "src/a.ts", "1\n")
    started(run_dir, repo)
    to_check(run_dir)
    judged(run_dir, "T001", run=True)
    run_script("task_set", run_dir.path, "T001", "--status", "진행", "--archive-judge")
    write(repo / SPEC, SKIPPED)
    assert to_check(run_dir, "T001", "machine_check=0").returncode == 0
    assert "- 끄기 |" in machine_file(run_dir).read_text(encoding="utf-8")


def test_git_failure_writes_no_file_and_flags(run_dir, tmp_path):
    plain = tmp_path / "plain"
    write(plain / SPEC, SKIPPED)
    run_dir.task("T001", "구현", {"건드릴 파일": "- **"}, kind="implementation", block="구현", status="진행", flow="a", **NEW)
    out = run_script("machine_check", plain, run_dir.task_dir("T001") / "task.md")
    assert out.returncode == 3 and "재지 못함" in out.stdout
    assert not machine_file(run_dir).exists()


def unmeasured(run_dir, status="자체검증", **more):
    code_task(run_dir, **more)
    tasks = run_dir.tasks()
    t = dict(tasks["T001"], status=status)
    tasks["T001"] = t
    return lib.test_change_rows(t, tasks)


@pytest.mark.parametrize("status", ["자체검증", "승인대기", "완료"])
def test_unmeasured_row_after_the_measurement(run_dir, status):
    assert [r["change"] for r in unmeasured(run_dir, status)] == [lib.TEST_UNMEASURED]


@pytest.mark.parametrize("status", ["대기", "진행", "백로그"])
def test_no_unmeasured_row_before_the_measurement(run_dir, status):
    assert unmeasured(run_dir, status) == []


def test_no_unmeasured_row_for_no_change(run_dir):
    assert unmeasured(run_dir, no_change="true") == []


def test_unmeasured_row_stops_until_the_code_check_answer(run_dir):
    code_task(run_dir)
    verifying(run_dir)
    tasks = run_dir.tasks()
    row = lib.flow_test_rows(tasks["T002"], tasks)[0]
    assert row["change"] == lib.TEST_UNMEASURED and row["key"]
    assert closes(run_dir).returncode != 0
    verifying(run_dir, record=[record(row["key"], "되살림")])
    assert closes(run_dir).returncode != 0   # 되살림은 다시 재라는 뜻이고 줄을 풀지 않는다
    verifying(run_dir, record=[record(row["key"])])
    assert closes(run_dir).returncode != 0   # 시험 변화의 답도 풀지 않는다. 먼저 다시 재고 코드 확인의 답을 받는다
    assert run_script("screen", run_dir.path, "T002", "--places", "--remeasure").returncode == 0
    assert run_script("task_set", run_dir.path, "T002", "--record", "코드 확인 재지 못함 T001|합쳐도 됨|그건 괜찮아").returncode == 0
    assert closes(run_dir).returncode == 0
    assert "재지 못함" in "\n".join(lib.wrap_up_test_lines(run_dir.tasks()))


def test_unmeasured_row_says_what_the_answer_means(run_dir):
    code_task(run_dir)
    verifying(run_dir)
    tasks = run_dir.tasks()
    text = "\n".join(screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)[1])
    assert "확인 없이 합쳐도 된다" in text


# ---------------------------------------------------------------- 차단 2: 커밋 뒤 재측정

def test_after_commit_measurement_keeps_the_lines(run_dir, repo):
    base_commit(repo, {SPEC: PASS, "tests/b.test.ts": PASS})
    write(repo / SPEC, SKIPPED)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "task")
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    started(run_dir, repo, status="승인대기", commit=sha)
    judged(run_dir, "T001", run=True)
    again = run_script("task_set", run_dir.path, "T001", "--status", "진행", "--record", "승인|다시|다시 봐 주세요")
    assert again.returncode == 0, again.output
    assert to_check(run_dir).returncode == 0
    assert "- 끄기 |" in machine_file(run_dir).read_text(encoding="utf-8")


def test_unknown_commit_is_unmeasured_rather_than_empty(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    started(run_dir, repo, commit="abcdef1")
    out = run_script("machine_check", repo, run_dir.task_dir("T001") / "task.md")
    assert out.returncode == 3 and not machine_file(run_dir).exists()


def test_without_commit_the_base_is_head(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    write(repo / SPEC, SKIPPED)
    started(run_dir, repo)
    run_script("machine_check", repo, run_dir.task_dir("T001") / "task.md")
    assert "- 끄기 |" in machine_file(run_dir).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 차단 3: 수집 밖으로 옮김

@pytest.mark.parametrize("new", ["tests/a.ts", "tests/a.test.ts.off", "tests/disabled/a.txt", "archive/a.ts"])
def test_moving_a_test_out_of_collection_is_deleted(repo, new):
    assert "삭제" in kinds_of(changes(repo, {"tests/a.test.ts": PASS}, {new: PASS}, deletes=["tests/a.test.ts"]))


def test_git_mv_out_of_collection_is_deleted(repo):
    base_commit(repo, {"tests/a.test.ts": PASS})
    (repo / "archive").mkdir()
    git(repo, "mv", "tests/a.test.ts", "archive/a.ts")
    assert "삭제" in kinds_of(machine_check.find_test_changes(str(repo), lib.test_change_settings(str(repo))))


@pytest.mark.parametrize("old, new", [
    ("tests/a.test.ts", "src/a.test.ts"), ("test_a.py", "tests/test_b.py"), ("a_test.go", "pkg/a_test.go"), ("tests/a.ts", "tests/sub/b.ts"),
])
def test_a_rename_that_stays_collected_is_not_deleted(repo, old, new):
    assert "삭제" not in kinds_of(changes(repo, {old: PASS}, {new: PASS}, deletes=[old]))


@pytest.mark.parametrize("new", ["tests/b.txt", "src/b.ts"])
def test_a_nameless_test_needs_the_folder_and_the_extension(repo, new):
    assert "삭제" in kinds_of(changes(repo, {"tests/a.ts": PASS}, {new: PASS}, deletes=["tests/a.ts"]))


# ---------------------------------------------------------------- 중요: 도우미 폴더의 시험

HELPER_FOLDER_TESTS = ["tests/utils/date.test.ts", "__tests__/helpers/x.test.ts", "tests/unit/support/y.spec.ts"]


@pytest.mark.parametrize("path", HELPER_FOLDER_TESTS)
def test_a_test_in_a_helper_folder_is_a_test(repo, path):
    rows = kinds_of(changes(repo, {path: PASS}, {path: PASS.replace("it(", "it.skip(")}))
    assert "끄기" in rows and "시험 도우미" not in rows


@pytest.mark.parametrize("path", HELPER_FOLDER_TESTS)
def test_deleting_a_test_in_a_helper_folder_is_deleted(repo, path):
    assert "삭제" in kinds_of(changes(repo, {path: PASS}, deletes=[path]))


# ---------------------------------------------------------------- 중요: 단언과 선언이 빠지는 길

def test_a_commented_out_assertion_is_lost(repo):
    base = {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n  expect(b).toBe(2);\n});\n', "src/a.ts": "1\n"}
    rows = changes(repo, base, {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n  // expect(b).toBe(2);\n});\n', "src/a.ts": "2\n"})
    assert "단언 약화" in kinds_of(rows)


def test_commented_marks_are_not_off(repo):
    assert "끄기" not in kinds_of(changes(repo, {}, {SPEC: '// it.skip("x", () => {});\n'}))


def test_a_commented_out_junit_test_is_deleted(repo):
    path = "src/test/FooTest.java"
    assert "삭제" in kinds_of(changes(repo, {path: "class A {\n  @Test\n  void a() {}\n}\n"}, {path: "class A {\n  // @Test\n  void a() {}\n}\n"}))


def test_an_unrelated_helper_assertion_does_not_cover_a_loss(repo):
    base = {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n  expect(b).toBe(2);\n});\n'}
    edits = {SPEC: 'it("x", () => {\n  expect(a).toBe(1);\n});\n', "tests/helpers/n.ts": "export const z = () => {\n  expect(1).toBe(1);\n};\n"}
    assert "단언 약화" in kinds_of(changes(repo, base, edits))


def test_a_helper_assertion_covers_one_loss_only(repo):
    # 도우미로 옮긴 양을 넘는 약화는 남는다
    body = 'it("x", () => {\n  expect(a).toBe(1);\n  keep();\n});\n'
    edits = {"a.test.ts": 'it("x", () => {\n  keep();\n});\n', "b.test.ts": 'it("x", () => {\n  keep();\n});\n',
             "tests/helpers/check.ts": "export function check() {\n  expect(a).toBe(1);\n}\n"}
    rows = changes(repo, {"a.test.ts": body, "b.test.ts": body}, edits)
    assert [r["place"].split(":")[0] for r in rows if r["change"] == "단언 약화"] == ["b.test.ts"]


# ---------------------------------------------------------------- 중요: 실행기 설정의 이름

@pytest.mark.parametrize("path, before, after, change", [
    ("vitest.worker.config.ts", "testTimeout: 5000,", "testTimeout: 15000,", "제한 시간과 허용 범위"),
    ("vite.config.ts", "exclude: [],", "exclude: ['a'],", "범위 축소"),
    ("playwright.dev.config.ts", "retries: 0,", "retries: 3,", "재시도"),
    ("vitest.workspace.ts", "include: [],", "include: ['a'],", "범위 축소"),
])
def test_runner_file_names(repo, path, before, after, change):
    assert change in kinds_of(changes(repo, {path: before + "\n"}, {path: after + "\n"}))


@pytest.mark.parametrize("line", ["onUnhandledError: unhandledFilter.filter,", "onConsoleLog: () => false,"])
def test_failure_filter_callbacks(repo, line):
    path = "vitest.worker.config.ts"
    assert "실패 거름" in kinds_of(changes(repo, {path: "export default {};\n"}, {path: line + "\n"}))


def test_filter_in_a_helper_path_from_the_setting(repo):
    wanted = dict(lib.test_change_settings(str(repo)), helper=["tools/vitest-*"])
    rows = changes(repo, {"tools/vitest-filter.ts": "a\n"}, {"tools/vitest-filter.ts": "onConsoleLog: f,\n"}, settings=wanted)
    assert {"실패 거름", "시험 도우미"} <= kinds_of(rows)


# ---------------------------------------------------------------- 중요: 새 정의는 값 변경이 아니다

def test_a_new_limit_in_a_test_file_is_not_a_change(repo):
    rows = changes(repo, {SPEC: PASS}, {SPEC: PASS + 'it("y", () => {}, { timeout: 5 });\n'})
    assert "제한 시간과 허용 범위" not in kinds_of(rows)


def test_a_removed_limit_in_a_test_file_is_not_a_change(repo):
    assert "제한 시간과 허용 범위" not in kinds_of(changes(repo, {SPEC: "timeout: 5,\n"}, {SPEC: "const a = 1;\n"}))


def test_a_limit_with_both_values_is_a_change(repo):
    row = next(r for r in changes(repo, {SPEC: "timeout: 5,\n"}, {SPEC: "timeout: 50,\n"}) if r["change"] == "제한 시간과 허용 범위")
    assert row["basis"] == "timeout: 5 → 50"


def test_a_new_limit_in_a_runner_file_is_a_change(repo):
    path = "vitest.config.ts"
    assert "제한 시간과 허용 범위" in kinds_of(changes(repo, {path: "export default {};\n"}, {path: "testTimeout: 5000,\n"}))


def test_a_new_retry_is_a_change_in_a_test_file(repo):
    assert "재시도" in kinds_of(changes(repo, {SPEC: PASS}, {SPEC: PASS + 'it("y", () => {}, { retry: 1 });\n'}))


# ---------------------------------------------------------------- 중요: 기대값만 바꿈

@pytest.mark.parametrize("before, after", [
    ('const url = "a";', 'const url = "b";'),
    ('test("a", async () => {});', "test.beforeEach(async () => {});"),
    ("  version: 3,", "  version: 4,"),
    ("  expect(a).toBe(1);", "  // expect(a).toBe(2);"),
])
def test_only_assertion_pairs_are_expectation_only(repo, before, after):
    assert "기대값만 바꿈" not in kinds_of(changes(repo, {SPEC: before + "\n"}, {SPEC: after + "\n"}))


def test_a_snapshot_change_is_not_expectation_only(repo):
    rows = kinds_of(changes(repo, {"__snapshots__/a.snap": "1\n"}, {"__snapshots__/a.snap": "2\n"}))
    assert "정답 파일" in rows and "기대값만 바꿈" not in rows


# ---------------------------------------------------------------- 중요: 되살림

def test_restored_row_stays_for_the_wrap_up_until_the_task_is_done(run_dir):
    tasks = flow(run_dir, OFF)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    tasks = flow(run_dir, OFF, record=[record(key, "되살림")])
    assert lib.unanswered_test_removals(tasks["T002"]) == []
    assert "끄기" in "\n".join(lib.wrap_up_test_lines(tasks))
    run_dir.task("T003", "되살림", kind="fix", block="구현", status="진행", flow="a",
                 origin="사용자 T002 2026-11-05 10:00:00 — 시험 변화 {}".format(key), **NEW)
    assert "끄기" in "\n".join(lib.wrap_up_test_lines(run_dir.tasks()))
    run_dir.task("T003", "되살림", kind="fix", block="구현", status="완료", flow="a", no_change="true",
                 origin="사용자 T002 2026-11-05 10:00:00 — 시험 변화 {}".format(key), **NEW)
    write(machine_file(run_dir, "T003"), "- 없음\n")
    assert "끄기" not in "\n".join(lib.wrap_up_test_lines(run_dir.tasks()))


# ---------------------------------------------------------------- 중요: 빈 원문, 지점

def test_an_answer_without_words_is_not_an_answer(run_dir):
    tasks = flow(run_dir, OFF)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    tasks = flow(run_dir, OFF, record=[record(key, text="")])
    assert len(lib.unanswered_test_removals(tasks["T002"])) == 1


@pytest.mark.parametrize("raw", ["시험 변화|sabc=받아들임", "시험 변화|sabc=받아들임|", "시험 변화|sabc=받아들임|  "])
def test_task_set_refuses_an_answer_without_words(run_dir, raw):
    flow(run_dir, OFF)
    out = run_script("task_set", run_dir.path, "T002", "--record", raw)
    assert out.returncode == 3 and "원문" in out.output
    assert run_dir.tasks()["T002"]["_sections"].get("승인 기록", "").strip() == ""


def test_this_point_cannot_close_the_flow_review(run_dir):
    tasks = flow(run_dir, RANGE)
    judged_verify(run_dir)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    out = run_script("task_set", run_dir.path, "T002", "--status", "완료", "--record", "시험 변화|{}=받아들임|좋아".format(key))
    assert out.returncode != 0 and "상태를 옮기지 않는다" in out.output
    assert run_dir.tasks()["T002"]["status"] == "승인대기"
    assert lib.TEST_CHANGE_POINT in lib.PARTIAL_POINTS


def test_an_answer_at_another_point_does_not_count(run_dir):
    tasks = flow(run_dir, OFF)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    other = '- 2026-11-05 10:00:00 | 답 | {}=받아들임 | 원문: "좋아"'.format(key)
    tasks = flow(run_dir, OFF, record=[other])
    assert len(lib.unanswered_test_removals(tasks["T002"])) == 1


# ---------------------------------------------------------------- 중요: 기준선 키

def test_a_later_baseline_line_does_not_inherit_the_answer(run_dir):
    set_baseline(run_dir, "- a")
    lib.note_baseline(str(run_dir.path))
    set_baseline(run_dir, "- a\n- b")
    tasks = flow(run_dir, "- 없음")
    key = lib.flow_test_rows(tasks["T002"], tasks)[0]["key"]
    tasks = flow(run_dir, "- 없음", record=[record(key)])
    set_baseline(run_dir, "- a\n- b\n- 나중에 넣은 실패")
    rows = lib.flow_test_rows(tasks["T002"], tasks)
    assert [r["answer"] for r in rows] == ["받아들임", ""]
    assert screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)[0] == 1


# ---------------------------------------------------------------- 권장

def test_key_is_on_the_screen_line_and_the_record_shape_is_printed(run_dir):
    tasks = flow(run_dir, OFF)
    key = lib.test_change_rows(tasks["T001"], tasks)[0]["key"]
    text = "\n".join(screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)[1])
    assert "- [{}] 끄기".format(key) in text
    assert '--record "시험 변화|{키},{키}=받아들임 {키}=되살림|{원문}"' in text


def test_no_record_shape_when_nothing_is_asked(run_dir):
    tasks = flow(run_dir, "- 기대값 변경 | 전체 | 3줄")
    assert "--record" not in "\n".join(screen.test_change_lines(str(run_dir.path), tasks["T002"], tasks)[1])


@pytest.mark.parametrize("line", [
    "fit('a', f)", "fdescribe('a', f)", "xtest('a', f)", "it.fails('a', f)", "test.failing('a', f)", "test.fail()", "t.Skipf('x')", "t.SkipNow()",
    "@unittest.skipIf(x)", "@unittest.skip('x')", "self.skipTest('x')", "pytest.importorskip('a')", "@pytest.mark.xfail",
])
def test_more_stack_marks_are_off(repo, line):
    assert "끄기" in kinds_of(changes(repo, {}, {SPEC: line + "\n"}))


@pytest.mark.parametrize("line", ["test.beforeEach(async () => {});", "test.use({});", "test.describe('a', () => {});", "test.step('a', f);"])
def test_playwright_hooks_are_not_declarations(repo, line):
    # 훅을 지워도 삭제가 아니고, 시험을 훅으로 바꾸면 삭제다
    keep = "test('b', async () => {});\n"
    assert "삭제" not in kinds_of(changes(repo, {SPEC: line + "\n" + keep}, {SPEC: keep}))


def test_test_to_hook_is_deleted(repo):
    keep = "test('b', async () => {});\n"
    edits = {SPEC: "test.beforeEach(async () => {});\n" + keep}
    assert "삭제" in kinds_of(changes(repo, {SPEC: "test('a', async () => {});\n" + keep}, edits))


@pytest.mark.parametrize("before, after", [('it("a", f);', 'xit("a", f);'), ('it("a", f);', 'fit("a", f);'), ('test("a", f);', 'xtest("a", f);')])
def test_turning_off_is_off_not_deleted(repo, before, after):
    rows = kinds_of(changes(repo, {SPEC: before + "\n"}, {SPEC: after + "\n"}))
    assert "끄기" in rows and "삭제" not in rows


def test_playwright_snapshot_folder_is_golden(repo):
    path = "tests/e2e/a.spec.ts-snapshots/x.png"
    rows = kinds_of(changes(repo, {path: "aa\n"}, {path: "bb\n"}))
    assert "정답 파일" in rows and "기대값만 바꿈" not in rows


def test_backlog_to_done_does_not_pass_the_guard(run_dir):
    flow(run_dir, OFF, status="백로그")
    out = run_script("task_set", run_dir.path, "T002", "--status", "완료", "--reason", "다른 실행에서 처리")
    assert out.returncode != 0 and "시험 끄기·삭제" in out.output


def test_backlog_to_done_passes_without_lines(run_dir):
    flow(run_dir, "- 없음", status="백로그")
    out = run_script("task_set", run_dir.path, "T002", "--status", "완료", "--reason", "다른 실행에서 처리")
    assert out.returncode == 0, out.output


# ---------------------------------------------------------------- 살아남은 변이

def test_guard_on_the_notify_transition_after_a_prior_approval(run_dir):
    approved = '- 2026-11-05 10:00:00 | 승인 | 승인 | 원문: "좋아"'
    flow(run_dir, OFF, status="자체검증", record=[approved])
    judged_verify(run_dir)
    out = run_script("task_set", run_dir.path, "T002", "--status", "완료", "--record", "알림|알림|")
    assert out.returncode != 0 and "시험 끄기·삭제" in out.output


def test_a_big_new_test_file_is_read_to_the_end(repo):
    # 크기 때문에 끄기를 놓치지 않는다
    body = "// 채움 줄입니다\n" * 120000 + SKIPPED
    assert len(body.encode("utf-8")) > 2 * 1024 * 1024
    assert "끄기" in kinds_of(changes(repo, {}, {SPEC: body}))


# ---------------------------------------------------------------- 문서와 정찰

def test_selfcheck_doc_says_the_override_still_measures():
    text = doc("main/selfcheck.md")
    assert "수동 override는 유지" not in text and "시험 변화" in text


def test_recon_doc_and_detect_script_name_the_setting():
    assert "## 시험 변화 경로" in doc("practices/project-recon.md")
    assert "시험 변화 경로 단서" in (ROOT / "scripts" / "detect-stack.sh").read_text(encoding="utf-8")


def test_detect_script_finds_the_candidates(tmp_path):
    write(tmp_path / "tests/golden/a.json", "1")
    write(tmp_path / "src/quote.golden.test.ts", "1")
    write(tmp_path / "tools/vitest-filter.ts", "1")
    write(tmp_path / "scripts/smoke.sh", "1")
    bash = shutil.which("bash")
    assert bash, "bash가 없음: Git Bash(또는 bash)를 PATH에 두고 다시 돌린다"
    out = subprocess.run([bash, str(ROOT / "scripts" / "detect-stack.sh"), str(tmp_path)], capture_output=True, text=True, encoding="utf-8").stdout
    clues = out[out.index("## 시험 변화 경로 단서"):out.index("## 경로 단서")]
    assert "- tests/golden/**" in clues and "- src/quote.golden.test.ts" in clues
    assert "- tools/vitest-filter.ts" in clues and "- scripts/smoke.sh" in clues


# ---------------------------------------------------------------- 재측정의 기준

def head_of(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def test_first_measurement_writes_the_base(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    started(run_dir, repo)
    to_check(run_dir)
    assert lib.test_change_base(run_dir.tasks()["T001"]) == head_of(repo)


def test_remeasure_without_a_commit_key_keeps_the_lines(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    write(repo / SPEC, SKIPPED)
    started(run_dir, repo)
    to_check(run_dir)
    judged(run_dir, "T001", run=True)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "task")
    assert run_script("task_set", run_dir.path, "T001", "--status", "진행", "--archive-judge").returncode == 0
    assert lib.test_change_base(run_dir.tasks()["T001"]), "되돌릴 때 기준이 남는다"
    assert to_check(run_dir).returncode == 0
    assert "- 끄기 |" in machine_file(run_dir).read_text(encoding="utf-8")


def test_a_recorded_base_that_is_gone_is_unmeasured(run_dir, repo):
    base_commit(repo, {SPEC: PASS})
    started(run_dir, repo)
    write(machine_file(run_dir), "기준: abcdef1234\n- 없음\n")
    out = run_script("machine_check", repo, run_dir.task_dir("T001") / "task.md")
    assert out.returncode == 3 and not lib.test_changes_measured(run_dir.tasks()["T001"])


def test_base_line_alone_is_not_measured(run_dir):
    tasks = flow(run_dir, "기준: abc1234")
    assert [r["change"] for r in lib.test_change_rows(tasks["T001"], tasks)] == [lib.TEST_UNMEASURED]


# ---------------------------------------------------------------- 곳과 함께

def code_check_point(run_dir, key="T001-abc"):
    return "{} {}|b1=문제 없음|좋아".format(lib.CODE_CHECK_ORIGIN, key)


def test_code_check_is_a_partial_point(run_dir):
    assert lib.CODE_CHECK_ORIGIN in lib.PARTIAL_POINTS


@pytest.mark.parametrize("point", ["시험 변화", "코드 확인 T001-abc"])
def test_a_partial_answer_is_not_a_whole_approval(run_dir, point):
    tasks = flow(run_dir, "- 없음", record=['- 2026-11-05 10:00:00 | {} | x | 원문: "승인"'.format(point)])
    assert not lib.has_quoted_answer(tasks["T002"]) and not lib.prior_approval(tasks["T002"])


def test_one_place_answer_does_not_close_the_flow_review(run_dir):
    flow(run_dir, "- 없음")
    judged_verify(run_dir)
    out = run_script("task_set", run_dir.path, "T002", "--status", "완료", "--record", code_check_point(run_dir))
    assert out.returncode != 0 and "상태를 옮기지 않는다" in out.output
    assert run_dir.tasks()["T002"]["status"] == "승인대기"

