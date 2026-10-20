"""재시도의 수정 전 사본(`tasks\\{id}\\before.r{n}\\`)과 지금을 견주는 읽기 전용 도구.

사본은 `task_set.py --archive-judge`가 판정 파일을 보관할 때 같은 n으로 뜬다. 판정자가 "앞 판정 뒤
무엇이 바뀌었나"를 보려고 부른다. 코드 폴더와 실행 폴더에는 아무것도 쓰지 않는다(git은 임시 색인·임시 객체 폴더로만 돈다).

사용:
  python retry_diff.py {실행 폴더} {task id} [--round n] [--full]

  --round n   before.r{n}을 본다. 없으면 가장 큰 n.
  --full      바뀐 파일마다 unified diff를 이어 찍는다(문서는 difflib, 코드는 두 트리의 git diff).

출력(종료 0):
  파일:       사본 목록의 경로마다 `같음` / `바뀜 +a -b` / `지워짐` / `사본 없음(상한)`.
              「건드릴 파일」 패턴(과 result.md·revised\\)에 지금 맞는데 목록에 없는 파일은 `새 파일`.
              실행 폴더 spec\\·ui\\·design\\ 아래에서 앞 판정 시각 뒤에 바뀐 파일 가운데 목록에 없는 것은 `사본 밖 변경`.
  코드:       code.patch로 앞 판정 시점 트리를 다시 세우고 지금 트리와 `git diff --stat`.
              HEAD가 사본의 HEAD와 다르면 맨 위에 `HEAD 바뀜 {앞}→{지금}`을 찍고 그래도 비교한다.
종료 코드: 0 / 2 사용법·task 없음·사본 없음

엔진 층 2(검사·계산). import는 devflow_lib·kinds와 표준 라이브러리만. 사본에 넣을 파일을 고르는 함수(snapshot_sources)와
임시 색인으로 git을 돌리는 TempGit은 사본을 뜨는 task_set.py도 쓴다(같은 집합·같은 방법).
"""
import difflib
import glob
import hashlib
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

import devflow_lib
import kinds

MANIFEST = "MANIFEST.md"
FILES_DIR = "files"
PATCH = "code.patch"
CAPPED = "사본 없음(상한)"
NO_MATCH = "맞는 파일 없음"
SNAPSHOT_DIR = re.compile(r"^before\.r(\d+)$")
WILDCARD = re.compile(r"[*?\[]")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
USAGE = "사용법: python retry_diff.py {실행 폴더} {task id} [--round n] [--full]"


# ---------------------------------------------------------------- 사본에 넣을 파일

def run_rel(run_dir, path):
    """실행 폴더 기준 경로(`/` 구분)로. 실행 폴더 밖이면 None. 작업 공간 기준 꼴(`_workspace/{실행}/…`, `{실행}/…`)도 받는다."""
    base = os.path.abspath(run_dir).replace("\\", "/").rstrip("/")
    name = os.path.basename(base)
    q = path.replace("\\", "/")
    if q.lower().startswith(base.lower() + "/"):
        q = q[len(base) + 1:]
    elif re.match(r"^(?:[A-Za-z]:)?/", q):
        return None
    else:
        m = re.match(r"^(?:\./)?(?:_workspace/)?" + re.escape(name) + "/", q, re.I)
        if m:
            q = q[m.end():]
    q = posixpath.normpath(re.sub(r"^\./", "", q))
    if q in (".", "") or q.startswith("../") or q == "..":
        return None
    return q


def _under_snapshot(rel, task_rel):
    """task 폴더의 before.r{n}\\ 아래(앞 회차 사본)는 사본에 넣지 않는다."""
    if not rel.startswith(task_rel + "/"):
        return False
    first = rel[len(task_rel) + 1:].split("/", 1)[0]
    return bool(SNAPSHOT_DIR.match(first))


def _files_under(run_dir, rel_dir):
    out = []
    for root, dirs, names in os.walk(os.path.join(run_dir, rel_dir)):
        dirs.sort()
        for n in sorted(names):
            out.append(os.path.relpath(os.path.join(root, n), run_dir).replace("\\", "/"))
    return out


def snapshot_sources(run_dir, t):
    """(사본에 넣을 파일의 실행 폴더 기준 경로 목록, 맞는 파일이 없는 경로·패턴 목록).
    `result.md`는 모든 kind에서, 코드 폴더에 쓰지 않는 kind는 「건드릴 파일」 가운데 실행 폴더 안 경로(패턴은 펼침)와
    task 폴더 `revised\\**`도. 코드 kind의 「건드릴 파일」은 코드 폴더 경로라 code.patch가 맡는다."""
    task_rel = run_rel(run_dir, t["_dir"]) or "tasks/{}".format(t.get("id", ""))
    files, missing = [], []

    def add(rel):
        if rel not in files and not _under_snapshot(rel, task_rel):
            files.append(rel)

    result = task_rel + "/result.md"
    if os.path.isfile(os.path.join(run_dir, result)):
        add(result)
    else:
        missing.append(result)
    if t.get("kind") in kinds.CODE_DIR_KINDS:
        return files, missing
    for tok in devflow_lib.touch_paths(t.get("_sections", {}).get("건드릴 파일", "")):
        rel = run_rel(run_dir, tok)
        if rel is None:
            continue
        full = os.path.join(run_dir, rel)
        if WILDCARD.search(rel):
            found = sorted(p for p in glob.glob(full, recursive=True) if os.path.isfile(p))
            found = [os.path.relpath(p, run_dir).replace("\\", "/") for p in found]
        elif os.path.isdir(full):
            found = _files_under(run_dir, rel)
        else:
            found = [rel] if os.path.isfile(full) else []
        if not found and rel not in missing:
            missing.append(rel)
        for f in found:
            add(f)
    revised = task_rel + "/revised"
    if os.path.isdir(os.path.join(run_dir, revised)):
        for f in _files_under(run_dir, revised):
            add(f)
    return files, missing


def sha16(data):
    return hashlib.sha256(data).hexdigest()[:16]


# ---------------------------------------------------------------- 임시 색인·임시 객체 폴더로 도는 git

class GitError(Exception):
    pass


class TempGit:
    """코드 폴더의 작업 트리·색인·`.git` 객체·ref를 바꾸지 않고 트리를 만든다. 색인은 지금 색인의 복사본(임시 폴더),
    새 객체는 임시 객체 폴더(`GIT_OBJECT_DIRECTORY`)에, 코드 폴더 객체는 `GIT_ALTERNATE_OBJECT_DIRECTORIES`로 읽는다.
    `with` 블록을 나가면 임시 폴더를 지운다."""

    def __init__(self, code_dir):
        self.dir = code_dir
        self.tmp = None

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="devflow-retry-")
        try:
            self.objects = self.plain("rev-parse", "--path-format=absolute", "--git-path", "objects").strip()
            self.real_index = self.plain("rev-parse", "--path-format=absolute", "--git-path", "index").strip()
            os.mkdir(os.path.join(self.tmp, "objects"))
        except BaseException:
            shutil.rmtree(self.tmp, ignore_errors=True)
            raise
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False

    def _run(self, args, env, binary=False):
        cmd = ["git", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "-C", self.dir] + list(args)
        try:
            out = subprocess.run(cmd, capture_output=True, env=env)
        except OSError as e:
            raise GitError("git을 돌리지 못함: {}".format(e))
        if out.returncode != 0:
            err = out.stderr.decode("utf-8", "replace").strip().splitlines()
            raise GitError("git {} 종료 {}: {}".format(args[0], out.returncode, err[0] if err else ""))
        return out.stdout if binary else out.stdout.decode("utf-8", "replace")

    def _env(self, index):
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        if index:
            env.update(GIT_INDEX_FILE=os.path.join(self.tmp, index),
                       GIT_OBJECT_DIRECTORY=os.path.join(self.tmp, "objects"),
                       GIT_ALTERNATE_OBJECT_DIRECTORIES=self.objects)
        return env

    def plain(self, *args):
        """코드 폴더의 색인으로 읽기만 하는 명령(`GIT_OPTIONAL_LOCKS=0`이라 status도 색인을 다시 쓰지 않는다)."""
        return self._run(args, self._env(None))

    def git(self, index, *args, binary=False):
        return self._run(args, self._env(index), binary=binary)

    def head(self):
        try:
            return self.plain("rev-parse", "--verify", "-q", "HEAD^{commit}").strip() or None
        except GitError:
            return None   # 커밋이 없는 저장소

    def now_tree(self, index="now.index"):
        """지금 작업 트리(추적 안 된 새 파일 포함, .gitignore 제외)의 트리. 임시 색인에 `git add -A`."""
        path = os.path.join(self.tmp, index)
        if os.path.isfile(self.real_index):
            shutil.copyfile(self.real_index, path)
        self.git(index, "add", "-A")
        return self.git(index, "write-tree").strip()

    def patch(self, base, index="now.index"):
        """(HEAD 대비 patch 바이트, 바뀐 파일 수). now_tree 뒤에 부른다."""
        rev = base or self.git(index, "hash-object", "-t", "tree", os.devnull).strip()
        data = self.git(index, "diff", "--cached", "--binary", "--no-color", "--no-ext-diff", "--no-textconv",
                        "--no-renames", rev, binary=True)
        names = self.git(index, "diff", "--cached", "--name-only", "-z", "--no-renames", rev, binary=True)
        return data, len([x for x in names.split(b"\0") if x])

    def tree_from_patch(self, base, patch_path, index="before.index"):
        """base 트리에 patch를 얹은 트리(앞 판정 시점)."""
        if base:
            self.git(index, "read-tree", base)
        else:
            self.git(index, "read-tree", "--empty")
        if os.path.getsize(patch_path):
            self.git(index, "apply", "--cached", "--whitespace=nowarn", patch_path)
        return self.git(index, "write-tree").strip()

    def status(self):
        return [line for line in self.plain("status", "--porcelain", "-uall").splitlines() if line.strip()]


# ---------------------------------------------------------------- 사본 읽기

def rounds(task_dir):
    """MANIFEST.md가 있는 before.r{n}의 n 목록(오름차순)."""
    out = []
    if os.path.isdir(task_dir):
        for name in os.listdir(task_dir):
            m = SNAPSHOT_DIR.match(name)
            if m and os.path.isfile(os.path.join(task_dir, name, MANIFEST)):
                out.append(int(m.group(1)))
    return sorted(out)


def read_manifest(path):
    """MANIFEST.md를 {"time", "judged", "kind", "files": [(경로, 상태, 바이트)], "missing": [패턴], "code": 줄 목록}으로.
    상태는 sha256 앞 16자(사본 있음) 또는 CAPPED."""
    text = devflow_lib.read_text(path)
    head = {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        m = re.match(r"^- ([^:]+):\s*(.*)$", line)
        if m:
            head[m.group(1).strip()] = m.group(2).strip()
    secs = devflow_lib.sections(text, level=2)
    files, missing = [], []
    for line in secs.get("파일", "").splitlines():
        if not line.startswith("- "):
            continue
        cells = [c.strip() for c in line[2:].split(" | ")]
        if len(cells) == 2 and cells[1] == NO_MATCH:
            missing.append(cells[0])
        elif len(cells) == 3 and cells[1] == CAPPED:
            files.append((cells[0], CAPPED, cells[2]))
        elif len(cells) == 3:
            files.append((cells[0], cells[2], cells[1]))
    code = [line for line in secs.get("코드", "").splitlines() if line.strip()]
    return {"time": head.get("시각", ""), "judged": head.get("앞 판정 시각", ""), "kind": head.get("kind", ""),
            "files": files, "missing": missing, "code": code}


def parse_code_line(line):
    """`- 폴더: X | HEAD: H | patch: … | 바뀐 파일 N`을 사전으로. 그 꼴이 아니면 None."""
    if not line.startswith("- 폴더: "):
        return None
    out = {}
    for cell in line[2:].split(" | "):
        k, _, v = cell.partition(":")
        out[k.strip()] = v.strip()
    return out


def stamp(text):
    try:
        return datetime.strptime(text, TIME_FORMAT).timestamp()
    except (TypeError, ValueError):
        return None


def _lines(data):
    return data.decode("utf-8", "replace").splitlines(keepends=True)


def line_counts(old, new):
    added = removed = 0
    for line in difflib.unified_diff(_lines(old), _lines(new), n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


# ---------------------------------------------------------------- 비교

def compare_files(run_dir, t, snap_dir, man):
    """(줄 목록, --full에 쓸 (경로, 앞 바이트, 지금 바이트) 목록)."""
    out, changed = [], []
    listed = set()
    for rel, state, _size in man["files"]:
        listed.add(rel)
        cur = os.path.join(run_dir, rel)
        if state == CAPPED:
            out.append("- {} | {}".format(rel, CAPPED))
            continue
        if not os.path.isfile(cur):
            out.append("- {} | 지워짐".format(rel))
            continue
        with open(os.path.join(snap_dir, FILES_DIR, rel), "rb") as f:
            old = f.read()
        with open(cur, "rb") as f:
            new = f.read()
        if old == new:
            out.append("- {} | 같음".format(rel))
        else:
            a, b = line_counts(old, new)
            out.append("- {} | 바뀜 +{} -{}".format(rel, a, b))
            changed.append((rel, old, new))
    now_files, _ = snapshot_sources(run_dir, t)
    fresh = [f for f in now_files if f not in listed]
    out += ["- {} | 새 파일".format(f) for f in fresh]
    since = stamp(man["judged"]) or stamp(man["time"])
    if since is not None:
        seen = listed | set(fresh)
        for top in kinds.CANON_DIRS:
            if not os.path.isdir(os.path.join(run_dir, top)):
                continue
            for rel in _files_under(run_dir, top):
                if rel not in seen and os.path.getmtime(os.path.join(run_dir, rel)) > since:
                    out.append("- {} | 사본 밖 변경".format(rel))
    return out, changed, fresh


def compare_code(snap_dir, man, full):
    """(맨 위 줄 목록, 코드 줄 목록, --full diff 글)."""
    top, body, diff = [], [], ""
    info = next((parse_code_line(x) for x in man["code"] if parse_code_line(x)), None)
    if info is None:
        body.append("코드: " + (man["code"][0][2:] if man["code"] else "없음"))
        return top, body, diff
    patch_cell = info.get("patch", "")
    if not patch_cell.startswith(PATCH):
        body.append("코드: patch {} — 바뀐 파일 목록만 사본에 있음(MANIFEST.md ## 코드)".format(patch_cell))
        return top, body, diff
    folder, base = info.get("폴더", ""), info.get("HEAD", "")
    base = base if re.fullmatch(r"[0-9a-f]{7,64}", base) else None
    try:
        with TempGit(folder) as g:
            now_head = g.head()
            if (base or None) != now_head:
                top.append("HEAD 바뀜 {}→{}".format(base or "(커밋 없음)", now_head or "(커밋 없음)"))
            before = g.tree_from_patch(base, os.path.join(snap_dir, PATCH))
            now = g.now_tree()
            stat = g.git("now.index", "diff", "--stat=1000", "--no-color", "--no-renames", before, now)
            if full:
                diff = g.git("now.index", "diff", "--no-color", "--no-ext-diff", "--no-renames", before, now)
    except (GitError, OSError) as e:
        body.append("코드: 비교 못 함 — {}".format(e))
        return top, body, diff
    lines = [x for x in stat.splitlines() if x.strip()]
    body.append("코드: {} (앞 판정 시점 → 지금 작업 트리)".format(folder))
    body += lines if lines else ["- 앞 판정 뒤 바뀐 파일 없음"]
    return top, body, diff


def main(argv):
    devflow_lib.utf8_stdout()
    args, n, full = [], None, False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--full":
            full = True
        elif a == "--round":
            if i + 1 >= len(argv) or not argv[i + 1].isdigit():
                print(USAGE)
                return 2
            n = int(argv[i + 1])
            i += 1
        elif a.startswith("--"):
            print(USAGE)
            return 2
        else:
            args.append(a)
        i += 1
    if len(args) != 2:
        print(USAGE)
        return 2
    run_dir, tid = args
    task_md = os.path.join(run_dir, "tasks", tid, "task.md")
    if not os.path.isfile(task_md):
        print("task를 찾지 못함: " + tid)
        return 2
    t = devflow_lib.load_task(task_md)
    have = rounds(t["_dir"])
    if n is None and have:
        n = have[-1]
    if n is None or n not in have:
        print("사본 없음: tasks\\{}\\before.r{}".format(tid, n if n is not None else "*"))
        return 2
    snap_dir = os.path.join(t["_dir"], "before.r{}".format(n))
    man = read_manifest(os.path.join(snap_dir, MANIFEST))
    file_lines, changed, fresh = compare_files(run_dir, t, snap_dir, man)
    top, code_lines, code_diff = compare_code(snap_dir, man, full)
    out = top + ["{} before.r{} (사본 {}, 앞 판정 {}, kind {})".format(tid, n, man["time"], man["judged"], man["kind"]),
                 "파일:"] + (file_lines or ["- 없음"]) + code_lines
    if full:
        for rel, old, new in changed:
            out += [x.rstrip("\n") for x in difflib.unified_diff(
                _lines(old), _lines(new), "before.r{}/{}".format(n, rel), rel)]
        for rel in fresh:
            with open(os.path.join(run_dir, rel), "rb") as f:
                out += [x.rstrip("\n") for x in difflib.unified_diff([], _lines(f.read()), "/dev/null", rel)]
        if code_diff:
            out += code_diff.rstrip("\n").splitlines()
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
