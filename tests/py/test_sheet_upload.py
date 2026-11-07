"""한 장 올리기(references/main/sheet-upload.md).

- 값은 「이번 실행의 값」 `한 장 올리기`이고, 행이 없는 옛 실행은 `없음`이다. 값이 `허용`일 때만 `--sheet`가 올릴 파일을 말한다.
- 올린 결과는 journal에 남고 `collect.py --measure`가 값과 횟수를 한 줄로 낸다.
- `sheet.html`은 고치지 않고 그대로 올라가므로 Artifact의 틀 계약을 만족해야 한다: 게시 때 뼈대로 감싸이고, 바깥 자원과 `file:`이 막히고,
  제목은 앞 8KB에서 찾고, 휴대폰 폭에서 가로로 밀리지 않고, 어두운 화면에서 글자가 읽힌다.
"""
import re
from pathlib import Path

import pytest

import collect
import devflow_lib as lib
import visual
from conftest import run_script, write
from test_flow_review import PAIR, flow_verify
from test_code_check import FV
from test_sheet import page_of, task

ROOT = Path(__file__).resolve().parents[2]
SEND = "https://claude.ai/code/artifact/00000000"


def allow(run_dir, value="허용"):
    path = run_dir.path / "run.md"
    text = path.read_text(encoding="utf-8")
    assert "## 이번 실행의 값" in text
    write(path, text.replace("## 이번 실행의 값\n", "## 이번 실행의 값\n| 한 장 올리기 | {} |\n".format(value), 1))


def sheet_out(run_dir, tid="T001"):
    p = run_script("visual", run_dir.path, tid, "--sheet")
    assert p.returncode == 0, p.output
    return p.stdout


# ---------------------------------------------------------------- 값

def test_run_without_the_row_reads_as_none(run_dir):
    assert lib.sheet_upload(str(run_dir.path)) == "없음"


@pytest.mark.parametrize("value,want", [("허용", "허용"), ("없음", "없음"), ("허용 아님", "없음"), ("", "없음")])
def test_only_the_exact_value_allows(run_dir, value, want):
    allow(run_dir, value)
    assert lib.sheet_upload(str(run_dir.path)) == want


def test_sheet_names_the_file_only_when_allowed(run_dir):
    task(run_dir, material="한 일")
    assert "올릴 파일:" not in sheet_out(run_dir)
    allow(run_dir)
    out = sheet_out(run_dir)
    assert "한 장: file:///" in out and "올릴 파일: " + str(run_dir.task_dir("T001") / "sheet.html") in out


def test_oversized_page_says_it_cannot_be_sent(run_dir, monkeypatch, capsys):
    task(run_dir, material="한 일")
    allow(run_dir)
    monkeypatch.setattr(visual, "UPLOAD_LIMIT", 10)
    assert visual.sheet(str(run_dir.path), "T001") == 0
    out = capsys.readouterr().out
    assert "올리지 못함: " in out and "올릴 파일:" not in out


def test_no_sheet_does_not_name_a_file(run_dir):
    run_dir.task("T001", "시험 task", kind="design", block="설계", status="승인대기", started_version="1.2.0-dev.1", rules="2")
    allow(run_dir)
    out = sheet_out(run_dir)
    assert "한 장 없음" in out and "올릴 파일:" not in out


# ---------------------------------------------------------------- 측정

def test_measure_counts_the_value_and_marks(run_dir):
    task(run_dir, material="한 일")
    assert collect.sheet_upload_line(str(run_dir.path)) == "- 한 장 올리기: 없음, 올림 0, 못 올림 0"
    allow(run_dir)
    assert run_script("visual", run_dir.path, "T001", "--sheet-sent", SEND).returncode == 0
    assert run_script("visual", run_dir.path, "T001", "--sheet-sent", SEND).returncode == 0
    assert run_script("visual", run_dir.path, "T001", "--sheet-failed", "도구가 거부함 | 재시도 안 함").returncode == 0
    line = collect.sheet_upload_line(str(run_dir.path))
    assert line == "- 한 장 올리기: 허용, 올림 2, 못 올림 1"
    assert line in collect.approval_measure(str(run_dir.path), run_dir.tasks())


def test_failure_reason_is_masked_and_mark_needs_a_value(run_dir):
    task(run_dir, material="한 일")
    assert run_script("visual", run_dir.path, "T001", "--sheet-failed", "password=hunter2-real-secret").returncode == 0
    assert "hunter2-real-secret" not in (run_dir.path / "journal.md").read_text(encoding="utf-8")
    assert run_script("visual", run_dir.path, "T001", "--sheet-sent").returncode == 2


# ---------------------------------------------------------------- Artifact의 틀

def tokens(block):
    return dict(re.findall(r"--(\w+):(#[0-9a-f]{3,6})", block))


def luminance(color):
    value = color.lstrip("#")
    value = "".join(c * 2 for c in value) if len(value) == 3 else value
    def channel(i):
        c = int(value[i:i + 2], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4)


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("block", [visual.SHEET_LIGHT, visual.SHEET_DARK])
@pytest.mark.parametrize("surface", ["bg", "code", "add", "del"])
def test_text_is_readable_in_both_themes(block, surface):
    colors = tokens(block)
    assert contrast(colors["fg"], colors[surface]) >= 4.5


def test_style_follows_the_viewer_theme_and_has_no_literal_colors_outside_tokens():
    style = visual.SHEET_STYLE
    assert style.startswith(":root{--bg:") and '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){' in style
    assert ':root[data-theme="dark"]{' in style and "color-scheme:dark" in visual.SHEET_DARK
    assert set(tokens(visual.SHEET_LIGHT)) == set(tokens(visual.SHEET_DARK))
    rules = style.split(':root[data-theme="dark"]{')[1].split("}", 1)[1]
    assert re.findall(r"#[0-9a-f]{3,6}", rules) == ["#fff"]   # 와이어프레임 틀의 바탕뿐이다
    assert "color:var(--fg);background:var(--bg)" in rules


def test_phone_width_rules():
    style = visual.SHEET_STYLE
    assert "padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))" in style
    assert "padding-block:1rem" in style and "padding:1rem" not in style
    assert "overflow-wrap:anywhere" in style and "img{max-width:100%" in style and "iframe{box-sizing:border-box;width:100%" in style


def test_page_head_holds_title_within_8kb_and_nothing_external(run_dir):
    task(run_dir, material="한 일 https://example.com/a", title="긴 제목 " * 40)
    page = page_of(run_dir)
    head = page.encode("utf-8")[:8192].decode("utf-8", "ignore")
    title = re.search(r"<title>(.*?)</title>", head).group(1)
    assert title.startswith("T001 긴 제목") and len(title) <= visual.SHEET_TITLE_CHARS
    assert 'name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"' in head
    assert 'name="claude:viewport-fit-sides"' in head
    assert "<script" not in page and "<link" not in page and "file:" not in page
    assert not re.search(r"""\ssrc=["'](?!data:)""", page)


def test_capture_is_embedded_not_linked(run_dir):
    section = PAIR.replace("- 로그: logs\\a.txt\n", "- 캡처: a.png, big.png\n")
    flow_verify(run_dir, section=section)
    write(run_dir.task_dir(FV) / "a.png", "그림")
    (run_dir.task_dir(FV) / "big.png").write_bytes(b"x" * (visual.IMAGE_LIMIT + 1))
    p = run_script("visual", run_dir.path, FV, "--sheet")
    assert p.returncode == 0, p.output
    page = (run_dir.task_dir(FV) / "sheet.html").read_text(encoding="utf-8")
    assert 'alt="a.png" src="data:image/png;base64,' in page
    assert "file:" not in page and "캡처가 커서 뺌: big.png" in page


# ---------------------------------------------------------------- 안내

def test_question_states_what_goes_up_and_old_runs_read_none():
    doc = (ROOT / "references" / "main" / "sheet-upload.md").read_text(encoding="utf-8")
    for word in ("코드 변경", "dev 응답", "claude.ai", "비공개", "비밀값 꼴", "업무 내용은 그대로", "`없음`으로 읽는다", "손으로 쓴 페이지는 어떤 경우에도 만들지 않는다"):
        assert word in doc, word
    assert "sheet-upload.md" in (ROOT / "references" / "main" / "start.md").read_text(encoding="utf-8")
    assert "sheet-upload.md" in (ROOT / "references" / "main" / "approval.md").read_text(encoding="utf-8")
