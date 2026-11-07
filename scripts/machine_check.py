"""구현·수정 task의 기계 조건 검사. 작성자의 말에 의존하지 않고 작업 트리를 본다.

하나라도 걸리면 읽기 판정을 한다(종료 코드 3). 걸린 것이 없으면 0.

검사(첫 실행의 셋):
  1. 대상 밖 파일: 작업 트리의 변경 파일이 머리 파일 「건드릴 파일」에 없다.
  2. 의존성 목록·설정·마이그레이션 파일이 바뀌었다.
  3. 테스트가 지워졌거나 건너뜀 표시가 늘었다.

1.2.0부터 시작한 task는 보안 신호에 걸린 제품 변경분을 `보안 신호: {파일}:{줄} | {낱말}` 줄로 함께 낸다(종료 코드는 바꾸지 않는다).
메인이 이 줄을 읽기 판정 프롬프트에 넣는다. 값은 프로젝트 설정 「경로 목록」의 `보안 신호 경로`, `보안 신호 낱말`이고, 없으면 시작값이다.
1.2.0부터 시작한 task는 3 대신 시험 변화 규칙(설계 6.12절)을 돌려 task 폴더 `test-changes.md`에 쓴다. 조건에 걸리는 것은 끄기와 삭제뿐이다.
값은 TypeScript와 vitest 프로젝트 하나의 관찰에서 왔고, 다른 스택의 꼴은 합집합으로 남긴다.

사용:
  python machine_check.py {코드 폴더} {task.md 경로} [--config-patterns "a,b"] [--test-dirs "tests,src/**/__tests__"] [--measure-only]

`--measure-only`는 시험 변화만 잰다(`machine_check=값`을 준 전이). 재지 못하면 종료 코드 3이고 파일을 쓰지 않는다.

「건드릴 파일」 절은 줄마다 `- 경로`이고 `*`, `**`를 쓸 수 있다. 설명(괄호, ` — ` 뒤)과 백틱은 떼고 경로만 패턴으로 쓴다.
"""
import fnmatch
import os
import re
import subprocess
import sys
from collections import Counter

import devflow_lib

DEFAULT_CONFIG = devflow_lib.DEFAULT_CONFIG_PATTERNS
OLD_SKIP_MARKS = re.compile(r"(\.skip\(|\bit\.skip\b|\bdescribe\.skip\b|\btest\.skip\b|\bxit\(|\bxdescribe\(|\.only\(|@Disabled|@Ignore|pytest\.mark\.skip|t\.Skip\()")
TEST_HINT = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(test|spec)\.[a-z]+$")
# 보안 신호의 시작값(설계 6.12절: 권한 부여 SQL, 인증 함수, 응답 헤더, CORS, 쿠키, 개인정보 칸). 올리는 데만 쓰며 오탐률은 첫 실행 뒤 고친다
DEFAULT_SECURITY_WORDS = ("GRANT ", "REVOKE ", "CREATE POLICY", "SECURITY DEFINER", "authenticate", "authorize", "verifyToken", "jwt",
                          "Set-Cookie", "Content-Security-Policy", "X-Frame-Options", "Strict-Transport-Security", "Access-Control-Allow",
                          "CORS", "cookie", "password", "passwd", "ssn", "주민번호", "resident_number", "phone_number", "Authorization", "ROW LEVEL SECURITY")
SHORT_WORD = 5   # 이 글자 수 이하의 낱말은 낱말 경계를 본다(`corset`, `classname`). 그보다 길면 어디서든 걸린다(`user_password`, `isAuthenticated`)
SECURITY_PATH_LABEL, SECURITY_WORD_LABEL = "보안 신호 경로", "보안 신호 낱말"
PATH_HIT = "경로"
REMOVED = "지운 줄"
FILE_HEAD = re.compile(r"^diff --git a/(.+) b/\1$")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# 1.2.0: 옛 표시와 호출 꼴의 합집합. 제품 칸의 낱말에서 거짓이 나지 않게 시험 파일에서만 본다
SKIP_MARKS = re.compile(r"(\b(?:it|test|describe)\.(?:skip|only|todo|fixme|fails?|failing|skipIf|runIf)\b|\b(?:fit|fdescribe|xtest)\(|\bt\.Skip(?:f|Now)\(|"
                        r"\bunittest\.skip|\bself\.skipTest\(|\bpytest\.(?:mark\.xfail|importorskip)|" + OLD_SKIP_MARKS.pattern[1:])
TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|spec|e2e)(/|$)")
TEST_NAME = re.compile(r"\.(test|spec)\.[a-z]+$|(^|/)test_[^/]+\.py$|_test\.(py|go)$|Tests?\.(java|kt)$")
TEST_HELPER = re.compile(r"(^|/)test[-_]?(utils?|helpers?|support)(/|$)|(^|/)conftest\.py$|(^|/)(tests?|__tests__|spec|e2e)/(.*/)?(utils?|helpers?|support|fixtures?)/")
RUNNER_CONFIG = re.compile(r"(^|/)((vitest|jest|playwright|cypress|karma)[\w.-]*\.config\.[a-z.]+|vite\.config\.[a-z.]+|vitest\.workspace\.[a-z.]+|\.mocharc[a-z.]*|pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml|package\.json)$")
GOLDEN = re.compile(r"(^|/)__snapshots__/|\.snap$|-snapshots/")
DECLARATION = re.compile(r"^\s*(?:[xf]?it(?:\.\w+)*|(?:x?test)(?:\.(?:only|skip|fixme|fails?|failing|todo|each|concurrent|skipIf|runIf))*)\s*\(|^\s*(?:async\s+)?def test_|^\s*@Test\b|^\s*func Test")
COMMENT = re.compile(r"^\s*(?://|/\*|\*|#(?!\[))")
ASSERTION = re.compile(r"\bexpect\(|\bassert(?:[A-Z_]\w*)?\b|\bt\.(?:Errorf?|Fatalf?)\(")
STRONG_MATCHER = re.compile(r"\.(?:toEqual|toBe|toStrictEqual)\(")
WEAK_MATCHER = re.compile(r"\.(?:toBeTruthy|toBeFalsy|toBeDefined|toContain|toMatch|toMatchObject|toHaveProperty|toBeGreaterThan\w*|toBeLessThan\w*|toBeCloseTo|toBeInstanceOf)\(|\bexpect\.(?:any|anything|objectContaining|arrayContaining|stringContaining)\(")
RANGE_SETTING = re.compile(r"""\b(?:include|exclude|testMatch|testRegex|testPathIgnorePatterns|testIgnore|testDir|testpaths|addopts|projects|collect_ignore|grep|grepInvert)\b["']?\s*[:=]|"test[\w:-]*"\s*:""")
FAILURE_FILTER = re.compile(r"passWithNoTests|allowOnly|dangerouslyIgnoreUnhandledErrors|onUnhandledError|onConsoleLog|onStackTrace|testFailureIgnore|ignoreFailures|continue-on-error|\|\|\s*true|\bbail\b")
# 값이 숫자로 적힌 정의만 본다. 이름을 그대로 쓰는 줄은 뺀다
RETRY_VALUE = re.compile(r"""\b(\w*(?:retries|retry|reruns))["']?\s*[:=(]\s*(\d[\d_.]*)""", re.I)
LIMIT_VALUE = re.compile(r"""\b(\w*(?:timeout|threshold|tolerance|maxdiffpixels|maxdiffpixelratio))["']?\s*[:=(]\s*(\d[\d_.]*)""", re.I)
LITERAL = re.compile(r"""^(?:-?\d[\d_.]*|'[^']*'|"[^"]*"|`[^`$]*`)$""")
PRODUCT_REF = re.compile(r"[A-Za-z_$][\w$]*\.[A-Za-z_$]|\b[A-Z][A-Z0-9_]{2,}\b")
FULL_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
COMMIT_HASH = re.compile(r"^[0-9a-fA-F]{7,40}$")


class MeasureError(Exception):
    """git이 실패해 시험 변화를 재지 못함. 빈 결과를 "변화 없음"으로 쓰지 않는다."""


def git(code_dir, *args):
    out = subprocess.run(["git", "-C", code_dir] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def git_strict(code_dir, *args):
    out = subprocess.run(["git", "-C", code_dir] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise MeasureError("git {}: {}".format(args[-1] if args else "", (out.stderr or "").strip().split("\n")[0]))
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


matches = devflow_lib.pattern_match


def security_signals(run_dir):
    """프로젝트 설정 「경로 목록」의 (보안 신호 경로, 보안 신호 낱말). 낱말 줄이 없으면 시작값, `없음`이면 빈 목록이다."""
    path = os.path.join(os.path.dirname(os.path.abspath(run_dir)), devflow_lib.PROJECT_SETTINGS)
    found = {}
    if os.path.isfile(path):
        for line in devflow_lib.sections(devflow_lib.read_text(path)).get("경로 목록", "").splitlines():
            label, colon, raw = line[2:].partition(":") if line.startswith("- ") else ("", "", "")
            if colon and label.strip() in (SECURITY_PATH_LABEL, SECURITY_WORD_LABEL):
                empty = devflow_lib.EMPTY_ITEM.match("- " + raw.strip())
                found[label.strip()] = [] if empty else [x.strip() for x in raw.replace("`", "").split(",") if x.strip()]
    return found.get(SECURITY_PATH_LABEL, []), found.get(SECURITY_WORD_LABEL, list(DEFAULT_SECURITY_WORDS))


def diff_rows(diff):
    """`--unified=0` diff의 바뀐 줄 [(파일, 새 쪽 줄 번호, 글, 지운 줄인가)]. 인증 호출을 지운 변경도 신호이므로 지운 줄도 넣는다."""
    rows, path, old, line, in_hunk = [], None, None, 0, False
    for raw in diff.splitlines():
        hunk = HUNK.match(raw)
        if raw.startswith("diff --git"):
            path, old, in_hunk = None, None, False
        elif hunk:
            line, in_hunk = max(1, int(hunk.group(1))), True
        elif not in_hunk and raw.startswith("--- "):
            old = raw[6:] if raw.startswith("--- a/") else None
        elif not in_hunk and raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else old
        elif path and raw.startswith("+"):
            rows.append((path, line, raw[1:], False))
            line += 1
        elif path and raw.startswith("-"):
            rows.append((path, line, raw[1:], True))
    return rows


def diff_files(diff):
    """diff가 건드린 파일과 처음 바뀐 줄 {파일: 줄}. 줄이 없는 이진 파일과 모드만 바뀐 파일은 1이다."""
    found = {}
    for raw in diff.splitlines():
        head = FILE_HEAD.match(raw)
        if head:
            found[head.group(1)] = None
    for path, line, _, _ in diff_rows(diff):
        if found.get(path) is None:
            found[path] = line
    return {path: line or 1 for path, line in found.items()}


def _word_pattern(word):
    bare = word.strip()
    if len(bare) > SHORT_WORD:
        return re.compile(re.escape(word), re.I)
    # 앞이 다른 낱말에 붙으면 세지 않되 낙타 꼴(`verifyJwt`)은 낱말의 시작으로 본다. 뒤에 소문자가 이어지면 다른 낱말이다(`corset`)
    tail = r"(?![a-z])" if word[-1:].isalnum() else ""
    caps = "{}|{}".format(re.escape(word[:1].upper() + word[1:].lower()), re.escape(word.upper()))
    return re.compile(r"(?:(?<![A-Za-z0-9])(?i:{})|(?<=[a-z0-9])(?:{})){}".format(re.escape(word), caps, tail))


def security_hits(diff, paths, words):
    """제품 변경분에서 보안 신호에 걸린 곳 [(파일, 줄, 낱말, 지운 줄의 글 또는 "")]. 시험 파일은 보지 않고, (파일, 줄, 낱말)마다 하나다."""
    patterns = [(w, _word_pattern(w)) for w in words]
    hits, seen = [], set()

    def add(path, line, word, text):
        if (path, line, word) not in seen:
            seen.add((path, line, word))
            hits.append((path, line, word, text))

    for path, line in diff_files(diff).items():
        if not TEST_HINT.search(path) and devflow_lib.path_in_list(path, paths):
            add(path, line, PATH_HIT, "")
    for path, line, text, removed in diff_rows(diff):
        if TEST_HINT.search(path):
            continue
        word = next((w for w, rx in patterns if rx.search(text)), None)
        if word:
            add(path, line, word.strip(), text if removed else "")
    return hits


def signal_row(hit):
    """신호 한 줄. 지운 글은 비밀값을 가려 싣는다."""
    path, line, word, removed = hit
    row = "{}:{} | {}".format(path, line, word)
    return row + " | {}: {}".format(REMOVED, devflow_lib.mask_line(removed.strip())) if removed else row


def untracked_diff(code_dir):
    """추적하지 않는 새 파일을 diff 꼴로. `git diff HEAD`에 나오지 않는다."""
    parts = []
    for name in git(code_dir, "ls-files", "--others", "--exclude-standard").splitlines():
        try:
            with open(os.path.join(code_dir, name), encoding="utf-8") as f:
                body = f.read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        parts += ["diff --git a/{0} b/{0}".format(name), "+++ b/" + name, "@@ -0,0 +1 @@"] + ["+" + l for l in body]
    return "\n".join(parts)
def file_diffs(code_dir, base="HEAD", head=None):
    """기준에서 작업 트리까지의 변경을 파일별로: {경로: {state: 고침/새 파일/지움, removed, added: [(줄, 글)], pairs: [(옛 글, 새 글)]}}."""
    out, entry, rem, add, olds, news = {}, None, 0, 0, [], []
    old_no, new_no = 0, 0
    diff = git_strict(code_dir, "-c", "core.quotepath=off", "diff", base, *([head] if head else []), "--unified=0", "--no-renames", "--no-color", "--no-ext-diff")
    for line in diff.split("\n"):
        if rem or add:
            if line.startswith("-") and rem:
                rem -= 1
                entry["removed"].append((old_no, line[1:]))
                olds.append(line[1:])
                old_no += 1
            elif line.startswith("+") and add:
                add -= 1
                entry["added"].append((new_no, line[1:]))
                news.append(line[1:])
                new_no += 1
            if not rem and not add and len(olds) == len(news):
                entry["pairs"] += zip(olds, news)
            continue
        if line.startswith("diff --git "):
            rest = line[len("diff --git "):]
            path = rest[2:2 + (len(rest) - 5) // 2]   # --no-renames라 두 경로가 같다
            entry = out.setdefault(path, {"state": "고침", "removed": [], "added": [], "pairs": []})
        elif line.startswith("new file mode") and entry:
            entry["state"] = "새 파일"
        elif line.startswith("deleted file mode") and entry:
            entry["state"] = "지움"
        elif FULL_HUNK.match(line) and entry is not None:
            old_start, old_count, new_start, new_count = FULL_HUNK.match(line).groups()
            rem, add = 1 if old_count is None else int(old_count), 1 if new_count is None else int(new_count)
            old_no, new_no, olds, news = int(old_start), int(new_start), [], []
    for path in git_strict(code_dir, "-c", "core.quotepath=off", "ls-files", "--others", "--exclude-standard").splitlines():
        out[path] = {"state": "새 파일", "removed": [], "added": new_file_lines(code_dir, path), "pairs": []}
    return out


def new_file_lines(code_dir, path):
    full = os.path.join(code_dir, path)
    if not (TEST_DIR.search(path) or TEST_NAME.search(path) or TEST_HELPER.search(path)) or not os.path.isfile(full):
        return []
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            return list(enumerate(f.read().splitlines(), 1))
    except OSError as e:
        raise MeasureError("새 파일을 읽지 못함 {}: {}".format(path, e))


def hits(pattern, lines):
    """주석만 있는 줄을 뺀 걸린 줄. 단언을 주석으로 막으면 단언이 준 것이다."""
    return [(no, text) for no, text in lines if pattern.search(text) and not COMMENT.match(text)]


def definitions(pattern, lines):
    """{이름: {값}}. 숫자로 적힌 정의만이고 이름을 그대로 쓰는 줄은 걸리지 않는다."""
    out = {}
    for _, text in hits(pattern, lines):
        for m in pattern.finditer(text):
            out.setdefault(m.group(1).lower(), set()).add(m.group(2))
    return out


def changed_definitions(pattern, removed, added, new_counts):
    """값이 바뀐 정의의 근거 글. new_counts가 거짓이면 옛 값과 새 값이 모두 있는 이름만 본다."""
    before, after = definitions(pattern, removed), definitions(pattern, added)
    names = set(before) | set(after) if new_counts else set(before) & set(after)
    return ["{}: {} → {}".format(name, ", ".join(sorted(before.get(name, ()))) or "없음", ", ".join(sorted(after.get(name, ()))) or "없음")
            for name in sorted(names) if before.get(name) != after.get(name)]


def stays_collected(old, new):
    """같은 내용의 새 파일이 이름 변경인가. 시험 이름 꼴이면 새 경로도 그 꼴이고, 꼴이 없으면 시험 폴더 안의 같은 확장자다."""
    if TEST_NAME.search(old):
        return bool(TEST_NAME.search(new))
    return bool(TEST_DIR.search(new)) and os.path.splitext(old)[1] == os.path.splitext(new)[1]


def literal_to_reference(old, new):
    """앞뒤 같은 글자를 뗀 가운데가 리터럴에서 제품 값 참조로 바뀐 줄인가(근거가 약해지는 변경)."""
    a, b = old.strip(), new.strip()
    head = len(os.path.commonprefix([a, b]))
    tail = len(os.path.commonprefix([a[head:][::-1], b[head:][::-1]]))
    mid_a, mid_b = a[head:len(a) - tail], b[head:len(b) - tail]
    return bool(LITERAL.match(mid_a)) and bool(PRODUCT_REF.search(mid_b)) and not LITERAL.match(mid_b)


def is_assertion(text):
    return bool(hits(ASSERTION, [(0, text)]))


PULLED_NAMES = 8   # `받아온 변경` 줄에 이름을 적는 파일 수


def merge_bases(code_dir, ours, theirs):
    return git_strict(code_dir, "merge-base", "--all", ours, theirs).split()


def _merge_parents(code_dir, base, head):
    """이 측정이 받아오기 병합을 지나는가: (ours, theirs) 또는 None. 병합 중이면 HEAD와 MERGE_HEAD, 끝났으면 그 커밋의 두 부모이고,
    기준이 ours의 조상이고 theirs가 아직 기준에 없을 때만이다. 기준이 병합 커밋 자신이면 받아온 변경이 차이에 들지 않는다."""
    merging = subprocess.run(["git", "-C", code_dir, "rev-parse", "-q", "--verify", "MERGE_HEAD"], capture_output=True, encoding="utf-8", errors="replace")
    if not head and merging.returncode == 0:
        ours, theirs = git_strict(code_dir, "rev-parse", "HEAD").strip(), merging.stdout.strip()
    else:
        parents = git_strict(code_dir, "rev-list", "--parents", "-n", "1", head or "HEAD").split()[1:]
        if len(parents) != 2:
            return None
        ours, theirs = parents

    return (ours, theirs) if _is_ancestor(code_dir, base, ours) and not _is_ancestor(code_dir, theirs, base) else None


def pull_sources(task):
    """받아오기의 출처로 인정하는 ref: 개발 기준·통합 브랜치와 flow.md `sync_pending`·`synced_to`. 여기서 닿지 않는 병합은 받아오기로 보지 않는다."""
    run_dir = devflow_lib.run_dir_of(task)
    meta = devflow_lib.run_meta(run_dir)
    out = [str(meta.get(key, "") or "").strip() for key in ("base_branch", "integration_branch")]
    flow_md = os.path.join(run_dir, "flows", str(task.get("flow", "") or ""), "flow.md")
    if task.get("flow") and os.path.isfile(flow_md):
        flow = devflow_lib.parse_meta(devflow_lib.split_front_matter(devflow_lib.read_text(flow_md))[0])
        for key in ("sync_pending", "synced_to"):
            # `{브랜치}@{출처 커밋} → {합친 결과}`. 결과는 흐름 쪽 커밋이라 그 앞의 자기 병합이 모두 여기서 닿는다. 괄호 글도 출처가 아니다
            text = re.sub(r"[(（].*?[)）]", " ", str(flow.get(key, "") or ""))
            for entry in text.split(","):
                for token in re.findall(r"[^\s\[\]'\"]+", re.split(r"→|->", entry)[0]):
                    out += token.split("@")
    return [ref for ref in dict.fromkeys(out) if ref]


def _is_ancestor(code_dir, a, b):
    return subprocess.run(["git", "-C", code_dir, "merge-base", "--is-ancestor", a, b], capture_output=True).returncode == 0


def pulled_files(code_dir, base, head, ours, theirs, sources=()):
    """받아온 쪽 그대로인 파일: 들어온 쪽이 고쳤고, 기준과 우리 쪽 끝 모두 갈림점과 같고(이쪽이 고친 적 없고), 결과가 들어온 쪽과 같다.
    셋 가운데 하나라도 아니면 이 task가 손댔을 수 있으므로 세던 대로 센다. 들어온 쪽이 출처에서 닿지 않거나(옆 가지를 자기가 병합한 것)
    갈림점이 하나가 아니면 None(가려내지 못함)."""
    if not any(_is_ancestor(code_dir, theirs, ref) for ref in sources):
        return None
    bases = merge_bases(code_dir, ours, theirs)
    if len(bases) != 1:
        return None

    def names(*refs):
        return set(git_strict(code_dir, "-c", "core.quotepath=off", "diff", "--name-only", "--no-renames", *refs).splitlines())
    return names(bases[0], theirs) - names(base, bases[0]) - names(bases[0], ours) - names(theirs, *([head] if head else []))


def find_test_changes(code_dir, settings, base="HEAD", head=None, sources=()):
    """시험 변화의 기계 줄 [{change, place, basis}]. 값은 설계 6.12절 표의 관찰에서 왔고 잡음은 첫 실행 뒤 고친다."""
    diffs = file_diffs(code_dir, base, head)
    rows = []
    parents = _merge_parents(code_dir, base, head)
    pulled = pulled_files(code_dir, base, head, *parents, sources=sources) if parents else set()
    pulled_diffs = {path: diffs.pop(path) for path in pulled or () if path in diffs}

    def add(change, path, lines, basis):
        rows.append({"change": change, "place": "{}:{}".format(path, lines[0][0]) if lines else path, "basis": basis})

    def is_golden(path):
        return bool(GOLDEN.search(path)) or devflow_lib.path_in_list(path, settings["golden"])

    def is_helper(path):
        # 도우미 폴더 아래의 시험 이름 꼴은 진짜 시험이다
        return not is_golden(path) and not TEST_NAME.search(path) and (bool(TEST_HELPER.search(path)) or devflow_lib.path_in_list(path, settings["helper"]))

    def is_test(path):
        return not is_golden(path) and not is_helper(path) and bool(TEST_DIR.search(path) or TEST_NAME.search(path))

    def is_runner(path):
        return bool(RUNNER_CONFIG.search(path))

    helper_assertions = Counter(text.strip() for p, d in diffs.items() if is_helper(p) for _, text in hits(ASSERTION, d["added"]))
    new_bodies = {p: [text for _, text in d["added"]] for p, d in diffs.items() if d["state"] == "새 파일"}
    for path, d in sorted(diffs.items()):
        removed, added, gone = d["removed"], d["added"], d["state"] == "지움"
        run_path = devflow_lib.path_in_list(path, settings["run"])
        if is_test(path):
            off_added, off_removed = hits(SKIP_MARKS, added), hits(SKIP_MARKS, removed)
            if len(off_added) > len(off_removed):
                add("끄기", path, off_added, "+{}/-{}".format(len(off_added), len(off_removed)))
            decl_added, decl_removed = hits(DECLARATION, added), hits(DECLARATION, removed)
            body = [text for _, text in removed]
            if gone and not any(new == body and stays_collected(path, p) for p, new in new_bodies.items()):
                add("삭제", path, [], "선언 {}개".format(len(decl_removed)))
            elif not gone and len(decl_removed) > len(decl_added):
                add("삭제", path, decl_removed, "선언 -{}".format(len(decl_removed) - len(decl_added)))
            if not gone:
                lost = len(hits(ASSERTION, removed)) - len(hits(ASSERTION, added))
                strong = len(hits(STRONG_MATCHER, removed)) - len(hits(STRONG_MATCHER, added))
                weak = len(hits(WEAK_MATCHER, added)) - len(hits(WEAK_MATCHER, removed))
                for _, text in hits(ASSERTION, removed):   # 같은 글자로 시험 도우미에 들어간 단언은 옮긴 것이다
                    if lost > 0 and helper_assertions[text.strip()] > 0:
                        helper_assertions[text.strip()] -= 1
                        lost -= 1
                if lost > 0:
                    add("단언 약화", path, hits(ASSERTION, removed), "단언 -{}".format(lost))
                if strong > 0 and weak > 0:
                    add("단언 약화", path, hits(WEAK_MATCHER, added), "강한 매처 -{}, 약한 매처 +{}".format(strong, weak))
            for old, new in d["pairs"]:
                if literal_to_reference(old, new):
                    add("리터럴이 제품 값으로", path, [(no, text) for no, text in added if text == new], "{} → {}".format(old.strip(), new.strip()))
                    break
        if is_runner(path):
            changed = {text.strip() for _, text in hits(RANGE_SETTING, added)} ^ {text.strip() for _, text in hits(RANGE_SETTING, removed)}
            if changed:
                add("범위 축소", path, hits(RANGE_SETTING, added) or hits(RANGE_SETTING, removed), "실행기 설정 {}줄".format(len(changed)))
        if run_path:
            add("시험을 돌리는 곳", path, added, d["state"])
        if (is_test(path) or is_helper(path) or is_runner(path)) and not gone:
            # 새 재시도는 판정을 느슨하게 한다. 제한 시간의 새 정의는 시험 파일에서 값 변경이 아니고, 실행기 설정에서는 전체에 걸리므로 본다
            for change, pattern, new_counts in (("재시도", RETRY_VALUE, True), ("제한 시간과 허용 범위", LIMIT_VALUE, is_runner(path))):
                found = changed_definitions(pattern, removed, added, new_counts)
                if found:
                    add(change, path, hits(pattern, added) or hits(pattern, removed), ", ".join(found))
        if is_test(path) or is_helper(path) or is_runner(path) or run_path:
            filter_added, filter_removed = hits(FAILURE_FILTER, added), hits(FAILURE_FILTER, removed)
            if len(filter_added) > len(filter_removed):
                add("실패 거름", path, filter_added, "+{}/-{}".format(len(filter_added), len(filter_removed)))
        if is_golden(path) and d["state"] != "새 파일":
            add("정답 파일", path, [], d["state"])
        if is_helper(path) and d["state"] != "새 파일":
            add("시험 도우미", path, [], d["state"])
    tests = {p: d for p, d in diffs.items() if is_test(p)}
    product = [p for p in diffs if not (is_test(p) or is_helper(p) or is_golden(p) or is_runner(p) or p.lower().endswith(".md"))]
    grew = any(len(hits(DECLARATION, d["added"])) > len(hits(DECLARATION, d["removed"])) for d in tests.values())
    both = {p: sum(1 for old, new in d["pairs"] if is_assertion(old) and is_assertion(new)) for p, d in tests.items()}
    paired = sorted(p for p, n in both.items() if n)
    if paired and not product and not grew:
        add(devflow_lib.TEST_EXPECT_ONLY, paired[0], [], "{}줄".format(sum(both.values())))
    changed_assertions = sum(1 for d in tests.values() for old, new in d["pairs"] if is_assertion(old) or is_assertion(new))
    if changed_assertions:
        rows.append({"change": devflow_lib.TEST_COUNT_ONLY, "place": "전체", "basis": "{}줄".format(changed_assertions)})
    if parents and pulled is None:
        rows.append({"change": devflow_lib.TEST_PULLED, "place": "전체", "basis": "받아온 변경 포함, 가려내지 못함(출처에서 닿지 않거나 갈림점이 여럿)"})
    pulled_tests = sorted(path for path in pulled_diffs if is_test(path) or is_helper(path) or is_golden(path) or is_runner(path))
    if pulled_tests:
        names = ", ".join(pulled_tests[:PULLED_NAMES]) + (" 외 {}개".format(len(pulled_tests) - PULLED_NAMES) if len(pulled_tests) > PULLED_NAMES else "")
        rows.append({"change": devflow_lib.TEST_PULLED, "place": "전체", "basis": "시험 쪽 파일 {}개({}), 받아온 쪽 그대로라 세지 않음".format(len(pulled_tests), names)})
    return rows


def record_test_changes(code_dir, task, head=None):
    """기계 줄을 task 폴더에 쓰고 돌려준다. 정찰 문서의 기준선도 처음 한 번 떠 둔다. head를 주면 작업 트리 대신 그 커밋까지 잰다(뒤 task의 변화를 넣지 않는다)."""
    run_dir = devflow_lib.run_dir_of(task)
    devflow_lib.note_baseline(run_dir)
    # 다시 재도 앞 회차의 변화가 사라지지 않게 첫 측정의 기준에서 잰다. 기준이 없는데 이미 커밋한 task면 그 커밋의 앞이다
    base = devflow_lib.test_change_base(task)
    devflow_lib.clear_test_changes(task)
    if not base:
        commit = str(task.get("commit", "") or "").strip()
        base = git_strict(code_dir, "rev-parse", "--verify", commit + "^" if COMMIT_HASH.match(commit) else "HEAD").strip()
    rows = find_test_changes(code_dir, devflow_lib.test_change_settings(run_dir), base, head, pull_sources(task))
    text = "\n".join("- {change} | {place} | {basis}".format(**row) for row in rows) or "- 없음"
    devflow_lib.write_text(os.path.join(task["_dir"], devflow_lib.TEST_CHANGES), "{}{}\n{}\n".format(devflow_lib.TEST_BASE_HEAD, base, text))
    return rows


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
    if "--measure-only" in argv:
        try:
            for row in record_test_changes(code_dir, task):
                print("시험 변화: {change} | {place} | {basis}".format(**row))
        except MeasureError as e:
            print("시험 변화를 재지 못함: {}".format(e))
            return 3
        return 0
    files, deleted = changed_files(code_dir)
    allowed = allowed_patterns(task)

    outside = [f for f in files if not matches(f, allowed)]
    config_hit = [f for f in files if matches(f, config) or matches(f.split("/")[-1], config)]
    new_rules = devflow_lib.version_at_least(task.get("started_version"), devflow_lib.RULES_V120)
    test_rows, unmeasured = [], ""
    try:
        test_rows = record_test_changes(code_dir, task) if new_rules else []
    except MeasureError as e:
        unmeasured = str(e)
    tests_deleted = [f for f in deleted if TEST_HINT.search(f)] if not new_rules else []
    diff = git(code_dir, "diff", "HEAD", "--unified=0")
    old_diff = "" if new_rules else diff
    skip_added = sum(1 for l in old_diff.splitlines() if l.startswith("+") and not l.startswith("+++") and OLD_SKIP_MARKS.search(l))
    skip_removed = sum(1 for l in old_diff.splitlines() if l.startswith("-") and not l.startswith("---") and OLD_SKIP_MARKS.search(l))

    if devflow_lib.version_at_least(task.get("started_version"), devflow_lib.RULES_V120):
        whole = diff + "\n" + untracked_diff(code_dir)
        for hit in security_hits(whole, *security_signals(devflow_lib.run_dir_of(task))):
            print("보안 신호: " + signal_row(hit))

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
    if unmeasured:
        flags.append("시험 변화를 재지 못함: {}".format(unmeasured))
    removals = [row for row in test_rows if row["change"] in devflow_lib.TEST_REMOVALS]
    if removals:
        flags.append("시험 끄기·삭제 {}줄: {}".format(len(removals), ", ".join(row["change"] + " " + row["place"] for row in removals[:10])))
    for row in test_rows:
        print("시험 변화: {change} | {place} | {basis}".format(**row))

    if flags:
        print("기계 조건에 걸림 {}건 → 읽기 판정을 한다".format(len(flags)))
        for f in flags:
            print("- " + f)
        return 3
    print("기계 조건에 걸린 것 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
