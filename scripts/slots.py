"""작업 칸(설계 8.3절). 서로 의존하지 않는 코드 task를 같은 흐름의 칸 폴더에서 나란히 돌리고 흐름 브랜치에 차례로 넣는다.

`작업 칸 수`(「이번 실행의 값」, 시작값 1)가 1이면 쓰이지 않는다. 절차는 references/main/slots.md다.

사용:
  python slots.py {실행 폴더} --count                     쓰는 칸 수. 값이 있어도 쓰지 못하면 그 이유를 함께 낸다
  python slots.py {실행 폴더} --set {n} "{원문}"          칸 수를 바꾼다. 코드 쓰는 task가 0일 때만이고 2 이상은 recon.md 「런타임: 폴더별」이 있어야 한다
  python slots.py {실행 폴더} --made {흐름} {n}           만든 칸 폴더를 flow.md `slots`에 적는다
  python slots.py {실행 폴더} {id} --open {n}             칸을 흐름 브랜치 끝에 떼어 꺼내고 `slot`, `slot_base`를 적는다(깨끗한 칸만)
  python slots.py {실행 폴더} {id} --pending {칸 커밋}    칸에서 커밋한 값을 `insert_pending`에 적는다
  python slots.py {실행 폴더} {id} --insert               흐름 브랜치에 넣는다. 끊겼으면 잇는다. 충돌하면 중단하고 종료 3이다
  python slots.py {실행 폴더} {id} --insert-failed {수정 id}  넣기 충돌이나 확인 실패를 고칠 수정 task를 적는다
  python slots.py {실행 폴더} {id} --checked              `flows\\{흐름}\\insert-checks\\{id}.md`를 읽어 넣은 뒤 확인을 닫는다
종료: 0 정상 / 2 사용법 / 3 거부(파일과 폴더는 그대로이거나 중단해 되돌렸다).
"""
import os
import re
import subprocess
import sys

import devflow_lib
import kinds

SLOT_COUNT = "작업 칸 수"
RUNTIME_MARK = re.compile(r"^[ \t*-]*런타임\s*:\s*폴더별[ \t]*(?:[(（][^)）\n]*[)）][ \t]*)?\r?$", re.M)   # 값 전체. 괄호에는 확인한 파일을 적는다
SYNC_ORIGIN = "받아오기"   # 받아오기 충돌을 고치는 task의 origin. 병합 중인 흐름 폴더에서 돈다
DEPS_LINE = re.compile(r"^[\s*-]*의존성 목록\s*:\s*(.+)$", re.M)
DEP_FILES = ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "requirements.txt", "poetry.lock", "uv.lock",
             "pyproject.toml", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "build.gradle", "build.gradle.kts", "pom.xml")
MIGRATION = re.compile(r"migrat|마이그레이션", re.I)
NO_VALUE = ("", "-", "없음", "(없음)")
NO_RUNTIME = "! 작업 칸 수 {}: recon.md에 「런타임: 폴더별」이 없어 1로 돈다"
INSERT_LEFT = "넣기 남음 {} (slots.py {{실행 폴더}} {} --insert. 끊겼으면 이어진다)"
CHECK_LEFT = "넣은 뒤 확인 남음 {} (run-judge가 끝나면 slots.py {{실행 폴더}} {} --checked)"
FIX_LEFT = "넣기 수정 기다림 {} {}"


class Reject(Exception):
    """거부. 명령행은 종료 3."""


def wanted_count(run_dir):
    """run.md 「이번 실행의 값」의 마지막 행. 없거나 못 읽으면 시작값이다."""
    path = os.path.join(run_dir, "run.md")
    values = devflow_lib.sections(devflow_lib.read_text(path)).get("이번 실행의 값", "") if os.path.isfile(path) else ""
    last = kinds.RUN_DEFAULTS[SLOT_COUNT]
    for line in values.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == SLOT_COUNT and cells[1].isdigit() and int(cells[1]) >= 1:
            last = int(cells[1])
    return last


def recon_text(run_dir):
    path = os.path.join(run_dir, "recon.md")
    return devflow_lib.read_text(path) if os.path.isfile(path) else ""


def slot_count(run_dir):
    """지금 쓰는 칸 수. 1.2.0부터 시작한 실행에서 recon.md가 폴더별 런타임을 확인했을 때만 2 이상이다."""
    wanted = wanted_count(run_dir)
    if wanted <= 1 or not RUNTIME_MARK.search(recon_text(run_dir)):
        return 1
    # 아직 아무 task도 시작하지 않은 실행은 새 실행이다. 첫 task만 칸 없이 돌면 뒤의 칸이 그 폴더를 옮긴다
    return wanted if devflow_lib.run_from_v120(run_dir) or not devflow_lib.started_tasks(run_dir) else 1


def count_problem(run_dir):
    wanted = wanted_count(run_dir)
    return NO_RUNTIME.format(wanted) if wanted > 1 and not RUNTIME_MARK.search(recon_text(run_dir)) else ""


def mark_line(run_dir):
    """사람에게 보일 표지 줄. 없으면 빈 글."""
    m = RUNTIME_MARK.search(recon_text(run_dir))
    return m.group(0).strip() if m else ""


def slot_of(t):
    return str(t.get("slot", "") or "").strip()


def folder_of(base, t):
    """task가 쓰는 코드 폴더: 칸이 있으면 `{흐름 폴더}-s{n}`, 없으면 흐름 폴더."""
    return "{}-s{}".format(base, slot_of(t)) if base and slot_of(t) else base


def _filled(t, key):
    return bool(str(t.get(key, "") or "").strip())


def holds_slot(t):
    """칸을 차지하는가: 도는 task, 넣기가 안 끝난 task, 커밋 전 변경을 칸에 남긴 승인대기와 보류."""
    if not slot_of(t) or (t.get("status") == "보류" and _filled(t, "insert_pending")):   # 보류여도 변경은 커밋에 있다
        return False
    if _filled(t, "insert_pending") or _filled(t, "insert_failed") or t.get("status") in kinds.BUSY_STATUSES:
        return True
    if _filled(t, "commit") or any(_filled(t, k) for k in ("parked", "repro_patch", "holds_nothing")) or devflow_lib.no_change(t):
        return False
    return t.get("status") in ("승인대기", "보류")


def slot_taken(tasks, t, n=None):
    """그 칸을 차지한 다른 task의 id. 넣기 수정은 원래 task의 칸을 이어받는다."""
    n = n or slot_of(t)
    return [o["id"] for o in tasks.values() if o["id"] != t["id"] and o.get("flow") == t.get("flow") and slot_of(o) == n and holds_slot(o)
            and str(o.get("insert_failed", "") or "").strip() != t["id"]]


def checking(tasks, flow, but=""):
    """넣은 뒤 확인을 기다리는 task의 id. 그동안 흐름 폴더의 HEAD를 옮기지 않는다. 실패해 수정을 기다리는 task는 뺀다."""
    return [o["id"] for o in tasks.values() if o.get("flow") == flow and o["id"] != but and _filled(o, "commit")
            and _filled(o, "insert_pending") and not _filled(o, "insert_failed")]


def _paths(t):
    return [p.replace("\\", "/").lstrip("./") for p in devflow_lib.touch_paths(t.get("_sections", {}).get("건드릴 파일", ""))]


def _stem(path):
    """패턴의 고정된 앞부분. `src/a/*.ts` → `src/a/`."""
    return re.split(r"[*?\[{]", path, maxsplit=1)[0]


def paths_overlap(a, b):
    """패턴끼리는 보수적으로 본다: 한쪽이 다른 쪽의 앞부분이면 겹침이다."""
    a, b = _stem(a), _stem(b)
    return a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/") or (a.endswith("/") and b.startswith(a)) \
        or (b.endswith("/") and a.startswith(b)) or a == "" or b == ""


def dep_files(run_dir):
    m = DEPS_LINE.search(recon_text(run_dir))
    return set(DEP_FILES) | ({x.strip().strip("`") for x in m.group(1).split(",")} if m else set())


def tasks_overlap(a, b, deps):
    """두 task의 「건드릴 파일」이 겹치는가. 비었거나 의존성 목록을 건드리면 겹치는 것으로 본다."""
    left, right = _paths(a), _paths(b)
    if not left or not right or any(os.path.basename(p) in deps for p in left + right):
        return True
    return any(paths_overlap(x, y) for x in left for y in right)


def convention_row(t):
    """규약 추가가 생길 수 있는 행: 「시그니처와 결정 번호」가 비지 않았거나 마이그레이션을 건드린다."""
    named = t.get("_sections", {}).get("시그니처와 결정 번호", "")
    filled = any(line.strip().lstrip("- ").strip() not in NO_VALUE for line in str(named).splitlines())
    return filled or any(MIGRATION.search(p) for p in _paths(t))


def assign(tasks, run_dir, flow, candidates):
    """같은 흐름의 시작 후보에 칸을 순서대로 배정하며 점유를 누적한다. {id: 칸 번호(int) 또는 못 띄우는 이유(str)}.
    고치는 task를 먼저 본다(references/main/loop.md 1절 2)."""
    count, deps = slot_count(run_dir), dep_files(run_dir)
    holding = [o for o in tasks.values() if o.get("flow") == flow and holds_slot(o)]
    busy = [o for o in holding if o.get("status") in kinds.BUSY_STATUSES]
    out = {}
    for t in sorted(candidates, key=lambda c: 0 if c.get("kind") == "fix" else 1):
        # 넣기 수정은 원래 task가 잡은 칸을 이어받는다. 그 task는 수정을 기다리므로 비키라고 할 수 없다
        others = [o for o in holding if str(o.get("insert_failed", "") or "").strip() != t["id"]]
        used = {str(slot_of(o) or o.get("_slot")) for o in others}
        free = next((n for n in range(1, count + 1) if str(n) not in used), None)
        crossing = [o["id"] for o in others if tasks_overlap(t, o, deps)]
        rule = [o["id"] for o in busy if convention_row(o)]
        if free is None:
            out[t["id"]] = "칸 없음"
        elif crossing:
            out[t["id"]] = "건드릴 파일 겹침: " + ", ".join(crossing)
        elif rule:
            out[t["id"]] = "규약 행 도는 중: " + ", ".join(rule)
        elif convention_row(t) and busy:
            out[t["id"]] = "규약 행은 다른 칸이 빌 때: " + ", ".join(o["id"] for o in busy)
        else:
            out[t["id"]] = free
            placed = dict(t, _slot=free)
            holding.append(placed)
            busy.append(placed)
    return out


def insert_notes(t):
    """재개와 `--ready`에 보일 넣기 상태. 없으면 빈 목록."""
    pending, failed = str(t.get("insert_pending", "") or "").strip(), str(t.get("insert_failed", "") or "").strip()
    if failed:
        return [FIX_LEFT.format(t["id"], failed)]
    if not pending:
        return []
    return [(CHECK_LEFT if _filled(t, "commit") else INSERT_LEFT).format(t["id"], t["id"])]


def flow_meta(run_dir, flow):
    path = os.path.join(run_dir, "flows", flow, "flow.md")
    if not flow or not os.path.isfile(path):
        raise Reject("flow.md를 찾지 못함: " + (flow or "흐름 없음"))
    return devflow_lib.parse_meta(devflow_lib.split_front_matter(devflow_lib.read_text(path))[0]), path


def git(folder, *args, check=True):
    proc = subprocess.run(["git", "-C", folder] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if check and proc.returncode != 0:
        raise Reject("git {} 실패({}): {}".format(args[0], folder, (proc.stderr or proc.stdout).strip()[:200]))
    return proc


def head_of(folder, rev):
    return git(folder, "rev-parse", rev).stdout.strip()


def flow_place(run_dir, t):
    """(흐름 폴더, 흐름 브랜치)."""
    meta, _ = flow_meta(run_dir, t.get("flow", ""))
    folder, branch = str(meta.get("dir", "") or "").strip(), str(meta.get("branch", "") or "").strip()
    if not folder or not os.path.isdir(folder) or not branch:
        raise Reject("흐름 폴더나 브랜치가 없음: flows\\{}\\flow.md".format(t.get("flow", "")))
    return folder, branch


def cmd_open(run_dir, t, doc, n):
    if slot_count(run_dir) < 2:
        raise Reject("칸을 쓰지 않는 실행이다(작업 칸 수 {})".format(slot_count(run_dir)))
    if not n.isdigit() or not 1 <= int(n) <= slot_count(run_dir):
        raise Reject("칸 번호는 1~{}".format(slot_count(run_dir)))
    taken = slot_taken(devflow_lib.load_tasks(run_dir), t, n)
    if taken:
        raise Reject("칸 {}을 {}가 차지함".format(n, ", ".join(taken)))
    base, branch = flow_place(run_dir, t)
    folder = "{}-s{}".format(base, n)
    if not os.path.isdir(folder):
        raise Reject("칸 폴더 없음: {} — 흐름 폴더와 같은 절차로 만들고 --made를 부른다".format(folder))
    dirty = git(folder, "status", "--porcelain").stdout.strip()
    if dirty:
        raise Reject("칸 폴더가 깨끗하지 않음: {}".format(dirty.splitlines()[0]))
    git(folder, "checkout", "-q", "--detach", branch)
    doc.set("slot", n)
    doc.set("slot_base", head_of(folder, "HEAD"))
    doc.save()
    print("{}: 칸 {} {} (시작 {})".format(t["id"], n, folder, doc.get("slot_base")[:12]))


def cmd_pending(run_dir, t, doc, sha):
    if not slot_of(t):
        raise Reject("칸이 없는 task다: commit=으로 적는다")
    if _filled(t, "commit") or _filled(t, "insert_failed"):
        raise Reject("이미 넣었거나 수정을 기다린다")
    base = flow_place(run_dir, t)[0]
    doc.set("insert_pending", head_of(folder_of(base, t), sha + "^{commit}"))
    doc.save()


def changed_overlap(run_dir, t, folder, sha):
    """넣는 커밋의 실제 파일이 칸을 차지한 다른 task의 「건드릴 파일」과 겹치면 그 id. 기다리지 않고 확인 범위를 넓히는 신호다."""
    files = [p for p in git(folder, "show", "--name-only", "--format=", sha).stdout.splitlines() if p.strip()]
    return [o["id"] for o in devflow_lib.load_tasks(run_dir).values()
            if o["id"] != t["id"] and o.get("flow") == t.get("flow") and holds_slot(o) and any(paths_overlap(f, p) for f in files for p in _paths(o))]


def picked_twin(folder, base, branch, sha):
    """같은 변경이 이미 들어갔으면 그 해시(끊긴 넣기). 작성 시각과 제목으로 찾는다. 없으면 빈 글."""
    mine = git(folder, "show", "-s", "--format=%at\t%s", sha).stdout.strip()
    for line in git(folder, "log", "--format=%H\t%at\t%s", "{}..{}".format(base, branch)).stdout.splitlines():
        head, _, rest = line.partition("\t")
        if rest == mine:
            return head
    return ""


def missing_files(run_dir, o, sha):
    """충돌로 넣지 못한 칸 커밋의 파일 가운데 수정 커밋에 없는 것. 내용까지는 보지 않는다. 이미 넣은 task(확인 실패)는 대조할 것이 없다."""
    pending = str(o.get("insert_pending", "") or "").strip()
    if not pending or not sha or _filled(o, "commit"):
        return []
    folder = flow_place(run_dir, o)[0]
    names = [set(git(folder, "show", "--name-only", "--format=", c).stdout.split("\n")) - {""} for c in (pending, sha)]
    return sorted(names[0] - names[1])


def waiting_on(run_dir, fix_id):
    return [o for o in devflow_lib.load_tasks(run_dir).values() if str(o.get("insert_failed", "") or "").strip() == fix_id]


def release(run_dir, fix_id, sha):
    """넣기까지 끝난 수정을 기다리던 task를 잇는다(원래 task의 commit을 덮지 않는다). 수정의 수정이면 사슬을 따라 올라간다."""
    for o in waiting_on(run_dir, fix_id):
        other = devflow_lib.Doc(o["_path"])
        lost = missing_files(run_dir, o, sha)
        if lost:
            line = "넣기 수정에 빠진 파일: {} (수정 {})".format(", ".join(lost), fix_id)
            other.append_line("넘길 이상 신호", "- " + line, before=["승인 기록"])
            print("! " + line)
        other.set("commit_via", fix_id)
        other.set("insert_failed", "")
        other.set("insert_pending", "")
        other.save()
        print("{}: commit_via {}".format(o["id"], fix_id))
        release(run_dir, o["id"], sha)


def fix_closed(run_dir, fix_id):
    """수정이 코드 없이(`no_change`) 또는 보류로 닫혔다. 기다리던 task의 표지를 지워 `--checked`나 `--insert`를 다시 부를 수 있게 한다."""
    for o in waiting_on(run_dir, fix_id):
        other = devflow_lib.Doc(o["_path"])
        other.set("insert_failed", "")
        other.save()
        devflow_lib.journal_append(run_dir, "메모", o["id"], "넣기 수정 {}가 코드 없이 닫힘".format(fix_id))
        print("{}: 넣기 수정 {}가 코드 없이 닫힘. 다시 --{}".format(o["id"], fix_id, "checked" if _filled(o, "commit") else "insert"))


def finish(run_dir, t, doc):
    """넣기가 끝났다. 자기 표지를 지우고 이 task를 기다리던 task를 잇는다."""
    doc.set("insert_pending", "")
    doc.set("insert_failed", "")
    doc.save()
    release(run_dir, t["id"], str(doc.get("commit") or "").strip())


def cmd_insert(run_dir, t, doc):
    sha = str(t.get("insert_pending", "") or "").strip()
    if not sha:
        raise Reject("넣을 커밋이 없음: --pending 먼저")
    if _filled(t, "commit"):
        print("이미 넣음 {}: 넣은 뒤 확인 --checked".format(t.get("commit")))
        return 0
    running = checking(devflow_lib.load_tasks(run_dir), t.get("flow"), t["id"])
    if running:
        raise Reject("넣은 뒤 확인을 기다림: {} — 도는 동안 흐름 폴더의 HEAD를 옮기지 않는다. 끝난 뒤 다시 부른다".format(", ".join(running)))
    folder, branch = flow_place(run_dir, t)
    if git(folder, "rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD", check=False).returncode == 0:
        git(folder, "cherry-pick", "--abort")   # 앞서 끊긴 넣기. 이 호출이 다시 넣는다
    if git(folder, "status", "--porcelain").stdout.strip():
        raise Reject("흐름 폴더가 깨끗하지 않음: " + folder)
    if head_of(folder, "HEAD") != head_of(folder, branch):
        raise Reject("흐름 폴더가 {}를 꺼내고 있지 않음".format(branch))
    base = str(t.get("slot_base", "") or "").strip()
    overlap = changed_overlap(run_dir, t, folder, sha)
    if git(folder, "merge-base", "--is-ancestor", sha, branch, check=False).returncode == 0:
        return _inserted(run_dir, t, doc, sha, picked=False, overlap=overlap)
    if "- " + sha in git(folder, "cherry", branch, sha, sha + "^").stdout:
        twin = picked_twin(folder, base, branch, sha)
        if twin:
            return _inserted(run_dir, t, doc, twin, picked=True, overlap=overlap)
    if head_of(folder, branch) == base:
        git(folder, "merge", "-q", "--ff-only", sha)
        return _inserted(run_dir, t, doc, sha, picked=False, overlap=overlap)
    picked = git(folder, "cherry-pick", sha, check=False)
    if picked.returncode != 0:
        git(folder, "cherry-pick", "--abort", check=False)
        devflow_lib.journal_append(run_dir, "넣기 충돌", t["id"], sha[:12])
        print("넣기 충돌 {}: 중단하고 되돌렸다. 수정 task를 만들고 --insert-failed {{수정 id}}(references/main/slots.md)".format(sha[:12]))
        return 3
    return _inserted(run_dir, t, doc, head_of(folder, "HEAD"), picked=True, overlap=overlap)


def _inserted(run_dir, t, doc, sha, picked, overlap):
    doc.set("commit", sha)
    devflow_lib.journal_append(run_dir, "넣음", t["id"], "{} {}".format(sha[:12], "cherry-pick" if picked else "앞감기"))
    if not picked:
        finish(run_dir, t, doc)
        print("넣음(앞감기) {}".format(sha))
        return 0
    doc.save()
    print("넣음(cherry-pick) {}. 넣은 뒤 확인: run-judge를 흐름 폴더에서 띄운다(flows\\{}\\insert-checks\\{}.md, 범위 {}..끝){}".format(
        sha, t.get("flow", ""), t["id"], str(t.get("slot_base", ""))[:12], " 겹침으로 넓힘: " + ", ".join(overlap) if overlap else ""))
    return 0


def cmd_checked(run_dir, t, doc):
    if not _filled(t, "insert_pending") or not _filled(t, "commit"):
        raise Reject("넣은 뒤 확인을 기다리는 task가 아님")
    path = os.path.join(run_dir, "flows", t.get("flow", ""), "insert-checks", t["id"] + ".md")
    if not os.path.isfile(path):
        raise Reject("넣은 뒤 확인 파일 없음: " + path)
    failed = devflow_lib.sections(devflow_lib.read_text(path), level=2).get("통과 못 한 기준")
    if failed is None:
        raise Reject("넣은 뒤 확인 파일에 「통과 못 한 기준」 절이 없음: " + path)
    if devflow_lib.item_count(failed):
        devflow_lib.journal_append(run_dir, "넣은 뒤 확인 실패", t["id"], "{}개".format(devflow_lib.item_count(failed)))
        print("넣은 뒤 확인 실패: 수정 task를 만들고 --insert-failed {수정 id}. 다음 승인 화면의 이상 신호로 적는다")
        return 3
    finish(run_dir, t, doc)
    print("넣은 뒤 확인 통과: {}".format(t["id"]))
    return 0


def cmd_insert_failed(run_dir, t, doc, fix):
    tasks = devflow_lib.load_tasks(run_dir)
    if fix not in tasks or tasks[fix].get("kind") != "fix":
        raise Reject("수정 task가 아님: " + fix)
    if not _filled(t, "insert_pending"):
        raise Reject("넣기를 기다리는 task가 아님")
    doc.set("insert_failed", fix)
    doc.save()


def cmd_set(run_dir, value, said):
    if not value.isdigit() or int(value) < 1:
        raise Reject("칸 수는 1 이상의 정수")
    if not said.strip():
        raise Reject("칸 수는 사람 원문이 있어야 바꾼다")
    if int(value) > 1 and not RUNTIME_MARK.search(recon_text(run_dir)):
        raise Reject("칸 2 이상은 recon.md에 「런타임: 폴더별」이 확인된 프로젝트에서만 고른다")
    tasks = devflow_lib.load_tasks(run_dir).values()
    busy = [o["id"] for o in tasks if o.get("kind") in kinds.CODE_DIR_KINDS and o.get("status") in kinds.BUSY_STATUSES]
    busy += [o["id"] for o in tasks if holds_slot(o) and o["id"] not in busy]
    if busy:
        raise Reject("코드 쓰는 task가 0일 때만 바꾼다: " + ", ".join(busy))
    doc = devflow_lib.Doc(os.path.join(run_dir, "run.md"))
    doc.append_line("이번 실행의 값", "| {} | {} |".format(SLOT_COUNT, value))
    doc.save()
    devflow_lib.journal_append(run_dir, "메모", "-", '작업 칸 수 {}. 원문: "{}"'.format(value, " ".join(said.split())))
    if int(value) > 1:
        print("표지: " + mark_line(run_dir))


def cmd_made(run_dir, flow, n):
    meta, path = flow_meta(run_dir, flow)
    folder = "{}-s{}".format(str(meta.get("dir", "") or "").strip(), n)
    if not os.path.isdir(folder):
        raise Reject("칸 폴더 없음: " + folder)
    doc = devflow_lib.Doc(path)
    have = meta.get("slots", [])
    have = have if isinstance(have, list) else devflow_lib.parse_value("x", "[" + str(have) + "]")
    if folder not in have:
        doc.set("slots", list(have) + [folder])
        doc.save()
    devflow_lib.journal_append(run_dir, "폴더 생성", "-", "칸 {}".format(folder))


def main(argv):
    devflow_lib.utf8_stdout()
    args = argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    run_dir, rest = args[0], args[1:]
    try:
        if rest == ["--count"]:
            print(slot_count(run_dir))
            if wanted_count(run_dir) > 1 and mark_line(run_dir):
                print("표지: " + mark_line(run_dir))
            if count_problem(run_dir):
                print(count_problem(run_dir))
            return 0
        if rest[0] == "--set" and len(rest) == 3:
            cmd_set(run_dir, rest[1], rest[2])
            return 0
        if rest[0] == "--made" and len(rest) == 3:
            cmd_made(run_dir, rest[1], rest[2])
            return 0
        tasks = devflow_lib.load_tasks(run_dir)
        if rest[0] not in tasks or len(rest) < 2:
            print(__doc__ if rest[0].startswith("--") else "task를 찾지 못함: " + rest[0])
            return 2
        t, doc, flag = tasks[rest[0]], devflow_lib.Doc(tasks[rest[0]]["_path"]), rest[1]
        value = rest[2] if len(rest) > 2 else ""
        if flag == "--open" and value:
            cmd_open(run_dir, t, doc, value)
        elif flag == "--pending" and value:
            cmd_pending(run_dir, t, doc, value)
        elif flag == "--insert":
            return cmd_insert(run_dir, t, doc)
        elif flag == "--insert-failed" and value:
            cmd_insert_failed(run_dir, t, doc, value)
        elif flag == "--checked":
            return cmd_checked(run_dir, t, doc)
        else:
            print(__doc__)
            return 2
        return 0
    except (Reject, devflow_lib.Reject) as e:
        print("거부: {}".format(e))
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
