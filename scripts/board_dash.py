"""진행 대시보드 판정: 작업 폴더에서 지금 세션의 실행을 골라, 띠·패널이 함께 쓸 판정을 JSON 하나로 낸다.
시작 판단(시작 가능·못 띄움·승인 대기 순서)은 board.py 함수를 그대로 부른다. 읽기만 한다.

사용:
  python board_dash.py {작업 폴더} [--session ID] [--now "YYYY-MM-DD HH:MM"] [--shown 실행이름]
    {작업 폴더}  `_workspace`를 품은 폴더. 실행 후보는 `_workspace\\*\\run.md`(한 단계 아래만)
    --session    지금 세션의 id. 없거나 빈 값이면 "알 수 없음"
    --now        판정의 "지금". 없으면 이 컴퓨터의 지역 시각
    --shown      직전에 보이던 실행 폴더 이름(그 run.md를 읽지 못하면 그 실행을 계속 고름)
  표준 출력에 UTF-8 JSON 한 객체, 종료 0. 인자가 없거나 꼴이 틀리면 이 글을 내고 종료 2.

JSON (schema 1):
  schema 1 / now "YYYY-MM-DD HH:MM" / workdir / session (id 또는 null)
  message   null | "이 세션이 진행하는 실행 없음" | "세션 id를 알 수 없어 실행을 고르지 못함"
  run       null | {name, dir, status, run_md_unreadable, flow_cap}
  tasks     [{id, title, kind, status, flow, block, group, parent, depends_on,
              class ("remaining" | "folded"), start ("ready" | "held" | "undecidable" | null),
              reason_text (held: 못 띄움 이유를 ", "로 이은 것 / undecidable: "읽지 못한 task에 의존" | "flow.md 읽지 못함"),
              elapsed (null | {kind: "approval" | "progress" | "start_wait", text: "1시간 35분" | "?"}),
              waiting_user, running_agent, external_progress,
              approval_requested, started, created, approved, n_decide}]   머리 파일 값 그대로(없으면 "")
  unreadable [{id (폴더 이름), why ("UTF-8 아님" | "머리 없음" | "status 값")}]
  flows     [{name, status, sync_pending, depends_on_flows, unreadable}]
  ready [id] / held [{id, reason_text}] / undecidable [{id, reason_text}] / queue [id] (board.queue 순서)
  counts    {by_status {상태: 수}, remaining, folded, unreadable, approval, waiting_user, running_agent, external_progress}
  folded_by_group {묶음 키(flow → block → "기타"): {상태: 수}}
  unclean   [{id, keys}]   접힌 task에 남은 running_agent·external_progress·waiting_user
  run이 null이면 목록은 비고 수는 0.
"""
import json
import os
import re
import sys
from datetime import datetime

import board
import devflow_lib
import kinds

NO_RUN = "이 세션이 진행하는 실행 없음"
NO_SESSION = "세션 id를 알 수 없어 실행을 고르지 못함"
DEP_UNREADABLE = "읽지 못한 task에 의존"
FLOW_UNREADABLE = "flow.md 읽지 못함"
COUNTED = ("running_agent", "external_progress", "waiting_user")
SHOWN_KEYS = ("waiting_user", "running_agent", "external_progress",
              "approval_requested", "started", "created", "approved", "n_decide")
TIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
TIME_FMT = "%Y-%m-%d %H:%M"


def head(text):
    """머리 줄 목록. 첫 줄이 `---`가 아니거나 닫는 `---`가 없으면 None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def read_head(path):
    """(머리 meta, 못 읽은 이유). 이유는 "UTF-8 아님" / "머리 없음" / None."""
    try:
        text = devflow_lib.read_text(path)
    except (OSError, UnicodeDecodeError):
        return None, "UTF-8 아님"
    lines = head(text)
    if lines is None:
        return None, "머리 없음"
    return devflow_lib.parse_meta(lines), None


def pick_run(workdir, session, shown):
    """(실행 폴더, 실행 이름, run.md meta 또는 None). 못 고르면 (None, None, None)."""
    base = os.path.join(workdir, "_workspace")
    if not os.path.isdir(base):
        return None, None, None
    found = []
    for name in sorted(os.listdir(base)):
        run_md = os.path.join(base, name, "run.md")
        if not os.path.isfile(run_md):
            continue
        meta, why = read_head(run_md)
        if why:
            if shown and name == shown:
                return os.path.join(base, name), name, None
            continue
        if meta.get("kind") == "devflow-harness" and str(meta.get("session_id", "")) == session:
            found.append((name, meta, os.path.getmtime(run_md)))
    if not found:
        return None, None, None
    going = [f for f in found if f[1].get("status") == "진행"] or found
    name, meta, _ = max(going, key=lambda f: f[2])
    return os.path.join(base, name), name, meta


def load_tasks(run_dir):
    """(task 사전, 읽지 못한 목록). 사전은 devflow_lib.load_tasks와 같은 키와 순서(읽힌 것만)."""
    tasks, unreadable = {}, []
    tasks_dir = os.path.join(run_dir, "tasks")
    if not os.path.isdir(tasks_dir):
        return tasks, unreadable
    for name in sorted(os.listdir(tasks_dir)):
        task_md = os.path.join(tasks_dir, name, "task.md")
        if not os.path.isfile(task_md):
            continue
        _, why = read_head(task_md)
        if not why:
            try:
                t = devflow_lib.load_task(task_md)
            except (OSError, UnicodeDecodeError):
                why = "UTF-8 아님"
            else:
                if t.get("status") not in kinds.STATUSES:
                    why = "status 값"
        if why:
            unreadable.append({"id": name, "why": why})
            continue
        t.setdefault("id", name)
        tasks[t["id"]] = t
    return tasks, unreadable


def load_flows(run_dir):
    """(flows 사전, 못 읽은 흐름 폴더 이름 목록, 폴더 순서의 (이름, meta 또는 None) 목록)."""
    base = os.path.join(run_dir, "flows")
    order, bad = [], []
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            p = os.path.join(base, name, "flow.md")
            if os.path.isfile(p):
                meta, why = read_head(p)
                order.append((name, meta))
                if why:
                    bad.append(name)
    flows = None
    if not bad:
        try:
            flows = board.load_flows(run_dir)
        except (OSError, UnicodeDecodeError):
            flows = None
    if flows is None:
        flows = {}
        for name, meta in order:
            if meta is None:
                continue
            for key in ("depends_on_flows", "sync_pending"):   # board.load_flows와 같은 규칙
                v = meta.get(key, [])
                meta[key] = v if isinstance(v, list) else devflow_lib.parse_value("x", "[" + v + "]")
            flows[meta.get("flow", name)] = meta
    listed = []
    for name, meta in order:
        if meta is None:
            listed.append({"name": name, "status": "", "sync_pending": [], "depends_on_flows": [], "unreadable": True})
            continue
        key = meta.get("flow", name)
        f = flows.get(key, meta)
        listed.append({"name": key, "status": f.get("status", ""), "sync_pending": f.get("sync_pending", []),
                       "depends_on_flows": f.get("depends_on_flows", []), "unreadable": False})
    return flows, bad, listed


def parse_time(value):
    if not isinstance(value, str) or not TIME.match(value):
        return None
    try:
        return datetime.strptime(value, TIME_FMT)
    except ValueError:
        return None


def span(start, now):
    """경과 문자열. 시각이 없거나 꼴이 틀리거나 지금보다 뒤면 "?"."""
    if start is None or start > now:
        return "?"
    minutes = int((now - start).total_seconds() // 60)
    if minutes < 60:
        return "{}분".format(minutes)
    if minutes < 24 * 60:
        return "{}시간 {}분".format(minutes // 60, minutes % 60)
    return "{}일 {}시간".format(minutes // (24 * 60), minutes % (24 * 60) // 60)


def released_at(tasks, t):
    """의존이 풀린 시각(datetime) 또는 None("?")."""
    refs = [r for r in [t.get("parent", "")] + list(t.get("depends_on", [])) if r and r in tasks]
    created = t.get("created", "")
    times = []
    for r in refs:
        at = parse_time(tasks[r].get("approved", ""))
        if at is None:
            return None
        times.append(at)
    if created or not refs:
        at = parse_time(created)
        if at is None:
            return None
        times.append(at)
    return max(times)


def elapsed(tasks, t, now):
    status = t.get("status")
    if status == "승인대기":
        return {"kind": "approval", "text": span(parse_time(t.get("approval_requested", "")), now)}
    if status in ("진행", "자체검증"):
        return {"kind": "progress", "text": span(parse_time(t.get("started", "")), now)}
    if status == "대기" and t["_start"] in ("ready", "held"):
        return {"kind": "start_wait", "text": span(released_at(tasks, t), now)}
    return None


def empty_counts():
    return {"by_status": {s: 0 for s in kinds.OPEN_STATUSES + kinds.CLOSED_STATUSES}, "remaining": 0, "folded": 0, "unreadable": 0,
            "approval": 0, "waiting_user": 0, "running_agent": 0, "external_progress": 0}


def judge(workdir, session, now, shown):
    session = (session or "").strip() or None
    out = {"schema": 1, "now": now.strftime(TIME_FMT), "workdir": workdir, "session": session,
           "message": None, "run": None, "tasks": [], "unreadable": [], "flows": [],
           "ready": [], "held": [], "undecidable": [], "queue": [],
           "counts": empty_counts(), "folded_by_group": {}, "unclean": []}
    if session is None:
        out["message"] = NO_SESSION
        return out
    run_dir, name, run_meta = pick_run(workdir, session, shown)
    if run_dir is None:
        out["message"] = NO_RUN
        return out
    cap = 2
    if run_meta is not None:
        try:
            cap = board.flow_cap(run_dir)
        except UnicodeDecodeError:
            cap = 2
    out["run"] = {"name": name, "dir": run_dir, "status": run_meta.get("status", "") if run_meta else "",
                  "run_md_unreadable": run_meta is None, "flow_cap": cap}

    tasks, unreadable = load_tasks(run_dir)
    flows, bad_flows, listed_flows = load_flows(run_dir)
    out["unreadable"] = unreadable
    out["flows"] = listed_flows
    bad_tasks = {u["id"] for u in unreadable}

    for t in tasks.values():
        t["_start"], t["_reason"] = None, ""
        if t.get("status") != "대기":
            continue
        refs = [t.get("parent", "")] + list(t.get("depends_on", []))
        if any(r in bad_tasks for r in refs if r):
            t["_start"], t["_reason"] = "undecidable", DEP_UNREADABLE
        elif not board.is_ready(tasks, t):
            continue
        elif (t.get("kind") in kinds.CODE_DIR_KINDS and t.get("flow", "") in bad_flows) or \
                (t.get("kind") == "full-verify" and bad_flows):
            t["_start"], t["_reason"] = "undecidable", FLOW_UNREADABLE
        else:
            why = board.start_blocks(tasks, flows, cap, t)
            t["_start"], t["_reason"] = ("held", ", ".join(why)) if why else ("ready", "")

    counts = out["counts"]
    counts["unreadable"] = len(unreadable)
    for t in tasks.values():
        status = t.get("status")
        cls = "remaining" if status in kinds.OPEN_STATUSES else "folded"
        group = t.get("flow") or t.get("block") or "기타"
        row = {"id": t["id"], "title": t.get("title", ""), "kind": t.get("kind", ""), "status": status,
               "flow": t.get("flow", ""), "block": t.get("block", ""), "group": group,
               "parent": t.get("parent", ""), "depends_on": t.get("depends_on", []),
               "class": cls, "start": t["_start"], "reason_text": t["_reason"],
               "elapsed": elapsed(tasks, t, now)}
        for key in SHOWN_KEYS:
            row[key] = t.get(key, "")
        out["tasks"].append(row)
        counts["by_status"][status] += 1
        counts[cls] += 1
        if status == "승인대기":
            counts["approval"] += 1
        if cls == "remaining":
            for key in COUNTED:
                if t.get(key):
                    counts[key] += 1
        else:
            by = out["folded_by_group"].setdefault(group, {})
            by[status] = by.get(status, 0) + 1
            left = [key for key in COUNTED if t.get(key)]
            if left:
                out["unclean"].append({"id": t["id"], "keys": left})
        if t["_start"] == "ready":
            out["ready"].append(t["id"])
        elif t["_start"] in ("held", "undecidable"):
            out[t["_start"]].append({"id": t["id"], "reason_text": t["_reason"]})
    out["queue"] = [t["id"] for t in board.queue(tasks)]
    return out


def parse_args(argv):
    """(작업 폴더, session, now, shown) 또는 None(인자 오류)."""
    if len(argv) < 2 or argv[1].startswith("--"):
        return None
    opts = {"--session": None, "--now": None, "--shown": None}
    rest = argv[2:]
    if len(rest) % 2:
        return None
    for flag, value in zip(rest[::2], rest[1::2]):
        if flag not in opts:
            return None
        opts[flag] = value
    if opts["--now"] is None:
        now = datetime.now()
    else:
        now = parse_time(opts["--now"])
        if now is None:
            return None
    return argv[1], opts["--session"], now, opts["--shown"] or None


def main(argv):
    devflow_lib.utf8_stdout()
    args = parse_args(argv)
    if args is None:
        print(__doc__)
        return 2
    print(json.dumps(judge(*args), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
