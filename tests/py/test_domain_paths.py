"""영역 규칙의 경로 쪽(설계 domain 3.2, 3.4, 3.8): 인프라 경로를 건드린 코드 task의 알림 불가, 그 실행의 첫 화면에 보이는
경로 목록 줄, 화면 경로에 닿는 구현의 읽기 판정, `detect-stack.sh`의 「경로 단서」.

가짜 실행 폴더(`RunDir`)와 그 부모 폴더의 프로젝트 설정 「경로 목록」으로 `screen.py`를 명령행으로 돌리고,
`screen.notify_status`·`required_judges`는 함수로 부른다. 규칙은 그 task의 `started_version`이 1.1.0 이상일 때만 켜진다.
"""
import shutil
import subprocess
from datetime import datetime

from conftest import ROOT, run_script, write

import screen

PATHS = {"화면": "client/**", "인프라": ".github/workflows/**, db/migrations/**", "문서": "docs/**"}
RESULT = ("# T001 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n{notify}\n"
          "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 설계대로 한 작업 1\n\n"
          "## 스스로 줄임\n없음\n\n## 본문\n본문\n\n## 규약 추가\n없음\n")
READ_JUDGE = ("판정자: rjudge-T001 {now}\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n"
              "| 기준 | 판정 | 근거 |\n|---|---|---|\n| 1 | 통과 | 읽음 |\n\n## 판단 대조\n- 없음\n")
RUN_JUDGE = ("판정자: xjudge-T001 {now}\n\n## 통과 못 한 기준\n- 없음\n\n## 검사 입력과 독립 근거\n"
             "- 제품 commit/diff: abc1234 | 시험 소스: tests@abc | 설정: cfg@abc | lock/설치: lock@abc | 명령: pytest -q | "
             "환경 초기화: 없음 | 판정자: xjudge-T001 | 시각: {now} | 종료 코드: 0 | 로그: logs/pytest.txt\n"
             "\n## 남은 검사와 자원 대기\n- 없음\n"
             "\n## 흐름 리뷰 전·후\n### 장면\n- 전: 칸 전부\n- 후: 두 칸\n")   # 흐름별 검증이 읽는 절이다. 코드 task에는 쓰이지 않는다
FIRST_RUN_LINE = "알림 조건(정해 주실 것·하실 일이 비고"


def settings(run_dir, detected="dryrun", paths=PATHS):
    """실행 폴더의 부모 폴더에 프로젝트 설정 「경로 목록」을 둔다."""
    write(run_dir.path.parent / "devflow-harness.project.md",
          "# 프로젝트 설정\n\n- 개발 기준 브랜치: main\n\n## 경로 목록\n- 감지한 실행: {}\n".format(detected)
          + "".join("- {} 경로: {}\n".format(k, paths.get(k, "없음")) for k in ("화면", "인프라", "문서")))


def code_task(run_dir, touch, version="1.1.0", notify="- 없음", tid="T001"):
    """자체 검증을 마친 코드 task(판정 파일 둘 다 통과). 판정 시각은 지금이다(기록 점검 R3이 파일 시각과 견준다)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.task(tid, "주문 저장", sections={"건드릴 파일": touch}, kind="implementation", block="구현", status="자체검증",
                 flow="orders", started_version=version, rules="2")
    run_dir.result(tid, RESULT.replace("T001", tid).format(notify=notify))
    run_dir.judge(tid, READ_JUDGE.replace("T001", tid).format(now=now))
    write(run_dir.task_dir(tid) / "judge-run.md", RUN_JUDGE.replace("T001", tid).format(now=now))


def screen_lines(run_dir, tid="T001"):
    r = run_script("screen", run_dir, tid)
    assert r.returncode == 0, r.output
    return r.stdout.splitlines()


def notify_line(lines):
    return [l for l in lines if l.startswith("알림 조건")]


def cell_lines(lines, cell, next_cell):
    """`■ {cell} (n)` 줄 다음부터 `■ {next_cell}` 줄 앞까지."""
    start = next(i for i, l in enumerate(lines) if l.startswith("■ {} (".format(cell)))
    end = next(i for i, l in enumerate(lines) if l.startswith("■ {} (".format(next_cell)))
    return [l for l in lines[start + 1:end] if l]


# --- (가)(나) 인프라 경로를 건드린 코드 task는 알림으로 지나가지 않는다 ------------------------------------------------

def test_infra_touch_blocks_notify(run_dir):
    settings(run_dir, detected="other-run")
    code_task(run_dir, "- db/migrations/0002.sql\n- src/orders.py")

    lines = screen_lines(run_dir)
    ok, why = screen.notify_status(str(run_dir), "T001")

    assert notify_line(lines) == ["알림 조건: 미충족(인프라 경로: db/migrations/0002.sql)"]
    assert (ok, why) == (False, "인프라 경로: db/migrations/0002.sql")


def test_touch_outside_infra_paths_notifies(run_dir):
    # 양성 대조: 같은 task의 경로가 인프라 경로 밖이면 알림 조건이 충족된다
    settings(run_dir, detected="other-run")
    code_task(run_dir, "- src/orders.py\n- docs/orders.md")

    lines = screen_lines(run_dir)
    ok, _ = screen.notify_status(str(run_dir), "T001")

    assert len(notify_line(lines)) == 1
    assert notify_line(lines)[0].startswith(FIRST_RUN_LINE) and ": 충족 — " in notify_line(lines)[0]
    assert ok is True


def test_infra_rule_is_off_for_tasks_started_before_1_1_0(run_dir):
    settings(run_dir, detected="other-run")
    code_task(run_dir, "- db/migrations/0002.sql\n- src/orders.py", version="1.0.4")

    lines = screen_lines(run_dir)
    ok, _ = screen.notify_status(str(run_dir), "T001")

    assert not any(l.startswith("알림 조건: 미충족(인프라 경로:") for l in lines)
    assert notify_line(lines)[0].startswith(FIRST_RUN_LINE) and ": 충족 — " in notify_line(lines)[0]
    assert ok is True


# --- (다) 그 실행의 첫 화면에 경로 목록 줄(칸 수에 세지 않음) ------------------------------------------------------

PATHS_LINE = ("- [경로 목록] 화면: client/** / 인프라: .github/workflows/**, db/migrations/** / 문서: docs/**"
              " — 틀렸으면 이 답에서 고쳐 주세요")


def counts_line(lines):
    return [l for l in lines if l.startswith("counts:")]


def test_paths_line_on_first_screen_after_notify_cell_and_not_counted(run_dir):
    settings(run_dir)
    code_task(run_dir, "- src/orders.py", notify="- 저장 함수 이름을 설계와 다르게 했습니다")
    run_dir.task("T002", "다음 설계", status="대기")

    lines = screen_lines(run_dir)
    settings(run_dir, detected="other-run")   # 감지한 실행이 다르면 줄이 없다(같은 결과의 대조)
    without = screen_lines(run_dir)

    assert cell_lines(lines, "알릴 것", "답하신 것의 반영") == ["- 저장 함수 이름을 설계와 다르게 했습니다", PATHS_LINE]
    assert PATHS_LINE not in without
    assert counts_line(lines) == counts_line(without) == [
        "counts: n_decide=0 n_todo=0 n_notify=1 n_unverified=0 n_children=0"]
    assert "알림 줄에 함께 적을 것: " + PATHS_LINE[2:] in lines


def test_paths_line_absent_once_another_task_was_approved(run_dir):
    settings(run_dir)
    code_task(run_dir, "- src/orders.py")
    run_dir.task("T002", "요구사항 질문", kind="question", block="요구사항", status="완료",
                 approval_requested="2026-10-30 09:00:00", approved="2026-10-30 09:05:00")

    lines = screen_lines(run_dir)

    assert PATHS_LINE not in lines
    assert cell_lines(lines, "알릴 것", "답하신 것의 반영") == ["- 없음"]


# --- (라) 화면 경로에 닿는 구현은 읽기 판정을 받는다 -------------------------------------------------------------

def test_screen_path_touch_requires_read_judge(run_dir, lib):
    settings(run_dir)
    code_task(run_dir, "- client/orders/List.tsx", tid="T001")
    code_task(run_dir, "- src/orders.py", tid="T002")
    code_task(run_dir, "- client/orders/List.tsx", tid="T003", version="1.0.4")
    tasks = run_dir.tasks()

    assert "read" in lib.required_judges(tasks["T001"])
    assert "read" not in lib.required_judges(tasks["T002"])
    assert "read" not in lib.required_judges(tasks["T003"])
    assert "run" in lib.required_judges(tasks["T002"])   # 같은 꼴의 task가 판정을 계산함(형 확인)


# --- (마) detect-stack.sh 「경로 단서」 ------------------------------------------------------------------------

def detect(folder):
    bash = shutil.which("bash")
    assert bash, "bash가 없음: Git Bash(또는 bash)를 PATH에 두고 다시 돌린다"
    proc = subprocess.run([bash, str(ROOT / "scripts" / "detect-stack.sh"), str(folder)],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout.splitlines()
    clues = out[out.index("## 경로 단서") + 1:]
    sections, cur = {}, None
    for line in clues:
        if line.startswith("### "):
            cur = line[4:]
            sections[cur] = []
        elif cur and line.startswith("- "):
            sections[cur].append(line[2:])
    return sections


def test_detect_stack_path_clues(tmp_path):
    proj = tmp_path / "proj"
    for name in (".github/workflows/ci.yml", "db/migrations/0001.sql", "docs/a.md", "client/a.tsx"):
        write(proj / name, "x\n")

    clues = detect(proj)

    assert clues == {"화면 경로 후보": ["client/**"],
                     "인프라 경로 후보": [".github/workflows/**", "db/migrations/**"],
                     "문서 경로 후보": ["docs/**"]}


def test_detect_stack_path_clues_empty_folder(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    assert detect(empty) == {"화면 경로 후보": ["없음"], "인프라 경로 후보": ["없음"], "문서 경로 후보": ["없음"]}
