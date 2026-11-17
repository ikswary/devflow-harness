"""`docs/plugin-practices.md`가 말하는 원칙 가운데 기계로 지킬 수 있는 것.

근거는 공식 문서(`_workspace/research-official-docs.md`): SKILL.md 500줄 미만, description 스펙 상한 1,024자,
서브에이전트 `tools`는 허용 목록, 플러그인 에이전트는 hooks·mcpServers·permissionMode를 무시, 경로는 슬래시.
"""
import json
import re

from conftest import ROOT

SKILL = ROOT / "skills" / "devflow-harness" / "SKILL.md"
AGENTS = sorted((ROOT / "agents").glob("*.md"))
PRACTICES = ROOT / "docs" / "plugin-practices.md"
IGNORED_IN_PLUGIN_AGENTS = ("hooks", "mcpServers", "permissionMode")
AGENT_DESC_MAX = 400   # 문서에 글자 상한은 없다("keep them short"). 지금 가장 긴 것 346자에 여유를 둔 값


def front(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path.name
    return text.split("---\n", 2)[1]


def field(fm, name):
    m = re.search(r"^{}:\s*(.*)$".format(re.escape(name)), fm, re.M)
    return m.group(1).strip().strip('"') if m else None


def test_skill_is_a_short_table_of_contents():
    fm = front(SKILL)
    desc = field(fm, "description")
    assert desc and len(desc) <= 1024, len(desc or "")
    assert SKILL.read_text(encoding="utf-8").count("\n") < 500


def test_agents_have_short_descriptions_and_tool_allowlists():
    assert len(AGENTS) == 9
    for path in AGENTS:
        fm = front(path)
        desc, tools = field(fm, "description"), field(fm, "tools")
        assert desc and len(desc) <= AGENT_DESC_MAX, (path.name, len(desc or ""))
        assert tools and "*" not in tools, path.name   # 생략하면 모든 도구를 물려받는다
        for name in IGNORED_IN_PLUGIN_AGENTS:
            assert field(fm, name) is None, (path.name, name)   # 플러그인 에이전트에서는 조용히 무시된다


def test_manifest_paths_use_forward_slashes():
    for name in ("plugin.json", "marketplace.json"):
        text = (ROOT / ".claude-plugin" / name).read_text(encoding="utf-8")
        for value in re.findall(r'"([^"]*)"', text):
            assert "\\" not in value, (name, value)   # 백슬래시 경로는 macOS·Linux에서 거부된다
        json.loads(text)


def test_practices_doc_is_reachable_and_names_its_tests():
    """원칙 문서는 maintain.md에서 가리키고, 문서가 이 시험 파일을 이름으로 가리킨다(문서와 시험을 한 묶음으로)."""
    assert "docs/plugin-practices.md" in (ROOT / "references" / "main" / "maintain.md").read_text(encoding="utf-8")
    assert "tests/py/test_plugin_practices.py" in PRACTICES.read_text(encoding="utf-8")
