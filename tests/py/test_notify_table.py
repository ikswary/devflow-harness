"""1.2.0 A9: 설계 5.1절 「묻기와 알림」 표의 task 층 판단. 공통 조건과 kind 행, `남는 것:`을 본다.

나머지 행은 다른 파일에 있다: 합치기와 마무리는 `test_owned_commands.py`, 설계 고친 판은 `test_design_approval.py`. 구현 kind의 `본보기`는 1.3.0이다.
"""
from datetime import datetime

import pytest

import devflow_lib
import exec as execmod
import kinds
import screen
import task_set
from conftest import run_script, write
from test_domain_paths import READ_JUDGE, RUN_JUDGE

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}
PROBE_TABLE = "\n## 탐침 기록\n| 가정 | 판정 | 관찰 | 근거 로그 |\n|---|---|---|---|\n| A1 | 참 | 200 | logs/a |\n"


def result(decide="- 없음", todo="- 없음", notify="- 없음", unverified="- 없음", tail=""):
    return ("# 결과\n\n## 승인 화면\n### 정해 주실 것\n{}\n### 하실 일·허용 요청\n{}\n### 알릴 것\n{}\n### 답하신 것의 반영\n- 없음\n"
            "### 확인 안 된 것\n{}\n### 건수만\n- 없음\n\n## 판단\n- 없음\n{}").format(decide, todo, notify, unverified, tail)


def judged(run_dir, tid="T001", run=False, failed=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = READ_JUDGE.replace("T001", tid).format(now=now)
    if failed:
        text = text.replace("## 통과 못 한 기준\n- 없음", "## 통과 못 한 기준\n" + failed)
    run_dir.judge(tid, text)
    if run:
        write(run_dir.task_dir(tid) / "judge-run.md", RUN_JUDGE.replace("T001", tid).format(now=now))


def make(run_dir, kind, cell=None, sections=None, meta=NEW, failed="", tail="", **more):
    block = kinds.block_of(kind) or "설계"
    sections = dict({"건드릴 파일": "- src/a.ts"} if kind in kinds.TOUCH_FILES_KINDS else {}, **(sections or {}))
    run_dir.task("T001", kind, sections, kind=kind, block=block, status="자체검증", flow=more.pop("flow", "a"), **dict(meta, **more))
    run_dir.result("T001", result(tail=tail, **(cell or {})))
    judged(run_dir, run=kinds.KINDS[kind].run_judge == "always", failed=failed)


def passes(run_dir):
    return screen.notify_status(str(run_dir.path), "T001")


# ---------------------------------------------------------------- 공통 조건: kind와 관계없이 묻는다

NOTIFYING = ["implementation", "fe-implementation", "be-implementation", "fix", "reverify", "full-verify"]


@pytest.mark.parametrize("kind", NOTIFYING)
def test_common_conditions_start_from_a_passing_row(run_dir, kind):
    make(run_dir, kind)
    assert passes(run_dir)[0]


@pytest.mark.parametrize("kind", NOTIFYING)
@pytest.mark.parametrize("cell", [{"decide": "- 정할 것"}, {"todo": "- 콘솔에서 할 일"}, {"notify": "- 둡니다 [성질: 위험]"}, {"unverified": "- 둡니다 [성질: 위험]"}])
def test_person_share_asks_for_every_kind(run_dir, kind, cell):
    make(run_dir, kind, cell)
    assert not passes(run_dir)[0]


@pytest.mark.parametrize("kind", NOTIFYING)
def test_failed_judge_asks_for_every_kind(run_dir, kind):
    make(run_dir, kind, failed="- 기준 1: 실패")
    assert not passes(run_dir)[0]


@pytest.mark.parametrize("kind", NOTIFYING)
def test_infra_path_asks_for_every_kind(run_dir, kind):
    make(run_dir, kind, sections={"건드릴 파일": "- db/migrations/0001.sql"})
    ok, why = passes(run_dir)
    assert not ok and "인프라" in why


# ---------------------------------------------------------------- kind 행


def test_scope_asks_and_an_empty_question_notifies(run_dir):
    for kind in ("brief", "req-overview", "req-detail"):
        make(run_dir, kind, flow="")
        assert not passes(run_dir)[0], kind
    make(run_dir, "question", flow="")
    assert passes(run_dir)[0]
    make(run_dir, "question", {"unverified": "- 볼 것"}, flow="")
    assert not passes(run_dir)[0]


@pytest.mark.parametrize("kind", ["design", "ui-design", "infra-design", "root-cause"])
def test_approach_asks(run_dir, kind):
    make(run_dir, kind, flow="")
    assert not passes(run_dir)[0]


def test_code_kind_notifies_with_notices_left(run_dir):
    make(run_dir, "implementation", {"notify": "- 알릴 줄", "unverified": "- 못 본 줄"})
    assert passes(run_dir)[0]


def test_code_kind_criterion_correction_asks(run_dir):
    make(run_dir, "implementation")
    run_dir.task("T001", "구현", {"건드릴 파일": "- src/a.ts", "판정 기준 정정": "- 출처: 판정자 | 줄"}, kind="implementation", block="구현", status="자체검증", flow="a", **NEW)
    assert not passes(run_dir)[0]


@pytest.mark.parametrize("origin,want", [("사용자 T005 2026-11-01 10:00 코드 확인 T010-aa", False), ("판정자 T005", True)])
def test_fix_row_code_check_origin_asks(run_dir, origin, want):
    make(run_dir, "fix", origin=origin)
    assert passes(run_dir)[0] is want


def test_fix_moving_an_answer_notifies_after_the_judge(run_dir):
    make(run_dir, "fix", sections={"판정 기준": "1. " + devflow_lib.ANSWER_CRITERION}, origin="사용자 T005 답")
    assert passes(run_dir)[0]


def test_flow_verify_asks(run_dir):
    make(run_dir, "flow-verify")
    ok, why = passes(run_dir)
    assert not ok and "지나가지 않는다" in why


def test_reverify_moved_lines_do_not_block(run_dir):
    make(run_dir, "reverify", {"notify": "- [T005] 옮긴 줄", "unverified": "- [T005] 옮긴 줄"})
    assert passes(run_dir)[0]


def test_full_verify_with_zero_findings_notifies_and_keeps_unverified(run_dir):
    make(run_dir, "full-verify", {"unverified": "- 실제 경로 못 돌림"}, flow="")
    assert passes(run_dir)[0]


@pytest.mark.parametrize("cell", [{"notify": "- 바로 고친다 지적"}, {"decide": "- 묻는다 지적"}])
def test_full_verify_with_findings_asks(run_dir, cell):
    make(run_dir, "full-verify", cell, flow="")
    assert not passes(run_dir)[0]


def test_full_verify_with_backlog_row_asks(run_dir):   # 권장 지적은 칸이 비어도 자식 행으로 나온다. 실제 꼴은 `## 자식 목록`과 `### 자식:`이다
    make(run_dir, "full-verify", flow="", tail="\n## 자식 목록\n나눈 기준: 지적\n\n### 자식: [백로그] 이름 고침\n- kind: fix\n- flow: fixes\n")
    b = screen.build(str(run_dir.path), "T001")
    assert b["facts"] and b["facts"]["rows"] == 1 and not b["notify_ok"]
    make(run_dir, "full-verify", flow="", tail="\n## 자식 목록\n나눈 기준: 없음\n\n자식 없음\n")
    assert screen.build(str(run_dir.path), "T001")["notify_ok"]


@pytest.mark.parametrize("line", ["- V-03 중요: 운영 권한 우회 가능성, 확인을 넘긴다", "- N-02 실제 경로에서 못 봄", "- 확인을 넘김(V-11): 운영에서 확인"])
def test_full_verify_handed_over_finding_asks(run_dir, line):   # 지적 ID가 있으면 지적이다
    make(run_dir, "full-verify", {"unverified": line}, flow="")
    assert not screen.build(str(run_dir.path), "T001")["notify_ok"]


@pytest.mark.parametrize("line", ["- AC-12 판정불가: 공용 dev에서 못 돌림", "- E-AC-13 판정불가: 못 돌림", "- [T050] V-03 옮긴 줄"])
def test_full_verify_undetermined_criterion_and_moved_line_pass(run_dir, line):
    make(run_dir, "full-verify", {"unverified": line}, flow="")
    assert screen.build(str(run_dir.path), "T001")["notify_ok"]


def test_full_verify_doubtful_finding_in_the_body_asks(run_dir):   # 「본문」 아래 "근거 부족"도 사람이 안 보면 사라진다
    make(run_dir, "full-verify", flow="", tail="\n## 본문\n추적표\n\n### 근거 부족\n- V-09 권한 우회 의심\n")
    assert not screen.build(str(run_dir.path), "T001")["notify_ok"]
    make(run_dir, "full-verify", flow="", tail="\n## 본문\n### 근거 부족\n- 없음\n")
    assert screen.build(str(run_dir.path), "T001")["notify_ok"]


def test_setting_conflict_fix_from_a_fetch_notifies(run_dir):   # 받아오기의 설정 충돌 수정
    make(run_dir, "fix", sections={"건드릴 파일": "- tsconfig.json", "범위": "받아온 출처 harness/x, 충돌 파일 tsconfig.json"})
    assert passes(run_dir)[0]


def test_old_full_verify_keeps_asking(run_dir):
    make(run_dir, "full-verify", meta=OLD, flow="")
    assert not passes(run_dir)[0]
    t = run_dir.tasks()["T001"]
    ctx = {"record": ("알림", "", ""), "reason": None, "archived": False, "snapshot": False, "old_stage": ""}
    assert "지나가지" in task_set.check_transition(str(run_dir.path), t, "자체검증", kinds.DONE, ctx)


def test_oldest_full_verify_without_a_version_keeps_asking(run_dir):
    make(run_dir, "full-verify", meta={"rules": "2"}, flow="")
    t = run_dir.tasks()["T001"]
    ctx = {"record": ("알림", "", ""), "reason": None, "archived": False, "snapshot": False, "old_stage": ""}
    assert "지나가지" in task_set.check_transition(str(run_dir.path), t, "자체검증", kinds.DONE, ctx)


@pytest.mark.parametrize("kind", ["deploy-plan", "deploy-exec"])
def test_deploy_asks(run_dir, kind):
    make(run_dir, kind, flow="")
    assert not passes(run_dir)[0]


# ---------------------------------------------------------------- 탐침과 `남는 것:`


def probe(run_dir, scope="", origin="", cell=None, tail=PROBE_TABLE, meta=NEW):
    make(run_dir, "probe", cell, sections={"범위": scope} if scope else {}, tail=tail, origin=origin, meta=meta, flow="", stage="기록")


def test_probe_plan_always_asks(run_dir):
    probe(run_dir, tail="")
    assert not passes(run_dir)[0]


def test_probe_with_nothing_left_notifies_when_all_true(run_dir):
    probe(run_dir, "가정 확인\n남는 것: 없음")
    assert passes(run_dir)[0]
    probe(run_dir, "가정 확인")   # 비면 없음
    assert passes(run_dir)[0]


def test_probe_false_assumption_or_decision_asks(run_dir):
    probe(run_dir, tail=PROBE_TABLE.replace("| 참 |", "| 거짓 |"))
    assert not passes(run_dir)[0]
    probe(run_dir, cell={"decide": "- 고침/받아들임"})
    assert not passes(run_dir)[0]


@pytest.mark.parametrize("scope", ["남는 것: 자원", "남는 것: 파일", "- `남는 것:` 자원", "남는 것 : 파일", "**남는 것:** 자원", "남는 것: 모르는 값", "남는 것: 없음\n남는 것: 자원"])
def test_probe_leaving_something_always_asks(run_dir, scope):
    probe(run_dir, scope)
    ok, why = passes(run_dir)
    assert not ok and "남기는 것" in why


def test_handed_todo_without_the_line_is_a_resource(run_dir):   # 메인이 적지 않아도 사람 승인이 사라지지 않는다
    probe(run_dir, origin="하실 일 넘김 T012")
    assert devflow_lib.probe_remains(run_dir.tasks()["T001"]) == "자원"
    assert not passes(run_dir)[0]


def test_handed_todo_cannot_write_itself_down_to_nothing(run_dir):
    probe(run_dir, "남는 것: 없음", origin="하실 일 넘김 T012")
    assert not passes(run_dir)[0]


def test_old_probe_keeps_the_old_rule(run_dir):
    probe(run_dir, "남는 것: 자원", meta=OLD)
    assert passes(run_dir)[0]


def test_probe_transition_refuses_the_notice_when_leaving_something(run_dir):
    probe(run_dir, "남는 것: 자원")
    lines = ["echo ok"]
    write(run_dir.task_dir("T001") / "approved-cmds-실행승인.md", "해시: {}\n얼린 시각: 2026-10-15 10:00:00\n\n1. echo ok\n".format(execmod.digest(lines)))
    write(run_dir.task_dir("T001") / "exec.md", "- 2026-10-15 10:01:00 | echo ok | 종료 코드 0 | 로그 x | 지점 실행승인:1 | 폴더 x\n")
    r = run_script("task_set", run_dir.path, "T001", "--status", "완료", "stage=끝", "--record", "알림|끝남|")
    assert r.returncode == 3 and "알림 불가" in r.output, r.output
