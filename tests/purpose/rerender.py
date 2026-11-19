"""목적 시험 화면 다시 그리기: 지난 실행 폴더의 사본을 한 task가 승인을 요청한 때의 상태로 자른다.

사용:
  python tests/purpose/rerender.py --run DIR --task TID --out DIR

- `--run`: 원본 실행 폴더(`tasks/`를 가진 폴더). 읽기만 하고 바꾸지 않는다.
- 만드는 것: `{out}/{원본 폴더 이름}`(원본 사본과 표지 파일 `.purpose-rerender`). 자르는 시각은 대상 task 머리 파일의
  `approval_requested`다. 사본을 `python scripts/screen.py {사본} {TID}`로 그리면 그때의 화면을 지금 스크립트로 다시 그린다.
- 자르는 규칙(설계 5절 R):
  1. 자르는 시각보다 늦게 만든(`created`) task 폴더를 지운다.
  2. 남은 머리 파일의 「승인 기록」에서 시각이 자르는 시각보다 늦은 줄(들여 쓴 하위 줄 포함)을 지운다.
  3. 자르는 시각보다 늦게 승인한(`approved`) 다른 task는 `status: 진행`, `approved` 빔.
  4. 대상 task는 `status: 승인대기`, `approval_mode`·`approved` 빔.
  5. 대상 task가 단계 kind(`kinds.STAGE_KINDS`)면 `stage: 결과승인`.
  머리 파일 없는 task 폴더, decisions.md·journal.md·`approved/`·`asked/`는 자르지 않는다.
- 지우는 것: `{out}/{원본 폴더 이름}`이 이미 있으면 표지가 있을 때만 지우고 다시 만든다.
- 종료 코드: 0 만듦, 3 거부(`--out`이 원본 안이거나 사본 자리가 원본을 덮음, 이 저장소 안 `_workspace/` 밖의 `--out`
  (setup_task.py `out_refusal`), 표지 없는 출력 폴더, 대상 머리 파일이나 `approval_requested`가 없음).
"""
import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = ".purpose-rerender"
REFUSED = 3
STAGE_RESULT = "결과승인"
WAITING, WORKING = "승인대기", "진행"   # kinds.STATUSES의 두 값
RECORD_SECTION = "승인 기록"
RECORD_TIME = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)\b")

sys.dont_write_bytecode = True   # tests/purpose/·scripts/ 아래에 __pycache__를 남기지 않는다
sys.path.insert(0, HERE)
import setup_task  # noqa: E402  (sys.path에 scripts/를 넣고 devflow_lib를 읽는다)
import devflow_lib  # noqa: E402
import kinds  # noqa: E402


class Refuse(Exception):
    """거부(종료 3). 메시지는 무엇이 안 되는지 한 줄."""


def _real(path):
    return os.path.normcase(os.path.realpath(path))


def _inside(path, base):
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:   # 드라이브가 다름
        return False


def place_refusal(run, out):
    """사본 자리를 거부할 까닭(없으면 None). `--out`이 원본 안이거나, 사본 자리가 원본이거나 원본을 품으면 거부."""
    run_r, out_r = _real(run), _real(out)
    dst_r = os.path.join(out_r, os.path.basename(run_r))
    if _inside(out_r, run_r):
        return "--out이 원본 실행 폴더 안임: {}".format(out)
    if _inside(run_r, dst_r):
        return "사본 자리가 원본 실행 폴더를 덮음: {}".format(dst_r)
    return setup_task.out_refusal(out)


def prepare(run, dst):
    if os.path.exists(dst):
        if not os.path.isfile(os.path.join(dst, MARKER)):
            raise Refuse("출력 폴더가 이미 있고 표지 {}가 없음(이 스크립트가 만든 폴더가 아님): {}".format(MARKER, dst))
        setup_task.remove(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copytree(run, dst)
    with open(os.path.join(dst, MARKER), "w", encoding="utf-8") as f:
        f.write("tests/purpose/rerender.py가 만든 잘린 사본. 다시 돌리면 지우고 새로 만든다.\n")


def drop_late_records(doc, cut):
    """「승인 기록」에서 시각이 cut보다 늦은 줄과 그 하위 줄을 지운다. 지운 줄 수를 돌려준다."""
    body = doc.section(RECORD_SECTION)
    if not body:
        return 0
    kept, dropping, dropped = [], False, 0
    for line in body.split("\n"):
        if line.startswith("- "):
            m = RECORD_TIME.match(line)
            dropping = bool(m) and m.group(1) > cut
        elif not (line[:1].isspace() and line.strip()):
            dropping = False   # 빈 줄이나 목록 밖 줄은 앞 항목의 하위 줄이 아니다
        if dropping:
            dropped += 1
        else:
            kept.append(line)
    if dropped:
        doc.set_section(RECORD_SECTION, "\n".join(kept).strip("\n"))
    return dropped


def cut_tasks(dst, task, cut):
    tasks_dir = os.path.join(dst, "tasks")
    for name in sorted(os.listdir(tasks_dir)):
        path = os.path.join(tasks_dir, name, "task.md")
        if not os.path.isfile(path):
            continue
        doc = devflow_lib.Doc(path)
        if name != task and (doc.get("created") or "") > cut:
            setup_task.remove(os.path.join(tasks_dir, name))
            print("뺌", name)
            continue
        changed = drop_late_records(doc, cut)
        if changed:
            print("승인 기록 줄 뺌", name, changed)
        if name == task:
            doc.set("status", WAITING)
            doc.set("approval_mode", "")
            doc.set("approved", "")
            if doc.get("kind") in kinds.STAGE_KINDS:
                doc.set("stage", STAGE_RESULT)
            changed = True
        elif (doc.get("approved") or "") > cut:
            doc.set("status", WORKING)
            doc.set("approved", "")
            print("진행으로", name)
            changed = True
        if changed:
            doc.save()


def rerender(args):
    run = os.path.abspath(args.run)
    head = os.path.join(run, "tasks", args.task, "task.md")
    if not os.path.isfile(head):
        raise Refuse("대상 task 머리 파일이 없음: {}".format(head))
    reason = place_refusal(run, args.out)
    if reason:
        raise Refuse(reason)
    cut = devflow_lib.Doc(head).get("approval_requested") or ""
    if not cut:
        raise Refuse("대상 task에 approval_requested가 없음(승인을 요청한 적 없는 task): {}".format(args.task))
    dst = os.path.join(os.path.abspath(args.out), os.path.basename(run))
    prepare(run, dst)
    print("자르는 시각", cut)
    cut_tasks(dst, args.task, cut)
    print("잘린 사본:", dst)


def main(argv=None):
    devflow_lib.utf8_stdout()
    p = argparse.ArgumentParser(description="목적 시험 화면 다시 그리기용 잘린 사본(tests/purpose/README.md)")
    p.add_argument("--run", required=True, help="원본 실행 폴더(바꾸지 않음)")
    p.add_argument("--task", required=True, help="그 승인 요청 시각으로 자를 task id")
    p.add_argument("--out", required=True, help="사본을 만들 곳({out}/{원본 폴더 이름})")
    args = p.parse_args(argv)
    try:
        rerender(args)
    except Refuse as e:
        print("거부:", e, file=sys.stderr)
        return REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
