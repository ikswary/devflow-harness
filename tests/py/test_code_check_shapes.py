"""1.2.0 A4 리뷰 반영: 코드 확인의 입력 꼴과 사람이 보는 내용(설계 11.1절, 6.12절 「보안」, 6.16절).

- 칸에 ` | `가 들어도 `지금 문제 있음`을 잃지 않는다.
- 지운 인증 코드는 카드에 보이고, 비밀값은 가린다.
- 위임으로 일반 곳을 남기는 것은 `L1`이 있을 때뿐이다. 코드 확인에서 온 수정은 재검증 없이 합친다.
"""
import pytest

import board
import devflow_lib as lib
import machine_check
import places
import screen
import visual
from conftest import run_script, write
from test_code_check import BODY, FV, code, commit, complete, git, judged, make_places, many, one_place, opinion, repo, verify, waiting  # noqa: F401
from test_review_contract import NEW, result

UNION = "- 코드 의견: {} | 값이 string | null로 나간다 | {} | null을 읽으면 깨진다 | 다른 곳은 빈 글로 바꾼다\n"
SECRET = 'const password = "hunter2-real-secret";\n'


def card(run_dir, n="1", *more):
    p = run_script("screen", run_dir.path, FV, "--card", str(n), *more)
    assert p.returncode == 0, p.output
    return p.stdout


def open_first(run_dir, plist=None):
    plist = plist or places.read(str(run_dir.path), FV)
    waiting(run_dir)
    assert run_script("task_set", run_dir.path, FV, "--card-open", plist[0]["key"]).returncode == 0
    return plist


# ---------------------------------------------------------------- ` | `가 든 의견


def test_union_in_an_opinion_keeps_the_problem_and_the_order(run_dir, repo):
    many(run_dir, repo, ["트랜잭션"] * 5 + ["구조"])
    path = run_dir.task_dir("T001") / "judge.md"
    path.write_text(path.read_text(encoding="utf-8").replace("## 판단 대조\n- 없음\n", "## 판단 대조\n" + UNION.format("src/f5.ts:3", places.PROBLEM)), encoding="utf-8")
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert got[0]["파일"] == ["src/f5.ts"] and got[0]["의견"] == places.PROBLEM


def test_union_on_a_file_with_no_judgment_still_makes_a_place(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", UNION.format("src/a.ts:3", places.PROBLEM), sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["파일"] for p in got] == [["src/a.ts"]] and got[0]["의견"] == places.PROBLEM
    assert "값이 string | null로 나간다" in got[0]["판단"][0]["text"]


def test_left_union_opinion_is_quoted_whole(run_dir, repo):
    line = UNION.format("src/a.ts:3", places.PROBLEM)
    code(run_dir, "T001", "- 도우미 [종류: 구조] [위치: src/a.ts:3]\n", line, sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo, values="| 위임 | L1~L3 |\n")
    make_places(run_dir)
    assert places.run_left(str(run_dir.path))["problems"] == [line[2:].rstrip("\n")]


@pytest.mark.parametrize("verdict", [places.PROBLEM, places.NO_PROBLEM])
def test_card_reads_every_cell_of_a_union_opinion(run_dir, repo, verdict):
    one_place(run_dir, repo, compare=UNION.format("src/a.ts:60", verdict))
    text = card(run_dir)
    assert "값이 string | null로 나간다" in text and "\n" + verdict + "\n" in text
    assert "깨지는 조건: null을 읽으면 깨진다" in text and "방식: 다른 곳은 빈 글로 바꾼다" in text


@pytest.mark.parametrize("cells,want", [
    (["a:1", "일", "지금 문제 있음", "조건", "방식"], ("일", "지금 문제 있음", "조건", "방식")),
    (["a:1", "x", "y", "지금 문제 없음", "조건", "방식"], ("x | y", "지금 문제 없음", "조건", "방식")),
    (["a:1", "일", "지금 문제 있음", "p", "q", "방식"], ("일", "지금 문제 있음", "p | q", "방식")),
    (["a:1", "일", "지금 문제 있음"], ("일", "지금 문제 있음", "", "")),
    (["a:1", "일", "지금 문제 있음", "조건"], ("일", "지금 문제 있음", "조건", "")),
    (["a:1", "일", "`지금 문제 있음`.", "조건", "방식"], ("일", "지금 문제 있음", "조건", "방식")),
    (["a:1", "일", "모름"], ("일 | 모름", "", "", "")),
    (["a:1"], ("", "", "", "")),
])
def test_opinion_cells(cells, want):
    got = places.opinion_cells(cells)
    assert (got["happened"], got["verdict"], got["breaks"], got["way"]) == want


def test_unreadable_verdict_is_no_opinion_but_shown(run_dir, repo):
    one_place(run_dir, repo, compare="- 코드 의견: src/a.ts:60 | 일어난 일 | 잘 모르겠음\n")
    assert places.read(str(run_dir.path), FV)[0]["의견"] == places.NO_OPINION
    assert "잘 모르겠음" in card(run_dir)


# ---------------------------------------------------------------- 지운 코드


def test_removed_auth_call_is_on_the_card(run_dir, repo):
    commit(repo, {"src/a.ts": "const v1 = 1;\nauthenticate(req);\nconst v3 = 3;\n"})
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": "const v1 = 1;\nconst v3 = 3;\n"}))
    verify(run_dir, repo)
    open_first(run_dir, make_places(run_dir))
    assert "src/a.ts:1 | authenticate | 지운 줄: authenticate(req);" in card(run_dir)


def test_removed_file_shows_the_code_before_the_commit(run_dir, repo):
    commit(repo, {"src/auth.ts": "function authenticate(req) {\n  return check(req);\n}\n"})
    (repo / "src" / "auth.ts").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "지움")
    code(run_dir, "T001", "- 없음\n", sha=git(repo, "rev-parse", "--short", "HEAD"))
    verify(run_dir, repo)
    open_first(run_dir, make_places(run_dir))
    text = card(run_dir)
    assert "(이 커밋에서 지움)" in text and "return check(req);" in text
    assert run_script("screen", run_dir.path, FV, "--answer", "1").returncode == 0


def test_added_line_is_not_called_removed(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": "authenticate(req);\n"}))
    verify(run_dir, repo)
    open_first(run_dir, make_places(run_dir))
    assert "지운 줄" not in card(run_dir)


def test_diff_rows_tell_removed_from_added():
    diff = "diff --git a/a.ts b/a.ts\n--- a/a.ts\n+++ b/a.ts\n@@ -2 +2 @@\n-old\n+new\n"
    assert machine_check.diff_rows(diff) == [("a.ts", 2, "old", True), ("a.ts", 2, "new", False)]


def test_removed_line_starting_with_dashes_is_not_a_header():
    diff = "diff --git a/a.sql b/a.sql\n--- a/a.sql\n+++ b/a.sql\n@@ -1 +0,0 @@\n--- GRANT x\n"
    assert machine_check.diff_rows(diff) == [("a.sql", 1, "-- GRANT x", True)]


# ---------------------------------------------------------------- 가림


def test_mask_lives_in_the_library_and_keeps_its_values():
    assert visual.mask_line is lib.mask_line and visual.MASK == lib.MASK
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZSJ9.abcDEF123_-"
    for line in ("service_role_key " + jwt, "api key: abcd1234efgh", "API-KEY=abcd1234efgh", "x ghp_abcdefghijklmnop", "u@example.com", "010-1234-5678"):
        assert lib.MASK in lib.mask_line(line), line
    assert lib.mask_line("api key: string") == "api key: string"


def test_mask_lines_keeps_numbers_and_covers_key_blocks():
    rows = ["const a = 1;", "-----BEGIN RSA PRIVATE KEY-----", "abcdef", "-----END RSA PRIVATE KEY-----", 'password = "x1"', "const b = 2;"]
    masked, n = lib.mask_lines(rows)
    assert len(masked) == len(rows) and n == 4
    assert masked[0] == rows[0] and masked[5] == rows[5] and all(lib.MASK in m for m in masked[1:5])


def test_card_and_shown_file_mask_secrets_and_count_them(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": "const a = 1;\n" + SECRET}))
    verify(run_dir, repo)
    plist = open_first(run_dir, make_places(run_dir))
    text = card(run_dir)
    assert "hunter2" not in text and lib.MASK in text and "1줄 가림" in text
    assert "hunter2" not in (run_dir.task_dir(FV) / "cards" / (plist[0]["key"] + ".shown.md")).read_text(encoding="utf-8")


def test_removed_secret_is_masked_in_card_and_places_file(run_dir, repo):
    commit(repo, {"src/a.ts": "const a = 1;\n" + SECRET})
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": "const a = 1;\n"}))
    verify(run_dir, repo)
    open_first(run_dir, make_places(run_dir))
    assert "hunter2" not in card(run_dir)
    assert "hunter2" not in (run_dir.task_dir(FV) / "places.md").read_text(encoding="utf-8")


def test_secret_in_an_opinion_is_masked(run_dir, repo):
    one_place(run_dir, repo, compare=opinion("src/a.ts:60", places.NO_PROBLEM).replace("일어난 일", "token=abcd1234efgh 를 쓴다"))
    assert "abcd1234efgh" not in card(run_dir)
    assert "abcd1234efgh" not in (run_dir.task_dir(FV) / "places.md").read_text(encoding="utf-8")


def test_fix_screen_masks_the_diff(run_dir, repo):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|이 코드만 고침 : 값을 바꾼다|2".format(got[0]["key"]))
    tid = run_script("task_set", run_dir.path, "new", "--from-answer", FV, "--place", got[0]["key"]).stdout.strip().splitlines()[-1]
    write(repo / "src" / "a.ts", BODY + SECRET)
    block = places.fix_block(str(run_dir.path), run_dir.tasks()[tid])
    assert any(lib.MASK in line for line in block) and not any("hunter2" in line for line in block)


# ---------------------------------------------------------------- 재검증 없음


def merge_setup(run_dir, repo):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|이 코드만 고침 : 값을 바꾼다|2".format(got[0]["key"]))
    tid = run_script("task_set", run_dir.path, "new", "--from-answer", FV, "--place", got[0]["key"]).stdout.strip().splitlines()[-1]
    assert complete(run_dir).returncode == 0
    path = run_dir.path / "run.md"
    path.write_text(path.read_text(encoding="utf-8").replace("status: 진행", "status: 진행\nintegration_branch: integ"), encoding="utf-8")
    return tid


def mergeable(run_dir):
    tasks = run_dir.tasks()
    flows = board.load_flows(str(run_dir.path))
    return board.mergeable_flows(tasks, flows, str(run_dir.path), lib.hold_blockers(tasks))


def test_merge_waits_for_the_code_check_fix_then_goes_without_a_reverify(run_dir, repo):
    tid = merge_setup(run_dir, repo)
    assert board.unreverified_fixes(run_dir.tasks()) == []
    assert mergeable(run_dir) == []
    path = run_dir.task_dir(tid) / "task.md"
    path.write_text(path.read_text(encoding="utf-8").replace("status: 대기", "status: 완료"), encoding="utf-8")
    assert board.unreverified_fixes(run_dir.tasks()) == []
    assert mergeable(run_dir) == ["reading"]


def test_other_fix_from_a_verify_still_needs_a_reverify(run_dir):
    run_dir.task(FV, "검증", kind="flow-verify", block="검증", status="완료", flow="a", **NEW)
    run_dir.task("T091", "수정", kind="fix", block="구현", status="완료", flow="a", parent=FV, origin="사용자 T090 2026-11-05 10:00:00")
    assert board.unreverified_fixes(run_dir.tasks()) == ["T091"]


# ---------------------------------------------------------------- 답의 꼴


@pytest.mark.parametrize("text", ["2 이 코드만 고침 :", "이 코드만 고침 :", "이 코드만 고침 :  ", "3 판단 안 됨 :", "판단 안 됨 :", "판단 안 됨 : :"])
def test_empty_text_is_asked_again(run_dir, repo, text):
    one_place(run_dir, repo)
    assert run_script("screen", run_dir.path, FV, "--answer", text).returncode == 3


def test_text_keeps_a_colon_inside(run_dir, repo):
    got = one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--answer", "이 코드만 고침 : a : b")
    assert "코드 확인 {}|이 코드만 고침 : a : b|".format(got[0]["key"]) in p.stdout


def test_four_with_its_name_is_the_bulk_answer(run_dir, repo):
    got = one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--answer", "4 나머지 남김")
    assert p.returncode == 0 and "코드 확인 {}|나머지 남김|".format(got[0]["key"]) in p.stdout
    assert run_script("screen", run_dir.path, FV, "--answer", "3 나머지 남김").returncode == 3


def test_comma_in_text_without_a_colon_is_one_answer(run_dir, repo):
    got = one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--answer", "3 판단 안 됨 호출부, 오류 경로")
    assert p.returncode == 0 and "코드 확인 {}|판단 안 됨 호출부, 오류 경로|".format(got[0]["key"]) in p.stdout


def test_judgment_mark_inside_the_text_is_text(run_dir, repo):
    got = one_place(run_dir, repo)
    text = "이 코드만 고침 : b1=null 일 때 막는다"
    p = run_script("screen", run_dir.path, FV, "--answer", text)
    assert "코드 확인 {}|{}|".format(got[0]["key"], text) in p.stdout
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|{}|{}".format(got[0]["key"], text, text)).returncode == 0
    assert places.read(str(run_dir.path), FV)[0]["답"] == text


def test_mark_inside_the_text_of_a_marked_answer(run_dir, repo):
    got = one_place(run_dir, repo, "- 도우미 [종류: 구조] [위치: src/a.ts:3]\n- 오류 [종류: 오류] [위치: src/a.ts:9]\n", "- 없음\n")
    value = "b1=문제 없음 b2=이 코드만 고침 : b1=null 을 막는다"
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|{}|2".format(got[0]["key"], value)).returncode == 0
    assert places.read(str(run_dir.path), FV)[0]["처리"] == places.ANSWERED


@pytest.mark.parametrize("word", ["보류", "중단"])
def test_hold_on_a_card_points_to_the_answer_table(run_dir, repo, word):
    one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--answer", word)
    assert p.returncode == 0 and "--status 보류" in p.stdout and "코드 확인 " not in p.stdout


# ---------------------------------------------------------------- 보안: 종류 이의, 표지, 낱말


def test_kind_objection_does_not_lower_security(run_dir, repo):
    code(run_dir, "T001", "- 권한 확인 [종류: 보안] [위치: src/a.ts:3]\n", "- 종류 이의: 권한 확인 | 보안 → 구조\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    assert make_places(run_dir)[0]["보안"] == "예"


@pytest.mark.parametrize("quote", ["도우미를 뺐다 [종류: 구조]", "도우미를…", "도우미를 뺐다 [위치: src/a.ts:3]"])
def test_kind_objection_reads_a_quote_with_tags_or_cut(run_dir, repo, quote):
    code(run_dir, "T001", "- 도우미를 뺐다 [종류: 구조] [위치: src/a.ts:3]\n", "- 종류 이의: {} | 구조 → 보안\n".format(quote), sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    assert make_places(run_dir)[0]["보안"] == "예"


@pytest.mark.parametrize("quote", ["", "…", "[종류: 구조]"])
def test_empty_quote_matches_nothing_and_is_reported(run_dir, repo, quote):
    code(run_dir, "T001", "- 도우미를 뺐다 [종류: 구조] [위치: src/a.ts:3]\n", "- 종류 이의: {} | 구조 → 보안\n".format(quote), sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    assert make_places(run_dir)[0]["보안"] == "아니오"
    assert "닿지 않음" in run_script("screen", run_dir.path, FV).stdout


def test_objection_that_reaches_no_judgment_is_shown(run_dir, repo):
    code(run_dir, "T001", "- 도우미 [종류: 구조] [위치: src/a.ts:3]\n", "- 종류 이의: 다른 문장 | 구조 → 보안\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    make_places(run_dir)
    assert "! 판정자 줄이 판단에 닿지 않음: T001 종류 이의 다른 문장" in run_script("screen", run_dir.path, FV).stdout


def test_partial_ac_counts_as_a_security_mark(run_dir, repo):
    write(run_dir.path / "spec" / "a.md", "# 묶음\n- AC-1 [보안] 거부한다\n")
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": BODY}), partial_ac=["AC-1"])
    verify(run_dir, repo)
    assert make_places(run_dir)[0]["부류"] == places.NO_JUDGMENT


@pytest.mark.parametrize("line,hit", [
    ("setCookie(x)", True), ("getCookie(x)", True), ("const user_password = v", True), ("userPassword", True), ("isAuthenticated()", True),
    ("verifyJwt(t)", True), ("app_password", True), ("v_password", True), ("appRolePassword", True), ("headers.Authorization", True),
    ("ALTER TABLE t ENABLE ROW LEVEL SECURITY;", True), ("userSsn", True), ("const jwt = 1", True), ("corsOptions", True), ("CORS", True),
    ("wear a corset", False), ("const className = 1", False), ("adjwtx", False), ("a fragrant smell", False), ("const total = 1", False),
])
def test_wider_start_words(line, hit):
    diff = "+++ b/src/a.ts\n@@ -0,0 +1 @@\n+{}\n".format(line)
    assert bool(machine_check.security_hits(diff, (), machine_check.DEFAULT_SECURITY_WORDS)) is hit


def test_project_word_matches_anywhere_and_short_word_keeps_its_edge():
    diff = "+++ b/a.ts\n@@ -0,0 +2 @@\n+myDangerZone()\n+abcfoox\n"
    assert [w for _, _, w, _ in machine_check.security_hits(diff, (), ["dangerZone", "foo"])] == ["dangerZone"]


def test_hits_have_no_duplicates():
    diff = "diff --git a/a.ts b/a.ts\n--- a/a.ts\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-authenticate(a)\n-authenticate(b)\n-authenticate(c)\n"
    assert len(machine_check.security_hits(diff, (), ["authenticate"])) == 1


def test_path_signal_sees_a_binary_file(run_dir, repo):
    write(run_dir.path.parent / "devflow-harness.project.md", "# 설정\n\n## 경로 목록\n- 보안 신호 경로: certs/**\n")
    (repo / "certs").mkdir()
    (repo / "certs" / "key.pem").write_bytes(b"\x00\x01\x02binary")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "이진")
    code(run_dir, "T001", "- 없음\n", sha=git(repo, "rev-parse", "--short", "HEAD"))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["파일"] for p in got] == [["certs/key.pem"]]
    open_first(run_dir, got)
    assert "이진 파일" in card(run_dir)


def test_binary_file_at_a_judgment_is_not_printed_as_text(run_dir, repo):
    (repo / "src").mkdir()
    (repo / "src" / "a.bin").write_bytes(b"\x00\x01garbage\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "이진")
    code(run_dir, "T001", "- 파일 추가 [종류: 구조] [위치: src/a.bin:1]\n", sha=git(repo, "rev-parse", "--short", "HEAD"))
    verify(run_dir, repo)
    open_first(run_dir, make_places(run_dir))
    text = card(run_dir)
    assert "이진 파일" in text and "garbage" not in text


def test_new_and_tracked_files_are_read_as_their_own(run_dir, repo):
    commit(repo, {"src/a.ts": "const a = 1;\n"})
    write(repo / "src" / "a.ts", "const a = 2;\n")
    write(repo / "n1.ts", "const password = x;\n")
    write(repo / "n2.ts", "const b = 1;\nsetCookie(y);\n")
    task = run_dir.task("T001", "구현", {"건드릴 파일": "- src/a.ts\n- n1.ts\n- n2.ts"}, kind="implementation", block="구현", status="진행", flow="reading", **NEW)
    out = run_script("machine_check", repo, task).stdout
    assert "보안 신호: n1.ts:1 | password" in out and "보안 신호: n2.ts:2 | cookie" in out and "보안 신호: src/a.ts" not in out


# ---------------------------------------------------------------- 둘째 검증


def test_second_verify_does_not_ask_again(run_dir, repo):
    code(run_dir, "T001", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    make_places(run_dir)
    code(run_dir, "T002", "- 새 판단 [종류: 구조] [위치: src/b.ts:3]\n", sha=commit(repo, {"src/b.ts": BODY}))
    run_dir.task("T095", "둘째 검증", kind="flow-verify", block="검증", status="자체검증", flow="reading", **NEW)
    run_dir.result("T095", result())
    judged(run_dir, "T095")
    assert [p["task"] for p in places.collect(str(run_dir.path), "T095")] == ["T002"]


def test_fix_from_any_verify_of_the_flow_makes_no_place(run_dir, repo):
    verify(run_dir, repo)
    run_dir.task("T095", "둘째 검증", kind="flow-verify", block="검증", status="자체검증", flow="reading", **NEW)
    code(run_dir, "T091", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=commit(repo, {"src/a.ts": BODY}), kind="fix", parent=FV)
    assert places.collect(str(run_dir.path), "T095") == []


def test_code_check_fix_makes_no_place_even_with_another_parent(run_dir, repo):
    verify(run_dir, repo)
    code(run_dir, "T091", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=commit(repo, {"src/a.ts": BODY}), kind="fix",
         origin="사용자 T090 2026-11-05 10:00:00 코드 확인 T001-abc")
    assert places.collect(str(run_dir.path), FV) == []


# ---------------------------------------------------------------- 재지 못함


def test_missing_folder_is_shown_and_not_silent(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": SECRET}))
    verify(run_dir)   # 코드 폴더 없음
    assert make_places(run_dir) == []
    assert "! 보안 신호를 재지 못함: T001" in run_script("screen", run_dir.path, FV).stdout


def test_done_is_refused_when_signals_could_not_be_measured_and_places_never_ran(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": SECRET}))
    verify(run_dir)
    waiting(run_dir)
    p = complete(run_dir)
    assert p.returncode == 3 and "--places" in p.output


def test_empty_commit_is_unmeasured_unless_no_change(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha="")
    code(run_dir, "T002", "- 없음\n", sha="", no_change="true")
    verify(run_dir, repo)
    make_places(run_dir)
    out = run_script("screen", run_dir.path, FV).stdout
    assert "! 보안 신호를 재지 못함: T001" in out and "T002" not in out.split("! 보안 신호를 재지 못함:")[1].splitlines()[0]


def test_card_without_any_code_does_not_take_fine(run_dir, repo):
    got = one_place(run_dir, repo, "- 도우미 [종류: 구조] [위치: src/a.ts:999]\n", "- 없음\n")
    text = card(run_dir)
    assert "1 문제 없음" not in text and "코드를 보이지 못" in text
    assert run_script("screen", run_dir.path, FV, "--answer", "1").returncode == 3
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|1".format(got[0]["key"])).returncode == 3
    assert run_script("screen", run_dir.path, FV, "--answer", "3 판단 안 됨 위치가 없음").returncode == 0


# ---------------------------------------------------------------- 발췌의 양


def lines_of(text):
    return [l for l in text.splitlines() if l[:1].isdigit() and "export const" in l]


def test_followed_excerpt_has_three_lines(run_dir, repo):
    one_place(run_dir, repo, "- 꼴 [종류: 구조] [위치: src/a.ts:30] [따름: src/z.ts:1]\n", "- 없음\n")
    assert len(lines_of(card(run_dir))) == 3


def test_many_places_have_a_floor_and_full_widens(run_dir, repo):
    judgments = "".join("- 판단{} [종류: 구조] [위치: src/a.ts:{}]\n".format(i, i * 20) for i in range(1, 6))
    one_place(run_dir, repo, judgments, "- 없음\n")
    small, wide = lines_of(card(run_dir)), lines_of(card(run_dir, "1", "--full"))
    assert len(small) == 12 and len(wide) > len(small) and len(wide) <= 61


def test_near_places_in_a_file_share_a_window(run_dir, repo):
    one_place(run_dir, repo, "- 가 [종류: 구조] [위치: src/a.ts:30]\n- 나 [종류: 구조] [위치: src/a.ts:32]\n", "- 없음\n")
    rows = lines_of(card(run_dir))
    assert len(rows) == len(set(rows))


def test_many_files_list_the_rest_and_full_keeps_the_total(run_dir, repo):
    write(run_dir.path / "spec" / "a.md", "# 묶음\n- AC-1 [보안] 거부한다\n")
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/f{:02d}.ts".format(i): BODY for i in range(20)}), closes_ac=["AC-1"])
    verify(run_dir, repo)
    open_first(run_dir, make_places(run_dir))
    small, wide = card(run_dir), card(run_dir, "1", "--full")
    assert "16개 더" in small and len(lines_of(small)) <= 15
    assert len(lines_of(wide)) <= 61 and len(lines_of(wide)) > len(lines_of(small))


def test_every_signal_line_can_be_seen(run_dir, repo):
    rows = ["const v{} = {};".format(i, i) for i in range(1, 321)]
    rows[4], rows[299] = "cookie();", "authorize();"
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": "\n".join(rows) + "\n"}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert got[0]["위치"] == ["src/a.ts:5", "src/a.ts:300"]
    open_first(run_dir, got)
    text = card(run_dir)
    assert "cookie();" in text and "authorize();" in text


# ---------------------------------------------------------------- 카드 사이, 중복 수정, 위임


def test_stop_between_cards_is_visible_and_holds_other_screens(run_dir, repo):
    many(run_dir, repo, ["구조", "구조"])
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"])
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|1".format(got[0]["key"]))
    want = "코드 확인 남음: {} 1곳, 다음 --card-open {}".format(FV, got[1]["key"])
    assert want in run_script("board", run_dir.path, "--resume").stdout
    assert want in run_script("board", run_dir.path, "--ready").stdout
    p = run_script("screen", run_dir.path, FV, "--save")
    assert "--save 안 함" in p.stdout and not (run_dir.task_dir(FV) / "screen-shown.md").exists()


def test_same_place_fix_is_not_made_twice(run_dir, repo):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|이 코드만 고침 : 바꾼다|2".format(got[0]["key"]))
    first = run_script("task_set", run_dir.path, "new", "--from-answer", FV, "--place", got[0]["key"]).stdout.strip().splitlines()[-1]
    again = run_script("task_set", run_dir.path, "new", "--from-answer", FV, "--place", got[0]["key"])
    assert again.returncode == 0 and again.stdout.strip().splitlines()[-1] == first
    assert sum(1 for t in run_dir.tasks().values() if t["kind"] == "fix") == 1


@pytest.mark.parametrize("value,want", [
    ("L1~L3", ("L1", "L2", "L3")), ("L2~L3", ("L2", "L3")), ("L1-L2", ("L1", "L2")), ("L1, L3", ("L1", "L3")), ("L4", ("L4")), ("L3~L1", ("L1", "L2", "L3")),
    ("L1 근거 없는 결정, L2 로컬", ("L1", "L2")), ("없음", ()), ("L1~L4 (운영 포함)", ("L1", "L2", "L3", "L4")),
])
def test_delegation_levels_read_ranges(run_dir, value, want):
    path = run_dir.path / "run.md"
    path.write_text(path.read_text(encoding="utf-8") + "| 위임 | {} |\n".format(value), encoding="utf-8")
    assert lib.delegation_levels(str(run_dir.path)) == (want if isinstance(want, tuple) else (want,))


@pytest.mark.parametrize("value,left", [("L1~L3", True), ("L1", True), ("L2~L3", False), ("L4", False)])
def test_only_l1_leaves_plain_places(run_dir, repo, value, left):
    many(run_dir, repo, ["구조"])
    verify(run_dir, repo, values="| 위임 | {} |\n".format(value))
    assert make_places(run_dir)[0]["처리"] == (places.LEFT_DELEGATED if left else places.WAITING)


def test_a_row_written_by_hand_does_not_leave_places(run_dir, repo):
    many(run_dir, repo, ["구조"])
    verify(run_dir, repo, values="| 위임 | L1~L3 |\n")
    (run_dir.path / "decisions.md").unlink()
    assert make_places(run_dir)[0]["처리"] == places.WAITING


def test_screen_module_is_untouched_by_old_screens(run_dir):
    assert screen.places.screen_lines(str(run_dir.path), "T001") == []
