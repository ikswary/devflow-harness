"""흐름 규약 파일을 만든다. 그 흐름의 끝난 코드 task 결과에서 「규약 추가」 절을 모은다.

에이전트는 규약 파일을 직접 고치지 않는다. 같은 흐름의 다음 구현 task를 띄우기 전에 메인이 돌린다.

사용:
  python conventions.py {실행 폴더} {흐름}
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
    run_dir, flow = argv[1], argv[2]
    tasks = devflow_lib.load_tasks(run_dir)
    parts = ["# 흐름 규약: " + flow, "",
             "이 흐름의 구현 task들이 새로 만든 공용 이름·형식·오류 코드와 기각한 대안. 스크립트가 만든 파일이니 직접 고치지 않는다.", ""]
    n = 0
    for tid, t in tasks.items():
        if t.get("flow") != flow or t.get("kind") not in kinds.CODE_WRITER_KINDS:
            continue
        if t.get("status") != kinds.DONE and not t.get("commit"):
            continue
        result_md = os.path.join(t["_dir"], "result.md")
        if not os.path.isfile(result_md):
            continue
        section = devflow_lib.sections(devflow_lib.read_text(result_md), level=2).get("규약 추가", "")
        if not section or section.strip() in ("없음", "- 없음", "(없음)"):
            continue
        parts += ["## {} {}".format(tid, t.get("title", "")), section, ""]
        n += 1
    out = os.path.join(run_dir, "flows", flow, "conventions.md")
    devflow_lib.write_text(out, "\n".join(parts))
    print("{} (task {}개의 규약)".format(out, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
