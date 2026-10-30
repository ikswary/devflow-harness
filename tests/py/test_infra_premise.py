"""`board.py {실행 폴더} --infra-premise`(설계 domain 3.7, A-19): 상세 정본마다 「인프라 전제」의 `- 없음`이 아닌 줄,
절이 없는 정본의 `!` 줄, 끝 줄의 인프라 결정 task.

가짜 실행 폴더(`RunDir`)의 `spec\\*.md`로 명령행을 돌려 출력 줄로 가른다. `overview.md`·`brief.md`는 상세 정본이 아니라 보지 않는다.
"""
from conftest import run_script, write

SPECS = {
    "a.md": "# 묶음 a\n\n## 인수 기준\n- AC-01 저장한다\n\n## 인프라 전제\n- [Q3] 요금제 무료 한도 안에서 메일을 보낸다\n",
    "b.md": "# 묶음 b\n\n## 인수 기준\n- AC-02 읽는다\n\n## 인프라 전제\n- 없음\n",
    "c.md": "# 묶음 c\n\n## 인수 기준\n- AC-03 지운다\n",
    "overview.md": "# 개요\n\n## 묶음\n- a, b, c\n",
}


def premise(run_dir):
    for name, text in SPECS.items():
        write(run_dir.path / "spec" / name, text)
    return run_script("board", run_dir, "--infra-premise")


def test_infra_premise_collects_lines_and_flags_missing_section(run_dir):
    proc = premise(run_dir)
    assert proc.returncode == 0, proc.output
    lines = proc.stdout.splitlines()
    assert "a.md: - [Q3] 요금제 무료 한도 안에서 메일을 보낸다" in lines, proc.output
    assert "! c.md: 「인프라 전제」 절 없음" in lines, proc.output
    # `- 없음`인 정본과 개요 정본은 줄을 내지 않는다(양성 대조는 위 a.md 줄)
    assert not [line for line in lines if "b.md" in line or "overview.md" in line], proc.output
    assert lines[-1] == "인프라 결정 task: 없음", proc.output


def test_infra_premise_names_infra_design_task_with_status(run_dir):
    run_dir.task("T001", "질문", kind="question", block="질문", status="완료")
    run_dir.task("T007", "인프라 결정", kind="infra-design", block="설계", status="대기")
    proc = premise(run_dir)
    assert proc.returncode == 0, proc.output
    assert proc.stdout.splitlines()[-1] == "인프라 결정 task: T007 (대기)", proc.output
