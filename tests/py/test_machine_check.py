"""기계 대조 `machine_check.py`의 「건드릴 파일」 패턴 시험.

형식 `references/formats/task-file.md` 「건드릴 파일」: 한 줄에 `- 경로` 하나, `*`·`**` 가능, 설명은 괄호나 ` — ` 뒤에.
`allowed_patterns`는 줄마다 설명과 백틱을 떼고(라이브러리의 같은 떼기 `_touch_line`) 경로만 패턴으로 쓴다.
"""
import machine_check


def _task(touch):
    return {"_sections": {"건드릴 파일": touch}}


def test_description_after_dash_and_in_parens_is_dropped():
    pats = machine_check.allowed_patterns(_task("- scripts/kinds.py — brief children 한 값만\n- docs/a.md (설명)"))
    assert machine_check.matches("scripts/kinds.py", pats)
    assert machine_check.matches("docs/a.md", pats)
    assert pats == ["scripts/kinds.py", "docs/a.md"]


def test_backticks_are_dropped():
    pats = machine_check.allowed_patterns(_task("- `scripts/board.py` — 표시"))
    assert pats == ["scripts/board.py"]
    assert machine_check.matches("scripts/board.py", pats)


def test_glob_patterns_still_match_and_outside_file_does_not():
    pats = machine_check.allowed_patterns(_task("- tests/**/*.py (시험)\n- docs/* — 문서\n- scripts/\n본문 줄(목록 기호 없음) other.py"))
    assert pats == ["tests/**/*.py", "docs/*", "scripts/"]
    assert machine_check.matches("tests/py/test_x.py", pats)
    assert machine_check.matches("docs/b.md", pats)
    assert machine_check.matches("scripts/exec.py", pats)
    # 양성 대조는 위 세 줄. 목록 기호가 없는 줄의 토큰과 목록 밖 파일은 대상 밖
    assert not machine_check.matches("other.py", pats)
    assert not machine_check.matches("README.md", pats)
