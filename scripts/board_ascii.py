"""진행 상황 그림: 머리 파일과 flow.md를 읽어 흐름별 한 줄씩 상태 기호로 그린다. 보는 용도다(원천은 머리 파일).

사용:
  python board.py {실행 폴더} --ascii
  python board_ascii.py {실행 폴더} [--watch 초]    --watch면 그 간격으로 다시 그린다(터미널에서 사람이 띄워 둘 때)
"""
import sys
import time

import board
import devflow_lib


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 2:
        print(__doc__)
        return 2
    run_dir = argv[1]
    if len(argv) > 3 and argv[2] == "--watch":
        interval = max(2, int(argv[3]))
        while True:
            print("\033[2J\033[H" + board.render_ascii(run_dir) + "\n 갱신 " + time.strftime("%H:%M:%S") + " (Ctrl+C로 끝)", flush=True)
            time.sleep(interval)
    print(board.render_ascii(run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
