"""1.2.0 A10 위임과 성질의 기계 끌어내기(설계 9절, 5.2절, 11.1절).

- 원문에서 층을 읽는다. 읽지 못하면 맡긴 것으로 보지 않고 되묻는다. 부정문은 맡기지 않은 것이다.
- 끌어낸 성질은 올리는 쪽으로만 틀린다.
- 위임으로 닫는 답은 관문을 지나야 적히고, 운영 명령은 실행 직전 확인을 받아야 돈다.
- 위임 안에서 실행이 멈추는 길이 없다(같은 원문, 되물음 두 번, 사람이 대신 답함).
"""
import os
import re
import shutil

import pytest

import delegation
import devflow_lib as lib
import exec as execmod
import screen
from conftest import run_script, write
from test_review_contract import NEW, judged, result

# ---------------------------------------------------------------- 층 읽기


@pytest.mark.parametrize("text,want", [
    # 실제 기록에서 쓰인 꼴과 설계안 예시
    ("ㅇㅋ dev 배포까지 진행", ("L2", "L3")),
    ("dev 배포까지 맡아", ("L2", "L3")),
    ("나머지 자동 승인", ("L1", "L2")),
    ("이번 실행 모두 자동승인", ("L1", "L2", "L3")),
    ("운영까지 전부 자동 승인", ("L1", "L2", "L3", "L4")),
    ("운영 빼고 전부 자동 승인", ("L1", "L2", "L3")),
    ("dev 배포까지 진행. 운영 배포는 이번 범위 밖", ("L2", "L3")),
    ("결정은 맡길게", ("L1",)),
    ("나머지는 추천대로 해", ("L1",)),
    ("나머지는 알아서 정해", ("L1",)),
    ("이번 실행은 추천대로 해", ("L1",)),
    ("결정은 내가 할게, dev 배포까지 맡아", ("L2", "L3")),
    ("커밋이랑 합치기는 맡아", ("L2",)),
    ("묻지 말고 전부 진행", ("L1", "L2", "L3")),
    ("L1~L3", ("L1", "L2", "L3")),
    ("L2~L4로 해", ("L2", "L3", "L4")),
    ("알아서 dev까지 해", ("L1", "L2", "L3")),
    ("전부 자동", ("L1", "L2", "L3")),
    ("나머지 자동", ("L1", "L2")),
    ("이후 전체", ("L1", "L2", "L3")),
    ("L4는 빼고 L1~L3", ("L1", "L2", "L3")),
])
def test_levels_are_read_from_real_wording(text, want):
    levels, why = delegation.read_levels(text)
    assert why == "" and levels == want


@pytest.mark.parametrize("text", [
    "알아서 해",                      # 무엇을 맡기는지 말하지 않았다
    "맡아",
    "그렇게 진행",
    "승인",
    "3 가",                           # 다른 답의 꼴
    "나머지 남김",
    "자동 승인해도 돼?",               # 물음
    "맡겨도 될까",
    "실패하면 묻고 나머지는 자동 승인",  # 조건
    "운영은 글쎄, dev까지 맡아",        # 운영을 맡겼는지 못 읽는다
    "",
])
def test_unreadable_wording_asks_again(text):
    levels, why = delegation.read_levels(text)
    assert levels is None and why


@pytest.mark.parametrize("text", ["자동 승인은 하지 마", "맡기지 마", "위임 안 해", "알아서 하지 마", "자동 승인 말고 하나씩 물어봐",
                                  "위임 안 함", "안 맡겨", "자동 승인 아니야", "자동 승인 그만"])
def test_negation_gives_nothing_and_takes_back_what_was_given(text):
    assert delegation.read_levels(text) == ((), "")
    assert delegation.read_levels(text, ("L1", "L2", "L3")) == ((), "")


def test_a_followup_only_narrows_or_adds_what_it_names():
    current = ("L1", "L2", "L3", "L4")
    assert delegation.read_levels("운영은 하지 마", current) == (("L1", "L2", "L3"), "")
    assert delegation.read_levels("아니 결정도 맡겨", ("L2", "L3")) == (("L1", "L2", "L3"), "")
    assert delegation.read_levels("dev까지만 맡아", current) == (("L2", "L3"), "")


# 리뷰가 재현한 원문. 어느 것도 `L3`, `L4`를 주면 안 된다(되묻거나 맡기지 않음이다)
NOT_GRANTING = [
    "그 라이브러리 니가 알아서 세팅하는걸로",
    "운영 전까지 자동 승인", "운영 불포함 전부 자동 승인", "운영 배포 전까지 맡아", "운영 직전까지 진행", "prod 전까지 맡아",
    "운영 미포함으로 진행", "운영 없이 dev까지", "운영까지 맡기긴 싫어", "운영까지 맡길 생각 없어", "운영까지 맡긴 적 없어",
    "운영까지 진행은 곤란해", "누가 운영까지 맡기래", "L4는 안돼",
    '"운영까지 맡아"라고 말한 건 예시야', '문서에 "전부 자동 승인"이라고 적혀 있던데', "ㄴㄴ 전부 자동승인",
    "자동 승인 안돼", "자동 승인 안해", "자동 승인 못해", "자동 승인 필요 없어", "자동 승인 X", "자동 승인 no",
    "결정은 맡기기 싫어", "dev까지 맡은 건 없어", "자동으로 시험 돌려줘", "라이브까지 맡아",
    "그 모듈까지 같이 병합해서 dev 배포", "자동승인 말고 전부 진행", "나머지 알아서 해",
]


# 끝말을 건너뛰던 입구(승인 없이, 묻지 말고, 이후 전체)와 한 화면의 답, 말이 모자란 꼴
NOT_GRANTING += [
    "승인 없이 운영 올리면 안 돼", "확인 없이 운영 건드리지 마", "묻지 말고 운영 돌리지는 마", "물어보지 말고 운영은 내가 볼 거야",
    "승인 없이 배포하면 안 됩니다", "이후 전체 자동 싫어", "승인 없이 진행하면 안 돼", "확인 없이 진행 금지", "확인 없이는 절대 안 돼", "묻지 말고 그냥 멈춰",
    "추천대로 해", "추천대로 진행", "알아서 정해", "알아서 골라", "결정해", "추천대로 알아서 정해",
    "운영까지 맡겨도 돼", "맡겨요", "자동 승인 해요", "아니요, 자동 승인", "아니요, 전부 자동 승인",
    "자동", "자동으로", "묻지 마", "승인 없이", "L4", "자동 승인",
    "운영만 맡아", "L4만", "dev만 맡아",
]


@pytest.mark.parametrize("text", NOT_GRANTING)
def test_review_wording_never_grants(text):
    levels, _ = delegation.read_levels(text)
    assert not levels, levels


@pytest.mark.parametrize("text", ["자동 승인 해제", "자동 승인 꺼줘", "위임 해제", "위임 풀어", "위임 철회", "자동 승인 끝", "자동 승인 멈춰", "자동 승인 그만"])
@pytest.mark.parametrize("current", [(), ("L1", "L2", "L3", "L4")])
def test_cancelling_words_clear_the_row(text, current):
    assert delegation.read_levels(text, current) == ((), "")


@pytest.mark.parametrize("text,want", [
    ("운영까지 맡아, 아니 dev까지만", ("L2", "L3")),
    ("운영까지 맡아, 아 잠깐 dev까지만 맡아", ("L2", "L3")),
])
def test_a_correction_reads_anew(text, want):
    assert delegation.read_levels(text) == (want, "")


def test_a_taken_level_is_not_given_back_by_the_cumulative_rule():
    levels, why = delegation.read_levels("dev는 맡기지 말고 운영까지 맡아")
    assert why == "" and levels == ("L2", "L4")


# 평소 답의 꼴(합성 문장). 위임의 말 셋만 층을 준다
ORDINARY_ANSWERS = [
    "(가) 문장 하나 고침 (Recommended)", "(나) 둘 다 미룸", "(다) 개발 뒤 운영도", "(다) 구현까지", "(가) dev에만 올림 (Recommended)",
    "승인", "승인 (Recommended)", "승인 + 문장 손봄 (Recommended)", "승인, 앞쪽에서 고침 (Recommended)", "승인하는데 할 일은 네가 해",
    "승인 + 그 설정값도 맡김", "보류", "그대로", "그대로 (Recommended)", "둘 다", "괜찮음", "받아들임 (Recommended)", "그대로 받아들임",
    "위험 받아들이고 승인", "백로그 유지 (Recommended)", "고칠 것이 있음", "왜 보류", "왜 그렇게 됐지", "이해가 안됨", "이거 너무 귀찮아",
    "아니 dev 배포 됐으면 됐어", "아니다 그냥 진행하자", "아니 이번 세션 끝나고 새로 띄울거야", "개발 병합 및 푸시, 그리고 배포까지 자동 실행",
    "기본(모두 묻기)", "dev 배포 뒤 확인", "dev 배포 끝난 뒤 지움 (Recommended)", "확실하게 배포", "병합과 push 모두 (Recommended)",
    "그 라이브러리 니가 알아서 세팅하는걸로", "내가 진행하는게 아니라 모드만 바꿔서 수행할거", "운영 배포는 사용자한테 다시 물어보는걸로",
    "제일 수정이 적은거", "지금 돌림 (Recommended)", "모두 통과", "확인 마침 (Recommended)", "새 실행 (Recommended)",
]


def test_ordinary_answers_do_not_delegate():
    granted = {text: delegation.read_levels(text)[0] for text in ORDINARY_ANSWERS if delegation.read_levels(text)[0]}
    assert granted == {}
    for text, want in (("나머지 자동 승인", ("L1", "L2")), ("이번 실행 모두 자동승인", ("L1", "L2", "L3")), ("ㅇㅋ dev 배포까지 진행", ("L2", "L3"))):
        assert delegation.read_levels(text) == (want, "")


def test_negated_target_alone_never_grants():
    assert delegation.read_levels("운영 배포는 하지 마") == ((), "")


@pytest.mark.parametrize("value,want", [
    ("L1~L3", ("L1", "L2", "L3")),
    ("L1 근거 없는 결정(추천안으로 정함), L2 로컬·통합 브랜치 명령", ("L1", "L2")),
    ("L1~L3 (L4 제외)", ("L1", "L2", "L3")),
    ("L1~L3, L4 제외", ("L1", "L2", "L3")),
    ("L4 빼고 L2~L3", ("L2", "L3")),
    ("없음 (L1 아님)", ()),
    ("L1 아님", ()),
    ("없음", ()),
])
def test_the_row_is_read_narrowly(run_dir, value, want):
    path = run_dir.path / "run.md"
    path.write_text(path.read_text(encoding="utf-8") + "| 위임 | {} |\n".format(value), encoding="utf-8")
    assert lib.delegation_levels(str(run_dir.path)) == want


# ---------------------------------------------------------------- 위임 문장과 적기


def deleg(run_dir, text):
    return run_script("screen", run_dir.path, "--delegate", text)


def confirm(run_dir, answer):
    return run_script("screen", run_dir.path, "--delegate-confirm", answer)


def granted(run_dir, text, answer="네"):
    """읽은 층을 보이고 사람이 확인한 뒤의 결과."""
    p = deleg(run_dir, text)
    assert p.returncode == 0 and "맞으면 ㅇ" in p.stdout, p.output
    return confirm(run_dir, answer)


def settings(run_dir, *lines):
    write(run_dir.path.parent / lib.PROJECT_SETTINGS, "\n".join(lines) + "\n")


def test_sentence_with_decisions_is_the_design_sentence(run_dir):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    p = granted(run_dir, "전부 자동 승인")
    assert p.returncode == 0, p.output
    assert ("위임: L1~L3으로 적었습니다. 이 실행의 코드 확인은 남긴 곳으로 건수와 위치만 남고 다시 오지 않습니다. "
            "보안과 시험 끄기·삭제는 기다립니다") in p.stdout


def test_sentence_without_decisions_does_not_promise_the_code_check_is_left(run_dir):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    p = granted(run_dir, "dev 배포까지 맡아")
    assert p.returncode == 0, p.output
    assert "위임: L2~L3으로 적었습니다." in p.stdout
    assert "다시 오지 않습니다" not in p.stdout and "코드 확인은 그대로" in p.stdout


def test_sentence_says_commands_are_asked_when_marks_are_empty(run_dir):
    assert "운영 표지" in granted(run_dir, "dev 배포까지 맡아").stdout


def test_delegate_writes_the_row_and_the_original(run_dir):
    p = granted(run_dir, "dev 배포까지 맡아")
    assert p.returncode == 0, p.output
    assert lib.delegation_levels(str(run_dir.path)) == ("L2", "L3")
    text = (run_dir.path / "decisions.md").read_text(encoding="utf-8")
    assert '위임 L2~L3 | 원문: "dev 배포까지 맡아" | 확인: "네" | 실행 전체' in text
    # 표의 다른 행은 그대로이고, 고쳐 말하면 행 하나만 바뀐다
    assert granted(run_dir, "운영까지 맡아").returncode == 0
    run_md = (run_dir.path / "run.md").read_text(encoding="utf-8")
    assert run_md.count("| 위임 |") == 1 and "| 수정 세대 상한 | 2 |" in run_md
    assert lib.delegation_levels(str(run_dir.path)) == ("L2", "L3", "L4")


# ---------------------------------------------------------------- 읽은 범위의 확인


def pending_file(run_dir):
    return run_dir.path / delegation.PENDING_FILE


def test_no_row_before_the_person_confirms(run_dir):
    p = deleg(run_dir, "dev 배포까지 맡아")
    assert p.returncode == 0
    assert "이렇게 맡기는 것으로 읽었습니다: 로컬 명령과 dev 배포. 결정과 운영은 계속 여쭙니다. 맞으면 ㅇ, 아니면 고쳐 말씀해 주세요." in p.stdout
    assert "L2" not in p.stdout   # 층 이름을 사람에게 보이지 않는다
    assert lib.delegation_levels(str(run_dir.path)) == ()
    assert not (run_dir.path / "decisions.md").exists()
    assert pending_file(run_dir).is_file() and "dev 배포까지 맡아" in pending_file(run_dir).read_text(encoding="utf-8")


@pytest.mark.parametrize("answer", ["ㅇ", "ㅇㅇ", "ㅇㅋ", "네", "넵", "맞아", "맞아요", "맞습니다", "네.", "yes"])
def test_a_short_yes_writes_the_row_and_both_words(run_dir, answer):
    p = granted(run_dir, "전부 자동 승인", answer)
    assert p.returncode == 0, p.output
    assert lib.delegation_levels(str(run_dir.path)) == ("L1", "L2", "L3")
    assert not pending_file(run_dir).exists()
    text = (run_dir.path / "decisions.md").read_text(encoding="utf-8")
    assert '원문: "전부 자동 승인" | 확인: "{}"'.format(answer) in text


@pytest.mark.parametrize("answer", ["아니", "아니요", "ㄴㄴ", "운영도 맡겨", "dev까지만", "네 그런데 운영은 빼고", "글쎄", "그 화면은 승인", ""])
def test_any_other_answer_drops_the_pending_and_asks_again(run_dir, answer):
    assert deleg(run_dir, "전부 자동 승인").returncode == 0
    p = confirm(run_dir, answer)
    assert p.returncode == 3 and "되물음" in p.stdout
    assert lib.delegation_levels(str(run_dir.path)) == () and not pending_file(run_dir).exists()
    assert not (run_dir.path / "decisions.md").exists()


def test_confirm_without_a_pending_is_refused(run_dir):
    p = confirm(run_dir, "네")
    assert p.returncode == 3 and "대기" in p.stdout
    assert lib.delegation_levels(str(run_dir.path)) == ()


def test_a_second_confirm_does_not_write_again(run_dir):
    assert granted(run_dir, "전부 자동 승인").returncode == 0
    assert confirm(run_dir, "네").returncode == 3


@pytest.mark.parametrize("text,want", [("운영은 하지 마", ("L1", "L2", "L3")), ("자동 승인 해제", ()), ("dev까지만 맡아", ("L2", "L3"))])
def test_narrowing_words_apply_without_a_confirm(run_dir, text, want):
    assert granted(run_dir, "운영까지 전부 자동 승인").returncode == 0
    p = deleg(run_dir, text)
    assert p.returncode == 0 and "맞으면 ㅇ" not in p.stdout
    assert lib.delegation_levels(str(run_dir.path)) == want and not pending_file(run_dir).exists()


def test_widening_a_row_still_needs_a_confirm_and_the_old_row_holds(run_dir):
    assert granted(run_dir, "dev 배포까지 맡아").returncode == 0
    assert "맞으면 ㅇ" in deleg(run_dir, "운영까지 맡아").stdout
    assert lib.delegation_levels(str(run_dir.path)) == ("L2", "L3")


@pytest.mark.parametrize("step", ["자동 승인 해제", "clear", "알아서 해"])
def test_cancelling_or_unreadable_words_drop_the_pending(run_dir, step):
    assert deleg(run_dir, "전부 자동 승인").returncode == 0
    if step == "clear":
        assert run_script("screen", run_dir.path, "--delegate-clear", "다시 엶").returncode == 0
    else:
        deleg(run_dir, step)
    assert not pending_file(run_dir).exists()
    assert confirm(run_dir, "네").returncode == 3
    assert lib.delegation_levels(str(run_dir.path)) == ()


def test_pending_is_not_a_delegation(run_dir):
    assert deleg(run_dir, "전부 자동 승인").returncode == 0
    make(run_dir, cells={"decide": DECIDE})
    assert gate(run_dir)["closable"] is False
    assert "■ 위임" not in run_script("screen", run_dir.path, "T010").stdout
    assert rec(run_dir, "T010", "승인|위임 L1|전부 자동 승인").returncode == 3
    assert delegation.current_original(str(run_dir.path)) == ""
    # 다른 화면의 답은 평소대로 적힌다
    assert rec(run_dir, "T010", "승인|(가)|가로 해 주세요").returncode == 0


@pytest.mark.parametrize("answer", ["L4 확인|운영|네", "실물 확인|[실물 확인 미룸] 화면 → 배포 메모|ㅇ", "되물음(이해)|뜻|ㅇ", "승인|(가)|ㅇ 가로 해 주세요"])
def test_any_recorded_answer_ends_the_pending(run_dir, answer):
    make(run_dir, cells={"decide": DECIDE})
    assert deleg(run_dir, "운영까지 전부 자동 승인").returncode == 0
    assert rec(run_dir, "T010", answer).returncode == 0
    assert not pending_file(run_dir).exists()
    assert confirm(run_dir, "ㅇ").returncode == 3
    assert lib.delegation_levels(str(run_dir.path)) == ()


def test_saving_a_screen_ends_the_pending(run_dir):
    make(run_dir, cells={"decide": DECIDE})
    assert deleg(run_dir, "운영까지 전부 자동 승인").returncode == 0
    assert run_script("screen", run_dir.path, "T010", "--save").returncode == 0
    assert not pending_file(run_dir).exists()


def test_a_card_ends_the_pending(run_dir):
    make(run_dir, cells={"decide": DECIDE})
    assert deleg(run_dir, "운영까지 전부 자동 승인").returncode == 0
    run_script("screen", run_dir.path, "T010", "--card")
    assert not pending_file(run_dir).exists()


def test_the_next_answer_confirms_however_old_the_task_times_are(run_dir):
    make(run_dir, cells={"decide": DECIDE}, asked_at="2099-01-01 00:00:00")
    assert deleg(run_dir, "전부 자동 승인").returncode == 0
    assert confirm(run_dir, "ㅇ").returncode == 0


@pytest.mark.parametrize("answer", ["네...", "네…", "ㅇ..", "맞아..."])
def test_a_trailing_off_answer_is_not_a_yes(run_dir, answer):
    assert deleg(run_dir, "전부 자동 승인").returncode == 0
    assert confirm(run_dir, answer).returncode == 3


@pytest.mark.parametrize("words", ["운영만 맡아", "dev만 맡아"])
def test_handing_word_with_only_is_not_a_plain_approval(run_dir, words):
    make(run_dir)
    assert rec(run_dir, "T010", "승인|승인|" + words).returncode == 3


def test_the_refusal_says_delegation_before_leaving_out(run_dir):
    plan(run_dir, ["npm run a"], "", kind="probe", stage="실행승인")
    p = rec(run_dir, "T020", "승인|실행 승인|묻지 말고 운영까지 해")
    assert p.returncode == 3 and "위임의 말" in p.output and "뺀다" not in p.output


def test_resume_shows_the_pending_line(run_dir):
    assert "위임 대기" not in run_script("board", run_dir.path, "--resume").stdout
    assert deleg(run_dir, "dev 배포까지 맡아").returncode == 0
    out = run_script("board", run_dir.path, "--resume").stdout
    assert "위임 대기" in out and "dev 배포까지 맡아" in out and "로컬 명령과 dev 배포" in out


def test_gate_compares_the_first_words_not_the_yes(run_dir):
    make(run_dir, cells={"decide": DECIDE})
    assert granted(run_dir, "전부 자동 승인", "넵").returncode == 0
    assert delegation.current_original(str(run_dir.path)) == "전부 자동 승인"
    assert rec(run_dir, "T010", "승인|위임 L1|넵").returncode == 3
    assert rec(run_dir, "T010", "승인|위임 L1~L3|전부 자동 승인").returncode == 0


@pytest.mark.parametrize("levels,part", [(("L1",), "결정. 로컬 명령, dev 배포와 운영은"), (("L1", "L2", "L3", "L4"), "결정, 로컬 명령, dev 배포와 운영. 맞으면"), (("L4",), "운영. 결정, 로컬 명령과 dev 배포는")])
def test_pending_sentence_uses_plain_words(levels, part):
    assert part.replace(". 맞으면", ".") in delegation.pending_sentence(levels)


def test_other_rows_starting_with_the_word_survive(run_dir):
    path = run_dir.path / "run.md"
    path.write_text(path.read_text(encoding="utf-8") + "| 위임 횟수 | 3 |\n", encoding="utf-8")
    assert granted(run_dir, "dev 배포까지 맡아").returncode == 0
    assert "| 위임 횟수 | 3 |" in path.read_text(encoding="utf-8")
    assert lib.delegation_levels(str(run_dir.path)) == ("L2", "L3")


def test_delegate_does_not_write_when_it_asks_again(run_dir):
    p = deleg(run_dir, "알아서 해")
    assert p.returncode == 3 and "되물음" in p.stdout
    assert lib.delegation_levels(str(run_dir.path)) == ()
    assert not (run_dir.path / "decisions.md").exists()


def test_negation_writes_none_so_nothing_is_delegated(run_dir):
    assert granted(run_dir, "전부 자동 승인").returncode == 0
    p = deleg(run_dir, "자동 승인은 하지 마")
    assert p.returncode == 0 and "없음" in p.stdout
    assert lib.delegation_levels(str(run_dir.path)) == ()


def test_second_unreadable_answer_takes_the_row_down(run_dir):
    assert granted(run_dir, "전부 자동 승인").returncode == 0
    assert deleg(run_dir, "위임을 어떻게 할지 모르겠어").returncode == 3
    assert lib.delegation_levels(str(run_dir.path)) == ("L1", "L2", "L3")   # 첫 되물음에서는 그대로다
    p = run_script("screen", run_dir.path, "--delegate-clear", "되물음 두 번")
    assert p.returncode == 0 and "없음" in p.stdout
    assert lib.delegation_levels(str(run_dir.path)) == ()
    text = (run_dir.path / "decisions.md").read_text(encoding="utf-8")
    assert "[메인] 위임 없음: 되물음 두 번 | 메인 판단" in text
    assert '원문: "되물음' not in text   # 사용자가 하지 않은 말을 원문으로 남기지 않는다
    assert delegation.current_original(str(run_dir.path)) == ""


def test_multi_line_original_stays_one_line(run_dir):
    assert granted(run_dir, "dev 배포까지 맡아\n운영은 하지 마").returncode == 0
    text = (run_dir.path / "decisions.md").read_text(encoding="utf-8")
    assert '원문: "dev 배포까지 맡아 운영은 하지 마"' in text and len(text.splitlines()) == 1
    assert lib.delegation_levels(str(run_dir.path)) == ("L2", "L3")


def test_sentence_matches_the_gate_when_marks_are_empty(run_dir):
    assert "그대로 여쭙니다" in granted(run_dir, "dev 배포까지 맡아").stdout
    p = granted(run_dir, "L1~L4")
    assert "그대로 여쭙니다" not in p.stdout and "한 번 더" in p.stdout


def test_row_goes_into_a_run_without_the_table(run_dir):
    path = run_dir.path / "run.md"
    path.write_text("---\nstatus: 진행\n---\n\n## 요청 원문\n시험\n", encoding="utf-8")
    assert granted(run_dir, "dev 배포까지 맡아").returncode == 0
    assert lib.delegation_levels(str(run_dir.path)) == ("L2", "L3")


def test_answer_points_to_delegate_when_it_cannot_read_the_words(run_dir):
    make(run_dir, cells={"decide": DECIDE})
    assert run_script("screen", run_dir.path, "T010", "--save").returncode == 0
    p = run_script("screen", run_dir.path, "T010", "--answer", "나머지 자동 승인")
    assert p.returncode == 3 and "--delegate" in p.stdout
    # 「하실 일」을 넘기는 말이나 다른 말로 위임 길을 안내하지 않는다
    for words in ("그 라이브러리 니가 알아서 세팅하는걸로", "알아서 해", "자동 승인은 하지 마"):
        p = run_script("screen", run_dir.path, "T010", "--answer", words)
        assert p.returncode == 3 and "--delegate" not in p.stdout, words
    # 짧은 답의 꼴은 그대로 풀린다
    assert run_script("screen", run_dir.path, "T010", "--answer", "1 가").returncode == 0


# ---------------------------------------------------------------- 성질 끌어내기


@pytest.mark.parametrize("line,want", [
    ("데이터를 옮겨야 합니다(D-3, 질문 1).", {"밖"}),
    ("외부 서비스 설정(확인 질문 3).", {"비용"}),
    ("요청서 줄 구분을 더했습니다(질문 4) [성질: 없음]", {"범위"}),
    ("비밀값 위치가 바뀝니다(질문 5·6).", {"범위"}),
    ("실제 꼴(확인 질문 1·3).", {"밖", "비용"}),
    ("[Q1] 마이그레이션", {"밖"}),
    ("[Q1·Q3] 자원", {"밖", "비용"}),
    ("[Q5, Q4] 권한", {"범위"}),
    ("주소가 바뀝니다(질문 2).", set()),
    ("해석했습니다(질문 6).", set()),
    ("확인 질문 1~6에 걸리지 않음", set()),
    ("걸린 질문 없음", set()),
    ("Q-1 (다)를 반영했습니다", set()),
    ("T001 Q4의 답을 옮겼습니다", set()),
    ("[사실] 코드에서 확인한 값(질문 4)", set()),
])
def test_properties_from_question_numbers(line, want):
    assert delegation.item_derived(line) == want


@pytest.mark.parametrize("line", ["실패를 그대로 둡니다: (가) 위험 수용 (나) 고침", "(가) 받아들임 (나) 고침",
                                  "(가) 백로그로 미루고 완료 (나) 지금 고침"])
def test_accepting_a_risk_is_risk_where_a_choice_is_offered(line):
    assert "위험" in delegation.item_derived(line, decide=True)
    assert "위험" not in delegation.item_derived(line)   # 「알릴 것」의 말로는 알림을 막지 않는다


def test_an_irreversible_choice_waits_even_with_only_outside(run_dir):
    make(run_dir, cells={"decide": "- 되돌릴 수 없음: 처음 들어가는 자원 [성질: 밖]\n  추천 (가): 이유"}, values="L1~L4")
    assert gate(run_dir)["closable"] is False


@pytest.mark.parametrize("line", ["로그인 권한을 정합니다", "개인정보 보관 기간", "[보안] 토큰 검사", "인증 방식"])
def test_security_words_raise_scope(line):
    assert "범위" in delegation.item_derived(line, decide=True)


WORDS = "전부 자동 승인"


def make(run_dir, tid="T010", kind="implementation", cells=None, status="승인대기", touch="(없음)", values="", title="시험", record="", **meta):
    """판정이 통과한 task 하나. kind가 코드면 판정 파일까지 둔다."""
    run_dir.task(tid, title, {"건드릴 파일": touch, "승인 기록": record}, kind=kind, status=status, **dict(NEW, **meta))
    run_dir.result(tid, result(**(cells or {})))
    judged(run_dir, tid, run=True)
    if values:
        path = run_dir.path / "run.md"
        path.write_text(path.read_text(encoding="utf-8") + "| 위임 | {} |\n".format(values), encoding="utf-8")
        write(run_dir.path / "decisions.md", '- 2026-11-05 08:00:00 | 위임 {} | 원문: "{}" | 실행 전체\n'.format(values, WORDS))


def gate(run_dir, tid="T010"):
    return screen.delegation_status(str(run_dir.path), tid)


def test_derived_mark_shows_on_the_screen(run_dir):
    make(run_dir, cells={"notify": "- 요청서 줄 구분을 더했습니다(질문 4) [성질: 없음]"})
    b = screen.build(str(run_dir.path), "T010")
    assert lib.item_properties(b["screen"]["알릴 것"]) >= {"범위"}


ADD_JUDGE = "\n## 칸 분류 확인\n{}\n"


def judge_lines(run_dir, tid, lines):
    path = run_dir.task_dir(tid) / "judge.md"
    text = path.read_text(encoding="utf-8")
    write(path, re.sub(r"## 칸 분류 확인\n(?:.*\n)*?(?=\n## |\Z)", "## 칸 분류 확인\n{}\n".format(lines), text) if "## 칸 분류 확인" in text
          else text + ADD_JUDGE.format(lines))


def test_judge_adds_a_property_without_a_retry(run_dir):
    make(run_dir, cells={"notify": "- 요청서 줄 구분을 더했습니다 [성질: 없음]"}, values="L1~L3")
    judge_lines(run_dir, "T010", "- 성질 더함: 요청서 줄 구분 범위")
    b = screen.build(str(run_dir.path), "T010")
    assert "[성질: 범위]" in b["screen"]["알릴 것"] and not b["move_failed"]
    assert "범위" in gate(run_dir)["why"]


def test_property_add_follows_a_line_that_moved(run_dir):
    make(run_dir, cells={"notify": "- 요청서 줄 구분을 더했습니다 [성질: 없음]"}, values="L1~L3")
    judge_lines(run_dir, "T010", "- 성질 더함: 요청서 줄 구분 범위\n- 알릴 것 → 확인 안 된 것 | 요청서 줄 구분 | 아직 못 봄")
    b = screen.build(str(run_dir.path), "T010")
    assert b["move_failed"] == [] and b["moved"] == 1
    assert "[성질: 범위]" in b["screen"]["확인 안 된 것"] and "요청서" not in b["screen"]["알릴 것"]


def test_property_add_with_an_arrow_in_the_item_is_not_a_move(run_dir):
    make(run_dir, cells={"notify": "- 가 → 나로 옮깁니다 [성질: 없음]"}, values="L1~L3")
    judge_lines(run_dir, "T010", "- 성질 더함: 가 → 나로 옮깁니다 비용")
    b = screen.build(str(run_dir.path), "T010")
    assert b["move_failed"] == [] and "[성질: 비용]" in b["screen"]["알릴 것"]


@pytest.mark.parametrize("line", ["- 성질 더함: 없는 항목입니다 범위", "- 성질 더함: 요청서 줄 구분 아무말", "- 성질 더함: 요청서"])
def test_unreadable_property_add_goes_to_a_person(run_dir, line):
    code_cells = {"notify": "- 요청서 줄 구분을 더했습니다 [성질: 없음]"}
    make(run_dir, cells=code_cells)
    judge_lines(run_dir, "T010", line)
    b = screen.build(str(run_dir.path), "T010")
    assert b["move_failed"] and not b["notify_ok"]


def test_risk_added_by_the_judge_stops_the_notice(run_dir):
    make(run_dir, cells={"notify": "- 결함을 그대로 둡니다 [성질: 없음]"}, status="자체검증")
    judge_lines(run_dir, "T010", "- 성질 더함: 결함을 그대로 위험")
    assert screen.build(str(run_dir.path), "T010")["risky"] is True


def test_old_task_ignores_property_adds(run_dir):
    make(run_dir, cells={"notify": "- 요청서 줄 구분을 더했습니다"}, started_version="1.1.1")
    judge_lines(run_dir, "T010", "- 성질 더함: 요청서 줄 구분 범위")
    b = screen.build(str(run_dir.path), "T010")
    assert "[성질:" not in b["screen"]["알릴 것"] and not b["move_failed"]


def test_old_task_is_not_marked_or_gated(run_dir):
    make(run_dir, cells={"notify": "- 요청서 줄 구분을 더했습니다(질문 4)"}, started_version="1.1.1", values="L1~L3")
    b = screen.build(str(run_dir.path), "T010")
    assert "[성질:" not in b["screen"]["알릴 것"]
    assert gate(run_dir)["closable"] is False and "1.2.0" in gate(run_dir)["why"]


def test_moved_lines_do_not_raise(run_dir):
    make(run_dir, cells={"notify": "- [T003] 비밀값 위치가 바뀝니다(질문 5)"}, values="L1~L3")
    assert gate(run_dir)["closable"] is True


def test_infra_path_is_cost_and_outside_for_the_whole_task(run_dir):
    make(run_dir, touch="- wrangler.jsonc", values="L1~L3")
    g = gate(run_dir)
    assert g["closable"] is False and "비용" in g["why"]


def test_changing_an_approved_spec_is_scope(run_dir):
    make(run_dir, kind="change", touch="- spec/pick.md", values="L1~L3")
    assert "범위" in gate(run_dir)["why"]


# ---------------------------------------------------------------- 위임 관문


DECIDE = "- 무엇을 고른다 [성질: 없음]\n  (가) 이것 (나) 저것\n  추천 (가): 이유"


def test_no_row_is_not_delegated(run_dir):
    make(run_dir, cells={"decide": DECIDE})
    g = gate(run_dir)
    assert g["levels"] == () and g["closable"] is False


def test_l1_closes_a_decision_without_properties(run_dir):
    make(run_dir, cells={"decide": DECIDE}, values="L1~L3")
    assert gate(run_dir)["closable"] is True


@pytest.mark.parametrize("cell,word", [
    ("- 고른다 [성질: 범위]\n  추천 (가): 이유", "범위"),
    ("- 고른다 [성질: 비용]\n  추천 (가): 이유", "비용"),
    ("- 고른다 [성질: 위험]\n  추천 (가): 이유", "위험"),
    ("- 고른다 [성질: 범위·밖]\n  추천 (가): 이유", "범위"),
    ("- 고른다\n  추천 (가): 이유", "성질"),            # 표시가 없으면 없는 것으로 보지 않는다
    ("- 고른다 [성질: 없음]\n  (가) (나)", "추천"),      # 추천안으로 정하는 층이다
    ("- 배포 줄 [성질: 위험]\n  추천 (가): 이유", "위험"),  # 배포 계획의 줄은 첫 질문을 닫지 않는다
])
def test_decision_waits_for_a_person(run_dir, cell, word):
    make(run_dir, cells={"decide": cell}, values="L1~L4")
    g = gate(run_dir)
    assert g["closable"] is False and word in g["why"]


def test_todo_always_waits(run_dir):
    make(run_dir, cells={"todo": "- 콘솔에서 키를 만듭니다"}, values="L1~L4")
    g = gate(run_dir)
    assert g["closable"] is False and "하실 일" in g["why"]


@pytest.mark.parametrize("cell,key", [("- 비밀값 위치(질문 5)", "notify"), ("- 받아들인 결함 [성질: 위험]", "unverified")])
def test_marked_report_lines_wait(run_dir, cell, key):
    make(run_dir, cells={key: cell}, values="L1~L3")
    assert gate(run_dir)["closable"] is False


def test_failed_criterion_waits(run_dir):
    make(run_dir, cells={"decide": DECIDE}, values="L1~L3")
    write(run_dir.task_dir("T010") / "judge.md", "## 판정 표\n\n## 통과 못 한 기준\n- 기준 1: 실패\n")
    assert "통과 못 한" in gate(run_dir)["why"]


def test_a_handed_over_todo_is_asked_even_within_the_row(run_dir):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    cell = "- 이 명령을 돌립니다 [성질: 밖]\n```cmd\nnpm run setup\n```"
    make(run_dir, kind="probe", stage="실행승인", cells={"decide": cell}, values="L1~L3", origin=lib.HANDED_ORIGIN + " T003")
    g = gate(run_dir)
    assert g["closable"] is False and "넘긴" in g["why"]


TODO = "- 그 설정을 콘솔에서 만듭니다"


def test_the_hand_over_answer_has_its_own_point_and_closes_nothing(run_dir):
    make(run_dir, cells={"todo": TODO}, approval_requested="2026-11-05 09:00:00")
    assert rec(run_dir, "T010", "승인|승인|그 설정은 네가 알아서 해").returncode == 3
    p = rec(run_dir, "T010", "하실 일 넘김|[하실 일 넘김 T010] 그 설정|그 설정은 네가 알아서 해")
    assert p.returncode == 0, p.output
    tasks = run_dir.tasks()
    assert tasks["T010"]["status"] == "승인대기"
    assert not (run_dir.task_dir("T010") / "approved-cmds-실행승인.md").exists()
    assert lib.handed_without_probe(str(run_dir.path), tasks) == ["T010"]


@pytest.mark.parametrize("line", ["승인|[하실 일 넘김 T050] 그 설정|전부 자동 승인", "승인|[하실 일 넘김 T999]|운영까지 맡아",
                                  "승인|[하실 일 넘김 T010] 그 설정|그 설정은 네가 알아서 해"])
def test_the_mark_cannot_sit_on_an_approval_line(run_dir, line):
    cell = TODO + "\n- 명령 [성질: 밖]\n```cmd\ngit push origin main\n```"
    make(run_dir, cells={"decide": cell}, approval_requested="2026-11-05 09:00:00")
    p = run_script("task_set", run_dir.path, "T010", "--status", "완료", "--record", line)
    assert p.returncode == 3 and "넘김" in p.output
    assert run_dir.tasks()["T010"]["status"] == "승인대기"
    assert not (run_dir.task_dir("T010") / "approved-cmds-실행승인.md").exists()


@pytest.mark.parametrize("line", ["하실 일 넘김|[하실 일 넘김 T999] 그 설정|네가 해", "하실 일 넘김|[하실 일 넘김 T010] 없는 일|네가 해",
                                  "하실 일 넘김|[하실 일 넘김 T010]|네가 해", "하실 일 넘김|표지 없음|네가 해"])
def test_the_mark_must_name_this_task_and_its_todo(run_dir, line):
    make(run_dir, cells={"todo": TODO})
    assert rec(run_dir, "T010", line).returncode == 3


def test_the_hand_over_answer_does_not_move_the_status(run_dir):
    make(run_dir, cells={"todo": TODO})
    p = run_script("task_set", run_dir.path, "T010", "--status", "완료", "--record", "하실 일 넘김|[하실 일 넘김 T010] 그 설정|네가 해")
    assert p.returncode == 3 and run_dir.tasks()["T010"]["status"] == "승인대기"


@pytest.mark.parametrize("point", ["하실 일 넘김", "L4 확인", "실물 확인"])
def test_a_bare_yes_on_these_points_is_not_an_approval(point):
    assert not lib.approval_line('- 2026-11-05 10:00:00 | {} | 무엇 | 원문: "승인"'.format(point))


@pytest.mark.parametrize("kw", [{"origin": "넘김: " + lib.HANDED_ORIGIN + " T003"}, {"record": '- 2026-11-05 09:00:00 | 하실 일 넘김 | [하실 일 넘김 T010] 그 설정 | 원문: "네가 해"'}])
def test_a_handed_line_waits_however_it_is_marked(run_dir, kw):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    make(run_dir, kind="probe", stage="실행승인", cells={"decide": "- 이 명령을 돌립니다 [성질: 밖]\n```cmd\nnpm run setup\n```"}, values="L1~L3", **kw)
    assert "넘긴" in gate(run_dir)["why"]


def test_a_handed_mark_in_a_command_line_waits(run_dir):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    make(run_dir, kind="probe", stage="실행승인", cells={"decide": "- [하실 일 넘김 T003] 이 명령을 돌립니다 [성질: 밖]\n```cmd\nnpm run setup\n```"}, values="L1~L3")
    assert "넘긴" in gate(run_dir)["why"]


@pytest.mark.parametrize("kind,stage,row,closable", [
    ("merge", "결과승인", "L2", True), ("probe", "결과승인", "L2", False), ("probe", "결과승인", "L3", True),
    ("wrap-up", "결과승인", "L2", False), ("wrap-up", "결과승인", "L3", True), ("deploy-exec", "결과승인", "L2", False),
])
def test_a_stage_screen_without_commands_splits_merge_from_the_rest(run_dir, kind, stage, row, closable):
    make(run_dir, kind=kind, stage=stage, values=row)
    assert gate(run_dir)["closable"] is closable


@pytest.mark.parametrize("left", ["자원", "파일"])
@pytest.mark.parametrize("stage", ["실행승인", "결과승인"])
def test_a_probe_that_leaves_something_goes_to_a_person(run_dir, left, stage):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    cell = "- 이 명령을 돌립니다 [성질: 밖]\n```cmd\nnpm run setup\n```"
    run_dir.task("T010", "탐침", {"범위": "받기\n남는 것: " + left}, kind="probe", status="승인대기", stage=stage, **NEW)
    run_dir.result("T010", result(decide=cell))
    judged(run_dir, "T010", run=True)
    path = run_dir.path / "run.md"
    path.write_text(path.read_text(encoding="utf-8") + "| 위임 | L1~L4 |\n", encoding="utf-8")
    write(run_dir.path / "decisions.md", '- 2026-11-05 08:00:00 | 위임 L1~L4 | 원문: "{}" | 실행 전체\n'.format(WORDS))
    g = gate(run_dir)
    assert g["closable"] is False and "남기" in g["why"]


@pytest.mark.parametrize("row,closable", [("L2", True), ("L1", False)])
def test_merge_result_after_the_answerless_merge_is_the_local_level(run_dir, row, closable):
    make(run_dir, kind="merge", stage="결과승인", values=row)
    g = gate(run_dir)
    assert g["need"] == ("L2",) and g["closable"] is closable


def test_wrap_up_stage_table_still_needs_outside_level(run_dir):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    cell = "- 이 명령을 원래 폴더에서 실행합니다 [성질: 밖]\n```cmd\ngit merge --ff-only harness/x/integration\n```"
    make(run_dir, kind="wrap-up", stage="실행승인", cells={"decide": cell}, values="L2")
    assert "L3" in gate(run_dir)["why"]


def test_commands_only_row_does_not_close_decisions(run_dir):
    make(run_dir, cells={"decide": DECIDE}, values="L2~L3")
    g = gate(run_dir)
    assert g["closable"] is False and "L1" in g["why"] and g["close"] == []


def test_l1_row_lists_what_closes_with_the_recommendation(run_dir):
    make(run_dir, cells={"decide": DECIDE + "\n- 다른 것 [성질: 범위]\n  추천 (가): 이유"}, values="L1~L3")
    g = gate(run_dir)
    assert g["closable"] is False and [c[:6] for c in g["close"]] == ["무엇을 고른"]


@pytest.mark.parametrize("cell", ["1. 범위를 바꿉니다 [성질: 범위]", "범위를 바꿀지 정해 주세요", "| 항목 | 값 |\n|---|---|\n| 범위 | 바꿈 |"])
@pytest.mark.parametrize("key", ["decide", "todo", "notify", "unverified"])
def test_a_cell_that_cannot_be_read_waits(run_dir, cell, key):
    make(run_dir, cells={key: cell}, values="L1~L3")
    g = gate(run_dir)
    assert g["closable"] is False and "칸 꼴" in g["why"]


@pytest.mark.parametrize("line", ["추천 없음: 근거가 없다", "추천하지 않음", "추천: 없음", "(가) (나) 추천할 근거 없음"])
def test_saying_there_is_no_recommendation_is_not_a_recommendation(run_dir, line):
    make(run_dir, cells={"decide": "- 고른다 [성질: 없음]\n  " + line}, values="L1~L3")
    assert "추천 없음" in gate(run_dir)["why"]


@pytest.mark.parametrize("line", ["추천 (가): 이유", "추천: (가)", "(가) 이것 (추천)", "추천안 (나): 이유", "(가) 이것 (Recommended)", "추천 가: 이유"])
def test_recommendation_shapes(run_dir, line):
    make(run_dir, cells={"decide": "- 고른다 [성질: 없음]\n  " + line}, values="L1~L3")
    assert gate(run_dir)["closable"] is True


@pytest.mark.parametrize("line", ["- 성질 더함: 없는 항목 앞부분 범위", "- 성질 더함: 요청서 줄 구분 범위.", "- 없는 칸 → 알릴 것 | 요청서 | 이유"])
def test_a_judge_line_that_cannot_be_read_waits(run_dir, line):
    make(run_dir, cells={"notify": "- 요청서 줄 구분을 더했습니다 [성질: 없음]"}, values="L1~L3")
    judge_lines(run_dir, "T010", line)
    g = gate(run_dir)
    assert g["closable"] is False and "판정자 줄을 읽지 못함" in g["why"]
    assert "판정자 줄을 읽지 못함" in run_script("screen", run_dir.path, "T010").stdout
    assert rec(run_dir, "T010", "승인|위임 L1|" + WORDS).returncode == 3


def test_text_before_the_items_waits(run_dir):
    make(run_dir, cells={"decide": "범위를 바꿀지 정해 주세요 [성질: 범위]\n- 작은 결정 [성질: 없음]\n  추천 (가): 이유"}, values="L1~L3")
    g = gate(run_dir)
    assert g["closable"] is False and "칸 꼴" in g["why"]


def test_fact_line_in_decide_does_not_wait(run_dir):
    make(run_dir, cells={"decide": "- [사실] 코드에서 확인한 값"}, values="L1~L3")
    assert gate(run_dir)["closable"] is True


def test_security_mark_raises_in_any_cell(run_dir):
    make(run_dir, cells={"notify": "- [보안] 토큰 저장 방식을 정했습니다 [성질: 없음]"}, values="L1~L3")
    assert "범위" in gate(run_dir)["why"]


@pytest.mark.parametrize("cell,word", [
    ("- 이 명령을 돌립니다\n```cmd\nnpm run x\n```", "성질"),
    ("- 어느 쪽으로 옮길지 고릅니다 (가) (나) [성질: 밖]\n```cmd\nnpm run x\n```", "추천"),
])
def test_a_command_item_is_not_exempt(run_dir, cell, word):
    make(run_dir, kind="probe", stage="실행승인", cells={"decide": cell}, values="L1~L3")
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    assert word in gate(run_dir)["why"]


def test_a_choice_in_a_command_item_needs_l1(run_dir):
    make(run_dir, kind="probe", stage="실행승인", cells={"decide": "- 옮길 곳 (가) (나) [성질: 밖]\n  추천 (가): 이유\n```cmd\nnpm run x\n```"}, values="L2~L3")
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    assert "L1" in gate(run_dir)["why"]


def test_flow_verify_gate_says_what_the_completion_guard_waits_for(run_dir):
    make(run_dir, kind="flow-verify", values="L1~L3", flow="a", body_marker="x")
    write(run_dir.task_dir("T010") / "places.md", "")
    import places
    original = places.completion_block
    try:
        places.completion_block = lambda r, t: "지금 답 없는 코드 확인 곳이 있음: k"
        g = screen.delegation_status(str(run_dir.path), "T010")
    finally:
        places.completion_block = original
    assert g["closable"] is False and "코드 확인 곳" in g["why"]


def test_commands_only_row_does_not_close_a_plain_approval(run_dir):
    make(run_dir, values="L2~L3")
    assert "L1" in gate(run_dir)["why"]


# ---------------------------------------------------------------- 명령의 층


def plan(run_dir, cmds, values, marks=("abcd1234",), branch="main", tid="T020", kind="deploy-plan", **meta):
    settings(run_dir, "- 운영 브랜치: `{}`".format(branch), "", "## 경로 목록", "- 운영 표지: " + ", ".join(marks))
    cell = "- 이 명령들을 실행합니다 [성질: 밖]\n```cmd\n" + "\n".join(cmds) + "\n```"
    make(run_dir, tid=tid, kind=kind, cells={"decide": cell}, values=values, **meta)


@pytest.mark.parametrize("cmds,want", [
    (["git merge --ff-only flow/a"], "L2"),
    (["git push origin dev"], "L3"),
    (["npm run deploy:dev"], "L3"),
    (["git push origin main"], "L4"),
    (["npx wrangler deploy --env abcd1234"], "L4"),
    (["cat PROD-worker.env"], "L4"),
    (["npm run deploy:prod"], "L4"),
    (["npx wrangler deploy --env production"], "L4"),
    (["git add . && git push origin dev"], "L3"),
    (["git commit -m x; npx wrangler deploy"], "L3"),
    (["git status | tee x"], "L3"),
    (["git add . & npm run deploy"], "L3"),
    (["git rebase -x 'npm run deploy' dev"], "L3"),
    (["git rebase --exec 'npm run deploy' dev"], "L3"),
    (["git rebase dev"], "L2"),
    (["npm run deploy:prd"], "L4"),
    (["npx wrangler deploy --env live"], "L4"),
    (["git -C D:/orig merge --ff-only harness/x/integration"], "L3"),
])
def test_command_levels(run_dir, cmds, want):
    plan(run_dir, cmds, "L1~L4", marks=("abcd1234", "prod-*.env"))
    t = run_dir.tasks()["T020"]
    assert delegation.command_level(str(run_dir.path), t, cmds) == want


@pytest.mark.parametrize("branch,line,want", [("", "git push origin main", "L4"), ("", "git push origin master", "L4"),
                                               ("release", "git push origin release", "L4"), ("release", "git push origin dev", "L3")])
def test_production_branch_defaults_to_the_usual_names(run_dir, branch, line, want):
    settings(run_dir, *(["- 운영 브랜치: `{}`".format(branch)] if branch else []), "", "## 경로 목록", "- 운영 표지: abcd1234")
    t = {"id": "T020", "title": "배포", "_dir": str(run_dir.task_dir("T020"))}
    assert delegation.command_level(str(run_dir.path), t, [line]) == want


@pytest.mark.parametrize("kind", ["wrap-up", "deploy-exec"])
def test_local_merge_of_an_export_reaches_outside(run_dir, kind):
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    t = {"id": "T020", "kind": kind, "title": "내보내기", "_dir": str(run_dir.task_dir("T020"))}
    assert delegation.command_level(str(run_dir.path), t, ["git merge --ff-only harness/x/integration"]) == "L3"


def test_one_reader_of_the_production_marks():
    assert not hasattr(delegation, "production_marks")


def test_empty_marks_raise_outside_commands_to_production(run_dir):
    t = {"id": "T020", "title": "dev 배포", "_dir": str(run_dir.task_dir("T020"))}
    assert delegation.command_level(str(run_dir.path), t, ["npm run deploy:dev"]) == "L4"
    assert delegation.command_level(str(run_dir.path), t, ["git merge --ff-only flow/a"]) == "L2"


def test_a_mark_in_the_judge_file_or_title_is_production(run_dir):
    plan(run_dir, ["npm run deploy"], "L1~L3")
    write(run_dir.task_dir("T020") / "judge-run.md", "## 판정 표\nabcd1234에 닿음\n\n## 통과 못 한 기준\n- 없음\n")
    t = run_dir.tasks()["T020"]
    assert delegation.command_level(str(run_dir.path), t, ["npm run deploy"]) == "L4"
    plan(run_dir, ["npm run deploy"], "L1~L3", tid="T021", title="운영 배포 계획")
    assert delegation.command_level(str(run_dir.path), run_dir.tasks()["T021"], ["npm run deploy"]) == "L4"


def test_main_inside_a_longer_name_is_not_the_branch(run_dir):
    plan(run_dir, ["echo x"], "L1~L3")
    assert delegation.command_level(str(run_dir.path), run_dir.tasks()["T020"], ["cat main-run.md", "curl https://domain.test"]) == "L3"


def test_command_within_the_row_closes_and_outside_waits(run_dir):
    plan(run_dir, ["npm run deploy:dev"], "L2~L3", kind="probe", stage="실행승인")
    assert gate(run_dir, "T020")["closable"] is True
    plan(run_dir, ["git push origin main"], "L2~L3", tid="T021", kind="probe", stage="실행승인")
    g = gate(run_dir, "T021")
    assert g["closable"] is False and "L4" in g["why"]


def test_deploy_plan_first_question_always_goes_to_a_person(run_dir):
    plan(run_dir, ["npm run deploy:dev"], "L1~L4")
    g = gate(run_dir, "T020")
    assert g["closable"] is False and "배포 계획" in g["why"]


def test_last_check_stage_is_never_delegated(run_dir):
    make(run_dir, kind="deploy-exec", stage="직전확인", values="L1~L4")
    g = gate(run_dir)
    assert g["closable"] is False and "직전" in g["why"]


# ---------------------------------------------------------------- 기록의 관문


def rec(run_dir, tid, line, *more):
    return run_script("task_set", run_dir.path, tid, "--record", line, *more)


def test_record_refuses_a_delegated_close_the_gate_does_not_allow(run_dir):
    make(run_dir, cells={"decide": "- 고른다 [성질: 범위]\n  추천 (가): 이유"}, values="L1~L3")
    p = rec(run_dir, "T010", "승인|위임 L1|전부 자동 승인")
    assert p.returncode == 3 and "위임으로 닫지 못함" in p.output
    assert "위임 L1" not in (run_dir.task_dir("T010") / "task.md").read_text(encoding="utf-8")


def test_record_takes_a_delegated_close_the_gate_allows(run_dir):
    make(run_dir, cells={"decide": DECIDE}, values="L1~L3")
    p = rec(run_dir, "T010", "승인|위임 L1|전부 자동 승인")
    assert p.returncode == 0, p.output


def test_person_answers_for_what_the_delegation_cannot_close(run_dir):
    make(run_dir, cells={"decide": "- 고른다 [성질: 범위]\n  추천 (가): 이유"}, values="L1~L3")
    p = rec(run_dir, "T010", "승인|(가)|가로 해 주세요")
    assert p.returncode == 0, p.output


def test_plain_approval_with_the_bulk_words_is_refused(run_dir):
    make(run_dir, cells={"decide": "- 고른다 [성질: 범위]\n  추천 (가): 이유"}, values="L1~L3")
    p = rec(run_dir, "T010", "승인|승인|나머지 자동 승인")
    assert p.returncode == 3 and "위임" in p.output
    p = rec(run_dir, "T010", "승인|승인|자동 승인은 하지 마")   # 부정문은 맡긴 말이 아니다
    assert p.returncode == 0, p.output


@pytest.mark.parametrize("words", ["묻지 말고 전부 자동 승인", "운영 빼고 전부 자동 승인", "운영까지 맡아", "전부 맡아", "모두 자동으로", "자동승인 말고 전부 진행"])
def test_bulk_words_cannot_pass_as_a_plain_approval(run_dir, words):
    make(run_dir)
    p = rec(run_dir, "T010", "승인|승인|" + words)
    assert p.returncode == 3 and ("위임" in p.output or "맡기는 말" in p.output)


@pytest.mark.parametrize("words", ["추천대로 해", "추천대로 진행", "알아서 정해", "알아서 골라", "결정해"])
def test_an_answer_for_one_screen_is_a_plain_answer(run_dir, words):
    make(run_dir, cells={"decide": DECIDE})
    assert run_script("screen", run_dir.path, "T010", "--save").returncode == 0
    p = run_script("screen", run_dir.path, "T010", "--answer", words)
    assert "--delegate" not in p.stdout
    assert deleg(run_dir, words).returncode == 3
    assert lib.delegation_levels(str(run_dir.path)) == ()
    p = rec(run_dir, "T010", "승인|(가)|" + words)
    assert p.returncode == 0, p.output


@pytest.mark.parametrize("words", ["다 맡길게", "알아서 올려", "앞으로 안 물어도 돼", "그 설정은 네가 알아서 해"])
def test_handing_words_with_no_level_are_not_a_person_approval(run_dir, words):
    make(run_dir)
    p = rec(run_dir, "T010", "승인|승인|" + words)
    assert p.returncode == 3 and "맡기는 말" in p.output


def test_leaving_something_out_of_the_commands_is_asked_again(run_dir):
    plan(run_dir, ["npm run a", "npm run b"], "", kind="probe", stage="실행승인")
    p = rec(run_dir, "T020", "승인|실행 승인|운영 빼고")
    assert p.returncode == 3 and "되묻" in p.output
    assert rec(run_dir, "T020", "승인|실행 승인|네 돌리세요").returncode == 0


def test_old_task_cannot_use_a_delegated_line(run_dir):
    make(run_dir, started_version="1.1.1", rules="2")
    p = rec(run_dir, "T010", "승인|위임 L3|네 그 명령 돌리세요")
    assert p.returncode == 3 and "1.2.0" in p.output


def test_a_person_answer_from_another_task_cannot_be_the_delegated_answer(run_dir):
    make(run_dir, cells={"decide": DECIDE}, values="L1~L3")
    p = rec(run_dir, "T010", "승인|위임 L1|네 그 명령 돌리세요")
    assert p.returncode == 3 and "원문" in p.output


def test_the_level_cell_must_cover_what_the_gate_needs(run_dir):
    plan(run_dir, ["npm run deploy:dev"], "L1~L3", kind="probe", stage="실행승인")
    write(run_dir.path / "decisions.md", '- 2026-11-05 08:00:00 | 위임 L1~L3 | 원문: "{}" | 실행 전체\n'.format(WORDS))
    p = rec(run_dir, "T020", "승인|위임 L1|" + WORDS)
    assert p.returncode == 3 and "L3" in p.output
    assert rec(run_dir, "T020", "승인|위임 L1~L3|" + WORDS).returncode == 0


def test_old_task_keeps_the_old_record(run_dir):
    make(run_dir, started_version="1.1.1")
    assert rec(run_dir, "T010", "승인|승인|나머지 자동 승인").returncode == 0


def test_same_original_does_not_stop_the_second_delegated_task(run_dir):
    long_text = "dev 배포까지 전부 자동 승인 부탁합니다"
    make(run_dir, cells={"decide": DECIDE}, values="L1~L3")
    write(run_dir.path / "decisions.md", '- 2026-11-05 08:00:00 | 위임 L1~L3 | 원문: "{}" | 실행 전체\n'.format(long_text))
    make(run_dir, tid="T009", cells={"decide": DECIDE}, record='- 2026-11-05 09:00:00 | 승인 | 위임 L1 | 원문: "{}"'.format(long_text))
    make(run_dir, tid="T011", cells={"decide": DECIDE}, approval_requested="2026-11-05 10:00:00")
    p = rec(run_dir, "T011", "승인|위임 L1|" + long_text)
    assert p.returncode == 0, p.output
    assert "재사용 답" not in (run_dir.task_dir("T011") / "task.md").read_text(encoding="utf-8")


def test_delegated_line_is_an_approval_for_freezing(run_dir):
    assert lib.approval_line('- 2026-11-05 10:00:00 | 승인 | 위임 L3 | 원문: "dev 배포까지 맡아"')


def test_delegated_close_freezes_the_commands_for_every_task_with_the_same_words(run_dir):
    words = "dev 배포까지 전부 자동 승인 부탁합니다"
    write(run_dir.path / "decisions.md", "")
    for tid in ("T020", "T021"):
        plan(run_dir, ["npm run deploy:dev"], "L1~L3", tid=tid, kind="probe", stage="실행승인", approval_requested="2026-11-05 09:00:00")
        write(run_dir.path / "decisions.md", '- 2026-11-05 08:00:00 | 위임 L1~L3 | 원문: "{}" | 실행 전체\n'.format(words))
        p = run_script("task_set", run_dir.path, tid, "--status", "진행", "stage=실행", "--record", "승인|위임 L3|" + words)
        assert p.returncode == 0, p.output
        assert "--freeze" in p.output
        assert (run_dir.task_dir(tid) / "approved-cmds-실행승인.md").is_file(), p.output


def test_waiting_task_still_closes_when_the_person_answers(run_dir):
    make(run_dir, cells={"todo": "- 콘솔에서 키를 만듭니다"}, values="L1~L3", approval_requested="2026-11-05 09:00:00")
    assert rec(run_dir, "T010", "승인|위임 L1|전부 자동 승인").returncode == 3
    p = run_script("task_set", run_dir.path, "T010", "--status", "보류", "--reason", "키를 아직 못 만듦")
    assert p.returncode == 0, p.output
    run_dir.task("T011", "다시", kind="implementation", status="대기", **NEW)
    assert lib.delegation_levels(str(run_dir.path)) == ("L1", "L2", "L3")   # 보류해도 위임은 그대로다


def test_second_unreadable_answer_leaves_no_row_and_the_run_can_go_on(run_dir):
    assert deleg(run_dir, "알아서 해").returncode == 3
    assert deleg(run_dir, "응 그래").returncode == 3
    make(run_dir, cells={"decide": DECIDE})
    assert gate(run_dir)["closable"] is False   # 사람에게 묻는 평소 길이다
    assert rec(run_dir, "T010", "승인|(가)|가로 해 주세요").returncode == 0


# ---------------------------------------------------------------- L4 직전 확인


def frozen(run_dir, tid, lines, at="2026-11-05 10:00:00", point="실행승인"):
    write(run_dir.task_dir(tid) / "approved-cmds-{}.md".format(point),
          "# 승인된 명령\n승인 기록 시각: {0}\n얼린 시각: {0}\n해시: x\n\n".format(at)
          + "\n".join("{}. {}".format(i, x) for i, x in enumerate(lines, 1)) + "\n")


def block(run_dir, tid, lines):
    tasks = lib.load_tasks(str(run_dir.path))
    return execmod.production_block(str(run_dir.path), tasks, tasks[tid], "실행승인", lines)


DELEGATED = '- 2026-11-05 09:59:00 | 승인 | 위임 L4 | 원문: "운영까지 맡아"'


def test_production_command_needs_the_check_with_the_environment_name(run_dir):
    plan(run_dir, ["git push origin main"], "L1~L4", record=DELEGATED)
    frozen(run_dir, "T020", ["git push origin main"])
    why = block(run_dir, "T020", ["git push origin main"])
    assert why and "L4 확인" in why
    assert rec(run_dir, "T020", "L4 확인|운영(예시)|네 올리세요").returncode == 0
    assert block(run_dir, "T020", ["git push origin main"]) == ""


@pytest.mark.parametrize("line", ['L4 확인 | 보류 | 원문: "멈춰"', 'L4 확인 | 안 함 | 원문: "아니"', 'L4 확인 |  | 원문: "네"'])
def test_a_refusal_or_a_blank_is_not_the_check(run_dir, line):
    plan(run_dir, ["git push origin main"], "L1~L4", record=DELEGATED + "\n- 2026-11-05 10:01:00 | " + line)
    frozen(run_dir, "T020", ["git push origin main"])
    assert block(run_dir, "T020", ["git push origin main"])


@pytest.mark.parametrize("words", ["아니 올리지 마", "운영까지 맡아", "그건 하지 마"])
def test_the_original_of_the_check_is_read_too(run_dir, words):
    plan(run_dir, ["git push origin main"], "L1~L4", record=DELEGATED)
    frozen(run_dir, "T020", ["git push origin main"])
    assert rec(run_dir, "T020", "L4 확인|운영(예시)|" + words).returncode == 0
    assert block(run_dir, "T020", ["git push origin main"])


def test_a_row_taken_down_stops_the_delegated_command(run_dir):
    plan(run_dir, ["npm run deploy:dev"], "L1~L3", record='- 2026-11-05 09:59:00 | 승인 | 위임 L3 | 원문: "전부 자동 승인"')
    frozen(run_dir, "T020", ["npm run deploy:dev"])
    assert block(run_dir, "T020", ["npm run deploy:dev"]) == ""
    assert deleg(run_dir, "자동 승인은 하지 마").returncode == 0
    why = block(run_dir, "T020", ["npm run deploy:dev"])
    assert why and "맡긴 층 밖" in why
    # 답만으로는 열리지 않고, 사람이 다시 승인해 다시 얼리면 열린다
    assert rec(run_dir, "T020", "승인|실행 승인|네 돌리세요").returncode == 0
    assert block(run_dir, "T020", ["npm run deploy:dev"])
    frozen(run_dir, "T020", ["npm run deploy:dev"], at="2099-01-01 00:00:00")
    assert block(run_dir, "T020", ["npm run deploy:dev"]) == ""


def test_a_later_answer_about_something_else_does_not_turn_the_freeze_into_a_person_approval(run_dir):
    plan(run_dir, ["git push origin main"], "L1~L4", record=DELEGATED)
    frozen(run_dir, "T020", ["git push origin main"])
    assert rec(run_dir, "T020", "승인|위험 수용|그 경고는 그대로 둡니다").returncode == 0
    assert "L4 확인" in block(run_dir, "T020", ["git push origin main"])


def test_a_later_result_answer_does_not_lift_the_row_check(run_dir):
    plan(run_dir, ["npm run deploy:dev"], "L1~L3", record='- 2026-11-05 09:59:00 | 승인 | 위임 L3 | 원문: "전부 자동 승인"')
    frozen(run_dir, "T020", ["npm run deploy:dev"])
    assert deleg(run_dir, "자동 승인은 하지 마").returncode == 0
    assert rec(run_dir, "T020", "승인|결과 승인|좋습니다 받아들입니다").returncode == 0
    assert "맡긴 층 밖" in block(run_dir, "T020", ["npm run deploy:dev"])


def test_a_refused_check_says_why_it_did_not_count(run_dir):
    plan(run_dir, ["git push origin main"], "L1~L4", record=DELEGATED)
    frozen(run_dir, "T020", ["git push origin main"])
    assert rec(run_dir, "T020", "L4 확인|운영(예시)|네 운영까지 진행").returncode == 0
    assert "세지 않았" in block(run_dir, "T020", ["git push origin main"])


def test_production_deploy_exec_under_a_row_needs_the_check_even_after_a_person_approved_the_plan(run_dir):
    plan(run_dir, ["git push origin main"], "L1~L4", record='- 2026-11-05 09:59:00 | 승인 | 실행 승인 | 원문: "네"', status="완료")
    make(run_dir, tid="T021", kind="deploy-exec", status="진행", parent="T020", stage="명령")
    frozen(run_dir, "T021", ["git push origin main"])
    assert block(run_dir, "T021", ["git push origin main"])
    assert rec(run_dir, "T021", "L4 확인|운영(예시)|네").returncode == 0
    assert block(run_dir, "T021", ["git push origin main"]) == ""


def test_step_command_is_tied_to_the_check(run_dir, workspace):
    """실제 명령 경로: `exec.py --step`이 확인 전에 거부하고, 확인 뒤에는 그 문을 지나 명령을 돌린다."""
    settings(run_dir, "## 경로 목록", "- 운영 표지: abcd1234")
    cell = "- 탐침 명령 [성질: 밖]\n```cmd\npython -c \"print(1)\" abcd1234\n```"
    make(run_dir, tid="T020", kind="probe", stage="실행승인", cells={"decide": cell}, values="L1~L4", approval_requested="2026-11-05 09:00:00")
    p = run_script("task_set", run_dir.path, "T020", "--status", "진행", "stage=실행", "--record", "승인|위임 L4|" + WORDS)
    assert p.returncode == 0, p.output
    assert (run_dir.task_dir("T020") / "approved-cmds-실행승인.md").is_file(), p.output
    p = run_script("exec", run_dir.path, "T020", "--step", "실행승인:1", "--cwd", workspace)
    assert p.returncode != 0 and "L4 확인" in p.output
    assert not (run_dir.task_dir("T020") / "exec.md").exists()
    assert rec(run_dir, "T020", "L4 확인|운영(abcd1234)|네 올리세요").returncode == 0
    p = run_script("exec", run_dir.path, "T020", "--step", "실행승인:1", "--cwd", workspace)
    assert "L4 확인" not in p.output, p.output
    if os.name == "nt" and "system32" in (shutil.which("bash") or "").lower():
        pytest.skip("PATH의 bash가 WSL이라 명령 줄이 돌지 못한다(L4 문을 지나는 것까지 봤다)")
    assert p.returncode == 0, p.output
    assert "abcd1234" in (run_dir.task_dir("T020") / "exec.md").read_text(encoding="utf-8")


def test_a_check_before_the_freeze_is_not_the_check(run_dir):
    plan(run_dir, ["git push origin main"], "L1~L4", record=DELEGATED + '\n- 2026-11-05 09:59:30 | L4 확인 | 운영 | 원문: "네"')
    frozen(run_dir, "T020", ["git push origin main"])
    assert block(run_dir, "T020", ["git push origin main"])


def test_person_approval_or_dev_command_does_not_need_it(run_dir):
    plan(run_dir, ["git push origin main"], "L1~L4", record='- 2026-11-05 09:59:00 | 승인 | 실행 승인 | 원문: "네 그 명령 돌리세요"')
    frozen(run_dir, "T020", ["git push origin main"])
    assert block(run_dir, "T020", ["git push origin main"]) == ""
    plan(run_dir, ["npm run deploy:dev"], "L1~L4", tid="T021", record=DELEGATED)
    frozen(run_dir, "T021", ["npm run deploy:dev"])
    assert block(run_dir, "T021", ["npm run deploy:dev"]) == ""


def test_deploy_exec_is_approved_by_its_parent_plan(run_dir):
    plan(run_dir, ["git push origin main"], "L1~L4", record=DELEGATED, status="완료")
    make(run_dir, tid="T021", kind="deploy-exec", status="진행", parent="T020", stage="명령")
    frozen(run_dir, "T021", ["git push origin main"])
    assert block(run_dir, "T021", ["git push origin main"])
    assert rec(run_dir, "T021", "L4 확인|운영(예시)|네").returncode == 0
    assert block(run_dir, "T021", ["git push origin main"]) == ""


def test_step_refuses_before_it_runs(run_dir):
    plan(run_dir, ["echo should-not-run"], "L1~L4", record=DELEGATED, title="운영 배포 계획", status=lib.kinds.DONE)
    frozen(run_dir, "T020", ["echo should-not-run"])
    assert not (run_dir.task_dir("T020") / "exec.md").exists()
    with pytest.raises(execmod.Reject, match="L4 확인"):
        tasks = lib.load_tasks(str(run_dir.path))
        execmod.require_production_check(str(run_dir.path), tasks, tasks["T020"], "실행승인", ["echo should-not-run"])


# ---------------------------------------------------------------- 화면의 줄


def test_screen_shows_the_gate_without_disturbing_answer_numbers(run_dir):
    make(run_dir, cells={"decide": DECIDE + "\n- 다른 것 [성질: 범위]\n  추천 (가): 이유"}, values="L1~L3")
    p = run_script("screen", run_dir.path, "T010", "--save")
    assert p.returncode == 0, p.output
    assert "■ 위임 L1~L3" in p.stdout and "범위" in p.stdout
    shown = (run_dir.task_dir("T010") / "screen-shown.md").read_text(encoding="utf-8")
    assert len(screen.shown_items(shown)) == len({k for k in screen.shown_items(shown)})
    assert run_script("screen", run_dir.path, "T010", "--answer", "1 가").returncode == 0


def test_screen_says_nothing_when_not_delegated(run_dir):
    make(run_dir, cells={"decide": DECIDE})
    assert "■ 위임" not in run_script("screen", run_dir.path, "T010").stdout
