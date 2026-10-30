"""측정 집계(B-9, 설계 B 3.8): `collect.py {실행 폴더} --measure` 명령행과 `zero_decision_approvals`·`perspective_counts` 단위.

명령행 사례는 표준 출력의 줄 전체를 단언한다. 결정 0 승인은 `완료`·`approval_mode: 승인`·`n_decide` 0·`n_todo` 0인
task이고, 관점 지적은 검증 무리 task `result.md` 「본문」과 설계 블록 task 판정 파일 「통과 못 한 기준」의 `관점:` 줄이다(D-9).
"""
import collect
from conftest import run_script, write

DONE = {"status": "완료", "approval_mode": "승인", "n_decide": "0", "n_todo": "0"}
LONG = "가나다라마 바사아자차카"   # 괄호·공백을 뺀 11글자: 한 마디 답이 아님
NO_FINDING = "- 관점 지적: 보안 0(설계 판정 0) · 운영 제약 0(설계 판정 0) · 데이터 정합 0(설계 판정 0) · 정확성 0 · 시험 0 · 관례 0 · 그 밖 0"


def approved(stamp, text):
    return '- {} | 승인 | 승인 | 원문: "{}"'.format(stamp, text)


def measure_of(run_dir):
    proc = run_script("collect", run_dir, "--measure")
    assert proc.returncode == 0, proc.output
    return proc.stdout.splitlines()


def approvals_setup(run_dir):
    run_dir.task("T001", "한 마디 답", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **DONE)
    # 앞 줄은 한 마디 답이지만 가장 늦은 승인 줄이 긴 원문이라 한 마디로 세지 않는다
    run_dir.task("T002", "긴 답", {"승인 기록": approved("2026-10-30 09:00:00", "승인") + "\n"
                                  + approved("2026-10-30 10:00:00", LONG)}, **DONE)
    run_dir.task("T003", "결정 하나", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, n_decide="1"))
    run_dir.task("T004", "알림", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, approval_mode="알림"))


def test_zero_decision_approvals_counts_kind_and_short_answers(run_dir):   # (가) 명령행
    approvals_setup(run_dir)
    assert measure_of(run_dir) == ["- 결정 0 승인: design 2(한 마디 1)", NO_FINDING]


def test_zero_decision_approvals_unit_in_kind_order(run_dir):   # (가) 단위: kinds.KINDS 차례, n_todo가 0이 아니면 뺌
    approvals_setup(run_dir)
    run_dir.task("T005", "질문", {"승인 기록": approved("2026-10-30 09:00:00", "네 (Recommended)")}, kind="question",
                 block="질문", **DONE)
    run_dir.task("T006", "할 일 하나", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, n_todo="1"))
    got = collect.zero_decision_approvals(run_dir.tasks())
    assert got == {"question": (1, 1), "design": (2, 1)}
    assert list(got) == ["question", "design"]


def verify_setup(run_dir, extra=""):
    run_dir.task("T010", "흐름별 검증", kind="flow-verify", block="검증")
    run_dir.result("T010", "# T010 결과\n\n## 승인 화면\n### 알릴 것\n- V-01 관점: 보안\n\n## 본문\n"
                   "### V-01\n- 관점: 보안\n### V-02\n- 관점: 보안\n### V-03\n- 관점: 시험\n" + extra + "\n## 규약 추가\n없음\n")
    run_dir.task("T011", "설계")
    for name in ("judge.md", "judge.r1.md"):
        write(run_dir.task_dir("T011") / name, "판정자: rjudge-T011 2026-10-30 09:00:00\n\n## 통과 못 한 기준\n"
              "- 기준 8: 실패 — 권한 확인이 빠짐. 관점: 보안\n\n## 판정 표\n| 8 | 실패 | 관점: 보안 |\n")


def test_perspective_counts_body_and_design_judges(run_dir):   # (나) 명령행
    verify_setup(run_dir)
    assert measure_of(run_dir) == [
        "- 결정 0 승인: 없음",
        "- 관점 지적: 보안 2(설계 판정 2) · 운영 제약 0(설계 판정 0) · 데이터 정합 0(설계 판정 0) · 정확성 0 · 시험 1"
        " · 관례 0 · 그 밖 0"]


def test_perspective_outside_seven_values_is_other(run_dir):   # (다)
    verify_setup(run_dir, extra="### V-04\n- 관점: 성능\n")
    got = collect.perspective_counts(run_dir.tasks())
    assert got["그 밖"] == (1, 0)
    assert got["보안"] == (2, 2) and got["시험"] == (1, 0)   # 양성 대조: 7값은 제 이름으로 센다


def test_no_matching_task_prints_none(run_dir):   # (라)
    run_dir.task("T001", "결정 있음", {"승인 기록": approved("2026-10-30 09:00:00", "승인")}, **dict(DONE, n_decide="2"))
    assert measure_of(run_dir) == ["- 결정 0 승인: 없음", NO_FINDING]
