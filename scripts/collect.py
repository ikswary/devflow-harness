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
  종료 코드: 0 정상(칸이 빠진 형식 경고는 목록 위에 적고 0), 2 사용법 오류,
             3 result.md나 「승인 화면」 절이 없는 `완료` task가 있음(목록 맨 위에 적힌다)
"""
import os
import sys

import devflow_lib
import kinds


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
        blocks.append("\n".join(part))
    path = os.path.join(out_dir, "notified-{}.md".format(flow))
    devflow_lib.write_text(path, "# 흐름 {}에서 알림으로 지나간 task (collect.py)\n\n".format(flow) + ("\n\n".join(blocks) or "- 없음") + "\n")
    print("알림으로 지나간 task {}개 -> {}".format(len(blocks), path))
    return 0


def main(argv):
    devflow_lib.utf8_stdout()
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
