r"""밖으로 나가는 명령(합치기, 개발 기준 브랜치에 넣기, push, 배포)을 승인된 줄만 돌린다(SKILL.md 7절).

메인이 화면의 명령을 다시 타이핑하지 않고 번호만 고른다. 기록(exec.md), `external_progress`, 로그, 병합 판정은
이 스크립트가 쓴다. 승인 뒤 명령을 고쳐야 하면 다시 승인받고 --refreeze 한다.

사용:
  python exec.py {실행 폴더} {id} --freeze --point P [--refreeze]
  python exec.py {실행 폴더} {id} --step P:n [--cwd 폴더]
  python exec.py {실행 폴더} {id} --user-result P:n "종료 코드 0, 출력 …"
  python exec.py {실행 폴더} {id} --verify
  python exec.py {실행 폴더} {id} --show

지점 P와 원천(「정해 주실 것」 안 ```cmd 울타리의 줄, 한 줄이 명령 하나. formats.md 4절)
  실행승인  그 task result.md. 배포 실행이면 부모 배포 계획의 result.md
  결과승인  그 task result.md(충돌을 고친 합치기의 병합 끝내기 명령. 실행승인에 얼린 줄은 뺀다)
  넣기승인  그 task result.md(배포 실행의 문서 넣기)
  되돌림    부모 배포 계획 result.md에서 제목에 「되돌리기」가 든 절들의 울타리
  얼린 파일: tasks\{id}\approved-cmds-{P}.md(줄 번호와 해시). 손으로 고치면 해시가 어긋나 --step이 거부한다.
  얼림은 그 승인의 기록(「승인 기록」에서 승인 요청 뒤의 답 줄. 배포 실행의 실행승인·되돌림은 완료된 부모 계획의 답)이
  있어야 한다. 다시 얼림(--refreeze)은 앞서 얼린 뒤의 새 답이 있어야 한다.
  task_set.py가 승인 기록(--record)으로 묻는 단계를 떠날 때, 배포 실행이 시작될 때 이것을 함께 부른다.

줄 앞 표시
  [사용자 실행]  돌리지 않는다. 사용자가 실행하고 알려 준 결과를 --user-result로 적는다.
  [유지 뒤]      배포 실행의 deploy_outcome이 유지일 때만 돈다(아니면 건너뜀으로 적는다).

--step 전에 보는 것
  - 상태: 합치기·마무리·배포 실행은 `진행`이고 stage가 묻는 단계·`끝`이 아님. 그 밖의 kind는 승인으로 `완료`된 뒤.
  - 한 번만: 얼린 뒤 같은 줄을 이미 돌렸으면(사용자 실행·건너뜀 포함) 거부. 다시 돌리려면 새 승인과 --refreeze.
  - 기대 브랜치(07 §A4, 원천에서 읽음): 합치기는 flow.md `branch` → run.md `integration_branch`, 마무리는
    `integration_branch`(흐름 하나면 그 흐름의 `branch`) → `base_branch`, 배포 실행 넣기는 배포 폴더의 브랜치 →
    `base_branch`. 병합 줄은 명령이 도는 폴더가 받는 브랜치를 꺼내 두었고 줄이 넣는 브랜치를 넣을 때만 돈다.
  - 작업 트리: 명령이 도는 폴더(기본: 합치기 = integration_dir, 마무리·넣기 = project(원래 폴더), 배포 실행 = 그
    흐름의 dir, 흐름 하나면 그 흐름의 dir, 그 밖 = 원래 폴더)의 `git status --porcelain`이 비어야 한다. 병합 줄은
    넣는 브랜치를 꺼낸 폴더(git worktree)도 비어야 한다(편집이 커밋되기 전에 넣지 않게).
    예외: `git add …`·`git commit …` 단독 줄(남은 변경을 커밋하는 줄), 원래 폴더의 병합 줄(병합이 바꾸는 파일과
    커밋 안 된 변경이 겹치지 않으면 됨. references/kinds/wrap-up/main-order.md 「뒤 절반」 2)과 `update-ref`·`push` 단독 줄.
병합 줄(`git … merge …`)은 앞뒤 해시로 병합 부모·앞감기를 판정해 exec.md에 적고, 병합이 끝나면
합치기는 머리 파일 `commit`, 마무리는 `exported_commit`에 새 끝을 적는다.

--verify  얼린 지점마다: 줄 수 = 돈 줄 수(사용자 실행은 종료 코드 0을 알려 준 것), 종료 코드 0, 병합 판정 통과.
          충돌로 멈춘 병합 줄은 결과승인 지점이 끝까지 돌고 병합(충돌 해결) 판정이 통과하면 받는다.
          돌지 않은 병합 줄은 넣는 브랜치의 끝이 받는 브랜치에 이미 들어 있으면 받는다(사용자가 직접 넣은 경우).
          되돌림 지점은 deploy_outcome이 되돌림일 때만, [유지 뒤] 줄은 유지일 때만 요구한다.

종료 코드: 0 / 2 사용법 / 3 거부·검증 실패
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

import devflow_lib
import kinds

USER = "[사용자 실행]"
AFTER_KEEP = "[유지 뒤]"
MERGE_LINE = re.compile(r"\bgit\b.*\smerge(\s|$)")
SEPARATORS = re.compile(r"[;&|<>`$]|\n")
GIT_PREFIX = r"^git\s+(?:-C\s+(?:\"[^\"]+\"|'[^']+'|\S+)\s+)?"
CONSUME_LINE = re.compile(GIT_PREFIX + r"(add|commit)(\s|$)")
NO_TREE_LINE = re.compile(GIT_PREFIX + r"(update-ref|push)(\s|$)")
TIME_FMT = "%Y-%m-%d %H:%M:%S"


class Reject(Exception):
    pass


def now():
    return datetime.now().strftime(TIME_FMT)


def ptime(value):
    value = str(value or "").strip()
    for fmt, n in ((TIME_FMT, 19), ("%Y-%m-%d %H:%M", 16)):
        try:
            return datetime.strptime(value[:n], fmt)
        except ValueError:
            pass
    return None


def load(run_dir, tid):
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        raise Reject("task를 찾지 못함: " + tid)
    return tasks, tasks[tid]


def single(line, pattern):
    """줄이 셸 구분자 없이 그 git 명령 하나뿐인가."""
    return bool(pattern.match(line)) and not SEPARATORS.search(line)


# ---------------------------------------------------------------- 승인과 원천

def approval_time(t):
    """「승인 기록」에서 승인 줄(devflow_lib.approval_line: 지점이나 결정이 승인) 가운데 가장 늦은 시각.
    승인 요청 전의 답은 세지 않는다. 보류·거절·되돌림·되물음 답으로는 얼리지 않는다."""
    best = None
    for line in devflow_lib.record_lines(t):
        f = devflow_lib.record_fields(line)
        if not devflow_lib.approval_line(line):
            continue
        when = ptime(f[0])
        if when and (best is None or when > best):
            best = when
    req = ptime(t.get("approval_requested"))
    if best and req and best < req:
        return None
    return best


def approved_at(tasks, t, point):
    if t.get("kind") == "deploy-exec" and point in ("실행승인", "되돌림"):
        parent = tasks.get(t.get("parent", ""))
        if parent is None or parent.get("status") != kinds.DONE:
            return None
        return approval_time(parent)
    return approval_time(t)


def heading_section(text, word):
    """제목(#…)에 word가 든 절들의 글(각각 같거나 높은 수준의 다음 제목까지)을 이어 붙인 것."""
    lines = (text or "").splitlines()
    out = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m and word in m.group(2):
            level = len(m.group(1))
            for nxt in lines[i + 1:]:
                m2 = re.match(r"^(#+)\s", nxt)
                if m2 and len(m2.group(1)) <= level:
                    break
                out.append(nxt)
    return "\n".join(out)


def source(run_dir, tasks, t, point):
    """(원천 설명, 명령 줄 목록)."""
    kind = t.get("kind", "")
    if point == "되돌림" or (point == "실행승인" and kind == "deploy-exec"):
        parent = tasks.get(t.get("parent", ""))
        if parent is None:
            raise Reject("부모 배포 계획을 찾지 못함")
        p = os.path.join(parent["_dir"], "result.md")
        if not os.path.isfile(p):
            raise Reject("부모의 result.md가 없음: " + p)
        if point == "되돌림":
            return "{} 「되돌리기」".format(p), devflow_lib.cmd_lines(heading_section(devflow_lib.read_text(p), "되돌리기"))
        return "{} 「정해 주실 것」".format(p), devflow_lib.cmd_lines(devflow_lib.decide_cell(parent["_dir"]))
    p = os.path.join(t["_dir"], "result.md")
    return "{} 「정해 주실 것」".format(p), devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"]))


def frozen_path(t, point):
    return os.path.join(t["_dir"], "approved-cmds-{}.md".format(point))


def digest(lines):
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def read_frozen(t, point):
    """얼린 줄 목록. 해시가 어긋나면 Reject."""
    p = frozen_path(t, point)
    if not os.path.isfile(p):
        return None
    text = devflow_lib.read_text(p)
    lines = [m.group(2) for m in re.finditer(r"^(\d+)\. (.*)$", text, flags=re.M)]
    m = re.search(r"^해시: (\w+)", text, flags=re.M)
    if not m or m.group(1) != digest(lines):
        raise Reject("{}의 해시가 맞지 않음(손으로 고침). 다시 승인받고 --refreeze".format(os.path.basename(p)))
    return lines


def frozen_time(t, point):
    p = frozen_path(t, point)
    if not os.path.isfile(p):
        return None
    m = re.search(r"^얼린 시각: (.+)$", devflow_lib.read_text(p), flags=re.M)
    return ptime(m.group(1)) if m else None


def freeze(run_dir, tid, point, refreeze=False):
    """얼림. (종료 코드, 메시지)."""
    if point not in kinds.EXEC_POINTS:
        return 2, "지점은 " + "/".join(kinds.EXEC_POINTS)
    try:
        tasks, t = load(run_dir, tid)
        at = approved_at(tasks, t, point)
        if at is None:
            return 3, ("얼릴 수 없음: {} 지점의 승인 기록이 없다. 승인 요청 뒤의 답 줄에서 지점 칸이나 결정 칸이 `승인`이어야 한다"
                       "(보류·거절·되돌림·되물음·알림은 세지 않음{}). 고치는 법: 사람이 실행을 승인했으면 "
                       "`task_set.py {{실행 폴더}} {} --record \"승인|{{결정}}|{{원문}}\"`으로 다시 적은 뒤 "
                       "`exec.py {{실행 폴더}} {} --freeze --point {}`(SKILL.md 3절 「답의 처리」)").format(
                point, ", 배포 실행은 부모 계획의 답" if t.get("kind") == "deploy-exec" and point in ("실행승인", "되돌림") else "",
                t.get("parent", tid) if t.get("kind") == "deploy-exec" and point in ("실행승인", "되돌림") else tid, tid, point)
        where, lines = source(run_dir, tasks, t, point)
        if point == "결과승인" and os.path.isfile(frozen_path(t, "실행승인")):
            done = read_frozen(t, "실행승인") or []
            lines = [x for x in lines if x not in done]   # 같은 칸에 남은 실행승인 줄(이미 돈 병합)은 빼고 끝내기 명령만
        if not lines:
            return 3, "얼릴 명령 없음: {}에 ```cmd 울타리가 없다".format(where)
        p = frozen_path(t, point)
        if os.path.isfile(p):
            old = read_frozen(t, point)
            if old == lines and not refreeze:
                return 0, "이미 얼림(같음): " + p
            if not refreeze:
                return 3, "이미 얼린 명령과 다름: 다시 승인받았으면 --refreeze ({})".format(p)
            old_at = frozen_time(t, point)
            if old_at and at <= old_at:
                return 3, ("다시 얼릴 수 없음: 앞서 얼린 {} 뒤의 새 승인 기록이 없다. 바뀐 명령을 다시 승인받아 "
                           "`task_set.py {{실행 폴더}} {} --record \"승인|{{결정}}|{{원문}}\"`으로 적은 뒤 --refreeze").format(
                    old_at.strftime(TIME_FMT), tid)
            n = 1
            while os.path.exists(p.replace(".md", ".r{}.md".format(n))):
                n += 1
            os.replace(p, p.replace(".md", ".r{}.md".format(n)))
        body = ["# 승인된 명령 — {} {}".format(tid, point), "원천: " + where, "승인 기록 시각: " + at.strftime(TIME_FMT),
                "얼린 시각: " + now(), "해시: " + digest(lines), ""] + ["{}. {}".format(i, x) for i, x in enumerate(lines, 1)]
        devflow_lib.write_text(p, "\n".join(body) + "\n")
        return 0, "얼림 {}줄: {}".format(len(lines), p)
    except Reject as e:
        return 3, str(e)


# ---------------------------------------------------------------- 폴더와 브랜치

def git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
        return out.returncode, out.stdout.rstrip()
    except OSError as e:
        return 1, str(e)


def rev(cwd, ref):
    rc, out = git(cwd, "rev-parse", "--verify", "-q", ref)
    return out if rc == 0 and out else ""


def head_branch(cwd):
    rc, out = git(cwd, "symbolic-ref", "--short", "-q", "HEAD")
    return out.strip() if rc == 0 else ""


def meta_value(meta, key):
    v = str(meta.get(key, "") or "").strip()
    return "" if v.startswith("(") else v


def flows_of(run_dir):
    import board
    return board.load_flows(run_dir)


def default_cwd(run_dir, tasks, t, point):
    meta = devflow_lib.run_meta(run_dir)
    project = meta_value(meta, "project")
    kind = t.get("kind", "")
    if kind == "merge":
        return meta_value(meta, "integration_dir") or project
    if kind == "deploy-exec" and point in ("실행승인", "되돌림"):
        import board
        flows = flows_of(run_dir)
        for ref in (t.get("flow", ""), tasks.get(t.get("parent", ""), {}).get("flow", "")):
            d = str(flows.get(ref, {}).get("dir", "") or "").strip() if ref else ""
            if d:
                return d
        if meta_value(meta, "integration_dir"):
            return meta_value(meta, "integration_dir")
        dirs = [str(f.get("dir", "") or "").strip() for _, f in board.flow_items(flows) if str(f.get("dir", "") or "").strip()]
        return dirs[0] if len(dirs) == 1 else project   # 흐름 하나인 실행은 그 흐름 폴더(원래 폴더는 쓰지 않는다)
    return project


def expected(run_dir, tasks, t, point):
    """(넣는 브랜치, 받는 브랜치). 원천에서 읽는다(07 §A4). 정할 수 없으면 빈 문자열."""
    import board
    meta = devflow_lib.run_meta(run_dir)
    ib, base = meta_value(meta, "integration_branch"), meta_value(meta, "base_branch")
    flows = flows_of(run_dir)
    kind = t.get("kind", "")
    if kind == "merge":
        return str(flows.get(t.get("flow", ""), {}).get("branch", "") or "").strip(), ib
    if kind == "wrap-up":
        if ib:
            return ib, base
        feats = [str(f.get("branch", "") or "").strip() for _, f in board.flow_items(flows)
                 if f.get("role") == "feature" and str(f.get("branch", "") or "").strip()]
        return (feats[0] if len(feats) == 1 else ""), base
    if kind == "deploy-exec" and point == "넣기승인":
        return head_branch(default_cwd(run_dir, tasks, t, "실행승인")), base
    return "", ""


def same_dir(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def merge_source(run_dir, line):
    """병합 줄이 넣는 브랜치: 흐름·통합 브랜치 이름 가운데 줄에 든 가장 긴 것, 없으면 줄의 마지막 낱말."""
    import board
    names = [str(f.get("branch", "") or "").strip() for _, f in board.flow_items(flows_of(run_dir))]
    names.append(meta_value(devflow_lib.run_meta(run_dir), "integration_branch"))
    hit = sorted([n for n in names if n and re.search(r"(?<![\w/.-])" + re.escape(n) + r"(?![\w/.-])", line)],
                 key=len, reverse=True)
    if hit:
        return hit[0]
    words = [w.strip("\"'") for w in line.split() if not w.startswith("-")]
    return words[-1] if words else ""


def worktree_of(cwd, branch):
    """branch를 꺼낸 git worktree의 경로(없으면 "")."""
    rc, out = git(cwd, "worktree", "list", "--porcelain")
    if rc != 0:
        return ""
    path = ""
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line[9:].strip()
        elif line.strip() == "branch refs/heads/" + branch:
            return path
    return ""


def dirty_files(cwd):
    rc, status = git(cwd, "status", "--porcelain")
    if rc != 0:
        return None
    return [l[3:].strip().strip('"') for l in status.splitlines() if l.strip()]


def pre_check(run_dir, tasks, t, point, cwd, line):
    """실행 전 확인. (넣는 브랜치, 받는 브랜치, 알림 글)을 돌려주고, 거부면 Reject."""
    if not os.path.isdir(cwd):
        raise Reject("명령을 돌릴 폴더가 없음: " + cwd)
    is_merge = bool(MERGE_LINE.search(line))
    merging = bool(rev(cwd, "MERGE_HEAD"))
    src, tgt = expected(run_dir, tasks, t, point)
    if is_merge or (merging and single(line, CONSUME_LINE)):
        if tgt and head_branch(cwd) != tgt:
            raise Reject("받는 브랜치가 맞지 않음: {}는 {}를 꺼내 두었다(기대 {})".format(cwd, head_branch(cwd) or "(분리된 HEAD)", tgt))
    if is_merge:
        found = merge_source(run_dir, line)
        if src and found != src:
            raise Reject("넣는 브랜치가 맞지 않음: 줄은 {}를 넣는다(기대 {}, 원천 flow.md·run.md)".format(found, src))
        src = src or found
        other = worktree_of(cwd, src) if src else ""
        if other and not same_dir(other, cwd):
            d = dirty_files(other)
            if d:
                raise Reject("넣는 브랜치 {}를 꺼낸 폴더({})에 커밋 안 된 변경: {} — 편집을 커밋한 뒤 넣는다".format(
                    src, other, ", ".join(d[:5])))
    if single(line, CONSUME_LINE):
        return src, tgt, ""
    dirty = dirty_files(cwd)
    if dirty is None:
        return src, tgt, "(git 저장소 아님: 작업 트리 확인 건너뜀)"
    if not dirty:
        return src, tgt, ""
    project = meta_value(devflow_lib.run_meta(run_dir), "project")
    if same_dir(cwd, project):
        if is_merge:
            rc, names = git(cwd, "diff", "--name-only", "HEAD..." + src)
            if rc != 0:
                raise Reject("원래 폴더에 커밋 안 된 변경 {}개가 있고 병합이 바꾸는 파일을 못 셈({})".format(len(dirty), src))
            both = sorted(set(dirty) & set(names.splitlines()))
            if both:
                raise Reject("원래 폴더의 커밋 안 된 변경이 병합과 겹침: " + ", ".join(both[:5]))
            return src, tgt, "(원래 폴더의 커밋 안 된 변경 {}개는 이 병합과 겹치지 않음)".format(len(dirty))
        if single(line, NO_TREE_LINE):
            return src, tgt, "(원래 폴더의 커밋 안 된 변경 {}개, 이 줄은 작업 트리를 쓰지 않음)".format(len(dirty))
    raise Reject("작업 트리가 깨끗하지 않음({}): {} — 편집이 다 들어갔는지 보고 커밋한 뒤 돌린다".format(cwd, ", ".join(dirty[:5])))


# ---------------------------------------------------------------- 실행

def append_exec(t, line):
    p = os.path.join(t["_dir"], "exec.md")
    eol = "\n"
    if os.path.isfile(p):
        with open(p, "rb") as f:
            eol = "\r\n" if b"\r\n" in f.read() else "\n"
    with open(p, "a", encoding="utf-8", newline="") as f:
        f.write(line + eol)


def set_head(t, **kv):
    doc = devflow_lib.Doc(t["_path"])
    for k, v in kv.items():
        doc.set(k, v)
    doc.save()


def outcome(t):
    return str(t.get("deploy_outcome", "") or "").strip()


def step_allowed(t, point, label):
    """상태와 한 번만(07 §A4: 승인 한 번은 그 실행 한 번)."""
    kind, st = t.get("kind", ""), t.get("status", "")
    if kind in kinds.STAGE_KINDS:
        stage = devflow_lib.stage_of(t)
        if st != "진행" or stage in kinds.ASK_STAGES or stage == "끝":
            raise Reject("실행 단계가 아님(상태 {}, stage {}): 승인 기록과 함께 진행·실행 단계로 바꾼 뒤 돌린다".format(st, stage or "-"))
    elif st != kinds.DONE:
        raise Reject("승인으로 완료된 뒤에만 돌린다(상태 {})".format(st))
    since = frozen_time(t, point)
    for e in exec_lines(t):
        if e["label"] == label and (since is None or (e["time"] and e["time"] >= since)):
            raise Reject("{}는 얼린 뒤 이미 돎({}) — 다시 돌리려면 새 승인과 --refreeze".format(label, e["time_s"]))


def step(run_dir, tid, point, n, cwd=None):
    tasks, t = load(run_dir, tid)
    lines = read_frozen(t, point)
    if lines is None:
        raise Reject("{} 지점을 얼리지 않았음(--freeze --point {})".format(point, point))
    if n < 1 or n > len(lines):
        raise Reject("{} 지점은 1~{}줄".format(point, len(lines)))
    line = lines[n - 1]
    label = "{}:{}".format(point, n)
    step_allowed(t, point, label)
    if line.startswith(USER):
        print("사용자 실행 줄: 그대로 보여 주고 사용자가 실행한 뒤 --user-result {} \"…\"로 적는다".format(label))
        print(line[len(USER):].strip())
        return 0
    cmd = line
    if cmd.startswith(AFTER_KEEP):
        cmd = cmd[len(AFTER_KEEP):].strip()
        if outcome(t) != "유지":
            append_exec(t, "- {} | {} | 건너뜀: deploy_outcome {} | 지점 {}".format(now(), cmd, outcome(t) or "(없음)", label))
            print("건너뜀: [유지 뒤] 줄인데 deploy_outcome이 유지가 아님")
            return 0
    cwd = cwd or default_cwd(run_dir, tasks, t, point)
    src, tgt, note = pre_check(run_dir, tasks, t, point, cwd, cmd)
    if note:
        print(note)
    is_merge = bool(MERGE_LINE.search(cmd))
    merging = bool(rev(cwd, "MERGE_HEAD"))
    before = rev(cwd, "HEAD")
    src_tip = rev(cwd, src) if (is_merge and src) else ""
    if merging:
        src_tip = rev(cwd, "MERGE_HEAD")
    set_head(t, external_progress="{} {}/{} 실행 중".format(point, n, len(lines)))
    logs = os.path.join(t["_dir"], "logs")
    os.makedirs(logs, exist_ok=True)
    log = os.path.join(logs, "exec-{}-{}.log".format(point, n))
    shell = shutil.which("bash")
    argv = [shell, "-c", cmd] if shell else cmd
    with open(log, "wb") as f:
        rc = subprocess.run(argv, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, shell=not shell).returncode
    append_exec(t, "- {} | {} | 종료 코드 {} | 로그 {} | 지점 {} | 폴더 {}".format(now(), cmd, rc, log, label, cwd))
    judged = ""
    after = rev(cwd, "HEAD")
    if is_merge or (merging and CONSUME_LINE.match(cmd)):
        parents = git(cwd, "rev-list", "--parents", "-n", "1", "HEAD")[1].split()[1:]
        if rc != 0 and rev(cwd, "MERGE_HEAD"):
            judged = "충돌"
        elif rc != 0:
            judged = "실패"
        elif merging:
            judged = "병합(충돌 해결)" if parents == [before, src_tip] else "불일치"
        elif after == src_tip and after != before:
            judged = "앞감기"
        elif parents == [before, src_tip]:
            judged = "병합"
        elif after == before and src_tip and git(cwd, "merge-base", "--is-ancestor", src_tip, before)[0] == 0:
            judged = "이미 들어 있음"
        else:
            judged = "불일치"
        append_exec(t, "- {} | 브랜치 판정 | {} | {} | 앞 {} 뒤 {} 넣은 {}@{} 받은 {}".format(
            now(), label, judged, before[:12], after[:12], src or "MERGE_HEAD", src_tip[:12], tgt or head_branch(cwd)))
        if judged in ("병합", "앞감기", "병합(충돌 해결)", "이미 들어 있음"):
            if t.get("kind") == "merge":
                set_head(t, commit=after[:12])
            elif t.get("kind") == "wrap-up":
                set_head(t, exported_commit=after[:12])
    done = rc == 0 and n == len(lines)
    set_head(t, external_progress="" if done else "{} {}/{} 끝 종료 코드 {}".format(point, n, len(lines), rc))
    with open(log, "rb") as f:
        tail = f.read().decode("utf-8", errors="replace").splitlines()[-20:]
    print("\n".join(tail))
    print("{} 종료 코드 {}{} (로그 {})".format(label, rc, ", 브랜치 판정 " + judged if judged else "", log))
    return 0 if rc == 0 else 3


def user_result(run_dir, tid, point, n, text):
    tasks, t = load(run_dir, tid)
    lines = read_frozen(t, point)
    if lines is None or not 1 <= n <= len(lines):
        raise Reject("얼린 줄이 없음: {}:{}".format(point, n))
    if not lines[n - 1].startswith(USER):
        raise Reject("[사용자 실행] 줄이 아님: " + lines[n - 1])
    label = "{}:{}".format(point, n)
    step_allowed(t, point, label)
    append_exec(t, "- {} | {} | 사용자 실행: {} | 지점 {}".format(now(), lines[n - 1][len(USER):].strip(),
                                                             text.replace("|", "/"), label))
    return 0


# ---------------------------------------------------------------- 검증

def exec_lines(t):
    """exec.md의 지점 줄 [{label, time, time_s, rc, user, skip}]과 브랜치 판정은 judged_lines."""
    p = os.path.join(t["_dir"], "exec.md")
    out = []
    if not os.path.isfile(p):
        return out
    for line in devflow_lib.read_text(p).splitlines():
        f = [c.strip() for c in line[2:].split("|")] if line.startswith("- ") else []
        if len(f) >= 4 and f[1] == "브랜치 판정":
            continue
        label = next((c[3:].strip() for c in f if c.startswith("지점 ")), None)
        if not label:
            continue
        rc = next((c for c in f if c.startswith("종료 코드 ")), "")
        out.append({"label": label, "time": ptime(f[0]), "time_s": f[0], "rc": rc[6:].strip() if rc else None,
                    "user": next((c for c in f if c.startswith("사용자 실행:")), ""),
                    "skip": any(c.startswith("건너뜀") for c in f)})
    return out


def exec_entries(t):
    """{지점:n: 마지막 줄}, {지점:n: 브랜치 판정}."""
    runs = {e["label"]: e for e in exec_lines(t)}
    return runs, devflow_lib.branch_judgements(t)


def landed(run_dir, tasks, t, point, line):
    """돌지 않은 병합 줄의 넣는 브랜치 끝이 받는 브랜치에 이미 들어 있나(사용자가 직접 넣음). (참/거짓, 받는 끝)."""
    if not MERGE_LINE.search(line):
        return False, ""
    cwd = default_cwd(run_dir, tasks, t, point)
    src, tgt = expected(run_dir, tasks, t, point)
    src = src or merge_source(run_dir, line)
    tgt = tgt or head_branch(cwd)
    if not (cwd and os.path.isdir(cwd) and src and tgt):
        return False, ""
    s, g = rev(cwd, src), rev(cwd, tgt)
    if s and g and git(cwd, "merge-base", "--is-ancestor", s, g)[0] == 0:
        return True, g
    return False, ""


def verify(run_dir, t):
    """(통과 여부, 줄 목록)."""
    out, ok = [], True
    tasks = devflow_lib.load_tasks(run_dir)
    runs, judged = exec_entries(t)
    points = [p for p in kinds.EXEC_POINTS if os.path.isfile(frozen_path(t, p))]
    if not points:
        if t.get("kind") == "wrap-up":
            # 사용자가 내보내기를 직접 하기로 해 얼린 명령이 없음: 넣는 브랜치가 개발 기준 브랜치에 들어 있으면 받는다
            src, tgt = expected(run_dir, tasks, t, "실행승인")
            cwd = default_cwd(run_dir, tasks, t, "실행승인")
            if src and tgt and cwd and os.path.isdir(cwd):
                s, g = rev(cwd, src), rev(cwd, tgt)
                if s and g and git(cwd, "merge-base", "--is-ancestor", s, g)[0] == 0:
                    return True, ["얼린 명령 없음 — {}가 {}에 이미 들어 있음(사용자 직접, 끝 {})".format(src, tgt, g[:12])]
        return False, ["얼린 지점 없음(exec.py --freeze)"]
    conflict_ok = False
    if "결과승인" in points:
        res = read_frozen(t, "결과승인") or []
        conflict_ok = all(runs.get("결과승인:{}".format(i), {}).get("rc") == "0" for i in range(1, len(res) + 1)) \
            and any(v == "병합(충돌 해결)" for k, v in judged.items() if k.startswith("결과승인:"))
    for p in points:
        try:
            lines = read_frozen(t, p)
        except Reject as e:
            return False, [str(e)]
        if p == "되돌림" and outcome(t) != "되돌림":
            out.append("{}: 되돌리지 않음(요구하지 않음)".format(p))
            continue
        bad, notes = [], []
        for i, line in enumerate(lines, 1):
            label = "{}:{}".format(p, i)
            e = runs.get(label)
            if line.startswith(AFTER_KEEP) and outcome(t) != "유지":
                continue
            if e is None:
                hit, tip = landed(run_dir, tasks, t, p, line)
                if hit:
                    notes.append("{} 안 돎 — 받는 브랜치에 이미 들어 있음(사용자 직접, 끝 {})".format(label, tip[:12]))
                else:
                    bad.append("{} 안 돎".format(label))
            elif line.startswith(USER):
                if "종료 코드 0" not in e["user"]:
                    bad.append("{} 사용자 실행 결과에 종료 코드 0 없음".format(label))
            elif e["skip"]:
                bad.append("{} 건너뜀".format(label))
            elif e["rc"] != "0":
                if judged.get(label) == "충돌" and conflict_ok:
                    continue
                bad.append("{} 종료 코드 {}".format(label, e["rc"]))
            if judged.get(label) in ("불일치", "실패"):
                bad.append("{} 브랜치 판정 {}".format(label, judged[label]))
        ok = ok and not bad
        out.append("{}: {}줄 {}{}".format(p, len(lines), "통과" if not bad else "실패 — " + "; ".join(bad),
                                          " (" + "; ".join(notes) + ")" if notes else ""))
    return ok, out


def target_tip(run_dir, t, point="실행승인"):
    """받는 브랜치의 지금 끝(짧은 해시). 마무리를 사용자가 직접 넣었을 때 exported_commit에 쓴다."""
    tasks = devflow_lib.load_tasks(run_dir)
    cwd = default_cwd(run_dir, tasks, t, point)
    _, tgt = expected(run_dir, tasks, t, point)
    return rev(cwd, tgt)[:12] if (cwd and tgt and os.path.isdir(cwd)) else ""


# ---------------------------------------------------------------- 명령 줄

def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 4 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    run_dir, tid, args = argv[1], argv[2], argv[3:]

    def opt(name):
        return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None

    def label(raw):
        p, _, n = (raw or "").partition(":")
        if p not in kinds.EXEC_POINTS or not n.isdigit():
            raise Reject("지점:번호 꼴이어야 함(예 실행승인:1)")
        return p, int(n)
    try:
        if "--freeze" in args:
            rc, msg = freeze(run_dir, tid, opt("--point") or "", "--refreeze" in args)
            print(msg)
            return rc
        if "--step" in args:
            p, n = label(opt("--step"))
            return step(run_dir, tid, p, n, opt("--cwd"))
        if "--user-result" in args:
            p, n = label(opt("--user-result"))
            text = args[args.index("--user-result") + 2] if len(args) > args.index("--user-result") + 2 else ""
            if not text:
                raise Reject("결과 문장이 없음")
            return user_result(run_dir, tid, p, n, text)
        if "--verify" in args:
            _, t = load(run_dir, tid)
            ok, lines = verify(run_dir, t)
            print("\n".join(lines))
            print("exec.py --verify: " + ("통과" if ok else "실패"))
            return 0 if ok else 3
        if "--show" in args:
            _, t = load(run_dir, tid)
            for p in kinds.EXEC_POINTS:
                lines = read_frozen(t, p)
                if lines is not None:
                    print("[{}]".format(p))
                    print("\n".join("{}. {}".format(i, x) for i, x in enumerate(lines, 1)))
            return 0
    except Reject as e:
        print("거부: {} — {}".format(tid, e))
        return 3
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
