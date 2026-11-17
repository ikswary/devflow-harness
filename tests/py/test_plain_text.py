"""1.3.0 A: 사람에게 가는 글의 사람의 말 검사와 글자 예산(구현 설계 2절 A, 7판 규칙 2절, U7).

- 내부 번호(`T012`, `D-3`, `AC-7`, `DG-18` 같은 꼴)는 그 글에서 처음 나올 때 바로 뒤 괄호로 풀어 쓰지 않으면 걸린다.
- `파일:줄` 근거는 펼침에만 둔다. 질문·경계 보고·알림에 있으면 걸린다.
- 하네스 용어(판정자, 탐침, 정본, 흐름별 검증, 머리 파일, 행, kind 이름)는 걸린다.
- 글자 예산(공백 포함, 줄바꿈 제외): 질문 400, 전제 질문 300, 경계 보고 본문 1,200, 머리 칸 400. 넘으면 걸린다.
- 걸림은 경고이고(U7) 화면 저장을 막지 않는다. 검사는 고치지 않는다.
"""
import pytest


@pytest.fixture(name="pt")
def _pt():
    import plain_text
    return plain_text


def test_clean_text_has_no_problem(pt):
    text = "가비아 CDN으로 계속할까요?\n(가) 계속 ← 추천   사진 한 장 2.4초 → 0.3초 기대\n(나) 그만둠"
    assert pt.problems(text, "ask") == []


@pytest.mark.parametrize("text", [
    "T051 설계를 승인할까요?", "결정 D-3을 다시 볼까요?", "기준 AC-7이 실패했습니다", "DG-18의 문구", "FR-2 범위",
])
def test_internal_number_is_flagged(pt, text):
    got = pt.problems(text, "ask")
    assert any(p.startswith("내부 번호") for p in got)


def test_internal_number_explained_once_is_fine(pt):
    text = "확인 기준 6(같은 커밋을 세 번 돌려 같은 결과)이 실패했습니다. 기준 6은 다시 돌립니다."
    assert pt.problems(text, "ask") == []
    assert any(p.startswith("내부 번호 기준 6") for p in pt.problems("확인 기준 6이 실패했습니다", "ask"))
    text = "결정 D-3(사진 주소에 폭을 넣음)을 다시 볼까요? D-3은 앞에서 정하셨습니다."
    assert pt.problems(text, "ask") == []


@pytest.mark.parametrize("text", ["근거는 worker/routes/media.ts:28 입니다", "tools/deploy/run.ts:102-131 참고"])
def test_file_line_is_flagged_outside_fold(pt, text):
    assert any(p.startswith("파일:줄") for p in pt.problems(text, "boundary"))


@pytest.mark.parametrize("word", ["판정자", "탐침", "정본", "흐름별 검증", "머리 파일", "design", "root-cause", "deploy-plan"])
def test_harness_words_are_flagged(pt, word):
    got = pt.problems("이번 {}에서 정한 것입니다".format(word), "notice")
    assert any(p.startswith("하네스 용어") and word in p for p in got)


@pytest.mark.parametrize("text", ["실행을 다시 합니다", "진행합니다", "이 행동은", "독립 확인: 맞습니다", "디자인을 바꿉니다", "deployment 문서"])
def test_ordinary_words_are_not_harness_words(pt, text):
    assert not any(p.startswith("하네스 용어") for p in pt.problems(text, "notice"))


def test_row_word_is_flagged_only_as_word(pt):
    assert any(p.startswith("하네스 용어") for p in pt.problems("자식 행을 더합니다", "notice"))
    assert any(p.startswith("하네스 용어") for p in pt.problems("행 3개를 만듭니다", "notice"))


@pytest.mark.parametrize("part,limit", [("ask", 400), ("premise", 300), ("boundary", 1200), ("head", 400)])
def test_budget(pt, part, limit):
    under = "가" * limit
    over = "가" * (limit + 1)
    assert pt.problems(under, part) == []
    got = pt.problems(over, part)
    assert len(got) == 1 and got[0].startswith("글자 수") and str(limit) in got[0]


def test_budget_counts_spaces_but_not_newlines(pt):
    assert pt.count("가 나\n다") == 4
    assert pt.count("가\n\n나") == 2


def test_notice_is_one_line(pt):
    assert any(p.startswith("알림은 한 줄") for p in pt.problems("첫 줄\n둘째 줄", "notice"))
    assert pt.problems("한 줄 알림입니다", "notice") == []


def test_unknown_part_is_an_error(pt):
    with pytest.raises(ValueError):
        pt.problems("글", "card")


@pytest.mark.parametrize("text", ["질문 Q4를 봅니다", "점검 R1이 걸림", "U7 경고", "AC7 실패", "기준 6이 실패했습니다", "가설 H6"])
def test_unhyphenated_internal_number_is_flagged(pt, text):
    assert any(p.startswith("내부 번호") for p in pt.problems(text, "ask"))


@pytest.mark.parametrize("text", [
    "AES-256으로 암호화", "RSA-2048 키", "SHA-384 해시", "ISO-8859-1 글꼴", "GPT-4 모델", "UTF-8 문서", "S3 버킷", "E2E 시험",
    "질문 1/2", "결정 3 다시", "dev 배포 0회", "4일째",
])
def test_ordinary_codes_are_not_internal_numbers(pt, text):
    assert not any(p.startswith("내부 번호") for p in pt.problems(text, "ask"))


@pytest.mark.parametrize("text", ["수정본을 올렸습니다", "개정본과 확정본", "사본을 남깁니다"])
def test_words_ending_with_bon_are_not_harness_words(pt, text):
    assert not any(p.startswith("하네스 용어") for p in pt.problems(text, "notice"))


@pytest.mark.parametrize("text", ["dev.example.kr:8443 으로 엽니다", "api.example.com:443 응답", "localhost:8787 에서", "시각 10:05"])
def test_host_port_is_not_file_line(pt, text):
    assert not any(p.startswith("파일:줄") for p in pt.problems(text, "boundary"))


@pytest.mark.parametrize("text", ["Makefile:12", "Dockerfile:3", "media.ts#L28", "media.ts 28행", "src/a.tsx:9", "db/0002_tables.sql:28"])
def test_other_file_line_forms(pt, text):
    assert any(p.startswith("파일:줄") for p in pt.problems(text, "boundary"))


@pytest.mark.parametrize("text", ["docs/design.md 문서", "https://x.kr/design/a", "design.md를 엽니다"])
def test_kind_word_inside_path_is_not_flagged(pt, text):
    assert not any(p.startswith("하네스 용어") for p in pt.problems(text, "notice"))


@pytest.mark.parametrize("text", ["자식 행들을 더합니다", "행마다 하나", "행에서 뺍니다", "행도 지웁니다", "행과 열"])
def test_row_word_with_more_particles(pt, text):
    assert any(p.startswith("하네스 용어") for p in pt.problems(text, "notice"))


@pytest.mark.parametrize("text", ["표의 2행", "28행"])
def test_numbered_row_is_not_harness_word(pt, text):
    assert not any(p.startswith("하네스 용어") for p in pt.problems(text, "notice"))
