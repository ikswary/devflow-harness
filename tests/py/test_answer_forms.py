"""1.3.0 A: 새 승인 화면의 답 꼴(구현 설계 2절 A, 7판 규칙 3.4·4.2).

- 즉시 질문: `1가`(공백 없음), `1 가`, `1 확인 먼저`, `1 펼쳐`. 여러 답은 쉼표·줄·` / `·공백으로 나눈다(`1가 2나`).
- 전제 질문: `전1 됨`, `전1 안 됨`, `전1 지금 해 보겠음`, `전1 예`, `전1 아니오`.
- 경계 보고: `진행`, `진행, 단 {조건}`, `결정 {n} 다시`, `멈춤`.
- 옛 꼴(`3 가`, `승인`, `이의 n`, `T021 ①가` 등)은 그대로 풀린다(test_shown_answer.py).
- 화면에 없는 값이나 꼴에 맞지 않는 말은 None이고 메인이 되묻는다.
"""
import pytest

ALLOWED = ("가", "나", "다", "진행", "멈춤", "승인", "확인 먼저", "펼쳐", "됨", "안 됨", "지금 해 보겠음", "예", "아니오")
WITH_TEXT = ()   # `진행`의 조건 글은 `진행, 단 …` 꼴로만 받는다(`진행 단 …`·`진행해`는 풀지 않음)


@pytest.mark.parametrize("text,want", [
    ("1가", [{"item": 1, "value": "가"}]),
    ("12나", [{"item": 12, "value": "나"}]),
    ("1 가", [{"item": 1, "value": "가"}]),
    ("1가 2나", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}]),
    ("1가 2가 3가 4가", [{"item": n, "value": "가"} for n in (1, 2, 3, 4)]),
    ("1가, 2나", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}]),
    ("1가\n2나", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}]),
    ("1 확인 먼저", [{"item": 1, "value": "확인 먼저"}]),
    ("1 가 2 나", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}]),
    ("1가, 2나 / 진행", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}, {"value": "진행"}]),
    ("1 가 2 나 / 진행", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}, {"value": "진행"}]),
    ("전1 됨, 1가 / 진행", [{"premise": 1, "value": "됨"}, {"item": 1, "value": "가"}, {"value": "진행"}]),
    ("2 펼쳐", [{"item": 2, "value": "펼쳐"}]),
])
def test_question_answers(lib, text, want):
    assert lib.parse_answer(text, ALLOWED, WITH_TEXT) == want


@pytest.mark.parametrize("text,want", [
    ("전1 됨", [{"premise": 1, "value": "됨"}]),
    ("전1 안 됨", [{"premise": 1, "value": "안 됨"}]),
    ("전2 지금 해 보겠음", [{"premise": 2, "value": "지금 해 보겠음"}]),
    ("전1 예", [{"premise": 1, "value": "예"}]),
    ("전1 아니오, 1가", [{"premise": 1, "value": "아니오"}, {"item": 1, "value": "가"}]),
])
def test_premise_answers(lib, text, want):
    assert lib.parse_answer(text, ALLOWED, WITH_TEXT) == want


@pytest.mark.parametrize("text,want", [
    ("진행", [{"value": "진행"}]),
    ("멈춤", [{"value": "멈춤"}]),
    ("결정 3 다시", [{"redo": 3}]),
    ("결정3 다시", [{"redo": 3}]),
    ("진행, 단 연장을 마친 뒤 시작", [{"value": "진행", "text": "연장을 마친 뒤 시작"}]),
    ("진행, 단 첫째, 둘째", [{"value": "진행", "text": "첫째, 둘째"}]),
    ("1가 2나 / 진행", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}, {"value": "진행"}]),
    ("1가 2가 3가 4가 / 진행, 단 11-20까지 오지 않으면 멈추고 다시 물어 주세요",
     [{"item": n, "value": "가"} for n in (1, 2, 3, 4)] + [{"value": "진행", "text": "11-20까지 오지 않으면 멈추고 다시 물어 주세요"}]),
    ("전1 지금 해 보겠음 / 1가 / 진행, 단 연장 뒤",
     [{"premise": 1, "value": "지금 해 보겠음"}, {"item": 1, "value": "가"}, {"value": "진행", "text": "연장 뒤"}]),
])
def test_boundary_answers(lib, text, want):
    assert lib.parse_answer(text, ALLOWED, WITH_TEXT) == want


@pytest.mark.parametrize("text", [
    "3개", "1가요", "1가나", "1 가 그리고 나머지는 알아서", "전1", "전1 모름", "전 1됨",
    "결정 다시", "진행해", "진행 단 조건", "진행, 단", "멈춤 해", "1가 / ", "/ 진행",
    "1가 2", "가1",
])
def test_unmatched_is_none(lib, text):
    assert lib.parse_answer(text, ALLOWED, WITH_TEXT) is None


@pytest.mark.parametrize("text,with_text,want", [
    ("판단 안 됨 구조 / 흐름", ("판단 안 됨",), [{"value": "판단 안 됨", "text": "구조 / 흐름"}]),
    ("2 판단 안 됨 a / b", ("판단 안 됨",), [{"item": 2, "value": "판단 안 됨", "text": "a / b"}]),
    ("고칠 것이 있음 : 이 줄 / 저 줄", ("고칠 것이 있음",), [{"value": "고칠 것이 있음", "text": "이 줄 / 저 줄"}]),
    ("1가 / 고칠 것이 있음 : a / b", ("고칠 것이 있음",), [{"item": 1, "value": "가"}, {"value": "고칠 것이 있음", "text": "a / b"}]),
])
def test_slash_inside_text_is_not_split(lib, text, with_text, want):
    """`/`로 나누는 것은 왼쪽이 새 답 꼴일 때뿐이다. 글을 받는 답의 글 안 `/`는 그대로 글이다(1.2.x 답이 바뀌지 않음)."""
    assert lib.parse_answer(text, ALLOWED + ("판단 안 됨", "고칠 것이 있음"), with_text) == want


def test_progress_text_only_when_allowed(lib):
    """`진행`을 받지 않는 화면(옛 task 화면)에서는 `진행, 단 …`도 풀지 않는다."""
    assert lib.parse_answer("진행, 단 조건", ("승인", "가")) is None
    assert lib.parse_answer("진행", ("승인", "가")) is None


@pytest.mark.parametrize("decision,want", [
    ("진행", True), ("진행 : 연장을 마친 뒤", True), ("진행, 단 연장을 마친 뒤", True),
    ("진행, 단 결제 기능은 보류", True), ("진행, 단 거절 문구는 그대로", True), ("진행, 단 되돌림 방법을 먼저 적어 주세요", True),
    ("멈춤", False), ("결정 3 다시", False), ("진행 보류", False), ("진행, 멈춤", False), ("진행중", False), ("진행하지 않음", False),
])
def test_progress_counts_as_approval(lib, decision, want):
    line = '- 2026-11-16 10:00:00 | 경계 보고 | {} | 원문: "{}"'.format(decision, decision)
    assert lib.approval_line(line) is want


OLD_SHOWN = "■ 정해 주실 것 (1)\n- [1] 무엇을 고를지 (가) 이쪽 (나) 저쪽\n\ncounts: n_decide=1\n"


@pytest.mark.parametrize("text", ["결정 1 다시", "전1 됨", "결정1 다시"])
def test_old_screen_does_not_take_new_forms(text):
    """1.2.x 화면(번호 단 항목)에는 전제·경계 답이 없다. 새 꼴은 되물음이고 `전체: `로 풀리지 않는다."""
    import screen
    assert screen.resolve_answer(OLD_SHOWN, "T001", text) is None


@pytest.mark.parametrize("text,want", [("1가", ["항목 1: 가 | 무엇을 고를지 (가) 이쪽 (나) 저쪽"]), ("1 가", ["항목 1: 가 | 무엇을 고를지 (가) 이쪽 (나) 저쪽"])])
def test_old_screen_takes_tight_item(text, want):
    """공백 없는 `1가`는 옛 화면에서도 `1 가`와 같이 풀린다."""
    import screen
    assert screen.resolve_answer(OLD_SHOWN, "T001", text) == want



@pytest.mark.parametrize("text,want", [
    ("1 가 / 2 나", [{"item": 1, "value": "가"}, {"item": 2, "value": "나"}]),
    ("1가 / 2 빼고 승인", [{"item": 1, "value": "가"}, {"except": 2, "value": "승인"}]),
    ("2 나 / 고칠 것이 있음 : a / b", [{"item": 2, "value": "나"}, {"value": "고칠 것이 있음", "text": "a / b"}]),
])
def test_old_forms_joined_by_slash(lib, text, want):
    assert lib.parse_answer(text, ALLOWED + ("고칠 것이 있음",), ("고칠 것이 있음",)) == want


@pytest.mark.parametrize("text", ["전1 문제 없음", "전1 1", "전2 이 코드만 고침 : 줄 이름", "결정 1 다시", "진행", "1가"])
def test_card_does_not_take_new_forms(text):
    """코드 확인 카드의 답에는 전제·경계·즉시 질문 꼴이 없다. 앞붙임이 말없이 떨어지지 않는다."""
    import places
    place = {"판단": [{"b": "b1"}], "처리": "기다림", "보안": "아니오"}
    assert places.resolve(place, text) is None


def test_unchosen_counts_tight_answer_in_record(run_dir):
    """결정 칸에 `1가`로 적힌 앞 답은 항목 1을 고른 것이다. `3개` 같은 말은 그 글자가 선택지일 때만 닫는다."""
    import devflow_lib
    import screen
    shown = "■ 정해 주실 것 (2)\n- [1] 하나 (가) 이쪽 (나) 저쪽\n- [2] 둘 (가) 이쪽 (나) 저쪽\n\ncounts: n_decide=2\n"
    run_dir.task("T001", "시험 T001", sections={"승인 기록": '- 2026-11-16 10:00:00 | 승인 | 1가 | 원문: "1가"'})
    t = devflow_lib.load_tasks(str(run_dir.path))["T001"]
    assert screen.unchosen_items(t, shown, ["전체: 승인"]) == [2]
    run_dir.task("T002", "시험 T002", sections={"승인 기록": '- 2026-11-16 10:00:00 | 승인 | 3개 고침 | 원문: "3개 고침"'})
    t = devflow_lib.load_tasks(str(run_dir.path))["T002"]
    assert screen.unchosen_items(t, shown, ["전체: 승인"]) == [1, 2]
