"""마른 시험 1~12를 명령행 계층에서 지킨다.

실행 폴더와 git 저장소는 모두 `tmp_path` 아래에 만든다. 시각은 기다리지 않고 `os.utime`으로 만든다.
"""
import os
import subprocess
import time
from datetime import datetime

import pytest

from conftest import RunDir, run_script, write

GIT_ID = ["-c", "user.name=dryrun", "-c", "user.email=dryrun@example.invalid", "-c", "commit.gpgsign=false"]


def screen_result(tid, decide="- 없음", todo="- 없음", notify="- 없음", children=""):
    return ("# {tid} 결과\n\n## 승인 화면\n### 정해 주실 것\n{decide}\n### 하실 일·허용 요청\n{todo}\n### 알릴 것\n{notify}\n"
            "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 설계대로 한 작업 2\n\n"
            "## 스스로 줄임\n없음\n\n## 본문\n마른 시험 본문\n\n{children}"
            "## 규약 추가\n없음\n").format(tid=tid, decide=decide, todo=todo, notify=notify, children=children)


def child_row(title, kind="design", flow="", depends="", touch="(없음)", one_line=None):
    lines = ["### 자식: " + title, "- kind: " + kind, "- flow: " + flow, "- depends_on: " + depends,
             "- difficulty: 일반", "- 한 줄: " + (one_line or title + "을 한다"),
             "#### 범위", "- " + title, "#### 판정 기준", "1. " + title + "이 있다"]
    if touch is not None:
        lines += ["#### 건드릴 파일", touch]
    return "\n".join(lines) + "\n\n"


def children_section(*rows, criterion="화면 단위"):
    return "## 자식 목록\n나눈 기준: {}\n\n{}".format(criterion, "".join(rows))


JUDGE_OK = ("판정자: rjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n"
            "| 기준 | 판정 | 근거 |\n|---|---|---|\n| 1 | 통과 | 읽음 |\n")


# --- 1 ---------------------------------------------------------------------------------------------------------

def test_s01_board_shows_table_queue_ready_and_cycle_check(run_dir):
    run_dir.task("T001", "요구사항 정리", status="완료")
    run_dir.task("T002", "설계", parent="T001")
    run_dir.task("T003", "질문 정리", kind="question", status="승인대기", approval_requested="2026-10-15 10:00:00")

    r = run_script("board", run_dir)

    assert r.returncode == 0, r.output
    lines = r.stdout.splitlines()
    assert "| id | 종류 | 제목 | 상태 | 흐름 | 부모 | 의존하는 task |" in lines
    assert "| T002 | design | 설계 | 대기 |  | T001 |  |" in lines
    assert "승인 대기 1개" in lines
    assert any(l.startswith("1. T003 질문 정리 (막고 있는 task 0개") for l in lines), r.stdout
    assert "지금 시작할 수 있는 task 1개" in lines
    assert any(l.startswith("- T002 설계 [design]") for l in lines), r.stdout
    assert "의존 고리 없음" in lines


# --- 2 ---------------------------------------------------------------------------------------------------------

def test_s02_screen_shows_six_cells_counts_children_and_notify(run_dir):
    run_dir.task("T001", "화면 설계", status="승인대기")
    kids = children_section(child_row("목록 화면", one_line="목록 화면을 그린다"),
                            child_row("상세 화면", one_line="상세 화면을 그린다"))
    run_dir.result("T001", screen_result("T001", decide="- 목록을 몇 줄씩 보일지 정한다",
                                         notify="- 정렬은 최근 순이다\n- 빈 목록 문구를 더했다", children=kids))
    run_dir.judge("T001", JUDGE_OK)

    r = run_script("screen", run_dir, "T001")

    assert r.returncode == 0, r.output
    lines = r.stdout.splitlines()
    for header in ("■ 정해 주실 것 (1)", "■ 하실 일·허용 요청 (0)", "■ 알릴 것 (2)", "■ 답하신 것의 반영 (0)",
                   "■ 확인 안 된 것 (0)", "■ 건수만 (1)"):
        assert header in lines, header
    assert "■ 만들 task 2개 (나눈 기준: 화면 단위)" in lines
    assert "- 목록 화면 [design] 목록 화면을 그린다" in lines
    assert "- 상세 화면 [design] 상세 화면을 그린다" in lines
    assert "counts: n_decide=1 n_todo=0 n_notify=2 n_unverified=0 n_children=2" in lines
    assert "알림 조건: 미충족(design는 알림으로 지나가지 않는다)" in lines


def test_s02_screen_notify_condition_for_code_task(run_dir):
    run_dir.task("T001", "목록 구현", kind="implementation", block="구현", status="자체검증")
    run_dir.result("T001", screen_result("T001", notify="- 정렬 함수 이름을 바꿨다"))
    run_dir.judge("T001", JUDGE_OK)

    r = run_script("screen", run_dir, "T001")

    assert r.returncode == 0, r.output
    assert "counts: n_decide=0 n_todo=0 n_notify=1 n_unverified=0 n_children=0" in r.stdout
    assert ("알림 조건(정해 주실 것·하실 일이 비고 통과 못 한 기준·판정불가 없음, 형식 문제 없음): 충족 — "
            "알림 줄에 붙일 것: 알릴 것 1, 확인 안 된 것 0") in r.stdout


# --- 3 ---------------------------------------------------------------------------------------------------------

def test_s03_spawn_children_dry_run_then_real_turns_sibling_title_into_id(run_dir):
    run_dir.task("T001", "화면 설계", status="완료")
    run_dir.result("T001", screen_result("T001", children=children_section(
        child_row("목록 화면"), child_row("상세 화면", depends="목록 화면"))))

    dry = run_script("spawn_children", run_dir, "T001", "--dry-run", "--now", "2026-10-15 11:00:00")

    assert dry.returncode == 0, dry.output
    assert "T002 목록 화면 [design] 흐름=- 의존=- (dry-run)" in dry.stdout
    assert "T003 상세 화면 [design] 흐름=- 의존=T002 (dry-run)" in dry.stdout
    assert sorted(os.listdir(run_dir.path / "tasks")) == ["T001"]

    real = run_script("spawn_children", run_dir, "T001", "--now", "2026-10-15 11:00:00")

    assert real.returncode == 0, real.output
    tasks = run_dir.tasks()
    assert sorted(tasks) == ["T001", "T002", "T003"]
    assert tasks["T002"]["title"] == "목록 화면" and tasks["T002"]["depends_on"] == []
    assert tasks["T003"]["title"] == "상세 화면"
    assert tasks["T003"]["depends_on"] == ["T002"]
    assert tasks["T003"]["parent"] == "T001" and tasks["T003"]["status"] == "대기"
    assert (run_dir.task_dir("T003") / "criteria.orig.md").read_text(encoding="utf-8") == "1. 상세 화면이 있다\n"


# --- 4 ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("touch, code, made", [
    (None, 3, ["T001"]),                       # 「건드릴 파일」을 뺀 코드 task 행 → 거부
    ("- src/list.py", 0, ["T001", "T002"]),    # 같은 행에 「건드릴 파일」이 있으면 만든다(대조)
], ids=["touch-missing", "touch-present"])
def test_s04_code_row_without_touch_files_exits_3_and_writes_no_header(run_dir, touch, code, made):
    run_dir.task("T001", "목록 설계", status="완료")
    run_dir.result("T001", screen_result("T001", children=children_section(
        child_row("목록 구현", kind="implementation", flow="list", touch=touch))))

    r = run_script("spawn_children", run_dir, "T001", "--now", "2026-10-15 11:00:00")

    assert r.returncode == code, r.output
    assert sorted(os.listdir(run_dir.path / "tasks")) == made
    if code == 3:
        assert "자식 목록의 형식 문제 1건. 머리 파일을 만들지 않았다." in r.stdout
        assert "- 「건드릴 파일」 없음(코드 task): 목록 구현" in r.stdout
        assert not (run_dir.path / "flows").exists()


# --- 5 ---------------------------------------------------------------------------------------------------------

def test_s05_second_code_row_in_same_flow_depends_on_first(run_dir):
    run_dir.task("T001", "목록 설계", status="완료")
    run_dir.result("T001", screen_result("T001", children=children_section(
        child_row("목록 구현", kind="implementation", flow="list", touch="- src/list.py"),
        child_row("목록 정렬", kind="implementation", flow="list", touch="- src/sort.py"),
        child_row("상세 구현", kind="implementation", flow="detail", touch="- src/detail.py"))))

    r = run_script("spawn_children", run_dir, "T001", "--now", "2026-10-15 11:00:00")

    assert r.returncode == 0, r.output
    tasks = run_dir.tasks()
    assert tasks["T002"]["depends_on"] == []
    assert tasks["T003"]["depends_on"] == ["T002"]     # 같은 흐름의 둘째는 첫째에 자동으로 의존
    assert tasks["T004"]["depends_on"] == []           # 다른 흐름의 행은 잇지 않는다(대조)
    assert "T003 목록 정렬 [implementation] 흐름=list 의존=T002" in r.stdout


# --- 6 ---------------------------------------------------------------------------------------------------------

def test_s06_queue_puts_blocking_approval_before_one_with_decision(run_dir):
    # T001: 정해 주실 것이 있고 먼저 요청됨. T002: 다른 task(T003)를 막음, 나중에 요청됨
    run_dir.task("T001", "배포 설계", status="승인대기", n_decide="2", approval_requested="2026-10-15 09:00:00")
    run_dir.task("T002", "화면 설계", status="승인대기", n_decide="0", approval_requested="2026-10-15 10:00:00")
    run_dir.task("T003", "목록 구현", kind="implementation", block="구현", depends_on=["T002"])

    r = run_script("board", run_dir, "--queue")

    assert r.returncode == 0, r.output
    lines = r.stdout.splitlines()
    assert lines[0] == "승인 대기 2개"
    assert lines[1] == "1. T002 화면 설계 (막고 있는 task 1개: T003, 정해 주실 것 0건, 요청 2026-10-15 10:00:00)"
    assert lines[2] == "2. T001 배포 설계 (막고 있는 task 0개, 정해 주실 것 2건, 요청 2026-10-15 09:00:00)"


# --- 7 ---------------------------------------------------------------------------------------------------------

def test_s07_resume_shows_liveness_check_last_write_and_stale_question(run_dir):
    run_dir.task("T001", "멈춘 구현", kind="implementation", block="구현", status="진행", running_agent="code-T001",
                 started="2026-10-15 08:00:00")
    run_dir.task("T002", "도는 구현", kind="implementation", block="구현", status="진행", running_agent="code-T002",
                 started="2026-10-15 08:00:00")
    stale = run_dir.result("T001", "# T001 결과\n")
    fresh = run_dir.result("T002", "# T002 결과\n")
    now = time.time()
    old = now - 2 * 60 * 60                        # 두 시간 전에 마지막으로 씀
    for p in (stale, run_dir.task_dir("T001") / "task.md"):
        os.utime(p, (old, old))
    os.utime(fresh, (now, now))
    os.utime(run_dir.task_dir("T002") / "task.md", (now - 60, now - 60))

    r = run_script("board", run_dir, "--resume")

    assert r.returncode == 0, r.output
    lines = {l.split(":", 1)[0]: l for l in r.stdout.splitlines() if l.startswith("- T")}
    stamp = datetime.fromtimestamp(old).strftime("%Y-%m-%d %H:%M:%S")
    assert "실행 중 에이전트 code-T001 (살아 있는지 확인. 결과 파일 마지막 수정 {} {})".format(
        stamp, os.path.join("tasks", "T001", "result.md")) in lines["- T001 멈춘 구현"]
    assert lines["- T001 멈춘 구현"].endswith("— 30분 넘게 멈춤: 에이전트 목록에 있어도 기다림 / 멈추고 이어 씀을 사용자에게 묻는다")
    assert "실행 중 에이전트 code-T002 (살아 있는지 확인. 결과 파일 마지막 수정 " in lines["- T002 도는 구현"]
    assert "30분 넘게 멈춤" not in lines["- T002 도는 구현"]   # 막 쓴 결과 파일이면 묻지 않는다(대조)


# --- 8 ---------------------------------------------------------------------------------------------------------

def test_s08_cycles_shows_loop_and_exits_3(run_dir):
    run_dir.task("T001", "목록 설계", depends_on=["T002"])
    run_dir.task("T002", "상세 설계", depends_on=["T001"])
    run_dir.task("T003", "배포 설계", depends_on=["T001"])

    r = run_script("board", run_dir, "--cycles")

    assert r.returncode == 3, r.output
    assert r.stdout.splitlines() == ["의존 고리 1개", "- T001 → T002 → T001"]


def test_s08_cycles_without_loop_exits_0(run_dir):
    run_dir.task("T001", "목록 설계")
    run_dir.task("T002", "상세 설계", depends_on=["T001"])

    r = run_script("board", run_dir, "--cycles")

    assert r.returncode == 0, r.output
    assert r.stdout.splitlines() == ["의존 고리 없음"]


# --- 9 ---------------------------------------------------------------------------------------------------------

def test_s09_backlog_lists_backlog_tasks_with_run_name(workspace):
    first = RunDir(workspace / "2026-10-01-first")
    first.task("T001", "목록 구현", kind="implementation", block="구현", status="완료")
    first.task("T002", "[백로그] 정렬 옵션", kind="implementation", block="구현", status="백로그")
    second = RunDir(workspace / "2026-10-02-second")
    second.task("T001", "상세 구현", kind="implementation", block="구현", status="대기")
    loose = workspace / "notes"                     # run.md가 없는 폴더는 실행이 아니다
    write(loose / "tasks" / "T001" / "task.md", "---\nid: T001\ntitle: 메모\nstatus: 백로그\n---\n")

    r = run_script("board", workspace, "--backlog")

    assert r.returncode == 0, r.output
    assert r.stdout.splitlines() == [
        "남은 백로그 1개",
        "- 2026-10-01-first / T002 [백로그] 정렬 옵션 [implementation] {}".format(first.task_dir("T002")),
    ]


# --- 10 --------------------------------------------------------------------------------------------------------

def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + GIT_ID + list(args), check=True, capture_output=True,
                          text=True, encoding="utf-8")


@pytest.fixture
def code_repo(tmp_path):
    repo = tmp_path / "code"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo / "src" / "app.py", "def app():\n    return 1\n")
    write(repo / "tests" / "test_app.py", "def test_app():\n    assert True\n")
    write(repo / "package.json", "{}\n")
    write(repo / "README.md", "앱\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


# 건너뜀 표시는 이 파일 자신의 diff가 그 검사에 걸리지 않게 나눠 적는다
SKIP_LINE = "@Dis" + "abled\n"


def edit_inside(repo):
    write(repo / "src" / "app.py", "def app():\n    return 2\n")
    write(repo / "src" / "new.py", "X = 1\n")


def edit_outside(repo):
    edit_inside(repo)
    write(repo / "README.md", "앱 설명\n")


def edit_config(repo):
    edit_inside(repo)
    write(repo / "package.json", "{\"name\": \"app\"}\n")


def edit_skip(repo):
    edit_inside(repo)
    with open(repo / "tests" / "test_app.py", "a", encoding="utf-8", newline="\n") as f:
        f.write(SKIP_LINE)


@pytest.mark.parametrize("edit, code, flag", [
    (edit_inside, 0, None),
    (edit_outside, 3, "- 대상 밖 파일 1개: README.md"),
    (edit_config, 3, "- 의존성·설정·마이그레이션 파일 1개: package.json"),
    (edit_skip, 3, "- 테스트 건너뜀 표시가 늘었다(+1 / -0)"),
], ids=["inside", "outside", "config", "skip-mark"])
def test_s10_machine_check_exit_code_by_change_kind(tmp_path, code_repo, edit, code, flag):
    run = RunDir(tmp_path / "run")
    head = run.task("T001", "앱 구현", kind="implementation", block="구현",
                    sections={"건드릴 파일": "- src/**\n- tests/**\n- package.json"})
    edit(code_repo)

    r = run_script("machine_check", code_repo, head)

    assert r.returncode == code, r.output
    lines = r.stdout.splitlines()
    if flag is None:
        assert lines[-1] == "기계 조건에 걸린 것 없음"
    else:
        assert "기계 조건에 걸림 1건 → 읽기 판정을 한다" in lines
        assert flag in lines


# --- 11 --------------------------------------------------------------------------------------------------------

def test_s11_conventions_collects_committed_code_tasks_only(run_dir):
    run_dir.task("T001", "목록 구현", kind="implementation", block="구현", flow="list", status="완료", commit="abc1234")
    run_dir.result("T001", screen_result("T001").replace("## 규약 추가\n없음\n", "## 규약 추가\n- 오류 코드 LIST_EMPTY\n"))
    run_dir.task("T002", "정렬 구현", kind="implementation", block="구현", flow="list", status="자체검증", commit="def5678")
    run_dir.result("T002", screen_result("T002").replace("## 규약 추가\n없음\n", "## 규약 추가\n- 함수 이름 sort_by_recent\n"))
    run_dir.task("T003", "필터 구현", kind="implementation", block="구현", flow="list", status="진행")
    run_dir.result("T003", screen_result("T003").replace("## 규약 추가\n없음\n", "## 규약 추가\n- 커밋 전 이름 FILTER_X\n"))
    run_dir.task("T004", "상세 구현", kind="implementation", block="구현", flow="detail", status="완료", commit="0a0b0c0")
    run_dir.result("T004", screen_result("T004").replace("## 규약 추가\n없음\n", "## 규약 추가\n- 다른 흐름 DETAIL_X\n"))
    run_dir.task("T005", "목록 설계", flow="list", status="완료")
    run_dir.result("T005", screen_result("T005").replace("## 규약 추가\n없음\n", "## 규약 추가\n- 설계 이름 DESIGN_X\n"))

    r = run_script("conventions", run_dir, "list")

    assert r.returncode == 0, r.output
    out = run_dir.path / "flows" / "list" / "conventions.md"
    assert "{} (task 2개의 규약)".format(out) in r.stdout
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# 흐름 규약: list\n")
    assert "## T001 목록 구현\n- 오류 코드 LIST_EMPTY\n" in text
    assert "## T002 정렬 구현\n- 함수 이름 sort_by_recent\n" in text
    for absent in ("FILTER_X", "DETAIL_X", "DESIGN_X"):
        assert absent not in text, absent


# --- 12 --------------------------------------------------------------------------------------------------------

def test_s12_apply_revision_waits_for_approval_then_moves_and_logs(run_dir):
    canon = write(run_dir.path / "design" / "list.md", "# 목록 설계\n\n정렬은 이름 순.\n\n## 변경 이력\n- T001 목록 설계\n")
    before = canon.read_bytes()
    run_dir.task("T002", "정렬 바꾸기", kind="change", block="설계", status="승인대기")
    write(run_dir.task_dir("T002") / "revised" / "design" / "list.md",
          "# 목록 설계\n\n정렬은 최근 순.\n\n## 변경 이력\n- T001 목록 설계\n")

    waiting = run_script("apply_revision", run_dir, "T002")

    assert waiting.returncode == 3, waiting.output
    assert "T002의 상태가 `완료`가 아니다(승인대기). 승인 뒤에 옮긴다." in waiting.stdout
    assert canon.read_bytes() == before

    run_dir.task("T002", "정렬 바꾸기", kind="change", block="설계", status="완료")
    done = run_script("apply_revision", run_dir, "T002")

    assert done.returncode == 0, done.output
    assert "옮긴 정본 1개" in done.stdout
    assert canon.read_text(encoding="utf-8") == (
        "# 목록 설계\n\n정렬은 최근 순.\n\n## 변경 이력\n- T001 목록 설계\n- T002 정렬 바꾸기\n")
