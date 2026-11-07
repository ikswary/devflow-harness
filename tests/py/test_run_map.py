"""1.2.0 A6: 실행 지도(`visual.py --run`)와 위험 수용 표지(`collect.py`의 `risk-accepted.md`). 설계 7.3절, 7.4절 (라).

- 지도는 값이 있는 칸만 쓴다. 제목도 남기지 않는다.
- 흐름이 하나 이하인 실행의 줄기는 한 줄이고, 따로 두는 줄(대기열, 위험 수용 …)은 그대로 남는다.
- 지도의 정책 줄기, 바뀐 정책, 규약으로 덮인 곳, 자동으로 정한 것은 1.3.0이라 쓰지 않는다.
"""
import os

import collect
import visual
from conftest import run_script, write

VERIFY_RESULT = ("## 승인 화면\n### 알릴 것\n- 없음\n\n## 본문\n### 인수 기준 추적\n"
                 "| 인수 기준 | 확인 방법 | 판정 | 근거 |\n|---|---|---|---|\n"
                 "| AC-1 가입 | 시험 | 통과 | a.test:1 |\n| AC-2 탈퇴 | 시험 | 실패 | a.test:2 |\n")


def two_flows(run_dir):
    """요구사항 → 설계 → 구현 → 검증이 흐름 둘로 갈린 실행."""
    write(run_dir.path / "spec" / "query.md", "## 인수 기준\n| AC | 문장 |\n|---|---|\n| AC-1 | 가 |\n| AC-2 | 나 |\n")
    run_dir.task("T001", "상세 query", {"건드릴 파일": "- spec/query.md\n- spec/overview.md"}, kind="req-detail", block="요구사항", status="완료")
    run_dir.task("T002", "설계 query", kind="design", block="설계", status="완료", parent="T001", flow="query")
    run_dir.task("T003", "구현 query", kind="implementation", block="구현", status="완료", parent="T002", flow="query",
                 closes_ac=["AC-1", "AC-2"])
    run_dir.task("T004", "검증 query", kind="flow-verify", block="검증", status="완료", parent="T002", flow="query")
    run_dir.result("T004", VERIFY_RESULT)
    run_dir.task("T005", "구현 pick", kind="implementation", block="구현", status="진행", flow="pick")
    run_dir.flow("query", status="합쳐짐")
    run_dir.flow("pick", status="진행")


def one_flow(run_dir):
    write(run_dir.path / "spec" / "query.md", "| AC-1 | 가 |\n")
    run_dir.task("T001", "상세 query", {"건드릴 파일": "- spec/query.md"}, kind="req-detail", block="요구사항", status="완료")
    run_dir.task("T002", "구현 query", kind="implementation", block="구현", status="완료", parent="T001", flow="query", closes_ac=["AC-1"])
    run_dir.flow("query", status="합쳐짐")


def run_map(run_dir, *extra):
    proc = run_script("visual", run_dir, "--run", *extra)
    assert proc.returncode == 0, proc.output
    return proc.stdout.splitlines()


def without_path(lines):
    assert lines[-1].startswith("전체: ")
    return lines[:-1]


def test_empty_cells_write_no_line(run_dir):
    two_flows(run_dir)
    lines = without_path(run_map(run_dir))
    assert lines == [
        "■ 실행 지도: dryrun · task 5개 · 흐름 2개",
        "## 요구사항", "- 묶음 query (상세 T001, 완료): 인수 기준 2개",
        "## 흐름",
        "- 요구사항: T001 완료",
        "- query (합쳐짐): T002 완료, T003 완료, T004 완료",
        "- pick (진행): T005 진행",
        "## 증거", "- query: 닫은 인수 기준 2개(T003), T004 통과 1 · 실패 1"]


def test_later_policy_lines_are_not_written(run_dir):   # 1.3.0으로 미룬 줄
    two_flows(run_dir)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | 칸 이름은 짧게 | 원문: "ㅇ" | T002\n')
    text = "\n".join(run_map(run_dir))
    for word in ("## 정책", "바뀐 정책", "규약으로 덮인", "자동으로 정한", "정책 대기"):
        assert word not in text


def test_one_flow_run_is_one_line(run_dir):
    one_flow(run_dir)
    lines = run_map(run_dir)
    full = run_dir.path / "run-map.md"
    assert lines == ["■ 실행 지도: dryrun 흐름 query 하나 | 요구사항 묶음 1개(인수 기준 1) | task 2개(완료 2) | 닫은 인수 기준 1 | 전체: {}".format(
        os.path.abspath(full))]
    # 한 줄로 줄여도 펼친 지도는 파일에 있다
    assert "## 흐름" in full.read_text(encoding="utf-8")


def test_one_flow_run_keeps_separate_lines(run_dir):
    one_flow(run_dir)
    run_dir.task("T003", "구현 더", kind="implementation", block="구현", status="승인대기", flow="query", n_decide="1",
                 approval_requested="2026-11-01 10:00:00")
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [위험 수용 T002] 옛 사이트 탈퇴 결함 | 원문: "그대로 둠" | T002\n')
    lines = run_map(run_dir)
    assert lines[0].startswith("■ 실행 지도: dryrun 흐름 query 하나")
    assert lines[1:] == ["## 받아들인 위험", "- T002 옛 사이트 탈퇴 결함",
                         "## 승인 대기열", "- T003 구현 더 | 자리: query | 막고 있는 task 0개 | 정해 주실 것 1건 | 요청 2026-11-01 10:00:00"]


def test_no_flow_run_is_also_one_line(run_dir):
    run_dir.task("T001", "질문", kind="question", block="요구사항", status="완료")
    assert run_map(run_dir)[0].startswith("■ 실행 지도: dryrun 흐름 없음 | task 1개(완료 1)")


def test_integration_flow_does_not_count_as_a_flow(run_dir):
    one_flow(run_dir)
    run_dir.flow("integration", role="integration", status="진행")
    assert len(run_map(run_dir)) == 1


def test_queue_shows_where_and_what_it_blocks(run_dir):
    two_flows(run_dir)
    run_dir.task("T006", "검증 pick", kind="flow-verify", block="검증", status="승인대기", flow="pick", n_decide="2",
                 approval_requested="2026-11-01 10:00:00")
    run_dir.task("T007", "마무리", kind="wrap-up", block="마무리", status="대기", depends_on=["T006"])
    run_dir.task("T008", "설계 더", kind="design", block="설계", status="승인대기", approval_requested="2026-11-01 11:00:00")
    lines = run_map(run_dir)
    at = lines.index("## 승인 대기열")
    assert lines[at + 1:at + 3] == [
        "- T006 검증 pick | 자리: pick | 막고 있는 task 1개: T007 | 정해 주실 것 2건 | 요청 2026-11-01 10:00:00",
        "- T008 설계 더 | 자리: 설계 | 막고 있는 task 0개 | 정해 주실 것 0건 | 요청 2026-11-01 11:00:00"]


def test_decisions_show_who_decided(run_dir):
    two_flows(run_dir)
    write(run_dir.path / "decisions.md",
          '- 2026-11-01 10:00 | 칸 이름은 짧게. 이유는 길다 | 원문: "ㅇㅋ" | T002\n'
          '- 2026-11-01 11:00 | 나머지 진행 | 원문: "나머지 자동 승인" | T004\n'
          '- 2026-11-01 12:00 | 옛 결정 → 대체: 2026-11-01 13:00 | 원문: "아니" | T002\n'
          '- 2026-11-01 13:00 | [위험 수용 T003] 항목 | 원문: "그대로" | T003\n')
    run_dir.result("T002", "## 승인 화면\n### 알릴 것\n- 칸 이름을 정했습니다\n- 빈 값은 null입니다\n")
    lines = run_map(run_dir)
    at = lines.index("## 결정")
    assert lines[at + 1:at + 5] == [
        "- 사람 2026-11-01 10:00 | 칸 이름은 짧게. (T002)",
        "- 위임 2026-11-01 11:00 | 나머지 진행 (T004)",
        "- 작성자 T002: 알릴 결정 2건",
        "- 대체되어 뺀 결정 1개"]


def test_old_decision_lines_are_not_lost(run_dir):   # 옛 실행의 꼴: 결정 칸을 `|`로 나눔, 원문에 `|`, 메인 판단
    two_flows(run_dir)
    write(run_dir.path / "decisions.md",
          "# 결정\n"
          '- 2026-11-01 10:00 | 대상 MCP | 백오피스 도구 | 원문: "백오피스 | 도구" | T001\n'
          '- 2026-11-01 11:00 | 요청 종류 | 기능 변경 | 메인 판단(동작이 바뀜)\n'
          "- 2026-11-01 12:00 | 꼴을 모르는 줄\n"
          '- 2026-11-01 13:00 | T015 | 칸 | 원문: 따옴표 없음 | T015\n')
    lines = run_map(run_dir)
    at = lines.index("## 결정")
    assert lines[at + 1:at + 5] == [
        "- 사람 2026-11-01 10:00 | 대상 MCP | 백오피스 도구 (T001)",
        "- 메인 2026-11-01 11:00 | 요청 종류 | 기능 변경",
        "- 사람 2026-11-01 13:00 | T015 | 칸 (T015)",
        "- 읽지 못한 결정 줄 1개(decisions.md를 직접 본다)"]


def decision_of(line):
    return collect.decision_row(line)


def test_real_record_forms_keep_related_to_task_numbers():   # 실제 기록의 꼴: 따옴표 둘, 따옴표 뒤의 글, 뒤에 붙은 추천
    assert decision_of('- t | 고름 | 원문: "a" / "b" | T001') == ("t", "고름", "사람", "T001")
    assert decision_of('- t | 고름 | 원문: "다시 말해", "승인" | T012') == ("t", "고름", "사람", "T012")
    assert decision_of('- t | 고름 | 원문: "둘째" → 추천 (가) | T045') == ("t", "고름", "사람", "T045")
    assert decision_of('- t | 고름 | 원문: "T001 말대로"') == ("t", "고름", "사람", "")
    assert decision_of('- t | 고름 | 원문: "앞 | T001 말대로"') == ("t", "고름", "사람", "")
    assert decision_of('- t | 고름 | 원문: "둠" | 진행 중 실행과 분리') == ("t", "고름", "사람", "")


def test_delegation_reads_the_whole_original_and_negation():
    assert decision_of('- t | 진행 | 원문: 나머지 자동 승인 | T1')[2] == "위임"
    assert decision_of('- t | 진행 | 원문: "먼저", "나머지 자동" | T1')[2] == "위임"
    assert decision_of('- t | 진행 | 원문: "자동 승인은 하지 마" | T1')[2] == "사람"


def test_main_judged_line_with_a_related_task():
    assert decision_of("- t | 다섯 | 메인 판단(이유) | T002") == ("t", "다섯", "메인", "T002")
    assert decision_of("- t | 다섯 | 메인 판단(이유)") == ("t", "다섯", "메인", "")
    assert decision_of("- t | 메인 판단만") is None


def test_design_waiting_approval_notices_are_not_counted(run_dir):   # 끝나지 않은 설계의 알릴 것은 아직 결정이 아니다
    two_flows(run_dir)
    run_dir.task("T002", "설계 query", kind="design", block="설계", status="승인대기", parent="T001", flow="query")
    run_dir.result("T002", "## 승인 화면\n### 알릴 것\n- 칸 이름을 정했습니다\n")
    assert "결정" not in dict(visual.map_sections(str(run_dir.path)))


def test_partial_pass_row_is_counted_as_other(run_dir):   # 실제 판정 칸: 부분 통과, 사람 지시로 제외
    two_flows(run_dir)
    run_dir.result("T004", VERIFY_RESULT + "| AC-3 | 시험 | 부분 통과 | - |\n| AC-4 | - | 사람 지시로 제외 | - |\n| AC-5 | 시험 | 판정불가 환경 | - |\n")
    assert "- query: 닫은 인수 기준 2개(T003), T004 통과 1 · 실패 1 · 판정불가 1 · 기타 2" in run_map(run_dir)


def test_verify_table_without_verdict_column(run_dir):
    two_flows(run_dir)
    run_dir.result("T004", "## 본문\n| 인수 기준 | 근거 |\n|---|---|\n| AC-1 | a |\n")
    assert "- query: 닫은 인수 기준 2개(T003), T004 인수 기준 1개" in run_map(run_dir)


def test_closed_acs_do_not_double_count(run_dir):
    two_flows(run_dir)
    run_dir.task("T006", "구현 더", kind="implementation", block="구현", status="완료", flow="query", closes_ac=["AC-2", "AC-3"])
    assert "- query: 닫은 인수 기준 3개(T003, T006), T004 통과 1 · 실패 1" in run_map(run_dir)


def test_open_task_closes_nothing_in_the_map(run_dir):
    two_flows(run_dir)
    run_dir.task("T005", "구현 pick", kind="implementation", block="구현", status="진행", flow="pick", closes_ac=["AC-9"])
    assert not any(line.startswith("- pick: ") for line in run_map(run_dir))


def test_open_task_closes_nothing_in_the_one_line(run_dir):
    one_flow(run_dir)
    run_dir.task("T003", "구현 더", kind="implementation", block="구현", status="진행", flow="query", closes_ac=["AC-9"])
    assert "닫은 인수 기준 1 |" in run_map(run_dir)[0]


def test_one_line_counts_shared_acs_once(run_dir):
    one_flow(run_dir)
    run_dir.task("T003", "구현 더", kind="implementation", block="구현", status="완료", flow="query", closes_ac=["AC-1"])
    assert "닫은 인수 기준 1 |" in run_map(run_dir)[0]


def test_one_line_keeps_bad_values_and_round(run_dir):
    one_flow(run_dir)
    p = run_dir.path / "run.md"
    p.write_text(p.read_text(encoding="utf-8").replace("round: 1", "round: 3"), encoding="utf-8")
    run_dir.task("T003", "검증", kind="flow-verify", block="검증", status="완료", flow="query")
    run_dir.result("T003", VERIFY_RESULT)
    run_dir.task("T004", "배포", kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지")
    run_dir.task("T005", "배포 둘", kind="deploy-exec", block="배포", status="완료", deploy_outcome="되돌림")
    line = run_map(run_dir)[0]
    assert line.startswith("■ 실행 지도: dryrun 회차 3 흐름 query 하나")
    assert "통과 아닌 판정 1" in line and "마지막 배포 되돌림" in line


def test_one_line_separate_lines_are_masked(run_dir):
    one_flow(run_dir)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [위험 수용 T002] token=abcdef123456 노출 | 원문: "둠" | T002\n')
    assert "abcdef123456" not in "\n".join(run_map(run_dir))


def test_prefixed_ac_ids_are_counted(run_dir):   # 실제 정본: `| E-AC-1 | E-FR-1 | …`
    write(run_dir.path / "spec" / "edit.md", "| E-AC-1 | E-FR-1, E-FR-4 | 가 |\n| E-AC-2 | E-FR-1 | 나 |\n| AC-CL-1 | FR-1 | 다 |\n")
    run_dir.task("T001", "상세", {"건드릴 파일": "spec/edit.md"}, kind="req-detail", block="요구사항", status="완료")
    assert visual.requirement_lines(str(run_dir.path), run_dir.tasks()) == ["- 묶음 edit (상세 T001, 완료): 인수 기준 3개"]


def test_screen_trace_table_keeps_its_old_ac_pattern():   # 옛 task의 「보는 자료」는 그대로다
    assert visual.AC_HEAD_RE.match("| E-AC-1 | E-FR-1 |") is None


def test_spec_without_a_task_still_shows(run_dir):   # 옛 실행: 정본은 있고 task가 가리키지 않는다
    write(run_dir.path / "spec" / "old.md", "| AC-1 | 가 |\n")
    write(run_dir.path / "spec" / "overview.md", "| AC-9 | 개요 |\n")
    run_dir.task("T001", "요구사항", {"건드릴 파일": "(없음)"}, kind="req-detail", block="요구사항", status="완료")
    assert visual.requirement_lines(str(run_dir.path), run_dir.tasks()) == ["- 묶음 old (상세 -): 인수 기준 1개"]
    assert visual.requirement_lines(str(run_dir.path), run_dir.tasks(), parent="T009") == []


def test_redone_detail_is_the_owner(run_dir):
    write(run_dir.path / "spec" / "a.md", "| AC-1 | 가 |\n")
    run_dir.task("T001", "상세 a", {"건드릴 파일": "spec/a.md"}, kind="req-detail", block="요구사항", status="보류")
    run_dir.task("T002", "상세 a 다시", {"건드릴 파일": "spec/a.md"}, kind="req-detail", block="요구사항", status="완료")
    run_dir.task("T003", "상세 a 또", {"건드릴 파일": "spec/a.md"}, kind="req-detail", block="요구사항", status="백로그")
    run_dir.task("T004", "설계", kind="design", block="설계", status="완료", parent="T002", flow="q")
    assert visual.requirement_lines(str(run_dir.path), run_dir.tasks()) == ["- 묶음 a (상세 T002, 완료): 인수 기준 1개"]
    assert visual.flow_place(str(run_dir.path), "q") == "실행 지도: 요구사항 묶음 a(상세 T002) / 흐름 하나"


def test_held_deploy_stays_and_says_so(run_dir):   # 실제 T019: 보류인데 배포는 남았다
    two_flows(run_dir)
    run_dir.task("T006", "배포", kind="deploy-exec", block="배포", status="보류", deploy_outcome="유지", deployed_commit="afd22cf")
    assert "- T006 배포 유지 afd22cf (task 보류)" in run_map(run_dir)


def test_change_tasks_have_their_own_lane(run_dir):   # 실제 mcp: 변경 task 13개가 기타로 묶였다
    run_dir.task("T001", "변경", kind="change", block="", status="완료")
    run_dir.task("T002", "기획", kind="brief", block="", status="완료")
    assert dict(visual.map_sections(str(run_dir.path)))["흐름"] == ["- 변경: T001 완료", "- 기획: T002 완료"]


def test_verify_task_notices_are_not_writer_decisions(run_dir):   # 검증의 「알릴 것」은 결정이 아니다
    two_flows(run_dir)
    run_dir.result("T004", "## 승인 화면\n### 알릴 것\n- 다시 돌렸습니다\n")
    assert "## 결정" not in run_map(run_dir)


def test_deploy_line_and_round(run_dir):
    two_flows(run_dir)
    (run_dir.path / "run.md").write_text((run_dir.path / "run.md").read_text(encoding="utf-8").replace("round: 1", "round: 2"), encoding="utf-8")
    run_dir.flow("pick", status="진행", round="2")
    run_dir.task("T006", "마무리", kind="wrap-up", block="마무리", status="완료", exported_commit="abc1234")
    run_dir.task("T007", "배포", kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지", deployed_commit="def5678")
    lines = run_map(run_dir)
    assert lines[0] == "■ 실행 지도: dryrun · 회차 2 · task 7개 · 흐름 2개"
    assert "- pick (진행, 회차 2): T005 진행" in lines
    at = lines.index("## 명령·배포")
    assert lines[at + 1:at + 3] == ["- T006 내보냄 abc1234", "- T007 배포 유지 def5678"]


def test_baseline_lines(run_dir):
    two_flows(run_dir)
    write(run_dir.path / "recon.md", "## 기준선\n- `a.test` 실패 | 이유 첫 줄\n- 없음\n\n## 합치기 관례\n- 기준선 아닌 줄\n")
    with open(run_dir.path / "run.md", "a", encoding="utf-8") as f:
        f.write("\n기준선: 물을 실패 0\n")
    lines = run_map(run_dir)
    at = lines.index("## 기준선")
    assert lines[at + 1:at + 3] == ["- `a.test` 실패 | 이유 첫 줄", "- 기준선: 물을 실패 0"]
    assert "기준선 아닌 줄" not in "\n".join(lines)


def test_request_text_mentioning_baseline_is_not_a_line(run_dir):
    two_flows(run_dir)
    p = run_dir.path / "run.md"
    p.write_text(p.read_text(encoding="utf-8").replace("마른 시험", "기준선을 고쳐 주세요"), encoding="utf-8")
    assert "## 기준선" not in run_map(run_dir)


def test_excluded_checks_and_what_went_unverified(run_dir):
    two_flows(run_dir)
    p = run_dir.path / "run.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "| 수정 세대 상한 | 2 |\n", '| 수정 세대 상한 | 2 |\n| 검증 제외 | 변이시험 \\| 이번 세션 \\| 끝까지 \\| 원문 "제외" |\n'), encoding="utf-8")
    run_dir.result("T003", "## 승인 화면\n### 확인 안 된 것\n- 변이 확인: 사람 지시로 제외\n- 다른 것\n")
    write(run_dir.task_dir("T003") / "judge-run.md", "## 통과 못 한 기준\n- 없음\n\n변이 2: 사람 지시로 제외\n")
    lines = run_map(run_dir)
    at = lines.index("## 뺀 검증")
    assert lines[at + 1:at + 4] == ['- 검증 제외: 변이시험 | 이번 세션 | 끝까지 | 원문 "제외"',
                                    "- T003 확인 안 된 것: - 변이 확인: 사람 지시로 제외",
                                    "- T003 judge-run.md: 변이 2: 사람 지시로 제외"]


def test_deferred_check_line_and_closing(run_dir):
    two_flows(run_dir)
    run_dir.task("T006", "검증 pick", {"승인 기록": '- 2026-11-01 10:00:00 | 승인 | [실물 확인 미룸] 실기기 스와이프 → 배포 실행의 배포 뒤 확인 | 원문: "dev에서 볼게"\n'
                                                 '- 2026-11-01 10:00:01 | 승인 | [실물 확인 미룸] 메일 모양 → 마무리의 배포 메모 | 원문: "나중에"'},
                 kind="flow-verify", block="검증", status="완료", flow="pick")
    lines = run_map(run_dir)
    at = lines.index("## 미룬 실물 확인")
    assert lines[at + 1:at + 3] == ["- 실기기 스와이프 | 미룬 흐름 리뷰 T006 | 확인할 곳 배포 실행의 배포 뒤 확인 | 안 닫힘",
                                    "- 메일 모양 | 미룬 흐름 리뷰 T006 | 확인할 곳 마무리의 배포 메모 | 안 닫힘"]
    # 유지이지만 항목 글이 없으면 닫지 않는다. 글이 있는 항목만 닫힌다
    run_dir.task("T007", "배포", {"승인 기록": '- 2026-11-02 10:00:00 | 결과승인 | 승인 | 원문: "유지, 메일  모양 확인함"'},
                 kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지")
    lines = run_map(run_dir)
    at = lines.index("## 미룬 실물 확인")
    assert lines[at + 1:at + 3] == ["- 실기기 스와이프 | 미룬 흐름 리뷰 T006 | 확인할 곳 배포 실행의 배포 뒤 확인 | 배포 유지 T007, 확인 답 못 찾음",
                                    "- 메일 모양 | 미룬 흐름 리뷰 T006 | 확인할 곳 마무리의 배포 메모 | 닫힘 T007"]


def deferred_task(run_dir, tid="T002"):
    run_dir.task(tid, "검증", {"승인 기록": '- 2026-11-01 10:00:00 | 승인 | [실물 확인 미룸] 스와이프 → 배포 실행의 배포 뒤 확인 | 원문: "ㅇ"'},
                 kind="flow-verify", block="검증", status="완료", flow="q")


def deferred_state(run_dir):
    return collect.deferred_checks(str(run_dir.path), run_dir.tasks())[0][3]


def test_deferred_closed_by_text_in_judge_run_file(run_dir):
    deferred_task(run_dir)
    run_dir.task("T007", "배포", kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지")
    write(run_dir.task_dir("T007") / "judge-run.md", "## 배포 뒤 확인\n- 스와이프: 통과\n")
    assert deferred_state(run_dir) == "닫힘 T007"


def test_rollback_deploy_does_not_close(run_dir):
    deferred_task(run_dir)
    run_dir.task("T007", "배포", {"승인 기록": '- 2026-11-02 10:00:00 | 결과승인 | 승인 | 원문: "스와이프 안 됨, 되돌림"'},
                 kind="deploy-exec", block="배포", status="완료", deploy_outcome="되돌림")
    assert deferred_state(run_dir) == "안 닫힘"


def test_finished_wrap_up_hands_over_to_the_note(run_dir):
    deferred_task(run_dir)
    run_dir.task("T008", "마무리", kind="wrap-up", block="마무리", status="승인대기")
    assert deferred_state(run_dir) == "안 닫힘"
    run_dir.task("T008", "마무리", kind="wrap-up", block="마무리", status="완료")
    assert deferred_state(run_dir) == "배포 메모로 넘김 T008"
    # 뒤에 배포가 유지로 끝났으면 사람이 다시 볼 곳은 그 배포다
    run_dir.task("T009", "배포", kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지")
    assert deferred_state(run_dir) == "배포 유지 T009, 확인 답 못 찾음"


def test_earlier_deploy_does_not_close_a_later_deferral(run_dir):   # 회차가 있는 실행
    run_dir.task("T001", "앞 배포", {"승인 기록": '- 2026-11-01 09:00:00 | 결과승인 | 승인 | 원문: "스와이프 봄"'},
                 kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지")
    run_dir.task("T000", "앞 마무리", kind="wrap-up", block="마무리", status="완료")
    deferred_task(run_dir)
    assert collect.deferred_checks(str(run_dir.path), run_dir.tasks()) == [("T002", "스와이프", "배포 실행의 배포 뒤 확인", "안 닫힘")]


def test_deferred_mark_without_a_task_is_not_closed(run_dir):   # 앞뒤를 모르면 닫았다고 하지 않는다
    run_dir.task("T002", "배포", kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지")
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [실물 확인 미룸] 스와이프 → 배포 실행의 배포 뒤 확인 | 원문: "ㅇ"\n')
    assert collect.deferred_checks(str(run_dir.path), run_dir.tasks()) == [("", "스와이프", "배포 실행의 배포 뒤 확인", "안 닫힘")]


def test_deferred_mark_in_decisions_uses_the_related_task(run_dir):
    run_dir.task("T002", "검증", kind="flow-verify", block="검증", status="완료", flow="q")
    write(run_dir.path / "decisions.md",
          '- 2026-11-01 10:00 | [실물 확인 미룸] 스와이프 → 마무리의 배포 메모 | 원문: "ㅇ" | T002\n'
          '- 2026-11-01 10:01 | [실물 확인 미룸] 대체된 것 → 마무리의 배포 메모 → 대체: 2026-11-01 11:00 | 원문: "ㅇ" | T002\n')
    assert collect.deferred_checks(str(run_dir.path), run_dir.tasks()) == [("T002", "스와이프", "마무리의 배포 메모", "안 닫힘")]


def test_deferred_mark_old_form_takes_the_end_cell_not_the_quote(run_dir):   # `|`가 든 항목, 원문의 T 번호
    run_dir.task("T007", "배포", kind="deploy-exec", block="배포", status="완료", deploy_outcome="유지")
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [실물 확인 미룸] A | B → 배포 뒤 확인 | 원문: "T001 말대로" | T050\n')
    assert collect.deferred_checks(str(run_dir.path), run_dir.tasks()) == [("T050", "A | B", "배포 뒤 확인", "안 닫힘")]


def test_main_notes_from_three_records(run_dir):
    two_flows(run_dir)
    run_dir.task("T006", "검증 pick", {"승인 기록": '- 2026-11-01 10:00:00 | 승인 | [메인] 위임 | 원문: "나머지 자동 승인"'},
                 kind="flow-verify", block="검증", status="완료", flow="pick")
    write(run_dir.path / "decisions.md", '- 2026-11-01 11:00 | [메인] B 조건을 채택 | 원문: "맡김" | T006\n- 2026-11-01 11:01 | 칸 | 원문: "ㅇ" | T002\n')
    write(run_dir.path / "journal.md", "- 2026-11-01 12:00 | 메모 | T006 | [메인] 공유 자원을 먼저 잡음\n- 2026-11-01 12:01 | 메모 | T006 | 다른 줄\n")
    sections = dict(visual.map_sections(str(run_dir.path)))
    assert sections["메인 기록"] == ['- T006 2026-11-01 10:00:00 | 승인 | [메인] 위임 | 원문: "나머지 자동 승인"',
                                 '- 2026-11-01 11:00 | [메인] B 조건을 채택 | 원문: "맡김" | T006',
                                 "- 2026-11-01 12:00 | 메모 | T006 | [메인] 공유 자원을 먼저 잡음"]
    assert not any("[메인]" in line for line in sections["결정"])


def test_mark_inside_a_quote_is_not_a_mark(run_dir):   # 사람 말에 든 표지 글은 표지가 아니다
    two_flows(run_dir)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | 칸 | 원문: "[메인] [위험 수용 T003] 말고" | T002\n')
    sections = dict(visual.map_sections(str(run_dir.path)))
    assert sections["결정"] == ["- 사람 2026-11-01 10:00 | 칸 (T002)"]
    assert "메인 기록" not in sections and "받아들인 위험" not in sections


def test_risk_accepted_file_from_marks(run_dir, tmp_path):
    write(run_dir.path / "decisions.md",
          '- 2026-11-01 10:00 | [위험 수용 T003] 옛 사이트 탈퇴 결함 | 원문: "그대로 둠" | T003\n'
          '- 2026-11-01 10:01 | 옛 위험 [위험 수용 T004] 뒤집힌 위험 → 대체: 2026-11-01 11:00 | 원문: "둠" | T004\n'
          '- 2026-11-01 10:02 | [위험 수용 T003] 옛 사이트 탈퇴 결함 | 원문: "다시 그대로" | T003\n'
          '- 2026-11-01 10:03 | 위험 수용을 다음에 정한다 | 원문: "ㅇ" | T005\n')
    out = tmp_path / "out"
    proc = run_script("collect", run_dir, out)
    assert proc.returncode == 0, proc.output
    assert "받아들인 위험 1개 -> {}".format(out / "risk-accepted.md") in proc.stdout
    assert (out / "risk-accepted.md").read_text(encoding="utf-8").splitlines()[-1] == "- T003 옛 사이트 탈퇴 결함 (2026-11-01 10:00)"
    assert "뒤집힌 위험" not in (out / "risk-accepted.md").read_text(encoding="utf-8")


def test_risk_accepted_file_without_marks(run_dir, tmp_path):
    out = tmp_path / "out"
    assert run_script("collect", run_dir, out).returncode == 0
    assert (out / "risk-accepted.md").read_text(encoding="utf-8").splitlines()[-1] == "- 표지 없음(백로그의 위험 수용은 따로 본다)"


def test_risk_from_approval_record(run_dir):   # 최종 CI 실패를 받아들이는 기존 길
    run_dir.task("T006", "마무리", {"승인 기록": '- 2026-11-01 10:00:00 | 승인 | 위험 수용 | 원문: "CI 실패 그대로 넣어"\n'
                                              '- 2026-11-01 10:01:00 | 승인 | 위험 수용 안 함 | 원문: "고쳐"\n'
                                              '- 2026-11-01 10:02:00 | 승인 | 위험 수용 | [위험 수용 T006] 최종 CI 실패 | 원문: "둠"\n'
                                              '- 2026-11-01 10:03:00 | 되물음 | 위험 수용 | 원문: "뭐가 위험?"'},
                 kind="wrap-up", block="마무리", status="완료")
    assert collect.risk_accepted(str(run_dir.path)) == [
        ("T006", "위험 수용: CI 실패 그대로 넣어", "2026-11-01 10:00:00"),
        ("T006", "최종 CI 실패", "2026-11-01 10:02:00")]
    assert "- T006 최종 CI 실패" in run_map(run_dir)


def test_risk_item_keeps_the_part_after_a_pipe(run_dir):   # 옛 꼴의 결정 칸
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | [위험 수용 T003] 탈퇴 결함 | 옛 사이트 전체에서 재현 | 원문: "둠" | T003\n')
    assert collect.risk_accepted(str(run_dir.path)) == [("T003", "탈퇴 결함 | 옛 사이트 전체에서 재현", "2026-11-01 10:00")]


def test_supersede_words_in_the_quote_do_not_drop_a_risk(run_dir):
    write(run_dir.path / "decisions.md",
          '- 2026-11-01 10:00 | [위험 수용 T003] 탈퇴 결함 | 원문: "옛 줄 → 대체: 말고 둠" | T003\n'
          '- 2026-11-01 10:01 | [위험 수용 T004] 뒤에 대체 | 원문: "둠" → 대체: 2026-11-01 11:00 | T004\n')
    live, superseded = collect.live_decisions(str(run_dir.path))
    assert superseded == 1 and len(live) == 1
    assert [r[0] for r in collect.risk_accepted(str(run_dir.path))] == ["T003"]


def test_indented_and_loose_lines_are_seen_and_counted(run_dir):
    two_flows(run_dir)
    write(run_dir.path / "decisions.md", "# 결정\n\n  - [위험 수용 T005] 들여쓴 위험\n자유 문장\n")
    sections = dict(visual.map_sections(str(run_dir.path)))
    assert sections["받아들인 위험"] == ["- T005 들여쓴 위험"]
    assert sections["결정"] == ["- 읽지 못한 결정 줄 1개(decisions.md를 직접 본다)"]


def test_flow_place_line(run_dir):
    two_flows(run_dir)
    assert run_map(run_dir, "--flow", "query") == ["실행 지도: 요구사항 묶음 query(상세 T001) / 흐름 2개 가운데 하나"]
    assert run_map(run_dir, "--flow", "pick") == ["실행 지도: 흐름 2개 가운데 하나"]
    assert not (run_dir.path / "run-map.md").exists()   # 자리 한 줄은 파일을 쓰지 않는다


def test_flow_place_line_one_flow_and_design_depending_on_detail(run_dir):
    write(run_dir.path / "spec" / "a.md", "| AC-1 | 가 |\n")
    write(run_dir.path / "spec" / "b.md", "| AC-2 | 나 |\n")
    run_dir.task("T001", "상세 a", {"건드릴 파일": "spec/a.md"}, kind="req-detail", block="요구사항", status="완료")
    run_dir.task("T002", "상세 b", {"건드릴 파일": "spec/b.md"}, kind="req-detail", block="요구사항", status="완료")
    run_dir.task("T003", "설계", kind="design", block="설계", status="완료", parent="T001", depends_on=["T002"], flow="q")
    assert run_map(run_dir, "--flow", "q") == ["실행 지도: 요구사항 묶음 a(상세 T001), b(상세 T002) / 흐름 하나"]


def test_flow_place_line_unknown_flow(run_dir):
    two_flows(run_dir)
    proc = run_script("visual", run_dir, "--run", "--flow", "없는흐름")
    assert proc.returncode == 2 and "흐름 없음: 없는흐름" in proc.stdout


def test_requirement_lines_for_one_block(run_dir):   # 요구사항 종합이 블록 구간만 쓴다
    write(run_dir.path / "spec" / "a.md", "| AC-1 | 가 |\n| AC-2 | 나 |\n")
    write(run_dir.path / "spec" / "b.md", "| AC-3 | 다 |\n")
    run_dir.task("T002", "상세 a", {"건드릴 파일": "spec/a.md"}, kind="req-detail", block="요구사항", status="완료", parent="T001")
    run_dir.task("T003", "상세 b", {"건드릴 파일": "spec/b.md"}, kind="req-detail", block="요구사항", status="승인대기", parent="T009")
    assert visual.requirement_lines(str(run_dir.path), run_dir.tasks(), parent="T001") == ["- 묶음 a (상세 T002, 완료): 인수 기준 2개"]
    assert len(visual.requirement_lines(str(run_dir.path), run_dir.tasks())) == 2


def test_sections_leave_queue_to_the_caller(run_dir):   # 마무리 리뷰는 대기열을 뺀다
    two_flows(run_dir)
    run_dir.task("T006", "검증 pick", kind="flow-verify", block="검증", status="승인대기", flow="pick")
    titles = [title for title, _ in visual.map_sections(str(run_dir.path))]
    assert titles == ["요구사항", "흐름", "증거", "승인 대기열"]


def test_secret_values_are_masked(run_dir):
    two_flows(run_dir)
    write(run_dir.path / "decisions.md", '- 2026-11-01 10:00 | token=abcdef123456 넣음 | 원문: "ㅇ" | T002\n')
    lines = run_map(run_dir)
    assert "abcdef123456" not in "\n".join(lines)
    assert "abcdef123456" not in (run_dir.path / "run-map.md").read_text(encoding="utf-8")


def test_value_on_the_clip_boundary_is_masked_first():
    for value in ("user.name@example.com", "010-1234-5678", "ghp_abcdefghijklmnop"):
        text = "가" * (visual.CLIP - 8) + " " + value   # 값의 앞 일곱 글자가 경계 안에 든다
        assert value[:5] not in visual._clip(text)


def test_more_secret_shapes_are_masked():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZSJ9.abcDEF123_-"
    for line in ("service_role_key " + jwt, "값 " + jwt, "api key: abcd1234efgh", "service_role: abcd1234efgh", "API-KEY=abcd1234efgh"):
        masked = visual.mask_line(line)
        assert visual.MASK in masked and "abcd1234efgh" not in masked and "eyJhbGci" not in masked, line
    assert visual.mask_line("api key: string") == "api key: string"   # 문서의 타입 이름은 값이 아니다


def test_long_decision_is_clipped_but_risk_item_is_not(run_dir):
    two_flows(run_dir)
    long_text = "가" * 300
    write(run_dir.path / "decisions.md",
          '- 2026-11-01 10:00 | {} | 원문: "ㅇ" | T002\n- 2026-11-01 10:01 | [위험 수용 T003] {} | 원문: "ㅇ" | T003\n'.format(long_text, long_text))
    lines = run_map(run_dir)
    assert not any(long_text in line for line in lines[:lines.index("## 받아들인 위험")])
    assert "- T003 " + long_text in lines


def test_only_the_map_file_is_written(run_dir):
    two_flows(run_dir)

    def snapshot():
        return {os.path.join(folder, n): os.path.getmtime(os.path.join(folder, n))
                for folder, _, names in os.walk(run_dir.path) for n in names}

    before = snapshot()
    run_map(run_dir)
    after = snapshot()
    assert set(after) - set(before) == {str(run_dir.path / "run-map.md")}
    assert all(after[p] == before[p] for p in before)


def test_map_file_is_rewritten_from_the_records(run_dir):
    two_flows(run_dir)
    run_map(run_dir)
    run_dir.task("T005", "구현 pick", kind="implementation", block="구현", status="완료", flow="pick")
    run_map(run_dir)
    assert "- pick (진행): T005 완료" in (run_dir.path / "run-map.md").read_text(encoding="utf-8")


def test_not_a_run_folder(tmp_path):
    proc = run_script("visual", tmp_path / "없음", "--run")
    assert proc.returncode == 2 and "실행 폴더 없음" in proc.stdout


def test_existing_screen_block_is_unchanged(run_dir):   # 옛 사용 그대로
    run_dir.task("T001", "설계")
    proc = run_script("visual", run_dir, "T001")
    assert proc.returncode == 0 and proc.stdout.splitlines()[0] == "■ 보는 자료"
