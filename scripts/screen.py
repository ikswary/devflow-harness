"""승인 화면의 재료를 모은다. 작성자의 result.md 「승인 화면」 절, 판정자의 judge.md, 자식 목록의 한 줄을 읽는다.

메인은 이 출력을 사용자에게 보여 주고(AskUserQuestion의 본문), 마지막 `counts:` 줄의 값을 머리 파일에 적는다.
맨 끝 `메인 컨텍스트:` 줄은 메인이 보고 SKILL.md 8절대로 한다(사용자 화면에는 옮기지 않는다).
결과 본문은 읽지 않는다. 표본 대조는 메인이 따로 한다.

화면에서 이 스크립트가 하는 일(메인은 result.md를 고치지 않는다):
- 판정자의 「칸 분류 확인」대로 항목을 옮긴다(formats.md 5절의 줄 형식).
- `main-run.md`에 같은 기준의 "직접 실행 … 통과"가 있는 판정불가는 세지 않고 「건수만」에 "메인 직접 실행 n"으로 둔다.
- 기록 점검(devflow_lib.record_check): 이 task의 걸림은 「정해 주실 것」 맨 위, 끝난 task의 걸림과 표 밖 전이는 「알릴 것」.
- 판정 기준 정정: 사용자 답이 출처면 「답하신 것의 반영」, 작성자·판정자가 출처면 「정해 주실 것」.
- 판정불가 꼬리표(SKILL.md 2절 표): `대상:`은 「확인 안 된 것」으로 옮겨 알림을 막지 않는다. `대상: 기준선 없음 {명령}`은
  decisions.md에 "기준선 질문 {명령}"이 없으면 「정해 주실 것」에 기준선 질문 한 항목을 더한다. `환경:`은 머리 줄에 센다.
- 마무리·합치기: 보류와 보류에 막힌 task를 「알릴 것」에 "[보류로 남김]"으로(합치기는 그 흐름의 것만).
- 통과 못 한 코드 task: 커밋 안내 한 줄과 이 task에 의존하는 대기 task.
- 재검증의 수정 행이 수정 세대 상한에 닿으면 「정해 주실 것」에 상한 항목((가) 만들기/(나) 백로그/(다) 설계 변경)을 더한다.
- 사용자 원문을 계기로 만든 코드 task(`origin: 사용자 …`)는 알림 불가.
- 자식 목록의 셈(행·kind·[백로그]·안별)을 `셈:` 줄로 보이고, 여섯 칸과 `나눈 기준:` 줄의 "자식 N행/M종" 꼴 주장이 셈과 다르면
  `! 수치 대조` 줄, 제목이 같은 행이면 `! 같은 제목 자식 행` 줄을 낸다. 칸 내용·칸별 수·`counts:`·알림 조건은 그대로다.

사용:
  python screen.py {실행 폴더} {task id}
"""
import os
import re
import sys

import board
import devflow_lib
import kinds

# 알림 정책은 등록표: 사람이 판단할 칸(정해 주실 것·하실 일)만 보고 알림을 정하는 종류 `kinds.NOTIFY_BY_DECIDE_KINDS`
# (변경 task는 사용자 답이 계기가 아닐 때만. 지운 번호 글자만 맞춘 변경을 승인으로 올려 사용자가
# "내가 뭘 보고 승인하라는거야"), 알림으로 지나갈 수 있는 종류 `kinds.NOTIFY_KINDS`(SKILL.md 3절. 그 밖은 언제나 승인),
# 화면에 알림 종류로도 보이지 않는 종류 `kinds.NEVER_NOTIFY_KINDS`. 화면의 칸 `kinds.CELLS`, 세는 칸 `kinds.COUNT_CELLS`.
KEY_RE = re.compile(r"(기준|변이)\s*(\d+)")
MOVE_RE = re.compile(r"^-\s*(.+?)\s*→\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*)$")
# 칸 안 문장의 자식 수 주장을 뽑는 꼴 셋. 꼴 밖의 숫자(줄 번호, task id, 다른 셈)는 보지 않는다.
# 꼴 1: `자식` 바로 뒤(사이에 `행`·`task`·공백만) 숫자 + 개/행. 꼴 2: 숫자 + 개/행 바로 뒤(공백·`의`만) `자식`. 꼴 3: {a}행 + 구분 하나 + {b}종
CLAIM_ROW_RES = (re.compile(r"자식(?:[ \t]|행|task)*(?<!\d)(\d+)(?:개|행)"),
                 re.compile(r"(?<!\d)(\d+)(?:개|행)(?:[ \t]|의)*자식"))
CLAIM_PAIR_RE = re.compile(r"(?<!\d)(\d+)행[/·, \t](\d+)종")
CLAIM_NOTE = "(메인은 결과를 고치지 않는다. 작성자에게 「승인 화면」만 다시 쓰게 하거나 셈 값을 함께 보인다)"


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
    kinds_n = {}
    for c in children:
        kinds_n[kind_of(c)] = kinds_n.get(kind_of(c), 0) + 1
    titles = {}
    for c in children:
        titles[c["title"].strip()] = titles.get(c["title"].strip(), 0) + 1
    return {
        "rows": len(children), "backlog": sum(1 for c in children if backlog(c)), "options": by_option,
        "kinds": kinds_n, "n_kinds": len(kinds_n),
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


def apply_moves(screen, judge_top):
    """판정자 「칸 분류 확인」의 `- {원래 칸} → {옮길 칸} | {항목 앞부분} | {이유}` 줄대로 항목을 옮긴다.
    (옮긴 수, 옮기지 못한 줄 목록)을 돌려준다."""
    moved, failed = 0, []
    for line in judge_top.get("칸 분류 확인", "").splitlines():
        line = line.strip()
        if not line.startswith("- ") or devflow_lib.EMPTY_ITEM.match(line):
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
    unparsed = [cell for cell in kinds.COUNT_CELLS if devflow_lib.unparsed_cell(screen.get(cell, ""))]

    moved, move_failed = apply_moves(screen, judge_top)
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

    # 다른 task의 걸림(notes)은 이 task의 알림 판단에 넣지 않는다. 화면과 알림 줄에는 함께 보인다
    counts = {k: devflow_lib.item_count(screen.get(cell, "")) for cell, k in kinds.COUNT_CELLS.items()}
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
        or (bool(move_failed) and devflow_lib.is_new_task(t))
    code_task = t.get("kind") in kinds.AUTO_DEPEND_KINDS
    judged = sum(counts.values())
    commit_hint = []
    if code_task and devflow_lib.item_count(failed) and not str(t.get("commit", "")).strip():
        # 통과 못 한 코드 task는 사람이 답해 완료될 때 커밋한다(SKILL.md 6절 「커밋」)
        commit_hint.append("커밋: 변경 task로 고침·원인 분석을 고르면 지금 변경을 커밋한 위에서 고칩니다. "
                           "보류를 고르면 커밋하지 않은 변경을 패치로 치울지 함께 묻습니다.")
    if devflow_lib.item_count(failed) and t.get("status") == "승인대기":
        deps = board.blocked_ids(tasks, tid)
        if deps:
            commit_hint.append("이 task에 의존하는 대기 task: " + ", ".join(deps))
    # 사용자 원문을 계기로 만든 코드·변경 task는 알림으로 지나가지 않는다(사람의 말을 옮긴 것, SKILL.md 3절)
    by_decide = t.get("kind") in kinds.NOTIFY_BY_DECIDE_KINDS
    user_answer = by_decide and devflow_lib.user_origin(t)
    if by_decide:
        notify_ok = counts["n_decide"] == 0 and counts["n_todo"] == 0 and not blocked and not user_answer
    else:
        notify_ok = judged == 0 and not blocked
    notify_kind = t.get("kind") in kinds.NOTIFY_KINDS and t.get("kind") not in kinds.NEVER_NOTIFY_KINDS
    return {
        "t": t, "tasks": tasks, "screen": screen, "missing": missing, "unparsed": unparsed, "failed": failed,
        "judge_top": judge_top, "counts": counts, "criterion": criterion, "kids": kids, "moved": moved,
        "move_failed": move_failed, "notify_ok": notify_ok and notify_kind, "notify_kind": notify_kind,
        "code_task": code_task, "user_answer": user_answer, "judged": judged, "notes": notes, "env_n": env_n, "commit_hint": commit_hint,
        "facts": facts, "claims": claims,
    }


def notify_status(run_dir, tid, tasks=None):
    """(알림 조건 충족 여부, 이유). `task_set.py`가 새 task의 `자체검증→완료`(알림)에서 부른다."""
    b = build(run_dir, tid, tasks)
    if "error" in b:
        return False, b["error"]
    if not b["notify_kind"]:
        return False, "{}는 알림으로 지나가지 않는다".format(b["t"].get("kind"))
    return b["notify_ok"], "screen.py 알림 조건 {}".format("충족" if b["notify_ok"] else "미충족")


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, tid = argv[1], argv[2]
    b = build(run_dir, tid)
    if "error" in b:
        print(b["error"])
        return 2
    t, screen, counts, failed, kids = b["t"], b["screen"], b["counts"], b["failed"], b["kids"]
    waiting = len(board.queue(b["tasks"]))

    print("[{} {}] {}".format(t.get("kind", ""), tid, t.get("title", "")))
    others = len(b["notes"])
    extra = " (+다른 task 기록 점검 {})".format(others) if others else ""
    env = " · 환경 판정불가 {}(SKILL.md 2절 표)".format(b["env_n"]) if b["env_n"] else ""
    print("대기 중 {}개 · 이 화면의 사람 판단 항목 {}개 (정해 주실 것 {}, 하실 일 {}, 알릴 것 {}, 확인 안 된 것 {}){}{}".format(
        waiting, b["judged"], counts["n_decide"], counts["n_todo"], counts["n_notify"], counts["n_unverified"], extra, env))
    if devflow_lib.item_count(failed):
        print()
        print("■ 자체 검증에서 통과 못 한 기준")
        print(failed)
        for line in b["commit_hint"]:
            print("  " + line)
    signals = t["_sections"].get("넘길 이상 신호", "")
    if signals and signals != "(없음)":
        print()
        print("■ 이상 신호")
        print(signals)
    for cell in kinds.CELLS:
        text = screen.get(cell, "")
        print()
        if cell == "알릴 것" and others:
            # 다른 task의 걸림은 이 task의 칸 수(counts:·n_notify)에 넣지 않고 따로 센다
            print("■ {} ({}){}".format(cell, devflow_lib.item_count(text), extra))
            own = text if devflow_lib.item_count(text) else ""
            print("\n".join(x for x in (own, "\n".join(b["notes"])) if x))
            continue
        print("■ {} ({})".format(cell, devflow_lib.item_count(text)))
        print(text if text else "- 없음")
    if b["judge_top"].get("확인 방법 요약"):
        print()
        print("■ 자체 검증의 확인 방법")
        print(b["judge_top"]["확인 방법 요약"])
    if b["criterion"] is not None:
        print()
        print("■ 만들 task {}개 (나눈 기준: {})".format(len(kids), b["criterion"] or "적히지 않음"))
        print("\n".join(kids) if kids else "- 없음")
        print(facts_line(b["facts"]))
    if b["missing"]:
        print()
        print("! 「승인 화면」 절에 빠진 칸: {} (작성자에게 채우게 한다)".format(", ".join(b["missing"])))
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
    print()
    print("counts: n_decide={n_decide} n_todo={n_todo} n_notify={n_notify} n_unverified={n_unverified} n_children={kids}".format(
        kids=len(kids), **counts))
    if b["unparsed"]:
        print()
        print("! `- ` 항목으로 세지 못한 칸: {} (작성자에게 `- ` 항목으로 고치게 한다. 그 전에는 알림 불가)".format(", ".join(b["unparsed"])))
    if not b["notify_kind"]:
        print("알림 조건: 미충족({}는 알림으로 지나가지 않는다)".format(t.get("kind")))
        return 0
    why = "통과 못 한 기준·판정불가 없음, 형식 문제 없음"
    if b["code_task"] and b["user_answer"]:
        print("알림 조건: 미충족(사용자 원문을 계기로 만든 task — origin {})".format(t.get("origin", "")))
    elif b["code_task"]:
        print("알림 조건(정해 주실 것·하실 일이 비고 {}): {} — 알림 줄에 붙일 것: 알릴 것 {}, 확인 안 된 것 {}".format(
            why, "충족" if b["notify_ok"] else "미충족", counts["n_notify"], counts["n_unverified"]))
    else:
        print("알림 조건(네 칸이 비고 {}): {}".format(why, "충족" if b["notify_ok"] else "미충족"))
    if b["notify_ok"] and b["notes"]:
        print("알림 줄에 함께 적을 것: " + " / ".join(n[2:].split(chr(10))[0] for n in b["notes"]))
    return 0


if __name__ == "__main__":
    rc = main(sys.argv)
    print()
    print(devflow_lib.main_context_line())
    sys.exit(rc)
