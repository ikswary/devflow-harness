r"""마무리 입력 모으기: 실행 하나의 task들에 흩어진 목록을 파일로 뽑는다.

메인이 기억에 기대 손으로 모으면 빠진다(첫 실행에서 마무리 프롬프트에 「확인 안 된 것」 목록이 빠졌다).
본문은 메인 컨텍스트를 거치지 않고 파일로만 가며, 메인은 출력의 건수와 경로만 본다.

사용:
  python collect.py {실행 폴더} {출력 폴더}
    {출력 폴더}\unverified-list.md   `완료` task마다 result.md 「승인 화면 > 확인 안 된 것」 항목
    {출력 폴더}\backlog-list.md      `백로그` task 한 줄씩(id, 종류, 흐름, 부모, 제목, 폴더)
  python collect.py {실행 폴더} {출력 폴더} --notified {흐름}
    {출력 폴더}\notified-{흐름}.md  그 흐름에서 알림으로 지나간 task마다 알릴 것·확인 안 된 것·이상 신호
    (흐름별 검증·재검증·수정 흐름 합치기를 띄우기 전에 메인이 돌리고, 작성자에게 경로를 준다)
  python collect.py {실행 폴더} --measure
    표준 출력 두 줄(결정 0 승인, 관점별 지적). 메인이 measure.md 그 실행 행의 비고 칸에 `; `로 잇는다
  종료 코드: 0 정상(칸이 빠진 형식 경고는 목록 위에 적고 0), 2 사용법 오류,
             3 result.md나 「승인 화면」 절이 없는 `완료` task가 있음(목록 맨 위에 적힌다)
  python collect.py {실행 폴더} --folder-wait
    흐름마다 `폴더 대기: {흐름} {분}분 ({task 수}개) / 흐름 작성 {분}분`을 내고, {실행 폴더}\..\measure.md에서
    첫 칸이 실행 폴더 이름인 마지막 행의 `비고` 칸에 `; `로 이어 덧붙인다(같은 흐름의 것은 바꾼다).
    폴더 대기 = 코드 폴더에 쓰는 task의 대기 구간 [준비 시각, started]가 같은 흐름 다른 쓰는 task의 차지 구간
    [started, 끝] 합집합과 겹친 분. 준비 시각은 created와 depends_on task들 approved 가운데 늦은 것, 끝은
    통과(no_change이거나 두 판정 파일 「통과 못 한 기준」 0)하고 approval_requested가 있으면 그 시각, 그 밖은 approved.
    끝이 없는 task는 빼고 센다. 차지 구간은 있으나 준비 시각을 못 정한 task는 `  준비 시각이 없어 대기를 못 잰 task {n}개`로 따로 낸다.
    종료 코드 3 = 측정 기록에 이 실행 행이 없음(줄만 내고 파일은 그대로)
"""
import fnmatch
import os
import re
import sys

import board
import devflow_lib
import kinds
import shadow_check


def unverified_items(result_md):
    """(항목 줄 목록, 문제, 경고)를 돌려준다. 문제는 뽑지 못함, 경고는 칸이 빠진 형식 위반(빈 칸으로 봄)."""
    if not os.path.isfile(result_md):
        return [], "result.md 없음", None
    top = devflow_lib.sections(devflow_lib.read_text(result_md), level=2)
    screen = top.get("승인 화면")
    if screen is None:
        return [], "「승인 화면」 절 없음", None
    sub = devflow_lib.sections(screen, level=3)
    text = sub.get("확인 안 된 것")
    if text is None:
        return [], None, "「확인 안 된 것」 칸 없음(빈 칸은 `- 없음`으로 적는 형식 위반, 빈 칸으로 봄)"
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if devflow_lib.item_count(text) == 0 and not devflow_lib.unparsed_cell(text):
        return [], None, None
    return lines, None, None   # `- ` 항목이 아닌 형식으로 쓴 칸도 버리지 않고 그대로 옮긴다


def notified(run_dir, out_dir, flow):
    """흐름별 검증·재검증·수정 흐름 합치기에 넘길 「알림으로 지나간 task」 목록과 그 task들의 알릴 것·확인 안 된 것.
    메인의 기억이 아니라 머리 파일의 `approval_mode: 알림`에서 뽑는다."""
    tasks = devflow_lib.load_tasks(run_dir)
    blocks = []
    for tid, t in tasks.items():
        if t.get("flow") != flow or t.get("approval_mode") != "알림" or t.get("status") != kinds.DONE:
            continue
        p = os.path.join(t["_dir"], "result.md")
        cells = devflow_lib.sections(devflow_lib.sections(devflow_lib.read_text(p), level=2).get("승인 화면", ""), level=3) if os.path.isfile(p) else {}
        part = ["## [{}] {} ({}, 커밋 {})".format(tid, t.get("title", ""), t.get("kind", ""), t.get("commit", "") or "-")]
        for name in ("알릴 것", "확인 안 된 것"):
            body = cells.get(name, "").strip() or "- 없음"
            part.append("### " + name)
            part.append(body)
        signals = t["_sections"].get("넘길 이상 신호", "").strip()
        if signals and signals != "(없음)":
            part += ["### 이상 신호", signals]
        evidence = shadow_check.notified_evidence(run_dir, t)
        if evidence is not None:
            part += ["### shadow 원 판정 고정 근거", "```json",
                     __import__("json").dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), "```"]
        blocks.append("\n".join(part))
    path = os.path.join(out_dir, "notified-{}.md".format(flow))
    devflow_lib.write_text(path, "# 흐름 {}에서 알림으로 지나간 task (collect.py)\n\n".format(flow) + ("\n\n".join(blocks) or "- 없음") + "\n")
    print("알림으로 지나간 task {}개 -> {}".format(len(blocks), path))
    return 0


def occupied(t):
    """차지 구간 (started, 끝)의 epoch. 끝이 없으면(열린 task) None."""
    start = board._epoch(t.get("started"))
    if start is None:
        return None
    asked = board._epoch(t.get("approval_requested"))
    failed = 0
    for name in kinds.JUDGE_FILES.values():
        p = os.path.join(t["_dir"], name)
        if os.path.isfile(p):
            failed += devflow_lib.item_count(devflow_lib.sections(devflow_lib.read_text(p), level=2).get("통과 못 한 기준", ""))
    # 통과한 코드 task는 커밋 뒤 승인대기로 가며 폴더를 놓고, 통과 못 한 것은 완료(approved)까지 커밋 대기로 막는다
    if asked is not None and (devflow_lib.no_change(t) or failed == 0):
        end = asked
    else:
        end = board._epoch(t.get("approved"))
    if end is None or end < start:
        return None
    return start, end


def ready_at(t, tasks):
    """준비 시각: created와 depends_on task들의 approved 가운데 가장 늦은 것. 하나도 못 읽으면 None."""
    deps = t.get("depends_on") or []
    if not isinstance(deps, list):
        deps = [d.strip() for d in str(deps).strip("[]").split(",") if d.strip()]
    times = [board._epoch(t.get("created"))] + [board._epoch(tasks[d].get("approved")) for d in deps if d in tasks]
    times = [x for x in times if x is not None]
    return max(times) if times else None


def union_minutes(intervals):
    """구간 (시작, 끝) epoch들의 합집합 길이(분, 반올림)."""
    total, cur = 0.0, None
    for s, e in sorted(intervals):
        if cur is None or s > cur[1]:
            if cur is not None:
                total += cur[1] - cur[0]
            cur = [s, e]
        else:
            cur[1] = max(cur[1], e)
    if cur is not None:
        total += cur[1] - cur[0]
    return int(round(total / 60))


def flow_wait(tasks, flow):
    """(폴더 대기 분, 겹친 task 수, 흐름 작성 분, 끝이 없어 뺀 task 수, 준비 시각이 없어 대기를 못 잰 task 수).
    흐름의 코드 폴더에 쓰는 task만 센다."""
    spans, skipped = {}, 0
    for tid, t in tasks.items():
        if t.get("flow") != flow or not board.writes(t):
            continue
        occ = occupied(t)
        if occ is None:
            skipped += 1
            continue
        spans[tid] = occ
    wait_min, n_tasks, unready = 0, 0, 0
    for tid, (start, _) in spans.items():
        ready = ready_at(tasks[tid], tasks)
        if ready is None:
            unready += 1
            continue
        if ready >= start:
            continue
        # 대기 구간과 다른 task 차지 구간의 겹침을 합집합으로 센다(둘이 함께 차지한 시간을 두 번 세지 않는다)
        cut = [(max(s, ready), min(e, start)) for o, (s, e) in spans.items() if o != tid and min(e, start) > max(s, ready)]
        minutes = union_minutes(cut)
        if minutes > 0:
            wait_min += minutes
            n_tasks += 1
    return wait_min, n_tasks, union_minutes(spans.values()), skipped, unready


def _cells(line):
    r"""표 행을 `|`로 가른 조각(맨 앞·맨 끝 조각 포함). `\|`는 칸 안 글자로 둔다."""
    return re.split(r"(?<!\\)\|", line)


WAIT_TAIL = r" \d+분 \(\d+개\) / 흐름 작성 \d+분"   # `폴더 대기: {흐름}` 뒤에 오는 조각 꼴


def put_segment(cell, seg):
    """`비고` 칸 글에서 seg와 같은 흐름의 폴더 대기 조각만 seg로 바꾸고(여럿이면 첫 자리에 하나만 남김),
    없으면 맨 끝에 덧붙인다. 조각 사이 구분자는 `; `로 통일하고, 조각을 지운 자리에 빈 구분자를 남기지 않는다.
    칸의 다른 글은 안쪽 글자를 그대로 둔다(옛 행의 앞뒤 ` / `만 `; `로 바뀐다)."""
    m = re.fullmatch(r"폴더 대기: (\S+)" + WAIT_TAIL, seg)
    pat = re.compile("폴더 대기: " + re.escape(m.group(1)) + WAIT_TAIL) if m else None
    wait = re.compile(r"(폴더 대기: \S+" + WAIT_TAIL + ")")
    items, placed = [], False
    for i, piece in enumerate(wait.split(cell)):
        if i % 2 == 1:   # 폴더 대기 조각
            if pat and pat.fullmatch(piece):
                if not placed:
                    items.append(seg)
                    placed = True
            else:
                items.append(piece)
        else:
            text = re.sub(r"^[\s;/]+|[\s;/]+$", "", piece)
            if text:
                items.append(text)
    if not placed:
        items.append(seg)
    return "; ".join(items)


def write_note(measure_path, run_name, segments):
    """측정 기록에서 첫 칸이 run_name인 마지막 행의 `비고` 칸에 조각을 `; `로 덧붙인다(같은 흐름의 조각은 바꾼다).
    파일·`비고` 열·행이 없으면 파일을 그대로 두고 False."""
    if not os.path.isfile(measure_path):
        return False
    with open(measure_path, "r", encoding="utf-8-sig", newline="") as f:
        lines = f.read().splitlines(keepends=True)
    col, row = None, None
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        parts = [c.strip() for c in _cells(line.strip())]
        if col is None:
            if "비고" in parts:
                col = parts.index("비고")
            continue
        if len(parts) > 1 and parts[1] == run_name:
            row = i
    if row is None:
        return False
    body = lines[row].rstrip("\r\n")
    end = lines[row][len(body):]
    parts = _cells(body)
    while len(parts) < col + 2:   # 칸이 모자란 행은 빈 칸을 채운다(맨 끝 조각은 닫는 `|` 뒤)
        parts.insert(len(parts) - 1, " ")
    cell = parts[col].strip()
    if cell == "-":
        cell = ""
    for seg in segments:
        cell = put_segment(cell, seg)
    parts[col] = " " + cell + " "
    lines[row] = "|".join(parts) + end
    with open(measure_path, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))
    return True


def folder_wait(run_dir):
    """흐름마다 폴더 대기 줄을 내고 측정 기록 이 실행 행의 `비고`에 덧붙인다. 행이 없으면 3."""
    tasks = devflow_lib.load_tasks(run_dir)
    segments = []
    for flow in sorted({t.get("flow") for t in tasks.values() if t.get("flow") and board.writes(t)}):
        wait_min, n_tasks, busy_min, skipped, unready = flow_wait(tasks, flow)
        seg = "폴더 대기: {} {}분 ({}개) / 흐름 작성 {}분".format(flow, wait_min, n_tasks, busy_min)
        print(seg)
        if skipped:
            print("  끝이 없어 뺀 task {}개".format(skipped))
        if unready:
            print("  준비 시각이 없어 대기를 못 잰 task {}개".format(unready))
        segments.append(seg)
    if not segments:
        print("폴더 대기: 코드 폴더에 쓰는 task 없음")
        return 0
    base = os.path.abspath(run_dir).rstrip("\\/")
    measure_path = os.path.join(os.path.dirname(base), "measure.md")
    if not write_note(measure_path, os.path.basename(base), segments):
        print("측정 기록에 이 실행 행 없음: {} (파일 그대로) -> {}".format(os.path.basename(base), measure_path))
        return 3
    print("비고에 덧붙임 -> {}".format(measure_path))
    return 0


PERSPECTIVES = ("보안", "운영 제약", "데이터 정합", "정확성", "시험", "관례", "그 밖")
DESIGN_PERSPECTIVES = PERSPECTIVES[:3]   # 설계 판정이 잡는 관점 셋(설계 자체 검증의 관점 질문)
PERSPECTIVE_RE = re.compile(r"관점:\s*(\S.*?)\s*$")


def zero_decision_approvals(tasks):
    """kind → (결정 0 승인 수, 그 가운데 한 마디 답 수). 결정 0 승인은 `완료`·`approval_mode: 승인`·`n_decide` 0·
    `n_todo` 0인 task이고, 한 마디 답은 가장 늦은 승인 줄의 원문이 `devflow_lib.short_answer`인 것(D-9). 차례는 `kinds.KINDS`."""
    counts = {}
    for t in tasks.values():
        if t.get("status") != kinds.DONE or t.get("approval_mode") != "승인":
            continue
        if str(t.get("n_decide", "")).strip() != "0" or str(t.get("n_todo", "")).strip() != "0":
            continue
        approvals = sorted((devflow_lib.record_fields(l)[0], i, l) for i, l in enumerate(devflow_lib.record_lines(t))
                           if devflow_lib.approval_line(l))
        quote = devflow_lib.record_quote(approvals[-1][2]) if approvals else None
        n, short = counts.get(t.get("kind", ""), (0, 0))
        counts[t.get("kind", "")] = (n + 1, short + (quote is not None and devflow_lib.short_answer(quote)))
    order = list(kinds.KINDS) + sorted(k for k in counts if k not in kinds.KINDS)
    return {k: counts[k] for k in order if k in counts}


def _perspectives(text):
    """`관점:` 줄의 값 목록. 7값이 아니면 `그 밖`."""
    out = []
    for line in text.splitlines():
        m = PERSPECTIVE_RE.search(line)
        if m:
            out.append(m.group(1) if m.group(1) in PERSPECTIVES else PERSPECTIVES[-1])
    return out


def perspective_counts(tasks):
    """관점 → (검증에서 나온 수, 설계 판정이 잡은 수). 검증 무리 task `result.md` 「본문」과 설계 블록 task의
    `judge.md`·`judge.r*.md` 「통과 못 한 기준」의 `관점:` 줄을 센다. 설계 판정 쪽은 관점 셋만(D-9)."""
    found = {p: 0 for p in PERSPECTIVES}
    caught = {p: 0 for p in PERSPECTIVES}
    for t in tasks.values():
        kind = t.get("kind", "")
        if kind in kinds.VERIFY_KINDS:
            res = os.path.join(t["_dir"], "result.md")
            body = devflow_lib.sections(devflow_lib.read_text(res)).get("본문", "") if os.path.isfile(res) else ""
            for name in _perspectives(body):
                found[name] += 1
        if (t.get("block") or (kinds.block_of(kind) if kind in kinds.KINDS else "")) != "설계":
            continue
        for name in sorted(os.listdir(t["_dir"])):
            if name != "judge.md" and not fnmatch.fnmatch(name, "judge.r*.md"):
                continue
            failed = devflow_lib.sections(devflow_lib.read_text(os.path.join(t["_dir"], name))).get("통과 못 한 기준", "")
            for p in _perspectives(failed):
                if p in DESIGN_PERSPECTIVES:
                    caught[p] += 1
    return {p: (found[p], caught[p]) for p in PERSPECTIVES}


def measure(run_dir):
    """측정 기록의 비고 칸에 옮길 두 줄(설계 B 3.8)을 표준 출력에 낸다."""
    tasks = devflow_lib.load_tasks(run_dir)
    zero = zero_decision_approvals(tasks)
    print("- 결정 0 승인: " + (" · ".join("{} {}(한 마디 {})".format(k, n, s) for k, (n, s) in zero.items()) or "없음"))
    parts = []
    for p, (n, d) in perspective_counts(tasks).items():
        parts.append("{} {}(설계 판정 {})".format(p, n, d) if p in DESIGN_PERSPECTIVES else "{} {}".format(p, n))
    print("- 관점 지적: " + " · ".join(parts))
    return 0


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) == 3 and argv[2] == "--folder-wait":
        return folder_wait(argv[1])
    if len(argv) >= 3 and argv[2] in ("--shadow-inputs", "--shadow-open", "--shadow-freeze", "--shadow-b-freeze", "--shadow-check"):
        return shadow_check.main([argv[0], argv[1]] + argv[2:])
    if len(argv) == 4 and argv[2] == "--shadow-init":
        try:
            path = shadow_check.init_plan(argv[1], argv[3])
        except shadow_check.ShadowError as e:
            print("실험 조건 불충족: " + str(e))
            return 3
        print("shadow 계획 고정: " + path)
        return 0
    if len(argv) == 3 and argv[2] == "--measure":
        return measure(argv[1])
    if len(argv) > 4 and argv[3] == "--notified":
        return notified(argv[1], argv[2], argv[4])
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, out_dir = argv[1], argv[2]
    tasks = devflow_lib.load_tasks(run_dir)

    # `완료` task만 모은다. 지금 도는 마무리는 아직 `완료`가 아니라 저절로 빠지고, 앞서 끝난 마무리는 들어간다.
    problems, warnings, blocks, n_items, n_tasks = [], [], [], 0, 0
    for tid, t in tasks.items():
        if t.get("status") != kinds.DONE:
            continue
        items, problem, warning = unverified_items(os.path.join(t["_dir"], "result.md"))
        if warning:
            warnings.append("- {} {}: {}".format(tid, t.get("title", ""), warning))
        if problem:
            problems.append("- {} {}: {}".format(tid, t.get("title", ""), problem))
            continue
        if not items:
            continue
        n_tasks += 1
        n_items += devflow_lib.item_count("\n".join(items))
        blocks.append("## {} {}\n{}".format(tid, t.get("title", ""), "\n".join(items)))

    head = ["# 각 task의 「확인 안 된 것」 (collect.py가 `완료` task의 result.md에서 뽑음)", ""]
    if problems:
        head += ["## 뽑지 못한 task (메인이 직접 확인)"] + problems + [""]
    if warnings:
        head += ["## 형식 경고"] + warnings + [""]
    devflow_lib.write_text(os.path.join(out_dir, "unverified-list.md"),
                     "\n".join(head) + "\n\n".join(blocks) + "\n")

    backlog = [(tid, t) for tid, t in tasks.items() if t.get("status") == "백로그"]
    lines = ["# 백로그 task (collect.py)", ""]
    for tid, t in backlog:
        lines.append("- {} [{}] 흐름 {} / 부모 {} / {} / {}".format(
            tid, t.get("kind", ""), t.get("flow", "") or "-", t.get("parent", "") or "-",
            t.get("title", ""), t["_dir"]))
    if not backlog:
        lines.append("- 없음")
    devflow_lib.write_text(os.path.join(out_dir, "backlog-list.md"), "\n".join(lines) + "\n")

    print("확인 안 된 것 {}항목 / {} task -> {}".format(
        n_items, n_tasks, os.path.join(out_dir, "unverified-list.md")))
    print("백로그 {}개 -> {}".format(len(backlog), os.path.join(out_dir, "backlog-list.md")))
    if warnings:
        print("형식 경고 {}개(목록 위)".format(len(warnings)))
    if problems:
        print("뽑지 못한 task {}개(목록 맨 위)".format(len(problems)))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
