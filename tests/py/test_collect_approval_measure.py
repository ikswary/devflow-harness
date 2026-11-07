"""1.2.0 측정 칸(A11, 설계 10절, 11.1절 A-R): `collect.py {실행 폴더} --measure`의 넷째 줄부터.

세는 법 표본은 옛 실행과 새 실행의 꼴만 본뜬 합성 문장이다. 못 읽은 값은 0이나 없음이 아니라 `재지 못함`이다.
측정은 기록을 바꾸지 않고, 관문과 판정은 이 값을 읽지 않는다.
"""
import json
import os
from datetime import datetime

import pytest

import collect
from conftest import SCRIPTS, run_script, write
from test_code_check import BODY, FV, code, commit, make_places, repo, verify, waiting  # noqa: F401  repo는 fixture다
from test_imports import import_graph
from test_review_contract import NEW, result

V120 = "1.2.0-dev.1"
FLOW = "flow-verify"
ASKED = {"status": "완료", "approval_mode": "승인", "n_decide": "0", "n_todo": "0", "started_version": V120}
KEY1, KEY2, KEY3, KEY4 = "T010-aaaa1111", "T011-bbbb2222", "T012-cccc3333", "T013-dddd4444"


def record(when, point, decision, text):
    return '- {} | {} | {} | 원문: "{}"'.format(when, point, decision, text)


def task_with(run_dir, tid, lines=(), **meta):
    run_dir.task(tid, "측정 " + tid, {"승인 기록": "\n".join(lines)}, **dict(ASKED, **meta))


def lines_of(run_dir):
    proc = run_script("collect", run_dir, "--measure")
    assert proc.returncode == 0, proc.output
    return proc.stdout.splitlines()


def line_of(run_dir, head):
    found = [l for l in lines_of(run_dir) if l.startswith("- {}:".format(head))]
    assert len(found) == 1, (head, lines_of(run_dir))
    return found[0]


def place_block(key, card="1", where="src/a.ts:3", state="기다림", answer="", opinion="의견 없음", security="아니오", judgments=1):
    head = ["## " + key, "- 카드: " + card, "- task: " + key.split("-")[0], "- 커밋: abc1234", "- 부류: 판단", "- 보안: " + security, "- 종류: 구조",
            "- 파일: src/a.ts", "- 위치: " + where, "- 발췌: 30", "- 의견: " + opinion, "- 처리: " + state, "- 답: " + answer]
    head += ["- b{}: 구조 | {} | 합성 판단 문장".format(i + 1, where) for i in range(judgments)]
    return "\n".join(head) + "\n"


def write_places(run_dir, tid, blocks, unmeasured="없음"):
    write(run_dir.task_dir(tid) / "places.md", "# 코드 확인 곳: {} common\n\n- 위임: 없음\n- 재지 못함: {}\n- 잰 task: T010\n\n".format(tid, unmeasured)
          + "\n".join(blocks))


def show_card(run_dir, tid, key, when):
    path = write(run_dir.task_dir(tid) / "cards" / (key + ".shown.md"), "카드 첫 줄\n코드 줄\n답 줄\n")
    stamp = datetime.strptime(when, "%Y-%m-%d %H:%M:%S").timestamp()
    os.utime(path, (stamp, stamp))


def flow_with_places(run_dir, tid="T020", **meta):
    """곳 넷: 문제 없음(2분), 이 코드만 고침(1분), 판단이 둘인 섞인 답, 판단 안 됨(시각 없음)."""
    task_with(run_dir, tid, [
        record("2026-11-01 10:02:00", "코드 확인 " + KEY1, "문제 없음", "1"),
        record("2026-11-01 10:03:00", "코드 확인 " + KEY2, "이 코드만 고침 : 널 처리", "2 이 코드만 고침 : 널 처리"),
        record("2026-11-01 10:04:00", "코드 확인 " + KEY3, "b1=문제 없음 b2=판단 안 됨 호출하는 쪽 코드", "b1 1, b2 판단 안 됨 호출하는 쪽 코드"),
        record("2026-11-01 10:05:00", "코드 확인 " + KEY4, "판단 안 됨 근거 문서", "3 판단 안 됨 근거 문서"),
    ], kind=FLOW, flow="common", **meta)
    write_places(run_dir, tid, [
        place_block(KEY1, "1", state="답함", answer="문제 없음"),
        place_block(KEY2, "2", state="답함", answer="이 코드만 고침 : 널 처리", opinion="지금 문제 있음"),
        place_block(KEY3, "3", state="답함", answer="b1=문제 없음 b2=판단 안 됨 호출하는 쪽 코드", opinion="지금 문제 없음", judgments=2),
        place_block(KEY4, "4", state="남김(판단 안 됨)", answer="판단 안 됨 근거 문서"),
        place_block("T014-eeee5555", "", state="남김(상한)"),
        place_block("T015-ffff6666", "", state="남김(위임)"),
    ])
    show_card(run_dir, tid, KEY1, "2026-11-01 10:00:00")
    show_card(run_dir, tid, KEY2, "2026-11-01 10:02:00")
    show_card(run_dir, tid, KEY3, "2026-11-01 10:03:00")


# ================================================================ 질문 꼴(세는 법 표본)
@pytest.mark.parametrize("line,meta,form", [
    (record("2026-11-01 10:00:00", "승인", "승인", "승인"), {}, "task 승인"),
    (record("2026-11-01 10:00:00", "승인", "위험 수용", "그대로 둠"), {}, "task 승인"),
    (record("2026-11-01 10:00:00", "전체", "승인", "ㅇㅇ"), {}, "task 승인"),
    (record("2026-11-01 10:00:00", "답", "승인", "승인"), {}, "task 승인"),
    (record("2026-11-01 10:00:00", "보류", "보류", "나중에"), {}, "task 승인"),
    (record("2026-11-01 10:00:00", "답(고칠 것)", "수정 요청", "칸 이름을 바꿔 주세요"), {}, "task 승인"),
    ('- 2026-10-06 10:41 "승인"', {}, "task 승인"),
    (record("2026-11-01 10:00:00", "정해 주실 것 V-1", "가", "가"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "정해 주실 것 2 QY-1", "나", "나"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "D-3", "가", "가"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "Q2", "네", "네"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "FR-QY-1 준비한 단계", "가", "가"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "항목 3", "가", "3 가"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "D-3", "가", "가"), {"kind": "probe"}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "답", "Q4 (가) 문서도 함께", "가"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "답", "H-3: 위쪽 띠에 둔다", "위쪽"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "답", "첫 화면 크기 = (나) 줄인다", "나"), {}, "정해 주실 것"),
    (record("2026-11-01 10:00:00", "답", "그 파일은 그대로 둔다", "두세요"), {}, "그 밖"),
    (record("2026-11-01 10:00:00", "백로그 다시 엶", "다시 함", "다시 해요"), {}, "그 밖"),
    (record("2026-11-01 10:00:00", "승인", "실행 승인", "돌려요"), {}, "명령 단계"),
    (record("2026-11-01 10:00:00", "실행승인", "승인", "ㅇㅋ"), {}, "명령 단계"),
    (record("2026-11-01 10:00:00", "결과승인", "승인", "ㅇㅋ"), {}, "명령 단계"),
    (record("2026-11-01 10:00:00", "결과 승인", "승인", "ㅇㅋ"), {}, "명령 단계"),
    (record("2026-11-01 10:00:00", "L4 확인", "운영 환경", "올려요"), {}, "명령 단계"),
    (record("2026-11-01 10:00:00", "승인", "승인", "진행"), {"kind": "probe"}, "명령 단계"),
    (record("2026-11-01 10:00:00", "코드 확인 " + KEY1, "문제 없음", "1"), {}, "코드 확인"),
    (record("2026-11-01 10:00:00", "시험 변화", "k1=받아들임", "받아들임"), {}, "시험 변화"),
    (record("2026-11-01 10:00:00", "리뷰 이의", "항목 2", "이의 2"), {}, "리뷰 이의"),
    (record("2026-11-01 10:00:00", "리뷰 이의 철회", "항목 2", "그대로 두세요"), {}, "리뷰 이의"),
    (record("2026-11-01 10:00:00", "하실 일", "넘김", "네가 해"), {}, "하실 일"),
    (record("2026-11-01 10:00:00", "실물 확인", "[실물 확인 미룸] 화면 → dev 주소", "미룸"), {}, "하실 일"),
    (record("2026-11-01 10:00:00", "승인", "[하실 일 넘김 T003] 설정", "네가 해"), {}, "하실 일"),
    (record("2026-11-01 10:00:00", "되물음(이해)", "뜻", "뭐죠"), {}, "이해 되물음"),
    (record("2026-11-01 10:00:00", "되물음(이해) 전체", "뜻", "뭐죠"), {}, "이해 되물음"),
    (record("2026-11-01 10:00:00", "되물음(이의)", "반대", "이상한데요"), {}, "이의 되물음"),
    (record("2026-11-01 10:00:00", "변이 권한 거부", "메인이 직접 돌림", "돌려요"), {}, "그 밖"),
    ('- 2026-10-05 22:33 예외 코드: "지금대로 둠"', {}, "그 밖"),
])
def test_question_form_sample(run_dir, line, meta, form):
    task_with(run_dir, "T001", [line], **meta)
    t = run_dir.tasks()["T001"]
    assert collect.question_form(t, collect.answer_lines(t)[0]) == form


@pytest.mark.parametrize("line", [
    record("2026-11-01 10:00:00", "승인", "위임 L1~L2", "이후 전체 맡겨"),
    record("2026-11-01 10:00:00", "추천 닫음", "위임 L1: D-1 추천 가", "이후 전체 맡겨"),
    record("2026-11-01 10:00:00", "승인", "[메인] 위임", "나머지 자동 승인"),
    '- 2026-11-01 10:00:00 | 알림 | 지나감 | 원문: (알림, 답 없음)',
    record("2026-11-01 10:00:00", "점검 확인", "R2", "ㅇㅇ"),
])
def test_lines_that_are_not_a_person_answering(run_dir, line):
    task_with(run_dir, "T001", [line])
    assert collect.answer_lines(run_dir.tasks()["T001"]) == []


def test_answers_line_splits_forms_and_keeps_what_is_not_counted_visible(run_dir):
    task_with(run_dir, "T001", [record("2026-11-01 10:00:00", "되물음(이해)", "뜻", "뭐죠"), record("2026-11-01 10:01:00", "승인", "승인", "승인")])
    task_with(run_dir, "T002", [record("2026-11-01 10:02:00", "D-1", "가", "가"), record("2026-11-01 10:02:30", "승인", "승인", "좋아요")], n_decide="1")
    task_with(run_dir, "T003", [record("2026-11-01 10:03:00", "승인", "위임 L1", "이후 전체 맡겨")])
    task_with(run_dir, "T004", [record("2026-11-01 10:04:00", "되물음(이해)", "뜻", "무슨 말이죠")], status="승인대기")
    assert line_of(run_dir, "답") == "- 답: 완료 task 3, 사람 답 4, 답/task 1.33 · 완료 밖 task의 답 1줄 · 위임으로 닫은 줄 1"
    assert line_of(run_dir, "질문 꼴별 답") == "- 질문 꼴별 답: task 승인 2 · 정해 주실 것 1 · 이해 되물음 1"


def test_baseline_answers_leave_out_lines_closed_by_delegation(run_dir):
    task_with(run_dir, "T001", [record("2026-11-01 10:00:00", "승인", "위임 L1", "이후 전체 맡겨"),
                                record("2026-11-01 10:00:01", "추천 닫음", "위임 L1: D-1 추천 가", "이후 전체 맡겨")])
    task_with(run_dir, "T002", [record("2026-11-01 10:01:00", "승인", "승인", "승인")])
    row = json.loads(run_script("collect", run_dir, "--baseline").stdout)
    assert row["answers"] == 1 and row["bulk"] == 1


# ================================================================ 도장
@pytest.mark.parametrize("point,decision,stamped", [
    ("코드 확인 " + KEY1, "문제 없음", True),
    ("코드 확인 " + KEY1, "나머지 남김", True),
    ("코드 확인 " + KEY1, "이 코드만 고침 : 널 처리", False),
    ("코드 확인 " + KEY1, "판단 안 됨 근거 문서", False),
    ("코드 확인 " + KEY1, "b1=문제 없음 b2=판단 안 됨 근거 문서", False),
    ("승인", "고칠 것이 있음", False),
    ("되물음(이의)", "반대", False),
])
def test_pushed_back_counts_place_answers_that_change_something(run_dir, point, decision, stamped):
    task_with(run_dir, "T001", [record("2026-11-01 10:00:00", point, decision, "답"), record("2026-11-01 10:01:00", "승인", "승인", "승인")])
    assert collect.is_stamp(run_dir.tasks()["T001"]) is stamped


def test_flow_review_stamps_split_by_todo(run_dir):
    plain = [record("2026-11-01 10:00:00", "승인", "승인", "승인")]
    task_with(run_dir, "T001", plain, kind=FLOW)
    task_with(run_dir, "T002", [record("2026-11-01 10:00:00", "리뷰 이의", "항목 1", "이의 1")] + plain, kind=FLOW)
    task_with(run_dir, "T003", plain, kind=FLOW, n_todo="2")
    task_with(run_dir, "T004", [record("2026-11-01 10:00:00", "되물음(이해)", "뜻", "뭐죠")] + plain, kind=FLOW, n_todo="1")
    task_with(run_dir, "T005", plain, kind=FLOW, n_decide="1")
    task_with(run_dir, "T006", plain, kind=FLOW, n_todo="")
    task_with(run_dir, "T007", plain)
    assert line_of(run_dir, "흐름 리뷰 도장") == ("- 흐름 리뷰 도장: 하실 일 없음 1/3 · 하실 일 있음 1/2 · 재지 못함: 칸이 빈 흐름 리뷰 1 · 이해 되물음 1")


# ================================================================ 곳 답과 곳당 시간
def test_place_answers_and_seconds(run_dir):
    flow_with_places(run_dir)
    assert line_of(run_dir, "코드 확인") == ("- 코드 확인: 흐름 리뷰 1 · 보일 곳 4 · 보안 곳 0 · 답함 3 · 남김(판단 안 됨) 1 · 남김(상한) 1 · 남김(위임) 1"
                                         " · 보안 신호를 재지 못한 task 0")
    assert line_of(run_dir, "곳 답") == "- 곳 답: 문제 없음 1 · 이 코드만 고침 1 · 판단 안 됨 1 · 섞임 1 · 코드 도장 1/4"
    assert line_of(run_dir, "곳당 시간") == ("- 곳당 시간: 중앙값 60초, 최대 120초(잰 곳 3) · 재지 못함: 시각이 없는 곳 1 · 같은 답 연속 최대 1"
                                         " · 폴더 표 요청 0 · 재지 못함: 전체 요청(기록 없음)")


def test_lacking_material_is_listed_in_the_person_words(run_dir):
    flow_with_places(run_dir)
    assert line_of(run_dir, "판단 안 됨의 부족한 것") == "- 판단 안 됨의 부족한 것: 호출하는 쪽 코드 / 근거 문서"


def test_lacking_material_is_masked_and_clipped_for_the_table_cell(run_dir):
    task_with(run_dir, "T020", kind=FLOW)
    long_text = "password=abc123 " + "가" * 100
    write_places(run_dir, "T020", [place_block(KEY1, state="남김(판단 안 됨)", answer="판단 안 됨 " + long_text)])
    got = line_of(run_dir, "판단 안 됨의 부족한 것")
    assert "abc123" not in got and got.endswith("…") and len(got) < 100


def test_opinion_rows_show_which_answer_came_from_each(run_dir):
    flow_with_places(run_dir)
    assert line_of(run_dir, "코드 의견") == ("- 코드 의견: 지금 문제 있음 1(이 코드만 고침 1) · 지금 문제 없음 1(섞임 1)"
                                         " · 의견 없음 4(문제 없음 1, 판단 안 됨 1, 답 없음 2)")


def test_bulk_leaving_counts_as_one_answer_and_the_rest_by_state(run_dir):
    task_with(run_dir, "T020", [record("2026-11-01 10:01:00", "코드 확인 " + KEY1, "나머지 남김", "4")], kind=FLOW)
    write_places(run_dir, "T020", [place_block(KEY1, state="남김(일괄)", answer="나머지 남김"), place_block(KEY2, "2", state="남김(일괄)")])
    show_card(run_dir, "T020", KEY1, "2026-11-01 10:00:00")
    assert line_of(run_dir, "곳 답") == "- 곳 답: 나머지 남김 1 · 코드 도장 1/1"
    assert "남김(일괄) 2" in line_of(run_dir, "코드 확인")


def test_security_places_get_their_own_count_and_time(run_dir):
    task_with(run_dir, "T020", [record("2026-11-01 10:01:00", "코드 확인 " + KEY1, "문제 없음", "1"),
                                record("2026-11-01 10:05:00", "코드 확인 " + KEY2, "문제 없음", "1")], kind=FLOW)
    write_places(run_dir, "T020", [place_block(KEY1, state="답함", answer="문제 없음", security="예"), place_block(KEY2, "2", state="답함", answer="문제 없음")])
    show_card(run_dir, "T020", KEY1, "2026-11-01 10:00:00")
    show_card(run_dir, "T020", KEY2, "2026-11-01 10:02:00")
    assert "보안 곳 1" in line_of(run_dir, "코드 확인")
    assert "최대 180초(잰 곳 2) · 보안 곳 중앙값 60초(잰 곳 1)" in line_of(run_dir, "곳당 시간")


def test_same_answer_streak_follows_answer_time(run_dir):
    task_with(run_dir, "T020", [record("2026-11-01 10:0{}:00".format(i), "코드 확인 " + k, "문제 없음", a)
                                for i, (k, a) in enumerate([(KEY1, "1"), (KEY2, "1"), (KEY3, "1"), (KEY4, "1 ")])], kind=FLOW)
    write_places(run_dir, "T020", [place_block(k, str(i + 1), state="답함", answer="문제 없음") for i, k in enumerate([KEY1, KEY2, KEY3, KEY4])])
    assert "같은 답 연속 최대 4" in line_of(run_dir, "곳당 시간")


def test_tree_request_is_counted(run_dir):
    flow_with_places(run_dir)
    write(run_dir.task_dir("T020") / "cards" / (KEY1 + ".tree.md"), "표\n")
    assert "폴더 표 요청 1" in line_of(run_dir, "곳당 시간")


@pytest.mark.parametrize("shown_at", ["2026-11-01 10:05:00"])
def test_card_time_after_the_answer_is_unmeasured_not_zero(run_dir, shown_at):
    task_with(run_dir, "T020", [record("2026-11-01 10:01:00", "코드 확인 " + KEY1, "문제 없음", "1")], kind=FLOW)
    write_places(run_dir, "T020", [place_block(KEY1, state="답함", answer="문제 없음")])
    show_card(run_dir, "T020", KEY1, shown_at)   # 복사로 파일 시각이 바뀐 실행
    got = line_of(run_dir, "곳당 시간")
    assert got.startswith("- 곳당 시간: 재지 못함: 시각이 없는 곳 1") and "중앙값" not in got


def test_answer_on_the_same_second_as_the_card_is_zero(run_dir):
    task_with(run_dir, "T020", [record("2026-11-01 10:00:00", "코드 확인 " + KEY1, "문제 없음", "1")], kind=FLOW)
    write_places(run_dir, "T020", [place_block(KEY1, state="답함", answer="문제 없음")])
    path = write(run_dir.task_dir("T020") / "cards" / (KEY1 + ".shown.md"), "카드\n")
    stamp = datetime(2026, 11, 1, 10, 0, 0).timestamp() + 0.7   # 기록은 초까지만 적는다
    os.utime(path, (stamp, stamp))
    assert "중앙값 0초" in line_of(run_dir, "곳당 시간")


def test_unreadable_place_values_are_unmeasured_not_zero(run_dir):
    task_with(run_dir, "T020", kind=FLOW)
    write_places(run_dir, "T020", [place_block(KEY1, state="답함", answer=""), place_block(KEY2, "2", state="답함", answer="그럭저럭"),
                                   place_block(KEY3, "3", state="이상한 값", opinion="모름")])
    assert "읽지 못함 2" in line_of(run_dir, "곳 답")
    assert "재지 못함: 처리를 읽지 못한 곳 1" in line_of(run_dir, "코드 확인")
    assert "재지 못함: 읽지 못한 의견 1" in line_of(run_dir, "코드 의견")


def test_real_card_and_record_path_gives_the_same_values(run_dir, repo):
    """손으로 쓴 places.md가 아니라 `screen.py --places`, `--card`, `--answer`, `task_set.py --record`가 남긴 꼴을 읽는다."""
    sha = commit(repo, {"src/a.ts": BODY, "src/b.ts": BODY})
    code(run_dir, "T040", "- 합성 판단 하나 [종류: 구조] [위치: src/a.ts:3]\n- 합성 판단 둘 [종류: 오류] [위치: src/b.ts:7]\n", sha=sha)
    verify(run_dir, repo)
    got = make_places(run_dir)
    waiting(run_dir)
    for place, text in zip(got, ("3 판단 안 됨 근거 문서", "1")):
        assert run_script("task_set", run_dir.path, FV, "--card-open", place["key"]).returncode == 0
        assert run_script("screen", run_dir.path, FV, "--card", place["카드"]).returncode == 0
        solved = run_script("screen", run_dir.path, FV, "--answer", text)
        rec = next(l for l in solved.stdout.splitlines() if l.startswith("--record: "))[len("--record: "):]
        assert run_script("task_set", run_dir.path, FV, "--record", rec).returncode == 0, rec
    assert line_of(run_dir, "코드 확인") == "- 코드 확인: 흐름 리뷰 1 · 보일 곳 2 · 보안 곳 0 · 답함 1 · 남김(판단 안 됨) 1 · 보안 신호를 재지 못한 task 0"
    assert line_of(run_dir, "곳 답") == "- 곳 답: 문제 없음 1 · 판단 안 됨 1 · 코드 도장 1/2"
    assert line_of(run_dir, "판단 안 됨의 부족한 것") == "- 판단 안 됨의 부족한 것: 근거 문서"
    assert "(잰 곳 2)" in line_of(run_dir, "곳당 시간") and "재지 못함: 시각이 없는 곳" not in line_of(run_dir, "곳당 시간")
    assert line_of(run_dir, "코드 의견") == "- 코드 의견: 의견 없음 2(문제 없음 1, 판단 안 됨 1)"
    assert "카드 " in line_of(run_dir, "읽을 줄") and "카드 0줄" not in line_of(run_dir, "읽을 줄")


def test_unmeasured_head_is_counted(run_dir):
    task_with(run_dir, "T020", kind=FLOW)
    write_places(run_dir, "T020", [place_block(KEY1)], unmeasured="T010, T011")
    assert "보안 신호를 재지 못한 task 2" in line_of(run_dir, "코드 확인")


def test_flow_review_without_places_file_is_not_zero_places(run_dir):
    task_with(run_dir, "T020", kind=FLOW)
    assert line_of(run_dir, "코드 확인") == "- 코드 확인: 흐름 리뷰 1 · 곳 파일 없음 1 · 보안 신호를 재지 못한 task 0"
    assert line_of(run_dir, "곳 답").startswith("- 곳 답: 재지 못함")
    assert line_of(run_dir, "곳당 시간").startswith("- 곳당 시간: 재지 못함")


def test_old_run_has_no_code_check_values(run_dir):
    task_with(run_dir, "T020", [record("2026-10-01 10:00:00", "승인", "승인", "승인")], kind=FLOW, started_version="1.1.1")
    for head in ("코드 확인", "곳 답", "곳당 시간", "코드 의견", "전·후", "알림으로 바꾼 것"):
        assert line_of(run_dir, head).startswith("- {}: 재지 못함: 1.2.0".format(head))


# ================================================================ 읽을 줄
def test_reading_lines_add_screen_and_cards_and_mark_missing_screens(run_dir):
    flow_with_places(run_dir)
    write(run_dir.task_dir("T020") / "screen-shown.md", "화면 1\n화면 2\n")
    task_with(run_dir, "T021", [record("2026-11-01 10:00:00", "승인", "승인", "승인")])
    task_with(run_dir, "T022", [record("2026-11-01 10:00:00", "승인", "위임 L1", "이후 전체 맡겨")])
    assert line_of(run_dir, "읽을 줄") == "- 읽을 줄: 묻는 승인 2, 화면 2줄, 카드 9줄 · 재지 못함: 화면을 남기지 않은 묻는 승인 1"


def screen_file(run_dir, tid, *lines):
    write(run_dir.task_dir(tid) / "screen-shown.md", "".join(l + "\n" for l in lines))


def test_flow_reading_takes_the_largest_flow_with_screens_and_cards(run_dir):
    plain = [record("2026-11-01 10:00:00", "승인", "승인", "승인")]
    task_with(run_dir, "T001", plain, flow="aa")
    screen_file(run_dir, "T001", "가", "나")
    task_with(run_dir, "T002", plain, flow="aa")
    screen_file(run_dir, "T002", "다")
    write(run_dir.task_dir("T002") / "cards" / (KEY1 + ".shown.md"), "카드\n코드\n")
    task_with(run_dir, "T003", plain, flow="bb")
    screen_file(run_dir, "T003", "라", "마")
    task_with(run_dir, "T004", plain)   # 흐름 밖
    screen_file(run_dir, "T004", *["줄"] * 50)
    assert line_of(run_dir, "흐름당 읽을 줄") == "- 흐름당 읽을 줄: 최대 5줄(aa), 흐름 2"


def test_flow_with_a_lost_screen_is_not_the_maximum(run_dir):
    plain = [record("2026-11-01 10:00:00", "승인", "승인", "승인")]
    task_with(run_dir, "T001", plain, flow="aa")
    screen_file(run_dir, "T001", *["줄"] * 9)
    task_with(run_dir, "T002", plain, flow="aa")
    task_with(run_dir, "T003", plain, flow="bb")
    screen_file(run_dir, "T003", "가")
    assert line_of(run_dir, "흐름당 읽을 줄") == "- 흐름당 읽을 줄: 최대 1줄(bb), 흐름 1 · 재지 못함: 화면을 남기지 않은 묻는 승인이 있는 흐름 1"


@pytest.mark.parametrize("flow,want", [("", "재지 못함: 흐름에 든 task 없음"), ("aa", "재지 못함: 모든 흐름에 화면을 남기지 않은 묻는 승인이 있음")])
def test_flow_reading_unmeasured(run_dir, flow, want):
    task_with(run_dir, "T001", [record("2026-11-01 10:00:00", "승인", "승인", "승인")], flow=flow)
    assert line_of(run_dir, "흐름당 읽을 줄") == "- 흐름당 읽을 줄: " + want


def test_wrap_review_lines_per_task_and_missing_file(run_dir):
    assert line_of(run_dir, "마무리 리뷰") == "- 마무리 리뷰: 재지 못함: 마무리 task 없음"
    task_with(run_dir, "T001", kind="wrap-up")
    assert line_of(run_dir, "마무리 리뷰") == "- 마무리 리뷰: 재지 못함: 리뷰 파일이 없는 마무리 1"
    write(run_dir.task_dir("T001") / "wrap-review.md", "가\n나\n다\n")
    assert line_of(run_dir, "마무리 리뷰") == "- 마무리 리뷰: T001 3줄"


def test_missing_material_counts_screens_and_old_runs_are_not_zero(run_dir):
    task_with(run_dir, "T001", [record("2026-11-01 10:00:00", "승인", "승인", "승인")], started_version="1.1.1")
    screen_file(run_dir, "T001", "! 리뷰 자료 없음(옛 화면)")
    assert line_of(run_dir, "리뷰 자료 없음").startswith("- 리뷰 자료 없음: 재지 못함: 1.2.0")
    task_with(run_dir, "T002", [record("2026-11-01 10:00:00", "승인", "승인", "승인")])
    screen_file(run_dir, "T002", "머리", "! 리뷰 자료 없음(묻는 화면인데 작성자가 쓰지 않았다)")
    task_with(run_dir, "T003", [record("2026-11-01 10:00:00", "승인", "승인", "좋아요")])
    screen_file(run_dir, "T003", "머리", "  인용: ! 리뷰 자료 없음")
    task_with(run_dir, "T004", [record("2026-11-01 10:00:00", "승인", "승인", "네")])
    assert line_of(run_dir, "리뷰 자료 없음") == "- 리뷰 자료 없음: 묻는 화면 2 가운데 1 · 재지 못함: 화면을 남기지 않은 묻는 승인 1"


def test_saved_screen_really_carries_the_missing_material_line(run_dir):
    run_dir.task("T001", "설계", kind="design", block="설계", status="승인대기", **NEW)
    run_dir.result("T001", result(decide="- 칸 이름을 정한다 (가) 짧게 (나) 길게 추천: (가)"))
    assert "! 리뷰 자료 없음" in run_script("screen", run_dir.path, "T001", "--save").stdout
    assert line_of(run_dir, "리뷰 자료 없음") == "- 리뷰 자료 없음: 묻는 화면 1 가운데 1"


def test_masked_counts_sheet_and_cards(run_dir):
    task_with(run_dir, "T001", [record("2026-11-01 10:00:00", "승인", "승인", "승인")], started_version="1.1.1")
    assert line_of(run_dir, "가림").startswith("- 가림: 재지 못함: 1.2.0")
    task_with(run_dir, "T002", [record("2026-11-01 10:00:00", "승인", "승인", "승인")])
    write(run_dir.task_dir("T002") / "sheet.html", "<body><p>3줄을 가렸습니다.</p></body>")
    task_with(run_dir, "T003", [record("2026-11-01 10:00:00", "승인", "승인", "네")])
    write(run_dir.task_dir("T003") / "sheet.html", "<body><pre>&lt;p&gt;9줄을 가렸습니다.&lt;/p&gt;</pre></body>")
    task_with(run_dir, "T004", [record("2026-11-01 10:00:00", "승인", "승인", "좋아요")])
    write(run_dir.task_dir("T004") / "cards" / (KEY1 + ".shown.md"), "코드\n비밀값 꼴 2줄 가림\n")
    assert line_of(run_dir, "가림") == "- 가림: 한 장 2장 3줄, 카드 2줄 · 한 장 없는 묻는 승인 1(실을 자료가 없었거나 만들지 못함)"


def test_real_sheet_mask_sentence_is_counted(run_dir):
    run_dir.task("T001", "설계", kind="design", block="설계", status="승인대기", **NEW)
    run_dir.result("T001", result().replace("## 승인 화면\n", "## 승인 화면\n### 리뷰 자료\n접속 값 password=abc123 을 쓴다\n\n", 1))
    assert "1줄 가림" in run_script("visual", run_dir.path, "T001", "--sheet").stdout
    assert line_of(run_dir, "가림").startswith("- 가림: 한 장 1장 1줄")


# ================================================================ 숨은 판단
def judged_code(run_dir, tid, body, **meta):
    task_with(run_dir, tid, **dict({"kind": "implementation"}, **meta))
    if body is not None:
        write(run_dir.task_dir(tid) / "judge.md", "판정자: rjudge 2026-11-01 10:00:00\n\n## 통과 못 한 기준\n- 없음\n\n## 판단 대조\n" + body + "\n")


def test_hidden_judgments_say_what_they_stand_in_for(run_dir):
    judged_code(run_dir, "T001", "- 숨은 판단: src/a.ts:3 | 재시도를 두 번 한다 | 오류\n- 사람이 볼 곳: 지목 없음\n- 숨은 판단: src/b.ts:9 | 표를 나눈다 | 데이터")
    judged_code(run_dir, "T002", "- 없음")
    judged_code(run_dir, "T003", "- 숨은 판단: 없음")
    assert line_of(run_dir, "숨은 판단") == "- 숨은 판단: `숨은 판단:` 2줄(`[설계:]`가 어디에도 없는 줄만 가르는 꼴이 없어 전체로 대신함)"


def test_hidden_judgments_unreadable_are_unmeasured(run_dir):
    assert line_of(run_dir, "숨은 판단").startswith("- 숨은 판단: 재지 못함: 1.2.0")
    judged_code(run_dir, "T001", "- 숨은 판단: 칸이 하나뿐인 줄")
    judged_code(run_dir, "T002", None)
    judged_code(run_dir, "T003", "- 숨은 판단: src/a.ts:3 | 지금 도는 task | 오류", status="진행")
    assert line_of(run_dir, "숨은 판단") == ("- 숨은 판단: `숨은 판단:` 0줄(`[설계:]`가 어디에도 없는 줄만 가르는 꼴이 없어 전체로 대신함)"
                                         " · 재지 못함: 칸이 모자란 줄 1 · 재지 못함: 「판단 대조」가 없는 task 1")


# ================================================================ 전·후
def run_section(*scenarios):
    return "## 흐름 리뷰 전·후\n\n" + "\n".join(scenarios) + "\n\n## 통과 못 한 기준\n- 없음\n"


RAN = "### 응답 칸\n- 전: 다섯 칸\n- 후: 두 칸\n"
NO_ENV = "### 저장 화면\n- 돌리지 못함: 환경이 없음 | 기준본 저장소가 없음\n- 대신: 시험이 확인한 것\n"
PARTIAL = "### 목록 화면\n- 전: 돌리지 못함: 권한 거부\n- 후: 두 칸\n"


def flow_verify(run_dir, tid, flow, section, picked=None, **meta):
    task_with(run_dir, tid, kind=FLOW, flow=flow, **meta)
    if section is not None:
        write(run_dir.task_dir(tid) / "judge-run.md", section)
    if picked is not None:
        run_dir.result(tid, "## 승인 화면\n### 알릴 것\n- 없음\n\n## 돌려 볼 시나리오\n" + "".join("- 장면 {}\n".format(i) for i in range(picked)))


def test_before_after_lines_name_flows_and_reasons(run_dir):
    flow_verify(run_dir, "T020", "aa", run_section(RAN))
    flow_verify(run_dir, "T021", "bb", run_section(NO_ENV))
    flow_verify(run_dir, "T022", "cc", run_section(RAN, PARTIAL))
    flow_verify(run_dir, "T023", "dd", run_section("### 빈 칸\n"))
    flow_verify(run_dir, "T024", "ee", None)
    assert line_of(run_dir, "전·후") == ("- 전·후: 흐름 리뷰 5 · 전부 돌림 1 · 일부 1(cc) · 못 돌림 1(bb) · 재지 못함 2(dd, ee)"
                                       " · 이유: 환경이 없음 1, 권한 거부 1")


def test_before_after_missing_results_are_not_all_run(run_dir):
    flow_verify(run_dir, "T020", "aa", run_section(RAN), picked=3)
    assert line_of(run_dir, "전·후") == "- 전·후: 흐름 리뷰 1 · 전부 돌림 0 · 일부 1(aa) · 못 돌림 0 · 재지 못함 0 · 이유: 결과 없는 시나리오 2"


def test_before_after_missing_results_add_up_across_flows(run_dir):
    flow_verify(run_dir, "T020", "aa", run_section(RAN), picked=3)
    flow_verify(run_dir, "T021", "bb", run_section(RAN), picked=2)
    assert line_of(run_dir, "전·후").endswith("이유: 결과 없는 시나리오 3")


def test_before_after_reason_outside_the_five_is_other(run_dir):
    flow_verify(run_dir, "T020", "aa", run_section("### 저장\n- 돌리지 못함: 시간이 모자람\n"))
    assert line_of(run_dir, "전·후").endswith("이유: 그 밖 1")


def test_before_after_ignores_open_flow_reviews_but_says_so(run_dir):
    flow_verify(run_dir, "T020", "aa", run_section(RAN))
    flow_verify(run_dir, "T021", "bb", run_section(NO_ENV), status="승인대기")
    assert line_of(run_dir, "전·후") == "- 전·후: 흐름 리뷰 1 · 전부 돌림 1 · 일부 0 · 못 돌림 0 · 재지 못함 0 · 닫히지 않은 흐름 리뷰 1"


# ================================================================ 알림으로 바꾼 것
def test_notified_conversions_are_counted_and_unmeasured_ones_say_so(run_dir):
    notify = dict(approval_mode="알림")
    task_with(run_dir, "T001", kind="merge", **notify)
    task_with(run_dir, "T002", kind="merge", **notify)
    write(run_dir.task_dir("T002") / "exec.md", "- 2026-11-01 10:00:00 | 브랜치 판정 | 실행:1 | 병합(충돌 해결) | x\n")
    task_with(run_dir, "T003", kind="merge", approval_mode="승인")
    task_with(run_dir, "T004", kind="wrap-up", **notify)
    task_with(run_dir, "T005", kind="full-verify", **notify)
    task_with(run_dir, "T006", kind="full-verify", approval_mode="승인")
    task_with(run_dir, "T007", kind="change", origin="사용자 T003 2026-11-01 09:00:00", **notify)
    (run_dir.task_dir("T007") / "task.md").write_text(
        (run_dir.task_dir("T007") / "task.md").read_text(encoding="utf-8").replace("## 건드릴 파일\n(없음)", "## 건드릴 파일\ndesign/common.md"), encoding="utf-8")
    task_with(run_dir, "T008", [record("2026-11-01 10:00:00", "되물음(이의)", "반대", "이건 왜 바뀌었죠"),
                                record("2026-11-01 10:01:00", "되물음(이해)", "뜻", "무슨 뜻이죠")], kind="wrap-up", approval_mode="승인")
    assert line_of(run_dir, "알림으로 바꾼 것") == (
        "- 알림으로 바꾼 것: 합치기 2 · 합치기 충돌 수정 1 · 마무리 결과 1 · 답만 옮긴 설계 고친 판 1 · 지적 0 전체 검증 1"
        " · 마무리의 이의 1(어느 칸인지 가리지 못함) · 재지 못함: 받아오기 충돌 수정(메인 기록의 꼴 없음), 뒤에 문제가 드러난 수(기록 칸 없음)")


# ================================================================ 위임
def decisions(run_dir, *lines):
    write(run_dir.path / "decisions.md", "".join(line + "\n" for line in lines))


def test_delegation_counts_original_and_approvals_before_each(run_dir):
    task_with(run_dir, "T001", [record("2026-11-01 09:00:00", "승인", "승인", "승인"),
                                record("2026-11-01 09:10:00", "되물음(이해)", "뜻", "뭐죠"),
                                record("2026-11-01 09:20:00", "승인", "승인", "좋아요")])
    task_with(run_dir, "T002", ['- 2026-11-01 09:30 "승인"'], approval_mode="")
    task_with(run_dir, "T003", [record("2026-11-01 11:00:00", "승인", "승인", "좋습니다")])
    task_with(run_dir, "T004", [record("2026-11-01 13:00:00", "승인", "위임 L1~L2", "나머지 맡겨 | 전부")])
    decisions(run_dir,
              '- 2026-11-01 10:00:00 | 위임 L1 | 원문: "결정은 맡겨" | 확인: "네" | 실행 전체',
              '- 2026-11-01 12:00:00 | 위임 L1~L2 | 원문: "나머지 맡겨 | 전부" | 실행 전체',
              '- 2026-11-01 12:30:00 | 위임 없음 | 원문: "이제 묻고 해" | 실행 전체',
              '- 2026-11-01 12:40:00 | [메인] 위임 없음: 되물음 두 번 | 메인 판단',
              '- 2026-11-01 12:50:00 | 칸 이름을 줄인다 | 원문: "줄여요" | T001')
    assert line_of(run_dir, "위임") == ('- 위임: 횟수 2 · [메인] 줄 1 · 일괄로 닫은 task 1 · "결정은 맡겨" 직전 승인 3 · "나머지 맡겨 / 전부" 직전 승인 1')


def test_old_form_bulk_decision_is_delegation(run_dir):
    decisions(run_dir, '- 2026-10-10 10:00 | 이후 진행 | 원문: "이후 전체 자동 승인" | T010')
    assert "횟수 1" in line_of(run_dir, "위임")


def test_same_original_repeated_on_each_task_is_one_delegation(run_dir):
    decisions(run_dir,
              '- 2026-10-10 10:00 | 표를 고친다 | 원문: "나머지 자동 승인" | T010',
              '- 2026-10-10 10:05 | 칸을 줄인다 | 원문: "나머지 자동 승인" | T011',
              '- 2026-10-10 11:00 | 위임 L1 | 원문: "다시 맡겨" | 실행 전체')
    assert line_of(run_dir, "위임") == '- 위임: 횟수 2 · [메인] 줄 0 · 일괄로 닫은 task 0 · "나머지 자동 승인" 직전 승인 0 · "다시 맡겨" 직전 승인 0'


def test_same_original_after_lowering_is_a_new_delegation(run_dir):
    decisions(run_dir,
              '- 2026-11-01 10:00:00 | 위임 L1 | 원문: "맡겨" | 실행 전체',
              '- 2026-11-01 11:00:00 | 위임 없음 | 원문: "이제 묻고 해" | 실행 전체',
              '- 2026-11-01 12:00:00 | 위임 L1 | 원문: "맡겨" | 실행 전체')
    assert "횟수 2" in line_of(run_dir, "위임")


def test_delegation_with_unreadable_time_is_unmeasured(run_dir):
    decisions(run_dir, '- 어제쯤 | 위임 L1 | 원문: "맡겨" | 실행 전체')
    assert line_of(run_dir, "위임").endswith('"맡겨" 직전 승인 재지 못함')


def test_delegation_notes_approvals_whose_time_is_unreadable(run_dir):
    task_with(run_dir, "T001", ['- 앞에서 | 승인 | 승인 | 원문: "승인"'])
    decisions(run_dir, '- 2026-11-01 10:00:00 | 위임 L1 | 원문: "맡겨" | 실행 전체')
    assert line_of(run_dir, "위임").endswith("· 시각 못 읽은 승인 1줄 뺌")


def test_no_delegation_is_a_zero_count(run_dir):
    assert line_of(run_dir, "위임") == "- 위임: 횟수 0 · [메인] 줄 0 · 일괄로 닫은 task 0"


# ================================================================ 줄과 경계
def test_measure_keeps_its_first_three_lines(run_dir):
    got = lines_of(run_dir)
    assert got[0].startswith("- 결정 0 승인: ") and got[1].startswith("- 관점 지적: ") and got[2].startswith("- 멈춤: ")
    assert [l.split(":")[0] for l in got[3:]] == ["- 답", "- 질문 꼴별 답", "- 읽을 줄", "- 흐름당 읽을 줄", "- 마무리 리뷰", "- 리뷰 자료 없음", "- 가림",
                                                  "- 코드 확인", "- 곳 답", "- 곳당 시간", "- 코드 의견", "- 숨은 판단", "- 흐름 리뷰 도장", "- 전·후", "- 알림으로 바꾼 것", "- 위임", "- 한 장 올리기",
                                                  "- 계약별 리뷰", "- 직접 내린 판단", "- 설계 승인", "- 책임 경계", "- 한 장 이의", "- 시험 변화", "- 설계 뿌리 결함", "- 멈춤 그 밖"]


def test_measure_lines_fit_a_table_cell(run_dir):
    flow_with_places(run_dir)
    task_with(run_dir, "T021", [record("2026-11-01 10:00:00", "D|1", "가", "가")])
    decisions(run_dir, '- 2026-11-01 10:00:00 | 위임 L1 | 원문: "맡겨 | 전부" | 실행 전체')
    assert not [l for l in lines_of(run_dir)[3:] if "|" in l]


def test_measure_does_not_write_into_the_run(run_dir):
    flow_with_places(run_dir)
    flow_verify(run_dir, "T021", "bb", run_section(NO_ENV))
    decisions(run_dir, '- 2026-11-01 10:00:00 | 위임 L1 | 원문: "맡겨" | 실행 전체')
    def snapshot():
        return sorted((str(f), f.stat().st_mtime, f.read_bytes()) for f in run_dir.path.rglob("*") if f.is_file())
    before = snapshot()
    assert run_script("collect", run_dir, "--measure").returncode == 0
    assert snapshot() == before


def test_gates_and_judges_do_not_read_measure_values():
    graph = import_graph()
    readers = {name for name, deps in graph.items() if "collect" in deps}
    assert readers <= {"visual"}   # 표시 층의 마무리 리뷰뿐이다
    outside = [p.name for p in SCRIPTS.glob("*.py") if p.name != "collect.py" and "approval_measure" in p.read_text(encoding="utf-8")]
    assert outside == []
