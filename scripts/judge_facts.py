"""판정 전 사실 검사(1.3.0, 구현 설계 2절 B, 7판 규칙 5.2). `tasks\\{id}\\facts.md`를 쓴다.

판정자가 작성자의 문장을 대조할 사실을 미리 뽑는다. 판단은 하지 않고 줄만 낸다. 판정자는 이 파일을 데이터로만 읽는다.
**값은 싣지 않는다.** 코드·설정 파일의 줄 글을 옮기지 않고 위치(파일:줄)와 이름·꼴만 쓴다. 설정 값은 길이와 꼴 이름,
코드의 기대 꼴은 함수 이름과 리터럴의 길이만 쓴다. 지운 문구는 사람이 읽는 문장(빈칸이나 한글이 든 것)만 싣는다.

검사(kind마다 도는 것은 등록표 `kinds.FACT_CHECKS`):
  producer  식별자의 생산처: 결과 파일과 「정본의 절」이 언급한 식별자(백틱 안의 이름, 맨글의 `ERR_X` 꼴)마다
            코드 파일의 정의·대입·반환·던짐 줄. 주석 줄, 문서, 시험 쪽 파일은 생산처로 세지 않는다
  tests     바뀐 동작의 기존 시험: 그 식별자와 코드 변경에서 지운 문구를 단언하는 시험 줄(기준 커밋 HEAD에서 찾는다)
  deploy    배포 도구의 시간 제한·재시도·되돌림: 배포 도구 설정·배포 스크립트·CI 워크플로의 값, 결과 파일 명령의 옵션
  config    설정 값의 꼴: 코드가 읽는 환경 키와 환경 파일의 키, 길이, 꼴 이름(JWT, URL 등), 코드의 기대 꼴
  env       시험이 물려받는 환경: 시험·시험 도우미·실행기 설정이 실제 환경을 넘기거나 환경 파일·환경 값을 읽는 줄
  security  보안 신호(1.2.0의 `machine_check` 신호를 이 파일에도 쓴다)

사용:
  python judge_facts.py {실행 폴더} {task.md 경로} [--code-dir {코드 폴더}]
코드 폴더를 주지 않으면 `run.md`의 `project`를 쓴다. 둘 다 없거나 검사가 실패하면 그 절에 `뽑지 못함`을 쓴다.
파일은 늘 쓰고 종료 코드는 늘 0이다(전이를 막지 않는다).
"""
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime

import devflow_lib
import kinds
import machine_check
import plain_text

LINE_CAP = 200     # 절마다 줄 수 상한(시작값, 구현 설계 5절). 넘으면 `외 n줄`
PER_NAME = 5       # 식별자 하나에 싣는 생산 줄
TESTS_PER_NAME = 3  # 식별자·문구 하나에 싣는 단언 줄(나머지는 파일 수로)
LONG_LINE = 2000   # 이보다 긴 줄(번들, 한 줄 HTML)은 훑지 않는다
GIT_TIMEOUT = 120  # 초
NOT_RUN = "- 돌리지 않음(이 일의 종류에는 해당하지 않음)"
SECTIONS = {"producer": "식별자의 생산처", "tests": "바뀐 동작의 기존 시험", "deploy": "배포 도구의 시간 제한·재시도·되돌림",
            "config": "설정 값의 꼴", "env": "시험이 물려받는 환경", "security": "보안 신호"}

# ---------------------------------------------------------------- 식별자

TICK = re.compile(r"`([^`\n]{1,120})`")
BARE_CODE = re.compile(r"(?<![A-Za-z0-9_`])([A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9])(?![A-Za-z0-9_`])")
NAME = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*(?:\(\))?$")
FILE_NAME = re.compile(r"\.{}$".format(plain_text.EXT))
# 호스트 이름(`cdn.example.com`)은 식별자가 아니다. 끝 마디 `com`을 이름으로 뽑아 생산처 없음 256곳이 되었다(목적 시험 T004)
HOST_NAME = re.compile(r"^(?:[a-z0-9-]+\.)+(?:com|net|org|kr|io|jp|cloud)$")
# 이름 꼴이지만 식별자가 아닌 것: 일반 약어, task·번호 꼴, 저장소 폴더 이름
NOT_NAMES = {"JSON", "URL", "URI", "HTTP", "HTTPS", "HEAD", "API", "UUID", "HTML", "CSS", "SQL", "YAML", "TOML", "UTF", "CLI",
             "PR", "CI", "CD", "DNS", "TLS", "SSL", "JWT", "CORS", "CSV", "PDF", "PNG", "SVG", "XML", "README", "TODO",
             "node_modules", "__init__", "__pycache__"}
# 언어 낱말(`.for`, `x.then()` 같은 꼴에서 마지막 마디로 나온다)
NOT_NAMES |= {"for", "if", "else", "while", "do", "return", "new", "this", "self", "true", "false", "null", "None", "def",
              "class", "async", "await", "import", "from", "export", "const", "let", "var", "function", "try", "catch",
              "throw", "raise", "then", "map", "filter", "length", "get", "set", "has", "push", "join", "split", "test",
              "run", "main", "init", "env", "log", "json", "text"}
NUMBERED = re.compile(r"^(?:T\d+|[A-Z]{1,4}\d+)$")


def _looks_like_identifier(name):
    """한 낱말 소문자(`true`, `wrangler`)는 명령·값일 수 있어 뺀다. 밑줄, 낙타 꼴, 대문자 셋 이상만 이름으로 본다."""
    return "_" in name or re.search(r"[a-z][A-Z]", name) or re.fullmatch(r"[A-Z][A-Z0-9]{2,}", name)


def identifiers(text):
    found = []
    spans = [(m.start(), "tick", m.group(1).strip()) for m in TICK.finditer(text or "")]
    spans += [(m.start(), "bare", m.group(1)) for m in BARE_CODE.finditer(text or "")]
    for _, how, raw in sorted(spans):
        called = False
        if how == "tick":
            if not NAME.match(raw) or (FILE_NAME.search(raw) and not raw.endswith("()")) or HOST_NAME.match(raw):
                continue
            called = raw.endswith("()") or "." in raw   # 호출 꼴과 점으로 이은 이름은 소문자 한 낱말이어도 이름이다
            raw = (raw[:-2] if raw.endswith("()") else raw).split(".")[-1]
        if raw in found or raw in NOT_NAMES or NUMBERED.match(raw) or len(raw) < 3 or not re.search(r"[A-Za-z]", raw):
            continue
        if (called and len(raw) >= 3) or _looks_like_identifier(raw):
            found.append(raw)
    return found


HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
SECTION_NAME = re.compile(r"「([^」]+)」")


def canon_sections(text, names):
    """정본 글에서 제목에 이름이 든 절(같거나 높은 단계의 다음 제목까지). 이름이 없으면 글 전체."""
    if not names:
        return text
    lines, out, level = text.splitlines(), [], None
    for line in lines:
        m = HEADING.match(line)
        if m:
            if level is not None and len(m.group(1)) <= level:
                level = None
            if level is None and any(n in m.group(2) for n in names):
                level = len(m.group(1))
        if level is not None:
            out.append(line)
    return "\n".join(out)


def source_text(run_dir, t):
    """식별자를 뽑을 글: 결과 파일과 「정본의 절」이 가리키는 절(절 이름이 없으면 그 파일 전체), 「건드릴 파일」의 정본.
    코드 task는 시작할 때 뜬 사본(design-copy)을 먼저 읽는다(판정자가 대조하는 판)."""
    parts = []
    result = os.path.join(t["_dir"], "result.md")
    if os.path.isfile(result):
        parts.append(devflow_lib.read_text(result))
    sections = t.get("_sections", {})
    seen = set()
    for line in (sections.get("정본의 절", "") + "\n" + sections.get("건드릴 파일", "")).splitlines():
        names = SECTION_NAME.findall(line)
        for m in devflow_lib.CANON_PATH_RE.finditer(line):
            rel = m.group(0).split("#")[0].rstrip(".:;").replace("\\", "/")
            if (rel, tuple(names)) in seen:
                continue
            seen.add((rel, tuple(names)))
            copy = os.path.join(t["_dir"], devflow_lib.DESIGN_COPY, *rel.split("/"))
            path = copy if os.path.isfile(copy) else os.path.join(run_dir, *rel.split("/"))
            if os.path.isfile(path) and devflow_lib.inside(run_dir, path):
                parts.append(canon_sections(devflow_lib.read_text(path), names))
    return "\n".join(parts)


# ---------------------------------------------------------------- git

def _git(code_dir, *args):
    out = subprocess.run(["git", "-C", code_dir, "-c", "core.quotepath=off"] + list(args), capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    if out.returncode not in (0, 1):   # git grep은 맞는 줄이 없으면 1
        raise RuntimeError((out.stderr or "").strip().split("\n")[0] or "git {}".format(args[0]))
    return out.stdout


def _grep(code_dir, words, rev=None):
    """[(경로, 줄, 글)]: 낱말 가운데 하나라도 있는 줄. rev가 없으면 작업 트리(추적 파일과 무시하지 않는 새 파일),
    있으면 그 커밋. 낱말은 파일로 넘긴다(명령 줄 길이 한도). 아주 긴 줄은 뺀다."""
    if not words:
        return []
    fd, pattern_file = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(words) + "\n")
        args = ["grep", "-n", "-I", "--no-color", "-F", "-f", pattern_file] + ([rev] if rev else ["--untracked"])
        text = _git(code_dir, *args)
    finally:
        os.unlink(pattern_file)
    rows = []
    for line in text.splitlines():
        if rev and line.startswith(rev + ":"):
            line = line[len(rev) + 1:]
        path, _, rest = line.partition(":")
        num, _, body = rest.partition(":")
        if num.isdigit() and len(body) <= LONG_LINE:
            rows.append((path.replace("\\", "/"), int(num), body))
    return rows


def _files(code_dir):
    return [f.replace("\\", "/") for f in _git(code_dir, "ls-files", "--cached", "--others", "--exclude-standard").splitlines()]


def _lines(code_dir, path):
    try:
        return devflow_lib.read_text(os.path.join(code_dir, path)).splitlines()
    except (OSError, UnicodeError, ValueError):
        return []


def is_test_side(path):
    return bool(machine_check.TEST_DIR.search(path) or machine_check.TEST_NAME.search(path)
                or machine_check.TEST_HELPER.search(path))


def _cap(rows):
    if len(rows) > LINE_CAP:
        return rows[:LINE_CAP] + ["- 외 {}줄".format(len(rows) - LINE_CAP)]
    return rows


# ---------------------------------------------------------------- 생산처

CODE_FILE = re.compile(r"\.(?:[cm]?[jt]sx?|py|go|rb|kt|kts|java|rs|php|cs|swift|scala|sql|sh|ps1|ya?ml|toml|json|jsonc|ini|cfg|env|vars|gradle)$"
                       r"|(?:^|/)(?:Makefile|Dockerfile)$", re.I)
COMMENT_LINE = re.compile(r"^\s*(?://|/\*|\*|#(?!\[)|--|;)")
# 이름이 던지거나 돌려주는 값 자체일 때만 생산이다: `throw ERR_X`, `raise MyError(…)`, `throw new AppError("ERR_X")`의 첫 인자.
# 이름을 부른 결과를 돌려주는 `return f(…)`와 문장 안의 이름(`raise ValueError("f failed")`)은 쓰임이다
END = r"(?![\w$])"
FIRST_ARG = r"(?:new\s+)?[\w$.]+\(\s*['\"]?{0}['\"]?\s*[,)]"
PRODUCE_KINDS = (
    ("던짐", r"\b(?:throw|raise)\s+(?:new\s+)?{0}" + END + r"|\b(?:throw|raise)\s+" + FIRST_ARG),
    ("반환", r"\breturn\s+{0}" + END + r"(?!\s*\()|\breturn\s+" + FIRST_ARG),
    ("정의", r"\b(?:def|function|fun|class|interface|type|enum|struct|fn|func|const|let|var|val)\s+{0}" + END
     + r"|^\s*(?:export\s+)?(?:(?:public|private|protected|static|async)\s+)*{0}\s*\([^)]*\)\s*(?:[:{{]|=>)"
     # SQL의 만듦(`create role x`, `create or replace function public.x(`, `create table if not exists "x"`)
     + r"|(?i:\bcreate\s+(?:or\s+replace\s+)?(?:role|user|table|view|materialized\s+view|function|procedure|sequence|type|schema|index|unique\s+index|policy|trigger|extension)\s+(?:if\s+not\s+exists\s+)?(?:[\w\"]+\.)?\"?){0}" + END),
    ("대입", r"^\s*(?:export\s+)?(?:(?:const|let|var|val)\s+)?(?:[\w$]+\.)*{0}\s*(?::[^=]+)?=(?!=)"
     + r"|^\s*['\"]?{0}['\"]?\s*[:=]"),
    # 오류 코드·이름을 글자 그대로 만드는 곳(`{ code: 'db_insert' }`, `return "E_GONE"`). 다른 것이 아닐 때만
    ("문자열", r"['\"`]{0}['\"`]"),
)


def producers(code_dir, names):
    if not names:
        return []
    hits = [h for h in _grep(code_dir, names) if CODE_FILE.search(h[0]) and not COMMENT_LINE.match(h[2])]
    any_name = re.compile(r"(?<![\w$])({})(?![\w$])".format("|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))))
    made = {n: [] for n in names}
    used = {n: 0 for n in names}
    in_tests = {n: 0 for n in names}
    pats = {n: [(label, re.compile(p.format(re.escape(n)))) for label, p in PRODUCE_KINDS] for n in names}
    for path, num, body in hits:
        for name in set(any_name.findall(body)):
            if is_test_side(path):
                in_tests[name] += 1
                continue
            label = next((lab for lab, rx in pats[name] if rx.search(body)), None)
            if label:
                made[name].append("{}:{} {}".format(path, num, label))
            else:
                used[name] += 1
    rows = []
    for name in names:
        use = "그 밖 쓰임 {}곳".format(used[name]) + ("(시험 쪽 {}곳 따로)".format(in_tests[name]) if in_tests[name] else "")
        if made[name]:
            more = " 외 {}곳".format(len(made[name]) - PER_NAME) if len(made[name]) > PER_NAME else ""
            rows.append("- `{}` | 생산: {}{} | {}".format(name, ", ".join(made[name][:PER_NAME]), more, use))
        else:
            rows.append("- `{}` | 생산처 없음 | {}".format(name, use))
    return rows


# ---------------------------------------------------------------- 기존 시험

STRING = re.compile(r"""(?<![\w\\])("[^"\n]{4,80}"|'[^'\n]{4,80}')""")
ASSERT = re.compile(machine_check.ASSERTION.pattern + "|" + machine_check.STRONG_MATCHER.pattern + "|"
                    + machine_check.WEAK_MATCHER.pattern + r"|\.toThrow\w*\(|\.rejects\b|assertRaises|pytest\.raises")
PROSE = re.compile(r"\s|[가-힣]")


def removed_strings(code_dir):
    """작업 트리 변경(HEAD 기준)에서 지운 줄의 문자열 가운데 사람이 읽는 문장(빈칸이나 한글이 든 것)만.
    빈칸 없는 문자열(키, 토큰, 경로)은 값일 수 있어 싣지 않는다. 가림 꼴이 걸리는 문자열도 뺀다."""
    out = []
    for line in _git(code_dir, "diff", "HEAD", "--unified=0", "--no-color").splitlines():
        if line.startswith("-") and not line.startswith("---"):
            for m in STRING.finditer(line[1:]):
                s = m.group(1)
                if PROSE.search(s[1:-1]) and devflow_lib.mask_line(s) == s and s not in out:
                    out.append(s)
    return out


def asserting_tests(code_dir, names, strings):
    """기준 커밋(HEAD)의 시험 파일에서 이름·문구를 단언하는 줄. 하나마다 줄 몇 개와 파일 수."""
    tokens = list(names) + list(strings)
    bare = {t: t.strip("\"'") for t in tokens}
    hits = [h for h in _grep(code_dir, sorted(set(bare.values())), rev="HEAD") if is_test_side(h[0])]
    cache, rows = {}, []
    for token in tokens:
        found = []
        for path, num, body in hits:
            if bare[token] not in body:
                continue
            if path not in cache:
                cache[path] = _git(code_dir, "show", "HEAD:" + path).splitlines()
            if any(ASSERT.search(x) for x in cache[path][num - 1:num + 2]):
                found.append((path, num))
        if found:
            shown = "`{}`".format(token) if token == bare[token] else token
            files = len({p for p, _ in found})
            more = " 외 {}줄(파일 {}개)".format(len(found) - TESTS_PER_NAME, files) if len(found) > TESTS_PER_NAME else ""
            rows.append("- {} | {} 단언{}".format(shown, ", ".join("{}:{}".format(p, n) for p, n in found[:TESTS_PER_NAME]), more))
    return rows


# ---------------------------------------------------------------- 배포 값

DEPLOY_CONFIG = re.compile(r"(?:^|/)(?:wrangler\.(?:toml|jsonc?)|vercel\.json|netlify\.toml|fly\.toml|render\.ya?ml|serverless\.ya?ml"
                           r"|app\.ya?ml|Procfile|\.gitlab-ci\.ya?ml|cloudbuild\.ya?ml|amplify\.ya?ml|firebase\.json)$"
                           r"|(?:^|/)\.github/workflows/[^/]+\.ya?ml$", re.I)
DEPLOY_SCRIPT = re.compile(r"(?:^|/)(?:deploy|rollback|release|배포)(?:[-_.][^/]*)?(?:/[^/]+)*\.(?:sh|ps1|bat|cmd|[cm]?js|ts|py|ya?ml|toml|json)$", re.I)
# 이름의 마디(-, _, . 로 나눈 것) 하나가 이 낱말이어야 한다(`WAITLIST_API_KEY`는 아님). 비밀 이름은 뺀다
LIMIT_WORD = re.compile(r"^(?:timeout|timeouts|retries|retry|attempts|wait|deadline|minutes|seconds)$", re.I)
SECRET_NAME = re.compile(r"key|token|secret|password|passwd|credential", re.I)
DEPLOY_VALUE = re.compile(r"""(?<![\w-])([A-Za-z][\w.-]*)["']?\s*[:=]\s*["']?(\d[\d_.]*)(?![\w.])""")
ROLLBACK = re.compile(r"roll[-_ ]?back|auto[-_]?revert|\brevert\b", re.I)
OPTION = re.compile(r"--?([A-Za-z][\w-]*)[= ](\d+)(?![\w.])")


def _limit_name(name):
    return not SECRET_NAME.search(name) and any(LIMIT_WORD.match(part) for part in re.split(r"[-_.]", name))


def deploy_values(code_dir, result_text):
    rows = []
    for path in _files(code_dir):
        if not (DEPLOY_CONFIG.search(path) or DEPLOY_SCRIPT.search(path)) or is_test_side(path):
            continue
        for num, body in enumerate(_lines(code_dir, path), 1):
            if len(body) > LONG_LINE or COMMENT_LINE.match(body):
                continue
            values = ["{}={}".format(m.group(1), m.group(2)) for m in DEPLOY_VALUE.finditer(body) if _limit_name(m.group(1))]
            values += ["--{}={}".format(m.group(1), m.group(2)) for m in OPTION.finditer(body) if _limit_name(m.group(1))]
            if values:
                rows.append("- {}:{} | {}".format(path, num, ", ".join(dict.fromkeys(values))))
            elif ROLLBACK.search(body):
                rows.append("- {}:{} | 되돌림을 말하는 줄".format(path, num))
    for num, body in enumerate((result_text or "").splitlines(), 1):
        values = ["{}={}".format(m.group(1), m.group(2)) for m in OPTION.finditer(body) if _limit_name(m.group(1))]
        if values:
            rows.append("- result.md:{} | 명령의 옵션 {}".format(num, ", ".join(values)))
    return rows


# ---------------------------------------------------------------- 설정 값의 꼴

ENV_READ = re.compile(r"""process\.env(?:\.([A-Z][A-Z0-9_]+)|\[["']([A-Z][A-Z0-9_]+)["']\])|(?:import\.meta\.env|\benv)\.([A-Z][A-Z0-9_]+)"""
                      r"""|os\.environ(?:\.get)?[\[(]["']([A-Z][A-Z0-9_]+)["']|os\.getenv\(["']([A-Z][A-Z0-9_]+)["']"""
                      r"""|Deno\.env\.get\(["']([A-Z][A-Z0-9_]+)["']\)""")
EXPECT = re.compile(r"""\.(startsWith|endsWith|includes|startswith|endswith)\(\s*(?:"([^"]*)"|'([^']*)')|\.(match|test)\(|(\.length|len\()""")
ENV_FILE = re.compile(r"^(?:\.env(?:\..+)?|\.dev\.vars(?:\..+)?|.+\.env)$")
ENV_PAIR = re.compile(r"""^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$""")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "__pycache__"}
SHAPES = (("JWT", re.compile(r"^eyJ[\w-]+\.[\w-]+\.?[\w-]*$")), ("URL", re.compile(r"^[a-z][a-z0-9+.-]*://")),
          ("PEM", re.compile(r"^-----BEGIN ")),
          ("sk_live_", re.compile(r"^sk_live_")), ("sk_test_", re.compile(r"^sk_test_")), ("sk-", re.compile(r"^sk-")),
          ("pk_", re.compile(r"^pk_")), ("ghp_", re.compile(r"^ghp_")), ("숫자", re.compile(r"^\d+$")),
          ("참·거짓", re.compile(r"^(?:true|false)$", re.I)), ("빈 값", re.compile(r"^$")))


def shape(value):
    """값의 꼴 이름과 길이. 값의 글자는 돌려주지 않는다(URL은 scheme 이름만)."""
    for label, rx in SHAPES:
        if rx.search(value):
            if label == "URL":
                scheme = value.split("://")[0]
                return "길이 {}, 꼴 URL({})".format(len(value), scheme if re.fullmatch(r"[a-z][a-z0-9+.-]{0,15}", scheme) else "?")
            return "길이 {}, 꼴 {}".format(len(value), label)
    return "길이 {}, 꼴 그 밖".format(len(value))


def env_values(text):
    """환경 파일 글의 [(키, 값)]. 따옴표로 연 값은 닫는 따옴표까지 여러 줄을 묶고, 따옴표 없는 값은 ` #` 뒤 주석을 뗀다."""
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        i += 1
        m = ENV_PAIR.match(line)
        if not m or line.lstrip().startswith("#"):
            continue
        raw = m.group(2).strip()
        if raw[:1] in ("'", '"'):
            q, body = raw[0], raw[1:]
            while q not in body and i < len(lines):
                body += "\n" + lines[i]
                i += 1
            value = body.split(q)[0]
        else:
            value = re.split(r"\s+#", raw)[0].strip()
        out.append((m.group(1), value))
    return out


def env_files(code_dir, depth=2):
    out = []
    for root, dirs, files in os.walk(code_dir):
        rel = os.path.relpath(root, code_dir)
        level = 0 if rel == "." else rel.count(os.sep) + 1
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS] if level < depth else []
        for name in files:
            if ENV_FILE.match(name):
                out.append(os.path.normpath(os.path.join(rel, name)).replace("\\", "/"))
    return sorted(out)


def _expect_hints(lines):
    """코드의 기대 꼴: 함수 이름과 리터럴의 길이만(`startsWith(길이 3)`). 리터럴의 글자는 싣지 않는다."""
    hints = []
    for x in lines:
        for m in EXPECT.finditer(x):
            if m.group(1):
                lit = m.group(2) if m.group(2) is not None else m.group(3)
                hints.append("{}(리터럴 길이 {})".format(m.group(1), len(lit or "")))
            elif m.group(4):
                hints.append(m.group(4) + "(정규식)")
            else:
                hints.append("길이 검사")
    return list(dict.fromkeys(hints))


def config_shapes(code_dir):
    stored = {}   # 키 → [(파일, 꼴)]
    for rel in env_files(code_dir):
        try:
            pairs = env_values(devflow_lib.read_text(os.path.join(code_dir, rel)))
        except (OSError, UnicodeError, ValueError):
            continue
        for key, value in pairs:
            stored.setdefault(key, []).append((rel, shape(value)))
    read = {}   # 키 → [인용]
    for path in _files(code_dir):
        if is_test_side(path) or not re.search(r"\.(?:[cm]?[jt]sx?|py|go|rb|kt|java|rs|php|cs|swift)$", path):
            continue
        lines = _lines(code_dir, path)
        for i, body in enumerate(lines):
            if len(body) > LONG_LINE:
                continue
            for m in ENV_READ.finditer(body):
                key = next(g for g in m.groups() if g)
                hints = _expect_hints(lines[i:i + 3])
                read.setdefault(key, []).append("{}:{}".format(path, i + 1) + (" (기대: {})".format(", ".join(hints)) if hints else ""))
    rows = []
    for key in sorted(set(read) | set(stored)):
        code = "코드: " + ", ".join(read[key][:3]) if key in read else "코드에서 읽지 않음"
        kept = " | ".join("{}: {}".format(f, s) for f, s in stored.get(key, [])) or "환경 파일에 키 없음"
        rows.append("- {} | {} | {}".format(key, code, kept))
    return rows


# ---------------------------------------------------------------- 물려받는 환경

INHERIT = (("실제 환경 전체를 넘김", re.compile(r"\.\.\.\s*(?:process\.env|env)\b|\*\*os\.environ|dict\(os\.environ|os\.environ\.copy\(|env\s*=\s*os\.environ")),
           ("환경 파일을 읽음", re.compile(r"\bdotenv\b|--env-file|\bloadEnv\(|\benv_?[Ff]ile\b")),
           ("실행기 설정의 env", re.compile(r"(?<![\w.])env\s*:\s*[{\[]|\bsetupFiles\b|\bglobalSetup\b")))


def inherited_env(code_dir):
    rows = []
    for path in _files(code_dir):
        test_side = is_test_side(path)
        if not (test_side or machine_check.RUNNER_CONFIG.search(path)):
            continue
        for num, body in enumerate(_lines(code_dir, path), 1):
            if len(body) > LONG_LINE:
                continue
            labels = [label for label, rx in INHERIT if rx.search(body)]
            keys = list(dict.fromkeys(next(g for g in m.groups() if g) for m in ENV_READ.finditer(body)))
            if keys:
                labels.append("환경 값을 읽음 " + ", ".join(keys))
            if labels:
                rows.append("- {}:{} | {}".format(path, num, "; ".join(labels)))
    return rows


def security_rows(run_dir, code_dir):
    diff = _git(code_dir, "diff", "HEAD", "--unified=0", "--no-color") + "\n" + machine_check.untracked_diff(code_dir)
    return ["- " + machine_check.signal_row(hit) for hit in machine_check.security_hits(diff, *machine_check.security_signals(run_dir))]


# ---------------------------------------------------------------- 파일

def project_dir(run_dir):
    path = os.path.join(run_dir, "run.md")
    if not os.path.isfile(path):
        return None
    meta, _ = devflow_lib.split_front_matter(devflow_lib.read_text(path))
    value = devflow_lib.parse_meta(meta).get("project", "")
    return value if value and os.path.isdir(value) else None


def _section_rows(key, run_dir, t, code_dir, names, result_text):
    if key == "producer":
        return producers(code_dir, names)
    if key == "tests":
        strings = removed_strings(code_dir) if t.get("kind") in kinds.AUTO_DEPEND_KINDS else []
        return asserting_tests(code_dir, names, strings)
    if key == "deploy":
        return deploy_values(code_dir, result_text)
    if key == "config":
        return config_shapes(code_dir)
    if key == "env":
        return inherited_env(code_dir)
    return security_rows(run_dir, code_dir)


def _why(e):
    return "{}: {}".format(type(e).__name__, str(e).split("\n")[0][:160])


def build(run_dir, t, code_dir):
    checks = kinds.FACT_CHECKS.get(t.get("kind", ""), ())
    code_dir = code_dir if code_dir and os.path.isdir(code_dir) else project_dir(run_dir)
    names, result_text, source_error = [], "", ""
    try:
        names = identifiers(source_text(run_dir, t))
        result_path = os.path.join(t["_dir"], "result.md")
        result_text = devflow_lib.read_text(result_path) if os.path.isfile(result_path) else ""
    except Exception as e:   # 결과 파일·정본을 읽지 못해도 파일은 쓴다
        source_error = _why(e)
    try:
        head = _git(code_dir, "rev-parse", "--short", "HEAD").strip() if code_dir else ""
    except Exception:
        head = ""
    out = ["# {} 미리 뽑은 사실".format(t.get("id", "")), "",
           "뽑은 시각: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
           "코드 폴더: {}".format(code_dir or "없음"), "기준 커밋: {}".format(head or "없음"),
           "이 파일은 판정 전에 스크립트가 뽑은 사실이다. 판단은 들어 있지 않고, 값(비밀값)은 싣지 않는다.", ""]
    for key, title in SECTIONS.items():
        out.append("## " + title)
        if key not in checks:
            out += [NOT_RUN, ""]
            continue
        if not code_dir:
            out += ["- 뽑지 못함: 코드 폴더 없음(흐름의 코드 폴더도 run.md `project`도 없음)", ""]
            continue
        if source_error and key in ("producer", "tests"):
            out += ["- 뽑지 못함: 결과 파일·정본을 읽지 못함({})".format(source_error), ""]
            continue
        try:
            rows = _section_rows(key, run_dir, t, code_dir, names, result_text)
        except Exception as e:   # 검사 하나가 실패해도 다른 절과 파일은 남긴다
            rows = ["- 뽑지 못함: {}".format(_why(e))]
        out += (_cap(rows) or ["- 없음"]) + [""]
    return "\n".join(out)


def write_facts(run_dir, t, code_dir=None):
    path = os.path.join(t["_dir"], kinds.FACTS_FILE)
    try:
        text = build(run_dir, t, code_dir)
    except Exception as e:
        text = "# {} 미리 뽑은 사실\n\n- 뽑지 못함: {}\n".format(t.get("id", ""), _why(e))
    devflow_lib.write_text(path, text)
    return path


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, task_md = argv[1], argv[2]
    code_dir = argv[argv.index("--code-dir") + 1] if "--code-dir" in argv else None
    t = devflow_lib.load_task(task_md)
    path = write_facts(run_dir, t, code_dir)
    print("미리 뽑은 사실: {}".format(path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
