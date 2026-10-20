"""행위자별로 읽는 하네스 문서(독자 데이터)와 읽는 양 계산.

시험 파일이 아니라 시험(`test_read_budget.py`)이 쓰는 도우미다.
- 행위자 = (에이전트, kind) 쌍 `{에이전트}:{kind}`와 메인 `main`. change는 대상마다 `{에이전트}:change:{대상}`.
- `NEW_READS`: 행위자마다 읽는 하네스 문서. 파일 단위이고 아직 없는 파일도 이름으로 적는다. `*`는 `/`를 넘지 않는 글자들,
  `{경우}`는 kind 모듈 폴더 바로 아래의 `.md` 가운데 `main-order.md`·`run-check.md`가 아닌 것(경우 파일).
- `BASELINE`: 행위자마다 읽는 양의 상한(바이트, 에이전트 정의 포함). 메인은 상한이 없어 뺀다.

사용법:
  python3 tests/py/reading.py budget
    `BASELINE`의 행위자마다 `{행위자} {상한} {지금}`, 지금 값이 상한보다 크면 끝에 ` 넘음`. 종료 0(경보).
    지금 값 = `row_bytes`(독자 파일의 바이트 합).
  사용법 오류는 종료 2.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import kinds  # noqa: E402  등록표

# ---------------------------------------------------------------------------
# 경로

ENTRY = "skills/devflow-harness/SKILL.md"
CONTRACT = "references/core/contract.md"
FORMATS = "references/core/formats.md"
WRITER = "references/roles/writer.md"
AGENT_ROLE = "references/roles/agent.md"
JUDGE_ROLE = "references/roles/judge.md"
CASE = "{경우}"
CASE_EXCLUDE = ("main-order.md", "run-check.md")


def _kind(definition):
    return "references/kinds/{}.md".format(definition)


def _practice(name):
    return "references/practices/{}.md".format(name)


def _agent(name):
    return "agents/{}.md".format(name)


def _format_file(name):
    return "{}/{}.md".format(kinds.FORMATS_DIR, name)


def definition_of(kind):
    """kind → 모듈 이름(`references/kinds/` 파일 이름에서 `.md`를 뗀 것)."""
    return kinds.KINDS[kind].definition[:-3]


def parse_actor(actor):
    """`{에이전트}:{kind}[:{대상}]` → (에이전트, kind, 대상 또는 None). 메인은 ("main", None, None)."""
    if actor == "main":
        return "main", None, None
    parts = actor.split(":")
    return parts[0], parts[1], parts[2] if len(parts) > 2 else None


# ---------------------------------------------------------------------------
# NEW_READS


def _module(definition):
    """kind 모듈과 경우 파일."""
    return (_kind(definition), "references/kinds/{}/{}".format(definition, CASE))


def _practice_files(name):
    """방법 문서와 그 아래 파일."""
    return (_practice(name), "references/practices/{}/*.md".format(name))


def _formats_for(reader):
    return tuple(_format_file(f) for f in kinds.FORMATS_READERS[reader])


# 작성자 행위자마다 (맡은 모듈들, 「먼저 읽을 것」의 방법 문서)
_WRITER_SPEC = {
    "requirements-writer:question": (("question",), ()),
    "requirements-writer:req-overview": (("req-overview",), ("requirements-spec",)),
    "requirements-writer:brief": (("brief",), ("product-brief",)),
    "requirements-writer:req-detail": (("req-detail",), ("requirements-spec",)),
    "requirements-writer:change:req-overview": (("change", "req-overview"), ()),
    "requirements-writer:change:req-detail": (("change", "req-detail"), ()),
    "requirements-writer:change:brief": (("change", "brief"), ()),
    "cause-writer:root-cause": (("root-cause",), ("root-cause-analysis", "build-and-test", "test-rules")),
    "cause-writer:question": (("question",), ("root-cause-analysis", "build-and-test", "test-rules")),
    "design-writer:design": (("design",), ("design-doc", "test-rules")),
    "design-writer:ui-design": (("ui-design",), ("ui-spec", "test-rules")),
    "design-writer:change:design": (("change", "design"), ("design-doc", "test-rules")),
    "design-writer:change:ui-design": (("change", "ui-design"), ("ui-spec", "test-rules")),
    "design-writer:question": (("question",), ("design-doc", "test-rules")),
    "code-writer:implementation": (("implementation",), ("implementation-practice", "build-and-test", "test-rules")),
    "code-writer:fix": (("implementation",), ("implementation-practice", "build-and-test", "test-rules")),
    "verify-writer:flow-verify": (("verify",), ("code-review-checklist", "test-rules")),
    "verify-writer:full-verify": (("verify",), ("code-review-checklist", "test-rules")),
    "verify-writer:reverify": (("verify",), ("code-review-checklist", "test-rules")),
    "release-writer:wrap-up": (("wrap-up",), ("release-practice",)),
    "release-writer:deploy-plan": (("deploy-plan",), ("release-practice",)),
    "release-writer:deploy-exec": (("deploy-exec",), ("release-practice",)),
}
# 변경 task의 대상 정의
_CHANGE_TARGETS = ("req-overview", "req-detail", "brief", "design", "ui-design")
# 읽기 판정자가 판정하는 kind(변경은 대상마다)
_READ_JUDGE_KINDS = (("question", "req-overview", "req-detail", "brief", "ui-design")
                     + tuple("change:" + t for t in _CHANGE_TARGETS)
                     + ("design", "implementation", "fix", "root-cause", "flow-verify", "full-verify", "reverify",
                        "merge", "wrap-up", "deploy-plan", "deploy-exec"))
# 실행 판정자가 판정하는 kind
_RUN_JUDGE_KINDS = ("implementation", "fix", "root-cause", "merge", "deploy-exec")
# 읽기 판정자의 판정용 방법 문서: test-rules(implementation·fix·design·root-cause·검증 셋), code-review-checklist(검증 셋)
_READ_JUDGE_PRACTICES = {k: ("test-rules",) for k in ("implementation", "fix", "design", "root-cause")}
_READ_JUDGE_PRACTICES.update({k: ("test-rules", "code-review-checklist")
                              for k in ("flow-verify", "full-verify", "reverify")})


def _new_agent(agent, *files):
    """에이전트 8 공통: 공통 계약, 에이전트 공통, 자기 정의 파일."""
    return (CONTRACT, AGENT_ROLE, _agent(agent)) + files


def _new_writer(actor):
    agent, _, _ = parse_actor(actor)
    modules, practices = _WRITER_SPEC[actor]
    files = (WRITER,) + _formats_for("writer")
    for m in modules:
        files += _module(m)
    for p in practices:
        files += _practice_files(p)
    return frozenset(_new_agent(agent, *files))


def _new_read_judge(kind, target=None):
    files = (WRITER, JUDGE_ROLE) + _formats_for("read-judge") + _module(definition_of(kind))
    if target:
        files += _module(target)   # change는 대상 모듈과 그 경우 파일도
    for p in _READ_JUDGE_PRACTICES.get(kind, ()):
        files += _practice_files(p)
    return frozenset(_new_agent("read-judge", *files))


def _new_run_judge(kind):
    files = (JUDGE_ROLE,) + _formats_for("run-judge") + _practice_files("build-and-test") + (
        "references/kinds/{}/run-check.md".format(definition_of(kind)),)
    return frozenset(_new_agent("run-judge", *files))


NEW_READS = {}
NEW_READS.update({a: _new_writer(a) for a in _WRITER_SPEC})
NEW_READS.update({"read-judge:" + k: _new_read_judge(*parse_actor("read-judge:" + k)[1:]) for k in _READ_JUDGE_KINDS})
NEW_READS.update({"run-judge:" + k: _new_run_judge(k) for k in _RUN_JUDGE_KINDS})
# 메인: 진입·references/main/, 공통 계약, formats 전체(목차·파일), registry(목차·파일), merge·wrap-up·deploy-exec 모듈,
# 모든 main-order.md, (새 실행) project-recon
NEW_READS["main"] = frozenset((ENTRY, "references/main/*.md", CONTRACT, FORMATS, kinds.FORMATS_DIR + "/*.md",
                               kinds.MD_INDEX, kinds.MD_DIR + "/*.md")
                              + _module("merge") + _module("wrap-up") + _module("deploy-exec")
                              + ("references/kinds/*/main-order.md",) + _practice_files("project-recon"))

# ---------------------------------------------------------------------------
# BASELINE: 행위자마다 읽는 양의 상한(바이트). 문서를 고쳐 이 값을 넘으면 시험이 실패한다.

BASELINE = {
    "requirements-writer:question": 32165,
    "requirements-writer:req-overview": 37209,
    "requirements-writer:brief": 43580,
    "requirements-writer:req-detail": 37507,
    "requirements-writer:change:req-overview": 39251,
    "requirements-writer:change:req-detail": 39549,
    "requirements-writer:change:brief": 43557,
    "cause-writer:root-cause": 48494,
    "cause-writer:question": 46754,
    "design-writer:design": 55214,
    "design-writer:ui-design": 55933,
    "design-writer:change:design": 59694,
    "design-writer:change:ui-design": 60413,
    "design-writer:question": 42802,
    "code-writer:implementation": 54645,
    "code-writer:fix": 54645,
    "verify-writer:flow-verify": 47398,
    "verify-writer:full-verify": 47398,
    "verify-writer:reverify": 47398,
    "release-writer:wrap-up": 41637,
    "release-writer:deploy-plan": 50122,
    "release-writer:deploy-exec": 47793,
    "read-judge:question": 32449,
    "read-judge:req-overview": 35055,
    "read-judge:req-detail": 35353,
    "read-judge:brief": 39361,
    "read-judge:ui-design": 40296,
    "read-judge:change:req-overview": 39535,
    "read-judge:change:req-detail": 39833,
    "read-judge:change:brief": 43841,
    "read-judge:change:design": 49341,
    "read-judge:change:ui-design": 44776,
    "read-judge:design": 51164,
    "read-judge:implementation": 45220,
    "read-judge:fix": 45220,
    "read-judge:root-cause": 40492,
    "read-judge:flow-verify": 47504,
    "read-judge:full-verify": 47504,
    "read-judge:reverify": 47504,
    "read-judge:merge": 37916,
    "read-judge:wrap-up": 37212,
    "read-judge:deploy-plan": 45697,
    "read-judge:deploy-exec": 43368,
    "run-judge:implementation": 27422,
    "run-judge:fix": 27422,
    "run-judge:root-cause": 26719,
    "run-judge:merge": 26719,
    "run-judge:deploy-exec": 28165,
}

# ---------------------------------------------------------------------------
# 읽는 양


def _pattern_re(entry):
    if CASE in entry:
        prefix = entry.split(CASE)[0]
        return re.compile(re.escape(prefix) + r"(?!(?:{})\Z)[^/]+\.md\Z".format(
            "|".join(re.escape(x) for x in CASE_EXCLUDE)))
    return re.compile("".join("[^/]*" if part == "*" else re.escape(part)
                              for part in re.split(r"(\*)", entry)) + r"\Z")


def matches(entry, path):
    """독자 표의 항목 하나가 파일 경로에 닿는지(정확한 경로, `*`, `{경우}`)."""
    if "*" in entry or CASE in entry:
        return bool(_pattern_re(entry).match(path))
    return entry == path


def _files():
    """{경로: 바이트}: 작업 트리의 skills/·references/·agents/ 아래 파일."""
    out = {}
    for top in ("skills", "references", "agents"):
        for p in (ROOT / top).rglob("*"):
            if p.is_file():
                out[p.relative_to(ROOT).as_posix()] = p.stat().st_size
    return out


def row_bytes(actor):
    """독자 파일의 바이트 합(경우 파일은 모두 셈). 없는 파일은 0."""
    files = _files()
    sizes = {}
    for entry in NEW_READS[actor]:
        if "*" in entry or CASE in entry:
            sizes.update({p: s for p, s in files.items() if matches(entry, p)})
        elif entry in files:
            sizes[entry] = files[entry]
    return sum(sizes.values())


USAGE = "사용법: python3 tests/py/reading.py budget\n"


def main(argv):
    if argv != ["budget"]:
        sys.stderr.write(USAGE)
        return 2
    out = []
    for actor, base in BASELINE.items():
        now = row_bytes(actor)
        out.append("{} {} {}{}".format(actor, base, now, " 넘음" if now > base else ""))
    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
