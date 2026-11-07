"""코드 확인의 곳(설계 11.1절 「1.2.0의 코드 확인」, 6.16절). 흐름별 검증 승인 앞에서 사람이 코드로 볼 판단을 묶고 차례를 정한다.

명령행은 `screen.py`(`--places`, `--card`, `--answer`)와 `task_set.py`(`--card-open`, `--record`, `new --place`)에 있다.
- 곳: 같은 task에서 `[위치]` 파일이 같거나 판정자가 `같은 곳:`으로 이은 판단의 묶음과, 판단 없는 보안 코드 하나.
- 고정: `tasks\\{id}\\places.md`에 한 번 쓰고 그 뒤로는 이 파일만 읽는다(재시도로 문장이 바뀌어도 키는 파일 목록의 해시라 그대로다).
- 차례: 보안 곳이 앞이고 상한과 따로 센다. 보안 밖은 판정자의 `지금 문제 있음`, 같은 판단의 셋째, 트랜잭션, 데이터, 외부호출, 오류, 구조, 설정 등록 순이다.
- `places.md`의 머리: `- 위임:`, `- 재지 못함:`(보안 신호를 재지 못한 task), `- 재지 못함 이유: {T} | {까닭}`, `- 잰 task:`, `- 잰 커밋: {T} | {커밋 또는 없음}`(지금 커밋과 다르면 재지 못함), `- 다시 잰 커밋: {T} | {커밋 또는 없음}`, `- 닿지 않음:`, `- 시도: {시각} | {메인이 한 일}`.
  곳마다 `## {키}`와 칸 `카드`, `task`, `커밋`, `부류`, `보안`, `종류`, `파일`, `위치`, `발췌`, `의견`, `처리`, `답`, 줄마다 `신호`, `b{n}: 종류 | 위치 | 문장`, `의견 줄`.
- `places.md`의 꼴은 `read`가 읽는 칸이다. 마무리 리뷰(A9)는 `run_left`, 흐름 리뷰(A7)는 `read`를 쓴다.
"""
import hashlib
import os
from datetime import datetime
import re
import subprocess

import delegation
import devflow_lib
import kinds
import machine_check

PLACES_FILE = "places.md"
GAP_NO_COMMIT, GAP_NO_FOLDER, GAP_GIT, GAP_NOT_RUN = "커밋 값 없음", "코드 폴더 없음", "git 실패", "시험 변화를 재지 않음"
GAP_OFF_SCOPE, GAP_NO_SCOPE, GAP_LATE = "커밋이 건드릴 파일과 안 맞음", "건드릴 파일이 없어 커밋을 대 보지 못함", "고정 뒤에 끝나 재지 않음"
GAP_CHANGED = "잰 뒤에 커밋이 바뀜"
GAP_WORDS = {GAP_NO_COMMIT: "머리 파일에 커밋 값이 없어 어떤 코드인지 찾지 못했습니다", GAP_NO_FOLDER: "코드 폴더가 없어 그 코드를 읽지 못했습니다",
             GAP_GIT: "git이 그 커밋을 읽지 못했습니다", GAP_NOT_RUN: "시험 변화를 잰 기록이 없습니다",
             GAP_OFF_SCOPE: "적힌 커밋이 이 task의 파일 범위를 건드리지 않아 이 task의 코드인지 알 수 없습니다",
             GAP_NO_SCOPE: "파일 범위가 적히지 않아 적힌 커밋이 이 task의 코드인지 알 수 없습니다",
             GAP_LATE: "곳을 고정한 뒤에 끝난 task라 재지 않았습니다",
             GAP_CHANGED: "곳을 고정한 뒤에 커밋이 바뀌어 지금 코드를 재지 않았습니다"}
GAP_REASON, GAP_TRIED, GAP_RETRIED = "재지 못함 이유", "시도", "다시 잰 커밋"
TRIED_DEFAULT = "기록을 다시 읽고 다시 재 보았습니다"
MEASURED_LABEL, MEASURED_AT = "잰 task", "잰 커밋"
PLACE_CAP = 5   # 흐름당 곳 수의 시작값. 보안 곳은 따로 센다(설계 11.1절)
CHECK_KINDS = ("구조", "데이터", "트랜잭션", "오류", "외부호출", "보안")   # 코드로 보는 판단 종류. 동작은 흐름 리뷰, 시험은 시험 변화로 간다
SETTING = "설정 등록"
RISK_ORDER = ("보안", "트랜잭션", "데이터", "외부호출", "오류", "구조", SETTING)
WITH_JUDGMENT = "판단"
NO_JUDGMENT = "판단 없는 보안 코드"
WAITING = "기다림"
ANSWERED = "답함"
LEFT_CAP = "남김(상한)"
LEFT_DELEGATED = "남김(위임)"
LEFT_BULK = "남김(일괄)"
LEFT_UNJUDGED = "남김(판단 안 됨)"
NO_OPINION = "의견 없음"
DELETED_NOTE = "(이 커밋에서 지움)"
BINARY_NOTE = "이진 파일이라 코드를 싣지 못함"
PROBLEM = "지금 문제 있음"
NO_PROBLEM = "지금 문제 없음"
SECURITY_MARK = "[보안]"
EXCERPT, EXCERPT_FOLLOW, EXCERPT_FULL = 12, 3, 60
EXCERPT_FLOOR = 3   # 위치당 줄 수의 바닥. 위치가 많으면 앞 몇 개만 싣고 수를 적는다
TREE_ROWS = 40
FIX_DIFF_LINES = 60
FIX_CRITERION = "원문의 요구가 변경에 빠짐없이, 그보다 넓지 않게 반영됨"
# 카드의 답 번호(설계 6.16절 「답의 꼴」). 맨 숫자는 이 번호다
FINE, FIX_ONLY, UNJUDGED, REST = "문제 없음", "이 코드만 고침", "판단 안 됨", "나머지 남김"
ANSWER_NUMBERS = (FINE, FIX_ONLY, UNJUDGED, REST)
ANSWER_TEXT = (FIX_ONLY, UNJUDGED)
ANSWER_NAMES = (FINE, FIX_ONLY, UNJUDGED, REST, "남김")
TEXT_ANSWER_HEAD = re.compile(r"^(?:\d+\s+)?(?:{}|{})(?:\s|$)".format(re.escape(FIX_ONLY), re.escape(UNJUDGED)))
FULL_ANSWER = re.compile(r"^(?:\d+\s+)?전체$")
JUDGE_LABEL = re.compile(r"^-?\s*(숨은 판단|종류 이의|같은 곳|같은 판단|코드 의견)\s*:\s*(.*)$")
WHERE = re.compile(r"^(.*?)(?::(\d+)(?:-\d+)?)?$")
CELL_SPLIT = re.compile(r"\s\|\s")
# 답 값 앞의 표지만 표지다. 글 속의 `b1=null`은 글이다
DECISION_TARGET = re.compile(r"(?:^|\s)(b\d+(?:,b\d+)*)=(?=" + "|".join(re.escape(n) for n in (FINE, FIX_ONLY, UNJUDGED)) + ")")
PIECE_TARGET = re.compile(r"^(b\d+)(?:\s*=\s*|\s+)(\S.*)$")
BARE_TARGET = re.compile(r"^b\d+$")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _path(text):
    return str(text or "").strip().strip("`").replace("\\", "/")


def _where(text):
    """`파일:줄`을 (파일, 줄 또는 None)으로."""
    m = WHERE.match(_path(text))
    return m.group(1), (int(m.group(2)) if m.group(2) else None)


def _short_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def code_folder(run_dir, t):
    """흐름의 코드 폴더(flow.md `dir`). 없으면 빈 글."""
    p = os.path.join(run_dir, "flows", str(t.get("flow", "") or ""), "flow.md")
    if not t.get("flow") or not os.path.isfile(p):
        return ""
    meta_lines, _ = devflow_lib.split_front_matter(devflow_lib.read_text(p))
    folder = str(devflow_lib.parse_meta(meta_lines).get("dir", "") or "")
    return folder if folder and os.path.isdir(folder) else ""


def _git(folder, *args):
    """(성공 여부, 출력). 한글 경로가 이스케이프되지 않게 quotepath를 끈다."""
    if not folder:
        return False, ""
    out = subprocess.run(["git", "-C", folder, "-c", "core.quotepath=off"] + list(args),
                         capture_output=True, encoding="utf-8", errors="replace")
    return out.returncode == 0, out.stdout


# ---------------------------------------------------------------- 판단과 판정자 칸


def _judgments(t):
    """결과 파일 「판단」의 판단 줄. `[설계:]` 줄과 꼴이 어긋난 줄은 판단이 아니다(꼴은 자체검증 앞에서 막는다)."""
    path = os.path.join(t["_dir"], "result.md")
    body = devflow_lib.sections(devflow_lib.read_text(path)).get("판단", "") if os.path.isfile(path) else ""
    out = []
    for line in body.splitlines():
        if not line.startswith("- ") or devflow_lib.JUDGMENT_NONE.match(line) or not devflow_lib.judgment_line_ok(line):
            continue
        tags = dict(devflow_lib.judgment_tags(line))
        if "설계" in tags:
            continue
        out.append({"text": devflow_lib.JUDGMENT_TAG.sub("", line[2:]).strip(), "kind": tags["종류"], "where": _path(tags["위치"]),
                    "follows": "따름" in tags})
    return out


def split_cells(text):
    """` | `로 칸을 나눈다. 백틱 안의 ` | `(`number | null`)는 칸 경계가 아니다. 백틱이 짝이 맞지 않으면 그냥 나눈다."""
    if text.count("`") % 2:
        return [c.strip() for c in CELL_SPLIT.split(text)]
    # 백틱 밖 조각만 나눠 이어 붙인다(홀수 번째 조각이 백틱 안)
    cells = [""]
    for at, piece in enumerate(text.split("`")):
        if at % 2:
            cells[-1] += "`" + piece + "`"
            continue
        parts = CELL_SPLIT.split(piece)
        cells[-1] += parts[0]
        cells += parts[1:]
    return [c.strip() for c in cells]


def _judge_lines(t):
    """판정 파일 「판단 대조」의 칸 줄 [(이름, 칸 목록, 줄 원문)]."""
    path = os.path.join(t["_dir"], kinds.JUDGE_FILES["read"])
    body = devflow_lib.sections(devflow_lib.read_text(path)).get("판단 대조", "") if os.path.isfile(path) else ""
    out = []
    for line in body.splitlines():
        m = JUDGE_LABEL.match(line.strip())
        if m:
            out.append((m.group(1), split_cells(m.group(2)), line.strip()[2:] if line.strip().startswith("- ") else line.strip()))
    return out


def _design_judgments(t):
    """결과 파일 「판단」의 `[설계:]` 판단 글. 곳이 되지 않지만 판정자가 인용할 수 있는 줄이다."""
    path = os.path.join(t["_dir"], "result.md")
    body = devflow_lib.sections(devflow_lib.read_text(path)).get("판단", "") if os.path.isfile(path) else ""
    lines = [line for line in body.splitlines() if line.startswith("- ") and devflow_lib.judgment_line_ok(line)]
    return [devflow_lib.JUDGMENT_TAG.sub("", line[2:]).strip() for line in lines if "설계" in dict(devflow_lib.judgment_tags(line))]


def _quote(text):
    """판정자가 인용한 판단 줄의 앞부분. 표지와 말줄임 뒤를 자른다. 비면 어느 판단에도 닿지 않는다."""
    return re.split(r"\[|…|\.\.\.", str(text or ""))[0].strip()


def _with_judge(t, judgments, lines, warnings):
    """판정자의 숨은 판단과 종류 이의를 더한다. 종류 이의는 코드로 보는 쪽으로만 옮기고, 작성자의 `보안`은 내리지 않는다(올리는 데만 쓴다).
    어느 판단에도 닿지 않은 인용은 warnings에 담는다."""
    out = [dict(j) for j in judgments]
    for name, cells, _ in lines:
        if name == "숨은 판단" and len(cells) >= 3 and cells[-1] in kinds.JUDGMENT_KINDS:
            out.append({"text": " | ".join(cells[1:-1]), "kind": cells[-1], "where": _path(cells[0]), "follows": False})
    for name, cells, _ in lines:
        if name not in ("종류 이의", "같은 판단"):
            continue
        quote = _quote(cells[0]) if len(cells) >= 2 else ""
        hit = [j for j in out if quote and j["text"].startswith(quote)]
        # `같은 판단:`이 `[설계:]` 판단을 가리키면 닿은 것이다. 곳이 되지 않을 뿐이다
        if not hit and not (name == "같은 판단" and quote and any(text.startswith(quote) for text in _design_judgments(t))):
            warnings.append("{} {} {}".format(t["id"], name, cells[0] if len(cells) >= 2 else ""))
        if name == "종류 이의" and len(cells) >= 2:
            after = cells[-1].split("→")[-1].strip()
            for j in hit:
                if after in CHECK_KINDS and j["kind"] != "보안":
                    j["kind"] = after
    return out


def _same_groups(files, lines):
    """파일을 `같은 곳:`으로 이은 묶음 목록. 묶음은 파일 집합이다."""
    groups = [{f} for f in files]
    for name, cells, _ in lines:
        if name != "같은 곳":
            continue
        linked = {_where(c)[0] for c in cells if c}
        hit = [g for g in groups if g & linked]
        if not hit:
            continue
        merged = set(linked).union(*hit)
        groups = [g for g in groups if g not in hit] + [merged]
    return groups


def opinion_cells(cells):
    """`코드 의견:` 칸 목록을 푼다. 일어난 일과 조건에 ` | `가 들어도 밀리지 않게 판정 칸의 자리로 나눈다(`string | null`).
    {"where", "happened", "verdict", "breaks", "way"}. 판정 칸을 찾지 못하면 verdict는 빈 글이다."""
    def verdict_of(cell):
        bare = cell.strip(" `*.")
        return bare if bare in (PROBLEM, NO_PROBLEM) else ""
    at = next((i for i, c in enumerate(cells) if i and verdict_of(c)), None)
    if at is None:
        # 꾸밈이 붙은 `지금 문제 있음(추정)`도 잃지 않는다
        at = next((i for i, c in enumerate(cells) if i and PROBLEM in c), None)
    if at is None:
        return {"where": cells[0] if cells else "", "happened": " | ".join(cells[1:]), "verdict": "", "breaks": "", "way": ""}
    after = cells[at + 1:]
    return {"where": cells[0], "happened": " | ".join(cells[1:at]), "verdict": verdict_of(cells[at]) or PROBLEM,
            "breaks": " | ".join(after[:-1]) if len(after) >= 2 else "".join(after), "way": after[-1] if len(after) >= 2 else ""}


def _opinions(lines):
    """파일 → 코드 의견(`opinion_cells`에 줄 원문 `raw`를 더한 것)."""
    out = {}
    for name, cells, raw in lines:
        if name == "코드 의견":
            note = dict(opinion_cells(cells), raw=raw)
            out.setdefault(_where(note["where"])[0], []).append(note)
    return out


def _stored_opinions(place):
    return [opinion_cells(split_cells(raw.split(":", 1)[-1].strip())) for raw in place["의견 줄"]]


# ---------------------------------------------------------------- 보안 표지와 신호


def security_marked(run_dir, t):
    """보안 표지: 머리 파일 「시그니처와 결정 번호」의 `[보안]`이나, 닫거나 일부를 맡은 인수 기준이 정본에서 처음 나오는 줄의 `[보안]`."""
    if SECURITY_MARK in t.get("_sections", {}).get("시그니처와 결정 번호", ""):
        return True
    closes = set(t.get("closes_ac") or []) | set(t.get("partial_ac") or [])   # 보안 기준의 일부만 맡은 코드도 사람이 본다
    if not closes or not os.path.isdir(os.path.join(run_dir, "spec")):
        return False
    return bool(closes & security_acs(run_dir))


def security_acs(run_dir):
    """정본에서 `[보안]`이 붙은 인수 기준 번호(번호가 처음 나오는 줄머리). 표 행과 앞붙이(`E-AC-1`)도 읽는다. 놓치면 보안 코드를 사람이 보지 않는다."""
    spec, found = os.path.join(run_dir, "spec"), set()
    for name in sorted(os.listdir(spec)):
        if not name.endswith(".md") or name in devflow_lib.SPEC_SKIP:
            continue
        seen = set()
        for line in devflow_lib.read_text(os.path.join(spec, name)).splitlines():
            m = devflow_lib.AC_ROW_RE.match(line)
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                if SECURITY_MARK in line:
                    found.add(m.group(1))
    return found


def _commit_of(t):
    """task의 커밋 해시. `HEAD`처럼 해시가 아닌 값은 어느 코드인지 고정하지 못하므로 커밋으로 보지 않는다."""
    sha = str(t.get("commit", "") or "").strip()
    return sha if machine_check.COMMIT_HASH.match(sha) else ""


def _changed(folder, t):
    """task 커밋의 (성공 여부, diff). 커밋이 없으면 실패다."""
    sha = _commit_of(t)
    if not sha:
        return False, ""
    return _git(folder, "show", "--format=", "--unified=0", "--no-renames", sha)   # 이름 바꿈은 지운 파일과 새 파일 둘로 본다. 옛 실행에서 드물었다


def gap_cause(run_dir, t):
    """코드 task를 재지 못한 까닭. 잴 수 있으면 빈 글이다."""
    if devflow_lib.no_code(t):
        return ""
    if not str(t.get("commit", "") or "").strip():
        return GAP_NO_COMMIT
    folder = code_folder(run_dir, t)
    if not folder:
        return GAP_NO_FOLDER
    return "" if _changed(folder, t)[0] else GAP_GIT


def _scope_gap(run_dir, t):
    """메인이 적은 커밋이 이 task의 코드로 보이지 않는 까닭. 「건드릴 파일」과 하나도 겹치지 않거나 대 볼 목록이 없으면 그 값으로 풀지 않는다."""
    if devflow_lib.no_code(t):
        return ""
    allowed = machine_check.allowed_patterns(t) or devflow_lib.touch_paths(t.get("_sections", {}).get("건드릴 파일", ""))
    if not allowed:
        return GAP_NO_SCOPE
    files = machine_check.diff_files(_changed(code_folder(run_dir, t), t)[1])
    return "" if any(machine_check.matches(path, allowed) for path in files) else GAP_OFF_SCOPE


def remeasure_cause(run_dir, t):
    """다시 잴 때 재지 못한 까닭: `gap_cause`에 커밋이 범위에 맞는지를 더한다."""
    return gap_cause(run_dir, t) or _scope_gap(run_dir, t)


def _product_files(diff):
    """diff의 {제품 파일: 처음 바뀐 줄}. 시험 파일은 제품 변경분이 아니다."""
    return {path: line for path, line in machine_check.diff_files(diff).items() if not machine_check.TEST_HINT.search(path)}


# ---------------------------------------------------------------- 묶기


def _flow_code_tasks(tasks, tid):
    """그 흐름의 1.2.0 코드 task. 검증에서 나온 수정과 코드 확인에서 온 수정은 흐름 뒤 수정이라 곳을 만들지 않는다."""
    verify = tasks[tid]

    def from_verify(t):
        refs = (t.get("parent", ""), str(t.get("cause_task", "")).strip())
        return any(r in tasks and tasks[r].get("kind") in kinds.VERIFY_KINDS for r in refs)

    return [t for t in tasks.values()
            if t.get("flow") == verify.get("flow") and devflow_lib.needs_judgment_record(t)
            and not from_verify(t) and devflow_lib.CODE_CHECK_ORIGIN not in str(t.get("origin", ""))
            and str(t.get("done_via", "")).strip() != "백로그"]


def _check_tasks(tasks, tid):
    """곳을 만드는 코드 task: 그 흐름에서 끝난 1.2.0 코드 task."""
    return [t for t in _flow_code_tasks(tasks, tid) if t.get("status") == kinds.DONE]


def check_tasks(tasks, tid):
    return _check_tasks(tasks, tid)


def measure_tasks(tasks, tid):
    """보안 신호를 재는 코드 task: 끝난 task와 커밋이 있는 보류·백로그. 커밋이 있으면 코드가 흐름 브랜치에 남아 합쳐진다. 치운 task는 코드가 패치로 빠져 커밋이 없다."""
    return _check_tasks(tasks, tid) + [t for t in _flow_code_tasks(tasks, tid) if t.get("status") in devflow_lib.HELD_STATUSES and not devflow_lib.not_in_flow(t)]


def task_judgments(t):
    """그 task의 판단 전부(판정자의 숨은 판단 포함)."""
    return _with_judge(t, _judgments(t), _judge_lines(t), [])


def behavior_rows(tasks, tid):
    """[{"task", "text", "where"}]: 그 흐름의 동작 판단(설계 7.1절 3). 곳이 되지 않고 흐름 리뷰의 번호 붙은 문장으로 간다."""
    out = []
    for t in _check_tasks(tasks, tid):
        out += [{"task": t["id"], "text": j["text"], "where": j["where"]} for j in task_judgments(t) if j["kind"] == "동작"]
    return out


def _asked_keys(tasks, run_dir, tid):
    """같은 흐름의 다른 검증이 이미 고정한 곳의 키. 앞 검증이 물은 곳을 다시 묻지 않는다."""
    verify = tasks[tid]
    keys = set()
    for t in tasks.values():
        if t["id"] != tid and t.get("kind") == "flow-verify" and t.get("flow") == verify.get("flow"):
            keys.update(p["key"] for p in read(run_dir, t["id"]))
    return keys


def _third_same(tasks):
    """`같은 판단:`으로 이어진 task 묶음에서 셋째부터의 {task id: 그 줄의 앞부분들}. 묶음은 task로 이으므로 다른 판단이 섞이면 넘치게 세고, 올리는 데만 쓴다."""
    links, groups = {}, []
    for t in tasks.values():
        if not devflow_lib.needs_judgment_record(t):
            continue
        for name, cells, _ in _judge_lines(t):
            if name == "같은 판단" and len(cells) >= 2 and cells[1] in tasks:
                links.setdefault(t["id"], []).append(_quote(cells[0]))
                pair = {t["id"], cells[1]}
                hit = [g for g in groups if g & pair]
                groups = [g for g in groups if g not in hit] + [pair.union(*hit)]
    big = {i for g in groups for i in sorted(g)[2:]}
    return {i: prefixes for i, prefixes in links.items() if i in big}


def _is_setting(where):
    path = _where(where)[0]
    return machine_check.matches(path, machine_check.DEFAULT_CONFIG) or machine_check.matches(path.rsplit("/", 1)[-1], machine_check.DEFAULT_CONFIG)


def _place(t, files, judgments, opinions, security, where=None, signals=()):
    """곳 하나. 번호·처리·카드 번호는 `_order`가 단다."""
    judgments = sorted(judgments, key=lambda j: (_where(j["where"])[0], _where(j["where"])[1] or 0))
    notes = [o for f in sorted(files) for o in opinions.get(f, [])]
    verdicts = {o["verdict"] for o in notes}
    mask = devflow_lib.mask_line
    if judgments:
        kind = min((j["kind"] for j in judgments), key=RISK_ORDER.index)
        if all(_is_setting(j["where"]) for j in judgments):
            kind = SETTING
    else:
        kind = "보안"
    follows = bool(judgments) and all(j["follows"] for j in judgments)
    security = security or not judgments or any(j["kind"] == "보안" for j in judgments)
    return {
        "key": "{}-{}".format(t["id"], _short_hash("\n".join(sorted(files)))), "task": t["id"], "커밋": _commit_of(t),
        "부류": WITH_JUDGMENT if judgments else NO_JUDGMENT, "보안": "예" if security else "아니오", "종류": kind,
        "파일": sorted(files), "위치": where or [j["where"] for j in judgments], "발췌": str(EXCERPT_FOLLOW if follows else EXCERPT),
        "의견": PROBLEM if PROBLEM in verdicts else (NO_PROBLEM if NO_PROBLEM in verdicts else NO_OPINION), "처리": WAITING, "답": "",
        "신호": list(signals), "판단": [dict(j, text=mask(j["text"])) for j in judgments], "의견 줄": [mask(o["raw"]) for o in notes],
        "_follows": follows, "_third": False,
    }


def _task_places(run_dir, t, measure, warnings):
    """task 하나의 곳. 보안 표지나 신호가 있으면 판단이 없어도 코드를 본다(설계 6.12절 「보안」)."""
    lines = _judge_lines(t)
    judgments = [j for j in _with_judge(t, _judgments(t), lines, warnings) if j["kind"] in CHECK_KINDS]
    opinions = _opinions(lines)
    files = {_where(j["where"])[0] for j in judgments}
    # 판단이 없는 곳의 `지금 문제 있음`은 말없이 사라지지 않게 판단으로 올린다
    for path, notes in opinions.items():
        problem = next((o for o in notes if o["verdict"] == PROBLEM), None)
        if problem and path not in files:
            judgments.append({"text": "(판정자 의견) " + problem["happened"], "kind": "구조", "where": problem["where"], "follows": False})
            files.add(path)
    ok, diff = _changed(code_folder(run_dir, t), t)
    if not ok and not devflow_lib.no_code(t):
        measure.append(t["id"])
    hit_files = {}
    for hit in machine_check.security_hits(diff, *machine_check.security_signals(run_dir)):
        hit_files.setdefault(hit[0], []).append(hit)
    marked = security_marked(run_dir, t)
    out, covered = [], set()

    def signal_rows(paths):
        return [machine_check.signal_row(hit) for f in sorted(paths) for hit in hit_files.get(f, [])]

    def signal_places(path, first_line):
        rows = list(dict.fromkeys("{}:{}".format(path, hit[1]) for hit in hit_files.get(path, [])))
        return rows or ["{}:{}".format(path, first_line)]

    for group in _same_groups(files, lines):
        members = [j for j in judgments if _where(j["where"])[0] in group]
        if not members:
            continue
        covered |= group
        out.append(_place(t, group, members, opinions, marked or bool(group & set(hit_files)), signals=signal_rows(group)))
    changed = _product_files(diff)
    if marked:
        rest = sorted(set(changed) - covered)
        if not ok and not changed:
            rest = [p for p in devflow_lib.touch_paths(t.get("_sections", {}).get("건드릴 파일", ""))
                    if p.replace("\\", "/") not in covered and not machine_check.TEST_HINT.search(p.replace("\\", "/")) and not re.search(r"[*?\[]", p)]
        if rest:
            where = [row for f in rest for row in signal_places(f, changed.get(f, 1))]
            out.append(_place(t, rest, [], opinions, True, where=where, signals=signal_rows(rest)))
    else:
        for path in sorted(set(hit_files) - covered):
            out.append(_place(t, [path], [], opinions, True, where=signal_places(path, 1), signals=signal_rows([path])))
    return out


def _measured_places(run_dir, t, measure, warnings):
    """`_task_places`에서 보류·백로그는 보안 곳만 남긴다. 내린 task에 새 질문을 늘리지 않는다."""
    found = _task_places(run_dir, t, measure, warnings)
    return found if t.get("status") == kinds.DONE else [p for p in found if p["보안"] == "예"]


def _risk(p):
    return (0 if p["의견"] == PROBLEM else 1 if p["_third"] else 2, RISK_ORDER.index(p["종류"]), p["_follows"], p["task"], p["파일"])


def _order(found, delegated):
    """보안 곳이 앞이고 상한과 따로 센다. 보안 밖은 위험 순이고 상한을 넘기지 않는다. 위임 중에는 보안 곳만 기다린다."""
    security = sorted((p for p in found if p["보안"] == "예"), key=lambda p: (p["의견"] != PROBLEM, p["task"], p["파일"]))
    plain = sorted((p for p in found if p["보안"] != "예"), key=_risk)
    card = 0
    for p in security:
        card += 1
        p["카드"] = str(card)
    for n, p in enumerate(plain):
        if delegated:
            p["처리"], p["카드"] = LEFT_DELEGATED, ""
        elif n >= PLACE_CAP:
            p["처리"], p["카드"] = LEFT_CAP, ""
        else:
            card += 1
            p["카드"] = str(card)
    return security + plain


def collect(run_dir, tid, measure=None, warnings=None):
    """흐름의 곳을 새로 계산한다(쓰지 않는다). 판단 번호는 곳 안에서 b1부터 매긴다.
    measure에 신호를 재지 못한 task를, warnings에 판단에 닿지 않은 판정자 줄을 담는다."""
    tasks = devflow_lib.load_tasks(run_dir)
    measure = [] if measure is None else measure
    warnings = [] if warnings is None else warnings
    found = []
    third = _third_same(tasks)
    asked = _asked_keys(tasks, run_dir, tid)
    for t in measure_tasks(tasks, tid):
        for p in _measured_places(run_dir, t, measure, warnings):
            p["_third"] = any(prefix and j["text"].startswith(prefix) for prefix in third.get(t["id"], ()) for j in p["판단"])
            if p["key"] not in asked:
                found.append(p)
    # 위임은 결정을 맡긴 층(L1)이 있을 때만 일반 곳을 남긴다. 명령만 맡긴 실행은 카드가 그대로 온다
    ordered = _order(found, "L1" in delegation.confirmed_levels(run_dir))
    for p in ordered:
        for n, j in enumerate(p["판단"], 1):
            j["b"] = "b{}".format(n)
    return ordered


# ---------------------------------------------------------------- places.md


def path_of(run_dir, tid):
    return os.path.join(run_dir, "tasks", tid, PLACES_FILE)


def render(tid, flow, plist, delegated, unmeasured=(), warnings=(), measured=(), reasons=(), stamps=()):
    lines = ["# 코드 확인 곳: {} {}".format(tid, flow), "",
             "- 위임: {}".format(", ".join(delegated) or "없음"), "- 재지 못함: {}".format(", ".join(unmeasured) or "없음"),
             "- {}: {}".format(MEASURED_LABEL, ", ".join(measured) or "없음")]
    lines += ["- {}: {} | {}".format(MEASURED_AT, task, mark) for task, mark in stamps]
    lines += ["- {}: {} | {}".format(GAP_REASON, task, why) for task, why in reasons]
    lines += ["- 닿지 않음: " + devflow_lib.mask_line(w) for w in warnings] + [""]
    for p in plist:
        lines.append("## " + p["key"])
        for label in ("카드", "task", "커밋", "부류", "보안", "종류"):
            lines.append("- {}: {}".format(label, p.get(label, "")))
        lines.append("- 파일: " + ", ".join(p["파일"]))
        lines.append("- 위치: " + ", ".join(p["위치"]))
        for label in ("발췌", "의견", "처리", "답"):
            lines.append("- {}: {}".format(label, p.get(label, "")))
        lines += ["- 신호: " + s for s in p["신호"]]
        lines += ["- {}: {} | {} | {}".format(j["b"], j["kind"], j["where"], j["text"]) for j in p["판단"]]
        lines += ["- 의견 줄: " + raw for raw in p["의견 줄"]]
        lines.append("")
    return "\n".join(lines)


def read(run_dir, tid):
    """places.md의 곳 목록(쓴 차례). 파일이 없으면 빈 목록."""
    path = path_of(run_dir, tid)
    if not os.path.isfile(path):
        return []
    out = []
    for key, body in devflow_lib.sections(devflow_lib.read_text(path)).items():
        p = {"key": key, "신호": [], "판단": [], "의견 줄": [], "파일": [], "위치": []}
        for line in body.splitlines():
            label, _, value = line[2:].partition(":") if line.startswith("- ") else ("", "", "")
            value = value.strip()
            if label in ("파일", "위치"):
                p[label] = [v.strip() for v in value.split(",") if v.strip()]
            elif label == "신호" or label == "의견 줄":
                p[label].append(value)
            elif re.fullmatch(r"b\d+", label):
                kind, where, text = (value.split(" | ", 2) + ["", ""])[:3]
                p["판단"].append({"b": label, "kind": kind, "where": where, "text": text})
            elif label:
                p[label] = value
        out.append(p)
    return out


def write_places(run_dir, tid, plist, delegated, unmeasured=(), warnings=(), measured=()):
    tasks = devflow_lib.load_tasks(run_dir)
    reasons = [(task, gap_cause(run_dir, tasks[task]) or GAP_GIT) for task in unmeasured if task in tasks]
    stamps = [(task, devflow_lib.commit_mark(tasks[task])) for task in measured if task in tasks]
    devflow_lib.write_text(path_of(run_dir, tid), render(tid, tasks[tid].get("flow", ""), plist, delegated, unmeasured, warnings, measured, reasons, stamps))


def note_lines(run_dir, tid):
    """places.md 머리의 재지 못함과 닿지 않음을 사람이 볼 줄로."""
    head = devflow_lib.read_text(path_of(run_dir, tid)).split("\n## ", 1)[0] if os.path.isfile(path_of(run_dir, tid)) else ""
    out = []
    for line in head.splitlines():
        if line.startswith("- 재지 못함: ") and line != "- 재지 못함: 없음":
            reasons = gap_reasons(run_dir, tid)
            named = ["{}({})".format(v.strip(), reasons[v.strip()]) if v.strip() in reasons else v.strip() for v in line.split(": ", 1)[1].split(",")]
            out.append("! 보안 신호를 재지 못함: {} (그 코드는 신호로 올리지 못했다)".format(", ".join(named)))
        elif line.startswith("- 닿지 않음: "):
            out.append("! 판정자 줄이 판단에 닿지 않음: " + line.split(": ", 1)[1])
    return out


def _head_tasks(run_dir, tid, label):
    head = devflow_lib.read_text(path_of(run_dir, tid)).split("\n## ", 1)[0] if os.path.isfile(path_of(run_dir, tid)) else ""
    for line in head.splitlines():
        if line.startswith("- {}: ".format(label)) and line != "- {}: 없음".format(label):
            return [v.strip() for v in line.split(": ", 1)[1].split(",") if v.strip()]
    return []


def unmeasured_tasks(run_dir, tid):
    """places.md 머리의 재지 못한 task."""
    return _head_tasks(run_dir, tid, "재지 못함")


def measured_tasks(run_dir, tid):
    """places.md 머리의 고정할 때 잰 task. 그 뒤에 끝난 task는 여기 없다."""
    return _head_tasks(run_dir, tid, MEASURED_LABEL)


def late_tasks(run_dir, tid, tasks):
    """곳을 고정할 때 재지 않은, 재야 할 코드 task(`measure_tasks`). 어떤 측정도 없었으므로 재지 못함이다."""
    if not os.path.isfile(path_of(run_dir, tid)):
        return []
    measured = measured_tasks(run_dir, tid)
    return [o["id"] for o in measure_tasks(tasks, tid) if o["id"] not in measured]


def changed_tasks(run_dir, tid, tasks):
    """잰 뒤에 커밋이 바뀐 task. 잰 값은 그때의 코드에 대한 것이다. 도장이 없는 머리는 어느 코드를 쟀는지 모르므로 보지 않는다."""
    return [task for task, mark in _head_pairs(run_dir, tid, MEASURED_AT).items() if task in tasks and devflow_lib.commit_mark(tasks[task]) != mark]


def gap_tasks(run_dir, tid, tasks):
    """재지 못한 task: 머리의 `재지 못함`, 고정 뒤 끝난 task, 잰 뒤에 커밋이 바뀐 task. 흐름 리뷰의 표시(`flow_review.code_line`)와 관문(`gap_rows`)이 같은 값을 쓴다."""
    return list(dict.fromkeys(unmeasured_tasks(run_dir, tid) + late_tasks(run_dir, tid, tasks) + changed_tasks(run_dir, tid, tasks)))


def _head_lines(run_dir, tid, label):
    head = devflow_lib.read_text(path_of(run_dir, tid)).split("\n## ", 1)[0] if os.path.isfile(path_of(run_dir, tid)) else ""
    return [line.split(": ", 1)[1] for line in head.splitlines() if line.startswith("- {}: ".format(label))]


def _head_pairs(run_dir, tid, label):
    """머리의 `- {label}: {T} | {값}` 줄을 {T: 값}으로."""
    return dict(tuple(v.strip() for v in row.split(" | ", 1)) for row in _head_lines(run_dir, tid, label) if " | " in row)


def gap_reasons(run_dir, tid):
    """places.md 머리의 {task: 재지 못한 까닭}."""
    return _head_pairs(run_dir, tid, GAP_REASON)


def _retried(run_dir, tid, task, tasks):
    """메인이 지금 커밋으로 이 task를 다시 재 보았는가. 커밋을 고친 뒤에는 다시 재야 사람에게 묻는다."""
    return task in tasks and _head_pairs(run_dir, tid, GAP_RETRIED).get(task) == devflow_lib.commit_mark(tasks[task])


def tried_lines(run_dir, tid):
    """메인이 다시 재며 한 일. 비어 있으면 아직 사람에게 묻지 않는다."""
    return _head_lines(run_dir, tid, GAP_TRIED)


def gap_rows(run_dir, t, tasks=None):
    """답을 기다리는 재지 못한 task [{"task", "title", "what", "why", "files"}]. 보안 신호와 시험 변화를 task마다 한 줄로 합친다."""
    if t.get("kind") != "flow-verify" or not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        return []
    tasks = devflow_lib.load_tasks(run_dir) if tasks is None else tasks
    answered = devflow_lib.unmeasured_answers(tasks)
    what = {}
    for task in gap_tasks(run_dir, t["id"], tasks):
        if task not in answered:
            what.setdefault(task, []).append("보안 신호")
    for row in devflow_lib.flow_test_rows(t, tasks):
        if devflow_lib.test_unmeasured_open(row):
            what.setdefault(row["task"], []).append("시험 변화")
    reasons = gap_reasons(run_dir, t["id"])
    late, changed = late_tasks(run_dir, t["id"], tasks), changed_tasks(run_dir, t["id"], tasks)
    out = []
    for task in sorted(what):
        if task in tasks:
            o = tasks[task]
            out.append({"task": task, "title": o.get("title", ""), "what": what[task], "why": reasons.get(task) or gap_cause(run_dir, o) or (GAP_LATE if task in late else GAP_CHANGED if task in changed else GAP_NOT_RUN),
                        "files": devflow_lib.touch_paths(o.get("_sections", {}).get("건드릴 파일", ""))})
    return out


def gap_block(run_dir, t, tasks=None):
    """재지 못한 task를 사람에게 묻는 줄. 메인이 아직 다시 재지 않았으면 메인이 할 일만 낸다. 추천을 달지 않는다."""
    tasks = devflow_lib.load_tasks(run_dir) if tasks is None else tasks
    rows = gap_rows(run_dir, t, tasks)
    if not rows:
        return []
    tried = tried_lines(run_dir, t["id"])
    stale = [r for r in rows if not _retried(run_dir, t["id"], r["task"], tasks)]
    if stale:
        return ["! 재지 못한 코드 task {}: {}. 메인이 기록을 고치고 `screen.py … --places --remeasure`를 돌린 뒤에도 남으면 묻는다".format(
            len(stale), ", ".join("{}({})".format(r["task"], r["why"]) for r in stale))]
    out = ["■ 코드 확인: 보지 못한 코드 {}곳".format(len(rows))]
    for r in rows:
        out += ["{} {}".format(r["task"], r["title"]), "파일 범위: {}".format(", ".join(r["files"]) or "적히지 않음"),
                "못 본 것: {}".format(", ".join(r["what"])), "못 본 까닭: {} ({})".format(GAP_WORDS.get(r["why"], r["why"]), r["why"]),
                "메인이 해 본 일: {}".format(" / ".join(row.split(" | ", 1)[-1] for row in tried)),
                "`{}`이라고 답하시면 그 코드를 보지 않고 합칩니다. `보류`도 받습니다.".format(devflow_lib.UNMEASURED_ANSWER),
                '기록: --record "{}{}|{}|{{원문}}"'.format(devflow_lib.UNMEASURED_POINT, r["task"], devflow_lib.UNMEASURED_ANSWER), ""]
    return out[:-1]


def unmeasured_answer_problem(run_dir, t, task, decision, quote):
    """`코드 확인 재지 못함 {T}` 답을 받을 수 없는 까닭. 받으면 빈 글."""
    if decision.strip() != devflow_lib.UNMEASURED_ANSWER:
        return "답은 `{}`뿐이다(그 밖은 `보류`로 처리한다)".format(devflow_lib.UNMEASURED_ANSWER)
    if not devflow_lib.person_quote(quote):
        return "빈 답과 위임의 말은 코드를 보지 않고 합치는 답으로 받지 않는다"
    tasks = devflow_lib.load_tasks(run_dir)
    if task not in [r["task"] for r in gap_rows(run_dir, t, tasks)]:
        return "{}는 답을 기다리는 재지 못한 task가 아니다".format(task)
    if not _retried(run_dir, t["id"], task, tasks):
        return "메인이 먼저 기록을 고치고 지금 커밋으로 `screen.py … --places --remeasure`를 돌린다"
    return ""


def _refresh(old, p, next_card):
    """기존 곳을 다시 잰 값으로 고친다. 신호는 올리는 데만 쓴다.
    답한 곳은 답한 커밋과 같거나 신호가 없으면 그대로다. 남긴 곳의 답은 보안 신호에 대한 답이 아니므로 신호가 새로 나오면 올리고, 이미 보안 곳이고 같은 커밋이면 다시 묻지 않는다."""
    same, secure = old.get("커밋", "") == p["커밋"], p["보안"] == "예"
    if old.get("처리") == ANSWERED and (same or not secure):
        return
    if old.get("처리") in (LEFT_BULK, LEFT_UNJUDGED) and same and (not secure or old.get("보안") == "예"):
        return
    old.update({"커밋": p["커밋"], "신호": p["신호"], "위치": p["위치"]})
    if secure:
        old.update({"보안": "예", "처리": WAITING, "답": "", "카드": old.get("카드") or next_card()})


def _merge_found(plist, found, delegated, asked):
    """다시 잰 task의 곳을 더한다. 키는 파일 목록이 정하므로 바뀌지 않고, 기존 곳은 `_refresh`가 고친다."""
    def next_card():
        return str(max([int(p["카드"]) for p in plist if str(p.get("카드", "")).isdigit()] or [0]) + 1)

    for p in found:
        old = find(plist, p["key"])
        if old is None and p["key"] in asked:
            continue
        if old is not None:
            _refresh(old, p, next_card)
            continue
        for n, j in enumerate(p["판단"], 1):
            j["b"] = "b{}".format(n)
        plain = sum(1 for o in plist if o.get("보안") != "예" and o.get("카드"))
        if p["보안"] == "예" or (not delegated and plain < PLACE_CAP):
            p["카드"] = next_card()
        else:
            p["처리"], p["카드"] = LEFT_DELEGATED if delegated else LEFT_CAP, ""
        plist.append(p)


def remeasure(run_dir, tid, tried=""):
    """재지 못한 task, 고정 뒤 끝난 task, 잰 뒤에 커밋이 바뀐 task만 다시 잰다(사용자 결정: 메인이 기록을 고쳐 다시 재고, 그래도 못 재면 사람에게 묻는다). 보안 신호와 시험 변화를 함께 잰다.
    잰 task는 곳을 더하고 `재지 못함`에서 빠진다. 보류로 내려간 task도 커밋 값이 비었으면 코드를 모르는 것이므로 빠지지 않는다. 시도는 머리에 남아 묻는 화면에 실린다.
    시험 변화는 줄이 없는 task, 다른 커밋으로 바뀐 task, `no_change`로 잰 뒤 커밋을 적은 task를 다시 잰다. 빈 값을 채운 task는 자체검증에서 잰 줄을 그대로 쓴다."""
    tasks = devflow_lib.load_tasks(run_dir)
    verify = tasks[tid]
    plist = read(run_dir, tid)
    asked = _asked_keys(tasks, run_dir, tid)
    delegated = "L1" in devflow_lib.delegation_levels(run_dir)
    targets = gap_tasks(run_dir, tid, tasks)
    measured = measured_tasks(run_dir, tid)
    stamps = _head_pairs(run_dir, tid, MEASURED_AT)
    moved = [task for task in changed_tasks(run_dir, tid, tasks) if stamps[task] != devflow_lib.UNMEASURED_NO_COMMIT or devflow_lib.no_change(tasks[task])]
    still, reasons = [], {}
    for task in targets:
        o = tasks.get(task)
        if o is None:
            continue
        cause = remeasure_cause(run_dir, o)
        if cause:
            still.append(task)
            reasons[task] = cause
        else:
            _merge_found(plist, _measured_places(run_dir, o, [], []), delegated, asked)
    unread = [row["task"] for row in devflow_lib.flow_test_rows(verify, tasks) if row["change"] == devflow_lib.TEST_UNMEASURED and row["task"] in tasks]
    for task in list(dict.fromkeys(unread + moved)):
        o = tasks[task]
        cause = remeasure_cause(run_dir, o)
        if not cause:
            try:
                machine_check.record_test_changes(code_folder(run_dir, o), o, str(o.get("commit", "")).strip())
            except (machine_check.MeasureError, OSError):
                cause = GAP_GIT
        elif task in moved:
            devflow_lib.clear_test_changes(o)   # 앞 커밋의 줄을 지금 커밋을 잰 것으로 두지 않는다
        if cause:
            reasons[task] = cause
    stamps.update((k, devflow_lib.commit_mark(tasks[k])) for k in targets if k in tasks)
    _rewrite(run_dir, tid, plist)
    path = path_of(run_dir, tid)
    head, _, body = devflow_lib.read_text(path).partition("\n## ")
    kept = [line for line in head.splitlines() if not line.startswith(("- 재지 못함: ", "- {}: ".format(MEASURED_LABEL), "- {}: ".format(MEASURED_AT), "- {}: ".format(GAP_REASON), "- {}: ".format(GAP_RETRIED)))]
    at = next((i for i, line in enumerate(kept) if line.startswith("- 위임: ")), len(kept) - 1) + 1
    kept[at:at] = (["- 재지 못함: {}".format(", ".join(still) or "없음"), "- {}: {}".format(MEASURED_LABEL, ", ".join(measured + [k for k in targets if k not in measured]) or "없음")]
                   + ["- {}: {} | {}".format(MEASURED_AT, k, v) for k, v in sorted(stamps.items())]
                   + ["- {}: {} | {}".format(GAP_REASON, k, v) for k, v in sorted(reasons.items())]
                   + ["- {}: {} | {}".format(GAP_RETRIED, k, devflow_lib.commit_mark(tasks[k])) for k in sorted(reasons)])
    while kept and not kept[-1].strip():
        kept.pop()
    kept.append("- {}: {} | {}".format(GAP_TRIED, _now(), devflow_lib.mask_line(" ".join((tried or TRIED_DEFAULT).split()))))
    devflow_lib.write_text(path, "\n".join(kept) + "\n" + ("\n## " + body if body else ""))


def _rewrite(run_dir, tid, plist):
    """처리와 답만 바꿔 다시 쓴다. 머리의 위임 줄과 차례는 그대로다."""
    path = path_of(run_dir, tid)
    head = devflow_lib.read_text(path).split("\n## ", 1)[0].rstrip("\n").split("\n")
    body = render(tid, "", plist, "").split("\n## ", 1)
    devflow_lib.write_text(path, "\n".join(head) + "\n\n## " + body[1] if len(body) > 1 else "\n".join(head) + "\n")


def waiting(plist):
    return [p for p in plist if p.get("처리") == WAITING]


def total_cards(plist):
    return sum(1 for p in plist if p.get("카드"))


def find(plist, key):
    return next((p for p in plist if p["key"] == key), None)


def by_card(plist, number):
    return next((p for p in plist if p.get("카드") == str(number)), None)


def left_lines(plist):
    """남긴 곳의 위치 줄(화면과 마무리 리뷰)."""
    return ["- {} {} {}".format(p["처리"], p["task"], ", ".join(p["위치"])) for p in plist if p.get("처리", "").startswith("남김")]


def fix_judgments(t):
    """흐름 뒤 수정의 판단(설계 11.1절 「흐름 뒤 `fix`」): (건수, 위치, `지금 문제 있음` 의견 줄 그대로). 곳을 만들지 않는다."""
    judgments, lines = _judgments(t), _judge_lines(t)
    hidden = [cells[0] for name, cells, _ in lines if name == "숨은 판단" and cells]
    problems = [raw for notes in _opinions(lines).values() for raw in (n["raw"] for n in notes if n["verdict"] == PROBLEM)]
    return len(judgments) + len(hidden), sorted({j["where"] for j in judgments}), problems


def answered_count(run_dir, tid):
    """그 흐름 리뷰에서 사람이 코드로 본 곳의 수."""
    return sum(1 for p in read(run_dir, tid) if p.get("처리") == ANSWERED)


def run_left(run_dir, only=None):
    """실행 전체의 남긴 곳: 건수, 위치, `지금 문제 있음`이 든 곳의 의견 줄 그대로(설계 11.1절 「남긴 곳」, 마무리 리뷰가 싣는다). only는 회차의 task id 집합이다."""
    summary = {"count": 0, "where": [], "problems": []}
    tasks_dir = os.path.join(run_dir, "tasks")
    for tid in sorted(os.listdir(tasks_dir)) if os.path.isdir(tasks_dir) else ():
        if only is not None and tid not in only:
            continue
        plist = read(run_dir, tid)
        lines = left_lines(plist)
        summary["count"] += len(lines)
        summary["where"] += lines
        for p in plist:
            if p.get("처리", "").startswith("남김") and p.get("의견") == PROBLEM:
                summary["problems"] += [raw for raw in p["의견 줄"] if PROBLEM in raw]
        gaps = unmeasured_tasks(run_dir, tid)
        if gaps:
            answered = devflow_lib.unmeasured_answers(devflow_lib.load_tasks(run_dir))
            merged = ["- 재지 못함(보지 않고 합침) {}".format(task) for task in gaps if task in answered]
            summary["count"] += len(merged)
            summary["where"] += merged
    return summary


def screen_lines(run_dir, tid):
    """흐름별 검증 화면에 싣는 줄. `places.md`가 없으면 빈 목록. 번호와 칸 수에 들지 않는다."""
    if not os.path.isfile(path_of(run_dir, tid)):
        return []
    plist = read(run_dir, tid)
    left = left_lines(plist)
    head = "■ 코드 확인: 보일 곳 {}, 답 {}, 남긴 곳 {}".format(total_cards(plist), sum(1 for p in plist if p.get("처리") == ANSWERED), len(left))
    open_rows = waiting(plist)
    return [head] + left + note_lines(run_dir, tid) + (["! 답 없는 곳 {}: {} (이 검증은 답이 있어야 완료된다)".format(len(open_rows), ", ".join(p["key"] for p in open_rows))] if open_rows else [])


def completion_block(run_dir, t):
    """흐름별 검증을 완료로 닫지 못하는 이유(없으면 빈 글). 합치기 전에 보안 곳과 답 없는 시험 끄기·삭제를 기다리고, 걸린 것을 한 번씩 함께 말한다."""
    if t.get("kind") != "flow-verify" or not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        return ""
    plist, why = read(run_dir, t["id"]), []
    if not os.path.isfile(path_of(run_dir, t["id"])):
        unmeasured = []
        if collect(run_dir, t["id"], unmeasured) or unmeasured:
            why.append("코드 확인 곳이 있거나 신호를 재지 못했는데 `screen.py … --places`를 돌리지 않음")
    rows = waiting(plist)
    if rows:
        why.append("지금 답 없는 코드 확인 곳이 있음: {} (`보류`는 받는다)".format(", ".join(p["key"] for p in rows)))
    objected = devflow_lib.open_objection(t, devflow_lib.load_tasks(run_dir))
    if objected:
        why.append("{} {}에 고치는 task가 없음(`new --from-answer {}`로 만들거나, 철회면 `--record \"{}|항목|원문\"`을 남긴다)".format(
            devflow_lib.REVIEW_OBJECTION, objected, t["id"], devflow_lib.OBJECTION_WITHDRAWN))
    tasks = devflow_lib.load_tasks(run_dir)
    gaps = gap_rows(run_dir, t, tasks)
    if gaps:
        why.append("재지 못한 코드 task의 답이 없음: {}. 메인이 기록을 고쳐 `screen.py … --places --remeasure`로 다시 재고, 그래도 남으면 `--record \"{}{{T}}|{}|{{원문}}\"`을 받는다(`보류`는 받는다)".format(
            ", ".join("{}({})".format(r["task"], r["why"]) for r in gaps), devflow_lib.UNMEASURED_POINT, devflow_lib.UNMEASURED_ANSWER))
    removals = [r for r in devflow_lib.unanswered_test_removals(t) if not r.split("] ", 1)[-1].startswith(devflow_lib.TEST_UNMEASURED + " |")]
    if removals:
        why.append("답 없는 시험 끄기·삭제가 있음(--record \"{}|{{키}}=받아들임|{{원문}}\"을 먼저 남긴다): {}".format(
            devflow_lib.TEST_CHANGE_POINT, " / ".join(removals)))
    return " / ".join(why)


# ---------------------------------------------------------------- 답


def _single_value(text):
    """조각 하나의 (값 이름, 글), 꼴이 어긋나면 None. 글이 `:`와 공백뿐이면 빈 글이다."""
    text = text.strip()
    piece = devflow_lib._answer_piece(text)
    if "task" in piece or "objection" in piece or "except" in piece or "items" in piece:
        return None
    piece = devflow_lib._answer_settled(piece, ANSWER_NAMES, ANSWER_TEXT)
    if piece is None:
        return None
    if "number" in piece:
        n = piece["number"]
        return (ANSWER_NUMBERS[n - 1], None) if 1 <= n <= len(ANSWER_NUMBERS) else None
    if "rest" in piece:
        return (REST, None)
    value = piece.get("value")
    if value == "남김" or value is None:
        return None
    if str(value).isdigit():
        n = int(value)
        return (ANSWER_NUMBERS[n - 1], None) if "item" not in piece and 1 <= n <= len(ANSWER_NUMBERS) else None
    if "item" in piece and (not 1 <= piece["item"] <= len(ANSWER_NUMBERS) or ANSWER_NUMBERS[piece["item"] - 1] != value):
        return None
    written = piece.get("text")
    return (value, written.strip() if written and written.strip(" :") else None)


def _value_text(value, text):
    if value == FIX_ONLY:
        return "{} : {}".format(value, " ".join(text.split()).replace("|", "/"))
    if value == UNJUDGED:
        return "{} {}".format(value, " ".join(text.split()).replace("|", "/"))
    return value


def resolve(place, text, tree_seen=False, has_code=True):
    """카드 답 원문을 푼다. {"show": "full"|"tree"} / {"decision": 결정 칸} / None(메인이 되묻는다).
    맨 숫자는 그 카드의 답 번호이고, 판단이 여럿이면 `b1 1, b2 이 코드만 고침 : …`처럼 판단마다 받는다."""
    text = (text or "").strip()
    if FULL_ANSWER.match(text):
        return {"show": "full"}
    numbers = [j["b"] for j in place["판단"]]
    rows, pending = [], []
    # 판단을 말하지 않은 글 답은 쉼표까지 글이다
    for piece in [text] if TEXT_ANSWER_HEAD.match(text) else devflow_lib._answer_pieces(text):
        if BARE_TARGET.match(piece):
            pending.append(piece)
            continue
        m = PIECE_TARGET.match(piece)
        got = _single_value(m.group(2) if m else piece)
        if got is None:
            return None
        targets = pending + ([m.group(1)] if m else [])
        pending = []
        rows.append((targets, got))
    if pending or not rows:
        return None
    if any(v[0] == REST for _, v in rows):
        if len(rows) > 1 or rows[0][0] or place.get("보안") == "예":
            return None
        return {"decision": REST}
    if any(v[0] in ANSWER_TEXT and not v[1] for _, v in rows) or (not has_code and any(v[0] == FINE for _, v in rows)):
        return None
    if not tree_seen and any(v[0] == UNJUDGED and "구조" in v[1] for _, v in rows):
        return {"show": "tree"}
    fix = any(v[0] == FIX_ONLY for _, v in rows)
    if len(rows) == 1 and not rows[0][0]:
        return {"decision": _value_text(*rows[0][1]), "fix": fix}   # 판단 전체에 같은 답
    named = [b for bs, _ in rows for b in bs]
    if sorted(named) != sorted(numbers) or any(not bs for bs, _ in rows):
        return None
    return {"decision": " ".join("{}={}".format(",".join(bs), _value_text(*v)) for bs, v in rows), "fix": fix}


def _decision_parts(decision):
    """결정 칸을 [(판단 번호들, 값)]으로. 맨 앞이 표지가 아니면 그 곳 전체의 값 하나다."""
    marks = list(DECISION_TARGET.finditer(decision))
    if not marks or marks[0].start() != 0:
        return [([], decision)]
    return [(m.group(1).split(","), (decision[m.end():marks[at + 1].start()] if at + 1 < len(marks) else decision[m.end():]).strip())
            for at, m in enumerate(marks)]


def decision_problem(place, decision, has_code=True):
    """`--record "코드 확인 {키}|{결정}|{원문}"`의 결정 칸 검사. 문제가 없으면 빈 글."""
    if place.get("처리") != WAITING:
        return "이 곳은 이미 처리됨({})".format(place.get("처리"))
    decision = decision.strip()
    if not decision:
        return "결정 칸이 비었음"
    if decision == REST:
        return "보안 곳은 남기지 않는다" if place.get("보안") == "예" else ""
    parts = _decision_parts(decision)
    for _, value in parts:
        if not _decision_value_ok(value):
            return "결정 칸의 꼴: " + value
        if value == FINE and not has_code:
            return "코드를 보이지 못한 곳은 `{}`을 받지 않는다".format(FINE)
    numbers = [j["b"] for j in place["판단"]]
    named = [b for bs, _ in parts for b in bs]
    return "" if not parts[0][0] or sorted(named) == sorted(numbers) else "답이 빠진 판단이 있음(판단 {})".format(", ".join(numbers))


def _decision_value_ok(value):
    return value == FINE or bool(re.fullmatch(re.escape(FIX_ONLY) + r" : \S.*", value)) or bool(re.fullmatch(re.escape(UNJUDGED) + r" \S.*", value))


def _all_unjudged(decision):
    return all(value.startswith(UNJUDGED) for _, value in _decision_parts(decision))


def apply_answer(run_dir, tid, key, decision):
    """답을 places.md에 적는다. `나머지 남김`은 보안 밖의 기다리는 곳을 함께 남긴다."""
    plist = read(run_dir, tid)
    place = find(plist, key)
    if decision.strip() == REST:
        for p in waiting(plist):
            if p.get("보안") != "예":
                p["처리"] = LEFT_BULK
        place["답"] = REST
    else:
        place["처리"] = LEFT_UNJUDGED if _all_unjudged(decision) else ANSWERED
        place["답"] = decision.strip()
    _rewrite(run_dir, tid, plist)
    return plist


def next_card_line(plist):
    rows = waiting(plist)
    if not rows:
        return "카드 끝: 지금 화면과 질문을 낸다"
    return "다음 카드: {} {}".format(rows[0].get("카드", ""), rows[0]["key"])


# ---------------------------------------------------------------- 카드


def _file_rows(folder, sha, path):
    """task 커밋의 파일 (줄 목록, 메모)(설계 6.16절 「발췌의 시점」). 지운 파일은 커밋 앞의 글이다. 못 읽거나 이진 파일이면 줄 목록이 None이다."""
    if not sha:
        return None, ""
    ok, text = _git(folder, "show", "{}:{}".format(sha, path))
    note = ""
    if not ok:
        ok, text = _git(folder, "show", "{}^:{}".format(sha, path))
        note = DELETED_NOTE
    if not ok:
        return None, ""
    if "\0" in text:
        return None, BINARY_NOTE
    return text.splitlines(), note


def _excerpts(run_dir, t, place, budget):
    """(발췌 줄, 가린 줄 수, 코드를 보였는가). 위치를 가운데 둔 창이고 위치가 많으면 줄 수를 나누되 바닥을 지키며 앞 몇 개만 싣는다.
    같은 파일의 겹치는 창은 합친다. 없는 줄은 `! 위치 없음`으로 낸다. 비밀값은 가린다."""
    folder, sha = code_folder(run_dir, t), place.get("커밋", "")
    wheres = list(dict.fromkeys(place["위치"]))
    keep = wheres[:max(1, budget // EXCERPT_FLOOR)]
    radius = max(1, (budget // max(1, len(keep)) - 1) // 2)
    by_file = {}
    for where in keep:
        path, line = _where(where)
        by_file.setdefault(path, []).append((where, line))
    out, masked, shown = [], 0, False
    for path, spots in by_file.items():
        rows, note = _file_rows(folder, sha, path)
        if rows is None:
            out.append("{}: {}".format(path, note) if note else "! 발췌 못 함: {} (커밋 {})".format(path, sha or "없음"))
            continue
        clean, _ = devflow_lib.mask_lines(rows)
        windows, named = [], []
        for where, line in spots:
            if line is not None and line > len(rows):
                out.append("! 위치 없음: {} (파일은 {}줄)".format(where, len(rows)))
                continue
            center = line or 1
            first, last = max(1, center - radius), min(len(rows), center + radius)
            named.append(where)
            if windows and first <= windows[-1][1] + 1:
                windows[-1][1] = max(windows[-1][1], last)
            else:
                windows.append([first, last])
        if not windows:
            continue
        shown = True
        out.append("{} (커밋 {}){}".format(", ".join(named), sha, " " + note if note else ""))
        out.append("```")
        for at, (first, last) in enumerate(sorted(windows)):
            if at:
                out.append("…")
            out += ["{} {}".format(n, clean[n - 1]) for n in range(first, last + 1)]
            masked += sum(1 for n in range(first, last + 1) if clean[n - 1] != rows[n - 1])
        out.append("```")
    if len(wheres) > len(keep):
        out.append("위치 {}개 더: {}".format(len(wheres) - len(keep), ", ".join(wheres[len(keep):])))
    return out, masked, shown


def code_shown(run_dir, place):
    """이 곳의 코드를 한 줄이라도 보일 수 있는가. 못 보이면 `문제 없음`을 받지 않는다."""
    t = devflow_lib.load_tasks(run_dir).get(place["task"])
    return bool(t) and _excerpts(run_dir, t, place, EXCERPT)[2]


def _moved_files(run_dir, t, place):
    """흐름 끝에서 task 커밋과 달라진 파일."""
    folder, sha = code_folder(run_dir, t), place.get("커밋", "")
    out = []
    for path in place["파일"]:
        ok, text = _git(folder, "diff", "--name-only", sha, "HEAD", "--", path) if sha else (False, "")
        if ok and text.strip():
            out.append(path)
    return out


def _title(place):
    files = place["파일"]
    head = files[0].rsplit("/", 1)[-1] if files else "코드"
    return head + (" 외 {}개 파일".format(len(files) - 1) if len(files) > 1 else "")


def card_text(run_dir, tid, place, plist, full=False):
    """한 장. 모바일에서도 읽히게 라벨 줄과 값 줄을 나누고 표를 쓰지 않는다. 답에 추천을 달지 않는다."""
    tasks = devflow_lib.load_tasks(run_dir)
    t = tasks.get(place["task"], {})
    flow = tasks.get(tid, {}).get("flow", "")
    head = "코드 확인 {}/{}: {} ({}, {} 흐름)".format(place.get("카드", ""), total_cards(plist), _title(place), place["task"], flow)
    lines = [head, "곳 키: {}".format(place["key"])]
    if place.get("보안") == "예":
        lines.append("보안 곳입니다. 답이 있어야 이 흐름을 합칠 수 있습니다.")
    opinions = _stored_opinions(place)
    lines += ["", "일어난 일"]
    happened = [o["happened"] for o in opinions if o["happened"]]
    lines += happened or ([j["text"] for j in place["판단"]] if place["판단"] else ["판단 기록이 없는 보안 코드입니다"])
    if place["판단"]:
        lines += ["", "판단"]
        lines += ["{} {} ({}, {})".format(j["b"], j["text"], j["kind"], j["where"]) for j in place["판단"]]
    if place["신호"]:
        lines += ["", "보안 신호"] + place["신호"]
    lines += ["", "코드"]
    budget = EXCERPT_FULL if full else int(place.get("발췌") or EXCERPT)
    code_lines, masked, has_code = _excerpts(run_dir, t, place, budget) if t else (["! 발췌 못 함: task 없음"], 0, False)
    lines += code_lines
    if masked:
        lines.append("비밀값 꼴 {}줄 가림".format(masked))
    moved = _moved_files(run_dir, t, place) if t else []
    if moved:
        lines.append("흐름 끝에서 달라짐: " + ", ".join(moved))
    if not full:
        lines.append("코드를 더 보려면: {} 전체".format(place.get("카드", "")))
    lines += ["", "의견"]
    if not opinions:
        lines.append(NO_OPINION)
    for o in opinions:
        lines.append(o["verdict"] or NO_OPINION)
        if o["breaks"]:
            lines.append("깨지는 조건: " + o["breaks"])
        if o["way"]:
            lines.append("저장소에서 같은 문제를 푸는 방식: " + o["way"])
    lines += ["", "답"]
    if has_code:
        lines.append("1 {}".format(FINE))
    else:
        lines.append("코드를 보이지 못해 `{}`은 받지 않습니다".format(FINE))
    lines += ["2 {} : {{무엇을}}".format(FIX_ONLY), "3 {} {{부족한 것}}".format(UNJUDGED)]
    if place.get("보안") != "예":
        lines.append("4 {}".format(REST))
    if len(place["판단"]) > 1:
        lines.append("판단마다 답하려면: b1 1, b2 2 이 코드만 고침 : {무엇을}")
    return "\n".join(lines)


def tree_text(run_dir, tid, place):
    """그 판단 폴더의 파일과 줄 수(설계 11.1절 `--tree`). 커밋 시점이다."""
    t = devflow_lib.load_tasks(run_dir).get(place["task"], {})
    folder, sha = code_folder(run_dir, t) if t else "", place.get("커밋", "")
    lines = ["폴더의 파일과 줄 수"]
    for parent in sorted({p.rsplit("/", 1)[0] if "/" in p else "." for p in place["파일"]}):
        ok, names = _git(folder, "ls-tree", "-r", "--name-only", sha, "--", parent) if sha else (False, "")
        if not ok:
            lines.append("! 표를 만들지 못함: {}".format(parent))
            continue
        rows = names.splitlines()
        lines.append("{} (파일 {}개)".format(parent, len(rows)))
        for name in rows[:TREE_ROWS]:
            text = _file_rows(folder, sha, name)[0]
            lines.append("{} | {}".format(name, len(text) if text is not None else "?"))
        if len(rows) > TREE_ROWS:
            lines.append("(뒤 {}개 생략)".format(len(rows) - TREE_ROWS))
    return "\n".join(lines)


def shown_path(run_dir, tid, key):
    return os.path.join(run_dir, "tasks", tid, "cards", key + ".shown.md")


def tree_path(run_dir, tid, key):
    return os.path.join(run_dir, "tasks", tid, "cards", key + ".tree.md")


def open_card_note(tasks, run_dir):
    """코드 확인을 기다리는 한 줄: 열린 카드(`답 대기: T081 카드 2/5`)나, 카드 사이에 끊겨 답 없는 곳이 남은 것. 없으면 빈 글."""
    for t in tasks.values():
        key = str(t.get("card_open", "") or "").strip()
        if key and t.get("status") == "승인대기":
            plist = read(run_dir, t["id"])
            place = find(plist, key)
            return "답 대기: {} 카드 {}/{} ({})".format(t["id"], place.get("카드", "?") if place else "?", total_cards(plist), key)
    for t in tasks.values():
        rows = waiting(read(run_dir, t["id"])) if t.get("status") == "승인대기" else []
        if rows:
            return "코드 확인 남음: {} {}곳, 다음 --card-open {}".format(t["id"], len(rows), rows[0]["key"])
    return ""


# ---------------------------------------------------------------- 코드 확인에서 온 수정


ORIGIN_KEY = re.compile(r"^사용자 (T\d+) .*?" + re.escape(devflow_lib.CODE_CHECK_ORIGIN) + r" (\S+)")


def answer_record(tasks, tid, key):
    """그 곳의 답 줄의 (시각, 원문). 없으면 ("", "")."""
    point = "{} {}".format(devflow_lib.CODE_CHECK_ORIGIN, key)
    for line in reversed(devflow_lib.record_lines(tasks[tid])):
        f = devflow_lib.record_fields(line)
        if len(f) >= 3 and f[1] == point:
            return f[0], devflow_lib.record_quote(line) or ""
    return "", ""


def fix_body(run_dir, tid, key):
    """`task_set.py new --from-answer {검증} --place {키}`의 본문: 범위는 원문, 건드릴 파일은 곳의 위치, 판정 기준은 고정 문장(설계 6.16절 「고침의 길」).
    (본문 절, 제목, 흐름) 또는 거부 이유 글."""
    place = find(read(run_dir, tid), key)
    if place is None:
        return "곳을 찾지 못함: " + key
    tasks = devflow_lib.load_tasks(run_dir)
    stamp, quote = answer_record(tasks, tid, key)
    if not stamp or FIX_ONLY not in place.get("답", ""):
        return "{}의 답에 `{}`이 없음 — 답을 --record로 먼저 적는다".format(key, FIX_ONLY)
    body = {"범위": "- 코드 확인 {} 답의 요구: \"{}\"".format(key, quote),
            "판정 기준": "1. " + FIX_CRITERION, "건드릴 파일": "\n".join("- " + f for f in place["파일"])}
    return body, "코드 확인 고침: {}".format(_title(place)), tasks[tid].get("flow", "")


def fix_block(run_dir, t):
    """코드 확인에서 온 수정의 승인 화면에 싣는 줄: 원문과 고친 변경의 발췌. 해당 없으면 빈 목록."""
    m = ORIGIN_KEY.match(str(t.get("origin", "") or ""))
    if not m:
        return []
    tid, key = m.group(1), m.group(2)
    tasks = devflow_lib.load_tasks(run_dir)
    quote = answer_record(tasks, tid, key)[1] if tid in tasks else ""
    folder = code_folder(run_dir, t)
    sha = str(t.get("commit", "") or "").strip()
    ok, diff = _git(folder, "show", "--format=", "--unified=3", sha) if sha else _git(folder, "diff", "HEAD", "--unified=3")
    rows, masked = devflow_lib.mask_lines(diff.splitlines())
    out = ["■ 코드 확인에서 고친 코드 ({})".format(key), "  답 원문: \"{}\"".format(devflow_lib.mask_line(quote))]
    if not ok:
        return out + ["  ! 변경을 읽지 못함"]
    if masked:
        out.append("  비밀값 꼴 {}줄 가림".format(masked))
    out += ["  " + line for line in rows[:FIX_DIFF_LINES]]
    if len(rows) > FIX_DIFF_LINES:
        out.append("  (뒤 {}줄 생략)".format(len(rows) - FIX_DIFF_LINES))
    return out
