"""구현·수정 task의 기계 조건 검사. 작성자의 말에 의존하지 않고 작업 트리를 본다.

하나라도 걸리면 읽기 판정을 한다(종료 코드 3). 걸린 것이 없으면 0.

검사(첫 실행의 셋):
  1. 대상 밖 파일: 작업 트리의 변경 파일이 머리 파일 「건드릴 파일」에 없다.
  2. 의존성 목록·설정·마이그레이션 파일이 바뀌었다.
  3. 테스트가 지워졌거나 건너뜀 표시가 늘었다.

사용:
  python machine_check.py {코드 폴더} {task.md 경로} [--config-patterns "a,b"] [--test-dirs "tests,src/**/__tests__"]

「건드릴 파일」 절은 줄마다 `- 경로`이고 `*`, `**`를 쓸 수 있다. 설명(괄호, ` — ` 뒤)과 백틱은 떼고 경로만 패턴으로 쓴다.
"""
import fnmatch
import re
import subprocess
import sys

import devflow_lib

DEFAULT_CONFIG = [
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "requirements*.txt", "pyproject.toml",
    "build.gradle*", "settings.gradle*", "pom.xml", "go.mod", "go.sum", "tsconfig*.json", "*.config.*",
    "wrangler.*", ".env*", "*.sql", "**/migrations/**", "**/migration/**", "Dockerfile*", ".github/**",
]
SKIP_MARKS = re.compile(r"(\.skip\(|\bit\.skip\b|\bdescribe\.skip\b|\btest\.skip\b|\bxit\(|\bxdescribe\(|\.only\(|@Disabled|@Ignore|pytest\.mark\.skip|t\.Skip\()")
TEST_HINT = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(test|spec)\.[a-z]+$")


def git(code_dir, *args):
    out = subprocess.run(["git", "-C", code_dir] + list(args), capture_output=True, text=True, encoding="utf-8")
    return out.stdout


def changed_files(code_dir):
    files = []
    deleted = []
    for line in git(code_dir, "status", "--porcelain", "--untracked-files=all").splitlines():
        if len(line) < 4:
            continue
        status, path = line[:2], line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.replace("\\", "/")
        files.append(path)
        if "D" in status:
            deleted.append(path)
    return files, deleted


def allowed_patterns(task):
    pats = []
    for line in task["_sections"].get("건드릴 파일", "").splitlines():
        line = line.strip()
        if line.startswith("- "):
            pats.append(devflow_lib._touch_line(line[2:]).strip().replace("\\", "/"))
    return pats


def matches(path, patterns):
    for p in patterns:
        if fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path, p.rstrip("/") + "/*") or path == p:
            return True
        if "**" in p and fnmatch.fnmatch(path, p.replace("**/", "*")):
            return True
    return False


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3:
        print(__doc__)
        return 2
    code_dir, task_md = argv[1], argv[2]
    config = DEFAULT_CONFIG
    if "--config-patterns" in argv:
        config = [x.strip() for x in argv[argv.index("--config-patterns") + 1].split(",") if x.strip()]
    task = devflow_lib.load_task(task_md)
    files, deleted = changed_files(code_dir)
    allowed = allowed_patterns(task)

    outside = [f for f in files if not matches(f, allowed)]
    config_hit = [f for f in files if matches(f, config) or matches(f.split("/")[-1], config)]
    tests_deleted = [f for f in deleted if TEST_HINT.search(f)]
    diff = git(code_dir, "diff", "HEAD", "--unified=0")
    skip_added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++") and SKIP_MARKS.search(l))
    skip_removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---") and SKIP_MARKS.search(l))

    flags = []
    print("변경 파일 {}개 (머리 파일의 건드릴 파일 {}줄)".format(len(files), len(allowed)))
    if not allowed:
        flags.append("머리 파일에 「건드릴 파일」이 없다")
    if outside:
        flags.append("대상 밖 파일 {}개: {}".format(len(outside), ", ".join(outside[:10])))
    if config_hit:
        flags.append("의존성·설정·마이그레이션 파일 {}개: {}".format(len(config_hit), ", ".join(config_hit[:10])))
    if tests_deleted:
        flags.append("지워진 테스트 {}개: {}".format(len(tests_deleted), ", ".join(tests_deleted[:10])))
    if skip_added > skip_removed:
        flags.append("테스트 건너뜀 표시가 늘었다(+{} / -{})".format(skip_added, skip_removed))

    if flags:
        print("기계 조건에 걸림 {}건 → 읽기 판정을 한다".format(len(flags)))
        for f in flags:
            print("- " + f)
        return 3
    print("기계 조건에 걸린 것 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
