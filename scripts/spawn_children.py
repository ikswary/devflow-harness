"""부모 task의 result.md 「자식 목록」 절에서 자식 task의 머리 파일을 만든다.

메인이 손으로 옮겨 적지 않기 위한 스크립트다. 부모가 승인된 뒤에 돌린다.

사용:
  python spawn_children.py {실행 폴더} {부모 task id} [--dry-run] [--depends-on T012] [--now "시각"]
                           [--option 묶음/안,…] [--backlog-option 묶음/안,…] [--replace] [--over-cap [백로그]]

- 자식 목록의 형식은 formats.md 「자식 목록」을 따른다.
- `depends_on`에 형제의 제목을 적으면 그 형제의 새 id로 바꾼다. 이미 있는 task id(T숫자)는 그대로 둔다.
- 같은 흐름의 코드 task(implementation, fix)는 앞 형제에 자동으로 의존한다(한 흐름의 코드 task는 차례로 진행).
- --depends-on: 모든 자식에 공통으로 더할 의존(예: 답을 반영하는 변경 task).
- 자식마다 `criteria.orig.md`(만들 때의 판정 기준)를 함께 쓴다.
- 코드 task 행(백로그·고르지 않은 안 밖)의 흐름에 flow.md가 없으면 함께 만든다(`status: 폴더 없음`, `role`, `round`).
  메인은 폴더를 만들 때 branch·dir·status를 채운다.
- 제목이 `[백로그]`로 시작하는 행은 `status: 백로그`로 만든다.
- --option 묶음/안,…: 행 키 `- option: 수정안/가`(여럿이면 `배포/나, 배포/다`)가 있는 행 가운데 고른 안이 하나라도 든 행과
  option 키가 없는 행만 만든다. 한 묶음에서 여럿을 골라도 된다. 받아들임(만들 행 없음)은 `V-02/없음`.
  option 행이 있는 묶음을 고르지 않으면 종료 코드 3. option 키 없는 옛 `[안 …]` 제목 행은 전부 만들고 코드 차례에 끼우지 않는다.
- --backlog-option 묶음/안,…: 사용자가 백로그로 남기라고 답한 안. 그 안이 든 행(고른 안이 함께 들지 않은 것)을 `백로그`로
  만든다(코드 차례 밖). 그 밖의 고르지 않은 안의 행은 만들지 않는다. 이 옵션의 묶음도 고른 묶음으로 센다.
- --replace: 변경 task의 자식 목록을 제목과 flow가 함께 같은 기존 task와 짝짓는다. 짝이 `대기`면 id·parent·created·status·
  승인 기록을 두고 본문 절·depends_on·closes_ac·partial_ac·difficulty·one_line만 바꾼다(depends_on은 행의 의존과 같은 흐름
  차례에, 원래 의존 가운데 아직 `완료`가 아닌 것을 남긴다). 짝이 대기가 아니거나 둘이면 종료 코드 3. 짝 없는 행은 새 task로
  만들고, 짝 없는 기존 형제 task는 출력에 찍는다.
- 수정 세대: 부모가 재검증이면 수정 행의 `fix_generation`은 그 재검증이 의존하는 수정의 최대 세대 + 1(흐름별·전체 검증은 0).
  run.md 「이번 실행의 값」 수정 세대 상한 이상이면 만들지 않고 종료 코드 3. --over-cap이면 만들고, --over-cap 백로그면
  수정·재검증 행을 `백로그`로 만든다. 상한에 닿지 않았는데 --over-cap을 주면 종료 코드 3.
- `kind: change` 행의 「건드릴 파일」에 정본(spec\\·design\\, 고친 판 revised\\) 밖 경로가 있으면 거부(코드를 고치는 변경은 fix).

종료 코드: 0 / 2 사용법(같은 옵션을 두 번 주면 2. 값은 쉼표로) / 3 거부(머리 파일을 만들지 않음)
"""
import os
import re
import sys

import devflow_lib
import kinds

OPTION_RE = re.compile(r"^[^/\s,]+/[^/\s,]+$")


def parse_children(result_text):
    top = devflow_lib.sections(result_text, level=2)
    block = top.get("자식 목록")
    if block is None:
        return None, []
    criterion = ""
    for line in block.splitlines():
        if line.startswith("나눈 기준:"):
            criterion = line.split(":", 1)[1].strip()
    children = []
    current = None
    sub = None
    for line in block.splitlines():
        if line.startswith("### 자식:"):
            current = {"title": line.split(":", 1)[1].strip(), "meta": {}, "body": {}}
            children.append(current)
            sub = None
        elif current is None:
            continue
        elif line.startswith("#### "):
            sub = line[5:].strip()
            current["body"][sub] = []
        elif sub is not None:
            current["body"][sub].append(line)
        elif line.startswith("- ") and ":" in line:
            key, raw = line[2:].split(":", 1)
            current["meta"][key.strip()] = raw.strip()
    for c in children:
        c["body"] = {k: "\n".join(v).strip() for k, v in c["body"].items()}
    return criterion, children


def split_list(raw):
    return [x.strip() for x in raw.split(",") if x.strip()]


def row_options(child):
    return split_list(child["meta"].get("option", ""))


def parked(child):
    """바로 돌지 않는 행: `[백로그]` 행과 option 키 없는 옛 `[안 …]` 행(고른 안인지 스크립트가 모른다)."""
    title = child["title"].lstrip()
    return title.startswith("[백로그]") or (title.startswith("[안") and not row_options(child))


def render(tid, parent_id, child, depends, now, status="대기", generation=0):
    meta = child["meta"]
    kind = meta.get("kind", "")
    block = meta.get("block", "") or (kinds.block_of(kind) if kind in kinds.KINDS else "")
    lines = [
        "---",
        "id: " + tid,
        "kind: " + kind,
        "block: " + block,
        "title: " + child["title"],
        "status: " + status,
        "parent: " + parent_id,
        "depends_on: " + devflow_lib.format_meta_value(depends),
        "flow: " + meta.get("flow", ""),
        "difficulty: " + meta.get("difficulty", ""),
        "closes_ac: " + devflow_lib.format_meta_value(split_list(meta.get("closes_ac", ""))),
        "partial_ac: " + devflow_lib.format_meta_value(split_list(meta.get("partial_ac", ""))),
        "one_line: " + meta.get("한 줄", ""),
        "origin: ",
        "cause_task: ",
        "fix_generation: {}".format(generation),
        "commit: ",
        "running_agent: ",
        "retry: 0",
        "judge_method: ",
        "approval_mode: ",
        "n_decide: 0",
        "n_todo: 0",
        "n_notify: 0",
        "n_unverified: 0",
        "n_children: 0",
        "split_criterion: ",
        "shrunk_reason: ",
        "awaiting_answer_apply: false",
        "external_progress: ",
        "created: " + now,
        "started: ",
        "judged: ",
        "approval_requested: ",
        "approved: ",
        "---",
        "",
    ]
    for key in kinds.BODY_KEYS:
        lines.append("## " + key)
        lines.append(child["body"].get(key, "") or "(없음)")
        lines.append("")
    lines += ["## 영향받는 task와 처리", "(없음)", "", "## 넘길 이상 신호", "(없음)", "", "## 승인 기록", ""]
    return "\n".join(lines)


def choose_rows(children, chosen_raw, problems, backlog_raw=""):
    """--option으로 만들 행을 고른다. (만들 행, 고르지 않은 행, 백로그로 만들 행의 제목). --backlog-option의 안이 든 행은
    (고른 안이 함께 들지 않았으면) 만들되 백로그로 둔다."""
    groups = {}
    for c in children:
        for o in row_options(c):
            if not OPTION_RE.match(o):
                problems.append("option 값은 `묶음/안`(예 수정안/가): '{}' — {}".format(o, c["title"]))
                continue
            g, a = o.split("/", 1)
            groups.setdefault(g, set()).add(a)
    chosen = split_list(chosen_raw or "")
    later = split_list(backlog_raw or "")
    if not groups:
        if chosen or later:
            problems.append("--option·--backlog-option을 받았는데 `- option:` 키가 있는 행이 없음(옛 [안 …] 제목 행은 옵션 없이 만든다)")
        return children, [], set()
    picked = {}
    for o in chosen:
        if not OPTION_RE.match(o):
            problems.append("--option 값은 `묶음/안`: '{}'".format(o))
            continue
        g, a = o.split("/", 1)
        if g not in groups:
            problems.append("행에 없는 묶음: {}(행의 묶음: {})".format(g, ", ".join(sorted(groups))))
        elif a != "없음" and a not in groups[g]:
            problems.append("행에 없는 안: {}(묶음 {}의 안: {})".format(o, g, ", ".join(sorted(groups[g]))))
        picked.setdefault(g, set()).add(a)
    for g, a in picked.items():
        if "없음" in a and len(a) > 1:
            problems.append("묶음 {}에 `없음`과 다른 안을 함께 고름".format(g))
    shelved = {}
    for o in later:
        g, a = o.split("/", 1) if OPTION_RE.match(o) else ("", "")
        if not g or g not in groups or a not in groups[g]:
            problems.append("--backlog-option은 행에 있는 `묶음/안`: '{}'".format(o))
        elif a in picked.get(g, set()):
            problems.append("같은 안을 --option과 --backlog-option에 함께 줌: {}".format(o))
        else:
            shelved.setdefault(g, set()).add(a)
    missing = sorted(set(groups) - set(picked) - set(shelved))
    if missing:
        problems.append("고르지 않은 묶음: {} — 승인에서 고른 안을 --option {}/{{안}}으로 넘긴다(받아들임이면 {}/없음)".format(
            ", ".join(missing), missing[0], missing[0]))
    wanted = {g + "/" + a for g, s in picked.items() for a in s}
    parked_opts = {g + "/" + a for g, s in shelved.items() for a in s}
    keep = [c for c in children if not row_options(c) or (wanted | parked_opts) & set(row_options(c))]
    backlog = {c["title"] for c in keep if row_options(c) and not wanted & set(row_options(c))}
    return keep, [c for c in children if c not in keep], backlog


def pair_rows(tasks, parent_id, rows, problems):
    """A5 --replace: 행마다 제목과 flow가 함께 같은 기존 task(부모 자신 제외). {제목: task}."""
    pairs = {}
    for c in rows:
        flow = c["meta"].get("flow", "")
        found = [t for t in tasks.values() if t["id"] != parent_id and str(t.get("title", "")).strip() == c["title"]
                 and str(t.get("flow", "") or "").strip() == flow]
        if len(found) > 1:
            problems.append("짝이 둘 이상({}): {} — 제목을 겹치지 않게 고쳐 다시 쓴다".format(
                ", ".join(t["id"] for t in found), c["title"]))
        elif found:
            t = found[0]
            if t.get("status") != "대기":
                problems.append("시작한 task {}({}): {} — 끝난 task 규칙으로(SKILL.md 5절 「변경 task를 만들 때」)".format(
                    t["id"], t.get("status"), c["title"]))
            elif t["_sections"].get("판정 기준 정정", "").strip():
                problems.append("판정 기준 정정 기록이 있는 task {}: {} — 정정을 확인한 뒤 손으로".format(t["id"], c["title"]))
            else:
                pairs[c["title"]] = t
    return pairs


def replace_task(t, child, depends, dry):
    """짝이 된 대기 task의 머리 파일에서 행이 정하는 것만 바꾼다(id·parent·created·status·승인 기록은 그대로)."""
    meta = child["meta"]
    doc = devflow_lib.Doc(t["_path"])
    doc.set("depends_on", depends)
    doc.set("difficulty", meta.get("difficulty", ""))
    doc.set("closes_ac", split_list(meta.get("closes_ac", "")))
    doc.set("partial_ac", split_list(meta.get("partial_ac", "")))
    doc.set("one_line", meta.get("한 줄", ""))
    for key in kinds.BODY_KEYS:
        doc.set_section(key, child["body"].get(key, "") or "(없음)", before=["영향받는 task와 처리", "넘길 이상 신호", "승인 기록"])
    if not dry:
        doc.save()
        # 만들 때의 판정 기준을 새 행으로(시작 전이라 기록 점검 R2의 비교 기준을 바꾼다)
        devflow_lib.write_text(os.path.join(t["_dir"], "criteria.orig.md"), (child["body"].get("판정 기준", "") or "(없음)") + "\n")


def find_loop(graph, starts):
    """starts에서 의존을 따라가 고리가 있으면 그 경로(없으면 [])."""
    state = {}

    def visit(n, path):
        if state.get(n) == 1:
            return path[path.index(n):] + [n]
        if state.get(n) == 2 or n not in graph:
            return []
        state[n] = 1
        for d in graph[n]:
            hit = visit(d, path + [n])
            if hit:
                return hit
        state[n] = 2
        return []
    for s in starts:
        hit = visit(s, [])
        if hit:
            return hit
    return []


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    run_dir, parent_id = argv[1], argv[2]
    twice = [f for f in ("--option", "--backlog-option", "--depends-on", "--now", "--over-cap") if argv.count(f) > 1]
    if twice:
        # 두 번 주면 뒤 것이 조용히 버려진다. 값은 쉼표로 한 번에
        print("같은 옵션을 두 번 줌: {} — 값은 쉼표로 이어 한 번에 준다".format(", ".join(twice)))
        return 2
    dry = "--dry-run" in argv
    replace = "--replace" in argv

    def opt(name):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else ""
    common_dep = split_list(opt("--depends-on"))
    now = opt("--now")
    over_cap = None
    if "--over-cap" in argv:
        over_cap = "백로그" if opt("--over-cap") == "백로그" else "만듦"

    tasks = devflow_lib.load_tasks(run_dir)
    if parent_id not in tasks:
        print("부모 task를 찾지 못함: " + parent_id)
        return 2
    parent = tasks[parent_id]
    result_md = os.path.join(parent["_dir"], "result.md")
    if not os.path.isfile(result_md):
        print("부모의 result.md가 없음: " + result_md)
        return 2
    criterion, children = parse_children(devflow_lib.read_text(result_md))
    if criterion is None:
        print("「자식 목록」 절이 없음")
        return 2
    if not children:
        print("자식 0개 (나눈 기준: {})".format(criterion or "-"))
        return 0

    problems = []
    rows, skipped, shelved = choose_rows(children, opt("--option") if "--option" in argv else "", problems,
                                         opt("--backlog-option") if "--backlog-option" in argv else "")

    def idle(c):   # 바로 돌지 않는 행: [백로그]·옛 [안 …] 행과 --backlog-option으로 백로그에 둘 행
        return parked(c) or c["title"] in shelved
    if replace and parent.get("kind") != "change":
        problems.append("--replace는 변경 task의 자식 목록에만({}는 {})".format(parent_id, parent.get("kind")))
    pairs = pair_rows(tasks, parent_id, rows, problems) if replace else {}
    number = devflow_lib.next_task_number(tasks)
    ids = {}
    for c in rows:
        if c["title"] in pairs:
            ids[c["title"]] = pairs[c["title"]]["id"]
        else:
            ids[c["title"]] = "T{:03d}".format(number)
            number += 1
    for c in rows:
        kind = c["meta"].get("kind")
        if not kind:
            problems.append("kind 없음: " + c["title"])
        if kind not in kinds.KINDS:
            problems.append("모르는 kind '{}': {}".format(kind, c["title"]))
        for key in ("범위", "판정 기준"):
            if not c["body"].get(key):
                problems.append("「{}」 없음: {}".format(key, c["title"]))
        if kind in kinds.TOUCH_FILES_KINDS and not c["body"].get("건드릴 파일"):
            problems.append("「건드릴 파일」 없음(코드 task): " + c["title"])
        if kind in kinds.AUTO_DEPEND_KINDS and not c["title"].lstrip().startswith("[백로그]") \
                and devflow_lib.flow_name_problem(run_dir, c["meta"].get("flow", "")):
            problems.append(devflow_lib.flow_name_problem(run_dir, c["meta"].get("flow", "")) + ": " + c["title"])
        if c["title"] in pairs and pairs[c["title"]].get("kind") != kind:
            problems.append("짝 {}의 kind({})가 행의 kind({})와 다름: {} — 새 task로 만들고 옛 것은 보류한다".format(
                pairs[c["title"]]["id"], pairs[c["title"]].get("kind"), kind, c["title"]))
        if kind == "change":
            for line in devflow_lib.touch_format_problems(c["body"].get("건드릴 파일", "")):
                problems.append("change 행의 「건드릴 파일」은 한 줄에 한 경로를 `- `로: '{}' — {}".format(line, c["title"]))
            bad = devflow_lib.outside_canon(devflow_lib.touch_paths(c["body"].get("건드릴 파일", "")), run_dir)
            if bad:
                problems.append("change 행의 「건드릴 파일」에 정본 밖 경로({}): {} — 코드를 고치는 변경은 kind: fix".format(
                    ", ".join(bad), c["title"]))
    if problems:
        print("자식 목록의 형식 문제 {}건. 머리 파일을 만들지 않았다.".format(len(problems)))
        for p in problems:
            print("- " + p)
        return 3

    # 수정 세대. 재검증이 낸 수정이 상한에 닿으면 만들지 않는다(screen.py가 재검증 화면 「정해 주실 것」에 올린다)
    generation = devflow_lib.child_fix_generation(tasks, parent)
    cap = devflow_lib.fix_cap(run_dir)
    live_fixes = [c for c in rows if c["meta"].get("kind") == "fix" and not idle(c)]
    if over_cap and (generation is None or generation < cap or not live_fixes):
        print("--over-cap은 수정 세대 상한에 닿은 재검증에만(이 부모의 수정 세대 {}, 상한 {}). 머리 파일을 만들지 않았다.".format(
            "-" if generation is None else generation, cap))
        return 3
    if generation is not None and live_fixes and generation >= cap and over_cap is None:
        print("수정 세대 상한({})에 닿음: 이 재검증의 수정 {}건이 세대 {}. 머리 파일을 만들지 않았다.".format(
            cap, len(live_fixes), generation))
        print("- 승인 화면에서 고른 답으로: (가) 그대로 만들기 → --over-cap / (나) 받아들이고 백로그로 → --over-cap 백로그"
              " / (다) 설계 변경 task로 → 이 자식은 만들지 않고 변경 task를 만든다")
        return 3

    skipped_titles = {c["title"] for c in skipped}
    last_code_in_flow = {}
    plan = []
    for c in rows:
        tid = ids[c["title"]]
        depends = []
        for dep in split_list(c["meta"].get("depends_on", "")):
            if dep in skipped_titles or (dep in shelved and not idle(c)):
                # 만들지 않는 행과, 일반 행이 백로그로 둔 행에 건 의존은 뺀다(백로그는 끝으로 세지만 기다릴 것이 아님)
                print("의존 뺌({}): {} → {}".format("백로그로 둔 안의 행" if dep in shelved else "고르지 않은 안의 행", c["title"], dep))
            elif dep in ids:
                depends.append(ids[dep])
            elif re.match(r"T\d+$", dep) and dep in tasks:
                depends.append(dep)
            elif replace and len([t for t in tasks.values() if str(t.get("title", "")).strip() == dep]) == 1:
                # 변경 task는 바뀐 행만 다시 쓰므로 바뀌지 않은 형제는 제목으로 가리킨다
                depends.append(next(t["id"] for t in tasks.values() if str(t.get("title", "")).strip() == dep))
            else:
                problems.append("의존하는 task를 찾지 못함 '{}': {}".format(dep, c["title"]))
        kind = c["meta"].get("kind")
        flow = c["meta"].get("flow", "")
        # 백로그 행과 옛 [안 …] 행은 바로 돌지 않으므로 코드 차례에 끼우지 않는다
        # (끼우면 그 뒤의 진짜 task가 영영 시작하지 못한다. 2026-10-06 마른 시험에서 재현). 고른 안의 행은 일반 행이다
        if kind in kinds.AUTO_DEPEND_KINDS and flow and not idle(c):
            prev = last_code_in_flow.get(flow)
            if prev is None and c["title"] in pairs:
                # 바꾸는 행이 이 목록에서 그 흐름의 첫 코드 행이면 원래의 자동 의존(같은 흐름 앞 코드 task)을 둔다
                old = pairs[c["title"]]
                prev = next((d for d in old.get("depends_on", []) if d in tasks and d not in ids.values()
                             and tasks[d].get("flow") == flow and tasks[d].get("kind") in kinds.AUTO_DEPEND_KINDS), None)
            if prev and prev not in depends:
                depends.append(prev)
            last_code_in_flow[flow] = tid
        for dep in common_dep:
            if dep not in depends:
                depends.append(dep)
        if c["title"] in pairs:
            # 바꾸는 task가 의존하던 아직 끝나지 않은 다른 변경 task는 남긴다. 지우면 그 승인 전에 시작할 수 있다
            #. 그 밖의 의존은 행과 같은 흐름 차례가 정한다(되살리면 고리가 생긴다)
            for dep in pairs[c["title"]].get("depends_on", []):
                if dep not in depends and dep in tasks and tasks[dep].get("kind") == "change" \
                        and tasks[dep].get("status") != kinds.DONE and dep != parent_id:
                    depends.append(dep)
        status = "대기"
        if c["title"].lstrip().startswith("[백로그]") or c["title"] in shelved:
            status = "백로그"
        elif over_cap == "백로그" and generation is not None and kind in ("fix", "reverify"):
            status = "백로그"
        gen = generation if (generation is not None and kind == "fix") else 0
        plan.append((tid, c, depends, status, gen))
    graph = {t: list(o.get("depends_on", [])) for t, o in tasks.items()}
    graph.update({tid: depends for tid, c, depends, status, gen in plan})
    loop = find_loop(graph, [tid for tid, *_ in plan])
    if loop:
        problems.append("새 의존이 고리를 만듦: {} — 행의 depends_on을 고친다".format(" → ".join(loop)))
    if problems:
        print("의존 문제 {}건. 머리 파일을 만들지 않았다.".format(len(problems)))
        for p in problems:
            print("- " + p)
        return 3

    print("나눈 기준: {}".format(criterion or "(적히지 않음)"))
    for c in skipped:
        print("고르지 않은 안의 행(만들지 않음): {} [{}]".format(c["title"], c["meta"].get("option", "")))
    tail = " (dry-run)" if dry else ""
    for tid, c, depends, status, gen in plan:
        head = "{} {} [{}] 흐름={} 의존={}".format(tid, c["title"], c["meta"].get("kind"),
                                                c["meta"].get("flow", "") or "-", ",".join(depends) or "-")
        if status != "대기" and c["title"] not in pairs:
            head += " 상태=" + status
        if gen:
            head += " 수정 세대={}".format(gen)
        if c["title"] in pairs:
            old = pairs[c["title"]]
            change = "" if list(old.get("depends_on", [])) == depends else " (의존 {} → {})".format(
                devflow_lib.format_meta_value(old.get("depends_on", [])), devflow_lib.format_meta_value(depends))
            print(head + " — 기존 task를 바꿈" + change + tail)
            if status != "대기":
                print("  {}는 대기 그대로 둠 — 행이 백로그면 `task_set.py … {} --status 백로그 --record`로".format(old["id"], old["id"]))
            replace_task(old, c, depends, dry)
            continue
        print(head + (" — 새 task" if replace else "") + tail)
        if not dry:
            path = os.path.join(run_dir, "tasks", tid, "task.md")
            devflow_lib.write_text(path, render(tid, parent_id, c, depends, now, status, gen))
            # 만들 때의 판정 기준을 남긴다. 기록 점검(devflow_lib.record_check R2)이 손으로 고친 판정 기준을 이것과 비교한다
            devflow_lib.write_text(os.path.join(run_dir, "tasks", tid, "criteria.orig.md"),
                             (c["body"].get("판정 기준", "") or "(없음)") + "\n")
    if replace:
        parents = {t.get("parent") for t in pairs.values() if t.get("parent")}
        paired = {t["id"] for t in pairs.values()}
        left = [t for t in tasks.values() if t.get("parent") in parents and t["id"] not in paired
                and t.get("status") == "대기"]
        for t in left:
            print("짝 없는 기존 task(그대로 둠): {} {} [{}] — 바뀐 행의 옛 제목이면 메인이 보류할지 정한다".format(
                t["id"], t.get("title", ""), t.get("kind", "")))
        for c in rows:
            if c["title"] in pairs:
                continue
            for t in tasks.values():
                if str(t.get("title", "")).strip() == c["title"] and t["id"] != parent_id:
                    print("제목은 같고 흐름이 다른 기존 task(짝짓지 않음): {} [{}] 흐름={} 상태 {} — 옛 것이면 메인이 보류할지 정한다".format(
                        t["id"], t.get("kind"), t.get("flow") or "-", t.get("status")))
        if not pairs:
            print("짝 0 — 모든 행을 새 task로 만들었다(제목과 flow가 같아야 짝이 된다)")
    old_alt = [tid for tid, c, *_ in plan if parked(c) and not c["title"].lstrip().startswith("[백로그]")]
    if old_alt:
        print("옛 [안 …] 행(option 키 없음) {}: 대기로 만들었다. 고르지 않은 안은 `task_set.py … --status 백로그`(백로그로 남김)나 "
              "`--status 보류 --reason …`으로 닫는다(SKILL.md 4절)".format(", ".join(old_alt)))
    # 새 흐름의 첫 코드 task 행이면 flow.md(폴더 없음, role, round)를 함께 만든다. 가드가 폴더 전에 그 흐름을 센다
    for tid, c, depends, status, gen in plan:
        flow = c["meta"].get("flow", "")
        if c["meta"].get("kind") in kinds.AUTO_DEPEND_KINDS and flow and not idle(c) and status == "대기":
            if dry:
                if not os.path.isfile(os.path.join(run_dir, "flows", flow, "flow.md")):
                    print("flow.md 만들 것: flows/{}/flow.md (dry-run)".format(flow))
            elif devflow_lib.ensure_flow_md(run_dir, flow):
                print("flow.md 만듦: flows/{}/flow.md(폴더 없음, role {})".format(flow, devflow_lib.flow_role(flow)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
