"""특성 시험 ③: 승인 화면·보드·자식 만들기 미리 보기·아스키 보드의 표준 출력을 골든 파일과 대조한다
.

- 네 명령(`screen.py {실행 폴더} T001`, `board.py {실행 폴더} --ready`, `spawn_children.py {실행 폴더} T001 --dry-run`,
  `board_ascii.py {실행 폴더}`)을 한 임시 실행 폴더에서 돌린다. 출력 꼴 자체가 동작이라(메인이 그대로 읽어 옮김) 줄 하나까지 대조한다.
- 아스키 보드 골든은 지금 동작으로 고정한다. 범례 줄은 없앤 상태 `멈춤`을 뺀 꼴이다.
- 가림은 세 가지뿐이다: 실행 폴더 절대 경로 → `{RUN}`, 시각(`YYYY-MM-DD HH:MM`, 초 포함 꼴) → `{TIME}`,
  `하네스 판본:`·`메인 컨텍스트:`·`! 에이전트 정의:`로 시작하는 줄은 줄째 자리 표시 줄로. 그 밖은 가리지 않는다.
- 골든은 환경 변수 `DEVFLOW_UPDATE_GOLDEN=1`일 때만 다시 쓴다(바뀐 차이는 경고로 남긴다). 기본은 대조만 한다.
"""
import difflib
import os
import re
import warnings
from pathlib import Path

import pytest

from conftest import RunDir, run_script, write

GOLDEN = Path(__file__).resolve().parent / "golden"
UPDATE = os.environ.get("DEVFLOW_UPDATE_GOLDEN") == "1"

TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?")
# 줄째 가리는 줄: 머리말 → 그 자리에 둘 줄. 자리 표시 줄은 원래 머리말로 시작하지 않는다(골든에 원래 줄이 남지 않게)
LINE_MASKS = {
    "하네스 판본:": "{VERSION_LINE}",
    "메인 컨텍스트:": "{CONTEXT_LINE}",
    "! 에이전트 정의:": "{AGENT_DEF_LINE}",
}


def mask(text, run_path):
    """출력에서 환경에 따라 바뀌는 세 가지만 가린다."""
    roots = sorted({str(run_path), str(Path(run_path).resolve())}, key=len, reverse=True)
    out = []
    for line in text.splitlines():
        prefix = next((p for p in LINE_MASKS if line.startswith(p)), None)
        if prefix is not None:
            out.append(LINE_MASKS[prefix])
            continue
        for root in roots:
            line = line.replace(root, "{RUN}")
        out.append(TIME_RE.sub("{TIME}", line))
    return "\n".join(out) + "\n"


RESULT_T001 = """# T001 회원 가입 설계 결과

## 승인 화면
### 정해 주실 것
- 가입 확인 메일을 다시 보내는 간격을 정해 주세요: 지금은 간격 없이 누를 때마다 보냅니다. (가) 1분 / (나) 5분. 추천 (가), 사용자가 기다리는 시간이 짧음
### 하실 일·허용 요청
- 없음
### 알릴 것
- 가입 폼의 필드 순서를 화면 정본대로 이름 → 메일 → 비밀번호로 둡니다
- 외부 메일 발송 서비스의 일일 한도는 설계 문서의 값을 그대로 씁니다
### 답하신 것의 반영
- 없음
### 확인 안 된 것
- 메일 발송 지연이 1분을 넘는 경우는 실제 서비스로 확인하지 않았습니다
### 건수만
- 설계 결정 4개

## 결정 지도
- 가입 확인 메일 간격(사용자)

## 스스로 줄임
없음

## 본문
설계 본문.

## 자식 목록
나눈 기준: 화면과 API를 따로 판정할 수 있게 나눔

### 자식: 가입 화면
- kind: implementation
- flow: signup
- depends_on:
- difficulty: 일반
- closes_ac: AC-01
- partial_ac:
- 한 줄: 가입 폼과 확인 메일 다시 보내기 단추를 만든다
#### 범위
- 가입 폼
#### 판정 기준
1. 가입 폼 시험 통과
#### 건드릴 파일
- src/signup/form.tsx
#### 시그니처와 결정 번호
- D-1
#### 정본의 절
- 2절

### 자식: 가입 API
- kind: implementation
- flow: signup
- depends_on:
- difficulty: 복잡
- closes_ac: AC-02
- partial_ac: AC-01
- 한 줄: 가입 요청과 확인 메일 발송 API를 만든다
#### 범위
- 가입 API
#### 판정 기준
1. 가입 API 시험 통과
#### 건드릴 파일
- src/signup/api.ts
#### 시그니처와 결정 번호
- D-2
#### 정본의 절
- 3절

### 자식: [백로그] 가입 통계
- kind: implementation
- flow: stats
- depends_on: 가입 API
- difficulty: 단순
- closes_ac:
- partial_ac:
- 한 줄: 가입 수를 날마다 센다
#### 범위
- 가입 통계
#### 판정 기준
1. 통계 시험 통과
#### 건드릴 파일
- src/stats/signup.ts
#### 시그니처와 결정 번호
- 없음
#### 정본의 절
- 4절
"""

JUDGE_T001 = """판정자: read-judge-T001 2026-10-15 10:20:30
# T001 판정

## 통과 못 한 기준
- 없음

## 판정 표
| 기준 | 판정 | 확인 방법 | 근거 |
|---|---|---|---|
| 1 | 통과 | 원본 전부 대조 | 설계 2절 |
| 2 | 통과 | 기록만 확인 | 결정 지도 |

## 확인 방법 요약
원본 전부 대조 1 · 기록만 확인 1

## 못 본 범위
- 없음

## 칸 분류 확인
- 알릴 것 → 확인 안 된 것 | 외부 메일 발송 서비스 | 한도 값을 실제 서비스로 보지 않음

## 권장
- 없음
"""


def build_run(run_dir):
    """네 명령이 함께 읽는 실행 폴더. 승인대기 설계(T001)와 그 아래 대기 task, 흐름 둘, 보류에 막힌 대기 task."""
    t001 = run_dir.task("T001", "회원 가입 설계", kind="design", block="설계", status="승인대기",
                        started="2026-10-15 09:10:00", approval_requested="2026-10-15 10:21:00",
                        sections={"판정 기준": "1. 설계 2절이 있다\n2. 결정 지도가 있다",
                                  "판정 기준 정정": "- 2026-10-15 09:30:00 | 정정 1 | 출처: 사용자 답 T001 2026-10-15 09:29:50"
                                                 " | 원문: criteria.orig.md | 고친 문장: criteria.amend1.md",
                                  "넘길 이상 신호": "- 화면 정본의 필드 이름이 요구사항과 한 곳 다름"})
    write(t001.parent / "criteria.orig.md", "1. 설계 2절이 있다\n")
    write(t001.parent / "criteria.amend1.md", "1. 설계 2절이 있다\n2. 결정 지도가 있다\n")
    run_dir.result("T001", RESULT_T001)
    run_dir.judge("T001", JUDGE_T001)
    run_dir.task("T002", "가입 요구사항 질문", kind="question", block="질문", status="대기")
    run_dir.task("T003", "로그인 화면", kind="implementation", block="구현", status="대기", flow="login")
    run_dir.task("T004", "로그인 설계 후속", kind="design", block="설계", status="대기", parent="T001")
    run_dir.task("T005", "알림 설계", kind="design", block="설계", status="보류")
    run_dir.task("T006", "알림 화면", kind="ui-design", block="설계", status="대기", depends_on=["T005"])
    run_dir.flow("login")
    return run_dir


@pytest.fixture(scope="module")
def golden_run(tmp_path_factory):
    return build_run(RunDir(tmp_path_factory.mktemp("golden") / "ws" / "dryrun"))


COMMANDS = {
    "screen": ("screen", "{run}", "T001"),
    "board_ready": ("board", "{run}", "--ready"),
    "spawn_dry_run": ("spawn_children", "{run}", "T001", "--dry-run", "--now", "2026-10-15 10:30:00"),
    "board_ascii": ("board_ascii", "{run}"),
}


def agent_def_precondition(lib):
    """`board.py --ready`는 플러그인 `agents/`의 판정자 정의를 검사해 문제마다 `! 에이전트 정의:` 줄을 더 찍는다. 그 줄은 가림이
    자리 표시 한 줄로 바꿀 뿐 지우지 않으므로, 정의 문제가 있는 환경에서는 골든과 줄 수부터 달라진다.
    대조(와 갱신) 전에 확인하고, 문제가 있으면 무엇이 문제이고 어떻게 준비하는지 말하고 실패한다(test-rules ⑥)."""
    problems = lib.agent_def_problems()
    if problems:
        pytest.fail("판정자 정의 문제: {} — 보드 골든은 정의 경고가 없는 환경에서만 대조한다. "
                    "판정자 정의 두 파일(판 표지와 tools의 Write를 갖춘 것)을 고치고 다시 돌린다".format("; ".join(problems)))


# 명령마다 출력이 기대는 환경 전제. screen.py·spawn_children.py·board_ascii.py는 정의 검사를 부르지 않는다
# (판본·컨텍스트 줄은 환경과 상관없이 늘 한 줄이라 줄째 가림으로 흡수된다).
PRECONDITIONS = {"board_ready": agent_def_precondition}


@pytest.mark.parametrize("name", list(COMMANDS))
def test_golden_output(golden_run, lib, name):
    if name in PRECONDITIONS:
        PRECONDITIONS[name](lib)
    script, *args = COMMANDS[name]
    proc = run_script(script, *[a.format(run=golden_run.path) for a in args])
    assert proc.returncode == 0, proc.output
    assert proc.stderr == "", proc.stderr
    got = mask(proc.stdout, golden_run.path)
    path = GOLDEN / (name + ".txt")
    if UPDATE:
        old = path.read_text(encoding="utf-8") if path.is_file() else ""
        if old != got:
            write(path, got)
            # 골든을 바꾼 변경은 대조 결과를 남긴다(test-rules ⑦)
            warnings.warn("골든을 다시 씀: {}\n{}".format(path.name, "".join(difflib.unified_diff(
                old.splitlines(True), got.splitlines(True), "이전 " + path.name, "새 " + path.name))))
        return
    if not path.is_file():
        pytest.fail("골든 파일 없음: {} — DEVFLOW_UPDATE_GOLDEN=1 python3 -m pytest tests/py/test_golden.py로 만든다".format(path))
    want = path.read_text(encoding="utf-8")
    diff = "".join(difflib.unified_diff(want.splitlines(True), got.splitlines(True), "골든 " + path.name, "지금 출력"))
    assert got == want, "골든과 다름(가린 뒤):\n" + diff


def test_mask_covers_only_three_kinds():
    """가림 함수: 실행 폴더 경로·시각·세 머리말 줄만 바꾸고, 머리말이 줄 가운데 있거나 다른 숫자 꼴이면 그대로 둔다."""
    run = "/tmp/pytest-of-x/golden0/ws/dryrun"
    text = "\n".join([
        "하네스 판본: 지금 abc1234 agents 2026-10-15 09:00 / run.md (없음) — 다름",
        "메인 컨텍스트: 측정 불가(세션 ID 환경 변수 없음)",
        "! 에이전트 정의: read-judge.md 없음 — 판정자 정의를 고치기 전에는 task를 띄우지 않는다",
        "부모의 result.md가 없음: {}/tasks/T001/result.md".format(run),
        "- 2026-10-15 09:30:00 | 정정 1 · 결과 파일 마지막 수정 2026-10-15 09:31",
        "참고: 하네스 판본: 줄 가운데 · 날짜만 2026-10-15 · 버전 1.2.3 · 숫자 12:34",
        "! 기록 점검: T001 R2: 판정 기준이 다름",
    ])
    assert mask(text, run).splitlines() == [
        "{VERSION_LINE}",
        "{CONTEXT_LINE}",
        "{AGENT_DEF_LINE}",
        "부모의 result.md가 없음: {RUN}/tasks/T001/result.md",
        "- {TIME} | 정정 1 · 결과 파일 마지막 수정 {TIME}",
        "참고: 하네스 판본: 줄 가운데 · 날짜만 2026-10-15 · 버전 1.2.3 · 숫자 12:34",
        "! 기록 점검: T001 R2: 판정 기준이 다름",
    ]
