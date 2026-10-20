"""devflow-harness 스크립트 공통 함수.

머리 파일(task.md)은 맨 앞의 `---` 사이에 `키: 값` 줄을 두고, 그 아래에 `## 제목` 절을 둔다.
값은 한 줄 문자열이거나 `[a, b]` 꼴의 목록이다. 형식은 formats.md가 원천이다.
"""
import io
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
# 300K에서 바로 막으면 사람이 없을 때 실행이 멈춘다(2026-10-07 실행: 11:13에 300K를 넘었고 구현 시작이 11:18).
CTX_ADVISE = 300_000
CTX_STOP = 400_000
CTX_TAIL_BYTES = 4 * 1024 * 1024
CTX_STALE_SEC = 600


def main_context():
    """메인 세션의 지금 컨텍스트(마지막 호출의 input + cache_read + cache_creation 토큰)를 세션 기록에서 읽는다.
    (토큰 수, 세션 ID 앞 8자) 또는 (None, 측정 불가 이유)를 돌려준다.
    세션은 CLAUDE_CODE_SESSION_ID로 찾을 때만 잰다. 가장 최근 기록으로 추정하면 같은 프로젝트에서 동시에 도는
    다른 세션을 잡는다(2026-10-07: 세 세션이 같은 프로젝트 폴더에서 함께 돌았다). 하위 에이전트 안에서도 이 변수는 메인 세션 ID다."""
    import glob
    import json
    import time
    from datetime import datetime
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        return None, "세션 ID 환경 변수 없음"
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    found = glob.glob(os.path.join(root, "*", sid + ".jsonl"))
    if not found:
        return None, "세션 기록 없음({})".format(sid[:8])
    path = found[0]
    ctx, ts = None, None
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
            if n:
                ctx, ts = n, d.get("timestamp")
    if ctx is None:
        return None, "usage 없음({})".format(sid[:8])
    try:
        age = time.time() - datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        age = 0
    if age > CTX_STALE_SEC:
        # /clear 뒤 옛 세션을 읽어 권고가 되풀이되지 않게 한다.
        return None, "마지막 기록이 {}분 전({})".format(int(age // 60), sid[:8])
    return ctx, sid[:8]


def main_context_line():
    """`screen.py`와 `board.py --ready`가 맨 끝에 붙이는 한 줄. `counts:`로 시작하지 않는다(메인이 counts 줄을 읽는다)."""
    ctx, info = main_context()
    if ctx is None:
        return "메인 컨텍스트: 측정 불가({})".format(info)
    line = "메인 컨텍스트: {}K (세션 {})".format(ctx // 1000, info)
    if ctx >= CTX_STOP:
        line += " — {}K 넘음: 새 task를 띄우지 않고 정리 지점을 기다려 `/clear` 뒤 `devflow-harness 이어서`를 권함(SKILL.md 8절)".format(CTX_STOP // 1000)
    elif ctx >= CTX_ADVISE:
        line += " — {}K 넘음: 다음 정리 지점에서 `/clear` 뒤 `devflow-harness 이어서`를 권함(SKILL.md 8절)".format(CTX_ADVISE // 1000)
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


# ---------------------------------------------------------------------------
# 필요한 판정과 기록 점검(SKILL.md 2절, formats.md 2·5절). R1~R5는 `started_version`이 있는 task
# (규칙 판 1을 넣은 뒤 `task_set.py --status 진행`으로 시작한 task)에만 적용한다. 옛 task의 판정 파일에는
# `판정자:` 첫 줄이 없어서 적용하면 모두 걸린다.

# 판정 파일 → 첫 줄 판정자 이름의 접두어(등록표 AGENTS의 short + "-")
JUDGE_PREFIX = {kinds.JUDGE_FILES[r]: kinds.AGENTS[n].short + "-" for r, n in (("read", "read-judge"), ("run", "run-judge"))}
# 판정자 첫 줄. 정의는 `date "+%Y-%m-%d %H:%M:%S"`를 쓰게 하지만, 초 없음·T 구분·시간대 꼬리도 받는다
JUDGE_LINE = re.compile(r"^판정자:\s*(\S+)\s+(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(:\d{2})?(?:\.\d+)?\s*(?:Z|[+-]\d{2}:?\d{2}|[A-Z]{2,4})?\s*$")
MTIME_SLACK = 60    # 초. 판정자가 첫 줄 시각을 쓴 뒤 파일을 닫기까지의 틈(판정 102초 뒤의 메인 Edit를 잡는 폭)


def is_new_task(t):
    return bool(str(t.get("started_version", "")).strip())


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


def required_judges(t):
    """이 task가 `완료`·`승인대기`로 가기 전에 있어야 하는 판정({"read", "run"}). 각 정의의 「자체 검증」에서 뽑았다.
    구현의 실행 판정은 늘 둔다(문서만 바꾸는 구현은 관련 테스트가 recon 「문서를 읽는 검사」).
    합치기는 exec.md 브랜치 판정에 `충돌`이 하나라도 있으면(충돌을 고친 합치기) 읽기 판정을 요구한다.
    테스트 실패로 코드를 고친 합치기는 exec.md에 흔적이 없어 여기서 가리지 못한다."""
    kind = t.get("kind", "")
    need = set()
    k = kinds.KINDS.get(kind)
    if k is not None and k.run_judge == "always":
        need.add("run")
    if k is not None and k.read_judge == "always":
        need.add("read")
    if kind == "implementation":
        cells = result_cells(t) or {}
        if t.get("closes_ac") or str(t.get("machine_check", "")).strip() == "3" or item_count(cells.get("알릴 것", "")):
            need.add("read")
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


def judges_present(t):
    """(있음 여부, 이유). 새 task는 필요한 판정 파일이 모두 있고 첫 줄 판정자가 그 역할이어야 한다.
    옛 task는 판정 파일이 하나라도 있으면 된다."""
    d = t["_dir"]
    if not is_new_task(t):
        if any(os.path.isfile(os.path.join(d, f)) for f in kinds.JUDGE_FILES.values()):
            return True, ""
        return False, "판정 파일(judge.md·judge-run.md)이 없음"
    missing = []
    need_names = {kinds.JUDGE_FILES[n] for n in required_judges(t)}
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
    return (not missing), "; ".join(missing)


def record_lines(t):
    return [l.strip() for l in t["_sections"].get("승인 기록", "").splitlines() if l.strip().startswith("- ")]


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
        if len(f) >= 2 and f[1] in ("알림", "점검 확인"):
            continue
        if re.search(r'"[^"]+"', line):
            return True
    return False


def approval_line(line):
    """승인 기록 한 줄이 승인인가(지점 칸이나 결정 칸이 `승인`, 옛 꼴 원문 "승인"·"승인 (…)").
    알림·점검 확인·되물음 줄과 결정이 보류·거절·되돌림인 줄은 승인이 아니다. 규칙 판 1의 승인 판별과
    exec.py의 얼림이 함께 쓴다."""
    f = record_fields(line)
    if len(f) < 2:   # 칸이 없는 옛 꼴은 원문만 본다
        return bool(re.search(r'"승인\s*(?:\(|")', line))
    point, decision = f[1], (f[2] if len(f) > 2 else "")
    if point in ("알림", "점검 확인") or point.startswith("되물음"):
        return False
    if any(w in decision for w in ("보류", "거절", "되돌림")):
        return False
    if point == "승인" or decision == "승인" or re.match(r"승인\s*[(:]", decision):
        return True
    return bool(re.search(r'"승인\s*(?:\(|")', line))   # 옛 꼴: 전체: "승인", "승인 (Recommended)"


def prior_approval(t):
    """사람이 이미 이 task를 승인했는가(승인 뒤 같은 작성자 일을 이어 한 task의 끝)."""
    return any(approval_line(line) for line in record_lines(t))


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
                and (lvl >= 2 or "받아오기" not in str(t.get("origin", ""))):
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


def settled(t, tasks, blockers=None):
    """가드가 끝으로 세는가: 완료·보류·백로그, 또는 보류에 막힌 대기. 흐름별 검증은 보류에 막혀도 끝으로 세지 않는다
    (같은 흐름 코드 task의 자동 의존 사슬로 막히므로, 끝으로 세면 사람에게 묻지 않고 마무리가 뜬다. 묻는 길은 board.py)."""
    st = t.get("status")
    if st in (kinds.DONE, "보류", "백로그"):
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


PATH_TOKEN = re.compile(r"(?:[A-Za-z]:)?[\w.*{}\-]*[/\\][\w./\\*{}\-]*|[\w*{}\-]+\.[A-Za-z0-9*]{1,8}")
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


def outside_canon(paths, run_dir=None):
    """정본 밖 경로(코드·문서 등). 실행 폴더의 절대 경로와 작업 공간 기준 경로(`_workspace/{실행}/…`, `{실행}/…`)는
    실행 폴더 기준으로 바꿔 본다(한 change 행이 `_workspace/{실행}/design/…`). `..`는 푼다."""
    base = (os.path.abspath(run_dir).replace("\\", "/").rstrip("/") + "/").lower() if run_dir else ""
    name = os.path.basename(os.path.abspath(run_dir)).lower() if run_dir else ""
    bad = []
    for p in paths:
        q = p.replace("\\", "/")
        if base and q.lower().startswith(base):
            q = q[len(base):]
        elif name:
            m = re.search(r"(?:^|/)(?:_workspace/)?" + re.escape(name) + "/", q, re.I)
            if m and (m.start() == 0 or "_workspace/" in q[:m.end()].lower()):
                q = q[m.end():]
        q = posixpath.normpath(re.sub(r"^\./", "", q))
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


def user_origin(t):
    """사용자 원문을 계기로 만든 task인가(`origin`이 `사용자`로 시작, `task_set.py new --from-answer`가 채움)."""
    return str(t.get("origin", "") or "").strip().startswith("사용자")


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
