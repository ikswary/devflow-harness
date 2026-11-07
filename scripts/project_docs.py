"""프로젝트 산출물(설계 7.5절). 1.2.0부터 시작한 실행은 프로젝트 `docs/`를 기준본으로 떠 변경판을 만들고, 마무리에서 코드와 함께 넣는다.

실행 폴더(`spec\\`·`ui\\`·`design\\`)에는 이번 실행이 고치는 파일만 있고, 프로젝트 원본의 사본은 `base\\docs\\…`에 있다(시작 커밋은 run.md `docs_base_commit`).
승인 해시는 정상 경로가 달라짐으로 뜨지 않게 승인 순간이 아니라 정본을 옮기고 고친 뒤에 찍는다: task 완료 전이(쓴 정본과 `앞 정본 줄`의 파일)와 `apply_revision.py`다.
찍은 판은 `approved\\`에 사본으로 둔다. 해시와 낡음은 판정 재료이고 승인을 대신하지 않는다.

사용:
  python project_docs.py {실행 폴더} --start
    실행 시작 점검: 기준본(아직 없을 때만), 작성 문서 낡음. 프로젝트 설정 `git 훅 경고`가 비면 `묻기:` 줄만 낸다(시작 질문에 묶는다)
  python project_docs.py {실행 폴더} --base
  python project_docs.py {실행 폴더} {마무리 id} --insert [코드 폴더] [--take "{문서}#{절}=이번 실행|프로젝트"] [--take "{문서}#(파일 전체)=뺌"]
    절 단위로 합쳐 넣고 tasks\\{id}\\docs-insert.md에 넣을 산출물 표를 쓴다. 코드 폴더 기본값은 통합 폴더, 흐름이 하나면 그 폴더다.
    둘 다 없으면 쓰지 않고 표만 낸다. 흐름이 둘 이상인데 통합 폴더가 없으면 종료 2다. 모르는 답도 종료 2다.
    종료 0 / 3(같은 절을 두 곳에서 고쳤다: 그 파일은 넣지 않는다. 메인이 묻고 --take로 반영한다)
  python project_docs.py {실행 폴더} {마무리 id} --generate {코드 폴더} [--check]
    프로젝트 설정 「생성 명령」을 돌려 표준 출력을 대상 파일에 쓴다. --check는 쓰지 않고 대조한다. 종료 0 / 3(--check의 다름).
    실패와 시간 초과는 사유만 내고 막지 않는다. 시간 제한(프로세스 나무째 종료), 전후 `git status` 대조, 코드 끝(sha)별 한 번만 돈다.
    작성자가 낸 `- 생성 명령 제안:` 줄은 실행 승인 화면에 싣고, 그 승인 뒤에 task_set.py가 설정에 등록한다. 등록 전에는 돌리지 않는다
  python project_docs.py {실행 폴더} --stale [--ok {문서}]
    작성 문서의 지키는 경로가 기준 커밋 뒤에 바뀌었으면 `확인 필요`로 적는다(_workspace\\policies\\docs-state.md). --ok는 그 문서의 기준 커밋을 지금 끝으로 옮긴다
  python project_docs.py {실행 폴더} --close "{줄}"
    닫힌 위험·미확인 항목을 상태 파일에 둔다. 다음 넣기가 문서에서 함께 지운다
  python project_docs.py {실행 폴더} --hook
  python project_docs.py {실행 폴더} --unhook
    묻고 받은 답을 프로젝트 설정 `git 훅 경고`에 적는다. --hook은 pre-commit을 두고(적용함), --unhook은 우리 훅만 지운다(안 함). 사용자 훅은 바이트로 가려 건드리지 않는다
  python project_docs.py --hook-check {작업 공간}
    pre-commit 훅이 부른다. 경고만 하고 늘 종료 0이다
"""
import difflib
import fnmatch
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime

import delegation
import devflow_lib
import kinds
import shadow_check

BASE_DIR = "base"
APPROVED_DIR = "approved"
HASH_FILE = "hashes.md"
ASKED_DIR = "asked"   # approved 아래. 승인을 물을 때의 판(사람이 본 판)
GEN_CACHE = "generated-cache"   # 코드 끝별 생성 명령 결과
INSERT_FILE = "docs-insert.md"
INSERTED_DIR = "inserted"
OURS_DIR = "inserted-ours"   # 넣기 전의 프로젝트 쪽. 다시 넣을 때 앞 넣기를 프로젝트의 변경으로 오해하지 않게 한다
CHOICE_FILE = "docs-choice.md"
STATE_FILE = "docs-state.md"
BASE_KEY = "docs_base_commit"
DOCS_ROOT = "docs"
NO_GIT = "git 저장소 아님"
NOT_APPLIED = "1.2.0부터 시작한 마무리가 아니거나 이 실행에 기준본이 없어 넣지 않습니다"
NO_GENERATOR = "생성 명령 없음: 제안 도면과 생성본을 대조하지 못함"
HOOK_MARK = "devflow-harness 문서 낡음 경고"
HOOK_SKIPPED = "git 훅을 두지 못함"
SAME, CHANGED, UNAPPROVED, TWO_PLACES = "승인한 그대로", "승인 뒤 달라짐", "승인 없이 들어감", "같은 절 두 곳"
AFTER_SCREEN = "승인 화면 뒤 달라짐"
UNCHECKED = "대조하지 못함"   # 물을 때의 사본이 없다. 사람이 본 판인지 모르므로 승인한 그대로로 적지 않는다
AFTER_INSERT, NOT_YET, SKIPPED = "넣은 뒤 달라짐", "아직 넣지 않음", "넣지 않고 뺌"
PROPOSED = "등록할 생성 명령"
PROPOSED_TAIL = " (승인하면 등록해 다음부터 돕니다)"
NOTIFIED, DELEGATED = "알림", "위임"
PASSED_BY = {NOTIFIED: "승인 없이 알림으로 지나감", DELEGATED: "승인 없이 위임으로 지나감"}   # 5.1절의 길이라 먼저 보실 것에 올리지 않는다
NEEDS_CHECK = "확인 필요"
RUN_SIDE, PROJECT_SIDE, SKIP_SIDE = "이번 실행", "프로젝트", "뺌"
WHOLE_FILE, HEADER = "(파일 전체)", "(머리글)"
HOOK_KEY = "git 훅 경고"
HOOK_ON, HOOK_OFF = "적용함", "안 함"
GLOSSARY = "docs/product/glossary.md"
UNVERIFIED_DOC = "docs/operations/unverified.md"
TEST_MAP = "docs/generated/test-map.md"
TEST_MAP_HEAD = "| 인수 기준 | 시험 파일 |\n|---|---|\n"
FLOW_WORDS = ("결정", "흐름도")   # 설계 정본 가운데 프로젝트에 넣는 절. 자식 행처럼 그 실행에만 참인 줄은 실행 폴더에 남는다
HISTORY = "## 변경 이력"
TERMS = "## 용어"
SECTION_RE = re.compile(r"^(##) .+$")
SUB_RE = re.compile(r"^(###) .+$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
PRIOR_LINE = re.compile(r"앞 정본 줄:\s*([^\s:|]+)")
PAIR_LINE = re.compile(r"지금:\s*(.+?)\s*\|\s*바뀜:\s*(.+?)\s*$", re.M)
OPTION_LINE = re.compile(r"^\s*(?:[-*]\s+)?(?:선택지\s*)?\(([가-힣])\)(의 문장(?:\([^()]*\))?:|의 앞 정본 줄:)?\s*(.+?)\s*$")
JUDGE_ALT = re.compile(r'^-\s*대안 문장:\s*"([^"]+)"', re.M)
LOCATION_TAIL = re.compile(r"\s*\(`?[^()\s`]+:\d+`?\)$")
WRAPPERS = {'"': '"', "'": "'", "`": "`", "“": "”", "‘": "’"}
ITEM_LINE = re.compile(r"^[-*]\s+(.+?)\s*$")
NOT_A_CHOICE = ("점검 확인", "되물음", "알림")   # 답의 지점이 이 말로 시작하면 선택지를 고른 줄이 아니다
LIST_MARK = re.compile(r"^(?:[-*]\s+)?(?:\([가-힣]\)\s*)?")
PROPOSAL_SHOWN = re.compile(r"^- " + PROPOSED + ": (.+)" + re.escape(PROPOSED_TAIL) + r"\s*$", re.M)
PROPOSAL_LINE = re.compile(r"^\s*(?:-\s*)?생성 명령 제안:\s*(.+?)\s*$", re.M)
GUARD_LINE = re.compile(r"^\s*(?:-\s*)?지키는 경로:\s*(\S+)\s*\|\s*(.+?)\s*$", re.M)
AC_ID = re.compile(r"AC-[\w-]+")
TEST_FILE = re.compile(r"[A-Za-z0-9_./\-]*(?:test|spec)[A-Za-z0-9_./\-]*\.[A-Za-z]+")
DIFF_LIMIT = 30   # 파일당 줄. 넘으면 건수만 더한다
DRAW_LIMIT = 40
GEN_TIMEOUT = 120


def _norm(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _git(folder, *args):
    """(종료 코드, 표준 출력). git이 없거나 폴더가 없어도 예외를 내지 않는다."""
    try:
        proc = subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(folder)] + list(args), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()


def _show(folder, rev, rel):
    """rev의 파일 글. 없으면 None. 원문 공백을 그대로 둔다."""
    try:
        proc = subprocess.run(["git", "-C", str(folder), "show", "{}:{}".format(rev, rel)], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n") if proc.returncode == 0 else None


def _read(path):
    try:
        return devflow_lib.read_text(path).replace("\r\n", "\n") if os.path.isfile(path) else None
    except UnicodeError:
        return None


def _join(root, rel):
    return os.path.join(str(root), *rel.replace("\\", "/").split("/"))


# ---------------------------------------------------------------- 대응표


def project_path(rel):
    """실행 폴더의 정본 경로에 대응하는 프로젝트 경로(`/` 구분). 표에 없으면 None(설계 7.5절 대응표)."""
    parts = rel.replace("\\", "/").split("/")
    top, rest = parts[0], parts[1:]
    name = "/".join(rest)
    if top == "spec" and len(rest) == 1 and name.endswith(".md"):
        if name == "brief.md":
            return "docs/product/brief.md"
        return GLOSSARY if name == "glossary.md" else "docs/product/requirements/" + name
    if top == "ui" and rest and name.endswith((".md", ".html")):
        return "docs/screens/" + name
    if top == "design" and len(rest) == 1 and name.endswith(".md"):
        return "docs/architecture/infra.md" if name == "infra.md" else "docs/architecture/flows/" + name
    return None


def _blocks(text):
    """[(`## 제목` 줄, 그 절의 원문)]. 첫 항목은 제목이 빈 머리글이다. 울타리 안의 `##`는 제목이 아니다."""
    out, title, rows, fence = [], "", [], False
    for line in _norm(text).split("\n"):
        if FENCE_RE.match(line):
            fence = not fence
        if not fence and SECTION_RE.match(line):
            out.append((title, "\n".join(rows)))
            title, rows = line.strip(), [line]
        else:
            rows.append(line)
    out.append((title, "\n".join(rows)))
    return out


def _sub_blocks(block):
    """(`##` 줄, [(`###` 제목, 원문)]). 울타리 안의 `###`는 제목이 아니다."""
    lines = block.split("\n")
    out, title, rows, fence = [], "", [], False
    for line in lines[1:]:
        if FENCE_RE.match(line):
            fence = not fence
        if not fence and SUB_RE.match(line):
            if title:
                out.append((title, "\n".join(rows)))
            title, rows = line.strip(), [line]
        elif title:
            rows.append(line)
    if title:
        out.append((title, "\n".join(rows)))
    return lines[0], out


def _design_projection(text):
    """설계 정본에서 기능 흐름도와 결정 절만 낸다. 제목에 낱말이 없는 `##` 절은 그 안의 맞는 `###` 절만 싣는다."""
    head, kept = "", []
    for title, block in _blocks(text):
        if not title:
            head = next((l for l in block.split("\n") if l.startswith("# ")), "")
        elif any(w in title for w in FLOW_WORDS):
            kept.append(block.rstrip())
        else:
            line, subs = _sub_blocks(block)
            found = [b.rstrip() for t, b in subs if any(w in t for w in FLOW_WORDS)]
            if found:
                kept.append("\n".join([line] + found))
    return "\n\n".join(([head] if head else []) + kept) + "\n" if kept else ""


def projection(rel, text):
    """프로젝트에 넣을 글. 「변경 이력」은 task 번호라 넣지 않는다."""
    dest = project_path(rel) or ""
    if dest.startswith("docs/architecture/flows/"):
        return _design_projection(text)
    if not dest.endswith(".md"):
        return text
    return "\n\n".join(block.rstrip() for title, block in _blocks(text) if title != HISTORY and block.strip()).rstrip() + "\n"


def projections(rel, text):
    """[(프로젝트 경로, 글)]. 개요의 「용어」는 용어집으로도 간다. 빈 글은 넣지 않는다."""
    dest = project_path(rel)
    if dest is None:
        return []
    out = [(dest, projection(rel, text))]
    if rel.replace("\\", "/") == "spec/overview.md":
        terms = next((block for title, block in _blocks(text) if title == TERMS), "")
        if terms.strip():
            out.append((GLOSSARY, "# 용어집\n\n" + terms.split("\n", 1)[-1].strip() + "\n"))
    return [(d, t) for d, t in out if t.strip()]


def canon_files(run_dir):
    """실행 폴더의 정본 경로(`\\` 구분), 정렬."""
    out = []
    for top in kinds.CANON_DIRS:
        for folder, _, names in sorted(os.walk(os.path.join(run_dir, top))):
            for name in sorted(names):
                out.append(os.path.relpath(os.path.join(folder, name), run_dir).replace("/", "\\"))
    return out


# ---------------------------------------------------------------- 기준본


def base_commit(run_dir):
    return str(devflow_lib.run_meta(run_dir).get(BASE_KEY, "") or "").strip()


def has_base(run_dir):
    return bool(base_commit(run_dir))


def applies(run_dir, t):
    """1.2.0부터 시작한 task이고 이 실행에 기준본이 있다. 옛 실행과 옛 task는 전과 같다."""
    return devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120) and has_base(run_dir)


def base_text(run_dir, rel):
    """정본 경로의 기준본 글. 없으면 None(옛 실행, 프로젝트에 아직 없는 문서)."""
    dest = project_path(rel)
    return _read(_join(os.path.join(run_dir, BASE_DIR), dest)) if dest else None


def _git_bytes(folder, *args):
    """표준 출력 바이트. 실패하면 None."""
    try:
        proc = subprocess.run(["git", "-C", str(folder)] + list(args), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def make_base(run_dir):
    """`base\\docs\\…`를 쓰고 시작 커밋을 run.md에 적는다. git이면 커밋된 판을 뜬다(작업 중인 글이 섞이지 않게).
    저장소인데 기준 브랜치를 못 찾으면 쓰지 않고 종료 3이다. "저장소 아님"으로 적으면 넣기가 끝까지 꺼진다."""
    meta = devflow_lib.run_meta(run_dir)
    project = str(meta.get("project", "") or "").strip()
    target = os.path.join(run_dir, BASE_DIR)
    branch = str(meta.get("base_branch", "") or "").strip() or "HEAD"
    copied = 0
    if _git(project, "rev-parse", "--is-inside-work-tree")[1] == "true":
        rc, tip = _git(project, "rev-parse", "--verify", "--quiet", branch + "^{commit}")
        if rc != 0:
            print("기준본을 뜨지 못함: 개발 기준 브랜치 {}를 {}에서 찾지 못함. 프로젝트 설정과 run.md `base_branch`를 고친 뒤 다시 돌린다".format(branch, project))
            return 3
        os.makedirs(target, exist_ok=True)
        _, names = _git(project, "ls-tree", "-r", "--name-only", tip, DOCS_ROOT)
        for rel in names.splitlines():
            raw = _git_bytes(project, "show", "{}:{}".format(tip, rel))
            if raw is not None:
                path = _join(target, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(raw)
                copied += 1
    else:
        os.makedirs(target, exist_ok=True)
        tip = NO_GIT
        for folder, _, names in os.walk(os.path.join(project, DOCS_ROOT)):
            for name in names:
                src = os.path.join(folder, name)
                path = os.path.join(target, os.path.relpath(src, project))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(src, "rb") as f, open(path, "wb") as out:
                    out.write(f.read())
                copied += 1
    doc = devflow_lib.Doc(os.path.join(run_dir, "run.md"))
    doc.set(BASE_KEY, tip)
    doc.save()
    print("기준본: 문서 {}개, 시작 커밋 {}".format(copied, tip))
    return 0


# ---------------------------------------------------------------- 승인 해시


def stamps(run_dir):
    """{정본 경로: {"sha", "task", "via", "at"}}."""
    text = _read(os.path.join(run_dir, APPROVED_DIR, HASH_FILE)) or ""
    out = {}
    for line in text.split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0].split("\\")[0] in kinds.CANON_DIRS:
            out[cells[0]] = {"sha": cells[1], "task": cells[2], "via": cells[3], "at": cells[4]}
    return out


def stamp_file(run_dir, rel, tid, via="", src=None):
    """정본의 해시와 사본을 남긴다. src를 주면 지금 정본 대신 그 파일(사람이 본 판)을 승인 판으로 찍는다.
    같은 경로의 앞 줄은 새 줄로 바꾼다(`승인 뒤 달라짐`의 기준은 마지막 승인이다)."""
    rel = rel.replace("/", "\\")
    src = src or _join(run_dir, rel)
    rows = stamps(run_dir)
    rows[rel] = {"sha": shadow_check.file_hash(src), "task": tid, "via": via, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    copy = _join(os.path.join(run_dir, APPROVED_DIR), rel)
    os.makedirs(os.path.dirname(copy), exist_ok=True)
    with open(src, "rb") as f:
        raw = f.read()
    with open(copy, "wb") as out:
        out.write(raw)
    lines = ["| 정본 | sha256 | task | 방식 | 시각 |", "|---|---|---|---|---|"]
    lines += ["| {} | {} | {} | {} | {} |".format(k, r["sha"], r["task"], r["via"], r["at"]) for k, r in sorted(rows.items())]
    devflow_lib.write_text(os.path.join(run_dir, APPROVED_DIR, HASH_FILE), "\n".join(lines) + "\n")


def _options(result):
    """{(항목, 선택지 표지): {"lines": [문장], "pairs": [(정본, 지금, 바뀜)]}}: 결과 「정해 주실 것」에 적힌 선택지. 항목은 들여쓰지 않은 목록 줄의 `:` 앞이다."""
    screen = devflow_lib.sections(result or "", level=2).get("승인 화면", "")
    out, item = {}, ""
    for line in devflow_lib.sections(screen, level=3).get("정해 주실 것", "").split("\n"):
        m = OPTION_LINE.match(line)
        if not m:
            head = ITEM_LINE.match(line)
            if head:
                item = head.group(1).split(":", 1)[0].strip().strip("*").strip()
            continue
        if not line[:1].isspace():
            item = ""
        entry = out.setdefault((item, m.group(1)), {"lines": [], "pairs": []})
        if m.group(2) == "의 앞 정본 줄:":
            pair = PAIR_LINE.search(m.group(3))
            if pair:
                entry["pairs"].append((m.group(3).split(":", 1)[0].strip().replace("/", "\\"), pair.group(1), pair.group(2)))
        else:
            entry["lines"].append(m.group(3))
    return out


def _answer_lines(t):
    """[(지점, 결정 칸과 원문)]: 이번 승인 차례(물은 뒤)의 답 줄. 앞 물음의 답이 끼면 고르지 않은 선택지가 설명이 된다."""
    asked = str(t.get("approval_requested", "") or "").strip()
    out = []
    for line in devflow_lib.record_lines(t):
        fields = devflow_lib.record_fields(line)
        if len(fields) < 3 or (asked and fields[0] < asked) or fields[1].startswith(NOT_A_CHOICE):
            continue
        out.append((fields[1], ", ".join(fields[2:])))
    return out


def _labels_in(text, labels):
    """글이 가리키는 선택지 표지."""
    return {label for label, sentences in labels.items()
            if re.search(r"\({}\)".format(label), text) or re.search(r"(?<![가-힣]){}(?:로|요|안|안으로)?(?![가-힣])".format(label), text)
            or any(sentence and sentence in text for sentence in sentences)}


def _line_choice(point, text, options):
    """답 한 줄이 고른 [(항목, 표지)]. 표지가 둘 이상이면 쉼표로 나뉜 조각마다 항목 이름과 짝지을 수 있을 때만 받는다. `(가)와 (나) 둘 다`는 읽지 않는다."""
    labels = {}
    for (_, label), entry in options.items():
        labels.setdefault(label, []).extend(_body(l) for l in entry["lines"])
    hits = _labels_in(text, labels)
    items = {item for item, _ in options}
    if len(hits) == 1:
        label = hits.pop()
        own = [item for item, other in options if other == label]
        named = [item for item in own if item and item in point + " " + text]
        return [(item, label) for item in named or own]
    out = []
    for piece in re.split(r"[,，]", text) if hits else ():
        found = _labels_in(piece, labels)
        if not found:
            continue
        named = [item for item in items if item and item in piece]
        if len(found) != 1 or len(named) != 1 or (named[0], next(iter(found))) not in options:
            return []
        out.append((named[0], next(iter(found))))
    return out


def _evidence(run_dir, t):
    """(설명이 되는 문장, 앞 정본 줄의 쌍). 물을 때 뜬 사본에서, 이번 승인 차례의 답이 고른 선택지 것만 읽는다. 화면 뒤에 쓴 글과 판정의 지적 글은 근거가 아니다.
    한 항목을 다시 고르면 뒤 답이 앞 답을 대신한다."""
    result, judge = _read(_asked_path(run_dir, t, "result.md")), _read(_asked_path(run_dir, t, "judge.md"))
    options, chosen, answers = _options(result), {}, _answer_lines(t)
    for point, text in answers:
        for item, label in _line_choice(point, text, options):
            chosen[item] = label
    entries = [options[key] for key in chosen.items()]
    lines = [l for entry in entries for l in entry["lines"]]
    if any("대안" in point + text for point, text in answers):
        lines += JUDGE_ALT.findall(devflow_lib.sections(judge or "", level=2).get("권장", ""))
    return {_body(l) for l in lines} - {""}, [pair for entry in entries for pair in entry["pairs"]]


def _body(line):
    """줄 전체를 견주기 위한 본문: 목록 표시, `(가)`, 끝의 위치 괄호, 앞뒤를 감싼 따옴표와 백틱만 벗긴다. 본문 안의 글자는 건드리지 않는다."""
    text = LOCATION_TAIL.sub("", LIST_MARK.sub("", line.strip(), count=1).strip())
    while len(text) >= 2 and WRAPPERS.get(text[0]) == text[-1]:
        text = text[1:-1].strip()
    return text


def _prior_canon(run_dir, t):
    """고른 선택지의 「앞 정본 줄」이 가리키는 정본: 메인이 Edit한 파일이다."""
    out = []
    for rel, _, _ in _evidence(run_dir, t)[1]:
        if rel.split("\\")[0] in kinds.CANON_DIRS and rel not in out:
            out.append(rel)
    return out


def _via(t):
    """사람이 직접 답하지 않고 지나간 길의 표지. 위임 답은 승인 줄이라 칸으로 가린다."""
    if str(t.get("approval_mode", "") or "") == NOTIFIED:
        return NOTIFIED
    lines = devflow_lib.record_lines(t)
    return DELEGATED if lines and delegation.is_delegated_line(lines[-1]) else ""


def _asked_path(run_dir, t, rel):
    return _join(os.path.join(run_dir, APPROVED_DIR, ASKED_DIR, t.get("id", "")), rel)


def _written(run_dir, t):
    return [] if os.path.isdir(os.path.join(t["_dir"], "revised")) else devflow_lib.written_canon(run_dir, t)


def snapshot_asked(run_dir, t):
    """승인을 물을 때 사람이 볼 판을 떠 둔다. 고친 판이 있는 변경 task는 그 판이다. 결과와 판정, 마무리 리뷰도 뜬다(설명의 근거, 화면에 실린 줄).
    근거부터 뜬다. 끊겨도 정본 사본이 없으면 `대조하지 못함`으로 보인다."""
    if not applies(run_dir, t):
        return []
    revised = os.path.join(t["_dir"], "revised")
    pairs = [(name, os.path.join(t["_dir"], name)) for name in ("result.md", "judge.md", devflow_lib.WRAP_REVIEW)]
    canon = [(rel, _join(run_dir, rel)) for rel in _written(run_dir, t)]
    for folder, _, names in os.walk(revised):
        canon += [(os.path.relpath(os.path.join(folder, n), revised).replace("/", "\\"), os.path.join(folder, n)) for n in names]
    for rel, src in pairs + canon:
        if os.path.isfile(src):
            copy = _asked_path(run_dir, t, rel)
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            with open(src, "rb") as f:
                raw = f.read()
            with open(copy, "wb") as out:
                out.write(raw)
    return [rel for rel, _ in canon]


def _explained(before, after, run_dir, t, rel):
    """앞 글과 지금 글의 차이가 이 task의 답으로 설명되는가. 줄마다 고른 선택지의 `지금:`→`바뀜:`이거나, 목록 표시와 `(가)`를 뗀 본문이 그 선택지 문장과 같아야 한다.
    설명할 수 없으면 거짓이다. 그러면 사람이 보지 않은 글로 친다."""
    sentences, chosen_pairs = _evidence(run_dir, t)
    pairs = [(a, b) for path, a, b in chosen_pairs if path == rel]
    old, new = [_norm(x).split("\n") for x in (before, after)]
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        removed = [l for l in old[i1:i2] if l.strip()]
        added = [l for l in new[j1:j2] if l.strip()]
        for at, line in enumerate(added):
            gone = removed[at] if at < len(removed) else None
            by_pair = gone is not None and any(a in gone and gone.replace(a, b) == line for a, b in pairs)
            if not by_pair and _body(line) not in sentences:
                return False
        if len(removed) > len(added):
            return False
    return True


def stamp_task(run_dir, t):
    """task 완료 때 찍는다. 쓴 정본은 물을 때의 판과 견주어 답으로 설명되면 지금 글을, 아니면 물을 때의 판을 찍는다(표에 `승인 화면 뒤 달라짐`).
    사본이 없으면 사람이 본 판을 모르므로 `대조하지 못함`이다. 알림은 물은 적이 없어 대조하지 않는다.
    앞 정본 줄의 파일은 마지막 승인 판과 견주어 답으로 설명될 때만 다시 찍는다. 파일 전체를 승인한 것이 아니다.
    고친 판이 있는 변경 task는 `apply_revision.py`가 찍는다."""
    if not applies(run_dir, t):
        return []
    tid, via, done = t.get("id", ""), _via(t), []
    written = _written(run_dir, t)
    for rel in written:
        current, asked = _read(_join(run_dir, rel)), _asked_path(run_dir, t, rel)
        if current is None:
            continue
        if not os.path.isfile(asked):
            stamp_file(run_dir, rel, tid, via or UNCHECKED)
        elif _explained(_read(asked), current, run_dir, t, rel):
            stamp_file(run_dir, rel, tid, via)
        else:
            stamp_file(run_dir, rel, tid, AFTER_SCREEN, asked)
        done.append(rel)
    rows = stamps(run_dir)
    for rel in _prior_canon(run_dir, t):
        current, approved = _read(_join(run_dir, rel)), _read(_join(os.path.join(run_dir, APPROVED_DIR), rel))
        if rel in written or current is None or approved is None or _norm(current) == _norm(approved) or not _explained(approved, current, run_dir, t, rel):
            continue
        stamp_file(run_dir, rel, tid, rows.get(rel, {}).get("via", ""))
        done.append(rel)
    return done


def _without_history(text):
    return "\n\n".join(block.rstrip() for title, block in _blocks(text) if title != HISTORY and block.strip())


def stamp_revision(run_dir, t, rel):
    """`apply_revision.py`가 정본을 옮긴 뒤에 부른다. 물을 때의 고친 판과 옮긴 글이 답으로 설명되지 않으면 물을 때의 판을 찍는다.
    HTML은 이력 줄을 붙이지 않으므로 그대로 견준다. 사본이 없으면 `대조하지 못함`이다."""
    if not applies(run_dir, t):
        return
    rel = rel.replace("/", "\\")
    tid, via = t.get("id", ""), _via(t)
    asked, current = _asked_path(run_dir, t, rel), _read(_join(run_dir, rel))
    if not os.path.isfile(asked) or current is None:
        stamp_file(run_dir, rel, tid, via or UNCHECKED)
    elif rel.endswith(".md"):
        if _explained(_without_history(_read(asked)), _without_history(current), run_dir, t, rel):
            stamp_file(run_dir, rel, tid, via)
        else:
            stamp_file(run_dir, rel, tid, AFTER_SCREEN, asked)
    elif _norm(_read(asked)) == _norm(current):
        stamp_file(run_dir, rel, tid, via)
    else:
        stamp_file(run_dir, rel, tid, AFTER_SCREEN, asked)


def _approval(run_dir, rel, rows):
    row = rows.get(rel)
    if row is None:
        return UNAPPROVED
    same = shadow_check.file_hash(_join(run_dir, rel)) == row["sha"]
    approved, current = _read(_join(os.path.join(run_dir, APPROVED_DIR), rel)), _read(_join(run_dir, rel))
    if not same and approved is not None and current is not None and projections(rel, approved) == projections(rel, current):
        same = True   # 넣지 않는 절만 바뀌었다. 볼 줄이 없는 경고를 내지 않는다
    if row["via"] == UNCHECKED:
        return UNCHECKED
    if same:
        return SAME
    return AFTER_SCREEN if row["via"] == AFTER_SCREEN else CHANGED


# ---------------------------------------------------------------- 넣기: 절 단위 합치기


def _titles_repeat(*texts):
    """같은 제목의 절이 있는 글이 있는가. 절 단위로 견줄 수 없다."""
    return any(len(titles) != len(set(titles)) for titles in ([k for k, _ in _blocks(x)] for x in texts))


def merge_sections(base, ours, theirs, take=None, whole=False):
    """(합친 글, 같은 절을 두 곳에서 고친 제목). 고친 절이 겹치지 않으면 합친다. take는 {제목: RUN_SIDE|PROJECT_SIDE}로 사람의 답이다.
    제목이 겹치는 글은 절로 가를 수 없어 파일 전체로 묻는다."""
    take = take or {}
    if _norm(ours) == _norm(theirs) or _norm(theirs) == _norm(base):
        return ours, []
    if _norm(ours) == _norm(base):
        return theirs, []
    if whole or _titles_repeat(base, ours, theirs):
        side = take.get(WHOLE_FILE)
        return (theirs if side == RUN_SIDE else ours if side == PROJECT_SIDE else None), ([] if side else [WHOLE_FILE])
    b, o, t = (dict(_blocks(x)) for x in (base, ours, theirs))
    order = [k for k, _ in _blocks(theirs)] + [k for k, _ in _blocks(ours) if k not in t]
    conflicts, out = [], []
    for title in order:
        bv, ov, tv = (_norm(x.get(title)) if title in x else None for x in (b, o, t))
        if ov == tv or tv == bv:
            kept = o.get(title)
        elif ov == bv:
            kept = t.get(title)
        elif take.get(title) == RUN_SIDE:
            kept = t.get(title)
        elif take.get(title) == PROJECT_SIDE:
            kept = o.get(title)
        else:
            conflicts.append(title or HEADER)
            continue
        if kept is not None and kept.strip():
            out.append(kept.rstrip())
    return (None, conflicts) if conflicts else ("\n\n".join(out) + "\n", [])


def _flow_overlay(base, raw):
    """넣는 절만 바꾼 흐름 문서. 결정·흐름도 밖의 절은 이번 실행이 지운 것이 아니라 넣지 않는 것이므로 기준본 그대로 둔다.
    (글, 파일 전체로 물어야 하는가). 제목이 겹치면 어느 절을 바꿀지 가를 수 없다."""
    if not base.strip():
        return raw, False
    if _titles_repeat(base, raw):
        return raw, True
    new = dict(_blocks(raw))
    used, out = set(), []
    for title, block in _blocks(base):
        if not title:
            out.append(block if block.strip() else new.get("", ""))
            used.add("")
            continue
        _, subs = _sub_blocks(block)
        if any(w in title for w in FLOW_WORDS):
            used.add(title)
            if title in new:
                out.append(new[title])
            continue
        if title not in new and not any(any(w in t for w in FLOW_WORDS) for t, _ in subs):
            out.append(block)
            continue
        used.add(title)
        new_subs = dict(_sub_blocks(new[title])[1]) if title in new else {}
        titles = [t for t, _ in subs]
        if len(titles) != len(set(titles)):
            return raw, True
        kept = [block.split("\n### ", 1)[0].rstrip()]
        for sub_title, text in subs:
            if any(w in sub_title for w in FLOW_WORDS):
                if sub_title in new_subs:
                    kept.append(new_subs[sub_title].rstrip())
            else:
                kept.append(text.rstrip())
        kept += [text.rstrip() for sub_title, text in new_subs.items() if sub_title not in titles]
        out.append("\n".join(kept))
    out += [block for title, block in _blocks(raw) if title not in used]
    return "\n\n".join(b.rstrip() for b in out if b.strip()) + "\n", False


def _glossary_terms(base, raw):
    """개요 「용어」를 용어집에 더한다. 프로젝트 용어집의 줄은 지우지 않는다. 개요는 이번 실행의 말만 담을 수 있다."""
    if not base.strip():
        return raw
    have = {l.strip() for l in base.split("\n")}
    added = [l for l in raw.split("\n")[2:] if l.strip() and l.strip() not in have]
    if not added:
        return base
    blocks = _blocks(base)
    if any(title == TERMS for title, _ in blocks):
        return "\n\n".join((b.rstrip() + "\n" + "\n".join(added)) if title == TERMS else b.rstrip() for title, b in blocks if b.strip()) + "\n"
    return base.rstrip() + "\n\n" + TERMS + "\n" + "\n".join(added) + "\n"


def _choice_title(title):
    title = title.strip()
    if title in (HEADER, ""):
        return ""
    return title if title == WHOLE_FILE or title.startswith("## ") else "## " + title


def _choices(t):
    """{문서: {제목: 쪽}}. 사람이 고른 답(`--take`). 다시 합쳐도 같은 결과가 나도록 task 폴더에 둔다."""
    out = {}
    for line in (_read(os.path.join(t["_dir"], CHOICE_FILE)) or "").split("\n"):
        if "#" in line and "=" in line:
            spec, side = line.rsplit("=", 1)
            dest, title = spec.split("#", 1)
            out.setdefault(dest.strip(), {})[_choice_title(title)] = side.strip()
    return out


def _flow_dirs(run_dir):
    flows, out = os.path.join(run_dir, "flows"), []
    for name in sorted(os.listdir(flows)) if os.path.isdir(flows) else []:
        path = os.path.join(flows, name, "flow.md")
        if os.path.isfile(path):
            meta_lines, _ = devflow_lib.split_front_matter(devflow_lib.read_text(path))
            folder = str(devflow_lib.parse_meta(meta_lines).get("dir", "") or "").strip()
            if folder and os.path.isdir(folder):
                out.append(folder)
    return out


def insert_folder(run_dir):
    """넣는 폴더: 통합 폴더, 흐름이 하나면 그 흐름 폴더. 정할 수 없으면 None이다. 원래 폴더에는 묻지 않고 쓰지 않는다."""
    found = str(devflow_lib.run_meta(run_dir).get("integration_dir", "") or "").strip()
    if found:
        return found
    dirs = _flow_dirs(run_dir)
    return dirs[0] if len(dirs) == 1 else None


def _project(run_dir):
    return str(devflow_lib.run_meta(run_dir).get("project", "") or "").strip()


def _tip(run_dir, folder, dest):
    if base_commit(run_dir) == NO_GIT:
        return None
    branch = str(devflow_lib.run_meta(run_dir).get("base_branch", "") or "").strip()
    return _show(folder or _project(run_dir), branch, dest) if branch else None


def _ours(run_dir, folder, dest, base):
    """합칠 프로젝트 쪽: 코드 폴더가 고쳤으면 그 글, 아니면 개발 기준 브랜치의 글(나란히 돈 실행이 먼저 넣었을 수 있다)."""
    here = _read(_join(folder, dest)) if folder else None
    kept = _read(_inserted_path(run_dir, dest, OURS_DIR))
    if kept is not None and here is not None and _norm(here) == _norm(_read(_inserted_path(run_dir, dest))):
        return kept
    if here is not None and _norm(here) != _norm(base):
        return here
    tip = _tip(run_dir, folder, dest)
    return tip if tip is not None else (here if here is not None else "")


def plan(run_dir, t, folder):
    """넣을 산출물의 행. 파일을 쓰지 않고, 넣은 뒤에 다시 돌려도 같은 표가 나온다. folder가 None이면 쓸 곳이 없는 표다."""
    rows_hash, choices, out = stamps(run_dir), _choices(t), []
    base_root = os.path.join(run_dir, BASE_DIR)
    own_glossary = os.path.isfile(_join(run_dir, "spec/glossary.md"))
    for rel in canon_files(run_dir):
        text = _read(_join(run_dir, rel))
        for dest, raw in projections(rel, text) if text is not None else ():
            from_terms = dest == GLOSSARY and project_path(rel) != GLOSSARY
            if from_terms and own_glossary:
                continue   # 승인받은 용어집이 따로 있다. 개요의 줄은 요구사항 문서에 남는다
            base = _read(_join(base_root, dest)) or ""
            theirs, whole = raw, False
            if dest.startswith("docs/architecture/flows/"):
                theirs, whole = _flow_overlay(base, raw)
            elif from_terms:
                theirs = _glossary_terms(base, raw)
            if _norm(theirs) == _norm(base):
                continue
            tip = _tip(run_dir, folder, dest)
            if tip is not None and _norm(tip) == _norm(theirs):
                continue   # 앞 회차가 이미 넣었다
            ours = _ours(run_dir, folder, dest, base)
            take = choices.get(dest) or {}
            skipped = take.get(WHOLE_FILE) == SKIP_SIDE
            merged, conflicts = (None, []) if skipped else merge_sections(base, ours, theirs, take, whole or not dest.endswith(".md"))
            if whole and not skipped and WHOLE_FILE not in take:
                merged, conflicts = None, [WHOLE_FILE]   # 한쪽만 고쳤어도 넣지 않는 절을 지울 수 있다
            row = rows_hash.get(rel) or {}
            out.append({"rel": rel, "dest": dest, "state": _approval(run_dir, rel, rows_hash), "via": row.get("via", ""), "base": base, "ours": ours,
                        "theirs": theirs, "proj": raw, "merged": merged, "conflicts": conflicts, "skipped": skipped})
    return out


def _diff_lines(before, after, limit=DIFF_LIMIT):
    rows = [l for l in list(difflib.unified_diff(_norm(before).splitlines(), _norm(after).splitlines(), lineterm="", n=0))[2:] if not l.startswith("@@")]
    return ["  " + l for l in rows[:limit]] + (["  … 나머지 {}줄".format(len(rows) - limit)] if len(rows) > limit else [])


def _approved_copy(run_dir, rel, fallback):
    return _read(_join(os.path.join(run_dir, APPROVED_DIR), rel)) or fallback


def _inserted_path(run_dir, dest, folder=INSERTED_DIR):
    return _join(os.path.join(run_dir, folder), dest)


def _other_changes(run_dir, folder, rows):
    """표 밖의 문서 변경 [(줄, 하위 줄)]. 결정 기록은 제목, 위험·미확인은 건수, 생성물은 줄 수만 싣는다(설계 7.3절)."""
    start = base_commit(run_dir)
    if start == NO_GIT or not folder:
        return []
    _, changed = _git(folder, "diff", "--name-only", start, "--", DOCS_ROOT)
    _, added = _git(folder, "ls-files", "--others", "--exclude-standard", "--", DOCS_ROOT)
    listed = {r["dest"] for r in rows} | {TEST_MAP}
    out, unverified = [], 0
    for rel in sorted(set(changed.splitlines() + added.splitlines())):
        rel = rel.strip().strip('"')
        now = _read(_join(folder, rel))
        if rel in listed or not rel or (now is not None and now == _tip(run_dir, folder, rel)):
            continue
        before = _show(folder, start, rel) or ""
        if rel.startswith("docs/decisions/"):
            title = next((l[2:].strip() for l in (now or "").split("\n") if l.startswith("# ")), rel)
            out.append(("- 결정 기록: {}".format(title), []))
        elif rel.startswith("docs/operations/"):
            old = set(before.split("\n"))
            unverified += sum(1 for l in (now or "").split("\n") if l.startswith("- ") and l not in old)
        elif rel.startswith("docs/generated/"):
            lines = _diff_lines(before, now or "", 10 ** 6)
            plus = sum(1 for l in lines if l.startswith("  +"))
            out.append(("- 생성물: {} +{} -{}".format(rel, plus, len(lines) - plus), []))
        else:
            out.append(("- {}: {} (표 밖)".format(UNAPPROVED, rel), _diff_lines(before, now or "")))
    return out + ([("- 위험·미확인 목록: {}건".format(unverified), [])] if unverified else [])


def _test_map_rows(text):
    return [line.strip() for line in (text or "").split("\n") if line.startswith("| ") and not line.startswith("| 인수 기준") and not line.startswith("|-")]


def _run_test_links(run_dir):
    """(이번 실행의 지도 행, 연결을 못 읽은 줄 수). 원천은 코드 task 「변이 확인 지시」다(설계 6.12절 7)."""
    rows, unread = [], 0
    for t in devflow_lib.load_tasks(run_dir).values():
        if t.get("kind") not in kinds.AUTO_DEPEND_KINDS or t.get("status") != kinds.DONE or not applies(run_dir, t):
            continue
        section = devflow_lib.sections(_read(os.path.join(t["_dir"], "result.md")) or "").get("변이 확인 지시", "")
        for line in section.split("\n"):
            if not line.lstrip().startswith("- ") or devflow_lib.EMPTY_ITEM.match(line.strip()):
                continue
            files, acs = TEST_FILE.findall(line), AC_ID.findall(line)
            if not files:
                unread += 1
            for name in files:
                rows.append("| {} | {} |".format(", ".join(acs) or "-", name.replace("\\", "/")))
    return rows, unread


def update_test_map(run_dir, folder):
    """테스트 지도는 누적 갱신이다: 지난 판 위에 이번 실행의 행을 더하고 시험 파일이 사라진 행만 지운다. 요약 줄 또는 빈 글."""
    path = _join(folder, TEST_MAP)
    rows, unread = _run_test_links(run_dir)
    old = _test_map_rows(_read(path))
    keep = []
    for row in old + rows:
        name = row.strip("|").rsplit("|", 1)[-1].strip()
        if row not in keep and os.path.isfile(_join(folder, name)):
            keep.append(row)
    if keep != old:
        devflow_lib.write_text(path, TEST_MAP_HEAD + "".join(r + "\n" for r in keep))
    base = _test_map_rows(_read(_join(os.path.join(run_dir, BASE_DIR), TEST_MAP)))
    added, removed = len([r for r in keep if r not in base]), len([r for r in base if r not in keep])
    return "- 테스트 지도: 더한 행 {}, 지운 행 {}, 연결을 못 읽은 줄 {}".format(added, removed, unread) if added or removed or unread else ""


def _remove_closed(run_dir, folder):
    """상태 파일의 닫힌 항목을 코드 폴더의 위험·미확인 목록에서 지운다. 상태 파일에서는 내보낸 뒤에 지운다(`_sync_state`). 이 실행을 버려도 닫힌 사실이 남는다."""
    path = _join(folder, UNVERIFIED_DOC)
    text = _read(path)
    closed = set(read_state(run_dir)["closed"])
    if not closed or text is None:
        return
    kept = [l for l in text.split("\n") if l.strip() not in closed]
    if len(kept) != len(text.split("\n")):
        devflow_lib.write_text(path, "\n".join(kept))


def _section_of(text, title):
    if title == WHOLE_FILE:
        return text
    return dict(_blocks(text)).get("" if title == HEADER else title, "")


def _state_lines(run_dir, r):
    """승인 상태 줄. 승인한 그대로는 파일 이름만, 달라진 것은 달라진 줄 그대로다. 합치기 전의 이번 실행 판으로 견준다."""
    if r["state"] == SAME:
        return ["- {}: {}".format(PASSED_BY.get(r["via"], SAME), r["dest"])]
    if r["state"] in (UNAPPROVED, UNCHECKED):
        return ["- {}: {}".format(r["state"], r["dest"])] + _diff_lines(r["base"], r["theirs"])
    approved = dict(projections(r["rel"], _approved_copy(run_dir, r["rel"], ""))).get(r["dest"], "")
    return ["- {}: {}".format(r["state"], r["dest"])] + _diff_lines(approved, r["proj"])


def review_rows(run_dir, t, rows, folder):
    """넣을 산출물 칸의 줄(설계 7.3절). 넣지 않은 글을 `승인한 그대로`로 보이지 않는다."""
    out = []
    for r in rows:
        if r["skipped"]:
            out.append("- {}: {}".format(SKIPPED, r["dest"]))
            continue
        if r["conflicts"]:
            for title in r["conflicts"]:
                out.append("- {}: {} {}".format(TWO_PLACES, r["dest"], title))
                out += ["  " + RUN_SIDE + ":"] + _diff_lines(_section_of(r["base"], title), _section_of(r["theirs"], title))
                out += ["  " + PROJECT_SIDE + ":"] + _diff_lines(_section_of(r["base"], title), _section_of(r["ours"], title))
            continue
        here = _read(_join(folder, r["dest"])) if folder else None
        missing = here is None or _norm(here) != _norm(r["merged"])
        if missing:
            out.append("- {}: {}".format(NOT_YET, r["dest"]))
        if not missing or r["state"] != SAME:
            out += _state_lines(run_dir, r)
        inserted = _read(_inserted_path(run_dir, r["dest"]))
        if inserted is not None and here is not None and _norm(inserted) != _norm(here) and not missing:
            out += ["- {}: {}".format(AFTER_INSERT, r["dest"])] + _diff_lines(inserted, here)
    for line, subs in _other_changes(run_dir, folder, rows):
        out += [line] + subs
    table = _read(os.path.join(t["_dir"], INSERT_FILE)) or ""
    out += [l for l in table.split("\n") if l.startswith("- 테스트 지도:")]
    out += ["- {}: {}{}".format(PROPOSED, " | ".join(cells), PROPOSED_TAIL) for cells in proposed_generators(run_dir, t)]
    return out


FOLDER_LINE = re.compile(r"^폴더: (.*)$", re.M)
NO_FOLDER = "넣을 코드 폴더를 정하지 못함"


def _review_folder(run_dir, t):
    """표를 쓴 폴더. 표가 없으면 넣을 폴더다."""
    found = FOLDER_LINE.search(_read(os.path.join(t["_dir"], INSERT_FILE)) or "")
    return (found.group(1).strip() if found.group(1).strip() != NO_FOLDER else None) if found else insert_folder(run_dir)


def unresolved(run_dir, t):
    """내보내기를 막는 `같은 절 두 곳`: [문서]. 옛 실행은 빈 값이다."""
    if not applies(run_dir, t):
        return []
    return [r["dest"] for r in plan(run_dir, t, _review_folder(run_dir, t)) if r["conflicts"]]


def review_lines(run_dir, t):
    """(마무리 리뷰의 칸 줄, 「먼저 보실 것」 한 줄 또는 빈 글). 옛 실행과 옛 마무리는 빈 값이다."""
    if not applies(run_dir, t):
        return [], ""
    folder = _review_folder(run_dir, t)
    lines = review_rows(run_dir, t, plan(run_dir, t, folder), folder)
    count = [(word, sum(1 for l in lines if l.startswith("- {}:".format(word))))
             for word in (TWO_PLACES, NOT_YET, UNCHECKED, AFTER_SCREEN, CHANGED, UNAPPROVED, AFTER_INSERT, PROPOSED)]
    bad = ", ".join("{} {}".format(w, n) for w, n in count if n)
    return lines, "- 넣을 산출물: {}(아래 칸)".format(bad) if bad else ""


def inserted_documents(run_dir):
    """넣은 문서 수(실행 지도 줄기의 끝). 같은 문서를 회차마다 세지 않는다."""
    return sum(len(files) for _, _, files in os.walk(os.path.join(run_dir, INSERTED_DIR)))


def _take_problem(rows, t, take):
    """`--take`의 문제 또는 None. 모르는 절이나 값을 말없이 쌓지 않는다."""
    if "#" not in take or "=" not in take:
        return "꼴은 {문서}#{절}={쪽}이다"
    spec, side = take.rsplit("=", 1)
    dest, title = spec.split("#", 1)
    side = side.strip()
    row = next((r for r in rows if r["dest"] == dest.strip()), None)
    if row is None:
        return "넣을 표에 없는 문서: " + dest.strip()
    known = {_choice_title(c) for c in row["conflicts"]} | set(_choices(t).get(dest.strip(), {}))
    if side == SKIP_SIDE:
        return None if _choice_title(title) == WHOLE_FILE else "뺌은 파일 전체만 받는다: {}#{}={}".format(dest.strip(), WHOLE_FILE, SKIP_SIDE)
    if side not in (RUN_SIDE, PROJECT_SIDE):
        return "모르는 쪽: {}({} / {} / {})".format(side, RUN_SIDE, PROJECT_SIDE, SKIP_SIDE)
    return None if _choice_title(title) in known else "같은 절 두 곳이 아닌 절: {}".format(title.strip() or HEADER)


def insert(run_dir, tid, folder=None, take=None):
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        print("task 없음: " + tid)
        return 2
    t = tasks[tid]
    if not applies(run_dir, t):
        print(NOT_APPLIED)
        return 0
    if not folder and not str(devflow_lib.run_meta(run_dir).get("integration_dir", "") or "").strip() and len(_flow_dirs(run_dir)) > 1:
        print("흐름이 둘 이상인데 통합 폴더가 없어 넣지 않습니다")
        return 2
    folder = folder or insert_folder(run_dir)
    if take:
        problem = _take_problem(plan(run_dir, t, folder), t, take)
        if problem:
            print("답을 받지 않음: " + problem)
            return 2
        path = os.path.join(t["_dir"], CHOICE_FILE)
        devflow_lib.write_text(path, (_read(path) or "") + take.strip() + "\n")
    written = base_commit(run_dir) != NO_GIT and bool(folder)
    if written:
        _remove_closed(run_dir, folder)
    rows = plan(run_dir, t, folder)
    for r in rows:
        if written and r["merged"] is not None:
            text = r["merged"].rstrip("\n") + "\n"
            devflow_lib.write_text(_inserted_path(run_dir, r["dest"], OURS_DIR), r["ours"])
            devflow_lib.write_text(_join(folder, r["dest"]), text)
            devflow_lib.write_text(_inserted_path(run_dir, r["dest"]), text)
    summary = update_test_map(run_dir, folder) if written else ""
    head = ["# 넣을 산출물", "", "시작 커밋: {}".format(base_commit(run_dir)), "폴더: {}".format(folder or NO_FOLDER), ""]
    table = ["| 넣을 곳 | 정본 | 승인 | 넣기 |", "|---|---|---|---|"]
    for r in rows:
        action = TWO_PLACES + " " + ", ".join(r["conflicts"]) if r["conflicts"] else SKIPPED if r["skipped"] else "넣음" if written else NOT_YET
        table.append("| {} | {} | {} | {} |".format(r["dest"], r["rel"], PASSED_BY.get(r["via"], r["state"]) if r["state"] == SAME else r["state"], action))
    tail = [""] + ([summary] if summary else [])
    devflow_lib.write_text(os.path.join(t["_dir"], INSERT_FILE), "\n".join(head + table + tail) + "\n")
    if not written:
        print("{}: 표만 씁니다".format(NO_GIT if base_commit(run_dir) == NO_GIT else NO_FOLDER))
    print("넣을 산출물 {}개 -> {}".format(len(rows), os.path.join(t["_dir"], INSERT_FILE)))
    two = [r for r in rows if r["conflicts"]]
    for r in two:
        print("{}: {} {}".format(TWO_PLACES, r["dest"], ", ".join(r["conflicts"])))
    return 3 if two else 0


# ---------------------------------------------------------------- 생성 명령과 도면 대조


def _gen_cells(text):
    """`이름 | 명령 | 대상`의 칸. 명령에는 `|`가 들 수 있어 첫 칸과 끝 칸만 뗀다. 못 읽으면 None."""
    cells = [c.strip() for c in text.split("|")]
    if len(cells) < 3 or not cells[0] or not cells[-1]:
        return None
    return cells[0].strip("`"), " | ".join(cells[1:-1]).strip().strip("`"), cells[-1].strip("`")


def _settings_path(run_dir):
    return os.path.join(os.path.dirname(os.path.abspath(run_dir)), devflow_lib.PROJECT_SETTINGS)


def _generator_rows(run_dir):
    """([(이름, 명령, 대상)], 못 읽은 줄). 프로젝트 설정 「생성 명령」의 줄이다. 테스트 지도는 누적 갱신이라 뺀다."""
    rows, bad = [], []
    for line in devflow_lib.sections(_read(_settings_path(run_dir)) or "").get("생성 명령", "").split("\n"):
        if line.startswith("- "):
            cells = _gen_cells(line[2:])
            if cells is None:
                bad.append(line[2:].strip())
            elif cells[2] != TEST_MAP:
                rows.append(cells)
    return rows, bad


def generators(run_dir):
    return _generator_rows(run_dir)[0]


def proposed_generators(run_dir, t):
    """작성자가 낸 생성 명령 가운데 아직 등록되지 않은 것. 사람이 승인하기 전에는 돌리지 않는다."""
    have = {cells[0] for cells in generators(run_dir)}
    found = [_gen_cells(m) for m in PROPOSAL_LINE.findall(_read(os.path.join(t["_dir"], "result.md")) or "")]
    return [cells for cells in found if cells and cells[0] not in have]


def register_proposed(run_dir, t):
    """실행 승인 답 뒤에 task_set.py가 부른다. 물을 때 뜬 마무리 리뷰에 실린 줄만 설정에 더한다. 답 때의 결과 파일로 등록하지 않는다.
    가린 줄은 결과 사본과 맞지 않아 등록되지 않는다. 등록된 명령은 셸로 돈다."""
    if not applies(run_dir, t):
        return []
    have = {cells[0] for cells in generators(run_dir)}
    offered = [_gen_cells(m) for m in PROPOSAL_LINE.findall(_read(_asked_path(run_dir, t, "result.md")) or "")]
    rows = [cells for cells in (_gen_cells(m) for m in PROPOSAL_SHOWN.findall(_read(_asked_path(run_dir, t, devflow_lib.WRAP_REVIEW)) or ""))
            if cells and cells in offered and cells[0] not in have]
    for cells in proposed_generators(run_dir, t):
        if cells not in rows and cells[0] not in {r[0] for r in rows}:
            print("생성 명령을 화면에 없어 등록하지 않음: {}".format(cells[0]))
    if not rows:
        return []
    path = _settings_path(run_dir)
    text = (_read(path) or "# 프로젝트 설정\n").rstrip("\n") + "\n"
    lines = ["- " + " | ".join(cells) for cells in rows]
    if "## 생성 명령" in text:
        text = text.replace("## 생성 명령\n", "## 생성 명령\n" + "\n".join(lines) + "\n", 1)
    else:
        text += "\n## 생성 명령\n" + "\n".join(lines) + "\n"
    devflow_lib.write_text(path, text)
    return [cells[0] for cells in rows]


def _kill_tree(proc):
    """셸만 죽이면 자식이 남아 파이프와 폴더를 쥔다."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.SubprocessError:
        pass


def _status_lines(folder):
    rc, out = _git(folder, "status", "--porcelain")
    return set(out.splitlines()) if rc == 0 else set()


def _launch(command, folder):
    """{"ok", "text", "touched"}. 표준 출력을 임시 파일로 받아 자식이 파이프를 쥐어도 기다리지 않는다. 사유에 명령 전문을 넣지 않는다."""
    before = _status_lines(folder)
    with tempfile.TemporaryFile() as out:
        try:
            options = {} if os.name == "nt" else {"start_new_session": True}
            proc = subprocess.Popen(command, shell=True, cwd=str(folder), stdout=out, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **options)
        except OSError as e:
            return {"ok": False, "text": "시작하지 못함({})".format(e.strerror or "오류"), "touched": []}
        limit = time.monotonic() + GEN_TIMEOUT
        while proc.poll() is None and time.monotonic() < limit:
            time.sleep(0.05)
        late = proc.poll() is None
        if late:
            _kill_tree(proc)
        out.seek(0)
        text = out.read().decode("utf-8", "replace").replace("\r\n", "\n")
    touched = sorted(l[3:].strip() for l in _status_lines(folder) - before)
    if late:
        return {"ok": False, "text": "시간 초과 {}초".format(GEN_TIMEOUT), "touched": touched}
    if proc.returncode != 0:
        return {"ok": False, "text": "종료 코드 {}".format(proc.returncode), "touched": touched}
    return {"ok": True, "text": text, "touched": touched}


def run_generator(run_dir, name, command, folder):
    """등록된 명령을 코드 끝(sha)별로 한 번만 돌린다. 실패도 그 끝에서는 다시 돌리지 않는다."""
    rc, tip = _git(folder, "rev-parse", "HEAD")
    if rc != 0:
        return _launch(command, folder)
    key = hashlib.sha256("{}\n{}\n{}".format(tip, name, command).encode("utf-8")).hexdigest()[:32]
    path = os.path.join(run_dir, GEN_CACHE, key + ".json")
    cached = _read(path)
    if cached is not None:
        return json.loads(cached)
    result = _launch(command, folder)
    devflow_lib.write_text(path, json.dumps(result, ensure_ascii=False))
    return result


def _touched_lines(name, result):
    return ["생성 명령이 코드 폴더를 고침: {} ({})".format(f, name) for f in result["touched"]]


def generate(run_dir, folder, check=False):
    """실패와 시간 초과는 사유만 낸다. --check의 다름만 종료 3이다(뽑은 결과와 다르면 판정 실패, 설계 7.5절)."""
    rows, bad = _generator_rows(run_dir)
    for line in bad:
        print("생성 명령 줄을 읽지 못함: " + line)
    if not rows:
        print(NO_GENERATOR)
        return 0
    differs = 0
    for name, command, target in rows:
        result = run_generator(run_dir, name, command, folder)
        path = _join(folder, target)
        for line in _touched_lines(name, result):
            print(line)
        if not result["ok"]:
            print("생성 실패: {} ({})".format(name, result["text"]))
        elif check:
            if _norm(_read(path)) != _norm(result["text"]):
                print("뽑은 결과와 다름: {}".format(target))
                differs += 1
        else:
            devflow_lib.write_text(path, result["text"])
            print("생성함: {} -> {}".format(name, target))
    return 3 if differs else 0


def _drawing_lines(text):
    """{제목: [도면 코드 줄]}. 제안 도면 절 안의 제목별 울타리 글이다."""
    out, title, fence = {}, "", False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            fence = not fence
            continue
        if fence:
            if line.strip():
                out.setdefault(title, []).append(" ".join(line.split()))
        elif line.startswith("#"):
            title = line.lstrip("#").strip()
    return out


def drawing_differences(run_dir, opened, folder):
    """제안 도면과 생성본의 다른 줄(설계 7.2절). 달라도 실패가 아니다. opened는 {절 제목: 절 글}이다.
    명령이 코드 폴더를 고치면 그 줄을 함께 낸다. 어떤 실패도 한 장을 막지 않는다."""
    rows, bad = _generator_rows(run_dir)
    if not rows and not bad:
        return [NO_GENERATOR]
    out = ["생성 명령 줄을 읽지 못함: " + line for line in bad]
    for word, text in opened.items():
        for sub_title, lines in _drawing_lines(text).items():
            heading = "{} {}".format(word, sub_title)
            gen = next((g for g in rows if g[0] in heading), None)
            if gen is None:
                out.append("같은 이름의 생성 명령이 없어 대조하지 못함: {}".format(heading.strip()))
                continue
            result = run_generator(run_dir, gen[0], gen[1], folder)
            out += _touched_lines(gen[0], result)
            if not result["ok"]:
                out.append("돌리지 못함: {} ({})".format(gen[0], result["text"]))
                continue
            produced = [" ".join(l.split()) for l in result["text"].split("\n") if l.strip()]
            only = ["제안에만: " + l for l in lines if l not in produced] + ["생성본에만: " + l for l in produced if l not in lines]
            out += only[:DRAW_LIMIT] + (["… 나머지 {}줄".format(len(only) - DRAW_LIMIT)] if len(only) > DRAW_LIMIT else [])
    return out


# ---------------------------------------------------------------- 낡음


def state_path(run_dir):
    """`_workspace\\policies\\docs-state.md`: 문서 안에 두면 넣은 뒤 다시 커밋해야 하므로 작업 공간에 둔다(설계 7.5절)."""
    return os.path.join(os.path.dirname(os.path.abspath(run_dir)), "policies", STATE_FILE)


def _read_state_file(path):
    state = {"docs": {}, "closed": []}
    sections = devflow_lib.sections(_read(path) or "")
    for line in sections.get("문서", "").split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0].startswith(DOCS_ROOT + "/"):
            state["docs"][cells[0]] = {"paths": cells[1], "commit": cells[2], "status": cells[3], "source": cells[4]}
    state["closed"] = [l.strip() for l in sections.get("닫힌 항목", "").split("\n") if l.strip().startswith("- ")]
    return state


def read_state(run_dir):
    return _read_state_file(state_path(run_dir))


def write_state(run_dir, state):
    lines = ["# 작성 문서 상태", "", "project_docs.py가 쓴다.", "", "## 문서", "| 문서 | 지키는 경로 | 기준 커밋 | 상태 | 넣은 task |", "|---|---|---|---|---|"]
    lines += ["| {} | {} | {} | {} | {} |".format(k, r["paths"], r["commit"], r["status"], r["source"]) for k, r in sorted(state["docs"].items())]
    lines += ["", "## 닫힌 항목"] + state["closed"]
    devflow_lib.write_text(state_path(run_dir), "\n".join(lines) + "\n")


def _sync_state(run_dir, state):
    """끝난 마무리가 넣은 문서의 기준 커밋을 넣은 끝으로 옮긴다. 한 마무리는 한 번만 옮긴다(뒤의 `--ok`를 되돌리지 않게).
    닫힌 항목은 내보낸 위험·미확인 목록에서 빠진 뒤에 상태에서 지운다."""
    run = os.path.basename(os.path.abspath(run_dir))
    project = _project(run_dir)
    for t in devflow_lib.load_tasks(run_dir).values():
        tip = str(t.get("exported_commit", "") or "").strip()
        if t.get("kind") != "wrap-up" or t.get("status") != kinds.DONE or not tip or not applies(run_dir, t):
            continue
        source = "{}/{}".format(run, t["id"])
        for doc, paths in GUARD_LINE.findall(_read(os.path.join(t["_dir"], "result.md")) or ""):
            if state["docs"].get(doc, {}).get("source") != source:
                state["docs"][doc] = {"paths": paths, "commit": tip, "status": "최신", "source": source}
        exported = _show(project, tip, UNVERIFIED_DOC)
        if exported is not None:
            have = {l.strip() for l in exported.split("\n")}
            state["closed"] = [c for c in state["closed"] if c in have]


def _spec_args(paths):
    return [":(glob)" + p.strip() for p in paths.split(",") if p.strip()]


def stale(run_dir, ok=None):
    """`확인 필요` 줄을 내고 상태 파일을 쓴다. 프로젝트를 고치지 않고 종료는 늘 0이다."""
    meta = devflow_lib.run_meta(run_dir)
    project = str(meta.get("project", "") or "").strip()
    branch = str(meta.get("base_branch", "") or "").strip() or "HEAD"
    state = read_state(run_dir)
    _sync_state(run_dir, state)
    rc, tip = _git(project, "rev-parse", branch)
    if ok and ok in state["docs"] and rc == 0:
        state["docs"][ok].update(commit=tip, status="최신")
    found = 0
    for doc, row in sorted(state["docs"].items()):
        code, _ = _git(project, "rev-parse", "--verify", "--quiet", row["commit"] + "^{commit}")
        why = "기준 커밋을 읽지 못함" if code != 0 else ""
        if not why:
            _, names = _git(project, "diff", "--name-only", row["commit"], branch, "--", *_spec_args(row["paths"]))
            why = names.splitlines()[0] if names else ""
        row["status"] = NEEDS_CHECK if why else "최신"
        if why:
            print("{}: {} | {}".format(NEEDS_CHECK, doc, why))
            found += 1
    if state["docs"] or state["closed"] or os.path.isfile(state_path(run_dir)):
        write_state(run_dir, state)
    print("문서 낡음: {}건".format(found))
    return 0


def close_item(run_dir, line):
    state = read_state(run_dir)
    if line.strip() not in state["closed"]:
        state["closed"].append(line.strip())
    write_state(run_dir, state)
    print("닫힌 항목으로 둠: " + line.strip())
    return 0


# ---------------------------------------------------------------- git 훅(막지 않고 경고만)


def hook_answer(run_dir):
    """프로젝트 설정 `git 훅 경고` 값. 없으면 빈 글이다(아직 묻지 않음)."""
    for line in (_read(_settings_path(run_dir)) or "").split("\n"):
        if line.startswith("- {}:".format(HOOK_KEY)):
            return line.split(":", 1)[1].strip()
    return ""


def _set_hook_answer(run_dir, value):
    """답 줄은 첫 `##` 앞에 둔다. 절 안에 들어가면 그 절의 줄로 읽힌다."""
    text = _read(_settings_path(run_dir)) or "# 프로젝트 설정\n"
    line = "- {}: {}".format(HOOK_KEY, value)
    if hook_answer(run_dir):
        text = re.sub(r"(?m)^- " + re.escape(HOOK_KEY) + ":.*$", line, text)
    else:
        found = re.search(r"(?m)^## ", text)
        at = found.start() if found else len(text)
        head = text[:at].rstrip("\n")
        text = head + "\n" + line + "\n" + ("\n" + text[at:] if found else "")
    devflow_lib.write_text(_settings_path(run_dir), text)


def _hook_file(project):
    """(pre-commit 경로, 두지 못하는 까닭)."""
    rc, folder = _git(project, "rev-parse", "--git-path", "hooks")
    if rc != 0:
        return None, NO_GIT
    _, custom = _git(project, "config", "core.hooksPath")
    if custom:
        return None, "core.hooksPath가 있음({})".format(custom)
    folder = folder if os.path.isabs(folder) else os.path.join(project, folder)
    return os.path.join(folder, "pre-commit"), ""


def _is_our_hook(path):
    """바이트로 가른다. UTF-8이 아닌 훅, 바이너리 훅, 끊어진 링크는 모두 사용자 것이다."""
    if os.path.islink(path) or not os.path.isfile(path):
        return False
    with open(path, "rb") as f:
        return HOOK_MARK.encode("utf-8") in f.read()


def install_hook(run_dir):
    """답을 받은 뒤에 부른다. 사용자 훅을 덮지 않는다."""
    _set_hook_answer(run_dir, HOOK_ON)
    return _write_hook(run_dir)


def _write_hook(run_dir):
    path, why = _hook_file(_project(run_dir))
    if path is None:
        print("{}: {}".format(HOOK_SKIPPED, why))
        return 0
    if os.path.lexists(path) and not _is_our_hook(path):
        print("{}: 다른 pre-commit이 있음".format(HOOK_SKIPPED))
        return 0
    script = os.path.abspath(__file__).replace("\\", "/")
    workspace = os.path.dirname(os.path.abspath(run_dir)).replace("\\", "/")
    silent = "echo \"{}: 경고를 내지 못함\"".format(HOOK_MARK)
    body = ("#!/bin/sh\n# {mark}. 막지 않는다\n"
            "if [ -f \"{script}\" ]; then\n"
            "  for py in python3 python py; do\n"
            "    command -v \"$py\" >/dev/null 2>&1 || continue\n"
            "    \"$py\" -c \"\" >/dev/null 2>&1 || continue\n"   # Windows의 python3 대리 실행은 찾아지지만 돌지 않는다
            "    PYTHONIOENCODING=utf-8 \"$py\" \"{script}\" --hook-check \"{workspace}\" 2>/dev/null || {silent}\n"
            "    exit 0\n"
            "  done\n"
            "fi\n"
            "{silent}\n"
            "exit 0\n").format(mark=HOOK_MARK, script=script, workspace=workspace, silent=silent)
    devflow_lib.write_text(path, body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print("git 훅 경고를 둠: {} (지우기: project_docs.py {{실행 폴더}} --unhook)".format(path))
    return 0


def remove_hook(run_dir):
    """우리 훅만 지우고 `안 함`을 적어 다시 두지 않는다."""
    _set_hook_answer(run_dir, HOOK_OFF)
    path, why = _hook_file(_project(run_dir))
    if path is not None and _is_our_hook(path):
        os.remove(path)
        print("git 훅 경고를 지움: " + path)
    else:
        print("지울 하네스 훅이 없음" + (": " + why if why else ""))
    return 0


def hook_check(workspace):
    """스테이지한 파일이 작성 문서의 지키는 경로에 들고 그 문서를 함께 고치지 않았으면 경고한다. 어떤 경우에도 커밋을 막지 않는다."""
    try:
        state = _read_state_file(os.path.join(workspace, "policies", STATE_FILE))
        _, names = _git(os.getcwd(), "diff", "--cached", "--name-only")
        staged = [n.strip() for n in names.splitlines()]
        for doc, row in sorted(state["docs"].items()):
            if doc in staged:
                continue
            hit = [n for n in staged for p in row["paths"].split(",") if fnmatch.fnmatch(n, p.strip())]
            if hit:
                print("{}: {}의 지키는 경로가 바뀝니다({})".format(HOOK_MARK, doc, hit[0]))
    except (OSError, ValueError, UnicodeError) as e:
        print("{}: 재지 못함 ({})".format(HOOK_MARK, e))
    return 0


def start(run_dir):
    if not has_base(run_dir):
        rc = make_base(run_dir)
        if rc:
            return rc
    answer = hook_answer(run_dir)
    if answer == HOOK_ON:
        _write_hook(run_dir)   # 플러그인 경로가 바뀌었어도 경고가 이어진다
    elif not answer and _git(_project(run_dir), "rev-parse", "--is-inside-work-tree")[1] == "true":
        print("묻기: 이 저장소에 문서 낡음 경고 훅(pre-commit)을 둘까요? 두면 하네스 밖의 커밋에서도 Python 스크립트가 돌아, 작성 문서가 지키는 경로를 고칠 때 경고만 합니다(막지 않음). "
              "답: 둠 -> --hook / 안 함 -> --unhook. 답은 프로젝트 설정에 남아 다시 묻지 않습니다")
    return stale(run_dir)


def _option(argv, flag):
    if flag not in argv:
        return None
    at = argv.index(flag) + 1
    return argv[at] if at < len(argv) else ""


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) >= 3 and argv[1] == "--hook-check":
        return hook_check(argv[2])
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, second = argv[1], argv[2]
    if second == "--start":
        return start(run_dir)
    if second == "--base":
        return make_base(run_dir)
    if second == "--hook":
        return install_hook(run_dir)
    if second == "--unhook":
        return remove_hook(run_dir)
    if second == "--stale":
        return stale(run_dir, _option(argv, "--ok"))
    if second == "--close":
        return close_item(run_dir, argv[3]) if len(argv) > 3 else 2
    if "--insert" in argv[3:]:
        folder = _option(argv, "--insert")
        folder = None if not folder or folder.startswith("--") else folder
        return insert(run_dir, second, folder, _option(argv, "--take"))
    if "--generate" in argv[3:]:
        folder = _option(argv, "--generate")
        if not folder or folder.startswith("--"):
            folder = insert_folder(run_dir)
        return generate(run_dir, folder, "--check" in argv[3:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
