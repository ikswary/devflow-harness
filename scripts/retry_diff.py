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
「치워 두기」 절(설계 8.2절)도 같은 방법으로 뜬다. 코드 폴더를 바꾸는 함수는 그 절의 revert_parked·cancel_parked·apply_parked뿐이고
`task_set.py --park`·`--unpark`·`--park-cancel`만 부른다(이 명령행 도구는 부르지 않는다).
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
        cmd = ["git", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "-c", "core.longpaths=true",
               "-C", self.dir] + list(args)
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
            # 시각까지 복사한다. 색인이 새것처럼 보이면 git의 같은 초 재확인이 꺼져 같은 크기로 고친 파일을 놓친다
            shutil.copy2(self.real_index, path)
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

    def capture(self):
        """(HEAD, 지금 트리, HEAD 대비 patch 바이트, 바뀐 파일 수). 재시도 사본과 치워 두기가 같은 꼴로 뜬다."""
        head = self.head()
        tree = self.now_tree()
        data, changed = self.patch(head)
        return head, tree, data, changed

    def status(self):
        return [line for line in self.plain("status", "--porcelain", "-uall").splitlines() if line.strip()]


# ---------------------------------------------------------------- 치워 두기(설계 8.2절)

# 표지(`parked`, `parked_pending`, `repro_patch`)의 값: `{패치 경로} {뜰 때의 HEAD} {파일 목록 해시}`. 패치 경로는 실행 폴더 기준이다
PARK_NO_HEAD = "-"     # 커밋이 없는 저장소
PARK_BEFORE = "붙기 전"
PARK_AFTER = "붙은 뒤"
PARK_CONFLICT = "충돌"
PARK_MISMATCH = "어긋남"
PARK_PARTIAL = "일부만 있음"   # 폴더의 변경이 패치 파일의 일부뿐(붙이다 끊겼거나 다른 변경)
# 표지 `park_applying`의 값. 뜰 때의 목록과 달라져도 붙은 뒤를 알아보는 근거다
APPLYING = "붙이는 중"
APPLY_CONFLICT = "충돌"
PATH_CHUNK = 100       # 한 번에 넘기는 경로 수(명령 줄 길이 상한)
SHOWN_PATHS = 20       # 거부 줄에 싣는 경로 수
CONFLICT_MARK = re.compile(rb"^<{7} .*?^>{7} ", re.M | re.S)


def real_git(folder, *args, env=None, stdin=None):
    """코드 폴더의 진짜 색인으로 돈다. 실패하면 GitError."""
    cmd = ["git", "--literal-pathspecs", "-c", "core.longpaths=true", "-C", folder] + list(args)
    try:
        out = subprocess.run(cmd, capture_output=True, env=env, input=stdin)
    except OSError as e:
        raise GitError("git을 돌리지 못함: {}".format(e))
    if out.returncode != 0:
        raise GitError("git {} 종료 {}: {}".format(args[0], out.returncode, error_line(out.stderr)))
    return out.stdout


def error_line(stderr):
    """git 오류 출력에서 이유가 적힌 줄. `error:` 줄을 먼저 고른다(`Applied patch … cleanly.`가 앞에 올 수 있다)."""
    lines = stderr.decode("utf-8", "replace").strip().splitlines()
    return next((x for x in lines if x.startswith("error:")), lines[0] if lines else "")


def status_entries(folder):
    """[(XY, 경로)]. `-z`라 한글 경로가 이스케이프되지 않는다. `GIT_OPTIONAL_LOCKS=0`이라 색인을 다시 쓰지 않는다."""
    raw = real_git(folder, "status", "--porcelain", "-z", "-uall", "--no-renames",
                   env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    return [(x[:2].decode("ascii"), os.fsdecode(x[3:])) for x in raw.split(b"\0") if x]


def unmerged(entries):
    return [p for xy, p in entries if "U" in xy or xy in ("AA", "DD")]


def list_digest(names):
    return sha16(b"\0".join(sorted(os.fsencode(n) for n in names)))


def park_mark(patch_rel, head, names):
    return "{} {} {}".format(patch_rel, head or PARK_NO_HEAD, list_digest(names))


def parse_mark(value):
    """표지 값을 (패치 경로, HEAD 또는 None, 파일 목록 해시)로."""
    patch, head, digest = str(value).split()
    return patch, None if head == PARK_NO_HEAD else head, digest


def _os_path(folder, name):
    """파일 함수에 넘길 경로. Windows는 260자 제한을 넘는 경로도 다루게 접두어를 붙인다."""
    path = os.path.abspath(os.path.join(folder, name))
    return "\\\\?\\" + path if os.name == "nt" and not path.startswith("\\\\") else path


def _require_top(folder):
    """코드 폴더가 저장소 맨 위인지. 하위 폴더면 `git apply`가 밖 경로를 말없이 건너뛰고 성공한다."""
    if real_git(folder, "rev-parse", "--show-prefix").strip():
        raise GitError("코드 폴더가 저장소 맨 위가 아님: {}".format(folder))


def _tree_names(g, index, a, b):
    raw = g.git(index, "diff", "--name-only", "-z", "--no-renames", a, b, binary=True)
    return {os.fsdecode(x) for x in raw.split(b"\0") if x}


def _parents(name):
    """`a/b/c`의 `a/b`, `a`."""
    out = []
    while "/" in name:
        name = name.rsplit("/", 1)[0]
        out.append(name)
    return out


def _not_restorable(folder, touched, in_patch):
    """touched를 되돌리면 사라지는데 패치로 돌아오지 않는 경로. 되돌리는 명령이 돌기 전에 묻는 하나뿐인 검사다. status와 패치가 보지 못하는
    것은 무시되는 파일과 안쪽 저장소·서브모듈이다. 복원 명령은 그 경로 자리, 그 아래, 부모 자리의 파일을 치우거나 덮어쓰므로
    무시되는 파일이 touched와 같거나 그 아래이거나 그 부모이면 복원되지 않는다."""
    lost = set(touched) - in_patch
    lost.update(n for n in touched if os.path.lexists(_os_path(folder, posixpath.join(n, ".git"))))
    paths = {n.rstrip("/") for n in touched}
    parents = {p for n in paths for p in _parents(n)}
    raw = real_git(folder, "ls-files", "-o", "-i", "--exclude-standard", "-z")
    for name in (os.fsdecode(x) for x in raw.split(b"\0") if x):
        if name in paths or name in parents or paths.intersection(_parents(name)):
            lost.add(name)
    return sorted(lost)


def _require_restorable(folder, touched, in_patch):
    lost = _not_restorable(folder, touched, in_patch)
    if lost:
        raise GitError("{}: 패치로 복원되지 않는 경로(무시되는 파일, 안쪽 저장소, 서브모듈, 패치 밖 변경)가 있어 되돌리지 않음: {}{}".format(
            PARK_MISMATCH, ", ".join(lost[:SHOWN_PATHS]), " 외 {}개".format(len(lost) - SHOWN_PATHS) if len(lost) > SHOWN_PATHS else ""))


def park_capture(folder):
    """(HEAD, patch 바이트, 파일 목록). 코드 폴더를 바꾸지 않는다. patch를 HEAD에 얹은 트리가 지금 트리와 같고 status의 변경이
    모두 patch에 있을 때만 돌려준다. 충돌 중인 파일, 패치로 복원되지 않는 경로(_not_restorable), 되돌리면 무시 규칙이 바뀌는
    `.gitignore`(가려졌던 파일이 드러나 되돌리기가 끝나지 않는다)가 있으면 GitError다."""
    _require_top(folder)
    entries = status_entries(folder)
    names = [p for _, p in entries]
    if unmerged(entries):
        raise GitError("충돌 중인 파일이 있어 치우지 않음: {}".format(", ".join(unmerged(entries))))
    _require_restorable(folder, names, set(names))   # 안쪽 저장소는 임시 색인에도 올라가지 않으므로 뜨기 전에 본다
    ignores = [p for p in names if posixpath.basename(p) == ".gitignore"]
    if ignores:
        raise GitError("`.gitignore`를 바꾼 task는 치우지 않음: {}".format(", ".join(ignores)))
    with TempGit(folder) as g:
        head, tree, data, _ = g.capture()
        if data:
            check = os.path.join(g.tmp, "check.patch")
            with open(check, "wb") as f:
                f.write(data)
            if g.tree_from_patch(head, check) != tree:
                raise GitError("뜬 패치로 지금 트리를 다시 세우지 못함")
        base = head or g.git("now.index", "hash-object", "-t", "tree", os.devnull).strip()
        in_patch = _tree_names(g, "now.index", base, tree)
    if data:
        _require_restorable(folder, names, in_patch)
    return head, data, names


def _delete_new(folder, names):
    """HEAD에 없는 파일: 색인에서 빼고 지운다. 뜬 파일 목록의 파일만 지우고, 그래서 빈 부모 폴더만 치운다
    (추적 파일이 있던 자리면 복원이 막힌다). 색인 삭제는 경로 규칙이 없는 `update-index`다(같은 이름의 추적 폴더를 건드리지 않는다)."""
    if names:
        real_git(folder, "update-index", "--force-remove", "-z", "--stdin",
                 stdin=b"".join(os.fsencode(n) + b"\0" for n in names))
    for name in names:
        path = _os_path(folder, name)
        try:
            if os.path.lexists(path):
                os.remove(path)
            parent = os.path.dirname(name)
            while parent:
                os.rmdir(_os_path(folder, parent))
                parent = os.path.dirname(parent)
        except FileNotFoundError:
            pass
        except OSError as e:
            if os.path.lexists(path):
                raise GitError("{}을 지우지 못함: {}".format(name, e))   # 빈 폴더가 아니어서 못 지운 부모는 그대로 둔다


def _restore_tracked(folder, names):
    """HEAD에 있는 파일: 색인과 작업 트리를 HEAD로."""
    for i in range(0, len(names), PATH_CHUNK):
        real_git(folder, "restore", "--source=HEAD", "--staged", "--worktree", "--", *names[i:i + PATH_CHUNK])


def _compare(folder, mark, patch_path):
    """(패치의 파일, 패치 결과와 다른 파일). 남은 변경이 모두 패치에 든 내용일 때만 돌려주고, 패치에 없는 내용(뜬 뒤 고친 파일,
    다른 새 파일)이 있거나 HEAD가 달라졌으면 GitError다. 코드 폴더를 바꾸지 않는다."""
    _, head, _ = parse_mark(mark)
    with TempGit(folder) as g:
        if g.head() != head:
            raise GitError("{}: 뜬 뒤 HEAD가 바뀜({})".format(PARK_MISMATCH, g.head() or "커밋 없음"))
        now = g.now_tree()
        base = head or g.git("now.index", "hash-object", "-t", "tree", os.devnull).strip()
        want = g.tree_from_patch(head, patch_path)
        differs = _tree_names(g, "now.index", now, want)
        extra = _tree_names(g, "now.index", base, now) & differs
        in_patch = _tree_names(g, "now.index", base, want)
    if extra:
        raise GitError("{}: 패치에 없는 내용이 있어 건드리지 않음: {}".format(PARK_MISMATCH, ", ".join(sorted(extra))))
    return in_patch, sorted(differs)


def _revert(folder, head, names):
    tracked = set()
    if head:
        raw = real_git(folder, "ls-tree", "-r", "-z", "--name-only", head)
        tracked = {os.fsdecode(x) for x in raw.split(b"\0") if x}
    # 새 파일을 먼저 지운다. 추적 파일이 있던 자리에 새 파일·폴더가 있으면 복원이 막힌다
    _delete_new(folder, [n for n in names if n not in tracked])
    _restore_tracked(folder, [n for n in names if n in tracked])
    left = status_entries(folder)
    if left:
        raise GitError("되돌린 뒤에도 변경이 남음: {}".format(", ".join(p for _, p in left)))


def revert_parked(folder, mark, patch_path):
    """패치에 담긴 변경만 작업 트리에서 되돌린다. 끊겼다 다시 불러도 된다."""
    in_patch, _ = _compare(folder, mark, patch_path)
    names = [p for _, p in status_entries(folder)]
    _require_restorable(folder, names, in_patch)   # 임시 색인이 놓쳐도 status가 본 변경은 되돌리지 않는다
    _revert(folder, parse_mark(mark)[1], names)


def cancel_parked(folder, mark, patch_path):
    """끊긴 되돌리기를 취소한다: 남은 변경이 패치 안의 것뿐이면 아무것도 되돌리지 않고, 패치 파일 가운데 이미 HEAD로 돌아간 것만 붙인다
    (이미 패치 결과인 파일은 건드리지 않으므로 지우지 못하는 파일에 막히지 않는다). 끊겼다 다시 불러도 된다."""
    _, todo = _compare(folder, mark, patch_path)
    for i in range(0, len(todo), PATH_CHUNK):
        ok, err = apply_parked(folder, parse_mark(mark)[1], patch_path, only=todo[i:i + PATH_CHUNK])
        if not ok:
            raise GitError("패치를 다시 붙이지 못함: {}".format(err))
    left = _compare(folder, mark, patch_path)[1]
    if left:
        raise GitError("패치를 다시 붙였는데 다른 파일이 남음: {}".format(", ".join(left)))


def apply_parked(folder, head, patch_path, only=None):
    """(붙었는가, 오류 줄). HEAD가 뜰 때와 같으면 `git apply`, 다르면 `git apply --3way`. 충돌이면 표지를 남기고 False다.
    only가 있으면 그 경로만 붙인다(`--include`는 글롭 패턴이라 특수 글자를 막는다)."""
    _require_top(folder)
    now = real_git(folder, "rev-parse", "--verify", "-q", "HEAD^{commit}").decode("ascii").strip() if head else None
    args = ["git", "-c", "core.longpaths=true", "-C", folder, "apply", "--whitespace=nowarn"] \
        + ([] if now == head else ["--3way"]) \
        + ["--include=" + re.sub(r"([*?\[\\])", r"\\\1", p) for p in only or []] + [patch_path]
    try:
        out = subprocess.run(args, capture_output=True)
    except OSError as e:
        raise GitError("git을 돌리지 못함: {}".format(e))
    return out.returncode == 0, error_line(out.stderr)


def markers_left(folder, names):
    """충돌했던 파일 가운데 충돌 표시가 남은 것."""
    left = []
    for name in names:
        path = _os_path(folder, name)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                if CONFLICT_MARK.search(f.read()):
                    left.append(name)
    return left


def missing_new_files(folder, mark, patch_path):
    """패치가 더한 새 파일 가운데 폴더에 없는 것(충돌을 풀다 함께 사라졌는지 보려고)."""
    head = parse_mark(mark)[1]
    with TempGit(folder) as g:
        base = head or g.git("before.index", "hash-object", "-t", "tree", os.devnull).strip()
        want = g.tree_from_patch(head, patch_path)
        raw = g.git("before.index", "diff", "--name-only", "-z", "--no-renames", "--diff-filter=A", base, want, binary=True)
    return sorted(n for n in (os.fsdecode(x) for x in raw.split(b"\0") if x) if not os.path.lexists(_os_path(folder, n)))


def park_state(folder, mark, patch_path, applying=""):
    """(붙기 전 / 붙은 뒤 / 충돌 / 일부만 있음 / 어긋남, 경로 목록). 아무것도 바꾸지 않는다. applying은 표지 `park_applying`의 값이다.
    충돌을 푼 뒤(APPLY_CONFLICT, 미해결 파일 없음)는 목록과 상관없이 붙은 뒤다. 폴더에 변경이 없으면 붙기 전이다. 파일 목록 해시가 같을 때
    HEAD가 뜰 때와 같으면 내용까지 패치와 견주고, 다르면(3way가 내용을 바꿀 수 있다) 붙이는 중 표지가 있어야 붙은 뒤다."""
    _, head, digest = parse_mark(mark)
    entries = status_entries(folder)
    names = [p for _, p in entries]
    if unmerged(entries):
        return PARK_CONFLICT, unmerged(entries)
    if applying == APPLY_CONFLICT:
        return PARK_AFTER, names
    if not names:
        return PARK_BEFORE, []
    with TempGit(folder) as g:
        same_head = g.head() == head
        base = head or g.git("now.index", "hash-object", "-t", "tree", os.devnull).strip()
        want = g.tree_from_patch(head, patch_path)
        in_patch = _tree_names(g, "now.index", base, want)
        if list_digest(names) == digest:
            if same_head:
                return (PARK_AFTER if g.now_tree() == want else PARK_MISMATCH), names
            return (PARK_AFTER if applying == APPLYING else PARK_MISMATCH), names
    return (PARK_PARTIAL if set(names) < in_patch else PARK_MISMATCH), names


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
