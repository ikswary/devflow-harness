"""1.3.0 사람에게 가는 화면(구현 설계 2절 D, 7판 규칙 1·3.4·4.2): 알림 한 줄, 즉시 질문, 경계 보고.

`screen.py`의 `build` 결과(b)를 받아 사람 몫 줄을 돌려준다. 1.3.0 전에 시작한 task와 단계 kind(명령 승인)는 None이고
`screen.py`의 옛 그리기가 그린다. 메인 몫 줄(경고, `counts:`)은 `screen.py`가 그대로 붙인다.

- 알림 한 줄: 알림으로 지나가는 task. `알림: [{일}] {제목} — {한 줄}`과 펼침.
- 즉시 질문(경계 사이 task): `[{일}] {제목}`, 질문 칸, 답 줄.
- 경계 보고(등록표 `boundary: report`): 머리(경계, 다시 묻지 않는다는 줄, 실행 위치·늘어난 까닭·지금까지 방향, 풀려는 문제),
  세 묶음(물을 것 → 하네스가 고칠 것 → 정한 것, 보이는 줄 12까지), 그사이 고친 것, 남긴 것, 다음, 질문 칸, 펼침, 답 줄.
- 질문 칸은 `■ 정해 주실 것 (n)`과 `- [n] …` 꼴이다(`screen.py --answer`가 남긴 화면에서 이 번호를 읽는다). 답 줄은 질문 뒤에 두고
  추천을 미리 채우지 않는다(7판 시험 I2).
"""
import os
import re

import devflow_lib
import exec as execmod
import kinds
import plain_text
import run_position

VISIBLE = 12   # 세 묶음을 합쳐 보이는 줄(7판 규칙 4.2)
LINE = 80      # 묶음 한 줄의 글자 수
ASK_WIDTH = 96  # 물을 것 한 줄(선택지가 잘리지 않게 조금 길다)
LETTER = re.compile(r"\(([가-힣])\)")
# 승인 뒤 정본에 넣을 재료(writer 규칙, project_docs가 읽음). 사람이 고를 때 읽는 글이 아니라 질문에서 빼고 펼침에 둔다(목적 시험 T051)
OPTION_TEXT = re.compile(r"^\s*[-*]\s+선택지\s*\([가-힣]\)의 (?:문장|앞 정본 줄)")
OPTION_NOTE = "  (선택지마다 정본에 넣을 문장은 펼침에 있습니다)"
LABELS = (("[탐침] ", "[직접 확인] "),)
GROWTH_LABEL = "[늘어남]"   # 작성자가 쓰는 늘어남 질문의 머리(formats/screen-cells.md)
GROWTH_FALLBACK = "(작성자가 쓰지 않아 하네스가 만든 질문입니다)"   # 형식의 머리표를 사람의 말로(묶음 한 줄)
NO_ASK = "이 경계를 지나면 여기 적힌 결정을 다시 묻지 않습니다."
BOUNDARY_ANSWER = "답  진행 / 진행, 단 {조건} / 결정 {n} 다시 / 멈춤   (질문의 답을 모두 앞에 쓰고 `진행`은 맨 뒤에. 예: 전1 됨, 2가, 진행)"
FIX_MARK, NEXT_MARK = "[하네스가 고칠 것]", "[다음 경계에서 물음]"
REVIEW = "리뷰 자료"   # screen.REVIEW_MATERIAL과 같은 칸 이름
# 명령 표(7판 규칙 4.4)의 어림: 쓰는 명령, 되돌리기 어려운 명령. 사람이 줄을 보고 고치게 어림만 한다
WRITES = re.compile(r"\b(?:deploy|publish|push|migrate|migration|apply|upload|put|create|delete|drop|rm|truncate|insert|update|"
                    r"rollback|release|merge|tag|secret|set|reset|restore|seed)\b", re.I)
HARD = re.compile(r"\b(?:drop|delete|truncate|purge|destroy)\b|\brm\s+-r|--force\b|\bforce-push\b|\breset\s+--hard\b", re.I)
TABLE_HEAD = "명령 표   (승인하실 것은 이 표의 줄입니다. 명령 원문은 맨 끝에 있습니다)"
DEPLOYS = re.compile(r"\b(?:deploy|publish|release)\b", re.I)   # 되돌리기 명령이 되돌리는 것은 배포다(마이그레이션·데이터는 아님)
CMD_NOTE = re.compile(r"^\s*줄\s*(\d+)\s*:\s*([^|\n]+?)(?:\s*\|\s*되돌림\s*:\s*([^\n]+))?\s*$", re.M)


def applies(b):
    t = b["t"]
    return devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V130) and t.get("kind") not in kinds.STAGE_KINDS


def _items(text):
    """칸 글의 항목 [첫 줄, 하위 줄들]."""
    out = []
    for line in (text or "").splitlines():
        if line.startswith("- ") and not devflow_lib.EMPTY_ITEM.match(line):
            out.append([line[2:].strip()])
        elif out and line.strip():
            out[-1].append(line.rstrip())
    return out


def _short(text, n=LINE):
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n - 1] + "…"


SENTENCE_END = re.compile(r"\.(?=\s)")   # 문장 끝: `.` 뒤 공백(`다. `를 포함)


def two_sentences(text):
    """앞 두 문장을 자르지 않고(HB-54). 문장 끝이 둘보다 적으면 줄 전체."""
    text = " ".join(text.split())
    ends = [m.end() for m in SENTENCE_END.finditer(text)]
    return text[:ends[1]] if len(ends) >= 2 else text


def place(t):
    block = kinds.KINDS.get(t.get("kind", ""), None)
    return "{} 중".format(block.block) if block and block.block else "문서 고침"


MARKS = re.compile(r"\s*\[(?:성질|종류|위치|따름|설계)\s*:[^\]]*\]|\s*←\s*추천")


def summary(first):
    """묶음 한 줄: 칸의 꼴(`| 이름: 값`), 성질·근거 표지, 추천 표시, 전제의 답 꼴을 뗀다(물을 것은 "A로 할지 B로 할지")."""
    text = first.split(" | ")[0]
    text = re.sub(r"^\[전제 (전\d+)\]\s*", r"\1 ", text)
    text = re.sub(r"^\[가정\]\s*", "", text)
    text = re.sub(r"\s*\(답: [^)]*\)$", "", text)
    for label, plain in LABELS:
        text = plain + text[len(label):] if text.startswith(label) else text
    return MARKS.sub("", text).strip()


def _property(first):
    marks = [m.strip() for m in devflow_lib.PROPERTY_MARK.findall(first) if m.strip() and m.strip() != "없음"]
    return " ({})".format(", ".join(marks)) if marks else ""


def _changed(first):
    """`바뀌는 앞 답: {날짜} "{원문}"`의 (날짜, 원문)."""
    return devflow_lib._source(first.split(devflow_lib.CHANGED_ANSWER, 1)[1]) if devflow_lib.CHANGED_ANSWER in first else ("", "")


def ask_line(first, width):
    """물을 것 묶음의 한 줄. ↺는 바뀌는 앞 답의 날짜와 원문을 남기고 앞을 줄인다(7판 규칙 4.2)."""
    date, quote = _changed(first)
    tail = ' (앞 답: {} "{}")'.format(date, _short(quote, 30)) if date else ""
    return _short(re.sub(r"^\[(?:독립 확인이 짚음|앞 일에서 짚음|앞 결정을 바꿈)\]\s*", "", summary(first)), max(20, width - len(tail))) + tail


def question_lines(first):
    """질문 칸 항목의 첫 줄과 덧붙일 하위 줄(3.4 꼴): 칸 꼴·표지는 떼고 추천 표시는 둔다. 성질과 앞에서 정하신 것은 하위 줄로."""
    head, _, fields = first.partition(" | ")
    text = devflow_lib.PROPERTY_MARK.sub("", head).strip()
    text = re.sub(r"\s+", " ", text)
    subs = []
    assume = re.search(r"(?:^|\| )가정:\s*([^|]+)", fields)
    if assume:
        subs.append("  확인 안 됨: " + assume.group(1).strip())
    props = _property(first)
    if props:
        subs.append("  성질: " + props.strip(" ()"))
    date, quote = _changed(first)
    if date:
        subs.append('  앞에서 정하신 것: {} "{}"'.format(date, quote))
    return text, subs


def _ask_mark(item):
    """물을 것의 기호: 전(먼저 답할 전제) / ↺(앞에서 정하신 것을 바꿈) / ?(확인 안 한 가정에 기댐) / !(독립 확인이 짚음) / ·(그 밖의 결정)."""
    first, body = item[0], "\n".join(item)
    if first.startswith(("[전제 전", "[가정] 전")):
        return "전"
    if devflow_lib.CHANGED_ANSWER in first or first.startswith("[앞 결정을 바꿈]") or "앞에서 정하신 것과 다름" in body:
        return "↺"
    if first.startswith(("[독립 확인이 짚음]", "[앞 일에서 짚음]")):
        return "!"
    if "가정:" in first or "확인 안 됨" in body:
        return "?"
    return "·"


MARK_ORDER = {"전": 0, "↺": 1, "?": 2, "·": 3, "!": 4}   # 물을 것 차례: 전제 → 앞 결정을 바꿈 → 가정 → 그 밖 → 짚음


def ordered_asks(screen):
    return sorted(_items(screen.get("정해 주실 것", "")), key=lambda item: MARK_ORDER[_ask_mark(item)])


def questions(b, start=1):
    """질문 칸 줄과 다음 번호. 항목마다 그 질문의 답 꼴을 하위 줄로 단다."""
    asks = ordered_asks(b["screen"])
    if not asks:
        return [], start
    out = ["■ 정해 주실 것 ({})".format(len(asks))]
    n = start
    for item in asks:
        first, subs = question_lines(item[0])
        out.append("- [{}] {}".format(n, first))
        rest = _without_cmd(item[1:])
        kept = [l for l in rest if not OPTION_TEXT.match(l)]
        out += subs + kept + ([OPTION_NOTE] if len(kept) < len(rest) else [])
        if item[0].startswith("[전제 전"):
            pass   # 전제의 답 꼴은 항목 안에 있다(`답: 전1 됨 / …`)
        else:
            letters = list(dict.fromkeys(LETTER.findall(first)))   # 선택지는 첫 줄에서만(인용 속 글자는 선택지가 아니다)
            forms = ["{}{}".format(n, c) for c in letters] or ["{} 예".format(n), "{} 아니오".format(n)]
            out.append("  답: {} / {} 확인 먼저 / {} 펼쳐".format(" / ".join(forms), n, n))
        n += 1
    return out, n


def _without_cmd(lines):
    """질문 항목의 하위 줄에서 cmd 울타리를 뺀다(명령은 표와 맨 끝 원문으로 간다)."""
    out, inside = [], False
    for line in lines:
        s = line.strip()
        if not inside and devflow_lib.CMD_FENCE.match(s):
            inside = True
            continue
        if inside:
            inside = s != "```"
            continue
        out.append(line)
    return out


def commands(run_dir, b):
    """(명령 표 줄, 명령 원문 줄). 명령이 없으면 둘 다 빈 목록."""
    try:
        rows = execmod.screen_lines(run_dir, b["tasks"], b["t"])
    except Exception:
        rows = []
    if not rows:
        return [], []
    back = devflow_lib.cmd_lines(execmod.heading_section(b["result_text"], "되돌리기")) if b.get("result_text") else []
    table, hard = [TABLE_HEAD, " 줄 | 하는 일 | 쓰기·읽기 | 되돌릴 수 있는가"], []
    described = {}   # 작성자가 「정해 주실 것」 하위 줄에 쓴 `줄 n: {하는 일} | 되돌림: {…}`
    for m in CMD_NOTE.finditer(b["screen"].get("정해 주실 것", "")):
        described[int(m.group(1))] = (m.group(2).strip(), (m.group(3) or "").strip() or None)
    for n, (line, _) in enumerate(rows, 1):
        if line in back:
            continue
        writes = bool(WRITES.search(line))
        what, said = described.get(n, (None, None))
        if said:
            undo = said
        elif HARD.search(line):
            undo = "어려움"
        elif writes:
            undo = "되돌리기 명령 있음" if back and DEPLOYS.search(line) else "확인 필요"
        else:
            undo = "읽기만"
        if HARD.search(line) or undo.startswith(("어려움", "안 됨", "불가")):
            hard.append("{}번 줄({})".format(n, _short(what or line, 30)))
        table.append(" {} | {} | {} | {}".format(n, _short(what or line, 44), "쓰기" if writes else "읽기", undo))
    head = ["되돌릴 수 없는 것  {}".format(", ".join(hard) if hard else "없음"),
            "되돌리는 방법      {}".format("되돌리기 명령 {}줄(명령 원문 끝)".format(len(back)) if back else "적힌 되돌리기 명령 없음")]
    raw = ["■ 명령 원문"] + ["{}. {}".format(n, line) for n, (line, _) in enumerate(rows, 1)]
    return head + table, raw


def notice(b):
    t, screen = b["t"], b["screen"]
    material = (screen.get(REVIEW, "") or "").strip().splitlines()
    notes = [i[0] for i in _items(screen.get("알릴 것", ""))]
    fixes = [x for x in notes if x.startswith(FIX_MARK)]
    deadlines = [x for x in notes if x.startswith("[기한]")]
    if fixes:
        tail = "하네스가 고칠 것 {}: {}".format(len(fixes), _short(fixes[0][len(FIX_MARK):].strip(), 40))
    elif deadlines:
        tail = _short(deadlines[0], 60)
    elif material:
        tail = _short(material[0], 60)
    else:
        tail = "물을 것 없음"
    return ["알림: [{}] {} — {}".format(place(t), t.get("title", ""), tail), _unfold(b)]


def _unfold(b):
    screen = b["screen"]
    parts = ["{} {}".format(c, devflow_lib.item_count(screen.get(c, ""))) for c in ("알릴 것", "확인 안 된 것", "건수만")
             if devflow_lib.item_count(screen.get(c, ""))]
    return "펼침: {}{}".format(os.path.join(b["t"]["_dir"], "result.md"), " ({})".format(" · ".join(parts)) if parts else "")


def _since_last_boundary(tasks, t):
    """앞 경계 보고(같은 실행의 다른 경계 kind가 승인된 때) 뒤에 알림으로 지나간 task."""
    marks = [str(o.get("approved", "")) for o in tasks.values()
             if o is not t and o.get("kind") in kinds.BOUNDARY_KINDS and str(o.get("approval_mode", "")).strip() == "승인"]
    after = max(marks) if marks else ""
    return [o for o in tasks.values() if o is not t and str(o.get("approval_mode", "")).strip() == "알림"
            and str(o.get("approved", "")) > after]


def _request(run_dir):
    path = os.path.join(run_dir, "run.md")
    if not os.path.isfile(path):
        return ""
    body = devflow_lib.sections(devflow_lib.read_text(path), level=2).get("요청 원문", "").strip().splitlines()
    return _short(body[0], 70) if body else ""


def boundary(run_dir, b, extra=None):
    t, screen, tasks = b["t"], b["screen"], b["tasks"]
    label = kinds.BOUNDARY_LABELS.get(t.get("kind", ""), place(t))
    out = ["[{}] {}".format(label, t.get("title", "")), NO_ASK, burden(screen), ""]
    out += run_position.head_lines(run_dir, tasks)
    request = _request(run_dir)
    if request:
        out += run_position._rows("원래 요청", [request])
    material = [l for l in (screen.get(REVIEW, "") or "").strip().splitlines() if l.strip() and not l.startswith("#")]
    out += run_position._rows("풀려는 문제", [_short(material[0], 70) if material else "(작성자가 「리뷰 자료」를 쓰지 않음)"])
    out += _blocking(b)
    asks = ordered_asks(screen)
    notes = [i[0] for i in _items(screen.get("알릴 것", ""))]
    fixes = [x[len(FIX_MARK):].strip() for x in notes if x.startswith(FIX_MARK)]
    carried = []
    rows = devflow_lib.decided_rows(screen.get(devflow_lib.DECIDED_CELL, ""))
    decided = rows
    out += ["", "물을 것 {}   (전 먼저 답해 주실 전제 · ↺ 앞에서 정하신 것을 바꿈 · ? 확인 안 한 가정에 기댐 · ! 독립 확인이 짚음)".format(len(asks))]
    out += [" {} {} → 질문 {}".format(_ask_mark(item), ask_line(item[0], ASK_WIDTH), n) for n, item in enumerate(asks, 1)]
    if fixes:
        out += ["하네스가 고칠 것 {}   (! 독립 확인이 짚음. 이 경계를 지나면 하네스가 고치고 알립니다)".format(len(fixes))] + [" ! " + _short(f) for f in fixes]
    room = max(0, VISIBLE - len(asks) - len(carried) - len(fixes))
    if decided:
        out.append("정한 것 {}   (◇ 앞에서 정하심 · ✔ 독립 확인이 근거를 봄)".format(len(decided)))
        out += [" {} {}".format(n, _short(_decided(row))) for n, row in enumerate(rows[:room], 1)]
        if len(decided) > room:
            rest = decided[room:]
            kinds_of = " · ".join("{} {}개".format(m, sum(1 for r in rest if r["mark"] == m)) for m in ("◇", "✔")
                                  if any(r["mark"] == m for r in rest))
            out.append(" … 외 {}({}) → 펼쳐".format(len(rest), kinds_of))
    since = [o.get("title", "") for o in _since_last_boundary(tasks, t)]
    if since:
        out += ["그사이 고친 것"] + [" - " + _short(x) for x in since]
    kept = [x for x in notes if x.startswith("[기한]")]   # 기한 있는 일은 늘 보인다(7판 시험 I5)
    kept += [x for x in notes if not x.startswith((FIX_MARK, NEXT_MARK, "[기한]")) and devflow_lib.PROPERTY_MARK.search(x)
             and "[성질: 없음]" not in x]
    kept += [i[0] for i in _items(screen.get("확인 안 된 것", ""))]
    if kept:
        out += ["남긴 것"] + [" - " + _short(summary(x) + _property(x)) for x in kept]
    if b["kids"]:
        names = [_short(k[2:].split(" [")[0], 24) for k in b["kids"][:3]]
        out.append("다음  {}개 일을 만듭니다: {}{}".format(len(b["kids"]), ", ".join(names), " 외" if len(b["kids"]) > 3 else ""))
    table, raw = commands(run_dir, b)
    if table:
        out += [""] + table
    qs, _ = questions(b)
    if qs:
        out += [""] + qs
    out += [""] + list(extra or []) + [BOUNDARY_ANSWER, _unfold(b)]
    if raw:
        out += [""] + raw
    return out


def _decided(row):
    if row["mark"] == "◇" and row["date"]:
        return '◇ {} ({} "{}")'.format(row["text"], row["date"], row["quote"])
    if row["mark"] == "✔" and row["dropped"]:
        return "✔ {} (버림: {})".format(row["text"], row["dropped"])
    return "{} {}".format(row["mark"], row["text"]).strip()


COST_MARK = re.compile(r"\[성질:[^\]]*(?:비용|밖)[^\]]*\]")


def burden(screen):
    """승인의 부담 한 줄(7판 규칙 2절). 돈·계정·바깥 시스템에 닿는 표지(성질 비용·밖)가 있으면 그 첫 항목을 밝힌다."""
    for cell in ("정해 주실 것", "하실 일·허용 요청", "알릴 것"):
        for item in _items(screen.get(cell, "")):
            if COST_MARK.search(item[0]):
                return "이 승인에는 돈·계정·바깥 시스템에 닿는 것이 있습니다: " + _short(summary(item[0]), 50)
    return "성질 표지로 보면 이 승인으로 돈·계정·바깥 시스템에 닿는 것은 없습니다."


def _blocking(b):
    """판정이 막은 것(통과 못 한 기준, 판정 미완료, 자원 대기)은 사람이 먼저 본다."""
    out = []
    if devflow_lib.item_count(b["failed"]):
        out += ["", "■ 통과 못 한 기준", b["failed"]]
    if not b["judges_ok"]:
        out += ["", "■ 판정 미완료", "- " + b["judges_why"]]
    if b["resource_wait"]:
        out += ["", "■ 자원 대기", "- " + b["resource_wait"]]
    return out


def instant(run_dir, b, extra=None):
    t = b["t"]
    qs, n = questions(b)
    table, raw = commands(run_dir, b)
    out = ["[{}] {}".format(place(t), t.get("title", ""))]
    material = [l for l in (b["screen"].get(REVIEW, "") or "").strip().splitlines() if l.strip() and not l.startswith("#")]
    if material:
        out.append(two_sentences(material[0]))
    out += _blocking(b)
    if b.get("committed"):   # 커밋한 코드 task: 고침은 그 커밋 위에 쌓인다(D-09)
        out += [""] + b["committed"]
    later = sum(1 for i in _items(b["screen"].get("알릴 것", "")) if i[0].startswith(NEXT_MARK))
    if later:
        out.append("독립 확인이 짚은 것 {}건은 다음 경계 보고에서 묻습니다".format(later))
    if table:
        out += [""] + table
    if qs:
        out += [""] + qs
    out += [""] + list(extra or []) + ["답  질문의 답 / 멈춤   (예: 1가, 2 확인 먼저)", _unfold(b)]
    if raw:
        out += [""] + raw
    return out


def render(run_dir, b, extra=None):
    """사람 몫 줄. extra는 답 줄 앞에 넣는 줄(흐름별 검증의 만든 것·시험 변화·코드 확인 곳)."""
    if not applies(b):
        return None
    if b["notify_ok"]:
        return notice(b)
    if b["t"].get("kind") in kinds.BOUNDARY_KINDS:
        return boundary(run_dir, b, extra)
    return instant(run_dir, b, extra)


def parts(lines):
    """[(종류, 글)]: 머리 칸, 경계 보고 본문(머리·질문·명령 밖), 질문 하나씩. 글자 예산은 부분마다 잰다(7판 규칙 4.2·3.4)."""
    out, body, q = [], [], None
    head = [l for l in lines if l.startswith(("실행 위치", "늘어난 까닭", "지금까지 방향", "원래 요청", "풀려는 문제", " " * run_position.WIDTH))]
    for line in lines:
        if line in head or line.startswith(("펼침: ", "답  ", "■ 명령 원문", "명령 표", " 줄 |")) or re.match(r"^ \d+ \| ", line):
            continue
        m = re.match(r"^- \[(\d+)\] ", line)
        if m:
            q = [line]
            out.append(("ask", q))
        elif q is not None and line.startswith("  "):
            q.append(line)
        else:
            q = None
            if not line.startswith("■ "):
                body.append(line)
    found = [("head", "\n".join(head))] if head else []
    if NO_ASK in body:
        found.append(("boundary", "\n".join(body)))
    return found + [(kind, "\n".join(text)) for kind, text in out]


def warnings(lines):
    """사람에게 가는 줄의 사람의 말 검사(plain_text, U7: 경고만). 메인이 작성자에게 한 번 고치게 한다. 부분마다 잰다."""
    found = []
    for kind, text in parts(lines):
        for problem in plain_text.problems(text, kind):
            found.append("{}: {}".format({"head": "머리 칸", "boundary": "경계 보고", "ask": "질문"}[kind], problem))
    found = list(dict.fromkeys(found))
    out = []
    if any(GROWTH_FALLBACK in line for line in lines):
        out.append("! 늘어남 질문 없음: 작성자에게 「정해 주실 것」 맨 앞에 `[늘어남]` 항목(선택지마다 원래 요청이 어떻게 나가는지)을 "
                   "쓰게 한다(formats/screen-cells.md, 「승인 화면」 고침 한 번에 함께)")
    return out + (["! 사람의 말(작성자 글이면 한 번 고치게 하고, 스크립트가 만든 줄이면 그대로 둔다): " + " / ".join(found)] if found else [])
