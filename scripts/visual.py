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
"""
import os
import re
import sys

import devflow_lib
import kinds

# 원천의 종류(kind 이름과 겹치지 않는 낱말. 엔진 코드의 kind 문자열은 engine_hooks가 있는 kind만, 시험 1(d))
DECISION, JOURNEY, SPEC, WIRE, VERIFY = "decision", "journey", "spec", "wire", "verify"
TABLE_WORDS = {DECISION: ("결정",), JOURNEY: ("여정", "화면 흐름"), SPEC: ("인수 기준",)}
LIMIT_KEY = "보는 자료 줄 수"

SOURCE_RE = re.compile(r"(?<![\w-])(?:spec|ui|design)[\\/][^\s`()'\"|,]*")
HEADING_RE = re.compile(r"^(#{1,3}) (.+)$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
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


def sources(run_dir, t):
    """[(종류, 실행 폴더 기준 경로)]. 경로는 `\\` 구분으로 적는다. 있는 파일만, 처음 나온 차례로 겹침 없이."""
    tid = t.get("id", "")
    entry = kinds.KINDS.get(t.get("kind", ""))
    if entry is not None and entry.verify_family:
        rel = "tasks\\{}\\result.md".format(tid)
        return [(VERIFY, rel)] if os.path.isfile(os.path.join(run_dir, "tasks", tid, "result.md")) else []
    secs = t.get("_sections", {})
    text = "\n".join(secs.get(name, "") for name in ("정본의 절", "건드릴 파일"))
    out, seen = [], set()
    for m in SOURCE_RE.finditer(text):
        rel = m.group(0).rstrip(".:;").replace("/", "\\")
        kind = _kind_of(rel)
        if kind is None or rel.lower() in seen:
            continue
        if os.path.isfile(os.path.join(run_dir, *rel.split("\\"))):
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


def trace_rows(text):
    """`| 정책 | FR | AC |` 표(머리 둘 줄 포함). FR 줄이 없으면 빈 목록.
    FR 줄: 줄머리(`- `·`| `·`#` 뒤)가 FR id인 줄. 정책은 같은 줄의 `P-n`, AC는 줄머리가 AC id이고 그 FR id를 담은 줄."""
    lines = text.splitlines()
    acs = [(m.group(1), line) for line in lines for m in [AC_HEAD_RE.match(line)] if m]
    rows, seen = [], set()
    for line in lines:
        m = FR_HEAD_RE.match(line)
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


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, tid = argv[1], argv[2]
    if not os.path.isfile(os.path.join(run_dir, "tasks", tid, "task.md")):
        print("task 없음: {} ({})".format(tid, os.path.join(run_dir, "tasks", tid, "task.md")))
        return 2
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
