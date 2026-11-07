"""devflow-harness 스크립트 공통 함수.

머리 파일(task.md)은 맨 앞의 `---` 사이에 `키: 값` 줄을 두고, 그 아래에 `## 제목` 절을 둔다.
값은 한 줄 문자열이거나 `[a, b]` 꼴의 목록이다. 형식은 formats.md가 원천이다.
"""
import io
import fnmatch
import hashlib
import os
import posixpath
import re
import sys

import kinds

EMPTY_ITEM = re.compile(r"^- 없음(?:$|[\s.(:,—-])")


def utf8_stdout():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    else:  # pragma: no cover
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def read_text(path):
    # utf-8-sig: PowerShell이 붙인 BOM을 떼고 읽는다(BOM이 남으면 첫 줄 `---`를 못 알아봐 머리 파일을 못 읽었다)
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def parse_value(key, raw):
    raw = raw.strip()
    if key in kinds.LIST_KEYS or (raw.startswith("[") and raw.endswith("]")):
        inner = raw.strip("[]").strip()
        if not inner:
            return []
        return [x.strip() for x in inner.split(",") if x.strip()]
    return raw


def split_front_matter(text):
    """(meta 줄 목록, 본문)을 돌려준다. 머리가 없으면 ([], text)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    return [], text


def parse_meta(meta_lines):
    meta = {}
    for line in meta_lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.split(" #", 1)[0] if " #" in raw else raw
        meta[key] = parse_value(key, raw)
    return meta


def sections(body, level=2):
    """`## 제목` 절을 {제목: 내용}으로 돌려준다(같은 수준 제목만 경계로 삼는다)."""
    out = {}
    current = None
    buf = []
    prefix = "#" * level + " "
    for line in body.splitlines():
        if line.startswith(prefix):
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = line[len(prefix):].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def load_task(task_md):
    text = read_text(task_md)
    meta_lines, body = split_front_matter(text)
    meta = parse_meta(meta_lines)
    meta["_path"] = task_md
    meta["_dir"] = os.path.dirname(task_md)
    meta["_sections"] = sections(body)
    for key in kinds.LIST_KEYS:
        meta.setdefault(key, [])
    if not str(meta.get("stage", "") or "").strip() and str(meta.get("deploy_stage", "") or "").strip():
        meta["stage"] = meta["deploy_stage"]   # 옛 배포 실행의 deploy_stage는 stage의 별칭
    return meta


def load_tasks(run_dir):
    tasks_dir = os.path.join(run_dir, "tasks")
    out = {}
    if not os.path.isdir(tasks_dir):
        return out
    for name in sorted(os.listdir(tasks_dir)):
        task_md = os.path.join(tasks_dir, name, "task.md")
        if os.path.isfile(task_md):
            t = load_task(task_md)
            out[t.get("id", name)] = t
    return out


def format_meta_value(value):
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]"
    return str(value)


class Reject(Exception):
    """스크립트가 거부할 때 내는 예외. task_set.py는 이 객체를 그대로 Reject로 쓴다."""
    pass


# ---------------------------------------------------------------- 머리 파일 글 고치기

class Doc:
    """머리 파일 글. 줄바꿈 꼴(CRLF/LF)을 그대로 두고 키와 절만 고친다."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8-sig")
        self.crlf = "\r\n" in text
        self.lines = text.replace("\r\n", "\n").split("\n")
        if not self.lines or self.lines[0].strip() != "---":
            raise Reject("머리 파일 형식 아님(첫 줄이 ---가 아님): " + path)
        self.end = next((i for i in range(1, len(self.lines)) if self.lines[i].strip() == "---"), None)
        if self.end is None:
            raise Reject("머리 파일의 머리가 닫히지 않음: " + path)

    def get(self, key):
        for i in range(1, self.end):
            if self.lines[i].split(":", 1)[0].strip() == key and ":" in self.lines[i]:
                return self.lines[i].split(":", 1)[1].strip()
        return None

    def set(self, key, value):
        value = format_meta_value(value) if isinstance(value, list) else str(value)
        line = "{}: {}".format(key, value).rstrip() if value else "{}:".format(key)
        for i in range(1, self.end):
            if ":" in self.lines[i] and self.lines[i].split(":", 1)[0].strip() == key:
                self.lines[i] = line
                return
        self.lines.insert(self.end, line)
        self.end += 1

    def _section_span(self, title):
        start = None
        for i in range(self.end + 1, len(self.lines)):
            if self.lines[i].startswith("## "):
                if start is not None:
                    return start, i
                if self.lines[i][3:].strip() == title:
                    start = i
        return (start, len(self.lines)) if start is not None else (None, None)

    def section(self, title):
        s, e = self._section_span(title)
        return None if s is None else "\n".join(self.lines[s + 1:e]).strip()

    def set_section(self, title, body, before=None):
        """절 내용을 바꾼다. 없으면 before 절 앞(없으면 끝)에 만든다."""
        body_lines = body.rstrip("\n").split("\n") + [""]
        s, e = self._section_span(title)
        if s is not None:
            self.lines[s + 1:e] = body_lines
            return
        at = len(self.lines)
        for b in before or []:
            bs, _ = self._section_span(b)
            if bs is not None:
                at = bs
                break
        while at == len(self.lines) and self.lines and self.lines[-1] == "":
            self.lines.pop()
            at = len(self.lines)
        block = ([""] if at == len(self.lines) else []) + ["## " + title] + body_lines
        self.lines[at:at] = block

    def append_line(self, title, line, before=None):
        cur = self.section(title)
        if cur is None:
            self.set_section(title, line, before)
            return
        keep = [l for l in cur.split("\n") if l.strip() and l.strip() not in ("(없음)",)]
        self.set_section(title, "\n".join(keep + [line]), before)

    def text(self):
        out = "\n".join(self.lines)
        return out.replace("\n", "\r\n") if self.crlf else out

    def save(self):
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(self.text())


def item_count(section_text):
    """절 안의 항목 수: 맨 앞이 `- `인 줄(들여쓴 하위 줄 제외)을 센다.
    `- 없음`, `- 없음.`, `- 없음 (설명)`처럼 '없음' 뒤에 설명만 붙은 줄은 세지 않는다
    (첫 실행에서 "- 없음 (문서만 바꿨다…)"를 항목 1로 세어 알림이 승인으로 갔다)."""
    n = 0
    for line in section_text.splitlines():
        if line.startswith("- "):
            if EMPTY_ITEM.match(line.strip()):
                continue
            n += 1
    return n


def unparsed_cell(section_text):
    """칸에 글이 있는데 `- ` 항목으로 세지 못하면 True(번호·표·문단으로 쓴 칸).
    0건으로 세면 정할 것이 있어도 알림으로 지나가므로, 이런 칸은 형식 확인이 필요하다고 본다."""
    lines = [l for l in section_text.splitlines() if l.strip()]
    if not lines or item_count(section_text) > 0:
        return False
    return not all(EMPTY_ITEM.match(l.strip()) for l in lines if l.startswith("- ")) or not any(l.startswith("- ") for l in lines)


def next_task_number(tasks):
    top = 0
    for tid in tasks:
        m = re.match(r"T(\d+)$", tid)
        if m:
            top = max(top, int(m.group(1)))
    return top + 1


# 메인 컨텍스트 문턱(SKILL.md 8절). 권고는 다음 정리 지점에서 /clear를 권하기만 하고, 새 task를 막는 것은 더 높은 문턱이다.
# 권고 문턱에서 바로 막으면 사람이 없을 때 실행이 멈춘다(2026-10-07 실행: 11:13에 300K를 넘었고 구현 시작이 11:18).
# 1.0.3에서 300K·400K → 200K·300K: 메인은 턴마다 컨텍스트 전체를 다시 보낸다(2026-10-29 실행: 99턴에 15.4M).
# 1.0.4에서 300K·500K: 재개 한 번이 약 2.5M(바닥 120~130K 캐시 쓰기)이라 재개 사이 호출이 적으면 낮은 문턱이 손해다.
# 1.1.0에서 「이번 실행의 값」으로: 시작값은 등록표 RUN_DEFAULTS가 원천이고, 실행마다 run.md 행으로 바꾼다(ctx_thresholds).
CTX_ADVISE = kinds.RUN_DEFAULTS["메인 컨텍스트 권함(K)"] * 1000
CTX_STOP = kinds.RUN_DEFAULTS["메인 컨텍스트 멈춤(K)"] * 1000
CTX_FLOOR_NOTE = 150_000   # 재개 바닥이 이 값 이상이면 screen.py가 한 번 알린다
CTX_TAIL_BYTES = 4 * 1024 * 1024
CTX_STALE_SEC = 600
# 메인 컨텍스트 줄(main_context_line)과 재개 뒤 기록이 없을 때의 이유(main_context)
CTX_LINE = "메인 컨텍스트: {}K (세션 {})"
CTX_STOP_TAIL = " — {}K 넘음: 새 task를 띄우지 않고 정리 지점을 기다려 `/clear` 뒤 `devflow-harness 이어서`를 권함(SKILL.md 8절)"
CTX_ADVISE_TAIL = " — {}K 넘음: 다음 정리 지점에서 `/clear` 뒤 `devflow-harness 이어서`를 권함(SKILL.md 8절)"
CTX_NO_RECORD_AFTER_RESUME = "재개 뒤 기록 없음({})"


def ctx_thresholds(run_dir=None):
    """(권함, 멈춤) 토큰 문턱. run.md 「이번 실행의 값」의 `메인 컨텍스트 권함`·`멈춤` 행(K 단위), 없으면 시작값.
    run_dir가 None이면 상수."""
    if run_dir is None:
        return CTX_ADVISE, CTX_STOP
    return (run_value(run_dir, "메인 컨텍스트 권함", CTX_ADVISE // 1000) * 1000,
            run_value(run_dir, "메인 컨텍스트 멈춤", CTX_STOP // 1000) * 1000)


def resume_since(run_dir):
    """journal.md에서 둘째 칸이 `재개`인 마지막 줄의 시각(지역 시각)을 epoch로. 없거나 못 읽으면 None."""
    from datetime import datetime
    p = os.path.join(run_dir, "journal.md")
    if not os.path.isfile(p):
        return None
    last = None
    for line in read_text(p).splitlines():
        f = [c.strip() for c in line.split("|")]
        if len(f) >= 2 and f[0].startswith("- ") and f[1] == "재개":
            last = f[0][2:].strip()
    if last is None:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(last, fmt).timestamp()
        except ValueError:
            pass
    return None


def _iso_epoch(ts):
    """세션 기록의 `timestamp`(UTC ISO, 끝이 `Z`)를 epoch로. 못 읽으면 None."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def main_context(run_dir=None):
    """메인 세션의 지금 컨텍스트(마지막 호출의 input + cache_read + cache_creation 토큰)를 세션 기록에서 읽는다.
    (토큰 수, 세션 ID 앞 8자) 또는 (None, 측정 불가 이유)를 돌려준다.
    세션은 CLAUDE_CODE_SESSION_ID로 찾을 때만 잰다. 가장 최근 기록으로 추정하면 같은 프로젝트에서 동시에 도는
    다른 세션을 잡는다(2026-10-07: 세 세션이 같은 프로젝트 폴더에서 함께 돌았다). 하위 에이전트 안에서도 이 변수는 메인 세션 ID다.
    run_dir를 주면 journal.md의 마지막 `재개` 줄 시각보다 이른 기록을 건너뛴다(/clear 앞 컨텍스트를 재지 않게)."""
    import glob
    import json
    import time
    since = resume_since(run_dir) if run_dir else None
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        return None, "세션 ID 환경 변수 없음"
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    found = glob.glob(os.path.join(root, "*", sid + ".jsonl"))
    if not found:
        return None, "세션 기록 없음({})".format(sid[:8])
    path = found[0]
    ctx, ts, skipped = None, None, False
    with open(path, "rb") as fh:
        size = os.path.getsize(path)
        if size > CTX_TAIL_BYTES:
            fh.seek(size - CTX_TAIL_BYTES)
            fh.readline()  # 잘린 첫 줄 버림
        for raw in fh:
            try:
                d = json.loads(raw.decode("utf-8"))
            except ValueError:
                continue
            if d.get("type") != "assistant":
                continue
            u = (d.get("message") or {}).get("usage")
            if not u:
                continue
            n = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            if not n:
                continue
            when = _iso_epoch(d.get("timestamp"))
            if since is not None and when is not None and when < since:
                skipped = True
                continue
            ctx, ts = n, d.get("timestamp")
    if ctx is None:
        if skipped:
            return None, CTX_NO_RECORD_AFTER_RESUME.format(sid[:8])
        return None, "usage 없음({})".format(sid[:8])
    when = _iso_epoch(ts)
    age = time.time() - when if when is not None else 0
    if age > CTX_STALE_SEC:
        # /clear 뒤 옛 세션을 읽어 권고가 되풀이되지 않게 한다.
        return None, "마지막 기록이 {}분 전({})".format(int(age // 60), sid[:8])
    return ctx, sid[:8]


def main_context_line(run_dir=None):
    """`screen.py`와 `board.py --ready`가 맨 끝에 붙이는 한 줄. `counts:`로 시작하지 않는다(메인이 counts 줄을 읽는다).
    run_dir를 주면 그 실행의 문턱(ctx_thresholds)과 재개 시각(main_context)을 쓴다."""
    advise, stop = ctx_thresholds(run_dir)
    ctx, info = main_context(run_dir)
    if ctx is None:
        return "메인 컨텍스트: 측정 불가({})".format(info)
    line = CTX_LINE.format(ctx // 1000, info)
    if ctx >= stop:
        line += CTX_STOP_TAIL.format(stop // 1000)
    elif ctx >= advise:
        line += CTX_ADVISE_TAIL.format(advise // 1000)
    return line


# ---------------------------------------------------------------------------
# 하네스 판본(SKILL.md 1절 「하네스가 바뀌었을 때」). 메인이 매니페스트를 손으로 보지 않게 여기서 계산한다.

def harness_version(harness_dir=None):
    """하네스 판본: `{harness_dir 또는 kinds.PLUGIN_ROOT}/.claude-plugin/plugin.json`의 `version` 문자열.
    파일이 없거나 읽지 못하거나 `version`이 문자열이 아니면 `?`(등록표 `kinds.plugin_version`)."""
    return kinds.plugin_version(harness_dir)


def same_version(a, b):
    """판본 둘이 같은가. 둘 다 비지 않고 앞뒤 공백을 뺀 문자열이 같으면 같다."""
    ka, kb = (a or "").strip(), (b or "").strip()
    return bool(ka) and ka == kb


def run_meta(run_dir):
    p = os.path.join(run_dir, "run.md")
    if not os.path.isfile(p):
        return {}
    meta_lines, _ = split_front_matter(read_text(p))
    return parse_meta(meta_lines)


def version_line(run_dir):
    """`board.py --ready`가 `메인 컨텍스트:` 줄 앞에 붙이는 한 줄."""
    now = harness_version()
    recorded = run_meta(run_dir).get("harness_version", "")
    same = same_version(now, recorded)
    line = "하네스 판본: 지금 {} / run.md {} — {}".format(now, recorded or "(없음)", "같음" if same else "다름")
    if not same:
        line += "(SKILL.md 1절 「하네스가 바뀌었을 때」)"
    return line


def run_value(run_dir, name, default):
    """run.md 「이번 실행의 값」 표에서 이름이 든 행의 첫 숫자. 못 읽으면 default."""
    try:
        for line in read_text(os.path.join(run_dir, "run.md")).splitlines():
            if line.startswith("|") and name in line:
                for c in [c.strip() for c in line.strip("|").split("|")][1:]:
                    digits = "".join(ch for ch in c if ch.isdigit())
                    if digits:
                        return int(digits)
    except OSError:
        pass
    return default


EMPTY_RETURN, EMPTY_RESUMED = "결과 없이 반환", "이어 씀"   # journal의 일 칸. 측정이 멈춘 시간으로 잰다
EMPTY_RETURN_LINE = "! 결과 없이 반환: {} {} — 끝나지 않았습니다. 사람 답을 기다리지 말고 이어 쓰는 에이전트를 띄운다(references/main/errors.md)"
SHEET_UPLOAD_KEY = "한 장 올리기"
PLAIN_ASK = "묻기: 한 장 올리기 허용이라 `AskUserQuestion` 대신 일반 메시지로 묻고 턴을 끝낸다(references/main/sheet-upload.md)"
SHEET_SENT, SHEET_FAILED = "한 장 올림", "한 장 못 올림"   # journal의 일 칸. 측정이 센다
SHEET_SENT_FILE = "sheet-sent.md"   # task 폴더. `{한 장 sha256} {일회 표지} {링크}`. 다음 판의 한 장에는 맞지 않는다
SHEET_ALLOWED_MARK = "-"   # 일회 표지 자리: 값이 `허용`일 때 올린 것. 일회 올리기면 올릴 때의 승인 기록 줄 수다


def sheet_upload(run_dir):
    """run.md 「이번 실행의 값」 `한 장 올리기`의 값. 마지막 행이 `허용`일 때만 허용이다(거두면 `없음` 행을 더한다).
    행이 없는 옛 실행과 그 밖의 값은 시작값 `없음`이다."""
    path = os.path.join(run_dir, "run.md")
    values = sections(read_text(path)).get("이번 실행의 값", "") if os.path.isfile(path) else ""
    last = kinds.RUN_DEFAULTS[SHEET_UPLOAD_KEY]
    for line in values.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == SHEET_UPLOAD_KEY:
            last = "허용" if cells[1] == "허용" else kinds.RUN_DEFAULTS[SHEET_UPLOAD_KEY]
    return last


def _sheet_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sheet_sent_write(t, link):
    """올린 표지를 지금 한 장에 묶는다. 한 장이 없거나 링크가 비면 표지를 두지 않는다. 못 올렸을 때도 이 함수로 지운다."""
    sheet, mark = os.path.join(t["_dir"], "sheet.html"), os.path.join(t["_dir"], SHEET_SENT_FILE)
    if link and os.path.isfile(sheet):
        once = SHEET_ALLOWED_MARK if sheet_upload(run_dir_of(t)) == "허용" else len(record_lines(t))
        write_text(mark, "{} {} {}\n".format(_sheet_hash(sheet), once, link))
    elif os.path.isfile(mark):
        os.remove(mark)


def sheet_sent_link(t):
    """지금 사람이 열 수 있는 한 장의 링크. 표지가 없거나 한 장이 그 뒤에 바뀌었으면 빈 글이다.
    값이 `허용`이 아니면 이 답을 기다리는 일회 올리기만 인정한다(값을 거두고 페이지를 지웠으면 링크가 죽었다). 답을 적으면 일회 올리기는 끝난다."""
    sheet, mark = os.path.join(t["_dir"], "sheet.html"), os.path.join(t["_dir"], SHEET_SENT_FILE)
    if not os.path.isfile(sheet) or not os.path.isfile(mark):
        return ""
    cells = read_text(mark).strip().split(" ", 2)
    if len(cells) != 3 or cells[0] != _sheet_hash(sheet):
        return ""
    if sheet_upload(run_dir_of(t)) != "허용" and cells[1] != str(len(record_lines(t))):
        return ""
    return cells[2].strip()


def journal_append(run_dir, kind, tid, line):
    """journal.md에 `- {YYYY-MM-DD HH:MM} | {일} | {id} | {줄}` 한 줄을 그 파일의 줄 끝 꼴로 더한다(덧붙이기 전용)."""
    from datetime import datetime
    p = os.path.join(run_dir, "journal.md")
    eol = "\n"
    if os.path.isfile(p):
        with open(p, "rb") as f:
            eol = "\r\n" if b"\r\n" in f.read() else "\n"   # 그 journal의 줄 끝 꼴을 따른다
    with open(p, "a", encoding="utf-8", newline="") as f:
        f.write("- {} | {} | {} | {}{}".format(datetime.now().strftime("%Y-%m-%d %H:%M"), kind, tid, line, eol))


# ---------------------------------------------------------------------------
# 필요한 판정과 기록 점검(SKILL.md 2절, formats.md 2·5절). R1~R5는 `started_version`이 있는 task
# (규칙 판 1을 넣은 뒤 `task_set.py --status 진행`으로 시작한 task)에만 적용한다. 옛 task의 판정 파일에는
# `판정자:` 첫 줄이 없어서 적용하면 모두 걸린다.

# 판정 파일 → 첫 줄 판정자 이름의 접두어(등록표 AGENTS의 short + "-")
JUDGE_PREFIX = {kinds.JUDGE_FILES[r]: kinds.AGENTS[n].short + "-" for r, n in (("read", "read-judge"), ("run", "run-judge"))}
# 판정자 첫 줄. 정의는 `date "+%Y-%m-%d %H:%M:%S"`를 쓰게 하지만, 초 없음·T 구분·시간대 꼬리도 받는다
JUDGE_LINE = re.compile(r"^판정자:\s*(\S+)\s+(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(:\d{2})?(?:\.\d+)?\s*(?:Z|[+-]\d{2}:?\d{2}|[A-Z]{2,4})?\s*$")
MTIME_SLACK = 60    # 초. 판정자가 첫 줄 시각을 쓴 뒤 파일을 닫기까지의 틈(판정 102초 뒤의 메인 Edit를 잡는 폭)
ISOLATION_CONTRACT_VERSION = "1.0.1"
RULES_V110 = "1.1.0"   # 1.1.0 판본 문턱. 이 판본부터 시작한 task에만 영역·판정 표지·재사용 거부 규칙을 적용한다
RULES_V111 = "1.1.1"   # 이 판본부터 시작한 STAGE kind task에만 묻는 stage별 판정 요구(kinds.STAGE_JUDGES)를 건다
CANON_PATH_RE = re.compile(r"(?<![\w-])(?:spec|ui|design)[\\/][^\s`()'\"|,]*")   # 머리 파일 글에 적힌 정본 경로
DESIGN_COPY = "design-copy"
# 값 안의 `]`는 끊지 않는다(`src/app/[id]/page.tsx:12`). 태그는 다음 태그나 줄 끝에서 닫힌다
JUDGMENT_TAG = re.compile(r"\[(종류|위치|따름|설계)\s*:\s*(.*?)\](?=\s*(?:\[(?:종류|위치|따름|설계)\s*:|$))")
JUDGMENT_PLACE = re.compile(r"^[^,]+:\d+(?:-\d+)?$")
JUDGMENT_NONE = re.compile(r"^- 없음(?:\s*\(.*\))?\s*$")
RULES_V120 = "1.2.0"   # 이 판본(1.2.0-dev.n 포함)부터 시작한 task에만 판단 기록·코드 확인 규칙을 적용한다
CODE_CHECK_ORIGIN = "코드 확인"   # 곳 답의 승인 기록 지점(`코드 확인 {키}`)과 그 답으로 만든 수정의 origin에 든다


def is_new_task(t):
    return bool(str(t.get("started_version", "")).strip())


def version_at_least(value, minimum):
    """점 세 정수 판본끼리 비교한다. 판본 꼴이 아니면 새 계약으로 간주하지 않는다."""
    def parts(v):
        m = re.match(r"^\s*(\d+)\.(\d+)\.(\d+)(?:\D.*)?$", str(v or ""))
        return tuple(int(x) for x in m.groups()) if m else None
    got, need = parts(value), parts(minimum)
    return bool(got and need and got >= need)


# 값의 가림. 사람에게 보이고 파일에 남는 글(한 장, 실행 지도, 코드 확인 카드)이 함께 쓴다
MASK = "[가림]"
KEY_BLOCK = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S)
SECRET_PAIR = re.compile(r"""(?i)((?:api[ _-]?key|service[_-]?role(?:[_-]?key)?|access[_-]?key|session[_-]?key|secret[_-]?key|credential|secret|token|password|passwd|pwd|authorization|private[_-]?key|비밀번호|암호|토큰)["']?\s*[:=]\s*)"""
                         r"""((?:bearer|basic)\s+\S+|"[^"]*"|'[^']*'|\S+)""")
# 문서의 타입 이름, 자리 표시, 한글 문장은 값이 아니다(설계 문서를 읽을 수 있어야 한다)
COOKIE_PAIR = re.compile(r"""(?i)((?<![\w-])(?:set-)?cookie["']?\s*[:=]\s*)(\S.*)$""")   # 쿠키는 값이 여럿이라 줄 끝까지 가린다
NOT_A_VALUE = re.compile(r"(?i)^(?:string|str|number|int|integer|bool|boolean|null|none|undefined|true|false|object|array|any"
                         r"|required|optional|text|uuid)[,|;)]*$|^[$<{\[(|가-힣]")
URL_CREDENTIAL = re.compile(r"(\b[a-z][a-z0-9+.-]{0,30}://[^\s:/@]{1,256}:)[^\s@/]{1,256}(@)")
KNOWN_TOKEN = re.compile(r"\b(?:sk|ghp|gho|ghs|ghu|github_pat|glpat|xox[abps])[-_][A-Za-z0-9_-]{10,}|\bAKIA[0-9A-Z]{16}\b"
                         r"|\beyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]*){0,2}"   # JWT(Supabase 키 꼴)
                         r"|(?i:\bbearer\s+)[A-Za-z0-9._~+/=-]{16,}")
PHONE = re.compile(r"\b01\d[- ]?\d{3,4}[- ]?\d{4}\b|\+82[- ]?\(?0?1\d\)?[- ]?\d{3,4}[- ]?\d{4}\b")
# 도메인 끝이 알파벳이어야 메일이다(`next@14.2.1`은 판 번호). 길이를 묶어 긴 줄에서도 느려지지 않는다
MAIL = re.compile(r"(?<![A-Za-z0-9._%+-])(?!git@)[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
KEY_BEGIN, KEY_END = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")


def mask_line(line):
    """한 줄의 비밀값 값 꼴과 전화번호·메일 꼴을 가린다."""
    def pair(m):
        return m.group(0) if NOT_A_VALUE.match(m.group(2)) else m.group(1) + MASK

    line = COOKIE_PAIR.sub(lambda m: m.group(0) if NOT_A_VALUE.match(m.group(2)) else m.group(1) + MASK, line)
    line = SECRET_PAIR.sub(pair, line)
    line = URL_CREDENTIAL.sub(lambda m: m.group(1) + MASK + m.group(2), line)
    line = KNOWN_TOKEN.sub(MASK, line)
    line = PHONE.sub(MASK, line)
    return MAIL.sub(MASK, line)


def mask_lines(rows):
    """줄 목록을 줄 수와 번호를 그대로 두고 가린다. 개인 키 묶음은 줄마다 가린다. (가린 줄 목록, 바뀐 줄 수)."""
    out, changed, in_key = [], 0, False
    for line in rows:
        if in_key or KEY_BEGIN.search(line):
            in_key = not KEY_END.search(line)
            out.append(MASK)
            changed += 1
            continue
        clean = mask_line(line)
        changed += clean != line
        out.append(clean)
    return out, changed


LEVEL_NOT = re.compile(r"L\d(?:\s*[~\-–—～〜]\s*L?\d)?\s*(?:은|는|을|를)?\s*(?:제외|빼고|뺌|말고|아님|없음|안\s*함)")
RISK_SENTENCE = "받아들인 위험은 답을 `--record \"승인|위험 수용|{원문}\"`으로 적고 `decisions.md`에 `[위험 수용 T0xx] {항목}` 한 줄을 쓴다"   # 문서 넷과 같은 글
DELEGATED_ANSWER = re.compile(r"이후\s*전체|나머지\s*자동|자동\s*승인|전부\s*자동")   # 위임의 말. 칸에 `위임 {층}`을 적지 않은 승인은 거부한다


def levels_in(value):
    """칸 글의 층. 괄호 안 글과 뺀 층은 세지 않는다."""
    found = set()
    value = LEVEL_NOT.sub("", re.sub(r"[(（][^)）]*[)）]", "", value or ""))
    for low, high in re.findall(r"L(\d)(?:\s*[~\-–—～〜]\s*L?(\d))?", value):
        ends = sorted((int(low), int(high or low)))
        found.update(range(ends[0], ends[1] + 1))
    return tuple("L{}".format(n) for n in sorted(found))


def delegation_levels(run_dir):
    """run.md 「이번 실행의 값」 `위임` 행의 층(설계 9절). `L1~L3`은 범위를 풀어 ("L1", "L2", "L3")이다. 행이나 층이 없으면 빈 튜플.
    괄호 안 글과 `L4 제외`, `L1 아님`처럼 뺀 층은 세지 않는다(좁은 쪽으로 읽는다)."""
    try:
        values = sections(read_text(os.path.join(run_dir, "run.md"))).get("이번 실행의 값", "")
    except OSError:
        return ()
    for line in values.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) < 2 or not cells[0].startswith("위임"):
            continue
        found = levels_in(cells[1])
        if found:
            return found
    return ()


def uses_isolation_contract(t):
    """1.0.1부터 시작한 task에만 새 judge-run 증거 계약을 강제한다. 진행 중 1.0.0 task는 그대로 끝낸다."""
    return version_at_least(t.get("started_version", ""), ISOLATION_CONTRACT_VERSION)


def uses_domain_rules(t):
    """1.1.0부터 시작한 task에만 영역 규칙(화면 id 대조, 영역 판정 기준 주입, 문서 행, 경로 알림)을 적용한다.
    spawn_children.py는 부모 task의 값으로, 그 밖은 그 task의 값으로 본다."""
    return version_at_least(t.get("started_version", ""), RULES_V110)


def resource_wait(t):
    progress = str(t.get("external_progress", "") or "").strip()
    return progress if progress.startswith("자원 대기:") else ""


def result_cells(t):
    p = os.path.join(t["_dir"], "result.md")
    if not os.path.isfile(p):
        return None
    return sections(sections(read_text(p), level=2).get("승인 화면", ""), level=3)


def branch_judgements(t):
    """exec.md의 브랜치 판정 줄(`- {시각} | 브랜치 판정 | {지점}:{n} | {판정} | …`)을 {지점:n: 판정}으로. 같은 지점은 뒤 줄이 이긴다.
    판정 값은 exec.py가 쓴 낱말 그대로다(`병합`·`앞감기`·`충돌`·`병합(충돌 해결)`·`불일치` 등)."""
    judged = {}
    p = os.path.join(t["_dir"], "exec.md")
    if os.path.isfile(p):
        for line in read_text(p).splitlines():
            f = [c.strip() for c in line[2:].split("|")] if line.startswith("- ") else []
            if len(f) >= 4 and f[1] == "브랜치 판정":
                judged[f[2]] = f[3]
    return judged


def contract_token(t):
    """머리 파일 「시그니처와 결정 번호」에 `[계약]` 토큰이 있는가(서버 구현의 읽기 판정 조건)."""
    return "[계약]" in t.get("_sections", {}).get("시그니처와 결정 번호", "")


def doc_check_command(run_dir):
    """recon.md 「문서를 읽는 검사」의 글(없거나 `없음`이면 "")."""
    p = os.path.join(run_dir or "", "recon.md")
    if not run_dir or not os.path.isfile(p):
        return ""
    text = sections(read_text(p), level=2).get("문서를 읽는 검사", "").strip()
    return "" if not text or re.match(r"^[-\s]*없음", text) else text


def doc_check_result(t):
    """배포 실행 main-run.md 「넣기 전 문서 검사」의 (`- 검증 commit:` SHA, `- 종료 코드:` 정수 또는 None). 없으면 ("", None).
    배포 기록 커밋은 CI를 거치지 않아 시험이 문서를 읽는 저장소에서는 넣기 전에 그 커밋에서 문서 검사를 돌린다.
    judge-run.md는 배포 뒤 확인과 배포 대상 동일성(완료 관문이 읽음)을 이미 담고 있어, 두 번째 실행 판정자가 덮어쓰지
    않게 메인 실행으로 적는다."""
    path = os.path.join(t["_dir"], "main-run.md")
    text = sections(read_text(path), level=2).get("넣기 전 문서 검사", "") if os.path.isfile(path) else ""
    m = re.search(r"^-\s*검증 commit\s*:\s*([0-9a-fA-F]{7,40})\s*$", text, flags=re.M)
    rc = re.search(r"^-\s*종료 코드\s*:\s*(-?\d+)", text, flags=re.M)
    return (m.group(1) if m else ""), (int(rc.group(1)) if rc else None)


def doc_check_commit(t):
    return doc_check_result(t)[0]


def inside(root, path):
    """path가 root 안의 파일인가. 링크를 푼 경로로 본다."""
    return os.path.normcase(os.path.realpath(path)).startswith(os.path.normcase(os.path.realpath(root)) + os.sep)


def copy_canon_sections(run_dir, task_dir, section_text):
    """코드 task가 시작할 때 「정본의 절」 파일의 사본과 해시를 뜬다(설계 6.12절). 정본은 git 밖이고 덮어써지므로,
    판정자가 `[설계:]`를 그 task 시점의 판으로 대조하려면 사본이 있어야 한다. 이미 떴으면 그대로 둔다."""
    folder = os.path.join(task_dir, DESIGN_COPY)
    hashes = os.path.join(folder, "hashes.md")
    if os.path.isfile(hashes):
        return
    rows, seen = [], set()
    for m in CANON_PATH_RE.finditer(section_text or ""):
        rel = posixpath.normpath(m.group(0).rstrip(".:;").replace("\\", "/"))
        if rel.lower() in seen:
            continue
        seen.add(rel.lower())
        path = os.path.join(run_dir, *rel.split("/"))
        if not os.path.isfile(path) or not inside(run_dir, path):
            rows.append("없음 " + rel)
            continue
        with open(path, "rb") as f:
            data = f.read()
        target = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)
        rows.append("{} {}".format(hashlib.sha256(data).hexdigest(), rel))
    os.makedirs(folder, exist_ok=True)
    write_text(hashes, "\n".join(rows) + "\n" if rows else "(정본의 절 없음)\n")


def run_dir_of(t):
    return os.path.dirname(os.path.dirname(t["_dir"])) if t.get("_dir") else None   # tasks\T…의 두 단계 위


def stage_judges(t, stage):
    """묻는 stage 앞의 판정 요구표를 쓰는가: 1.1.1부터 시작한 task이고 (kind, stage)가 kinds.STAGE_JUDGES에 있으면 그 칸."""
    if not stage or not version_at_least(t.get("started_version", ""), RULES_V111):
        return None
    return kinds.STAGE_JUDGES.get((t.get("kind", ""), stage))


def needs_judgment_record(t):
    """결과 파일 「판단」과 판정 파일 「판단 대조」를 쓰는 task: 1.2.0부터 시작한 코드 task."""
    return t.get("kind") in kinds.AUTO_DEPEND_KINDS and version_at_least(t.get("started_version"), RULES_V120)


def judgment_problems(t):
    """결과 파일 「판단」 절의 문제 목록. 꼴은 `references/practices/code-judgment.md`다."""
    path = os.path.join(t["_dir"], "result.md")
    if not needs_judgment_record(t) or not os.path.isfile(path):
        return []
    body = sections(read_text(path), level=2).get("판단", "").strip()
    if not body:
        return ["「판단」 절 없음"]
    out = []
    for line in body.splitlines():
        indented = line.startswith((" ", "\t"))
        if not line.strip() or JUDGMENT_NONE.match(line) or (indented and not line.lstrip().startswith("- ")):
            continue
        if indented or not line.startswith("- ") or not judgment_line_ok(line):
            out.append("「판단」 줄의 꼴: " + line[:60])
    return out


def judgment_tags(line):
    """「판단」 줄의 표지 [(이름, 값)]. 값의 공백과 백틱을 벗긴다."""
    return [(key, value.strip(" `")) for key, value in JUDGMENT_TAG.findall(line)]


def judgment_line_ok(line):
    """`[설계:]` 하나이거나, 닫힌 `[종류:]`, `파일:줄` 꼴 `[위치:]` 하나씩에 `[따름:]`이 있어도 되는 줄."""
    found = judgment_tags(line)
    tags = dict(found)
    if len(tags) != len(found) or not all(tags.values()):
        return False
    if "설계" in tags:
        return set(tags) == {"설계"}
    return tags.get("종류") in kinds.JUDGMENT_KINDS and bool(JUDGMENT_PLACE.match(tags.get("위치", ""))) \
        and ("따름" not in tags or bool(JUDGMENT_PLACE.match(tags["따름"])))


FLOW_REVIEW_SECTION = "흐름 리뷰 전·후"


def answer_source(t):
    """`--from-answer`로 만든 task가 가리키는 답의 (task, 시각). 아니면 ("", "")."""
    m = ANSWER_ORIGIN.match(str(t.get("origin", "") or "").strip())
    return (m.group(1), m.group(2)) if m else ("", "")


def open_objection(t, tasks):
    """닫히지 않은 흐름 리뷰 이의의 시각(없으면 빈 글): 마지막 이의 뒤에 그 답에서 만든 task도 철회도 없을 때."""
    last, withdrawn = "", ""
    for line in record_lines(t):
        f = record_fields(line)
        if len(f) >= 2 and f[1] == REVIEW_OBJECTION:
            last = f[0]
        elif len(f) >= 2 and f[1] == OBJECTION_WITHDRAWN:
            withdrawn = f[0]
    if not last or withdrawn >= last:
        return ""
    return "" if any(answer_source(o)[0] == t.get("id") and answer_source(o)[1] >= last for o in tasks.values()) else last


def flow_review_rules(t):
    """1.2.0부터 시작한 흐름별 검증: 실행 판정이 전·후를 돌리고 화면이 흐름 리뷰 차례를 쓴다(설계 7.1절). 옛 task는 지금 규칙 그대로다."""
    return t.get("kind") == "flow-verify" and version_at_least(t.get("started_version"), RULES_V120)


def required_judges(t, stage=None):
    """이 task가 `완료`·`승인대기`로 가기 전에 있어야 하는 판정({"read", "run"}). 각 정의의 「자체 검증」에서 뽑았다.
    stage(묻는 단계)를 주면 STAGE kind는 kind 단위 always 대신 kinds.STAGE_JUDGES의 칸을 쓴다(stage_judges).
    구현의 실행 판정은 늘 둔다(문서만 바꾸는 구현은 관련 테스트가 recon 「문서를 읽는 검사」).
    합치기는 exec.md 브랜치 판정에 `충돌`이 하나라도 있으면(충돌을 고친 합치기) 읽기 판정을 요구한다.
    테스트 실패로 코드를 고친 합치기는 exec.md에 흔적이 없어 여기서 가리지 못한다.
    배포 실행 넣기승인 앞의 문서 검사(recon.md 「문서를 읽는 검사」)는 판정 파일이 아니라 main-run.md로 본다(judges_present)."""
    kind = t.get("kind", "")
    need = set()
    k = kinds.KINDS.get(kind)
    gate = stage_judges(t, stage)
    if gate is not None:
        need |= set(gate)
    if gate is None and k is not None and k.run_judge == "always" and (kind != "flow-verify" or flow_review_rules(t)):
        need.add("run")   # 흐름별 검증의 실행 판정은 전·후 몫이고 1.2.0부터다
    if gate is None and k is not None and k.read_judge == "always":
        need.add("read")
    if needs_judgment_record(t):
        need.add("read")   # 숨은 판단과 코드 의견은 읽기 판정이 쓴다(설계 11.1절)
    if kind in kinds.IMPLEMENT_KINDS and k.read_judge == "conditional":
        cells = result_cells(t) or {}
        if t.get("closes_ac") or str(t.get("machine_check", "")).strip() == "3" or item_count(cells.get("알릴 것", "")):
            need.add("read")
        if kind == "be-implementation" and contract_token(t):
            need.add("read")   # 「시그니처와 결정 번호」에 [계약]이 있는 서버 구현
        if uses_domain_rules(t) and touched_in_paths(t, "화면"):
            need.add("read")   # 화면 경로에 닿는 구현(판정자가 "화면 동작을 바꾸는가"를 본다)
    if kind == "deploy-exec" and os.path.isfile(os.path.join(t["_dir"], "result.md")):
        need.add("read")   # 배포 기록(result.md)을 쓴 뒤의 읽기 판정
    if kind == "merge" and "충돌" in branch_judgements(t).values():
        need.add("read")   # 충돌을 고친 합치기의 읽기 판정
    return need


def judge_header(path):
    """판정 파일 첫 줄 `판정자: {인스턴스 이름} {YYYY-MM-DD HH:MM:SS}`를 (이름, 시각 초)로. 없으면 (None, None).
    초가 없으면 그 분의 끝(59초)으로 본다(판정 뒤 바뀜을 늦게 잡는 쪽). 시간대 꼬리는 버리고 이 컴퓨터 시각으로 본다."""
    from datetime import datetime
    if not os.path.isfile(path):
        return None, None
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        m = JUDGE_LINE.match(line.strip())
        if not m:
            return _judge_header_loose(line.strip())
        sec = m.group(4)[1:] if m.group(4) else "59"
        when = datetime.strptime("{} {}:{}".format(m.group(2), m.group(3), sec), "%Y-%m-%d %H:%M:%S")
        return m.group(1), when.timestamp()
    return None, None


def _judge_header_loose(line):
    """`date` 기본 출력(`Wed Oct  7 23:24:33 KST 2026`) 같은 꼴도 받는다. 못 읽으면 (None, None)."""
    from datetime import datetime
    m = re.match(r"^판정자:\s*(\S+)\s+(.+)$", line)
    if not m:
        return None, None
    words = [w for w in m.group(2).split() if not re.fullmatch(r"[A-Z]{2,5}|[+-]\d{4}", w)]
    text = " ".join(words)
    for fmt in ("%a %b %d %H:%M:%S %Y", "%Y년 %m월 %d일 %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return m.group(1), datetime.strptime(text, fmt).timestamp()
        except ValueError:
            pass
    return None, None


def judges_present(t, stage=None):
    """(있음 여부, 이유). 새 task는 필요한 판정 파일이 모두 있고 첫 줄 판정자가 그 역할이어야 한다.
    옛 task는 판정 파일이 하나라도 있으면 된다. stage는 STAGE kind가 묻는 단계(required_judges)."""
    d = t["_dir"]
    if not is_new_task(t):
        if any(os.path.isfile(os.path.join(d, f)) for f in kinds.JUDGE_FILES.values()):
            return True, ""
        return False, "판정 파일(judge.md·judge-run.md)이 없음"
    missing = []
    need = required_judges(t, stage)
    need_names = {kinds.JUDGE_FILES[n] for n in need}
    for name in sorted(set(kinds.JUDGE_FILES.values())):
        path = os.path.join(d, name)
        if not os.path.isfile(path):
            if name in need_names:
                missing.append("{} 없음".format(name))
            continue
        # 필요하지 않아도 있는 판정 파일은 그 역할의 판정자가 쓴 것이어야 한다(메인이 쓴 judge.md를 잡는다)
        who, _ = judge_header(path)
        if not who or not who.startswith(JUDGE_PREFIX[name]):
            missing.append("{} 첫 줄 판정자가 {}…가 아님({})".format(name, JUDGE_PREFIX[name], who or "판정자 줄 없음"))
    if not missing and (t.get("kind"), stage) == ("deploy-exec", "넣기승인") and stage_judges(t, stage) is not None \
            and doc_check_command(run_dir_of(t)) and (not doc_check_result(t)[0] or doc_check_result(t)[1] is None):
        missing.append("main-run.md 「넣기 전 문서 검사」의 검증 commit·종료 코드 없음(recon.md 「문서를 읽는 검사」를 배포 기록 "
                       "커밋에서 돌림. 실패한 결과는 화면 맨 위에 올리고 묻는다)")
    if needs_judgment_record(t) and os.path.isfile(os.path.join(d, kinds.JUDGE_FILES["read"])) \
            and "판단 대조" not in sections(read_text(os.path.join(d, kinds.JUDGE_FILES["read"])), level=2):
        missing.append("judge.md 「판단 대조」 절 없음(references/practices/code-judgment.md)")
    if flow_review_rules(t) and os.path.isfile(os.path.join(d, kinds.JUDGE_FILES["run"])) \
            and FLOW_REVIEW_SECTION not in sections(read_text(os.path.join(d, kinds.JUDGE_FILES["run"])), level=2):
        missing.append("judge-run.md 「{}」 절 없음(references/formats/judge-run-file.md)".format(FLOW_REVIEW_SECTION))
    if flow_review_rules(t) and judge_header(os.path.join(d, kinds.JUDGE_FILES["read"]))[1] is not None \
            and judge_header(os.path.join(d, kinds.JUDGE_FILES["run"]))[1] is not None \
            and judge_header(os.path.join(d, kinds.JUDGE_FILES["read"]))[1] < judge_header(os.path.join(d, kinds.JUDGE_FILES["run"]))[1]:
        missing.append("읽기 판정이 실행 판정보다 앞섬(새 전·후를 「이 흐름이 한 일」과 대조하도록 읽기 판정을 다시 띄운다)")
    if not missing:
        missing.extend(judge_run_contract_problems(t))
    return (not missing), "; ".join(missing)


FINAL_CI_KEYS = ("범위", "검증 commit", "검증 artifact")


def final_ci_values(t):
    """judge-run.md 「최종 배포 후보 CI」의 {범위, 검증 commit, 검증 artifact}. 마무리의 완료 관문, 얼림의 넣는 끝
    (exec.py), 배포의 권위 있는 최종 CI(canonical_final_ci)가 함께 읽는 하나의 원천."""
    path = os.path.join(t["_dir"], kinds.JUDGE_FILES["run"])
    text = sections(read_text(path), level=2).get("최종 배포 후보 CI", "") if os.path.isfile(path) else ""
    values = {}
    for line in text.splitlines():
        m = re.match(r"^-\s*({})\s*:\s*(.+?)\s*$".format("|".join(FINAL_CI_KEYS)), line.strip())
        if m:
            values[m.group(1)] = m.group(2)
    return values


SOURCE_TESTED = "없음(소스 시험)"   # 소스를 시험하고 배포 때 빌드하는 프로젝트의 `검증 artifact`. 이 글자 그대로일 때만 표지다
SOURCE_TESTED_FACT = "빌드 결과물 자체를 시험한 것은 아닙니다. 빌드 설정과 환경 차이는 배포 뒤 확인이 잡습니다"
ARTIFACT_ID = re.compile(r"[A-Za-z0-9][!-~]*")


def started_tasks(run_dir):
    """시작한 적이 있는 task. 시작한 적 없는 대기·백로그·보류 행(시작 시각과 판본이 모두 빔)은 세지 않는다."""
    return [o for o in load_tasks(run_dir).values()
            if not (o.get("status") in ("대기", "백로그", "보류") and not o.get("started") and not o.get("started_version"))]


def run_from_v120(run_dir):
    """이 실행이 1.2.0부터 시작했는가: 시작한 task가 있고 모두 1.2.0 이상이다. run.md 판본은 하네스를 올릴 때 고치고
    새 task의 started_version은 지금 판본이므로, 그 하나만 보면 앞서 시작한 실행의 뒤 task가 새 규칙을 받는다."""
    started = started_tasks(run_dir)
    return bool(started) and all(version_at_least(o.get("started_version"), RULES_V120) for o in started)


def final_ci_artifact_problem(value):
    """1.2.0부터 `검증 artifact`로 받는 값은 소스 시험 표지 글자 그대로이거나, 숫자가 든 빈칸 없는 식별자다(문제 글, 없으면 빈 글)."""
    if value == SOURCE_TESTED or (ARTIFACT_ID.fullmatch(value) and any(c.isdigit() for c in value)):
        return ""
    return "최종 배포 후보 CI 검증 artifact가 식별자나 `{}`가 아님({})".format(SOURCE_TESTED, value)


def canonical_final_ci(run_dir):
    """현재 실행의 권위 있는 최종 후보: 완료된 1.0.1 wrap-up 가운데 가장 늦게 승인된 것."""
    wraps = [o for o in load_tasks(run_dir).values()
             if o.get("kind") == "wrap-up" and o.get("status") == kinds.DONE and uses_isolation_contract(o)]
    if not wraps:
        return None, "완료된 1.0.1 wrap-up 최종 CI가 없음"
    wraps.sort(key=lambda o: (str(o.get("approved", "")), str(o.get("id", ""))))
    authority = wraps[-1]
    values = final_ci_values(authority)
    missing = [k for k in FINAL_CI_KEYS if not values.get(k)]
    if missing:
        return None, "{}의 최종 CI 필수 값 없음: {}".format(authority.get("id"), ", ".join(missing))
    return values, ""


def deploy_only_run(run_dir):
    """1.2.0부터 시작했고 마무리 task가 하나도 없는 실행(배포만). 끝나지 않은 마무리가 있으면 아니다."""
    return run_from_v120(run_dir) and not any(o.get("kind") == "wrap-up" for o in load_tasks(run_dir).values())


def no_ci_accepted(run_dir, t):
    """배포만 실행에서 사람이 최종 CI 없음을 받아들였는가."""
    return deploy_only_run(run_dir) and risk_accepted(t, item=NO_CI_RISK)


def source_tested_lines(run_dir, t):
    """마무리·배포 화면에 보일 소스 시험의 한계. 빌드 결과물을 시험했거나 1.2.0 앞에 시작한 실행이면 빈 목록."""
    kind = str(t.get("kind", ""))
    if not (kind == "wrap-up" or kind.startswith("deploy-")) or not run_from_v120(run_dir):
        return []
    if kind != "wrap-up" and deploy_only_run(run_dir):
        fact = "- 이 실행에는 마무리 task가 없어 최종 CI가 없습니다. 올라갈 커밋을 이 실행이 시험하지 않았습니다"
        return [fact if no_ci_accepted(run_dir, t) else fact + ". 배포를 닫으려면 그 위험을 받아들인다는 답이 필요합니다"]
    values = final_ci_values(t) if kind == "wrap-up" else canonical_final_ci(run_dir)[0] or {}
    if values.get("검증 artifact") != SOURCE_TESTED:
        return []
    return ["- 최종 CI는 소스를 시험했습니다. " + SOURCE_TESTED_FACT]


def final_ci_cause(t):
    """마무리 judge-run.md 「최종 CI 실패 원인」의 `- 원인: 문서|코드`(없으면 ""). 실행 판정자가 문서 커밋 전 끝에서
    같은 실패를 다시 돌려 가른다(references/kinds/wrap-up/run-check.md)."""
    path = os.path.join(t["_dir"], kinds.JUDGE_FILES["run"])
    text = sections(read_text(path), level=2).get("최종 CI 실패 원인", "") if os.path.isfile(path) else ""
    m = re.search(r"^-\s*원인\s*:\s*\**\s*(문서|코드)", text, flags=re.M)
    return m.group(1) if m else ""


def final_ci_failed(t):
    """마무리의 최종 CI(실행 판정)에 통과 못 한 기준이 있는가(judge-run.md 「통과 못 한 기준」 항목 수)."""
    path = os.path.join(t["_dir"], kinds.JUDGE_FILES["run"])
    if not os.path.isfile(path):
        return 0
    return item_count(sections(read_text(path), level=2).get("통과 못 한 기준", ""))


RISK_REFUSED = re.compile(r"안\s*함|않|아니|거부")


BUILD_ID_RISK, TREE_RISK, NO_CI_RISK = "빌드 식별자", "작업 트리", "최종 CI 없음"   # 위험 수용 답의 결정 칸에 적는 이유(`승인|위험 수용 {이유}|{원문}`)


def risk_answer(line, item=""):
    """승인 기록 한 줄이 위험을 받아들인 답인가. item을 주면 결정 칸에 그 이유가 있고 원문이 있는 답만 받는다.
    item이 없으면(최종 CI·문서 검사 실패) 이유가 붙은 답은 받지 않는다: 사람이 동의한 위험이 다르다."""
    f = record_fields(line)
    decision = f[2].strip() if len(f) >= 3 else ""
    if not decision.startswith("위험 수용") or RISK_REFUSED.search(decision) or not approval_line(line) \
            or reused_answer(line):
        return False
    if not item:
        return not any(reason in decision for reason in (BUILD_ID_RISK, TREE_RISK, NO_CI_RISK))
    return item in decision and bool((record_quote(line) or "").strip())


def risk_accepted(t, since=None, item=""):
    """실패를 사람이 받아들였는가: 기준 시각(since, 없으면 실행 판정 파일의 판정 시각) 뒤의 승인 줄 가운데 결정 칸이
    `위험 수용`으로 시작하고 부정어(`안 함`·`않`·`아니`·`거부`)가 없는 것(`--record "승인|위험 수용|{원문}"`,
    selfcheck.md 「실패 처리」의 위험을 받아들임 = 승인). 리뷰 111b N4: `위험 수용 안 함`을 승인으로 세던 판별.
    item을 주면 그 이유를 적은 답만 센다(risk_answer)."""
    from datetime import datetime
    judged = since if since is not None else judge_header(os.path.join(t["_dir"], kinds.JUDGE_FILES["run"]))[1]
    for line in record_lines(t):
        if not risk_answer(line, item):
            continue
        f = record_fields(line)
        for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16)):
            try:
                when = datetime.strptime(f[0][:n], fmt).timestamp()
                break
            except ValueError:
                when = None
        # 판정 시각에 초가 없으면 judge_header가 그 분의 끝(59초)으로 읽으므로 1분 폭을 둔다
        if when is not None and (judged is None or when >= judged - 59):
            return True
    return False


def judge_run_contract_problems(t):
    """완료 전 실행 판정 계약 문제. 자원 대기는 모든 판본, 새 두 절은 1.0.1부터 검사한다."""
    wait = resource_wait(t)
    if wait:
        return [wait]
    if not uses_isolation_contract(t) or "run" not in required_judges(t):
        return []
    path = os.path.join(t["_dir"], kinds.JUDGE_FILES["run"])
    if not os.path.isfile(path):
        return []   # 파일 없음은 judges_present의 기존 경로가 보고한다
    sec = sections(read_text(path), level=2)
    problems = []
    evidence = sec.get("검사 입력과 독립 근거")
    if evidence is None:
        problems.append("judge-run.md 「검사 입력과 독립 근거」 없음")
    else:
        required = (("제품",), ("시험",), ("설정",), ("lock", "설치", "의존"), ("명령",), ("환경",),
                    ("판정자",), ("시각",), ("종료 코드",), ("로그",))
        missing = ["/".join(words) for words in required if not any(word in evidence for word in words)]
        if missing or item_count(evidence) == 0:
            problems.append("judge-run.md 「검사 입력과 독립 근거」 필수 값 없음: {}".format(
                ", ".join(missing) if missing else "실행 근거"))
    remaining = sec.get("남은 검사와 자원 대기")
    if remaining is None:
        problems.append("judge-run.md 「남은 검사와 자원 대기」 없음")
    elif item_count(remaining):
        problems.append("실행하지 않은 검사 또는 자원 대기가 남음")
    return problems


RECORD_MESSAGE = ' | 원문 메시지: "'
TEST_CHANGE_POINT = "시험 변화"
UNMEASURED_POINT = CODE_CHECK_ORIGIN + " 재지 못함 "   # `코드 확인 재지 못함 {T}|합쳐도 됨|{원문}`. 보안 신호와 시험 변화를 함께 푼다. 줄에는 `{T}@{커밋}`으로 적힌다
UNMEASURED_NO_COMMIT = "없음"   # 답 줄과 다시 잰 줄의 커밋 칸: 커밋 값이 비었다(코드가 없다는 뜻이 아니라 모른다는 뜻이다)
UNMEASURED_ANSWER = "합쳐도 됨"
REVIEW_OBJECTION = "리뷰 이의"   # 흐름 리뷰의 `이의 n`. 고치는 task가 생기거나 철회될 때까지 그 검증을 닫지 못한다
OBJECTION_WITHDRAWN = REVIEW_OBJECTION + " 철회"
PARTIAL_POINTS = (TEST_CHANGE_POINT, CODE_CHECK_ORIGIN, REVIEW_OBJECTION)   # 한 지점의 답을 남기는 승인 기록 지점의 머리. 전체 승인으로 세지 않고 상태도 옮기지 않는다


def record_core(line):
    """승인 기록 줄에서 `원문 메시지:` 칸을 뗀 줄. 그 칸은 사람이 읽는 기록이고, 한 메시지에 다른 task의 답이 함께 있으므로
    승인 판별과 얼림의 재료가 되지 않는다."""
    at = line.rfind(RECORD_MESSAGE)
    return line[:at] if at >= 0 else line


def record_lines(t):
    return [record_core(l.strip()) for l in t["_sections"].get("승인 기록", "").splitlines() if l.strip().startswith("- ")]


def record_fields(line):
    """승인 기록 한 줄 `- {시각} | {지점} | {결정} | 원문: …`을 칸 목록으로."""
    return [c.strip() for c in line[2:].split("|")]


def acked_codes(t):
    """승인 기록의 `점검 확인` 줄이 가리키는 점검 코드(R1~R5, U1…)와 그 확인의 가장 늦은 시각(초)."""
    from datetime import datetime
    out = {}
    for line in record_lines(t):
        f = record_fields(line)
        if len(f) >= 3 and f[1] == "점검 확인" and f[2].split():
            when = 0.0
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    when = datetime.strptime(f[0], fmt).timestamp()
                    break
                except ValueError:
                    pass
            code = f[2].split()[0]
            out[code] = max(out.get(code, 0.0), when)
    return out


def has_quoted_answer(t):
    """사용자 답의 원문(따옴표 안의 말)이 있는 승인 기록 줄이 있는가. 알림·점검 확인 줄은 세지 않는다."""
    for line in record_lines(t):
        f = record_fields(line)
        if len(f) >= 2 and (f[1] in ("알림", "점검 확인") or f[1].startswith(PARTIAL_POINTS)):
            continue   # 곳 답과 시험 변화 답은 그 지점의 답이고 task 전체의 답이 아니다(설계 6.16절)
        if re.search(r'"[^"]+"', line):
            return True
    return False


CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_ANSWER_TASK = re.compile(r"^(T\d{3,})\s+(\S.*)$")
_ANSWER_TASK_ITEM = re.compile(r"^([" + CIRCLED + r"])\s*(\S.*)$")
_ANSWER_TASK_ITEMS = re.compile(r"^(\S.*?)\s+([" + CIRCLED + r"\s]+)$")
_ANSWER_OBJECTION = re.compile(r"^이의\s+(\d+)$")
_ANSWER_REST = re.compile(r"^나머지\s+(\S.*)$")
_ANSWER_EXCEPT = re.compile(r"^(\d+)\s*빼고\s+(\S.*)$")
_ANSWER_ITEM = re.compile(r"^(\d+)[.)]?\s+(\S.*)$")


def _answer_piece(text):
    m = _ANSWER_TASK.match(text)
    if m:
        task, rest = m.group(1), m.group(2)
        one = _ANSWER_TASK_ITEM.match(rest)
        if one:
            return {"task": task, "item": CIRCLED.index(one.group(1)) + 1, "value": one.group(2)}
        many = _ANSWER_TASK_ITEMS.match(rest)
        if many:
            return {"task": task, "value": many.group(1),
                    "items": [CIRCLED.index(c) + 1 for c in many.group(2) if c in CIRCLED]}
        return {"task": task, "value": rest}
    m = _ANSWER_OBJECTION.match(text)
    if m:
        return {"objection": int(m.group(1))}
    m = _ANSWER_REST.match(text)
    if m:
        return {"rest": True, "value": m.group(1)}
    m = _ANSWER_EXCEPT.match(text)
    if m:
        return {"except": int(m.group(1)), "value": m.group(2)}
    m = _ANSWER_ITEM.match(text)
    if m:
        return {"item": int(m.group(1)), "value": m.group(2)}
    if re.fullmatch(r"[0-9]+", text):
        return {"number": int(text)}
    return {"value": text}


def _answer_settled(piece, allowed, with_text):
    """값을 화면의 선택지로 맞춘 조각, 맞지 않으면 None. 맨 번호와 이의는 값이 없고, with_text의 선택지만 뒤에 글을 받는다."""
    value = piece.get("value")
    if value is None or value in allowed or re.fullmatch(r"[0-9]+", value):
        return piece
    for name in with_text:
        m = re.fullmatch(re.escape(name) + r"(?:\s*:\s*|\s+)(\S.*)", value, re.S)
        if m:
            return dict(piece, value=name, text=m.group(1))
    return None


def _answer_pieces(text):
    """줄바꿈과 쉼표로 나눈다. 조각에 `:`가 나오면 그 줄의 나머지는 글이므로 나누지 않는다."""
    out = []
    for line in (text or "").split("\n"):
        pending = line
        while pending:
            head, comma, tail = pending.partition(",")
            if ":" in head or not comma:
                out.append(pending)
                break
            out.append(head)
            pending = tail
    return [p.strip() for p in out if p.strip()]


def parse_answer(text, allowed, with_text=(), own_task=None):
    """답의 꼴(설계 8.1절)을 기계로 푼다. allowed는 그 화면의 선택지 이름이고 with_text는 그 가운데 뒤에 글을 받는 것이다.
    조각이 모두 꼴에 맞고 값이 선택지이면 목록, 아니면 None(메인이 되묻는다). own_task를 주면 다른 task의 조각은 그 화면이
    풀도록 값을 보지 않고 `raw`에 원문을 담아 돌려준다. 글은 한 줄이다(여러 task의 답은 줄로 나눈다)."""
    parsed = []
    for text_piece in _answer_pieces(text):
        piece = _answer_piece(text_piece)
        if own_task and piece.get("task") not in (None, own_task):
            parsed.append({"task": piece["task"], "raw": text_piece})
        else:
            parsed.append(_answer_settled(piece, allowed, with_text))
    return parsed if parsed and all(parsed) else None


HANDED_POINT = "하실 일 넘김"   # 넘김 답의 지점. 승인 줄이 아니라 명령을 얼리지도, 화면을 닫지도 않는다


def approval_line(line):
    """승인 기록 한 줄이 승인인가(지점 칸이나 결정 칸이 `승인`, 옛 꼴 원문 "승인"·"승인 (…)").
    알림·점검 확인·되물음 줄과 결정이 보류·거절·되돌림인 줄은 승인이 아니다. 규칙 판 1의 승인 판별과
    exec.py의 얼림이 함께 쓴다."""
    line = record_core(line)
    f = record_fields(line)
    if len(f) < 2:   # 칸이 없는 옛 꼴은 원문만 본다
        return bool(re.search(r'"승인\s*(?:\(|")', line))
    point, decision = f[1], (f[2] if len(f) > 2 else "")
    if point in ("알림", "점검 확인", HANDED_POINT, "L4 확인", "실물 확인") or point.startswith(("되물음",) + PARTIAL_POINTS):
        return False
    if any(w in decision for w in ("보류", "거절", "되돌림")):
        return False
    if point == "승인" or decision == "승인" or re.match(r"승인\s*[(:]", decision):
        return True
    return bool(re.search(r'"승인\s*(?:\(|")', line))   # 옛 꼴: 전체: "승인", "승인 (Recommended)"


def prior_approval(t):
    """사람이 이미 이 task를 승인했는가(승인 뒤 같은 작성자 일을 이어 한 task의 끝)."""
    return any(approval_line(line) for line in record_lines(t))


SHORT_ANSWER_CHARS = 10   # T001 Q4: 괄호 안과 공백을 뺀 글자 수가 이 값 이하면 한 마디 답


def short_answer(text):
    """한 마디 답인가: 괄호 (…)·（…）를 안까지 지우고 공백을 모두 지운 길이가 SHORT_ANSWER_CHARS 이하."""
    return len("".join(PAREN.sub("", text or "").split())) <= SHORT_ANSWER_CHARS


def answer_key(text):
    """원문을 견줄 때의 꼴(공백 차이를 지움)."""
    return " ".join((text or "").split())


def record_quote(line):
    """승인 기록 줄의 `원문: "…"` 따옴표 안(없으면 None)."""
    m = re.search(r'원문:\s*"([^"]*)"', line)
    return m.group(1) if m else None


def reused_answer(line):
    """`--reuse-answer`로 적은 승인 기록 줄인가(칸 가운데 `재사용 답:`으로 시작하는 것이 있음)."""
    return any(c.startswith("재사용 답:") for c in record_fields(line))


def norm_text(text):
    return "\n".join(l.strip() for l in (text or "").splitlines() if l.strip())


def text_diff(old, new, limit=6):
    """두 글의 다른 줄을 `원문: …`·`지금: …` 줄로(사람이 화면에서 판단할 재료)."""
    a = [l.strip() for l in (old or "").splitlines() if l.strip()]
    b = [l.strip() for l in (new or "").splitlines() if l.strip()]
    gone = [l for l in a if l not in b]
    came = [l for l in b if l not in a]
    out = ["원문: " + l for l in gone[:limit]] + ["지금: " + l for l in came[:limit]]
    if len(gone) > limit or len(came) > limit:
        out.append("(다른 줄 더 있음)")
    return out


def criteria_files(task_dir):
    """(원본 경로, [정정 경로 …]) — 정정은 번호 순."""
    orig = os.path.join(task_dir, "criteria.orig.md")
    amends = []
    if os.path.isdir(task_dir):
        for name in os.listdir(task_dir):
            m = re.match(r"criteria\.amend(\d+)\.md$", name)
            if m:
                amends.append((int(m.group(1)), os.path.join(task_dir, name)))
    return orig, [p for _, p in sorted(amends)]


def unlisted_entries(t):
    """머리 파일 「표 밖 전이」 절의 줄(`task_set.py --unlisted`가 쓴다)."""
    return [l.strip() for l in t["_sections"].get("표 밖 전이", "").splitlines() if l.strip().startswith("- ")]


def record_check(t):
    """기록 점검. [(코드, 내용, 하위 줄 목록)]을 돌려준다. 승인 기록에 `점검 확인 {코드}`가 있는 것은 뺀다
    (R3는 확인 시각 뒤에 그 파일이 다시 바뀌었으면 다시 걸린다).
    R1 필요한 판정 파일·판정자 줄, R2 판정 기준이 만들 때와 다름, R3 판정 뒤 바뀐 판정 파일·result.md,
    R4 코드 task 완료인데 commit 빔, R5 승인인데 원문 없음 — 이 다섯은 새 task만. U{n} 표 밖 전이는 모든 task."""
    out = []   # (코드, 내용, 하위 줄, 바뀐 시각)
    d = t["_dir"]
    status, kind = t.get("status", ""), t.get("kind", "")
    for i, line in enumerate(unlisted_entries(t), 1):
        out.append(("U{}".format(i), "[표 밖 전이] " + line[2:], [], 0))
    if is_new_task(t):
        # 합치기·마무리·배포 실행의 승인대기는 실행 승인일 수 있어 판정 전이다
        closed = status == kinds.DONE or (status == "승인대기" and kind not in kinds.STAGE_KINDS)
        if closed and str(t.get("done_via", "")).strip() != "백로그":
            ok, why = judges_present(t)
            if not ok:
                out.append(("R1", "필요한 판정 파일: " + why, [], 0))
        orig, amends = criteria_files(d)
        if os.path.isfile(orig):
            expect = amends[-1] if amends else orig
            cur = t["_sections"].get("판정 기준", "")
            if norm_text(cur) != norm_text(read_text(expect)):
                out.append(("R2", "판정 기준이 {}와 다르고 「판정 기준 정정」 기록이 없음".format(os.path.basename(expect)),
                            text_diff(read_text(expect), cur), 0))
        times = {}
        for name in kinds.JUDGE_FILES.values():
            p = os.path.join(d, name)
            who, when = judge_header(p)
            if who and when:
                times[name] = when
                if os.path.getmtime(p) > when + MTIME_SLACK:
                    out.append(("R3", "{}가 첫 줄의 판정 시각 뒤에 바뀜".format(name), [], os.path.getmtime(p)))
        readers = [times["judge.md"]] if "judge.md" in times else []
        if kind in kinds.READBACK_KINDS and "judge-run.md" in times:
            readers.append(times["judge-run.md"])
        res = os.path.join(d, "result.md")
        if readers and os.path.isfile(res) and os.path.getmtime(res) > max(readers) + MTIME_SLACK:
            snap = os.path.join(d, "result.pre-screen.md")
            only_screen = False
            if os.path.isfile(snap):
                a = sections(read_text(snap), level=2)
                b = sections(read_text(res), level=2)
                a.pop("승인 화면", None)
                b.pop("승인 화면", None)
                only_screen = a == b
            if not only_screen:
                out.append(("R3", "result.md가 그것을 읽은 판정 뒤에 바뀜(「승인 화면」 밖)", [], os.path.getmtime(res)))
        lvl = rules_level(t)
        # 규칙 판 2 규칙으로 시작한 task는 받아오기 수정(메인이 병합 커밋을 commit=으로)과 합치기(exec.py가 commit에)도 본다
        if status == kinds.DONE and kind in kinds.commit_kinds(lvl) and not str(t.get("commit", "")).strip() \
                and (lvl >= 2 or "받아오기" not in str(t.get("origin", ""))) and not no_change(t):
            out.append(("R4", "코드 task가 완료인데 commit이 빔", [], 0))
        if str(t.get("approval_mode", "")).strip() == "승인" and not has_quoted_answer(t):
            out.append(("R5", "승인인데 「승인 기록」에 사용자 원문 줄이 없음", [], 0))
    acked = acked_codes(t)
    ack_crit = os.path.join(d, "criteria.ack.md")   # R2를 확인할 때의 「판정 기준」(task_set.py가 남김)
    keep = []
    for code, msg, sub, changed in out:
        if code == "R2" and code in acked and os.path.isfile(ack_crit):
            # 확인한 뒤 판정 기준이 또 바뀌었으면 다시 건다
            if norm_text(t["_sections"].get("판정 기준", "")) == norm_text(read_text(ack_crit)):
                continue
            keep.append((code, msg + "(점검 확인 뒤 또 바뀜)", text_diff(read_text(ack_crit), t["_sections"].get("판정 기준", ""))))
            continue
        if code in acked and not (changed and changed > acked[code] + MTIME_SLACK):
            continue
        keep.append((code, msg, sub))
    return keep


def record_findings(tasks):
    """모든 task의 기록 점검 [(id, 코드, 내용, 하위 줄)]."""
    out = []
    for tid, t in tasks.items():
        for code, msg, sub in record_check(t):
            out.append((tid, code, msg, sub))
    return out


# ---------------------------------------------------------------------------
# 규칙 판 1 판정자 정의가 갖춰졌는가. 정의는 플러그인 `agents/`(`{kinds.PLUGIN_ROOT}/agents`)에 있다.
# 옛 정의로 판정자를 띄우면 판정 파일에 `판정자:` 줄이 없어 새 task의 자체 검증 뒤 전이가 모두 거부된다.
# 정의 본문의 판 표지 한 줄 `def-version: {값}`. 판정자 정의, 판정자 공통 `references/roles/judge.md`, 형식 파일
# `references/formats/judge-file.md`·`judge-run-file.md`가 판정 파일 규칙(첫 줄 판정자, judge-run.md 직접 쓰기)을 바꾸면
# 등록표 `kinds.DEF_VERSION_MIN`과 정의의 표지를 함께 올린다. 문장을 다듬는 것만으로는 바꾸지 않는다.
# 검사하는 정의와 요구 도구는 등록표 AGENTS의 `has_def_version`·`required_tools`(판정자 둘).
AGENT_DEF_RE = re.compile(r"def-version:\s*([0-9]{4}-[0-9]{2}-[0-9]{2}[\w-]*)")


def agent_def_problems(agents_dir=None):
    """플러그인 판정자 정의의 문제 목록(없으면 빈 목록): 판 표지가 없거나 kinds.DEF_VERSION_MIN보다 옛것, tools에 Write 없음."""
    base = agents_dir or os.path.join(kinds.PLUGIN_ROOT, "agents")
    out = []
    for agent, a in kinds.AGENTS.items():
        if not (a.has_def_version or a.required_tools):
            continue
        name, tools_need = agent + ".md", a.required_tools
        p = os.path.join(base, name)
        if not os.path.isfile(p):
            out.append("{} 없음".format(name))
            continue
        text = read_text(p)
        lost = []
        m = AGENT_DEF_RE.search(text)
        if a.has_def_version and not m:
            lost.append("판 표지 def-version(필요 {} 이상)".format(kinds.DEF_VERSION_MIN))
        elif a.has_def_version and m.group(1) < kinds.DEF_VERSION_MIN:
            lost.append("판 표지 def-version {}가 {}보다 옛것".format(m.group(1), kinds.DEF_VERSION_MIN))
        tools = next((l for l in text.splitlines() if l.startswith("tools:")), "")
        lost += ["tools에 " + x for x in tools_need if x not in [w.strip() for w in tools[6:].split(",")]]
        if lost:
            out.append("{}: {}".format(name, ", ".join(lost)))
    return out


# ---------------------------------------------------------------------------
# 상태 기계(규칙 판 2: 시작 조건, stage, 보류에서 나가는 길, 회차, 합치는 조건).
# 가드가 "끝"으로 세는 상태는 완료·보류·백로그와, 부모·의존하는 task를 따라 보류에 닿는 대기다(settled).
# 한 단계만 보면 같은 흐름의 자동 의존 사슬 셋째부터 끝으로 세지 못해 마무리가 영영 뜨지 않는다.

# 규칙 판(`kinds.RULES`, task_set.py가 대기→진행 때 머리 파일 `rules`에 적는다. task별 규칙 판 2 강제(stage 전이)는
# 2 이상에만 건다), 단계(`kinds.stages_of`, 묻는 단계 `kinds.ASK_STAGES`), 흐름 역할(`kinds.FLOW_ROLES`)은 등록표에 있다.


UNFINISHED_KEYS = ("insert_pending", "insert_failed", "waiting_policy", "parked")


def rules_level(t):
    """0: 옛 task(started_version 없음), 1: 규칙 판 1 규칙으로 시작, 2 이상: 그 판의 규칙으로 시작(`rules`)."""
    if not is_new_task(t):
        return 0
    try:
        return int(str(t.get("rules", "") or "1").strip())
    except ValueError:
        return 1


def stage_of(t):
    return str(t.get("stage", "") or "").strip()


def hold_blockers(tasks):
    """{대기 task id: [막는 보류 task id …]}. 부모·의존하는 task를 따라가 보류에 닿는 대기 task만 담는다."""
    memo = {}

    def visit(tid, seen):
        if tid in memo:
            return memo[tid]
        t = tasks.get(tid)
        if t is None or t.get("status") != "대기" or tid in seen:
            return []
        seen = seen | {tid}
        found = set()
        for ref in [t.get("parent", "")] + list(t.get("depends_on", [])):
            if not ref or ref not in tasks:
                continue
            st = tasks[ref].get("status")
            if st == "보류":
                found.add(ref)
            elif st == "대기":
                found.update(visit(ref, seen))
        memo[tid] = sorted(found)
        return memo[tid]

    out = {}
    for tid in tasks:
        b = visit(tid, frozenset())
        if b:
            out[tid] = b
    return out


def unfinished_mark(t):
    """넣기·정책 대기·치움 표지가 있는가. 있으면 상태가 `완료`여도 끝나지 않은 것으로 센다(설계 8.3절)."""
    return any(str(t.get(k, "") or "").strip() for k in UNFINISHED_KEYS)


def dependency_done(t):
    """의존 판정이 끝으로 보는 task: 표지가 없는 `완료`."""
    return t.get("status") == kinds.DONE and not unfinished_mark(t)


def settled(t, tasks, blockers=None):
    """가드가 끝으로 세는가: 완료·보류·백로그, 또는 보류에 막힌 대기. 흐름별 검증은 보류에 막혀도 끝으로 세지 않는다
    (같은 흐름 코드 task의 자동 의존 사슬로 막히므로, 끝으로 세면 사람에게 묻지 않고 마무리가 뜬다. 묻는 길은 board.py).
    `보류`를 먼저 본다. 치운 변경이 남아도 끝이다. 그 밖에 표지가 있으면 끝이 아니다."""
    st = t.get("status")
    if st == "보류":
        return True
    if unfinished_mark(t):
        return False
    if st in (kinds.DONE, "백로그"):
        return True
    if st == "대기" and t.get("kind") != "flow-verify":
        b = hold_blockers(tasks) if blockers is None else blockers
        return t.get("id") in b
    return False


def flow_role(name, meta=None):
    """flow.md `role`. 옛 flow.md에 없으면 이름으로 추정한다(`fixes`·`fixes-r2` → fixes, `integration`·`integration-r2`
    → integration, `deploy-1` → deploy, 나머지 feature. 이름이 `deploy`이거나 `deploy-verify`인 기능 흐름이 실제로 있다)."""
    role = str((meta or {}).get("role", "") or "").strip()
    if role in kinds.FLOW_ROLES:
        return role
    name = name or ""
    if re.fullmatch(r"fixes(-r\d+)?", name):
        return "fixes"
    if re.fullmatch(r"integration(-r\d+)?", name):
        return "integration"
    if re.fullmatch(r"deploy-\d+", name):
        return "deploy"
    return "feature"


def as_round(value):
    try:
        return int(str(value or "1").strip() or 1)
    except ValueError:
        return 1


def run_round(run_dir):
    return as_round(run_meta(run_dir).get("round", ""))


def ensure_flow_md(run_dir, flow):
    r"""흐름의 첫 코드 task 행을 만들 때 `flows\{흐름}\flow.md`(폴더 없음, role, round)를 함께 만든다.
    이미 있으면 건드리지 않는다. 만들었으면 경로를 돌려준다."""
    if not flow:
        return None
    p = os.path.join(run_dir, "flows", flow, "flow.md")
    if os.path.isfile(p):
        return None
    lines = ["---", "flow: " + flow, "role: " + flow_role(flow), "round: {}".format(run_round(run_dir)),
             "branch:", "dir:", "base_commit:", "depends_on_flows: []", "branched_from:", "sync_pending: []",
             "synced_to:", "status: 폴더 없음", "---", ""]
    write_text(p, "\n".join(lines))
    return p


def flow_name_problem(run_dir, flow):
    """새 코드 task 행의 흐름 이름이 앞 회차 흐름의 것이면 그 사유(아니면 ""). 상태와 상관없이 거부한다:
    단일 흐름 실행은 내보낸 뒤에도 `flow.md`가 `진행`으로 남고, 정리 단계가 브랜치를 지우면 git도 막지 않는다.
    이름을 다시 쓰면 회차 2의 task가 회차 1 흐름에 붙어 회차 가드에서 빠진다."""
    if not flow:
        return ""
    p = os.path.join(run_dir, "flows", flow, "flow.md")
    if not os.path.isfile(p):
        return ""
    meta = parse_meta(split_front_matter(read_text(p))[0])
    now_round = run_round(run_dir)
    if as_round(meta.get("round", "")) < now_round:
        raw = str(meta.get("round", "") or "").strip()
        return ("flows/{}/flow.md의 round({})가 run.md round({})와 다르다(상태 {}). 앞 회차의 흐름이면 이번 회차는 새 이름을 "
                "쓰고(예 {}-r{}), 이번 회차에 손으로 만든 flow.md면 그 round를 {}로 고친다").format(
            flow, raw or "없음 = 1", now_round, str(meta.get("status", "")).strip() or "-",
            re.sub(r"-r\d+$", "", flow), now_round, now_round)
    return ""


CMD_FENCE = re.compile(r"^```\s*cmd\s*$")


def cmd_lines(text):
    """글에서 ```cmd 울타리 안의 비지 않은 줄(명령 하나가 한 줄)."""
    out, inside = [], False
    for line in (text or "").splitlines():
        s = line.strip()
        if not inside and CMD_FENCE.match(s):
            inside = True
            continue
        if inside and s.startswith("```"):
            inside = False
            continue
        if inside and s:
            out.append(s)
    return out


_SHELL_WORD = r"(?:\"[^\"]+\"|'[^']+'|\S+)"
# `git [-c k=v …] -C {경로}`의 경로, 병합 줄의 앞붙이 `cd {경로} &&`(또는 `;`)의 경로
GIT_C_PATH = re.compile(r"^git(?:\s+-c\s+" + _SHELL_WORD + r")*\s+-C\s+(?P<path>" + _SHELL_WORD + ")")
CD_PREFIX = re.compile(r"^cd\s+(?P<path>" + _SHELL_WORD + r")\s*(?:&&|;)")
DQ_ESCAPES = "\"\\$`"   # bash 큰따옴표 안에서 백슬래시가 이스케이프하는 글자


def shell_dir(path, cwd):
    """명령 줄의 폴더 경로를 실행 폴더 기준으로 푼 비교용 꼴. Git Bash 꼴 `/d/…`는 `D:/…`로 읽는다.
    `$`가 든 경로(변수)는 풀 수 없어 None."""
    p = path.strip("\"'")
    if "$" in p:
        return None
    m = re.match(r"^/([A-Za-z])(/.*)?$", p)
    if m:
        p = m.group(1).upper() + ":" + (m.group(2) or "/")
    return os.path.normcase(os.path.normpath(os.path.join(cwd, p.replace("\\", "/"))))


def cmd_line_problems(line, cwd="", bash=True, check_dir=True, merge=False):
    """exec.py가 bash -c로 돌릴 줄의 꼴 문제 목록. 따옴표 밖 백슬래시는 bash가 지우고(2026-10-31 T043:
    `git -C D:\\workspace\\…`가 `D:workspace…`로 바뀌어 128), 실행 전 확인(받는 브랜치, 작업 트리)이 실행 폴더를 보는
    줄이 `git -C`로 다른 폴더를 가리키면 확인과 실행의 폴더가 갈린다.
    - bash가 없으면(cmd.exe로 돎) 백슬래시는 보지 않는다. 큰따옴표 안의 `\\"`·`\\\\`·`\\$`·``\\` ``는 이스케이프다.
    - check_dir: 폴더를 대조한다(실행 전 확인이 폴더를 보지 않는 줄은 exec.py가 끈다). cwd를 모르면 대조하지 않는다.
      경로는 cwd 기준으로 풀고 `$`가 든 경로는 대조하지 않는다. merge(병합 줄)면 앞붙이 `cd X &&`도 본다.
    - `[사용자 실행]` 줄은 exec.py가 돌리지 않고, `[유지 뒤]` 줄(운영 브랜치 옮기기, `git -C {원래 폴더}`)은 폴더를 대조하지 않는다."""
    s = line.strip()
    if s.startswith("[사용자 실행]"):
        return []
    if s.startswith("[유지 뒤]"):
        s, check_dir = s[len("[유지 뒤]"):].strip(), False
    out, quote, i = [], "", 0
    while bash and i < len(s):
        ch = s[i]
        if quote == '"' and ch == "\\" and i + 1 < len(s) and s[i + 1] in DQ_ESCAPES:
            i += 2
            continue
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "\\":
            out.append("따옴표 밖 백슬래시(bash가 지운다): 경로는 `/`로 쓴다")
            break
        i += 1
    if not (check_dir and cwd):
        return out
    here = shell_dir(cwd, "")
    m = CD_PREFIX.match(s) if merge else None
    if m:
        where = shell_dir(m.group("path"), cwd)
        if where is not None and where != here:
            out.append("병합 줄의 `cd {}`가 실행 폴더 {}와 다름: 병합 줄은 실행 폴더에서 돈다".format(m.group("path"), cwd))
        s = s[m.end():].strip()
    m = GIT_C_PATH.match(s)
    if m:
        where = shell_dir(m.group("path"), cwd)
        if where is not None and where != here:
            out.append("`git -C {}`가 실행 폴더 {}와 다름: 실행 전 확인이 실행 폴더를 본다".format(m.group("path").strip("\"'"), cwd))
    return out


def decide_cell(task_dir):
    """result.md 「승인 화면 > 정해 주실 것」 글(없으면 "")."""
    p = os.path.join(task_dir, "result.md")
    if not os.path.isfile(p):
        return ""
    return sections(sections(read_text(p), level=2).get("승인 화면", ""), level=3).get("정해 주실 것", "")


# 판정불가 꼬리표(SKILL.md 2절 표). 판정자가 「통과 못 한 기준」 항목의 이유 앞에 붙인다
# 꼬리표는 항목 맨 앞의 고정 표지로만 인식한다: `- 기준 {n}: 판정불가 {환경|지시|대상}: {이유}`(formats.md 5절).
# 글 가운데 우연히 든 "대상:"이나 실패와 섞인 항목은 꼬리표 없음(승인으로)으로 본다.
ITEM_TAG_RE = re.compile(r"^-\s*(?:기준|변이)\s*\d+\s*:\s*판정불가\s+(" + "|".join(kinds.UNDECIDED_TAGS) + r")\s*:")
ITEM_KEY_RE = re.compile(r"(?:기준|변이)\s*\d+")
BASELINE_FAIL_RE = re.compile(r"원래(?:부터)?\s*실패\w*")   # 기준선 없음 이유의 "원래부터 실패"만 실패 판정이 아니다


def mixed_fail(rest):
    """표지 뒤 글에 실패가 섞였나(번호가 없어도). 기준선 없음 이유의 "원래부터 실패"는 빼고 본다."""
    return "실패" in BASELINE_FAIL_RE.sub("", rest or "")
BASELINE_RE = re.compile(r"^-\s*(?:기준|변이)\s*\d+\s*:\s*판정불가\s+대상\s*:\s*기준선 없음\s+`?([^`|()\n]+?)`?\s*(?:$|[|(,.;])")


def undecided_tag(text):
    """「통과 못 한 기준」 항목 하나(첫 줄과 들여쓴 줄)의 판정불가 꼬리표('환경'·'지시'·'대상'). 첫 줄이 고정 표지로
    시작하지 않거나, 다른 기준·변이 번호나 실패 판정이 함께 들어 있으면 None(꼬리표 없음 = 알림을 막는다)."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return None
    m = ITEM_TAG_RE.match(lines[0])
    if not m:
        return None
    rest = " ".join(lines)[m.end():]
    if ITEM_KEY_RE.search(rest) or mixed_fail(rest):
        return None
    return m.group(1)


def table_tag(line):
    """판정 표 한 줄의 판정불가 꼬리표: 판정 칸이 정확히 `판정불가`이고 근거 칸이 `{꼬리표}:`로 시작할 때만."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 3 or cells[1] != "판정불가":
        return None
    m = re.match(r"^(환경|지시|대상)\s*:", cells[-1])
    if not m or mixed_fail(cells[-1][m.end():]) or ITEM_KEY_RE.search(cells[-1][m.end():]):
        return None
    return m.group(1)


# ---------------------------------------------------------------------------
# 자식 만들기(수정 세대, 코드를 고치는 변경은 fix)

# 정본으로 세는 「건드릴 파일」 경로: spec\·ui\·design\, 변경 task 폴더의 고친 판(revised\spec·ui·design)과 자기 result.md
_CANON = "|".join(kinds.CANON_DIRS)
CANON_RE = re.compile(r"^(?:" + _CANON + r")/[^/]|^tasks/T\d+/(?:revised/(?:" + _CANON + r")/[^/]|result\.md$)")


PATH_TOKEN = re.compile(r"(?:[A-Za-z]:)?[\w.*{}\-]*[/\\][\w./\\*{}\-]*|[\w*{}\-]+\.[A-Za-z0-9*]{1,8}|\.[A-Za-z][\w.\-]*")
NOTE_TAIL = re.compile(r"\s+[—–]\s.*$")          # `- 경로 — 설명`의 설명
PAREN = re.compile(r"[（(][^)）]*[)）]")            # 괄호 설명


def _touch_line(line):
    """「건드릴 파일」 한 줄에서 설명(괄호, ` — ` 뒤)과 백틱을 뗀 글."""
    return NOTE_TAIL.sub("", PAREN.sub(" ", line.replace("`", " ")))


def touch_paths(text):
    """「건드릴 파일」 절의 경로 목록. 줄마다(목록 기호·표 칸과 상관없이) 경로 꼴 토큰을 모두 뽑는다(드라이브 문자 포함)
    (한 줄에 쉼표로 적은 코드 경로가 정본으로 지나가지 않게). 설명(괄호, ` — ` 뒤)은 뗀다."""
    out = []
    for line in (text or "").splitlines():
        for tok in PATH_TOKEN.findall(_touch_line(line).replace("|", " ")):
            tok = re.sub(r":\d+(?:-\d+)?$", "", tok.lstrip(",;").rstrip(".,;"))
            if tok and tok not in out:
                out.append(tok)
    return out


def touch_format_problems(text):
    """`- 경로` 한 줄에 한 경로가 아닌 내용 줄(정본만 고치는 change·--from-answer는 이 꼴만 받는다).
    빈 표시(`(없음)`, `- 없음 …`, `(없음 — 설명)`)와 설명(괄호, ` — ` 뒤)은 문제로 보지 않는다."""
    bad = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or EMPTY_ITEM.match(s) or re.match(r"^[（(]\s*없음", s):
            continue
        rest = _touch_line(s[2:]) if s.startswith("- ") else ""
        if not s.startswith("- ") or len(PATH_TOKEN.findall(rest)) != 1:
            bad.append(s)
    return bad


def canon_relative(path, run_dir=None):
    """실행 폴더의 절대 경로와 작업 공간 기준 경로(`_workspace/{실행}/…`, `{실행}/…`)를 실행 폴더 기준으로 바꾼다. `..`는 푼다."""
    q = path.replace("\\", "/")
    if run_dir:
        base = os.path.abspath(run_dir).replace("\\", "/").rstrip("/").lower() + "/"
        name = os.path.basename(os.path.abspath(run_dir)).lower()
        if q.lower().startswith(base):
            q = q[len(base):]
        else:
            m = re.search(r"(?:^|/)(?:_workspace/)?" + re.escape(name) + "/", q, re.I)
            if m and (m.start() == 0 or "_workspace/" in q[:m.end()].lower()):
                q = q[m.end():]
    return posixpath.normpath(re.sub(r"^\./", "", q))


def outside_canon(paths, run_dir=None):
    """정본 밖 경로(코드·문서 등). 경로 꼴은 `canon_relative`가 맞춘다(한 change 행이 `_workspace/{실행}/design/…`)."""
    bad = []
    for p in paths:
        q = canon_relative(p, run_dir)
        if q.startswith("..") or not CANON_RE.match(q):
            bad.append(p)
    return bad


def is_code_change(t):
    """옛 실행의 코드를 고치는 `change`(「건드릴 파일」에 정본 밖 경로). 새로 만드는 것은 거부되고 `fix`가 된다.
    가드는 이것도 코드 폴더에 쓰는 task로 센다."""
    if t.get("kind") != "change":
        return False
    run_dir = os.path.dirname(os.path.dirname(t["_dir"])) if t.get("_dir") else None   # tasks\T…의 두 단계 위
    return bool(outside_canon(touch_paths(t["_sections"].get("건드릴 파일", "")), run_dir))


# ---------------------------------------------------------------------------
# 영역 규칙(프로젝트 경로 목록, 인수 기준의 화면 id, 영역 판정 기준)

PROJECT_SETTINGS = "devflow-harness.project.md"
PATH_LISTS = (("화면", "화면 경로"), ("인프라", "인프라 경로"), ("문서", "문서 경로"))


def project_paths(run_dir):
    """프로젝트 설정(실행 폴더의 부모 폴더의 devflow-harness.project.md) 「경로 목록」 절.
    {"실행": 감지한 실행, "화면": [패턴], "인프라": [..], "문서": [..]}. 파일·절·줄이 없거나 `없음`이면 빈 값."""
    out = {"실행": ""}
    out.update({key: [] for key, _ in PATH_LISTS})
    path = os.path.join(os.path.dirname(os.path.abspath(run_dir)), PROJECT_SETTINGS)
    if not os.path.isfile(path):
        return out
    labels = {label: key for key, label in PATH_LISTS}
    for line in sections(read_text(path)).get("경로 목록", "").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        label, raw = (s.strip() for s in line[2:].split(":", 1))
        raw = raw.replace("`", "")
        if label == "감지한 실행":
            out["실행"] = raw
        elif label in labels and not EMPTY_ITEM.match("- " + raw):
            out[labels[label]] = [p.strip() for p in raw.split(",") if p.strip()]
    return out


def production_marks(run_dir):
    """(운영 표지 패턴 목록, 운영 브랜치). 표지는 프로젝트 설정 「경로 목록」 절의 `- 운영 표지: …` 줄이다."""
    path = os.path.join(os.path.dirname(os.path.abspath(run_dir)), PROJECT_SETTINGS)
    text = read_text(path) if os.path.isfile(path) else ""
    marks, branch = [], ""
    for line in sections(text).get("경로 목록", "").splitlines():
        if line.startswith("- ") and ":" in line and line[2:].split(":", 1)[0].strip() == "운영 표지":
            raw = line.split(":", 1)[1].replace("`", "").strip()
            if not EMPTY_ITEM.match("- " + raw):
                marks = [p.strip() for p in raw.split(",") if p.strip()]
    for line in text.splitlines():
        if line.startswith("- ") and ":" in line and line[2:].split(":", 1)[0].strip() == "운영 브랜치":
            branch = line.split(":", 1)[1].replace("`", "").strip()
    return marks, branch


def path_in_list(path, patterns):
    """경로가 패턴 목록의 하나에 드는가. 패턴은 저장소 기준 `/` 경로로 `**`(여러 단계)·`*`(한 단계 안)만 쓰고 전체가 맞아야 한다.
    경로의 와일드카드는 글자 그대로 대조한다(`db/migrations/*.sql`은 `db/migrations/**`에 든다)."""
    p = re.sub(r"^(?:\./)+", "", str(path).replace("\\", "/"))
    for pat in patterns:
        pat = re.sub(r"^(?:\./)+", "", str(pat).replace("\\", "/"))
        regex = "".join(".*" if tok == "**" else "[^/]*" if tok == "*" else re.escape(tok)
                        for tok in re.split(r"(\*\*|\*)", pat) if tok)
        if re.fullmatch(regex, p):
            return True
    return False


# 시험 변화(설계 6.12절 「시험」). 기계 줄은 `machine_check.py`가 task 폴더에 쓰고 꼴은 `practices/test-rules.md`다

TEST_CHANGES = "test-changes.md"
TEST_BASE_HEAD = "기준: "   # 파일 첫 줄. 다음 측정이 같은 커밋에서 잰다
TEST_REMOVALS = ("끄기", "삭제")   # 위임 중에도 합치기 전에 기다리는 변화(설계 9절)
TEST_UNMEASURED = "재지 못함"   # 줄을 남기지 못한 task. 끄기가 있는지 모르므로 코드 확인의 재지 못함 답(확인 없이 합쳐도 된다)이 있어야 닫는다
MEASURED_STATUSES = ("자체검증", "승인대기", kinds.DONE)
TEST_EXPECT_ONLY = "기대값만 바꿈"
TEST_PROXY = "대리 확인"
TEST_BASELINE = "기준선 추가"
TEST_COUNT_ONLY = "기대값 변경"   # 건수와 펼침만. 묻지 않는다
TEST_PULLED = "받아온 변경"   # 받아오기 병합에서 들어온 쪽 그대로인 파일의 건수, 또는 가려내지 못했다는 한 줄. 묻지 않는다
TEST_CHANGE_NAMES = TEST_REMOVALS + (TEST_UNMEASURED,
    "범위 축소", "시험을 돌리는 곳", "재시도", "제한 시간과 허용 범위", "단언 약화", "정답 파일", "실패 거름", "시험 도우미",
    TEST_PROXY, TEST_BASELINE, TEST_EXPECT_ONLY, "리터럴이 제품 값으로", TEST_COUNT_ONLY, TEST_PULLED)
TEST_SETTING_LABELS = {"run": "시험을 돌리는 곳", "golden": "정답 경로", "helper": "시험 도우미 경로"}
BASELINE_SEEN = "baseline-seen.md"
TEST_ANSWER = re.compile(r"([\w,]+)=(받아들임|되살림)")
ANSWER_ORIGIN = re.compile(r"^사용자\s+(T\d+)\s+(\d{4}-\d\d-\d\d \d\d:\d\d(?::\d\d)?)")


def test_change_settings(run_dir):
    """프로젝트 설정 「시험 변화 경로」 절의 패턴 목록. 파일·절·줄이 없거나 `없음`이면 빈 목록."""
    out = {key: [] for key in TEST_SETTING_LABELS}
    path = os.path.join(os.path.dirname(os.path.abspath(run_dir)), PROJECT_SETTINGS)
    if not os.path.isfile(path):
        return out
    labels = {label: key for key, label in TEST_SETTING_LABELS.items()}
    for line in sections(read_text(path)).get("시험 변화 경로", "").splitlines():
        label, _, raw = line[2:].partition(":") if line.startswith("- ") else ("", "", "")
        raw = raw.replace("`", "").strip()
        if label.strip() in labels and not EMPTY_ITEM.match("- " + raw):
            out[labels[label.strip()]] = [p.strip() for p in raw.split(",") if p.strip()]
    return out


def baseline_items(run_dir):
    """recon.md 「기준선」의 `- ` 줄."""
    path = os.path.join(run_dir, "recon.md")
    text = sections(read_text(path), level=2).get("기준선", "") if os.path.isfile(path) else ""
    return [line.strip() for line in text.splitlines() if line.startswith("- ")]


def note_baseline(run_dir):
    """실행의 첫 기계 조건 검사 때 기준선을 떠 둔다. 정찰 문서는 git 밖이라 뒤에 늘어난 줄을 이것과 견준다."""
    path = os.path.join(run_dir, BASELINE_SEEN)
    if not os.path.isfile(path):
        write_text(path, "\n".join(baseline_items(run_dir)) + "\n")


def baseline_additions(run_dir):
    """첫 검사 뒤에 recon.md 「기준선」에 늘어난 줄."""
    path = os.path.join(run_dir, BASELINE_SEEN)
    if not os.path.isfile(path):
        return []
    seen = set(read_text(path).splitlines())
    return [line for line in baseline_items(run_dir) if line not in seen]


def test_change_base(t):
    """앞 측정이 적어 둔 기준 커밋(없으면 "")."""
    path = os.path.join(t["_dir"], TEST_CHANGES)
    for line in read_text(path).splitlines() if os.path.isfile(path) else []:
        if line.startswith(TEST_BASE_HEAD):
            return line[len(TEST_BASE_HEAD):].strip()
    return ""


def clear_test_changes(t):
    """다시 재기 전에 앞 회차의 줄을 지운다. 재지 못하면 앞 줄이 남아 잰 것으로 보이지 않게 한다. 기준 줄은 남긴다."""
    path = os.path.join(t["_dir"], TEST_CHANGES)
    base = test_change_base(t)
    if base:
        write_text(path, TEST_BASE_HEAD + base + "\n")
    elif os.path.isfile(path):
        os.remove(path)


def test_changes_measured(t):
    """이번 회차의 줄이 있는가(변화가 없어도 `- 없음`을 쓴다)."""
    path = os.path.join(t["_dir"], TEST_CHANGES)
    return os.path.isfile(path) and any(line.startswith("- ") for line in read_text(path).splitlines())


def _test_row(tid, change, place, basis, why="적지 않음", guard="없음", key_text=""):
    # 키에 줄 번호를 넣지 않는다. 재시도로 줄이 밀려도 앞서 받은 답이 그 변화를 가리킨다
    name = re.sub(r":\d+(?:-\d+)?$", "", place)
    key = "s" + hashlib.sha1("{}|{}|{}{}".format(tid, change, name, key_text).encode("utf-8")).hexdigest()[:6]
    return {"task": tid, "change": change, "place": place, "file": name, "basis": basis, "why": why, "guard": guard,
            "key": key, "ask": change not in (TEST_COUNT_ONLY, TEST_PULLED), "answer": "", "quote": ""}


def test_change_answers(tasks):
    """승인 기록 `- {시각} | 시험 변화 | {키},{키}=받아들임 {키}=되살림 | 원문: "…"`을 {키: (답, 원문)}으로. 뒤 줄이 이긴다."""
    out = {}
    for t in tasks.values():
        for line in record_lines(t):
            f = record_fields(line)
            if len(f) >= 3 and f[1] == TEST_CHANGE_POINT and (record_quote(line) or "").strip():
                for keys, value in TEST_ANSWER.findall(f[2]):
                    out.update({key: (value, record_quote(line) or "") for key in keys.split(",") if key})
    return out


def person_quote(text):
    """사람이 그 일을 두고 한 말인가. 빈 답과 위임의 말은 코드를 보지 않고 합치는 답으로 세지 않는다."""
    text = (text or "").strip()
    return bool(text) and not DELEGATED_ANSWER.search(text) and "위임" not in text


def commit_mark(t):
    """답과 다시 재기를 묶는 그 task의 지금 커밋 값."""
    return str(t.get("commit", "") or "").strip() or UNMEASURED_NO_COMMIT


def unmeasured_answers(tasks):
    """승인 기록의 `코드 확인 재지 못함 {T}@{커밋}|합쳐도 됨|{원문}`을 {T: 원문}으로. 답은 받을 때의 코드에 대한 것이라 커밋이 지금과 같을 때만 센다.
    `@{커밋}`이 없는 옛 꼴은 어느 코드의 답인지 모르므로 세지 않는다."""
    out = {}
    for t in tasks.values():
        for line in record_lines(t):
            f = record_fields(line)
            if len(f) >= 3 and f[1].startswith(UNMEASURED_POINT) and f[2] == UNMEASURED_ANSWER and person_quote(record_quote(line)):
                task, at, mark = f[1][len(UNMEASURED_POINT):].strip().partition("@")
                if at and task in tasks and commit_mark(tasks[task]) == mark.strip():
                    out[task] = record_quote(line)
    return out


def prior_answer(t, tasks):
    """그 task를 계기로 한 사람의 답 원문: 자기 승인 기록, 없으면 `origin`이 가리킨 답. 없으면 None."""
    for line in record_lines(t):
        f = record_fields(line)
        if len(f) >= 2 and f[1] not in ("알림", "점검 확인") and not f[1].startswith(("되물음",) + PARTIAL_POINTS) and record_quote(line):
            return record_quote(line)
    if not user_origin(t):
        return None
    origin = str(t.get("origin", ""))
    m = ANSWER_ORIGIN.match(origin.strip())
    source = tasks.get(m.group(1)) if m else None
    for line in record_lines(source) if source else []:
        if line.startswith("- " + m.group(2)) and record_quote(line):
            return record_quote(line)
    return origin


def _section_lines(path, name):
    text = sections(read_text(path), level=2).get(name, "") if os.path.isfile(path) else ""
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_change_rows(t, tasks=None):
    """코드 task 하나의 시험 변화 줄(1.2.0부터 시작한 task). 기계 줄에 결과 파일 「시험 변화」의 이유와 대신 지키는 것을 붙이고,
    기계가 못 본 작성자 줄과 판정자의 `대리 확인:`을 더하고, 받은 답을 붙인다."""
    if not needs_judgment_record(t):
        return []
    tasks = load_tasks(run_dir_of(t)) if tasks is None else tasks
    rows = []
    machine = os.path.join(t["_dir"], TEST_CHANGES)
    # 커밋이 있는 보류·백로그는 코드가 흐름 브랜치에 남으므로 내려도 재지 못함이 사라지지 않는다
    measured_at = t.get("status") in MEASURED_STATUSES or (t.get("status") in HELD_STATUSES and str(t.get("commit", "") or "").strip())
    if not test_changes_measured(t) and not no_code(t) and measured_at:
        rows.append(_test_row(t["id"], TEST_UNMEASURED, t["id"], "machine_check가 줄을 남기지 못함"))
    for line in read_text(machine).splitlines() if os.path.isfile(machine) else []:
        cells = [c.strip() for c in line[2:].split(" | ", 2)] if line.startswith("- ") else []
        if len(cells) == 3:
            rows.append(_test_row(t["id"], *cells))
    for line in _section_lines(os.path.join(t["_dir"], "result.md"), "시험 변화"):
        cells = [c.strip() for c in line[2:].split(" | ")] if line.startswith("- ") else []
        if len(cells) < 2:
            continue
        why = cells[2] if len(cells) > 2 and cells[2] else "적지 않음"
        guard = cells[3] if len(cells) > 3 and cells[3] else "없음"
        name = re.sub(r":\d+(?:-\d+)?$", "", cells[1])
        found = [r for r in rows if r["change"] == cells[0] and r["file"] == name]
        if not found:
            rows.append(_test_row(t["id"], cells[0], cells[1], "작성자", why, guard))
        for row in found:
            row.update(why=why, guard=guard)
    for line in _section_lines(os.path.join(t["_dir"], "judge.md"), "판단 대조"):
        m = re.match(r"^(?:- )?" + TEST_PROXY + r":\s*(.*)$", line)
        cells = [c.strip() for c in m.group(1).split(" | ")] if m else []
        if len(cells) == 3:
            rows.append(_test_row(t["id"], TEST_PROXY, cells[0], "본 것: {} / 못 본 것: {}".format(cells[1], cells[2])))
    return _with_answers(rows, t, tasks)


def _with_answers(rows, t, tasks):
    answers = test_change_answers(tasks)
    merged = unmeasured_answers(tasks)
    for row in rows:
        if row["change"] == TEST_UNMEASURED:   # 코드 확인의 답으로만 푼다. 먼저 다시 재는 차례를 건너뛰지 않고, 답이 커밋에 묶인다
            if row["task"] in merged:
                row["answer"], row["quote"] = "받아들임", merged[row["task"]]
        elif row["key"] in answers:
            row["answer"], row["quote"] = answers[row["key"]]
        elif row["change"] == TEST_EXPECT_ONLY and t is not None:
            quote = prior_answer(t, tasks)
            if quote is not None:
                row["answer"], row["quote"] = "앞선 답", quote
    return rows


def _baseline_rows(run_dir, tasks):
    # 기준선은 실패를 빼는 곳이다. 뒤에 넣은 줄이 앞선 답을 물려받지 않게 키에 그 줄을 넣는다
    return _with_answers([_test_row("실행", TEST_BASELINE, "recon.md 「기준선」", line, key_text=line) for line in baseline_additions(run_dir)], None, tasks)


HELD_STATUSES = ("보류", "백로그")


def not_in_flow(t):
    """이 흐름에 합쳐지지 않는 코드 task: 커밋 없는 보류·백로그. 커밋이 있으면 코드가 흐름 브랜치에 남으므로 보류로 합치기 전 가드를 피하지 못한다."""
    return t.get("status") in HELD_STATUSES and not str(t.get("commit", "") or "").strip()


def held_test_rows(t, tasks):
    """흐름 리뷰가 묻지 않는, 합쳐지지 않는 코드 task의 시험 변화 줄. 줄은 `wrap_up_test_lines`로 마무리 리뷰에 남는다."""
    return [row for other in tasks.values() if other.get("kind") in kinds.AUTO_DEPEND_KINDS and other.get("flow") == t.get("flow")
            and not_in_flow(other) for row in test_change_rows(other, tasks) if row["ask"] and not row["answer"]]


def flow_test_rows(t, tasks=None):
    """흐름별 검증이면 그 흐름의 코드 task와 실행의 기준선 추가 줄, 코드 task면 그 task의 줄.
    커밋 없는 보류·백로그 코드 task의 줄은 합치지 않는 코드라 묻지 않고, 흐름 검증의 완료도 막지 않는다(남은 것만 검증하는 `partial_flow`가 멈추지 않게)."""
    tasks = load_tasks(run_dir_of(t)) if tasks is None else tasks
    if t.get("kind") in kinds.AUTO_DEPEND_KINDS:
        return test_change_rows(t, tasks)
    if t.get("kind") != "flow-verify" or not version_at_least(t.get("started_version"), RULES_V120):
        return []
    rows = []
    for other in tasks.values():
        if other.get("kind") in kinds.AUTO_DEPEND_KINDS and other.get("flow") == t.get("flow") and not not_in_flow(other):
            rows += test_change_rows(other, tasks)
    return rows + _baseline_rows(run_dir_of(t), tasks)


def test_change_line(row):
    return "{change} | {place} | {basis} | 이유: {why} | 대신 지키는 것: {guard} | {task}".format(**row)


def test_unmeasured_open(row):
    """재지 못함 줄이 아직 답을 기다리는가. `되살림`은 다시 재라는 뜻이고, 빈 답과 위임의 말은 풀지 않는다."""
    return row["change"] == TEST_UNMEASURED and not (row["answer"] == "받아들임" and person_quote(row["quote"]))


def unanswered_test_removals(t):
    """답 없는 시험 끄기·삭제와 재지 못한 task의 줄(앞에 `[키]`). 흐름별 검증을 합치기 전까지 막는 가드가 부른다(설계 9절, 11.1절)."""
    return ["[{}] {}".format(row["key"], test_change_line(row)) for row in flow_test_rows(t)
            if (row["change"] in TEST_REMOVALS and not row["answer"]) or test_unmeasured_open(row)]


def restored_done(key, tasks):
    """`되살림`의 뒤 task(`origin`에 그 키를 적은 task)가 끝났는가."""
    return any(key in str(t.get("origin", "")) and t.get("status") == kinds.DONE for t in tasks.values())


def wrap_up_test_lines(tasks, only=None):
    """마무리 리뷰에 올릴 줄(설계 6.12절): 답 없이 남은 변화(위임으로 지나감, 흐름 뒤 수정), 대신 지키는 것 없이 받아들인 변화,
    재지 못한 채 합친 task, 아직 되살리지 않은 `되살림`. only는 회차의 task id 집합이다."""
    rows = []
    for t in tasks.values():
        if only is None or t.get("id") in only:
            rows += test_change_rows(t, tasks)
    new_task = next((t for t in tasks.values() if needs_judgment_record(t)), None)
    if new_task is not None:
        rows += _baseline_rows(run_dir_of(new_task), tasks)
    return [test_change_line(row) for row in rows
            if row["ask"] and (not row["answer"] or (row["answer"] == "받아들임" and row["guard"] == "없음")
                               or (row["answer"] == "되살림" and not restored_done(row["key"], tasks)))]


DEFAULT_CONFIG_PATTERNS = [
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "requirements*.txt", "pyproject.toml",
    "build.gradle*", "settings.gradle*", "pom.xml", "go.mod", "go.sum", "tsconfig*.json", "*.config.*",
    "wrangler.*", ".env*", "*.sql", "**/migrations/**", "**/migration/**", "Dockerfile*", ".github/**",
]
# 설정·마이그레이션 가운데 인프라인 것. 인프라 경로가 `없음`인 빈 저장소에서 마이그레이션이 알림으로 지나가지 않게 한다(설계 5.2절)
def pattern_match(path, patterns):
    """`machine_check.py`의 패턴 대조: `*`가 `/`를 넘는다. 경로 목록의 `path_in_list`와 뜻이 다르다."""
    for p in patterns:
        if fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path, p.rstrip("/") + "/*") or path == p:
            return True
        if "**" in p and fnmatch.fnmatch(path, p.replace("**/", "*")):
            return True
    return False


DEFAULT_INFRA_PATTERNS = ["wrangler.*", ".env*", "*.sql", "**/migrations/**", "**/migration/**", "Dockerfile*", ".github/**"]
# 사람 답 없이 끝내는 충돌의 파일(설계 5.3절 6): 코드나 명령이 들지 않은 형식과 목록. 사용자 결정으로 `package.json`은 남긴다. `*.config.*`, 빌드 스크립트, `pyproject.toml`은 뺀다
SETTING_PATTERNS = ["tsconfig*.json", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "requirements*.txt", "go.mod", "go.sum",
                    "poetry.lock", "Cargo.lock", ".gitignore", ".gitattributes", ".editorconfig"]


def infra_paths_in(run_dir, paths):
    """파일 목록 가운데 인프라에 드는 것. 프로젝트 설정 경로 목록이 있으면 그것으로, 없으면 기본 패턴으로 본다(`touched_in_paths`와 같다)."""
    patterns = project_paths(run_dir)["인프라"]
    if patterns:
        return [p for p in paths if path_in_list(p, patterns)]
    return [p for p in paths if pattern_match(p, DEFAULT_INFRA_PATTERNS) or pattern_match(p.rsplit("/", 1)[-1], DEFAULT_INFRA_PATTERNS)]


def settings_only(run_dir, paths):
    """동작을 바꾸지 않는 충돌의 파일 조건(설계 5.3절 6): 모두 설정·형식 파일이고 프로젝트의 인프라 경로에 들지 않는다. 비면 재지 못한 것이라 거짓이다."""
    def setting(p):
        base = p.rsplit("/", 1)[-1]
        return pattern_match(base, SETTING_PATTERNS) and not infra_paths_in(run_dir, [p]) and not pattern_match(base, DEFAULT_INFRA_PATTERNS)
    return bool(paths) and all(setting(p) for p in paths)


def touched_in_paths(t, key, fallback=()):
    """머리 파일 「건드릴 파일」 경로 가운데 프로젝트 설정 경로 목록 `key`(화면·인프라·문서)에 드는 것.
    실행 폴더는 `t["_dir"]`의 두 단계 위다. 경로 목록이 없으면 fallback으로 본다."""
    if not t.get("_dir"):
        return []
    patterns = project_paths(os.path.dirname(os.path.dirname(t["_dir"])))[key]
    if not patterns:
        paths = [p.replace("\\", "/") for p in touch_paths(t.get("_sections", {}).get("건드릴 파일", ""))]
        return [p for p in paths if pattern_match(p, fallback) or pattern_match(p.rsplit("/", 1)[-1], fallback)]
    return [p for p in touch_paths(t.get("_sections", {}).get("건드릴 파일", "")) if path_in_list(p, patterns)]


SPEC_SKIP = ("overview.md", "brief.md")
AC_HEAD_RE = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)?[*_`\[]*(AC-\d+(?:-\d+)*)(?![\d-])")
AC_ANY_RE = re.compile(r"AC-\d+(?:-\d+)*(?![\d-])")
SCREEN_TAG_RE = re.compile(r"\[화면:\s*([^\]]*)\]")


def ac_spec_entries(run_dir):
    """상세 정본 spec\\*.md(overview.md·brief.md 제외)에서 인수 기준 번호가 처음 나오는 줄머리(제목·목록 줄)의 `[화면: …]`.
    ({번호: (묶음, 화면 id 집합)}, [중복 경고 줄]). 같은 번호가 두 파일에 있으면 그 번호는 빼고 경고만 낸다."""
    spec = os.path.join(run_dir, "spec")
    found = {}
    if os.path.isdir(spec):
        for name in sorted(os.listdir(spec)):
            if not name.endswith(".md") or name in SPEC_SKIP:
                continue
            seen = set()
            for line in read_text(os.path.join(spec, name)).splitlines():
                m = AC_HEAD_RE.match(line)
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                screens = {s.strip() for tag in SCREEN_TAG_RE.findall(line) for s in tag.split(",") if s.strip()}
                found.setdefault(m.group(1), []).append((name[:-3], screens))
    entries, warnings = {}, []
    for number, rows in found.items():
        if len(rows) > 1:
            warnings.append("! 인수 기준 중복: {} ({})".format(number, ", ".join(b + ".md" for b, _ in rows)))
        else:
            entries[number] = rows[0]
    return entries, warnings


def ac_screen_map(run_dir):
    """({인수 기준 번호: 화면 id 집합}, [중복 경고 줄]). 화면 id가 없는 번호는 빈 집합이다."""
    entries, warnings = ac_spec_entries(run_dir)
    return {number: screens for number, (_, screens) in entries.items()}, warnings


# 영역 판정 기준 문장(spawn_children.py가 행의 「판정 기준」 끝에 넣는다, 설계 A-16). 중괄호는 행마다 채운다
DOMAIN_CRITERIA = {
    "화면": "(영역 판정) 화면 정본 ui\\{묶음}.md(없으면 설계 「화면」 절)의 화면 {화면 id} 요소 id가 코드에 시험 표식"
          "(웹 data-testid, 안드로이드 testTag)으로 있고, 인수 기준 {번호}의 화면 시험이 그 표식으로 단언한다.",
    "계약": "(영역 판정) 설계 「공용 형식」의 [계약] 항목과 코드의 경로·필드·오류 코드가 같고, 계약 시험이 그 항목을 단언한다.",
    "화면 경로": "(영역 판정) 화면 경로({경로})를 건드린 변경이 화면 동작을 바꾸는지 판정자가 확인했고, 바꾸면 결과 「알릴 것」에 있다.",
}
DOMAIN_CRITERIA_HEAD = "(스크립트 주입: 영역 판정)"


def no_change(t):
    """코드를 바꾸지 않은 코드 task인가(`no_change: true`, 메인이 적는다). 커밋이 없어도 R4·커밋 대기에 걸지 않는다."""
    # 넣기 충돌을 수정 task가 맡아 넣었으면(`commit_via`, 설계 8.3절) 이 task의 코드는 그 수정 task의 커밋에 있다
    return str(t.get("no_change", "") or "").strip().lower() in ("true", "예") or bool(str(t.get("commit_via", "") or "").strip())


def no_code(t):
    """재 볼 코드가 없는가: `no_change` 표시가 있고 커밋이 없다. 커밋이 있으면 코드가 있으므로 표시를 보지 않는다."""
    return no_change(t) and not str(t.get("commit", "") or "").strip()


WRAP_REVIEW = "wrap-review.md"   # 마무리 리뷰 파일(`visual.py --wrap-review`, 설계 7.3절)
PROBE_NOTHING = "없음"
HANDED_ORIGIN = "하실 일 넘김"   # 넘긴 「하실 일」의 탐침 origin(설계 5.3절 1)
HANDED_REMAINS = "자원"
HANDED_MARK = re.compile(r"\[하실 일 넘김 (T\d+)\]")
SUPERSEDED_MARK = "→ 대체:"
REMAINS_LINE = re.compile(r"^[\s\-*`]*남는 것[`*\s]*[:：][ \t`*]*([^\s`*|,.()]*)", re.M)


def handed_without_probe(run_dir, tasks):
    """답 표지 `[하실 일 넘김 T0xx]`가 있는데 그 origin의 탐침 task가 없는 T0xx 목록(설계 5.3절 1). 마무리 시작 조건이 대조한다. 원문 따옴표 안과 대체된 줄은 표지가 아니다.
    decisions.md를 못 읽어도 시작을 막지 않는다(마무리 리뷰가 재지 못함으로 말한다)."""
    path = os.path.join(run_dir, "decisions.md")
    try:
        lines = read_text(path).splitlines() if os.path.isfile(path) else []
    except (OSError, UnicodeError):
        lines = []
    lines += [line for t in tasks.values() for line in record_lines(t)]
    marked = []
    for line in lines:
        head = line.split('"')[0]
        if SUPERSEDED_MARK in head:
            continue
        marked += [m for m in HANDED_MARK.findall(head) if m not in marked]
    made = [str(t.get("origin", "") or "") for t in tasks.values() if t.get("kind") == "probe"]
    return [m for m in marked if not any(re.match(re.escape(HANDED_ORIGIN) + r"\s+" + m + r"(?!\d)", o.strip()) for o in made)]


def probe_remains(t):
    """탐침이 끝난 뒤 남기는 것(`남는 것:` 줄, 설계 5.3절). 「범위」에 적고 비면 `없음`이다. 넘긴 일은 적지 않아도 `자원`으로 보고,
    여러 줄이면 `없음`이 아닌 값이 이긴다. 모르는 값은 그대로 돌려주어 묻는 쪽으로 간다."""
    found = [v for v in REMAINS_LINE.findall(t.get("_sections", {}).get("범위", "")) if v]
    others = [v for v in found if v != PROBE_NOTHING]
    if others:
        return others[0]
    if str(t.get("origin", "") or "").strip().startswith(HANDED_ORIGIN):
        return HANDED_REMAINS
    return PROBE_NOTHING


def user_origin(t):
    """사용자 원문을 계기로 만든 task인가(`origin`이 `사용자`로 시작, `task_set.py new --from-answer`가 채움)."""
    return str(t.get("origin", "") or "").strip().startswith("사용자")


PROPERTY_MARK = re.compile(r"\[성질\s*[:：]\s*([^\]]*)\]")
DERIVED_CELLS = ("정해 주실 것", "알릴 것", "확인 안 된 것")   # 성질이 붙는 칸(설계 5.2절)
ADDABLE_PROPERTIES = ("범위", "밖", "비용", "위험")   # 판정자가 `성질 더함:`으로 더하는 값
MOVED_CELLS = ("알릴 것", "확인 안 된 것")   # 옮겨 오는 줄의 칸(설계 5.3절 7). 결정과 「하실 일」은 옮겨 와도 사람에게 간다
ANSWER_CRITERION = "「답하신 것의 반영」이 이 원문의 요구를 빠짐없이, 넘치지 않게 옮겼다"
MOVED_ITEM = re.compile(r"^- \[T\d+\]")


def item_properties(section_text):
    """칸에 적힌 `[성질: …]`의 값 집합(설계 5.2절). 쉼표나 가운뎃점으로 나눈다."""
    found = set()
    for mark in PROPERTY_MARK.findall(section_text or ""):
        found |= {p.strip(" `") for p in re.split(r"[,·/、]", mark) if p.strip(" `")}
    return found


def has_risk_mark(section_text):
    """성질 표시 안에 `위험`이 있는가. 꼴이 어긋나도 묻는 쪽으로 읽는다."""
    return any("위험" in mark for mark in PROPERTY_MARK.findall(section_text or ""))


def answer_is_judged(t):
    """사용자 답을 옮긴 task의 판정 기준에 그 옮김을 보는 줄이 있는가(`task_set.py new --from-answer`가 넣는다)."""
    return ANSWER_CRITERION in t.get("_sections", {}).get("판정 기준", "")


def next_criterion(text, sentence):
    """판정 기준 끝에 붙일 줄. 번호 목록이면 가장 큰 번호 다음, 아니면 글머리."""
    numbers = [int(n) for n in re.findall(r"^(\d+)\.\s", text or "", re.M)]
    return "{}. {}".format(max(numbers) + 1, sentence) if numbers else "- " + sentence


def without_moved_items(section_text):
    """다른 task에서 옮겨 온 `- [T0xx]` 항목(하위 줄 포함)을 뗀 칸. 옮겨 온 줄은 알림 판단과 수에 넣지 않는다(설계 5.3절 7)."""
    out, moved = [], False
    for line in (section_text or "").splitlines():
        if line.startswith("- "):
            moved = bool(MOVED_ITEM.match(line))
        if not moved:
            out.append(line)
    return "\n".join(out)


def review_contract(t):
    """그 task의 리뷰 계약(설계 4.3절). 변경 task는 고치는 정본으로 가른다: `spec` 아래가 있으면 scope, 아니면 approach."""
    kind = t.get("kind")
    if kind in kinds.KINDS and kinds.KINDS[kind].review:
        return kinds.KINDS[kind].review
    return "scope" if any(p.startswith("spec/") for p in change_paths(t)) else "approach"


def change_paths(t):
    """변경 task가 고치는 정본의 실행 폴더 기준 경로."""
    run_dir = os.path.dirname(os.path.dirname(t["_dir"])) if t.get("_dir") else None
    paths = touch_paths(t.get("_sections", {}).get("건드릴 파일", ""))
    return [re.sub(r"^tasks/T\d+/revised/", "", canon_relative(p, run_dir)) for p in paths]


def is_design_revision(t):
    """변경 task가 설계 정본만 고치는가. 인프라 정본은 자원 결정이라 뺀다(설계 7.2절의 고친 판)."""
    paths = change_paths(t)
    return bool(paths) and all(p.startswith("design/") and not p.startswith("design/infra") for p in paths)


def is_run_wide(t):
    """실행 전체 설계이거나 그 고친 판인가(머리 키 `run_wide`, 설계 7.2절)."""
    return str(t.get("run_wide", "") or "").strip().lower() in ("true", "예")


# 정본의 요구사항 행. 화면 AC 검사의 AC_HEAD_RE보다 넓다: 표 행과 앞붙이(`E-AC-1`)도 읽는다
_ROW_HEAD = r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|\s*|#+\s*)?[*_`\[]*"
AC_ROW_RE = re.compile(_ROW_HEAD + r"((?:[A-Z]+-)?AC-[0-9A-Za-z_-]+)")
FR_ROW_RE = re.compile(_ROW_HEAD + r"((?:[A-Z]+-)?FR-[0-9A-Za-z_-]+)")
_ITEM_LINE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|\|)")
MARK_FILLED = "담당이 채움"     # 작성자가 채운 값(설계 7.6절). 기획은 괄호 없이 쓴다
MARK_CHANGED = "[바뀜:"         # 기존 동작을 바꾸는 요구. 작성자가 `[바뀜: 파일:줄]`로 쓰고 판정자가 대조한다


def ac_rows(text):
    """인수 기준 [(번호, 그 행의 글)]. 행은 줄머리가 그 번호인 줄부터 다음 제목이나 FR·AC 줄 앞까지이고, 울타리 안은 보지 않는다.
    같은 번호가 다시 나오면(추적표) 앞의 행만 둔다."""
    rows, current, seen, fence = [], None, set(), False
    for line in (text or "").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence, current = not fence, None
            continue
        if fence:
            continue
        head = AC_ROW_RE.match(line)
        if head or FR_ROW_RE.match(line) or line.lstrip().startswith("#"):
            current = None
        if head and head.group(1) not in seen:
            seen.add(head.group(1))
            current = [head.group(1), line.strip()]
            rows.append(current)
        elif current is not None and line.strip():
            current[1] += "\n" + line.strip()
    return [tuple(r) for r in rows]


def filled_lines(text):
    """담당 값이 있는 줄. 목록·표 줄과 인수 기준 행 안의 줄만이다. 범례 문장과 울타리 안은 값이 아니다."""
    in_rows = {line for _, row in ac_rows(text) for line in row.splitlines()}
    out, fence = [], False
    for line in (text or "").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and MARK_FILLED in line and (_ITEM_LINE.match(line) or line.strip() in in_rows):
            out.append(line.strip())
    return out


def spec_marks(text):
    """정본 글의 셈: 인수 기준 수, 기존 동작을 바꾸는 요구, 담당 값이 있는 줄, 표지 없는 새 동작(설계 7.6절)."""
    rows = ac_rows(text)
    changed = sum(1 for _, row in rows if MARK_CHANGED in row)
    plain = sum(1 for _, row in rows if MARK_CHANGED not in row and MARK_FILLED not in row)
    return {"ac": len(rows), "changed": changed, "filled": len(filled_lines(text)), "new": plain}


def written_canon(run_dir, t):
    """task가 쓴 정본의 실행 폴더 기준 경로(`\\` 구분, 있는 파일만, 처음 나온 차례). 「건드릴 파일」이 먼저이고,
    없으면 결과 「본문」의 `정본:` 줄이다(정본을 처음 쓰는 task는 행에 건드릴 파일을 적지 않는다). 이름표가 없으면 자기 kind의
    정본 가운데 첫 경로만 본다. 본문은 다른 정본도 인용한다."""
    def found(text):
        out = []
        for m in CANON_PATH_RE.finditer(text or ""):
            # 경로 뒤에 조사가 붙을 수 있다(`spec/a.md를`)
            rel = re.sub(r"(\.(?:md|html))[^.\\/]*$", r"\1", m.group(0).rstrip(".:;")).replace("/", "\\")
            path = os.path.join(run_dir, *rel.split("\\"))
            if rel not in out and os.path.isfile(path) and inside(run_dir, path):
                out.append(rel)
        return out
    paths = found(t.get("_sections", {}).get("건드릴 파일", ""))
    prefix = kinds.WRITTEN_CANON.get(t.get("kind", ""))
    result = os.path.join(t.get("_dir") or "", "result.md")
    if paths or prefix is None or not os.path.isfile(result):
        return paths
    body = sections(read_text(result)).get("본문", "")

    def own(rel):
        q = rel.replace("\\", "/")
        if not q.startswith(prefix) or (prefix == "design/" and q.startswith("design/infra")):
            return False
        return prefix != "spec/" or os.path.basename(q) not in SPEC_SKIP
    labelled = [rel for rel in found("\n".join(l for l in body.splitlines() if "정본:" in l)) if own(rel)]
    return labelled or [rel for rel in found(body) if own(rel)][:1]


JUDGE_ORIGIN = re.compile(r"판정자 (T\d+)")   # 판정자 대안 문장에서 온 변경 task의 origin(설계 5.3절 4)
CORRECTION_CRITERION = "이 대안 문장만 옮겼고 그 밖은 바꾸지 않았다"
_SAME_MEANING = re.compile(r"뜻\s*바뀜\s*[:：]\s*없음")


def _cited_canon(line):
    return {re.sub(r":\d.*$", "", m.rstrip(".:;")).replace("\\", "/") for m in CANON_PATH_RE.findall(line)}


def unchanged_corrections(judge_text, paths=None):
    """판정자 「권장」의 대안 문장 가운데 뜻이 그대로이고 설계 정본을 고치는 줄. 요구사항·기획을 함께 가리키면 뺀다.
    인프라·화면 정본의 정정은 묻는다. paths를 주면 그 정본을 모두 가리키는 줄만이다."""
    out = []
    for line in sections(judge_text or "", level=2).get("권장", "").splitlines():
        cited = _cited_canon(line)
        design = {p for p in cited if p.startswith("design/") and not p.startswith("design/infra")}
        if line.startswith("- ") and _SAME_MEANING.search(line) and design and not any(p.startswith("spec/") for p in cited) \
                and (paths is None or set(paths) <= design):
            out.append(line)
    return out


def correction_is_judged(t):
    """판정 기준에 대안 문장의 옮김을 보는 줄이 있는가(`task_set.py new --origin "판정자 …"`가 넣는다)."""
    return CORRECTION_CRITERION in t.get("_sections", {}).get("판정 기준", "")


def correction_sentence(t):
    """판정 기준에 옮겨 적은 대안 문장. 없으면 빈 글."""
    for line in t.get("_sections", {}).get("판정 기준", "").splitlines():
        if CORRECTION_CRITERION in line:
            return line.split(CORRECTION_CRITERION, 1)[1].lstrip(": ").strip()
    return ""


def fix_cap(run_dir):
    """run.md 「이번 실행의 값」의 수정 세대 상한(시작값 2)."""
    return run_value(run_dir, "수정 세대", kinds.RUN_DEFAULTS["수정 세대 상한"])


def child_fix_generation(tasks, parent):
    """부모가 만드는 수정 task의 세대: 재검증이면 그 재검증이 의존하는 수정 task들의 최대 세대 + 1, 흐름별·전체 검증이면 0,
    그 밖(원인 분석·합치기 등)은 None(세지 않음, 0으로 만든다)."""
    kind = parent.get("kind")
    if kind in ("flow-verify", "full-verify"):
        return 0
    if kind != "reverify":
        return None
    gens = []
    for ref in [parent.get("parent", "")] + list(parent.get("depends_on", [])):
        o = tasks.get(ref)
        if o is not None and o.get("kind") == "fix":
            try:
                gens.append(int(str(o.get("fix_generation", "") or "0").strip() or 0))
            except ValueError:
                gens.append(0)
    return max(gens, default=0) + 1
