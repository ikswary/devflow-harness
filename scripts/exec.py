r"""밖으로 나가는 명령(합치기, 개발 기준 브랜치에 넣기, push, 배포)을 승인된 줄만 돌린다(SKILL.md 7절).

메인이 화면의 명령을 다시 타이핑하지 않고 번호만 고른다. 기록(exec.md), `external_progress`, 로그, 병합 판정은
이 스크립트가 쓴다. 승인 뒤 명령을 고쳐야 하면 다시 승인받고 --refreeze 한다.

사용:
  python exec.py {실행 폴더} {id} --freeze --point P [--refreeze]
  python exec.py {실행 폴더} {id} --freeze --point 실행 [--finish]
  python exec.py {실행 폴더} {id} --step P:n [--cwd 폴더]
  python exec.py {실행 폴더} {id} --user-result P:n "종료 코드 0, 출력 …"
  python exec.py {실행 폴더} {id} --main-result P:n "종료 코드 0, 출력 …"
  python exec.py {실행 폴더} {id} --verify
  python exec.py {실행 폴더} {id} --show

지점 P와 원천(「정해 주실 것」 안 ```cmd 울타리의 줄, 한 줄이 명령 하나. formats.md 4절)
  실행승인  그 task result.md. 배포 실행이면 부모 배포 계획의 result.md
  결과승인  그 task result.md(충돌을 고친 합치기의 병합 끝내기 명령. 실행승인에 얼린 줄은 뺀다)
  넣기승인  그 task result.md(배포 실행의 문서 넣기)
  되돌림    부모 배포 계획 result.md에서 제목에 「되돌리기」가 든 절들의 울타리
  실행      사람 답 없이 얼리는 유일한 지점: 1.2.0부터 시작한 합치기의 고정 꼴 `git merge --no-ff {흐름 브랜치} -m "{머리} {흐름 브랜치}"`
            (설계 5.3절 6). 원천은 flow.md와 recon.md 「합치기 관례」의 메시지 머리뿐이고 자유 글은 옮기지 않는다. --finish는 설정·형식
            파일뿐인 충돌을 끝내는 `git commit --no-edit`를 둘째 줄로 더하고 판정이 본 충돌 파일의 해시를 적는다. 그 --step은 조건을 다시 보고 충돌 파일만 스테이지한다.
  얼린 파일: tasks\{id}\approved-cmds-{P}.md(줄 번호와 해시). 손으로 고치면 해시가 어긋나 --step이 거부한다.
  얼림은 그 승인의 기록(「승인 기록」에서 승인 요청 뒤의 답 줄. 배포 실행의 실행승인·되돌림은 완료된 부모 계획의 답)이
  있어야 한다. 다시 얼림(--refreeze)은 앞서 얼린 뒤의 새 답이 있어야 한다.
  task_set.py가 승인 기록(--record)으로 묻는 단계를 떠날 때, 배포 실행이 시작될 때 이것을 함께 부른다.

줄 앞 표시
  [사용자 실행]  돌리지 않는다. 사용자가 실행하고 알려 준 결과를 --user-result로 적는다.
  [유지 뒤]      배포 실행의 deploy_outcome이 유지일 때만 돈다(아니면 건너뜀으로 적는다).

--main-result  --step이 실패한 줄을 사람에게 묻고(승인 기록에 답) 메인이 다른 방법으로 실행한 결과. 그 줄의 마지막
  실행이 실패이고 그 뒤 답이 있을 때만 받고, --step과 같은 꼴로 exec.md에 적는다(병합 줄이면 병합 판정과
  commit·exported_commit을 지금 git 상태로).

얼림의 넣는 끝(병합·push 줄): 마무리 실행승인은 judge-run.md 「최종 배포 후보 CI」의 검증 commit, 합치기 실행승인·실행은
  흐름 브랜치의 끝, 배포 실행 넣기승인은 배포 폴더 브랜치의 끝을 얼린 파일에 적고, --step은 넣는 쪽의 지금 끝이
  다르면 거부한다. 마무리의 병합 줄은 --ff-only여야 하고, 최종 CI가 실패했으면 승인 기록의 위험 수용 답
  (`승인|위험 수용|…`)이 있어야 돈다.

--step 전에 보는 것
  - 상태: 합치기·마무리·배포 실행은 `진행`이고 stage가 묻는 단계·`끝`이 아님. 탐침은 `진행`이고 stage `실행`.
    그 밖의 kind는 승인으로 `완료`된 뒤.
  - 한 번만: 얼린 뒤 같은 줄을 이미 돌렸으면(사용자 실행·건너뜀 포함) 거부. 다시 돌리려면 새 승인과 --refreeze.
  - 기대 브랜치(07 §A4, 원천에서 읽음): 합치기는 flow.md `branch` → run.md `integration_branch`, 마무리는
    `integration_branch`(흐름 하나면 그 흐름의 `branch`) → `base_branch`, 배포 실행 넣기는 배포 폴더의 브랜치 →
    `base_branch`. 병합 줄은 명령이 도는 폴더가 받는 브랜치를 꺼내 두었고 줄이 넣는 브랜치를 넣을 때만 돈다.
  - 작업 트리: 명령이 도는 폴더(기본: 합치기 = integration_dir, 마무리·넣기 = project(원래 폴더), 배포 실행 = 그
    흐름의 dir, 흐름 하나면 그 흐름의 dir, 그 밖 = 원래 폴더)의 `git status --porcelain`이 비어야 한다. 병합 줄은
    넣는 브랜치를 꺼낸 폴더(git worktree)도 비어야 한다(편집이 커밋되기 전에 넣지 않게).
    예외: `git add …`·`git commit …` 단독 줄(남은 변경을 커밋하는 줄), 원래 폴더의 병합 줄(병합이 바꾸는 파일과
    커밋 안 된 변경이 겹치지 않으면 됨. references/kinds/wrap-up/main-order.md 순서 5)과 `update-ref`·`push` 단독 줄.
    탐침(기본 폴더: 머리 파일 flow의 flow.md `dir`, 없으면 원래 폴더)의 병합 줄이 아닌 줄은 작업 트리를 쓰지 않는
    줄이라(계획 판정) 확인하지 않고, 커밋 안 된 변경 수를 exec.md 줄 끝에 `(탐침: …)`로 적는다.
병합 줄(`git … merge …`)은 앞뒤 해시로 병합 부모·앞감기를 판정해 exec.md에 적고, 병합이 끝나면
합치기는 머리 파일 `commit`, 마무리는 `exported_commit`에 새 끝을 적는다.

배포 폴더 상태: 1.2.0부터 시작한 배포 실행의 실행승인 줄은 --step이 돌기 전에 HEAD 전체 해시와 커밋 안 된 변경 수를
  exec.md에 적는다. 배포 뒤 HEAD는 배포 기록 커밋으로 움직이므로, 소스를 시험한 최종 CI의 완료 관문
  (task_set.source_tested_problem)은 이 줄을 읽는다. [사용자 실행] 줄과 --main-result로 다시 돌린 줄은 실행한 순간을 잴 수 없어
  재지 못함으로 다룬다.

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

import delegation
import devflow_lib
import kinds

USER = "[사용자 실행]"
AFTER_KEEP = "[유지 뒤]"
MERGE_LINE = re.compile(r"\bgit\b.*\smerge(\s|$)")
SEPARATORS = re.compile(r"[;&|<>`$]|\n")
GIT_PREFIX = r"^git\s+(?:-C\s+(?:\"[^\"]+\"|'[^']+'|\S+)\s+)?"
CONSUME_LINE = re.compile(GIT_PREFIX + r"(add|commit)(\s|$)")
NO_TREE_LINE = re.compile(GIT_PREFIX + r"(update-ref|push)(\s|$)")
PUSH_LINE = re.compile(r"\bgit\b.*\spush(\s|$)")
COMMIT_ANY = re.compile(r"(?:^|[;&|]\s*)git(?:\s+-[Cc]\s+\S+)*\s+(?:add|commit)(?:\s|$)")
# 합치기의 고정 꼴(설계 5.3절 6). 메시지 머리는 이 글자만 받고, 어긋나면 기본값을 쓴다
MERGE_CONVENTION = "합치기 관례"
DEFAULT_MERGE_HEAD = "merge:"
MESSAGE_TEMPLATE = re.compile(r"메시지[^`\n]*`([^`\n]*)`")
SAFE_HEAD = re.compile(r"\w[\w :./-]{0,39}")
SAFE_BRANCH = re.compile(r"\w[\w./-]*")
OWNED_LINE = re.compile(r'git merge --no-ff (\S+) -m "(\w[\w :./-]{0,39}) (\S+)"')
FINISH_LINE = "git commit --no-edit"   # 충돌 파일은 --step이 경로를 적어 스테이지한다
NO_CHOICE = "동작 선택: 없음"   # 충돌을 푼 작성자가 「본문」에 적는 단독 줄
CONFLICT_CRITERION = "충돌을 푼 줄이 동작을 바꾸지 않는다. 택한 줄과 버린 줄을 기준마다 적는다"
CONFLICT_MARK_WORDS = "동작을 바꾸지 않는다"
SOLVED_LINE = re.compile(r"^풀린 파일 (.+): ([0-9a-fA-F]*)$", flags=re.M)
CONFLICT_MARK = re.compile(r"^(<{7} |>{7} )", re.M)
CONFLICT_FILES = "충돌 파일"
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


def insert_line(line):
    """넣는 쪽 끝을 대조할 줄: 병합 줄과 `git … push` 줄(PR 방식의 내보내기)."""
    cmd = line[len(AFTER_KEEP):].strip() if line.startswith(AFTER_KEEP) else line
    return bool(MERGE_LINE.search(cmd) or PUSH_LINE.search(cmd))


def line_problems(t, point, line, cwd):
    """`--step`이 실행 전에 거부할 줄의 꼴 문제(pre_check와 screen.py가 함께 쓴다). 폴더 대조는 실행 전 확인이 폴더를
    보는 줄(병합 줄, 작업 트리를 쓰는 줄)에만 건다: `update-ref`·`push`·`add`·`commit` 단독 줄, `[유지 뒤]` 줄,
    탐침의 병합 줄이 아닌 줄은 대조하지 않는다. 마무리의 병합 줄은 `--ff-only`여야 한다(넣은 끝 = 최종 CI commit)."""
    if line.startswith(USER):
        return []
    cmd = line[len(AFTER_KEEP):].strip() if line.startswith(AFTER_KEEP) else line
    is_merge = bool(MERGE_LINE.search(cmd))
    no_tree = single(cmd, NO_TREE_LINE) or single(cmd, CONSUME_LINE) or (t.get("kind") == "probe" and not is_merge)
    out = devflow_lib.cmd_line_problems(line, cwd, bash=bool(shutil.which("bash")), check_dir=not no_tree,
                                        merge=is_merge)
    if t.get("kind") == "wrap-up" and is_merge and "--ff-only" not in cmd.split():
        out.append("마무리의 병합 줄에 `--ff-only`가 없음: 앞감기가 아니면 넣은 끝이 최종 CI의 검증 commit이 아니다")
    if t.get("kind") == "deploy-exec" and point == "넣기승인" and COMMIT_ANY.search(cmd):
        # 리뷰 111b N5(나): 메인이 이미 커밋했으므로 커밋 줄은 실패하고, 넣기 안에서 커밋하면 끝이 옮겨 병합 줄이 거부된다
        out.append("넣기 줄에 `git add`·`git commit`: 배포 기록은 메인이 넣기 승인 전에 커밋한다(넣는 명령은 병합 줄만)")
    return out


def recovery(tasks, t, point):
    """줄을 고쳐야 할 때의 회복 경로(원천이 어디인가)."""
    if t.get("kind") == "deploy-exec" and point in ("실행승인", "되돌림"):
        return ("원천이 완료된 배포 계획({})이라 고칠 수 없다: 새 배포 계획 task로 고친 명령을 승인받는다"
                "(references/main/new-task.md)".format(t.get("parent", "")))
    return "원천 줄(그 task result.md 「정해 주실 것」)을 고쳐 다시 승인받고 --refreeze"


def screen_lines(run_dir, tasks, t):
    """승인 화면 task의 cmd 줄마다 [(줄, 문제 목록)]. 줄이 실제로 도는 task·지점·폴더는 `source`·`default_cwd`와 같다:
    배포 계획의 「정해 주실 것」은 자식 배포 실행의 실행승인, 「되돌리기」는 되돌림, 그 밖은 지금 stage가 지점이면 그
    지점(배포 실행의 넣기승인 등), 아니면 실행승인."""
    if t.get("kind") == "deploy-plan":
        child = next((o for o in tasks.values() if o.get("parent") == t.get("id") and o.get("kind") == "deploy-exec"),
                     {"kind": "deploy-exec", "parent": t.get("id", ""), "flow": t.get("flow", "")})
        text = devflow_lib.read_text(os.path.join(t["_dir"], "result.md")) \
            if os.path.isfile(os.path.join(t["_dir"], "result.md")) else ""
        groups = [(child, "실행승인", devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"]))),
                  (child, "되돌림", devflow_lib.cmd_lines(heading_section(text, "되돌리기")))]
    else:
        stage = devflow_lib.stage_of(t)
        point = stage if stage in kinds.EXEC_POINTS else "실행승인"
        groups = [(t, point, devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"])))]
    out = []
    for runner, point, lines in groups:
        if not lines:
            continue
        try:
            cwd = default_cwd(run_dir, tasks, runner, point)
        except Exception:
            cwd = ""
        out += [(line, line_problems(runner, point, line, cwd)) for line in lines]
    return out


# ---------------------------------------------------------------- 승인과 원천

def approval_time(t):
    """「승인 기록」에서 승인 줄(devflow_lib.approval_line: 지점이나 결정이 승인) 가운데 가장 늦은 시각.
    승인 요청 전의 답은 세지 않는다. 보류·거절·되돌림·되물음 답과 재사용 답(`--reuse-answer`)으로는 얼리지 않는다."""
    best = None
    for line in devflow_lib.record_lines(t):
        f = devflow_lib.record_fields(line)
        if not devflow_lib.approval_line(line) or devflow_lib.reused_answer(line):
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


def digest(lines, tips=None, solved=None):
    """얼린 줄(과 넣는 끝, 풀린 충돌 파일)의 해시. 넣는 끝이 없는 옛 얼린 파일은 줄만으로 같다."""
    body = list(lines) + ["넣는 끝 {}: {}".format(n, sha) for n, sha in sorted((tips or {}).items())] \
        + ["풀린 파일 {}: {}".format(n, sha) for n, sha in sorted((solved or {}).items())]
    return hashlib.sha256("\n".join(body).encode("utf-8")).hexdigest()[:16]


TIP_LINE = re.compile(r"^넣는 끝 (\d+): ([0-9a-fA-F]{7,40})$", flags=re.M)


def read_frozen(t, point):
    """얼린 줄 목록. 해시가 어긋나면 Reject."""
    p = frozen_path(t, point)
    if not os.path.isfile(p):
        return None
    text = devflow_lib.read_text(p)
    lines = [m.group(2) for m in re.finditer(r"^(\d+)\. (.*)$", text, flags=re.M)]
    m = re.search(r"^해시: (\w+)", text, flags=re.M)
    if not m or m.group(1) != digest(lines, frozen_tips_raw(text), dict(SOLVED_LINE.findall(text))):
        raise Reject("{}의 해시가 맞지 않음(손으로 고침). 다시 승인받고 --refreeze".format(os.path.basename(p)))
    return lines


def frozen_tips_raw(text):
    return {int(m.group(1)): m.group(2) for m in TIP_LINE.finditer(text)}


def frozen_solved(t, point):
    """{충돌 파일: 얼릴 때의 blob 해시}. 해시는 read_frozen이 본다."""
    p = frozen_path(t, point)
    return dict(SOLVED_LINE.findall(devflow_lib.read_text(p))) if os.path.isfile(p) else {}


def frozen_tips(t, point):
    """{줄 번호: 얼릴 때 넣는 쪽의 끝 SHA}(병합·push 줄. 해시는 read_frozen이 본다)."""
    p = frozen_path(t, point)
    return frozen_tips_raw(devflow_lib.read_text(p)) if os.path.isfile(p) else {}


def insert_tip(run_dir, tasks, t, point):
    """(넣는 쪽의 끝 SHA, 못 정한 이유). 승인한 대상과 넣는 대상을 묶는다(07 원칙: 내보내는 것은 검증한 그 commit).
    마무리는 judge-run.md 「최종 배포 후보 CI」의 검증 commit, 합치기는 흐름 브랜치의 끝, 배포 실행의 넣기는 배포
    폴더 브랜치의 끝(메인이 넣기승인 전에 커밋한 배포 기록). 그 밖의 지점은 ("", "")."""
    kind = t.get("kind", "")
    if kind == "wrap-up" and point == "실행승인":
        sha = devflow_lib.final_ci_values(t).get("검증 commit", "")
        if devflow_lib.uses_isolation_contract(t) and not re.fullmatch(r"[0-9a-fA-F]{7,40}", sha or ""):
            return "", ("judge-run.md 「최종 배포 후보 CI」의 검증 commit이 없음: 문서 커밋과 최종 CI가 실행승인보다 먼저다"
                        "(references/kinds/wrap-up/main-order.md)")
        return sha, ""
    if (kind, point) in (("merge", "실행승인"), ("merge", kinds.OWNED_POINT), ("deploy-exec", "넣기승인")):
        src, _ = expected(run_dir, tasks, t, point)
        cwd = default_cwd(run_dir, tasks, t, point)
        sha = rev(cwd, src) if src and cwd and os.path.isdir(cwd) else ""
        checked, code = devflow_lib.doc_check_result(t) if kind == "deploy-exec" else ("", None)
        if sha and checked and not (sha.startswith(checked) or checked.startswith(sha)):
            return "", "넣을 끝 {}이 main-run.md 「넣기 전 문서 검사」의 검증 commit {}과 다름: 그 끝에서 다시 검사한다".format(
                sha[:12], checked)
        if checked and code != 0:
            # 리뷰 111b N2: 실패한(또는 종료 코드가 없는) 문서 검사는 위험 수용 답이 있을 때만 넣는다(마무리 최종 CI와 같은 꼴)
            since = os.path.getmtime(os.path.join(t["_dir"], "main-run.md"))
            if not devflow_lib.risk_accepted(t, since=since):
                return "", ("main-run.md 「넣기 전 문서 검사」의 종료 코드가 {}: 고쳐 다시 커밋·검사하거나, 넣으려면 "
                            "`--record \"승인|위험 수용|{{원문}}\"`으로 답을 적는다").format("없음" if code is None else code)
        return sha, ""
    return "", ""


def frozen_time(t, point):
    p = frozen_path(t, point)
    if not os.path.isfile(p):
        return None
    m = re.search(r"^얼린 시각: (.+)$", devflow_lib.read_text(p), flags=re.M)
    return ptime(m.group(1)) if m else None


def owned_merge(t):
    """사람 답 없이 얼리는 합치기인가: 1.2.0부터 시작한 합치기."""
    return t.get("kind") == "merge" and devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)


def merge_head(run_dir):
    """recon.md 「합치기 관례」에서 메시지 머리만 읽는다. 템플릿의 `{` 앞 글자가 꼴에 맞지 않으면 기본값이다."""
    path = os.path.join(run_dir, "recon.md")
    part = devflow_lib.sections(devflow_lib.read_text(path), level=2).get(MERGE_CONVENTION, "") if os.path.isfile(path) else ""
    m = MESSAGE_TEMPLATE.search(part)
    head = m.group(1).split("{")[0].strip() if m else ""
    return head if SAFE_HEAD.fullmatch(head) else DEFAULT_MERGE_HEAD


def owned_merge_line(run_dir, t):
    """(고정 꼴 한 줄, 못 만든 이유). 넣는 브랜치와 받는 브랜치는 flow.md와 run.md에서만 읽는다."""
    src, tgt = expected(run_dir, devflow_lib.load_tasks(run_dir), t, kinds.OWNED_POINT)
    if not (src and tgt):
        return "", "흐름 브랜치나 통합 브랜치를 정하지 못함(flow.md `branch`, run.md `integration_branch`)"
    if not SAFE_BRANCH.fullmatch(src) or ".." in src:
        return "", "고정 꼴에 넣지 못하는 브랜치 이름: {}".format(src)
    meta = devflow_lib.run_meta(run_dir)
    if tgt == meta_value(meta, "base_branch") or same_dir(default_cwd(run_dir, {}, t, kinds.OWNED_POINT), meta_value(meta, "project")):
        return "", "받는 쪽이 개발 기준 브랜치나 원래 폴더다(기본 브랜치 반영은 사람에게 묻는다)"
    line = 'git merge --no-ff {0} -m "{1} {0}"'.format(src, merge_head(run_dir))
    if merge_source(run_dir, line) != src:   # 메시지 머리에 다른 브랜치 이름이 들면 넣는 브랜치 판별이 끌려간다
        line = 'git merge --no-ff {0} -m "{1} {0}"'.format(src, DEFAULT_MERGE_HEAD)
    return line, ""


def conflict_files(t):
    """그 합치기의 충돌 파일(exec.py가 병합이 멈춘 때 적은 줄). 없으면 빈 목록."""
    path = os.path.join(t["_dir"], "exec.md")
    out = []
    for line in devflow_lib.read_text(path).splitlines() if os.path.isfile(path) else []:
        f = [c.strip() for c in line[2:].split("|")] if line.startswith("- ") else []
        if len(f) >= 4 and f[1] == CONFLICT_FILES:
            out = [x.strip() for x in f[3].split(",") if x.strip()]
    return out


def no_choice_written(t):
    """「본문」 절 안의 단독 줄 `동작 선택: 없음`. 내용은 판정 기준 `CONFLICT_CRITERION`이 대조한다(인용과 다른 칸의 글은 세지 않는다)."""
    path = os.path.join(t["_dir"], "result.md")
    if not os.path.isfile(path):
        return False
    body = devflow_lib.sections(devflow_lib.read_text(path), level=2).get("본문", "")
    return any(line.rstrip() == NO_CHOICE for line in body.splitlines())


def add_conflict_criterion(t):
    """병합이 멈춘 합치기의 판정 기준에 동작을 묻는 문장을 더한다. 스크립트가 정본 판정 기준과 그 원본을 함께 고쳐 기록 점검 R2에 걸리지 않는다."""
    doc = devflow_lib.Doc(t["_path"])
    text = doc.section("판정 기준") or ""
    if CONFLICT_CRITERION in text:
        return
    line = devflow_lib.next_criterion(text, CONFLICT_CRITERION)
    doc.set_section("판정 기준", (text.rstrip() + "\n" + line).strip())
    doc.save()
    orig, amends = devflow_lib.criteria_files(t["_dir"])
    latest = amends[-1] if amends else orig
    if os.path.isfile(latest):
        devflow_lib.write_text(latest, devflow_lib.read_text(latest).rstrip() + "\n" + line + "\n")


def _table_rows(judge_text):
    """읽기 판정 「판정 표」의 행을 칸 목록으로. 머리와 구분선은 뺀다."""
    rows = [[c.strip() for c in line.strip().strip("|").split("|")]
            for line in devflow_lib.sections(judge_text, level=2).get("판정 표", "").splitlines() if line.strip().startswith("|")]
    return [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]


def _judge_problem(t):
    """읽기 판정이 충돌 끝내기를 받치는가. 통과 못 한 기준, 판정불가, 실패가 없고 `CONFLICT_CRITERION`의 행이 통과여야 한다. 표의 기준 칸은 문장이거나 번호다."""
    judge = os.path.join(t["_dir"], kinds.JUDGE_FILES["read"])
    text = devflow_lib.read_text(judge) if os.path.isfile(judge) else ""
    failed = devflow_lib.sections(text, level=2).get("통과 못 한 기준")
    if failed is None or devflow_lib.item_count(failed):
        return "통과한 읽기 판정이 없음"
    rows = _table_rows(text)
    if any(len(r) > 1 and r[1].startswith(("판정불가", "실패")) for r in rows):
        return "판정 표에 판정불가나 실패가 있음"
    number = next((m.group(1) for m in re.finditer(r"^\s*(\d+)[.)]\s+(.*)$", t.get("_sections", {}).get("판정 기준", ""), re.M) if CONFLICT_MARK_WORDS in m.group(2)), None)
    hit = [r for r in rows if CONFLICT_MARK_WORDS in r[0] or (number and re.fullmatch(r"(?:기준\s*)?" + number, r[0]))]
    if not any(len(r) > 1 and r[1].startswith("통과") for r in hit):
        return "판정 표에 `{}` 기준의 통과 행이 없음".format(CONFLICT_MARK_WORDS)
    return ""


def merged_tree(cwd, ours, theirs):
    """자동 병합 결과의 tree(`git merge-tree --write-tree`, git 2.38 이상). 충돌이 있어도 tree를 낸다. 못 쓰면 빈 글이고 묻는 쪽으로 떨어진다."""
    rc, out = git(cwd, "merge-tree", "--write-tree", ours, theirs)
    first = out.splitlines()[0].strip() if out else ""
    return first if rc in (0, 1) and re.fullmatch(r"[0-9a-f]{40,64}", first) else ""


def names(cwd, *args):
    """(파일 목록, 재지 못한 이유). 한글 이름을 따옴표로 감싸지 않게 끈다."""
    rc, out = git(cwd, "-c", "core.quotepath=off", "diff", "--name-only", *args)
    return out.splitlines(), "" if rc == 0 else "git diff 실패"


def _outside_conflict(cwd, files):
    """스테이지된 충돌 밖 파일이 자동 병합 결과와 다르면 그 파일 목록(이유 글). 대조하지 못해도 이유를 내어 묻는다."""
    tree = merged_tree(cwd, "HEAD", "MERGE_HEAD")
    if not tree:
        return "자동 병합 결과를 재지 못함(git 2.38 이상의 merge-tree가 필요)"
    cached, why1 = names(cwd, "--cached", "HEAD")
    auto, why2 = names(cwd, "HEAD", tree)
    if why1 or why2:
        return "자동 병합과의 차이를 재지 못함({})".format(why1 or why2)
    other = [p for p in sorted(set(cached) | set(auto)) if p not in files and rev(cwd, ":" + p) != rev(cwd, "{}:{}".format(tree, p))]
    return "충돌 밖 파일이 자동 병합과 다름: {}".format(", ".join(other[:5])) if other else ""


def solved_hashes(cwd, files):
    """풀린 충돌 파일의 blob 해시. 없는 파일은 빈 글이다(묻는다). 줄 끝 변환을 맞추려고 `git hash-object`를 쓴다."""
    out = {}
    for name in files:
        rc, sha = git(cwd, "hash-object", "--", name) if os.path.isfile(os.path.join(cwd, name)) else (1, "")
        out[name] = sha.strip() if rc == 0 else ""
    return out


def _finish_problem(run_dir, t, cwd, solved=None):
    """충돌을 사람 답 없이 끝내지 못하는 이유(설계 5.3절 6). 없으면 빈 글. solved는 얼린 충돌 파일 해시이고, 주면 끝내기 직전의 재확인이다.
    파일 조건, `동작 선택: 없음`, 사람 몫 없음, 읽기 판정, 판정 뒤 바뀌지 않음, 푼 작업 트리, 충돌 밖 파일을 모두 본다."""
    if devflow_lib.branch_judgements(t).get(kinds.OWNED_POINT + ":1") != "충돌" or not rev(cwd, "MERGE_HEAD"):
        return "멈춘 병합이 없음"
    files = conflict_files(t)
    if not devflow_lib.settings_only(run_dir, files):
        return "충돌이 설정·형식 파일뿐이 아님({})".format(", ".join(files) or "충돌 파일 기록 없음")
    if not no_choice_written(t):
        return "결과 파일 「본문」에 단독 줄 `동작 선택: 없음`이 없음"
    cells = devflow_lib.result_cells(t) or {}
    if devflow_lib.item_count(cells.get("정해 주실 것", "")) or devflow_lib.item_count(cells.get("하실 일·허용 요청", "")):
        return "「정해 주실 것」이나 「하실 일」이 있음"
    why = _judge_problem(t)
    if why:
        return why
    judge = os.path.join(t["_dir"], kinds.JUDGE_FILES["read"])
    now_hash = solved_hashes(cwd, files)
    for name in files:
        path = os.path.join(cwd, name)
        if not now_hash[name]:
            return "충돌 파일이 없거나 재지 못함: {}".format(name)
        if CONFLICT_MARK.search(devflow_lib.read_text(path)):
            return "충돌 표시가 남음: {}".format(name)
        if solved is None and os.path.getmtime(path) > os.path.getmtime(judge):
            return "판정 뒤 바뀐 충돌 파일: {}".format(name)
        if solved is not None and solved.get(name) != now_hash[name]:
            return "판정이 본 충돌 파일이 달라짐: {}".format(name)
    rc, status = git(cwd, "-c", "core.quotepath=off", "status", "--porcelain")
    if rc != 0:
        return "작업 트리를 재지 못함(git status 실패)"
    stray = [l[3:].strip().strip('"') for l in status.splitlines() if l[1:2] != " " and l[3:].strip().strip('"') not in files]
    if stray:
        return "충돌 밖 파일의 변경: {}".format(", ".join(stray[:5]))
    return _outside_conflict(cwd, files)


def review_tip_problem(run_dir, tasks, t, cwd, src, tgt):
    """흐름 리뷰가 답을 받은 끝 뒤의 커밋이 모두 그 흐름의 끝난 task 커밋인가(설계가 실행 승인을 뺀 근거). 받아 온 통합 브랜치의 커밋과 병합 커밋은 세지 않는다. 흐름 리뷰가 없는 흐름은 보지 않는다."""
    flow = t.get("flow", "")
    reviews = [o for o in tasks.values() if o.get("kind") == "flow-verify" and o.get("flow") == flow and o.get("status") == kinds.DONE]
    if not reviews:
        return ""
    tip = str(reviews[-1].get("reviewed_tip", "") or "").strip()
    if not tip:
        return "흐름 리뷰가 본 끝이 기록되지 않음({})".format(reviews[-1]["id"])
    rc, out = git(cwd, "rev-list", "--no-merges", src, "^" + tip, "^" + tgt)
    if rc != 0:
        return "흐름 리뷰 뒤의 커밋을 재지 못함"
    done = [str(o.get("commit", "") or "").strip() for o in tasks.values() if o.get("flow") == flow and o.get("status") == kinds.DONE]
    stray = [c for c in out.splitlines() if not any(d and (c.startswith(d) or d.startswith(c)) for d in done)]
    return "흐름 리뷰 뒤의 task 없는 커밋 {}개: {}".format(len(stray), ", ".join(c[:12] for c in stray[:5])) if stray else ""


def flow_tip(run_dir, t):
    """그 흐름 브랜치의 지금 끝. 못 읽으면 빈 글이고, 합치기가 묻는 쪽으로 간다."""
    flow = flows_of(run_dir).get(t.get("flow", ""), {})
    branch = str(flow.get("branch", "") or "").strip()
    folder = next((d for d in (meta_value(flow, "dir"), meta_value(devflow_lib.run_meta(run_dir), "project")) if d and os.path.isdir(d)), "")
    return rev(folder, branch)[:12] if branch and folder else ""


def freeze_owned(run_dir, tid, finish=False):
    """사람 답 없는 얼림: `(merge, 실행)` 한 쌍과 고정 꼴에만 연다. (종료 코드, 메시지). 이미 돈 병합을 다시 돌리려면 그 뒤의 사람 답이 있어야 한다."""
    try:
        tasks, t = load(run_dir, tid)
        if not owned_merge(t):
            return 3, "사람 답 없는 얼림은 1.2.0부터 시작한 합치기만 받는다(이 task: {} {})".format(t.get("kind", ""), t.get("started_version", ""))
        if t.get("status") != "진행" or devflow_lib.stage_of(t) != kinds.OWNED_POINT:
            return 3, "합치기의 실행 단계가 아님(상태 {}, stage {})".format(t.get("status", ""), devflow_lib.stage_of(t) or "-")
        p = frozen_path(t, kinds.OWNED_POINT)
        old = read_frozen(t, kinds.OWNED_POINT)
        if finish:
            cwd = default_cwd(run_dir, tasks, t, kinds.OWNED_POINT)
            why = _finish_problem(run_dir, t, cwd)
            if old is None or why:
                return 3, "사람 답 없이 끝내지 못함: {} — stage=결과승인으로 묻는다".format(why or "얼린 병합 줄이 없음")
            lines, tips, solved = old[:1] + [FINISH_LINE], frozen_tips(t, kinds.OWNED_POINT), solved_hashes(cwd, conflict_files(t))
        else:
            line, why = owned_merge_line(run_dir, t)
            if why:
                return 3, "얼릴 수 없음: {} — stage=결과승인으로 묻는다".format(why)
            sha, why = insert_tip(run_dir, tasks, t, kinds.OWNED_POINT)
            if why:
                return 3, "얼릴 수 없음: " + why
            src, tgt = expected(run_dir, tasks, t, kinds.OWNED_POINT)
            why = review_tip_problem(run_dir, tasks, t, default_cwd(run_dir, tasks, t, kinds.OWNED_POINT), src, tgt)
            if why:
                return 3, "얼릴 수 없음: {} — stage=결과승인으로 묻는다".format(why)
            lines, tips, solved = [line], ({1: sha} if sha else {}), {}
        when = frozen_time(t, kinds.OWNED_POINT)
        ran = [e for e in exec_lines(t) if e["label"] == kinds.OWNED_POINT + ":1" and (when is None or (e["time"] and e["time"] >= when))]
        answered = approval_time(t)
        again = ran and answered and when and answered > when   # 돈 병합을 사람 답 뒤에 다시 돌린다. 같은 줄이어도 새로 얼려야 --step이 받는다
        if old == lines and frozen_tips(t, kinds.OWNED_POINT) == tips and not again:
            return 0, "이미 얼림(같음): " + p
        if old is not None:
            if not finish and ran and not again:
                return 3, "이미 돈 병합을 사람 답 없이 다시 얼리지 않는다: 답을 --record로 적은 뒤 다시 얼린다"
            n = 1
            while os.path.exists(p.replace(".md", ".r{}.md".format(n))):
                n += 1
            os.replace(p, p.replace(".md", ".r{}.md".format(n)))
        body = ["# 하네스 소유 명령 — {} {}".format(tid, kinds.OWNED_POINT), "원천: flow.md, run.md, recon.md 「{}」의 메시지 머리".format(MERGE_CONVENTION),
                "승인 기록 시각: 사람 답 없음(설계 5.3절 6)", "얼린 시각: " + now(), "해시: " + digest(lines, tips, solved), ""] \
            + ["{}. {}".format(i, x) for i, x in enumerate(lines, 1)] \
            + ([""] + ["넣는 끝 {}: {}".format(n, sha) for n, sha in sorted(tips.items())] if tips else []) \
            + ["풀린 파일 {}: {}".format(n, sha) for n, sha in sorted(solved.items())]
        devflow_lib.write_text(p, "\n".join(body) + "\n")
        return 0, "얼림 {}줄(사람 답 없음): {}".format(len(lines), p)
    except Reject as e:
        return 3, str(e)


def freeze(run_dir, tid, point, refreeze=False):
    """얼림. (종료 코드, 메시지)."""
    if point not in kinds.EXEC_POINTS:
        if point == kinds.OWNED_POINT:
            return 3, "이 지점은 답이 없는 고정 꼴만 받는다(exec.py --freeze --point {}, 1.2.0부터 시작한 합치기)".format(point)
        return 2, "지점은 " + "/".join(kinds.EXEC_POINTS)
    try:
        tasks, t = load(run_dir, tid)
        if point == "실행승인" and owned_merge(t):
            return 3, "1.2.0부터 시작한 합치기에는 실행승인 지점이 없다(--point {})".format(kinds.OWNED_POINT)
        at = approved_at(tasks, t, point)
        if at is None:
            return 3, ("얼릴 수 없음: {} 지점의 승인 기록이 없다. 승인 요청 뒤의 답 줄에서 지점 칸이나 결정 칸이 `승인`이어야 한다"
                       "(보류·거절·되돌림·되물음·알림·재사용 답은 세지 않음{}). 고치는 법: 사람이 실행을 승인했으면 "
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
        if os.path.isfile(frozen_path(t, point)) and not refreeze and read_frozen(t, point) == lines \
                and not frozen_tips(t, point):
            # 리뷰 111b N8: 1.1.1 전에 넣는 끝 없이 얼린 파일은 줄이 같으면 같음으로 본다(--step은 넣는 끝을 대조하지 않음)
            return 0, "이미 얼림(같음, 넣는 끝 없는 옛 얼림): " + frozen_path(t, point)
        tips = {}
        if any(insert_line(x) for x in lines):
            sha, why = insert_tip(run_dir, tasks, t, point)
            if why:
                return 3, "얼릴 수 없음: " + why
            tips = {i: sha for i, x in enumerate(lines, 1) if sha and insert_line(x)}
        p = frozen_path(t, point)
        if os.path.isfile(p):
            old = read_frozen(t, point)
            if old == lines and frozen_tips(t, point) == tips and not refreeze:
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
                "얼린 시각: " + now(), "해시: " + digest(lines, tips), ""] \
            + ["{}. {}".format(i, x) for i, x in enumerate(lines, 1)] \
            + ([""] + ["넣는 끝 {}: {}".format(n, sha) for n, sha in sorted(tips.items())] if tips else [])
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
    if kind == "probe":
        # 탐침 줄은 작업 트리를 쓰지 않으므로 흐름이 없으면 원래 폴더에서 돈다(설계 A-18)
        flow = flows_of(run_dir).get(t.get("flow", ""), {}) if t.get("flow", "") else {}
        return meta_value(flow, "dir") or project
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


def pre_check(run_dir, tasks, t, point, cwd, line, raw=None, tip=""):
    """실행 전 확인. (넣는 브랜치, 받는 브랜치, 알림 글)을 돌려주고, 거부면 Reject.
    raw는 얼린 줄 그대로(`[유지 뒤]` 표시 포함), tip은 얼릴 때 적은 넣는 쪽의 끝(frozen_tips)."""
    if not os.path.isdir(cwd):
        raise Reject("명령을 돌릴 폴더가 없음: " + cwd)
    bad = line_problems(t, point, raw or line, cwd)
    if bad:
        raise Reject("명령 줄 꼴: {} — {}".format("; ".join(bad), recovery(tasks, t, point)))
    is_merge = bool(MERGE_LINE.search(line))
    merging = bool(rev(cwd, "MERGE_HEAD"))
    src, tgt = expected(run_dir, tasks, t, point)
    if is_merge or (merging and single(line, CONSUME_LINE)):
        if tgt and head_branch(cwd) != tgt:
            raise Reject("받는 브랜치가 맞지 않음: {}는 {}를 꺼내 두었다(기대 {})".format(cwd, head_branch(cwd) or "(분리된 HEAD)", tgt))
    if insert_line(line) and t.get("kind") == "wrap-up" and devflow_lib.uses_isolation_contract(t) \
            and devflow_lib.final_ci_failed(t) and not devflow_lib.risk_accepted(t):
        raise Reject("최종 CI가 실패했고 승인 기록에 위험 수용 답이 없음: 고칠지·위험을 받아들일지·보류할지 묻는다"
                     "(references/kinds/wrap-up/main-order.md 「최종 CI가 실패하면」)")
    if insert_line(line) and tip:
        found = merge_source(run_dir, line) if not src else src
        now_tip = rev(cwd, found) if found else ""
        if not (now_tip and (now_tip.startswith(tip) or tip.startswith(now_tip))):
            raise Reject("넣는 쪽의 끝이 승인 때와 다름: {}는 지금 {}, 얼릴 때 {} — 바뀐 끝을 다시 검증·승인받고 --refreeze".format(
                found or "(넣는 브랜치 모름)", now_tip[:12] or "(없음)", tip[:12]))
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
    if t.get("kind") == "probe" and not is_merge:
        dirty = dirty_files(cwd)
        if dirty is None:
            return src, tgt, "(탐침: 작업 트리를 쓰지 않는 줄, git 저장소 아님)"
        return src, tgt, "(탐침: 작업 트리를 쓰지 않는 줄, 커밋 안 된 변경 {}개)".format(len(dirty))
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


TREE_STATE = "배포 폴더 상태"


def note_deploy_tree(t, point, label, cwd):
    """`- {시각} | 배포 폴더 상태 | {지점}:{n} | HEAD {해시} | 변경 {수}`. 지점 칸이 `지점 `으로 시작하지 않아 돈 줄로 읽히지 않는다."""
    if t.get("kind") != "deploy-exec" or point != "실행승인" \
            or not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        return
    head = rev(cwd, "HEAD") if os.path.isdir(cwd) else ""
    dirty = dirty_files(cwd) if os.path.isdir(cwd) else None
    append_exec(t, "- {} | {} | {} | HEAD {} | 변경 {}".format(
        now(), TREE_STATE, label, head or "읽지 못함", "읽지 못함" if dirty is None else len(dirty)))


def deploy_tree_records(t):
    """{지점:n: (HEAD, 변경)} 줄마다 마지막 기록."""
    p = os.path.join(t["_dir"], "exec.md")
    out = {}
    for line in devflow_lib.read_text(p).splitlines() if os.path.isfile(p) else []:
        f = [c.strip() for c in line[2:].split("|")] if line.startswith("- ") else []
        if len(f) >= 5 and f[1] == TREE_STATE:
            out[f[2]] = (f[3][len("HEAD "):], f[4][len("변경 "):])
    return out


def deploy_lines(t):
    """[(번호, 얼린 줄)] 실행승인 가운데 배포인 줄(`[유지 뒤]` 제외)."""
    return [(i, x) for i, x in enumerate(read_frozen(t, "실행승인") or [], 1) if not x.startswith(AFTER_KEEP)]


def line_unmeasured(t, i, line):
    """`[사용자 실행]` 줄이거나 마지막 실행이 `--main-result`인 줄: 남은 기록은 있어도 실패한 시도의 돌기 전 값이다."""
    entries = run_entries(t, "실행승인:{}".format(i))
    return line.startswith(USER) or bool(entries and entries[-1]["main"])


def deploy_tree_unmeasured(t):
    """사용자나 메인이 다른 방법으로 실행해 그 순간의 HEAD·작업 트리를 재지 못한 줄의 지점 이름."""
    try:
        return ["실행승인:{}".format(i) for i, x in deploy_lines(t) if line_unmeasured(t, i, x)]
    except Reject:
        return []


def deploy_tree_problem(t, commit):
    """배포한 줄들이 깨끗한 작업 트리의 그 커밋에서 돌았는가(문제 글, 없으면 빈 글). `[유지 뒤]` 줄은 배포가 아니라 보지 않고,
    잴 수 없는 줄은 보지 않는다(deploy_tree_unmeasured). 앞의 git 줄은 HEAD를 그 커밋으로 옮기는 줄일 수
    있어 HEAD가 달라도 되지만, 마지막 줄과 git이 아닌 줄은 그 커밋이어야 한다."""
    try:
        ran = deploy_lines(t)
    except Reject as e:
        return "배포 폴더 상태를 읽지 못함: {}".format(e)
    if not ran:
        return "얼린 배포 명령이 없어 배포 폴더 상태를 읽지 못함"
    records = deploy_tree_records(t)
    for i, line in ran:
        if line_unmeasured(t, i, line):
            continue
        label = "실행승인:{}".format(i)
        if label not in records:
            return "{}의 배포 폴더 상태 기록 없음(exec.py로 돌리거나 결과를 적지 않은 줄)".format(label)
        head, dirty = records[label]
        if dirty == "읽지 못함" or not re.fullmatch(r"[0-9a-fA-F]{40}", head):
            return "{}의 배포 폴더 HEAD·작업 트리를 읽지 못함".format(label)
        if dirty != "0":
            return "{} 때 배포 폴더의 작업 트리가 깨끗하지 않음(변경 {}개)".format(label, dirty)
        if head.lower() != commit.lower() and (i == ran[-1][0] or not line.startswith("git ")):
            return "{} 때 배포 폴더 HEAD({})가 배포 commit({})과 다름".format(label, head[:12], commit[:12])
    return ""


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
    if kind == "probe":
        if st != "진행" or devflow_lib.stage_of(t) != "실행":
            raise Reject("탐침의 실행 단계가 아님(상태 {}, stage {}): 실행승인 답과 함께 진행·stage=실행으로 바꾼 뒤 돌린다".format(
                st, devflow_lib.stage_of(t) or "-"))
    elif kind in kinds.STAGE_KINDS:
        stage = devflow_lib.stage_of(t)
        if st != "진행" or stage in kinds.ASK_STAGES or stage == "끝":
            raise Reject("실행 단계가 아님(상태 {}, stage {}): 승인 기록과 함께 진행·실행 단계로 바꾼 뒤 돌린다".format(st, stage or "-"))
    elif st != kinds.DONE:
        raise Reject("승인으로 완료된 뒤에만 돌린다(상태 {})".format(st))
    since = frozen_time(t, point)
    for e in exec_lines(t):
        if e["label"] == label and (since is None or (e["time"] and e["time"] >= since)):
            raise Reject("{}는 얼린 뒤 이미 돎({}) — 다시 돌리려면 새 승인과 --refreeze".format(label, e["time_s"]))


L4_POINT = "L4 확인"
L4_REFUSED = re.compile(r"보류|거절|안\s*함|아니|않|하지\s*마|말고|말아|멈춰|취소|안\s*돼|안돼|안\s*해|안해|못")


def _is_check(line, run_dir, since):
    """얼린 뒤의 `L4 확인` 답인가. 환경 이름 칸이 비었거나, 거절이거나, 위임의 말을 다시 적은 것은 확인이 아니다."""
    f = devflow_lib.record_fields(line)
    if len(f) <= 2 or f[1] != L4_POINT or not f[2].strip():
        return False
    words = devflow_lib.record_quote(line) or ""
    if L4_REFUSED.search(f[2]) or L4_REFUSED.search(words) or delegation.read_levels(words)[0]:
        return False
    if devflow_lib.answer_key(words) == devflow_lib.answer_key(delegation.current_original(run_dir)):
        return False
    at = ptime(f[0])
    return since is None or (at is not None and at >= since)


def frozen_by_delegation(tasks, t, point):
    """이 명령을 얼린 답이 위임 답인가: 얼린 파일의 `승인 기록 시각` 이하의 마지막 승인 줄로 본다. 뒤에 다른 일로 받은 답은 보지 않는다.
    사람이 다시 승인하면 --refreeze로 그 답이 얼린 답이 된다."""
    path = frozen_path(t, point)
    m = re.search(r"^승인 기록 시각: (.+)$", devflow_lib.read_text(path), flags=re.M) if os.path.isfile(path) else None
    at = ptime(m.group(1)) if m else None
    if at is None:
        return False
    source_task = tasks.get(t.get("parent", "")) if t.get("kind") == "deploy-exec" and point == "실행승인" else t
    last = None
    for line in devflow_lib.record_lines(source_task or {"_sections": {}}):
        when = ptime(devflow_lib.record_fields(line)[0])
        if devflow_lib.approval_line(line) and when is not None and when <= at:
            last = line
    return bool(last and delegation.is_delegated_line(last))


def production_block(run_dir, tasks, t, point, lines):
    """얼린 명령을 지금 돌리면 안 되는 이유(없으면 빈 글, 설계 9절). 사람이 직접 승인한 명령은 그 답이 확인이다.
    위임으로 승인된 명령은 지금 행 안에 있어야 하고, 운영 명령은 실행 직전 확인이 있어야 한다. 배포 실행의 운영 명령은
    계획을 사람이 승인했어도 위임 중이면 확인을 받는다(계획 승인과 실행 사이가 길다). 되돌림은 사람이 고른 뒤에만 돌므로 보지 않는다."""
    if point == "되돌림" or not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        return ""
    delegated = frozen_by_delegation(tasks, t, point)
    levels = devflow_lib.delegation_levels(run_dir)
    level = delegation.command_level(run_dir, t, lines)
    if delegated and level not in levels:
        return ("맡긴 층 밖이다: 이 명령은 {}이고 지금 위임 행은 {}다 — 사람에게 묻고 답을 `--record \"승인|…|{{원문}}\"`으로 적고 "
                "`--freeze --point {} --refreeze`로 다시 얼린 뒤 돌린다".format(level, delegation.levels_text(levels) or "없음", point))
    if level != "L4" or not (delegated or (levels and t.get("kind") == "deploy-exec")):
        return ""
    since = frozen_time(t, point)
    records = devflow_lib.record_lines(t)
    if any(_is_check(line, run_dir, since) for line in records):
        return ""
    tried = [line for line in records if len(devflow_lib.record_fields(line)) > 2 and devflow_lib.record_fields(line)[1] == L4_POINT]
    note = " 앞서 적은 답은 거절이거나 맡기는 말이거나 얼리기 전의 답이라 확인으로 세지 않았다." if tried else ""
    return ("운영 명령이다: 환경 이름을 적어 한 번 묻고 답을 `task_set.py {{실행 폴더}} {} --record \"{}|{{환경 이름}}|{{원문}}\"`으로 "
            "적은 뒤 돌린다. 안 된다는 답이면 돌리지 않고 `보류`로 둔다.{}").format(t.get("id"), L4_POINT, note)


def require_production_check(run_dir, tasks, t, point, lines):
    why = production_block(run_dir, tasks, t, point, lines)
    if why:
        raise Reject(why)


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
    require_production_check(run_dir, tasks, t, point, lines)
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
    if point == kinds.OWNED_POINT and cwd and not same_dir(cwd, default_cwd(run_dir, tasks, t, point)):
        raise Reject("사람 답 없이 얼린 줄은 정해진 폴더에서만 돈다: {}".format(default_cwd(run_dir, tasks, t, point)))
    cwd = cwd or default_cwd(run_dir, tasks, t, point)
    if point == kinds.OWNED_POINT and line == FINISH_LINE:
        why = _finish_problem(run_dir, t, cwd, solved=frozen_solved(t, point))
        if why:
            raise Reject("사람 답 없이 끝내지 못함: {} — stage=결과승인으로 묻는다".format(why))
        rc, _ = git(cwd, "add", "--", *conflict_files(t))
        if rc != 0:
            raise Reject("충돌 파일을 스테이지하지 못함")
    src, tgt, note = pre_check(run_dir, tasks, t, point, cwd, cmd, raw=line, tip=frozen_tips(t, point).get(n, ""))
    if note:
        print(note)
    note_deploy_tree(t, point, label, cwd)
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
    append_exec(t, "- {} | {} | 종료 코드 {} | 로그 {} | 지점 {} | 폴더 {}{}".format(
        now(), cmd, rc, log, label, cwd, " | " + note if t.get("kind") == "probe" and note else ""))
    judged = ""
    after = rev(cwd, "HEAD")
    if is_merge or (merging and CONSUME_LINE.match(cmd)):
        judged = merge_judgement(cwd, before, after, src_tip, rc=rc, merging=merging)
        append_exec(t, "- {} | 브랜치 판정 | {} | {} | 앞 {} 뒤 {} 넣은 {}@{} 받은 {}".format(
            now(), label, judged, before[:12], after[:12], src or "MERGE_HEAD", src_tip[:12], tgt or head_branch(cwd)))
        record_landing(t, judged, after, src_tip)
        if judged == "충돌" and t.get("kind") == "merge":
            append_exec(t, "- {} | {} | {} | {}".format(now(), CONFLICT_FILES, label, ", ".join(names(cwd, "--diff-filter=U")[0])))
            if owned_merge(t):
                add_conflict_criterion(t)
    elif rc == 0 and t.get("kind") == "wrap-up" and PUSH_LINE.search(cmd):
        # PR 방식: 내보낸 것은 push한 브랜치의 끝(최종 CI의 검증 commit과 대조된다)
        pushed = src or merge_source(run_dir, cmd)
        tip = rev(cwd, pushed) if pushed else ""
        if tip:
            set_head(t, exported_commit=tip[:12])
    done = rc == 0 and n == len(lines)
    set_head(t, external_progress="" if done else "{} {}/{} 끝 종료 코드 {}".format(point, n, len(lines), rc))
    with open(log, "rb") as f:
        tail = f.read().decode("utf-8", errors="replace").splitlines()[-20:]
    print("\n".join(tail))
    print("{} 종료 코드 {}{} (로그 {})".format(label, rc, ", 브랜치 판정 " + judged if judged else "", log))
    return 0 if rc == 0 else 3


def merge_judgement(cwd, before, after, src_tip, rc=0, merging=False):
    """병합 줄의 앞뒤 해시로 병합 판정 낱말."""
    parents = git(cwd, "rev-list", "--parents", "-n", "1", "HEAD")[1].split()[1:]
    if rc != 0 and rev(cwd, "MERGE_HEAD"):
        return "충돌"
    if rc != 0:
        return "실패"
    if merging:
        return "병합(충돌 해결)" if parents == [before, src_tip] else "불일치"
    if after == src_tip and after != before:
        return "앞감기"
    if before and parents == [before, src_tip]:
        return "병합"
    if src_tip and git(cwd, "merge-base", "--is-ancestor", src_tip, after)[0] == 0 and (after == before or not before):
        return "이미 들어 있음"
    return "불일치"


def record_landing(t, judged, after, src_tip):
    """병합이 끝났으면 합치기는 `commit`, 마무리는 `exported_commit`(앞감기·이미 들어 있음은 넣은 끝 = 검증한 commit)."""
    if judged not in ("병합", "앞감기", "병합(충돌 해결)", "이미 들어 있음"):
        return
    if t.get("kind") == "merge":
        set_head(t, commit=after[:12])
    elif t.get("kind") == "wrap-up":
        set_head(t, exported_commit=(src_tip if judged in ("앞감기", "이미 들어 있음") and src_tip else after)[:12])


def failed_run(t, label):
    """exec.md에서 그 줄의 마지막 실행이 돈 폴더와, 마지막 브랜치 판정의 `앞` 해시(실패 직전 받는 끝). 없으면 ""."""
    p = os.path.join(t["_dir"], "exec.md")
    folder = before = ""
    for line in (devflow_lib.read_text(p).splitlines() if os.path.isfile(p) else []):
        f = [c.strip() for c in line[2:].split("|")] if line.startswith("- ") else []
        if len(f) >= 4 and f[1] == "브랜치 판정" and f[2] == label:
            m = re.match(r"앞 ([0-9a-fA-F]{7,40})\b", f[4] if len(f) > 4 else "")
            before = m.group(1) if m else ""
        elif "지점 " + label in f:
            folder = next((c[3:].strip() for c in f if c.startswith("폴더 ")), "")
    return folder, before


def main_result(run_dir, tid, point, n, text):
    """실패한 줄을 사람 답을 받아 메인이 다른 방법으로 실행한 결과를 `--step`과 같은 꼴로 적는다(T043: 메인이 exec.md를
    손으로 덧붙임). 그 줄의 마지막 실행이 실패했고 그 뒤 승인 기록에 사용자 답(원문, 알림·점검 확인 줄은 빼고)이 있을
    때만 받는다. 폴더는 실패한 실행의 폴더(`--cwd`로 돌렸으면 그 폴더)다. 병합 줄이면 실패 직전 받는 끝(그 줄의 브랜치
    판정 `앞`)을 앞 해시로 병합 판정을 내고, 얼린 넣는 끝과 대조한다. 마무리는 받는 끝 = 넣은 끝 = 얼린 끝(앞감기)일
    때만 `exported_commit`을 적고 아니면 `불일치`다(리뷰 111b N1: 병합 커밋을 `이미 들어 있음`으로 받던 길)."""
    tasks, t = load(run_dir, tid)
    lines = read_frozen(t, point)
    if lines is None or not 1 <= n <= len(lines):
        raise Reject("얼린 줄이 없음: {}:{}".format(point, n))
    label = "{}:{}".format(point, n)
    kind, st, stage = t.get("kind", ""), t.get("status", ""), devflow_lib.stage_of(t)
    if kind in kinds.STAGE_KINDS and (st != "진행" or stage in kinds.ASK_STAGES or stage == "끝"):
        raise Reject("실행 단계가 아님(상태 {}, stage {})".format(st, stage or "-"))
    last = [e for e in exec_lines(t) if e["label"] == label]
    if not last or last[-1]["user"] or last[-1]["skip"] or last[-1]["rc"] in (None, "0"):
        raise Reject("{}의 마지막 실행이 실패가 아님 — --main-result는 실패한 줄을 다른 방법으로 실행한 결과만 받는다".format(label))
    failed_at = last[-1]["time"]

    def answer(line):
        f = devflow_lib.record_fields(line)
        when = ptime(f[0])
        return bool((devflow_lib.record_quote(line) or "").strip()) and f[1:2] not in (["알림"], ["점검 확인"]) \
            and when is not None and failed_at is not None and when >= failed_at
    if not any(answer(l) for l in devflow_lib.record_lines(t)):
        raise Reject("{} 실패({}) 뒤 승인 기록에 사용자 답이 없음: 다른 방법으로 실행하기 전에 묻고 --record로 적는다".format(
            label, last[-1]["time_s"]))
    m = re.search(r"종료 코드\s*(-?\d+)", text)
    if not m:
        raise Reject("결과 문장에 `종료 코드 N`이 없음")
    rc = int(m.group(1))
    cmd = lines[n - 1][len(AFTER_KEEP):].strip() if lines[n - 1].startswith(AFTER_KEEP) else lines[n - 1]
    folder, before = failed_run(t, label)
    cwd = folder or default_cwd(run_dir, tasks, t, point)
    append_exec(t, "- {} | {} | 종료 코드 {} | 메인 실행: {} | 지점 {} | 폴더 {}".format(
        now(), cmd, rc, text.replace("|", "/"), label, cwd))
    judged = ""
    if MERGE_LINE.search(cmd) and os.path.isdir(cwd):
        src, tgt = expected(run_dir, tasks, t, point)
        src = src or merge_source(run_dir, cmd)
        after, src_tip = rev(cwd, "HEAD"), (rev(cwd, src) if src else "")
        before = rev(cwd, before) if before else ""   # exec.md에는 12자로 적혀 있다
        judged = merge_judgement(cwd, before, after, src_tip, rc=rc) if src_tip else "불일치"
        tip = frozen_tips(t, point).get(n, "")
        if tip and src_tip and not (src_tip.startswith(tip) or tip.startswith(src_tip)):
            judged = "불일치"   # 넣은 끝이 승인 때 얼린 끝이 아니다
        if kind == "wrap-up" and judged != "불일치" and rc == 0 and after != src_tip:
            judged = "불일치"   # 마무리는 앞감기만: 받는 끝이 검증한 commit이어야 한다
        append_exec(t, "- {} | 브랜치 판정 | {} | {} | 앞 {} 뒤 {} 넣은 {}@{} 받은 {}".format(
            now(), label, judged, before[:12] or "(모름)", after[:12], src or "(모름)", src_tip[:12],
            tgt or head_branch(cwd)))
        record_landing(t, judged, after, src_tip)
    set_head(t, external_progress="" if rc == 0 and n == len(lines) else "{} {}/{} 끝 종료 코드 {}".format(
        point, n, len(lines), rc))
    print("{} 메인 실행 결과 적음: 종료 코드 {}{}".format(label, rc, ", 브랜치 판정 " + judged if judged else ""))
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


def run_entries(t, label):
    """그 줄의 실행 기록 [{cmd, folder, main, user, skip, rc}]. 칸 수에 기대지 않고 머리로 읽는다."""
    p = os.path.join(t["_dir"], "exec.md")
    out = []
    for line in devflow_lib.read_text(p).splitlines() if os.path.isfile(p) else []:
        f = [c.strip() for c in line[2:].split("|")] if line.startswith("- ") else []
        if len(f) >= 4 and f[1] != "브랜치 판정" and "지점 " + label in f:
            rc = next((c[6:].strip() for c in f if c.startswith("종료 코드 ")), None)
            out.append({"cmd": f[1], "rc": rc, "folder": next((c[3:].strip() for c in f if c.startswith("폴더 ")), ""),
                        "main": any(c.startswith("메인 실행:") for c in f), "user": any(c.startswith("사용자 실행:") for c in f),
                        "skip": any(c.startswith("건너뜀") for c in f)})
    return out


def _ran_as_frozen(t, label, line, folder=""):
    """얼린 줄이 글자 그대로 `--step`으로 돌았으면 빈 글, 아니면 이유."""
    entries = run_entries(t, label)
    if not entries:
        return "{}가 돌지 않았다".format(label)
    if any(e["main"] for e in entries):
        return "{}를 메인이 다른 방법으로 실행했다".format(label)
    if any(e["user"] or e["skip"] for e in entries):
        return "{}를 사용자가 실행했거나 건너뛰었다".format(label)
    if entries[-1]["cmd"] != line:
        return "{}의 돈 줄이 얼린 줄과 다르다".format(label)
    if folder and not same_dir(entries[-1]["folder"], folder):
        return "{}가 돈 폴더가 다르다: {}".format(label, entries[-1]["folder"])
    return ""


def merge_notice_problems(run_dir, t):
    """합치기를 사람 답 없이 닫지 못하는 이유 목록(설계 5.3절 6). 얼린 고정 꼴과 실제 명령이 글자까지 같고, 병합이거나 설정·형식 충돌을 끝낸 것일 때만 빈 목록이다."""
    point = kinds.OWNED_POINT
    try:
        lines = read_frozen(t, point)
    except Reject as e:
        return [str(e)]
    if not lines:
        return ["사람 답 없이 얼린 합치기가 없음(--freeze --point {})".format(point)]
    tasks = devflow_lib.load_tasks(run_dir)
    src, _ = expected(run_dir, tasks, t, point)
    shape = OWNED_LINE.fullmatch(lines[0])
    if not (shape and shape.group(1) == src and shape.group(3) == src) or lines[1:] not in ([], [FINISH_LINE]):
        return ["얼린 줄이 고정 꼴이 아님: {}".format(lines[0])]
    folder = default_cwd(run_dir, tasks, t, point)
    out = [why for why in (_ran_as_frozen(t, "{}:{}".format(point, i), line, folder) for i, line in enumerate(lines, 1)) if why]
    judged = devflow_lib.branch_judgements(t)
    first = judged.get(point + ":1", "")
    commit = str(t.get("commit", "") or "").strip()
    if first == "충돌":
        if judged.get(point + ":2") != "병합(충돌 해결)":
            out.append("충돌을 끝내지 않았다")
        elif not devflow_lib.settings_only(run_dir, conflict_files(t)) or not no_choice_written(t):
            out.append("설정·형식 파일뿐인 충돌이 아니다")
        else:
            out += _landed_problems(folder, commit, conflict_files(t), frozen_solved(t, point))
    elif first != "병합":
        out.append("브랜치 판정이 병합이 아님({})".format(first or "없음"))
    # 인프라는 실제 변경 파일로 잰다(합치기 머리 파일에는 「건드릴 파일」이 없다)
    changed, why = names(folder, "{0}^1...{0}^2".format(commit)) if commit else ([], "합친 커밋이 없음")
    if why:
        out.append("합친 파일을 재지 못함({})".format(why))
    infra = devflow_lib.infra_paths_in(run_dir, changed)
    if infra:
        out.append("인프라 파일을 합침: " + ", ".join(infra[:5]))
    return out


def _landed_problems(cwd, commit, files, solved):
    """사람 답 없이 끝낸 병합 커밋의 내용: 충돌 밖 파일은 자동 병합 그대로이고 충돌 파일은 판정이 본 해시다."""
    tree = merged_tree(cwd, commit + "^1", commit + "^2") if commit else ""
    if not tree:
        return ["자동 병합 결과를 재지 못함(git 2.38 이상의 merge-tree가 필요)"]
    other, why = names(cwd, commit, tree)
    if why:
        return ["병합 커밋을 재지 못함({})".format(why)]
    out = ["병합 커밋의 충돌 밖 파일이 자동 병합과 다름: " + ", ".join(p for p in other[:5] if p not in files)] if [p for p in other if p not in files] else []
    return out + ["병합 커밋의 충돌 파일이 판정이 본 것과 다름: " + n for n in files if solved.get(n) != rev(cwd, "{}:{}".format(commit, n))]


def wrap_notice_problems(run_dir, t):
    """마무리 결과를 사람 답 없이 닫지 못하는 이유 목록(설계 5.3절 6): `--verify` 실패, `불일치`, 얼린 줄대로 돌지 않은 줄(사용자가 직접 넣음, 메인 실행)."""
    ok, lines = verify(run_dir, t)
    if not ok:
        return ["exec.py --verify 실패({})".format("; ".join(lines))]
    try:
        frozen = read_frozen(t, "실행승인")
    except Reject as e:
        return [str(e)]
    if not frozen:
        return ["얼린 내보내기 명령이 없음(사용자가 직접 넣음)"]
    folder = default_cwd(run_dir, devflow_lib.load_tasks(run_dir), t, "실행승인")
    out = [why for why in (_ran_as_frozen(t, "실행승인:{}".format(i), line, folder) for i, line in enumerate(frozen, 1)) if why]
    out += ["{} 브랜치 판정 {}".format(k, v) for k, v in devflow_lib.branch_judgements(t).items() if v not in ("앞감기", "병합")]
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
    points = [p for p in kinds.FROZEN_POINTS if os.path.isfile(frozen_path(t, p))]
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
    # 사람 답 없이 끝낸 충돌: 둘째 줄(끝내기)이 돌았으면 멈춘 첫 줄을 받는다
    conflict_ok = conflict_ok or (runs.get(kinds.OWNED_POINT + ":2", {}).get("rc") == "0"
                                  and judged.get(kinds.OWNED_POINT + ":2") == "병합(충돌 해결)")
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
    """사용자가 직접 넣은 마무리의 exported_commit(짧은 해시): 받는 브랜치의 끝이 넣는 브랜치의 끝과 같으면(앞감기) 그 끝
    (= 검증한 commit), 아니면 ""."""
    tasks = devflow_lib.load_tasks(run_dir)
    cwd = default_cwd(run_dir, tasks, t, point)
    src, tgt = expected(run_dir, tasks, t, point)
    if not (cwd and src and tgt and os.path.isdir(cwd)):
        return ""
    s, g = rev(cwd, src), rev(cwd, tgt)
    # 리뷰 111b N6: 실행 경로의 `--ff-only`와 같이, 받는 끝이 넣는 끝 그대로(앞감기)일 때만. 병합 커밋으로 넣었거나
    # 그 뒤 받는 쪽이 움직였으면 비워 두어 완료 관문이 거부하고 메인이 묻는다
    return s[:12] if s and g and s == g else ""


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
        if p not in kinds.FROZEN_POINTS or not n.isdigit():
            raise Reject("지점:번호 꼴이어야 함(예 실행승인:1)")
        return p, int(n)
    try:
        if "--freeze" in args:
            if opt("--point") == kinds.OWNED_POINT:
                rc, msg = freeze_owned(run_dir, tid, finish="--finish" in args)
            else:
                rc, msg = freeze(run_dir, tid, opt("--point") or "", "--refreeze" in args)
            print(msg)
            return rc
        if "--step" in args:
            p, n = label(opt("--step"))
            return step(run_dir, tid, p, n, opt("--cwd"))
        if "--main-result" in args:
            p, n = label(opt("--main-result"))
            text = args[args.index("--main-result") + 2] if len(args) > args.index("--main-result") + 2 else ""
            if not text:
                raise Reject("결과 문장이 없음")
            return main_result(run_dir, tid, p, n, text)
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
            for p in kinds.FROZEN_POINTS:
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
