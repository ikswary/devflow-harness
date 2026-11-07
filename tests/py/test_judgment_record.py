"""1.2.0 A3: 코드 판단 기록(설계 6.12절, 11.1절).

- 1.2.0부터 시작한 코드 task는 결과 파일 「판단」과 판정 파일 「판단 대조」를 쓰고, 읽기 판정을 늘 받는다.
- 시작할 때 「정본의 절」 사본과 해시를 떠서 판정자가 그 시점의 설계로 대조한다.
- 옛 판본으로 시작한 task는 지금 규칙 그대로다.
"""
import hashlib
import re
from datetime import datetime
from pathlib import Path

import pytest

import devflow_lib as lib
import kinds
import screen
import task_set
from conftest import run_script, write
from test_domain_paths import READ_JUDGE
from test_review_contract import NEW, OLD, code_task

ROOT = Path(__file__).resolve().parents[2]
CODE_KINDS = ("implementation", "fe-implementation", "be-implementation", "fix")


def set_judgment(run_dir, body, tid="T001"):
    path = run_dir.task_dir(tid) / "result.md"
    text = path.read_text(encoding="utf-8").split("## 판단")[0]
    path.write_text(text + ("## 판단\n{}\n".format(body) if body is not None else ""), encoding="utf-8")


def problems(run_dir):
    return lib.judgment_problems(run_dir.tasks()["T001"])


def test_kinds_and_doc_agree():
    doc = (ROOT / "references" / "practices" / "code-judgment.md").read_text(encoding="utf-8")
    assert set(re.findall(r"^\| `([^`]+)` \|", doc, re.M)) == set(kinds.JUDGMENT_KINDS)
    for kind in ("implementation", "fe-implementation", "be-implementation"):
        text = (ROOT / "references" / "kinds" / (kind + ".md")).read_text(encoding="utf-8")
        assert text.count("code-judgment.md") == 2


@pytest.mark.parametrize("kind", CODE_KINDS)
def test_new_code_task_always_needs_read_judge(run_dir, kind):
    run_dir.task("T001", "구현", kind=kind, block="구현", status="자체검증", flow="a", **NEW)
    assert lib.required_judges(run_dir.tasks()["T001"]) >= {"read", "run"}


def test_old_implementation_keeps_the_condition(run_dir):
    run_dir.task("T001", "구현", kind="implementation", block="구현", status="자체검증", flow="a", **OLD)
    assert "read" not in lib.required_judges(run_dir.tasks()["T001"])


@pytest.mark.parametrize("body", [
    "- 없음", "- 없음 (설계대로 함)", "- 공용 도우미를 새로 뺐다 [종류: 구조] [위치: src/a.ts:12]",
    "- 재시도 3회 [종류: 외부호출] [위치: src/a.ts:12] [따름: src/b.ts:3]\n  이유는 하위 줄로 쓴다",
    "- 저장 위치 [설계: 3절 저장]", "- 정렬 기준 [설계: 답 2026-11-05 10:00:00]",
    "- 라우트 분리 [종류: 구조] [위치: src/app/[id]/page.tsx:12]", "- 라우트 [종류: 구조] [위치: src/[...slug].tsx:3] [따름: src/[a]/b.tsx:9]",
    "- 백틱 [종류: 오류] [위치: `src/a.ts:12`]", "- 구간 [종류: 데이터] [위치: src/a.ts:12-20]",
])
def test_readable_judgments_pass(run_dir, body):
    code_task(run_dir)
    set_judgment(run_dir, body)
    assert problems(run_dir) == []


@pytest.mark.parametrize("body", [
    "- 도우미를 뺐다", "- 도우미 [종류: 이름] [위치: src/a.ts:12]", "- 도우미 [종류: 구조]", "- 도우미 [종류: 구조] [위치: src/a.ts]",
    "1. 도우미 [종류: 구조] [위치: src/a.ts:12]", "- 도우미 [종류: 구조] [위치: src/a.ts:abc]", "- 빈 값 [설계:]",
    "- 둘 다 [종류: 구조] [설계: 3절]", "- 따름 [종류: 구조] [위치: a.ts:1] [따름: b.ts]", "- 둘 [종류: 구조] [위치: a.ts:1, b.ts:2]",
    "- 두 번 [종류: 구조] [위치: a.ts:1] [위치: b.ts:2]", "- 앞 줄 [설계: 3절]\n  - 들여 쓴 판단 [종류: 구조] [위치: a.ts:1]", "- 없음. 그런데 도우미를 뺐다",
])
def test_unreadable_judgments_are_reported(run_dir, body):
    code_task(run_dir)
    set_judgment(run_dir, body)
    assert "꼴" in problems(run_dir)[0]


@pytest.mark.parametrize("body", [None, ""])
def test_missing_section_blocks_notify(run_dir, body):
    code_task(run_dir)
    assert screen.notify_status(str(run_dir.path), "T001")[0] is True
    set_judgment(run_dir, body)
    assert problems(run_dir) == ["「판단」 절 없음"]
    assert screen.notify_status(str(run_dir.path), "T001")[0] is False
    assert "! 판단 기록" in run_script("screen", run_dir.path, "T001").stdout


@pytest.mark.parametrize("kind", CODE_KINDS)
def test_every_code_kind_writes_the_record(run_dir, kind):
    run_dir.task("T001", "구현", kind=kind, block="구현", status="진행", flow="a", **NEW)
    run_dir.result("T001", "# 결과\n")
    assert problems(run_dir) == ["「판단」 절 없음"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T001", READ_JUDGE.format(now=now).split("## 판단 대조")[0])
    assert "판단 대조" in lib.judges_present(run_dir.tasks()["T001"])[1]


@pytest.mark.parametrize("kind", ("design", "merge"))
def test_other_kinds_write_no_record(run_dir, kind):
    run_dir.task("T001", "다른 것", kind=kind, block="설계", status="진행", **NEW)
    run_dir.result("T001", "# 결과\n")
    assert problems(run_dir) == []


def test_bad_record_is_sent_back_before_any_judge_runs(run_dir):
    run_dir.task("T001", "구현", kind="implementation", block="구현", status="진행", flow="a", **NEW)
    run_dir.result("T001", "# 결과\n\n## 판단\n- 도우미를 뺐다\n")
    p = run_script("task_set", run_dir.path, "T001", "--status", "자체검증")
    assert p.returncode == 3 and "판단 기록" in p.output
    assert run_dir.tasks()["T001"]["status"] == "진행"
    set_judgment(run_dir, "- 없음")
    assert run_script("task_set", run_dir.path, "T001", "--status", "자체검증").returncode == 0


def test_old_task_needs_no_record(run_dir):
    code_task(run_dir, meta=OLD)
    set_judgment(run_dir, None)
    assert problems(run_dir) == []
    assert "! 판단 기록" not in run_script("screen", run_dir.path, "T001").stdout


def test_judge_must_write_the_comparison_section(run_dir):
    code_task(run_dir)
    assert lib.judges_present(run_dir.tasks()["T001"])[0] is True
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T001", READ_JUDGE.format(now=now).split("## 판단 대조")[0])
    ok, why = lib.judges_present(run_dir.tasks()["T001"])
    assert ok is False and "판단 대조" in why


def test_old_judge_needs_no_comparison_section(run_dir):
    code_task(run_dir, meta=OLD)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T001", READ_JUDGE.format(now=now).split("## 판단 대조")[0])
    assert lib.judges_present(run_dir.tasks()["T001"])[0] is True


def start(run_dir, sections, kind="implementation", meta=NEW):
    run_dir.task("T001", "구현", {"정본의 절": sections}, kind=kind, block="구현", status="대기", flow="a", **meta)
    p = run_script("task_set", run_dir.path, "T001", "--status", "진행")
    assert p.returncode == 0, p.output
    return run_dir.task_dir("T001") / lib.DESIGN_COPY


def test_start_copies_the_canon_with_hash(run_dir):
    write(run_dir.path / "design" / "a.md", "# 설계\n결정 1\n")
    copy = start(run_dir, "design/a.md 3절, spec\\b.md, design/a.md")
    assert (copy / "design" / "a.md").read_text(encoding="utf-8") == "# 설계\n결정 1\n"
    digest = hashlib.sha256((run_dir.path / "design" / "a.md").read_bytes()).hexdigest()
    assert (copy / "hashes.md").read_text(encoding="utf-8").splitlines() == [digest + " design/a.md", "없음 spec/b.md"]


def test_copy_keeps_the_first_version_when_restarted(run_dir):
    write(run_dir.path / "design" / "a.md", "처음\n")
    copy = start(run_dir, "design/a.md")
    write(run_dir.path / "design" / "a.md", "뒤에 고침\n")
    lib.copy_canon_sections(str(run_dir.path), str(run_dir.task_dir("T001")), "design/a.md")
    assert (copy / "design" / "a.md").read_text(encoding="utf-8") == "처음\n"


def test_copy_refuses_paths_outside_the_run(run_dir):
    write(run_dir.path.parent / "secret.md", "밖\n")
    copy = start(run_dir, "design/../../secret.md")
    assert (copy / "hashes.md").read_text(encoding="utf-8").startswith("없음 ")
    assert not (copy / "secret.md").exists()


def test_no_section_still_marks_the_copy(run_dir):
    assert (start(run_dir, "(없음)") / "hashes.md").read_text(encoding="utf-8") == "(정본의 절 없음)\n"


@pytest.mark.parametrize("kind", CODE_KINDS)
def test_every_code_kind_copies_on_a_real_first_start(run_dir, monkeypatch, kind):
    # 실제 첫 시작은 머리 파일에 판본이 없고, 이 전이에서 지금 판본을 적는다
    write(run_dir.path / "design" / "a.md", "결정\n")
    run_dir.task("T001", "구현", {"정본의 절": "design/a.md."}, kind=kind, block="구현", status="대기", flow="a")
    monkeypatch.setattr(lib, "harness_version", lambda *a: "1.2.0-dev.1")
    assert task_set.main(["task_set.py", str(run_dir.path), "T001", "--status", "진행"]) == 0
    assert (run_dir.task_dir("T001") / lib.DESIGN_COPY / "design" / "a.md").read_text(encoding="utf-8") == "결정\n"


def test_copy_failure_does_not_stop_the_start(run_dir, monkeypatch, capsys):
    run_dir.task("T001", "구현", {"정본의 절": "design/a.md"}, kind="implementation", block="구현", status="대기", flow="a", **NEW)

    def broken(*a):
        raise OSError("디스크 없음")
    monkeypatch.setattr(lib, "copy_canon_sections", broken)
    assert task_set.main(["task_set.py", str(run_dir.path), "T001", "--status", "진행"]) == 0
    assert "! 설계 사본을 뜨지 못함: 디스크 없음" in capsys.readouterr().out
    assert run_dir.tasks()["T001"]["status"] == "진행"


def test_old_or_other_kind_makes_no_copy(run_dir):
    assert not start(run_dir, "design/a.md", meta=OLD).exists()


def test_design_kind_makes_no_copy(run_dir):
    assert not start(run_dir, "design/a.md", kind="design").exists()


def test_documented_baseline_lines_are_what_the_screen_reads():
    doc = (ROOT / "references" / "formats" / "judge-run-file.md").read_text(encoding="utf-8")
    block = doc.split("## 기준선 측정")[1].split("```")[1]
    rows = [line for line in block.splitlines() if line.startswith("- ") and not line.startswith("- 돌지 못함:")]
    assert len(rows) == 1 and screen.baseline_row(rows[0])["closes"] == "AC-22"
    assert "- 돌지 못함:" in block
    assert "judge-run-file" in (ROOT / "agents" / "run-judge.md").read_text(encoding="utf-8")


def test_judge_definitions_carry_the_new_version():
    assert lib.agent_def_problems() == []
    assert kinds.DEF_VERSION_MIN == "2026-11-07-a15"
