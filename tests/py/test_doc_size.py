"""문서 크기 도구 `tests/py/doc_size.py`의 고정 표본 시험.

임시 폴더를 플러그인 폴더로 삼아(`doc_size.ROOT`를 바꿈) 상한 바로 위·바로 아래 파일과 `PENDING`을 본다.
맨 아래 「문서 크기 상한 시험」은 이 저장소의 하네스 문서를 그대로 잰다.
"""
import pytest

import doc_size

ENTRY = "skills/devflow-harness/SKILL.md"


@pytest.fixture(name="root")
def _root(tmp_path, monkeypatch):
    monkeypatch.setattr(doc_size, "ROOT", tmp_path)
    monkeypatch.setattr(doc_size, "PENDING", [])
    return tmp_path


def put(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def lines(n):
    return b"x\n" * n


def size(n):
    return b"x" * (n - 1) + b"\n"


def test_101_lines_is_over_and_100_is_not(root):
    over = put(root, "references/a.md", lines(101))
    ok = put(root, "references/b.md", lines(100))
    assert doc_size.check([str(root / over), str(root / ok)]) == [("references/a.md", 101, 202, "줄")]


def test_8193_bytes_is_over_and_8192_is_not(root):
    over = put(root, "agents/a.md", size(8193))
    ok = put(root, "agents/b.md", size(8192))
    assert doc_size.check([str(root / over), str(root / ok)]) == [("agents/a.md", 1, 8193, "바이트")]


def test_entry_6145_bytes_is_over_and_6144_is_not(root):
    put(root, ENTRY, size(6145))
    assert doc_size.check([str(root / ENTRY)]) == [(ENTRY, 1, 6145, "진입")]
    put(root, ENTRY, size(6144))
    assert doc_size.check([str(root / ENTRY)]) == []


def test_pending_file_is_normal_up_to_its_value_and_over_beyond(root, monkeypatch):
    rel = put(root, "references/kinds/x.md", size(8300))
    monkeypatch.setattr(doc_size, "PENDING", [(rel, "바이트", 8300, "줄일 후보 L-01")])
    assert doc_size.check([str(root / rel)]) == []
    put(root, rel, size(8301))
    assert doc_size.check([str(root / rel)]) == [(rel, 1, 8301, "바이트")]


def test_pending_covers_only_its_limit(root, monkeypatch):
    rel = put(root, "references/kinds/y.md", lines(101) + size(8200))
    monkeypatch.setattr(doc_size, "PENDING", [(rel, "바이트", 9000, "항목")])
    assert doc_size.check([str(root / rel)]) == [(rel, 102, 8402, "줄")]


def test_no_path_checks_scope_without_repeats_docs_or_nested_agents(root):
    for rel in ("skills/a/b/c.md", "references/core/repeats.md", "docs/notes.md", "agents/sub/x.md",
                "references/x.txt", "README.md"):
        put(root, rel, lines(101))
    put(root, "agents/ok.md", lines(1))
    assert doc_size.scope_files() == ["agents/ok.md", "skills/a/b/c.md"]
    assert doc_size.check([]) == [("skills/a/b/c.md", 101, 202, "줄")]


def test_main_prints_over_lines_and_exits_1(root, capsys):
    put(root, "references/a.md", lines(101))
    put(root, ENTRY, size(6145))
    assert doc_size.main(["check"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "references/a.md 101줄 202B 넘음(줄)",
        "skills/devflow-harness/SKILL.md 1줄 6145B 넘음(진입)",
        "doc_size: 2개 넘음"]


def test_main_counts_pending_as_normal_and_exits_0(root, capsys, monkeypatch):
    rel = put(root, "references/a.md", lines(150))
    monkeypatch.setattr(doc_size, "PENDING", [(rel, "줄", 150, "항목 1")])
    assert doc_size.main(["check"]) == 0
    assert capsys.readouterr().out.splitlines() == ["references/a.md 150줄 300B 보류(줄 ≤ 150: 항목 1)",
                                                    "doc_size: 정상"]


def test_main_missing_path_and_bad_usage_exit_2(root, capsys):
    assert doc_size.main(["check", str(root / "references/none.md")]) == 2
    assert "references/none.md 없음" in capsys.readouterr().err
    assert doc_size.main([]) == 2
    assert doc_size.main(["check", "--rev"]) == 2
    assert "사용법: python3 tests/py/doc_size.py check" in capsys.readouterr().err


# ── 문서 크기 상한 시험: 이 저장소의 하네스 문서를 그대로 잰다 ──

MAIN_DIR = "references/main/"
MAIN_FILES = sorted(p.name for p in (doc_size.ROOT / MAIN_DIR).glob("*.md"))
# 진입이 직접 가리켜야 하는 그 밖의 파일·폴더(formats, registry 목차와 폴더, kind의 main-order)
ENTRY_POINTS = ("`references/core/contract.md`", "`references/core/formats.md`", "`references/formats/`",
                "`references/core/registry.md`", "`references/registry/`", "`references/kinds/{정의}/main-order.md`")


def entry_text():
    path = doc_size.ROOT / ENTRY
    assert path.is_file(), "진입 {} 없음 — 플러그인 폴더에서 돌린다".format(path)
    return path.read_text(encoding="utf-8")


def test_repo_harness_docs_are_within_limits_or_pending_value():
    files = doc_size.scope_files()
    assert ENTRY in files and len(files) > len(MAIN_FILES)   # 범위를 실제로 잼(빈 범위로 녹색이 되지 않게)
    assert doc_size.check([]) == []


def test_repo_entry_limit_is_6144_bytes():
    assert doc_size.LIMITS["진입"] == 6144
    assert doc_size.limits_of(ENTRY) == ("줄", "진입")


def test_main_dir_has_step_files():
    assert MAIN_FILES, "{} 아래 단계 파일이 없음".format(doc_size.ROOT / MAIN_DIR)


@pytest.mark.parametrize("name", MAIN_FILES)
def test_entry_points_to_each_main_file(name):
    assert "`{}{}`".format(MAIN_DIR, name) in entry_text()


@pytest.mark.parametrize("name", MAIN_FILES)
def test_main_file_does_not_point_into_main_dir(name):
    text = (doc_size.ROOT / MAIN_DIR / name).read_text(encoding="utf-8")
    assert text.strip(), name
    assert MAIN_DIR not in text


@pytest.mark.parametrize("point", ENTRY_POINTS)
def test_entry_points_to_contract_formats_registry_and_main_order(point):
    assert point in entry_text()
