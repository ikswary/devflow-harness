r"""결정 요약: 실행의 `decisions.md`에서 대체되지 않은 결정을 한 줄씩 뽑는다.

재개한 메인이 `decisions.md` 전문을 읽으면 결정마다 원문과 이유까지 컨텍스트에 실린다. 메인은 이 요약만 보고,
전문이 필요한 결정은 줄 앞의 시각으로 `decisions.md`에서 찾는다.

사용:
  python decisions.py {실행 폴더} --brief
    첫 줄  `결정 {n}개 (대체 {m}개 뺌). 전문은 decisions.md에서 시각으로 찾는다`
    결정마다 `- {시각} | {결정 칸의 첫 문장}`(대체된 결정은 뺀다). 원문 없는 둘째 꼴 줄은 끝에 ` (원문 없음)`,
      대체 표지가 아닌 `대체` 낱말이 든 줄은 끝에 ` (대체 언급)`(숨기지 않는다. 어느 줄을 대체했는지는 전문에서 본다)
    끝 줄  `형식 밖 {k}줄: {시각, …}`(형식에 맞지 않는 비지 않은 줄이 있을 때만)
  둘째 꼴(run-files.md): `- {시각} [T…] {결정}. 원문: "…"`. `{시각}`은 `YYYY-MM-DD HH:MM[:SS]`이고 그 뒤가 `|`로
  시작하지 않는 줄이다. 앞의 `[T…]` 머리(없어도 됨)를 떼고 `원문:` 앞을 결정으로 읽는다. `원문:`이 없으면
  줄 끝까지가 결정이고 ` (원문 없음)`을 단다. 결정이 비면 형식 밖이다.
  칸 꼴 결정 줄은 `- `로 시작하고 `|`가 둘 이상이며 셋째 칸(앞뒤 공백을 뗀 칸)이 `원문:`으로 시작하고 둘째 칸(결정 칸)이
  task id 꼴(`T` 뒤 ASCII 숫자 `[0-9]`만이고 전각 같은 유니코드 숫자는 아니다. 쉼표·가운뎃점(`·`)·공백(둘레 공백
  허용)으로 이은 묶음 `T015,T016`·`T015, T016`·`T015 T016`·`T040·T041·T042`·`T040 · T041`, 끝에 쉼표·가운뎃점이 남은
  `T015,`, 구분자 없이 붙은 `T015T016` 포함)이 아닌 줄,
  결정 칸에 `|`가 든 줄(`- t | A | B | 원문: "x" | T1`)은 `run-files.md`의 칸 차례대로 셋째 칸이 `B`라 형식 밖으로 센다.
  결정이 `T`로 시작하는 일반 낱말(`Test 추가`, `T자형 배치`)이면 task id 꼴이 아니라 형식 안이다.
  소문자 `t015`는 하네스 task id 표기가 아니므로 형식 안이다.
  대체된 결정은 대체 표지(`→ 대체:`와 공백·콜론 변형 `→대체:`·`→ 대체 :`·`→ 대체`)가 든 결정 줄이다(두 꼴 모두.
  대체 판별이 `원문:` 칸 판별보다 앞선다).
  형식 밖 줄의 시각은 `- ` 뒤 첫 `|` 앞 글(앞뒤 공백을 뗌)이고, `- `로 시작하지 않거나 `|`가 없는 줄은 줄 앞 30자다.
  결정 칸은 첫 `|`와 둘째 `|` 사이, 첫 문장은 그 칸에서 첫 `. ` 앞까지(마침표는 남김, 없으면 칸 전체).
  `decisions.md`가 없으면 `결정 0개 (decisions.md 없음)`.
  종료 코드: 0 정상, 2 사용법 오류
"""
import os
import re
import sys

import devflow_lib

SUPERSEDED = "→ 대체:"   # 쓰는 꼴(run-files.md). collect.py가 이 글자로 찾는다
SUPERSEDED_MARK = re.compile(r"→\s*대체\s*:?")   # 읽는 꼴: 공백·콜론 변형도 대체 표지다(D-19)
TASK_ID_CELL = re.compile(r"T[0-9]+(?:(?:\s*[,·]\s*|\s+)?T[0-9]+)*(?:\s*[,·])?")
TIME_HEAD = re.compile(r"- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)(\s.*)?$")
TASK_TAG = re.compile(r"\[T[^\]]*\]\s*")
NO_ORIGINAL = " (원문 없음)"
REPLACE_MENTION = " (대체 언급)"


def first_sentence(cell):
    """결정 칸의 첫 문장: 첫 `. ` 앞까지(마침표 포함). 없으면 칸 전체."""
    cut = cell.find(". ")
    return cell if cut < 0 else cell[:cut + 1]


def malformed_label(line):
    """형식 밖 줄을 알아볼 글: `- ` 뒤 첫 `|` 앞(앞뒤 공백 뗌). `- `로 시작하지 않거나 `|`가 없으면 줄 앞 30자."""
    if line.startswith("- ") and "|" in line:
        return line[2:].split("|")[0].strip()
    return line[:30]


def head_form(line):
    """둘째 꼴(`- {시각} [T…] {결정}. 원문: "…"`, 원문 없는 `- {시각} {글}` 포함)이면 (시각, 결정, 원문 있음), 아니면 None.
    시각 뒤가 `|`로 시작하면 칸 꼴이다. 결정이 비면 ("", "", False)."""
    m = TIME_HEAD.match(line)
    rest = (m.group(2) or "").strip() if m else ""
    if not rest or rest.startswith("|"):
        return None
    body = TASK_TAG.sub("", rest, count=1) if TASK_TAG.match(rest) else rest
    cut = body.find("원문:")
    decision = (body if cut < 0 else body[:cut]).strip()
    return (m.group(1), decision, cut >= 0) if decision else ("", "", False)


def brief_lines(text):
    """(출력 줄 목록, 남긴 결정 수, 뺀 대체 수, 형식 밖 줄 수)를 돌려준다."""
    kept, superseded, malformed = [], 0, []
    for line in text.splitlines():
        if not line.strip():
            continue
        head = head_form(line)
        if head is None and (not line.startswith("- ") or line.count("|") < 2):
            malformed.append(malformed_label(line))
            continue
        if SUPERSEDED_MARK.search(line):
            superseded += 1
            continue
        mention = REPLACE_MENTION if "대체" in line else ""
        if head is not None:
            when, decision, original = head
            if not decision:
                malformed.append(malformed_label(line))
                continue
            kept.append("- {} | {}{}{}".format(when, first_sentence(decision), "" if original else NO_ORIGINAL, mention))
            continue
        cells = line[2:].split("|")
        if len(cells) < 3 or not cells[2].strip().startswith("원문:") or TASK_ID_CELL.fullmatch(cells[1].strip()):
            malformed.append(malformed_label(line))
            continue
        kept.append("- {} | {}{}".format(cells[0].strip(), first_sentence(cells[1].strip()), mention))
    lines = ["결정 {}개 (대체 {}개 뺌). 전문은 decisions.md에서 시각으로 찾는다".format(len(kept), superseded)] + kept
    if malformed:
        lines.append("형식 밖 {}줄: {}".format(len(malformed), ", ".join(malformed)))
    return lines, len(kept), superseded, len(malformed)


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) != 3 or argv[2] != "--brief":
        print(__doc__)
        return 2
    path = os.path.join(argv[1], "decisions.md")
    if not os.path.isfile(path):
        print("결정 0개 (decisions.md 없음)")
        return 0
    lines = brief_lines(devflow_lib.read_text(path))[0]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
