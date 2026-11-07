"""흐름 리뷰(설계 7.1절). 1.2.0부터 시작한 흐름별 검증의 승인 화면과 한 장이 쓰는 재료를 모은다.

화면의 차례는 `screen.py`, 한 장의 틀은 `visual.py`가 맡고, 실행 지도의 자리와 사람 지시로 뺀 검증은 `visual.py`의 「보는 자료」 앞에 실린다.
- 전·후: 실행 판정자가 `judge-run.md` 「흐름 리뷰 전·후」에 쓴다(꼴은 `references/formats/judge-run-file.md`). 돌리지 못한 시나리오는 「확인 안 된 것」으로 간다.
- 값이 비거나 못 읽으면 "없음"이 아니라 "재지 못함"이다. 사람에게 갈 것이 말없이 사라지지 않게 한다.
- 화면에 싣는 값은 가린 뒤 자른다. 자른 뒤에 가리면 경계에 걸린 값의 앞부분이 남는다.
"""
import os
import re

import devflow_lib
import kinds
import places

SECTION = devflow_lib.FLOW_REVIEW_SECTION
PICKED = "돌려 볼 시나리오"   # 결과 파일의 절. 검증 작성자가 고른 것
RESULT_TITLE = "■ 실제로 돌려 본 결과"
NOT_RUN = "돌리지 못함"
RAN, PARTIAL, UNREAD = "돌림", "일부", "재지 못함"
DESIGNED, JUDGED = "설계대로", "판단 있음"
INSTEAD = "대신"
REVIEW_FILE = "review.md"
CLIP = 160
STRAY_SHOWN = 5
FENCE = re.compile(r"^\s*(```|~~~)")
FIELD = re.compile(r"^(?:[-*+]\s+)?[*_`]*(전|후|명령|로그|캡처|대신|돌리지 못함)[*_`]*\s*:\s*(.*)$")
SCENARIO_HEAD = re.compile(r"^#{3,6}\s+(.+)$")
SCENARIO_ITEM = re.compile(r"^(?:[-*+]\s+)?[*_`]*시나리오(?:\s*\d+)?[*_`]*\s*:\s*(.*)$")
TABLE_SPLIT = re.compile(r"\s\|\s")
TABLE_RULE = re.compile(r"^\|[\s:|-]+\|?$")
# 전·후 칸의 첫 내용이 돌리지 않았다는 말인가, 값이 아닌가. 판정자가 꼴을 어겨도 돌린 것으로 세지 않는다
NOT_RUN_WORDS = re.compile(r"^(?:돌리지\s*못함|못\s*돌림|돌릴\s*수\s*없음|돌리지\s*않음|안\s*돌림|실행\s*안\s*함|실행\s*못\s*함|실행하지\s*(?:못함|않음))(?![가-힣])")
EMPTY_VALUE = re.compile(r"(?i)^(?:없음|해당\s*없음|n/?a|-+|—+)$")
VERDICT = re.compile(r"^[*_`\s]*(부분 통과|통과|실패|판정불가)")
VERDICTS = ("통과", "부분 통과", "실패", "판정불가", "기타")
PEOPLE = re.compile(r"^-?\s*사람이 볼 곳\s*:\s*(.*)$")
NO_PEOPLE = "지목 없음"
# 파일 이름 꼴로만 찾는다. 한 장에 무엇을 잰 값인지 함께 적는다
DATA_PATTERNS = ("*.sql", "**/migrations/**", "**/migration/**", "*schema*", "*openapi*", "*.proto", "*.graphql")
DATA_DIFF_LINES = 200
PEOPLE_CAP = 3
HEAD_FILE = "review-head.md"   # `visual.py`가 낸 칸 8, 9의 기록. `screen-shown.md`에 남지 않아 따로 둔다
EXCLUDE_NAME = "검증 제외"


def clean(text):
    """값을 가린다. 줄은 그대로 둔다."""
    return "\n".join(devflow_lib.mask_line(line) for line in devflow_lib.KEY_BLOCK.sub(devflow_lib.MASK, str(text or "")).split("\n"))


def clip(text):
    """가린 뒤 첫 내용 줄을 자른다. 코드 울타리 줄은 내용이 아니다. 뒤에 줄이 더 있으면 말줄임을 단다."""
    rows = _content(clean(text))
    if not rows:
        return ""
    head = rows[0]
    return head[:CLIP] + "…" if len(head) > CLIP or len(rows) > 1 else head


def _content(text):
    return [row.strip() for row in str(text or "").split("\n") if row.strip() and not FENCE.match(row)]


def _fence_step(line, fence):
    """울타리 안이면 연 표지를, 밖이면 None을 돌려준다. 다른 표지의 줄은 울타리 안의 글이다."""
    m = FENCE.match(line)
    if not m:
        return fence
    if fence is None:
        return m.group(1)
    return None if m.group(1) == fence else fence


def _bare(text):
    return re.sub(r"^\*\*\s*|\s*\*\*$", "", str(text or "").strip())


# ---------------------------------------------------------------- 전·후 읽기


def run_section(text):
    """「흐름 리뷰 전·후」 절의 글, 없으면 None. 실행 출력 안의 `## `에서 끊기지 않게 코드 울타리를 본다."""
    rows, fence, found = [], None, False
    for line in text.split("\n"):
        fence = _fence_step(line, fence)
        if fence is None and line.startswith("## "):
            if found:
                break
            found = line[3:].strip() == SECTION
            continue
        if found:
            rows.append(line)
    return "\n".join(rows).strip() if found else None


def _table_cells(line):
    return [c.replace("\\|", "|").strip() for c in TABLE_SPLIT.split(line.strip().strip("|").strip())]


def _table_row(line, head):
    """표 머리에 맞는 행의 시나리오. 칸에 ` | `가 들어 칸 수가 어긋나면 어느 칸인지 모르므로 None이다(읽지 못한 줄로 보인다)."""
    cells = _table_cells(line)
    if len(cells) != len(head):
        return None
    row = dict(zip(head, cells))
    return {"name": _bare(row.pop("시나리오", "") or cells[0]), "fields": {k: _bare(v) for k, v in row.items() if v and k != "시나리오"}}


def parse(section):
    """(시나리오 목록, 읽지 못한 줄). 시나리오는 {"name", "fields"}이고, 값의 뒷줄은 앞 칸에 잇는다."""
    rows, stray, current, field, fence, table = [], [], None, None, None, None

    def extend(line):
        if current is not None and field is not None:
            current["fields"][field] += "\n" + line
        elif line.strip():
            stray.append(line.strip())

    for line in section.split("\n"):
        was = fence
        fence = _fence_step(line, fence)
        if was is not None or fence is not None:
            extend(line)
            continue
        if not line.strip():
            continue
        if devflow_lib.EMPTY_ITEM.match(line.strip()) and current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("|"):
            if TABLE_RULE.match(stripped):
                continue
            cells = _table_cells(stripped)
            if "전" in cells and "후" in cells or NOT_RUN in cells:
                table = cells
                continue
            row = _table_row(stripped, table) if table else None
            if row is None:
                stray.append(stripped)
            else:
                rows.append(row)
            current, field = None, None
            continue
        head = SCENARIO_HEAD.match(stripped) or SCENARIO_ITEM.match(stripped)
        if head:
            current, field = {"name": _bare(head.group(1)), "fields": {}}, None
            rows.append(current)
            continue
        found = FIELD.match(stripped)
        if found and current is not None:
            field = found.group(1)
            value = _bare(found.group(2))
            current["fields"][field] = current["fields"][field] + "\n" + value if field in current["fields"] else value
            continue
        extend(line)
    return rows, stray


def _first(value):
    """값의 첫 내용 줄에서 꾸밈을 벗긴 글."""
    rows = _content(value)
    return re.sub(r"[)\]*_`.,\s]+$", "", re.sub(r"^[\s(\[*_`]+", "", rows[0])) if rows else ""


def _side_state(value):
    """전이나 후 칸 하나: 돌림, 돌리지 못함, 재지 못함."""
    head = _first(value)
    if not head or EMPTY_VALUE.match(head):
        return UNREAD
    return NOT_RUN if NOT_RUN_WORDS.match(head) else RAN


def state(row):
    """시나리오 하나의 상태. 한쪽만 돌렸어도 다른 쪽이 돌리지 못했다고 적혀 있어야 일부다. 애매하면 재지 못함이다."""
    f = row["fields"]
    sides = [_side_state(f.get("전")), _side_state(f.get("후"))]
    told = bool(str(f.get(NOT_RUN, "") or "").strip()) or NOT_RUN in sides
    ran = sides.count(RAN)
    if ran == 2:
        return PARTIAL if told else RAN
    if ran == 1:
        return PARTIAL if told else UNREAD
    return NOT_RUN if told else UNREAD


def _why(row):
    f = row["fields"]
    if str(f.get(NOT_RUN, "") or "").strip():
        return clip(f[NOT_RUN]) or "이유를 적지 않음"
    for value in (f.get("전"), f.get("후")):
        if _side_state(value) == NOT_RUN:
            return clip(NOT_RUN_WORDS.sub("", _first(value)).lstrip(" :*_`")) or "이유를 적지 않음"
    return "이유를 적지 않음"


def read(t):
    """{"problem": 재지 못한 까닭(없으면 빈 글), "rows", "stray"}."""
    path = os.path.join(t["_dir"], kinds.JUDGE_FILES["run"])
    if not os.path.isfile(path):
        return {"problem": "judge-run.md 없음", "rows": [], "stray": []}
    section = run_section(devflow_lib.read_text(path))
    if section is None:
        return {"problem": "judge-run.md 「{}」 절 없음".format(SECTION), "rows": [], "stray": []}
    rows, stray = parse(section)
    return {"problem": "" if rows else "시나리오 없음", "rows": rows, "stray": stray}


def picked_count(result_text):
    """작성자가 고른 시나리오 수. 절이 없으면 None."""
    section = devflow_lib.sections(result_text, level=2).get(PICKED)
    return None if section is None else devflow_lib.item_count(section)


def _side(label, value):
    if str(value or "").strip():
        return "    {}: {}".format(label, clip(value))
    return "    {}: {}(적지 않음)".format(label, UNREAD)


def result_lines(t, result_text):
    """화면의 칸 2. 들여 찍어 `--answer` 화면 해석에 칸으로 읽히지 않게 한다."""
    data, out = read(t), []
    picked = picked_count(result_text)
    if data["problem"]:
        out.append("{}: {}({})".format(RESULT_TITLE, UNREAD, data["problem"]))
    else:
        counts = {}
        for row in data["rows"]:
            counts[state(row)] = counts.get(state(row), 0) + 1
        out.append("{} (시나리오 {}: {})".format(RESULT_TITLE, len(data["rows"]), ", ".join("{} {}".format(k, v) for k, v in counts.items())))
    for row in data["rows"]:
        out.append("  ▸ " + (clip(row["name"]) or "(이름 없음)"))
        now, f = state(row), row["fields"]
        if now in (RAN, PARTIAL):
            out += [_side("전", f.get("전")), _side("후", f.get("후"))]
            if f.get(NOT_RUN):
                out.append("    {}: {}".format(NOT_RUN, _why(row)))
        elif now == NOT_RUN:
            out += ["    {}: {}".format(NOT_RUN, _why(row)), "    시험이 대신 확인한 것: " + (clip(f.get(INSTEAD)) or "{}(적지 않음)".format(UNREAD))]
        elif f.get("전") or f.get("후"):
            out += [_side("전", f.get("전")), _side("후", f.get("후")), "    {}: 돌렸다고 읽을 수 없음".format(UNREAD)]
        else:
            out.append("    {}: 전·후도, 돌리지 못한 이유도 적지 않음".format(UNREAD))
    if picked is None:
        out.append("  ! 작성자가 「{}」를 쓰지 않음".format(PICKED))
    elif picked > len(data["rows"]):
        out.append("  ! 고른 시나리오 {}개 가운데 결과 {}개".format(picked, len(data["rows"])))
    out += ["  ! 읽지 못한 줄: " + clip(line) for line in data["stray"][:STRAY_SHOWN]]
    if len(data["stray"]) > STRAY_SHOWN:
        out.append("  ! 읽지 못한 줄 {}개 더(judge-run.md)".format(len(data["stray"]) - STRAY_SHOWN))
    return out


def unverified_items(t):
    """「확인 안 된 것」 칸의 항목. 전·후는 작성자 뒤에 돌아 작성자가 옮겨 적지 못하므로 스크립트가 올린다."""
    data = read(t)
    if data["problem"]:
        return ["- [{}] 전·후 전체: {}({})".format(NOT_RUN, UNREAD, data["problem"])]
    out = []
    for row in data["rows"]:
        name = clip(row["name"]) or "(이름 없음)"
        now = state(row)
        if now == RAN:
            continue
        if now == PARTIAL:
            out.append("- [전·후 일부만] {}: {}".format(name, _why(row)))
        elif now == NOT_RUN:
            out.append("- [{}] {}: {}".format(NOT_RUN, name, _why(row)))
        else:
            told = "돌렸다고 읽을 수 없음" if row["fields"].get("전") or row["fields"].get("후") else "전·후도, 이유도 적지 않음"
            out.append("- [{}] {}: {}({})".format(NOT_RUN, name, UNREAD, told))
    return out


# ---------------------------------------------------------------- 터미널 맨 위


def answer_line(decide, places_open, tests, behavior, todo):
    """`답할 것 n개`와 묶음별 수."""
    parts = [("정해 주실 것", decide), ("코드 확인", places_open), ("시험 변화", tests), ("동작 문장", behavior), ("하실 일", todo)]
    shown = ["{} {}".format(name, n) for name, n in parts if n]
    return "답할 것 {}개".format(sum(n for _, n in parts)) + (": " + ", ".join(shown) if shown else "")


def _old_code(tasks, t):
    """같은 흐름에서 끝났지만 판단 기록이 없는 옛 코드 task."""
    return [o["id"] for o in tasks.values() if o.get("kind") in kinds.AUTO_DEPEND_KINDS and o.get("flow") == t.get("flow")
            and o.get("status") == kinds.DONE and not devflow_lib.needs_judgment_record(o)]


def _held_commits(tasks, t):
    """커밋이 있는 보류·백로그 코드 task. 코드가 흐름 브랜치에 남는데 보안 곳만 재고 판단은 보지 않는다."""
    return [o["id"] for o in tasks.values() if o.get("kind") in kinds.AUTO_DEPEND_KINDS and o.get("flow") == t.get("flow")
            and o.get("status") in devflow_lib.HELD_STATUSES and not devflow_lib.not_in_flow(o)]


def _code_mark(o):
    """코드 task 하나가 머리 줄의 어디에 드는가(설계 11.1절, 사용자 결정 (가)). 꼴이 어긋나거나 읽지 못하거나 코드가 없으면 재지 못함이다."""
    judge = os.path.join(o["_dir"], kinds.JUDGE_FILES["read"])
    if devflow_lib.no_change(o) or not os.path.isfile(os.path.join(o["_dir"], "result.md")) or devflow_lib.judgment_problems(o) \
            or not os.path.isfile(judge) or "판단 대조" not in devflow_lib.sections(devflow_lib.read_text(judge), level=2):
        return UNREAD
    told = devflow_lib.item_count((devflow_lib.result_cells(o) or {}).get("알릴 것", ""))
    return JUDGED if places.task_judgments(o) or told else DESIGNED


def code_line(run_dir, tasks, t):
    """`코드 n군데, 설계대로 k, 판단 있음 m, 안 보여 드림 j`(설계 11.1절). 설계대로는 판단이 `없음`이거나 `[설계:]`뿐이고, 동작 판단과 달라진 점이 없고,
    꼴이 맞고 코드가 있는 task만이다. `places.md`가 없고 곳이 있거나 신호를 재지 못하면 재지 못함이고, 고정할 때 재지 않은 task도 재지 못함이다."""
    tid = t["id"]
    gaps = []
    if not os.path.isfile(places.path_of(run_dir, tid)):
        if places.collect(run_dir, tid, gaps) or gaps:
            return "코드: {}(`--places`를 돌리기 전)".format(UNREAD)
    else:
        gaps = places.gap_tasks(run_dir, tid, tasks)
    plist = places.read(run_dir, tid)
    left = sum(1 for p in plist if p.get("처리", "").startswith("남김"))
    counts = {DESIGNED: 0, JUDGED: 0}
    for o in places.check_tasks(tasks, tid):
        mark = UNREAD if o["id"] in gaps else _code_mark(o)
        if mark == UNREAD:
            gaps = gaps + [o["id"]] if o["id"] not in gaps else gaps
        else:
            counts[mark] += 1
    line = "코드 {}군데, 설계대로 {}, 판단 있음 {}, 안 보여 드림 {}".format(len(plist) - left, counts[DESIGNED], counts[JUDGED], left)
    gaps = list(dict.fromkeys(gaps + _old_code(tasks, t) + _held_commits(tasks, t)))
    return line + ", {} {}".format(UNREAD, " ".join(gaps)) if gaps else line


def notes(tasks, t):
    """판단 기록이 어긋나 동작 문장과 곳을 다 재지 못한 task의 줄."""
    bad = ["{}({})".format(o["id"], devflow_lib.judgment_problems(o)[0]) for o in places.check_tasks(tasks, t["id"]) if devflow_lib.judgment_problems(o)]
    return ["! 판단 기록을 읽지 못함: " + clip(", ".join(bad))] if bad else []


def behavior_body(tasks, t):
    """번호 붙은 동작 문장(칸 3 가운데 동작 판단)의 `- ` 줄."""
    return ["- {} | {} | {}".format(clip(row["text"]), clip(row["where"]), row["task"]) for row in places.behavior_rows(tasks, t["id"])]


def people(tasks, t):
    """(판정자가 지목한 곳 [(task, 위치, 깨지는 조건)], 재지 못한 task). 코드 확인과 다른 길이다(설계 7.1절 「코드 요약」).
    `지목 없음` 줄도 없으면 판정자가 재지 않은 것이므로 지목 없음으로 세지 않는다."""
    rows, unread = [], []
    for o in places.check_tasks(tasks, t["id"]):
        path = os.path.join(o["_dir"], kinds.JUDGE_FILES["read"])
        body = devflow_lib.sections(devflow_lib.read_text(path), level=2).get("판단 대조") if os.path.isfile(path) else None
        found = [m for m in (PEOPLE.match(line.strip()) for line in (body or "").splitlines()) if m]
        if not found:
            unread.append(o["id"])
        for m in found:
            if NO_PEOPLE not in m.group(1):
                where, _, why = m.group(1).partition(" | ")
                rows.append((o["id"], where.strip(), why.strip() or "깨지는 조건을 적지 않음"))
    return rows, unread


def people_lines(tasks, t):
    rows, unread = people(tasks, t)
    out = ["■ 사람이 볼 곳 (판정자 지목 {})".format(len(rows))] if rows else []
    out += ["  {} {}: {}".format(tid, clip(where), clip(why)) for tid, where, why in rows]
    for tid in sorted({row[0] for row in rows}):
        n = sum(1 for row in rows if row[0] == tid)
        if n > PEOPLE_CAP:
            out.append("! 사람이 볼 곳이 {}곳을 넘김: {} {}곳".format(PEOPLE_CAP, tid, n))
    if unread:
        out.append("! 사람이 볼 곳을 {}: {}(지목 줄 없음)".format(UNREAD, ", ".join(unread)))
    return out


SAME_ANSWER_CHARS = 10   # 검증 작성자의 줄과 앞이 이만큼 같으면 같은 답을 옮긴 줄로 본다


def answered_items(tasks, t, written):
    """칸 6의 줄: 코드 task가 옮긴 답. 작성자가 이미 옮겨 적은 글은 다시 싣지 않는다."""
    out = []
    for o in places.check_tasks(tasks, t["id"]):
        cells = devflow_lib.result_cells(o) or {}
        for line in cells.get("답하신 것의 반영", "").splitlines():
            if line.startswith("- ") and not devflow_lib.EMPTY_ITEM.match(line) and line[2:].strip() not in written:
                out.append("- [{}] {}".format(o["id"], line[2:].strip()))
    # 검증 작성자가 같은 말로 적은 줄만 건수로 접는다. 다루지 않은 줄은 사람이 볼 내용이다
    heads = [line[2:].strip()[:SAME_ANSWER_CHARS] for line in written.splitlines() if line.startswith("- ")]
    same = [line for line in out if line.split("] ", 1)[1][:SAME_ANSWER_CHARS] in heads]
    if len(same) < 2:
        return out
    tally = {}
    for line in same:
        tid = line[3:].split("]", 1)[0]
        tally[tid] = tally.get(tid, 0) + 1
    return ["- 코드 task가 옮긴 같은 답 {}건: {}(각 task 결과 「답하신 것의 반영」)".format(len(same), ", ".join("{} {}".format(k, n) for k, n in tally.items()))] \
        + [line for line in out if line not in same]


# ---------------------------------------------------------------- 접어 둔 근거


def _verdict_cell(cell):
    return cell == "판정" or cell.startswith("판정(")


def _ac_table(result_text):
    """머리에 `판정`이 있는 표의 행 [(줄, 칸, 표 머리 칸, 표 머리 줄)]. 첫 칸의 꼴은 보지 않는다(`K-I5`, 묶음 이름). 표 밖의 `|` 줄은 뺀다."""
    body = devflow_lib.sections(result_text, level=2).get("본문", "") or result_text
    rows, head, head_line = [], None, ""
    for line in body.splitlines():
        if not line.startswith("|"):
            head = None
            continue
        if TABLE_RULE.match(line):
            continue
        cells = [_bare(c) for c in _table_cells(line)]
        if head is None:
            head, head_line = (cells if any(_verdict_cell(c) for c in cells) else []), line
        elif head:
            rows.append((line, cells, head, head_line))
    return rows


def verdict_counts(result_text):
    """(행 수, {판정: 수}). 머리에 맞으면 `판정` 칸을 쓰고, 칸에 ` | `가 들어 어긋나면 처음 나온 판정 낱말을 쓴다."""
    counts = {v: 0 for v in VERDICTS}
    rows = _ac_table(result_text)
    for _, cells, head, _ in rows:
        at = next(i for i, c in enumerate(head) if _verdict_cell(c))
        m = VERDICT.match(cells[at]) if len(cells) == len(head) else None
        m = m or next((x for x in map(VERDICT.match, cells[1:]) if x), None)
        counts[m.group(1) if m else "기타"] += 1
    return len(rows), counts


def write_review(run_dir, t, result_text):
    """칸 10을 `tasks\\{id}\\review.md`에 쓰고 경로를 돌려준다. 못 쓰면 None."""
    flow = t.get("flow", "")
    notified = os.path.join(t["_dir"], "notified-{}.md".format(flow))
    lines, last = ["# 접어 둔 근거: {} {}".format(t["id"], flow), "", "## 인수 기준별 시험 결과"], None
    rows = _ac_table(result_text)
    for row, _, _, head_line in rows:
        if head_line != last:
            lines.append(head_line)
            last = head_line
        lines.append(row)
    if not rows:
        lines.append("{}: 인수 기준 표를 읽지 못함".format(UNREAD))
    lines += ["", "## 알림 task의 칸 모음", devflow_lib.read_text(notified) if os.path.isfile(notified) else "{}: {} 없음".format(UNREAD, os.path.basename(notified))]
    path = os.path.abspath(os.path.join(t["_dir"], REVIEW_FILE))
    try:
        devflow_lib.write_text(path, clean("\n".join(lines)) + "\n")
    except OSError:
        return None
    return path


def evidence_line(run_dir, t, result_text):
    total, counts = verdict_counts(result_text)
    path = write_review(run_dir, t, result_text)
    head = "인수 기준 표 {}행: {}".format(total, ", ".join("{} {}".format(v, n) for v, n in counts.items() if n)) if total else "인수 기준 표 {}".format(UNREAD)
    return "근거(접어 둠): {} → {}".format(head, path or "{}(review.md를 쓰지 못함)".format(UNREAD))


# ---------------------------------------------------------------- 코드 요약(한 장)


def code_summary(run_dir, tasks, t):
    """구조 변화, 규모, 전체 변경, 규약 추가 건수. 흐름의 코드 task 커밋에서 잰다(받아오기로 들어온 남의 변경을 세지 않는다)."""
    folder = places.code_folder(run_dir, t)
    out = {"files": {}, "plus": 0, "minus": 0, "new_dirs": [], "deleted": [], "rules": 0, "unmeasured": [], "outside": [], "commits": [], "old": _old_code(tasks, t)}
    planned = []
    for o in places.check_tasks(tasks, t["id"]):
        path = os.path.join(o["_dir"], "result.md")
        if os.path.isfile(path):
            out["rules"] += devflow_lib.item_count(devflow_lib.sections(devflow_lib.read_text(path), level=2).get("규약 추가", ""))
        planned += devflow_lib.touch_paths(o.get("_sections", {}).get("건드릴 파일", ""))
        sha = str(o.get("commit", "") or "").strip()
        if not sha:
            if not devflow_lib.no_change(o):
                out["unmeasured"].append(o["id"])
            continue
        ok, numstat = places._git(folder, "show", "--numstat", "--format=", "--no-renames", sha)
        done, names = places._git(folder, "show", "--name-status", "--format=", "--no-renames", sha)
        if not (ok and done):
            out["unmeasured"].append(o["id"])
            continue
        out["commits"].append((o["id"], sha))
        status = dict(reversed(line.split("\t", 1)) for line in names.splitlines() if "\t" in line)
        for line in numstat.splitlines():
            cells = line.split("\t")
            if len(cells) != 3:
                continue
            plus, minus = (int(c) if c.isdigit() else 0 for c in cells[:2])
            out["plus"] += plus
            out["minus"] += minus
            out["files"][cells[2]] = status.get(cells[2], "?")
        for name, mark in status.items():
            folder_of = os.path.dirname(name)
            if mark == "D":
                out["deleted"].append(name)
            elif mark == "A" and folder_of and folder_of not in out["new_dirs"] and not places._git(folder, "cat-file", "-e", "{}^:{}".format(sha, folder_of))[0]:
                out["new_dirs"].append(folder_of)
    planned = [p.replace("\\", "/") for p in planned]
    out["outside"] = [f for f in out["files"] if f not in planned and not devflow_lib.pattern_match(f, planned)]
    return out


def data_changes(run_dir, summary, t):
    """[(파일, 변경 줄)]: API·데이터 모델 꼴의 파일이 바뀐 곳."""
    folder = places.code_folder(run_dir, t)
    out = []
    for tid, sha in summary["commits"]:
        ok, names = places._git(folder, "show", "--name-only", "--format=", "--no-renames", sha)
        for name in names.splitlines() if ok else ():
            if devflow_lib.pattern_match(name, DATA_PATTERNS):
                done, diff = places._git(folder, "show", "--format=", "--no-renames", sha, "--", name)
                rows = diff.splitlines() if done else ["{}: git show 실패".format(UNREAD)]
                if len(rows) > DATA_DIFF_LINES:
                    rows = rows[:DATA_DIFF_LINES] + ["… {}줄 더".format(len(rows) - DATA_DIFF_LINES)]
                out.append(("{} {}".format(tid, name), "\n".join(rows)))
    return out


# ---------------------------------------------------------------- 전·후 명령


def exclusions(run_dir):
    """「이번 실행의 값」의 `검증 제외` 줄(설계 6.1절 실행 지시 층, 7.1절 9)."""
    run_md = os.path.join(run_dir, "run.md")
    values = devflow_lib.sections(devflow_lib.read_text(run_md)).get("이번 실행의 값", "") if os.path.isfile(run_md) else ""
    out = []
    for line in values.splitlines():
        at = line.find(EXCLUDE_NAME)
        if at >= 0:
            rest = re.sub(r"^[\s|:]+", "", line[at + len(EXCLUDE_NAME):]).rstrip(" |").replace("\\|", "|")
            out.append("{}: {}".format(EXCLUDE_NAME, rest))
    return out


def ops_hit(line, marks, branch=""):
    """그 명령 줄에 걸린 운영 표지나 운영 브랜치의 말. 없으면 빈 글. `*`는 사이의 아무 글이다(A10의 `delegation`과 같은 대조)."""
    low = line.lower()
    for mark in marks:
        if re.search(".*".join(re.escape(part) for part in mark.lower().split("*")), low):
            return "운영 표지 " + mark
    if branch and re.search(r"(?<![\w-])" + re.escape(branch) + r"(?![\w-])", line):
        return "운영 브랜치 " + branch
    return ""


def _command_section(text):
    """정본에서 제목에 `전·후`가 든 절의 (제목, 줄). 없으면 (None, [])."""
    title, level, rows, fence = None, 0, [], None
    for line in text.splitlines():
        fence = _fence_step(line, fence)
        m = re.match(r"^(#{1,6}) (.+)$", line) if fence is None else None
        if m and title is not None and len(m.group(1)) <= level:
            break
        if m and title is None and ("전·후" in m.group(2) or "전후" in m.group(2)):
            title, level = m.group(2).strip(), len(m.group(1))
            continue
        if title is not None:
            rows.append(line)
    return title, [row for row in rows if row.strip()]


def _run_wide(tasks):
    """끝난 것 가운데 나중 실행 전체 설계, 없으면 나중 것. 없으면 None."""
    rows = [t for t in tasks.values() if devflow_lib.is_run_wide(t)]
    done = [t for t in rows if t.get("status") == kinds.DONE]
    return (done or rows or [None])[-1]


def _flow_lines(run_dir, t):
    """전을 꺼낼 커밋과 후를 돌릴 폴더."""
    path = os.path.abspath(os.path.join(run_dir, "flows", str(t.get("flow", "") or ""), "flow.md"))
    meta = devflow_lib.parse_meta(devflow_lib.split_front_matter(devflow_lib.read_text(path))[0]) if os.path.isfile(path) else {}
    base = str(meta.get("base_commit", "") or "").strip()
    folder = places.code_folder(run_dir, t)
    return ["전: {} ({})".format(base, path) if base else "전: {}(flow.md의 base_commit 없음)".format(UNREAD),
            "후: " + folder if folder else "후: {}(흐름 폴더 없음)".format(UNREAD)]


def command_lines(run_dir, tasks, t):
    """실행 판정자에게 줄 전·후 명령의 원천(설계 7.1절 「돌리는 규칙」). 값을 가려 보이므로 글자 그대로는 경로의 원본에서 읽는다."""
    out = ["전·후를 돌리는 명령의 원천. 그 밖의 새 명령은 실행 폴더나 임시 폴더 안에서 끝나면 돌리고, 밖에 닿으면 `{}: 새 명령이 필요함`이다".format(NOT_RUN)]
    out += _flow_lines(run_dir, t)
    recon = os.path.abspath(os.path.join(run_dir, "recon.md"))
    if os.path.isfile(recon):
        names = [n for n in devflow_lib.sections(devflow_lib.read_text(recon)) if "명령" in n or "잠금" in n]
        out.append("recon.md: {} {}".format(recon, " ".join("「{}」".format(n) for n in names) or "{}(명령 절 없음)".format(UNREAD)))
    else:
        out.append("recon.md: {}(파일 없음)".format(UNREAD))
    wide = _run_wide(tasks)
    marks, branch = devflow_lib.production_marks(run_dir)
    if wide is None:
        out.append("실행 전체 설계 없음: recon.md의 명령만 쓴다")
    elif wide.get("status") != kinds.DONE:
        out.append("실행 전체 설계 {}: 아직 승인 전({}). 그 명령은 쓰지 않는다".format(wide["id"], wide.get("status", "")))
    else:
        found = None
        for rel in devflow_lib.touch_paths(wide.get("_sections", {}).get("건드릴 파일", "")):
            path = os.path.join(run_dir, *rel.replace("\\", "/").split("/"))
            title, rows = _command_section(devflow_lib.read_text(path)) if os.path.isfile(path) and devflow_lib.inside(run_dir, path) else (None, [])
            if title:
                found = (rel, title, rows)
                break
        if found is None:
            out.append("실행 전체 설계 {}: 전·후 명령 절 없음. recon.md의 명령만 쓴다".format(wide["id"]))
        else:
            out.append("실행 전체 설계 {}: {} 「{}」".format(wide["id"], found[0], clean(found[1])))
            for row in found[2]:
                hit = ops_hit(row, marks, branch)
                out.append("  ! 돌리지 않음({}): {}".format(hit, clean(row)) if hit else "  " + clean(row))
    if marks:
        out.append("운영 표지: {}. 명령이나 환경 변수에 걸리면 돌리지 않는다".format(", ".join(marks)))
    else:
        out.append("운영 표지: 가르지 못함(프로젝트 설정 `운영 표지`가 비어 dev와 운영을 가르지 못한다). 밖으로 나가는 명령은 돌리지 않는다")
    out += [clean(line) for line in exclusions(run_dir)]
    return out
