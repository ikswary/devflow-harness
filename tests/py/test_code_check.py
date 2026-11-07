"""1.2.0 A4: 코드 확인(설계 11.1절 「1.2.0의 코드 확인」, 6.16절).

- `screen.py {실행} {flow-verify} --places`가 흐름의 코드 판단을 곳으로 묶어 `places.md`에 고정한다.
- 위험 순으로 카드를 내고, 답은 판단마다 받는다. 답이 빠진 곳이 있으면 흐름별 검증이 완료되지 않는다.
- 위임 중에는 일반 곳을 남기고 보안 곳만 기다린다.
- 옛 판본으로 시작한 task는 0곳이고 동작이 바뀌지 않는다.
"""
import re
import shutil
import subprocess
from datetime import datetime

import pytest

import devflow_lib as lib
import machine_check
import places
import screen
import task_set
from conftest import run_script, write
from test_domain_paths import READ_JUDGE, RUN_JUDGE
from test_review_contract import NEW, OLD, result

if shutil.which("git") is None:
    pytest.exit("git이 없음: 코드 확인 시험은 실제 git 저장소를 쓴다 — git을 설치하고 다시 돌린다", returncode=4)

FV = "T090"
BODY = "\n".join("export const line{} = {};".format(i, i) for i in range(1, 121)) + "\n"
# T040(mcp 실행 reading 흐름)의 결정 지도와 알릴 것을 판단 줄로 옮긴 표본. 판정자가 잇지 않으면 파일이 둘이다
T040_JUDGMENTS = ("- 요약 둘째 줄부터 값의 구역까지를 renderRunSections 하나가 돌려준다 [종류: 구조] [위치: worker/mcp/reading/run-body.ts:40]\n"
                  "- 요약 첫 줄은 body.ts에 둔다 [종류: 구조] [위치: worker/mcp/reading/body.ts:22]\n"
                  "- body.ts가 값 구역 도구를 내보낸다 [종류: 구조] [위치: worker/mcp/reading/body.ts:60]\n"
                  "- body.ts와 run-body.ts가 서로를 가져온다 [종류: 구조] [위치: worker/mcp/reading/run-body.ts:5]\n"
                  "- 확인 정보가 없는 확인 대기는 표를 두지 않는다 [종류: 오류] [위치: worker/mcp/reading/run-body.ts:87]\n")
T040_LINK = "- 같은 곳: worker/mcp/reading/body.ts:22 | worker/mcp/reading/run-body.ts:5\n"


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"] + list(args),
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "code"
    path.mkdir()
    git(path, "init", "-q")
    write(path / "README.md", "시작\n")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "시작")
    return path


def commit(repo, files):
    for name, text in files.items():
        write(repo / name, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "변경")
    return git(repo, "rev-parse", "--short", "HEAD")


def judged(run_dir, tid, compare="- 없음\n"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = READ_JUDGE.replace("T001", tid).format(now=now).split("## 판단 대조")[0] + "## 판단 대조\n" + compare
    run_dir.judge(tid, text)
    write(run_dir.task_dir(tid) / "judge-run.md", RUN_JUDGE.replace("T001", tid).format(now=now))


def code(run_dir, tid, judgments, compare="- 없음\n", sha="", meta=NEW, kind="implementation", sections=None, test_lines="- 없음\n", **more):
    """끝난 코드 task. 판단 줄과 판정자의 「판단 대조」, 기계가 쓴 시험 변화 줄을 받는다."""
    run_dir.task(tid, "구현 " + tid, dict({"건드릴 파일": "- src/a.ts"}, **(sections or {})), kind=kind, block="구현", status="완료",
                 flow="reading", commit=sha, **dict(meta, **more))
    run_dir.result(tid, result().split("## 판단")[0] + "## 판단\n" + judgments)
    judged(run_dir, tid, compare)
    write(run_dir.task_dir(tid) / lib.TEST_CHANGES, test_lines)


def verify(run_dir, repo=None, status="자체검증", meta=NEW, values=""):
    run_dir.flow("reading", dir=str(repo) if repo else "", status="폴더 있음")
    run_dir.task(FV, "흐름별 검증", kind="flow-verify", block="검증", status=status, flow="reading", **meta)
    run_dir.result(FV, result())
    judged(run_dir, FV)
    if values:
        path = run_dir.path / "run.md"
        path.write_text(path.read_text(encoding="utf-8") + values, encoding="utf-8")
        write(run_dir.path / "decisions.md", '- 2026-11-05 08:00:00 | 위임 L1~L3 | 원문: "전부 자동 승인" | 실행 전체\n')


def make_places(run_dir):
    p = run_script("screen", run_dir.path, FV, "--places")
    assert p.returncode == 0, p.output
    return places.read(str(run_dir.path), FV)


def waiting(run_dir):
    run_script("task_set", run_dir.path, FV, "--status", "승인대기")


def answer_all(run_dir, plist):
    for p in plist:
        if p["처리"] == "기다림":
            assert run_script("task_set", run_dir.path, FV, "--card-open", p["key"]).returncode == 0
            r = run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|문제 없음".format(p["key"]))
            assert r.returncode == 0, r.output


def complete(run_dir):
    return run_script("task_set", run_dir.path, FV, "--status", "완료", "--record", "승인|승인|승인합니다")


# ---------------------------------------------------------------- 묶음과 키


def test_t040_five_judgments_make_two_places_without_a_link(run_dir, repo):
    code(run_dir, "T040", T040_JUDGMENTS, sha=commit(repo, {"worker/mcp/reading/body.ts": BODY, "worker/mcp/reading/run-body.ts": BODY}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert sorted(p["파일"] for p in got) == [["worker/mcp/reading/body.ts"], ["worker/mcp/reading/run-body.ts"]]
    assert sorted(len(p["판단"]) for p in got) == [2, 3]
    assert all(j["b"] == "b{}".format(n) for p in got for n, j in enumerate(p["판단"], 1))


def test_t040_five_judgments_make_one_place_with_a_link(run_dir, repo):
    code(run_dir, "T040", T040_JUDGMENTS, T040_LINK, sha=commit(repo, {"worker/mcp/reading/body.ts": BODY, "worker/mcp/reading/run-body.ts": BODY}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert len(got) == 1
    assert [b["b"] for b in got[0]["판단"]] == ["b1", "b2", "b3", "b4", "b5"]
    assert got[0]["key"].startswith("T040-")


def test_key_stays_when_a_retry_changes_the_sentence(run_dir, repo):
    sha = commit(repo, {"src/a.ts": BODY})
    code(run_dir, "T001", "- 처음 문장 [종류: 구조] [위치: src/a.ts:3]\n", sha=sha)
    verify(run_dir, repo)
    first = places.collect(str(run_dir.path), FV)[0]["key"]
    code(run_dir, "T001", "- 다시 쓴 문장 [종류: 구조] [위치: src/a.ts:9]\n", sha=sha)
    assert places.collect(str(run_dir.path), FV)[0]["key"] == first


def test_places_file_is_fixed_after_the_first_run(run_dir, repo):
    sha = commit(repo, {"src/a.ts": BODY})
    code(run_dir, "T001", "- 처음 문장 [종류: 구조] [위치: src/a.ts:3]\n", sha=sha)
    verify(run_dir, repo)
    make_places(run_dir)
    code(run_dir, "T001", "- 다시 쓴 문장 [종류: 구조] [위치: src/b.ts:9]\n", sha=sha)
    assert make_places(run_dir)[0]["판단"][0]["text"].startswith("처음")


@pytest.mark.parametrize("kind,want", [("구조", 1), ("데이터", 1), ("트랜잭션", 1), ("오류", 1), ("외부호출", 1), ("보안", 1), ("동작", 0), ("시험", 0)])
def test_only_code_kinds_become_places(run_dir, repo, kind, want):
    code(run_dir, "T001", "- 판단 [종류: {}] [위치: src/a.ts:3]\n".format(kind), sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    assert len(make_places(run_dir)) == want


def test_design_lines_are_not_judgments(run_dir, repo):
    code(run_dir, "T001", "- 저장 위치 [설계: 3절]\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    assert make_places(run_dir) == []


def test_hidden_judgment_takes_the_same_path(run_dir, repo):
    compare = ("- 숨은 판단: src/a.ts:5 | 도우미를 새로 뺐다 | 구조\n- 숨은 판단: src/b.ts:5 | 제목을 바꿨다 | 동작\n")
    code(run_dir, "T001", "- 없음\n", compare, sha=commit(repo, {"src/a.ts": BODY, "src/b.ts": BODY}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["파일"] for p in got] == [["src/a.ts"]]
    assert got[0]["판단"][0]["text"] == "도우미를 새로 뺐다"


def test_kind_objection_only_raises(run_dir, repo):
    judgments = "- 재시도 값 [종류: 시험] [위치: src/a.ts:5]\n- 공용 도우미 [종류: 구조] [위치: src/b.ts:5]\n"
    compare = "- 종류 이의: 재시도 값 | 시험 → 외부호출\n- 종류 이의: 공용 도우미 | 구조 → 동작\n"
    code(run_dir, "T001", judgments, compare, sha=commit(repo, {"src/a.ts": BODY, "src/b.ts": BODY}))
    verify(run_dir, repo)
    assert sorted(p["파일"][0] for p in make_places(run_dir)) == ["src/a.ts", "src/b.ts"]


# ---------------------------------------------------------------- 옛 task


def test_old_task_makes_no_place(run_dir, repo):
    code(run_dir, "T001", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", meta=OLD, sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    assert make_places(run_dir) == []


def test_old_verify_writes_nothing_and_completes(run_dir, repo):
    code(run_dir, "T001", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo, meta=OLD)
    p = run_script("screen", run_dir.path, FV, "--places")
    assert p.returncode == 0 and "0곳" in p.stdout
    assert not (run_dir.task_dir(FV) / "places.md").exists()
    waiting(run_dir)
    assert complete(run_dir).returncode == 0


def test_only_verify_tasks_take_places(run_dir, repo):
    code(run_dir, "T001", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=commit(repo, {"src/a.ts": BODY}))
    assert run_script("screen", run_dir.path, "T001", "--places").returncode == 3


# ---------------------------------------------------------------- 양과 차례


def many(run_dir, repo, kinds_in_order):
    files = {"src/f{}.ts".format(i): BODY for i in range(len(kinds_in_order))}
    sha = commit(repo, files)
    code(run_dir, "T001", "".join("- 판단{} [종류: {}] [위치: src/f{}.ts:3]\n".format(i, k, i) for i, k in enumerate(kinds_in_order)), sha=sha)


def test_risk_order(run_dir, repo):
    many(run_dir, repo, ["구조", "오류", "외부호출", "데이터", "트랜잭션", "보안"])
    verify(run_dir, repo)
    assert [p["종류"] for p in make_places(run_dir)] == ["보안", "트랜잭션", "데이터", "외부호출", "오류", "구조"]


def test_config_registration_goes_last(run_dir, repo):
    sha = commit(repo, {"tsconfig.json": "{}\n", "src/a.ts": BODY})
    code(run_dir, "T001", "- 경로 등록 [종류: 트랜잭션] [위치: tsconfig.json:1]\n- 구조 [종류: 구조] [위치: src/a.ts:3]\n", sha=sha)
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["파일"] for p in got] == [["src/a.ts"], ["tsconfig.json"]]
    assert got[1]["종류"] == "설정 등록"


def test_followed_pattern_goes_behind_the_same_kind_with_a_short_excerpt(run_dir, repo):
    sha = commit(repo, {"src/a.ts": BODY, "src/b.ts": BODY})
    code(run_dir, "T001", "- 꼴을 따름 [종류: 구조] [위치: src/a.ts:30] [따름: src/z.ts:1]\n- 새로 정함 [종류: 구조] [위치: src/b.ts:30]\n", sha=sha)
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["파일"][0] for p in got] == ["src/b.ts", "src/a.ts"]
    assert got[1]["발췌"] == "3"


def test_cap_leaves_the_rest(run_dir, repo):
    many(run_dir, repo, ["구조"] * 7)
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["처리"] for p in got].count("기다림") == 5
    assert [p["처리"] for p in got].count("남김(상한)") == 2


def test_security_places_stay_outside_the_cap(run_dir, repo):
    many(run_dir, repo, ["보안"] * 6 + ["구조"] * 7)
    verify(run_dir, repo)
    got = make_places(run_dir)
    state = [(p["보안"], p["처리"]) for p in got]
    assert state.count(("예", "기다림")) == 6
    assert state.count(("아니오", "기다림")) == 5
    assert state.count(("아니오", "남김(상한)")) == 2
    assert [p["보안"] for p in got][:6] == ["예"] * 6


def opinion(where, verdict):
    return "- 코드 의견: {} | 일어난 일 | {} | 깨지는 조건 | 다른 곳의 방식\n".format(where, verdict)


def test_problem_opinion_goes_first_and_does_not_break_the_cap(run_dir, repo):
    many(run_dir, repo, ["트랜잭션"] * 5 + ["구조"])
    path = run_dir.task_dir("T001") / "judge.md"
    text = path.read_text(encoding="utf-8").replace("## 판단 대조\n- 없음\n", "## 판단 대조\n" + opinion("src/f5.ts:3", "지금 문제 있음"))
    path.write_text(text, encoding="utf-8")
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert got[0]["파일"] == ["src/f5.ts"] and got[0]["의견"] == "지금 문제 있음"
    assert [p["처리"] for p in got].count("기다림") == 5


def test_left_problem_opinion_is_quoted_for_the_wrap_up_review(run_dir, repo):
    many(run_dir, repo, ["구조"] * 7)
    path = run_dir.task_dir("T001") / "judge.md"
    compare = "".join(opinion("src/f{}.ts:3".format(i), "지금 문제 있음") for i in range(6))
    text = path.read_text(encoding="utf-8").replace("## 판단 대조\n- 없음\n", "## 판단 대조\n" + compare)
    path.write_text(text, encoding="utf-8")
    verify(run_dir, repo)
    got = make_places(run_dir)
    left = [p for p in got if p["처리"] == "남김(상한)"]
    assert len(left) == 2 and sum(1 for p in left if p["의견"] == "지금 문제 있음") == 1
    summary = places.run_left(str(run_dir.path))
    assert summary["count"] == 2
    assert len(summary["where"]) == 2
    assert summary["problems"] == [opinion("src/f5.ts:3", "지금 문제 있음")[2:].rstrip("\n")]


def test_opinion_with_no_judgment_is_not_lost(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", opinion("src/a.ts:3", "지금 문제 있음") + opinion("src/b.ts:3", "지금 문제 없음"),
         sha=commit(repo, {"src/a.ts": BODY, "src/b.ts": BODY}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["파일"] for p in got] == [["src/a.ts"]]
    assert got[0]["의견"] == "지금 문제 있음"


def test_third_same_judgment_is_raised(run_dir, repo):
    sha = commit(repo, {"src/{}.ts".format(c): BODY for c in "abcdefg"})
    code(run_dir, "T001", "".join("- 판단 [종류: 트랜잭션] [위치: src/{}.ts:3]\n".format(c) for c in "abcdef"), sha=sha)
    code(run_dir, "T002", "- 같은 도우미 [종류: 구조] [위치: src/g.ts:3]\n", sha=sha, depends_on=["T001"])
    code(run_dir, "T003", "- 같은 도우미 [종류: 구조] [위치: src/g.ts:3]\n", "- 같은 판단: 같은 도우미 | T002\n", sha=sha)
    code(run_dir, "T004", "- 같은 도우미 [종류: 구조] [위치: src/g.ts:3]\n", "- 같은 판단: 같은 도우미 | T003\n", sha=sha)
    verify(run_dir, repo)
    got = make_places(run_dir)
    shown = [p["task"] for p in got if p["처리"] == "기다림"]
    assert "T004" in shown and "T003" not in shown and "T002" not in shown


# ---------------------------------------------------------------- 보안 표지와 신호


def security_settings(run_dir, words="", paths=""):
    write(run_dir.path.parent / "devflow-harness.project.md", "# 프로젝트 설정\n\n## 경로 목록\n- 감지한 실행: dryrun\n"
          + ("- 보안 신호 경로: {}\n".format(paths) if paths else "") + ("- 보안 신호 낱말: {}\n".format(words) if words else ""))


def test_default_security_signal_makes_a_place_without_judgments(run_dir, repo):
    sha = commit(repo, {"src/a.ts": "const a = 1;\nres.setHeader('Set-Cookie', c);\n", "tests/a.test.ts": "res.setHeader('Set-Cookie', c);\n"})
    code(run_dir, "T001", "- 없음\n", sha=sha)
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert len(got) == 1 and got[0]["부류"] == places.NO_JUDGMENT
    assert got[0]["파일"] == ["src/a.ts"] and got[0]["위치"] == ["src/a.ts:2"] and got[0]["보안"] == "예"


def test_removed_line_counts_as_a_signal(run_dir, repo):
    commit(repo, {"src/a.ts": "authenticate(req);\nconst a = 1;\n"})
    sha = commit(repo, {"src/a.ts": "const a = 1;\n"})
    code(run_dir, "T001", "- 없음\n", sha=sha)
    verify(run_dir, repo)
    assert make_places(run_dir)[0]["파일"] == ["src/a.ts"]


def test_project_words_and_paths_replace_the_start_values(run_dir, repo):
    security_settings(run_dir, words="dangerZone", paths="db/grants/**")
    sha = commit(repo, {"src/a.ts": "res.setHeader('Set-Cookie', c);\n", "src/b.ts": "dangerZone();\n", "db/grants/x.txt": "내용\n"})
    code(run_dir, "T001", "- 없음\n", sha=sha)
    verify(run_dir, repo)
    assert sorted(p["파일"][0] for p in make_places(run_dir)) == ["db/grants/x.txt", "src/b.ts"]


def test_signal_lifts_a_judgment_place_into_security(run_dir, repo):
    sha = commit(repo, {"src/a.ts": "const a = 1;\nconst cors = true;\n"})
    code(run_dir, "T001", "- 도우미 [종류: 구조] [위치: src/a.ts:1]\n", sha=sha)
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert len(got) == 1 and got[0]["보안"] == "예" and got[0]["부류"] == places.WITH_JUDGMENT


def test_security_mark_on_ac_shows_the_rest_of_the_task(run_dir, repo):
    write(run_dir.path / "spec" / "a.md", "# 묶음\n- AC-1 [보안] 권한이 없으면 거부한다\n- AC-2 목록을 보인다\n")
    sha = commit(repo, {"src/a.ts": BODY, "src/b.ts": BODY, "tests/a.test.ts": BODY})
    code(run_dir, "T001", "- 도우미 [종류: 구조] [위치: src/a.ts:3]\n", sha=sha, closes_ac=["AC-1"])
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert [p["보안"] for p in got] == ["예", "예"]
    assert sorted(p["부류"] for p in got) == sorted([places.NO_JUDGMENT, places.WITH_JUDGMENT])
    assert ["src/b.ts"] in [p["파일"] for p in got]


def test_plain_ac_is_not_security(run_dir, repo):
    write(run_dir.path / "spec" / "a.md", "# 묶음\n- AC-1 [보안] 거부한다\n- AC-2 목록을 보인다\n")
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": BODY}), closes_ac=["AC-2"])
    verify(run_dir, repo)
    assert make_places(run_dir) == []


def test_security_mark_on_design_row(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": BODY}), sections={"시그니처와 결정 번호": "- 결정 3 [보안]"})
    verify(run_dir, repo)
    assert make_places(run_dir)[0]["부류"] == places.NO_JUDGMENT


@pytest.mark.parametrize("line,hit", [
    ("res.setHeader('Set-Cookie', c)", True), ("GRANT SELECT ON t TO anon;", True), ("verifyToken(req)", True),
    ("const className = 'x'", False), ("const total = 1", False), ("app.use(cors())", True), ("const password = x", True),
])
def test_start_words(line, hit):
    words = machine_check.DEFAULT_SECURITY_WORDS
    diff = "+++ b/src/a.ts\n@@ -0,0 +1 @@\n+{}\n".format(line)
    assert bool(machine_check.security_hits(diff, (), words)) is hit


def test_machine_check_prints_signal_lines_only_for_new_tasks(run_dir, repo):
    write(repo / "src" / "a.ts", "const a = 1;\nres.setHeader('Set-Cookie', c);\n")
    new = run_dir.task("T001", "구현", {"건드릴 파일": "- src/a.ts"}, kind="implementation", block="구현", status="진행", flow="reading", **NEW)
    p = run_script("machine_check", repo, new)
    assert p.returncode == 0 and "보안 신호: src/a.ts:2 | Set-Cookie" in p.stdout
    old = run_dir.task("T002", "구현", {"건드릴 파일": "- src/a.ts"}, kind="implementation", block="구현", status="진행", flow="reading", **OLD)
    p = run_script("machine_check", repo, old)
    assert p.returncode == 0 and "보안 신호" not in p.stdout


# ---------------------------------------------------------------- 카드


def one_place(run_dir, repo, judgments="- 도우미를 뺐다 [종류: 구조] [위치: src/a.ts:60]\n", compare=None):
    compare = compare if compare is not None else "- 코드 의견: src/a.ts:60 | 두 파일이 도우미를 함께 쓴다 | 지금 문제 없음 | 최상위에서 읽으면 깨진다 | 다른 곳은 공용 파일로 뺀다\n"
    code(run_dir, "T001", judgments, compare, sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    assert run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"]).returncode == 0
    return got


def test_card_is_a_plain_message_with_code_and_opinion(run_dir, repo):
    got = one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--card", "1")
    assert p.returncode == 0, p.output
    card = p.stdout
    for part in ("코드 확인 1/1", "T001", "reading", "일어난 일", "두 파일이 도우미를 함께 쓴다", "b1", "도우미를 뺐다", "export const line60 = 60;",
                 "지금 문제 없음", "최상위에서 읽으면 깨진다", "다른 곳은 공용 파일로 뺀다", "1 문제 없음", "2 이 코드만 고침 : {무엇을}",
                 "3 판단 안 됨 {부족한 것}", "4 나머지 남김", got[0]["key"]):
        assert part in card, part
    assert "추천" not in card
    code_lines = [l for l in card.splitlines() if re.match(r"^\d+ +export const", l)]
    assert 9 <= len(code_lines) <= 15
    assert (run_dir.task_dir(FV) / "cards" / (got[0]["key"] + ".shown.md")).is_file()


def test_full_card_shows_about_sixty_lines(run_dir, repo):
    one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--card", "1", "--full")
    code_lines = [l for l in p.stdout.splitlines() if re.match(r"^\d+ +export const", l)]
    assert 50 <= len(code_lines) <= 61


def test_card_reads_the_task_commit_not_the_later_tree(run_dir, repo):
    one_place(run_dir, repo)
    commit(repo, {"src/a.ts": "export const later = 1;\n"})
    p = run_script("screen", run_dir.path, FV, "--card", "1")
    assert "export const line60 = 60;" in p.stdout and "export const later" not in p.stdout
    assert "흐름 끝에서 달라짐" in p.stdout


def test_card_reports_a_missing_line(run_dir, repo):
    one_place(run_dir, repo, "- 도우미 [종류: 구조] [위치: src/a.ts:999]\n", "- 없음\n")
    p = run_script("screen", run_dir.path, FV, "--card", "1")
    assert "! 위치 없음: src/a.ts:999" in p.stdout and "의견 없음" in p.stdout


def test_card_says_when_the_opinion_is_empty_or_problem(run_dir, repo):
    one_place(run_dir, repo, compare=opinion("src/a.ts:60", "지금 문제 있음"))
    assert "지금 문제 있음" in run_script("screen", run_dir.path, FV, "--card", "1").stdout


def test_card_without_a_number_reopens_the_open_card_after_clear(run_dir, repo):
    got = one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--card")
    assert p.returncode == 0 and got[0]["key"] in p.stdout
    resume = run_script("board", run_dir.path, "--resume")
    assert "답 대기: {} 카드 1/1".format(FV) in resume.stdout
    assert got[0]["key"] in resume.stdout


def test_card_refuses_another_key_than_the_open_one(run_dir, repo):
    many(run_dir, repo, ["구조", "구조"])
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    assert run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"]).returncode == 0
    assert run_script("screen", run_dir.path, FV, "--card", "2").returncode == 3


def test_tree_lists_the_folder_and_shows_the_same_card(run_dir, repo):
    code(run_dir, "T001", "- 도우미 [종류: 구조] [위치: src/lib/a.ts:3]\n", sha=commit(repo, {"src/lib/a.ts": "a\nb\nc\n", "src/lib/b.ts": "a\n", "src/c.ts": "a\n"}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"])
    p = run_script("screen", run_dir.path, FV, "--card", "1", "--tree")
    assert p.returncode == 0, p.output
    assert "src/lib/a.ts | 3" in p.stdout and "src/lib/b.ts | 1" in p.stdout and "src/c.ts" not in p.stdout
    assert "코드 확인 1/1" in p.stdout


def test_security_card_without_judgment_has_signal_and_no_bulk_answer(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": "const a = 1;\nres.setHeader('Set-Cookie', c);\n"}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"])
    card = run_script("screen", run_dir.path, FV, "--card", "1").stdout
    assert "src/a.ts:2 | Set-Cookie" in card and "나머지 남김" not in card and "1 문제 없음" in card


# ---------------------------------------------------------------- 답 표본


@pytest.mark.parametrize("text,want", [
    ("1", "문제 없음"), ("문제 없음", "문제 없음"), ("1 문제 없음", "문제 없음"),
    ("2 이 코드만 고침 : 이름을 바꾼다, 시험도", "이 코드만 고침 : 이름을 바꾼다, 시험도"), ("이 코드만 고침 : 이름", "이 코드만 고침 : 이름"),
    ("3 판단 안 됨 호출 흐름", "판단 안 됨 호출 흐름"), ("판단 안 됨 호출 흐름", "판단 안 됨 호출 흐름"), ("4", "나머지 남김"), ("나머지 남김", "나머지 남김"),
])
def test_answer_samples_on_one_judgment(run_dir, repo, text, want):
    got = one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--answer", text)
    assert p.returncode == 0, p.output
    assert "코드 확인 {}|{}|{}".format(got[0]["key"], want, text) in p.stdout


@pytest.mark.parametrize("text", ["2", "이 코드만 고침", "3", "판단 안 됨", "5", "승인", "1 판단 안 됨 호출", "b9 문제 없음", "좋아요"])
def test_answers_out_of_shape_are_asked_again(run_dir, repo, text):
    one_place(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--answer", text)
    assert p.returncode == 3 and "되물음" in p.stdout


def two_judgments(run_dir, repo):
    return one_place(run_dir, repo, "- 도우미 [종류: 구조] [위치: src/a.ts:3]\n- 오류 처리 [종류: 오류] [위치: src/a.ts:9]\n", "- 없음\n")


@pytest.mark.parametrize("text,want", [
    ("b1 문제 없음, b2 이 코드만 고침 : 잡는다, 올린다", "b1=문제 없음 b2=이 코드만 고침 : 잡는다, 올린다"),
    ("b1 1, b2 3 판단 안 됨 호출", "b1=문제 없음 b2=판단 안 됨 호출"),
    ("b1,b2 문제 없음", "b1,b2=문제 없음"),
    ("1", "문제 없음"),
])
def test_answers_per_judgment(run_dir, repo, text, want):
    got = two_judgments(run_dir, repo)
    p = run_script("screen", run_dir.path, FV, "--answer", text)
    assert p.returncode == 0, p.output
    assert "코드 확인 {}|{}|".format(got[0]["key"], want) in p.stdout


def test_partial_answer_is_asked_again(run_dir, repo):
    two_judgments(run_dir, repo)
    assert run_script("screen", run_dir.path, FV, "--answer", "b1 문제 없음").returncode == 3


def test_full_and_tree_are_not_answers(run_dir, repo):
    one_place(run_dir, repo)
    for text in ("전체", "1 전체"):
        p = run_script("screen", run_dir.path, FV, "--answer", text)
        assert p.returncode == 0 and "--card 1 --full" in p.stdout and "코드 확인 " not in p.stdout
    p = run_script("screen", run_dir.path, FV, "--answer", "판단 안 됨 구조 표")
    assert p.returncode == 0 and "--card 1 --tree" in p.stdout


def test_second_structure_request_counts_as_left(run_dir, repo):
    got = one_place(run_dir, repo)
    assert run_script("screen", run_dir.path, FV, "--card", "1", "--tree").returncode == 0
    p = run_script("screen", run_dir.path, FV, "--answer", "판단 안 됨 구조 표")
    assert "코드 확인 {}|판단 안 됨 구조 표|".format(got[0]["key"]) in p.stdout


def test_record_marks_place_clears_card_and_tells_the_next(run_dir, repo):
    many(run_dir, repo, ["구조", "구조"])
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"])
    p = run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|1".format(got[0]["key"]))
    assert p.returncode == 0, p.output
    assert "다음 카드: 2" in p.stdout
    after = places.read(str(run_dir.path), FV)
    assert after[0]["처리"] == "답함" and after[0]["답"] == "문제 없음"
    assert not str(run_dir.tasks()[FV].get("card_open", "") or "").strip()
    assert lib.has_quoted_answer(run_dir.tasks()[FV]) is False


def test_record_refuses_unknown_key_and_partial_answer(run_dir, repo):
    got = two_judgments(run_dir, repo)
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 T001-없음|문제 없음|1").returncode == 3
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|b1=문제 없음|1".format(got[0]["key"])).returncode == 3
    assert places.read(str(run_dir.path), FV)[0]["처리"] == "기다림"


def test_rest_left_counts_as_one_answer_and_keeps_security_waiting(run_dir, repo):
    many(run_dir, repo, ["보안", "구조", "구조", "구조"])
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    run_script("task_set", run_dir.path, FV, "--card-open", got[1]["key"])
    p = run_script("screen", run_dir.path, FV, "--answer", "나머지 남김")
    assert p.returncode == 0, p.output
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|나머지 남김|나머지 남김".format(got[1]["key"])).returncode == 0
    after = places.read(str(run_dir.path), FV)
    assert [p["처리"] for p in after] == ["기다림", "남김(일괄)", "남김(일괄)", "남김(일괄)"]
    assert run_dir.tasks()[FV]["_sections"]["승인 기록"].count("코드 확인") == 1
    assert "지금 답 없는" in complete(run_dir).output


def test_rest_left_is_refused_on_a_security_card(run_dir, repo):
    many(run_dir, repo, ["보안", "구조"])
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"])
    assert run_script("screen", run_dir.path, FV, "--answer", "나머지 남김").returncode == 3
    assert run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|나머지 남김|나머지 남김".format(got[0]["key"])).returncode == 3


def test_not_judged_counts_as_left_and_is_listed(run_dir, repo):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|판단 안 됨 호출 흐름|3".format(got[0]["key"]))
    assert places.read(str(run_dir.path), FV)[0]["처리"] == "남김(판단 안 됨)"
    assert places.run_left(str(run_dir.path))["count"] == 1
    assert complete(run_dir).returncode == 0


def test_left_places_are_shown_on_the_verify_screen(run_dir, repo):
    many(run_dir, repo, ["구조"] * 7)
    verify(run_dir, repo)
    make_places(run_dir)
    out = run_script("screen", run_dir.path, FV).stdout
    assert "■ 코드 확인: 보일 곳 5, 답 0, 남긴 곳 2" in out
    assert out.count("- 남김(상한)") == 2


# ---------------------------------------------------------------- 가드와 대기


def test_done_is_refused_while_a_place_has_no_answer(run_dir, repo):
    got = one_place(run_dir, repo)
    p = complete(run_dir)
    assert p.returncode == 3 and got[0]["key"] in p.output
    assert run_dir.tasks()[FV]["status"] == "승인대기"
    answer_all(run_dir, got)
    assert complete(run_dir).returncode == 0


def test_hold_is_allowed_while_a_place_has_no_answer(run_dir, repo):
    one_place(run_dir, repo)
    p = run_script("task_set", run_dir.path, FV, "--status", "보류", "--record", "보류|보류|잠시 둡니다")
    assert p.returncode == 0, p.output
    assert not str(run_dir.tasks()[FV].get("card_open", "") or "").strip()


def test_done_is_refused_when_places_never_ran(run_dir, repo):
    code(run_dir, "T001", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    waiting(run_dir)
    p = complete(run_dir)
    assert p.returncode == 3 and "--places" in p.output


def test_done_passes_when_there_is_nothing_to_look_at(run_dir, repo):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    waiting(run_dir)
    assert complete(run_dir).returncode == 0


def test_done_waits_for_unanswered_test_removals(run_dir, repo, monkeypatch):
    code(run_dir, "T001", "- 없음\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    t = run_dir.tasks()[FV]
    assert places.completion_block(str(run_dir.path), t) == ""
    monkeypatch.setattr(lib, "unanswered_test_removals", lambda task: ["시험 끄기 src/a.test.ts:3"])
    assert "시험 끄기 src/a.test.ts:3" in places.completion_block(str(run_dir.path), t)


def test_unanswered_test_removals_is_empty_when_nothing_changed(run_dir):
    run_dir.task("T001", "구현", kind="implementation", block="구현", status="완료", **NEW)
    write(run_dir.task_dir("T001") / lib.TEST_CHANGES, "- 없음\n")
    assert lib.unanswered_test_removals(run_dir.tasks()["T001"]) == []


def test_return_during_a_card_keeps_the_card_and_holds_other_screens(run_dir, repo):
    got = one_place(run_dir, repo)
    run_dir.task("T050", "다른 구현", kind="design", status="진행", **NEW)
    run_dir.result("T050", result())
    judged(run_dir, "T050")
    # 반환 처리(다른 task의 전이)는 카드를 건드리지 않는다
    assert run_script("task_set", run_dir.path, "T050", "--status", "자체검증").returncode == 0
    assert run_script("task_set", run_dir.path, "T050", "--status", "승인대기").returncode == 0
    assert run_dir.tasks()[FV]["card_open"] == got[0]["key"]
    # 다른 화면을 띄우지 않는다
    p = run_script("screen", run_dir.path, "T050", "--save")
    assert "--save 안 함" in p.stdout and "답 대기" in p.stdout
    assert not (run_dir.task_dir("T050") / "screen-shown.md").exists()
    ready = run_script("board", run_dir.path, "--ready")
    assert "답 대기: {} 카드 1/1".format(FV) in ready.stdout
    answer_all(run_dir, got)
    assert run_script("screen", run_dir.path, "T050", "--save").returncode == 0
    assert (run_dir.task_dir("T050") / "screen-shown.md").is_file()


def test_card_open_needs_waiting_status_and_a_waiting_place(run_dir, repo):
    code(run_dir, "T001", "- 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo)
    got = make_places(run_dir)
    assert run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"]).returncode == 3
    waiting(run_dir)
    assert run_script("task_set", run_dir.path, FV, "--card-open", "T001-없음").returncode == 3
    assert run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"]).returncode == 0
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|1".format(got[0]["key"]))
    assert run_script("task_set", run_dir.path, FV, "--card-open", got[0]["key"]).returncode == 3


# ---------------------------------------------------------------- 위임


def test_delegation_leaves_plain_places_and_passes(run_dir, repo):
    many(run_dir, repo, ["구조", "오류"])
    verify(run_dir, repo, values="| 위임 | L1~L3 |\n")
    got = make_places(run_dir)
    assert [p["처리"] for p in got] == ["남김(위임)", "남김(위임)"]
    assert "위임" in (run_dir.task_dir(FV) / "places.md").read_text(encoding="utf-8").splitlines()[2]
    waiting(run_dir)
    assert complete(run_dir).returncode == 0


def test_delegation_waits_for_security_places(run_dir, repo):
    many(run_dir, repo, ["보안", "구조"])
    verify(run_dir, repo, values="| 위임 | L1~L3 |\n")
    got = make_places(run_dir)
    assert [p["처리"] for p in got] == ["기다림", "남김(위임)"]
    waiting(run_dir)
    assert complete(run_dir).returncode == 3
    answer_all(run_dir, got)
    assert complete(run_dir).returncode == 0


OFF_LINE = "- 끄기 | src/a.test.ts:3 | +1/-0\n"


def with_off_line(run_dir, repo, kinds_list):
    many(run_dir, repo, kinds_list)
    first = sorted(tid for tid, t in run_dir.tasks().items() if t.get("kind") == "implementation")[0]
    write(run_dir.task_dir(first) / lib.TEST_CHANGES, OFF_LINE)
    verify(run_dir, repo, values="| 위임 | L1~L3 |\n")
    got = make_places(run_dir)
    waiting(run_dir)
    return got


def answer_test_change(run_dir):
    tasks = run_dir.tasks()
    keys = [row["key"] for row in lib.flow_test_rows(tasks[FV], tasks)]
    r = run_script("task_set", run_dir.path, FV, "--record", "{}|{}=받아들임|괜찮습니다".format(lib.TEST_CHANGE_POINT, ",".join(keys)))
    assert r.returncode == 0, r.output


def test_delegation_refusal_names_the_place_and_the_test_change_once_each(run_dir, repo):
    got = with_off_line(run_dir, repo, ["보안", "구조"])
    out = complete(run_dir)
    assert out.returncode == 3
    assert out.output.count("지금 답 없는 코드 확인 곳이 있음") == 1 and out.output.count("답 없는 시험 끄기·삭제") == 1
    assert out.output.count(got[0]["key"]) == 1 and out.output.count("끄기 | src/a.test.ts:3") == 1


def test_delegation_waits_for_the_test_change_after_the_place_is_answered(run_dir, repo):
    got = with_off_line(run_dir, repo, ["보안", "구조"])
    answer_all(run_dir, got)
    out = complete(run_dir)
    assert out.returncode == 3 and "시험 끄기·삭제" in out.output and "코드 확인 곳" not in out.output
    answer_test_change(run_dir)
    assert complete(run_dir).returncode == 0


def test_delegation_waits_for_the_place_after_the_test_change_is_answered(run_dir, repo):
    got = with_off_line(run_dir, repo, ["보안", "구조"])
    answer_test_change(run_dir)
    out = complete(run_dir)
    assert out.returncode == 3 and "코드 확인 곳" in out.output and "시험 끄기·삭제" not in out.output
    answer_all(run_dir, got)
    assert complete(run_dir).returncode == 0


def test_delegation_with_a_plain_place_waits_only_for_the_test_change(run_dir, repo):
    assert [p["처리"] for p in with_off_line(run_dir, repo, ["구조"])] == ["남김(위임)"]
    assert "시험 끄기·삭제" in complete(run_dir).output
    answer_test_change(run_dir)
    assert complete(run_dir).returncode == 0


@pytest.mark.parametrize("row,want", [("| 위임 | 없음 |\n", False), ("| 동시에 도는 흐름 | 2 |\n", False), ("| 위임 | L4 |\n", True), ("| 위임 층 | L1 |\n", True)])
def test_delegation_row(run_dir, row, want):
    path = run_dir.path / "run.md"
    path.write_text(path.read_text(encoding="utf-8") + row, encoding="utf-8")
    assert bool(lib.delegation_levels(str(run_dir.path))) is want


def test_problem_opinion_left_by_delegation_is_quoted(run_dir, repo):
    code(run_dir, "T001", "- 도우미 [종류: 구조] [위치: src/a.ts:3]\n", opinion("src/a.ts:3", "지금 문제 있음"), sha=commit(repo, {"src/a.ts": BODY}))
    verify(run_dir, repo, values="| 위임 | L1~L3 |\n")
    make_places(run_dir)
    assert places.run_left(str(run_dir.path))["problems"] == [opinion("src/a.ts:3", "지금 문제 있음")[2:].rstrip("\n")]


# ---------------------------------------------------------------- 고침


def fix_from_answer(run_dir, repo):
    got = one_place(run_dir, repo)
    run_dir.flow("reading", dir=str(repo), status="폴더 있음")
    p = run_script("screen", run_dir.path, FV, "--answer", "2 이 코드만 고침 : 도우미 이름을 바꾼다")
    assert p.returncode == 0, p.output
    assert "--from-answer {} --place {}".format(FV, got[0]["key"]) in p.stdout
    r = run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|이 코드만 고침 : 도우미 이름을 바꾼다|2 이 코드만 고침 : 도우미 이름을 바꾼다".format(got[0]["key"]))
    assert r.returncode == 0, r.output
    n = run_script("task_set", run_dir.path, "new", "--from-answer", FV, "--place", got[0]["key"])
    assert n.returncode == 0, n.output
    return got[0]["key"], n.stdout.strip().splitlines()[-1]


def test_fix_gets_origin_paths_and_fixed_criterion(run_dir, repo):
    key, tid = fix_from_answer(run_dir, repo)
    t = run_dir.tasks()[tid]
    assert t["kind"] == "fix" and t["flow"] == "reading" and t["parent"] == FV
    assert re.fullmatch(r"사용자 {} \d{{4}}-\d\d-\d\d \d\d:\d\d:\d\d 코드 확인 {}".format(FV, re.escape(key)), t["origin"])
    assert "src/a.ts" in t["_sections"]["건드릴 파일"]
    assert "도우미 이름을 바꾼다" in t["_sections"]["범위"]
    assert "원문의 요구가 변경에 빠짐없이, 그보다 넓지 않게 반영됨" in t["_sections"]["판정 기준"]


def test_fix_from_a_code_check_is_not_notified_and_shows_the_change(run_dir, repo):
    _, tid = fix_from_answer(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--status", "완료", "--record", "승인|승인|승인합니다")
    path = run_dir.task_dir(tid) / "task.md"
    path.write_text(path.read_text(encoding="utf-8").replace("status: 대기", "status: 자체검증\nstarted_version: 1.2.0-dev.1\nrules: 2"), encoding="utf-8")
    run_dir.result(tid, result())
    judged(run_dir, tid)
    write(repo / "src" / "a.ts", BODY.replace("line60", "renamed60"))
    assert screen.notify_status(str(run_dir.path), tid)[0] is False
    out = run_script("screen", run_dir.path, tid).stdout
    assert "알림 조건: 미충족(사용자 원문" in out
    assert "■ 코드 확인에서 고친 코드" in out and "도우미 이름을 바꾼다" in out and "renamed60" in out


def test_fix_on_a_new_harness_quotes_the_answer_and_still_asks(run_dir, repo, monkeypatch):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|이 코드만 고침 : 이름을 바꾼다|2 이 코드만 고침 : 이름을 바꾼다".format(got[0]["key"]))
    monkeypatch.setattr(lib, "harness_version", lambda *a: "1.2.0-dev.1")
    assert task_set.main(["task_set.py", str(run_dir.path), "new", "--from-answer", FV, "--place", got[0]["key"]]) == 0
    t = next(o for o in run_dir.tasks().values() if o["kind"] == "fix")
    assert lib.answer_is_judged(t) and "2 이 코드만 고침 : 이름을 바꾼다" in t["_sections"]["판정 기준"]
    assert t["origin"].endswith("코드 확인 " + got[0]["key"])


def test_fix_needs_the_fix_answer_first(run_dir, repo):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|1".format(got[0]["key"]))
    assert run_script("task_set", run_dir.path, "new", "--from-answer", FV, "--place", got[0]["key"]).returncode == 3


def test_fix_after_the_flow_review_makes_no_new_place(run_dir, repo):
    _, tid = fix_from_answer(run_dir, repo)
    code(run_dir, tid, "- 다른 판단 [종류: 구조] [위치: src/a.ts:3]\n", sha=git(repo, "rev-parse", "--short", "HEAD"), kind="fix", parent=FV)
    assert all(p["task"] != tid for p in places.collect(str(run_dir.path), FV))


def test_plain_from_answer_ignores_code_check_lines(run_dir, repo):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|1".format(got[0]["key"]))
    write(run_dir.path / "body.md", "## 범위\n- 고침\n## 판정 기준\n1. 기준\n## 건드릴 파일\n- src/a.ts\n")
    n = run_script("task_set", run_dir.path, "new", "--from-answer", FV, "--title", "고침", "--body-from", run_dir.path / "body.md", "--flow", "reading")
    assert n.returncode == 3 and "원문" in n.output


def test_code_check_answer_is_not_an_approval(run_dir, repo):
    got = one_place(run_dir, repo)
    run_script("task_set", run_dir.path, FV, "--record", "코드 확인 {}|문제 없음|승인 (문제 없음)".format(got[0]["key"]))
    t = run_dir.tasks()[FV]
    assert lib.prior_approval(t) is False and lib.has_quoted_answer(t) is False
    assert screen.CODE_CHECK_ORIGIN == lib.CODE_CHECK_ORIGIN


def test_leaving_the_wait_adds_no_key_to_an_old_task(run_dir):
    run_dir.task("T001", "옛 설계", kind="design", status="승인대기", **OLD)
    assert run_script("task_set", run_dir.path, "T001", "--status", "보류", "--reason", "둔다").returncode == 0
    assert "card_open" not in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")


def test_wrap_up_summary_is_empty_without_places(run_dir):
    assert places.run_left(str(run_dir.path)) == {"count": 0, "where": [], "problems": []}
