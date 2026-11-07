"""A13 재확인의 재현: 절차대로 고른 선택지가 거짓 경고가 되는 길(답을 여러 줄로 적음, 문장을 감싸 씀). 실제 전이를 돌린다."""
import time

import pytest

import project_docs
from conftest import run_script, write
from test_project_docs import BRIEF, NEW, _project, insert, review, started, wrap  # noqa: F401

DOC = "docs/product/brief.md"
SAME = "승인한 그대로: " + DOC
AFTER = "승인 화면 뒤 달라짐: " + DOC
EDIT = BRIEF.replace("하루 한 번", "하루 두 번")
WRONG = BRIEF.replace("하루 한 번", "하루 아홉 번")
JUDGE = "판정자: rjudge-T010 2026-11-06 10:00:00\n# T010 판정\n\n## 통과 못 한 기준\n- 없음\n"
TWO_LINES = ["정해 주실 것 정책|(가) 하루 두 번|(가) 하루 두 번 (Recommended)", "승인|승인|승인"]


def res(body):
    return "# 결과\n\n## 승인 화면\n### 정해 주실 것\n" + body


OPT = res("- 정책: 몇 번 돌릴지\n  - 선택지 (가)의 문장: 하루 두 번\n  - 선택지 (나)의 문장: 하루 아홉 번\n")
TWO_ITEMS = res("- 정책\n  - 선택지 (가)의 문장: 하루 두 번\n  - 선택지 (나)의 문장: 하루 아홉 번\n"
                "- 범위\n  - 선택지 (가)의 문장: 전체\n  - 선택지 (나)의 문장: 일부\n")


def asked(run_dir, project, result):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="자체검증", **NEW)
    run_dir.result("T010", result)
    run_dir.judge("T010", JUDGE)
    out = run_script("task_set", run_dir, "T010", "--status", "승인대기")
    assert out.returncode == 0, out.output


def answered(run_dir, project, after, records):
    write(run_dir.path / "spec" / "brief.md", after)
    for record in records[:-1]:
        out = run_script("task_set", run_dir, "T010", "--record", record)
        assert out.returncode == 0, out.output
    out = run_script("task_set", run_dir, "T010", "--status", "완료", "--record", records[-1])
    assert out.returncode == 0, out.output
    wrap(run_dir)
    insert(run_dir, project)
    return review(run_dir)


# ---------------------------------------------------------------- N-C1 그 승인 차례의 답 줄 전부


def test_choice_line_then_approval_line_explains_the_edit(run_dir, project):
    asked(run_dir, project, OPT)
    joined = answered(run_dir, project, EDIT, TWO_LINES)
    assert SAME in joined and "달라짐" not in joined


def test_choice_line_then_approval_line_does_not_explain_another_option(run_dir, project):
    asked(run_dir, project, OPT)
    joined = answered(run_dir, project, WRONG, TWO_LINES)
    assert AFTER in joined and "승인한 그대로" not in joined


def test_prior_line_chosen_on_an_earlier_line_is_stamped(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    project_docs.stamp_file(str(run_dir.path), "spec\\brief.md", "T001")
    write(run_dir.path / "design" / "feat.md", "# 설계\n")
    prior = "- 정책\n  - 선택지 (가)의 앞 정본 줄: spec/brief.md:3 | 지금: 하루 한 번 | 바뀜: 하루 두 번\n"
    run_dir.task("T020", "설계", {"건드릴 파일": "- design/feat.md"}, kind="design", block="설계", status="자체검증", **NEW)
    run_dir.result("T020", res(prior))
    run_dir.judge("T020", JUDGE.replace("T010", "T020"))
    assert run_script("task_set", run_dir, "T020", "--status", "승인대기").returncode == 0
    write(run_dir.path / "spec" / "brief.md", EDIT)
    assert run_script("task_set", run_dir, "T020", "--record", TWO_LINES[0]).returncode == 0
    assert run_script("task_set", run_dir, "T020", "--status", "완료", "--record", TWO_LINES[1]).returncode == 0
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["task"] == "T020"


def test_answers_before_this_question_do_not_count(run_dir, project):
    """앞 물음의 답이 끼면 고르지 않은 선택지가 설명이 된다."""
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="자체검증", **NEW)
    run_dir.result("T010", OPT)
    run_dir.judge("T010", JUDGE)
    assert run_script("task_set", run_dir, "T010", "--record", "정해 주실 것 정책|(나)|(나)로 하세요").returncode == 0
    time.sleep(1.1)
    assert run_script("task_set", run_dir, "T010", "--status", "승인대기").returncode == 0
    joined = answered(run_dir, project, WRONG, ["승인|승인|승인"])
    assert AFTER in joined


def test_later_answer_replaces_the_earlier_one_for_that_item(run_dir, project):
    asked(run_dir, project, OPT)
    joined = answered(run_dir, project, EDIT, ["정해 주실 것 정책|(나)|(나)로", "정해 주실 것 정책|(가)|아니 (가)로", "승인|승인|승인"])
    assert SAME in joined
    # 앞서 고른 (나)는 근거에서 빠진다
    assert project_docs.stamps(str(run_dir.path))["spec\\brief.md"]["via"] == ""


def test_check_and_question_lines_do_not_choose(run_dir, project):
    asked(run_dir, project, OPT)
    joined = answered(run_dir, project, EDIT, ["점검 확인|R3|(가) 말고요", "되물음(이해)|되물음|(가)가 뭐죠", "승인|승인|승인"])
    assert AFTER in joined


def test_several_items_on_one_line_are_read(run_dir, project):
    asked(run_dir, project, TWO_ITEMS)
    joined = answered(run_dir, project, EDIT, ["승인|승인: 정책 (가), 범위 (나)|정책 (가), 범위 (나)"])
    assert SAME in joined and "달라짐" not in joined


def test_several_items_do_not_mix_their_sentences(run_dir, project):
    asked(run_dir, project, TWO_ITEMS)
    joined = answered(run_dir, project, WRONG, ["승인|승인: 정책 (가), 범위 (나)|정책 (가), 범위 (나)"])
    assert AFTER in joined


def test_two_labels_without_item_names_stay_unread(run_dir, project):
    asked(run_dir, project, OPT)
    assert AFTER in answered(run_dir, project, EDIT, ["승인|승인|(가)와 (나) 둘 다"])


def test_same_label_for_every_item(run_dir, project):
    asked(run_dir, project, TWO_ITEMS)
    assert SAME in answered(run_dir, project, EDIT, ["승인|승인|둘 다 (가)"])


def test_judge_alternative_named_on_an_earlier_line(run_dir, project):
    started(run_dir, project)
    write(run_dir.path / "spec" / "brief.md", BRIEF)
    run_dir.task("T010", "기획", {"건드릴 파일": "- spec/brief.md"}, kind="brief", block="요구사항", status="자체검증", **NEW)
    run_dir.result("T010", res("- 없음\n"))
    run_dir.judge("T010", JUDGE + '\n## 권장\n- 대안 문장: "하루 두 번" 뜻 바뀜: 있음\n')
    assert run_script("task_set", run_dir, "T010", "--status", "승인대기").returncode == 0
    assert SAME in answered(run_dir, project, EDIT, ["정해 주실 것 Q1|판정자 대안|판정자 대안 문장으로", "승인|승인|승인"])


# ---------------------------------------------------------------- N-C2 감싼 문장


@pytest.mark.parametrize("written", [
    '선택지 (가)의 문장: "하루 두 번"',
    "선택지 (가)의 문장: `하루 두 번`",
    "선택지 (가)의 문장: “하루 두 번”",
    '선택지 (가)의 문장(`spec/brief.md:3`): "하루 두 번"',
    "선택지 (가)의 문장(spec/brief.md:3): `하루 두 번`",
    '선택지 (가)의 문장: "하루 두 번" (spec/brief.md:3)',
    "선택지 (가)의 문장: 하루 두 번 (`spec/brief.md:3`)",
])
def test_wrapped_sentence_explains(run_dir, project, written):
    asked(run_dir, project, res("- 정책\n  - " + written + "\n  - 선택지 (나)의 문장: 하루 아홉 번\n"))
    joined = answered(run_dir, project, EDIT, ["승인|승인|(가)로 하세요"])
    assert SAME in joined and "달라짐" not in joined


@pytest.mark.parametrize("written,after", [
    ('"하루 두 번" 정도', EDIT),                                  # 문장 뒤에 글이 더 있다
    ("하루 `두` 번", EDIT),                                        # 본문 안의 글자는 건드리지 않는다
    ("하루 두 번 (아침)", EDIT),                                   # 위치 꼴이 아닌 괄호
    ("하루 두 번", BRIEF.replace("하루 한 번", "`하루 두 번` 더")),
    ("한도 50건", BRIEF.replace("하루 한 번", '"한도 5"')),         # 감싼 부분 문자열은 여전히 설명이 아니다
])
def test_whole_line_match_still_holds(run_dir, project, written, after):
    asked(run_dir, project, res("- 정책\n  - 선택지 (가)의 문장: " + written + "\n"))
    assert AFTER in answered(run_dir, project, after, ["승인|승인|(가)로 하세요"])


def test_quote_on_one_side_is_not_stripped():
    assert project_docs._body('"하루 두 번') == '"하루 두 번'
