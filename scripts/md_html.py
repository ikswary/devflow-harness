"""한 장(sheet.html)에 싣는 Markdown의 작은 변환기(설계 4.2절). 표준 라이브러리만 쓴다.

다루는 것: 제목(`#`→h3, `##`→h4, `###` 이하→h5), 문단(줄바꿈은 `<br>`로 지킨다), 글머리·번호 목록(들여쓰기로 중첩,
항목 아래 들여쓴 울타리·표·목록은 항목 안의 블록, 번호는 `<ol start>`·`<li value>`로 원문대로), 파이프 표(코드 구간 안의 `|`와
`\\|`는 칸을 나누지 않고, 칸 수는 머리에 맞춘다), 울타리 코드(같은 문자로 여는 길이 이상인 줄에서만 닫힌다), mermaid 울타리
(안내 한 줄 + 펼친 「도면 원문」. 한 장의 초기화 스크립트가 그리면 안내를 지우고 원문을 접는다), 4칸 들여쓴 코드, 가로줄,
인라인 코드·**굵게**(굵게 안의 코드 포함), 표지 칩, 「앞 정본 줄 … | 지금: … | 바뀜: …」의 두 칸.
모든 글은 먼저 html.escape를 거친다(원문의 태그를 살리지 않는다). 사용자 글은 속성값에 넣지 않는다(`start`·`value`는 숫자만).
가리기(visual.sheet_html의 safe)를 거친 글만 받는다. 이 모듈은 가리지 않는다.
"""
import html
import re

FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^`\s]*)[^`]*$")
HEAD = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
MARKER = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])(\s+|$)(.*)$")
TABLE_SEP_CELL = re.compile(r"^\s*:?-+:?\s*$")
RULE = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
TAG = re.compile(r"\[((?:성질|바뀜)\s*[:：][^\]]*|담당이 채움|전제 바뀜|되돌릴 수 없는 단계 포함|보안|탐침|계약|사실|해석|백로그|Q\d)\]")
SLOT = "\x00{}\x00"
SLOT_RE = re.compile("\x00(\\d+)\x00")
# 선택지가 앞 정본을 바꾸는 줄(references/formats/result-file.md). project_docs.PAIR_LINE이 읽는 꼴과 같다(시험이 대조한다)
PAIR = re.compile(r"^(?P<head>.*?앞 정본 줄:[^|]*?)\s*\|\s*지금:\s*(?P<now>.+?)\s*\|\s*바뀜:\s*(?P<new>.+?)\s*$")
DIAGRAM_FAILED = "그림을 그리지 못했습니다. 아래 원문을 보세요."
DIAGRAM_SOURCE = "도면 원문"
DIAGRAM_OPEN = '<figure class="diagram">'   # 한 장은 이 꼴이 있을 때만 그리는 스크립트를 싣는다


def _code_spans(text):
    """[(시작, 끝, 안의 글)]: 같은 길이의 백틱 줄로 닫히는 코드 구간. 닫히지 않는 백틱은 글자다."""
    out, i = [], 0
    while True:
        start = text.find("`", i)
        if start < 0:
            return out
        end = start
        while end < len(text) and text[end] == "`":
            end += 1
        close = re.compile(r"(?<!`)" + text[start:end] + r"(?!`)").search(text, end)
        if close is None:
            i = end
            continue
        body = text[end:close.start()]
        if body.strip() and body[:1] == " " and body[-1:] == " ":
            body = body[1:-1]
        out.append((start, close.end(), body))
        i = close.end()


def inline(text):
    """한 줄 글. 코드 구간을 자리표로 바꾼 뒤 escape·굵게·칩을 처리하고 되돌린다(굵게 안의 코드가 깨지지 않게)."""
    text = (text or "").replace("\x00", "")
    codes, parts, last = [], [], 0
    for start, end, body in _code_spans(text):
        parts += [text[last:start], SLOT.format(len(codes))]
        codes.append("<code>{}</code>".format(html.escape(body, quote=False)))
        last = end
    parts.append(text[last:])
    s = html.escape("".join(parts), quote=False)
    s = BOLD.sub(r"<strong>\1</strong>", s)
    s = TAG.sub(lambda m: '<span class="tag">[{}]</span>'.format(m.group(1)), s)
    return SLOT_RE.sub(lambda m: codes[int(m.group(1))], s)


def pair_html(text):
    """「앞 정본 줄 … | 지금: … | 바뀜: …」이면 지금·바뀐 뒤 두 칸 HTML, 아니면 None."""
    m = PAIR.match(text.strip())
    if not m:
        return None
    return ('<div class="pair"><div class="pair-head">{}</div><div class="del"><span class="pair-label">지금</span> {}</div>'
            '<div class="add"><span class="pair-label">바뀐 뒤</span> {}</div></div>').format(
        inline(m.group("head")), inline(m.group("now")), inline(m.group("new")))


def split_row(line):
    """표 한 줄의 칸. 코드 구간 안의 `|`와 `\\|`는 칸을 나누지 않는다(`\\|`는 `|`로 보인다)."""
    s = line.strip()
    spans = _code_spans(s)
    cells, cur, i, k = [], [], 0, 0
    while i < len(s):
        if k < len(spans) and i == spans[k][0]:
            cur.append(s[i:spans[k][1]].replace("\\|", "|"))
            i = spans[k][1]
            k += 1
            continue
        if s[i] == "\\" and s[i + 1:i + 2] == "|":
            cur.append("\\|")   # 칸을 나누지 않는다. 아래에서 `|`로 바꾼다
            i += 2
            continue
        if s[i] == "|":
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(s[i])
        i += 1
    cells.append("".join(cur))
    if s.startswith("|"):
        cells = cells[1:]
    if len(cells) > 1 and s.endswith("|") and not s.endswith("\\|") and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip().replace("\\|", "|") for c in cells]


def table_start(lines, i):
    """머리 줄과 구분 줄. 구분 줄의 칸 수가 머리와 같아야 한다(`x | y` 다음 `---`는 표가 아니다)."""
    if "|" not in lines[i] or i + 1 >= len(lines):
        return False
    width, sep = len(split_row(lines[i])), lines[i + 1]
    if "-" not in sep or ("|" not in sep and width > 1):
        return False
    cells = split_row(sep)
    return len(cells) == width and all(TABLE_SEP_CELL.match(c) for c in cells)


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _fence_close(line, mark):
    s = line.strip()
    return len(s) >= len(mark) and set(s) == {mark[0]}


def _block_start(lines, i):
    line = lines[i]
    return bool(FENCE_OPEN.match(line) or HEAD.match(line) or MARKER.match(line) or RULE.match(line) or table_start(lines, i))


def _table(lines, i):
    head = split_row(lines[i])
    rows, i = [], i + 2
    while i < len(lines) and lines[i].strip() and "|" in lines[i] and not (FENCE_OPEN.match(lines[i]) or HEAD.match(lines[i])):
        cells = split_row(lines[i])
        if len(cells) > len(head):   # 남는 칸은 마지막 칸에 붙인다(칸이 밀리지 않게)
            cells = cells[:len(head) - 1] + [" | ".join(cells[len(head) - 1:])]
        rows.append(cells + [""] * (len(head) - len(cells)))
        i += 1
    out = ['<div class="table"><table><thead><tr>']
    out += ["<th>{}</th>".format(inline(c)) for c in head]
    out.append("</tr></thead><tbody>")
    out += ["<tr>" + "".join("<td>{}</td>".format(inline(c)) for c in r) + "</tr>" for r in rows]
    out.append("</tbody></table></div>")
    return "".join(out), i


def _fence(lines, i, opts):
    m = FENCE_OPEN.match(lines[i])
    pad, mark, lang = len(m.group(1)), m.group(2), m.group(3).lower()
    body, i = [], i + 1
    while i < len(lines) and not _fence_close(lines[i], mark):
        body.append(lines[i][min(pad, _indent(lines[i])):])
        i += 1
    src = html.escape("\n".join(body), quote=False)
    if lang == "mermaid" and opts["mermaid"]:
        return (DIAGRAM_OPEN + '<p class="draw-note">{}</p><details open><summary>{}</summary><pre>{}</pre></details></figure>'
                .format(DIAGRAM_FAILED, DIAGRAM_SOURCE, src)), i + 1
    return "<pre>{}</pre>".format(src), i + 1


def _next_text(lines, i):
    return next((j for j in range(i, len(lines)) if lines[j].strip()), None)


def _list(lines, i, opts):
    """목록 하나. 항목의 몸은 첫 줄 글과, 표지보다 깊게 들여쓴 줄(내용 들여쓰기만큼 덜어 다시 변환)과 들여쓰지 않고 이어진 줄이다."""
    first = MARKER.match(lines[i])
    ordered = first.group(2)[0].isdigit()
    base = _indent(lines[i])
    start = int(first.group(2)[:-1]) if ordered else None
    items = []
    while i < len(lines):
        m = MARKER.match(lines[i])
        if not m or _indent(lines[i]) > base + 3 or m.group(2)[0].isdigit() != ordered:
            break
        number = int(m.group(2)[:-1]) if ordered else None
        content = _indent(lines[i]) + len(m.group(2)) + max(1, min(len(m.group(3)), 4))
        body, i = [m.group(4)], i + 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                nxt = _next_text(lines, i)
                if nxt is None or _indent(lines[nxt]) <= base:
                    break
                body.append("")
            elif _indent(line) > base:
                body.append(line[min(content, _indent(line)):])
            elif body[-1].strip() and not _block_start(lines, i):
                body.append(line.strip())
            else:
                break
            i += 1
        items.append((number, body))
        nxt = _next_text(lines, i)
        if nxt is not None and nxt > i and MARKER.match(lines[nxt]) and _indent(lines[nxt]) <= base + 3:
            i = nxt   # 빈 줄 뒤에 이어지는 같은 목록의 항목
    tag = "ol" if ordered else "ul"
    out = ['<ol start="{}">'.format(start) if ordered and start != 1 else "<{}>".format(tag)]
    expected = start
    for number, body in items:
        attr = ' value="{}"'.format(number) if ordered and number != expected else ""
        expected = number + 1 if ordered else None
        out.append("<li{}>{}</li>".format(attr, _item_body(body, opts)))
    out.append("</{}>".format(tag))
    return "".join(out), i


def _item_body(body, opts):
    """항목의 첫 문단은 <p> 없이 싣는다(촘촘한 목록)."""
    blocks = _blocks(body, opts)
    if blocks and blocks[0][0] == "p":
        return blocks[0][1][3:-4] + "".join(b for _, b in blocks[1:])
    return "".join(b for _, b in blocks)


def _paragraph(lines, i, opts):
    para = [lines[i].strip()]
    i += 1
    while i < len(lines) and lines[i].strip() and not _block_start(lines, i):
        para.append(lines[i].strip())
        i += 1
    pair = pair_html(para[0]) if len(para) == 1 else None
    if pair:
        return "pair", pair, i
    return "p", "<p>{}</p>".format(("<br>" if opts["breaks"] else " ").join(inline(p) for p in para)), i


def _blocks(lines, opts):
    """[(종류, HTML)]. 종류 "p"는 문단이다."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif FENCE_OPEN.match(line):
            block, i = _fence(lines, i, opts)
            out.append(("pre", block))
        elif _indent(line) >= 4 and not MARKER.match(line):
            code = []
            while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) >= 4):
                code.append(lines[i][4:])
                i += 1
            while not code[-1].strip():
                code.pop()
            out.append(("pre", "<pre>{}</pre>".format(html.escape("\n".join(code), quote=False))))
        elif HEAD.match(line):
            h = HEAD.match(line)
            level = min(len(h.group(1)) + 2, 5)
            out.append(("h", "<h{0}>{1}</h{0}>".format(level, inline(h.group(2)))))
            i += 1
        elif RULE.match(line):
            out.append(("hr", "<hr>"))
            i += 1
        elif table_start(lines, i):
            block, i = _table(lines, i)
            out.append(("table", block))
        elif MARKER.match(line):
            block, i = _list(lines, i, opts)
            out.append(("list", block))
        else:
            kind, block, i = _paragraph(lines, i, opts)
            out.append((kind, block))
    return out


def to_html(text, mermaid=True, breaks=True):
    """Markdown 글 → HTML 조각. mermaid가 False면 mermaid 울타리도 코드로 보인다. breaks면 문단 안 줄바꿈을 지킨다."""
    lines = (text or "").replace("\x00", "").replace("\r\n", "\n").replace("\t", "    ").split("\n")
    try:
        return "".join(b for _, b in _blocks(lines, {"mermaid": mermaid, "breaks": breaks}))
    except RecursionError:
        # 목록 표시를 수백 개 이은 줄처럼 중첩이 깊은 글은 원문으로 낸다. 한 장 만들기가 실패해 승인을 막지 않게 한다
        return "<pre>{}</pre>".format(html.escape("\n".join(lines)))


ITEM_NO = re.compile(r"^\[(\d+)\]\s+")
OPTION = re.compile(r"\(([가-힣])\)")
ASK_CELLS = ("정해 주실 것", "하실 일")


def items(body):
    """(칸 머리 줄, [(번호 또는 "", 항목 줄)]). 항목은 들여쓰지 않은 `- ` 줄과 그 아래 줄이다."""
    lead, its = [], []
    for line in (body or "").split("\n"):
        if line.startswith("- "):
            n = ITEM_NO.match(line[2:])
            its.append((n.group(1) if n else "", [line[2 + (n.end() if n else 0):]]))
        elif its:
            its[-1][1].append(line)
        elif line.strip():
            lead.append(line.strip())
    return lead, its


def first_option(cells):
    """(항목 번호, 선택지 표지) 또는 None: 「정해 주실 것」·「하실 일」 칸의 번호 달린 항목 가운데 처음으로 `(가)` 꼴 선택지가 든 것.
    다른 칸의 글이 선택지를 말하는 것(「확인 안 된 것」의 "원천 (나)에서는")은 고를 항목이 아니다."""
    for title, body in cells:
        if not (title[2:] if title.startswith("■ ") else title).startswith(ASK_CELLS):
            continue
        for no, lines in items(body)[1]:
            found = OPTION.findall("\n".join(lines))
            if no and found:
                return no, min(found)   # 항목 안의 첫 표지((가)가 (나)보다 앞)
    return None


def item_cards(cell_title, body):
    """승인 화면 칸 하나(■ 제목, `- [n] …` 항목들)를 칸 제목과 번호 원 카드로 낸다. 항목 아래 들여쓴 줄은 카드 안의 블록이다.
    「정해 주실 것」·「하실 일」 칸은 class ask(왼쪽 굵은 선)다."""
    title = cell_title[2:] if cell_title.startswith("■ ") else cell_title.strip()
    out = ['<section class="cell{}"><h3>{}</h3>'.format(" ask" if title.startswith(ASK_CELLS) else "", inline(title))]
    lead, its = items(body)
    if lead:
        out.append('<p class="lead">{}</p>'.format("<br>".join(inline(x) for x in lead)))
    for no, lines in its:
        rest = [l[2:] if l.startswith("  ") else l for l in lines[1:]]
        more = to_html("\n".join(rest)) if any(l.strip() for l in rest) else ""
        out.append('<div class="item">{}<div class="text"><p>{}</p>{}</div></div>'.format(
            '<span class="no">{}</span>'.format(no) if no else "", inline(lines[0]), more))
    out.append("</section>")
    return "".join(out)
