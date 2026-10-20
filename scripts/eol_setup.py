"""대상 프로젝트의 줄 끝을 저장소에서 LF로 고정한다(.gitattributes `* text=auto eol=lf`).

Windows에서 Python 텍스트 모드·PowerShell 쓰기는 LF 파일을 CRLF로 바꾼다. 저장소가 줄 끝을 고정하지 않으면
그 바이트가 그대로 커밋돼 diff가 수백 줄로 불어난다(하네스 저장소에서 커밋 5개, 2026-10-10 조사).

사용:
  python eol_setup.py {프로젝트 폴더}            점검만. 아무것도 바꾸지 않는다
  python eol_setup.py {프로젝트 폴더} --apply    .gitattributes를 쓰고, 줄 끝을 LF로 정리해 스테이징한다(커밋은 메인)

점검 출력의 첫 줄:
  고정됨 / 고정 안 됨 / git 저장소 아님
--apply는 작업 트리에 커밋하지 않은 변경이 있으면 아무것도 하지 않고 종료 3(--renormalize가 그 변경까지 스테이징하므로).
종료 0 = 고정됨 또는 적용함, 1 = 고정 안 됨(점검), 2 = 인자 오류, 3 = 적용 못 함.
"""
import os
import subprocess
import sys

import devflow_lib

RULES = [
    "# 줄 끝은 저장소에서 LF로 맞춘다(Windows 도구가 CRLF로 다시 써도 커밋에는 LF). devflow-harness가 넣음",
    "* text=auto eol=lf",
    "*.bat text eol=crlf",
    "*.cmd text eol=crlf",
]


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def pinned(text):
    # `*` 패턴이 eol이나 text=auto를 정하면 고정된 것으로 본다
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] == "*" and any(p.startswith("eol=") or p == "text=auto" for p in parts[1:]):
            return True
    return False


def crlf_files(cwd):
    # git ls-files --eol: "i/crlf w/crlf attr/... \tpath"
    _, out = git(cwd, "ls-files", "--eol")
    index, work = [], []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        info, path = line.split("\t", 1)
        cols = info.split()
        if cols[0] in ("i/crlf", "i/mixed"):
            index.append(path)
        if len(cols) > 1 and cols[1] in ("w/crlf", "w/mixed") and "eol=crlf" not in info:
            work.append(path)
    return index, work


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 2 or argv[1].startswith("-"):
        print(__doc__)
        return 2
    cwd = argv[1]
    apply = "--apply" in argv[2:]
    code, top = git(cwd, "rev-parse", "--show-toplevel")
    if code != 0:
        print("git 저장소 아님: " + cwd)
        return 1
    attr = os.path.join(cwd, ".gitattributes")
    text = open(attr, "rb").read().decode("utf-8", "replace") if os.path.isfile(attr) else ""
    index, work = crlf_files(cwd)
    if pinned(text) and not index:
        print("고정됨")
        return 0
    if not apply:
        print("고정 안 됨")
        print("- .gitattributes: " + ("있음, `*` 줄 끝 규칙 없음" if text else "없음"))
        print("- 저장소에 CRLF로 든 파일 {}개{}".format(len(index), (": " + ", ".join(index[:10]) + (" …" if len(index) > 10 else "")) if index else ""))
        return 1
    # 추적하지 않는 파일(??)은 --renormalize가 건드리지 않는다
    _, dirty = git(cwd, "status", "--porcelain", "--untracked-files=no")
    if dirty.strip():
        print("적용 못 함: 커밋하지 않은 변경이 있음")
        print(dirty.rstrip())
        return 3
    if not pinned(text):
        # 맨 앞에 둔다. 뒤에 오는 기존 줄(경로별 규칙)이 우선한다
        body = "\n".join(RULES) + "\n" + ("\n" + text.replace("\r\n", "\n") if text else "")
        with open(attr, "wb") as f:
            f.write(body.encode("utf-8"))
    git(cwd, "add", ".gitattributes")
    git(cwd, "add", "--renormalize", ".")
    # 작업 트리도 LF로(저장소 쪽은 위에서 맞춤). 바이너리는 i/-text라 목록에 들지 않는다
    _, work = crlf_files(cwd)
    for path in work:
        p = os.path.join(cwd, path)
        with open(p, "rb") as f:
            data = f.read()
        with open(p, "wb") as f:
            f.write(data.replace(b"\r\n", b"\n"))
    git(cwd, "add", "--renormalize", ".")
    _, staged = git(cwd, "diff", "--cached", "--name-only")
    names = [s for s in staged.splitlines() if s]
    print("적용함: 스테이징 {}개(.gitattributes와 줄 끝만 바뀐 파일). 메인이 커밋한다".format(len(names)))
    for s in names:
        print("- " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
