r"""마무리 입력 모으기: 실행 하나의 task들에 흩어진 목록을 파일로 뽑는다.

메인이 기억에 기대 손으로 모으면 빠진다(첫 실행에서 마무리 프롬프트에 「확인 안 된 것」 목록이 빠졌다).
본문은 메인 컨텍스트를 거치지 않고 파일로만 가며, 메인은 출력의 건수와 경로만 본다.

사용:
  python collect.py {실행 폴더} {출력 폴더}
    {출력 폴더}\unverified-list.md   `완료` task마다 result.md 「승인 화면 > 확인 안 된 것」 항목과 그 task의 `[실물 확인 미룸]` 표지 줄
    {출력 폴더}\backlog-list.md      `백로그` task 한 줄씩(id, 종류, 흐름, 부모, 제목, 폴더)
    {출력 폴더}\risk-accepted.md     decisions.md와 승인 기록의 `[위험 수용 T0xx] {항목}`, 승인 기록의 답 `승인|위험 수용|{원문}`마다 한 줄(대체된 줄은 뺌. 설계 7.3절)
  python collect.py {실행 폴더} {출력 폴더} --notified {흐름}
    {출력 폴더}\notified-{흐름}.md  그 흐름에서 알림으로 지나간 task마다 알릴 것·확인 안 된 것·이상 신호
    (흐름별 검증·재검증·수정 흐름 합치기를 띄우기 전에 메인이 돌리고, 작성자에게 경로를 준다)
  python collect.py {실행 폴더} --measure
    표준 출력 줄(결정 0 승인, 관점별 지적, 멈춤과 1.2.0 칸. 세는 법은 docs/approval-baseline-1.1.1.md). 메인이 measure.md 그 실행 행의 비고 칸에 `; `로 잇는다
  종료 코드: 0 정상(칸이 빠진 형식 경고는 목록 위에 적고 0), 2 사용법 오류,
             3 result.md나 「승인 화면」 절이 없는 `완료` task가 있음(목록 맨 위에 적힌다)
  python collect.py {실행 폴더} --folder-wait
    흐름마다 `폴더 대기: {흐름} {분}분 ({task 수}개) / 흐름 작성 {분}분`을 내고, {실행 폴더}\..\measure.md에서
    첫 칸이 실행 폴더 이름인 마지막 행의 `비고` 칸에 `; `로 이어 덧붙인다(같은 흐름의 것은 바꾼다).
    폴더 대기 = 코드 폴더에 쓰는 task의 대기 구간 [준비 시각, started]가 같은 흐름 다른 쓰는 task의 차지 구간
    [started, 끝] 합집합과 겹친 분. 준비 시각은 created와 depends_on task들 approved 가운데 늦은 것, 끝은
    통과(no_change이거나 두 판정 파일 「통과 못 한 기준」 0)하고 approval_requested가 있으면 그 시각, 그 밖은 approved.
    치워 둔 구간(journal.md의 `치움`~`붙임`)은 차지 구간에서 뺀다.
    끝이 없는 task는 빼고 센다. 차지 구간은 있으나 준비 시각을 못 정한 task는 `  준비 시각이 없어 대기를 못 잰 task {n}개`로 따로 낸다.
    종료 코드 3 = 측정 기록에 이 실행 행이 없음(줄만 내고 파일은 그대로)
"""
import fnmatch
import json
import os
import re
import statistics
import sys
from datetime import datetime

import board
import decisions
import delegation
import deploy_reuse
import devflow_lib
import exec as execmod
import flow_review
import kinds
import places
import shadow_check
import slots


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


PARK_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?) \| (치움|붙임) \| (\S+) \|")


def parked_spans(t):
    """journal.md에서 그 task를 치워 둔 구간 [(치움, 붙임)]의 epoch. 아직 안 붙였으면 끝은 무한대."""
    path = os.path.join(os.path.dirname(os.path.dirname(t["_dir"])), "journal.md")
    if not os.path.isfile(path):
        return []
    spans, start = [], None
    for line in devflow_lib.read_text(path).splitlines():
        m = PARK_LINE.match(line)
        if not m or m.group(3) != t.get("id"):
            continue
        at = board._epoch(m.group(1))
        if m.group(2) == "치움":
            start = at if start is None else start
        elif start is not None:
            spans.append((start, at))
            start = None
    return spans + ([(start, float("inf"))] if start is not None else [])


def held_spans(t, occ):
    """차지 구간 occ에서 치워 둔 구간을 뺀 구간 목록."""
    out, cur = [], occ[0]
    for s, e in parked_spans(t):
        if min(s, occ[1]) > cur:
            out.append((cur, min(s, occ[1])))
        cur = max(cur, e)
    return out + ([(cur, occ[1])] if cur < occ[1] else [])


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
    starts, spans, skipped = {}, {}, 0
    for tid, t in tasks.items():
        if t.get("flow") != flow or not board.writes(t):
            continue
        occ = occupied(t)
        if occ is None:
            skipped += 1
            continue
        starts[tid] = occ[0]
        spans[tid] = held_spans(t, occ)
    wait_min, n_tasks, unready = 0, 0, 0
    for tid, start in starts.items():
        ready = ready_at(tasks[tid], tasks)
        if ready is None:
            unready += 1
            continue
        if ready >= start:
            continue
        # 대기 구간과 다른 task 차지 구간의 겹침을 합집합으로 센다(둘이 함께 차지한 시간을 두 번 세지 않는다)
        cut = [(max(s, ready), min(e, start)) for o, held in spans.items() if o != tid for s, e in held
               if min(e, start) > max(s, ready)]
        minutes = union_minutes(cut)
        if minutes > 0:
            wait_min += minutes
            n_tasks += 1
    return wait_min, n_tasks, union_minutes(x for held in spans.values() for x in held), skipped, unready


def _cells(line):
    r"""표 행을 `|`로 가른 조각(맨 앞·맨 끝 조각 포함). `\|`는 칸 안 글자로 둔다."""
    return re.split(r"(?<!\\)\|", line)


# `폴더 대기: {흐름}` 뒤에 오는 조각 꼴. 끝은 칸 끝·공백·`/`·`;`·다른 조각의 머리 `폴더 대기: `다(`… 30분x`처럼 글자가
# 바로 이어지면 조각이 아니라 글, `{조각}{다른 조각}`처럼 붙은 두 조각은 각각 조각)
WAIT_TAIL = r" \d+분 \(\d+개\) / 흐름 작성 \d+분(?=[\s/;]|폴더 대기: |$)"
NOTE_SEP = re.compile(r"((?:(?<=\s)|^)[/;]+(?=\s|$)|;(?=\s))")   # 비고 칸 글 사이 구분자(put_segment)


def put_segment(cell, seg):
    """`비고` 칸 글을 조각 열로 보고 seg를 넣는다.
    칸에서 폴더 대기 조각(`WAIT_TAIL`의 끝 경계까지 맞는 것)을 먼저 찾고, 그 사이 글은 구분자에서 나눈다. 구분자는 폴더 대기 조각
    바로 앞·뒤에 붙은 `/`·`;` 덩어리(`{조각};a`, `a/{조각}`. 조각은 기계가 만든 꼴이라 붙은 것도 구분자다), 양옆이 공백이거나 칸
    맨 앞·끝·폴더 대기 조각 경계인 `/`·`;` 덩어리(` / `, 홀로 남은 `/`·`;`), 뒤에 공백이 오는 `;`(`; `)다. seg와 같은 흐름의 폴더
    대기 조각은 첫 자리 하나만 seg로 바꾸고 나머지는 버리며, 없으면 seg를 맨 끝에 더한다. 앞뒤 공백을 뗀 뒤 비었거나 `/`·`;`만
    남은 조각은 버리고, 나머지를 `; `로 잇는다. 다만 ` / ` 하나만 사이에 두고 이웃했던 두 글 조각은 ` / `로 잇는다(B 줄 안의 ` / `).
    폴더 대기 조각에 닿지 않은 글에 붙은 `/`·`;`는 글자 그대로 남는다(`a/b`, `;메모`, `메모 a/`, 칸 끝 `메모 a;`. 그래서
    `메모 a;`에 덧붙이면 `메모 a;; {seg}`). 조각 꼴 뒤에 글자가 바로 이어진 `{조각}x`는 글이다(`{조각}x / a; {seg}`). 구분자
    없이 붙은 두 조각 `{조각}{다른 조각}`은 각각 조각이다(같은 흐름이면 하나만 남는다). 사람이 쓴 글 안이라도 조각 꼴 바로 뒤에
    `폴더 대기: `가 붙으면 그 조각 꼴은 조각이다(`메모({조각}폴더 대기: 글)` → `메모(; {새 조각}; 폴더 대기: 글)`). 그래서 붙은 조각이 든 칸도 두 번 넣은 결과가 한 번 넣은 결과와 같다."""
    m = re.fullmatch(r"폴더 대기: (\S+)" + WAIT_TAIL, seg)
    pat = re.compile("폴더 대기: " + re.escape(m.group(1)) + WAIT_TAIL) if m else None
    wait = re.compile(r"(폴더 대기: \S+" + WAIT_TAIL + ")")
    items, placed = [], False   # (조각, 앞 조각과 ` / `로 잇는가)
    pieces = wait.split(cell)
    for i, piece in enumerate(pieces):
        if i % 2 == 1:   # 폴더 대기 조각
            if pat and pat.fullmatch(piece):
                if placed:
                    continue
                piece, placed = seg, True
            items.append((piece, False))
            continue
        if i > 0:   # 폴더 대기 조각 바로 뒤·앞에 붙은 `/`·`;`는 구분자로 뗀다
            piece = re.sub(r"^[/;]+", "", piece)
        if i < len(pieces) - 1:
            piece = re.sub(r"[/;]+$", "", piece)
        tokens = NOTE_SEP.split(piece)   # 글, 구분자, 글, … 차례
        last = None   # 이 글 덩어리에서 마지막으로 남긴 글 조각의 자리
        for j in range(0, len(tokens), 2):
            if re.fullmatch(r"[\s/;]*", tokens[j]):   # 비었거나 `/`·`;`만 남은 조각
                continue
            items.append((tokens[j].strip(), last == j - 2 and tokens[j - 1] == "/"))
            last = j
    if not placed:
        items.append((seg, False))
    return "".join((" / " if slash else "; ") + text if k else text for k, (text, slash) in enumerate(items))


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


STALL_NOTE = re.compile(r"\| 메모 \| [^|]*\| 멈춤 측정: 처리 못 한 반환 (\d+)개(?:, (\d+)분)?")
JOURNAL_TIME = re.compile(r"^- (\d{4}-\d\d-\d\d \d\d:\d\d(?::\d\d)?)(.*)")
RESUME_NOTE = re.compile(r"^ \| 재개 \||^ 재개\(")
RESUME_RETRACTED = re.compile(r"\| 메모 \| - \| 정정: 앞의 [^|]*재개 줄")   # 다른 세션이 잘못 남긴 줄을 메인이 정정한 줄(resume.md)


def empty_return_note(lines):
    """결과 없이 반환된 뒤 이어 쓰는 에이전트를 띄울 때까지의 시간(설계 A-R 문제 3). 줄이 없으면 빈 글."""
    opened, count, minutes, cells = {}, 0, 0, [[c.strip() for c in line.split("|")] for line in lines]
    for head, *rest in cells:
        if len(rest) < 2:
            continue
        try:
            when = datetime.strptime(head[2:18], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if rest[0] == devflow_lib.EMPTY_RETURN:
            count += 1
            opened.setdefault(rest[1], when)
        elif rest[0] == devflow_lib.EMPTY_RESUMED and rest[1] in opened:
            minutes += int((when - opened.pop(rest[1])).total_seconds() / 60)
    if not count:
        return ""
    return " · 결과 없이 반환 {}번 {}분".format(count, minutes) + (", 닫히지 않음 {}".format(len(opened)) if opened else "")


def stall_line(run_dir):
    """멈춤(설계 8.1절): `--record`가 적은 처리 못 한 반환의 합과, 재개 줄과 그 앞 journal 줄의 사이. 사이에는 `/clear` 대기와
    사람이 자리를 비운 시간이 섞인다. 재개 줄은 `- {시각} | 재개 |`와 옛 꼴 `- {시각} 재개(`만 세고, 그보다 옛 꼴은 세지 못한다.
    앞 줄보다 이른 줄(옛 실행의 손으로 쓴 시각)은 사이에 넣지 않고 따로 낸다."""
    path = os.path.join(run_dir, "journal.md")
    asks = returns = minutes = resumes = gap = backward = 0
    last = None
    lines = devflow_lib.read_text(path).splitlines() if os.path.isfile(path) else []
    for at, line in enumerate(lines):
        stall = STALL_NOTE.search(line)
        if stall:
            asks += 1
            returns += int(stall.group(1))
            minutes += int(stall.group(2) or 0)
        stamp = JOURNAL_TIME.match(line)
        if not stamp:
            continue
        try:
            when = datetime.strptime(stamp.group(1)[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if RESUME_NOTE.match(stamp.group(2)):
            if at + 1 < len(lines) and RESUME_RETRACTED.search(lines[at + 1]):
                continue
            resumes += 1
            gap += max(0, int((when - last).total_seconds() / 60)) if last else 0
        if last and when < last:
            backward += 1
        last = max(last, when) if last else when
    tail = empty_return_note(lines) + (" · 시각 거꾸로 {}줄".format(backward) if backward else "")
    return "- 멈춤: 잰 질문 {}번, 처리 못 한 반환 {}개 {}분 · 재개 {}번, 앞 기록과의 사이 {}분{}".format(asks, returns, minutes, resumes, gap, tail)


def measure(run_dir):
    """측정 기록의 비고 칸에 옮길 줄(설계 B 3.8, 멈춤)을 표준 출력에 낸다."""
    tasks = devflow_lib.load_tasks(run_dir)
    zero = zero_decision_approvals(tasks)
    print("- 결정 0 승인: " + (" · ".join("{} {}(한 마디 {})".format(k, n, s) for k, (n, s) in zero.items()) or "없음"))
    parts = []
    for p, (n, d) in perspective_counts(tasks).items():
        parts.append("{} {}(설계 판정 {})".format(p, n, d) if p in DESIGN_PERSPECTIVES else "{} {}".format(p, n))
    print("- 관점 지적: " + " · ".join(parts))
    print(stall_line(run_dir))
    for line in approval_measure(run_dir, tasks):
        print(line)
    line = deploy_reuse.measure_line(tasks)
    if line:
        print(line)
    return 0


CODE_APPROVAL_KINDS = tuple(kinds.IMPLEMENT_KINDS) + ("fix",)


QUOTED = re.compile(r'"([^"]+)"')
BULK_ANSWER = re.compile(r"이후\s*전체|나머지\s*자동|자동\s*승인|전부\s*자동|알아서")


def human_lines(t):
    """사람 답 줄: 따옴표 안 글이 있고 알림·점검 확인·메인 판단이 아닌 줄. 옛 꼴은 칸 없는 자유 문장이고 한 줄에 답이 여럿일 수 있다."""
    out = []
    for line in devflow_lib.record_lines(t):
        f = devflow_lib.record_fields(line)
        if len(f) >= 2 and f[1] in ("알림", "점검 확인"):
            continue
        if (len(f) > 2 and f[2].startswith("[메인]")) or line[2:].lstrip().startswith("(메인"):
            continue
        if QUOTED.search(line):
            out.append(line)
    return out


def answer_lines(t):
    """사람이 답한 줄. 위임으로 닫은 줄(`승인|위임 {층}`, `추천 닫음|위임 L1`)은 사람의 판단으로 세지 않는다."""
    return [line for line in human_lines(t) if not delegation.is_delegated_line(line)]


def is_bulk(t):
    """일괄 답으로 닫힘: 사람 줄이 모두 `위임 {층}` 답이거나 따옴표 안이 일괄 위임의 말이다(설계 2.1절은 이것을 묻는 승인에서 뺀다)."""
    quotes = [q for line in answer_lines(t) for q in QUOTED.findall(line)]
    return bool(human_lines(t)) and all(BULK_ANSWER.search(q) for q in quotes)


def is_asked(t):
    """묻는 승인: 사람이 답한 `완료` task. `--record "결과 승인|…"`은 `approval_mode`를 비우므로 빈 값도 사람 줄로 가린다."""
    if t.get("status") != kinds.DONE or is_bulk(t):
        return False
    mode = str(t.get("approval_mode", "") or "").strip()
    return mode == "승인" or (not mode and bool(human_lines(t)))


def _pushed_back(line):
    f = devflow_lib.record_fields(line)
    return bool(re.search(r"되물음|이의|고칠|고침|판단 안 됨", " ".join(f[1:3]) if len(f) >= 2 else line))


def is_stamp(t):
    """도장(설계 10절 P5, 2.1절): 묻는 승인에 정할 것이 없고(`zero_decision_approvals`와 같이 칸이 비면 0으로 보지 않음)
    되물음·이의·고칠 것이 없다."""
    if not is_asked(t) or any(str(t.get(k, "")).strip() != "0" for k in ("n_decide", "n_todo")):
        return False
    return not any(_pushed_back(l) for l in human_lines(t))


def is_plain_stamp(t):
    """도장 가운데 사람 줄이 모두 승인인 것. 화면 밖 선택을 답한 task(`변이 권한 거부 | 메인이 직접 돌림`)를 뺀다."""
    return is_stamp(t) and all(devflow_lib.approval_line(l) for l in human_lines(t))


def baseline_row(run_dir):
    """1.1.1 기준값 한 줄(설계 10절 P3, P5와 폴더 대기). 실행 폴더를 쓰지 않는다. 답은 `완료` task의 사람 답 줄 수다."""
    tasks = devflow_lib.load_tasks(run_dir)
    done = [t for t in tasks.values() if t.get("status") == kinds.DONE]
    asked = [t for t in done if is_asked(t)]
    code = [t for t in asked if t.get("kind") in CODE_APPROVAL_KINDS]
    wait = 0
    for flow in {t.get("flow") for t in tasks.values() if t.get("flow") and board.writes(t)}:
        wait += flow_wait(tasks, flow)[0]
    return {"run": os.path.basename(os.path.abspath(run_dir).rstrip("\\/")), "tasks": len(done),
            "answers": sum(len(answer_lines(t)) for t in done), "asked": len(asked), "bulk": sum(map(is_bulk, done)),
            "stamp": sum(map(is_stamp, asked)), "code": len(code),
            "code_stamp": sum(map(is_stamp, code)), "code_plain": sum(map(is_plain_stamp, code)), "folder_wait_min": wait}


# 실행 지도와 마무리 리뷰의 재료(설계 7.3절). 메인이 답을 적을 때 붙인 표지를 해석 없이 뽑는다
RISK_MARK = re.compile(r"\[위험 수용 (T[0-9]+)\]\s*")
DEFER_MARK = re.compile(r"\[실물 확인 미룸\]\s*")
MAIN_MARK = "[메인]"
ORIGINAL_HEAD = re.compile(r"\|\s*원문:")
TASK_ID = re.compile(r"T[0-9]+")
TASK_CELL = re.compile(r"\s*T[0-9]+(?:[\s,·]+T[0-9]+)*\s*")
NOT_BULK = re.compile(devflow_lib.RISK_REFUSED.pattern + r"|하지\s*마|말고")
MAIN_JUDGED = "메인 판단"
WHO_PERSON, WHO_DELEGATED, WHO_MAIN = "사람", "위임", "메인"
EXCLUDE_NOTE = "사람 지시로"
BASELINE_NAME = "기준선"
REQUEST_SECTIONS = ("요청 원문", "다시 연 요청")   # 사람이 쓴 글이라 기준선을 찾지 않는다
KEPT_OUTCOME = "유지"
ANSWER_NOT_FOUND = "배포 유지 {}, 확인 답 못 찾음"
HANDED_TO_NOTE = "배포 메모로 넘김 {}"
CLOSED, NOT_CLOSED = "닫힘 {}", "안 닫힘"


def task_block(t):
    kind = t.get("kind", "")
    return t.get("block") or (kinds.block_of(kind) if kind in kinds.KINDS else "")


def split_decision(line):
    """결정 줄을 (원문 앞 글, 원문 칸 글 또는 None, 관련 task)로 나눈다. 원문은 따옴표가 둘이거나 `|`가 들 수 있어(옛 실행의 꼴) 끝 칸만
    관련 칸으로 본다. 끝 칸에 따옴표가 있으면 원문의 조각이고, T 번호가 없으면 관련 칸이 아니다."""
    head = ORIGINAL_HEAD.search(line)
    if head is None:
        body, sep, last = line.rpartition("|")
        return (body, None, ", ".join(TASK_ID.findall(last))) if sep and TASK_CELL.fullmatch(last) else (line, None, "")
    rest = line[head.end():]
    body, sep, last = rest.rpartition("|")
    if sep and '"' not in last and TASK_ID.search(last):
        return line[:head.start()], body.strip(), ", ".join(TASK_ID.findall(last))
    return line[:head.start()], rest.strip(), ""


def is_superseded(line):
    """`→ 대체:`가 원문의 따옴표 밖에 있는가. 사람 말에 든 같은 글은 대체가 아니다."""
    before, original, _ = split_decision(line)
    return decisions.SUPERSEDED in before + QUOTED.sub("", original or "")


def live_decisions(run_dir):
    """(대체되지 않은 줄, 대체된 줄 수). 빈 줄과 제목만 뺀다. 들여쓴 줄과 형식 밖 줄도 표지를 찾도록 남긴다."""
    path = os.path.join(run_dir, "decisions.md")
    lines = [l.strip() for l in devflow_lib.read_text(path).splitlines()] if os.path.isfile(path) else []
    lines = [l for l in lines if l and not l.startswith("#")]
    live = [l for l in lines if not is_superseded(l)]
    return live, len(lines) - len(live)


def is_marked(line):
    """원문 앞에 표지가 있는 결정 줄. 표지가 든 줄은 따로 두는 칸으로 간다."""
    before = split_decision(line)[0]
    return bool(RISK_MARK.search(before) or DEFER_MARK.search(before)) or MAIN_MARK in before


def decision_row(line):
    """(시각, 결정, 정한 쪽, 관련 task) 또는 None(형식 밖). 옛 실행은 결정 칸을 `|`로 나눠 쓴 줄이 많아(mcp 61줄 가운데 41줄)
    `decisions.brief_lines`보다 넓게 `원문:` 칸 앞을 모두 결정으로 읽는다. 원문 없이 `메인 판단`인 줄은 메인이 정한 것이다."""
    if not line.startswith("- "):
        return None
    before, original, related = split_decision(line)
    cells = [c.strip() for c in before[2:].split("|")]
    if len(cells) < 2:
        return None
    if original is not None:
        who = WHO_DELEGATED if cells[1].startswith(WHO_DELEGATED) or (BULK_ANSWER.search(original) and not NOT_BULK.search(original)) else WHO_PERSON
        return cells[0], " | ".join(cells[1:]), who, related
    if len(cells) < 3 or not cells[-1].startswith(MAIN_JUDGED):
        return None
    return cells[0], " | ".join(cells[1:-1]), WHO_MAIN, related


def _mark_text(before, mark):
    return before[mark.end():].strip(" |")


def _mark_when(before, mark):
    """표지 앞 칸이 있으면 그 줄의 시각이다(칸 없는 들여쓴 줄은 빈 값)."""
    cut = before.find("|")
    return before[2:cut].strip() if before.startswith("- ") and 0 <= cut < mark.start() else ""


def risk_accepted(run_dir, tasks=None):
    """[(task, 항목, 시각)]. 원천은 decisions.md와 승인 기록의 `[위험 수용 T0xx]` 표지와, 표지 없는 승인 기록의 답 줄
    `승인|위험 수용|{원문}`이다(판별은 `devflow_lib.risk_accepted`와 같고, 시각 문턱은 보지 않는다). 같은 항목은 처음 줄 하나만 둔다."""
    tasks = devflow_lib.load_tasks(run_dir) if tasks is None else tasks
    out, seen = [], set()

    def add(tid, item, when):
        if (tid, item) not in seen:
            seen.add((tid, item))
            out.append((tid, item, when))

    records = [(None, line) for line in live_decisions(run_dir)[0]]
    records += [(tid, line) for tid, t in tasks.items() for line in devflow_lib.record_lines(t)]
    marked = set()
    for tid, line in records:
        before = split_decision(line)[0]
        mark = RISK_MARK.search(before)
        if mark:
            marked.add((mark.group(1), devflow_lib.answer_key(devflow_lib.record_quote(line))))
            add(mark.group(1), _mark_text(before, mark), _mark_when(before, mark))
        elif tid is not None and (tid, devflow_lib.answer_key(devflow_lib.record_quote(line))) not in marked:
            # 표지를 적은 위험은 그 표지 한 줄이다(결정 줄이 승인 기록보다 앞에 온다). 같은 원문일 때만 뺀다
            f = devflow_lib.record_fields(line)
            decision = f[2] if len(f) >= 3 else ""
            if decision.startswith("위험 수용") and not devflow_lib.RISK_REFUSED.search(decision) \
                    and devflow_lib.approval_line(line) and not devflow_lib.reused_answer(line):
                add(tid, "{}: {}".format(decision, devflow_lib.record_quote(line) or "-"), f[0])
    return out


def _answer_found(t, item):
    """그 배포 task의 승인 기록이나 `judge-run.md`에 항목 글이 있는가(공백 차이는 보지 않는다)."""
    path = os.path.join(t["_dir"], kinds.JUDGE_FILES["run"])
    text = t["_sections"].get("승인 기록", "") + "\n" + (devflow_lib.read_text(path) if os.path.isfile(path) else "")
    return " ".join(item.split()) in " ".join(text.split())


def _deferred_state(tasks, tid, item):
    """미룬 확인의 상태. 뒤 task만 보고, 틀릴 때 안 닫힘 쪽으로 틀린다(앞뒤를 모르면 안 닫힘)."""
    later = [o for i, o in tasks.items() if tid and i > tid]
    kept = [o for o in later if str(o.get("deploy_outcome", "") or "").strip() == KEPT_OUTCOME]
    for o in kept:
        if item and _answer_found(o, item):
            return CLOSED.format(o["id"])
    if kept:
        return ANSWER_NOT_FOUND.format(kept[0]["id"])
    wraps = [o["id"] for o in later if o.get("kind") == "wrap-up" and o.get("status") == kinds.DONE]
    return HANDED_TO_NOTE.format(wraps[0]) if wraps else NOT_CLOSED


def deferred_checks(run_dir, tasks):
    """[(미룬 흐름 리뷰 task, 항목, 확인할 곳, 상태)]. 원천은 승인 기록과 decisions.md의 `[실물 확인 미룸] {항목} → {확인할 곳}`이다."""
    marked = [(tid, line) for tid, t in tasks.items() for line in devflow_lib.record_lines(t)]
    marked += [(None, line) for line in live_decisions(run_dir)[0]]
    out, seen = [], set()
    for tid, line in marked:
        before, _, related = split_decision(line)
        mark = DEFER_MARK.search(before)
        if not mark:
            continue
        tid = (TASK_ID.findall(related) or [""])[0] if tid is None else tid
        item, _, place = _mark_text(before, mark).rpartition("→")
        item, place = (item.strip(), place.strip()) if item else (place.strip(), "")
        if (tid, item) not in seen:
            seen.add((tid, item))
            out.append((tid, item, place, _deferred_state(tasks, tid, item)))
    return out


def _bare(line):
    return line[2:] if line.startswith("- ") else line


def main_notes(run_dir, tasks):
    """`[메인]` 표지 줄(`- ` 뗀 글). 승인 기록은 앞에 task를 붙이고, decisions.md와 journal.md는 줄에 관련 task가 있다."""
    out = ["{} {}".format(tid, _bare(line)) for tid, t in tasks.items() for line in devflow_lib.record_lines(t) if MAIN_MARK in line]
    out += [_bare(line) for line in live_decisions(run_dir)[0] if MAIN_MARK in split_decision(line)[0]]
    path = os.path.join(run_dir, "journal.md")
    if os.path.isfile(path):
        out += [_bare(line) for line in devflow_lib.read_text(path).splitlines() if line.startswith("- ") and MAIN_MARK in line]
    return out


def screen_cell(t, name):
    """그 task result.md 「승인 화면」의 칸 글. 없으면 빈 글."""
    path = os.path.join(t["_dir"], "result.md")
    if not os.path.isfile(path):
        return ""
    return devflow_lib.sections(devflow_lib.sections(devflow_lib.read_text(path), level=2).get("승인 화면", ""), level=3).get(name, "")


def excluded_checks(run_dir, tasks):
    """사람 지시로 뺀 검증 줄(설계 7.1절 9): 「이번 실행의 값」의 `검증 제외`와, 그 때문에 확인하지 않았다고 적힌 칸과 판정 파일 줄."""
    out = flow_review.exclusions(run_dir)
    for tid, t in tasks.items():
        out += ["{} 확인 안 된 것: {}".format(tid, l.strip()) for l in screen_cell(t, "확인 안 된 것").splitlines() if EXCLUDE_NOTE in l]
        for name in kinds.JUDGE_FILES.values():
            path = os.path.join(t["_dir"], name)
            if os.path.isfile(path):
                out += ["{} {}: {}".format(tid, name, l.strip()) for l in devflow_lib.read_text(path).splitlines() if EXCLUDE_NOTE in l]
    return out


def baseline_lines(run_dir):
    """기준선 줄: `recon.md` 「기준선」 항목과, 물을 실패가 0일 때 메인이 `run.md`에 쓴 한 줄."""
    out = []
    recon = os.path.join(run_dir, "recon.md")
    if os.path.isfile(recon):
        part = devflow_lib.sections(devflow_lib.read_text(recon)).get(BASELINE_NAME, "")
        out += [l[2:].strip() for l in part.splitlines() if l.startswith("- ") and not devflow_lib.EMPTY_ITEM.match(l.strip())]
    run_md = os.path.join(run_dir, "run.md")
    if os.path.isfile(run_md):
        parts = devflow_lib.sections(devflow_lib.read_text(run_md))
        for title, part in parts.items():
            if not title.startswith(REQUEST_SECTIONS):
                out += [re.sub(r"^[-|\s]+", "", l).rstrip(" |") for l in part.splitlines() if BASELINE_NAME in l]
    return out


# 마무리 리뷰의 재료(설계 7.3절). 값을 못 읽으면 "없음"이 아니라 재지 못함을 낸다
REVIEW_MARKED = 5   # 성질 붙은 항목을 줄로 싣는 수. 나머지는 갈 곳별 건수다
UNMEASURED = "재지 못함: {}"
TEST_TOTAL = "시험 변화 합계"
TEST_VIEW = "시험 체계"
NOT_AFTER_BLOCKS = ("마무리", "배포")   # 흐름 리뷰 뒤의 줄을 모으는 쪽과 그 뒤 블록
PLACE_TASK = re.compile(r"(?<![A-Za-z0-9])T\d+(?!\d)")   # 뒤에 조사가 붙는다(`T113이 확인`)


def _cell_items(text):
    """칸 글을 항목으로 묶는다. `- `로 시작하지 않는 글도 버리지 않는다(`unverified_items`와 같다)."""
    out = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        if line.startswith("- ") or not out:
            out.append(line)
        else:
            out[-1] += "\n" + line
    return [i for i in out if not devflow_lib.EMPTY_ITEM.match(i.strip())]


def _goes_to(item):
    """확인 안 된 것의 갈 곳: 적힌 task, 배포, 탐침. 못 읽으면 안 적힘이다(건수는 사라지지 않는다)."""
    first = PLACE_TASK.search(MOVED_HEAD.sub("", item))
    if first:
        return first.group(0)
    return next((word for word in ("탐침", "배포") if word in item), "갈 곳 안 적힘")


MOVED_HEAD = re.compile(r"^- \[T\d+\]\s*")


def _kept_moved(item, tasks):
    """옮겨 온 줄은 원래 task가 끝났으면 거기서 뽑히므로 뺀다. 원래 task가 끝나지 않았으면 여기서만 보인다."""
    m = devflow_lib.MOVED_ITEM.match(item)
    return not m or tasks.get(item[3:].split("]")[0], {}).get("status") != kinds.DONE


def unverified_review(tasks, only=None):
    """(성질 붙은 항목 줄, 나머지 갈 곳별 건수 줄, 재지 못함 줄). 성질 붙은 항목은 다섯 줄까지 틀리면 무엇이 일어나는가가 적힌 글 그대로 싣는다."""
    marked, rest, broken = [], {}, []
    for tid, t in tasks.items():
        if t.get("status") != kinds.DONE or (only is not None and tid not in only):
            continue
        lines, problem, _ = unverified_items(os.path.join(t["_dir"], "result.md"))
        if problem:
            broken.append(UNMEASURED.format("{} {}".format(tid, problem)))
            continue
        for item in _cell_items("\n".join(lines)):
            if not _kept_moved(item, tasks):
                continue
            if devflow_lib.PROPERTY_MARK.search(item) and len(marked) < REVIEW_MARKED:
                marked.append("- {} {}".format(tid, item[2:] if item.startswith("- ") else item))
            else:
                place = _goes_to(item)
                rest[place] = rest.get(place, 0) + 1
    return marked, ["- 나머지 {}건(전체는 이 task의 unverified-list.md): {}".format(sum(rest.values()), " · ".join("{} {}".format(k, v) for k, v in sorted(rest.items())))] if rest else [], broken


def code_check_lines(run_dir, tasks, only=None):
    """사람이 코드로 본 곳 n, 남긴 곳 k와 위치, `지금 문제 있음`이 든 남긴 곳의 의견 줄(설계 11.1절). 흐름 리뷰가 닫히지 않은 흐름은 재지 못함이다."""
    seen = sum(places.answered_count(run_dir, tid) for tid, t in tasks.items()
               if t.get("kind") == "flow-verify" and (only is None or tid in only))
    left = places.run_left(run_dir, only)
    out = ["- 사람이 코드로 본 곳 {}, 남긴 곳 {}".format(seen, left["count"])] if seen or left["count"] else []
    out += left["where"]
    out += ["- 남긴 곳의 의견: " + line for line in left["problems"]]
    for flow in sorted({t.get("flow") for t in tasks.values() if t.get("flow") and devflow_lib.needs_judgment_record(t) and t.get("status") == kinds.DONE}):
        if devflow_lib.flow_role(flow) == "feature" and not any(t.get("kind") == "flow-verify" and t.get("flow") == flow and t.get("status") == kinds.DONE
                                                                for t in tasks.values()):
            out.append("- " + UNMEASURED.format("흐름 {}의 흐름 리뷰가 닫히지 않아 코드 확인이 없다".format(flow)))
    return out


def is_after_review(t, tasks):
    """흐름 리뷰가 이미 지난 task인가: 수정 흐름이거나, 그 흐름의 흐름 리뷰가 답을 받은 뒤에 시작했다. 흐름 밖의 task도 흐름 리뷰가 보지 않는다."""
    flow = t.get("flow", "")
    if not flow or devflow_lib.flow_role(flow) == "fixes":
        return True
    answered = [str(o.get("approved", "") or "") for o in tasks.values() if o.get("kind") == "flow-verify" and o.get("flow") == flow and o.get("status") == kinds.DONE]
    started = str(t.get("started", "") or "")
    return bool(answered and started and started >= min(answered))


def after_review_lines(tasks, only=None):
    """「흐름 리뷰 뒤에 바뀐 것」(설계 5.3절 6, 7, 11.1절): 흐름 뒤 수정의 목록과 판단 건수, 위치, `지금 문제 있음` 의견 줄, 알림으로 지나간 흐름 밖 task의 알릴 것.
    답을 받지 않는다. 코드 확인의 `이 코드만 고침`에서 온 수정은 그 task에서 코드로 물었으므로 뺀다. 옮겨 온 줄은 원래 task에서 싣는다."""
    out = []
    for tid, t in tasks.items():
        kind = t.get("kind", "")
        if t.get("status") != kinds.DONE or kind == "flow-verify" or task_block(t) in NOT_AFTER_BLOCKS or (only is not None and tid not in only):
            continue
        if kind == "merge" and any(v == "병합(충돌 해결)" and k.startswith(kinds.OWNED_POINT + ":") for k, v in devflow_lib.branch_judgements(t).items()):
            out.append("- [{}] 충돌을 사람 답 없이 끝냄: {}".format(tid, ", ".join(execmod.conflict_files(t)) or UNMEASURED.format("충돌 파일 줄 없음")))
        if not is_after_review(t, tasks) or devflow_lib.CODE_CHECK_ORIGIN in str(t.get("origin", "")):
            continue
        mode = str(t.get("approval_mode", "") or "").strip()
        if kind == "fix":
            line = "- [{}] {} ({}, 커밋 {})".format(tid, t.get("title", ""), mode or "-", t.get("commit", "") or "-")
            if devflow_lib.needs_judgment_record(t):
                try:
                    count, where, problems = places.fix_judgments(t)
                except (OSError, UnicodeError, ValueError) as e:
                    out.append(line + " | " + UNMEASURED.format(e))
                    continue
                out.append(line + " | 판단 {}건{}".format(count, " " + ", ".join(where) if where else ""))
                out += ["- [{}] 의견: {}".format(tid, raw) for raw in problems]
            else:
                out.append(line)
        if mode == "알림":
            out += ["- [{}] {}".format(tid, item[2:] if item.startswith("- ") else item)
                    for item in _cell_items(devflow_lib.without_moved_items(screen_cell(t, "알릴 것")))]
    return out


def test_total_lines(tasks, only=None):
    """전체 검증 시험 체계 관점의 합계 한 줄(설계 7.6절). 지적이 0이어도 오른다. 그 관점에 줄이 없거나, 흐름이 둘 이상인데 그 관점 task가 없으면 재지 못함이다.
    흐름 하나인 실행은 전체 검증이 없고 흐름 리뷰가 시험 변화를 묻는다."""
    out = []
    views = [t for t in tasks.values() if t.get("kind") == "full-verify" and TEST_VIEW in t["_sections"].get("범위", "")]
    features = {t.get("flow") for t in tasks.values() if t.get("flow") and devflow_lib.flow_role(t.get("flow")) == "feature"}
    if only is None and not views and (len(features) > 1 or any(t.get("kind") == "full-verify" for t in tasks.values())):
        out.append("- " + UNMEASURED.format("{} 관점 task가 없어 `{}:` 줄이 없다".format(TEST_VIEW, TEST_TOTAL)))
    for tid, t in tasks.items():
        if t.get("kind") != "full-verify" or t.get("status") != kinds.DONE or (only is not None and tid not in only):
            continue
        found = [l.strip().lstrip("- ") for name in kinds.CELLS for l in screen_cell(t, name).splitlines() if TEST_TOTAL in l]
        out += ["- {} {}".format(tid, l) for l in found]
        if not found and TEST_VIEW in t["_sections"].get("범위", ""):
            out.append("- " + UNMEASURED.format("{} 시험 체계 관점에 `{}:` 줄이 없다".format(tid, TEST_TOTAL)))
    return out


# 1.2.0 측정 칸(설계 10절, 11.1절 A-R). 실행 폴더를 읽기만 하고, 관문과 판정은 이 값을 읽지 않는다. 못 읽은 값은 0이 아니라 재지 못함이다
V120_MISSING = "1.2.0부터 시작한 {} 없음"
FORM_TASK, FORM_DECIDE, FORM_COMMAND, FORM_TODO, FORM_UNDERSTAND, FORM_OBJECT, FORM_OTHER = "task 승인", "정해 주실 것", "명령 단계", "하실 일", "이해 되물음", "이의 되물음", "그 밖"
QUESTION_FORMS = (FORM_TASK, FORM_DECIDE, FORM_COMMAND, devflow_lib.CODE_CHECK_ORIGIN, devflow_lib.TEST_CHANGE_POINT,
                  devflow_lib.REVIEW_OBJECTION, FORM_TODO, FORM_UNDERSTAND, FORM_OBJECT, FORM_OTHER)   # 정책 쪽 꼴은 1.3.0이다
COMMAND_POINT = re.compile(r"실행\s*승인|넣기\s*승인|직전\s*확인|결과\s*승인|L4 확인")
DECIDE_POINT = re.compile(r"^(?:정해 주실 것|항목\s|\d+(?:\s|$)|(?:[A-Z]+-)*[A-Z]+-?\d+(?:\s|$))")
DECIDE_ANSWER = re.compile(r"[(（][가-힣][)）]|^(?:[A-Z]+-)*[A-Z]+-?\d+\b")   # 지점이 `답`뿐인 옛 꼴은 결정 칸의 선택지나 항목 번호로 가른다
TODO_POINT = re.compile(r"^(?:하실 일|실물 확인)")
WHOLE_POINT = re.compile(r"^(?:승인|전체|보류|고칠 것|답\(고칠 것\)|나눠서 다시)")
MIXED, UNREAD_VALUE = "섞임", "읽지 못함"
PLACE_ANSWERS = (places.FINE, places.FIX_ONLY, places.UNJUDGED, places.REST, MIXED, UNREAD_VALUE)
PLACE_STATES = (places.WAITING, places.ANSWERED, places.LEFT_UNJUDGED, places.LEFT_BULK, places.LEFT_CAP, places.LEFT_DELEGATED)
OPINIONS = (places.PROBLEM, places.NO_PROBLEM, places.NO_OPINION)
NO_ANSWER = "답 없음"
LACK_CLIP = 60
NOT_RUN_REASONS = ("환경이 없음", "새 명령이 필요함", "사람 지시로 뺌", "런타임이 뜨지 않음", "권한 거부")   # references/kinds/verify/flow-review.md
NO_RESULT = "결과 없는 시나리오"
TIME_HEAD = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d(?::\d\d)?")
CARD_FILES = (".shown.md", ".tree.md")
MATERIAL_MISSING = "! 리뷰 자료 없음"   # screen.py가 찍는 줄의 머리
SHEET_MASKED = re.compile(r"<p>(\d+)줄을 가렸습니다\.</p>")   # visual.py의 고정 틀. 사람 글은 이스케이프되어 이 꼴이 되지 않는다
CARD_MASKED = re.compile(r"^\s*비밀값 꼴 (\d+)줄 가림$")   # places.py의 카드 줄


def question_form(t, line):
    """사람 답 줄 하나의 질문 꼴. 지점 칸이 자유 글이라 앞 낱말로 가르고, 못 가르면 `그 밖`이다(사라지지 않는다)."""
    f = devflow_lib.record_fields(line)
    point, decision = (f[1], f[2] if len(f) > 2 else "") if len(f) >= 2 else ("", "")
    for head in (devflow_lib.CODE_CHECK_ORIGIN, devflow_lib.TEST_CHANGE_POINT, devflow_lib.REVIEW_OBJECTION):
        if point.startswith(head):
            return head
    if point.startswith("되물음"):
        return FORM_OBJECT if "이의" in point else FORM_UNDERSTAND
    if TODO_POINT.match(point) or devflow_lib.HANDED_MARK.search(decision) or DEFER_MARK.search(decision):
        return FORM_TODO
    if COMMAND_POINT.search(point) or COMMAND_POINT.search(decision):
        return FORM_COMMAND
    if DECIDE_POINT.match(point) or (point.startswith("답") and DECIDE_ANSWER.search(decision)):
        return FORM_DECIDE
    whole = devflow_lib.approval_line(line) or bool(WHOLE_POINT.match(point))
    if whole and t.get("kind") in kinds.STAGE_KINDS:
        return FORM_COMMAND
    return FORM_TASK if whole else FORM_OTHER


def _tally(counts, order=()):
    """값이 있는 칸만 `이름 n`으로. order 밖의 이름은 뒤에 붙인다."""
    names = list(order) + [k for k in counts if k not in order]
    return ["{} {}".format(k, counts[k]) for k in names if counts.get(k)]


def _bump(counts, key):
    counts[key] = counts.get(key, 0) + 1


def _cell_text(text):
    """표 칸에 들어갈 사람 글: 가리고, `|`를 바꾸고, 자른다."""
    text = " ".join(devflow_lib.mask_line(str(text)).replace("|", "/").split())
    return text[:LACK_CLIP] + "…" if len(text) > LACK_CLIP else text


def answers_lines(tasks):
    """답 수(P3. 1.2.0은 규칙 몫이 없어 모두 `그 밖`이다)와 질문 꼴별 답."""
    done = [t for t in tasks.values() if t.get("status") == kinds.DONE]
    forms = {}
    for t in done:
        for line in answer_lines(t):
            _bump(forms, question_form(t, line))
    total = sum(forms.values())
    head = "- 답: 완료 task {}, 사람 답 {}, 답/task {}".format(len(done), total, "{:.2f}".format(total / len(done)) if done else "재지 못함")
    open_answers = sum(len(answer_lines(t)) for t in tasks.values() if t.get("status") != kinds.DONE)
    delegated = sum(len(human_lines(t)) - len(answer_lines(t)) for t in done)
    head += " · 완료 밖 task의 답 {}줄".format(open_answers) if open_answers else ""
    head += " · 위임으로 닫은 줄 {}".format(delegated) if delegated else ""
    return [head, "- 질문 꼴별 답: " + (" · ".join(_tally(forms, QUESTION_FORMS)) or "없음")]


def _line_count(path):
    return len(devflow_lib.read_text(path).splitlines())


def _card_files(t):
    folder = os.path.join(t["_dir"], "cards")
    return [os.path.join(folder, n) for n in sorted(os.listdir(folder))] if os.path.isdir(folder) else []


def reading_line(tasks):
    """읽을 줄 수(P3). 화면은 마지막으로 남긴 `screen-shown.md`이고, 카드는 처음 낸 장과 폴더 표다."""
    asked = [t for t in tasks.values() if is_asked(t)]
    screen = missing = 0
    for t in asked:
        path = os.path.join(t["_dir"], "screen-shown.md")
        if os.path.isfile(path):
            screen += _line_count(path)
        else:
            missing += 1
    cards = sum(_line_count(p) for t in tasks.values() for p in _card_files(t) if p.endswith(CARD_FILES))
    tail = " · " + UNMEASURED.format("화면을 남기지 않은 묻는 승인 {}".format(missing)) if missing else ""
    return "- 읽을 줄: 묻는 승인 {}, 화면 {}줄, 카드 {}줄{}".format(len(asked), screen, cards, tail)


def _new_tasks(tasks):
    return [t for t in tasks.values() if devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)]


def _screen_lines(t):
    """그 task의 `screen-shown.md` 줄 목록. 파일이 없으면 None."""
    path = os.path.join(t["_dir"], "screen-shown.md")
    return devflow_lib.read_text(path).splitlines() if os.path.isfile(path) else None


def flow_reading_line(tasks):
    """흐름마다 묻는 승인의 화면과 그 흐름 task의 카드를 합한 줄 수의 최댓값. 화면이 빠진 흐름은 값이 낮으므로 최댓값에서 빼고 수를 적는다."""
    totals, missing = {}, {}
    for t in tasks.values():
        flow = t.get("flow")
        if not flow:
            continue
        totals.setdefault(flow, 0)
        totals[flow] += sum(_line_count(p) for p in _card_files(t) if p.endswith(CARD_FILES))
        if is_asked(t):
            shown = _screen_lines(t)
            if shown is None:
                _bump(missing, flow)
            else:
                totals[flow] += len(shown)
    if not totals:
        return "- 흐름당 읽을 줄: " + UNMEASURED.format("흐름에 든 task 없음")
    measured = {f: n for f, n in totals.items() if f not in missing}
    if not measured:
        return "- 흐름당 읽을 줄: " + UNMEASURED.format("모든 흐름에 화면을 남기지 않은 묻는 승인이 있음")
    top = max(sorted(measured), key=measured.get)
    tail = " · " + UNMEASURED.format("화면을 남기지 않은 묻는 승인이 있는 흐름 {}".format(len(missing))) if missing else ""
    return "- 흐름당 읽을 줄: 최대 {}줄({}), 흐름 {}{}".format(measured[top], top, len(measured), tail)


def wrap_review_line(tasks):
    """마무리 리뷰 파일의 줄 수. 회차마다 하나다."""
    wraps = [t for t in tasks.values() if t.get("kind") == "wrap-up"]
    if not wraps:
        return "- 마무리 리뷰: " + UNMEASURED.format("마무리 task 없음")
    paths = [(t["id"], os.path.join(t["_dir"], devflow_lib.WRAP_REVIEW)) for t in wraps]
    found = ["{} {}줄".format(tid, _line_count(p)) for tid, p in paths if os.path.isfile(p)]
    missing = len(paths) - len(found)
    return "- 마무리 리뷰: " + " · ".join(found + ([UNMEASURED.format("리뷰 파일이 없는 마무리 {}".format(missing))] if missing else []))


def missing_material_line(tasks):
    """묻는 화면에 찍힌 `! 리뷰 자료 없음` 수. 1.2.0 앞 화면에는 이 줄이 없으므로 0으로 내지 않는다."""
    new = _new_tasks(tasks)
    if not new:
        return "- 리뷰 자료 없음: " + UNMEASURED.format(V120_MISSING.format("task"))
    screens = [(t, _screen_lines(t)) for t in new]
    shown = [lines for _, lines in screens if lines is not None]
    count = sum(any(l.startswith(MATERIAL_MISSING) for l in lines) for lines in shown)
    lost = sum(lines is None and is_asked(t) for t, lines in screens)
    tail = " · " + UNMEASURED.format("화면을 남기지 않은 묻는 승인 {}".format(lost)) if lost else ""
    return "- 리뷰 자료 없음: 묻는 화면 {} 가운데 {}{}".format(len(shown), count, tail)


def hidden_judgment_line(tasks):
    """숨은 판단 건수. 판정 파일의 꼴로는 `[설계:]`가 어디에도 없어 옮긴 줄과 판정자가 새로 찾은 줄을 가르지 못해 `숨은 판단:` 전체를 낸다."""
    codes = [t for t in tasks.values() if devflow_lib.needs_judgment_record(t) and t.get("status") == kinds.DONE]
    if not codes:
        return "- 숨은 판단: " + UNMEASURED.format(V120_MISSING.format("끝난 코드 task"))
    count = bad = unread = 0
    for t in codes:
        path = os.path.join(t["_dir"], kinds.JUDGE_FILES["read"])
        if not os.path.isfile(path) or "판단 대조" not in devflow_lib.sections(devflow_lib.read_text(path)):
            unread += 1
            continue
        for name, cells, _ in places._judge_lines(t):
            if name != "숨은 판단" or flow_review.EMPTY_VALUE.match(cells[0]):
                continue
            count += len(cells) >= 3
            bad += len(cells) < 3
    parts = ["`숨은 판단:` {}줄(`[설계:]`가 어디에도 없는 줄만 가르는 꼴이 없어 전체로 대신함)".format(count)]
    if bad:
        parts.append(UNMEASURED.format("칸이 모자란 줄 {}".format(bad)))
    if unread:
        parts.append(UNMEASURED.format("「판단 대조」가 없는 task {}".format(unread)))
    return "- 숨은 판단: " + " · ".join(parts)


def masked_line(tasks):
    """비밀값 꼴을 가린 줄 수: 남은 `sheet.html`의 끝 문장과 카드의 가림 줄. 터미널 출력은 남지 않는다."""
    new = _new_tasks(tasks)
    if not new:
        return "- 가림: " + UNMEASURED.format(V120_MISSING.format("task"))
    sheets = sheet_lines = card_lines = absent = 0
    for t in new:
        path = os.path.join(t["_dir"], "sheet.html")
        if os.path.isfile(path):
            sheets += 1
            found = SHEET_MASKED.search(devflow_lib.read_text(path))
            sheet_lines += int(found.group(1)) if found else 0
        elif is_asked(t):
            absent += 1
        for p in _card_files(t):
            if p.endswith(".shown.md"):
                card_lines += sum(int(m.group(1)) for m in map(CARD_MASKED.match, devflow_lib.read_text(p).splitlines()) if m)
    tail = " · 한 장 없는 묻는 승인 {}(실을 자료가 없었거나 만들지 못함)".format(absent) if absent else ""
    return "- 가림: 한 장 {}장 {}줄, 카드 {}줄{}".format(sheets, sheet_lines, card_lines, tail)


def place_answer_class(place):
    """곳 답 하나의 갈래와 `판단 안 됨`의 부족한 것들. 답이 없으면 (None, []). 판단마다 답이 갈리면 `섞임`이다."""
    answer = str(place.get("답", "") or "").strip()
    if not answer:
        return (UNREAD_VALUE if place.get("처리") == places.ANSWERED else None), []
    if answer == places.REST:
        return places.REST, []
    values = [value for _, value in places._decision_parts(answer)]
    if not all(places._decision_value_ok(v) for v in values):
        return UNREAD_VALUE, []
    lacks = [v[len(places.UNJUDGED):].strip() for v in values if v.startswith(places.UNJUDGED)]
    names = {places.FINE if v == places.FINE else (places.UNJUDGED if v.startswith(places.UNJUDGED) else places.FIX_ONLY) for v in values}
    return (names.pop() if len(names) == 1 else MIXED), lacks


def _place_seconds(run_dir, tasks, tid, key):
    """처음 낸 카드(`cards\\{키}.shown.md`의 시각)에서 곳 답 줄까지의 초. 파일이 없거나 시각이 답보다 늦으면(복사한 실행) None. 기록은 초까지만 적는다."""
    answered = board._epoch(places.answer_record(tasks, tid, key)[0])
    path = places.shown_path(run_dir, tid, key)
    if answered is None or not os.path.isfile(path):
        return None
    gap = answered - os.path.getmtime(path)
    return None if gap <= -1 else max(0, int(gap))


def _longest_streak(values):
    best = run = 0
    last = None
    for v in values:
        run = run + 1 if v == last else 1
        best, last = max(best, run), v
    return best


def code_check_measure(run_dir, tasks):
    """코드 확인의 곳 수와 답, 곳당 시간, 부족한 것, 의견. 흐름 리뷰가 없으면 모두 재지 못함이다."""
    reviews = [t for t in tasks.values() if devflow_lib.flow_review_rules(t)]
    if not reviews:
        missing = UNMEASURED.format(V120_MISSING.format("흐름별 검증"))
        return ["- {}: {}".format(name, missing) for name in ("코드 확인", "곳 답", "곳당 시간", "코드 의견")]
    states, answers, opinions, unread_states, unread_opinions = {}, {}, {}, 0, 0
    lacks, seconds, secure_seconds, no_time, shown, secure, no_file, unmeasured, streak, trees = [], [], [], 0, 0, 0, 0, 0, 0, 0
    for t in reviews:
        tid = t["id"]
        if not os.path.isfile(places.path_of(run_dir, tid)):
            no_file += 1
            continue
        plist = places.read(run_dir, tid)
        unmeasured += len(places.unmeasured_tasks(run_dir, tid))
        shown += places.total_cards(plist)
        secure += sum(p.get("보안") == "예" for p in plist)
        trees += sum(p.endswith(".tree.md") for p in _card_files(t))
        said = []
        for p in plist:
            if p.get("처리") in PLACE_STATES:
                _bump(states, p["처리"])
            else:
                unread_states += 1
            name, lacking = place_answer_class(p)
            if name:
                _bump(answers, name)
            lacks += lacking
            if p.get("의견") in OPINIONS:
                _bump(opinions.setdefault(p["의견"], {}), name or NO_ANSWER)
            else:
                unread_opinions += 1
            if name and name != UNREAD_VALUE:
                gap = _place_seconds(run_dir, tasks, tid, p["key"])
                if gap is None:
                    no_time += 1
                else:
                    seconds.append(gap)
                    if p.get("보안") == "예":
                        secure_seconds.append(gap)
                when, quote = places.answer_record(tasks, tid, p["key"])
                said.append((when, devflow_lib.answer_key(quote)))
        streak = max(streak, _longest_streak([q for _, q in sorted(said)]))
    head = ["- 코드 확인: 흐름 리뷰 {}".format(len(reviews))]
    if no_file:
        head.append("곳 파일 없음 {}".format(no_file))
    if no_file < len(reviews):
        head.append("보일 곳 {}".format(shown))
        head.append("보안 곳 {}".format(secure))
    head += _tally(states, PLACE_STATES)
    if unread_states:
        head.append(UNMEASURED.format("처리를 읽지 못한 곳 {}".format(unread_states)))
    head.append("보안 신호를 재지 못한 task {}".format(unmeasured))
    lines = [" · ".join(head)]
    if no_file == len(reviews):
        return lines + ["- {}: {}".format(name, UNMEASURED.format("곳 파일이 없음")) for name in ("곳 답", "곳당 시간", "코드 의견")]
    stamped = answers.get(places.FINE, 0) + answers.get(places.REST, 0)
    lines.append("- 곳 답: " + " · ".join(_tally(answers, PLACE_ANSWERS) + ["코드 도장 {}/{}".format(stamped, sum(answers.values()))]))
    time = []
    if seconds:
        time.append("중앙값 {}초, 최대 {}초(잰 곳 {})".format(int(statistics.median(seconds)), max(seconds), len(seconds)))
    if secure_seconds:
        time.append("보안 곳 중앙값 {}초(잰 곳 {})".format(int(statistics.median(secure_seconds)), len(secure_seconds)))
    if no_time:
        time.append(UNMEASURED.format("시각이 없는 곳 {}".format(no_time)))
    if not seconds and not no_time:
        time.append("잰 곳 0")
    time += ["같은 답 연속 최대 {}".format(streak), "폴더 표 요청 {}".format(trees), UNMEASURED.format("전체 요청(기록 없음)")]
    lines.append("- 곳당 시간: " + " · ".join(time))
    if lacks:
        lines.append("- 판단 안 됨의 부족한 것: " + " / ".join(_cell_text(x) for x in lacks))
    rows = ["{} {}({})".format(o, sum(opinions[o].values()), ", ".join(_tally(opinions[o], PLACE_ANSWERS + (NO_ANSWER,)))) for o in OPINIONS if o in opinions]
    if unread_opinions:
        rows.append(UNMEASURED.format("읽지 못한 의견 {}".format(unread_opinions)))
    lines.append("- 코드 의견: " + (" · ".join(rows) or "없음"))
    return lines


def flow_stamp_line(tasks):
    """흐름 리뷰 도장(10절 P5): 정할 것과 이의가 없는 묻는 흐름 리뷰. 「하실 일」 때문에 늘 낮게 나오므로 그 칸으로 나눠 센다."""
    plain, todo, unread, understood = [0, 0], [0, 0], 0, 0
    for t in tasks.values():
        if t.get("kind") != "flow-verify" or t.get("status") != kinds.DONE:
            continue
        understood += sum(question_form(t, l) == FORM_UNDERSTAND for l in answer_lines(t))
        if not is_asked(t):
            continue
        decide, need = str(t.get("n_decide", "")).strip(), str(t.get("n_todo", "")).strip()
        if not decide.isdigit() or not need.isdigit():
            unread += 1
            continue
        row = todo if int(need) else plain
        row[1] += 1
        row[0] += int(decide) == 0 and not any(_pushed_back(l) for l in human_lines(t))
    parts = ["하실 일 없음 {}/{}".format(*plain), "하실 일 있음 {}/{}".format(*todo)]
    if unread:
        parts.append(UNMEASURED.format("칸이 빈 흐름 리뷰 {}".format(unread)))
    return "- 흐름 리뷰 도장: " + " · ".join(parts + ["이해 되물음 {}".format(understood)])


def before_after_line(tasks):
    """전·후를 돌리지 못한 흐름과 이유(10절 흐름 리뷰). 시나리오 하나라도 못 읽으면 그 흐름은 재지 못함이고, 고른 것보다 결과가 적으면 일부다."""
    reviews = [t for t in tasks.values() if devflow_lib.flow_review_rules(t)]
    if not reviews:
        return "- 전·후: " + UNMEASURED.format(V120_MISSING.format("흐름별 검증"))
    closed = [t for t in reviews if t.get("status") == kinds.DONE]
    ran, partial, not_run, unread, reasons = 0, [], [], [], {}
    for t in closed:
        data = flow_review.read(t)
        name = t.get("flow", "") or t["id"]
        if data["problem"]:
            unread.append(name)
            continue
        states = [flow_review.state(row) for row in data["rows"]]
        path = os.path.join(t["_dir"], "result.md")
        picked = flow_review.picked_count(devflow_lib.read_text(path)) if os.path.isfile(path) else None
        short = max(0, (picked or 0) - len(states))
        for row, now in zip(data["rows"], states):
            if now in (flow_review.NOT_RUN, flow_review.PARTIAL):
                why = flow_review._why(row)
                _bump(reasons, next((r for r in NOT_RUN_REASONS if r in why), FORM_OTHER))
        if short:
            reasons[NO_RESULT] = reasons.get(NO_RESULT, 0) + short
        if flow_review.UNREAD in states:
            unread.append(name)
        elif all(s == flow_review.RAN for s in states) and not short:
            ran += 1
        elif all(s == flow_review.NOT_RUN for s in states) and not short:
            not_run.append(name)
        else:
            partial.append(name)

    def named(label, names):
        return "{} {}({})".format(label, len(names), ", ".join(names)) if names else "{} 0".format(label)

    parts = ["흐름 리뷰 {}".format(len(closed)), "전부 돌림 {}".format(ran), named("일부", partial), named("못 돌림", not_run), named(flow_review.UNREAD, unread)]
    if len(closed) < len(reviews):
        parts.append("닫히지 않은 흐름 리뷰 {}".format(len(reviews) - len(closed)))
    if reasons:
        parts.append("이유: " + ", ".join(_tally(reasons, NOT_RUN_REASONS)))
    return "- 전·후: " + " · ".join(parts)


def notified_line(tasks):
    """알림으로 바꾼 것(10절, 5.3절 6, 7). 1.2.0부터 시작한 task만 본다. 기록에 없는 값은 재지 못함으로 적는다."""
    new = [t for t in tasks.values() if devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)]
    if not new:
        return "- 알림으로 바꾼 것: " + UNMEASURED.format(V120_MISSING.format("task"))
    passed = [t for t in new if t.get("status") == kinds.DONE and str(t.get("approval_mode", "")).strip() == "알림"]
    merges = [t for t in passed if t.get("kind") == "merge"]
    conflicts = sum(any(v == "병합(충돌 해결)" for v in devflow_lib.branch_judgements(t).values()) for t in merges)
    wraps = sum(t.get("kind") == "wrap-up" for t in passed)
    moved = sum(t.get("kind") == "change" and devflow_lib.user_origin(t) and devflow_lib.is_design_revision(t) for t in passed)
    verifies = sum(t.get("kind") == "full-verify" for t in passed)
    objections = sum(_pushed_back(l) and question_form(t, l) != FORM_UNDERSTAND for t in new if t.get("kind") == "wrap-up" for l in answer_lines(t))
    return ("- 알림으로 바꾼 것: 합치기 {} · 합치기 충돌 수정 {} · 마무리 결과 {} · 답만 옮긴 설계 고친 판 {} · 지적 0 전체 검증 {}"
            " · 마무리의 이의 {}(어느 칸인지 가리지 못함) · {}").format(
        len(merges), conflicts, wraps, moved, verifies, objections, UNMEASURED.format("받아오기 충돌 수정(메인 기록의 꼴 없음), 뒤에 문제가 드러난 수(기록 칸 없음)"))


def _record_time(line):
    m = TIME_HEAD.match(line[2:].strip())
    return m.group(0) if m else None


def delegation_line(run_dir, tasks):
    """위임(10절): 횟수, 원문, 그 앞 위임 뒤로 받은 승인 수, `[메인]` 표지 줄 수. 위임을 내린 줄과 메인의 기록 줄은 횟수에 넣지 않는다."""
    rows = [(line, decision_row(line)) for line in live_decisions(run_dir)[0]]
    given, said_last = [], None
    for line, row in rows:
        if not row or row[2] != WHO_DELEGATED:
            continue
        if re.match(r"위임\s+없음", row[1]):
            said_last = None
            continue
        quote = QUOTED.search(split_decision(line)[1] or "")
        said = quote.group(1) if quote else None
        if said is None or said != said_last:   # 옛 실행은 같은 위임 말을 task마다 적었다
            given.append((row[0], said))
        said_last = said
    approvals, no_time = [], 0
    for t in tasks.values():
        for line in answer_lines(t):
            if devflow_lib.approval_line(line):
                when = _record_time(line)
                if when:
                    approvals.append(when)
                else:
                    no_time += 1
    parts = ["횟수 {}".format(len(given)), "[메인] 줄 {}".format(len(main_notes(run_dir, tasks))),
             "일괄로 닫은 task {}".format(sum(is_bulk(t) for t in tasks.values() if t.get("status") == kinds.DONE))]
    last = ""
    for when, text in given:
        said = '"{}"'.format(_cell_text(text)) if text else "원문 없음"
        if TIME_HEAD.match(when):
            parts.append("{} 직전 승인 {}".format(said, sum(last <= at < when for at in approvals)))
            last = when
        else:
            parts.append("{} 직전 승인 재지 못함".format(said))
    if no_time and given:
        parts.append("시각 못 읽은 승인 {}줄 뺌".format(no_time))
    return "- 위임: " + " · ".join(parts)


DESIGN_ROOT = re.compile(r"뿌리:\s*설계")
ENV_UNJUDGED = re.compile(r"판정불가 환경:")


def _minutes(t):
    """물은 때(`approval_requested`)부터 답한 때(`approved`)까지 분. 못 읽으면 None."""
    try:
        start, end = [datetime.strptime(str(t.get(k, ""))[:16], "%Y-%m-%d %H:%M") for k in ("approval_requested", "approved")]
    except ValueError:
        return None
    return max(0, int((end - start).total_seconds() / 60))


def _median(values):
    return "재지 못함" if not values else "{}분".format(int(statistics.median(values)))


def contract_lines(tasks):
    """계약별 리뷰와 사람이 직접 내린 판단(10절). 1.2.0부터 시작한 묻는 task만, 빈 계약은 고치는 정본에 따르므로 `그 밖`으로 센다."""
    rows = {}
    for t in _new_tasks(tasks):
        if is_asked(t):
            k = kinds.KINDS[t["kind"]].review if t.get("kind") in kinds.KINDS else ""
            rows.setdefault(k or FORM_OTHER, []).append(t)
    if not rows:
        return ["- 계약별 리뷰: " + UNMEASURED.format("묻는 task 없음"), "- 직접 내린 판단: " + UNMEASURED.format("묻는 task 없음")]
    out, decided = [], []
    for name, group in sorted(rows.items()):
        lines = [(t, l) for t in group for l in answer_lines(t)]
        said = sum(question_form(t, l) == FORM_DECIDE for t, l in lines)
        out.append("{} {}(시간 {}, 바꾼 답 {}, 이해 되물음 {}, 도장 {})".format(
            name, len(group), _median([m for m in map(_minutes, group) if m is not None]),
            sum(_pushed_back(l) and question_form(t, l) != FORM_UNDERSTAND for t, l in lines),
            sum(question_form(t, l) == FORM_UNDERSTAND for t, l in lines), sum(is_stamp(t) for t in group)))
        if said:
            decided.append("{} {}".format(name, said))
    return ["- 계약별 리뷰: " + " · ".join(out), "- 직접 내린 판단: " + (" · ".join(decided) or "0")]


def design_approval_line(tasks):
    """설계 승인(10절): 설계 승인 수, 시간 중앙값, 설계 승인의 이의, 그 뒤 구현에서 나온 이의. 이의가 접근에 관한 것인지는 가리지 못한다."""
    designs = [t for t in _new_tasks(tasks) if t.get("kind") == "design" and t.get("status") == kinds.DONE]
    if not designs:
        return "- 설계 승인: " + UNMEASURED.format(V120_MISSING.format("설계"))
    objected = sum(question_form(t, l) == FORM_OBJECT for t in designs for l in answer_lines(t))
    later = sum(question_form(t, l) == FORM_OBJECT for t in _new_tasks(tasks) if t.get("kind") in CODE_APPROVAL_KINDS for l in answer_lines(t))
    return "- 설계 승인: {}건, 시간 {}, 이의 {}, 뒤 구현의 이의 {}(접근인지 가리지 못함)".format(
        len(designs), _median([m for m in map(_minutes, designs) if m is not None]), objected, later)


def boundary_line(run_dir, tasks):
    """책임 경계(10절). 미룬 실물 확인만 기록에서 읽고 나머지는 기록 칸이 없어 재지 못한다."""
    checks = deferred_checks(run_dir, tasks)
    states = {}
    for _tid, _item, _place, state in checks:
        _bump(states, state)
    return "- 책임 경계: 미룬 실물 확인 {}({}) · {}".format(
        len(checks), ", ".join(_tally(states)) or "없음",
        UNMEASURED.format("로컬 사실로 생긴 변경 task, 판정자가 짚은 사용자 결정, 탐침 뒤 다시 물은 결정, 흐름 지도가 놓친 겹침, 전체 검증이 다시 짚은 기준(기록 칸 없음)"))


def sheet_layer_line(tasks):
    """한 장(10절)의 이의 층. 이의 답에 한 장 번호가 없어 층을 가르지 못하므로 수만 낸다."""
    if not _new_tasks(tasks):
        return "- 한 장 이의: " + UNMEASURED.format(V120_MISSING.format("task"))
    objected = sum(question_form(t, l) == FORM_OBJECT for t in _new_tasks(tasks) for l in answer_lines(t))
    return "- 한 장 이의: {}(모양·규칙·변경분은 {})".format(objected, UNMEASURED.format("답에 한 장 번호 없음"))


def test_change_measure_line(tasks):
    """시험 변화(10절): 변화 종류별 줄과 답."""
    if not _new_tasks(tasks):
        return "- 시험 변화: " + UNMEASURED.format(V120_MISSING.format("task"))
    kinds_of, answers = {}, {}
    for t in _new_tasks(tasks):
        for row in devflow_lib.test_change_rows(t, tasks):
            _bump(kinds_of, row.get("change") or FORM_OTHER)
        for line in answer_lines(t):
            f = devflow_lib.record_fields(line)
            if len(f) >= 3 and f[1] == devflow_lib.TEST_CHANGE_POINT:
                _bump(answers, f[2].split()[-1] if f[2].split() else FORM_OTHER)
    return "- 시험 변화: {} · 답 {}".format(" · ".join(_tally(kinds_of)) or "없음", ", ".join(_tally(answers)) or "없음")


def design_root_line(tasks):
    """설계 뿌리 결함(10절): 검증 결과의 `뿌리:` 칸. `뿌리: 설계`가 설계를 그대로 따라 생긴 지적이다."""
    closed = [t for t in _new_tasks(tasks) if t.get("kind") in kinds.VERIFY_KINDS and t.get("status") == kinds.DONE]
    if not closed:
        return "- 설계 뿌리 결함: " + UNMEASURED.format(V120_MISSING.format("끝난 검증 task"))
    found = 0
    for t in closed:
        path = os.path.join(t["_dir"], "result.md")
        if os.path.isfile(path):
            found += len(DESIGN_ROOT.findall(devflow_lib.read_text(path)))
    return "- 설계 뿌리 결함: {}".format(found)


def stall_more_line():
    """멈춤(10절)에서 기록이 없는 칸."""
    return "- 멈춤 그 밖: " + UNMEASURED.format("실행 전체 설계 대기, 설계 승인이 종합을 기다린 시간(기록 칸 없음)")


def slot_line(run_dir, tasks):
    """작업 칸(설계 8.3절): 칸 수와 흔들림. 칸 2 실행에서 1 실행보다 늘면 시작값을 1로 되돌리는 근거다. 칸 1이면 줄을 내지 않는다."""
    count = slots.slot_count(run_dir)
    if count < 2:
        return []
    path = os.path.join(run_dir, "journal.md")
    journal_text = devflow_lib.read_text(path) if os.path.isfile(path) else ""
    retried = sum(int(str(t.get("retry", "0") or "0")) for t in tasks.values() if str(t.get("retry", "0") or "0").isdigit())
    unjudged = sum(len(ENV_UNJUDGED.findall(devflow_lib.read_text(os.path.join(t["_dir"], n))))
                   for t in tasks.values() for n in kinds.JUDGE_FILES.values() if os.path.isfile(os.path.join(t["_dir"], n)))
    return ["- 작업 칸: {} · 재시도 {} · 판정불가 환경 {} · 넣기 충돌 {} · 넣은 뒤 확인 실패 {}".format(
        count, retried, unjudged, journal_text.count("| 넣기 충돌 |"), journal_text.count("| 넣은 뒤 확인 실패 |"))]


def sheet_upload_line(run_dir):
    """한 장 올리기의 값과 올린 횟수, 못 올린 횟수. 횟수는 journal의 표지만 센다."""
    path = os.path.join(run_dir, "journal.md")
    marks = [line.split(" | ")[1].strip() for line in (devflow_lib.read_text(path).splitlines() if os.path.isfile(path) else [])
             if line.startswith("- ") and line.count(" | ") >= 2]
    return "- 한 장 올리기: {}, 올림 {}, 못 올림 {}".format(devflow_lib.sheet_upload(run_dir), marks.count(devflow_lib.SHEET_SENT), marks.count(devflow_lib.SHEET_FAILED))


def approval_measure(run_dir, tasks):
    """1.2.0 칸(설계 10절과 11.1절의 경계 표). 정책과 규약 칸은 1.3.0이다."""
    return answers_lines(tasks) + [reading_line(tasks), flow_reading_line(tasks), wrap_review_line(tasks), missing_material_line(tasks), masked_line(tasks)] \
        + code_check_measure(run_dir, tasks) + [hidden_judgment_line(tasks), flow_stamp_line(tasks), before_after_line(tasks), notified_line(tasks), delegation_line(run_dir, tasks), sheet_upload_line(run_dir)]         + contract_lines(tasks) + [design_approval_line(tasks), boundary_line(run_dir, tasks), sheet_layer_line(tasks), test_change_measure_line(tasks),
                                   design_root_line(tasks), stall_more_line()] + slot_line(run_dir, tasks)


def write_risk_accepted(run_dir, out_dir, tasks):
    risks = risk_accepted(run_dir, tasks)
    lines = ["# 받아들인 위험 (collect.py가 decisions.md와 승인 기록의 위험 수용 표지와 답에서 뽑음)", ""]
    lines += ["- {} {}{}".format(tid, item, " ({})".format(when) if when else "") for tid, item, when in risks]
    if not risks:
        lines.append("- 표지 없음(백로그의 위험 수용은 따로 본다)")
    path = os.path.join(out_dir, "risk-accepted.md")
    devflow_lib.write_text(path, "\n".join(lines) + "\n")
    print("받아들인 위험 {}개 -> {}".format(len(risks), path))


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) == 3 and argv[2] == "--baseline":
        print(json.dumps(baseline_row(argv[1]), ensure_ascii=False))
        return 0
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
    deferred = {}   # 미룬 실물 확인은 그 흐름 리뷰 task의 「확인 안 된 것」이다(설계 7.4절 라)
    for tid, item, place, _ in deferred_checks(run_dir, tasks):
        deferred.setdefault(tid, []).append("- [실물 확인 미룸] {} → {}".format(item, place))
    for tid, t in tasks.items():
        if t.get("status") != kinds.DONE:
            continue
        items, problem, warning = unverified_items(os.path.join(t["_dir"], "result.md"))
        if devflow_lib.flow_review_rules(t):
            items = items + flow_review.unverified_items(t)   # 전·후는 작성자 뒤에 돌아 결과 파일에 없다
        if not problem:
            items = items + deferred.pop(tid, [])
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

    for tid, items in deferred.items():   # 아직 닫히지 않았거나 task를 못 찾은 표지도 잃지 않는다
        n_items += len(items)
        blocks.append("## {}\n{}".format(tid or "task 모름", "\n".join(items)))
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
    write_risk_accepted(run_dir, out_dir, tasks)
    if warnings:
        print("형식 경고 {}개(목록 위)".format(len(warnings)))
    if problems:
        print("뽑지 못한 task {}개(목록 맨 위)".format(len(problems)))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
