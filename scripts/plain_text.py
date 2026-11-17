"""사람에게 가는 글(질문, 경계 보고, 알림, 머리 칸)의 사람의 말 검사와 글자 예산(1.3.0, 구현 설계 2절 A, 7판 규칙 2절).

걸린 것을 문장 목록으로 돌려주기만 하고 고치지 않는다. 걸림은 경고다(U7: 화면 저장을 막지 않고, 메인이 작성자에게 한 번 고치게 한다).

- 내부 번호: task id(`T012`), 대문자 접두어 번호(`D-3`, `AC-7`, `DG-18`, `Q4`, `R1`, `H6`), 판정 기준 번호(`기준 6`).
  그 글에서 처음 나올 때 바로 뒤 괄호로 풀어 쓰면 통과. 일반 표기(`UTF-8`, `AES-256`, `S3`)는 빼고, 화면 자신의 번호
  (`질문 1`, `결정 3`, `전1`)는 내부 번호가 아니다.
- `파일:줄`: 코드·문서 파일의 `:줄`, `#L줄`, ` 줄행`. 근거는 펼침에만 둔다. 호스트:포트는 아니다.
- 하네스 용어: 판정자(→ 독립 확인), 탐침, 정본, 흐름별 검증, 머리 파일, 행, kind 이름(경로·주소 안의 낱말은 아님).
- 글자 예산: 공백 포함, 줄바꿈 제외. 알림은 한 줄.
"""
import re

import kinds

BUDGET = {"ask": 400, "premise": 300, "boundary": 1200, "head": 400, "notice": None}
INTERNAL_NUMBER = re.compile(
    r"(?<![A-Za-z0-9_-])(T\d{3,}|[A-Z]{1,4}-\d+(?:-\d+)*|[A-Z]{1,3}\d{1,3})(?![A-Za-z0-9_])"
    r"|(?<![가-힣])(기준\s*\d+)(?![0-9])")
COMMON_PREFIX = ("UTF", "SHA", "AES", "RSA", "ISO", "GPT", "HTTP", "TLS", "CVE", "MD", "IPV")   # 일반 표기의 접두어
COMMON_CODES = {"S3", "A4", "B2", "H2O"}
EXT = r"(?:pyi|py|tsx|ts|jsx|js|mjs|cjs|md|jsonc|json|yml|yaml|toml|sql|sh|ps1|scss|css|html|go|java|kts|kt|rs|rb|php|cs|swift|txt|ini|cfg|env|vars|lock|xml|gradle)"
FILE_LINE = re.compile(
    r"(?:[\w./\\-]*[\w-]\.{}(?![A-Za-z0-9])|(?:[\w./\\-]*[/\\])?(?:Makefile|Dockerfile))"
    r"(?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?|\s\d+(?:-\d+)?행)".format(EXT))
HARNESS_WORDS = ("판정자", "탐침", "정본", "흐름별 검증", "머리 파일")
ROW_WORD = re.compile(r"(?<![가-힣0-9])행(?:들|을|이|의|은|에서|에|으로|로|마다|도|과|만|까지)*(?![가-힣])")


def count(text):
    """글자 수: 공백 포함, 줄바꿈 제외."""
    return len((text or "").replace("\r", "").replace("\n", ""))


def _kind_word(name):
    return re.compile(r"(?<![A-Za-z0-9_./\\-]){}(?![A-Za-z0-9_./\\-])".format(re.escape(name)))


KIND_WORDS = [(name, _kind_word(name)) for name in sorted(kinds.KINDS, key=len, reverse=True)]
HARNESS_PATTERNS = [(w, re.compile(r"(?<![가-힣]){}".format(re.escape(w)))) for w in HARNESS_WORDS]


def _common(code):
    return code in COMMON_CODES or ("-" in code and code.split("-")[0] in COMMON_PREFIX)


def _internal_numbers(text):
    seen, out = set(), []
    for m in INTERNAL_NUMBER.finditer(text):
        code = " ".join((m.group(1) or m.group(2)).split())
        if _common(code) or code in seen:
            continue
        seen.add(code)
        if not re.match(r"\s?[(（]", text[m.end():]):
            out.append("내부 번호 {}: 처음 나올 때 뜻을 괄호로 풀어 쓴다".format(code))
    return out


def problems(text, part):
    """걸린 것의 문장 목록. part는 ask / premise / boundary / head / notice."""
    if part not in BUDGET:
        raise ValueError("모르는 글의 종류: {}".format(part))
    text = text or ""
    out = []
    for m in FILE_LINE.finditer(text):
        out.append("파일:줄 {}: 근거 줄은 펼침에 둔다".format(m.group(0).strip()))
    out += _internal_numbers(FILE_LINE.sub(" ", text))   # 파일 이름 안의 글자는 번호가 아니다
    for word, pattern in HARNESS_PATTERNS:
        if pattern.search(text):
            out.append("하네스 용어 '{}': 뜻으로 쓴다{}".format(word, "(독립 확인)" if word == "판정자" else ""))
    if ROW_WORD.search(text):
        out.append("하네스 용어 '행': 무엇을 만드는지 뜻으로 쓴다")
    for name, pattern in KIND_WORDS:
        if pattern.search(text):
            out.append("하네스 용어 '{}': kind 이름 대신 그 일을 사람의 말로 쓴다".format(name))
    limit = BUDGET[part]
    if limit is not None and count(text) > limit:
        out.append("글자 수 {} > {}: 줄이거나 펼침으로 옮긴다".format(count(text), limit))
    if part == "notice" and "\n" in text.strip():
        out.append("알림은 한 줄이다")
    return out
