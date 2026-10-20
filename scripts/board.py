"""보드: task 머리 파일을 읽어 전체 상태를 보여 준다. 원천은 머리 파일이고 이 출력은 보는 용도다.

사용:
  python board.py {실행 폴더}                 전체 표 + 승인 대기열 + 시작할 수 있는 task + 고리 검사
  python board.py {실행 폴더} --queue         승인 대기열만
  python board.py {실행 폴더} --ready         지금 시작할 수 있는 task만(흐름 상한, 폴더 사용 중, 받아오기 대기, 커밋 대기,
                                              kind별 시작 조건: 흐름별 검증·전체 검증·마무리). 이어서 합칠 수 있는 흐름,
                                              재검증 없는 수정, 보류에 막힌 대기 task(남은 것이 모두 그것이면 끝 질문),
                                              그 아래 점검 확인이 없는 기록 점검 걸림(`! 기록 점검:`, 없으면 줄 없음),
                                              `하네스 판본:` 한 줄(SKILL.md 1절), 맨 끝에 `메인 컨텍스트:` 한 줄(SKILL.md 8절)
  python board.py {실행 폴더} --ascii         진행 상황 그림(흐름별 줄, 상태 기호, 승인 대기·도는 에이전트)
  python board.py {실행 폴더} --cycles        의존 고리만(있으면 종료 코드 3)
  python board.py {실행 폴더} --log           승인 기록을 시간순으로
  python board.py {실행 폴더} --resume        재개 때 볼 것(진행·자체검증·승인대기, 실행 중 에이전트와 그 결과 파일의 마지막
                                              수정 시각, 외부 작업 진행, 답 반영 대기). `--now "시각"`으로 기준 시각을 줄 수 있다
  python board.py {작업 공간} --backlog       작업 공간의 모든 실행에서 남은 백로그
"""
import os
import sys

import devflow_lib
import kinds


def blocked_ids(tasks, tid):
    """tid가 `완료`가 아니어서 시작하지 못하는 대기 task id(부모 또는 의존하는 task로 가리키는 것)."""
    return [t["id"] for t in tasks.values() if t.get("status") == "대기"
            and (t.get("parent") == tid or tid in t.get("depends_on", []))]


def blockers(tasks, tid):
    return len(blocked_ids(tasks, tid))


def is_ready(tasks, t, holds=None):
    """부모와 의존하는 task가 `완료`. 마무리와 흐름별 검증은 보류에 막혀 끝난 것(settled)도 기다리지 않는다
    (마무리는 남김 목록이 화면에 붙고, 흐름별 검증은 start_blocks가 "보류된 구현 있음"으로 묻게 한다)."""
    if t.get("status") != "대기":
        return False
    wrap = t.get("kind") in ("wrap-up", "flow-verify")
    if wrap and holds is None:
        holds = devflow_lib.hold_blockers(tasks)
    for ref in [t.get("parent", "")] + list(t.get("depends_on", [])):
        if not ref or ref not in tasks or tasks[ref].get("status") == kinds.DONE:
            continue
        if wrap and devflow_lib.settled(tasks[ref], tasks, holds):
            continue
        return False
    return True


def find_cycles(tasks):
    cycles = []
    state = {}

    def visit(tid, path):
        state[tid] = 1
        for dep in tasks[tid].get("depends_on", []):
            if dep not in tasks:
                continue
            if state.get(dep) == 1:
                cycles.append(path[path.index(dep):] + [dep] if dep in path else [tid, dep])
            elif state.get(dep) is None:
                visit(dep, path + [dep])
        state[tid] = 2

    for tid in tasks:
        if state.get(tid) is None:
            visit(tid, [tid])
    return cycles


def queue(tasks):
    waiting = [t for t in tasks.values() if t.get("status") == "승인대기"]

    def key(t):
        try:
            decide = int(t.get("n_decide", "0") or 0)
        except ValueError:
            decide = 0
        return (-blockers(tasks, t["id"]), -(1 if decide > 0 else 0), t.get("approval_requested", "") or "9")

    return sorted(waiting, key=key)


def print_table(tasks):
    print("| id | 종류 | 제목 | 상태 | 흐름 | 부모 | 의존하는 task |")
    print("|---|---|---|---|---|---|---|")
    for tid, t in tasks.items():
        print("| {} | {} | {} | {} | {} | {} | {} |".format(
            tid, t.get("kind", ""), t.get("title", ""), t.get("status", ""), t.get("flow", ""),
            t.get("parent", ""), ", ".join(t.get("depends_on", []))))


def print_queue(tasks):
    q = queue(tasks)
    print("승인 대기 {}개".format(len(q)))
    for i, t in enumerate(q, 1):
        ids = blocked_ids(tasks, t["id"])
        print("{}. {} {} (막고 있는 task {}개{}, 정해 주실 것 {}건, 요청 {})".format(
            i, t["id"], t.get("title", ""), len(ids), ": " + ", ".join(ids) if ids else "", t.get("n_decide", "0") or 0,
            t.get("approval_requested", "") or "-"))


# 코드 폴더에 쓰는 task는 등록표 `kinds.CODE_DIR_KINDS`(원인 분석은 재현 테스트를 쓴다), 흐름의 구현·수정은
# `kinds.AUTO_DEPEND_KINDS`, 그 폴더를 쓰는 중인 상태는 `kinds.BUSY_STATUSES`(자체 검증은 그 폴더에서 테스트를 돈다).


def writes(t):
    """코드 폴더에 쓰는 task. 옛 실행의 코드를 고치는 change도 센다(새로 만드는 것은 fix)."""
    return t.get("kind") in kinds.CODE_DIR_KINDS or devflow_lib.is_code_change(t)


def load_flows(run_dir):
    """{흐름 이름: flow.md 머리}. 머리마다 `role`(옛 파일은 이름으로 추정)과 `round`(없으면 1)를 채우고,
    run.md `round`(없으면 1)를 `_round` 키로 함께 싣는다(start_blocks 인수를 늘리지 않으려고)."""
    out = {"_round": devflow_lib.run_round(run_dir)}
    base = os.path.join(run_dir, "flows")
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        p = os.path.join(base, name, "flow.md")
        if os.path.isfile(p):
            meta_lines, _ = devflow_lib.split_front_matter(devflow_lib.read_text(p))
            meta = devflow_lib.parse_meta(meta_lines)
            for key in ("depends_on_flows", "sync_pending"):
                v = meta.get(key, [])
                meta[key] = v if isinstance(v, list) else devflow_lib.parse_value("x", "[" + v + "]")
            key = meta.get("flow", name)
            meta["role"] = devflow_lib.flow_role(key, meta)
            meta["round"] = devflow_lib.as_round(meta.get("round", ""))
            out[key] = meta
    return out


def flow_items(flows):
    return [(n, f) for n, f in flows.items() if not n.startswith("_")]


def flow_cap(run_dir):
    """run.md 「이번 실행의 값」의 `동시에 도는 흐름` 값. 못 읽으면 SKILL.md 시작값 2."""
    try:
        for line in devflow_lib.read_text(os.path.join(run_dir, "run.md")).splitlines():
            if line.startswith("|") and "동시에 도는 흐름" in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                for c in cells[1:]:
                    digits = "".join(ch for ch in c if ch.isdigit())
                    if digits:
                        return int(digits)
    except OSError:
        pass
    return kinds.RUN_DEFAULTS["동시에 도는 흐름"]


def commit_waiting(tasks, flow):
    """흐름에서 통과 못 한 채 사람을 기다리는(승인대기, commit 빔) 코드 task id. 커밋 전이라 받아오기와 다음 쓰는 task를 막는다."""
    return [o["id"] for o in tasks.values() if flow and o.get("flow") == flow and o.get("kind") in kinds.AUTO_DEPEND_KINDS
            and o.get("status") == "승인대기" and not str(o.get("commit", "")).strip()]


def flow_done(tasks, name, f, holds):
    """흐름이 끝났나: 합쳐짐(또는 폴더 지움), 또는 코드 task가 모두 보류·백로그·보류에 막힘
    (코드 task가 하나도 없으면 폴더를 만들기 전(`폴더 없음`)일 때만 끝으로 센다)."""
    status = (f or {}).get("status")
    if status in ("합쳐짐", "폴더 지움"):
        return True
    code = [o for o in tasks.values() if o.get("flow") == name and o.get("kind") in kinds.AUTO_DEPEND_KINDS]
    if not code:
        return status == "폴더 없음"
    return all(o.get("status") in ("보류", "백로그") or o["id"] in holds for o in code)


def downstream(tasks, roots, kinds):
    """roots(id 집합)나 kinds 종류의 task에 부모·의존으로 (사슬을 따라) 닿는 task id. 그 뒤에야 도는 task라
    흐름별 검증·마무리의 시작 조건에서 기다리지 않는다(기다리면 서로 기다려 막힌다)."""
    after = set(roots) | {o["id"] for o in tasks.values() if o.get("kind") in kinds}
    memo = {}

    def hit(tid, seen):
        if tid in memo:
            return memo[tid]
        t = tasks.get(tid)
        if t is None or tid in seen:
            return False
        refs = [r for r in [t.get("parent", "")] + list(t.get("depends_on", [])) if r in tasks]
        memo[tid] = any(r in after or hit(r, seen | {tid}) for r in refs)
        return memo[tid]
    return {tid for tid in tasks if hit(tid, frozenset())}


def round_flows(tasks, flows, role):
    """이번 회차의 그 역할 흐름 {이름: 머리}. 코드 task는 있는데 flow.md가 아직 없는 흐름도 넣는다(이름으로 역할 추정)."""
    rnd = flows.get("_round", 1)
    out = {n: f for n, f in flow_items(flows) if f.get("role", devflow_lib.flow_role(n, f)) == role
           and f.get("round", 1) == rnd}
    for o in tasks.values():
        n = o.get("flow", "")
        if n and n not in flows and o.get("kind") in kinds.AUTO_DEPEND_KINDS and devflow_lib.flow_role(n) == role:
            out.setdefault(n, {})
    return out


def start_blocks(tasks, flows, cap, t, holds=None):
    """의존은 풀렸지만 지금 띄우면 안 되는 이유(없으면 빈 목록). SKILL.md 1절 2, references/kinds/merge/main-order.md 「받아오기」.
    머리 파일 `waiting_user`(formats.md 3절)가 비어 있지 않으면 '사용자 할 일 대기'.
    kind별 시작 조건: 흐름별 검증·전체 검증·마무리. 끝은 devflow_lib.settled(완료·보류·백로그·보류에 막힌 대기)."""
    why = []
    kind, flow = t.get("kind"), t.get("flow", "")
    if holds is None:
        holds = devflow_lib.hold_blockers(tasks)
    if writes(t) and flow:
        if any(o.get("flow") == flow and writes(o) and o.get("status") in kinds.BUSY_STATUSES
               for o in tasks.values() if o is not t):
            why.append("폴더 사용 중")
        if flows.get(flow, {}).get("sync_pending"):
            why.append("받아오기 먼저")
        waiting = [x for x in commit_waiting(tasks, flow) if x != t.get("id")]
        if waiting:
            why.append("커밋 대기: " + ", ".join(waiting))
        busy_flows = {o.get("flow") for o in tasks.values()
                      if writes(o) and o.get("status") in kinds.BUSY_STATUSES and o.get("flow")}
        if flow not in busy_flows and len(busy_flows) >= cap:
            why.append("흐름 상한 {}".format(cap))
    if kind in ("flow-verify", "reverify") and flow and flows.get(flow, {}).get("sync_pending"):
        why.append("받아오기 먼저")
    if kind == "flow-verify" and flow:
        later = downstream(tasks, {t.get("id")}, ("wrap-up", "deploy-plan", "deploy-exec", "full-verify"))
        code = [o for o in tasks.values() if o is not t and o.get("flow") == flow
                and (o.get("kind") in kinds.AUTO_DEPEND_KINDS or devflow_lib.is_code_change(o)) and o["id"] not in later]
        left = [o["id"] for o in code if not devflow_lib.settled(o, tasks, holds)]
        if left:
            why.append("흐름 코드 task 남음: " + ", ".join(left))
        held = [o["id"] for o in code if o.get("kind") == "implementation"
                and (o.get("status") == "보류" or o["id"] in holds)]
        if held and not left and str(t.get("partial_flow", "")).strip().lower() not in ("true", "예"):
            why.append("보류된 구현 있음: {} — 묻기: (가) 이 흐름 보류 / (나) 남은 것만 검증(--record 뒤 partial_flow=true)".format(
                ", ".join(held)))
    if kind == "full-verify":
        left = [n for n, f in round_flows(tasks, flows, "feature").items() if not flow_done(tasks, n, f, holds)]
        if left:
            why.append("안 합친 흐름: " + ", ".join(left))
    if kind == "wrap-up":
        later = downstream(tasks, {t.get("id")}, ("deploy-plan", "deploy-exec"))
        # 다른 마무리(원인 분석이 따로 낸 마무리 행)는 기다리지 않는다. 서로 기다리면 둘 다 못 뜬다
        left = [o["id"] for o in tasks.values() if o is not t and o.get("kind") not in ("deploy-plan", "deploy-exec", "wrap-up")
                and o["id"] not in later and not devflow_lib.settled(o, tasks, holds)]
        if left:
            why.append("끝나지 않은 task: " + ", ".join(left))
        busy = [o["id"] for o in tasks.values() if o is not t and o.get("kind") == "wrap-up"
                and o.get("status") in ("진행", "자체검증", "승인대기")]
        if busy:   # 다른 마무리는 기다리지 않되 함께 돌지는 않는다(같은 통합 폴더 문서를 고친다)
            why.append("다른 마무리 진행 중: " + ", ".join(busy))
        fx = [n for n, f in round_flows(tasks, flows, "fixes").items()
              if not flow_done(tasks, n, f, holds) and any(
                  o.get("flow") == n and o.get("kind") in kinds.AUTO_DEPEND_KINDS and o.get("status") == kinds.DONE
                  for o in tasks.values())]
        if fx:
            why.append("수정 흐름 안 합침: " + ", ".join(fx))
    if t.get("waiting_user"):
        why.append("사용자 할 일 대기")
    return why


def unreverified_fixes(tasks):
    """검증 task에서 나온 수정(부모나 cause_task가 검증 task) 가운데 어느 재검증의 depends_on에도 없는 것."""
    covered = set()
    for o in tasks.values():
        if o.get("kind") == "reverify":
            covered.update(o.get("depends_on", []))
    out = []
    for o in tasks.values():
        if o.get("kind") != "fix" or o.get("status") in ("백로그", "보류") or o["id"] in covered:
            continue
        src = [x for x in (o.get("parent", ""), str(o.get("cause_task", "")).strip()) if x in tasks]
        if any(tasks[x].get("kind") in kinds.VERIFY_KINDS for x in src):
            out.append(o["id"])
    return out


def mergeable_flows(tasks, flows, run_dir, holds):
    """합칠 수 있는 흐름(references/kinds/merge.md 「합치는 조건」을 상태로): 흐름이 둘 이상인 실행에서
    기능 흐름은 흐름별 검증 완료 + 그 흐름의 수정·재검증이 모두 끝(settled) + 재검증 없는 수정 없음,
    수정 흐름은 전체 검증이 모두 끝 + 끝난 수정이 있음 + 재검증 없는 수정 없음.
    공통: 받아오기 없음, depends_on_flows가 모두 합쳐짐, 다른 합치기가 진행·승인대기가 아님, 그 흐름의 합치기 task가 아직 없음."""
    ib = str(devflow_lib.run_meta(run_dir).get("integration_branch", "") or "").strip()
    if not ib or ib.startswith("("):
        return []
    if any(o.get("kind") == "merge" and o.get("status") in ("진행", "자체검증", "승인대기") for o in tasks.values()):
        return []
    nore = set(unreverified_fixes(tasks))
    rnd = flows.get("_round", 1)
    out = []
    for n, f in flow_items(flows):
        role = f.get("role", devflow_lib.flow_role(n, f))
        if role not in ("feature", "fixes") or f.get("round", 1) != rnd:
            continue
        if f.get("status") in ("합쳐짐", "폴더 지움", "폴더 없음") or f.get("sync_pending"):
            continue
        if any(flows.get(d, {}).get("status") != "합쳐짐" for d in f.get("depends_on_flows", [])):
            continue
        mine = [o for o in tasks.values() if o.get("flow") == n]
        if any(o.get("kind") == "merge" and o.get("status") != "보류" for o in mine):
            continue
        fixes = [o for o in mine if o.get("kind") in ("fix", "reverify")]
        if not all(devflow_lib.settled(o, tasks, holds) for o in fixes) or any(o["id"] in nore for o in fixes):
            continue
        if role == "feature":
            if not any(o.get("kind") == "flow-verify" and o.get("status") == kinds.DONE for o in mine):
                continue
        else:
            fv = [o for o in tasks.values() if o.get("kind") == "full-verify"]
            if not fv or not all(devflow_lib.settled(o, tasks, holds) for o in fv):
                continue
            if not any(o.get("kind") == "fix" and o.get("status") == kinds.DONE for o in mine):
                continue
        out.append(n)
    return out


def print_ready(tasks, run_dir=None):
    flows = load_flows(run_dir) if run_dir else {}
    cap = flow_cap(run_dir) if run_dir else kinds.RUN_DEFAULTS["동시에 도는 흐름"]
    holds = devflow_lib.hold_blockers(tasks)
    ready, held = [], []
    for t in tasks.values():
        if not is_ready(tasks, t, holds):
            continue
        why = start_blocks(tasks, flows, cap, t, holds)
        (held if why else ready).append((t, why))
    print("지금 시작할 수 있는 task {}개".format(len(ready)))
    for t, _ in ready:
        mark = " (코드 폴더 필요: 흐름 {})".format(t.get("flow", "")) if t.get("kind") in kinds.CODE_WRITER_KINDS else ""
        print("- {} {} [{}]{}".format(t["id"], t.get("title", ""), t.get("kind", ""), mark))
    if held:
        print("의존은 풀렸지만 지금은 못 띄움 {}개(공유 자원 잠금은 메인이 따로 본다)".format(len(held)))
        for t, why in held:
            print("- {} {} [{}] ({})".format(t["id"], t.get("title", ""), t.get("kind", ""), ", ".join(why)))
    print_state_lines(tasks, flows, run_dir, holds, ready)


def print_state_lines(tasks, flows, run_dir, holds, ready):
    """합칠 수 있는 흐름·재검증 없는 수정, 받아오기 보류, 보류에 막힌 대기와 끝 질문. 해당 없으면 찍지 않는다."""
    if run_dir:
        can = mergeable_flows(tasks, flows, run_dir, holds)
        if can:
            print("합칠 수 있는 흐름: {} (합치기 task를 만든다, references/kinds/merge.md)".format(", ".join(can)))
    nore = unreverified_fixes(tasks)
    if nore:
        print("재검증 없는 수정: {} (재검증 task를 만든다, SKILL.md 5절)".format(", ".join(nore)))
    for n, f in flow_items(flows):
        waiting = commit_waiting(tasks, n)
        if f.get("sync_pending") and waiting:
            print("받아오기 보류(커밋 대기): {} — {}가 통과 못 한 채 승인대기".format(n, ", ".join(waiting)))
    if holds:
        print("보류에 막힌 대기 task {}개: {}".format(len(holds), ", ".join(
            "{}(← {})".format(k, ", ".join(v)) for k, v in sorted(holds.items()))))
    active = [o for o in tasks.values() if o.get("status") in ("진행", "자체검증", "승인대기")]
    left = [o for o in tasks.values() if o.get("status") == "대기" and not devflow_lib.settled(o, tasks, holds)]
    shelved = [o["id"] for o in tasks.values() if o.get("status") == "보류"]
    if not ready and not active and not left and holds:
        print("! 끝 질문: 남은 task가 모두 보류에 막혔다(보류 {}) — 보류 목록을 보이고 끝낼지 묻는다(SKILL.md 9절)".format(
            ", ".join(shelved)))


def print_record_findings(tasks):
    """기록 점검(devflow_lib.record_check)에서 점검 확인이 없는 걸림. 메인은 걸린 task의 승인 화면(screen.py)에서 사람에게 보인 뒤
    `task_set.py {id} --record "점검 확인|{코드}|{원문}"`을 남긴다. 걸림이 없으면 아무것도 찍지 않는다."""
    for problem in devflow_lib.agent_def_problems():
        # 규칙 판 1 판정자 정의가 없으면 새 task의 자체 검증 뒤 전이가 모두 거부된다(SKILL.md 0절 1)
        print("! 에이전트 정의: {} — 판정자 정의를 고치기 전에는 task를 띄우지 않는다".format(problem))
    found = devflow_lib.record_findings(tasks)
    if not found:
        return
    print("! 기록 점검 {}건(점검 확인 없음)".format(len(found)))
    for tid, code, msg, sub in found:
        print("! 기록 점검: {} {}: {}".format(tid, code, msg))
        for s in sub:
            print("    " + s)


def print_cycles(tasks):
    cycles = find_cycles(tasks)
    if not cycles:
        print("의존 고리 없음")
        return 0
    print("의존 고리 {}개".format(len(cycles)))
    for c in cycles:
        print("- " + " → ".join(c))
    return 3


def print_log(tasks):
    rows = []
    for tid, t in tasks.items():
        for line in t["_sections"].get("승인 기록", "").splitlines():
            line = line.strip()
            if line.startswith("- "):
                rows.append((line[2:], tid))
    for line, tid in sorted(rows):
        print("{} | {}".format(tid, line))
    if not rows:
        print("승인 기록 없음")


STALE_MIN = 30   # 결과 파일이 이만큼(분) 넘게 멈췄으면 기다림 / 멈추고 이어 씀을 사용자에게 묻는다(SKILL.md 0절 4)


def _epoch(text):
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(str(text or "").strip(), fmt).timestamp()
        except ValueError:
            pass
    return None


def last_output(run_dir, t):
    """에이전트가 쓰는 파일 가운데 가장 늦은 수정 (epoch, 경로). 결과 파일(result.md·judge*.md·logs/·revised/),
    정본을 쓰는 task면 시작 뒤 고친 spec/·design/, 코드 task면 코드 폴더의 바뀐 파일(git status). 없으면 (None, None)."""
    cands = []
    d = t["_dir"]
    for root, _dirs, files in os.walk(d):
        top = os.path.relpath(root, d) == "."
        cands += [os.path.join(root, f) for f in files if not top or f == "result.md" or f.startswith("judge")]
    started = _epoch(t.get("started"))
    if run_dir and t.get("kind") in kinds.CANON_WRITER_KINDS and started:
        for sub in kinds.CANON_DIRS:
            for root, _dirs, files in os.walk(os.path.join(run_dir, sub)):
                cands += [p for p in (os.path.join(root, f) for f in files) if os.path.getmtime(p) >= started]
    folder = flows_dir(run_dir, t.get("flow", "")) if run_dir and writes(t) else None
    if folder:
        import subprocess
        try:
            out = subprocess.run(["git", "-C", folder, "status", "--porcelain", "-uall"], capture_output=True, text=True,
                                 encoding="utf-8", timeout=20).stdout
            cands += [os.path.join(folder, line[3:].strip().strip('"')) for line in out.splitlines() if len(line) > 3]
        except (OSError, subprocess.SubprocessError):
            pass
    best = (None, None)
    for p in cands:
        if os.path.isfile(p):
            m = os.path.getmtime(p)
            if best[0] is None or m > best[0]:
                best = (m, p)
    return best


def flows_dir(run_dir, flow):
    meta = load_flows(run_dir).get(flow) if flow else None
    d = str((meta or {}).get("dir", "") or "").strip()
    return d if d and os.path.isdir(d) else None


def agent_note(run_dir, t, now):
    """`running_agent`가 있는 task의 재개 줄: 살아 있는지 확인하라는 말과 결과 파일의 마지막 수정 시각."""
    from datetime import datetime
    when, path = last_output(run_dir, t)
    ref = when or _epoch(t.get("started"))
    if when:
        where = os.path.relpath(path, run_dir) if run_dir and os.path.abspath(path).startswith(os.path.abspath(run_dir)) else path
        last = "결과 파일 마지막 수정 {} {}".format(datetime.fromtimestamp(when).strftime("%Y-%m-%d %H:%M:%S"), where)
    else:
        last = "결과 파일 없음(시작 {})".format(t.get("started") or "-")
    note = "실행 중 에이전트 {} (살아 있는지 확인. {})".format(t.get("running_agent"), last)
    if ref and now - ref > STALE_MIN * 60:
        note += " — {}분 넘게 멈춤: 에이전트 목록에 있어도 기다림 / 멈추고 이어 씀을 사용자에게 묻는다".format(STALE_MIN)
    return note


def print_resume(tasks, run_dir=None, now=None):
    import time
    now = now or time.time()
    print("재개 때 볼 것")
    for tid, t in tasks.items():
        notes = []
        if t.get("status") in ("진행", "자체검증", "승인대기"):
            notes.append("상태 " + t.get("status"))
        if t.get("running_agent"):
            notes.append(agent_note(run_dir, t, now))
        if t.get("external_progress"):
            notes.append("외부 작업 진행: {} (실행 기록을 보여 주고 먼저 묻는다)".format(t.get("external_progress")))
        if str(t.get("awaiting_answer_apply", "")).lower() in ("true", "예"):
            notes.append("답 반영 대기")
        if notes:
            print("- {} {}: {}".format(tid, t.get("title", ""), " / ".join(notes)))


def print_backlog(workspace):
    origins = set()
    backlog = []
    for name in sorted(os.listdir(workspace)):
        run_dir = os.path.join(workspace, name)
        if not os.path.isfile(os.path.join(run_dir, "run.md")):
            continue
        for tid, t in devflow_lib.load_tasks(run_dir).items():
            if t.get("origin"):
                origins.add(os.path.normcase(os.path.normpath(t["origin"])))
            if t.get("status") == "백로그":
                backlog.append((name, tid, t))
    left = [(r, tid, t) for r, tid, t in backlog
            if os.path.normcase(os.path.normpath(t["_dir"])) not in origins]
    print("남은 백로그 {}개".format(len(left)))
    for r, tid, t in left:
        print("- {} / {} {} [{}] {}".format(r, tid, t.get("title", ""), t.get("kind", ""), t["_dir"]))


# ---------------------------------------------------------------- 진행 상황 그림(--ascii, board_ascii.py)

# 상태 글자 `kinds.STATUS_GLYPH`, 종류 글자 `kinds.glyph`, 범례 `kinds.LEGEND`(등록표). 모르는 값은 `?`.
PER_LINE = 6


def pad(text, width):
    """한글처럼 화면에서 두 칸을 쓰는 글자를 세어 폭을 맞춘다."""
    import unicodedata
    out, used = "", 0
    for ch in text:
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + w > width:
            break
        out, used = out + ch, used + w
    return out + " " * (width - used)


def cell(t):
    kind = t.get("kind")
    letter = kinds.glyph(kind) if kind in kinds.KINDS else "?"
    return "{}[{}]{}".format(letter, kinds.STATUS_GLYPH.get(t.get("status"), "?"), t["id"])


def lanes(tasks, flows):
    order, rows = [], {}
    for tid, t in tasks.items():
        key = t.get("flow") or t.get("block") or "기타"
        if key not in rows:
            rows[key] = []
            order.append(key)
        rows[key].append(t)
    return [(k, rows[k]) for k in order]


def render_ascii(run_dir, tasks=None):
    """진행 상황 그림(`--ascii`, board_ascii.py). 흐름별 한 줄씩 상태 기호로 그린다."""
    tasks = tasks if tasks is not None else devflow_lib.load_tasks(run_dir)
    flows = load_flows(run_dir)
    cap = flow_cap(run_dir)
    count = {}
    for t in tasks.values():
        count[t.get("status", "?")] = count.get(t.get("status", "?"), 0) + 1
    name = os.path.basename(os.path.normpath(run_dir))
    out = []
    bar = "=" * 72
    out.append(bar)
    out.append(" {} | 동시 흐름 상한 {} | task {} ({})".format(
        name, cap, len(tasks), " · ".join("{} {}".format(k, v) for k, v in sorted(count.items(), key=lambda kv: -kv[1]))))
    out.append(bar)
    for key, row in lanes(tasks, flows):
        f = flows.get(key)
        head = " " + pad(key, 14)
        tags = []
        if f:
            tags.append(f.get("status", ""))
            if f.get("branched_from"):
                tags.append("<- " + f["branched_from"])
            if f.get("sync_pending"):
                tags.append("받아오기 대기 {}".format(len(f["sync_pending"])))
        cells = [cell(t) for t in row]
        lines = [" ─ ".join(cells[i:i + PER_LINE]) for i in range(0, len(cells), PER_LINE)] or ["(없음)"]
        out.append(head + lines[0] + ("   ({})".format(", ".join(x for x in tags if x)) if any(tags) else ""))
        for more in lines[1:]:
            out.append(" " * 15 + more)
    out.append("-" * 72)
    q = queue(tasks)
    out.append(" 승인 대기 {}: {}".format(len(q), ", ".join("{} {}".format(t["id"], t.get("title", "")[:24]) for t in q[:3]) or "-"))
    running = ["{}({})".format(t.get("running_agent"), t["id"]) for t in tasks.values() if t.get("running_agent")]
    out.append(" 도는 에이전트: {}".format(", ".join(running) or "-"))
    ready, held = [], []
    for t in tasks.values():
        if is_ready(tasks, t):
            why = start_blocks(tasks, flows, cap, t)
            (held if why else ready).append("{}{}".format(t["id"], "({})".format(", ".join(why)) if why else ""))
    out.append(" 시작 가능: {}{}".format(", ".join(ready) or "-", "   못 띄움: " + ", ".join(held) if held else ""))
    out.append(" " + kinds.LEGEND)
    return "\n".join(out)


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    flag = argv[2] if len(argv) > 2 else ""
    if flag == "--backlog":
        print_backlog(target)
        return 0
    tasks = devflow_lib.load_tasks(target)
    if flag == "--queue":
        print_queue(tasks)
    elif flag == "--ready":
        print_ready(tasks, target)
        print_record_findings(tasks)
        print()
        print(devflow_lib.version_line(target))
        print(devflow_lib.main_context_line())
    elif flag == "--ascii":
        print(render_ascii(target, tasks))
    elif flag == "--cycles":
        return print_cycles(tasks)
    elif flag == "--log":
        print_log(tasks)
    elif flag == "--resume":
        # --now "YYYY-MM-DD HH:MM[:SS]": 마른 시험에서 그때의 경과를 다시 보려고(기본은 지금). 못 읽으면 2
        at = None
        if "--now" in argv:
            raw = argv[argv.index("--now") + 1] if argv.index("--now") + 1 < len(argv) else ""
            at = _epoch(raw)
            if at is None:
                print("--now를 읽지 못함: '{}' (YYYY-MM-DD HH:MM[:SS])".format(raw))
                return 2
        print_resume(tasks, target, at)
    else:
        print_table(tasks)
        print()
        print_queue(tasks)
        print()
        print_ready(tasks, target)
        print()
        return print_cycles(tasks)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
