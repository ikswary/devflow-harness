"""1.2.0 A1: 리뷰 계약과 사람 몫 판정(설계 4.3절, 5.1~5.3절).

- 계약은 등록표 칸 `review`이고, 변경 task는 고치는 정본으로 가른다.
- 성질 `위험`이 있으면 kind와 관계없이 묻고, 옮겨 온 `[T0xx]` 줄은 알림 판단과 수에 넣지 않는다.
- `scope`, `approach` 계약은 늘 묻고, `behavior` 계약은 답을 옮겼어도 판정이 통과하면 알림이다. 코드 확인에서 온 수정은 묻는다.
- 옛 판본으로 시작한 task는 지금 규칙 그대로다.
"""
from datetime import datetime

import pytest

import devflow_lib as lib
import kinds
import screen
import task_set
from conftest import run_script, write
from test_domain_paths import READ_JUDGE, RUN_JUDGE, settings

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}


def result(decide="- 없음", todo="- 없음", notify="- 없음", unverified="- 없음"):
    return ("# 결과\n\n## 승인 화면\n### 정해 주실 것\n{}\n### 하실 일·허용 요청\n{}\n### 알릴 것\n{}\n"
            "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n{}\n### 건수만\n- 없음\n\n## 판단\n- 없음\n").format(decide, todo, notify, unverified)


def judged(run_dir, tid="T001", run=False):
    """판정 파일. 시각이 지금이어야 기록 점검 R3에 걸리지 않는다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge(tid, READ_JUDGE.replace("T001", tid).format(now=now))
    if run:
        write(run_dir.task_dir(tid) / "judge-run.md", RUN_JUDGE.replace("T001", tid).format(now=now))


def code_task(run_dir, tid="T001", notify="- 없음", meta=NEW, touch="- src/a.ts", criteria="1. 기준", cells=None, **more):
    run_dir.task(tid, "구현", {"건드릴 파일": touch, "판정 기준": criteria}, kind="implementation", block="구현", status="자체검증",
                 flow="a", **dict(meta, **more))
    run_dir.result(tid, result(**(cells or {"notify": notify})))
    judged(run_dir, tid, run=True)


def other_task(run_dir, kind, meta=NEW, sections=None, block="설계", **cells):
    run_dir.task("T001", kind, sections, kind=kind, block=block, status="자체검증", **meta)
    run_dir.result("T001", result(**cells))
    judged(run_dir)


def notifies(run_dir, tid="T001"):
    ok, why = screen.notify_status(str(run_dir.path), tid)
    return ok, why, run_script("screen", run_dir.path, tid).stdout


EXPECTED = {
    "question": "scope", "brief": "scope", "req-overview": "scope", "req-detail": "scope",
    "design": "approach", "ui-design": "approach", "infra-design": "approach", "root-cause": "approach",
    "implementation": "behavior", "fe-implementation": "behavior", "be-implementation": "behavior", "fix": "behavior",
    "flow-verify": "behavior+risk", "reverify": "risk", "full-verify": "risk",
    "merge": "command", "probe": "command", "deploy-plan": "command", "deploy-exec": "command", "wrap-up": "command+run",
    "change": "",
}


def test_every_kind_has_its_contract():
    assert {name: k.review for name, k in kinds.KINDS.items()} == EXPECTED


@pytest.mark.parametrize("touch,want", [
    ("- spec/overview.md", "scope"),
    ("- spec\\brief.md", "scope"),
    ("- design/list.md", "approach"),
    ("- ui/list.md", "approach"),
    ("- design/list.md\n- spec/list.md", "scope"),
    ("- tasks/T003/revised/spec/overview.md", "scope"),
    ("- ./spec/a.md", "scope"),
    ("- tasks/T003/revised/design/list.md", "approach"),
])
def test_change_contract_follows_the_canon_it_edits(lib, touch, want):
    t = {"kind": "change", "_sections": {"건드릴 파일": touch}}
    assert lib.review_contract(t) == want


@pytest.mark.parametrize("line", [
    "[성질: 위험]", "[성질:위험]", "[성질 : 위험]", "[성질：위험]", "[성질: 위험 수용]", "[성질: 범위/위험]", "[성질: 범위 위험]",
    "[성질: 범위、위험]", "[성질: `위험`]",
])
def test_risk_mark_reads_loosely_toward_asking(lib, line):
    assert lib.has_risk_mark("- 값을 정했다 " + line) is True


@pytest.mark.parametrize("line", ["- 위험을 줄였다", "- [성질: 범위]", ""])
def test_risk_mark_needs_the_mark(lib, line):
    assert lib.has_risk_mark(line) is False


@pytest.mark.parametrize("line,want", [
    ("- 값을 정했다 [성질: 위험]", {"위험"}),
    ("- 값을 정했다 [성질: 앞 판단과 다름]", {"앞 판단과 다름"}),
    ("- 값을 정했다 [성질: 범위, 위험]\n  설명", {"범위", "위험"}),
    ("- 값을 정했다 [성질: 비용·밖]", {"비용", "밖"}),
    ("- 값을 정했다\n  [성질: 범위]", {"범위"}),
    ("- [사실] 코드에 있다", set()),
    ("", set()),
])
def test_item_properties(lib, line, want):
    assert lib.item_properties(line) == want


def test_without_moved_items_drops_the_sub_lines_too(lib):
    text = "- [T012] 옮긴 줄\n  하위\n- 이 task의 줄\n  하위 2"
    assert lib.without_moved_items(text) == "- 이 task의 줄\n  하위 2"
    assert lib.item_count(lib.without_moved_items("- [T012] 옮긴 줄")) == 0


def test_risk_item_blocks_notify(run_dir):
    code_task(run_dir, notify="- 재시도를 뺐다 [성질: 위험]")
    ok, why, out = notifies(run_dir)
    assert ok is False and "위험" in why
    assert "알림 조건: 미충족(성질 `위험` 항목이 있다)" in out


def test_other_properties_do_not_block_a_code_task(run_dir):
    code_task(run_dir, notify="- 칸을 더했다 [성질: 범위]")
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def test_risk_item_on_old_task_keeps_old_rule(run_dir):
    code_task(run_dir, notify="- 재시도를 뺐다 [성질: 위험]", meta=OLD)
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def test_moved_risk_line_does_not_block_and_is_not_counted(run_dir):
    other_task(run_dir, "reverify", block="검증", notify="- [T012] 재시도를 뺐다 [성질: 위험]\n  하위 줄", unverified="- [T013] 옮긴 가정")
    ok, why, out = notifies(run_dir)
    assert ok is True, why
    assert "n_notify=0" in out and "n_unverified=0" in out
    assert "■ 알릴 것 (0, 앞 task에서 옮긴 것 1)" in out
    assert "- [1] [T012] 재시도를 뺐다" in out


@pytest.mark.parametrize("cell", ["decide", "todo"])
def test_moved_decision_and_todo_are_still_the_persons(run_dir, cell):
    code_task(run_dir, cells={cell: "- [T012] 재시도 횟수를 (가) 3 (나) 5 가운데 정해 주세요"})
    ok, _, out = notifies(run_dir)
    assert ok is False
    assert ("n_decide=1" if cell == "decide" else "n_todo=1") in out
    assert "■ {} (1)".format("정해 주실 것" if cell == "decide" else "하실 일·허용 요청") in out


def test_risk_in_unverified_cell_asks(run_dir):
    code_task(run_dir, cells={"unverified": "- 결함을 받아들였다 [성질: 위험]"})
    assert notifies(run_dir)[0] is False


@pytest.mark.parametrize("line", ["- [사실] 코드에 있다", "- [기록 점검] 줄", "- [보류로 남김] 줄"])
def test_only_task_ids_count_as_moved(lib, line):
    assert lib.item_count(lib.without_moved_items(line)) == 1


def test_moved_lines_still_count_on_old_task(run_dir):
    other_task(run_dir, "reverify", meta=OLD, block="검증", notify="- [T012] 옮긴 줄")
    ok, why, _ = notifies(run_dir)
    assert ok is False, why


@pytest.mark.parametrize("touch", ["- spec/list.md", "- design/list.md"])
def test_change_task_asks_on_new_rules(run_dir, touch):
    other_task(run_dir, "change", sections={"건드릴 파일": touch})
    ok, why, _ = notifies(run_dir)
    assert ok is False and "change" in why


def test_change_task_on_old_rules_can_notify(run_dir):
    other_task(run_dir, "change", meta=OLD, sections={"건드릴 파일": "- design/list.md"})
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


@pytest.mark.parametrize("cell", ["decide", "todo", "notify", "unverified"])
def test_question_with_something_to_see_asks_on_new_rules(run_dir, cell):
    other_task(run_dir, "question", block="질문", **{cell: "- 볼 것"})
    ok, _, out = notifies(run_dir)
    assert ok is False
    assert "scope 계약의 question" in out


def test_question_with_nothing_to_ask_notifies(run_dir):
    other_task(run_dir, "question", block="질문")
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def test_question_on_old_rules_can_notify(run_dir):
    other_task(run_dir, "question", meta=OLD, block="질문")
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


JUDGED = "1. 기준\n2. {}: \"이름을 고쳐\"".format(lib.ANSWER_CRITERION)


@pytest.mark.parametrize("origin,meta,criteria,want", [
    ("사용자 T009 2026-11-05 10:00:00", NEW, JUDGED, True),
    ("사용자 T009 2026-11-05 10:00:00", NEW, "1. 기준", False),
    ("사용자 T009 2026-11-05 10:00:00 코드 확인 T005-ab12", NEW, JUDGED, False),
    ("사용자 T009 2026-11-05 10:00:00", OLD, JUDGED, False),
])
def test_code_task_from_an_answer(run_dir, origin, meta, criteria, want):
    code_task(run_dir, meta=meta, origin=origin, criteria=criteria)
    ok, why, _ = notifies(run_dir)
    assert ok is want, why


def test_user_origin_probe_does_not_notify_on_new_rules(run_dir):
    run_dir.task("T001", "탐침", {"판정 기준": JUDGED}, kind="probe", block="설계", status="자체검증", stage="기록",
                 origin="사용자 T009 2026-11-05 10:00:00", **NEW)
    run_dir.result("T001", result())
    judged(run_dir)
    assert notifies(run_dir)[0] is False


APPROVED = {"승인 기록": '- 2026-11-05 09:00:00 | 승인 | 승인 | 원문: "승인"'}


@pytest.mark.parametrize("cells,want", [({"notify": "- 결함을 둔다 [성질: 위험]"}, 3), ({"decide": "- 고를 것"}, 3), ({"todo": "- 할 일"}, 3), ({}, 0)])
def test_prior_approval_does_not_pass_the_persons_share(run_dir, cells, want):
    run_dir.task("T001", "구현", dict(APPROVED, **{"건드릴 파일": "- src/a.ts"}), kind="implementation", block="구현", status="자체검증", flow="a", **NEW)
    run_dir.result("T001", result(**cells))
    judged(run_dir, run=True)
    p = run_script("task_set", run_dir.path, "T001", "--status", "완료", "--record", "알림|지나감|")
    assert p.returncode == want, p.output


def test_transition_notify_and_ask_on_new_rules(run_dir):
    other_task(run_dir, "question", block="질문", decide="- 고를 것")
    assert run_script("task_set", run_dir.path, "T001", "--status", "완료", "--record", "알림|지나감|").returncode == 3
    assert run_script("task_set", run_dir.path, "T001", "--status", "승인대기").returncode == 0


def test_empty_started_version_keeps_old_rules(run_dir):
    code_task(run_dir, notify="- 재시도를 뺐다 [성질: 위험]", meta={"started_version": "", "rules": "2"})
    assert screen.build(str(run_dir.path), "T001")["risky"] is False


def test_infra_path_blocks_a_task_that_writes_no_code_on_new_rules(run_dir):
    settings(run_dir, paths={"인프라": "infra/**"})
    other_task(run_dir, "reverify", block="검증", sections={"건드릴 파일": "- infra/db.sql"})
    ok, why, _ = notifies(run_dir)
    assert ok is False and "인프라 경로" in why


@pytest.mark.parametrize("touch,want", [
    ("- db/migrations/001.sql", False), ("- migrations/0001.sql", False), ("- db/schema.sql", False), ("- db\\install.sql", False),
    ("- apps/api/wrangler.toml", False), ("- docker/Dockerfile", False), ("- .env.local", False), ("- .github/workflows/a.yml", False),
    ("- src/a.ts", True),
])
def test_empty_infra_paths_use_the_default_patterns_on_new_rules(run_dir, touch, want):
    settings(run_dir, paths={"인프라": "없음"})
    code_task(run_dir, touch=touch)
    ok, why, _ = notifies(run_dir)
    assert ok is want, why


def test_listed_infra_paths_do_not_mix_the_default_patterns(run_dir):
    settings(run_dir, paths={"인프라": "infra/**"})
    code_task(run_dir, touch="- db/schema.sql")
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def test_empty_infra_paths_stay_empty_on_old_rules(run_dir):
    settings(run_dir, paths={"인프라": "없음"})
    code_task(run_dir, touch="- db/migrations/001.sql", meta=OLD)
    ok, why, _ = notifies(run_dir)
    assert ok is True, why


def baseline_file(run_dir, *lines):
    write(run_dir.path / "baseline-run.md", "판정자: xjudge\n\n" + "\n".join(lines) + "\n")


ROW = "- {} | {} | 기준 커밋에 있음: {} | 변경 전 실패: {} | 닫는 인수 기준: {}"


def test_baseline_screen_asks_only_failures_from_the_base_commit(run_dir):
    baseline_file(run_dir, ROW.format("a 시험", "시간 초과", "예", "예", "AC-1"), ROW.format("b 시험", "타입 오류", "아니오", "아니오", "없음"),
                  ROW.format("c[x|y] 시험", "값 다름", "예", "아니오", "없음"), "- 돌지 못함: e2e | 브라우저 없음")
    p = run_script("screen", run_dir.path, "--baseline")
    assert p.returncode == 0, p.output
    assert "■ 기준선: 이 실패를 이 실행과 무관한 것으로 두는가 (1)" in p.stdout
    assert "- [1] a 시험 | 시간 초과" in p.stdout and "닫는 인수 기준: AC-1" in p.stdout
    assert "닫는 인수 기준은 판정불가가 된다" in p.stdout
    assert "! 새 실패(이 실행과 무관할 수 없어 기준선이 될 수 없다): b 시험 | 타입 오류" in p.stdout
    assert "! 새 실패(이 실행과 무관할 수 없어 기준선이 될 수 없다): c[x|y] 시험 | 값 다름" in p.stdout
    assert "! 돌지 못함: e2e | 브라우저 없음" in p.stdout


def test_baseline_screen_without_failures_does_not_ask(run_dir):
    baseline_file(run_dir, "실패 없음")
    p = run_script("screen", run_dir.path, "--baseline")
    assert p.returncode == 0
    assert "기준선 질문 없음" in p.stdout and "■ 기준선" not in p.stdout


def test_baseline_screen_with_only_new_failures_says_where_they_go(run_dir):
    baseline_file(run_dir, ROW.format("b 시험", "타입 오류", "아니오", "아니오", "없음"))
    p = run_script("screen", run_dir.path, "--baseline")
    assert p.returncode == 0 and "새 실패는 메인이" in p.stdout


@pytest.mark.parametrize("lines", [
    (), ("빌드 실패: gradle 없음",), ("- a | 이유 | 기준 커밋에 있음: 예",), ("| a | 이유 |",),
    ("- a | 이유 | 기준 커밋에 있음: 예(파일 있음) | 변경 전 실패: 예 | 닫는 인수 기준: 없음",),
    ("실패 없음", "- 어긋난 줄"),
])
def test_baseline_screen_does_not_read_broken_records_as_clean(run_dir, lines):
    baseline_file(run_dir, *lines)
    p = run_script("screen", run_dir.path, "--baseline")
    assert p.returncode == 3, p.output
    assert "읽지 못한 줄" in p.stdout


def test_baseline_screen_needs_the_record(run_dir):
    assert run_script("screen", run_dir.path, "--baseline").returncode == 3


def test_fix_from_an_answer_gets_the_criterion(run_dir, lib, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(lib, "harness_version", lambda: "1.2.0-dev.1")
    run_dir.task("T001", "앞", {"승인 기록": '- 2026-11-05 10:00:00 | 답 | 고침 | 원문: "이름을 고쳐"'}, status="완료", **NEW)
    body = write(tmp_path / "body.md", "## 범위\n- 고침\n\n## 판정 기준\n1. 이름이 바뀐다\n\n## 건드릴 파일\n- src/a.ts\n")
    rc = task_set.main(["task_set.py", str(run_dir.path), "new", "--from-answer", "T001", "--title", "고침", "--flow", "a",
                        "--body-from", str(body)])
    assert rc == 0, capsys.readouterr().out
    line = '2. {}: "이름을 고쳐"'.format(lib.ANSWER_CRITERION)
    assert line in (run_dir.task_dir("T002") / "task.md").read_text(encoding="utf-8")
    assert lib.ANSWER_CRITERION in (run_dir.task_dir("T002") / "criteria.orig.md").read_text(encoding="utf-8")
    assert lib.answer_is_judged(run_dir.tasks()["T002"]) is True


@pytest.mark.parametrize("text,want", [
    ("1. 하나\n2. 둘", "3. 새 줄"), ("1. 하나\n   1. 하위\n2. 둘\n5. 다섯", "6. 새 줄"), ("- 글머리", "- 새 줄"), ("", "- 새 줄"),
])
def test_next_criterion_numbers(lib, text, want):
    assert lib.next_criterion(text, "새 줄") == want


def test_fix_from_an_answer_on_the_old_harness_keeps_the_criteria(run_dir, lib, monkeypatch, tmp_path):
    monkeypatch.setattr(lib, "harness_version", lambda: "1.1.1")
    run_dir.task("T001", "앞", {"승인 기록": '- 2026-11-05 10:00:00 | 답 | 고침 | 원문: "이름을 고쳐"'}, status="완료", **OLD)
    body = write(tmp_path / "body.md", "## 범위\n- 고침\n\n## 판정 기준\n1. 이름이 바뀐다\n\n## 건드릴 파일\n- src/a.ts\n")
    assert task_set.main(["task_set.py", str(run_dir.path), "new", "--from-answer", "T001", "--title", "고침", "--flow", "a",
                          "--body-from", str(body)]) == 0
    assert lib.ANSWER_CRITERION not in (run_dir.task_dir("T002") / "task.md").read_text(encoding="utf-8")


def test_change_from_an_answer_gets_no_criterion(run_dir, lib, monkeypatch, tmp_path):
    monkeypatch.setattr(lib, "harness_version", lambda: "1.2.0-dev.1")
    run_dir.task("T001", "앞", {"승인 기록": '- 2026-11-05 10:00:00 | 답 | 고침 | 원문: "이름을 고쳐"'}, status="완료", **NEW)
    body = write(tmp_path / "body.md", "## 범위\n- 고침\n\n## 판정 기준\n1. 이름이 바뀐다\n\n## 건드릴 파일\n- spec/a.md\n")
    assert task_set.main(["task_set.py", str(run_dir.path), "new", "--from-answer", "T001", "--title", "고침", "--body-from", str(body)]) == 0
    assert lib.ANSWER_CRITERION not in (run_dir.task_dir("T002") / "task.md").read_text(encoding="utf-8")
