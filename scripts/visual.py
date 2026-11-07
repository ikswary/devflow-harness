"""승인 화면 뒤에 붙이는 「보는 자료」 블록을 낸다. 정본의 표와 와이어프레임 경로를 그대로 옮긴다(설계 B 3.6, D-5).

원천은 머리 파일 「정본의 절」·「건드릴 파일」 글에 적힌 `spec\\`·`ui\\`·`design\\` 경로(실행 폴더 기준, 있는 파일만,
처음 나온 차례)다. kind 이름으로 가르지 않는다. 등록표 `verify_family`인 task는 대신 그 task `result.md` 「본문」을 본다.
- `design\\…md`: 제목에 "결정"이 든 절의 표
- `spec\\brief.md`: 제목에 "여정"·"화면 흐름"이 든 절의 표
- 그 밖의 `spec\\…md`: FR 줄에서 만든 `| 정책 | FR | AC |` 추적표, FR 줄이 없으면 제목에 "인수 기준"이 든 절의 표
- `ui\\wireframes\\…html`: `- 와이어프레임: file:///{절대 경로}` 한 줄(`ui\\…md`는 쓰지 않는다)
- 검증 무리: 「본문」의 표 가운데 머리 줄에 "인수 기준"이 든 것

첫 줄 뒤 줄이 「이번 실행의 값」 `보는 자료 줄 수`를 넘으면 전체를 `tasks\\{id}\\visual.md`에 쓰고,
앞 그만큼의 줄과 `- 전체 {첫 줄 뒤 줄 수}줄: {visual.md 절대 경로}`를 낸다. `screen.py`는 결과 본문을 읽지 않으므로 따로 둔다.

사용:
  python visual.py {실행 폴더} {task id}     종료 0 / 2(사용법·task 없음)
  python visual.py {실행 폴더} {task id} --sheet
    브라우저 한 장(설계 4.2절). tasks\\{id}\\sheet.html을 쓰고 `한 장: file:///…`을 낸다. 스크립트 없는 고정 틀이고 값은 모두
    이스케이프하며, 비밀값의 값 꼴과 전화번호·메일 꼴은 가린다(타입 이름과 한글 문장은 두므로 모든 꼴을 잡지는 못한다).
    만들지 못하면 `한 장 없음: {이유} ({재료 폴더})`이고 승인은 막지 않는다.
    「이번 실행의 값」 `한 장 올리기`가 `허용`이면 `올릴 파일: {경로}`를 함께 낸다(references/main/sheet-upload.md). 게시 때 문서 뼈대로 감싸이므로
    이미지는 data:로 넣고, 색은 토큰으로 두고, 스크립트와 바깥 자원을 쓰지 않는다.
  python visual.py {실행 폴더} {task id} --sheet --once
    값이 `없음`이어도 그 한 번을 위해 크기를 보고 `올릴 파일:`을 낸다. 값은 바꾸지 않는다.
  python visual.py {실행 폴더} {task id} --sheet-sent "링크"
  python visual.py {실행 폴더} {task id} --sheet-failed "사유"
    올린 결과를 journal에 한 줄 남긴다. `collect.py --measure`가 센다. `--sheet-sent`의 표지가 지금 한 장과 맞을 때만 화면이 자료를 접는다.
    1.2.0부터 시작한 task는 머리에 판과 터미널 번호를 적고, 요구사항 정본의 `담당이 채움`·`[바뀜:]` 표지를 모으며,
    설계 정본의 제안 도면·시험 표·흐름 지도를 펼친다. 도면은 코드 원문으로 싣는다(틀에 스크립트가 없다).
  python visual.py {실행 폴더} --run
    실행 지도(설계 7.3절). 정본과 기록에서 만들어 {실행 폴더}\\run-map.md에 쓰고 표준 출력에도 낸다. 읽는 자료이고 판정 근거가 아니다.
    값이 없는 칸은 제목도 쓰지 않는다. 흐름이 하나 이하면 줄기를 첫 줄 한 줄로 줄이고 펼친 지도는 파일에만 둔다.
  python visual.py {실행 폴더} {task id} --wrap-review
    마무리 리뷰(설계 7.3절). tasks\\{id}\\wrap-review.md를 쓰고 screen.py가 마무리 실행 승인 화면에 싣는다. 못 읽은 값은 재지 못함으로 낸다.
  python visual.py {실행 폴더} --run --flow {흐름}
    리뷰 화면에 싣는 자리 한 줄(`실행 지도: 요구사항 묶음 {묶음}(상세 {id}) / 흐름 {n}개 가운데 하나`). 파일을 쓰지 않는다. 없는 흐름이면 종료 2
"""
import base64
import difflib
import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import board
import collect
import decisions
import deploy_reuse
import devflow_lib
import flow_review
import kinds
import places
import project_docs
import screen

# 원천의 종류(kind 이름과 겹치지 않는 낱말. 엔진 코드의 kind 문자열은 engine_hooks가 있는 kind만, 시험 1(d))
DECISION, JOURNEY, SPEC, WIRE, VERIFY = "decision", "journey", "spec", "wire", "verify"
TABLE_WORDS = {DECISION: ("결정",), JOURNEY: ("여정", "화면 흐름"), SPEC: ("인수 기준",)}
LIMIT_KEY = "보는 자료 줄 수"

SOURCE_RE = devflow_lib.CANON_PATH_RE
HEADING_RE = re.compile(r"^(#{1,3}) (.+)$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
IMAGE_ENDS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
IMAGE_LIMIT = 2 * 1024 * 1024   # 캡처 한 장의 바이트. 넘으면 싣지 않고 경로만 적는다
UPLOAD_LIMIT = 16 * 1024 * 1024   # Artifact 한 쪽의 상한
LINE_HEAD = r"^\s*(?:[-*]\s+|\|\s*|#+\s*)?"
FR_HEAD_RE = re.compile(LINE_HEAD + r"(FR-[\w-]+)")
AC_HEAD_RE = re.compile(LINE_HEAD + r"(AC-[\w-]+)")
POLICY_RE = re.compile(r"(?<![\w-])P-\d+(?![\w-])")
TRACE_HEAD = ["| 정책 | FR | AC |", "|---|---|---|"]


def _kind_of(rel):
    q = rel.replace("\\", "/").lower()
    if q.startswith("design/") and q.endswith(".md"):
        return DECISION
    if q == "spec/brief.md":
        return JOURNEY
    if q.startswith("spec/") and q.endswith(".md"):
        return SPEC
    if q.startswith("ui/wireframes/") and q.endswith(".html"):
        return WIRE
    return None


def sources(run_dir, t, names=("정본의 절", "건드릴 파일")):
    """[(종류, 실행 폴더 기준 경로)]. 경로는 `\\` 구분으로 적는다. 실행 폴더 안의 있는 파일만, 처음 나온 차례로 겹침 없이."""
    tid = t.get("id", "")
    entry = kinds.KINDS.get(t.get("kind", ""))
    if entry is not None and entry.verify_family:
        rel = "tasks\\{}\\result.md".format(tid)
        return [(VERIFY, rel)] if os.path.isfile(os.path.join(run_dir, "tasks", tid, "result.md")) else []
    secs = t.get("_sections", {})
    text = "\n".join(secs.get(name, "") for name in names)
    out, seen = [], set()
    for m in SOURCE_RE.finditer(text):
        rel = m.group(0).rstrip(".:;").replace("/", "\\")
        kind = _kind_of(rel)
        if kind is None or rel.lower() in seen:
            continue
        path = os.path.join(run_dir, *rel.split("\\"))
        if os.path.isfile(path) and devflow_lib.inside(run_dir, path):
            seen.add(rel.lower())
            out.append((kind, rel))
    return out


def tables_under(text, words):
    """[(절 제목, `|` 줄 목록)]: 제목에 words 가운데 하나가 든 ##·### 절마다(표 줄이 있는 절만). 울타리 안은 보지 않는다."""
    out, title, rows, fence = [], None, [], False

    def close():
        if title is not None and rows and any(w in title for w in words):
            out.append((title, rows))

    for line in text.splitlines():
        if FENCE_RE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            close()
            title, rows = (m.group(2).strip() if len(m.group(1)) >= 2 else None), []
        elif line.lstrip().startswith("|"):
            rows.append(line.strip())
    close()
    return out


def _ids(pattern, line):
    out = []
    for x in pattern.findall(line):
        if x not in out:
            out.append(x)
    return out


def trace_rows(text, ac_re=AC_HEAD_RE, fr_re=FR_HEAD_RE):
    """`| 정책 | FR | AC |` 표(머리 둘 줄 포함). FR 줄이 없으면 빈 목록.
    FR 줄: 줄머리(`- `·`| `·`#` 뒤)가 FR id인 줄. 정책은 같은 줄의 `P-n`, AC는 줄머리가 AC id이고 그 FR id를 담은 줄."""
    lines = text.splitlines()
    acs = [(m.group(1), line) for line in lines for m in [ac_re.match(line)] if m]
    rows, seen = [], set()
    for line in lines:
        m = fr_re.match(line)
        if not m or m.group(1) in seen:
            continue
        fr = m.group(1)
        seen.add(fr)
        has_fr = re.compile(r"(?<![\w-])" + re.escape(fr) + r"(?![\w-])")
        ac = []
        for aid, aline in acs:
            if has_fr.search(aline) and aid not in ac:
                ac.append(aid)
        rows.append("| {} | {} | {} |".format(", ".join(_ids(POLICY_RE, line)), fr, ", ".join(ac)))
    return TRACE_HEAD + rows if rows else []


def _verify_tables(text):
    """「본문」의 표(이어진 `|` 줄 묶음) 가운데 머리 줄에 "인수 기준"이 든 것."""
    body = devflow_lib.sections(text).get("본문", "")
    blocks, cur = [], []
    for line in body.splitlines() + [""]:
        if line.lstrip().startswith("|"):
            cur.append(line.strip())
        elif cur:
            blocks.append(cur)
            cur = []
    return [("본문", b) for b in blocks if "인수 기준" in b[0]]


def _source_lines(run_dir, kind, rel):
    path = os.path.join(run_dir, *rel.split("\\"))
    if kind == WIRE:
        return ["- 와이어프레임: file:///" + os.path.abspath(path).replace("\\", "/").lstrip("/")]
    text = devflow_lib.read_text(path)
    if kind == VERIFY:
        found = _verify_tables(text)
    elif kind == SPEC:
        rows = trace_rows(text)
        found = [("추적표", rows)] if rows else tables_under(text, TABLE_WORDS[SPEC])
    else:
        found = tables_under(text, TABLE_WORDS[kind])
    if not found:
        return ["- 없음 ({}에 고를 표 없음)".format(rel)]
    out = []
    for title, rows in found:
        out.append("- {} 「{}」".format(rel, title))
        out += rows
    return out


def build(run_dir, tid):
    """「보는 자료」 블록 전체(줄 수 상한을 적용하기 전). 첫 줄은 `■ 보는 자료`."""
    t = devflow_lib.load_task(os.path.join(run_dir, "tasks", tid, "task.md"))
    t.setdefault("id", tid)
    out = ["■ 보는 자료"]
    srcs = sources(run_dir, t)
    if not srcs:
        return out + ["- 없음 (정본의 절·건드릴 파일에 원천 경로 없음)"]
    for kind, rel in srcs:
        out += _source_lines(run_dir, kind, rel)
    return out


MASK, KEY_BLOCK, mask_line = devflow_lib.MASK, devflow_lib.KEY_BLOCK, devflow_lib.mask_line
DOC_LIMIT = 400000   # 글자. 넘는 문서는 한 장에 싣지 않고 경로만 적는다
SHEET_CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'"
SHEET_VIEWPORT = "width=device-width,initial-scale=1,viewport-fit=cover"
SHEET_TITLE_CHARS = 40
SHEET_LIGHT = "--bg:#fff;--fg:#222;--line:#ccc;--code:#f5f5f2;--add:#e4f5e4;--del:#fae4e4"
SHEET_DARK = "--bg:#1c1c1a;--fg:#ddd;--line:#555;--code:#2a2a27;--add:#23402a;--del:#4a2626;color-scheme:dark"
# 어두운 화면은 시스템 설정과 게시 화면의 data-theme을 모두 따른다. 와이어프레임은 자기 틀 안의 밝은 문서라 바탕을 흰색으로 둔다
SHEET_STYLE = (":root{" + SHEET_LIGHT + "}"
               '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){' + SHEET_DARK + "}}"
               ':root[data-theme="dark"]{' + SHEET_DARK + "}"
               "body{font:15px/1.6 system-ui,sans-serif;max-width:64rem;margin:0 auto;padding-block:1rem;"
               "padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));"
               "color:var(--fg);background:var(--bg);overflow-wrap:anywhere}"
               "h1{font-size:1.25rem}h2{font-size:1.05rem;border-bottom:1px solid var(--line);padding-bottom:.2rem;margin-top:1.6rem}"
               "pre{background:var(--code);padding:.6rem;overflow-x:auto;white-space:pre-wrap;overflow-wrap:anywhere}"
               ".add{background:var(--add)}.del{background:var(--del)}img{max-width:100%;height:auto}"
               "iframe{box-sizing:border-box;width:100%;height:28rem;border:1px solid var(--line);background:#fff}")
OPEN_SECTIONS = ("제안 도면", "시험 표", "흐름 지도", "배포 구성도")   # 설계 정본에서 처음부터 펼칠 절(설계 7.6절)
ELEMENT_ID = re.compile(r"""data-el\s*=\s*["']([^"']+)["']""")


def _text(path):
    try:
        return devflow_lib.read_text(path)
    except UnicodeError:
        raise ValueError("UTF-8이 아닌 파일: {}".format(path))


def _revised_files(t, ext):
    """[(정본 기준 경로, 고친 판 경로)]. 변경 task가 `revised\\`에 쓴 파일이고 그 폴더 안에 있는 것만이다."""
    revised = os.path.join(t["_dir"], "revised")
    out = []
    for folder, _, names in sorted(os.walk(revised)):
        for name in sorted(names):
            path = os.path.join(folder, name)
            if name.endswith(ext) and devflow_lib.inside(revised, path):
                out.append((os.path.relpath(path, revised), path))
    return out


def changed_documents(run_dir, t):
    """[(정본 경로, 기준 글 또는 None, 지금 글)]. 변경 task는 앞 승인판(정본)과 고친 판을 견주고, 작성 task는 「건드릴 파일」의 정본을 기준본(`base\\`, 설계 7.5절)과 견준다.
    기준본이 없으면 새 문서다. 설계 정본은 넣는 절이 일부뿐이라 새 문서로 두고 sheet_html이 그 절의 변경분을 따로 싣는다. 「정본의 절」은 task가 읽는 문서이므로 올리지 않는다."""
    if _revised_files(t, ".html") or _revised_files(t, ".md"):
        out = []
        for rel, path in _revised_files(t, ".md"):
            canon = os.path.join(run_dir, rel)
            out.append((rel, _text(canon) if os.path.isfile(canon) else None, _text(path)))
        return out
    return [(rel, None if _kind_of(rel) == DECISION else project_docs.base_text(run_dir, rel), _text(os.path.join(run_dir, *rel.split("\\"))))
            for rel in devflow_lib.written_canon(run_dir, t) if _kind_of(rel) in (DECISION, JOURNEY, SPEC)]


def wire_pairs(run_dir, t):
    """[(정본 경로, 앞 승인판 또는 None, 볼 판)]. 고친 와이어프레임이 먼저이고, 나머지는 머리 파일이 가리키는 정본이다."""
    out, seen = [], set()
    for rel, path in _revised_files(t, ".html"):
        if _kind_of(rel) == WIRE:
            canon = os.path.join(run_dir, rel)
            out.append((rel, _text(canon) if os.path.isfile(canon) else None, _text(path)))
            seen.add(rel.lower())
    for kind, rel in sources(run_dir, t):
        if kind == WIRE and rel.lower() not in seen:
            out.append((rel, project_docs.base_text(run_dir, rel), _text(os.path.join(run_dir, *rel.split("\\")))))
    return out


def _diff_block(before, after, safe):
    """원문으로 비교한 뒤 낼 줄만 가린다. 앞뒤를 따로 가려 비교하면 값이 바뀐 줄이 사라진다."""
    rows = []
    for line in list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=3))[2:]:
        if line.startswith("@@"):
            rows.append("<div>{}</div>".format(html.escape(line)))
            continue
        style = {"+": "add", "-": "del"}.get(line[:1], "")
        shown = html.escape(line[:1] + safe(line[1:]))
        rows.append('<div class="{}">{}</div>'.format(style, shown) if style else "<div>{}</div>".format(shown))
    return "".join(rows)


def _table_changes(before, after):
    """바뀐 문서 행(규칙과 요구사항은 표에 있다). (뺀 줄, 더한 줄)."""
    old = [l.strip() for l in before.splitlines() if l.lstrip().startswith("|")]
    new = [l.strip() for l in after.splitlines() if l.lstrip().startswith("|")]
    return [l for l in old if l not in new], [l for l in new if l not in old]


def design_sections(text):
    """{절 제목: 그 절의 글}: 정본에서 처음부터 펼쳐 보일 절(설계 7.2절). 제목에 낱말이 든 ##·### 절을 다음 같은 층 제목 앞까지 원문 그대로 낸다.
    제목 전체가 키라 도면 여러 절이 모두 나온다. 다이어그램 코드도 원문이다. 틀에 스크립트가 없어 그리지 않는다."""
    out, word, level, rows, fence = {}, None, 0, [], False

    def close():
        if word is not None and word not in out:
            out[word] = "\n".join(rows).strip()

    for line in text.splitlines():
        if FENCE_RE.match(line):
            fence = not fence
        m = HEADING_RE.match(line) if not fence else None
        if m and (word is None or len(m.group(1)) <= level):
            close()
            found = len(m.group(1)) >= 2 and any(w in m.group(2) for w in OPEN_SECTIONS)
            word, level, rows = (m.group(2).strip() if found else None), len(m.group(1)), []
        elif word is not None:
            rows.append(line)
    close()
    return out


def _spec_blocks(text, safe):
    """요구사항 정본의 표지 모음(설계 7.6절): 기능 요구사항 전부, 표지 있는 인수 기준(펼침), 나머지 인수 기준과 번호 추적표(접음)."""
    rows = devflow_lib.ac_rows(text)
    frs = [line.strip() for line in text.splitlines() if devflow_lib.FR_ROW_RE.match(line)]
    if not rows and not frs:
        return []
    def marked(row):
        return devflow_lib.MARK_FILLED in row or devflow_lib.MARK_CHANGED in row
    picked = [row for _, row in rows if marked(row)]
    rest = [row for _, row in rows if not marked(row)]
    out = ["<h3>기능 요구사항 {}개</h3>".format(len(frs)), "<pre>{}</pre>".format(html.escape(safe("\n".join(frs))))] if frs else []
    if picked:
        out += ["<h3>표지가 있는 인수 기준 {}개</h3>".format(len(picked)), "<pre>{}</pre>".format(html.escape(safe("\n".join(picked))))]
    if rest:
        out.append("<details><summary>나머지 인수 기준 {}개</summary><pre>{}</pre></details>".format(len(rest), html.escape(safe("\n".join(rest)))))
    trace = trace_rows(text, devflow_lib.AC_ROW_RE, devflow_lib.FR_ROW_RE)
    if trace:
        out.append("<details><summary>번호 추적표</summary><pre>{}</pre></details>".format(html.escape(safe("\n".join(trace)))))
    return out


def _head_blocks(run_dir, t, safe):
    """한 장 머리의 판과 터미널 번호(설계 4.2절). 번호는 screen.py가 매긴 그대로다. 화면 재료를 못 읽어도 한 장을 막지 않는다."""
    res = os.path.join(t["_dir"], "result.md")
    stamp = datetime.fromtimestamp(os.path.getmtime(res)).strftime("%Y-%m-%d %H:%M:%S") if os.path.isfile(res) else "없음"
    try:
        retry = int(str(t.get("retry", "") or "0").strip() or 0)
    except ValueError:
        retry = 0
    out = ["<p>판 {} · 결과 {}</p>".format(retry + 1, stamp)]
    try:
        b = screen.build(run_dir, t.get("id", ""))
    except (devflow_lib.Reject, KeyError, OSError, UnicodeError, ValueError):
        return out
    if "error" not in b and screen.material_missing(b):
        out.append("<p>{}</p>".format(html.escape(safe(screen.MATERIAL_MISSING))))
    out += ["<p>{}</p>".format(html.escape(safe(line))) for line in (screen.head_lines(b)[:1] if "error" not in b else [])]
    lines = []
    for title, body in screen.cell_blocks(b) if "error" not in b else []:
        lines += [line[2:] for line in body.splitlines() if screen.ITEM_LINE.match(line)] if body else [title[2:]]
    if lines:
        out += ["<h2>터미널 번호</h2>", "<pre>{}</pre>".format(html.escape(safe("\n".join(lines))))]
    return out


def _captures(t, value, safe):
    """캡처 칸의 파일(task 폴더 안의 이미지만)을 싣는다. 없거나 밖이면 경로만 적는다."""
    out = []
    for rel in re.split(r"[,\n]", str(value or "")):
        rel = rel.strip().strip("`")
        if not rel:
            continue
        path = os.path.join(t["_dir"], *rel.replace("\\", "/").split("/"))
        if os.path.isfile(path) and devflow_lib.inside(t["_dir"], path) and rel.lower().endswith(IMAGE_ENDS):
            if os.path.getsize(path) > IMAGE_LIMIT:
                out.append("<p>캡처가 커서 뺌: {} ({}바이트). 파일을 직접 보세요.</p>".format(html.escape(safe(rel)), os.path.getsize(path)))
                continue
            # 올린 뒤에도 보이도록 파일 경로가 아니라 내용을 싣는다
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            out.append('<p><img alt="{}" src="data:{};base64,{}"></p>'.format(html.escape(safe(rel), quote=True), IMAGE_TYPES[os.path.splitext(rel)[1].lower()], data))
        else:
            out.append("<p>캡처 없음: {}</p>".format(html.escape(safe(rel))))
    return out


def _scenario_blocks(t, safe):
    """칸 2의 전문. 터미널은 자른 줄이다."""
    data = flow_review.read(t)
    out = ["<h2>실제로 돌려 본 결과</h2>"]
    if data["problem"]:
        out.append("<p>{}: {}</p>".format(flow_review.UNREAD, html.escape(safe(data["problem"]))))
    for row in data["rows"]:
        out.append("<h3>{} ({})</h3>".format(html.escape(safe(row["name"])), html.escape(flow_review.state(row))))
        for label, value in row["fields"].items():
            if label == "캡처":
                out += _captures(t, value, safe)
            else:
                out.append("<h4>{}</h4><pre>{}</pre>".format(html.escape(label), html.escape(safe(value))))
    out += ["<p>읽지 못한 줄: {}</p>".format(html.escape(safe(line))) for line in data["stray"]]
    return out


def _drawing_blocks(run_dir, t, opened, safe):
    """제안 도면과 생성본의 다른 곳(설계 7.2절). 달라도 실패가 아니고 같으면 싣지 않는다. 도면은 원문 표시를 유지한다."""
    drawings = {word: text for word, text in opened.items() if "제안 도면" in word}
    folder = places.code_folder(run_dir, t)
    if not drawings or not folder:
        return []
    lines = project_docs.drawing_differences(run_dir, drawings, folder)
    if lines == [project_docs.NO_GENERATOR]:
        return ["<p>{}</p>".format(html.escape(project_docs.NO_GENERATOR))]
    return ["<h3>설계와 달라진 점</h3>", "<pre>{}</pre>".format(html.escape(safe("\n".join(lines))))] if lines else []


def _design_blocks(run_dir, tasks, t, summary, safe):
    """구조도 변경분과 시험 표 대조. 설계 정본의 제안과 설계 행에 없던 파일을 함께 싣는다."""
    parent = tasks.get(t.get("parent", ""))
    opened = {}
    for kind, rel in sources(run_dir, parent, ("건드릴 파일",)) if parent else ():
        if kind == DECISION:
            opened.update(design_sections(_text(os.path.join(run_dir, *rel.split("\\")))))
    out = ["<h2>구조도와 시험 표</h2>"]
    if not opened:
        out.append("<p>{}: 이 검증의 부모 설계에서 제안 도면과 시험 표를 찾지 못함</p>".format(flow_review.UNREAD))
    for word, text in opened.items():
        out += ["<h3>{}</h3>".format(html.escape(safe(word))), "<pre>{}</pre>".format(html.escape(safe(text)))]
    out += ["<h3>설계 제안과 다른 곳(코드 task의 「건드릴 파일」에 없던 파일)</h3>",
            "<pre>{}</pre>".format(html.escape(safe("\n".join(summary["outside"]) or "없음")))]
    out += _drawing_blocks(run_dir, t, opened, safe)
    notes = [line for o in places.check_tasks(tasks, t["id"]) for line in screen.test_change_notes(o)]
    out += ["<h3>시험 표 대조</h3>", "<pre>{}</pre>".format(html.escape(safe("\n".join(notes) or "판정자 대조 줄 없음")))]
    return out


def _flow_blocks(run_dir, t, safe):
    """흐름 리뷰의 한 장(설계 7.1절 표): 전·후 전문과 캡처, 구조도 변경분, 시험 표 대조, API·데이터 모델 변경분, 남긴 곳, 코드 요약."""
    tasks = devflow_lib.load_tasks(run_dir)
    summary = flow_review.code_summary(run_dir, tasks, t)
    out = _scenario_blocks(t, safe) + _design_blocks(run_dir, tasks, t, summary, safe)
    changes = flow_review.data_changes(run_dir, summary, t)
    out.append("<h2>API·데이터 모델 변경분(파일 이름 꼴로만 찾음)</h2>")
    if not changes:
        out.append("<p>없음</p>")
    for name, diff in changes:
        out += ["<h3>{}</h3>".format(html.escape(safe(name))), "<pre>{}</pre>".format(html.escape(safe(diff)))]
    left = places.read(run_dir, t["id"])
    rows = places.left_lines(left)
    rows += [raw for p in left if p.get("처리", "").startswith("남김") and p.get("의견") == places.PROBLEM for raw in p["의견 줄"]]
    out += ["<h2>남긴 곳</h2>", "<pre>{}</pre>".format(html.escape(safe("\n".join(rows) or "없음")))]
    people, unread = flow_review.people(tasks, t)
    summary_rows = ["규모: 파일 {}개, +{} -{}".format(len(summary["files"]), summary["plus"], summary["minus"]),
                    "구조 변화: 새 폴더 {} / 지운 파일 {}".format(", ".join(summary["new_dirs"]) or "없음", ", ".join(summary["deleted"]) or "없음"),
                    "경계 위반: 이 요약은 재지 않는다(린트를 돌리지 않고 파일 목록만 봄)",
                    "규약 추가: {}건".format(summary["rules"])]
    if summary["unmeasured"]:
        summary_rows.append("{}: {}(커밋을 읽지 못함)".format(flow_review.UNREAD, ", ".join(summary["unmeasured"])))
    if summary["old"]:
        summary_rows.append("{}: {}(판단 기록 없는 옛 코드 task)".format(flow_review.UNREAD, ", ".join(summary["old"])))
    summary_rows += ["사람이 볼 곳: " + flow_review.NO_PEOPLE] if not people and not unread and not summary["old"] else []
    summary_rows += ["사람이 볼 곳: {} {}: {}".format(tid, where, why) for tid, where, why in people]
    summary_rows += ["사람이 볼 곳을 {}: {}".format(flow_review.UNREAD, ", ".join(unread))] if unread else []
    out += ["<h2>코드 요약</h2>", "<pre>{}</pre>".format(html.escape(safe("\n".join(summary_rows))))]
    out += ["<details><summary>전체 변경 파일 {}개</summary><pre>{}</pre></details>".format(
        len(summary["files"]), html.escape(safe("\n".join("{} {}".format(mark, name) for name, mark in summary["files"].items()))))]
    return out


def sheet_html(run_dir, t):
    """(한 장 HTML, 가린 줄 수) 또는 (None, 0). 실을 자료가 없으면 None이다. 차례는 설명 → 모양 → 바뀐 규칙 → 줄 단위 변경분이다."""
    tid = t.get("id", "")
    v120 = devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)
    res = os.path.join(t["_dir"], "result.md")
    top = devflow_lib.sections(_text(res), level=2) if os.path.isfile(res) else {}
    material = devflow_lib.sections(top.get("승인 화면", ""), level=3).get("리뷰 자료", "").strip()
    wires = wire_pairs(run_dir, t)
    docs = changed_documents(run_dir, t)
    review = devflow_lib.flow_review_rules(t)
    wrap_review = os.path.join(t["_dir"], REVIEW_FILE)
    wrap_review = _text(wrap_review) if v120 and os.path.isfile(wrap_review) else ""
    if not material and not wires and not docs and not review and not wrap_review:
        return None, 0
    hidden = set()   # 같은 줄이 표와 변경분에 함께 나와도 한 줄로 센다

    def safe(text):
        out = []
        for line in KEY_BLOCK.sub(MASK, text).splitlines():
            clean = mask_line(line)
            if MASK in clean:
                hidden.add(line)
            out.append(clean)
        return "\n".join(out)

    def frame(text):
        return '<iframe sandbox srcdoc="{}"></iframe>'.format(html.escape(safe(text), quote=True))

    def over_limit(rel, *texts):
        size = max(len(x) for x in texts if x)
        return "<p>크기 때문에 뺌: {} ({}자). 파일을 직접 보세요.</p>".format(html.escape(safe(rel)), size) if size > DOC_LIMIT else ""

    body = ["<h1>{} {}</h1>".format(html.escape(safe(tid)), html.escape(safe(str(t.get("title", "")))))]
    head = _head_blocks(run_dir, t, safe) if v120 else []
    body += head[:1]   # 판 줄. 사람은 문제와 고치는 법을 먼저 보고, 그다음 정할 것과 번호를 본다
    if material:
        title, lines = screen.material_parts(material, "이 흐름이 한 일" if review else "이 task가 한 일")
        body += ["<h2>{}</h2>".format(html.escape(safe(title))), "<pre>{}</pre>".format(html.escape(safe("\n".join(lines))))]
    body += head[1:]
    if v120 and t.get("kind") == "deploy-plan":
        commands = deploy_reuse.sheet_lines(run_dir, t)
        if commands:
            body += ["<h2>명령과 되돌리기</h2>", "<pre>{}</pre>".format(html.escape(safe("\n".join(commands))))]
    if review:
        body += _flow_blocks(run_dir, t, safe)
    if wrap_review:
        body += ["<h2>마무리 리뷰</h2>", "<pre>{}</pre>".format(html.escape(safe(wrap_review)))]
    for rel, before, after in wires:
        body.append("<h2>모양: {}</h2>".format(html.escape(safe(rel))))
        big = over_limit(rel, before, after)
        if big:
            body.append(big)
            continue
        found = set(ELEMENT_ID.findall(after))
        if before is None:
            body.append(frame(after))
            if found:
                body.append("<p>요소: {}</p>".format(html.escape(safe(", ".join(sorted(found))))))
            continue
        body += ["<h3>고치기 전</h3>", frame(before), "<h3>고친 뒤</h3>", frame(after)]
        old = set(ELEMENT_ID.findall(before))
        body.append("<p>요소 더함: {} / 요소 뺌: {}</p>".format(html.escape(safe(", ".join(sorted(found - old)) or "없음")),
                                                          html.escape(safe(", ".join(sorted(old - found)) or "없음"))))
    for rel, before, after in docs:
        body.append("<h2>문서: {}</h2>".format(html.escape(safe(rel))))
        big = over_limit(rel, before, after)
        if big:
            body.append(big)
            continue
        opened = design_sections(after) if v120 and _kind_of(rel) == DECISION else {}
        if before is None:
            for word, text in opened.items():
                body += ["<h3>{}</h3>".format(html.escape(safe(word))), "<pre>{}</pre>".format(html.escape(safe(text)))]
            if v120 and _kind_of(rel) == SPEC:
                body += _spec_blocks(after, safe)
            body.append("<details><summary>새 문서 전체</summary><pre>{}</pre></details>".format(html.escape(safe(after))))
            base = project_docs.base_text(run_dir, rel)
            if base is not None and _kind_of(rel) == DECISION:
                body.append("<details><summary>프로젝트 문서와 달라진 곳</summary><pre>{}</pre></details>".format(
                    _diff_block(KEY_BLOCK.sub(MASK, base), KEY_BLOCK.sub(MASK, project_docs.projection(rel, after)), safe)))
            continue
        if v120 and _kind_of(rel) == SPEC and not _revised_files(t, ".md"):
            body += _spec_blocks(after, safe)
        old_open = design_sections(before)
        for word, text in opened.items():
            if text != old_open.get(word):
                body += ["<h3>바뀐 {}</h3>".format(html.escape(safe(word))), "<pre>{}</pre>".format(html.escape(safe(text)))]
        before, after = KEY_BLOCK.sub(MASK, before), KEY_BLOCK.sub(MASK, after)
        removed, added = _table_changes(before, after)
        if removed or added:
            body.append("<h3>바뀐 규칙과 요구사항</h3>")
            body += ['<div class="del">{}</div>'.format(html.escape(safe(l))) for l in removed]
            body += ['<div class="add">{}</div>'.format(html.escape(safe(l))) for l in added]
        body.append("<details><summary>줄 단위 변경분</summary><pre>{}</pre></details>".format(_diff_block(before, after, safe)))
    if hidden:
        body.append("<p>{}줄을 가렸습니다.</p>".format(len(hidden)))
    name = "{} {}".format(safe(tid), safe(str(t.get("title", "")))).strip()[:SHEET_TITLE_CHARS]
    page = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="{}">'
            '<meta name="claude:viewport-fit-sides" content="cover"><meta http-equiv="Content-Security-Policy" content="{}">'
            "<title>{}</title><style>{}</style></head><body>{}</body></html>").format(
        SHEET_VIEWPORT, html.escape(SHEET_CSP, quote=True), html.escape(name), SHEET_STYLE, "".join(body))
    return page, len(hidden)


def sheet(run_dir, tid, once=False):
    """한 장을 쓰고 경로 줄을 낸다. 실패해도 승인을 막지 않고, 앞 판의 한 장을 남기지 않는다."""
    task_dir = os.path.abspath(os.path.join(run_dir, "tasks", tid))
    path = os.path.join(task_dir, "sheet.html")
    try:
        if os.path.exists(path):
            os.remove(path)
        t = devflow_lib.load_task(os.path.join(task_dir, "task.md"))
        t.setdefault("id", tid)
        page, hidden = sheet_html(run_dir, t)
        if page is None:
            print("한 장 없음: 실을 자료가 없음 ({})".format(task_dir))
            return 0
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
    except (devflow_lib.Reject, OSError, UnicodeError, ValueError) as e:
        print("한 장 없음: {} ({})".format(e, task_dir))
        return 0
    print("한 장: " + Path(path).as_uri() + (" ({}줄 가림)".format(hidden) if hidden else ""))
    if once or devflow_lib.sheet_upload(run_dir) == "허용":
        size = os.path.getsize(path)
        print("올리지 못함: {}바이트가 상한 {}을 넘음".format(size, UPLOAD_LIMIT) if size > UPLOAD_LIMIT else "올릴 파일: " + path)
    return 0


def sheet_mark(run_dir, tid, kind, text):
    """올린 결과 한 줄. 사유에 값이 섞여도 journal에 남지 않게 가린다."""
    t = devflow_lib.load_task(os.path.join(run_dir, "tasks", tid, "task.md"))
    devflow_lib.sheet_sent_write(t, text.strip() if kind == devflow_lib.SHEET_SENT else "")
    devflow_lib.journal_append(run_dir, kind, tid, mask_line(" ".join(text.split())))
    print("{}: {}".format(kind, tid))
    return 0


# ---------------------------------------------------------------- 실행 지도(--run, 설계 7.3절)

READ_ERRORS = (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError)
MAP_TITLE = "■ 실행 지도"
MAP_FILE = "run-map.md"
REQUIREMENT_BLOCK = "요구사항"
DECISION_BLOCKS = (REQUIREMENT_BLOCK, "설계")   # 「알릴 것」이 작성자가 정한 결정인 블록
COUNTED_ROLES = ("feature", "fixes")   # 합치기·배포 흐름은 지도의 흐름 수에 세지 않는다
PASSED = "통과"
VERDICTS = (PASSED, "실패", "판정불가")
OTHER_VERDICT = "기타"
CLIP = 160
STEM_TITLES = ("요구사항", "결정", "흐름", "증거", "명령·배포", "넣은 산출물")   # 줄기. 나머지 칸은 따로 두는 줄이다
# 옛 실행은 인수 기준에 앞붙이를 쓴다(`E-AC-1`). 「보는 자료」의 AC_HEAD_RE는 옛 task의 화면이라 그대로 둔다


def _clip(text):
    """값을 가린 뒤 자른다. 자른 뒤에 가리면 경계에 걸린 값의 앞부분이 남는다."""
    text = mask_line(text)
    return text if len(text) <= CLIP else text[:CLIP] + "…"


def requirement_rows(run_dir, tasks):
    """[(묶음, task 또는 None, 인수 기준 수)]. 요구사항 블록 task의 「건드릴 파일」에 있는 `spec\\{묶음}.md`마다 한 줄이고, task는 끝난 것 가운데 나중
    것, 없으면 나중 것이다(보류된 상세를 다시 쓴 실행). task가 가리키지 않는 `spec\\*.md`는 task 없이 뒤에 붙는다(옛 실행)."""
    owner = {}
    for t in tasks.values():
        if collect.task_block(t) != REQUIREMENT_BLOCK:
            continue
        for kind, rel in sources(run_dir, t, ("건드릴 파일",)):
            name = os.path.basename(rel)
            if kind == SPEC and name.lower() not in devflow_lib.SPEC_SKIP:
                old = owner.get(name)
                if old is None or t.get("status") == kinds.DONE or old.get("status") != kinds.DONE:
                    owner[name] = t
    spec = os.path.join(run_dir, "spec")
    rest = sorted(n for n in os.listdir(spec) if n.endswith(".md") and n.lower() not in devflow_lib.SPEC_SKIP and n not in owner) \
        if os.path.isdir(spec) else []
    out = []
    for name in list(owner) + rest:
        text = devflow_lib.read_text(os.path.join(spec, name))
        acs = {m.group(1) for m in map(devflow_lib.AC_ROW_RE.match, text.splitlines()) if m}
        out.append((name[:-3], owner.get(name), len(acs)))
    return out


def requirement_lines(run_dir, tasks, parent=None, only=None):
    """요구사항 줄. parent를 주면 그 부모에서 생긴 블록 구간만이다(요구사항 종합, 설계 7.2절). only는 회차의 task id 집합이다."""
    out = []
    for name, t, n in requirement_rows(run_dir, tasks):
        if only is not None and (t is None or t.get("id") not in only):
            continue
        if parent is None or (t is not None and t.get("parent") == parent):
            where = "상세 {}, {}".format(t["id"], t.get("status", "")) if t is not None else "상세 -"
            out.append("- 묶음 {} ({}): 인수 기준 {}개".format(name, where, n))
    return out


def _decision_lines(run_dir, tasks):
    """결정 줄과 정한 쪽. 표지 줄은 따로 두는 칸으로 가므로 뺀다. 정책과 자동으로 정한 것은 1.3.0이다."""
    live, superseded = collect.live_decisions(run_dir)
    out, unread = [], 0
    for line in live:
        if collect.is_marked(line):
            continue
        row = collect.decision_row(line)
        if row is None:
            unread += 1
            continue
        when, text, who, related = row
        out.append("- {} {} | {}{}".format(who, when, _clip(decisions.first_sentence(text)), " ({})".format(related) if related else ""))
    for t in tasks.values():
        if collect.task_block(t) in DECISION_BLOCKS and t.get("status") == kinds.DONE:
            n = devflow_lib.item_count(collect.screen_cell(t, "알릴 것"))
            if n:
                out.append("- 작성자 {}: 알릴 결정 {}건".format(t["id"], n))
    if superseded:
        out.append("- 대체되어 뺀 결정 {}개".format(superseded))
    if unread:
        out.append("- 읽지 못한 결정 줄 {}개(decisions.md를 직접 본다)".format(unread))
    return out


def _lane_key(t):
    """지도의 줄 이름. 변경 task는 등록표의 블록이 비어 있어 따로 이름을 준다."""
    return t.get("flow") or collect.task_block(t) or ("변경" if t.get("kind") == "change" else "기타")


def _flow_lines(tasks, flows):
    lanes = {}
    for t in tasks.values():
        lanes.setdefault(_lane_key(t), []).append(t)
    out = []
    for key, row in lanes.items():
        f = flows.get(key) or {}
        tags = [str(f.get("status", "") or "")] + (["회차 {}".format(f["round"])] if f.get("round", 1) > 1 else [])
        tag = " ({})".format(", ".join(x for x in tags if x)) if any(tags) else ""
        out.append("- {}{}: {}".format(key, tag, ", ".join("{} {}".format(t["id"], t.get("status", "")) for t in row)))
    return out


def _verdict_counts(t):
    """검증 task 「본문」 인수 기준 표의 ({판정: 수}, 판정 칸이 없는 표의 행 수). 셋에 들지 않는 판정은 기타로 세어 합계가 행 수와 맞다."""
    path = os.path.join(t["_dir"], "result.md")
    tables = _verify_tables(devflow_lib.read_text(path)) if os.path.isfile(path) else []
    counts, plain = {v: 0 for v in VERDICTS + (OTHER_VERDICT,)}, 0
    for _, table in tables:
        head = [c.strip() for c in table[0].strip("|").split("|")]
        col = head.index("판정") if "판정" in head else None
        for line in table[1:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if col is None:
                plain += 1
                continue
            value = cells[col] if col < len(cells) else ""
            counts[next((v for v in VERDICTS if value.startswith(v)), OTHER_VERDICT)] += 1
    return counts, plain


def _verdicts(t):
    """검증 표를 센 글. 표가 없으면 빈 글."""
    counts, plain = _verdict_counts(t)
    if not any(counts.values()):
        return "{} 인수 기준 {}개".format(t["id"], plain) if plain else ""
    counts[OTHER_VERDICT] += plain
    return "{} {}".format(t["id"], " · ".join("{} {}".format(v, n) for v, n in counts.items() if n or v == PASSED))


def _closed_acs(tasks):
    """{흐름: (닫은 인수 기준 집합, 닫은 task id)}. 끝난 task의 `closes_ac`를 겹침 없이 모은다. 차례는 처음 나온 대로다."""
    out = {}
    for t in tasks.values():
        ac = t.get("closes_ac") or []
        if ac and devflow_lib.dependency_done(t):
            acs, ids = out.setdefault(t.get("flow") or "실행 전체", (set(), []))
            acs.update(ac)
            ids.append(t["id"])
    return out


def _evidence_lines(tasks):
    """흐름마다 닫은 인수 기준과 검증 표의 판정. 실물 확인을 미룬 것은 따로 두는 칸이다."""
    closes = _closed_acs(tasks)
    verdicts, order = {}, list(closes)
    for t in tasks.values():
        found = _verdicts(t) if t.get("kind") in kinds.VERIFY_KINDS else ""
        if found:
            key = t.get("flow") or "실행 전체"
            verdicts.setdefault(key, []).append(found)
            if key not in order:
                order.append(key)
    out = []
    for key in order:
        parts = ["닫은 인수 기준 {}개({})".format(len(closes[key][0]), ", ".join(closes[key][1]))] if key in closes else []
        out.append("- {}: {}".format(key, ", ".join(parts + verdicts.get(key, []))))
    return out


def _deploy_lines(tasks):
    """머리 파일의 내보낸 커밋과 배포 결과. 보류된 task의 배포도 실제로 남은 것이라 빼지 않고 표시한다.
    넣은 산출물 수는 산출물 대응표(설계 7.5절)가 생긴 뒤 더한다."""
    out = []
    for t in tasks.values():
        exported = str(t.get("exported_commit", "") or "").strip()
        outcome = str(t.get("deploy_outcome", "") or "").strip()
        status = t.get("status", "")
        tail = " (task {})".format(status) if status != kinds.DONE else ""
        if exported:
            out.append("- {} 내보냄 {}{}".format(t["id"], exported, tail))
        if outcome:
            commit = str(t.get("deployed_commit", "") or "").strip()
            out.append("- {} 배포 {}{}{}".format(t["id"], outcome, " " + commit if commit else "", tail))
    return out


def _queue_lines(tasks):
    out = []
    for t in board.queue(tasks):
        ids = board.blocked_ids(tasks, t["id"])
        out.append("- {} {} | 자리: {} | 막고 있는 task {}개{} | 정해 주실 것 {}건 | 요청 {}".format(
            t["id"], t.get("title", ""), t.get("flow") or collect.task_block(t) or "-", len(ids), ": " + ", ".join(ids) if ids else "",
            t.get("n_decide", "0") or 0, t.get("approval_requested", "") or "-"))
    return out


def _deferred_lines(run_dir, tasks):
    return ["- {} | 미룬 흐름 리뷰 {} | 확인할 곳 {} | {}".format(item, tid or "-", place or "-", state)
            for tid, item, place, state in collect.deferred_checks(run_dir, tasks)]


def _inserted_lines(run_dir):
    count = project_docs.inserted_documents(run_dir)
    return ["- 문서 {}개".format(count)] if count else []


def map_sections(run_dir, tasks=None):
    """[(칸 제목, `- ` 줄)]. 값이 있는 칸만 지도 차례로 낸다. 마무리 리뷰는 여기서 승인 대기열을 뺀다(설계 7.3절)."""
    tasks = devflow_lib.load_tasks(run_dir) if tasks is None else tasks
    flows = board.load_flows(run_dir)
    return _built_sections([
        ("요구사항", lambda: requirement_lines(run_dir, tasks)),
        ("결정", lambda: _decision_lines(run_dir, tasks)),
        ("흐름", lambda: _flow_lines(tasks, flows)),
        ("증거", lambda: _evidence_lines(tasks)),
        ("명령·배포", lambda: _deploy_lines(tasks)),
        ("넣은 산출물", lambda: _inserted_lines(run_dir)),
        ("기준선", lambda: ["- " + _clip(l) for l in collect.baseline_lines(run_dir)]),
        ("뺀 검증", lambda: ["- " + l for l in collect.excluded_checks(run_dir, tasks)]),
        ("미룬 실물 확인", lambda: _deferred_lines(run_dir, tasks)),
        ("메인 기록", lambda: ["- " + l for l in collect.main_notes(run_dir, tasks)]),
        ("받아들인 위험", lambda: ["- {} {}".format(tid, item) for tid, item, _ in collect.risk_accepted(run_dir, tasks)]),
        ("승인 대기열", lambda: _queue_lines(tasks)),
    ])


def _built_sections(cells):
    """칸마다 따로 만든다. 값 하나가 깨져도 다른 칸과 파일을 막지 않고, "없음"이 아니라 재지 못함을 낸다."""
    out = []
    for title, build in cells:
        try:
            lines = build()
        except READ_ERRORS as e:
            lines = ["- " + collect.UNMEASURED.format(e)]
        if lines:
            out.append((title, lines))
    return out


def round_sections(run_dir, tasks, cut, only):
    """뒤 회차의 칸(설계 7.3절): 앞 마무리 뒤의 줄만이다. 줄기도 이번 회차 task로 추리고, 위험은 줄의 시각으로 거른다(항목 글의 날짜가 아니다)."""
    subset = {i: t for i, t in tasks.items() if i in only}
    flows = board.load_flows(run_dir)

    def decided():
        return [l for l in _decision_lines(run_dir, subset) if _since(l, cut)]

    def deferred():
        return ["- {} | 미룬 흐름 리뷰 {} | 확인할 곳 {} | {}".format(item, tid or "-", place or "-", state)
                for tid, item, place, state in collect.deferred_checks(run_dir, tasks) if tid in only or not state.startswith(collect.CLOSED.split("{")[0])]
    return _built_sections([
        ("요구사항", lambda: requirement_lines(run_dir, tasks, only=only)),
        ("결정", decided),
        ("흐름", lambda: _flow_lines(subset, flows)),
        ("증거", lambda: _evidence_lines(subset)),
        ("명령·배포", lambda: _deploy_lines(subset)),
        ("뺀 검증", lambda: ["- " + l for l in collect.excluded_checks(run_dir, subset)]),
        ("미룬 실물 확인", deferred),
        ("메인 기록", lambda: [l for l in ("- " + n for n in collect.main_notes(run_dir, tasks)) if _since(l, cut)]),
        ("받아들인 위험", lambda: ["- {} {}".format(tid, item) for tid, item, when in collect.risk_accepted(run_dir, tasks) if not when or when >= cut[:16]]),
    ])


def counted_flows(tasks, flows):
    """지도가 세는 흐름 이름. 머리가 있으면 그 역할로, 코드 task만 있는 흐름은 이름으로 추정한다."""
    names = [n for n, f in board.flow_items(flows) if f.get("role") in COUNTED_ROLES]
    for t in tasks.values():
        n = t.get("flow", "")
        if n and n not in names and n not in flows and devflow_lib.flow_role(n) in COUNTED_ROLES:
            names.append(n)
    return names


def _run_name(run_dir):
    return os.path.basename(os.path.abspath(run_dir).rstrip("\\/"))


def _map_head(run_dir, tasks, names):
    rnd = devflow_lib.run_round(run_dir)
    return "{}: {}{} · task {}개 · 흐름 {}개".format(MAP_TITLE, _run_name(run_dir), " · 회차 {}".format(rnd) if rnd > 1 else "", len(tasks), len(names))


def _one_line(run_dir, tasks, names, sections):
    """흐름이 하나 이하인 실행의 줄기 한 줄(설계 7.3절). 값이 없는 조각은 쓰지 않고, 나쁜 값과 회차는 숫자에서 사라지지 않게 따로 쓴다."""
    rows = requirement_rows(run_dir, tasks)
    count = {}
    for t in tasks.values():
        count[t.get("status", "?")] = count.get(t.get("status", "?"), 0) + 1
    decided = len(dict(sections).get("결정", []))
    closed = set().union(*[acs for acs, _ in _closed_acs(tasks).values()])
    deploys = len(dict(sections).get("명령·배포", []))
    outcomes = [str(t.get("deploy_outcome", "") or "").strip() for t in tasks.values()]
    outcomes = [o for o in outcomes if o]
    failed = sum(n for t in tasks.values() if t.get("kind") in kinds.VERIFY_KINDS
                 for v, n in _verdict_counts(t)[0].items() if v != PASSED)
    parts = ["요구사항 묶음 {}개(인수 기준 {})".format(len(rows), sum(n for _, _, n in rows)) if rows else "",
             "결정 {}줄".format(decided) if decided else "",
             "task {}개({})".format(len(tasks), ", ".join("{} {}".format(k, v) for k, v in count.items())) if tasks else "",
             "닫은 인수 기준 {}".format(len(closed)) if closed else "",
             "통과 아닌 판정 {}".format(failed) if failed else "",
             "명령·배포 {}줄".format(deploys) if deploys else "",
             "마지막 배포 {}".format(outcomes[-1]) if outcomes else ""]
    rnd = devflow_lib.run_round(run_dir)
    head = "{}: {}{} {}".format(MAP_TITLE, _run_name(run_dir), " 회차 {}".format(rnd) if rnd > 1 else "",
                                "흐름 {} 하나".format(names[0]) if names else "흐름 없음")
    return " | ".join([head] + [p for p in parts if p])


def flow_place(run_dir, flow, tasks=None):
    """리뷰 화면에 싣는 자리 한 줄. 흐름의 task에서 부모를 따라 올라가 닿는 요구사항 묶음을 찾는다. 없는 흐름이면 None."""
    tasks = devflow_lib.load_tasks(run_dir) if tasks is None else tasks
    names = counted_flows(tasks, board.load_flows(run_dir))
    if flow not in names:
        return None
    rows = requirement_rows(run_dir, tasks)
    stack, seen = [t["id"] for t in tasks.values() if t.get("flow") == flow], set()
    while stack:
        tid = stack.pop()
        if tid in seen or tid not in tasks:
            continue
        seen.add(tid)
        t = tasks[tid]
        # 의존은 흐름 순서에도 쓰이므로 요구사항 task로 가는 것만 따른다(설계 하나가 상세 여럿을 맡을 때)
        stack += [t.get("parent", "")] + [d for d in t.get("depends_on", []) if d in tasks and collect.task_block(tasks[d]) == REQUIREMENT_BLOCK]
    found = ["{}(상세 {})".format(name, t["id"]) for name, t, _ in rows if t is not None and t["id"] in seen]
    where = "흐름 {}개 가운데 하나".format(len(names)) if len(names) > 1 else "흐름 하나"
    return "실행 지도: " + " / ".join((["요구사항 묶음 " + ", ".join(found)] if found else []) + [where])


def write_map(run_dir, tasks):
    """펼친 지도를 파일에 쓴다. (흐름 이름, 칸, 경로)."""
    names = counted_flows(tasks, board.load_flows(run_dir))
    sections = map_sections(run_dir, tasks)
    full = [_map_head(run_dir, tasks, names)]
    for title, lines in sections:
        full += ["## " + title] + lines
    path = os.path.abspath(os.path.join(run_dir, MAP_FILE))
    devflow_lib.write_text(path, "\n".join(mask_line(line) for line in full) + "\n")
    return names, sections, path


def map_screen(run_dir, tasks, names, sections, path):
    """화면에 낼 지도. 흐름이 하나 이하면 줄기를 한 줄로 줄인다(설계 7.3절). 줄기 밖의 칸은 그대로 둔다."""
    if len(names) > 1:
        out = [_map_head(run_dir, tasks, names)]
        for title, lines in sections:
            out += ["## " + title] + lines
        return [mask_line(line) for line in out] + ["전체: " + path]
    try:
        head = _one_line(run_dir, tasks, names, sections)
    except READ_ERRORS as e:
        head = "{} {}".format(MAP_TITLE, collect.UNMEASURED.format(e))
    out = [mask_line(head) + " | 전체: " + path]
    for title, lines in sections:
        if title not in STEM_TITLES:
            out += ["## " + title] + [mask_line(line) for line in lines]
    return out


def run_map(run_dir, rest):
    """실행 지도 명령행. 펼친 지도를 파일에 쓰고, 흐름이 하나 이하면 표준 출력의 줄기를 한 줄로 줄인다."""
    if not os.path.isfile(os.path.join(run_dir, "run.md")):
        print("실행 폴더 없음: {}".format(run_dir))
        return 2
    tasks = devflow_lib.load_tasks(run_dir)
    if "--flow" in rest:
        at = rest.index("--flow") + 1
        name = rest[at] if at < len(rest) else ""
        place = flow_place(run_dir, name, tasks)
        print(mask_line(place) if place else "흐름 없음: {}".format(name))
        return 0 if place else 2
    names, sections, path = write_map(run_dir, tasks)
    print("\n".join(map_screen(run_dir, tasks, names, sections, path)))
    return 0


# ---------------------------------------------------------------- 마무리 리뷰(--wrap-review, 설계 7.3절)

REVIEW_FILE = devflow_lib.WRAP_REVIEW
REVIEW_TITLE = "■ 마무리 리뷰"
WORK_MISSING = "! 이 실행이 한 일 없음(작성자가 `### 리뷰 자료`를 쓰지 않았다)"
TIME_IN_LINE = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d")
FIRST_TITLE = "먼저 보실 것"
FIRST_SECTIONS = ("받아들인 위험", "미룬 실물 확인")   # 지도에서 앞으로 옮기는 칸


def previous_cut(tasks, t):
    """같은 실행의 앞 마무리를 사람이 보았으면 그 마무리가 시작한 시각, 아니면 None(전체를 펼친다).
    앞 회차가 위임이었거나 리뷰를 보이지 않은 옛 마무리면 사람이 전체를 한 번도 안 볼 수 있다(설계 7.3절). 시작 시각은 그 리뷰가 다 본 쪽으로 이르다."""
    before = [o for o in tasks.values() if o.get("kind") == t.get("kind") and o.get("status") == kinds.DONE and o["id"] < t["id"]]
    if not before:
        return None
    last = before[-1]
    if not os.path.isfile(os.path.join(last["_dir"], REVIEW_FILE)) or collect.is_bulk(last) or not collect.human_lines(last):
        return None
    return str(last.get("started", "") or "") or None


def _since(line, cut):
    found = TIME_IN_LINE.search(line)
    return not found or found.group(0) >= cut[:16]


def _first_of(lines):
    """사람이 판단할 줄인가: `지금 문제 있음`, 시험 끄기·삭제, 재지 못함. 받아들인 위험과 미룬 실물 확인은 칸째 앞으로 옮긴다."""
    return [l for l in lines if places.PROBLEM in l or collect.UNMEASURED.split(":")[0] in l
            or any(l.startswith("- {} |".format(word)) for word in devflow_lib.TEST_REMOVALS)]


def review_lines(run_dir, tid):
    """마무리 리뷰의 줄(1.3.0의 정책 줄기, 바뀐 정책, 규약으로 덮인 곳, 자동으로 정한 것은 싣지 않는다). 값이 없는 칸은 제목도 쓰지 않는다.
    차례는 「먼저 보실 것」, 지도, 나머지 칸이다. 지도 전체를 보이되 사람이 판단할 줄이 결정 목록 뒤로 밀리지 않게 한다(사용자 결정)."""
    tasks = devflow_lib.load_tasks(run_dir)
    t = tasks[tid]
    try:
        cut = previous_cut(tasks, t)
    except READ_ERRORS:
        cut = None
    only = None if cut is None else {i for i, o in tasks.items() if i != tid and (not o.get("approved") or str(o["approved"]) >= cut)}
    names, sections, path = write_map(run_dir, tasks)
    sections = round_sections(run_dir, tasks, cut, only) if cut is not None else sections
    sections = [(title, lines) for title, lines in sections if title != "승인 대기열"]
    first = [line for title, lines in sections if title in FIRST_SECTIONS for line in lines]
    sections = [(title, lines) for title, lines in sections if title not in FIRST_SECTIONS]
    rest = []

    def unverified():
        marked, others, broken = collect.unverified_review(tasks, only)
        return marked + others + ["- " + b for b in broken]
    try:
        inserted, summary = project_docs.review_lines(run_dir, t)
    except READ_ERRORS as e:
        inserted, summary = ["- " + collect.UNMEASURED.format(e)], ""
    rest.append(("넣을 산출물", inserted))
    first += [summary] if summary else []
    for title, build in (("남은 확인 안 된 것", unverified), ("코드 확인", lambda: collect.code_check_lines(run_dir, tasks, only)),
                         ("흐름 리뷰 뒤에 바뀐 것", lambda: collect.after_review_lines(tasks, only)),
                         ("시험 변화", lambda: collect.test_total_lines(tasks, only) + ["- " + l for l in devflow_lib.wrap_up_test_lines(tasks, only)])):
        try:
            lines = build()
        except READ_ERRORS as e:
            lines = ["- " + collect.UNMEASURED.format(e)]
        rest.append((title, lines))
    moved = [l for title, lines in sections + rest for l in _first_of(lines)]
    first += [l for l in moved if l not in first]
    out = [REVIEW_TITLE]
    if not collect.screen_cell(t, "리뷰 자료").strip():
        out.append(WORK_MISSING)
    if first:
        out += ["## " + FIRST_TITLE] + first
    sections = [(title, [l for l in lines if l not in moved]) for title, lines in sections]
    sections = [(title, lines) for title, lines in sections if lines]
    if cut is not None:
        out.append("{}: {} 뒤에 바뀐 것만 싣습니다. 앞 마무리에서 지도 전체를 보셨습니다. 전체: {}".format(MAP_TITLE, cut, path))
        for title, lines in sections:
            out += ["## " + title] + lines
    else:
        out += map_screen(run_dir, tasks, names, sections, path)
    for title, lines in rest:
        lines = [l for l in lines if l not in moved]
        out += ["## " + title] + lines if lines else []
    return [mask_line(line) for line in out]


def write_review(run_dir, tid):
    """`tasks\\{id}\\wrap-review.md`를 쓴다. 승인 화면이 이 파일을 싣는다. 어떤 값이 깨져도 파일은 생긴다. 없으면 실행승인 전이가 멈춘다."""
    try:
        lines = review_lines(run_dir, tid)
    except READ_ERRORS as e:
        lines = [REVIEW_TITLE, "## " + FIRST_TITLE, "- " + collect.UNMEASURED.format(e)]
    path = os.path.join(run_dir, "tasks", tid, REVIEW_FILE)
    devflow_lib.write_text(path, "\n".join(lines) + "\n")
    print("마무리 리뷰 {}줄 -> {}".format(len(lines), path))
    return 0


def flow_review_head(run_dir, t):
    """흐름 리뷰의 칸 8, 9: 지도에서 이 흐름의 자리와 사람 지시로 뺀 검증. 이 줄은 화면 칸 뒤의 「보는 자료」 앞에 실린다(`screen.py`는 지도 층을 부르지 못한다)."""
    if not devflow_lib.flow_review_rules(t):
        return []
    tasks = devflow_lib.load_tasks(run_dir)
    place = flow_place(run_dir, t.get("flow", ""), tasks)
    out = [mask_line(place) if place else "실행 지도: {}(흐름 {}가 지도에 없음)".format(flow_review.UNREAD, t.get("flow", ""))]
    own = {o["id"] for o in tasks.values() if o.get("flow") == t.get("flow")}
    lines = [line for line in collect.excluded_checks(run_dir, tasks) if not re.match(r"T\d+ ", line) or line.split(" ", 1)[0] in own]
    if lines:
        out += ["■ 사람 지시로 뺀 검증"] + ["- " + flow_review.clip(line) for line in lines]
    return out + [""]


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, tid = argv[1], argv[2]
    if tid == "--run":
        return run_map(run_dir, argv[3:])
    if not os.path.isfile(os.path.join(run_dir, "tasks", tid, "task.md")):
        print("task 없음: {} ({})".format(tid, os.path.join(run_dir, "tasks", tid, "task.md")))
        return 2
    for flag, kind in (("--sheet-sent", devflow_lib.SHEET_SENT), ("--sheet-failed", devflow_lib.SHEET_FAILED)):
        if flag in argv[3:]:
            at = argv.index(flag) + 1
            if at >= len(argv):
                print(__doc__)
                return 2
            return sheet_mark(run_dir, tid, kind, argv[at])
    if "--sheet" in argv[3:]:
        return sheet(run_dir, tid, "--once" in argv[3:])
    if "--wrap-review" in argv[3:]:
        return write_review(run_dir, tid)
    t = devflow_lib.load_task(os.path.join(run_dir, "tasks", tid, "task.md"))
    t.setdefault("id", tid)
    head = flow_review_head(run_dir, t)
    if head:
        print("\n".join(head))
        devflow_lib.write_text(os.path.join(t["_dir"], flow_review.HEAD_FILE),
                               "보인 시각: {}\n{}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "\n".join(head).rstrip()))
    lines = build(run_dir, tid)
    limit = devflow_lib.run_value(run_dir, LIMIT_KEY, kinds.RUN_DEFAULTS[LIMIT_KEY])
    if len(lines) - 1 > limit:
        full = os.path.abspath(os.path.join(run_dir, "tasks", tid, "visual.md"))
        devflow_lib.write_text(full, "\n".join(lines) + "\n")
        lines = lines[:1 + limit] + ["- 전체 {}줄: {}".format(len(lines) - 1, full)]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
