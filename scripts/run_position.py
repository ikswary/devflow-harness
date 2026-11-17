"""경계 보고의 머리 칸(1.3.0, 구현 설계 2절 D, 7판 규칙 4.2): 실행 위치, 늘어난 까닭, 지금까지 방향.

- 실행 위치: task 수(백로그 뺌), 첫 task를 만든 날부터 며칠째, 끝난 배포 실행 수, 남은 task 수와 그 가운데 막혀 있는 것.
- 늘어난 까닭: 처음 계획의 task 수 → 지금 task 수와 원인별 수. 처음 계획은 실행에서 처음 사람이 승인한 계획 task
  (등록표 `FIRST_PLAN_KINDS`)의 자식이 만들어진 시각까지 있던 task 수다. 키로 찍지 않고 바뀌지 않는 `created`에서 계산하므로
  값이 고정되고 옛 실행에도 쓴다. 원인은 등록표 `GROWTH_CAUSES`(kind) → 사용자 원문 계기 → 「새로 나눈 일」 차례로 가른다.
  원인별 수의 합은 늘어난 수와 같다(사람이 맞춰 볼 필요가 없게).
- 지금까지 방향: `decisions.md`에서 결정 칸이 `[방향]`으로 시작하고 대체되지 않은 줄(최근 셋).
- 한 줄에 항목 셋을 넘기지 않는다(7판 규칙 4.2). 줄은 사람의 말로 쓰고 task id를 싣지 않는다.
- 명령행 `run_position.py {실행 폴더}`: 머리 칸 줄과 `늘어남:` 줄(없으면 `늘어남: 없음`). 메인이 경계 보고 kind 작성자의
  프롬프트 `실행 위치:`에 넣는다(formats/screen-cells.md 「늘어남 질문」, 목적 시험 T051).
"""
import os
import re
import sys
import unicodedata
from datetime import datetime

import devflow_lib
import kinds

DIRECTION = "[방향]"
NEW_SPLIT = "새로 나눈 일"
USER_CAUSE = "답하신 것으로 생긴 일"
STAMP = "%Y-%m-%d %H:%M:%S"
GROWTH_SHOWN = 3   # 「늘어난 까닭」에 보이는 원인 수. 나머지는 「그 밖」 한 줄로 합쳐 합계가 맞게(7판 규칙 4.2, 머리 칸 약 400자)
WIDTH = 14   # 머리 칸 이름의 터미널 폭(「늘어난 까닭」 10 + 여백)


def _time(value):
    try:
        return datetime.strptime(str(value or "").strip()[:19], STAMP)
    except ValueError:
        return None


def counted(tasks):
    """머리 칸이 세는 task(백로그 뺌)."""
    return {tid: t for tid, t in tasks.items() if t.get("status") != "백로그"}


def first_plan(tasks):
    """(처음 계획의 task 수, 기준 시각) 또는 (None, None). 사람이 승인한(approval_mode 승인) 계획 task 가운데 자식이 있는 첫 것."""
    plans = sorted((_time(t.get("approved")), tid) for tid, t in tasks.items()
                   if t.get("kind") in kinds.FIRST_PLAN_KINDS and str(t.get("approval_mode", "")).strip() == "승인"
                   and _time(t.get("approved")))
    for _, tid in plans:
        children = [_time(o.get("created")) for o in tasks.values() if o.get("parent") == tid and _time(o.get("created"))]
        if children:
            cut = max(children)
            return sum(1 for o in counted(tasks).values() if _time(o.get("created")) and _time(o.get("created")) <= cut), cut
    return None, None


def growth(tasks, cut):
    """처음 계획 뒤에 생긴 task의 원인별 수 [(원인, 수)] (수가 큰 차례)."""
    tally = {}
    for t in counted(tasks).values():
        made = _time(t.get("created"))
        if not made or made <= cut:
            continue
        cause = kinds.GROWTH_CAUSES.get(t.get("kind", "")) or (USER_CAUSE if devflow_lib.user_origin(t) else _split_cause(tasks, t))
        tally[cause] = tally.get(cause, 0) + 1
    return sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))


def _split_cause(tasks, t):
    """새로 나눈 일은 그 일을 낳은 앞 일의 이름으로 묶는다(사람이 무엇이 늘었는지 알게)."""
    parent = tasks.get(t.get("parent", "")) if t.get("parent") else None
    return "「{}」에서 나온 일".format(parent.get("title", "")) if parent and parent.get("title") else NEW_SPLIT


def big_growth(tasks):
    """처음 계획보다 큰 원인 하나 (원인, 수, 처음 계획 수) 또는 None. 경계 보고가 "붙일까요, 뗄까요?"를 다시 묻는다(7판 규칙 4.2)."""
    first, cut = first_plan(tasks)
    if first is None:
        return None
    causes = growth(tasks, cut)
    return (causes[0][0], causes[0][1], first) if causes and causes[0][1] > first else None


def directions(run_dir):
    path = os.path.join(run_dir, "decisions.md")
    if not os.path.isfile(path):
        return []
    out = []
    for line in devflow_lib.read_text(path).splitlines():
        if not line.startswith("- ") or "→ 대체:" in line:
            continue
        f = [c.strip() for c in line[2:].split("|")]
        if len(f) >= 2 and f[1].startswith(DIRECTION):
            quote = re.search(r'원문:\s*"([^"]*)"', line)
            text = f[1][len(DIRECTION):].strip()
            out.append("{} {}{}".format(f[0][:10], text, ' ("{}")'.format(quote.group(1)[:30]) if quote and quote.group(1) else ""))
    return out


def width(text):
    """터미널 폭(한글 등 넓은 글자는 2)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _rows(label, items, cols=WIDTH):
    """항목을 한 줄에 셋까지 ` · `로 잇고, 넘으면 다음 줄로. 이름 칸은 터미널 폭으로 맞춘다."""
    out, pad = [], " " * cols
    for i in range(0, len(items), 3):
        head = label + " " * max(1, cols - width(label)) if i == 0 else pad
        out.append(head + " · ".join(items[i:i + 3]))
    return out


def head_lines(run_dir, tasks, today=None):
    live = counted(tasks)
    made = [_time(t.get("created")) for t in live.values() if _time(t.get("created"))]
    today = today or datetime.now()
    days = (today.date() - min(made).date()).days + 1 if made else 1
    deploys = sum(1 for t in live.values() if t.get("kind") in kinds.DEPLOY_EXEC_KINDS and t.get("status") == kinds.DONE)
    left = [t for t in live.values() if t.get("status") not in kinds.CLOSED_STATUSES]
    held = [t for t in live.values() if t.get("status") == "보류"]
    where = ["task {}개".format(len(live)), "{}일째".format(days), "배포 {}회".format(deploys)]
    rest = ["남은 일 {}개".format(len(left))] + (["보류 {}개".format(len(held))] if held else [])
    lines = _rows("실행 위치", where) + _rows("", rest)
    first, cut = first_plan(tasks)
    if first is not None and len(live) > first:
        causes = growth(tasks, cut)
        lines += _rows("늘어난 까닭", ["처음 계획 {}개 → 지금 {}개".format(first, len(live))])
        shown, rest = causes[:GROWTH_SHOWN], causes[GROWTH_SHOWN:]
        if len(rest) == 1:
            shown, rest = causes, []
        lines += ["{}{} +{}".format(" " * WIDTH, cause, n) for cause, n in shown]
        if rest:
            lines.append("{}그 밖 {}가지 +{}".format(" " * WIDTH, len(rest), sum(n for _, n in rest)))
    way = directions(run_dir)
    if way:
        lines += ["지금까지 방향"] + [" " * WIDTH + w for w in way]
    return lines


def growth_line(tasks):
    big = big_growth(tasks)
    return "늘어남: {} +{}개가 처음 계획 {}개보다 큽니다".format(*big) if big else "늘어남: 없음"


def main(argv):
    if len(argv) != 2:
        print("쓰는 법: run_position.py {실행 폴더}", file=sys.stderr)
        return 2
    tasks = devflow_lib.load_tasks(argv[1])
    for line in head_lines(argv[1], tasks) + [growth_line(tasks)]:
        print(line)
    return 0


if __name__ == "__main__":
    devflow_lib.utf8_stdout()
    sys.exit(main(sys.argv))
