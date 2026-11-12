"""1.2.0 A2: 화면 머리 세 줄, 리뷰 자료, 브라우저 한 장(설계 4.2절, 7.6절).

- 머리 세 줄은 1.2.0부터 시작한 task의 묻는 화면에만 나오고, 값은 등록표와 칸에서 스크립트가 낸다.
- 한 장은 고정 틀이다. 값을 가린 뒤 이스케이프한다. 스크립트는 mermaid 도면이 있을 때만 고정된 둘이다(test_sheet_render.py).
- 만들지 못해도 승인을 막지 않는다.
"""
import os
import re
import shutil
import time
from html.parser import HTMLParser

import pytest

import kinds
import visual
from conftest import run_script, write
from test_review_contract import code_task

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
# Markdown 변환(md_html)이 내는 태그와 속성까지. script·src는 없다: 도면이 없는 장에는 스크립트를 싣지 않는다
ALLOWED_TAGS = {"html", "head", "meta", "title", "style", "body", "h1", "h2", "h3", "h4", "h5", "p", "pre", "div", "details", "summary", "iframe",
                "table", "thead", "tbody", "tr", "th", "td", "ul", "ol", "li", "code", "strong", "span", "section", "br", "hr", "figure"}
ALLOWED_ATTRS = {"lang", "charset", "name", "http-equiv", "content", "class", "sandbox", "srcdoc", "start", "value", "open"}
HOSTILE = '<script>alert(1)</script><img src=x onerror=y>'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags, self.attrs, self.metas, self.frames = [], [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs += [name for name, _ in attrs]
        if tag == "meta":
            self.metas.append(dict(attrs))
        if tag == "iframe":
            self.frames.append(dict(attrs))


def result(material="", decide="- 없음", notify="- 없음", unverified="- 없음", extra=""):
    block = "### 리뷰 자료\n{}\n".format(material) if material else ""
    return ("# 결과\n\n## 승인 화면\n{}### 정해 주실 것\n{}\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n{}\n"
            "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n{}\n### 건수만\n- 없음\n{}").format(block, decide, notify, unverified, extra)


def task(run_dir, kind="design", meta=NEW, sections=None, title="시험 task", status="승인대기", **cells):
    run_dir.task("T001", title, sections, kind=kind, block="설계", status=status, **meta)
    run_dir.result("T001", result(**cells))


def sheet_of(run_dir):
    p = run_script("visual", run_dir.path, "T001", "--sheet")
    assert p.returncode == 0, p.output
    return p.stdout, run_dir.task_dir("T001") / "sheet.html"


def page_of(run_dir):
    return sheet_of(run_dir)[1].read_text(encoding="utf-8")


def screen_of(run_dir):
    return run_script("screen", run_dir.path, "T001").stdout


def child_row(title, kind="implementation", option=""):
    extra = "- option: {}\n".format(option) if option else ""
    return ("### 자식: {0}\n- kind: {1}\n- flow: a\n- depends_on: \n- difficulty: 일반\n{2}- 한 줄: 한다\n\n"
            "#### 범위\n- 범위\n#### 판정 기준\n1. 기준\n#### 건드릴 파일\n- src/a.ts\n\n").format(title, kind, extra)


# ---------------------------------------------------------------- 머리 세 줄

def test_stage_heads_are_exactly_these():
    assert kinds.STAGE_HEAD == {
        ("probe", "실행승인"): ("이 명령을 실행해도 되는가, 결과가 무엇을 가르는가", "승인한 명령을 실행합니다"),
        ("probe", "결과승인"): ("이 결과로 결정을 가르는 것을 받아들이는가", ""),
        ("merge", "실행승인"): ("이 명령으로 합쳐도 되는가", "승인한 합치기 명령을 실행합니다"),
        ("merge", "결과승인"): ("충돌을 맞게 풀었는가", "병합 커밋을 끝냅니다"),
        ("wrap-up", "실행승인"): ("이 상태로 넣어도 되는가", "내보내기 명령을 실행합니다"),
        ("wrap-up", "결과승인"): ("넣은 결과를 받아들이는가", ""),
        ("deploy-exec", "직전확인"): ("되돌릴 수 없는 단계까지 이 배포를 시작해도 되는가", "배포 명령을 실행합니다"),
        ("deploy-exec", "결과승인"): ("실패면 어떻게 하는가, 결과를 유지하는가", "답대로 유지하거나 되돌립니다"),
        ("deploy-exec", "넣기승인"): ("배포 기록 문서를 넣어도 되는가", "문서 넣기 명령을 실행합니다"),
    }


def test_every_kind_says_what_is_decided():
    assert set(kinds.KINDS) - set(kinds.DECIDES) - kinds.STAGE_KINDS == {"change"}
    asked = {(k, s) for k in kinds.STAGE_KINDS for s in kinds.stages_of(k) + kinds.OLD_STAGES.get(k, ()) if s in kinds.ASK_STAGES}
    assert asked == set(kinds.STAGE_HEAD)


@pytest.mark.parametrize("kind,sentence", [
    ("question", "이 선택지 가운데 무엇인가"), ("req-overview", "이 범위와 묶음 나눔이 원하는 일의 경계인가"),
    ("brief", "사람이 겪는 순서와 규칙이 원하는 제품인가"), ("req-detail", "이 문장대로 만들고 시험해도 되는가, 담당 값을 받아들이는가"),
    ("ui-design", "이 모양과 조작으로 쓰게 해도 되는가, 어느 시안인가"), ("design", "이 접근으로 구현을 시작해도 되는가"),
    ("be-implementation", "이 구조 판단의 코드를 받아들이는가"), ("fe-implementation", "이 구조 판단의 코드를 받아들이는가, 화면이 맞는가"),
    ("fix", "지적대로 고쳤는가"), ("flow-verify", "의도대로 동작하는가, 남은 위험을 받아들이는가"),
    ("reverify", "고친 것을 받아들이는가"), ("full-verify", "남은 위험을 받아들이는가"), ("deploy-plan", "이 배포를 해도 되는가"),
])
def test_decides_sentences_match_the_design_table(kind, sentence):
    assert kinds.DECIDES[kind] == sentence


def test_head_lines_on_new_task(run_dir):
    task(run_dir, decide="- 저장 위치 [성질: 비용]", notify="- 이름을 바꿨다")
    out = screen_of(run_dir).splitlines()
    assert out[1] == "정하는 것: 이 접근으로 구현을 시작해도 되는가"
    assert out[2].startswith("볼 곳: 정해 주실 것 ") and "성질 붙은 항목 1" in out[2]
    assert out[3] == "승인하면: 이 task가 닫힙니다"


def test_marked_items_count_own_lines_of_three_cells(run_dir):
    task(run_dir, notify="- [T009] 옮겨 온 줄 [성질: 비용]\n- 자기 줄 [성질: 범위]", unverified="- 받아들인 것 [성질: 위험]")
    assert "성질 붙은 항목 2" in screen_of(run_dir)


def test_head_lines_say_who_starts_next(run_dir):
    task(run_dir)
    run_dir.task("T002", "다음", depends_on=["T001"])
    assert "승인하면: 기다리던 task 1개가 시작할 수 있습니다(T002)" in screen_of(run_dir)


def test_head_lines_do_not_promise_a_task_waiting_on_others(run_dir):
    task(run_dir)
    run_dir.task("T003", "진행 중", status="진행")
    run_dir.task("T002", "다음", depends_on=["T001", "T003"])
    out = screen_of(run_dir)
    assert "시작할 수 있습니다" not in out and "1개는 아직 다른 task를 기다립니다(T002)" in out


def test_head_lines_count_children_by_kind(run_dir):
    task(run_dir, extra="\n## 자식 목록\n나눈 기준: 화면\n\n" + child_row("목록 [draft]") + child_row("상세") + child_row("[백로그] 나중"))
    out = screen_of(run_dir)
    assert "승인하면: task 2개가 생깁니다(implementation 2), 백로그로 1개를 남깁니다" in out
    assert "draft" not in out.split("승인하면:")[1].split("\n")[0]


def test_head_lines_say_children_depend_on_the_option(run_dir):
    task(run_dir, extra="\n## 자식 목록\n나눈 기준: 안\n\n" + child_row("가안", option="가") + child_row("나안", option="나"))
    assert "승인하면: 고른 안에 따라 task가 생깁니다(안 가 1개, 안 나 1개)" in screen_of(run_dir)


@pytest.mark.parametrize("path,sentence", [
    ("spec/a.md", "이 변경이 내 답을 맞게 옮겼는가"), ("ui/list.md", "이 모양과 조작으로 쓰게 해도 되는가, 어느 시안인가"),
    ("design/infra.md", "이 자원 결정으로 가도 되는가"), ("design/a.md", "이 접근으로 구현을 시작해도 되는가"),
])
def test_change_head_follows_the_canon(run_dir, path, sentence):
    task(run_dir, kind="change", sections={"건드릴 파일": "- " + path}, decide="- 고를 것")
    assert "정하는 것: " + sentence in screen_of(run_dir)


@pytest.mark.parametrize("kind,stage,decides,after", [
    ("wrap-up", "실행승인", "이 상태로 넣어도 되는가", "내보내기 명령을 실행합니다"),
    ("probe", "실행승인", "이 명령을 실행해도 되는가, 결과가 무엇을 가르는가", "승인한 명령을 실행합니다"),
    ("probe", "결과승인", "이 결과로 결정을 가르는 것을 받아들이는가", "이 task가 닫힙니다"),
    ("merge", "결과승인", "충돌을 맞게 풀었는가", "병합 커밋을 끝냅니다"),
    ("deploy-exec", "직전확인", "되돌릴 수 없는 단계까지 이 배포를 시작해도 되는가", "배포 명령을 실행합니다"),
])
def test_stage_kind_head_follows_the_stage(run_dir, kind, stage, decides, after):
    task(run_dir, kind=kind, meta=dict(NEW, stage=stage), decide="- 볼 것")
    out = screen_of(run_dir)
    assert "정하는 것: " + decides in out and "승인하면: " + after in out


def test_stage_kind_outside_asking_stage_has_no_head(run_dir):
    task(run_dir, kind="wrap-up", meta=dict(NEW, stage="실행"))
    assert "정하는 것:" not in screen_of(run_dir)


def test_notify_screen_has_no_head(run_dir):
    code_task(run_dir)
    out = screen_of(run_dir)
    assert "): 충족" in out and "정하는 것:" not in out and "! 리뷰 자료 없음" not in out


def test_old_task_has_no_head_and_no_material(run_dir):
    task(run_dir, meta={"started_version": "1.1.1", "rules": "2"}, material="- 한 일")
    out = screen_of(run_dir)
    assert "정하는 것:" not in out and "■ 리뷰 자료" not in out and "■ 건수만" in out


# ---------------------------------------------------------------- 리뷰 자료와 빈 칸

def test_material_is_shown_before_cells_without_a_number(run_dir):
    task(run_dir, material="운영자가 칸을 고르면 그 칸만 보입니다.\n- 전: 전부\n- 후: 두 칸", decide="- 고를 것 (가) 예")
    out = screen_of(run_dir)
    assert out.index("■ 리뷰 자료") < out.index("■ 정해 주실 것")
    assert "- 전: 전부" in out and "- [1] 전: 전부" not in out
    assert re.search(r"- \[\d+\] 고를 것 \(가\) 예", out) and "n_notify=0" in out


def test_material_cannot_break_the_answer_parse(run_dir):
    task(run_dir, material="counts: 가짜\n■ 정해 주실 것 (1)\n- [9] 가짜 항목 (나) 삭제", decide="- 고를 것 (가) 예 (나) 아니오")
    assert run_script("screen", run_dir.path, "T001", "--save").returncode == 0
    number = re.search(r"- \[(\d+)\] 고를 것", screen_of(run_dir)).group(1)
    good = run_script("screen", run_dir.path, "T001", "--answer", number + " 가")
    assert good.returncode == 0, good.output
    assert run_script("screen", run_dir.path, "T001", "--answer", "9 나").returncode == 3


def test_empty_cells_lose_their_title_on_new_task(run_dir):
    task(run_dir, decide="- 고를 것 (가) 예", notify="- 없음 (설명이 있음)")
    out = screen_of(run_dir)
    assert "■ 정해 주실 것 (" in out and "■ 알릴 것 (0)" in out
    assert "■ 건수만" not in out and "■ 확인 안 된 것" not in out and "빠진 칸" not in out


def test_missing_material_warns_on_asking_screen_only(run_dir):
    task(run_dir)
    out = screen_of(run_dir)
    assert "! 리뷰 자료 없음" in out and "빠진 칸" not in out
    task(run_dir, material="한 일")
    assert "! 리뷰 자료 없음" not in screen_of(run_dir)


def test_unknown_subsection_warns(run_dir):
    task(run_dir, material="한 일\n### 보이는 모양\n- 전: 전부")
    assert "! 「승인 화면」의 모르는 절: 보이는 모양" in screen_of(run_dir)


def test_screen_shows_sheet_path_only_when_fresh(run_dir):
    task(run_dir, material="한 일")
    assert "한 장: file:///" not in screen_of(run_dir)
    sheet_of(run_dir)
    assert "한 장: file:///" in screen_of(run_dir).split("■ 리뷰 자료")[0]
    result_md = run_dir.task_dir("T001") / "result.md"
    os.utime(result_md, (time.time() + 60, time.time() + 60))
    assert "한 장: file:///" not in screen_of(run_dir)


# ---------------------------------------------------------------- 한 장: 틀과 이스케이프

def test_sheet_csp_really_applies_and_only_fixed_tags_appear(run_dir):
    write(run_dir.path / "design" / "list.md", "# 설계\n\n| 규칙 | 값 |\n|---|---|\n| 정렬 | 이름 {0} |\n\n본문 앞 {0}\n".format(HOSTILE))
    write(run_dir.path / "ui" / "wireframes" / "a&b.html", '<div data-el="{}"></div>'.format('&lt;x&gt;<b>'))
    task(run_dir, kind="change", title="제목 " + HOSTILE, material="자료 " + HOSTILE, sections={"건드릴 파일": "- design/list.md\n- ui/wireframes/a&b.html"})
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "# 설계\n\n| 규칙 | 값 |\n|---|---|\n| 정렬 | 최근 {0} |\n\n본문 뒤 {0}\n".format(HOSTILE))
    write(run_dir.task_dir("T001") / "revised" / "design" / "new.md", "새 문서 {}\n".format(HOSTILE))
    text = page_of(run_dir)
    page = Page(text)
    assert set(page.tags) <= ALLOWED_TAGS and set(page.attrs) <= ALLOWED_ATTRS
    csp = [m for m in page.metas if m.get("http-equiv") == "Content-Security-Policy"]
    assert [m["content"] for m in csp] == [visual.SHEET_CSP]
    assert visual.SHEET_CSP.startswith("default-src 'none'")
    assert text.index("Content-Security-Policy") < text.index("<title>")
    assert "a&amp;b.html" in text
    assert "<script" not in text and "&lt;script&gt;" in text


def test_sheet_order_is_explanation_shape_rules_lines(run_dir):
    write(run_dir.path / "design" / "list.md", "| 규칙 | 값 |\n|---|---|\n| 정렬 | 이름 |\n")
    write(run_dir.path / "ui" / "wireframes" / "list.html", '<div data-el="a"></div>')
    task(run_dir, kind="change", material="한 일", sections={"건드릴 파일": "- design/list.md\n- ui/wireframes/list.html"})
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "| 규칙 | 값 |\n|---|---|\n| 정렬 | 최근 |\n")
    page = page_of(run_dir)
    assert page.index("이 task가 한 일") < page.index("모양: ") < page.index("바뀐 규칙과 요구사항") < page.index("줄 단위 변경분")


# ---------------------------------------------------------------- 한 장: 가림

@pytest.mark.parametrize("line,hidden", [
    ("API_KEY=abc123", "abc123"), ("SECRET_KEY=abc123", "abc123"), ("password: hunter2", "hunter2"), ('"password": "hunter2"', "hunter2"),
    ("Authorization: Bearer abc123def456", "abc123def456"), ('password = "two words"', "words"), ("비밀번호: mypass1", "mypass1"),
    ("postgres://u:pw1234@db:5432/app", "pw1234"), ("키 AKIAABCDEFGHIJKLMNOP", "AKIAABCDEFGHIJKLMNOP"),
    ("토큰 ghp_abcdefghij012345", "ghp_abcdefghij012345"), ("github_pat_abcdefghij012345", "abcdefghij012345"), ("glpat-abcdefghij012345", "abcdefghij012345"),
    ("고객 010-1234-5678", "010-1234-5678"), ("고객 +82 10-1234-5678", "1234-5678"), ("메일 a.b+c@example.com", "a.b+c@example.com"),
])
def test_sheet_masks_secrets_and_personal_values(run_dir, line, hidden):
    task(run_dir, material=line)
    out, path = sheet_of(run_dir)
    assert hidden not in path.read_text(encoding="utf-8")
    assert "1줄 가림" in out and "<p>1줄을 가렸습니다.</p>" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("line", [
    "| password: string | 필수 |", "Authorization: 헤더가 없으면 거부한다", "next@14.2.1", "git@github.com:o/r.git", "판 1.2.0-dev.1",
    "주문 01012345678901", "token: {발급 값}",
])
def test_sheet_keeps_what_only_looks_like_a_secret(run_dir, line):
    task(run_dir, material=line)
    out, path = sheet_of(run_dir)
    assert "가림" not in out
    assert visual.html.escape(line) in path.read_text(encoding="utf-8")


def test_sheet_masks_private_key_block(run_dir):
    task(run_dir, material="앞\n-----BEGIN RSA PRIVATE KEY-----\nabcSECRETbody\n-----END RSA PRIVATE KEY-----\n뒤")
    page = page_of(run_dir)
    assert "abcSECRETbody" not in page and "PRIVATE KEY" not in page and "앞" in page and "뒤" in page


def test_sheet_masks_every_place_and_counts_a_line_once(run_dir):
    write(run_dir.path / "design" / "list.md", "| 키 | 값 |\n|---|---|\n| API_KEY=oldvalue | 쓴다 |\n")
    write(run_dir.path / "ui" / "wireframes" / "list.html", '<p>010-1111-2222</p><div data-el="me@example.com"></div>')
    task(run_dir, kind="change", title="제목 password=titlevalue", sections={"건드릴 파일": "- design/list.md\n- ui/wireframes/list.html"})
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "| 키 | 값 |\n|---|---|\n| API_KEY=newvalue | 쓴다 |\n")
    out, path = sheet_of(run_dir)
    page = path.read_text(encoding="utf-8")
    for leaked in ("oldvalue", "newvalue", "titlevalue", "010-1111-2222", "me@example.com"):
        assert leaked not in page, leaked
    # 값이 바뀐 줄은 앞뒤를 따로 가려도 사라지지 않는다: 표와 변경분에 한 번씩 나와도 줄 수는 원문 기준이다
    assert page.count('<div class="del">| API_KEY=[가림] | 쓴다 |</div>') == 1
    assert page.count('<div class="add">| API_KEY=[가림] | 쓴다 |</div>') == 1
    assert '<div class="del">-| API_KEY=[가림] | 쓴다 |</div>' in page
    assert "5줄 가림" in out   # 제목, 옛 표 줄, 새 표 줄, 와이어프레임 한 줄, 요소 이름


# ---------------------------------------------------------------- 한 장: 고를 문서와 와이어프레임

def test_sheet_without_material_says_so_and_writes_nothing(run_dir):
    task(run_dir)
    out, path = sheet_of(run_dir)
    assert out.startswith("한 장 없음:") and str(run_dir.task_dir("T001")) in out
    assert not path.exists()


def test_sheet_removes_the_old_page_when_nothing_is_left(run_dir):
    task(run_dir, material="한 일")
    assert sheet_of(run_dir)[1].exists()
    task(run_dir)
    assert not sheet_of(run_dir)[1].exists()


def test_sheet_failure_does_not_block(run_dir, monkeypatch, capsys):
    task(run_dir, material="한 일")

    def broken(*a):
        raise OSError("디스크 없음")
    monkeypatch.setattr(visual, "sheet_html", broken)
    assert visual.main(["visual.py", str(run_dir.path), "T001", "--sheet"]) == 0
    assert "한 장 없음: 디스크 없음" in capsys.readouterr().out


def test_sheet_of_broken_encoding_does_not_block(run_dir):
    (run_dir.path / "design").mkdir(parents=True, exist_ok=True)
    (run_dir.path / "design" / "list.md").write_bytes("한글".encode("cp949"))
    task(run_dir, sections={"건드릴 파일": "- design/list.md"})
    out = sheet_of(run_dir)[0]
    assert out.startswith("한 장 없음:") and "list.md" in out


def test_sheet_of_broken_task_file_does_not_block(run_dir):
    task(run_dir, material="한 일")
    (run_dir.task_dir("T001") / "task.md").write_bytes("---\ntitle: 한글\n---\n".encode("cp949"))
    assert sheet_of(run_dir)[0].startswith("한 장 없음:")


def test_sheet_of_change_shows_table_rows_and_folded_lines(run_dir):
    write(run_dir.path / "design" / "list.md", "# 설계\n\n| 규칙 | 값 |\n|---|---|\n| 정렬 | 이름 |\n\n본문 앞\n")
    task(run_dir, kind="change", sections={"건드릴 파일": "- design/list.md"})
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "# 설계\n\n| 규칙 | 값 |\n|---|---|\n| 정렬 | 최근 |\n\n본문 뒤\n")
    page = page_of(run_dir)
    assert page.index("| 정렬 | 이름 |") < page.index("<details>")
    assert '<div class="add">| 정렬 | 최근 |</div>' in page
    assert "줄 단위 변경분" in page and '<div class="add">+본문 뒤</div>' in page


def test_sheet_of_new_document_folds_it(run_dir):
    write(run_dir.path / "design" / "list.md", "# 설계\n본문\n")
    task(run_dir, sections={"건드릴 파일": "- design/list.md"})
    assert "<details><summary>새 문서 전체" in page_of(run_dir)


def test_sheet_skips_documents_the_task_only_reads(run_dir):
    write(run_dir.path / "design" / "other.md", "남이 쓴 설계 본문\n")
    task(run_dir, kind="implementation", material="한 일", sections={"정본의 절": "- design/other.md"})
    assert "남이 쓴 설계 본문" not in page_of(run_dir)


def test_sheet_never_reads_outside_the_run_folder(run_dir):
    write(run_dir.path.parent / "secret.md", "밖의 문서 본문\n")
    write(run_dir.path.parent / "secret.html", '<p>밖의 와이어프레임</p>')
    task(run_dir, material="한 일", sections={"건드릴 파일": "- spec/../../secret.md\n- ui/wireframes/../../../secret.html"})
    page = page_of(run_dir)
    assert "밖의" not in page


def test_sheet_sandboxes_wireframes_in_srcdoc_and_lists_elements(run_dir):
    write(run_dir.path / "ui" / "wireframes" / "list.html", '<div data-el="a"></div><div data-el="b"></div><script>x</script>')
    task(run_dir, sections={"건드릴 파일": "- ui/wireframes/list.html"})
    text = page_of(run_dir)
    frames = Page(text).frames
    assert len(frames) == 1 and "sandbox" in frames[0] and not frames[0]["sandbox"] and "<script>x</script>" in frames[0]["srcdoc"]
    assert "요소: a, b" in text and "<script" not in text


def test_sheet_of_changed_wireframe_shows_before_and_after(run_dir):
    write(run_dir.path / "ui" / "wireframes" / "list.html", '<p>옛 모양</p><div data-el="old"></div><div data-el="both"></div>')
    task(run_dir, kind="change", sections={"건드릴 파일": "- ui/wireframes/list.html"})
    write(run_dir.task_dir("T001") / "revised" / "ui" / "wireframes" / "list.html", '<p>새 모양</p><div data-el="new"></div><div data-el="both"></div>')
    text = page_of(run_dir)
    frames = Page(text).frames
    assert [("옛 모양" in f["srcdoc"], "새 모양" in f["srcdoc"]) for f in frames] == [(True, False), (False, True)]
    assert "요소 더함: new / 요소 뺌: old" in text


def test_sheet_of_new_wireframe_in_change_is_shown(run_dir):
    task(run_dir, kind="change", sections={"건드릴 파일": "- ui/wireframes/new.html"})
    write(run_dir.task_dir("T001") / "revised" / "ui" / "wireframes" / "new.html", '<p>새 화면</p>')
    frames = Page(page_of(run_dir)).frames
    assert len(frames) == 1 and "새 화면" in frames[0]["srcdoc"]


def test_sheet_of_empty_revised_folder_falls_back_to_the_document(run_dir):
    write(run_dir.path / "design" / "list.md", "본문\n")
    task(run_dir, sections={"건드릴 파일": "- design/list.md"})
    (run_dir.task_dir("T001") / "revised").mkdir()
    assert "새 문서 전체" in page_of(run_dir)


def test_sheet_stays_fast_on_big_inputs(run_dir):
    write(run_dir.path / "design" / "list.md", "".join("옛 줄 {}\n".format(i) for i in range(4000)))
    task(run_dir, kind="change", material="a" * 160000, sections={"건드릴 파일": "- design/list.md"})
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "".join("새 줄 {}\n".format(i) for i in range(4000)))
    start = time.time()
    assert "한 장: " in sheet_of(run_dir)[0]
    assert time.time() - start < 20


def test_sheet_leaves_out_too_big_documents(run_dir, monkeypatch, capsys):
    write(run_dir.path / "design" / "list.md", "x" * 100 + "\n")
    task(run_dir, sections={"건드릴 파일": "- design/list.md"})
    monkeypatch.setattr(visual, "DOC_LIMIT", 10)
    assert visual.main(["visual.py", str(run_dir.path), "T001", "--sheet"]) == 0
    page = (run_dir.task_dir("T001") / "sheet.html").read_text(encoding="utf-8")
    assert "크기 때문에 뺌" in page and "x" * 100 not in page


def test_sheet_uri_is_encoded(run_dir, capsys, tmp_path):
    other = tmp_path / "run dir #1"
    other.mkdir()
    task(run_dir, material="한 일")
    shutil.copytree(run_dir.path, other / "run")
    assert visual.main(["visual.py", str(other / "run"), "T001", "--sheet"]) == 0
    uri = capsys.readouterr().out.split("한 장: ")[1].strip()
    assert "run%20dir%20%231" in uri and " " not in uri


def test_sheet_leaves_out_too_big_wireframes(run_dir, monkeypatch):
    write(run_dir.path / "ui" / "wireframes" / "list.html", "<p>" + "x" * 100 + "</p>")
    task(run_dir, sections={"건드릴 파일": "- ui/wireframes/list.html"})
    monkeypatch.setattr(visual, "DOC_LIMIT", 10)
    assert visual.main(["visual.py", str(run_dir.path), "T001", "--sheet"]) == 0
    page = (run_dir.task_dir("T001") / "sheet.html").read_text(encoding="utf-8")
    assert "크기 때문에 뺌" in page and "<iframe" not in page


def test_size_limit_looks_at_the_bigger_version(run_dir, monkeypatch):
    write(run_dir.path / "design" / "list.md", "가" * 80 + "\n")
    task(run_dir, kind="change", sections={"건드릴 파일": "- design/list.md"})
    write(run_dir.task_dir("T001") / "revised" / "design" / "list.md", "나" * 80 + "\n")
    monkeypatch.setattr(visual, "DOC_LIMIT", 100)
    assert visual.main(["visual.py", str(run_dir.path), "T001", "--sheet"]) == 0
    assert "크기 때문에 뺌" not in (run_dir.task_dir("T001") / "sheet.html").read_text(encoding="utf-8")


def test_plain_visual_output_is_unchanged(run_dir):
    task(run_dir)
    assert run_script("visual", run_dir.path, "T001").stdout.startswith("■ 보는 자료")
