r"""결정 요약: 실행의 `decisions.md`에서 대체되지 않은 결정을 한 줄씩 뽑는다.

재개한 메인이 `decisions.md` 전문을 읽으면 결정마다 원문과 이유까지 컨텍스트에 실린다. 메인은 이 요약만 보고,
전문이 필요한 결정은 줄 앞의 시각으로 `decisions.md`에서 찾는다.

사용:
  python decisions.py {실행 폴더} --brief
    첫 줄  `결정 {n}개 (대체 {m}개 뺌). 전문은 decisions.md에서 시각으로 찾는다`
    결정마다 `- {시각} | {결정 칸의 첫 문장}`(대체된 결정은 뺀다)
    끝 줄  `형식 밖 {k}줄: {시각, …}`(형식에 맞지 않는 비지 않은 줄이 있을 때만)
  결정 줄은 `- `로 시작하고 `|`가 둘 이상이며 셋째 칸(앞뒤 공백을 뗀 칸)이 `원문:`으로 시작하고 둘째 칸(결정 칸)이
  task id 꼴(`T` 뒤 ASCII 숫자 `[0-9]`만이고 전각 같은 유니코드 숫자는 아니다. 쉼표·공백·쉼표와 공백으로 이은
  `T015,T016`·`T015, T016`·`T015 T016` 포함)이 아닌 줄,
  결정 칸에 `|`가 든 줄(`- t | A | B | 원문: "x" | T1`)은 `run-files.md`의 칸 차례대로 셋째 칸이 `B`라 형식 밖으로 센다.
  결정이 `T`로 시작하는 일반 낱말(`Test 추가`, `T자형 배치`)이면 task id 꼴이 아니라 형식 안이다.
  대체된 결정은 `→ 대체:`가 든 결정 줄이다(대체 판별이 `원문:` 칸 판별보다 앞선다).
  형식 밖 줄의 시각은 `- ` 뒤 첫 `|` 앞 글(앞뒤 공백을 뗌)이고, `- `로 시작하지 않거나 `|`가 없는 줄은 줄 앞 30자다.
  결정 칸은 첫 `|`와 둘째 `|` 사이, 첫 문장은 그 칸에서 첫 `. ` 앞까지(마침표는 남김, 없으면 칸 전체).
  `decisions.md`가 없으면 `결정 0개 (decisions.md 없음)`.
  종료 코드: 0 정상, 2 사용법 오류
"""
import os
import re
import sys

import devflow_lib

SUPERSEDED = "→ 대체:"
TASK_ID_CELL = re.compile(r"T[0-9]+(?:(?:\s*,\s*|\s+)T[0-9]+)*")


def first_sentence(cell):
    """결정 칸의 첫 문장: 첫 `. ` 앞까지(마침표 포함). 없으면 칸 전체."""
    cut = cell.find(". ")
    return cell if cut < 0 else cell[:cut + 1]


def malformed_label(line):
    """형식 밖 줄을 알아볼 글: `- ` 뒤 첫 `|` 앞(앞뒤 공백 뗌). `- `로 시작하지 않거나 `|`가 없으면 줄 앞 30자."""
    if line.startswith("- ") and "|" in line:
        return line[2:].split("|")[0].strip()
    return line[:30]


def brief_lines(text):
    """(출력 줄 목록, 남긴 결정 수, 뺀 대체 수, 형식 밖 줄 수)를 돌려준다."""
    kept, superseded, malformed = [], 0, []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith("- ") or line.count("|") < 2:
            malformed.append(malformed_label(line))
            continue
        if SUPERSEDED in line:
            superseded += 1
            continue
        cells = line[2:].split("|")
        if len(cells) < 3 or not cells[2].strip().startswith("원문:") or TASK_ID_CELL.fullmatch(cells[1].strip()):
            malformed.append(malformed_label(line))
            continue
        kept.append("- {} | {}".format(cells[0].strip(), first_sentence(cells[1].strip())))
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
