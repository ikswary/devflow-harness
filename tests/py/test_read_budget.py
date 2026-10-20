"""읽는 양과 선언 대조 시험.

- 읽는 양: `reading.BASELINE`의 행위자마다 `reading.row_bytes`(독자 파일의 바이트 합, 경우 파일은 모두 셈) ≤ 상한.
  `PENDING_OVER`(행위자, 상한, 그때 값, 사유)에 든 행은 "그때 값 이하"만 단언한다. 규칙을 지우지 않고는 상한 안으로
  맞출 수 없을 때 넣고, 맞춘 뒤 목록에서 뺀다.
- 선언 대조: 에이전트 정의 「읽을 것」의 경로(formats 파일 포함)와 kind 모듈 「먼저 읽을 것」의 방법 문서 경로를 합친 것이
  `reading.NEW_READS`의 그 행위자 항목 가운데 경로 하나를 가리키는 것과 같다. 견주지 않는 것: 자기 정의 파일(시스템
  프롬프트), kind 모듈 파일(「맡은 kind 모듈」로만 적음), 패턴 항목(`*`·`{경우}`), 아직 없는 `run-check.md`(「있으면」).
  - 정의의 경로 가운데 `→`가 있는 줄은 그 앞의 백틱 kind에만 든다(실행 판정자의 kind별 `run-check.md`).
  - 모듈의 방법 문서: 작성자는 그 kind의 모듈(변경은 변경 모듈만) 「먼저 읽을 것」에서 `판정자:` 줄을 뺀 것.
    작성자별 줄(`- {역할} 작성자(`{에이전트}`): …`)이 있으면 자기 줄만, 그 줄의 대상 조건
    (`설계면`·`화면 정본이면`, `그리고` 뒤는 조건 없음)은 변경 대상으로 가른다. 읽기 판정자는 `판정자:` 줄, 실행 판정자는 없음.
"""
import re

import kinds
import reading
from conftest import ROOT

# (행위자, 상한, 그때 값, 사유). 평소 빈 목록
PENDING_OVER: list[tuple[str, int, int, str]] = []

AGENT_DIR = ROOT / "agents"
KIND_DIR = ROOT / "references" / "kinds"
PLUGIN_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+\.md)")
AUTHOR_LINE_RE = re.compile(r"- .+ 작성자\(`([a-z-]+)`\): (.*)\Z")
# 작성자별 줄의 대상 조건 낱말 → 변경 대상(change.md 「먼저 읽을 것」)
TARGET_WORDS = (("화면 정본이면", "ui-design"), ("설계면", "design"))


def over_budget(pending=None, sizes=None):
    """[(행위자, 상한, 지금, 한도)]: 지금 값이 한도(상한, `PENDING_OVER` 행은 그때 값)를 넘는 행."""
    pending = {a: then for a, _, then, _ in (PENDING_OVER if pending is None else pending)}
    out = []
    for actor, base in reading.BASELINE.items():
        now = reading.row_bytes(actor) if sizes is None else sizes[actor]
        limit = pending.get(actor, base)
        if now > limit:
            out.append((actor, base, now, limit))
    return out


def test_pending_over_rows_are_baseline_rows_over_their_baseline():
    seen = set()
    for actor, base, then, item in PENDING_OVER:
        assert actor in reading.BASELINE and actor not in seen, actor
        seen.add(actor)
        assert base == reading.BASELINE[actor], (actor, base)
        assert then > base and item, (actor, then, item)   # 상한 이하면 목록에 둘 까닭이 없다


def test_read_budget():
    assert len(reading.BASELINE) == 48
    assert over_budget() == []


def test_read_budget_detects_one_byte_over_limit_and_pending_value():
    sizes = {a: base for a, base in reading.BASELINE.items()}
    assert over_budget(pending=[], sizes=sizes) == []
    sizes["code-writer:fix"] += 1
    assert over_budget(pending=[], sizes=sizes) == [("code-writer:fix", 54645, 54646, 54645)]
    # 보류 행은 그때 값까지 받고, 그 위 1바이트에서 걸린다
    pending = [("code-writer:fix", 54645, 54646, "표본")]
    assert over_budget(pending=pending, sizes=sizes) == []
    sizes["code-writer:fix"] += 1
    assert over_budget(pending=pending, sizes=sizes) == [("code-writer:fix", 54645, 54647, 54646)]


# ---------------------------------------------------------------------------
# 선언 대조


def section(text, title):
    """`## {title}` 절의 줄들(다음 `## ` 앞까지)."""
    lines = text.splitlines()
    start = lines.index("## " + title) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def agent_paths(text, kind):
    """정의 「읽을 것」의 경로 가운데 그 kind의 행위자에게 드는 것."""
    out = set()
    for line in section(text, "읽을 것"):
        if "→" not in line:
            out |= set(PLUGIN_PATH_RE.findall(line))
            continue
        for part in line.split(", "):
            if "→" in part:
                left, right = part.split("→", 1)
                if kind in re.findall(r"`([a-z-]+)`", left):
                    out |= set(PLUGIN_PATH_RE.findall(right))
    return out


def targeted_paths(text, target):
    """작성자별 줄의 글에서 그 변경 대상(없으면 None)에 드는 방법 문서 경로."""
    out, cond = set(), None
    for piece in re.split(r"(\$\{CLAUDE_PLUGIN_ROOT\}/[A-Za-z0-9_./-]+\.md)", text):
        m = PLUGIN_PATH_RE.fullmatch(piece)
        if not m:
            if "그리고" in piece:
                cond = None
            for word, t in TARGET_WORDS:
                if word in piece:
                    cond = t
                    break
            continue
        if cond is None or cond == target:
            out.add(m.group(1))
    return out


def module_practices(text, agent, target=None):
    """kind 모듈 「먼저 읽을 것」의 방법 문서 경로. agent가 판정자면 `판정자:` 줄만."""
    lines = section(text, "먼저 읽을 것")
    if agent == "read-judge":
        return {p for line in lines if line.startswith("판정자:") for p in PLUGIN_PATH_RE.findall(line)}
    if agent == "run-judge":
        return set()
    authors = {m.group(1): m.group(2) for m in map(AUTHOR_LINE_RE.match, lines) if m}
    if authors:
        assert agent in authors, "작성자별 줄에 `{}`가 없음".format(agent)
        return {p for p in targeted_paths(authors[agent], target) if p.startswith("references/practices/")}
    body = "\n".join(line for line in lines if not line.startswith("판정자:"))
    return {p for p in PLUGIN_PATH_RE.findall(body) if p.startswith("references/practices/")}


def declared(actor, agent_text=None, module_text=None):
    """그 행위자의 선언: 정의 「읽을 것」 경로 + 모듈 「먼저 읽을 것」의 방법 문서."""
    agent, kind, target = reading.parse_actor(actor)
    agent_text = agent_text or (AGENT_DIR / (agent + ".md")).read_text(encoding="utf-8")
    module_text = module_text or (KIND_DIR / kinds.KINDS[kind].definition).read_text(encoding="utf-8")
    return agent_paths(agent_text, kind) | module_practices(module_text, agent, target)


def expected(actor):
    """NEW_READS 가운데 견주는 항목(머리 docstring)."""
    agent, _, _ = reading.parse_actor(actor)
    out = set()
    for entry in reading.NEW_READS[actor]:
        if "*" in entry or reading.CASE in entry or entry == "agents/{}.md".format(agent):
            continue
        if re.fullmatch(r"references/kinds/[a-z-]+\.md", entry):
            continue
        if entry.endswith("/run-check.md") and not (ROOT / entry).is_file():
            continue
        out.add(entry)
    return out


def test_declared_reads_match_new_reads():
    actors = [a for a in reading.NEW_READS if a != "main"]
    assert len(actors) == 48
    problems = {a: (sorted(declared(a) - expected(a)), sorted(expected(a) - declared(a)))
                for a in actors if declared(a) != expected(a)}
    assert problems == {}


def test_declared_reads_detect_a_dropped_practice_and_target_words():
    actor = "design-writer:change:ui-design"
    text = (KIND_DIR / "change.md").read_text(encoding="utf-8")
    assert declared(actor, module_text=text) == expected(actor)
    assert "references/practices/ui-spec.md" in declared(actor) and "references/practices/design-doc.md" not in declared(actor)
    broken = text.replace("화면 정본이면 `${CLAUDE_PLUGIN_ROOT}/references/practices/ui-spec.md`, ", "")
    assert broken != text
    assert expected(actor) - declared(actor, module_text=broken) == {"references/practices/ui-spec.md"}
    # 실행 판정자의 kind별 줄은 그 kind에만 든다
    run = (AGENT_DIR / "run-judge.md").read_text(encoding="utf-8")
    assert "references/kinds/implementation/run-check.md" in agent_paths(run, "fix")
    assert "references/kinds/implementation/run-check.md" not in agent_paths(run, "deploy-exec")
