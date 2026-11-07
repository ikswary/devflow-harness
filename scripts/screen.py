"""승인 화면의 재료를 모은다. 작성자의 result.md 「승인 화면」 절, 판정자의 judge.md, 자식 목록의 한 줄을 읽는다.

메인은 이 출력을 사용자에게 보여 주고(AskUserQuestion의 본문), 마지막 `counts:` 줄의 값을 머리 파일에 적는다.
맨 끝 `메인 컨텍스트:` 줄은 메인이 보고 SKILL.md 8절대로 한다(사용자 화면에는 옮기지 않는다).
결과 본문은 읽지 않는다(탐침의 기록 표는 알림 조건을 위해 읽는다). 표본 대조는 메인이 따로 한다.

화면에서 이 스크립트가 하는 일(메인은 result.md를 고치지 않는다):
- 판정자의 「칸 분류 확인」대로 항목을 옮긴다(formats.md 5절의 줄 형식).
- `main-run.md`에 같은 기준의 "직접 실행 … 통과"가 있는 판정불가는 세지 않고 「건수만」에 "메인 직접 실행 n"으로 둔다.
- 기록 점검(devflow_lib.record_check): 이 task의 걸림은 「정해 주실 것」 맨 위, 끝난 task의 걸림과 표 밖 전이는 「알릴 것」.
- 판정 기준 정정: 사용자 답이 출처면 「답하신 것의 반영」, 작성자·판정자가 출처면 「정해 주실 것」.
- 판정불가 꼬리표(SKILL.md 2절 표): `대상:`은 「확인 안 된 것」으로 옮겨 알림을 막지 않는다. `대상: 기준선 없음 {명령}`은
  decisions.md에 "기준선 질문 {명령}"이 없으면 「정해 주실 것」에 기준선 질문 한 항목을 더한다. `환경:`은 머리 줄에 센다.
- 마무리·합치기: 보류와 보류에 막힌 task를 「알릴 것」에 "[보류로 남김]"으로(합치기는 그 흐름의 것만).
- 통과 못 한 코드 task: 커밋 안내 한 줄(`no_change: true`면 없음)과 이 task에 의존하는 대기 task.
- 메인용 두 블록(머리 파일 「넘길 이상 신호」, judge.md 「확인 방법 요약」)은 한 줄로 줄이고 전문은 `tasks\\{id}\\screen-main.md`에 쓴다.
  "메인이 처리할 것"은 `MAIN_SIGNAL_WORDS` 가운데 하나가 든 이상 신호 항목이다. 요약 줄 아래에 첫 줄이 `PREMISE_MARK`로
  시작하는 항목 전부(자르지 않음), 이어서 메인이 처리할 항목 전부(앞 SUMMARY_CHARS자)를 한 줄씩 낸다(둘 다 드는 항목은 앞에만).
- 재개 바닥 알림: journal.md의 마지막 `재개 바닥 {n}K` 메모가 150K 이상이고 그 뒤 `바닥 알림` 메모가 없으면
  `counts:` 줄 앞에 `! 재개 바닥` 줄을 내고 journal에 `바닥 알림 {n}K` 메모를 더한다(재개마다 한 번).
- 재검증의 수정 행이 수정 세대 상한에 닿으면 「정해 주실 것」에 상한 항목((가) 만들기/(나) 백로그/(다) 설계 변경)을 더한다.
- 사용자 원문을 계기로 만든 코드 task(`origin: 사용자 …`)는 알림 불가. 1.2.0부터 시작한 코드 task는 판정 기준이 그 옮김을 보면 알림(코드 확인에서 온 수정은 묻는다).
- 영역 규칙(1.1.0부터 시작한 task): 코드 task의 「건드릴 파일」이 프로젝트 설정 「경로 목록」의 인프라 경로에 들면 알림 불가.
  「경로 목록」의 `감지한 실행`이 이 실행이고 다른 task에 승인 요청·승인이 없으면 「알릴 것」 뒤에 `- [경로 목록]` 줄
  (칸 수·`counts:`에 넣지 않음, 알림이면 알림 줄에도).
- 탐침: 결과에 `## 탐침 기록` 절이 없으면(계획) 알림 불가, 있으면 그 표에 가정 행이 없거나 판정 칸의 첫 낱말이 `참`이 아닌 행이 있을 때 알림 불가.
- 자식 목록의 셈(행·kind·[백로그]·안별)을 `셈:` 줄로 보이고, 여섯 칸과 `나눈 기준:` 줄의 "자식 N행/M종" 꼴 주장이 셈과 다르면
  `! 수치 대조` 줄, 제목이 같은 행이면 `! 같은 제목 자식 행` 줄을 낸다. 칸 내용·칸별 수·`counts:`·알림 조건은 그대로다.
- 1.2.0부터 시작한 설계와 설계 고친 판: 7.2절 칸 차례, 성질 붙은 「알릴 것」 먼저, 「건수만」의 자식 행과 코드를 볼 task 수, 끝 질문 줄.
  같은 실행의 요구사항 상세가 모두 닫히기 전에는 묻지 않는다(`board.summary_wait`, `--save` 거부).
- 1.2.0: 재사용한 배포 계획은 머리에 재사용·다시 씀·이번 실행 몫의 수를 싣고, 명령과 되돌리기를 번호와 표시를 붙여 모두 보인다(deploy_reuse.py).
- 1.2.0: 답이나 판정자 대안 문장만 옮긴 고친 판(자식 행과 결정 번호가 그대로)은 알림이고, 그 한 줄을 뒤의 묻는 화면에 싣는다.
- 1.2.0: 다른 형제 상세가 모두 닫힌 요구사항 상세의 화면에 `■ 요구사항 종합`을 싣는다(들여 찍어 번호가 없다).
- 1.2.0: 묻는 화면은 사람이 볼 것을 앞에 둔다. 리뷰 자료(본문 안 첫 제목 앞까지, 나머지는 한 장이 있을 때 접음)가 칸보다 먼저이고, 메인용 줄(이상 신호, 확인 방법)은 `counts:` 앞으로 민다.
  전제 변경 줄이 있으면 이상 신호는 맨 위에 남는다. 칸별 수는 머리의 `볼 곳:`과 `counts:`가 대신하고, 「건수만」과 항목이 둘 이상인 「답하신 것의 반영」은 번호 없는 한 줄이다.
- 1.2.0: 흐름별 검증은 설계 7.1절 차례로 낸다(`flow_review.py`). 머리 뒤 `답할 것`과 `코드 n군데` 줄, `■ 이 흐름이 한 일`, `■ 실제로 돌려 본 결과`, 시험 변화, 번호 붙은 동작 문장,
  칸들, `근거(접어 둠)` 줄. 돌리지 못한 시나리오는 「확인 안 된 것」에 더한다. 칸 밖의 줄은 들여 찍어 `--answer` 해석에 칸으로 읽히지 않는다.
- 작성자가 쓰고 판정자가 옮긴 「정해 주실 것」 수(스크립트가 덧붙인 항목 제외)가 「이번 실행의 값」 한 승인의 결정 수 상한(0이면 없음)을 넘고 1.1.0부터 시작한 task이면 `! 결정 수 상한` 줄을 낸다(`counts:`는 그대로).

사용:
  python screen.py {실행 폴더} {task id}
  python screen.py {실행 폴더} --baseline
    실행 판정자의 baseline-run.md로 기준선 화면을 낸다. 실패가 0이면 묻지 않는다고 낸다.
  python screen.py {실행 폴더} {task id} --save
    묻기 직전에 쓴다. `승인대기`이면 화면을 tasks\\{id}\\screen-shown.md에 남기고 그 시각을 머리 파일 asked_at에 적는다.
  python screen.py {실행 폴더} {task id} --answer "원문"
    답의 꼴(`3 가`, `T021 승인`, `이의 4`, `2 빼고 승인`, `나머지 남김`)을 남긴 화면으로 푼다. 쓰지 않는다.
    글은 한 줄이고 여러 task의 답은 줄로 나눈다. 종료 3이면 메인은 해석하지 않고 되묻는다. 답을 적은 뒤 다시 물으면 다시 --save 한다.
    머리 파일 card_open이 찼으면 그 카드의 답으로 풀고 `--record` 값을 찍는다(맨 숫자는 그 카드의 답 번호).
  python screen.py {실행 폴더} --delegate "원문"
    위임 원문의 층을 읽는다. 넓히는 말이면 행을 쓰지 않고 delegation-pending.md에 적어 사용자에게 확인받을 문장을 낸다.
    줄이거나 없애는 말이면 바로 「이번 실행의 값」 `위임` 행과 decisions.md에 쓴다.
    종료 3이면 맡긴 것으로 보지 않고 쓰지도 않는다. 메인은 한 번 되묻고, 그 답도 못 읽으면 위임 없이 간다.
  python screen.py {실행 폴더} --delegate-confirm "사람의 답"
    짧은 긍정 답일 때만 대기한 층을 행과 decisions.md에 쓴다. 그 밖의 답은 대기를 지우고 종료 3이다. `task_set.py --record`, `--save`, `--card`도 대기를 지운다.
  python screen.py {실행 폴더} --delegate-clear "이유"
    위임 행을 `없음`으로 내린다. 사용자의 말이 아니므로 decisions.md에 원문 없는 `[메인]` 줄로 적는다.
  python screen.py {실행 폴더} {흐름별 검증 id} --places --remeasure [--tried "메인이 한 일"]
    재지 못한 task만 보안 신호와 시험 변화를 다시 재어 곳을 더한다. 이미 답한 곳과 키는 바꾸지 않는다. 그래도 남으면 묻는 줄을 낸다.
  python screen.py {실행 폴더} {흐름별 검증 id} --places
    흐름의 코드 판단을 곳으로 묶어 tasks\\{id}\\places.md에 고정한다(승인대기 앞에 돌린다). 그 뒤로는 이 파일만 읽는다.
  python screen.py {실행 폴더} {흐름별 검증 id} --card [n] [--full] [--tree]
    카드 한 장을 일반 메시지 재료로 낸다. n이 없으면 card_open의 카드. 처음 낸 장을 tasks\\{id}\\cards\\{키}.shown.md에 남긴다.
    --full은 코드 약 60줄, --tree는 그 판단 폴더의 파일과 줄 수 표를 앞에 붙인다.
  python screen.py {실행 폴더} {흐름별 검증 id} --flow-commands
    흐름 리뷰의 전·후를 돌릴 명령의 원천을 낸다(recon.md, 승인된 실행 전체 설계, 운영 표지, 검증 제외). 실행 판정자의 프롬프트에 그대로 넣는다.
"""
import contextlib
import io
import os
import re
import sys
from pathlib import Path
from datetime import datetime

import board
import delegation
import deploy_reuse
import devflow_lib
import flow_review
import kinds
import places

# 알림 정책은 등록표: 사람이 판단할 칸(정해 주실 것·하실 일)만 보고 알림을 정하는 종류 `kinds.NOTIFY_BY_DECIDE_KINDS`
# (1.2.0 앞에 시작한 변경 task는 사용자 답이 계기가 아닐 때만. 지운 번호 글자만 맞춘 변경을 승인으로 올려 사용자가
# "내가 뭘 보고 승인하라는거야"), 알림으로 지나갈 수 있는 종류 `kinds.NOTIFY_KINDS`(SKILL.md 3절. 그 밖은 언제나 승인),
# 화면에 알림 종류로도 보이지 않는 종류 `kinds.NEVER_NOTIFY_KINDS`. 화면의 칸 `kinds.CELLS`, 세는 칸 `kinds.COUNT_CELLS`.
KEY_RE = re.compile(r"(기준|변이)\s*(\d+)")
ADD_PROPERTY = re.compile(r"^-\s*성질 더함\s*:\s*(.*)$")
MOVE_RE = re.compile(r"^-\s*(.+?)\s*→\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*)$")
# 칸 안 문장의 자식 수 주장을 뽑는 꼴 셋. 꼴 밖의 숫자(줄 번호, task id, 다른 셈)는 보지 않는다.
# 꼴 1: `자식` 바로 뒤(사이에 `행`·`task`·공백만) 숫자 + 개/행. 꼴 2: 숫자 + 개/행 바로 뒤(공백·`의`만) `자식`. 꼴 3: {a}행 + 구분 하나 + {b}종
CLAIM_ROW_RES = (re.compile(r"자식(?:[ \t]|행|task)*(?<!\d)(\d+)(?:개|행)"),
                 re.compile(r"(?<!\d)(\d+)(?:개|행)(?:[ \t]|의)*자식"))
CLAIM_PAIR_RE = re.compile(r"(?<!\d)(\d+)행[/·, \t](\d+)종")
CLAIM_NOTE = "(메인은 결과를 고치지 않는다. 작성자에게 「승인 화면」만 다시 쓰게 하거나 셈 값을 함께 보인다)"
# 메인이 처리할 이상 신호의 낱말(공통 계약 「실행을 흔들지 않는다」·「우회하지 않는다」). 요약 줄은 앞 SUMMARY_CHARS자까지
MAIN_SIGNAL_WORDS = ("권한 거부", "자원 대기", "PID", "잠금")
SUMMARY_CHARS = 100
# 메인이 승인 대기 task에 적는 전제 변경 줄의 표지(references/kinds/change/main-order.md). 사용자가 승인 전에 볼 줄이라 자르지 않는다
PREMISE_MARK = "[전제 바뀜]"
STARTED_PREFIX = "(작성 시작 뒤) "   # 메인이 승인 전 시작한 task의 표지 앞에 붙이는 접두(references/main/selfcheck.md)
FLOOR_RE = re.compile(r"^재개 바닥 (\d+)K")
# 화면 줄과 journal 메모. 메인용 요약 두 줄(main_summary), 통과 못 한 기준의 머리와 커밋 안내, 재개 바닥 알림
SIGNALS_HEAD = "■ 이상 신호 {}건 · 메인이 처리할 것 {}건 → {}"
METHOD_HEAD = "■ 자체 검증의 확인 방법: {}"
FAILED_HEAD = "■ 자체 검증에서 통과 못 한 기준"
COMMIT_HINT = ("커밋: 변경 task로 고침·원인 분석을 고르면 지금 변경을 커밋한 위에서 고칩니다. "
               "보류를 고르면 커밋하지 않은 변경을 패치로 치울지 함께 묻습니다.")
FLOOR_ALERT = "! 재개 바닥 {}K({}K 이상): 하네스 밖 도구 정의가 큼. 이 프로젝트에 필요 없는 MCP 서버를 끄면 줄어듦"
FLOOR_NOTED = "바닥 알림 {}K"   # floor_alert가 앞부분으로 이미 알렸는지 읽는다
# 탐침 알림을 막는 이유 셋(probe_block). 시험이 같은 상수로 기대값을 만든다
PROBE_PLAN_BLOCK = "탐침 계획(「탐침 기록」 절 없음)은 늘 승인"
PROBE_NO_ROWS = "탐침 기록 표에 가정 행 없음"
PROBE_NOT_TRUE = "탐침 가정 참 아님 {}"
PROBE_LEAVES = "탐침이 남기는 것 `{}`은 결과 승인을 늘 묻는다"
FINDING_ID = re.compile(r"(?<![\w-])(?!AC-|FR-)[A-Z]{1,2}-\d+")   # 지적 ID(`V-03`, `N-02`). 인수 기준 번호는 지적이 아니다
DOUBT_TITLE = "근거 부족"


def children_lines(result_text):
    import spawn_children
    criterion, children = spawn_children.parse_children(result_text)
    if criterion is None:
        return None, []
    return criterion, ["- {} [{}]{} {}".format(c["title"], c["meta"].get("kind", ""),
                                             " (안 {})".format(c["meta"]["option"]) if c["meta"].get("option") else "",
                                             c["meta"].get("한 줄", "")) for c in children]


def child_facts(children):
    """자식 목록 행(`spawn_children.parse_children`의 항목)의 셈.
    행은 합치지 않는다. 비교 집합은 전체 / `[백로그]` 뺀 행 / 안마다(안 없는 행 + 그 안이 든 행) / 안마다 `[백로그]` 뺀 행이고,
    종류는 같은 부분 집합마다의 서로 다른 kind 수다."""
    import spawn_children

    def backlog(c):
        return c["title"].lstrip().startswith("[백로그]")

    def kind_of(c):
        return c["meta"].get("kind", "").strip()

    options = []
    for c in children:
        for o in spawn_children.row_options(c):
            if o not in options:
                options.append(o)
    subsets = [list(children), [c for c in children if not backlog(c)]]
    by_option = {}
    for o in options:
        rows = [c for c in children if not spawn_children.row_options(c) or o in spawn_children.row_options(c)]
        by_option[o] = len(rows)
        subsets += [rows, [c for c in rows if not backlog(c)]]
    kinds_n, live_kinds = {}, {}
    for c in children:
        kinds_n[kind_of(c)] = kinds_n.get(kind_of(c), 0) + 1
        if not backlog(c):
            live_kinds[kind_of(c)] = live_kinds.get(kind_of(c), 0) + 1
    titles = {}
    for c in children:
        titles[c["title"].strip()] = titles.get(c["title"].strip(), 0) + 1
    return {
        "rows": len(children), "backlog": sum(1 for c in children if backlog(c)), "options": by_option,
        "kinds": kinds_n, "n_kinds": len(kinds_n), "live_kinds": live_kinds,
        "row_set": sorted({len(s) for s in subsets}), "kind_set": sorted({len({kind_of(c) for c in s}) for s in subsets}),
        "same_titles": [(k, n) for k, n in titles.items() if n > 1],
    }


def facts_line(facts):
    """`셈:` 줄(만들 task 목록 바로 뒤)."""
    parts = ["[백로그] {}".format(facts["backlog"])] + ["안 {}: {}".format(o, n) for o, n in facts["options"].items()]
    kinds_part = ", ".join("{} {}".format(k or "kind 없음", n) for k, n in facts["kinds"].items())
    return "셈: 자식 행 {} ({}) · 종류 {}{}".format(facts["rows"], ", ".join(parts), facts["n_kinds"],
                                                " ({})".format(kinds_part) if kinds_part else "")


def unit_claims(text):
    """글 조각 하나의 주장 [(행|종류, 값, 조각)]. 같은 숫자를 여러 꼴이 잡으면 한 주장이고, 조각은 겹친 꼴을 합친 글이다."""
    found = {}
    spans = []
    for rx in CLAIM_ROW_RES:
        for m in rx.finditer(text):
            found.setdefault(("행", m.start(1)), int(m.group(1)))
            spans.append((m.start(), m.end()))
    for m in CLAIM_PAIR_RE.finditer(text):
        found.setdefault(("행", m.start(1)), int(m.group(1)))
        found.setdefault(("종류", m.start(2)), int(m.group(2)))
        spans.append((m.start(), m.end()))
    clusters = []
    for a, b in sorted(spans):
        if clusters and a < clusters[-1][1]:
            clusters[-1][1] = max(clusters[-1][1], b)
        else:
            clusters.append([a, b])
    out = []
    for (what, pos), value in sorted(found.items(), key=lambda x: (x[0][1], x[0][0])):
        a, b = next(c for c in clusters if c[0] <= pos < c[1])
        out.append((what, value, text[a:b]))
    return out


def count_claims(screen_cells, criterion, facts):
    """「승인 화면」 여섯 칸(판정자 칸 분류로 옮긴 뒤)과 `나눈 기준:` 줄에서 4.3의 꼴로 뽑은 주장 가운데 셈의 비교 집합에
    없는 것. [(칸, 주장 조각, 행|종류, 주장 값, 셈 값, 비교 집합)]."""
    if not facts:
        return []
    units = []
    for cell in kinds.CELLS:
        head, its = items(screen_cells.get(cell, ""))
        units += [(cell, "\n".join(head))] + [(cell, "\n".join(it)) for it in its]
    units.append(("나눈 기준", criterion or ""))
    out = []
    for cell, text in units:
        for what, value, frag in unit_claims(text):
            total, allowed = (facts["rows"], facts["row_set"]) if what == "행" else (facts["n_kinds"], facts["kind_set"])
            if value not in allowed:
                out.append((cell, frag, what, value, total, tuple(allowed)))
    return out


def cmd_line_warnings(run_dir, tasks, t):
    """cmd 줄(「정해 주실 것」, 배포 계획은 「되돌리기」도) 가운데 exec.py 실행 전 확인(exec.line_problems)에 걸릴 줄.
    줄이 도는 task·지점·폴더는 exec.screen_lines가 exec.py와 같은 함수로 정한다."""
    import exec as execmod
    return ["- {} — {}".format(line, "; ".join(bad)) for line, bad in execmod.screen_lines(run_dir, tasks, t) if bad]


def claim_lines(claims, facts):
    """`counts:` 줄 앞에 낼 경고 줄(같은 제목 행, 수치 대조)."""
    lines = ["! 같은 제목 자식 행 {} {}".format(title, n) for title, n in (facts or {}).get("same_titles", [])]
    lines += ["! 수치 대조: {} 「{}」 — 셈 {} {}(비교 집합 {}) {}".format(
        cell, frag, what, total, ", ".join(str(v) for v in allowed), CLAIM_NOTE)
        for cell, frag, what, _, total, allowed in claims]
    return lines


def fix_cap_item(run_dir, tasks, t, result_text):
    """재검증의 수정 행이 수정 세대 상한에 닿으면 「정해 주실 것」에 올릴 한 항목. spawn_children.py가 같은 값으로 거부한다."""
    if t.get("kind") != "reverify":
        return []
    import spawn_children
    _, children = spawn_children.parse_children(result_text)
    fixes = [c for c in children if c["meta"].get("kind") == "fix" and not spawn_children.parked(c)]
    gen, cap = devflow_lib.child_fix_generation(tasks, t), devflow_lib.fix_cap(run_dir)
    if not fixes or gen is None or gen < cap:
        return []
    return ["- [수정 세대 상한] 수정 세대 상한({})에 닿았습니다: 이 재검증의 수정 {}건(세대 {})을 (가) 그대로 만들기 / "
            "(나) 받아들이고 백로그로 / (다) 설계 변경 task로. 고친 수정의 재검증에서 또 수정이 나와, 같은 곳을 도는지 "
            "사람이 볼 때입니다".format(cap, len(fixes), gen)]


def items(text):
    """칸 글을 항목(맨 앞 `- ` 줄과 그 아래 들여쓴 줄) 목록으로. 항목 앞의 글은 첫 항목에 붙이지 않고 버리지 않는다."""
    out, head = [], []
    for line in (text or "").splitlines():
        if line.startswith("- "):
            out.append([line])
        elif out:
            out[-1].append(line)
        else:
            head.append(line)
    return head, out


def join_items(head, its):
    lines = list(head)
    for it in its:
        lines += it
    return "\n".join(lines).strip()


def item_key(text):
    m = KEY_RE.search(text)
    return m.group(1) + m.group(2) if m else None


def main_run_resolved(task_dir):
    """main-run.md에서 "직접 실행"이고 결과에 "통과"가 있는 기준 키({"기준3", "변이1"})."""
    p = os.path.join(task_dir, "main-run.md")
    keys = set()
    if not os.path.isfile(p):
        return keys
    for line in devflow_lib.read_text(p).splitlines():
        if not line.startswith("- "):
            continue
        f = [c.strip() for c in line[2:].split("|")]
        if len(f) >= 4 and f[1] == "직접 실행" and "통과" in f[3]:
            for m in KEY_RE.finditer(f[2]):
                keys.add(m.group(1) + m.group(2))
    return keys


def unresolved_failed(text, resolved):
    """「통과 못 한 기준」에서 main-run.md로 푼 판정불가 항목을 뺀 글과 뺀 수."""
    head, its = items(text)
    keep, dropped = [], 0
    for it in its:
        body = "\n".join(it)
        k = item_key(body)
        if k and k in resolved and "판정불가" in body:
            dropped += 1
            continue
        keep.append(it)
    return join_items([], keep), dropped


def table_blocks(table, resolved, allow_target=False):
    """판정 표에 알림을 막는 행(실패, 꼬리표 없는 판정불가)이 있나. `대상` 판정불가는 실행 판정의 표에서만 막지 않는다
    (그 행은 table_targets가 「확인 안 된 것」으로 옮긴다)."""
    for line in table.splitlines():
        if "| 판정불가" not in line and "| 실패" not in line:
            continue
        if allow_target and devflow_lib.table_tag(line) == "대상":
            continue
        first = line.strip().strip("|").split("|")[0].strip()
        k = item_key(first) or ("기준" + first if first.isdigit() else None)
        if "| 실패" not in line and k and k in resolved:
            continue
        return True
    return False


def apply_property_adds(screen, judge_top):
    """판정자 「칸 분류 확인」의 `- 성질 더함: {항목 앞부분} {성질}` 줄대로 그 항목 첫 줄에 성질을 더한다(옮긴 뒤의 칸에서 찾는다).
    재시도를 낳지 않는다. 읽지 못한 줄 목록을 돌려주고, 그 줄은 옮기지 못한 줄처럼 알림을 막는다."""
    failed = []
    for line in judge_top.get("칸 분류 확인", "").splitlines():
        m = ADD_PROPERTY.match(line.strip())
        if not m:
            continue
        words = m.group(1).rsplit(None, 1)
        prefix, name = (words[0].strip().strip("\"'`「」"), words[1]) if len(words) == 2 else ("", "")
        found = False
        for cell in devflow_lib.DERIVED_CELLS:
            head, its = items(screen.get(cell, ""))
            hit = next((it for it in its if not devflow_lib.MOVED_ITEM.match(it[0]) and it[0][2:].strip().startswith(prefix)), None) \
                if len(prefix) >= 4 and name in devflow_lib.ADDABLE_PROPERTIES else None
            if hit is not None:
                if name not in devflow_lib.item_properties("\n".join(hit)):
                    hit[0] += " [성질: {}]".format(name)
                screen[cell] = join_items(head, its)
                found = True
                break
        if not found:
            failed.append(line.strip())
    return failed


def apply_moves(screen, judge_top):
    """판정자 「칸 분류 확인」의 `- {원래 칸} → {옮길 칸} | {항목 앞부분} | {이유}` 줄대로 항목을 옮긴다.
    (옮긴 수, 옮기지 못한 줄 목록)을 돌려준다."""
    moved, failed = 0, []
    for line in judge_top.get("칸 분류 확인", "").splitlines():
        line = line.strip()
        if not line.startswith("- ") or devflow_lib.EMPTY_ITEM.match(line) or ADD_PROPERTY.match(line):
            continue
        if "→" not in line:
            continue   # 옮길 것이 아닌 설명 줄(옛 판정의 37%에 있었다). 알림을 막지 않는다
        m = MOVE_RE.match(line)
        if not m or m.group(1) not in kinds.CELLS or m.group(2) not in kinds.CELLS:
            failed.append(line)
            continue
        src, dst, prefix = m.group(1), m.group(2), m.group(3).strip().strip("\"'`「」")
        head, its = items(screen.get(src, ""))
        hit = next((it for it in its if it[0][2:].strip().startswith(prefix)), None) if len(prefix) >= 4 else None
        if hit is None:
            failed.append(line)
            continue
        its.remove(hit)
        screen[src] = join_items(head, its) or "- 없음"
        dhead, dits = items(screen.get(dst, ""))
        dits = [it for it in dits if not devflow_lib.EMPTY_ITEM.match(it[0].strip())]
        dits.append(hit + ["  (판정자 칸 분류: {} → {})".format(src, dst)])
        screen[dst] = join_items(dhead, dits)
        moved += 1
    return moved, failed


def add_items(screen, cell, lines, top=False):
    if not lines:
        return
    head, its = items(screen.get(cell, ""))
    its = [it for it in its if not devflow_lib.EMPTY_ITEM.match(it[0].strip())]
    new = [[l] for l in lines]
    screen[cell] = join_items(head, new + its if top else its + new)


def table_targets(table, known):
    """실행 판정 표의 `대상` 판정불가 행을 「확인 안 된 것」 항목 줄로(같은 기준이 항목에 이미 있으면 뺀다)."""
    out = []
    for line in table.splitlines():
        if devflow_lib.table_tag(line) != "대상":
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        k = item_key(cells[0]) or ("기준" + cells[0] if cells[0].isdigit() else cells[0])
        if k not in known:
            out.append("- [판정불가 대상] {}: {}(판정 표)".format(k.replace("기준", "기준 ").replace("변이", "변이 "), cells[-1]))
    return out


def split_tagged(text, allow_target=True):
    """「통과 못 한 기준」 글을 (남길 글, 대상: 항목 줄 목록, 환경: 항목 수)로 가른다.
    `대상`은 실행 판정(judge-run.md)의 항목에서만 받는다. 읽기 판정의 `대상`은 꼬리표 없음(알림을 막음)."""
    head, its = items(text)
    keep, target, env = [], [], 0
    for it in its:
        body = "\n".join(it)
        tag = devflow_lib.undecided_tag(body)
        if tag == "대상" and not allow_target:
            tag = None
        if tag == "대상":
            target.append(body)
            continue
        if tag == "환경":
            env += 1
        keep.append(it)
    return join_items([], keep), target, env


def baseline_questions(run_dir, target_items):
    """`대상: 기준선 없음 {명령}` 가운데 decisions.md에 "기준선 질문 {명령}"이 아직 없는 명령(중복 없이)."""
    p = os.path.join(run_dir, "decisions.md")
    asked = devflow_lib.read_text(p) if os.path.isfile(p) else ""
    out = []
    for body in target_items:
        m = devflow_lib.BASELINE_RE.search(body)
        if not m:
            continue
        cmd = m.group(1).strip()
        if cmd and "기준선 질문 " + cmd not in asked and cmd not in out:
            out.append(cmd)
    return out


def held_lines(tasks, t):
    """마무리·합치기 화면 「알릴 것」에 붙일 "[보류로 남김]" 줄(합치기는 그 흐름의 것만)."""
    if t.get("kind") not in ("wrap-up", "merge"):
        return []
    holds = devflow_lib.hold_blockers(tasks)
    out = []
    for o in tasks.values():
        if o is t or not (o.get("status") == "보류" or o["id"] in holds):
            continue
        if t.get("kind") == "merge" and o.get("flow") != t.get("flow"):
            continue
        why = "보류" if o.get("status") == "보류" else "보류에 막힘: " + ", ".join(holds[o["id"]])
        out.append("- [보류로 남김] {} {} ({})".format(o["id"], o.get("title", ""), why))
    return out


def amendments(t):
    """머리 파일 「판정 기준 정정」의 줄 [(출처, 줄, 원문과 고친 문장의 다른 줄)]."""
    out = []
    for line in t["_sections"].get("판정 기준 정정", "").splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        m = re.search(r"출처:\s*([^|]+)", line)
        before = re.search(r"원문:\s*(criteria\.[\w.]+\.md)", line)
        after = re.search(r"고친 문장:\s*(criteria\.[\w.]+\.md)", line)
        sub = []
        if before and after:
            pa, pb = (os.path.join(t["_dir"], x.group(1)) for x in (before, after))
            if os.path.isfile(pa) and os.path.isfile(pb):
                sub = devflow_lib.text_diff(devflow_lib.read_text(pa), devflow_lib.read_text(pb))
        out.append(((m.group(1).strip() if m else ""), line[2:], sub))
    return out


def probe_block(top):
    """탐침의 알림을 막는 이유(없으면 빈 글). 계획(「탐침 기록」 절 없음)은 늘 승인, 기록은 가정 행이 없거나 판정 칸의 첫 낱말이 `참`이 아닌 행이 있으면 승인."""
    if "탐침 기록" not in top:
        return PROBE_PLAN_BLOCK
    rows = [[c.strip() for c in line.strip().strip("|").split("|")]
            for line in top["탐침 기록"].splitlines() if line.strip().startswith("|")]
    col = rows[0].index("판정") if rows and "판정" in rows[0] else 1
    rows = [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]   # 머리 아래 구분선 줄은 가정 행이 아니다
    if not rows:
        return PROBE_NO_ROWS
    def verdict(r):   # 판정 칸의 첫 낱말(굵게 `*`·백틱·괄호 앞까지). `판정불가(로그 없음)`도 `판정불가`로 읽는다
        m = re.match(r"[\s*`]*([^\s*`(（]*)", r[col] if len(r) > col else "")
        return m.group(1)
    bad = sum(1 for r in rows if verdict(r) != "참")
    return PROBE_NOT_TRUE.format(bad) if bad else ""


def main_summary(t, judge_top):
    """메인용 두 블록의 (이상 신호 줄 목록, 확인 방법 줄, screen-main.md 본문). 두 블록이 다 비면 ([], None, None)."""
    signals = t["_sections"].get("넘길 이상 신호", "")
    signals = "" if signals == "(없음)" else signals
    method = judge_top.get("확인 방법 요약", "")
    if not signals and not method:
        return [], None, None
    signal_lines, method_line = [], None
    path = "tasks\\{}\\screen-main.md".format(t["id"])   # 골든이 운영체제와 무관하게 글자 그대로
    if signals:
        head, its = items(signals)
        its = [it for it in its if not devflow_lib.EMPTY_ITEM.match(it[0].strip())]
        if not its and "".join(head).strip():
            its = [["- " + " ".join(l.strip() for l in head if l.strip())]]   # `- ` 항목 없이 쓴 글은 한 건
        todo = [it for it in its if any(w in "\n".join(it) for w in MAIN_SIGNAL_WORDS)]
        signal_lines.append(SIGNALS_HEAD.format(len(its), len(todo), path))
        def first(it):   # 항목 첫 줄. 맨 앞 접두는 건너뛴다
            f = it[0][2:].strip()
            return f[len(STARTED_PREFIX):].lstrip() if f.startswith(STARTED_PREFIX) else f
        premise = [it for it in its if first(it).startswith(PREMISE_MARK)]
        signal_lines += ["  " + first(it) for it in premise]
        signal_lines += ["  " + it[0][2:].strip()[:SUMMARY_CHARS] for it in todo if it not in premise]
    if method:
        first = next((l.strip() for l in method.splitlines() if l.strip()), "")
        method_line = METHOD_HEAD.format(first[:SUMMARY_CHARS])
    body = "# {} 메인용 전문\n\n## 이상 신호\n{}\n\n## 자체 검증의 확인 방법\n{}\n".format(
        t["id"], signals or "- 없음", method or "- 없음")
    return signal_lines, method_line, body


def floor_alert(run_dir):
    """journal.md의 마지막 `재개 바닥 {n}K` 메모의 n이 CTX_FLOOR_NOTE 이상이고 그 뒤 `바닥 알림` 메모가 없으면 n, 아니면 None.
    `재개 바닥 측정 불가(…)` 메모도 마지막 바닥으로 센다(값이 없어 알리지 않음)."""
    p = os.path.join(run_dir, "journal.md")
    if not os.path.isfile(p):
        return None
    floor, alerted = None, False
    for line in devflow_lib.read_text(p).splitlines():
        cells = [c.strip() for c in line[2:].split("|")] if line.startswith("- ") else []
        if len(cells) < 4 or cells[1] != "메모":
            continue
        note = "|".join(cells[3:]).strip()
        if note.startswith("재개 바닥"):
            m = FLOOR_RE.match(note)
            floor, alerted = (int(m.group(1)) if m else None), False
        elif note.startswith(FLOOR_NOTED.split("{}")[0].rstrip()):
            alerted = True
    if floor is None or alerted or floor * 1000 < devflow_lib.CTX_FLOOR_NOTE:
        return None
    return floor


def hidden_findings(unverified, body):
    """칸이 비어도 지적인 것: 「확인 안 된 것」으로 넘긴 지적 ID와 「본문」의 근거 부족(설계 7.6절의 지적 0을 가른다)."""
    if FINDING_ID.search(unverified or ""):
        return True
    doubt = devflow_lib.sections(body or "", level=3).get(DOUBT_TITLE, "")
    return bool(devflow_lib.item_count(doubt))


def own_cell_items(cell, text, v120):
    """알림 판단과 칸 수에 넣는 글. 옮겨 온 줄을 빼는 칸은 `MOVED_CELLS`뿐이다."""
    return devflow_lib.without_moved_items(text) if v120 and cell in devflow_lib.MOVED_CELLS else text


def build(run_dir, tid, tasks=None):
    """화면 재료를 계산한다. 출력 없이 dict를 돌려준다(task_set.py가 알림 조건을 볼 때도 쓴다)."""
    tasks = tasks or devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        return {"error": "task를 찾지 못함: " + tid}
    t = tasks[tid]
    result_md = os.path.join(t["_dir"], "result.md")
    if not os.path.isfile(result_md):
        return {"error": "result.md가 없음"}
    result_text = devflow_lib.read_text(result_md)
    top = devflow_lib.sections(result_text, level=2)
    screen = devflow_lib.sections(top.get("승인 화면", ""), level=3)
    missing = [c for c in kinds.CELLS if c not in screen]

    judge_top = {}
    judge_md = os.path.join(t["_dir"], "judge.md")
    if os.path.isfile(judge_md):
        judge_top = devflow_lib.sections(devflow_lib.read_text(judge_md), level=2)
    # 실행 판정(judge-run.md)도 「통과 못 한 기준」 절을 읽는다(formats.md 5절)
    run_md = os.path.join(t["_dir"], "judge-run.md")
    run_failed = ""
    if os.path.isfile(run_md):
        run_failed = devflow_lib.sections(devflow_lib.read_text(run_md), level=2).get("통과 못 한 기준", "")
    # 묻는 단계(1.1.1부터: 합치기 실행승인 등)는 그 stage 앞에 필요한 판정만 본다(task_set.py 관문과 같은 함수)
    judges_ok, judges_why = devflow_lib.judges_present(t, devflow_lib.stage_of(t))
    resource_wait = str(t.get("external_progress", "")).strip() if str(t.get("external_progress", "")).startswith("자원 대기:") else ""
    unparsed = [cell for cell in kinds.COUNT_CELLS if devflow_lib.unparsed_cell(screen.get(cell, ""))]

    moved, move_failed = apply_moves(screen, judge_top)
    if devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        move_failed += apply_property_adds(screen, judge_top)
        # 끌어낸 성질을 칸에 더한다(설계 5.2절). 수와 알림 판단은 그대로이고, 위험은 선택지가 있는 칸에서만 끌어낸다
        for cell in devflow_lib.DERIVED_CELLS:
            if cell in screen:
                screen[cell] = delegation.mark_derived(screen[cell], cell == "정해 주실 것")
    claim_cells = dict(screen)   # 주장은 작성자가 쓰고 판정자가 옮긴 칸에서만 뽑는다(아래에서 스크립트가 더하는 줄은 보지 않는다)

    resolved = main_run_resolved(t["_dir"])
    read_failed, by_read = unresolved_failed(judge_top.get("통과 못 한 기준", ""), resolved)
    exec_failed, by_run = unresolved_failed(run_failed, resolved)
    by_main = by_read + by_run
    if by_main:
        add_items(screen, "건수만", ["- 메인 직접 실행 {}(main-run.md)".format(by_main)])
    read_failed, _, env_read = split_tagged(read_failed, allow_target=False)
    exec_failed, target, env_run = split_tagged(exec_failed, allow_target=True)
    failed = "\n".join(x for x in (read_failed, exec_failed) if x)
    env_n = env_read + env_run
    run_table = devflow_lib.sections(devflow_lib.read_text(run_md), level=2).get("판정 표", "") if os.path.isfile(run_md) else ""
    known = {item_key(b.splitlines()[0]) for b in target}
    add_items(screen, "확인 안 된 것", ["- [판정불가 대상] " + b.splitlines()[0][2:].strip() for b in target]
              + table_targets(run_table, known))
    add_items(screen, "정해 주실 것", [
        "- [기준선 질문] `{}`의 원래 실패를 recon.md 「기준선」에 넣을지: (가) 넣음 — 기준선에 적고 같은 판정을 다시 돌림"
        " / (나) 넣지 않음 — 이 판정불가는 「확인 안 된 것」으로 둠 (묻는 턴에 decisions.md에 \"기준선 질문 {} {}\")".format(c, c, tid)
        for c in baseline_questions(run_dir, target)], top=True)
    add_items(screen, "알릴 것", held_lines(tasks, t))
    add_items(screen, "정해 주실 것", fix_cap_item(run_dir, tasks, t, result_text), top=True)

    # 기록 점검: 이 task의 걸림은 정해 주실 것 맨 위, 끝난 task의 걸림과 표 밖 전이는 알릴 것
    own, notes = [], []
    for otid, code, msg, sub in devflow_lib.record_findings(tasks):
        line = "- [기록 점검] {} {}: {}".format(otid, code, msg) + "".join("\n  " + s for s in sub)
        if code.startswith("U"):
            notes.append(line)
        elif otid == tid and t.get("status") not in kinds.CLOSED_STATUSES:
            own.append(line)
        elif tasks[otid].get("status") in kinds.CLOSED_STATUSES:
            notes.append(line)
    add_items(screen, "정해 주실 것", own, top=True)

    decide_amend, answer_amend = [], []
    for source, line, sub in amendments(t):
        body = "".join("\n  " + s for s in sub)
        if source.startswith("사용자 답"):
            answer_amend.append("- 판정 기준을 답대로 고침({}){}".format(line, body))
        else:
            decide_amend.append("- [판정 기준 정정] 판정 전에 판정 기준을 고쳤습니다({}){}".format(line, body))
    add_items(screen, "정해 주실 것", decide_amend, top=True)
    add_items(screen, "답하신 것의 반영", answer_amend)

    review = devflow_lib.flow_review_rules(t)
    if review:
        add_items(screen, "확인 안 된 것", flow_review.unverified_items(t))
        add_items(screen, "답하신 것의 반영", flow_review.answered_items(tasks, t, screen.get("답하신 것의 반영", "")))

    # 다른 task의 걸림(notes)은 이 task의 알림 판단에 넣지 않는다. 화면과 알림 줄에는 함께 보인다
    v120 = devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)
    own_items = lambda cell: own_cell_items(cell, screen.get(cell, ""), v120)
    counts = {k: devflow_lib.item_count(own_items(cell)) for cell, k in kinds.COUNT_CELLS.items()}
    criterion, kids = children_lines(result_text)
    facts = None
    if criterion is not None:
        import spawn_children
        facts = child_facts(spawn_children.parse_children(result_text)[1])
    claims = count_claims(claim_cells, criterion, facts)
    table = judge_top.get("판정 표", "")
    undecided_in_table = table_blocks(table, resolved) or table_blocks(run_table, resolved, allow_target=True)
    # 구현·수정 task는 사용자가 판단하거나 손대야 하는 칸(정해 주실 것, 하실 일)만 본다. 알릴 것·확인 안 된 것은
    # 알림 줄에 건수로 남고 흐름별 검증 승인 화면에 모여 올라간다(첫 실행: 코드 task 15개 중 정해 주실 것이 있던 것 0개인데 전부 승인으로 감).
    # 옮기지 못한 칸 분류는 새 task만 알림을 막는다(옛 판정자는 줄 형식 없이 썼다)
    blocked = bool(devflow_lib.item_count(failed)) or undecided_in_table or bool(missing) or bool(unparsed) \
        or not judges_ok or bool(resource_wait) \
        or (bool(move_failed) and devflow_lib.is_new_task(t))
    judgment = devflow_lib.judgment_problems(t)
    blocked = blocked or bool(judgment)
    code_task = t.get("kind") in kinds.AUTO_DEPEND_KINDS
    judged = sum(counts.values())
    commit_hint = []
    if code_task and devflow_lib.item_count(failed) and not str(t.get("commit", "")).strip() and not devflow_lib.no_change(t):
        # 통과 못 한 코드 task는 사람이 답해 완료될 때 커밋한다(SKILL.md 6절 「커밋」)
        commit_hint.append(COMMIT_HINT)
    if devflow_lib.item_count(failed) and t.get("status") == "승인대기":
        deps = board.blocked_ids(tasks, tid)
        if deps:
            commit_hint.append("이 task에 의존하는 대기 task: " + ", ".join(deps))
    # 사용자 원문을 계기로 만든 코드·변경 task는 알림으로 지나가지 않는다(사람의 말을 옮긴 것, SKILL.md 3절)
    by_decide = t.get("kind") in kinds.NOTIFY_BY_DECIDE_KINDS
    contract = devflow_lib.review_contract(t) if v120 else ""
    user_answer = by_decide and devflow_lib.user_origin(t)
    moved_only = v120 and revision_only(run_dir, tasks, t, result_text, screen)
    if moved_only:
        user_answer = False
    if contract == "behavior" and devflow_lib.answer_is_judged(t):
        # 답을 옮긴 코드 task는 판정이 그 옮김을 보고 알림으로 지나간다. 코드를 보고 고치라고 한 답만 결과도 코드로 묻는다(설계 5.3절 2)
        user_answer = user_answer and CODE_CHECK_ORIGIN in str(t.get("origin", ""))
    risky = v120 and devflow_lib.has_risk_mark("\n".join(own_items(cell) for cell in ("정해 주실 것", "알릴 것", "확인 안 된 것")))
    findings = kinds.notify_policy(t.get("kind")) == "findings"
    if findings:
        # 지적 0인 전체 검증 관점(설계 7.6절). 확인 안 된 것은 마무리 리뷰로 가므로 막지 않는다
        notify_ok = v120 and not blocked and not (counts["n_decide"] or counts["n_todo"] or counts["n_notify"]) and not (facts and facts["rows"]) \
            and not hidden_findings(own_items("확인 안 된 것"), top.get("본문", ""))
    elif by_decide:
        notify_ok = counts["n_decide"] == 0 and counts["n_todo"] == 0 and not blocked and not user_answer
    else:
        notify_ok = judged == 0 and not blocked
    # 1.1.0부터 시작한 코드 task는 「건드릴 파일」이 인프라 경로에 들면 알림으로 지나가지 않는다(작업 트리는 보지 않음)
    infra_paths = devflow_lib.touched_in_paths(t, "인프라", devflow_lib.DEFAULT_INFRA_PATTERNS if v120 else ()) \
        if (code_task or v120) and devflow_lib.uses_domain_rules(t) else []
    notify_ok = notify_ok and not infra_paths and not risky
    probe_why = probe_block(top) if t.get("kind") == "probe" else ""
    if v120 and t.get("kind") == "probe" and not probe_why and devflow_lib.probe_remains(t) != devflow_lib.PROBE_NOTHING:
        probe_why = PROBE_LEAVES.format(devflow_lib.probe_remains(t))
    notify_ok = notify_ok and not probe_why
    notify_kind = t.get("kind") in kinds.NOTIFY_KINDS and t.get("kind") not in kinds.NEVER_NOTIFY_KINDS \
        and (contract not in ASKING_CONTRACTS or moved_only or (kinds.notify_policy(t.get("kind")) == "all_cells" and judged == 0)) \
        and (v120 or not findings)
    if v120 and facts and design_screen(t):
        add_items(screen, "건수만", ["- 자식 행 {}, 판정 통과 뒤 코드를 볼 task {}".format(
            facts["rows"] - facts["backlog"], security_tasks(run_dir, spawn_children.parse_children(result_text)[1]))])
    identity = devflow_lib.source_tested_lines(run_dir, t)
    if v120 and not (notify_ok and notify_kind):
        add_items(screen, "알릴 것", moved_revision_lines(tasks, t) + correction_lines(tasks, t) + held_design_lines(tasks, t) + identity)
    return {
        "run_dir": run_dir, "result_text": result_text,
        "t": t, "tasks": tasks, "screen": screen, "missing": missing, "unparsed": unparsed, "failed": failed,
        "judge_top": judge_top, "counts": counts, "criterion": criterion, "kids": kids, "moved": moved,
        "move_failed": move_failed, "notify_ok": notify_ok and notify_kind, "notify_kind": notify_kind,
        "code_task": code_task, "user_answer": user_answer, "judged": judged, "notes": notes, "identity": identity, "env_n": env_n, "commit_hint": commit_hint,
        "facts": facts, "claims": claims, "judges_ok": judges_ok, "judges_why": judges_why,
        "resource_wait": resource_wait, "infra_paths": infra_paths, "probe_block": probe_why,
        "risky": risky, "contract": contract, "v120": v120, "judgment": judgment, "review": review,
        "behavior": flow_review.behavior_body(tasks, t) if review else [],
        "paths_note": paths_note(run_dir, tasks, tid) if devflow_lib.uses_domain_rules(t) else "",
        "n_decide_claim": devflow_lib.item_count(claim_cells.get("정해 주실 것", "")),
    }


def paths_note(run_dir, tasks, tid):
    """경로 목록 알림 줄. 프로젝트 설정 「경로 목록」의 `감지한 실행`이 이 실행이고 다른 task에 승인 요청·승인 시각이
    없으면(그 실행의 첫 화면) 한 줄, 아니면 빈 글. 칸 수와 `counts:`에는 넣지 않는다."""
    paths = devflow_lib.project_paths(run_dir)
    if paths["실행"] != os.path.basename(os.path.abspath(run_dir)):
        return ""
    if any(str(o.get(key, "") or "").strip() for otid, o in tasks.items() if otid != tid
           for key in ("approval_requested", "approved")):
        return ""
    return "- [경로 목록] 화면: {} / 인프라: {} / 문서: {} — 틀렸으면 이 답에서 고쳐 주세요".format(
        *(", ".join(paths[key]) or "없음" for key in ("화면", "인프라", "문서")))


def notify_status(run_dir, tid, tasks=None):
    """(알림 조건 충족 여부, 이유). `task_set.py`가 새 task의 `자체검증→완료`(알림)에서 부른다."""
    b = build(run_dir, tid, tasks)
    if "error" in b:
        return False, b["error"]
    if not b["notify_kind"]:
        return False, "{}는 알림으로 지나가지 않는다".format(b["t"].get("kind"))
    if b["infra_paths"]:
        return False, "인프라 경로: " + ", ".join(b["infra_paths"])
    if b["risky"]:
        return False, "성질 `위험` 항목이 있다"
    if b["probe_block"]:
        return False, b["probe_block"]
    return b["notify_ok"], "screen.py 알림 조건 {}".format("충족" if b["notify_ok"] else "미충족")


def design_screen(t):
    """7.2절 차례를 쓰는 화면: 설계와 설계 정본을 고치는 변경(화면·인프라 정본은 7.6절의 자기 행을 따른다)."""
    return t.get("kind") == "design" or (t.get("kind") == "change" and devflow_lib.is_design_revision(t))


def security_tasks(run_dir, children):
    """판정 통과 뒤 코드를 볼 task 수(1.2.0의 7.2절 6): 코드 행 가운데 코드 확인과 같은 범위(`places.security_marked`)의 보안 표지가 있는 것.
    `[백로그]` 행은 세지 않는다. 정본을 못 읽으면 행의 표지만 본다."""
    import spawn_children

    def secure(c):
        signature = c["body"].get("시그니처와 결정 번호", "")
        row = {"_sections": {"시그니처와 결정 번호": signature}, "closes_ac": spawn_children.split_list(c["meta"].get("closes_ac", "")),
               "partial_ac": spawn_children.split_list(c["meta"].get("partial_ac", ""))}
        try:
            return places.security_marked(run_dir, row)
        except (OSError, UnicodeError):
            return places.SECURITY_MARK in signature
    return sum(1 for c in children if c["meta"].get("kind", "").strip() in kinds.AUTO_DEPEND_KINDS
               and not c["title"].lstrip().startswith("[백로그]") and secure(c))


def _text_of(path):
    """못 읽으면 빈 글이다. 다른 task의 파일이 깨져도 이 화면을 막지 않고 묻는 쪽으로 간다."""
    try:
        return devflow_lib.read_text(path) if os.path.isfile(path) else ""
    except (OSError, UnicodeError):
        return ""


def _written_specs(run_dir, t):
    """task가 쓴 요구사항·기획 정본의 글(셈의 재료)."""
    try:
        rels = devflow_lib.written_canon(run_dir, t)
    except (OSError, UnicodeError):
        return []
    return [_text_of(os.path.join(run_dir, *rel.split("\\"))) for rel in rels if rel.startswith("spec\\")]


def _approval_cells(t):
    """다른 task의 「승인 화면」 칸."""
    top = devflow_lib.sections(_text_of(os.path.join(t["_dir"], "result.md")), level=2)
    return devflow_lib.sections(top.get("승인 화면", ""), level=3)


def decision_numbers(text):
    """정본의 결정 번호: 줄머리가 번호인 행만 센다(`| D-GD-1 |`, `- D-3을`, `### I-2`). 문장 안의 인용은 번호 집합에 섞이지 않고 울타리 안은 보지 않는다."""
    out, fence = set(), False
    for line in (text or "").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        m = None if fence else DECISION_ROW.match(line)
        if m:
            out.add(m.group(1))
    return out


def _revised_paths(t):
    """`revised` 아래의 모든 파일(실행 폴더 기준, `/` 구분). 승인 뒤 `apply_revision.py`가 이 파일을 전부 옮긴다."""
    revised = os.path.join(t["_dir"], "revised")
    return {os.path.relpath(os.path.join(folder, name), revised).replace("\\", "/")
            for folder, _, names in os.walk(revised) for name in names}


def revision_only(run_dir, tasks, t, result_text, cells):
    """설계 고친 판이 답이나 판정자 대안 문장만 옮겼는가(설계 7.2절, 5.3절 4). 판정 기준이 그 옮김을 보고, 실제로 옮겨질 파일이 「건드릴 파일」과
    같고, 자식 행과 결정 번호가 그대로이고, 사람에게 갈 성질이나 새 가정이 없을 때만이다. 판별하지 못하면 묻는다."""
    if t.get("kind") != "change" or not devflow_lib.is_design_revision(t):
        return False
    paths = devflow_lib.change_paths(t)
    if devflow_lib.user_origin(t):
        if not devflow_lib.answer_is_judged(t):
            return False
    else:
        source = devflow_lib.JUDGE_ORIGIN.match(str(t.get("origin", "") or ""))
        judge = _text_of(os.path.join(tasks[source.group(1)]["_dir"], "judge.md")) if source and source.group(1) in tasks else ""
        if not (devflow_lib.correction_is_judged(t) and devflow_lib.unchanged_corrections(judge, paths)):
            return False
    if _revised_paths(t) != set(paths):
        return False
    if devflow_lib.PROPERTY_MARK.search(own_cell_items("알릴 것", cells.get("알릴 것", ""), True)) \
            or devflow_lib.item_count(own_cell_items("확인 안 된 것", cells.get("확인 안 된 것", ""), True)):
        return False
    import spawn_children
    if spawn_children.parse_children(result_text)[1]:
        return False
    for path in paths:
        canon, revised = os.path.join(run_dir, *path.split("/")), os.path.join(t["_dir"], "revised", *path.split("/"))
        before = decision_numbers(_text_of(canon))
        if not before or before != decision_numbers(_text_of(revised)):
            return False
    return True


def _passed_by_notice(o):
    return o.get("kind") == "change" and o.get("status") == kinds.DONE and str(o.get("approval_mode", "")).strip() == "알림" \
        and devflow_lib.version_at_least(o.get("started_version"), devflow_lib.RULES_V120)


def moved_revision_lines(tasks, t):
    """답만 옮겨 알림으로 지나간 설계 고친 판의 전·후 한 줄(설계 7.2절). 그 뒤에 물어서 답을 받은 화면이 없을 때 다음에 묻는 화면에 싣는다.
    그 앞에 물은 화면에는 이 줄이 없었으므로 답을 뒤에 받아도 세지 않는다."""
    out = []
    for o in tasks.values():
        if o is t or not (_passed_by_notice(o) and devflow_lib.user_origin(o) and devflow_lib.is_design_revision(o)):
            continue
        at = str(o.get("approved", ""))
        if any(str(a.get("approved", "")) > at and str(a.get("approval_requested", "")) > at
               and str(a.get("approval_mode", "")).strip() != "알림" for a in tasks.values()):
            continue
        _, its = items(_approval_cells(o).get("답하신 것의 반영", ""))
        line = its[0][0][2:].strip() if its else o.get("title", "")
        out.append("- [{}] 설계 고친 판(답만 옮김): {}".format(o["id"], line))
    return out


def correction_lines(tasks, t):
    """판정자 대안 문장으로 정본을 고쳐 지나간 변경의 한 줄(설계 5.3절 4). 그 흐름 리뷰에 싣는다. 흐름은 원천 task의 것이 먼저이고 없으면 정본 이름이다.
    흐름 리뷰가 없거나 그 리뷰가 답을 받은 뒤에 고쳤으면 마무리에 싣는다."""
    in_review = t.get("kind") == "flow-verify"
    if not in_review and t.get("kind") != "wrap-up":
        return []
    out = []
    for o in tasks.values():
        source = devflow_lib.JUDGE_ORIGIN.match(str(o.get("origin", "") or ""))
        if o is t or not (_passed_by_notice(o) and source):
            continue
        origin_flow = tasks[source.group(1)].get("flow") if source.group(1) in tasks else ""
        names = {origin_flow} if origin_flow else {os.path.splitext(os.path.basename(p))[0] for p in devflow_lib.change_paths(o)}
        at = str(o.get("approved", ""))
        carried = any(f.get("kind") == "flow-verify" and f.get("flow") in names and not (str(f.get("approved", "") or "") and str(f.get("approved")) < at)
                      for f in tasks.values())
        if t.get("flow") in names if in_review else not carried:
            out.append("- [{}] 판정자 대안 문장으로 정본을 고침(뜻 바뀜 없음): {}".format(o["id"], devflow_lib.correction_sentence(o) or o.get("title", "")))
    return out


def held_design_lines(tasks, t):
    """닫힌 설계를 뺀 채 도는 실행 전체 설계가 끝나기 전까지 묻는 화면에 싣는 줄(설계 7.2절). 그 실행 전체 설계의 화면에도 반드시 실린다."""
    family = [o for o in tasks.values() if devflow_lib.is_run_wide(o) and o.get("status") not in kinds.CLOSED_STATUSES]
    out = []
    for o in tasks.values():
        if o.get("kind") == "design" and o.get("status") == "보류" and not devflow_lib.is_run_wide(o):
            for wide in family:
                if o["id"] not in wide.get("depends_on", []):
                    out.append("- [{}] 보류된 설계를 실행 전체 설계 {}에서 빼고 진행합니다. 풀리면 고친 판을 냅니다: {}".format(o["id"], wide["id"], o.get("title", "")))
    return out


def block_summary(run_dir, tasks, t):
    """요구사항 블록 끝 종합(설계 7.2절)의 줄. 다른 형제 상세가 모두 닫혔을 때 화면을 만드는 task에만 싣는다. 형제가 없으면 모을 것이 없다.
    실행 지도가 아니라 형제의 결과와 정본에서 바로 센다."""
    if t.get("kind") != "req-detail":
        return []
    block = [o for o in tasks.values() if o.get("kind") == "req-detail" and o.get("parent", "") == t.get("parent", "")]
    if len(block) < 2 or any(o is not t and board.detail_open(tasks, o) for o in block):
        return []
    out = ["■ 요구사항 종합 (묶음 {})".format(len([o for o in block if o.get("status") != "백로그"]))]
    for o in block:
        if o.get("status") == "백로그":
            continue
        text = "\n".join(_written_specs(run_dir, o))
        marks = devflow_lib.spec_marks(text)
        out.append("  {} {}: 인수 기준 {}(바꾸는 요구 {}, 담당 값 {}, 새 동작 {}) | 사람이 정함 {}, 작성자가 정함 {}".format(
            o["id"], o.get("title", ""), marks["ac"], marks["changed"], marks["filled"], marks["new"],
            devflow_lib.item_count(_approval_cells(o).get("정해 주실 것", "")), marks["filled"]))
        out += ["    담당 값: " + line[:SUMMARY_CHARS] for line in devflow_lib.filled_lines(text)]
    ids = {o["id"] for o in block}
    for o in tasks.values():
        source = re.match(r"사용자 (T\d+)", str(o.get("origin", "") or ""))
        if o.get("kind") == "change" and source and source.group(1) in ids:
            out.append("  답으로 고침: {} {}({})".format(o["id"], o.get("title", ""), source.group(1)))
    return out


CODE_CHECK_ORIGIN = devflow_lib.CODE_CHECK_ORIGIN
# 정본 결정 번호(설계 D-n, D-GD-n, 인프라 I-n). 한글 조사는 뒤에 붙을 수 있다
DECISION_ROW = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|\s*|#+\s*)?[*_`\[]*([DI](?:-[A-Z]+)?-\d+)(?![0-9A-Za-z_-])")
REVIEW_MATERIAL = "리뷰 자료"   # 결과 파일 「승인 화면」의 있어도 되는 칸(설계 4.2절). 번호와 수에 들지 않는다
MATERIAL_MISSING = "! 리뷰 자료 없음(묻는 화면인데 작성자가 `### 리뷰 자료`를 쓰지 않았다)"
MATERIAL_HEADING = re.compile(r"^#+\s*(?:■\s*)?(.*\S)\s*$")
MOVED_TITLE = "{}, 앞 task에서 옮긴 것 {}"   # 칸 수는 이 task의 것이고(`counts:`), 옮겨 온 항목은 따로 말한다
ASKING_CONTRACTS = ("scope", "approach")   # 설계 5.1절. 네 칸이 모두 빈 질문은 물을 것이 없고, 설계 고친 판의 알림은 7.2절에서 연다
FIXED_ANSWERS = ("승인", "고칠 것이 있음", "나눠서 다시", "보류", "남김")
ANSWERS_WITH_TEXT = ("고칠 것이 있음",)
ITEM_LINE = re.compile(r"^- \[(\d+)\] (.*)$")
CHOICE_LETTER = re.compile(r"\(([가-힣])\)")


def number_items(text, start):
    """칸의 맨 앞 `- ` 항목에 화면 항목 번호를 단다(`3 가`, `이의 4`의 번호, 설계 8.1절). 다음 번호를 함께 돌려준다."""
    out = []
    for line in text.split("\n"):
        if line.startswith("- ") and not devflow_lib.EMPTY_ITEM.match(line):
            line = "- [{}] {}".format(start, line[2:])
            start += 1
        out.append(line)
    return "\n".join(out), start


def shown_items(shown):
    """남긴 화면의 칸에서 번호 → 그 항목의 글(들여쓴 하위 줄 포함). 칸 밖의 `- [n]`은 항목이 아니다."""
    items, current, in_cell = {}, None, False
    for line in shown.split("\n"):
        if line.startswith("counts:"):
            break
        if line.startswith("■ "):
            in_cell, current = line[2:].split(" (")[0] in kinds.CELLS + (kinds.FLOW_BEHAVIOR_CELL,), None
            continue
        mark = ITEM_LINE.match(line) if in_cell else None
        if mark:
            current = int(mark.group(1))
            items[current] = mark.group(2)
        elif current is not None and (line.startswith((" ", "\t")) or not line.strip()):
            items[current] += "\n" + line
        else:
            current = None
    return items


def _answer_targets(piece):
    """조각이 가리키는 항목 번호."""
    if "items" in piece:
        return piece["items"]
    number = piece.get("item", piece.get("objection", piece.get("except")))
    return [] if number is None else [number]


def _answer_value_fits(piece, items):
    """일반 화면의 값 규칙. 숫자 값은 받지 않고, 글자는 그 항목의 선택지일 때만, `남김`은 일괄이나 항목 지정에서만 받는다."""
    value = piece.get("value")
    if value is None:
        return True
    if value.isdigit():
        return False
    bare = value.strip("()")
    if len(bare) == 1:
        targets = [piece["item"]] if "item" in piece else piece.get("items", [])
        return bool(targets) and all("({})".format(bare) in items[n] for n in targets)
    return value != "남김" or "rest" in piece or "item" in piece or "items" in piece


def _answers_conflict(own):
    """서로 어긋난 답. 전체 답과 일괄 답은 각각 하나, 항목당 답 하나이고 이의와 예외는 항목 답과 겹치지 않는다."""
    whole = [p for p in own if not _answer_targets(p) and "rest" not in p]
    bulk = [p for p in own if "rest" in p or "except" in p]
    targets = [n for p in own for n in _answer_targets(p)]
    return len(whole) > 1 or len(bulk) > 1 or len(targets) != len(set(targets))


ANSWERED_NUMBER = re.compile(r"(?<![A-Za-z0-9_-])(\d+)(?=번|[\s:.,)]|$)")   # 답 줄 칸의 항목 번호. `T002`, `3개`는 아니다


def decide_items(shown):
    """남긴 화면 「정해 주실 것」 칸에서 사람이 고를 항목(글에 선택지 글자가 있는 것)의 {번호: 글}. 선택지 없는 항목은 전체 답이
    닫고, 기록 점검 줄은 점검 확인으로 닫는다."""
    bodies = shown_items(shown)
    out, inside = {}, False
    for line in shown.split("\n"):
        if line.startswith("counts:"):
            break
        if line.startswith("■ "):
            inside = line[2:].split(" (")[0] == "정해 주실 것"
            continue
        mark = ITEM_LINE.match(line) if inside else None
        if mark and not mark.group(2).startswith("[기록 점검]") and CHOICE_LETTER.search(bodies.get(int(mark.group(1)), "")):
            out[int(mark.group(1))] = bodies[int(mark.group(1))]
    return out


def unchosen_items(t, shown, lines):
    """전체 `승인` 답에서 아직 고르지 않은 「정해 주실 것」 번호. 일반 메시지에는 질문 도구처럼 항목마다 답을 받는 강제가 없다."""
    if "전체: 승인" not in lines or any(l.startswith(("나머지 전부:", "다른 task:")) or "빼고 전부:" in l for l in lines):
        return []
    items = decide_items(shown)
    chosen = {int(n) for l in lines for m in [re.match(r"항목 ([\d, ]+):", l)] if m for n in m.group(1).split(", ")}
    for line in devflow_lib.record_lines(t):
        fields = devflow_lib.record_fields(line)
        cells = " ".join(fields[1:3])
        if fields[1:2] and fields[1].startswith("되물음"):
            continue
        numbers = {int(n) for n in ANSWERED_NUMBER.findall(cells)} & set(items)
        chosen |= numbers
        if not numbers:   # 번호 없는 글자는 그 글자를 가진 항목이 하나로 정해질 때만 닫는다
            fits = {n for letter in CHOICE_LETTER.findall(cells) for n, body in items.items()
                    if n not in chosen and "({})".format(letter) in body}
            chosen |= fits if len(fits) == 1 else set()
    return [n for n in items if n not in chosen]


def resolve_answer(shown, tid, text):
    """답 원문을 남긴 화면으로 푼 줄 목록, 풀지 못하면 None(메인이 되묻는다). 맨 숫자는 일반 화면에서 뜻이 갈리므로 풀지 않는다."""
    items = shown_items(shown)
    letters = sorted({c for body in items.values() for c in CHOICE_LETTER.findall(body)})
    allowed = FIXED_ANSWERS + tuple(letters) + tuple("({})".format(c) for c in letters)
    parsed = devflow_lib.parse_answer(text, allowed, ANSWERS_WITH_TEXT, own_task=tid)
    if parsed is None:
        return None
    own = [p for p in parsed if "raw" not in p]
    if any("number" in p or not set(_answer_targets(p)) <= set(items) or not _answer_value_fits(p, items) for p in own):
        return None
    if _answers_conflict(own):
        return None
    lines = []
    for piece in parsed:
        if "raw" in piece:
            lines.append("다른 task: {} | {}".format(piece["task"], piece["raw"]))
            continue
        value = piece.get("value", "") + (" : " + piece["text"] if "text" in piece else "")
        number = next(iter(_answer_targets(piece)), None)
        if "objection" in piece:
            lines.append("이의: 항목 {} | {}".format(number, items[number].split("\n")[0][:SUMMARY_CHARS]))
        elif "except" in piece:
            lines.append("{} 빼고 전부: {}".format(number, value))
        elif "rest" in piece:
            lines.append("나머지 전부: {}".format(value))
        elif "item" in piece:
            lines.append("항목 {}: {} | {}".format(number, value, items[number].split("\n")[0][:SUMMARY_CHARS]))
        elif "items" in piece:
            lines.append("항목 {}: {}".format(", ".join(map(str, piece["items"])), value))
        else:
            lines.append("전체: {}".format(value))
    return lines


def card_answer(run_dir, tid, key, text):
    """열린 카드의 답을 푼다. 쓰지 않고, 메인이 돌릴 값을 찍는다."""
    plist = places.read(run_dir, tid)
    place = places.find(plist, key)
    if place is None:
        print("되물음: 열린 카드 {}가 places.md에 없음".format(key))
        return 3
    if text.strip() in ("보류", "중단"):
        print("보류·중단: 승인 답 표대로 처리한다(`task_set.py {{실행 폴더}} {} --status 보류 --record …`). 답 없는 곳이 있어도 받는다".format(tid))
        return 0
    got = places.resolve(place, text, os.path.isfile(places.tree_path(run_dir, tid, key)), places.code_shown(run_dir, place))
    if got is None:
        print("되물음: 답의 꼴이 맞지 않음(해석하지 않고 다시 묻는다)")
        return 3
    if "show" in got:
        print("다시 보임: screen.py {{실행 폴더}} {} --card {} --{}".format(tid, place.get("카드", ""), got["show"]))
        return 0
    print("--record: {} {}|{}|{}".format(devflow_lib.CODE_CHECK_ORIGIN, key, got["decision"], " ".join(text.split())))
    if got.get("fix"):
        print("고침 task: task_set.py {{실행 폴더}} new --from-answer {} --place {}".format(tid, key))
    return 0


def answer(run_dir, tid, text):
    task_dir = os.path.join(run_dir, "tasks", tid)
    path = os.path.join(task_dir, "screen-shown.md")
    try:
        doc = devflow_lib.Doc(os.path.join(task_dir, "task.md"))
    except (devflow_lib.Reject, OSError) as e:
        print("되물음: 머리 파일을 읽지 못함({})".format(e))
        return 3
    card_key = str(doc.get("card_open") or "").strip()
    if card_key and doc.get("status") == "승인대기":
        return card_answer(run_dir, tid, card_key, text)
    # `--record`가 asked_at을 비우므로, 비어 있으면 그 화면은 이미 답을 받았거나 낡았다
    if not os.path.isfile(path) or doc.get("status") != "승인대기" or not str(doc.get("asked_at") or "").strip():
        print("되물음: 지금 열린 화면 없음(`--save`로 물은 뒤에 푼다)")
        return 3
    shown = devflow_lib.read_text(path)
    lines = resolve_answer(shown, tid, text)
    if lines is None:
        print("되물음: 답의 꼴이 맞지 않음(해석하지 않고 다시 묻는다)")
        if delegation.read_levels(text)[0]:
            print("위임 원문이면 `screen.py {실행 폴더} --delegate \"원문\"`으로 층을 먼저 적는다")
        return 3
    if devflow_lib.sheet_upload(run_dir) == "허용":
        unchosen = unchosen_items(devflow_lib.load_tasks(run_dir)[tid], shown, lines)
        if unchosen:
            print("되물음: 항목 {}을 고르지 않음(`{} (가)`처럼 고른 뒤 승인한다)".format(", ".join(map(str, unchosen)), unchosen[0]))
            return 3
    print("\n".join(lines))
    if devflow_lib.flow_review_rules({"kind": doc.get("kind"), "started_version": doc.get("started_version")}):
        for line in lines:
            if line.startswith("이의: "):
                print('--record: {}|{}|{}'.format(devflow_lib.REVIEW_OBJECTION, line.split(": ", 1)[1].split(" | ")[0], " ".join(text.split())))
                print("고침 task: task_set.py {{실행 폴더}} new --from-answer {} --title … --body-from … --flow {} (닫기 전에 만든다. 철회면 --record \"{}|항목|원문\")".format(
                    tid, doc.get("flow"), devflow_lib.OBJECTION_WITHDRAWN))
    return 0


BASELINE_LABEL = re.compile(r"^(기준 커밋에 있음|변경 전 실패|닫는 인수 기준)\s*:\s*(.*)$")
BASELINE_CLEAN = re.compile(r"^(?:- )?실패 없음(?:\s*[(（](.*)[)）])?\.?$")   # 판정자가 쓰는 꼴. 괄호 글은 화면에 그대로 싣고, 뒤에 다른 말이 이어지면 읽지 않는다


def baseline_row(line):
    """`baseline-run.md`의 실패 줄을 이름표로 읽는다. 이름에 파이프가 들어도 뒤의 이름표로 찾고, 꼴이 어긋나면 None."""
    if not line.startswith("- "):
        return None
    cells = [c.strip() for c in re.split(r"\s\|\s", line[2:])]
    labels = {}
    while cells and BASELINE_LABEL.match(cells[-1]):
        key, value = BASELINE_LABEL.match(cells.pop()).groups()
        labels[key] = value.strip()
    if len(cells) < 2 or set(labels) != {"기준 커밋에 있음", "변경 전 실패", "닫는 인수 기준"}:
        return None
    if labels["기준 커밋에 있음"] not in ("예", "아니오") or labels["변경 전 실패"] not in ("예", "아니오"):
        return None
    return {"name": " | ".join(cells[:-1]), "why": cells[-1], "base": labels["기준 커밋에 있음"],
            "before": labels["변경 전 실패"], "closes": labels["닫는 인수 기준"]}


def baseline_screen(run_dir):
    """기준선 화면(설계 4.3절). 사실은 실행 판정자가 `baseline-run.md`에 쓰고, 무관한지는 사람이 정한다.
    기준 커밋에 없던 시험 파일의 실패는 이 실행과 무관할 수 없으므로 물을 후보에서 뺀다."""
    path = os.path.join(run_dir, "baseline-run.md")
    if not os.path.isfile(path):
        print("기준선 측정 기록이 없음: baseline-run.md")
        return 3
    asked, new, not_run, unread, clean, notes = [], [], [], [], False, []
    # 옛 실행은 예전 읽기 그대로다: 첫 줄의 판정자, 글자 그대로의 `실패 없음`, 실패 줄과 함께 있어도 받음
    v120 = devflow_lib.version_at_least(devflow_lib.run_meta(run_dir).get("harness_version", ""), devflow_lib.RULES_V120)
    raw = [line.strip() for line in devflow_lib.read_text(path).splitlines()]
    for number, line in enumerate([line for line in raw if line] if v120 else raw):
        if not line or (number == 0 and line.startswith("판정자:")):
            continue
        written = BASELINE_CLEAN.match(line) if v120 else None
        if written:
            clean = True
            notes += [written.group(1)] if written.group(1) else []
        elif line == "실패 없음":
            clean = True
        elif line.startswith("- 돌지 못함:"):
            not_run.append(line[2:])
        else:
            row = baseline_row(line)
            if row is None:
                unread.append(line)
            else:
                (asked if row["base"] == "예" and row["before"] == "예" else new).append(row)
    if unread or (v120 and clean and (asked or new or not_run)) or (not clean and not asked and not new and not not_run):
        print("! 읽지 못한 줄이 있어 기준선을 판단하지 않는다: {}".format(" / ".join(unread) or "내용 없음"))
        print("실행 판정자에게 다시 재게 한다(`- {시험} | {이유 첫 줄} | 기준 커밋에 있음: 예 | 변경 전 실패: 예 | 닫는 인수 기준: {번호}`, 실패가 없으면 `실패 없음`).")
        return 3
    for note in notes:
        print("! 판정자가 적은 글: {} (실패 없음으로 읽었다. 글이 실패나 돌지 못한 시험을 말하면 다시 재게 한다)".format(note))
    for row in new:
        print("! 새 실패(이 실행과 무관할 수 없어 기준선이 될 수 없다): {} | {}".format(row["name"], row["why"]))
    for item in not_run:
        print("! " + item + " (기준선에 넣지 않고 판정불가로 둔다)")
    if not asked:
        print("기준선 질문 없음: 물을 실패 0 (run.md에 한 줄을 쓴다{})".format(". 새 실패는 메인이 그 시험을 만든 task로 돌려보낸다" if new else ""))
        return 0
    print("■ 기준선: 이 실패를 이 실행과 무관한 것으로 두는가 ({})".format(len(asked)))
    for n, row in enumerate(asked, 1):
        print("- [{}] {} | {}".format(n, row["name"], row["why"]))
        print("  기준 커밋에 있음: 예 | 변경 전 실패: 예 | 닫는 인수 기준: {}".format(row["closes"]))
    print("기준선에 넣으면 그 시험이 닫는 인수 기준은 판정불가가 된다.")
    return 0


def write_delegation(run_dir, levels, text, reason="", confirm=None):
    """위임 행을 쓰는 한 자리다. 쓰고 나서 사용자에게 보일 문장을 낸다."""
    delegation.clear_pending(run_dir)
    delegation.write_levels(run_dir, levels, text, reason=reason, confirm=confirm)
    print(delegation.sentence(run_dir, levels))
    return 0


def delegate_command(run_dir, text):
    """위임 원문을 층으로 옮겨 적는다(설계 9절). 읽지 못하면 쓰지 않고 종료 3이다."""
    current = devflow_lib.delegation_levels(run_dir)
    levels, why = delegation.read_levels(text, current)
    if why:
        delegation.clear_pending(run_dir)
        print("되물음: {} (맡긴 것으로 보지 않았고 적지 않았습니다)".format(why))
        print("물을 것: 어디까지 맡기시는지. 결정(추천안으로 정함) / 로컬·통합 브랜치 명령 / dev 밖 명령 / 운영")
        return 3
    if set(levels) <= set(current):   # 줄이거나 없애는 말은 안전한 쪽이라 확인 없이 쓴다
        return write_delegation(run_dir, levels, text)
    delegation.write_pending(run_dir, levels, text)
    print(delegation.pending_sentence(levels))
    return 0


def delegate_confirm_command(run_dir, answer):
    """읽은 범위를 사람이 확인한 답을 받는다. 짧은 긍정 답일 때만 행을 쓰고, 그 밖에는 대기를 지우고 되묻는다."""
    pending = delegation.read_pending(run_dir)
    if pending is None:
        print("거부: 확인을 기다리는 위임 대기가 없다(`--delegate`를 먼저 돌린다)")
        return 3
    if not delegation.is_yes(answer):
        delegation.clear_pending(run_dir)
        print("되물음: 긍정 답이 아니어서 맡긴 것으로 보지 않았고 적지 않았습니다. 고쳐 말씀하시면 `--delegate`로 다시 읽습니다")
        return 3
    return write_delegation(run_dir, pending["levels"], pending["text"], confirm=answer)


def delegate_clear_command(run_dir, reason):
    """위임 행을 `없음`으로 내린다. 사용자의 말이 아니므로 원문을 적지 않는다(되물음 두 번, 다시 열기)."""
    return write_delegation(run_dir, (), None, reason)


def delegation_status(run_dir, tid, tasks=None):
    """이 task의 화면을 위임으로 닫을 수 있는가(`delegation.gate`). `task_set.py`가 `승인|위임 …` 답을 거를 때 부른다."""
    b = build(run_dir, tid, tasks)
    if "error" in b:
        return {"levels": devflow_lib.delegation_levels(run_dir), "need": (), "wait": [], "close": [], "closable": False,
                "why": b["error"] + "(화면 재료가 없으면 사람에게 묻는다)"}
    return delegation.gate(run_dir, b["t"], b["screen"], b["failed"], held=places.completion_block(run_dir, b["t"]), unread=b["move_failed"])


def places_command(run_dir, tid, argv=()):
    """`--places`: 흐름의 곳을 한 번만 고정하고 목록을 찍는다. `--remeasure`면 재지 못한 task만 다시 잰다."""
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        print("task를 찾지 못함: " + tid)
        return 2
    t = tasks[tid]
    if t.get("kind") != "flow-verify":
        print("--places는 흐름별 검증 task에서만(지금 {})".format(t.get("kind")))
        return 3
    if not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        print("코드 확인 0곳(1.2.0 앞에 시작한 검증)")
        return 0
    if not os.path.isfile(places.path_of(run_dir, tid)):
        unmeasured, warnings = [], []
        found = places.collect(run_dir, tid, unmeasured, warnings)
        places.write_places(run_dir, tid, found, delegation.confirmed_levels(run_dir), unmeasured, warnings,
                            [o["id"] for o in places.measure_tasks(tasks, tid)])
    if "--remeasure" in argv:
        tried = argv[argv.index("--tried") + 1] if "--tried" in argv and argv.index("--tried") + 1 < len(argv) else ""
        places.remeasure(run_dir, tid, tried)
    plist = places.read(run_dir, tid)
    print("코드 확인: 보일 곳 {} (보안 {}), 남긴 곳 {}".format(places.total_cards(plist), sum(1 for p in plist if p.get("보안") == "예"), len(places.left_lines(plist))))
    for line in places.note_lines(run_dir, tid):
        print(line)
    for p in plist:
        if p.get("카드"):
            print("- 카드 {}: {} | {} | {} | {} | {}".format(p["카드"], p["key"], p["종류"], ", ".join(p["위치"]), p["처리"], p["의견"]))
    for line in places.left_lines(plist):
        print(line)
    for line in places.gap_block(run_dir, devflow_lib.load_tasks(run_dir)[tid]):
        print(line)
    return 0


def card_command(run_dir, tid, argv):
    """`--card [n] [--full] [--tree]`: 카드 한 장. 대기는 머리 파일 card_open이 정하고 `task_set.py --card-open`이 쓴다."""
    delegation.clear_pending(run_dir)   # 다른 질문을 내면 그 뒤의 답은 위임 확인의 답이 아니다
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        print("task를 찾지 못함: " + tid)
        return 2
    plist = places.read(run_dir, tid)
    open_key = str(tasks[tid].get("card_open", "") or "").strip()
    number = next((a for a in argv[argv.index("--card") + 1:] if a.isdigit()), None)
    place = places.by_card(plist, number) if number else places.find(plist, open_key)
    if place is None:
        print("카드를 찾지 못함: {}".format(number or "열린 카드 없음(`task_set.py … --card-open {키}`로 연다)"))
        return 3
    if place["key"] != open_key:
        print("이 카드는 열려 있지 않음: 먼저 `task_set.py {{실행 폴더}} {} --card-open {}`(지금 열린 카드 {})".format(tid, place["key"], open_key or "없음"))
        return 3
    if "--tree" in argv:
        text = places.tree_text(run_dir, tid, place)
        devflow_lib.write_text(places.tree_path(run_dir, tid, place["key"]), text + "\n")
        print(text)
        print()
    card = places.card_text(run_dir, tid, place, plist, "--full" in argv)
    print(card)
    shown = places.shown_path(run_dir, tid, place["key"])
    if not os.path.isfile(shown):   # 곳당 시간은 처음 낸 때부터 잰다
        devflow_lib.write_text(shown, card + "\n")
    return 0


def flow_commands(run_dir, tid):
    """흐름 리뷰의 전·후를 돌릴 명령의 원천. 옛 흐름별 검증은 전·후를 돌리지 않는다."""
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks or not devflow_lib.flow_review_rules(tasks[tid]):
        print("거부: 1.2.0부터 시작한 흐름별 검증만 전·후를 돌린다({})".format(tid))
        return 2
    print("\n".join(flow_review.command_lines(run_dir, tasks, tasks[tid])))
    return 0


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) == 3 and argv[2] == "--baseline":
        return baseline_screen(argv[1])
    if len(argv) == 4 and argv[2] == "--delegate":
        return delegate_command(argv[1], argv[3])
    if len(argv) == 4 and argv[2] == "--delegate-confirm":
        return delegate_confirm_command(argv[1], argv[3])
    if len(argv) == 4 and argv[2] == "--delegate-clear":
        return delegate_clear_command(argv[1], argv[3])
    if len(argv) >= 4 and argv[3] == "--places":
        return places_command(argv[1], argv[2], argv)
    if len(argv) >= 4 and argv[3] == "--card":
        return card_command(argv[1], argv[2], argv)
    if len(argv) == 4 and argv[3] == "--flow-commands":
        return flow_commands(argv[1], argv[2])
    if "--answer" in argv:
        at = argv.index("--answer")
        if at != 3 or len(argv) != 5:
            print(__doc__)
            return 2
        return answer(argv[1], argv[2], argv[4])
    if "--save" not in argv:
        return show(argv)
    # 답은 남긴 화면의 차례로 푼다(설계 8.1절). 다시 만든 화면은 차례가 바뀔 수 있다.
    args = [a for a in argv if a != "--save"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = show(args)
    print(out.getvalue(), end="")
    if rc != 0:
        return rc
    task_dir = os.path.join(args[1], "tasks", args[2])
    try:
        doc = devflow_lib.Doc(os.path.join(task_dir, "task.md"))
        status = doc.get("status")
        if status != "승인대기":
            print("! --save 안 함: 상태가 {}(묻는 화면은 승인대기에서만 남긴다)".format(status))
            return rc
        tasks = devflow_lib.load_tasks(args[1])
        note = places.open_card_note(tasks, args[1])
        if note:
            print("! --save 안 함: {}(카드 답을 받기 전에는 다른 화면을 띄우지 않는다)".format(note))
            return rc
        held = board.summary_wait(tasks, tasks[args[2]]) if args[2] in tasks else []
        if held:
            print("! --save 안 함: 요구사항 종합을 기다린다({})".format(", ".join(held)))
            return rc
        delegation.clear_pending(args[1])   # 다른 질문을 내면 그 뒤의 답은 위임 확인의 답이 아니다
        devflow_lib.write_text(os.path.join(task_dir, "screen-shown.md"), out.getvalue())
        doc.set("asked_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))   # engine 키. task_set은 이 파일을 부르므로 거꾸로 부르지 못한다
        doc.save()
        if devflow_lib.sheet_upload(args[1]) == "허용":
            print(devflow_lib.PLAIN_ASK)   # screen-shown.md 밖이다. 답을 풀 항목이 아니다
    except devflow_lib.Reject as e:
        print("! --save 실패: {}".format(e))
        return 3
    return rc


def after_approval(b):
    """머리의 `승인하면:` 값. 만들 task와 기다리던 task를 함께 말하고, 둘 다 없으면 닫힌다고 말한다."""
    t, facts, parts = b["t"], b["facts"], []
    if facts and facts["rows"]:
        live = facts["rows"] - facts["backlog"]
        if facts["options"]:
            parts.append("고른 안에 따라 task가 생깁니다({})".format(", ".join("안 {} {}개".format(o, n) for o, n in facts["options"].items())))
        elif live:
            parts.append("task {}개가 생깁니다({})".format(live, ", ".join("{} {}".format(k, n) for k, n in facts["live_kinds"].items())))
        if facts["backlog"]:
            parts.append("백로그로 {}개를 남깁니다".format(facts["backlog"]))
        if t.get("kind") == "design" and not devflow_lib.is_run_wide(t) and board.wave_state(b["tasks"], t):
            parts.append("구현은 실행 전체 설계 뒤에 시작합니다")
    if devflow_lib.is_run_wide(t):
        flows = board.load_flows(b["run_dir"])
        freed = [o["id"] for o in b["tasks"].values() if o.get("status") == "대기" and t["id"] in board.run_wide_block(b["tasks"], flows, o)]
        if freed:
            parts.append("기다리던 구현 {}개가 시작할 수 있습니다({})".format(len(freed), ", ".join(freed)))
    waiting = board.blocked_ids(b["tasks"], t["id"])
    if waiting:
        done = dict(b["tasks"])
        done[t["id"]] = dict(t, status=kinds.DONE)
        ready = [i for i in waiting if board.is_ready(done, done[i])]
        rest = [i for i in waiting if i not in ready]
        if ready:
            parts.append("기다리던 task {}개가 시작할 수 있습니다({})".format(len(ready), ", ".join(ready)))
        if rest:
            parts.append("{}개는 아직 다른 task를 기다립니다({})".format(len(rest), ", ".join(rest)))
    return ", ".join(parts) or "이 task가 닫힙니다"


def see_values(b):
    """`볼 곳:`의 값(설계 7.6절). 칸 수는 옮겨 온 줄을 빼고, 담당 값과 요구 수는 이 task가 쓴 정본에서 센다."""
    t, counts, facts = b["t"], b["counts"], b["facts"] or {}
    marks = devflow_lib.spec_marks("\n".join(_written_specs(b["run_dir"], t)))
    marks = {key: marks[key] for key in ("changed", "filled", "new")}
    judgments = devflow_lib.sections(b["result_text"], level=2).get("판단", "")
    return dict(marks, decide=counts["n_decide"], todo=counts["n_todo"], notify=counts["n_notify"], unverified=counts["n_unverified"],
                marked=sum(1 for cell in ("정해 주실 것", "알릴 것", "확인 안 된 것")
                           for line in own_cell_items(cell, b["screen"].get(cell, ""), True).splitlines()
                           if line.startswith("- ") and devflow_lib.PROPERTY_MARK.search(line)),
                children=facts.get("rows", 0) - facts.get("backlog", 0), options=len(facts.get("options", {})),
                viewpoints=facts.get("live_kinds", {}).get("full-verify", 0), judgments=devflow_lib.item_count(judgments),
                answered=devflow_lib.item_count(b["screen"].get("답하신 것의 반영", "")))


def see_rows(t):
    """그 task의 `볼 곳:` 줄 차례."""
    if devflow_lib.is_run_wide(t):
        return kinds.SEE_RUN_WIDE
    kind = t.get("kind", "")
    if kind != "change":
        return kinds.SEE_COUNTS.get(kind, kinds.SEE_DEFAULT)
    if any(p.startswith("spec/") for p in devflow_lib.change_paths(t)):
        return kinds.SEE_SPEC_CHANGE
    if devflow_lib.is_design_revision(t):
        return kinds.SEE_COUNTS["design"]
    return kinds.SEE_DEFAULT


def decides_of(t):
    """`정하는 것:` 값. 단계 kind는 부르는 쪽이 등록표에서 읽는다."""
    if devflow_lib.is_run_wide(t):
        return kinds.RUN_WIDE_DECIDES
    if t.get("kind", "") in kinds.DECIDES:
        return kinds.DECIDES[t.get("kind", "")]
    paths = devflow_lib.change_paths(t)
    return next((text for prefix, text in kinds.CHANGE_DECIDES if any(p.startswith(prefix) for p in paths)),
                kinds.CHANGE_DECIDES[-1][1])


def head_lines(b):
    """묻는 화면의 머리 세 줄(설계 7.6절): 정하는 것, 볼 곳, 승인하면. 값은 스크립트가 낸다.
    단계 kind에서 묻는 단계가 아니면 빈 목록이고, 메인이 승인 요청 꼴을 그대로 쓴다."""
    t = b["t"]
    kind = t.get("kind", "")
    after = None
    if kind in kinds.STAGE_KINDS:
        head = kinds.STAGE_HEAD.get((kind, devflow_lib.stage_of(t)))
        if head is None:
            return []
        decides, after = head
    else:
        decides = decides_of(t)
    values = see_values(b)
    see = ["{} {}".format(label, values[key]) for label, key in see_rows(t)]
    return ["정하는 것: " + decides, "볼 곳: " + ", ".join(see), "승인하면: " + (after or after_approval(b))]


def marked_first(text):
    """성질이 붙은 항목을 앞으로 옮긴다(설계 7.2절 5). 그 밖의 차례는 그대로다."""
    head, its = items(text)
    its.sort(key=lambda it: not devflow_lib.PROPERTY_MARK.search("\n".join(it)))
    return join_items(head, its)


def material_parts(material, default):
    """리뷰 자료의 (제목, 본문 줄). 첫 줄이 제목이면 화면 제목으로 올려 제목이 두 번 나오지 않게 한다. 칸 이름은 제목으로 올리지 않는다."""
    lines = material.strip().splitlines()
    head = MATERIAL_HEADING.match(lines[0]) if lines else None
    if head and head.group(1) not in kinds.CELLS:
        return head.group(1), lines[1:]
    return default, lines


def fold_material(lines, link):
    """터미널에 낼 줄: 본문 안 첫 제목 앞까지. 접은 줄은 올린 한 장(link)에 있다."""
    at = next((i for i, line in enumerate(lines) if MATERIAL_HEADING.match(line)), None)
    if at is None:
        return lines
    shown = lines[:at]
    while shown and not shown[-1].strip():
        shown.pop()
    return shown + ["(나머지 {}줄은 한 장: {}) {}".format(len(lines) - at, MATERIAL_HEADING.match(lines[at]).group(1), link)]


def material_missing(b):
    """묻는 화면인데 작성자가 리뷰 자료를 쓰지 않았는가. 단계 kind는 자기 절에서 따로 본다."""
    return b["v120"] and not b["notify_ok"] and b["t"].get("kind") not in kinds.STAGE_KINDS and not b["screen"].get(REVIEW_MATERIAL, "").strip()


def count_title(cell, text, numbered):
    """칸 제목의 수. 옮겨 온 항목은 `counts:`에 들지 않으므로 그 수와 따로 적어 항목 수와 어긋나 보이지 않게 한다."""
    own, total = devflow_lib.item_count(own_cell_items(cell, text, numbered)), devflow_lib.item_count(text)
    return "■ {} ({})".format(cell, MOVED_TITLE.format(own, total - own) if numbered and total != own else own)


def one_line_cell(cell, head, its):
    parts = [line.strip() for line in head if line.strip()] + [" ".join(line.strip(" -") for line in it) for it in its]
    return "■ {} ({}): {}".format(cell, len(its), " · ".join(parts))


def cell_blocks(b):
    """화면의 칸 [(칸 제목 줄, 글)]. 차례와 번호는 터미널과 한 장이 함께 쓴다(설계 4.2절). 1.2.0 앞에 시작한 task는 번호가 없다."""
    t, screen, numbered = b["t"], b["screen"], b["v120"]
    others = len(b["notes"])
    extra = " (+다른 task 기록 점검 {})".format(others) if others else ""
    order = kinds.DESIGN_SCREEN_CELLS if numbered and design_screen(t) else kinds.CELLS
    next_item, out = 1, []
    if b.get("behavior"):
        body, next_item = number_items("\n".join(b["behavior"]), next_item)
        out.append(("■ {} ({})".format(kinds.FLOW_BEHAVIOR_CELL, len(b["behavior"])), "  이의가 있으면 `이의 n`, 없으면 답하지 않아도 됩니다\n" + body))
    for cell in order:
        text = screen.get(cell, "")
        if cell == "알릴 것" and numbered and design_screen(t):
            text = marked_first(text)
        if cell == "알릴 것" and (others or b["paths_note"]):
            # 다른 task의 걸림과 경로 목록 줄은 이 task의 칸 수(counts:·n_notify)에 넣지 않고 따로 센다
            title = count_title(cell, text, numbered) + extra
            own = text if devflow_lib.item_count(text) else ""
            # 번호를 달면 옮겨 온 줄도 화면 항목이다. 칸 수만 이 task의 것을 센다
            body = "\n".join(x for x in (own, "\n".join(b["notes"]), b["paths_note"]) if x)
        else:
            if numbered and text.strip() in ("", "- 없음") and cell not in b["missing"]:
                continue   # 값이 없는 칸은 제목도 싣지 않는다(설계 7.6절)
            lead, its = items(text)
            if numbered and (cell == "건수만" or (cell == "답하신 것의 반영" and len(its) > 1)):
                # 칸 하나를 줄 하나로 합친다. 정할 항목이 아니라 번호를 달지 않고, 글은 줄이지 않는다
                out.append((one_line_cell(cell, lead, its), ""))
                continue
            title = count_title(cell, text, numbered)
            body = text if text else "- 없음"
        if numbered:
            body, next_item = number_items(body, next_item)
        out.append((title, body))
    return out


def test_change_notes(t):
    """시험 변화와 함께 보이는 줄(설계 6.12절 6): 판정자의 시험 표 대조, 작성자가 적은 변이를 찾지 못한 단언."""
    judge = os.path.join(t["_dir"], "judge.md")
    table = devflow_lib.sections(devflow_lib.read_text(judge), level=2).get("판단 대조", "") if os.path.isfile(judge) else ""
    out = ["{}: {}".format(t["id"], line.strip().lstrip("- ")) for line in table.splitlines()
           if re.match(r"^(?:- )?(?:시험 표 대조|기대값 근거 어긋남):", line.strip())]
    cells = devflow_lib.result_cells(t) or {}
    out += ["{}: {}".format(t["id"], line.strip().lstrip("- ")) for line in cells.get("확인 안 된 것", "").splitlines() if "변이" in line]
    return out


def blank_table_note(line):
    """표대로도 옮김도 없는 시험 표 대조 줄. 볼 것이 없다."""
    return re.search(r"시험 표 대조: 표대로 0 \| 낮은 계층으로 옮김 0 \| 표에 없던 시험 0(?!\d)", line)


def test_change_lines(run_dir, t, tasks):
    """(답할 줄 수, 화면 줄). 흐름별 검증이면 묻는 꼴이고, 코드 task면 흐름 리뷰에서 물을 것을 알린다.
    답은 `받아들임 / 되살림`이고 추천을 달지 않는다(설계 6.12절 4)."""
    asks = t.get("kind") == "flow-verify"
    lines, count = [], 0
    for row in devflow_lib.flow_test_rows(t, tasks):
        line = devflow_lib.test_change_line(row)
        if not row["ask"]:
            lines.append("건수: {} {} (tasks\\{}\\{})".format(row["change"], row["basis"], row["task"], devflow_lib.TEST_CHANGES))
        elif row["answer"]:
            lines.append('- {} | 답: {} "{}"'.format(line, row["answer"], row["quote"]))
        else:
            count += 1
            if row["change"] == devflow_lib.TEST_EXPECT_ONLY:
                lines.append("! 경보: 제품 변경 없이 기대값만 바꿨는데 앞선 답이 없다")
            cue = "\n  코드 확인의 재지 못함으로 task마다 한 번 묻습니다(답은 확인 없이 합쳐도 된다는 뜻입니다)" if row["change"] == devflow_lib.TEST_UNMEASURED else ""
            lines.append("- [{}] {}{}".format(row["key"], line, cue) if asks else "- " + line)
    for other in tasks.values() if asks else ():
        if other.get("kind") in kinds.AUTO_DEPEND_KINDS and other.get("flow") == t.get("flow") and devflow_lib.needs_judgment_record(other):
            lines += [note for note in test_change_notes(other) if not blank_table_note(note)]
    if asks and any(row["ask"] and not row["answer"] and row["change"] != devflow_lib.TEST_UNMEASURED for row in devflow_lib.flow_test_rows(t, tasks)):
        lines.insert(0, '줄마다 받아들임 / 되살림. 답을 남기는 꼴(상태를 함께 옮기지 않는다): --record "{}|{{키}},{{키}}=받아들임 {{키}}=되살림|{{원문}}"'.format(devflow_lib.TEST_CHANGE_POINT))
    held = devflow_lib.held_test_rows(t, tasks) if asks else []
    if held:
        lines.append("보류·백로그 코드 task의 시험 변화 {}줄은 이 검증에서 묻지 않습니다(마무리 리뷰에 남습니다): {}".format(
            len(held), ", ".join(sorted({row["task"] for row in held}))))
    return count, lines


def wrap_review_lines(t):
    """마무리 실행 승인 화면 맨 앞의 마무리 리뷰(설계 7.3절). 머리 줄 밖은 들여 찍는다. 칸이나 `counts:`로 읽히면 안 된다."""
    if t.get("kind") != "wrap-up" or devflow_lib.stage_of(t) != "실행승인":
        return []
    path = os.path.join(t["_dir"], devflow_lib.WRAP_REVIEW)
    if not os.path.isfile(path):
        return ["! 마무리 리뷰 없음: `visual.py {{실행 폴더}} {} --wrap-review`를 먼저 돌린다".format(t["id"])]
    lines = devflow_lib.read_text(path).splitlines()
    out = lines[:1]
    for at, line in enumerate(lines[1:], 1):
        if line.startswith("## ") and at + 1 < len(lines) and not lines[at + 1].startswith("## ") \
                and (at + 2 == len(lines) or lines[at + 2].startswith("## ")):
            continue   # 줄이 하나뿐인 칸은 제목과 한 줄로 낸다
        previous = lines[at - 1]
        solo = previous.startswith("## ") and not line.startswith("## ") and (at + 1 == len(lines) or lines[at + 1].startswith("## "))
        out.append("  {}: {}".format(previous, re.sub(r"^- ", "", line)) if solo else "  " + line)
    return out


def sheet_line(t):
    """`visual.py --sheet`가 만든 한 장의 경로 줄. 결과보다 오래된 한 장은 없는 것으로 친다."""
    sheet = os.path.join(t["_dir"], "sheet.html")
    result = os.path.join(t["_dir"], "result.md")
    if not os.path.isfile(sheet) or os.path.getmtime(sheet) < os.path.getmtime(result):
        return ""
    return "한 장: " + Path(os.path.abspath(sheet)).as_uri()


def show(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, tid = argv[1], argv[2]
    b = build(run_dir, tid)
    if "error" in b:
        print(b["error"])
        return 2
    t, screen, counts, failed, kids = b["t"], b["screen"], b["counts"], b["failed"], b["kids"]
    tasks = b["tasks"]
    waiting = len(board.queue(b["tasks"]))

    print("[{} {}] {}".format(t.get("kind", ""), tid, t.get("title", "")))
    others = len(b["notes"])
    extra = " (+다른 task 기록 점검 {})".format(others) if others else ""
    env = " · 환경 판정불가 {}(SKILL.md 2절 표)".format(b["env_n"]) if b["env_n"] else ""
    head = []
    if b["v120"] and (not b["notify_ok"] or devflow_lib.stage_of(t) in kinds.ASK_STAGES):
        head = head_lines(b)
        # 칸별 수는 `볼 곳:`과 `counts:`에 있다. 머리가 있으면 대기열만 그 줄에 붙인다
        head = [line + " · 대기 중 {}개{}{}".format(waiting, extra, env) if line.startswith("볼 곳: ") else line for line in head]
        head += deploy_reuse.screen_head(run_dir, t)
        if any(head + [sheet_line(t)]):
            print("\n".join(line for line in head + [sheet_line(t)] if line))
    n_test, test_lines = test_change_lines(run_dir, t, tasks) if b["v120"] else (0, [])
    if b["review"]:
        print(flow_review.answer_line(counts["n_decide"], len(places.waiting(places.read(run_dir, tid))), n_test, len(b["behavior"]), counts["n_todo"]))
        print(flow_review.code_line(run_dir, tasks, t))
    behavior = ", 동작 문장 {}".format(len(b["behavior"])) if b["behavior"] else ""
    if not head:
        print("대기 중 {}개 · 이 화면의 사람 판단 항목 {}개 (정해 주실 것 {}, 하실 일 {}, 알릴 것 {}, 확인 안 된 것 {}{}){}{}".format(
            waiting, b["judged"] + len(b["behavior"]), counts["n_decide"], counts["n_todo"], counts["n_notify"], counts["n_unverified"], behavior, extra, env))
    if devflow_lib.item_count(failed):
        print()
        print(FAILED_HEAD)
        print(failed)
        for line in b["commit_hint"]:
            print("  " + line)
    if not b["judges_ok"]:
        print()
        print("■ 판정 미완료")
        print("- {}".format(b["judges_why"]))
    if b["resource_wait"]:
        print()
        print("■ 자원 대기")
        print("- {}".format(b["resource_wait"]))
    signal_lines, method_line, main_text = main_summary(t, b["judge_top"])
    if main_text is not None:
        devflow_lib.write_text(os.path.join(t["_dir"], "screen-main.md"), main_text)
    numbered = b["v120"]
    # 메인용 줄은 사람이 먼저 보는 자리에 두지 않고 `counts:` 앞으로 민다. 사용자가 승인 전에 볼 전제 변경 줄이 있으면 그대로 맨 위다
    main_lines = []
    if numbered and not any(line.startswith("  " + PREMISE_MARK) for line in signal_lines):
        main_lines, signal_lines = signal_lines, []
    if signal_lines:
        print()
        print("\n".join(signal_lines))
    if b["review"] and not screen.get(REVIEW_MATERIAL, "").strip():
        print()
        print("■ 이 흐름이 한 일")
        print("  재지 못함: 작성자가 「{}」를 쓰지 않았다".format(REVIEW_MATERIAL))
    if numbered and screen.get(REVIEW_MATERIAL, "").strip():
        title, material = material_parts(screen[REVIEW_MATERIAL], "이 흐름이 한 일" if b["review"] else REVIEW_MATERIAL)
        print()
        print("■ " + title)
        # 들여 찍는다. 자료의 `counts:`나 `■ 칸` 줄이 --answer의 화면 해석에 칸으로 읽히면 안 된다
        # 사람이 열 수 있는 한 장이 있을 때만 접는다. file://은 모바일에서 열리지 않는다
        link = devflow_lib.sheet_sent_link(t) if sheet_line(t) else ""
        print("\n".join("  " + line for line in (fold_material(material, link) if link else material)))
    review = wrap_review_lines(t) if numbered else []
    if review:
        print()
        print("\n".join(review))
    if b["review"]:
        print()
        print("\n".join(flow_review.result_lines(t, b["result_text"])))
    if test_lines:
        print()
        print("■ 시험 변화 (답할 것 {})".format(n_test) if t.get("kind") == "flow-verify" else "■ 시험 변화 (흐름 리뷰에서 묻습니다)")
        print("\n".join(test_lines))
    review_notes = flow_review.people_lines(tasks, t) + flow_review.notes(tasks, t) if b["review"] else []
    if review_notes:
        print()
        print("\n".join(review_notes))
    summary = block_summary(run_dir, tasks, t) if numbered else []
    if summary:
        print()
        print("\n".join(summary))
    if numbered and t.get("kind") == "deploy-plan":
        screen["정해 주실 것"] = deploy_reuse.annotate(run_dir, t, screen.get("정해 주실 것", ""))
    for title, body in cell_blocks(b):
        if numbered and method_line and title.startswith("■ 건수만 ("):
            # 둘 다 건수다. 줄을 따로 두지 않는다
            title, method_line = title + " · 확인 방법: " + method_line[len(METHOD_HEAD.format("")):], None
        print()
        print(title)
        if body:
            print(body)
    if method_line and numbered:
        main_lines.append(method_line)
    elif method_line:
        print()
        print(method_line)
    if b["review"]:
        print()
        print(flow_review.evidence_line(run_dir, t, b["result_text"]))
    check_lines = places.screen_lines(run_dir, tid) + (places.gap_block(run_dir, t, tasks) + places.fix_block(run_dir, t) if b["v120"] else [])
    if check_lines:
        print()
        print("\n".join(check_lines))
    if b["criterion"] is not None:
        print()
        print("■ 만들 task {}개 (나눈 기준: {})".format(len(kids), b["criterion"] or "적히지 않음"))
        print("\n".join(kids) if kids else "- 없음")
        print(facts_line(b["facts"]))
    held = board.summary_wait(tasks, t) if numbered else []
    if held:
        print()
        print("! 요구사항 종합 전: {}가 닫힌 뒤에 묻는다(`board.py --queue`)".format(", ".join(held)))
    elif numbered and design_screen(t) and not b["notify_ok"]:
        print()
        print("질문: {} — 승인 / 고칠 것이 있음 / 나눠서 다시 / 보류".format(decides_of(t)))
    corrections = devflow_lib.unchanged_corrections(_text_of(os.path.join(t["_dir"], "judge.md"))) if numbered else []
    if corrections:
        print()
        print("! 판정자 대안 문장(뜻 바뀜 없음) {}건: 묻지 않고 변경 task로 고친다(`--origin \"판정자 {} 대안 문장\"`)".format(len(corrections), tid))
    if b["missing"]:
        print()
        print("! 「승인 화면」 절에 빠진 칸: {} (작성자에게 채우게 한다)".format(", ".join(b["missing"])))
    if b["judgment"]:
        print()
        print("! 판단 기록(작성자에게 고치게 한다. 그 전에는 알림 불가): " + " / ".join(b["judgment"]))
    if numbered:
        unknown = [name for name in screen if name not in kinds.CELLS and name != REVIEW_MATERIAL]
        if unknown:
            print()
            print("! 「승인 화면」의 모르는 절: {} (사람에게 보이지 않는다. 자료 안의 제목은 `####`로 쓴다)".format(", ".join(unknown)))
        if material_missing(b):
            print()
            print(MATERIAL_MISSING)
    bad_cmds = cmd_line_warnings(run_dir, b["tasks"], t)
    if bad_cmds:
        print()
        print("! 명령 줄 꼴(exec.py가 실행 전에 거부함. 묻기 전에 작성자에게 고치게 한다):")
        print("\n".join(bad_cmds))
    if b["moved"]:
        print()
        print("판정자 칸 분류대로 옮긴 항목: {}".format(b["moved"]))
    if b["move_failed"]:
        print()
        print("! 옮기지 못한 칸 분류 {}줄(형식: formats.md 5절. 메인이 화면에서 옮겨 보인다{}):".format(
            len(b["move_failed"]), ". 그 전에는 알림 불가" if devflow_lib.is_new_task(t) else ""))
        print("\n".join(b["move_failed"]))
    warn = claim_lines(b["claims"], b["facts"])
    if warn:
        print()
        print("\n".join(warn))
    floor = floor_alert(run_dir)
    if floor is not None:
        print()
        print(FLOOR_ALERT.format(floor, devflow_lib.CTX_FLOOR_NOTE // 1000))
        devflow_lib.journal_append(run_dir, "메모", tid, FLOOR_NOTED.format(floor))
    cap = devflow_lib.run_value(run_dir, "한 승인의 결정 수 상한", kinds.RUN_DEFAULTS["한 승인의 결정 수 상한"])
    if cap and b["n_decide_claim"] > cap and devflow_lib.version_at_least(b["t"].get("started_version"), devflow_lib.RULES_V110):
        print()
        print("! 결정 수 상한: 정해 주실 것 {} > {}(「이번 실행의 값」) — 메인은 `나눠서 다시`를 추천으로 묻는다".format(b["n_decide_claim"], cap))
    if b["v120"] and devflow_lib.delegation_levels(run_dir) and not b["notify_ok"]:
        print()
        print("\n".join(delegation.gate_lines(delegation.gate(run_dir, t, screen, failed, held=places.completion_block(run_dir, t), unread=b["move_failed"]))))
    print()
    if main_lines:
        print("\n".join(main_lines))
    print("counts: n_decide={n_decide} n_todo={n_todo} n_notify={n_notify} n_unverified={n_unverified} n_children={kids}".format(
        kids=len(kids), **counts))
    if b["unparsed"]:
        print()
        print("! `- ` 항목으로 세지 못한 칸: {} (작성자에게 `- ` 항목으로 고치게 한다. 그 전에는 알림 불가)".format(", ".join(b["unparsed"])))
    if not b["notify_kind"]:
        print("알림 조건: 미충족({}는 알림으로 지나가지 않는다)".format(
            "{} 계약의 {}".format(b["contract"], t.get("kind")) if b["contract"] in ASKING_CONTRACTS else t.get("kind")))
        return 0
    if b["risky"]:
        print("알림 조건: 미충족(성질 `위험` 항목이 있다)")
        return 0
    if b["infra_paths"]:
        print("알림 조건: 미충족(인프라 경로: {})".format(", ".join(b["infra_paths"])))
        return 0
    if b["probe_block"]:
        print("알림 조건: 미충족({})".format(b["probe_block"]))
        return 0
    why = "통과 못 한 기준·판정불가·판정 미완료·자원 대기 없음, 형식 문제 없음"
    if b["code_task"] and b["user_answer"]:
        print("알림 조건: 미충족(사용자 원문을 계기로 만든 task — origin {})".format(t.get("origin", "")))
    elif b["code_task"]:
        print("알림 조건(정해 주실 것·하실 일이 비고 {}): {} — 알림 줄에 붙일 것: 알릴 것 {}, 확인 안 된 것 {}".format(
            why, "충족" if b["notify_ok"] else "미충족", counts["n_notify"], counts["n_unverified"]))
    else:
        print("알림 조건(네 칸이 비고 {}): {}".format(why, "충족" if b["notify_ok"] else "미충족"))
    together = b["notes"] + ([b["paths_note"]] if b["paths_note"] else []) + b["identity"]
    if b["notify_ok"] and together:
        print("알림 줄에 함께 적을 것: " + " / ".join(n[2:].split(chr(10))[0] for n in together))
    return 0


if __name__ == "__main__":
    rc = main(sys.argv)
    print()
    print(devflow_lib.main_context_line(sys.argv[1] if len(sys.argv) > 1 else None))
    sys.exit(rc)
