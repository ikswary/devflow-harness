r"""배포 계획 재사용. 유지로 끝난 배포의 계획에서 작성자가 고정으로 표시한 항목을 절차서로 저장하고, 다음 계획은 기계가 항목마다 재사용을 가른다.

1.2.0부터 시작한 실행에만 적용한다. 옛 실행은 지금 그대로고, 절차서가 없으면 동작은 지금과 같다.

절차서: `_workspace\policies\deploy\{환경}.md`(`docs-state.md`와 같은 층). dev와 운영은 파일이 다르고 섞어 쓰지 않는다.
  항목은 명령 줄 C, 되돌리기 줄 R, 사전 조건 P, 공통 배포 뒤 확인 V다. 설명 글은 재사용하지 않고 작성자가 쓴다.
  항목마다 그 항목이 인용한 근거와 그때의 해시를 묶는다. 근거는 파일(blob 해시)이거나, 문서의 절이나 줄을 인용했으면 그 절
  (`docs/deploy.md#배포 > 7.2 순서`, 제목의 위치까지 키이고 값은 절 글자의 해시)이다. 위치를 가리지 못하면 파일 전체에 묶는다.
  실행마다 달라지는 값은 자리 값 `{{이름}}`으로 바꾼다. 경로는 꼴마다 `{{배포 폴더}}`(D:/x), `{{배포 폴더:bash}}`(/d/x),
  `{{배포 폴더:win}}`(D:\x)이고 짧은 해시는 `{{올릴 커밋:7}}`, 다른 명령을 가리키는 번호는 `{{줄:C4}}`다. 머리의 digest가 본문과 어긋나면 손상이다.

첫 계획의 저장: 작성자가 본문 「고정 항목」에 적은 명령·되돌리기 줄(`- 명령 1~3: 읽기`, `- 명령 4: 쓰기 | 근거`)과 `[고정]`을 붙인 사전 조건·확인 행만 남긴다.
  표시가 없으면 이번 실행 몫이다. 종류를 적지 않은 줄은 쓰기다.

판정: 근거가 저장 커밋 뒤 바뀌었거나 근거를 읽지 못한 항목만 `다시 쓸 것`이다. 나머지는 값만 넣어 그대로 쓴다.
  쓰기 명령이 인용하지 않은 배포 경로(배포 도구, 인프라 경로, 워크플로, package.json)가 바뀌면 쓰기 명령이 다시 쓸 것이고, 배포 도구가 바뀌면 되돌리기 줄도 그렇다.
  인용한 문서의 어느 항목에도 안 묶인 절이 바뀌면 제목을 알리고 작성자가 읽어 「더한 항목」으로 처리한다.
  처음부터 쓰는 것은 절차서가 없거나 손상됐을 때, 사람이 지시했을 때, 환경이나 올릴 커밋을 읽지 못해 어느 값도 넣을 수 없을 때뿐이다.

사용:
  python deploy_reuse.py {실행 폴더} {id} --decide
    항목마다 가려 tasks\{id}\reuse.md에 적는다. 배포 계획이 `대기→진행`일 때 task_set.py가 함께 부른다.
  python deploy_reuse.py {실행 폴더} {id} --compose
    작성자의 tasks\{id}\own.md와 절차서로 result.md와 tasks\{id}\reuse-items.json을 만든다. 거부는 종료 코드 3이고 result.md를 쓰지 않는다.
  python deploy_reuse.py {실행 폴더} {id} --check
    읽기 판정이 돌린다: 값 치환, 재사용 항목의 근거 해시, 절차서 대조, 다시 쓴 항목과 앞 판의 차이. 재사용 항목이 달라졌으면 판정 실패가 아니라
    `달라진 재사용 항목`으로 낸다(사람이 본다). 종료 코드 3은 값을 넣지 못했거나 재사용 항목의 근거가 달라졌을 때다.
  python deploy_reuse.py {실행 폴더} {id} --fresh "이유"
    사람이 지시했을 때 처음부터 쓰는 쪽으로 돌린다.

저장은 배포 실행이 `완료`로 갈 때 task_set.py가 함께 부른다. 실패해도 전이를 막지 않고 알리기만 한다.
"""
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime

import devflow_lib
import exec as execmod
import kinds

DECISION_FILE = "reuse.md"
OWN_FILE = "own.md"
MANIFEST_FILE = "reuse-items.json"
REUSE, FRESH = "재사용", "처음부터"
WHY_NONE, WHY_DAMAGED, WHY_UNMEASURED, WHY_HUMAN = "절차서 없음", "절차서 손상", "재지 못함", "사람이 지시"
KEEP, REWRITE = "재사용", "다시 쓸 것"
REWRITTEN, DRIFT, ADDED, REMOVED, THIS_RUN = "다시 씀", "달라짐", "더함", "뺌", "이번만"
WHY_EVIDENCE, WHY_OTHER = "근거 바뀜", "그 밖"
BASIS_FILES, BASIS_NONE, BASIS_UNKNOWN = "파일", "없음", "모름"
CMD, TEXT = "cmd", "글"
READ, WRITE = "읽기", "쓰기"

SECTIONS = (("C", "명령"), ("R", "되돌리기"), ("P", "사전 조건"), ("V", "배포 뒤 확인"))
SECTION_NAMES = tuple(name for _, name in SECTIONS)
PREFIX = {name: letter for letter, name in SECTIONS}
ENV_TOKENS = {"운영": "운영", "prod": "운영", "production": "운영", "dev": "dev", "개발": "dev"}
ENV_VALUE = re.compile(r"(?:^|[,\s])환경\s+([^\s,]+)")
PLACE = re.compile(r"\{\{([가-힣][^{}]*)\}\}")   # 영문으로 시작하는 `{{.Names}}` 같은 도구의 꼴은 자리 값이 아니다
HEX = re.compile(r"(?<![0-9a-zA-Z])[0-9a-f]{7,40}(?![0-9a-zA-Z])")
TASK_ID = re.compile(r"(?<![A-Za-z0-9_-])T\d{3,}(?![A-Za-z0-9_-])")   # `T110의`처럼 한글 조사가 붙어도 task id다
THIS_RUN_CHECK = re.compile(r"(?<![\w-])(?:AC|FR)-[\w-]+")   # 닫는 인수 기준이 적힌 확인은 그 실행의 몫이다
FIXED_TAG = re.compile(r"\[고정\]\s*")
FIXED_MARK = re.compile(r"^-\s*(명령|되돌리기)\s+([\d\s,~-]+?)\s*(?::\s*(읽기|쓰기))?\s*(?:[:|]\s*(.*))?$")
# `명령 6줄`은 줄 수이지 번호가 아니다
LINE_LINK = re.compile(r"(?:(\d+)(?:\s*[~-]\s*(\d+))?(\s*번(?:째)?\s*줄))|(?:(명령\s*)(\d+)(?:\s*[~-]\s*(\d+))?(?![\d]|\s*줄))")
ROW_RANGE = re.compile(r"^\|\s*(\d+)(?:\s*[~-]\s*(\d+))?\s*\|")
TABLE_RULE = re.compile(r"^\|[\s:|-]+\|$")
LIST_ROW = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|\|)")
FILE_TOKEN = re.compile(r"[\w./-]+\.\w+")
# 파일 이름 뒤의 위치: `:510`(줄), `:7.2`(절), `:484,524`, `:663-669`, `:2.4`·`2.2`, `` ` 1절``
LOC_AFTER = re.compile(r"(?::(\d+(?:\.\d+)*)((?:\s*[,~-]\s*\d+(?:\.\d+)*|`?\s*·\s*`?:?\d+(?:\.\d+)*)*))|(?:`?\s+(\d+(?:\.\d+)*)절)")
LOC_NUMBER = re.compile(r"\d+(?:\.\d+)*")
HEADING = re.compile(r"^(#+)\s+(.*\S)\s*$")
EVIDENCE_SPLIT = re.compile(r",\s*(?=`?(?:\.[A-Za-z][\w.-]*|[\w./-]*[A-Za-z][\w./-]*\.[A-Za-z]\w*)(?:[:#,`\s]|$))")   # 절 제목 안의 쉼표에서는 나누지 않는다
PKG_TOOL = re.compile(r"(?<![\w-])(?:npm|npx|pnpm|yarn)(?:\.cmd)?(?![\w-])")
HOLD_BACK = re.compile(r"되돌릴 수 없")
HOLD_TAG = "[되돌릴 수 없는 단계 포함]"
DEPLOY_NAME = re.compile(r"(?:^|/)(?:deploy|rollback|배포)[^/]*(?:/|$)", flags=re.I)
TEST_PATH = re.compile(r"(?:^|/)(?:tests?|__tests__)/|\.test\.")
WORKFLOWS = ".github/workflows/"
NEW_SIGNAL = re.compile(r"새\s*자원|새\s*바인딩|새\s*외부\s*서비스|새\s*배포\s*방식|배포\s*방식(?:을|이)?\s*(?:바|변경)|첫\s*배포|처음\s*배포")
NEGATION = re.compile(r"없|아니|않|0개")
SHELL_JOIN = re.compile(r"(&&|\|\||;|\|)")
USER_RUN, AFTER_KEEP = "[사용자 실행]", "[유지 뒤]"
REQUIRED = ("값", "항목", "근거 경로")
OPTIONAL = ("되돌릴 수 없는 단계",)
OWN_REQUIRED = ("올릴 커밋", "되돌릴 수 없는 단계", "배포 전 확인", "배포 뒤 확인", "미룬 실물 확인", "배포 뒤 적을 문서")
OWN_FENCED = ("추가 명령", "다시 쓴 항목", "더한 항목")
OWN_CELLS = ("배포 전 확인", "배포 뒤 확인", "미룬 실물 확인")
OWN_BODY = ("설명", "연결 경로 대조", "멈추는 조건")
PATH_NAMES = ("실행 폴더", "배포 폴더", "원래 폴더")
TWO_MEANINGS = "뜻이 둘인 값"
SECRET_VALUE = "비밀값"
UNKNOWN_VALUE = "(지난 실행의 값)"


class Refuse(Exception):
    pass


# ---------------------------------------------------------------- 값과 자리 값

def env_of(t):
    """머리 파일에 적힌 환경: `split_criterion`의 `환경 X`. 토큰 전체가 맞을 때만 받고, 제목에서 추측하지 않는다."""
    m = ENV_VALUE.search(str(t.get("split_criterion", "") or ""))
    return ENV_TOKENS.get(m.group(1), "") if m else ""


def procedure_path(run_dir, env):
    return os.path.join(os.path.dirname(os.path.abspath(run_dir)), "policies", "deploy", env + ".md")


def path_forms(path):
    s = str(path).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", s)
    if not m:
        return {"": s, ":bash": s, ":win": s}
    return {"": s, ":bash": "/{}/{}".format(m.group(1).lower(), m.group(2)), ":win": s.replace("/", "\\")}


def git(cwd, *args):
    """(종료 코드, 표준 출력). 돌리지 못하면 코드 1."""
    try:
        p = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=cwd, capture_output=True, encoding="utf-8", errors="replace")
    except OSError:
        return 1, ""
    return p.returncode, (p.stdout or "").strip()


def full_commit(cwd, value):
    rc, out = git(cwd, "rev-parse", "--verify", "-q", "{}^{{commit}}".format(value)) if value else (1, "")
    return out if rc == 0 and out else ""


def tree_blobs(cwd, commit):
    """{경로: blob 해시}. 읽지 못하면 None."""
    rc, out = git(cwd, "ls-tree", "-r", commit)
    if rc != 0:
        return None
    found = {}
    for line in out.splitlines():
        left, _, path = line.partition("\t")
        parts = left.split()
        if path and len(parts) == 3:
            found[path] = parts[2]
    return found


def wrap_task(tasks, t):
    """이 계획이 의존하는 이 실행의 마무리 task. 배포만으로 시작했으면 없다."""
    ids = [t.get("parent", "")] + list(t.get("depends_on") or [])
    return next((tasks[i] for i in ids if i in tasks and tasks[i].get("kind") == "wrap-up"), None)


def child_row(t):
    return {"kind": "deploy-exec", "id": "", "parent": t.get("id", ""), "flow": t.get("flow", "")}


def deploy_folder(run_dir, tasks, t):
    return execmod.default_cwd(run_dir, tasks, child_row(t), "실행승인")


def values_for(run_dir, tasks, t, commit, previous=""):
    meta = devflow_lib.run_meta(run_dir)
    out = {"올릴 커밋": commit, "이 task": t.get("id", ""), "실행 이름": os.path.basename(os.path.abspath(run_dir))}
    if previous:
        out["직전 배포 커밋"] = previous
    wrap = wrap_task(tasks, t)
    if wrap:
        out["마무리 task"] = wrap["id"]
    branch = execmod.meta_value(meta, "integration_branch")
    if branch:
        out["통합 브랜치"] = branch
    paths = {"실행 폴더": os.path.abspath(run_dir), "배포 폴더": deploy_folder(run_dir, tasks, t), "원래 폴더": execmod.meta_value(meta, "project")}
    for name in PATH_NAMES:
        if paths[name]:
            for form, value in path_forms(paths[name]).items():
                out[name + form] = value
    return out


def line_values(items, extras=0):
    """{`줄:C4`: 실제 번호}. 뺀 항목은 없어서 그 자리 값이 남는다."""
    alive = [x for x in items if x["section"] == "명령" and x.get("status") != REMOVED]
    return {"줄:" + x["id"]: str(n) for n, x in enumerate(alive, extras + 1)}


def render(text, values):
    def one(m):
        name = m.group(1)
        base, _, n = name.partition(":")
        if name in values:
            return values[name]
        if n.isdigit() and base in values:
            return values[base][:int(n)]
        return m.group(0)
    return PLACE.sub(one, text)


def left_places(text):
    return sorted(set(PLACE.findall(text or "")))


def generalize(text, values):
    """실행 값을 자리 값으로. (바뀐 글, 그대로 남은 값 목록). 뜻이 둘인 폴더는 바꾸지 않고 다시 쓸 값으로 둔다.
    통합 브랜치는 git 명령의 인자에서만 바꾼다(`npm run release`의 낱말을 건드리지 않는다)."""
    out, unknown = text, []
    pathy = [(name, value) for name, value in values.items() if name.split(":")[0] in PATH_NAMES and value]
    twice = {value for _, value in pathy if len({name.split(":")[0] for name, v in pathy if v == value}) > 1}
    for name, value in sorted(pathy, key=lambda x: -len(x[1])):
        pattern = re.escape(value) + r"(?![\w-])"
        if value in twice:
            if re.search(pattern, out):
                unknown.append(TWO_MEANINGS)
            continue
        out = re.sub(pattern, lambda _m, n=name: "{{" + n + "}}", out)
    if values.get("실행 이름"):
        out = re.sub(r"(?<![\w-])" + re.escape(values["실행 이름"]) + r"(?![\w-])", "{{실행 이름}}", out)
    if values.get("통합 브랜치"):
        word = r"(?<![\w/.-])" + re.escape(values["통합 브랜치"]) + r"(?![\w/.-])"
        out = "".join(re.sub(word, "{{통합 브랜치}}", part) if re.search(r"(?<![\w-])git\s", part) else part for part in SHELL_JOIN.split(out))

    def task_id(m):
        for name in ("이 task", "마무리 task"):
            if values.get(name) == m.group(0):
                return "{{" + name + "}}"
        unknown.append(m.group(0))
        return m.group(0)

    def commit(m):
        s = m.group(0)
        for name in ("올릴 커밋", "직전 배포 커밋"):
            if values.get(name, "").startswith(s):
                return "{{" + name + ("" if len(s) == len(values[name]) else ":{}".format(len(s))) + "}}"
        return s
    out = TASK_ID.sub(task_id, out)
    out = HEX.sub(commit, out)
    return out, unknown


def other_commits(cwd, text, commit):
    """글에 든, 올릴 커밋이 아닌 커밋(전체 해시 집합). 커밋이 아닌 16진 글자는 세지 않는다."""
    out = set()
    for token in HEX.findall(text or ""):
        full = full_commit(cwd, token)
        if full and full != commit:
            out.add(full)
    return out


def stale_values(cwd, general, unknown, commit):
    """자리 값으로 바꾸지 못한, 지난 실행의 값."""
    return sorted(set(unknown) | {c[:7] for c in other_commits(cwd, general, commit)})


def masked(text):
    """(가린 글, 남은 값 목록). 비밀값은 절차서에 남기지 않고 그 항목을 다시 쓰게 한다."""
    clean = devflow_lib.mask_line(text)
    return clean, ([SECRET_VALUE] if clean != text else [])


def linked_lines(text):
    out = set()
    for m in LINE_LINK.finditer(text or ""):
        a = int(m.group(1) or m.group(5))
        b = int(m.group(2) or m.group(6) or a)
        out.update(range(a, b + 1))
    return out


def link_lines(text, ids):
    """다른 명령을 가리키는 번호를 항목 자리 값으로. (바뀐 글, 항목이 없는 번호)."""
    missing = []

    def one(n):
        if int(n) in ids:
            return "{{줄:" + ids[int(n)] + "}}"
        missing.append(n)
        return n

    def sub(m):
        if m.group(1):
            return one(m.group(1)) + ("~" + one(m.group(2)) if m.group(2) else "") + m.group(3)
        return m.group(4) + one(m.group(5)) + ("~" + one(m.group(6)) if m.group(6) else "")
    return LINE_LINK.sub(sub, text), missing


# ---------------------------------------------------------------- 절차서 파일

def body_digest(body):
    joined = "\n".join("## {}\n{}".format(k, body[k].strip()) for k in sorted(body))
    return hashlib.sha256(joined.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:16]


def write_procedure(path, head, body):
    head = dict(head, digest=body_digest(body))
    lines = ["---"] + ["{}: {}".format(k, v) for k, v in head.items()] + ["---", "", "# 배포 절차서: {}".format(head.get("env", "")), ""]
    for name in REQUIRED + OPTIONAL:
        if name in body:
            lines += ["## " + name, body[name].strip(), ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    devflow_lib.write_text(path, "\n".join(lines))


def parse_procedure(text):
    meta_lines, rest = devflow_lib.split_front_matter(text or "")
    return devflow_lib.parse_meta(meta_lines), {k: v.strip() for k, v in devflow_lib.sections(rest, level=2).items()}


def item_block(x):
    lines = ["### {} | {} | {}".format(x["id"], x["section"], x["kind"])]
    if x["kind"] == CMD:
        lines.append("- 종류: " + x["mode"])
    if x["basis"] == BASIS_FILES:
        lines += ["- 근거 파일: {} | {}".format(p, h) for p, h in sorted(x["evidence"].items())]
    else:
        lines.append("- 근거: " + x["basis"])
    if x.get("stale"):
        lines.append("- 남은 값: " + ", ".join(x["stale"]))
    lines.append("- 글: " + x["text"])
    return "\n".join(lines)


def parse_items(text):
    """절차서 「항목」을 항목 목록으로. 꼴이 어긋나면 ValueError."""
    out = []
    for title, block in devflow_lib.sections(text or "", level=3).items():
        parts = [p.strip() for p in title.split("|")]
        if len(parts) != 3 or parts[1] not in SECTION_NAMES or parts[2] not in (CMD, TEXT):
            raise ValueError("항목 제목을 읽지 못함: " + title)
        x = {"id": parts[0], "section": parts[1], "kind": parts[2], "mode": WRITE, "evidence": {}, "basis": BASIS_UNKNOWN, "stale": [], "text": None}
        for line in block.splitlines():
            if line.startswith("- 근거 파일: ") and " | " in line:
                path, blob = line[len("- 근거 파일: "):].rsplit(" | ", 1)
                x["evidence"][path] = blob
                x["basis"] = BASIS_FILES
            elif line.startswith("- 근거: "):
                x["basis"] = line[len("- 근거: "):].strip()
            elif line.startswith("- 종류: "):
                x["mode"] = line[len("- 종류: "):].strip()
            elif line.startswith("- 남은 값: "):
                x["stale"] = [v.strip() for v in line[len("- 남은 값: "):].split(",") if v.strip()]
            elif line.startswith("- 글: "):
                x["text"] = line[len("- 글: "):]
        if x["text"] is None:
            raise ValueError("항목에 글이 없음: " + parts[0])
        out.append(x)
    return out


def procedure_problem(head, body, env):
    """손상 이유(없으면 빈 글)."""
    if not head.get("saved_commit") or not head.get("digest"):
        return "머리를 읽지 못함"
    if str(head.get("env", "")) != env:
        return "머리의 환경이 {}임".format(head.get("env", ""))
    missing = [name for name in REQUIRED if name not in body]
    if missing:
        return "절 없음: " + ", ".join(missing)
    if body_digest(body) != str(head.get("digest", "")):
        return "본문이 digest와 다름(손으로 고침)"
    try:
        items = parse_items(body["항목"])
    except ValueError as e:
        return str(e)
    if not any(x["section"] == "명령" and x["kind"] == CMD for x in items):
        return "명령이 없음"
    return ""


def load_procedure(run_dir, env):
    """(머리, 본문, 문제). 파일이 없으면 (None, None, "")."""
    path = procedure_path(run_dir, env)
    if not os.path.isfile(path):
        return None, None, ""
    try:
        head, body = parse_procedure(devflow_lib.read_text(path))
    except (OSError, ValueError, UnicodeError) as e:
        return {}, {}, "읽지 못함: {}".format(e)
    return head, body, procedure_problem(head, body, env)


def value_rows(values):
    return "\n".join("- {}: {}".format(k, v) for k, v in values.items())


def parse_values(text):
    return dict(line[2:].split(": ", 1) for line in (text or "").splitlines() if line.startswith("- ") and ": " in line)


def parse_list(text):
    return [line[2:].strip() for line in (text or "").splitlines() if line.startswith("- ") and line[2:].strip() != "없음"]


def infra_patterns(run_dir):
    return devflow_lib.project_paths(run_dir)["인프라"]


def is_infra(path, patterns):
    if patterns:
        return devflow_lib.path_in_list(path, patterns)
    return devflow_lib.pattern_match(path, devflow_lib.DEFAULT_INFRA_PATTERNS) \
        or devflow_lib.pattern_match(path.rsplit("/", 1)[-1], devflow_lib.DEFAULT_INFRA_PATTERNS)


def is_deploy_tool(path):
    return bool(DEPLOY_NAME.search(path)) and not TEST_PATH.search(path) and not path.endswith(".md")


def is_watched(path, patterns):
    """저장 뒤 바뀌면 배포 절차에 닿을 수 있는 경로: 배포 도구·문서 이름, package.json, 인프라 경로, 워크플로(발동 브랜치 규칙)."""
    return path == "package.json" or path.startswith(WORKFLOWS) or is_infra(path, patterns) \
        or (bool(DEPLOY_NAME.search(path)) and not TEST_PATH.search(path))


def is_git_line(line):
    """git만 쓰는 줄. 기대는 파일이 없고, 배포 경로가 바뀌면 다시 쓴다."""
    s = line.strip()
    for mark in (USER_RUN, AFTER_KEEP):
        if s.startswith(mark):
            s = s[len(mark):].strip()
    parts = [p.strip() for p in re.split(r"&&|\|\||;", s) if p.strip() and not p.strip().startswith("cd ")]
    return bool(parts) and all(p.startswith("git ") for p in parts)


# ---------------------------------------------------------------- 항목에 근거 묶기

def doc_headings(text):
    """[(줄 번호(1부터), 수준, 제목, 제목 경로)]. 울타리 안의 `#`은 제목이 아니다. 경로는 위 제목까지 `>`로 잇는다."""
    out, inside, stack = [], False, []
    for n, line in enumerate((text or "").splitlines(), 1):
        if line.strip().startswith("```"):
            inside = not inside
        m = HEADING.match(line) if not inside else None
        if m:
            level, title = len(m.group(1)), m.group(2)
            stack = [s for s in stack if s[0] < level] + [(level, title)]
            out.append((n, level, title, " > ".join(s[1] for s in stack)))
    return out


def doc_section(text, key):
    """제목 경로가 key인 절의 글(같거나 높은 수준의 다음 제목까지). 없거나 둘 이상이면 None."""
    heads = doc_headings(text)
    hits = [i for i, h in enumerate(heads) if h[3] == key]
    if len(hits) != 1:
        return None
    at = hits[0]
    lines = (text or "").splitlines()
    end = next((h[0] - 1 for h in heads[at + 1:] if h[1] <= heads[at][1]), len(lines))
    return "\n".join(lines[heads[at][0] - 1:end])


def leaf_sections(text):
    """{제목 경로: 그 제목 바로 아래 글}. 어느 절이 바뀌었는지 볼 때 쓴다."""
    heads = doc_headings(text)
    lines = (text or "").splitlines()
    out = {}
    for i, h in enumerate(heads):
        end = heads[i + 1][0] - 1 if i + 1 < len(heads) else len(lines)
        out[h[3]] = "\n".join(lines[h[0]:end]).strip()
    return out


class Evidence:
    """한 커밋의 근거 값. 키는 경로(blob 해시)이거나 `경로#제목 경로`(그 절 글자의 해시)다."""

    def __init__(self, cwd, commit, blobs):
        self.cwd, self.commit, self.blobs, self.texts = cwd, commit, blobs, {}

    def text(self, path):
        if path not in self.texts:
            rc, out = git(self.cwd, "show", "{}:{}".format(self.commit, path))
            self.texts[path] = out if rc == 0 else None
        return self.texts[path]

    def hash_of(self, key):
        path, _, title = key.partition("#")
        if path not in self.blobs:
            return None
        if not title:
            return self.blobs[path]
        part = doc_section(self.text(path), title)
        return hashlib.sha256(part.replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()[:16] if part is not None else None

    def section_key(self, path, number, by_line):
        """인용한 위치가 든 절의 키. 가리지 못하면 빈 글(그 파일 전체에 묶는다)."""
        text = self.text(path)
        heads = doc_headings(text)
        if by_line:
            if int(number) > len((text or "").splitlines()):
                return ""
            above = [h for h in heads if h[0] <= int(number)]
            hits = above[-1:]
        else:
            hits = [h for h in heads if re.match(re.escape(number) + r"(?:[.\s]|$)(?![\d])", h[2])]
        if len(hits) != 1 or sum(1 for h in heads if h[3] == hits[0][3]) != 1:
            return ""
        return "{}#{}".format(path, hits[0][3])


def base_path(key):
    return key.partition("#")[0]


def cited_files(text, ev):
    """글이 인용한 근거의 키. 이름만 적었어도 저장소에 하나뿐이면 든다. 문서의 절이나 줄을 인용했으면 그 절에만 묶는다."""
    by_name = {}
    for p in ev.blobs:
        by_name.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    found = set()
    text = text or ""
    for m in FILE_TOKEN.finditer(text):
        tok = re.sub(r"^(?:\./|/)+", "", m.group(0).rstrip(".,"))
        names = by_name.get(tok.rsplit("/", 1)[-1], [])
        path = tok if tok in ev.blobs else (names[0] if len(names) == 1 and "/" not in tok else "")
        if not path:
            continue
        loc = LOC_AFTER.match(text, m.end()) if path.endswith(".md") else None
        keys = []
        if loc:
            numbers = [(loc.group(3), False)] if loc.group(3) else [(n, "." not in n) for n in LOC_NUMBER.findall(loc.group(1) + (loc.group(2) or ""))]
            keys = [ev.section_key(path, n, by_line) for n, by_line in numbers]
        found.update(keys if keys and all(keys) else [path])
    return found


def command_files(line, ev, grounds):
    """명령 줄이 기대는 근거: 줄과 근거 표가 인용한 것, 패키지 도구면 package.json, 도구 이름과 같은 저장소 맨 위 파일."""
    found = cited_files(line, ev) | set(grounds)
    if PKG_TOOL.search(line) and "package.json" in ev.blobs:
        found.add("package.json")
    for p in ev.blobs:
        if "/" not in p and p.split(".")[0] and "." in p and p.split(".")[0] != "package" and re.search(r"(?<![\w./-])" + re.escape(p.split(".")[0]) + r"(?![\w-])", line):
            found.add(p)
    return found


def grounds_by_line(text, ev):
    """「명령 목록과 근거」에서 {줄 번호: 근거 키 집합}. `| 1~3 | …`나 `4번 줄: …` 꼴의 줄을 읽는다."""
    out = {}
    for line in (text or "").splitlines():
        s = line.strip()
        m = ROW_RANGE.match(s)
        numbers = set(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1)) if m else linked_lines(s)
        files = cited_files(s, ev)
        for n in numbers:
            out.setdefault(n, set()).update(files)
    return out


def fixed_marks(text, ev):
    """본문 「고정 항목」 → {("명령"|"되돌리기", 번호): (종류, 근거 키 집합)}. 종류를 적지 않은 줄은 쓰기다."""
    out = {}
    for line in (text or "").splitlines():
        m = FIXED_MARK.match(line.strip())
        if not m:
            continue
        files = cited_files(m.group(4) or "", ev)
        for part in m.group(2).split(","):
            ends = [int(x) for x in re.findall(r"\d+", part)]
            for n in range(ends[0], ends[-1] + 1) if ends else ():
                out[(m.group(1), n)] = (m.group(3) or WRITE, files)
    return out


def plan_sections(text):
    return devflow_lib.sections(devflow_lib.sections(text, level=2).get("본문", ""), level=3)


def find_section(sec, word):
    return next((body for title, body in sec.items() if word in title), None)


def hold_text(*texts):
    """되돌릴 수 없다고 적은 줄. 칸 머리의 표지만 든 줄은 빼고, 다음 작성자가 참고로 읽는다."""
    out, inside = [], False
    for text in texts:
        for line in (text or "").splitlines():
            if line.strip().startswith("```"):
                inside = not inside
                continue
            if not inside and HOLD_BACK.search(line.replace(HOLD_TAG, "")):
                out.append(line.strip().lstrip("- ").strip())
    return out


class ItemMaker:
    """처음부터 쓴 계획에서 작성자가 고정으로 표시한 것을 항목으로 만든다."""

    def __init__(self, values, cwd, commit, ev):
        self.values, self.cwd, self.commit, self.ev = values, cwd, commit, ev
        self.counts = Counter()
        self.items = []

    def add(self, section, kind, general, stale=()):
        self.counts[section] += 1
        x = {"id": "{}{}".format(PREFIX[section], self.counts[section]), "section": section, "kind": kind, "text": general,
             "mode": WRITE, "evidence": {}, "basis": BASIS_UNKNOWN, "stale": list(stale)}
        self.items.append(x)
        return x

    def clean(self, line):
        general, unknown = generalize(line, self.values)
        general, secret = masked(general)
        return general, stale_values(self.cwd, general, unknown, self.commit) + secret

    def bind(self, x, files, basis):
        x["evidence"] = {key: self.ev.hash_of(key) for key in sorted(files)}
        x["basis"] = BASIS_FILES if files else basis
        return x

    def command(self, section, line, mode, grounds=()):
        general, stale = self.clean(line)
        if not stale and render(general, self.values) != line:
            stale = ["되살린 줄이 다름"]
        x = self.add(section, CMD, general, stale)
        x["mode"] = mode
        files = command_files(general, self.ev, grounds)
        return self.bind(x, files, BASIS_NONE if mode == READ or is_git_line(general) else BASIS_UNKNOWN)

    def rows(self, section, text, line_items, skip=None):
        """`[고정]`을 붙인 행만 항목이 된다. 표시 없는 행과 설명 글은 남기지 않는다."""
        ids = {n: x["id"] for n, x in line_items.items()}
        for raw in (text or "").splitlines():
            s = raw.strip()
            if not FIXED_TAG.search(s) or not LIST_ROW.match(s) or (skip and skip(s)):
                continue
            general, stale = self.clean(FIXED_TAG.sub("", raw.rstrip()))
            numbers = linked_lines(general)
            general, missing = link_lines(general, ids)
            if missing:
                stale = stale + ["고정 아닌 줄을 가리킴: " + ", ".join(missing)]
            x = self.add(section, TEXT, general, stale)
            links = [line_items[n] for n in numbers if n in line_items]
            files = cited_files(general, self.ev)
            for link in links:
                files |= set(link["evidence"])
            unknown = not links or any(link["basis"] == BASIS_UNKNOWN for link in links)
            self.bind(x, files, BASIS_UNKNOWN if unknown else BASIS_NONE)


def items_from_plan(plan, values, lines, undo, cwd, commit, ev):
    """처음부터 쓴 계획에서 항목을 만든다. 값이 남은 줄은 다음에 다시 쓸 항목으로 둔다."""
    text = devflow_lib.read_text(os.path.join(plan["_dir"], "result.md"))
    sec = plan_sections(text)
    marks = fixed_marks(find_section(sec, "고정 항목"), ev)
    grounds = grounds_by_line(find_section(sec, "명령 목록"), ev)
    make = ItemMaker(values, cwd, commit, ev)
    line_items = {}
    for n, line in enumerate(lines, 1):
        if ("명령", n) in marks:
            mode, files = marks[("명령", n)]
            line_items[n] = make.command("명령", line, mode, grounds.get(n, set()) | files)
    if not line_items:
        raise Refuse("고정으로 표시한 명령이 없음(본문 「고정 항목」)")
    for n, line in enumerate(undo, 1):
        if ("되돌리기", n) in marks:
            mode, files = marks[("되돌리기", n)]
            make.command("되돌리기", line, mode, files)
    make.rows("사전 조건", find_section(sec, "사전 조건"), line_items)
    make.rows("배포 뒤 확인", find_section(sec, "배포 뒤 확인"), line_items, skip=THIS_RUN_CHECK.search)
    hold = []
    for line in hold_text(devflow_lib.decide_cell(plan["_dir"]), find_section(sec, "되돌리기")):
        general, unknown = generalize(line, values)
        for token in unknown:
            general = general.replace(token, UNKNOWN_VALUE)
        hold.append("- " + masked(general)[0])
    return make.items, hold


# ---------------------------------------------------------------- 저장

def items_from_manifest(manifest, values, lines, undo, ev, cwd, commit):
    """재사용한 계획의 항목: 재사용 항목은 그대로, 다시 쓴 항목은 새 값으로. 이번 실행 몫은 넣지 않는다."""
    items = [dict(x) for x in manifest["items"] if x["status"] != REMOVED]
    extras = int(manifest.get("extras", 0))
    numbers = {n: x["id"] for n, x in enumerate((x for x in items if x["section"] == "명령"), extras + 1)}
    for section, frozen in (("명령", lines[extras:]), ("되돌리기", undo)):
        group = [x for x in items if x["section"] == section and x["kind"] == CMD]
        if len(frozen) != len(group):
            raise Refuse("얼린 {} 줄 수가 항목과 다름".format(section))
        for x, line in zip(group, frozen):
            if render(x["text"], dict(values, **line_values(items, extras))) != line:   # 승인 전에 손으로 고친 줄: 사람이 본 줄이 새 값이다
                general, unknown = generalize(line, values)
                general, secret = masked(general)
                general, missing = link_lines(general, numbers)
                x["text"] = general
                x["stale"] = stale_values(cwd, general, unknown, commit) + secret + (["줄을 찾지 못함"] if missing else [])
    used = Counter()
    for x in manifest["items"]:
        m = re.match(r"^([A-Z])(\d+)$", x["id"])
        if m:
            used[m.group(1)] = max(used[m.group(1)], int(m.group(2)))
    renamed = {}
    for x in items:
        if x["status"] == ADDED:
            letter = PREFIX[x["section"]]
            used[letter] += 1
            renamed[x["id"]] = "{}{}".format(letter, used[letter])
            x["id"] = renamed[x["id"]]
    for x in items:
        for old, new in renamed.items():
            x["text"] = x["text"].replace("{{줄:" + old + "}}", "{{줄:" + new + "}}")
        if x["basis"] == BASIS_FILES:
            present = {}
            for key in x["evidence"]:
                value = ev.hash_of(key)
                # 절이 없어졌으면 그 파일 전체에 묶는다. 파일까지 없어졌으면 근거를 모른다
                if value is None and base_path(key) in ev.blobs:
                    key, value = base_path(key), ev.blobs[base_path(key)]
                if value is not None:
                    present[key] = value
            x["evidence"] = present
            x["basis"] = BASIS_FILES if present else BASIS_UNKNOWN
    return items


def save(run_dir, t, tasks=None):
    """(저장했는가, 한 줄). 유지로 끝난 배포 실행의 승인된 계획만 저장한다."""
    tasks = tasks or devflow_lib.load_tasks(run_dir)
    if not devflow_lib.run_from_v120(run_dir):
        return False, "1.2.0 앞에 시작한 실행"
    plan = tasks.get(t.get("parent", ""))
    if t.get("status") != kinds.DONE or str(t.get("deploy_outcome", "")).strip() != "유지":
        return False, "유지로 끝난 배포가 아님"
    if plan is None or plan.get("kind") != "deploy-plan":
        return False, "부모 배포 계획을 찾지 못함"
    run_md = os.path.join(t["_dir"], "judge-run.md")
    run_top = devflow_lib.sections(devflow_lib.read_text(run_md), level=2) if os.path.isfile(run_md) else None
    if run_top is None or devflow_lib.item_count(run_top.get("통과 못 한 기준", "")):
        return False, "배포 뒤 확인이 모두 통과하지 않음"
    decision = read_decision(plan)
    env = decision.get("env") or env_of(plan)   # split_criterion은 자식을 쓴 뒤 나눈 기준으로 덮일 수 있다
    if not env:
        return False, "환경을 읽지 못함"
    try:
        cwd = deploy_folder(run_dir, tasks, plan)
        commit = full_commit(cwd, str(t.get("deployed_commit", "") or "").strip())
        if not commit:
            raise Refuse("deployed_commit을 읽지 못함")
        lines = execmod.read_frozen(t, "실행승인") or []
        undo = execmod.read_frozen(t, "되돌림") or []
        if not lines:
            raise Refuse("얼린 명령이 없음")
        blobs = tree_blobs(cwd, commit)
        if blobs is None:
            raise Refuse("커밋의 파일 목록을 읽지 못함")
        ev = Evidence(cwd, commit, blobs)
        old_head, old_body, problem = load_procedure(run_dir, env)
        manifest = read_manifest(plan)
        if decision.get("decision") == REUSE:
            if not manifest:
                raise Refuse("재사용 판정인데 조립 기록이 없음")
            if not old_head or problem or str(old_head.get("digest", "")) != decision.get("digest", ""):
                raise Refuse("재사용한 절차서가 그 사이 바뀜")
            values = values_for(run_dir, tasks, plan, commit, str(old_head["saved_commit"]))
            items = items_from_manifest(manifest, values, lines, undo, ev, cwd, commit)
            own_hold = manifest.get("hold", "")
            hold = own_hold or old_body.get("되돌릴 수 없는 단계", "")
        else:
            marks = fixed_marks(find_section(plan_sections(devflow_lib.read_text(os.path.join(plan["_dir"], "result.md"))), "고정 항목"), ev)
            kept = [line for n, line in enumerate(lines, 1) if ("명령", n) in marks] + [line for n, line in enumerate(undo, 1) if ("되돌리기", n) in marks]
            others = other_commits(cwd, "\n".join(kept), commit)
            previous = next(iter(others)) if len(others) == 1 else ""
            if previous and git(cwd, "merge-base", "--is-ancestor", previous, commit)[0] != 0:
                previous = ""
            values = values_for(run_dir, tasks, plan, commit, previous)
            items, hold_lines = items_from_plan(plan, values, lines, undo, cwd, commit, ev)
            hold = "\n".join(hold_lines)
        patterns = sorted(set(infra_patterns(run_dir)) | set(parse_list(old_body.get("근거 경로", "")) if old_body else ()))
    except (Refuse, execmod.Reject, OSError) as e:
        return False, str(e)
    body = {"값": value_rows(dict(values, **line_values(items))), "항목": "\n\n".join(item_block(x) for x in items), "근거 경로": "\n".join("- " + p for p in patterns) or "- 없음"}
    if hold:
        body["되돌릴 수 없는 단계"] = hold
    head = {"env": env, "saved_commit": commit, "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from_run": os.path.basename(os.path.abspath(run_dir)), "from_task": plan["id"], "exec_task": t["id"]}
    write_procedure(procedure_path(run_dir, env), head, body)
    return True, "{} 절차서 저장(커밋 {}, 항목 {}, 명령 {}줄)".format(env, commit[:7], len(items), sum(1 for x in items if x["section"] == "명령"))


# ---------------------------------------------------------------- 판정

def origin_head(t):
    """배포만으로 시작한 실행이 가리키는 task 폴더의 머리 값. `origin`이 비면 {}, 읽지 못하면 None."""
    origin = str(t.get("origin", "") or "").strip()
    if not origin:
        return {}
    path = os.path.join(origin, "task.md")
    if not os.path.isfile(path):
        return None
    meta_lines, _ = devflow_lib.split_front_matter(devflow_lib.read_text(path))
    return devflow_lib.parse_meta(meta_lines)


def run_commit(run_dir, tasks, t, cwd):
    """마무리의 `exported_commit`. 배포만이면 `origin`의 것이고, 그 값이 비면 개발 기준 브랜치의 끝이다."""
    wrap = wrap_task(tasks, t)
    source = wrap if wrap else origin_head(t)
    if source is None:
        return ""
    value = str(source.get("exported_commit", "") or "").strip()
    return full_commit(cwd, value or execmod.meta_value(devflow_lib.run_meta(run_dir), "base_branch"))


def memo_text(tasks, t):
    wrap = wrap_task(tasks, t)
    origin = str(t.get("origin", "") or "").strip()
    folder = wrap["_dir"] if wrap else origin
    path = os.path.join(folder, "result.md") if folder else ""
    if not path or not os.path.isfile(path):
        return None
    return execmod.heading_section(devflow_lib.read_text(path), "배포 메모").strip() or None


def design_plan_text(run_dir):
    design = os.path.join(run_dir, "design")
    out = []
    for name in sorted(os.listdir(design)) if os.path.isdir(design) else []:
        path = os.path.join(design, name)
        if name.endswith(".md") and os.path.isfile(path):
            out.append(execmod.heading_section(devflow_lib.read_text(path), "배포 계획"))
    return "\n".join(out)


def new_requirements(run_dir, tasks, t):
    """새 자원이나 새 배포 방식을 알리는 줄. 전체를 다시 쓰게 하지 않고 작성자가 그 몫을 항목으로 더한다."""
    out = ["인프라 결정 task {}".format(o["id"]) for o in tasks.values() if o.get("kind") == "infra-design" and o.get("status") not in ("보류", "백로그")]
    memo = memo_text(tasks, t)
    if memo is None:
        out.append("배포 메모를 읽지 못함: 작성자가 읽어 새 자원과 새 배포 방식이 있는지 본다")
    for line in ((memo or "") + "\n" + design_plan_text(run_dir)).splitlines():
        if NEW_SIGNAL.search(line) and not NEGATION.search(line):
            out.append(line.strip().lstrip("- ")[:80])
    return sorted(out)


def docs_needing_check(run_dir):
    """`docs-state.md`에서 `확인 필요`인 문서."""
    path = os.path.join(os.path.dirname(os.path.abspath(run_dir)), "policies", "docs-state.md")
    if not os.path.isfile(path):
        return set()
    out = set()
    for line in devflow_lib.sections(devflow_lib.read_text(path)).get("문서", "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[3] == "확인 필요":
            out.add(cells[0])
    return out


def unbound_sections(items, ev, old_ev, changed):
    """인용한 문서에서 어느 항목에도 안 묶인 절이 바뀐 곳 [(경로, 제목 경로 목록)]. 파일 전체에 묶인 문서는 항목이 이미 걸린다."""
    keys = {k for x in items for k in x["evidence"]}
    out = []
    for path in sorted({base_path(k) for k in keys if base_path(k).endswith(".md")} & changed):
        if path in keys:
            continue
        bound = [k.partition("#")[2] for k in keys if base_path(k) == path]
        before, after = leaf_sections(old_ev.text(path)), leaf_sections(ev.text(path))
        moved = [t for t in sorted(set(before) | set(after)) if before.get(t) != after.get(t)
                 and not any(t == b or t.startswith(b + " > ") for b in bound)]
        if moved:
            out.append((path, moved))
    return out


def mark(x, why, detail):
    x["status"], x["why"], x["detail"] = REWRITE, why, detail


def judge_items(run_dir, cwd, head, body, commit, values, t):
    """항목마다 재사용과 다시 쓸 것을 가른다. 그때의 값으로 만든 줄과 지금 값으로 만든 줄을 함께 둔다. (항목, 알림). 못 가리면 다시 쓸 것이다."""
    items = parse_items(body["항목"])
    old_values = parse_values(body["값"])
    saved = str(head.get("saved_commit", ""))
    changed, blobs = None, tree_blobs(cwd, commit)
    if full_commit(cwd, saved):
        rc, out = git(cwd, "diff", "--name-only", saved, commit)
        changed = set(out.splitlines()) if rc == 0 else None
    readable = blobs is not None and changed is not None
    stale_docs = docs_needing_check(run_dir)
    ev = Evidence(cwd, commit, blobs or {})
    child = child_row(t)
    values = dict(values, **line_values(items))
    for x in items:
        x["rendered"], x["old"] = render(x["text"], values), render(x["text"], old_values)
        x["status"], x["why"], x["detail"] = KEEP, "", ""
        hits = sorted(k for k in x["evidence"] if readable and (ev.hash_of(k) != x["evidence"][k] or base_path(k) in stale_docs))
        left = left_places(x["rendered"])
        if not readable:
            mark(x, WHY_OTHER, "저장 커밋 {}과 이번 커밋의 근거를 읽지 못함".format(saved[:7]))
        elif hits:
            mark(x, WHY_EVIDENCE, "저장 커밋 {} 뒤 바뀜: {}".format(saved[:7], ", ".join(hits)))
        elif x["stale"]:
            mark(x, WHY_OTHER, "지난 실행의 값이 남음: {}".format(", ".join(x["stale"])))
        elif left:
            mark(x, WHY_OTHER, "채우지 못한 자리 값: {}".format(", ".join(left)))
        elif x["basis"] == BASIS_UNKNOWN:
            mark(x, WHY_OTHER, "근거 파일을 읽지 못함")
        elif x["kind"] == CMD:
            bad = execmod.line_problems(child, "되돌림" if x["section"] == "되돌리기" else "실행승인", x["rendered"], cwd)
            if bad:
                mark(x, WHY_OTHER, "명령 꼴 문제: {}".format(bad[0]))
    notices = []
    if readable:
        patterns = sorted(set(parse_list(body["근거 경로"])) | set(infra_patterns(run_dir)))
        writes = [x for x in items if x["kind"] == CMD and x["mode"] != READ]
        write_cited = {base_path(k) for x in writes for k in x["evidence"]}
        docs_cited = {base_path(k) for x in items for k in x["evidence"] if base_path(k).endswith(".md")}
        loose = sorted(p for p in changed if p not in write_cited and p not in docs_cited and is_watched(p, patterns))
        tools = sorted(p for p in changed if is_deploy_tool(p))
        for x in writes:
            if x["status"] != KEEP:
                continue
            if loose:
                mark(x, WHY_EVIDENCE, "쓰기 명령이 인용하지 않은 배포 경로가 바뀜: {}".format(", ".join(loose[:3])))
            elif tools and x["section"] == "되돌리기":
                mark(x, WHY_EVIDENCE, "배포 도구가 바뀜: {}".format(", ".join(tools[:3])))
        old_ev = Evidence(cwd, saved, {})
        for path, titles in unbound_sections(items, ev, old_ev, changed):
            notices.append("{}: 어느 항목에도 안 묶인 절이 바뀜: {}".format(path, ", ".join(titles[:5])))
    return items, notices


def judged(decision, kind="", reason="", **more):
    return dict({"decision": decision, "kind": kind, "reason": reason, "items": [], "notices": []}, **more)


def evaluate(run_dir, t, tasks=None):
    """항목별 판정. 파일을 쓰지 않는다."""
    tasks = tasks or devflow_lib.load_tasks(run_dir)
    env = env_of(t)
    if not env:
        return judged(FRESH, WHY_UNMEASURED, "머리 파일 split_criterion에 `환경 운영`이나 `환경 dev`가 없음", warn=has_procedure(run_dir))
    head, body, problem = load_procedure(run_dir, env)
    if head is None:
        return judged(FRESH, WHY_NONE, "{} 절차서가 아직 없음".format(env), env=env)
    if problem:
        return judged(FRESH, WHY_DAMAGED, "{} 절차서: {}".format(env, problem), env=env)
    try:
        cwd = deploy_folder(run_dir, tasks, t)
        commit = run_commit(run_dir, tasks, t, cwd)
        if not commit:
            return judged(FRESH, WHY_UNMEASURED, "올릴 커밋을 읽지 못함", env=env)
        values = values_for(run_dir, tasks, t, commit, str(head["saved_commit"]))
        items, notices = judge_items(run_dir, cwd, head, body, commit, values, t)
        notices = new_requirements(run_dir, tasks, t) + notices
    except (OSError, ValueError, KeyError, devflow_lib.Reject) as e:
        return judged(FRESH, WHY_UNMEASURED, str(e) or "재지 못함", env=env)
    return judged(REUSE, env=env, commit=commit, saved_commit=str(head["saved_commit"]), digest=str(head["digest"]),
                  items=items, values=values, body=body, notices=notices, cwd=cwd)


def has_procedure(run_dir):
    folder = os.path.dirname(procedure_path(run_dir, "x"))
    return os.path.isdir(folder) and any(n.endswith(".md") for n in os.listdir(folder))


def decision_path(t):
    return os.path.join(t["_dir"], DECISION_FILE)


def counts_of(items):
    flagged = [x for x in items if x["status"] == REWRITE]
    return {"reused": sum(1 for x in items if x["status"] == KEEP), "rewrite": len(flagged),
            "why_evidence": sum(1 for x in flagged if x["why"] == WHY_EVIDENCE), "why_other": sum(1 for x in flagged if x["why"] == WHY_OTHER)}


def write_decision(t, d):
    rows = ["decision", "kind", "reason", "env", "commit", "saved_commit", "digest", "reused", "rewrite", "why_evidence", "why_other"]
    d = dict(d, **(counts_of(d["items"]) if d.get("items") and "reused" not in d else {}))
    text = ["# 배포 계획 재사용 판정", ""] + ["- {}: {}".format(k, d[k]) for k in rows if d.get(k) not in (None, "")]
    if d.get("decision") == REUSE:
        flagged = [x for x in d["items"] if x["status"] == REWRITE]
        text += ["", "## 다시 쓸 것(`own.md` 「다시 쓴 항목」에 쓴다)"]
        for x in flagged:
            text += ["- {} | {} | {}: {}".format(x["id"], x["section"], x["why"], x["detail"]), "  지금 글: " + x["rendered"]]
        text += ["- 없음"] if not flagged else []
        if d["notices"]:
            text += ["", "## 알림(읽어 보고 필요한 몫을 `own.md` 「더한 항목」에 쓴다)"] + ["- " + x for x in d["notices"]]
        past = d["body"].get("되돌릴 수 없는 단계", "")
        if past:
            text += ["", "## 지난 계획의 되돌릴 수 없는 단계(참고, 이번 답은 `own.md`에 쓴다)", render(past, d["values"])]
        text += ["", "## 재사용 항목(고치지 않는다. 값은 스크립트가 넣었다)"]
        text += ["- {} | {}: {}".format(x["id"], x["section"], x["rendered"]) for x in d["items"] if x["status"] == KEEP]
    devflow_lib.write_text(decision_path(t), "\n".join(text) + "\n")


def read_decision(t):
    path = decision_path(t)
    if not os.path.isfile(path):
        return {}
    return dict(line[2:].split(": ", 1) for line in devflow_lib.read_text(path).split("\n## ")[0].splitlines()
                if line.startswith("- ") and ": " in line)


def decide(run_dir, t, tasks=None):
    d = evaluate(run_dir, t, tasks)
    write_decision(t, d)
    return d


def decision_line(d):
    if d["decision"] == REUSE:
        c = counts_of(d["items"])
        tail = " 알림 {}건: {}".format(len(d["notices"]), "; ".join(d["notices"])) if d["notices"] else ""
        return "배포 계획 재사용: 재사용 {}, 다시 쓸 것 {}(근거 바뀜 {}, 그 밖 {}). {} 절차서(저장 커밋 {} → 이번 커밋 {}). 작성자는 다시 쓸 항목과 이번 실행 몫만 씁니다.{}".format(
            c["reused"], c["rewrite"], c["why_evidence"], c["why_other"], d["env"], d["saved_commit"][:7], d["commit"][:7], tail)
    if d.get("warn"):
        # 재사용이 이 한 값에 기대므로 빠뜨린 것을 정상처럼 지나가게 두지 않는다
        return ("! 배포 계획 재사용: 절차서가 있는데 환경을 읽지 못해 처음부터 씁니다. 머리 파일 split_criterion에 `환경 dev`나 `환경 운영`을 적고 "
                "`deploy_reuse.py {실행 폴더} {id} --decide`를 다시 부릅니다")
    return "배포 계획 재사용: 처음부터 씁니다. {}: {}".format(d["kind"], d["reason"])


def on_plan_start(run_dir, t):
    """1.2.0부터 시작한 실행의 계획이 시작될 때 판정한다. 옛 실행은 None(파일도 쓰지 않음)."""
    if not devflow_lib.run_from_v120(run_dir):
        return None
    return decision_line(decide(run_dir, t))


def after_transition(run_dir, t, old, new):
    """task_set.py가 전이 뒤 부른다. 판정과 저장은 전이보다 권위가 낮아 실패해도 전이를 되돌리지 않는다."""
    try:
        kind = t.get("kind", "")
        if kind == "deploy-plan" and old == "대기" and new == "진행":
            line = on_plan_start(run_dir, devflow_lib.load_tasks(run_dir)[t["id"]])
            if line:
                print(line)
        elif kind == "deploy-exec" and new == kinds.DONE and devflow_lib.run_from_v120(run_dir):
            tasks = devflow_lib.load_tasks(run_dir)
            ok, msg = save(run_dir, tasks[t["id"]], tasks)
            print("배포 절차서: {}".format(msg if ok else "저장 안 함. " + msg))
    except Exception as e:   # 처음부터 쓰는 쪽으로 떨어지므로 전이를 막지 않는다
        print("! 배포 계획 재사용 처리 실패(전이는 유지): {}".format(e))


# ---------------------------------------------------------------- 작성자 몫 합치기

def as_items(text):
    """칸에 넣을 항목 줄. `- `로 시작하지 않는 줄은 항목으로 만들고 `없음`은 뺀다."""
    out = []
    for line in (text or "").splitlines():
        s = line.rstrip()
        if not s.strip() or s.strip() in ("없음", "- 없음"):
            continue
        out.append(s if s.startswith(("- ", "  ")) else "- " + s.strip())
    return out


def parse_own_block(block):
    """{"근거", "그대로", "종류", "cmd", "글"}: 다시 쓴 항목이나 더한 항목 한 칸."""
    out = {"근거": None, "그대로": None, "종류": None, "cmd": devflow_lib.cmd_lines(block), "글": []}
    inside = False
    for raw in block.splitlines():
        s = raw.strip()
        if devflow_lib.CMD_FENCE.match(s) or (inside and s.startswith("```")):
            inside = not inside
            continue
        if inside or not s:
            continue
        m = re.match(r"^(근거|그대로|종류)\s*(?::\s*(.*))?$", s)
        if m:
            out[m.group(1)] = (m.group(2) or "").strip()
        else:
            out["글"].append(raw.rstrip())
    return out


def evidence_from(value, ev, iid, may_have_none):
    """`근거:` 줄의 값 → (근거 사전, basis). 값은 `경로`, `경로:줄`, `경로:절 번호`, `경로#제목 경로`를 쉼표로 잇는다.
    쓰기 명령은 `근거: 없음`을 받지 않는다(한 번의 답으로 묶음이 풀린다). 글, 읽기 줄, git 줄만 받는다."""
    if value is None:
        raise Refuse("{}에 `근거:` 줄이 없음(파일이 없으면 `근거: 없음`)".format(iid))
    if value == BASIS_NONE:
        if not may_have_none:
            raise Refuse("{}는 쓰기 명령이라 `근거: 없음`을 받지 않음: 기대는 파일을 적는다".format(iid))
        return {}, BASIS_NONE
    keys, missing = set(), []
    for raw in (p.strip().strip("`") for p in EVIDENCE_SPLIT.split(value) if p.strip()):
        found = {raw} if ev.hash_of(raw) is not None else (cited_files(raw, ev) if ":" in raw else set())
        keys |= found
        if not found:
            missing.append(raw)
    if not keys or missing:
        raise Refuse("{}의 근거 파일이 올릴 커밋에 없음: {}".format(iid, ", ".join(missing) or "(비었음)"))
    return {k: ev.hash_of(k) for k in sorted(keys)}, BASIS_FILES


def dropped_items(own, by_id):
    """「뺄 항목」 → {id: 이유}. 이유 없이는 빼지 못한다."""
    out = {}
    for line in as_items(own.get("뺄 항목", "")):
        m = re.match(r"^-\s*([A-Z]\d+)\s*:\s*(\S.*)$", line)
        if not m:
            raise Refuse("뺄 항목은 `- C5: 이유` 꼴로 쓴다: {}".format(line))
        if m.group(1) not in by_id:
            raise Refuse("절차서에 없는 항목: {}".format(m.group(1)))
        out[m.group(1)] = m.group(2)
    return out


def own_text_of(parsed, kind, iid, d, t, section):
    """작성자가 쓴 글이나 명령 한 줄을 자리 값으로. 번호는 항목이 모두 정해진 뒤 묶는다."""
    if kind == CMD:
        if len(parsed["cmd"]) != 1:
            raise Refuse("{}는 명령 한 줄을 `cmd` 울타리에 쓴다".format(iid))
        line = parsed["cmd"][0]
        bad = execmod.line_problems(child_row(t), "되돌림" if section == "되돌리기" else "실행승인", line, d["cwd"])
        if bad:
            raise Refuse("{}의 꼴 문제: {}".format(iid, bad[0]))
    else:
        if len(parsed["글"]) != 1:
            raise Refuse("{}는 글 한 줄로 쓴다".format(iid))
        line = parsed["글"][0]
    general, unknown = generalize(line, d["values"])
    general, secret = masked(general)
    stale = stale_values(d["cwd"], general, unknown, d["commit"]) + secret
    if stale:
        raise Refuse("{}에 실행마다 달라지는 값이 남음({}): 이번 실행에만 필요한 내용이면 이번 실행 몫에 쓴다".format(iid, ", ".join(stale)))
    return general


def merge_own(d, own, t, extras):
    """판정한 항목에 작성자 몫을 합쳐 조립할 항목 목록을 낸다. 다시 쓸 항목이 빠지면 거부한다."""
    blobs = tree_blobs(d["cwd"], d["commit"])
    if blobs is None:
        raise Refuse("올릴 커밋의 파일 목록을 읽지 못함")
    ev = Evidence(d["cwd"], d["commit"], blobs)
    items = [dict(x, note="") for x in d["items"]]
    by_id = {x["id"]: x for x in items}
    dropped = dropped_items(own, by_id)
    blocks = devflow_lib.sections(own.get("다시 쓴 항목", ""), level=3)
    unknown = [k for k in blocks if k not in by_id]
    if unknown:
        raise Refuse("절차서에 없는 항목: {}".format(", ".join(unknown)))
    missing = [x["id"] for x in items if x["status"] == REWRITE and x["id"] not in blocks and x["id"] not in dropped]
    if missing:
        raise Refuse("다시 쓸 항목이 빠짐: {} (`그대로: 이유`도, 「뺄 항목」도 된다)".format(", ".join(missing)))
    both = sorted(set(blocks) & set(dropped))
    if both:
        raise Refuse("다시 쓰면서 뺄 수 없음: {}".format(", ".join(both)))
    for iid, reason in dropped.items():
        by_id[iid]["status"], by_id[iid]["note"] = REMOVED, reason
    written = []
    for iid, block in blocks.items():
        x, parsed = by_id[iid], parse_own_block(block)
        was_flagged = x["status"] == REWRITE
        if parsed["종류"] in (READ, WRITE) and x["kind"] == CMD:
            x["mode"] = parsed["종류"]
        if parsed["그대로"] is not None:
            if x["stale"] or left_places(x["rendered"].replace("{{줄:", "")):
                raise Refuse("{}는 지난 실행의 값이나 빈 자리 값이 남아 그대로 둘 수 없음".format(iid))
            line = x["rendered"]
            x["note"] = parsed["그대로"]
        else:
            x["text"] = own_text_of(parsed, x["kind"], iid, d, t, x["section"])
            x["stale"] = []
            line = x["text"]
            written.append(x)
        none_ok = x["kind"] == TEXT or x["mode"] == READ or is_git_line(line)
        x["evidence"], x["basis"] = evidence_from(parsed["근거"], ev, iid, none_ok)
        x["status"] = REWRITTEN if was_flagged else DRIFT
    for title, block in devflow_lib.sections(own.get("더한 항목", ""), level=3).items():
        parts = [p.strip() for p in title.split("|")]
        if len(parts) < 2 or parts[1] not in SECTION_NAMES:
            raise Refuse("더한 항목의 제목은 `A1 | 절 이름 | C5 앞`: {}".format(title))
        parsed = parse_own_block(block)
        kind = CMD if parts[1] in ("명령", "되돌리기") else TEXT
        mode = parsed["종류"] if parsed["종류"] in (READ, WRITE) else WRITE
        general = own_text_of(parsed, kind, parts[0], d, t, parts[1])
        evidence, basis = evidence_from(parsed["근거"], ev, parts[0], kind == TEXT or mode == READ or is_git_line(general))
        new = {"id": parts[0], "section": parts[1], "kind": kind, "mode": mode, "text": general, "evidence": evidence, "basis": basis, "stale": [],
               "status": ADDED, "why": "", "detail": "", "old": "", "note": "", "rendered": general}
        at = next((i for i, x in enumerate(items) if len(parts) > 2 and x["id"] == parts[2].split()[0]), None)
        if len(parts) > 2 and at is None:
            raise Refuse("더한 항목의 자리를 찾지 못함: {}".format(title))
        if at is None:
            same = [i for i, x in enumerate(items) if x["section"] == parts[1] and not x["text"].startswith(AFTER_KEEP)]
            at = (same[-1] + 1) if same else len(items)
        items.insert(at, new)
        written.append(new)
    # 번호는 차례가 정해진 뒤에: 작성자가 쓴 번호를 항목에 묶고, 뺀 줄을 가리키는 항목은 거부한다
    alive = [x for x in items if x["section"] == "명령" and x["status"] != REMOVED]
    numbers = {n: x["id"] for n, x in enumerate(alive, len(extras) + 1)}
    for x in written:
        x["text"], unmatched = link_lines(x["text"], numbers)
        if unmatched:
            raise Refuse("{}가 항목이 아닌 줄을 가리킴: 명령 {}".format(x["id"], ", ".join(unmatched)))
    values = dict(d["values"], **line_values(items, len(extras)))
    for x in items:
        if x["status"] == REMOVED:
            continue
        x["rendered"] = render(x["text"], values)
        left = [n for n in left_places(x["rendered"]) if n.startswith("줄:")]
        if left:
            raise Refuse("{}가 뺀 항목을 가리킴: {}. 그 항목을 다시 쓰거나 함께 뺀다".format(x["id"], ", ".join(n[2:] for n in left)))
    return items


# ---------------------------------------------------------------- 조립

def cell(lines):
    return "\n".join(lines) if lines else "- 없음"


def own_key(own, key):
    m = re.search(r"^-?\s*{}\s*:\s*(.*)$".format(re.escape(key)), own.get("자식", ""), flags=re.M)
    return m.group(1).strip() if m else ""


def section_text(items, section):
    """한 절의 글. 이어진 명령 항목은 `cmd` 울타리로 묶는다."""
    out, in_fence = [], False
    for x in items:
        if x["section"] != section or x["status"] == REMOVED:
            continue
        if (x["kind"] == CMD) != in_fence:
            out.append("```cmd" if not in_fence else "```")
            in_fence = not in_fence
        out.append(x["rendered"])
    if in_fence:
        out.append("```")
    return "\n".join(out)


def command_items(items, section="명령"):
    return [x for x in items if x["section"] == section and x["kind"] == CMD and x["status"] != REMOVED]


def kept_flagged(items):
    return [x for x in items if x["status"] == REWRITTEN and x.get("note")]


def change_lines(items, brief=False):
    """앞 판과의 차이. 고친 항목만 앞과 새 줄을 보인다. 그대로 둔 항목은 화면(brief)에서 건수 한 줄이고 이유는 판정자가 본다.
    뺀 항목은 「알릴 것」에 있다."""
    kept = kept_flagged(items)
    out = ["그대로 둠 {}: {}".format(len(kept), ", ".join(x["id"] for x in kept))] if brief and kept else []
    for x in items:
        if any(x is k for k in kept):
            if not brief:
                out.append("{} {} {}, 그대로 둠: {}".format(x["id"], x["section"], x["why"], x["note"]))
        elif x["status"] == REWRITTEN:
            out += ["{} {} {}: {}".format(x["id"], x["section"], x["why"], x["detail"]), "  앞: " + x["old"], "  새: " + x["rendered"]]
        elif x["status"] == DRIFT:
            out += ["{} {} [달라진 재사용 항목]: 근거가 그대로인데 작성자가 고침".format(x["id"], x["section"]), "  앞: " + x["old"], "  새: " + x["rendered"]]
        elif x["status"] == ADDED:
            out += ["{} {} [더함]".format(x["id"], x["section"]), "  새: " + x["rendered"]]
    return out


def dropped_lines(items):
    return ["- [뺀 항목] {}({}): {}. 앞 판: {}".format(x["id"], x["section"], x.get("note", ""), x.get("old", "")) for x in items if x["status"] == REMOVED]


def mine_count(own, extras):
    return sum(len(as_items(own.get(name, ""))) for name in OWN_CELLS) + len(as_items(own.get("배포 뒤 적을 문서", ""))) + len(extras)


def compose_text(t, d, items, own, extras):
    tid, env, commit = t["id"], d["env"], d["commit"]
    values = d["values"]
    all_lines = extras + [x["rendered"] for x in command_items(items)]
    hold = as_items(own["되돌릴 수 없는 단계"])
    user_run = ["- {} 명령 {}: {}".format(USER_RUN, i, x[len(USER_RUN):].strip()) for i, x in enumerate(all_lines, 1) if x.startswith(USER_RUN)]
    plain = lambda s: s.strip().lstrip("-0123456789. ").strip()
    # 재사용하는 확인은 글자로 가리지 않고 전부 싣는다. 쓰기 확인이 사람 눈을 비켜 이어지지 않게 한다
    checks = ["- [배포 뒤 확인 {}] {}".format(x["id"], plain(x["rendered"])) for x in items if x["section"] == "배포 뒤 확인" and x["status"] != REMOVED]
    marked = ["- {}: {}".format(x["id"], plain(x["rendered"])) for x in items if x["section"] == "사전 조건" and x["status"] != REMOVED
              and devflow_lib.PROPERTY_MARK.search(x["rendered"])]
    decide_lines = ["- **{}아래 명령 {}줄을 이 순서로 실행해 {}에 {}을 올릴지 정해 주세요.** 이 승인이 배포 실행의 승인입니다.".format(
        HOLD_TAG + " " if hold else "", len(all_lines), env, commit[:7])]
    decide_lines += ["  - 되돌릴 수 없음: " + x.lstrip("- ") for x in hold]
    decide_lines += ["  - 선택지: (가) 승인 / (나) 보류", "  - 작업 폴더: {}".format(values.get("배포 폴더", "")), "", "  ```cmd"]
    decide_lines += ["  " + x for x in all_lines] + ["  ```"]
    decide_lines += as_items(own.get("정해 주실 것", ""))
    # 이번 실행 몫을 칸마다 되풀이하지 않는다: 확인은 리뷰 자료에, 미룬 실물 확인은 「하실 일」에 한 번씩
    material = ["재사용 항목은 절차서에서 값만 바꿨습니다. 아래는 다시 쓴 항목과 이번 실행 몫입니다.", ""]
    changes = change_lines(items, brief=True)
    if changes:
        material += ["다시 쓴 항목(앞 판과의 차이):"] + changes + [""]
    material += ["배포 전 확인:"] + as_items(own["배포 전 확인"]) + ["", "배포 뒤 확인(이번 실행):"] + as_items(own["배포 뒤 확인"])
    todo = as_items(own["미룬 실물 확인"]) + user_run + as_items(own.get("하실 일", ""))
    notify = ["- 올릴 커밋: `{}`. 배포 폴더: `{}`".format(commit, values.get("배포 폴더", ""))] + dropped_lines(items) + checks + marked \
        + ["- [알림] " + x for x in d["notices"]] \
        + ["- 배포 뒤 적을 문서: " + (own["배포 뒤 적을 문서"].strip() or "없음")] + as_items(own.get("알릴 것", ""))
    grounds = ["- {}: {}({})".format(x["id"], ", ".join(sorted(x["evidence"])) if x["basis"] == BASIS_FILES else "근거 파일 " + x["basis"], x["mode"])
               for x in items if x["kind"] == CMD and x["status"] != REMOVED]
    out = ["# {} 배포 계획: {}({}) 결과".format(tid, env, commit[:7]), "", "## 승인 화면", "### 리뷰 자료"] + material
    out += ["", "### 정해 주실 것"] + decide_lines
    out += ["", "### 하실 일·허용 요청", cell(todo), "", "### 알릴 것", cell(notify), "", "### 답하신 것의 반영", cell(as_items(own.get("답하신 것의 반영", ""))),
            "", "### 확인 안 된 것", cell(as_items(own.get("확인 안 된 것", ""))), "", "### 건수만",
            "- 명령 {}줄, 항목 {}, 이번 실행 몫 {}".format(len(all_lines), sum(1 for x in items if x["status"] != REMOVED), mine_count(own, extras)), ""]
    out += ["## 결정 지도", "- 이 task가 내린 결정: 다시 쓴 항목과 이번 실행 몫(작성자), 재사용 항목은 {} 절차서(저장 커밋 {})와 기계 판정.".format(env, d["saved_commit"][:7]), "",
            "## 스스로 줄임", "없음", "", "## 본문", "### 올릴 것", "- 커밋: {}".format(commit), "- 배포 폴더: `{}`".format(values.get("배포 폴더", "")), ""]
    if own.get("설명", "").strip():
        out += ["### 설명", own["설명"].strip(), ""]
    out += ["### 사전 조건", section_text(items, "사전 조건") or "없음", "", "#### 이번 실행의 배포 전 확인"] + as_items(own["배포 전 확인"])
    out += ["", "### 명령 목록과 근거"] + grounds + ["", "### 배포 뒤 확인", section_text(items, "배포 뒤 확인") or "없음", "", "#### 이번 실행의 확인"]
    out += as_items(own["배포 뒤 확인"]) + ["", "#### 미룬 실물 확인"] + (as_items(own["미룬 실물 확인"]) or ["- 없음"])
    for name in ("연결 경로 대조", "멈추는 조건"):
        if own.get(name, "").strip():
            out += ["", "### " + name, own[name].strip()]
    out += ["", "### 되돌리기", section_text(items, "되돌리기") or "없음", "", "### 배포 뒤 적을 문서", own["배포 뒤 적을 문서"].strip() or "없음", "",
            "## 자식 목록", "나눈 기준: 환경 {}, 시점 지금.".format(env), "",
            "### 자식: 배포 실행: {}({})".format(env, commit[:7]), "- kind: deploy-exec", "- flow:", "- depends_on: " + own_key(own, "depends_on"), "- difficulty: 일반",
            "- closes_ac: " + own_key(own, "closes_ac"), "- partial_ac: " + own_key(own, "partial_ac"),
            "- 한 줄: 승인된 {} 배포 명령 {}줄을 순서대로 실행하고 배포 뒤 확인을 거쳐 유지·되돌림을 정한다".format(env, len(all_lines)),
            "#### 범위", "이 task({}) 「승인 화면」의 명령 목록과 본문 「배포 뒤 확인」, 「되돌리기」를 그대로 실행한다.".format(tid),
            "#### 판정 기준", "1. `references/kinds/deploy-exec.md` 「자체 검증」을 따른다.", "2. `deployed_commit`이 {}이다.".format(commit)]
    extra_rule = own_key(own, "판정 기준")
    if extra_rule:
        out.append("3. " + extra_rule)
    out += ["#### 건드릴 파일", "(없음)", "#### 시그니처와 결정 번호", "- 없음", "#### 정본의 절", "- references/kinds/deploy-exec.md", "",
            "## 실행 기록", "- `deploy_reuse.py --compose`가 {} 절차서와 `own.md`로 만들었습니다.".format(env), ""]
    return "\n".join(out)


def manifest_path(t):
    return os.path.join(t["_dir"], MANIFEST_FILE)


def read_manifest(t):
    path = manifest_path(t)
    if not os.path.isfile(path):
        return None
    try:
        return json.loads(devflow_lib.read_text(path))
    except ValueError:
        return None


def earlier_env_plan(tasks, t, env):
    """같은 실행의 다른 환경 배포 계획(운영 계획의 앞 환경)."""
    if env != "운영":
        return None
    return next((o for o in tasks.values() if o is not t and o.get("kind") == "deploy-plan" and env_of(o) == "dev"), None)


def compose(run_dir, tid):
    """(종료 코드, 한 줄). 작성자 몫이 모자라거나 판정이 달라졌으면 result.md를 쓰지 않는다."""
    tasks = devflow_lib.load_tasks(run_dir)
    t = tasks.get(tid)
    if t is None or t.get("kind") != "deploy-plan":
        return 3, "배포 계획 task가 아님: {}".format(tid)
    decision = read_decision(t)
    if decision.get("decision") != REUSE:
        return 3, "재사용 판정이 아님: 처음부터 쓴다"
    d = evaluate(run_dir, t, tasks)
    if d["decision"] != REUSE or d["digest"] != decision.get("digest") or d["commit"] != decision.get("commit"):
        return 3, "판정 뒤 달라짐({}): `--decide`를 다시 돌린다".format(d.get("reason") or "절차서나 커밋이 바뀜")
    own_path = os.path.join(t["_dir"], OWN_FILE)
    if not os.path.isfile(own_path):
        return 3, "작성자 몫이 없음: {}".format(own_path)
    own = devflow_lib.sections(devflow_lib.read_text(own_path), level=2)
    missing = [name for name in OWN_REQUIRED if not own.get(name, "").strip()]
    if missing:
        return 3, "작성자 몫에 빠진 절: {} (없으면 `없음`이라고 쓴다)".format(", ".join(missing))
    if d["commit"] not in own["올릴 커밋"]:
        return 3, "작성자의 올릴 커밋이 {}가 아님".format(d["commit"])
    for name, body in own.items():
        if name not in OWN_FENCED and any(devflow_lib.CMD_FENCE.match(line.strip()) for line in body.splitlines()):
            return 3, "명령은 「추가 명령」, 「다시 쓴 항목」, 「더한 항목」에만 쓴다: {}".format(name)
        if name not in OWN_FENCED and linked_lines(body):
            # 추가 명령과 더하고 뺀 항목으로 번호가 밀린다. 항목에 묶으면 조립 때 실제 번호가 들어간다
            return 3, "「{}」에 줄 번호가 있음: 번호는 밀리므로 `{{{{줄:C4}}}}`처럼 항목 id로 쓴다".format(name)
    earlier = earlier_env_plan(tasks, t, d["env"])
    if earlier and not own_key(own, "depends_on"):
        return 3, "같은 실행에 앞 환경 계획 {}가 있음: 「자식」에 depends_on을 쓴다".format(earlier["id"])
    if earlier and not as_items(own["배포 전 확인"]):
        return 3, "같은 실행에 앞 환경 계획 {}가 있음: 배포 전 확인 맨 앞에 앞 환경 실행의 사전 조건을 쓴다".format(earlier["id"])
    extras = devflow_lib.cmd_lines(own.get("추가 명령", ""))
    for line in extras:
        bad = execmod.line_problems(child_row(t), "실행승인", line, d["cwd"])
        if bad:
            return 3, "추가 명령의 꼴 문제({}): {}".format(line[:40], bad[0])
    try:
        items = merge_own(d, own, t, extras)
    except Refuse as e:
        return 3, str(e)
    numbers = dict(d["values"], **line_values(items, len(extras)))
    shown = {name: render(body, numbers) if name not in OWN_FENCED else body for name, body in own.items()}
    text = compose_text(t, d, items, shown, extras)
    left = left_places(text)
    if left:
        return 3, "채우지 못한 자리 값: {}".format(", ".join(left))
    devflow_lib.write_text(os.path.join(t["_dir"], "result.md"), text)
    hold = "\n".join("- " + masked(generalize(x.lstrip("- "), d["values"])[0])[0] for x in as_items(own["되돌릴 수 없는 단계"]))
    manifest = {"env": d["env"], "commit": d["commit"], "saved": d["saved_commit"], "digest": d["digest"], "extras": len(extras),
                "extra_lines": extras, "mine": mine_count(own, extras), "notices": d["notices"], "hold": hold, "items": items}
    devflow_lib.write_text(manifest_path(t), json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    plan = line_plan(run_dir, t)
    d.update(reused=plan["reused"], rewrite=plan["rewritten"], why_evidence=plan["why_evidence"], why_other=plan["why_other"])
    write_decision(t, d)
    return 0, "result.md를 만들었습니다: 재사용 {}, 다시 씀 {}, 명령 {}줄".format(plan["reused"], plan["rewritten"], len(plan["lines"]))


def fresh(run_dir, tid, why):
    t = devflow_lib.load_tasks(run_dir).get(tid)
    if t is None:
        return 3, "task를 찾지 못함: {}".format(tid)
    write_decision(t, judged(FRESH, WHY_HUMAN, " ".join(str(why).split()), env=env_of(t)))
    return 0, "처음부터 씁니다: {}".format(why)


# ---------------------------------------------------------------- 화면

def expected_lines(section, items, stored, values):
    """[(id, 기대 줄, 표시)]. 재사용 항목의 기대 줄은 조립 기록을 믿지 않고 절차서에서 다시 만든다."""
    out = []
    for x in command_items(items, section):
        if x["status"] == KEEP and x["id"] in stored:
            out.append((x["id"], render(stored[x["id"]]["text"], values), KEEP))
        else:
            out.append((x["id"], x["rendered"], {KEEP: DRIFT}.get(x["status"], DRIFT if x["status"] == DRIFT else x["status"])))
    return out


def labeled(expected, actual):
    """실제 줄마다 (번호, 표시, 줄). 기대와 다른 줄은 `달라짐`이다. (줄 목록, 달라진 항목 id)."""
    out, drifted = [], []
    keys = [line for _, line, _ in expected]
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, keys, actual, autojunk=False).get_opcodes():
        if op == "equal":
            out += [(b1 + i + 1, expected[a1 + i][2], actual[b1 + i]) for i in range(a2 - a1)]
        else:
            out += [(n + 1, DRIFT, actual[n]) for n in range(b1, b2)]
            drifted += [expected[i][0] for i in range(a1, a2) if expected[i][0]]
    return out, drifted


def line_plan(run_dir, t):
    """승인 화면의 줄과 머리의 셈. 재사용으로 조립한 것이 아니면 None. 실제 도는 줄은 result.md에서 읽고, 달라짐은 절차서와 견준다."""
    if read_decision(t).get("decision") != REUSE:
        return None
    manifest = read_manifest(t)
    if not manifest:
        return None
    tasks = devflow_lib.load_tasks(run_dir)
    items = manifest["items"]
    head, body, problem = load_procedure(run_dir, manifest["env"])
    moved = not head or bool(problem) or str(head.get("digest", "")) != manifest["digest"]
    stored = {} if moved else {x["id"]: x for x in parse_items(body["항목"])}
    values = dict(values_for(run_dir, tasks, t, manifest["commit"], manifest["saved"]), **line_values(items, manifest["extras"]))
    drifted = [x["id"] for x in items if x["status"] == DRIFT]
    ids = {x["id"] for x in items}
    drifted += [i for i in stored if i not in ids]
    drifted += [x["id"] for x in items if x["status"] == KEEP and stored and x["id"] not in stored]
    expected = [("", line, THIS_RUN) for line in manifest.get("extra_lines", [])] + expected_lines("명령", items, stored, values)
    result = os.path.join(t["_dir"], "result.md")
    text = devflow_lib.read_text(result) if os.path.isfile(result) else ""
    lines, off = labeled(expected, devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"])))
    undo, off_undo = labeled(expected_lines("되돌리기", items, stored, values), devflow_lib.cmd_lines(execmod.heading_section(text, "되돌리기")))
    written = devflow_lib.sections(text, level=2).get("본문", "")
    prose = [x["id"] for x in items if x["status"] == KEEP and x["kind"] == TEXT
             and (render(stored[x["id"]]["text"], values) if x["id"] in stored else x["rendered"]) not in written]
    drifted = sorted(set(drifted + off + off_undo + prose))
    judged_items = [x for x in items if x["status"] != REMOVED]
    rewritten = [x for x in judged_items if x["status"] == REWRITTEN]
    return {"lines": lines, "undo": undo, "drifted": drifted, "moved": moved, "rewritten": len(rewritten),
            "why_evidence": sum(1 for x in rewritten if x["why"] == WHY_EVIDENCE), "why_other": sum(1 for x in rewritten if x["why"] == WHY_OTHER),
            "added": sum(1 for x in judged_items if x["status"] == ADDED), "removed": [x["id"] for x in items if x["status"] == REMOVED],
            "reused": sum(1 for x in judged_items if x["status"] == KEEP and x["id"] not in drifted), "mine": manifest.get("mine", 0),
            "saved": manifest["saved"], "commit": manifest["commit"], "env": manifest["env"], "notices": manifest.get("notices", [])}


def annotate(run_dir, t, cell_text):
    """「정해 주실 것」의 cmd 울타리를 번호와 표시가 붙은 줄로 보인다. 접지 않고, 되돌리기도 함께 싣는다(result.md는 고치지 않는다)."""
    if not devflow_lib.run_from_v120(run_dir):
        return cell_text
    plan = line_plan(run_dir, t)
    if not plan:
        return cell_text
    out, inside, done = [], False, False
    for line in (cell_text or "").splitlines():
        s = line.strip()
        if not inside and not done and devflow_lib.CMD_FENCE.match(s):
            inside = True
            continue
        if inside:
            if s.startswith("```"):
                inside, done = False, True
                out += ["  {}. [{}] {}".format(n, label, text) for n, label, text in plan["lines"]]
                out += ["  되돌리기 {}. [{}] {}".format(n, label, text) for n, label, text in plan["undo"]] or ["  되돌리기: 없음"]
            continue
        out.append(line)
    return "\n".join(out)


def sheet_lines(run_dir, t):
    """한 장에 실을 줄. 재사용 계획이 아니면 빈 목록."""
    plan = line_plan(run_dir, t)
    if not plan:
        return []
    return ["{}. [{}] {}".format(n, label, text) for n, label, text in plan["lines"]] + [""] \
        + ["되돌리기 {}. [{}] {}".format(n, label, text) for n, label, text in plan["undo"]]


def screen_head(run_dir, t):
    """승인 화면 머리 줄. 재사용 계획이 아니면 빈 목록."""
    if t.get("kind") != "deploy-plan" or not devflow_lib.run_from_v120(run_dir) or t.get("status") in kinds.CLOSED_STATUSES:
        return []
    if read_decision(t).get("decision") != REUSE:
        return []
    plan = line_plan(run_dir, t)
    if plan is None:
        return ["! 재사용 판정인데 `--compose`로 조립하지 않았습니다"]
    tail = ", 더함 {}".format(plan["added"]) if plan["added"] else ""
    if plan["removed"]:
        tail += ", 뺌 {}({})".format(len(plan["removed"]), ", ".join(plan["removed"]))
    out = ["지난 {} 계획에서 재사용 {}, 다시 씀 {}(근거 바뀜 {}, 그 밖 {}), 이번 실행 몫 {}{}. {} → {}, 명령 {}줄".format(
        plan["env"], plan["reused"], plan["rewritten"], plan["why_evidence"], plan["why_other"], plan["mine"], tail,
        plan["saved"][:7], plan["commit"][:7], len(plan["lines"]))]
    if plan["drifted"]:
        out[0] += ", 달라진 재사용 항목 {}".format(len(plan["drifted"]))
        out.append("! 달라진 재사용 항목: {}. 근거가 그대로인데 절차서와 다릅니다. 줄을 보고 판단해 주세요".format(", ".join(plan["drifted"])))
    if plan["moved"]:
        out.append("! 절차서가 판정 뒤 바뀌었습니다: 재사용 항목을 대조하지 못했습니다")
    out += ["! 알림: " + x for x in plan["notices"]]
    return out


# ---------------------------------------------------------------- 판정자 대조와 측정

def check(run_dir, tid):
    """(통과, 줄 목록). 읽기 판정이 재사용 항목을 다시 읽는 대신 이것을 돌린다. 달라진 재사용 항목은 실패가 아니라 사람에게 올린다."""
    tasks = devflow_lib.load_tasks(run_dir)
    t = tasks.get(tid)
    manifest = read_manifest(t) if t else None
    if t is None or read_decision(t).get("decision") != REUSE or not manifest:
        return False, ["재사용으로 조립한 계획이 아님"]
    ok = True
    cwd = deploy_folder(run_dir, tasks, t)
    values = values_for(run_dir, tasks, t, manifest["commit"], manifest["saved"])
    out = ["값: {} = {}".format(k, v) for k, v in values.items() if ":" not in k]
    values = dict(values, **line_values(manifest["items"], manifest["extras"]))
    for x in manifest["items"]:
        if x["status"] != REMOVED and render(x["text"], values) != x["rendered"]:
            ok = False
            out.append("값 치환이 다름: {}".format(x["id"]))
    blobs = tree_blobs(cwd, manifest["commit"])
    ev = Evidence(cwd, manifest["commit"], blobs or {})
    kept = [x for x in manifest["items"] if x["status"] == KEEP]
    moved = [x["id"] for x in kept if blobs is None or any(ev.hash_of(k) != h for k, h in x["evidence"].items())]
    if moved:
        ok = False
        out.append("재사용 항목의 근거가 다름: {}".format(", ".join(moved)))
    else:
        out.append("재사용 항목 {}: 근거 해시 일치".format(len(kept)))
    plan = line_plan(run_dir, t)
    if plan["drifted"]:
        out.append("달라진 재사용 항목(사람이 봄): {}".format(", ".join(plan["drifted"])))
    if plan["moved"]:
        out.append("절차서가 판정 뒤 바뀌어 대조하지 못함")
    out.append("다시 쓴 항목 {}, 더함 {}, 뺌 {}".format(plan["rewritten"], plan["added"], len(plan["removed"])))
    out += change_lines(manifest["items"]) + dropped_lines(manifest["items"])
    text = devflow_lib.read_text(os.path.join(t["_dir"], "result.md")) if os.path.isfile(os.path.join(t["_dir"], "result.md")) else ""
    if left_places(text):
        ok = False
        out.append("채우지 못한 자리 값이 남음: {}".format(", ".join(left_places(text))))
    return ok, out


def measure_line(tasks):
    """`collect.py --measure`의 한 줄. 판정이 하나도 없는 실행(옛 실행)은 빈 글이다."""
    reused, rewritten, why, seen = 0, 0, Counter(), False
    for t in tasks.values():
        if t.get("kind") != "deploy-plan":
            continue
        d = read_decision(t)
        seen = seen or bool(d)
        if d.get("decision") == REUSE:
            reused += int(d.get("reused", "0") or 0)
            rewritten += int(d.get("rewrite", "0") or 0)
        elif d.get("decision") == FRESH:
            why[d.get("kind", "")] += 1
    if not seen:
        return ""
    detail = "({})".format(", ".join("{} {}".format(k, n) for k, n in sorted(why.items()))) if why else ""
    return "- 배포 계획 재사용: 재사용 항목 {}, 다시 쓴 항목 {}, 처음부터 {}{}".format(reused, rewritten, sum(why.values()), detail)


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 4:
        print(__doc__)
        return 2
    run_dir, tid, op = argv[1], argv[2], argv[3]
    if op == "--decide":
        t = devflow_lib.load_tasks(run_dir).get(tid)
        if t is None:
            print("task를 찾지 못함: " + tid)
            return 3
        print(decision_line(decide(run_dir, t)))
        return 0
    if op == "--compose":
        rc, msg = compose(run_dir, tid)
        print(msg)
        return rc
    if op == "--check":
        ok, lines = check(run_dir, tid)
        print("\n".join(lines))
        print("판정: " + ("통과" if ok else "실패"))
        return 0 if ok else 3
    if op == "--fresh" and len(argv) == 5:
        rc, msg = fresh(run_dir, tid, argv[4])
        print(msg)
        return rc
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
