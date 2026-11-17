"""「통과 못 한 기준」 항목 번호 파서(설계 harness-tests 4.4절, 결정 D8·D18).

- `devflow_lib.item_key`가 항목 머리에서만 번호를 읽는다. 꼴 표(`ITEM_HEADS`)의 줄마다 표본 하나 이상. 표본은 다른 프로젝트
  실행 폴더의 판정 파일을 읽기만 하고 꼴만 본떠 지었다(실제 문장을 옮기지 않음, T001 답 3가).
- `task_set.failed_numbers`(「재시도 범위」)와 `screen.item_key`(main-run.md 해결 열쇠·대상 블록 열쇠)가 같은 머리를 같게 읽는다.
- 판정 표 첫 칸은 항목 머리가 아니라 기준 칸이라 `screen.cell_key`가 지금(6e08abb) 동작 그대로 읽는다.
"""
import pytest

import devflow_lib as lib
import screen
import task_set
from conftest import run_script, write

# 꼴 표의 줄 → (표본 머리들, item_key 결과). 표의 「결과」 칸 그대로
HEAD_TABLE = [
    ("- 기준 3: …, - 기준 3. …, - 기준 3) …, - 기준 3： …",
     ["- 기준 3: 인용한 줄이 원천에 없다", "- 기준 3. 인용한 줄이 원천에 없다",
      "- 기준 3) 인용한 줄이 원천에 없다", "- 기준 3： 인용한 줄이 원천에 없다", "- 기준 3 : 칸 앞에 공백"],
     ("기준", [3])),
    ("- 기준 3(…, - 기준 3 (…, - 기준 3 「…",
     ["- 기준 3(인용 실재): 줄 번호가 다르다", "- 기준 3 (시험 계층): 판정불가 환경: 잠금 사용 중",
      "- 기준 3 「판정 기준」의 관찰 방법이 없다"],
     ("기준", [3])),
    ("- 기준 8-10: …, - 기준 8~10 …",
     ["- 기준 8-10: 자식 행 셋이 같은 결함", "- 기준 8~10 자식 행 셋이 같은 결함"],
     ("기준", [8, 9, 10])),
    ("- 머리 기준 2 …, - 판정 기준 2 …",
     ["- 머리 기준 2 「영향받는 task」의 행이 비었다", "- 판정 기준 2 관찰 방법이 판정 때 없는 경로다"],
     ("기준", [2])),
    ("- 3. …, - 3) …",
     ["- 3. 인용한 줄이 원천에 없다", "- 3) 인용한 줄이 원천에 없다"],
     ("기준", [3])),
    ("- 변이 1: …",
     ["- 변이 1: 판정불가 환경: 기준 3의 명령이 잠금 사용 중"],
     ("변이", [1])),
    ("`기준` 뒤가 숫자가 아님, - AC-V-3: …, - 블록 기준 4(…), - T012 판정 기준 5(…), 그 밖",
     ["- 기준 성질(writer 2절): 선택지에 위험이 없다. 기준 3과도 닿는다", "- AC-V-3: 확인 안 됨",
      "- 블록 기준 4(자식 행): 범위가 겹친다", "- T012 판정 기준 5(인용): 줄 번호가 다르다",
      "- 새 실패 하나", "- 기준 x 실패", "- 자체 검증 2(인수 기준): 빠졌다", "- 3.5초가 걸려 기준 2를 넘는다",
      "- 기준 10-8: 거꾸로 쓴 범위", "- 변이 1~3: 판정불가 환경: 잠금 사용 중"],
     None),
]

HEAD_CASES = [(row, line, want) for row, lines, want in HEAD_TABLE for line in lines]
CRITERION_HEADS = [(row, line, want) for row, line, want in HEAD_CASES if want and want[0] == "기준"]


def failed_of(tmp_path, *items):
    p = tmp_path / "judge.md"
    write(p, "판정자: rjudge-T001 2026-11-17 10:00:00\n\n## 통과 못 한 기준\n" + "".join(x + "\n" for x in items) + "\n## 권장\n- 없음\n")
    return task_set.failed_numbers([str(p)])


@pytest.mark.parametrize("row,line,want", HEAD_CASES, ids=[c[1][:24] for c in HEAD_CASES])
def test_item_key_follows_the_head_table(row, line, want):
    assert lib.item_key(line) == want, row


def test_every_table_row_has_a_sample_and_the_table_names_six_heads():
    assert all(lines for _, lines, _ in HEAD_TABLE)
    names = [name for name, _ in lib.ITEM_HEADS]
    assert len(names) == 6 and len(set(names)) == 6
    assert [n for n in names if n.startswith("변이")] == ["변이 번호"]


def test_item_key_reads_only_the_first_line():
    assert lib.item_key("- 기준 성질(writer 2절): 위험이 없다\n  - 기준 3: 들여쓴 줄") is None
    assert lib.item_key("  - 기준 4: 들여쓴 머리\n  기준 7의 설명") == ("기준", [4])


# ---------------------------------------------------------------- 재시도 범위(failed_numbers)

def test_failed_numbers_reads_the_own_number_not_the_description(tmp_path):
    assert failed_of(tmp_path, "- 기준 6: 행이 어긋남. 탐침 정의의 기준 2(probe.md:45)를 통과할 수 없다") == ([6], [])


def test_failed_numbers_named_criterion_is_an_item_without_number(tmp_path):
    line = "- 기준 성질(writer 2절): 선택지에 위험이 없다. 머리 기준 3과도 닿는다"
    assert failed_of(tmp_path, line) == ([], [line[2:]])


def test_failed_numbers_range(tmp_path):
    assert failed_of(tmp_path, "- 기준 8-10: 자식 행 셋이 같은 결함") == ([8, 9, 10], [])


def test_failed_numbers_mutation_is_an_item_without_number(tmp_path):
    line = "- 변이 1: 판정불가 환경: 기준 3의 명령이 잠금 사용 중"
    assert failed_of(tmp_path, line) == ([], [line[2:]])


@pytest.mark.parametrize("row,line,want", CRITERION_HEADS, ids=[c[1][:24] for c in CRITERION_HEADS])
def test_screen_and_retry_scope_read_the_same_first_number(tmp_path, row, line, want):
    nums, loose = failed_of(tmp_path, line)
    assert nums == want[1] and loose == []
    assert screen.item_key(line) == "기준{}".format(nums[0])


def test_archive_judge_writes_head_numbers_to_retry_scope(run_dir):
    """명령행 한 사례: `--archive-judge`의 「재시도 범위」가 머리 번호만 고칠 기준으로 적고 나머지는 번호 없는 항목으로 둔다."""
    run_dir.task("T001", "설계", kind="design", block="설계", status="자체검증", started_version="1.2.1", rules="2")
    run_dir.result("T001", "# 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n")
    run_dir.judge("T001", "판정자: rjudge-T001 2026-11-17 10:00:00\n\n## 통과 못 한 기준\n"
                  "- 기준 6: 행이 어긋남. 탐침 정의의 기준 2(probe.md:45)를 통과할 수 없다\n"
                  "- 기준 8-10: 자식 행 셋이 같은 결함\n"
                  "- 변이 1: 판정불가 환경: 기준 3의 명령이 잠금 사용 중\n")
    r = run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge")
    assert r.returncode == 0, r.output
    text = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    scope = text.split("## 재시도 범위\n", 1)[1].split("\n## ", 1)[0]
    assert "고칠 기준: 6, 8, 9, 10." in scope
    assert "  - 번호 없는 항목: 변이 1: 판정불가 환경: 기준 3의 명령이 잠금 사용 중" in scope.splitlines()


# ---------------------------------------------------------------- 화면(screen)

def test_unresolved_failed_keys_a_mutation_item_by_its_head(tmp_path):
    """머리가 `- 변이 1:`이고 설명에 `기준 3`이 든 판정불가 항목의 열쇠는 `변이1`이다."""
    item = "- 변이 1: 판정불가 환경: 기준 3의 명령이 잠금 사용 중\n"
    kept, dropped = screen.unresolved_failed(item, {"변이1"})
    assert dropped == 1 and kept == ""
    kept, dropped = screen.unresolved_failed(item, {"기준3"})
    assert dropped == 0 and kept == item.strip()


def test_unresolved_failed_reads_only_the_first_line_of_an_item():
    """6e08abb는 항목 글 전체에서 처음 나온 `기준 n`을 열쇠로 써서 아래 두 항목을 `기준3`으로 풀었다."""
    item = "- 기준 성질(writer 2절): 판정불가 환경: 잠금 사용 중\n  - 기준 3: 들여쓴 설명\n"
    assert screen.unresolved_failed(item, {"기준3"})[1] == 0
    assert screen.unresolved_failed("- 기준 성질(writer 2절): 판정불가 환경: 기준 3의 명령이 잠금 사용 중\n", {"기준3"})[1] == 0
    assert screen.unresolved_failed("- 기준 3: 판정불가 환경: 잠금 사용 중\n", {"기준3"})[1] == 1


@pytest.mark.parametrize("cell,want", [("3", "기준3"), ("기준 3", "기준3"), ("기준 3 (인용 실재)", "기준3"),
                                       ("변이 1", "변이1"), ("기준 성질", None)])
def test_cell_key_keeps_the_table_cell_reading(cell, want):
    assert screen.cell_key(cell) == want


TARGET_TABLE = ("| 기준 | 판정 | 근거 |\n|---|---|---|\n"
                "| 기준 성질 | 판정불가 | 대상: 실제 메일함은 사람만 본다 |\n"
                "| 2 | 판정불가 | 대상: 실제 경로 없음 |\n"
                "| 변이 1 | 판정불가 | 대상: 잠금 사용 중 |\n")


def test_table_targets_lines_match_6e08abb():
    """6e08abb의 screen.table_targets가 같은 표에서 낸 줄(그 커밋의 함수를 돌려 받은 값)."""
    assert screen.table_targets(TARGET_TABLE, set()) == [
        "- [판정불가 대상] 기준  성질: 대상: 실제 메일함은 사람만 본다(판정 표)",
        "- [판정불가 대상] 기준 2: 대상: 실제 경로 없음(판정 표)",
        "- [판정불가 대상] 변이 1: 대상: 잠금 사용 중(판정 표)",
    ]
    assert screen.table_targets(TARGET_TABLE, {"기준2", "변이1"}) == [
        "- [판정불가 대상] 기준  성질: 대상: 실제 메일함은 사람만 본다(판정 표)"]


def test_table_blocks_named_cell_has_no_key():
    """`기준 성질` 칸은 열쇠가 없어 main-run.md로 풀리지 않는다(지금 동작). 숫자 칸은 풀린다."""
    named = "| 기준 성질 | 판정불가 | 환경: 잠금 사용 중 |\n"
    assert screen.table_blocks(named, {"기준3"}) is True
    assert screen.table_blocks("| 3 | 판정불가 | 환경: 잠금 사용 중 |\n", {"기준3"}) is False
