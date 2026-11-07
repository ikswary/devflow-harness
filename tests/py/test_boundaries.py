"""1.2.0 A10 흐름별 책임 경계(설계 7.4절)와 답의 표지.

- 7.4절이 kind 문서에 넣는 기준마다 작성자 문장과 판정자 문장이 함께 있다(문서대로 쓴 작성자를 판정자가 실패시키지 않게).
- 위험 수용 표지는 한 문장이고, 적은 표지가 실행 지도와 마무리 입력에 실제로 뽑힌다.
"""
import pytest

import collect
import devflow_lib as lib
import visual
from conftest import ROOT, run_script
from test_review_contract import NEW, result


def doc(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(rel, name):
    return lib.sections(doc(rel), level=2).get(name, "")


@pytest.mark.parametrize("rel,writer,judge", [
    # (가) 로컬 가정: 작성자가 닫고, 판정자는 읽어 닫을 수 있는 것만 실패로 적는다
    ("references/kinds/design.md", "직접 읽어 닫고", "파일을 읽어 닫을 수 있는 가정이 남아 있으면 실패(실행이나 dev·배포가 필요한 가정은 넘겨도 된다)"),
    # (나) 다시 만드는 화면
    ("references/kinds/ui-design/rebuild.md", "기준본대로 다시 만듦", "집합 대조에서 뺀다"),
    ("references/kinds/ui-design/rebuild.md", "기준본대로 다시 만듦", "표본으로 열어"),
    ("references/kinds/fe-implementation.md", "시험 표식", "다시 만드는 화면은 조작 표 요소 칸의 요소 id"),
    ("references/kinds/fe-implementation.md", "시험 표식", "이 행이 닫는 조작 표 행 가운데 관찰 방법이 시험인 행마다"),
    # (라) 미룬 실물 확인
    ("references/kinds/deploy-plan.md", "미룬 실물 확인은 사람이 볼 것으로 옮긴다", "미룬 실물 확인이 배포 뒤 확인의 사람이 볼 것에 빠짐없이"),
    # (다) 설계에 없던 선택
    ("references/practices/code-task.md", "결정 종류로 칸을 가른다", "사용자 결정이 아닌지(그렇다면 실패)"),
    # (마) 부정 전제
    ("references/kinds/req-detail.md", "찾아본 방법(검색어, 범위, 결과 건수)", "같은 검색을 다시 돌려 본다"),
    # (바) 앞으로의 계획
    ("references/kinds/brief.md", "「앞으로의 계획」 줄:", "「앞으로의 계획」 줄이 있거나 「정해 주실 것」에 있다"),
    # (사) 탐침에 기대는 선택지
    ("references/roles/writer.md", "그 결정에서 닫고 탐침 행을 먼저", "`[탐침]` 가정에 기대는 선택지가 열린 채 있거나"),
    # (아) 전체 검증의 관점
    ("references/kinds/design/run-wide.md", "흐름별 검증이 그것을 볼 수 없는 이유", "그 줄이 없거나 흐름 하나 안의 일이면 실패"),
])
def test_writer_and_judge_sentences_go_together(rel, writer, judge):
    text = doc(rel)
    assert writer in text and judge in text


def test_rebuilt_screen_has_what_the_judges_compare():
    # 판정이 대조할 요소 집합을 잃지 않게 요소 칸은 요소 id를 지닌다. 요소 표와 와이어프레임은 두지 않으므로 그 대조에서는 뺀다
    spec = doc("references/practices/ui-spec.md")
    assert "`{요소 id} ← {기준본 파일:줄이나 선택자}`" in spec and "요소 표와 와이어프레임은 두지 않는다" in spec
    assert "다시 만드는 화면은 조작 표의 행마다" in doc("references/kinds/design/ui-spec.md")


def test_rebuilt_screen_is_a_ui_design_target_in_the_brief():
    brief = doc("references/kinds/brief.md")
    assert brief.count("기준본대로 다시 만듦") >= 3
    assert "실행 폴더에 `ui\\rules.md`가 없고 화면 목록에 \"새로 그림\"인 화면이 있을 때만" in brief   # UI 규약 행의 조건은 그대로다


def test_new_infra_decision_has_a_line_the_main_can_edit():
    # 인프라 정본에 없는 결정도 `지금:`이 있어야 메인이 Edit한다
    rows = doc("references/kinds/design/rows.md")
    assert "넣을 곳의 줄을 `지금:`에" in rows
    assert "`design\\infra.md`" in doc("references/kinds/design/checks.md") and "`design\\infra.md`의 `앞 정본 줄`" in rows


def test_full_verify_does_not_retrace_and_wrap_up_takes_the_owner():
    assert "흐름이 닫은 인수 기준은 다시 추적하지 않고" in doc("references/kinds/verify/after-flow.md")
    assert "기준마다 소유한 검증의 판정" in doc("references/kinds/wrap-up.md")


def test_deferred_check_reaches_the_deploy_plan_judge():
    assert "미룬 실물 확인이 배포 뒤 확인의 사람이 볼 것에 빠짐없이" in doc("references/kinds/deploy-plan.md")
    assert "미룸({확인할 곳})" in doc("references/kinds/verify.md")


@pytest.mark.parametrize("rel", ["references/formats/run-files.md", "references/kinds/wrap-up/main-order.md",
                                 "references/main/selfcheck.md", "references/main/delegation.md"])
def test_risk_mark_is_one_sentence(rel):
    text = doc(rel)
    assert lib.RISK_SENTENCE in text
    assert "백로그에 한 줄" not in text and "백로그 한 줄" not in text


@pytest.mark.parametrize("rel,sentence", [
    ("references/kinds/ui-design.md", "그 묶음의 설계 task는 상세가 이미 만들었고 이 task에 의존한다"),
    ("references/kinds/ui-design.md", "원 산출물은 머리 파일 「건드릴 파일」의 `ui\\{묶음}.md`와 `ui\\wireframes\\{묶음}.html`이고"),
    ("references/kinds/verify.md", "메인의 기억으로 목록을 만들지 않는다"),
    ("references/kinds/deploy-exec/main-order.md", "해석해 줄이지 않는다"),
])
def test_rule_sentences_outside_this_work_stay(rel, sentence):
    assert sentence in doc(rel)


def test_screens_all_rebuilt_have_no_wireframe_to_draw():
    text = doc("references/kinds/ui-design/rebuild.md")
    assert "와이어프레임: 없음" in text and "그릴 화면이 있을 때" in doc("references/kinds/brief.md")
    assert "기준본 위치" in text


def test_hand_over_docs_use_the_own_point():
    line = '`--record "하실 일 넘김|[하실 일 넘김 T0xx] {항목}|{원문}"`'
    assert line in doc("references/main/delegation.md") and line in doc("references/kinds/probe/main-order.md")
    assert "대기 뒤의 바로 다음 답만" in doc("references/main/delegation.md")


def test_judge_docs_say_how_to_add_a_property():
    assert "성질 더함: {항목 앞부분} {성질}" in doc("references/formats/judge-file.md")
    assert "`위험`은 실패로 적는다" in doc("references/formats/judge-file.md")   # writer.md와 같게 읽힌다
    assert "배포 명령 목록의 첫 승인" in doc("references/main/delegation.md")
    assert "--refreeze" in doc("references/main/delegation.md")
    assert "성질 더함" in doc("references/roles/writer.md")


def test_task_set_guide_is_the_same_sentence():
    source = (ROOT / "scripts" / "task_set.py").read_text(encoding="utf-8")
    assert "RISK_SENTENCE" in source and "백로그 한 줄" not in source


def test_approval_points_to_the_marks_without_the_old_wording():
    text = doc("references/main/approval.md")
    assert "위험 받아들임" not in text and "위임과 답의 표지" in text


def test_marked_risk_is_one_line_in_the_list(run_dir):
    run_dir.task("T010", "마무리", {"승인 기록": '- 2026-11-05 10:00:00 | 승인 | 위험 수용 | 원문: "그대로 넣자"'}, kind="wrap-up", status="완료", **NEW)
    (run_dir.path / "decisions.md").write_text('- 2026-11-05 10:00 | [위험 수용 T010] 최종 CI 실패 두 건 | 원문: "그대로 넣자" | T010\n', encoding="utf-8")
    assert [r[:2] for r in collect.risk_accepted(str(run_dir.path))] == [("T010", "최종 CI 실패 두 건")]


def test_marks_reach_first_look_of_the_wrap_up_review(run_dir):
    """적은 표지가 마무리 리뷰의 「먼저 보실 것」에 실제로 실린다."""
    deferred = '- 2026-11-05 10:00:00 | 실물 확인 | [실물 확인 미룸] 실기기 스와이프 → 배포 실행의 배포 뒤 확인 | 원문: "나중에 볼게요"'
    risk = '- 2026-11-05 10:01:00 | 승인 | 위험 수용 | 원문: "그대로 넣자"'
    run_dir.task("T010", "검증 pick", {"승인 기록": deferred + "\n" + risk}, kind="flow-verify", flow="pick", status="완료", **NEW)
    run_dir.result("T010", result())
    run_dir.task("T020", "마무리", kind="wrap-up", status="승인대기", **NEW)
    run_dir.result("T020", result())
    (run_dir.path / "decisions.md").write_text('- 2026-11-05 10:01 | [위험 수용 T010] 최종 CI 실패 두 건 | 원문: "그대로 넣자" | T010\n', encoding="utf-8")
    lines = visual.review_lines(str(run_dir.path), "T020")
    at = next(i for i, line in enumerate(lines) if visual.FIRST_TITLE in line)
    first = []
    for line in lines[at + 1:]:
        if line.startswith("#"):
            break
        first.append(line)
    assert any("최종 CI 실패 두 건" in line for line in first), lines
    assert any("실기기 스와이프" in line for line in first), lines


def test_another_risk_answer_of_the_same_task_stays(run_dir):
    records = '- 2026-11-05 10:00:00 | 승인 | 위험 수용 | 원문: "그대로 넣자"\n- 2026-11-05 11:00:00 | 승인 | 위험 수용 | 원문: "문서 실패도 받아들임"'
    run_dir.task("T010", "마무리", {"승인 기록": records}, kind="wrap-up", status="완료", **NEW)
    (run_dir.path / "decisions.md").write_text('- 2026-11-05 10:00 | [위험 수용 T010] 최종 CI 실패 두 건 | 원문: "그대로 넣자" | T010\n', encoding="utf-8")
    got = [r[1] for r in collect.risk_accepted(str(run_dir.path))]
    assert got[0] == "최종 CI 실패 두 건" and len(got) == 2 and "문서 실패도" in got[1]


def test_deferred_mark_goes_into_the_unverified_list(run_dir):
    line = '- 2026-11-05 10:00:00 | 실물 확인 | [실물 확인 미룸] 실기기 스와이프 → 배포 실행의 배포 뒤 확인 | 원문: "dev 올린 뒤 볼게요"'
    run_dir.task("T010", "검증", {"승인 기록": line}, kind="flow-verify", status="완료", **NEW)
    run_dir.result("T010", result(unverified="- 판정불가 하나"))
    run_dir.task("T011", "검증 끝나지 않음", {"승인 기록": line}, kind="flow-verify", status="승인대기", **NEW)
    p = run_script("collect", run_dir.path, run_dir.path)
    assert p.returncode == 0, p.output
    text = (run_dir.path / "unverified-list.md").read_text(encoding="utf-8")
    assert "- 판정불가 하나\n" in text and "- [실물 확인 미룸] 실기기 스와이프 → 배포 실행의 배포 뒤 확인" in text.split("## T011")[0]
    assert "## T011" in text   # 닫히기 전의 표지도 잃지 않는다


def test_deferred_mark_survives_a_task_without_a_screen(run_dir):
    line = '- 2026-11-05 10:00:00 | 실물 확인 | [실물 확인 미룸] 스와이프 → 배포 메모 | 원문: "나중에"'
    run_dir.task("T010", "검증", {"승인 기록": line}, kind="flow-verify", status="완료", **NEW)
    p = run_script("collect", run_dir.path, run_dir.path)
    assert p.returncode == 3
    assert "[실물 확인 미룸] 스와이프" in (run_dir.path / "unverified-list.md").read_text(encoding="utf-8")


def test_deferred_line_is_not_an_approval_of_the_task():
    assert not lib.approval_line('- 2026-11-05 10:00:00 | 실물 확인 | [실물 확인 미룸] 스와이프 → 배포 메모 | 원문: "나중에"')


def test_delegated_answers_are_counted_as_bulk_not_as_a_person(run_dir):
    run_dir.task("T010", "구현", {"승인 기록": '- 2026-11-05 10:00:00 | 승인 | 위임 L1 | 원문: "dev 배포까지 전부 맡아"'}, kind="implementation", status="완료", approval_mode="승인", **NEW)
    assert collect.is_bulk(run_dir.tasks()["T010"])
    assert not collect.is_asked(run_dir.tasks()["T010"])
    assert collect.decision_row('- 2026-11-05 10:00 | 위임 L2~L3 | 원문: "dev 배포까지 맡아" | 실행 전체')[2] == "위임"
