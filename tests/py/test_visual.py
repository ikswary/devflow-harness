"""승인 화면의 「보는 자료」(B-5, 설계 B 3.6): `visual.py` 명령행(원천 다섯 종류·없음·상한·task 없음)과 `trace_rows` 단위.

명령행 사례는 표준 출력의 줄 전체를 단언한다. 원천 경로는 머리 파일 「정본의 절」·「건드릴 파일」에 적는다.
"""
import os

import visual
from conftest import run_script, write

DESIGN = ("# 설계\n\n## 1. 개요\n| 개요 | 값 |\n|---|---|\n\n## 2. 결정 기록\n\n| 번호 | 결정 |\n|---|---|\n"
          "| D-1 | 가 |\n| D-2 | 나 |\n\n## 3. 구성\n| 구성 | 값 |\n")
DECISION_ROWS = ["| 번호 | 결정 |", "|---|---|", "| D-1 | 가 |", "| D-2 | 나 |"]


def lines_of(proc):
    assert proc.returncode == 0, proc.output
    return proc.stdout.splitlines()


def visual_of(run_dir, tid):
    return lines_of(run_script("visual", run_dir, tid))


def test_design_decision_table(run_dir):   # (가)
    write(run_dir.path / "design" / "x.md", DESIGN)
    run_dir.task("T001", "설계 승인", {"정본의 절": "design\\x.md 2절"})
    assert visual_of(run_dir, "T001") == ["■ 보는 자료", "- design\\x.md 「2. 결정 기록」"] + DECISION_ROWS


def test_brief_journey_and_screen_flow_tables(run_dir):   # (나)
    write(run_dir.path / "spec" / "brief.md",
          "# 기획\n## 범위\n| 범위 | 값 |\n## 여정\n| 단계 | 할 일 |\n|---|---|\n| 1 | 가입 |\n"
          "### 화면 흐름\n| 화면 | 다음 |\n|---|---|\n| 가입 | 홈 |\n")
    run_dir.task("T001", "기획", {"정본의 절": "`spec/brief.md` 여정"})
    assert visual_of(run_dir, "T001") == [
        "■ 보는 자료",
        "- spec\\brief.md 「여정」", "| 단계 | 할 일 |", "|---|---|", "| 1 | 가입 |",
        "- spec\\brief.md 「화면 흐름」", "| 화면 | 다음 |", "|---|---|", "| 가입 | 홈 |"]


def test_spec_trace_rows_from_fr_lines(run_dir):   # (다)
    write(run_dir.path / "spec" / "a.md",
          "## 기능\n- FR-01 가입한다 (P-1)\n- FR-02 탈퇴한다 P-2, P-3\n\n## 인수 기준\n"
          "| 번호 | 문장 |\n|---|---|\n- AC-01 (FR-01) 가입 화면\n- AC-02 (FR-01) 가입 메일\n- AC-03 (FR-02) 탈퇴\n")
    run_dir.task("T001", "요구사항", {"정본의 절": "spec\\a.md"})
    assert visual_of(run_dir, "T001") == [
        "■ 보는 자료", "- spec\\a.md 「추적표」", "| 정책 | FR | AC |", "|---|---|---|",
        "| P-1 | FR-01 | AC-01, AC-02 |", "| P-2, P-3 | FR-02 | AC-03 |"]


def test_spec_without_fr_lines_uses_acceptance_table(run_dir):   # (다) FR 줄이 없을 때
    write(run_dir.path / "spec" / "b.md",
          "## 요구\n| 요구 | 값 |\n## 인수 기준\n| AC | 문장 |\n|---|---|\n| AC-01 | 가입 |\n")
    run_dir.task("T001", "요구사항", {"정본의 절": "spec\\b.md"})
    assert visual_of(run_dir, "T001") == [
        "■ 보는 자료", "- spec\\b.md 「인수 기준」", "| AC | 문장 |", "|---|---|", "| AC-01 | 가입 |"]


def test_wireframe_path_line(run_dir):   # (라)
    page = write(run_dir.path / "ui" / "wireframes" / "a.html", "<html></html>\n")
    write(run_dir.path / "ui" / "a.md", "## 결정\n| 화면 | 값 |\n")   # ui\…md는 원천이 아니다
    run_dir.task("T001", "화면 구현", {"건드릴 파일": "- src/a.tsx\n- ui/a.md\n- ui/wireframes/a.html"})
    out = visual_of(run_dir, "T001")
    assert len(out) == 2 and out[0] == "■ 보는 자료"
    assert out[1].startswith("- 와이어프레임: file:///")
    assert out[1].endswith(os.path.abspath(page).replace("\\", "/"))


def test_verify_family_uses_acceptance_tables_of_its_body(run_dir):   # (마)
    write(run_dir.path / "design" / "x.md", DESIGN)   # 검증 무리는 「정본의 절」을 보지 않는다
    run_dir.task("T001", "흐름별 검증", {"정본의 절": "design\\x.md"}, kind="flow-verify", block="검증")
    run_dir.result("T001", "# T001 결과\n\n## 승인 화면\n| 인수 기준 | 칸 |\n\n## 본문\n"
                   "| 지적 | 관점 |\n|---|---|\n| V-01 | 시험 |\n\n"
                   "| 인수 기준 | 판정 |\n|---|---|\n| AC-01 | 통과 |\n\n## 실행 기록\n| 인수 기준 | 밖 |\n")
    assert visual_of(run_dir, "T001") == [
        "■ 보는 자료", "- tasks\\T001\\result.md 「본문」", "| 인수 기준 | 판정 |", "|---|---|", "| AC-01 | 통과 |"]


def test_no_source_path_gives_one_none_line(run_dir):   # (바)
    run_dir.task("T001", "원천 없음", {"정본의 절": "(없음)", "건드릴 파일": "- scripts/a.py\n- design/missing.md"})
    out = visual_of(run_dir, "T001")
    assert out[0] == "■ 보는 자료"
    assert out[1:] == ["- 없음 (정본의 절·건드릴 파일에 원천 경로 없음)"]


def test_source_without_matching_table(run_dir):   # (바) 원천은 있으나 고를 표가 없음
    write(run_dir.path / "design" / "y.md", "## 1. 개요\n| 개요 | 값 |\n")
    run_dir.task("T001", "설계", {"정본의 절": "design\\y.md"})
    assert visual_of(run_dir, "T001") == ["■ 보는 자료", "- 없음 (design\\y.md에 고를 표 없음)"]


def set_limit(run_dir, n):
    p = run_dir.path / "run.md"
    p.write_text(p.read_text(encoding="utf-8") + "| 보는 자료 줄 수 | {} |\n".format(n), encoding="utf-8", newline="\n")


def test_over_limit_writes_visual_md(run_dir):   # (사)
    write(run_dir.path / "design" / "x.md", DESIGN)
    run_dir.task("T001", "설계 승인", {"정본의 절": "design\\x.md"})
    set_limit(run_dir, 3)
    full = os.path.abspath(run_dir.task_dir("T001") / "visual.md")
    whole = ["■ 보는 자료", "- design\\x.md 「2. 결정 기록」"] + DECISION_ROWS
    assert visual_of(run_dir, "T001") == whole[:4] + ["- 전체 5줄: " + full]
    assert open(full, encoding="utf-8").read().splitlines() == whole


def test_at_limit_prints_everything(run_dir):   # (사) 경계: 첫 줄 뒤 줄 수가 상한과 같으면 자르지 않는다
    write(run_dir.path / "design" / "x.md", DESIGN)
    run_dir.task("T001", "설계 승인", {"정본의 절": "design\\x.md"})
    set_limit(run_dir, 5)
    assert visual_of(run_dir, "T001") == ["■ 보는 자료", "- design\\x.md 「2. 결정 기록」"] + DECISION_ROWS
    assert not (run_dir.task_dir("T001") / "visual.md").exists()


def test_missing_task_exits_2(run_dir):   # (아)
    run_dir.task("T001", "있는 task")
    proc = run_script("visual", run_dir, "T099")
    assert proc.returncode == 2, proc.output
    assert "task 없음: T099" in proc.output
    assert run_script("visual", run_dir).returncode == 2


def test_trace_rows_matches_whole_ids():
    text = ("| FR-1 | 가 | P-1 |\n# FR-10 나\n- AC-01 (FR-1) 가\n- AC-02 (FR-10) 나\n"
            "- AC-03 FR-1, FR-10 둘 다\n- 참고 AC-04 (FR-1)\n- AC-05 (SFR-1) 다른 id\n")
    assert visual.trace_rows(text) == ["| 정책 | FR | AC |", "|---|---|---|",
                                       "| P-1 | FR-1 | AC-01, AC-03 |", "|  | FR-10 | AC-02, AC-03 |"]
    assert visual.trace_rows("- AC-01 (FR-1)\n") == []
