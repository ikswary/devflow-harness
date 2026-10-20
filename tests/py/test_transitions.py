"""특성 시험 ②: 상태 전이 검사의 허용·거부와 거부 이유 문구.

- `design/structure.md` 2.2 전이표 18행과 2.3 stage 좁힘 6행. 사례 이름의 `r22_{n}`·`r23_{n}`이 표의 행 번호다.
- 표 행은 함수 단위(`task_set.check_transition`·`task_set.stage_rule`)로 부른다. `--unlisted` 행(2.2 17행),
  `키=값` 행(2.2 18행), 없앤 값 `멈춤`(어느 상태 집합에도 없음)은 `main`의 옵션 처리에서 일어나므로
  명령행(`task_set.py`)으로 돌린다.
- 판본 비교(`대기`→`진행`)는 `run.md`의 `harness_version`을 비우거나 어떤 판본과도 다른 값을 넣고, "같음"은 함수 단위에서
  라이브러리의 `harness_version`을 바꿔 끼운다.
- 명령행 사례는 거부 이유 줄만 단언하고 출력 전체를 대조하지 않는다. 이름 바꾸기 task가 바꾸는 거부 문구(배포 실행의
  stage 끝 조건)는 바뀌는 경로 밖 부분만 단언한다.
"""
import pytest

import exec as execmod
import task_set
from conftest import run_script, write

REC_OK = ("승인", "승인", "승인")
REC_NOTIFY = ("알림", "알림으로 지나감", "")
NEW = {"started_version": "시험 판본", "rules": "2"}      # 새 task, 규칙 판 2(stage 좁힘이 걸림)
READ_JUDGE = "판정자: rjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
RUN_JUDGE = "판정자: xjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
NOT_TABLE = "전이표에 없는 전이"
DEPLOY_NOT_END = "배포 실행은 stage: 끝이 된 뒤에 완료"   # 뒤의 정의 경로 괄호는 이름 바꾸기가 고친다
APPROVED = "- 2026-10-15 10:00:00 | 승인 | 승인 | 원문: \"승인\""
ODD_VERSION = "판본-시험-zz00000 agents 1999-01-01 00:00"   # 어떤 판본과도 같을 수 없는 값


def ctx(record=None, reason=None, archived=False, snapshot=False, old_stage=""):
    return {"record": record, "reason": reason, "archived": archived, "snapshot": snapshot, "old_stage": old_stage}


def load(run_dir, tid="T001"):
    return run_dir.tasks()[tid]


def make(run_dir, tid="T001", title="전이 시험", judge=None, run_judge=None, **meta):
    run_dir.task(tid, title, **meta)
    if judge:
        run_dir.judge(tid, judge)
    if run_judge:
        write(run_dir.task_dir(tid) / "judge-run.md", run_judge)
    return load(run_dir, tid)


def check(run_dir, t, old, new, **kw):
    return task_set.check_transition(str(run_dir), t, old, new, ctx(**kw))


def rule(run_dir, t, old, new, **kw):
    return task_set.stage_rule(str(run_dir), t, old, new, ctx(**kw))


def set_run_version(run_dir, value):
    p = run_dir.path / "run.md"
    text = p.read_text(encoding="utf-8")
    assert "harness_version:\n" in text
    write(p, text.replace("harness_version:\n", "harness_version: {}\n".format(value)))


def freeze_ok(run_dir, tid, point="실행승인", ran=True):
    """얼린 명령 한 줄(`echo ok`)과, ran이면 그 줄이 종료 코드 0으로 돈 exec.md 기록. `exec.verify`가 통과하는 꼴."""
    d = run_dir.task_dir(tid)
    lines = ["echo ok"]
    write(d / "approved-cmds-{}.md".format(point),
          "# 얼린 명령\n\n1. echo ok\n\n해시: {}\n얼린 시각: 2026-10-15 10:00:00\n".format(execmod.digest(lines)))
    if ran:
        write(d / "exec.md", "- 2026-10-15 10:01:00 | echo ok | 종료 코드 0 | 지점 {}:1\n".format(point))


def front_value(run_dir, key, tid="T001"):
    text = (run_dir.task_dir(tid) / "task.md").read_text(encoding="utf-8")
    head = text.split("---")[1]
    for line in head.splitlines():
        if line.split(":", 1)[0].strip() == key:
            return line.split(":", 1)[1].strip()
    return None


# ================================================================ 2.2 전이표 (함수 단위)

# 1 같은 상태(old == new): 늘 허용. stage 좁힘보다 먼저라 STAGE kind의 맞지 않는 stage도 걸리지 않는다
def test_r22_01_same_status_always_allowed(run_dir):
    t = make(run_dir, kind="merge", status="승인대기", stage="실행", **NEW)
    assert check(run_dir, t, "승인대기", "승인대기") is None
    t2 = make(run_dir, "T002", status="완료")
    assert check(run_dir, t2, "완료", "완료") is None


# 2 STAGE kind이고 rules ≥ 2이고 새 상태가 보류가 아님: 먼저 stage_rule. rules가 1이면 걸리지 않는다
def test_r22_02_stage_kind_rules2_checks_stage_rule_first(run_dir):
    t = make(run_dir, kind="merge", status="진행", stage="실행", **NEW)
    why = check(run_dir, t, "진행", "승인대기")
    assert why is not None and why.startswith("merge의 승인대기는 묻는 단계와 함께")
    t1 = make(run_dir, "T002", kind="merge", status="진행", stage="실행", started_version="시험 판본", rules="1")
    assert check(run_dir, t1, "진행", "승인대기") is None


# 3 모든 상태 → 보류: R 또는 r
@pytest.mark.parametrize("old", ["대기", "진행", "자체검증", "승인대기", "완료", "백로그"])
def test_r22_03_any_to_hold_needs_record_or_reason(run_dir, old):
    t = make(run_dir, status=old)
    assert check(run_dir, t, old, "보류") == "보류는 --record(사용자 답) 또는 --reason(메인 판단)과 함께"
    assert check(run_dir, t, old, "보류", record=REC_OK) is None
    assert check(run_dir, t, old, "보류", reason="흡수") is None


# 4 대기 → 진행: run.md 판본이 비었거나 지금 판본과 같음. 다르면 거부
def test_r22_04_wait_to_run_allowed_when_run_version_empty(run_dir):
    t = make(run_dir)
    assert check(run_dir, t, "대기", "진행") is None


def test_r22_04_wait_to_run_rejected_when_run_version_differs(run_dir):
    set_run_version(run_dir, ODD_VERSION)
    t = make(run_dir)
    why = check(run_dir, t, "대기", "진행")
    assert why is not None
    assert why.startswith("run.md 하네스 판본({})이 지금 판본(".format(ODD_VERSION))
    assert "과 다름" in why


def test_r22_04_wait_to_run_allowed_when_run_version_same(run_dir, lib, monkeypatch):
    # "같음"은 함수 단위에서 지금 판본을 바꿔 끼운다
    monkeypatch.setattr(lib, "harness_version", lambda harness_dir=None: "시험판 agents 2026-10-15 10:00")
    set_run_version(run_dir, "시험판 agents 2026-10-15 10:00")
    t = make(run_dir)
    assert check(run_dir, t, "대기", "진행") is None


# 5 진행 → 자체검증: 조건 없음
def test_r22_05_run_to_selfcheck_unconditional(run_dir):
    t = make(run_dir, status="진행")
    assert check(run_dir, t, "진행", "자체검증") is None


# 6 자체검증 → 진행: --archive-judge와 함께
def test_r22_06_selfcheck_to_run_needs_archive_judge(run_dir):
    t = make(run_dir, status="자체검증")
    assert check(run_dir, t, "자체검증", "진행") == "자체검증→진행(재시도)은 --archive-judge와 함께"
    assert check(run_dir, t, "자체검증", "진행", archived=True) is None


# 7 자체검증 → 승인대기: 필요한 판정이 있음
def test_r22_07_selfcheck_to_waiting_approval_needs_judges(run_dir):
    t = make(run_dir, status="자체검증", **NEW)
    why = check(run_dir, t, "자체검증", "승인대기")
    assert why == "필요한 판정이 없음: judge.md 없음"
    t2 = make(run_dir, "T002", status="자체검증", judge=READ_JUDGE, **NEW)
    assert check(run_dir, t2, "자체검증", "승인대기") is None


def test_r22_07_selfcheck_to_waiting_approval_rejects_wrong_judge_role(run_dir):
    t = make(run_dir, status="자체검증", judge=RUN_JUDGE, **NEW)
    why = check(run_dir, t, "자체검증", "승인대기")
    assert why == "필요한 판정이 없음: judge.md 첫 줄 판정자가 rjudge-…가 아님(xjudge-T001)"


# 8 자체검증 → 완료: R(알림·승인) / 알림 가능 kind·STAGE·승인 줄 / 필요한 판정 / deploy-exec면 stage 끝 / 새 알림 task는 screen 조건
def test_r22_08_selfcheck_to_done_needs_notify_or_approve_record(run_dir):
    t = make(run_dir, kind="implementation", block="구현", status="자체검증", judge=READ_JUDGE)
    assert check(run_dir, t, "자체검증", "완료") == "자체검증→완료는 --record \"알림|…\"(또는 승인)와 함께"
    assert check(run_dir, t, "자체검증", "완료", record=("답", "고침", "고쳐")) \
        == "자체검증→완료는 --record \"알림|…\"(또는 승인)와 함께"
    assert check(run_dir, t, "자체검증", "완료", record=REC_NOTIFY) is None


def test_r22_08_selfcheck_to_done_rejects_kind_that_cannot_notify(run_dir):
    t = make(run_dir, status="자체검증", judge=READ_JUDGE)
    assert check(run_dir, t, "자체검증", "완료", record=REC_NOTIFY) == "design는 알림으로 지나가지 않는다(승인대기로)"


def test_r22_08_selfcheck_to_done_allowed_for_design_with_prior_approval_line(run_dir):
    t = make(run_dir, status="자체검증", judge=READ_JUDGE)
    run_dir.task("T001", "전이 시험", sections={"승인 기록": APPROVED}, status="자체검증")
    t = load(run_dir)
    assert check(run_dir, t, "자체검증", "완료", record=REC_NOTIFY) is None


def test_r22_08_selfcheck_to_done_needs_judges(run_dir):
    t = make(run_dir, kind="implementation", block="구현", status="자체검증")
    assert check(run_dir, t, "자체검증", "완료", record=REC_NOTIFY) == "필요한 판정이 없음: 판정 파일(judge.md·judge-run.md)이 없음"


def test_r22_08_selfcheck_to_done_deploy_exec_needs_stage_end(run_dir):
    t = make(run_dir, kind="deploy-exec", block="배포", status="자체검증", stage="기록", judge=READ_JUDGE)
    why = check(run_dir, t, "자체검증", "완료", record=REC_NOTIFY)
    assert why is not None and why.startswith(DEPLOY_NOT_END)
    t2 = make(run_dir, "T002", kind="deploy-exec", block="배포", status="자체검증", stage="끝", judge=READ_JUDGE)
    assert check(run_dir, t2, "자체검증", "완료", record=REC_NOTIFY) is None


def test_r22_08_selfcheck_to_done_new_notify_task_needs_screen_condition(run_dir):
    t = make(run_dir, kind="implementation", block="구현", status="자체검증", run_judge=RUN_JUDGE, **NEW)
    assert check(run_dir, t, "자체검증", "완료", record=REC_NOTIFY) == "알림 불가: result.md가 없음"


# 9 승인대기 → 완료: R + 필요한 판정 + (deploy-exec면 stage 끝)
def test_r22_09_waiting_approval_to_done(run_dir):
    t = make(run_dir, status="승인대기", judge=READ_JUDGE)
    assert check(run_dir, t, "승인대기", "완료") == "승인대기→완료는 --record(사용자 답)와 함께"
    assert check(run_dir, t, "승인대기", "완료", record=REC_OK) is None
    t2 = make(run_dir, "T002", status="승인대기")
    assert check(run_dir, t2, "승인대기", "완료", record=REC_OK) == "필요한 판정이 없음: 판정 파일(judge.md·judge-run.md)이 없음"


def test_r22_09_waiting_approval_to_done_deploy_exec_needs_stage_end(run_dir):
    t = make(run_dir, kind="deploy-exec", block="배포", status="승인대기", stage="결과승인", judge=READ_JUDGE)
    why = check(run_dir, t, "승인대기", "완료", record=REC_OK)
    assert why is not None and why.startswith(DEPLOY_NOT_END)


# 10 승인대기 → 진행: R 또는 --screen-snapshot
def test_r22_10_waiting_approval_to_run(run_dir):
    t = make(run_dir, status="승인대기")
    assert check(run_dir, t, "승인대기", "진행") == "승인대기→진행은 --record(사람 답) 또는 --screen-snapshot과 함께"
    assert check(run_dir, t, "승인대기", "진행", record=REC_OK) is None
    assert check(run_dir, t, "승인대기", "진행", snapshot=True) is None


# 11 진행 → 승인대기: STAGE kind만
@pytest.mark.parametrize("kind", ["merge", "wrap-up", "deploy-exec"])
def test_r22_11_run_to_waiting_approval_stage_kinds_only(run_dir, kind):
    t = make(run_dir, kind=kind, status="진행")
    assert check(run_dir, t, "진행", "승인대기") is None


def test_r22_11_run_to_waiting_approval_rejected_for_other_kinds(run_dir):
    t = make(run_dir, status="진행")
    assert check(run_dir, t, "진행", "승인대기") == "진행→승인대기는 합치기·마무리·배포 실행만(그 밖은 자체검증을 거침)"


# 12 진행 → 완료: STAGE kind만, R, 필요한 판정, (deploy-exec면 stage 끝)
def test_r22_12_run_to_done(run_dir):
    t = make(run_dir, status="진행", judge=READ_JUDGE)
    assert check(run_dir, t, "진행", "완료", record=REC_OK) == "진행→완료는 합치기·마무리·배포 실행만"
    t2 = make(run_dir, "T002", kind="wrap-up", block="마무리", status="진행", judge=READ_JUDGE)
    assert check(run_dir, t2, "진행", "완료") == "진행→완료는 --record와 함께"
    assert check(run_dir, t2, "진행", "완료", record=REC_OK) is None
    t3 = make(run_dir, "T003", kind="wrap-up", block="마무리", status="진행")
    assert check(run_dir, t3, "진행", "완료", record=REC_OK) == "필요한 판정이 없음: 판정 파일(judge.md·judge-run.md)이 없음"


def test_r22_12_run_to_done_deploy_exec_needs_stage_end(run_dir):
    t = make(run_dir, kind="deploy-exec", block="배포", status="진행", stage="넣기", judge=READ_JUDGE)
    why = check(run_dir, t, "진행", "완료", record=REC_OK)
    assert why is not None and why.startswith(DEPLOY_NOT_END)
    t2 = make(run_dir, "T002", kind="deploy-exec", block="배포", status="진행", stage="끝", judge=READ_JUDGE)
    assert check(run_dir, t2, "진행", "완료", record=REC_OK) is None


# 9·12 합치기 충돌: exec.md에 브랜치 판정 `충돌` 줄이 있으면 judge.md를 요구한다.
# 충돌 줄이 없는 합치기는 judge.md 없이 허용 그대로, judge.md(첫 줄 rjudge-)를 두면 충돌이어도 허용
CONFLICT_LINE = "- 2026-10-15 10:00:00 | 브랜치 판정 | 실행승인:1 | 충돌 | 앞 x 뒤 y 넣은 z@w 받은 v\n"
NO_READ_JUDGE = "필요한 판정이 없음: judge.md 없음"


def conflict_merge(run_dir, status, tid="T001", conflict=True, judge=None):
    """stage 끝·rules 2·실행 판정 통과·exec.py --verify 통과인 합치기. conflict면 브랜치 판정 `충돌` 줄을 더하고,
    judge가 없으면 judge.md 없음."""
    make(run_dir, tid, kind="merge", block="검증", status=status, stage="끝", judge=judge, run_judge=RUN_JUDGE, **NEW)
    freeze_ok(run_dir, tid)
    if conflict:
        p = run_dir.task_dir(tid) / "exec.md"
        write(p, p.read_text(encoding="utf-8") + CONFLICT_LINE)
    t = load(run_dir, tid)
    assert execmod.exec_entries(t)[1] == ({"실행승인:1": "충돌"} if conflict else {})   # 충돌 줄이 판정으로 읽힌다
    assert execmod.verify(str(run_dir), t)[0] is True                 # 얼린 명령 검증은 통과
    assert (run_dir.task_dir(tid) / "judge.md").exists() == bool(judge)
    return t


def test_r22_12_merge_conflict_run_to_done_needs_read_judge(run_dir):
    t = conflict_merge(run_dir, "진행")
    assert check(run_dir, t, "진행", "완료", record=REC_OK) == NO_READ_JUDGE
    plain = conflict_merge(run_dir, "진행", tid="T002", conflict=False)
    assert check(run_dir, plain, "진행", "완료", record=REC_OK) is None
    judged = conflict_merge(run_dir, "진행", tid="T003", judge=READ_JUDGE)
    assert check(run_dir, judged, "진행", "완료", record=REC_OK) is None


def test_r22_09_merge_conflict_waiting_approval_to_done_needs_read_judge(run_dir):
    t = conflict_merge(run_dir, "승인대기")
    assert check(run_dir, t, "승인대기", "완료", record=REC_OK, old_stage="결과승인") == NO_READ_JUDGE
    plain = conflict_merge(run_dir, "승인대기", tid="T002", conflict=False)
    assert check(run_dir, plain, "승인대기", "완료", record=REC_OK, old_stage="결과승인") is None
    judged = conflict_merge(run_dir, "승인대기", tid="T003", judge=READ_JUDGE)
    assert check(run_dir, judged, "승인대기", "완료", record=REC_OK, old_stage="결과승인") is None


# 13 보류 → 대기, 보류 → 백로그: R
@pytest.mark.parametrize("new", ["대기", "백로그"])
def test_r22_13_hold_out_needs_record(run_dir, new):
    t = make(run_dir, status="보류")
    assert check(run_dir, t, "보류", new) == "보류에서 나가는 전이는 --record(사용자 답)와 함께"
    assert check(run_dir, t, "보류", new, reason="메인 판단") == "보류에서 나가는 전이는 --record(사용자 답)와 함께"
    assert check(run_dir, t, "보류", new, record=REC_OK) is None


# 14 대기 → 백로그: 제목이 [백로그]·[안으로 시작하거나 R 또는 r
def test_r22_14_wait_to_backlog(run_dir):
    t = make(run_dir)
    assert check(run_dir, t, "대기", "백로그") == "대기→백로그는 [백로그] 행이거나 --record·--reason과 함께"
    assert check(run_dir, t, "대기", "백로그", record=REC_OK) is None
    assert check(run_dir, t, "대기", "백로그", reason="미룸") is None
    t2 = make(run_dir, "T002", title="[백로그] 나중에")
    assert check(run_dir, t2, "대기", "백로그") is None
    t3 = make(run_dir, "T003", title="[안 나] 다른 안")
    assert check(run_dir, t3, "대기", "백로그") is None


# 15 백로그 → 완료: R 또는 r
def test_r22_15_backlog_to_done(run_dir):
    t = make(run_dir, status="백로그")
    assert check(run_dir, t, "백로그", "완료") == "백로그→완료는 --record 또는 --reason \"다른 실행·회고에서 처리: {경로}\""
    assert check(run_dir, t, "백로그", "완료", record=REC_OK) is None
    assert check(run_dir, t, "백로그", "완료", reason="다른 실행·회고에서 처리: 어딘가") is None


# 16 그 밖 전부: 거부("전이표에 없는 전이"). 구조 분석 2.2 「전이표에 없어서 U로만 가능한 전이」 목록 전부
UNLISTED_PAIRS = [
    ("대기", "자체검증"), ("대기", "승인대기"), ("대기", "완료"),
    ("진행", "대기"), ("진행", "백로그"),
    ("자체검증", "대기"), ("자체검증", "백로그"),
    ("승인대기", "대기"), ("승인대기", "자체검증"), ("승인대기", "백로그"),
    ("완료", "대기"), ("완료", "진행"), ("완료", "자체검증"), ("완료", "승인대기"), ("완료", "백로그"),
    ("보류", "진행"), ("보류", "자체검증"), ("보류", "승인대기"), ("보류", "완료"),
    ("백로그", "대기"), ("백로그", "진행"), ("백로그", "자체검증"), ("백로그", "승인대기"),
]


@pytest.mark.parametrize("old,new", UNLISTED_PAIRS)
def test_r22_16_pairs_outside_table_rejected(run_dir, old, new):
    t = make(run_dir, status=old, judge=READ_JUDGE)
    why = check(run_dir, t, old, new, record=REC_OK, reason="이유", archived=True, snapshot=True)
    assert why == "{} {}→{}(--unlisted \"이유\"로만)".format(NOT_TABLE, old, new)


# ================================================================ 17·18행, 없앤 값 멈춤 (명령행)

# 17 --unlisted: 전이표에 없는 짝만 실행하고 「표 밖 전이」 절과 journal.md에 남긴다. U가 없으면 거부.
#    표 안 전이의 조건 미충족은 U가 있어도 종료 3이고 파일은 그대로
def test_r22_17_unlisted_cli_rejected_without_u(run_dir):
    run_dir.task("T001", "전이 시험")
    r = run_script("task_set", run_dir, "T001", "--status", "완료")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} 대기→완료".format(NOT_TABLE) in r.stdout
    assert front_value(run_dir, "status") == "대기"


def test_r22_17_unlisted_cli_runs_pair_outside_table_and_records(run_dir):
    run_dir.task("T001", "전이 시험")
    r = run_script("task_set", run_dir, "T001", "--status", "완료", "--unlisted", "시험 이유")
    assert r.returncode == 0, r.output
    assert "T001: 대기→완료" in r.stdout.splitlines()
    assert front_value(run_dir, "status") == "완료"
    sec = load(run_dir)["_sections"].get("표 밖 전이", "")
    assert sec.startswith("- ") and sec.rstrip().endswith("| 대기→완료 | 시험 이유"), sec
    journal = (run_dir.path / "journal.md").read_text(encoding="utf-8")
    assert "| 표 밖 전이 | T001 | 대기→완료: 시험 이유 (거부 이유: {} 대기→완료".format(NOT_TABLE) in journal


def test_r22_17_unlisted_cli_rejects_unmet_condition_inside_table(run_dir):
    # U는 표 안 전이의 조건 미충족(→보류의 R·r 없음)을 넘기지 못한다
    run_dir.task("T001", "전이 시험", status="진행")
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "--status", "보류", "--unlisted", "조건 없이")
    assert r.returncode == 3, r.output
    assert "거부: T001 — 보류는 --record(사용자 답) 또는 --reason(메인 판단)과 함께{} (머리 파일은 그대로)".format(
        task_set.UNLISTED_ONLY) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before
    assert not (run_dir.path / "journal.md").exists()


def test_r22_17_unlisted_cli_ignored_when_transition_allowed(run_dir):
    run_dir.task("T001", "전이 시험", status="진행")
    r = run_script("task_set", run_dir, "T001", "--status", "자체검증", "--unlisted", "쓸데없음")
    assert r.returncode == 0, r.output
    assert front_value(run_dir, "status") == "자체검증"
    assert "표 밖 전이" not in load(run_dir)["_sections"]
    assert not (run_dir.path / "journal.md").exists()


def test_r22_17_unlisted_cli_rejects_missing_judges(run_dir):
    # 필요한 판정 없음(자체검증→승인대기, 판정 파일 없음)도 U로 넘기지 못한다
    run_dir.task("T001", "전이 시험", kind="implementation", block="구현", status="자체검증", **NEW)
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기", "--unlisted", "판정 없이")
    assert r.returncode == 3, r.output
    assert "거부: T001 — 필요한 판정이 없음: " in r.stdout
    assert "{} (머리 파일은 그대로)".format(task_set.UNLISTED_ONLY) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before
    assert not (run_dir.path / "journal.md").exists()


def test_r22_17_unlisted_cli_rejects_stage_rule_before_table(run_dir):
    # T041: stage 좁힘(2.2 2행)은 전이표보다 먼저라, 표 밖 짝(대기→완료)이어도 stage 거부를 U로 넘기지 못한다
    run_dir.task("T001", "전이 시험", kind="merge", block="검증", stage="실행", **NEW)
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "--status", "완료", "--unlisted", "x")
    assert r.returncode == 3, r.output
    assert "거부: T001 — merge는 stage: 끝이 된 뒤에 완료{} (머리 파일은 그대로)".format(
        task_set.UNLISTED_ONLY) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before
    assert not (run_dir.path / "journal.md").exists()


def test_r22_17_unlisted_cli_runs_outside_table_after_stage_rule_passes(run_dir):
    # T041: stage 좁힘을 지나면(→승인대기, 묻는 단계 실행승인) 표 밖 짝(대기→승인대기)은 U로 실행하고 기록한다
    run_dir.task("T001", "전이 시험", kind="merge", block="검증", stage="실행승인", **NEW)
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기", "--unlisted", "x")
    assert r.returncode == 0, r.output
    assert "T001: 대기→승인대기" in r.stdout.splitlines()
    assert front_value(run_dir, "status") == "승인대기"
    sec = load(run_dir)["_sections"].get("표 밖 전이", "")
    assert sec.startswith("- ") and sec.rstrip().endswith("| 대기→승인대기 | x"), sec


# 18 키=값: status·retry·kind는 전용 옵션으로만, machine_check=값은 진행→자체검증 전이(--status 자체검증)와 함께서만.
#    거부는 종료 3이고 파일은 그대로. 스크립트가 채우는 키도 그대로 거부
def test_r22_18_key_value_status_rejected(run_dir):
    run_dir.task("T001", "전이 시험")
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "status=완료")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} (머리 파일은 그대로)".format(task_set.OPTION_ONLY.format("status")) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before


def test_r22_18_key_value_kind_rejected(run_dir):
    run_dir.task("T001", "전이 시험", status="진행")
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기")
    assert r.returncode == 3, r.output
    assert "진행→승인대기는 합치기·마무리·배포 실행만" in r.stdout
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "kind=merge", "stage=실행승인", "--status", "승인대기")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} (머리 파일은 그대로)".format(task_set.OPTION_ONLY.format("kind")) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before


def test_r22_18_key_value_script_keys_rejected(run_dir):
    run_dir.task("T001", "전이 시험")
    r = run_script("task_set", run_dir, "T001", "rules=2")
    assert r.returncode == 3, r.output
    assert "rules는 스크립트가 채우는 키다(키=값으로 바꾸지 않는다)" in r.stdout
    assert front_value(run_dir, "rules") is None


def test_r22_18_key_value_status_with_status_option_rejected(run_dir):
    run_dir.task("T001", "전이 시험")
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "status=완료")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} (머리 파일은 그대로)".format(task_set.OPTION_ONLY.format("status")) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before


def test_r22_18_key_value_retry_rejected(run_dir):
    run_dir.task("T001", "전이 시험", kind="implementation", block="구현", status="자체검증", retry="2")
    run_dir.judge("T001", READ_JUDGE)
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge")
    assert r.returncode == 3, r.output
    assert "재시도 상한 2" in r.stdout
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "retry=0", "--status", "진행", "--archive-judge")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} (머리 파일은 그대로)".format(task_set.OPTION_ONLY.format("retry")) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before
    assert (run_dir.task_dir("T001") / "judge.md").is_file()
    assert not (run_dir.task_dir("T001") / "judge.r1.md").exists()


def test_r22_18_key_value_status_with_amend_criteria_rejected(run_dir, tmp_path):
    # 출처는 받는 꼴(`작성자 …`)이어야 한다. 아니면 상태와 상관없이 출처 검사에서 거부된다
    run_dir.task("T001", "전이 시험", kind="implementation", block="구현", status="자체검증")
    fixed = write(tmp_path / "criteria-new.md", "1. 고친 판정 기준\n")
    r = run_script("task_set", run_dir, "T001", "--amend-criteria", fixed, "--source", "작성자 x")
    assert r.returncode == 3, r.output
    assert "판정 기준 정정은 판정자가 뜨기 전(대기·진행)에만" in r.stdout
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "status=진행", "--amend-criteria", fixed, "--source", "작성자 x")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} (머리 파일은 그대로)".format(task_set.OPTION_ONLY.format("status")) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before
    assert not (run_dir.task_dir("T001") / "criteria.amend1.md").exists()


def test_r22_18_key_value_machine_check_without_selfcheck_rejected(run_dir):
    run_dir.task("T001", "전이 시험", kind="implementation", block="구현", status="자체검증", machine_check="3", **NEW)
    write(run_dir.task_dir("T001") / "judge-run.md", RUN_JUDGE)
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기")
    assert r.returncode == 3, r.output
    assert "필요한 판정이 없음: judge.md 없음" in r.stdout
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "machine_check=0", "--status", "승인대기")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} (머리 파일은 그대로)".format(task_set.SELFCHECK_ONLY.format("machine_check")) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before


def test_r22_18_key_value_machine_check_with_selfcheck_skips_machine_check(run_dir):
    # 이 짝은 4.7 뒤에도 허용 그대로다(machine_check=값은 진행→자체검증 전이(--status 자체검증)와 함께서만)
    run_dir.task("T001", "전이 시험", kind="implementation", block="구현", status="진행", **NEW)
    r = run_script("task_set", run_dir, "T001", "machine_check=0", "--status", "자체검증")
    assert r.returncode == 0, r.output
    assert "T001: 진행→자체검증" in r.stdout.splitlines()
    assert "machine_check:" not in r.stdout                   # machine_check.py를 부르지 않았다
    assert front_value(run_dir, "status") == "자체검증"
    assert front_value(run_dir, "machine_check") == "0"


def test_r22_18_key_value_machine_check_same_selfcheck_rejected(run_dir):
    # 이미 자체검증인 task의 machine_check=값 --status 자체검증(상태 그대로)은 거부.
    #    받으면 기계 조건 값을 덮어 읽기 판정 없이 승인대기로 간다. 받는 짝은 진행→자체검증뿐(위 사례)
    run_dir.task("T001", "전이 시험", kind="implementation", block="구현", status="자체검증", machine_check="3", **NEW)
    write(run_dir.task_dir("T001") / "judge-run.md", RUN_JUDGE)
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    r = run_script("task_set", run_dir, "T001", "machine_check=0", "--status", "자체검증")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} (머리 파일은 그대로)".format(task_set.SELFCHECK_ONLY.format("machine_check")) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기")
    assert r.returncode == 3, r.output
    assert "거부: T001 — {}".format(NO_READ_JUDGE) in r.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before


# 없앤 값 멈춤: 어느 상태 집합에도 없어 대기로 읽지 않는다. 전이표에 없는 짝이라 --unlisted로만 움직인다
@pytest.mark.parametrize("new", ["완료", "진행"])
def test_r21_removed_status_pause_rejected_cli(run_dir, new):
    run_dir.task("T001", "전이 시험", status="멈춤")
    r = run_script("task_set", run_dir, "T001", "--status", new)
    assert r.returncode == 3, r.output
    assert "거부: T001 — {} 멈춤→{}(--unlisted \"이유\"로만)".format(NOT_TABLE, new) in r.stdout
    assert front_value(run_dir, "status") == "멈춤"


def test_r21_removed_status_pause_to_running_with_unlisted_cli(run_dir):
    run_dir.task("T001", "전이 시험", status="멈춤")
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "--unlisted", "시험 이유")
    assert r.returncode == 0, r.output
    assert "T001: 멈춤→진행" in r.stdout.splitlines()
    assert front_value(run_dir, "status") == "진행"


# 없앤 값 → 보류: *→보류 행이라 --reason으로 보류가 된다(대기로 바꿔 읽지 않음)
def test_r21_removed_status_pause_to_hold_with_reason_cli(run_dir):
    run_dir.task("T001", "전이 시험", status="멈춤")
    r = run_script("task_set", run_dir, "T001", "--status", "보류", "--reason", "x")
    assert r.returncode == 0, r.output
    assert "T001: 멈춤→보류" in r.stdout.splitlines()
    assert front_value(run_dir, "status") == "보류"


# ================================================================ 2.3 stage 좁힘 (함수 단위)

# 1 → 승인대기: st가 묻는 단계
@pytest.mark.parametrize("kind,ask,other", [("merge", "실행승인", "실행"), ("wrap-up", "결과승인", "실행"),
                                            ("deploy-exec", "직전확인", "명령")])
def test_r23_1_to_waiting_approval_needs_ask_stage(run_dir, kind, ask, other):
    t = make(run_dir, kind=kind, status="진행", stage=other, **NEW)
    assert rule(run_dir, t, "진행", "승인대기") == "{}의 승인대기는 묻는 단계와 함께(stage=결과승인/넣기승인/실행승인/직전확인)".format(kind)
    t2 = make(run_dir, "T002", kind=kind, status="진행", stage=ask, **NEW)
    assert rule(run_dir, t2, "진행", "승인대기") is None


# 2 승인대기 → 진행: --screen-snapshot이 아니면 st가 묻는 단계도 끝도 아님
def test_r23_2_waiting_approval_to_run_needs_next_run_stage(run_dir):
    for tid, st in (("T001", "결과승인"), ("T002", "끝")):
        t = make(run_dir, tid, kind="merge", status="승인대기", stage=st, **NEW)
        assert rule(run_dir, t, "승인대기", "진행", record=REC_OK) \
            == "승인대기→진행은 다음 실행 단계와 함께(stage=실행승인/실행/결과승인/끝 가운데 묻는 단계가 아닌 것)"
        assert rule(run_dir, t, "승인대기", "진행", snapshot=True) is None
    t3 = make(run_dir, "T003", kind="merge", status="승인대기", stage="실행", **NEW)
    assert rule(run_dir, t3, "승인대기", "진행", record=REC_OK) is None


# 3 → 완료: st == 끝
@pytest.mark.parametrize("kind", ["merge", "wrap-up", "deploy-exec"])
def test_r23_3_to_done_needs_stage_end(run_dir, kind):
    t = make(run_dir, kind=kind, status="진행", stage="실행승인" if kind != "deploy-exec" else "기록", **NEW)
    assert rule(run_dir, t, "진행", "완료", record=REC_OK) == "{}는 stage: 끝이 된 뒤에 완료".format(kind)


# 4 → 완료, merge: exec.verify 통과, 그리고 실행 판정의 통과 못 한 기준 0이거나 "답함"
def test_r23_4_merge_done_needs_verify(run_dir):
    t = make(run_dir, kind="merge", status="진행", stage="끝", **NEW)
    why = rule(run_dir, t, "진행", "완료", record=REC_OK)
    assert why == "exec.py --verify 실패(얼린 지점 없음(exec.py --freeze)) — stage=결과승인으로 승인을 받는다"
    freeze_ok(run_dir, "T001")
    assert rule(run_dir, load(run_dir), "진행", "완료", record=REC_OK) is None


def test_r23_4_merge_done_with_failed_run_criteria_needs_answer(run_dir):
    t = make(run_dir, kind="merge", status="승인대기", stage="끝",
             run_judge="판정자: xjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 기준 2: 시험 실패\n", **NEW)
    freeze_ok(run_dir, "T001")
    t = load(run_dir)
    assert rule(run_dir, t, "진행", "완료", record=REC_OK) == "실행 판정에 통과 못 한 기준 1개 — stage=결과승인으로 승인을 받는다"
    # 답함: 옛 상태 승인대기·옛 stage 결과승인·R
    assert rule(run_dir, t, "승인대기", "완료", record=REC_OK, old_stage="결과승인") is None
    assert rule(run_dir, t, "승인대기", "완료", old_stage="결과승인") \
        == "실행 판정에 통과 못 한 기준 1개 — stage=결과승인으로 승인을 받는다"
    # 답함: approved-cmds-결과승인.md가 있음
    freeze_ok(run_dir, "T001", point="결과승인", ran=False)
    write(run_dir.task_dir("T001") / "exec.md",
          "- 2026-10-15 10:01:00 | echo ok | 종료 코드 0 | 지점 실행승인:1\n"
          "- 2026-10-15 10:02:00 | echo ok | 종료 코드 0 | 지점 결과승인:1\n")
    assert rule(run_dir, load(run_dir), "진행", "완료", record=REC_OK) is None


# 5 → 완료, wrap-up: "답함"이고 exec.verify 통과
def test_r23_5_wrap_up_done_needs_answer_then_verify(run_dir):
    t = make(run_dir, kind="wrap-up", block="마무리", status="승인대기", stage="끝", **NEW)
    assert rule(run_dir, t, "진행", "완료", record=REC_OK) == "마무리는 결과승인(승인대기)에서 --record와 함께 완료"
    assert rule(run_dir, t, "승인대기", "완료", old_stage="결과승인") == "마무리는 결과승인(승인대기)에서 --record와 함께 완료"
    assert rule(run_dir, t, "승인대기", "완료", record=REC_OK, old_stage="결과승인") \
        == "exec.py --verify 실패(얼린 지점 없음(exec.py --freeze))"
    freeze_ok(run_dir, "T001")
    assert rule(run_dir, load(run_dir), "승인대기", "완료", record=REC_OK, old_stage="결과승인") is None


# 6 → 완료, deploy-exec: deploy_outcome이 유지이고 approved-cmds-*가 있으면 exec.verify 통과
def test_r23_6_deploy_exec_done_keep_with_frozen_needs_verify(run_dir):
    t = make(run_dir, kind="deploy-exec", block="배포", status="진행", stage="끝", deploy_outcome="유지", **NEW)
    assert rule(run_dir, t, "진행", "완료", record=REC_OK) is None          # 얼린 명령 없음
    freeze_ok(run_dir, "T001", ran=False)
    why = rule(run_dir, load(run_dir), "진행", "완료", record=REC_OK)
    assert why == "exec.py --verify 실패(실행승인: 1줄 실패 — 실행승인:1 안 돎)"
    freeze_ok(run_dir, "T001")
    assert rule(run_dir, load(run_dir), "진행", "완료", record=REC_OK) is None


def test_r23_6_deploy_exec_done_not_keep_skips_verify(run_dir):
    make(run_dir, kind="deploy-exec", block="배포", status="진행", stage="끝", deploy_outcome="되돌림", **NEW)
    freeze_ok(run_dir, "T001", ran=False)
    assert rule(run_dir, load(run_dir), "진행", "완료", record=REC_OK) is None
