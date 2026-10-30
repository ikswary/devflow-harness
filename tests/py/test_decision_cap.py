"""한 승인의 결정 수 상한(B-6, 설계 B 3.7): `screen.py` 명령행의 `! 결정 수 상한` 줄(넘음·같음·값 없음).

「이번 실행의 값」의 상한은 `run.md` 표 행으로 준다. 상한 줄은 화면에 더해지기만 하고 `counts:` 줄은 바뀌지 않는다.
"""
from datetime import datetime

from conftest import RunDir, run_script


def judge_ok():
    """판정 시각을 부를 때 만든다. started_version이 있는 task는 기록 점검(R3)이 돌아서 판정 시각이 결과 파일 mtime과 어긋나면 항목이 덧붙는다."""
    return ("판정자: rjudge-T001 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n"
            "| 기준 | 판정 | 근거 |\n|---|---|---|\n| 1 | 통과 | 읽음 |\n")


DECIDE_3 = "- 저장 방식을 정한다\n- 캐시 수명을 정한다\n- 오류 문구를 정한다"

CAP_LINE = "! 결정 수 상한"


def result(decide):
    return ("# T001 결과\n\n## 승인 화면\n### 정해 주실 것\n{}\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n- 없음\n"
            "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 설계대로 한 작업 1\n\n"
            "## 스스로 줄임\n없음\n\n## 본문\n본문\n").format(decide)


def set_cap(run_dir, n):
    p = run_dir.path / "run.md"
    p.write_text(p.read_text(encoding="utf-8") + "| 한 승인의 결정 수 상한 | {} |\n".format(n), encoding="utf-8", newline="\n")


def screen_of(run_dir, cap=None, version="1.1.0"):
    """「정해 주실 것」 항목 셋인 task의 `screen.py` 출력 줄. cap이 None이면 run.md에 상한 행을 두지 않는다."""
    run_dir.task("T001", "설계", status="승인대기", started_version=version)
    run_dir.result("T001", result(DECIDE_3))
    run_dir.judge("T001", judge_ok())
    if cap is not None:
        set_cap(run_dir, cap)
    proc = run_script("screen", run_dir, "T001")
    assert proc.returncode == 0, proc.output
    return proc.stdout.splitlines()


def cap_lines(lines):
    return [l for l in lines if l.startswith(CAP_LINE)]


def counts_line(lines):
    found = [l for l in lines if l.startswith("counts:")]
    assert len(found) == 1, lines
    return found[0]


def test_over_cap_shows_line_before_counts(run_dir):   # (가) 상한 2, 항목 셋
    lines = screen_of(run_dir, cap=2)

    found = cap_lines(lines)
    assert len(found) == 1 and found[0].startswith("! 결정 수 상한: 정해 주실 것 3 > 2("), lines
    assert lines.index(found[0]) < lines.index(counts_line(lines))


def test_cap_equal_to_count_shows_no_line(run_dir):   # (나) 상한 3, 항목 셋(경계)
    lines = screen_of(run_dir, cap=3)

    assert cap_lines(lines) == []
    assert counts_line(lines).startswith("counts: n_decide=3 ")   # 셋이 정해 주실 것으로 세어졌다(양성 대조)


def test_no_cap_row_shows_no_line(run_dir):   # (다) 그 행 없음 → 시작값 0(없음)
    lines = screen_of(run_dir)

    assert cap_lines(lines) == []
    assert counts_line(lines).startswith("counts: n_decide=3 ")


def test_old_version_task_shows_no_line(run_dir):   # 1.0.4로 시작한 task는 상한 1, 항목 셋이어도 줄이 없다
    lines = screen_of(run_dir, cap=1, version="1.0.4")

    assert cap_lines(lines) == []
    assert counts_line(lines).startswith("counts: n_decide=3 ")


def test_v110_task_shows_line_with_same_condition(run_dir):   # 양성 대조: 같은 조건에서 1.1.0이면 줄이 있다
    lines = screen_of(run_dir, cap=1, version="1.1.0")

    found = cap_lines(lines)
    assert len(found) == 1 and found[0].startswith("! 결정 수 상한: 정해 주실 것 3 > 1("), lines


def test_cap_line_does_not_change_counts(workspace):   # (가)와 (다)의 counts: 줄이 같다
    over = screen_of(RunDir(workspace / "over"), cap=2)
    none = screen_of(RunDir(workspace / "none"))

    assert len(cap_lines(over)) == 1 and cap_lines(none) == []
    assert counts_line(over) == counts_line(none)


def test_script_added_item_is_not_counted_against_cap(run_dir):   # 스크립트가 덧붙인 [판정 기준 정정] 항목은 상한에 세지 않는다(V-01)
    run_dir.task("T001", "설계", status="승인대기",
                 started_version="1.1.0",
                 sections={"판정 기준 정정": "- 2026-10-15 09:30:00 | 정정 1 | 출처: 작성자 T001 | 원문: criteria.orig.md | 고친 문장: criteria.amend1.md"})
    run_dir.result("T001", result("- 저장 방식을 정한다\n- 캐시 수명을 정한다"))
    run_dir.judge("T001", judge_ok())
    set_cap(run_dir, 2)
    proc = run_script("screen", run_dir, "T001")
    assert proc.returncode == 0, proc.output
    lines = proc.stdout.splitlines()

    assert cap_lines(lines) == []
    assert counts_line(lines).startswith("counts: n_decide=3 ")   # 덧붙은 항목까지 셋으로 세어졌다(양성 대조)
