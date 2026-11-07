"""1.2.0 A7: 흐름 리뷰(설계 7.1절, 5.1절의 `flow-verify` 행).

- 1.2.0부터 시작한 흐름별 검증은 실행 판정을 요구하고, `judge-run.md` 「흐름 리뷰 전·후」를 화면에 싣는다.
- 돌리지 못한 시나리오는 「확인 안 된 것」으로 가고, 값이 비거나 못 읽으면 "재지 못함"이다.
- 전·후 명령은 `recon.md`와 승인된 실행 전체 설계에서 읽는다.
- 칸 밖의 새 줄은 `--answer` 해석에 칸으로 읽히지 않고, 재현한 값은 가린 뒤 자른다.
- 옛 판본으로 시작한 흐름별 검증은 지금 규칙 그대로다.
"""
import re
import time
from datetime import datetime

import pytest

import board
import collect
import devflow_lib as lib
import flow_review
import kinds
import places
import screen
import visual
from conftest import run_script, write
from test_code_check import FV, code, git, repo as repo  # noqa: F401  같은 재료를 쓴다
from test_domain_paths import READ_JUDGE, RUN_JUDGE
from test_review_contract import NEW, OLD, result

PAIR = ("## 흐름 리뷰 전·후\n### 신청 상세 보기\n- 전: 단계 1 결과에 칸 전부\n- 후: 접수번호와 고객 이름만\n"
        "- 명령: `npm run demo`\n- 로그: logs\\a.txt\n"
        "### 없는 칸 검사\n- 돌리지 못함: 환경이 없음 | 언어 모델 에이전트가 필요\n- 대신: 칸 이름 대조를 시험이 확인함\n")


def run_file(tid, section=PAIR, now=None):
    now = now or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return RUN_JUDGE.split("\n## 흐름 리뷰")[0].replace("T001", tid).format(now=now) + "\n" + section


def flow_verify(run_dir, section=PAIR, status="승인대기", meta=NEW, material="운영자가 칸을 적으면 응답에 그 칸만 나옵니다.", picked=2, cells=None, **more):
    run_dir.flow("reading", status="폴더 있음", base_commit="abc")
    run_dir.task(FV, "흐름별 검증", kind="flow-verify", block="검증", status=status, flow="reading", **dict(meta, **more))
    body = result(**(cells or {})).replace("## 판단\n- 없음\n", "")
    if material is not None:
        body = body.replace("### 정해 주실 것", "### 리뷰 자료\n{}\n\n### 정해 주실 것".format(material))
    if picked is not None:
        body += "\n## 돌려 볼 시나리오\n" + "".join("- 장면 {}\n".format(n) for n in range(picked))
    run_dir.result(FV, body)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge(FV, READ_JUDGE.replace("T001", FV).format(now=now))
    if section is not None:
        write(run_dir.task_dir(FV) / "judge-run.md", run_file(FV, section, now))


def screen_text(run_dir, tid=FV):
    p = run_script("screen", run_dir.path, tid)
    assert p.returncode == 0, p.output
    return p.stdout


# ---------------------------------------------------------------- 판본 문턱과 5.1절

def test_new_flow_verify_needs_the_run_judge_and_old_does_not(run_dir, lib):
    flow_verify(run_dir)
    run_dir.task("T091", "옛 검증", kind="flow-verify", block="검증", flow="reading", **OLD)
    tasks = run_dir.tasks()
    assert lib.required_judges(tasks[FV]) == {"read", "run"}
    assert lib.required_judges(tasks["T091"]) == {"read"}
    assert kinds.KINDS["flow-verify"].run_judge == "always"
    assert kinds.KINDS["full-verify"].run_judge == "never"
    assert "run" not in lib.required_judges(dict(tasks["T091"], kind="reverify", started_version="1.2.0-dev.1"))


def test_missing_run_file_or_section_stops_approval(run_dir):
    flow_verify(run_dir, section=None)
    ok, why = lib.judges_present(run_dir.tasks()[FV])
    assert not ok and "judge-run.md 없음" in why
    write(run_dir.task_dir(FV) / "judge-run.md", run_file(FV, ""))
    ok, why = lib.judges_present(run_dir.tasks()[FV])
    assert not ok and "흐름 리뷰 전·후" in why


def test_nothing_run_does_not_stop_the_run(run_dir):
    # 전부 돌리지 못해도 멈추지 않는다: 절과 근거가 있으면 판정이 끝난 것이다(run-check.md 끝 문단)
    only = "## 흐름 리뷰 전·후\n### 장면\n- 돌리지 못함: 환경이 없음 | 서버 없음\n- 대신: 단위 시험이 확인함\n"
    flow_verify(run_dir, section=only)
    assert lib.judges_present(run_dir.tasks()[FV]) == (True, "")
    assert not lib.item_count(lib.sections(lib.read_text(run_dir.task_dir(FV) / "judge-run.md")).get("통과 못 한 기준", ""))


def test_flow_verify_always_asks(run_dir):
    # 5.1절 `flow-verify` 행: 칸이 모두 비어도 묻는다
    flow_verify(run_dir)
    b = screen.build(str(run_dir.path), FV)
    assert not b["notify_ok"] and not b["notify_kind"]
    ok, why = screen.notify_status(str(run_dir.path), FV)
    assert not ok and "알림으로 지나가지 않는다" in why


def test_old_flow_verify_screen_is_as_before(run_dir):
    flow_verify(run_dir, meta=OLD, material=None, picked=None)
    out = screen_text(run_dir)
    for word in ("답할 것", "코드 ", "■ 이 흐름이 한 일", "실제로 돌려 본 결과", "근거(접어 둠)", "전·후"):
        assert word not in out, word
    assert not (run_dir.task_dir(FV) / flow_review.REVIEW_FILE).exists()
    assert run_script("screen", run_dir.path, FV, "--flow-commands").returncode == 2
    assert visual.flow_review_head(str(run_dir.path), run_dir.tasks()[FV]) == []
    assert lib.required_judges(run_dir.tasks()[FV]) == {"read"}


# ---------------------------------------------------------------- 화면의 차례

def test_screen_order_and_head_lines(run_dir):
    flow_verify(run_dir, cells={"notify": "- [T040] 줄 구분을 넣음"})
    out = screen_text(run_dir)
    at = [out.index(w) for w in ("정하는 것:", "답할 것 ", "코드 0군데, 설계대로 0, 판단 있음 0, 안 보여 드림 0", "■ 이 흐름이 한 일", "■ 실제로 돌려 본 결과",
                                 "■ 알릴 것", "■ 확인 안 된 것", "근거(접어 둠)", "counts:")]
    assert at == sorted(at)
    assert "  운영자가 칸을 적으면 응답에 그 칸만 나옵니다." in out
    assert "■ 리뷰 자료" not in out


def test_before_and_after_and_not_run_lines(run_dir):
    flow_verify(run_dir)
    out = screen_text(run_dir)
    assert "■ 실제로 돌려 본 결과 (시나리오 2: 돌림 1, 돌리지 못함 1)" in out
    assert "  ▸ 신청 상세 보기\n    전: 단계 1 결과에 칸 전부\n    후: 접수번호와 고객 이름만" in out
    assert "  ▸ 없는 칸 검사\n    돌리지 못함: 환경이 없음 | 언어 모델 에이전트가 필요\n    시험이 대신 확인한 것: 칸 이름 대조를 시험이 확인함" in out
    assert "- [1] [돌리지 못함] 없는 칸 검사: 환경이 없음 | 언어 모델 에이전트가 필요" in out
    assert "n_unverified=1" in out


@pytest.mark.parametrize("section, word", [
    (None, "judge-run.md 없음"),
    ("", "절 없음"),
    ("## 흐름 리뷰 전·후\n- 없음\n", "시나리오 없음"),
])
def test_unread_results_are_not_shown_as_none(run_dir, section, word):
    flow_verify(run_dir, section=section)
    out = screen_text(run_dir)
    assert "■ 실제로 돌려 본 결과: 재지 못함(" in out and word in out
    assert "[돌리지 못함] 전·후 전체: 재지 못함" in out


def test_scenario_with_no_fields_is_unread(run_dir):
    flow_verify(run_dir, section="## 흐름 리뷰 전·후\n### 장면\n아무 말\n", picked=1)
    out = screen_text(run_dir)
    assert "재지 못함: 전·후도, 돌리지 못한 이유도 적지 않음" in out
    assert "- [1] [돌리지 못함] 장면: 재지 못함(전·후도, 이유도 적지 않음)" in out
    assert "! 읽지 못한 줄: 아무 말" in out


def test_partial_scenario_and_missing_writer_list(run_dir):
    section = "## 흐름 리뷰 전·후\n### 장면\n- 전: 돌리지 못함: 새 명령이 필요함 | 기준본 띄우기\n- 후: 두 칸\n"
    flow_verify(run_dir, section=section, picked=None)
    out = screen_text(run_dir)
    assert "(시나리오 1: 일부 1)" in out
    assert "    전: 돌리지 못함: 새 명령이 필요함 | 기준본 띄우기\n    후: 두 칸" in out
    assert "- [1] [전·후 일부만] 장면: 새 명령이 필요함 | 기준본 띄우기" in out
    assert "! 작성자가 「돌려 볼 시나리오」를 쓰지 않음" in out


def test_fewer_results_than_picked(run_dir):
    flow_verify(run_dir, picked=3)
    assert "! 고른 시나리오 3개 가운데 결과 2개" in screen_text(run_dir)


def test_missing_material_is_unread_not_empty(run_dir):
    flow_verify(run_dir, material=None)
    out = screen_text(run_dir)
    assert "■ 이 흐름이 한 일\n  재지 못함: 작성자가 「리뷰 자료」를 쓰지 않았다" in out
    assert "! 리뷰 자료 없음" in out


# ---------------------------------------------------------------- 읽는 꼴

@pytest.mark.parametrize("section, before, after", [
    ("### 장면\n- **전**: 칸 전부\n- **후**: 두 칸\n", "칸 전부", "두 칸"),
    ("### **장면**\n**전:** 칸 전부\n**후:** 두 칸\n", "칸 전부", "두 칸"),
    ("- 시나리오: 장면\n  전: 칸 전부\n  후: 두 칸\n", "칸 전부", "두 칸"),
    ("| 시나리오 | 전 | 후 | 명령 |\n|---|---|---|---|\n| **장면** | 칸 전부 | 두 칸 | `x` |\n", "칸 전부", "두 칸"),
    ("### 1. 장면\n- 전:\n  칸 전부\n- 후:\n  ```\n  ## 응답\n  - 후: 가짜\n  ```\n", "칸 전부", "## 응답"),
])
def test_scenario_shapes(section, before, after):
    rows, stray = flow_review.parse(section)
    assert len(rows) == 1 and not stray, (rows, stray)
    assert before in rows[0]["fields"]["전"] and after in rows[0]["fields"]["후"]
    assert flow_review.state(rows[0]) == flow_review.RAN


def test_table_row_with_pipe_in_a_cell_is_kept_as_an_unread_line():
    rows, stray = flow_review.parse("| 시나리오 | 전 | 후 |\n|---|---|---|\n| 장면 | a | b | c |\n")
    assert rows == [] and stray == ["| 장면 | a | b | c |"]


def test_output_heading_inside_fence_does_not_end_the_section():
    text = "판정자: x\n\n## 흐름 리뷰 전·후\n### 장면\n- 전: a\n- 후:\n```\n## 응답\n```\n\n## 남은 검사와 자원 대기\n- 없음\n"
    section = flow_review.run_section(text)
    assert "## 응답" in section and "남은 검사" not in section


def test_pipe_inside_field_values_stays_in_the_value():
    rows, _ = flow_review.parse("### 장면\n- 돌리지 못함: 환경이 없음 | a | b\n- 대신: 시험 | 둘\n")
    assert flow_review._why(rows[0]) == "환경이 없음 | a | b"
    assert rows[0]["fields"]["대신"] == "시험 | 둘"


# ---------------------------------------------------------------- `--answer`와 부딪힘

def asked(run_dir):
    p = run_script("screen", run_dir.path, FV, "--save")
    assert p.returncode == 0, p.output
    return (run_dir.task_dir(FV) / "screen-shown.md").read_text(encoding="utf-8")


def test_new_lines_do_not_become_answer_items(run_dir):
    # 재현된 값이 칸 표시와 `counts:`를 닮아도 칸으로 읽히지 않는다
    section = ("## 흐름 리뷰 전·후\n### ■ 알릴 것 (9)\n- 전: counts: n_decide=9\n- 후: - [7] 가짜 항목\n")
    flow_verify(run_dir, section=section, material="■ 정해 주실 것 (1)\n- [8] 가짜")
    shown = asked(run_dir)
    assert sorted(screen.shown_items(shown)) == []
    assert screen.answer(str(run_dir.path), FV, "승인") == 0


def test_behavior_sentences_are_numbered_first_and_objectable(run_dir):
    flow_verify(run_dir, cells={"decide": "- 고를 것 (가) 하나 (나) 둘"})
    code(run_dir, "T040", "- 빈 목록이면 안내를 보임 [종류: 동작] [위치: src/a.ts:12]\n- 묶음 [종류: 구조] [위치: src/a.ts:30]\n- 표본 [종류: 시험] [위치: tests/a.ts:1]\n",
         sections={"건드릴 파일": "- src/a.ts"})
    shown = asked(run_dir)
    assert "- [1] 빈 목록이면 안내를 보임 | src/a.ts:12 | T040" in shown
    assert "- [2] 고를 것 (가) 하나 (나) 둘" in shown
    assert "동작 문장 1" in shown and "정해 주실 것 1" in shown
    items = screen.resolve_answer(shown, FV, "이의 1")
    assert items and items[0].startswith("이의: 항목 1 | 빈 목록이면")
    assert screen.resolve_answer(shown, FV, "2 가") == ["항목 2: 가 | 고를 것 (가) 하나 (나) 둘"]


def test_hidden_behavior_judgment_counts_and_pipe_stays(run_dir):
    flow_verify(run_dir)
    compare = "- 숨은 판단: src/b.ts:4 | 재시도 | 한 번 더 | 동작\n"
    code(run_dir, "T040", "- 없음\n", compare=compare)
    out = screen_text(run_dir)
    assert "- [1] 재시도 | 한 번 더 | src/b.ts:4 | T040" in out


# ---------------------------------------------------------------- 코드 머리 줄

def test_code_line_counts_places_design_and_left(run_dir, repo):
    sha = git_commit(repo, "src/a.ts", "x\n")
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    judged = "".join("- 판단 {n} [종류: 구조] [위치: src/f{n}.ts:1]\n".format(n=n) for n in range(7))
    code(run_dir, "T040", judged, sha=sha, sections={"건드릴 파일": "- src/a.ts"})
    code(run_dir, "T041", "- 없음\n", sha=sha)
    assert run_script("screen", run_dir.path, FV, "--places").returncode == 0
    plist = places.read(str(run_dir.path), FV)
    left = sum(1 for p in plist if p["처리"].startswith("남김"))
    assert left == 2 and len(plist) == 7
    assert "코드 5군데, 설계대로 1, 판단 있음 1, 안 보여 드림 2" in screen_text(run_dir)


def point_flow(run_dir, repo):
    run_dir.flow("reading", status="폴더 있음", base_commit="abc", dir=str(repo))


def git_commit(repo, path, text):
    write(repo / path, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "변경")
    return git(repo, "rev-parse", "--short", "HEAD")


def test_code_line_is_unread_before_places_or_with_old_tasks(run_dir, repo):
    sha = git_commit(repo, "src/a.ts", "x\n")
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    code(run_dir, "T040", "- 판단 [종류: 구조] [위치: src/a.ts:1]\n", sha=sha)
    assert "코드: 재지 못함(`--places`를 돌리기 전)" in screen_text(run_dir)
    run_dir.task("T030", "옛 구현", kind="implementation", block="구현", status="완료", flow="reading", **OLD)
    assert run_script("screen", run_dir.path, FV, "--places").returncode == 0
    assert ", 재지 못함 T030" in screen_text(run_dir)


# ---------------------------------------------------------------- 사람이 볼 곳, 근거, 답의 반영

def test_people_lines_and_unread(run_dir):
    flow_verify(run_dir)
    code(run_dir, "T040", "- 없음\n", compare="- 사람이 볼 곳: domain/quote.ts:92 | 금액의 유일한 계산 지점이 바뀜 | 둘\n")
    code(run_dir, "T041", "- 없음\n", compare="- 사람이 볼 곳: 지목 없음\n")
    out = screen_text(run_dir)
    assert "■ 사람이 볼 곳 (판정자 지목 1)\n  T040 domain/quote.ts:92: 금액의 유일한 계산 지점이 바뀜 | 둘" in out
    (run_dir.task_dir("T041") / "judge.md").unlink()
    assert "! 사람이 볼 곳을 재지 못함: T041(지목 줄 없음)" in screen_text(run_dir)


AC_TABLE = ("\n## 본문\n| 인수 기준 | 확인 방법 | 판정 | 근거 |\n|---|---|---|---|\n"
            "| E-AC-1 | 시험 | 통과 | a:1 |\n| **E-AC-2** | 시험 | **부분 통과** | b:2 |\n"
            "| AC-QY-3 | 순 변경 | 판정불가 | c |\n| E-AC-4 | 실패 경로 | 통과 | d |\n| E-AC-5 | 두 칸 | 넷 | 실패 | e |\n")


def test_evidence_counts_real_table_rows_and_writes_review_file(run_dir):
    flow_verify(run_dir)
    path = run_dir.task_dir(FV) / "result.md"
    path.write_text(path.read_text(encoding="utf-8") + AC_TABLE + "\n표 밖의 글\n\n| 010-1234-5678 전화 | 줄 |\n", encoding="utf-8")
    write(run_dir.task_dir(FV) / "notified-reading.md", "## [T040] 구현\n연락처 010-1234-5678\n")
    out = screen_text(run_dir)
    assert "근거(접어 둠): 인수 기준 표 5행: 통과 2, 부분 통과 1, 실패 1, 판정불가 1 → " in out
    review = (run_dir.task_dir(FV) / "review.md").read_text(encoding="utf-8")
    assert "| **E-AC-2** |" in review and "## [T040] 구현" in review and "010-1234-5678" not in review


def test_evidence_says_unread_without_a_table_or_notified_file(run_dir):
    flow_verify(run_dir)
    assert "근거(접어 둠): 인수 기준 표 재지 못함 → " in screen_text(run_dir)
    review = (run_dir.task_dir(FV) / "review.md").read_text(encoding="utf-8")
    assert "재지 못함: 인수 기준 표를 읽지 못함" in review and "재지 못함: notified-reading.md 없음" in review


def test_code_task_answers_reach_the_cell_once(run_dir):
    flow_verify(run_dir, cells=None)
    code(run_dir, "T040", "- 없음\n")
    path = run_dir.task_dir("T040") / "result.md"
    path.write_text(path.read_text(encoding="utf-8").replace("### 답하신 것의 반영\n- 없음", "### 답하신 것의 반영\n- 조회 정의 대신 표시 칸"), encoding="utf-8")
    out = screen_text(run_dir)
    assert "[T040] 조회 정의 대신 표시 칸" in out and "■ 답하신 것의 반영 (1)" in out


# ---------------------------------------------------------------- 가림

def test_replayed_values_are_masked_before_clipping(run_dir):
    token = "ghp_" + "a" * 40
    long_tail = "가" * 158
    section = "## 흐름 리뷰 전·후\n### 장면\n- 전: {} {}\n- 후: password=hunter2secret\n- 명령: x\n".format(long_tail, token)
    flow_verify(run_dir, section=section, picked=1)
    out = screen_text(run_dir)
    assert "ghp_" not in out and "hunter2secret" not in out and "password=[가림]" in out
    assert long_tail[:20] in out


def test_private_key_block_in_output_is_masked(run_dir):
    section = "## 흐름 리뷰 전·후\n### 장면\n- 전: -----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n- 후: 끝\n"
    flow_verify(run_dir, section=section, picked=1)
    assert "abc" not in screen_text(run_dir).split("■ 실제로 돌려 본 결과")[1].split("■")[0]


# ---------------------------------------------------------------- 전·후 명령

RECON = "# 프로젝트 정찰\n\n## 스택과 명령\n- npm test\n\n## 공유 자원과 잠금\n- devdb:lock\n"


def commands(run_dir):
    p = run_script("screen", run_dir.path, FV, "--flow-commands")
    assert p.returncode == 0, p.output
    return p.stdout


def test_no_run_wide_design_uses_recon_only(run_dir):
    flow_verify(run_dir)
    write(run_dir.path / "recon.md", RECON)
    out = commands(run_dir)
    assert "「스택과 명령」 「공유 자원과 잠금」" in out
    assert "실행 전체 설계 없음: recon.md의 명령만 쓴다" in out


def test_no_recon_is_unread(run_dir):
    flow_verify(run_dir)
    assert "recon.md: 재지 못함(파일 없음)" in commands(run_dir)


def wide(run_dir, status="완료", doc="# 실행 전체\n\n## 흐름 리뷰의 전·후를 띄울 명령\n- `npm run preview --prefix base`\n- `deploy --host prod.example.com`\n\n## 그 밖\n- 다른 줄\n"):
    run_dir.task("T005", "실행 전체 설계", {"건드릴 파일": "- design/run.md"}, kind="design", block="설계", status=status, run_wide="true", **NEW)
    if doc is not None:
        write(run_dir.path / "design" / "run.md", doc)


def test_approved_run_wide_commands_are_read_and_ops_marks_stop_them(run_dir):
    flow_verify(run_dir)
    write(run_dir.path / "recon.md", RECON)
    wide(run_dir)
    write(run_dir.path.parent / "devflow-harness.project.md", "# 설정\n\n## 경로 목록\n- 운영 표지: prod.example.com, *secret*\n")
    out = commands(run_dir)
    assert "실행 전체 설계 T005: design/run.md 「흐름 리뷰의 전·후를 띄울 명령」" in out
    assert "  - `npm run preview --prefix base`" in out
    assert "  ! 돌리지 않음(운영 표지 prod.example.com): - `deploy --host prod.example.com`" in out
    assert "다른 줄" not in out


def test_unapproved_or_silent_run_wide_design_gives_no_commands(run_dir):
    flow_verify(run_dir)
    wide(run_dir, status="승인대기")
    out = commands(run_dir)
    assert "실행 전체 설계 T005: 아직 승인 전(승인대기)" in out and "npm run preview" not in out
    wide(run_dir, doc="# 실행 전체\n\n## 흐름 지도\n- a\n")
    assert "실행 전체 설계 T005: 전·후 명령 절 없음" in commands(run_dir)


def test_exclusions_reach_the_commands_and_the_review_head(run_dir):
    flow_verify(run_dir)
    path = run_dir.path / "run.md"
    path.write_text(path.read_text(encoding="utf-8").replace("| 수정 세대 상한 | 2 |\n", '| 수정 세대 상한 | 2 |\n| 검증 제외 | 변이시험 \\| 이번 세션 \\| 끝까지 \\| 원문 "제외" |\n'), encoding="utf-8")
    assert '검증 제외: 변이시험 | 이번 세션 | 끝까지 | 원문 "제외"' in commands(run_dir)
    p = run_script("visual", run_dir.path, FV)
    assert p.returncode == 0, p.output
    assert "■ 사람 지시로 뺀 검증" in p.stdout and "변이시험" in p.stdout


# ---------------------------------------------------------------- 지도의 자리

def test_map_place_comes_before_the_seen_material(run_dir):
    flow_verify(run_dir)
    run_dir.flow("other")
    out = run_script("visual", run_dir.path, FV).stdout
    assert out.index("실행 지도: 흐름 2개 가운데 하나") < out.index("■ 보는 자료")


def test_flow_not_on_the_map_is_unread(run_dir):
    flow_verify(run_dir)
    (run_dir.path / "flows" / "reading" / "flow.md").unlink()
    run_dir.flow("reading", role="deploy")
    assert "실행 지도: 재지 못함(흐름 reading가 지도에 없음)" in run_script("visual", run_dir.path, FV).stdout


# ---------------------------------------------------------------- 시험 변화의 보류 줄

def held_code(run_dir, status="보류"):
    run_dir.task("T041", "보류한 구현", kind="implementation", block="구현", status=status, flow="reading", **NEW)
    run_dir.result("T041", result())
    write(run_dir.task_dir("T041") / lib.TEST_CHANGES, "- 끄기 | a.test.ts:1 | it.skip\n")


@pytest.mark.parametrize("status", ["보류", "백로그"])
def test_held_code_test_rows_do_not_stop_the_flow_and_stay_visible(run_dir, status):
    flow_verify(run_dir, partial_flow="true")
    held_code(run_dir, status)
    tasks = run_dir.tasks()
    assert lib.flow_test_rows(tasks[FV], tasks) == []
    assert lib.unanswered_test_removals(tasks[FV]) == []
    assert places.completion_block(str(run_dir.path), tasks[FV]) == ""
    assert "보류·백로그 코드 task의 시험 변화 1줄은 이 검증에서 묻지 않습니다(마무리 리뷰에 남습니다): T041" in screen_text(run_dir)
    assert any("a.test.ts:1" in line for line in lib.wrap_up_test_lines(tasks))


def test_done_code_test_rows_are_still_asked(run_dir):
    flow_verify(run_dir)
    code(run_dir, "T040", "- 없음\n", test_lines="- 끄기 | a.test.ts:1 | it.skip\n")
    tasks = run_dir.tasks()
    assert len(lib.flow_test_rows(tasks[FV], tasks)) == 1
    assert "시험 변화 1" in screen_text(run_dir)


# ---------------------------------------------------------------- 뒤로 남는 길

def test_not_run_scenario_reaches_the_unverified_list(run_dir, workspace):
    flow_verify(run_dir, status="완료", approved="2026-11-05 10:00:00")
    out = workspace / "out"
    out.mkdir()
    assert collect.main(["collect.py", str(run_dir.path), str(out)]) in (0, None)
    text = (out / "unverified-list.md").read_text(encoding="utf-8")
    assert "- [돌리지 못함] 없는 칸 검사: 환경이 없음 | 언어 모델 에이전트가 필요" in text


# ---------------------------------------------------------------- 한 장

def test_sheet_has_the_flow_review_blocks_and_escapes(run_dir, repo):
    sha = git_commit(repo, "db/migrations/1.sql", "create table <t>(id int);\n")
    section = ("## 흐름 리뷰 전·후\n### <b>장면</b>\n- 전: <script>x</script>\n- 후: 연락처 010-1234-5678\n- 캡처: logs\\a.png, ../../x.png\n")
    flow_verify(run_dir, section=section, picked=1)
    point_flow(run_dir, repo)
    code(run_dir, "T040", "- 없음\n", sha=sha, compare="- 사람이 볼 곳: db/migrations/1.sql:1 | 표가 바뀜\n", sections={"건드릴 파일": "- src/other.ts"})
    write(run_dir.task_dir(FV) / "logs" / "a.png", "png")
    page, hidden = visual.sheet_html(str(run_dir.path), lib.load_task(str(run_dir.task_dir(FV) / "task.md")) | {"id": FV})
    assert "<script>x" not in page and "&lt;script&gt;x" in page and "010-1234-5678" not in page
    assert hidden >= 1
    assert "<img" in page and "a.png" in page and "캡처 없음: ../../x.png" in page
    for word in ("코드 요약", "규모: 파일 1개, +1 -0", "새 폴더 db/migrations", "규약 추가: 0건", "경계 위반: 이 요약은 재지 않는다", "사람이 볼 곳: T040 db/migrations/1.sql:1: 표가 바뀜",
                 "API·데이터 모델 변경분", "create table &lt;t&gt;", "남긴 곳", "설계 제안과 다른 곳", "db/migrations/1.sql"):
        assert word in page, word


def test_sheet_says_unread_when_commits_are_missing(run_dir):
    flow_verify(run_dir, section=None, picked=None, material=None)
    code(run_dir, "T040", "- 없음\n")
    page, _ = visual.sheet_html(str(run_dir.path), lib.load_task(str(run_dir.task_dir(FV) / "task.md")) | {"id": FV})
    assert "재지 못함: T040(커밋을 읽지 못함)" in page
    assert "재지 못함</p>" in page or "재지 못함: judge-run.md 없음" in page
    assert "사람이 볼 곳을 재지 못함: T040" in page and "사람이 볼 곳: 지목 없음" not in page


def test_sheet_failure_does_not_stop_the_approval(run_dir, monkeypatch, capsys):
    flow_verify(run_dir)
    def broken(*_):
        raise lib.Reject("머리 파일을 읽지 못함")
    monkeypatch.setattr(visual, "_flow_blocks", broken)
    assert visual.sheet(str(run_dir.path), FV) == 0
    assert "한 장 없음: 머리 파일을 읽지 못함" in capsys.readouterr().out


def test_value_with_underscores_keeps_its_letters():
    rows, _ = flow_review.parse("### 장면\n- 전: __init__\n- 후: **두 칸**\n")
    assert rows[0]["fields"] == {"전": "__init__", "후": "두 칸"}


def test_old_flow_verify_sheet_is_as_before(run_dir):
    flow_verify(run_dir, meta=OLD, material=None, picked=None)
    assert visual.sheet_html(str(run_dir.path), lib.load_task(str(run_dir.task_dir(FV) / "task.md")) | {"id": FV}) == (None, 0)


# ---------------------------------------------------------------- 재시도

def test_retry_archives_the_run_file_and_asks_for_a_new_one(run_dir):
    flow_verify(run_dir, status="자체검증")
    p = run_script("task_set", run_dir.path, FV, "--archive-judge")
    assert p.returncode == 0, p.output
    assert not (run_dir.task_dir(FV) / "judge-run.md").exists()
    ok, why = lib.judges_present(run_dir.tasks()[FV])
    assert not ok and "judge-run.md 없음" in why
    assert "[돌리지 못함] 전·후 전체: 재지 못함(judge-run.md 없음)" in screen_text(run_dir)


def test_cli_answer_runs_on_the_saved_review_screen(run_dir):
    flow_verify(run_dir)
    assert run_script("screen", run_dir.path, FV, "--save").returncode == 0
    p = run_script("screen", run_dir.path, FV, "--answer", "승인")
    assert p.returncode == 0 and "전체: 승인" in p.stdout


# ---------------------------------------------------------------- 코드 리뷰 지적

FENCED = "## 흐름 리뷰 전·후\n### 장면\n- 전:\n```\nHTTP 200 칸 전부\n```\n- 후:\n  ~~~\n  HTTP 200 두 칸\n  ~~~\n"


def test_fenced_values_show_their_content_on_the_screen(run_dir):
    flow_verify(run_dir, section=FENCED, picked=1)
    out = screen_text(run_dir)
    assert "    전: HTTP 200 칸 전부\n    후: HTTP 200 두 칸" in out
    assert "(시나리오 1: 돌림 1)" in out


def test_empty_fence_is_not_a_run(run_dir):
    flow_verify(run_dir, section="## 흐름 리뷰 전·후\n### 장면\n- 전:\n```\n```\n- 후:\n```\n```\n", picked=1)
    assert "[돌리지 못함] 장면: 재지 못함" in screen_text(run_dir)


def test_other_fence_mark_inside_a_fence_does_not_close_it():
    rows, stray = flow_review.parse("### 가\n- 전:\n```\nx\n~~~\n### 안쪽\n```\n- 후: b\n")
    assert [r["name"] for r in rows] == ["가"] and not stray
    assert rows[0]["fields"]["후"] == "b"


def committed_held(run_dir, repo, status="보류", answer=None):
    sha = git_commit(repo, "a.test.ts", "it.skip\n")
    code(run_dir, "T041", "- 없음\n", sha=sha, test_lines="- 끄기 | a.test.ts:1 | it.skip\n")
    p = run_dir.task_dir("T041") / "task.md"
    p.write_text(p.read_text(encoding="utf-8").replace("status: 완료", "status: " + status), encoding="utf-8")
    return sha


@pytest.mark.parametrize("status", ["보류", "백로그"])
def test_held_task_with_a_commit_is_asked_and_blocks(run_dir, repo, status):
    flow_verify(run_dir, partial_flow="true")
    point_flow(run_dir, repo)
    committed_held(run_dir, repo, status)
    tasks = run_dir.tasks()
    assert [r["task"] for r in lib.flow_test_rows(tasks[FV], tasks)] == ["T041"]
    assert lib.held_test_rows(tasks[FV], tasks) == []
    assert "답 없는 시험 끄기" in places.completion_block(str(run_dir.path), tasks[FV])
    out = screen_text(run_dir)
    assert "시험 변화 1" in out and "이 검증에서 묻지 않습니다" not in out


def test_held_task_with_a_commit_is_never_counted_as_designed(run_dir, repo):
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    committed_held(run_dir, repo)
    assert run_script("screen", run_dir.path, FV, "--places").returncode == 0
    assert "설계대로 0, 판단 있음 0, 안 보여 드림 0, 재지 못함 T041" in screen_text(run_dir)


def test_held_rows_count_only_unanswered_asked_rows(run_dir):
    flow_verify(run_dir, partial_flow="true")
    run_dir.task("T041", "보류", kind="implementation", block="구현", status="보류", flow="reading", **NEW)
    run_dir.result("T041", result())
    write(run_dir.task_dir("T041") / lib.TEST_CHANGES, "- 끄기 | a.test.ts:1 | it.skip\n- 삭제 | c.test.ts | 파일\n- {} | b.test.ts:1 | 새 시험\n".format(lib.TEST_COUNT_ONLY))
    tasks = run_dir.tasks()
    rows = lib.test_change_rows(tasks["T041"], tasks)
    asked = [r for r in rows if r["ask"]]
    assert len(asked) == 2 and len(rows) == 3
    assert len(lib.held_test_rows(tasks[FV], tasks)) == len(asked)
    key = asked[0]["key"]
    assert run_script("task_set", run_dir.path, FV, "--record", "{}|{}=받아들임|받아들임".format(lib.TEST_CHANGE_POINT, key)).returncode == 0
    tasks = run_dir.tasks()
    assert len(lib.held_test_rows(tasks[FV], tasks)) == len(asked) - 1


def ops_settings(run_dir, line="- 운영 표지: prod.example.com, *secret*\n"):
    write(run_dir.path.parent / "devflow-harness.project.md", "# 설정\n\n## 경로 목록\n" + line)


def test_production_marks_read_the_path_list_line(run_dir):
    assert lib.production_marks(str(run_dir.path)) == ([], "")
    ops_settings(run_dir, "- 운영 표지: `prod.example.com`, `*secret*`\n")
    assert lib.production_marks(str(run_dir.path))[0] == ["prod.example.com", "*secret*"]
    ops_settings(run_dir, "- 운영 표지: 없음\n")
    assert lib.production_marks(str(run_dir.path))[0] == []
    write(run_dir.path.parent / "devflow-harness.project.md", "# 설정\n\n## 운영 표지\n- prod.example.com\n")
    assert lib.production_marks(str(run_dir.path))[0] == []


def test_empty_marks_say_they_cannot_tell_dev_from_production(run_dir):
    flow_verify(run_dir)
    wide(run_dir)
    out = commands(run_dir)
    assert "운영 표지: 가르지 못함" in out and "돌리지 않음(운영 표지" not in out
    ops_settings(run_dir)
    out = commands(run_dir)
    assert "가르지 못함" not in out and "돌리지 않음(운영 표지 prod.example.com)" in out


def test_production_branch_stops_a_command(run_dir):
    flow_verify(run_dir)
    wide(run_dir, doc="# 실행 전체\n\n## 흐름 리뷰의 전·후 명령\n- `git push origin release`\n- `git push origin release-dev`\n")
    write(run_dir.path.parent / "devflow-harness.project.md", "# 설정\n\n- 운영 브랜치: `release`\n\n## 경로 목록\n- 운영 표지: abcd1234\n")
    out = commands(run_dir)
    assert "돌리지 않음(운영 브랜치 release): - `git push origin release`" in out
    assert "  - `git push origin release-dev`" in out


def finished(run_dir, tid, judgments="- 없음\n", notify=None, **more):
    code(run_dir, tid, judgments, **more)
    if notify:
        p = run_dir.task_dir(tid) / "result.md"
        p.write_text(p.read_text(encoding="utf-8").replace("### 알릴 것\n- 없음", "### 알릴 것\n" + notify), encoding="utf-8")


def code_head(run_dir, tid=FV):
    return next(l for l in screen_text(run_dir, tid).splitlines() if l.startswith("코드"))


def test_designed_counts_only_tasks_with_nothing_to_tell(run_dir, repo):
    sha = git_commit(repo, "src/a.ts", "x\n")
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    code(run_dir, "T040", "- 없음\n", sha=sha)
    code(run_dir, "T041", "- 칸을 나눔 [설계: D-GD-1]\n", sha=sha)
    code(run_dir, "T042", "- 빈 목록이면 안내 [종류: 동작] [위치: src/a.ts:1]\n", sha=sha)
    finished(run_dir, "T043", notify="- 설계와 달라진 점: 캐시를 빼고 직접 조회", sha=sha)
    code(run_dir, "T044", "- 시험 대역 [종류: 시험] [위치: tests/a.ts:1]\n", sha=sha)
    code(run_dir, "T045", "- 없음\n", sha=sha, compare="- 숨은 판단: src/b.ts:1 | 재시도 | 동작\n- 사람이 볼 곳: 지목 없음\n")
    code(run_dir, "T046", "꼴이 어긋난 판단 줄 [종류: 구조]\n", sha=sha)
    code(run_dir, "T047", "- 없음\n", no_change="true")
    assert run_script("screen", run_dir.path, FV, "--places").returncode == 0
    head = code_head(run_dir)
    assert head.startswith("코드 0군데, 설계대로 2, 판단 있음 4, 안 보여 드림 0, 재지 못함 ")
    assert "T046" in head and "T047" in head


def test_unmeasured_task_is_not_designed(run_dir):
    # 코드 폴더가 없으면 보안 신호를 재지 못한다. 그 task는 설계대로가 아니라 재지 못함이다
    flow_verify(run_dir)
    code(run_dir, "T040", "- 없음\n")
    write(run_dir.task_dir(FV) / "places.md", "# 코드 확인 곳: T090 reading\n\n- 위임: 없음\n- 재지 못함: T040\n- 잰 task: T040\n")
    assert code_head(run_dir) == "코드 0군데, 설계대로 0, 판단 있음 0, 안 보여 드림 0, 재지 못함 T040"


def test_second_verify_does_not_turn_an_asked_judgment_into_designed(run_dir, repo):
    sha = git_commit(repo, "src/a.ts", "x\n")
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    code(run_dir, "T040", "- 큰 구조 판단 [종류: 구조] [위치: src/a.ts:1]\n", sha=sha)
    assert run_script("screen", run_dir.path, FV, "--places").returncode == 0
    assert code_head(run_dir).startswith("코드 1군데, 설계대로 0, 판단 있음 1")
    run_dir.task("T092", "둘째 검증", kind="flow-verify", block="검증", status="승인대기", flow="reading", **NEW)
    run_dir.result("T092", (run_dir.task_dir(FV) / "result.md").read_text(encoding="utf-8"))
    assert run_script("screen", run_dir.path, "T092", "--places").returncode == 0
    head = next(l for l in run_script("screen", run_dir.path, "T092").stdout.splitlines() if l.startswith("코드"))
    assert head.startswith("코드 0군데, 설계대로 0, 판단 있음 1")


def test_task_finished_after_the_freeze_is_unread(run_dir, repo):
    sha = git_commit(repo, "src/a.ts", "x\n")
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    assert run_script("screen", run_dir.path, FV, "--places").returncode == 0
    assert "- 잰 task: 없음" in (run_dir.task_dir(FV) / "places.md").read_text(encoding="utf-8")
    code(run_dir, "T044", "- 없음\n", sha=sha)
    assert code_head(run_dir) == "코드 0군데, 설계대로 0, 판단 있음 0, 안 보여 드림 0, 재지 못함 T044"


@pytest.mark.parametrize("before, after, want", [
    ("없음", "없음", flow_review.UNREAD),
    ("-", "N/A", flow_review.UNREAD),
    ("못 돌림", "실행 안 함", flow_review.NOT_RUN),
    ("(돌리지 못함: 서버 없음)", "돌릴 수 없음: 환경 없음", flow_review.NOT_RUN),
    ("**돌리지 못함**: 서버 없음", "`돌리지 못함`", flow_review.NOT_RUN),
    ("칸 전부", "없음", flow_review.UNREAD),
    ("칸 전부", "못 돌림", flow_review.PARTIAL),
    ("돌리지 못함: 새 명령", "두 칸", flow_review.PARTIAL),
    ("없음이라고 응답함", "두 칸", flow_review.RAN),
])
def test_side_words_that_mean_not_run(before, after, want):
    rows, _ = flow_review.parse("### 장면\n- 전: {}\n- 후: {}\n".format(before, after))
    assert flow_review.state(rows[0]) == want


def test_both_sides_with_a_not_run_field_is_partial():
    rows, _ = flow_review.parse("### 장면\n- 전: a\n- 후: b\n- 돌리지 못함: 환경이 없음 | 둘째 경로\n")
    assert flow_review.state(rows[0]) == flow_review.PARTIAL
    assert flow_review._why(rows[0]) == "환경이 없음 | 둘째 경로"


@pytest.mark.parametrize("word", ["없음", "못 돌림", "N/A"])
def test_not_run_words_reach_the_unverified_cell(run_dir, word):
    flow_verify(run_dir, section="## 흐름 리뷰 전·후\n### 장면\n- 전: {0}\n- 후: {0}\n".format(word), picked=1)
    out = screen_text(run_dir)
    assert "[돌리지 못함] 장면: " in out and "돌림 1" not in out


def test_missing_people_line_is_unread_not_none(run_dir):
    flow_verify(run_dir)
    code(run_dir, "T040", "- 없음\n", compare="- 숨은 판단: 없음\n")
    assert "! 사람이 볼 곳을 재지 못함: T040(지목 줄 없음)" in screen_text(run_dir)
    page, _ = visual.sheet_html(str(run_dir.path), lib.load_task(str(run_dir.task_dir(FV) / "task.md")) | {"id": FV})
    assert "사람이 볼 곳: 지목 없음" not in page and "사람이 볼 곳을 재지 못함: T040" in page


def test_more_than_three_people_lines_warn_and_are_all_shown(run_dir):
    flow_verify(run_dir)
    code(run_dir, "T040", "- 없음\n", compare="".join("- 사람이 볼 곳: src/f{0}.ts:1 | 조건 {0}\n".format(n) for n in range(4)))
    out = screen_text(run_dir)
    assert "! 사람이 볼 곳이 3곳을 넘김: T040 4곳" in out and "src/f3.ts:1" in out


def test_read_judge_before_the_run_judge_stops_approval(run_dir):
    flow_verify(run_dir, status="자체검증")
    assert lib.judges_present(run_dir.tasks()[FV]) == (True, "")
    path = run_dir.task_dir(FV) / "judge.md"
    text = path.read_text(encoding="utf-8").split("\n", 1)[1]
    path.write_text("판정자: rjudge-T090 2020-01-01 00:00:00\n" + text, encoding="utf-8")
    ok, why = lib.judges_present(run_dir.tasks()[FV])
    assert not ok and "읽기 판정이 실행 판정보다 앞섬" in why
    assert run_script("task_set", run_dir.path, FV, "--status", "승인대기").returncode != 0


def test_old_flow_verify_has_no_order_check(run_dir):
    flow_verify(run_dir, meta=OLD, status="자체검증")
    path = run_dir.task_dir(FV) / "judge.md"
    path.write_text("판정자: rjudge-T090 2020-01-01 00:00:00\n" + path.read_text(encoding="utf-8").split("\n", 1)[1], encoding="utf-8")
    assert "앞섬" not in lib.judges_present(run_dir.tasks()[FV])[1]


def test_behavior_cell_says_how_to_object_and_it_is_not_an_item(run_dir):
    flow_verify(run_dir)
    code(run_dir, "T040", "- 빈 목록이면 안내 [종류: 동작] [위치: src/a.ts:12]\n")
    shown = asked(run_dir)
    assert "■ 구현이 정한 동작 (1)\n  이의가 있으면 `이의 n`, 없으면 답하지 않아도 됩니다\n- [1] 빈 목록이면 안내" in shown
    assert sorted(n for n in screen.shown_items(shown) if "이의" in screen.shown_items(shown)[n]) == []


REAL_TABLE = ("\n## 본문\n| 기준 | 확인 | 판정 | 근거 |\n|---|---|---|---|\n| K-I1-db | 로컬 시험 | 통과 | a |\n| K-I5 | verify:full | 실패 | b |\n"
              "| M-03의 빌드 몫 | 빌드 | **부분 통과** | c |\n| 묶음 전체 | 표본 | 판정불가 | d |\n\n다른 글\n\n| 표 밖 | 실패 |\n")


def test_real_table_rows_are_read_whatever_the_first_cell(run_dir):
    flow_verify(run_dir)
    path = run_dir.task_dir(FV) / "result.md"
    path.write_text(path.read_text(encoding="utf-8") + REAL_TABLE, encoding="utf-8")
    assert "인수 기준 표 4행: 통과 1, 부분 통과 1, 실패 1, 판정불가 1" in screen_text(run_dir)
    review = (run_dir.task_dir(FV) / "review.md").read_text(encoding="utf-8")
    assert "| K-I5 | verify:full | 실패 | b |" in review and "| 기준 | 확인 | 판정 | 근거 |" in review and "표 밖" not in review


def test_first_command_line_follows_the_run_check_rule_and_flow_paths(run_dir, repo):
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    out = commands(run_dir)
    first = out.splitlines()[0]
    assert "실행 폴더나 임시 폴더 안에서 끝나" in first and "밖에 닿으면" in first
    assert "전: abc (" in out and "flow.md" in out
    assert "후: " + str(repo) in out


def test_flow_paths_unread_when_missing(run_dir):
    flow_verify(run_dir)
    (run_dir.path / "flows" / "reading" / "flow.md").unlink()
    out = commands(run_dir)
    assert "전: 재지 못함(flow.md의 base_commit 없음)" in out and "후: 재지 못함(흐름 폴더 없음)" in out


def test_done_run_wide_design_wins_over_a_later_open_one(run_dir):
    flow_verify(run_dir)
    wide(run_dir)
    run_dir.task("T006", "고친 판", {"건드릴 파일": "- design/run2.md"}, kind="change", block="설계", status="승인대기", run_wide="true", **NEW)
    write(run_dir.path / "design" / "run2.md", "# 고친 판\n\n## 흐름 리뷰의 전·후 명령\n- `승인 전 명령`\n")
    out = commands(run_dir)
    assert "실행 전체 설계 T005:" in out and "승인 전 명령" not in out


def test_run_wide_document_names_the_section():
    from conftest import ROOT
    assert "## 흐름 리뷰의 전·후 명령" in (ROOT / "references" / "kinds" / "design" / "run-wide.md").read_text(encoding="utf-8")


def test_old_code_task_is_in_the_sheet_and_blocks_none(run_dir, repo):
    sha = git_commit(repo, "src/a.ts", "x\n")
    flow_verify(run_dir)
    point_flow(run_dir, repo)
    run_dir.task("T030", "옛 구현", kind="implementation", block="구현", status="완료", flow="reading", commit=sha, **OLD)
    page, _ = visual.sheet_html(str(run_dir.path), lib.load_task(str(run_dir.task_dir(FV) / "task.md")) | {"id": FV})
    assert "재지 못함: T030(판단 기록 없는 옛 코드 task)" in page and "사람이 볼 곳: 지목 없음" not in page


def test_person_item_line_includes_behavior_sentences(run_dir):
    flow_verify(run_dir)
    code(run_dir, "T040", "- 빈 목록이면 안내 [종류: 동작] [위치: src/a.ts:12]\n")
    assert "답할 것 1개: 동작 문장 1\n" in screen_text(run_dir)


@pytest.mark.parametrize("line", ["Set-Cookie: session=abcd1234efgh; Path=/; HttpOnly", "cookie: a=1; sid=secretvalue", '"set-cookie":"sid=secretvalue; Path=/"'])
def test_cookie_values_are_masked(line):
    out = lib.mask_line(line)
    assert lib.MASK in out and "abcd1234efgh" not in out and "secretvalue" not in out


@pytest.mark.parametrize("line", ["Cookie: 세션을 유지합니다", "cookie: string", "res.cookie(name)"])
def test_cookie_words_in_documents_stay(line):
    assert lib.mask_line(line) == line


def test_other_flow_exclusions_stay_out_of_the_review_head(run_dir):
    flow_verify(run_dir)
    run_dir.flow("other")
    for tid, flow in (("T040", "reading"), ("T050", "other")):
        run_dir.task(tid, "구현", kind="implementation", block="구현", status="완료", flow=flow, **NEW)
        run_dir.result(tid, result(unverified="- {} 변이는 사람 지시로 뺌".format(tid)))
    head = visual.flow_review_head(str(run_dir.path), lib.load_task(str(run_dir.task_dir(FV) / "task.md")) | {"id": FV})
    text = "\n".join(head)
    assert "T040 변이는 사람 지시로 뺌" in text and "T050" not in text


def test_review_head_is_recorded_for_the_shown_screen(run_dir):
    flow_verify(run_dir)
    assert run_script("visual", run_dir.path, FV).returncode == 0
    text = (run_dir.task_dir(FV) / flow_review.HEAD_FILE).read_text(encoding="utf-8")
    assert text.startswith("보인 시각: ") and "실행 지도: " in text


def test_terminal_and_sheet_numbers_are_the_same(run_dir):
    flow_verify(run_dir, cells={"decide": "- 고를 것 (가) 하나 (나) 둘"})
    code(run_dir, "T040", "- 빈 목록이면 안내 [종류: 동작] [위치: src/a.ts:12]\n")
    shown = asked(run_dir)
    page, _ = visual.sheet_html(str(run_dir.path), lib.load_task(str(run_dir.task_dir(FV) / "task.md")) | {"id": FV})
    numbers = screen.shown_items(shown)
    assert sorted(numbers) == list(range(1, len(numbers) + 1)) and len(numbers) >= 3
    for n, body in numbers.items():
        assert "[{}] {}".format(n, body.split("\n")[0]) in page.replace("&lt;", "<").replace("&gt;", ">")


def test_rerun_after_retry_needs_a_later_read_judge(run_dir):
    flow_verify(run_dir, status="자체검증")
    assert run_script("task_set", run_dir.path, FV, "--archive-judge").returncode == 0
    write(run_dir.task_dir(FV) / "judge-run.md", run_file(FV, PAIR, "2026-11-05 12:00:00"))
    run_dir.judge(FV, READ_JUDGE.replace("T001", FV).format(now="2026-11-05 11:00:00"))
    assert "앞섬" in lib.judges_present(run_dir.tasks()[FV])[1]
    run_dir.judge(FV, READ_JUDGE.replace("T001", FV).format(now="2026-11-05 12:30:00"))
    assert "앞섬" not in lib.judges_present(run_dir.tasks()[FV])[1]


# ---------------------------------------------------------------- 이의의 길

def objected(run_dir):
    """화면을 남기고 `이의 1`을 받아 `--answer`가 찍은 기록을 남긴다."""
    code(run_dir, "T040", "- 빈 목록이면 안내 [종류: 동작] [위치: src/a.ts:12]\n", no_change="true")
    assert run_script("screen", run_dir.path, FV, "--places").returncode == 0
    assert run_script("screen", run_dir.path, FV, "--save").returncode == 0
    p = run_script("screen", run_dir.path, FV, "--answer", "이의 1")
    assert p.returncode == 0, p.output
    line = next(l for l in p.stdout.splitlines() if l.startswith("--record: "))
    r = run_script("task_set", run_dir.path, FV, "--record", line[len("--record: "):])
    assert r.returncode == 0, r.output
    return p.stdout


def fix_from_answer(run_dir, tid="T060", touch="- src/a.ts", flow="reading"):
    write(run_dir.path / "body.md", "## 범위\n- 안내 문구를 고친다\n\n## 판정 기준\n1. 문구\n\n## 건드릴 파일\n{}\n".format(touch))
    args = ["new", "--from-answer", FV, "--title", "이의 고침", "--body-from", run_dir.path / "body.md"] + (["--flow", flow] if flow else [])
    p = run_script("task_set", run_dir.path, *args)
    assert p.returncode == 0, p.output
    return p.stdout


def close_verify(run_dir):
    return run_script("task_set", run_dir.path, FV, "--status", "완료", "--record", "승인|승인|승인합니다")


def test_objection_prints_the_record_and_the_fix_command(run_dir):
    flow_verify(run_dir)
    out = objected(run_dir)
    assert "이의: 항목 1 | 빈 목록이면 안내" in out
    assert "new --from-answer {}".format(FV) in out and "--flow reading" in out
    assert "리뷰 이의" in run_dir.tasks()[FV]["_sections"]["승인 기록"]


def test_objection_is_not_an_approval_and_does_not_move_the_status(run_dir):
    flow_verify(run_dir)
    objected(run_dir)
    t = run_dir.tasks()[FV]
    assert not lib.prior_approval(t) and t["status"] == "승인대기"
    fix_from_answer(run_dir)
    p = run_script("task_set", run_dir.path, FV, "--status", "완료", "--record", "리뷰 이의|항목 1|이의 1")
    assert p.returncode != 0 and "상태를 옮기지 않는다" in p.output


def test_objection_without_a_fix_cannot_close_and_with_one_can(run_dir):
    flow_verify(run_dir)
    objected(run_dir)
    p = close_verify(run_dir)
    assert p.returncode != 0 and "리뷰 이의" in p.output
    fix_from_answer(run_dir)
    assert run_dir.tasks()[new_task_id(run_dir)]["kind"] == "fix"
    p = close_verify(run_dir)
    assert p.returncode == 0, p.output


def test_withdrawn_objection_can_close(run_dir):
    flow_verify(run_dir)
    objected(run_dir)
    r = run_script("task_set", run_dir.path, FV, "--record", "리뷰 이의 철회|항목 1|괜찮습니다")
    assert r.returncode == 0, r.output
    p = close_verify(run_dir)
    assert p.returncode == 0, p.output


def test_new_objection_after_a_fix_needs_another_fix(run_dir):
    flow_verify(run_dir)
    objected(run_dir)
    fix_from_answer(run_dir)
    time.sleep(1.1)
    r = run_script("task_set", run_dir.path, FV, "--record", "리뷰 이의|항목 1|이의 1 다시")
    assert r.returncode == 0, r.output
    assert close_verify(run_dir).returncode != 0


def test_hold_is_accepted_with_an_open_objection(run_dir):
    flow_verify(run_dir)
    objected(run_dir)
    assert run_script("task_set", run_dir.path, FV, "--status", "보류", "--reason", "나중에").returncode == 0


def test_old_flow_verify_has_no_objection_gate(run_dir):
    flow_verify(run_dir, meta=OLD)
    run_script("task_set", run_dir.path, FV, "--record", "리뷰 이의|항목 1|이의 1")
    t = run_dir.tasks()[FV]
    assert places.completion_block(str(run_dir.path), t) == ""


def merge_ready(run_dir):
    merge_setup(run_dir)
    tasks = run_dir.tasks()
    return board.mergeable_flows(tasks, board.load_flows(str(run_dir.path)), str(run_dir.path), lib.hold_blockers(tasks))


def merge_setup(run_dir):
    path = run_dir.path / "run.md"
    text = path.read_text(encoding="utf-8")
    if "integration_branch" not in text:
        path.write_text(text.replace("status: 진행", "status: 진행\nintegration_branch: integ"), encoding="utf-8")


def done(run_dir, tid):
    p = run_dir.task_dir(tid) / "task.md"
    p.write_text(re.sub(r"(?m)^status: .*$", "status: 완료", p.read_text(encoding="utf-8")), encoding="utf-8")


def new_task_id(run_dir):
    return next(i for i, t in run_dir.tasks().items() if t.get("title") == "이의 고침")


def test_merge_waits_for_the_objection_fix_and_then_goes(run_dir):
    flow_verify(run_dir)
    objected(run_dir)
    fix_from_answer(run_dir)
    assert close_verify(run_dir).returncode == 0, "승인과 함께 온 이의"
    assert merge_ready(run_dir) == []
    fix = new_task_id(run_dir)
    assert run_dir.tasks()[fix]["kind"] == "fix" and run_dir.tasks()[fix]["flow"] == "reading"
    done(run_dir, fix)
    assert merge_ready(run_dir) == ["reading"], "고친 뒤에는 재검증 없이도 합친다. 영원히 멈추지 않는다"


def test_merge_waits_for_an_objection_fix_of_another_kind_or_flow(run_dir):
    # 정본만 고치면 변경 task이고 흐름이 없다. 그래도 그 흐름의 합치기가 기다린다
    flow_verify(run_dir)
    objected(run_dir)
    fix_from_answer(run_dir, touch="- spec/reading.md", flow="")
    assert close_verify(run_dir).returncode == 0
    fix = new_task_id(run_dir)
    assert run_dir.tasks()[fix]["kind"] == "change"
    assert merge_ready(run_dir) == []
    done(run_dir, fix)
    assert merge_ready(run_dir) == ["reading"]


def test_merge_goes_when_the_objection_fix_is_held(run_dir):
    flow_verify(run_dir)
    objected(run_dir)
    fix_from_answer(run_dir)
    assert close_verify(run_dir).returncode == 0
    fix = new_task_id(run_dir)
    assert run_script("task_set", run_dir.path, fix, "--status", "보류", "--reason", "사람이 미룸").returncode == 0
    assert merge_ready(run_dir) == ["reading"]


def test_merge_of_an_old_verify_is_as_before(run_dir):
    flow_verify(run_dir, meta=OLD, status="완료")
    merge_setup(run_dir)
    assert merge_ready(run_dir) == ["reading"]
    run_dir.task("T060", "다른 흐름의 답", {"건드릴 파일": "- spec/x.md"}, kind="change", block="", status="대기", origin="사용자 {} 2026-11-05 10:00:00".format(FV), **NEW)
    assert merge_ready(run_dir) == ["reading"]
