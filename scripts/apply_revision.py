"""승인된 변경 task의 고친 판을 정본에 옮긴다.

변경 task의 작성자는 정본을 직접 고치지 않고 자기 task 폴더의 revised 폴더에 고친 판(정본과 같은 상대 경로)을 쓴다.
판정과 승인을 통과한 뒤 메인이 이 스크립트로 옮긴다. 정본 맨 끝의 「변경 이력」에 task id를 남긴다.

사용:
  python apply_revision.py {실행 폴더} {변경 task id} [--dry-run]
"""
import os
import sys

import devflow_lib
import kinds


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, tid = argv[1], argv[2]
    dry = "--dry-run" in argv
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        print("task를 찾지 못함: " + tid)
        return 2
    t = tasks[tid]
    if t.get("status") != kinds.DONE and not dry:
        print("{}의 상태가 `완료`가 아니다({}). 승인 뒤에 옮긴다.".format(tid, t.get("status")))
        return 3
    revised = os.path.join(t["_dir"], "revised")
    if not os.path.isdir(revised):
        print("revised 폴더가 없음: " + revised)
        return 2
    moved = 0
    for root, _dirs, files in os.walk(revised):
        for name in files:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, revised)
            top = rel.replace("\\", "/").split("/")[0]
            if top not in kinds.CANON_DIRS:
                print("정본이 아닌 경로는 옮기지 않음: " + rel)
                continue
            dst = os.path.join(run_dir, rel)
            text = devflow_lib.read_text(src).rstrip("\n")
            note = "- {} {}".format(tid, t.get("title", ""))
            if not name.lower().endswith(".md"):
                # 와이어프레임 HTML 등 마크다운이 아닌 정본은 그대로 옮긴다(변경 이력 절을 붙이면 브라우저에 글자로 보인다)
                print("{} → {}{}".format(rel, dst, " (dry-run)" if dry else ""))
                if not dry:
                    devflow_lib.write_text(dst, text + "\n")
                moved += 1
                continue
            if "## 변경 이력" not in text:
                text += "\n\n## 변경 이력\n"
            history = text.split("## 변경 이력", 1)[1].splitlines()
            # 고친 판에 이 task의 이력 줄이 이미 있으면 더하지 않는다(작성자가 적어 둔 경우)
            if any(line.strip() == "- " + tid or line.startswith("- {} ".format(tid)) for line in history):
                text += "\n"
            else:
                text += "\n" + note + "\n"
            print("{} → {}{}".format(rel, dst, " (dry-run)" if dry else ""))
            if not dry:
                devflow_lib.write_text(dst, text)
            moved += 1
    print("옮긴 정본 {}개".format(moved))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
