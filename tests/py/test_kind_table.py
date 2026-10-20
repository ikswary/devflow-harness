"""특성 시험 ①: kind 17 × 속성 8의 지금 값(함수 단위).

기대값은 `design/peer-alignment.md` 1.1 표에서 옮긴 데이터다(아래 `EXPECTED`). 실제 값은 스크립트의 상수와 판정 함수에서
읽는다. 기대값을 같은 코드로 계산하지 않는다.

속성과 실제 값을 읽는 곳(표의 원천 칸):
- 블록: `kinds.block_of`
- 필요한 판정(읽기·실행): `lib.required_judges`(조건 칸은 조건을 하나씩 채운 task로 확인)
- 알림 정책: `kinds.notify_policy`, `kinds.STAGE_KINDS`, `kinds.NEVER_NOTIFY_KINDS`
- stage: `kinds.stages_of`
- 코드 폴더 쓰기: `board.writes`
- 흐름 상한 셈: `kinds.KINDS[kind].writers`의 code-writer, 파생 `kinds.CODE_WRITER_KINDS`
- 자동 의존: `kinds.KINDS[kind].auto_depends_in_flow`, 파생 `kinds.AUTO_DEPEND_KINDS`
- 표시 글자: `kinds.glyph`
"""
import pytest

import board
import kinds
from conftest import write

# 표의 칸 글자 그대로. "—"는 빈 칸, 알림 칸의 낱말은 표 아래 「알림」 칸의 뜻 문단의 다섯 이름.
ASK_ONLY = "승인만"
FOUR_ZERO = "네 칸 모두 0"
DECIDE_ZERO = "「정해」「하실」 0, origin 사용자면 불가"
STAGED = "단계"
NEVER = "불가"
MERGE_STAGES = ("실행승인", "실행", "결과승인", "끝")
WRAP_STAGES = ("실행승인", "실행", "결과승인", "끝")
DEPLOY_STAGES = ("사전조건", "직전확인", "명령", "확인", "결과승인", "브랜치", "기록", "넣기승인", "넣기", "끝")

# kind: (블록, 읽기 판정, 실행 판정, 알림, stage, 코드 폴더 쓰기, 흐름 상한 셈, 자동 의존, 글자)
EXPECTED = {
    "question":       ("질문",     "늘",        "—", FOUR_ZERO,   "—",           "—", "—", "—", "Q"),
    "brief":          ("기획",     "늘",        "—", ASK_ONLY,    "—",           "—", "—", "—", "B"),
    "req-overview":   ("요구사항", "늘",        "—", ASK_ONLY,    "—",           "—", "—", "—", "Q"),
    "req-detail":     ("요구사항", "늘",        "—", ASK_ONLY,    "—",           "—", "—", "—", "Q"),
    "root-cause":     ("원인 분석", "늘",       "늘", ASK_ONLY,   "—",           "예", "—", "—", "C"),
    "ui-design":      ("설계",     "늘",        "—", ASK_ONLY,    "—",           "—", "—", "—", "U"),
    "design":         ("설계",     "늘",        "—", ASK_ONLY,    "—",           "—", "—", "—", "S"),
    "implementation": ("구현",     "조건",      "늘", DECIDE_ZERO, "—",          "예", "예", "예", ""),
    "fix":            ("구현",     "늘",        "늘", DECIDE_ZERO, "—",          "예", "예", "예", "F"),
    "change":         ("",         "늘",        "—", DECIDE_ZERO, "—",           "—", "—", "—", "X"),
    "flow-verify":    ("검증",     "늘",        "—", ASK_ONLY,    "—",           "—", "—", "—", "V"),
    "reverify":       ("검증",     "늘",        "—", FOUR_ZERO,   "—",           "—", "—", "—", "R"),
    # merge의 읽기 판정은 exec.md 브랜치 판정 `충돌`이 있을 때
    "merge":          ("구현",     "조건",      "늘", STAGED,     MERGE_STAGES,  "예", "예", "—", "M"),
    "full-verify":    ("검증",     "늘",        "—", ASK_ONLY,    "—",           "—", "—", "—", "V"),
    "wrap-up":        ("마무리",   "늘",        "—", STAGED,      WRAP_STAGES,   "—", "—", "—", "W"),
    "deploy-plan":    ("배포",     "늘",        "—", NEVER,       "—",           "—", "—", "—", "D"),
    "deploy-exec":    ("배포",     "조건",      "늘", STAGED,      DEPLOY_STAGES, "—", "—", "—", "E"),
}
FIELDS = ("블록", "읽기 판정", "실행 판정", "알림", "stage", "코드 폴더 쓰기", "흐름 상한 셈", "자동 의존", "글자")

# 판정 칸의 낱말 → 함수에서 관찰한 꼴. "—"는 어느 조건에서도 요구하지 않음이다.
JUDGE_WORD = {"늘": "늘", "조건": "조건", "—": "없음"}
ALERT_ITEM_RESULT = "# T 결과\n\n## 승인 화면\n### 알릴 것\n- 설계와 달라진 점 하나\n"
# exec.py가 쓰는 브랜치 판정 줄 꼴(`- {시각} | 브랜치 판정 | {지점}:{n} | {판정} | …`). 판정 값만 바꿔 쓴다
BRANCH_LINE = "- 2026-10-15 10:00:00 | 브랜치 판정 | 실행승인:1 | {} | 앞 x 뒤 y 넣은 z@w 받은 v\n"
CONFLICT_EXEC = BRANCH_LINE.format("충돌")


def test_expected_table_covers_the_seventeen_kinds():
    # 기대 데이터가 17행이고, 스크립트가 아는 kind 집합(블록 표·글자 표)과 같다
    assert len(EXPECTED) == 17
    assert set(EXPECTED) == set(kinds.KINDS)


def _task(base, name, kind, **meta):
    d = base / name
    d.mkdir()
    t = {"kind": kind, "_dir": str(d), "_sections": {}}
    t.update(meta)
    return t


def _probes(base, kind):
    """조건 없는 task 하나와, 표에 적힌 조건(closes_ac, machine_check 3, 「알릴 것」 1, result.md 있음,
    exec.md 브랜치 판정 `충돌` 줄)을 하나씩 채운 task들."""
    plain = _task(base, "plain", kind)
    with_ac = _task(base, "ac", kind, closes_ac=["AC-01"])
    with_mc = _task(base, "mc", kind, machine_check="3")
    with_result = _task(base, "result", kind)
    write(base / "result" / "result.md", ALERT_ITEM_RESULT)
    with_conflict = _task(base, "conflict", kind)
    write(base / "conflict" / "exec.md", CONFLICT_EXEC)
    return plain, [with_ac, with_mc, with_result, with_conflict]


def _judge_word(lib, kind, role, base):
    plain, conditioned = _probes(base, kind)
    if role in lib.required_judges(plain):
        return "늘"
    if any(role in lib.required_judges(t) for t in conditioned):
        return "조건"
    return "없음"


def _notify_word(kind):
    if kind in kinds.STAGE_KINDS:
        return STAGED
    if kind in kinds.NEVER_NOTIFY_KINDS:
        return NEVER
    policy = kinds.notify_policy(kind)
    if policy == "by_decide":
        return DECIDE_ZERO
    if policy == "all_cells":
        return FOUR_ZERO
    return ASK_ONLY


def _yes(flag):
    return "예" if flag else "—"


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_kind_attributes(kind, lib, tmp_path):
    block, read, run, notify, stage, writes, flow_cap, auto_dep, letter = EXPECTED[kind]
    (tmp_path / "read").mkdir()
    (tmp_path / "run").mkdir()
    (tmp_path / "w").mkdir()

    actual = {
        "블록": kinds.block_of(kind),
        "읽기 판정": _judge_word(lib, kind, "read", tmp_path / "read"),
        "실행 판정": _judge_word(lib, kind, "run", tmp_path / "run"),
        "알림": _notify_word(kind),
        "stage": kinds.stages_of(kind) or "—",
        # change는 「건드릴 파일」이 비어 있는 꼴로 본다(정본 밖 경로를 고치는 옛 실행의 change는 `writes`가 참)
        "코드 폴더 쓰기": _yes(board.writes(_task(tmp_path / "w", "t", kind))),
        "흐름 상한 셈": _yes("code-writer" in kinds.KINDS[kind].writers),
        "자동 의존": _yes(kinds.KINDS[kind].auto_depends_in_flow),
        "글자": kinds.glyph(kind),
    }
    expected = dict(zip(FIELDS, (block, JUDGE_WORD[read], JUDGE_WORD[run], notify, stage, writes, flow_cap,
                                 auto_dep, letter)))
    assert actual == expected

    # 엔진이 쓰는 파생 집합도 같은 값이다(표의 원천 칸 둘째 값): 흐름 상한은 CODE_WRITER_KINDS,
    # 자동 의존은 AUTO_DEPEND_KINDS, stage는 STAGE_KINDS
    assert _yes(kind in kinds.CODE_WRITER_KINDS) == flow_cap
    assert _yes(kind in kinds.AUTO_DEPEND_KINDS) == auto_dep
    assert (kind in kinds.STAGE_KINDS) == (stage != "—")


@pytest.mark.parametrize("cond", ["closes_ac", "machine_check", "alert_item"])
def test_implementation_read_judge_conditions_each_add_read(cond, lib, tmp_path):
    # 표: implementation의 읽기 판정은 조건(`closes_ac`·`machine_check`=3·「알릴 것」≥1). 하나씩만 채워도 요구된다
    plain = _task(tmp_path, "plain", "implementation")
    assert lib.required_judges(plain) == {"run"}
    if cond == "closes_ac":
        t = _task(tmp_path, "c", "implementation", closes_ac=["AC-01"])
    elif cond == "machine_check":
        t = _task(tmp_path, "c", "implementation", machine_check="3")
    else:
        t = _task(tmp_path, "c", "implementation")
        write(tmp_path / "c" / "result.md", ALERT_ITEM_RESULT)
    assert lib.required_judges(t) == {"run", "read"}


def test_implementation_machine_check_other_than_3_does_not_add_read(lib, tmp_path):
    assert lib.required_judges(_task(tmp_path, "c", "implementation", machine_check="0")) == {"run"}


def test_deploy_exec_read_judge_only_with_result_md(lib, tmp_path):
    # 표: deploy-exec의 읽기 판정은 조건(`result.md` 있음)
    assert lib.required_judges(_task(tmp_path, "a", "deploy-exec")) == {"run"}
    t = _task(tmp_path, "b", "deploy-exec")
    write(tmp_path / "b" / "result.md", "# T 배포 기록\n")
    assert lib.required_judges(t) == {"run", "read"}


def test_merge_read_judge_only_with_conflict_branch_judgement(lib, tmp_path):
    # 다른 kind의 조건을 모두 채워도 충돌 줄이 없으면 실행 판정만, 브랜치 판정 `충돌`이 있으면 읽기 판정도
    t = _task(tmp_path, "m", "merge", closes_ac=["AC-01"], machine_check="3")
    write(tmp_path / "m" / "result.md", ALERT_ITEM_RESULT)
    write(tmp_path / "m" / "exec.md", BRANCH_LINE.format("병합") + BRANCH_LINE.format("병합(충돌 해결)"))
    assert lib.required_judges(t) == {"run"}
    write(tmp_path / "m" / "exec.md", BRANCH_LINE.format("병합") + CONFLICT_EXEC)
    assert lib.required_judges(t) == {"run", "read"}
