"""1.2.1: 한 장의 Markdown 변환과 mermaid 도면(설계 4.2절, md_html.py).

- 표·목록·코드·굵게를 원문 꼴대로 낸다. 표 안 코드의 `|`, 굵게 안의 코드, 목록 안의 울타리·표, 끊긴 번호 목록, 4백틱 울타리.
- 모든 글은 escape된다. 원문의 `<script>`와 `on*` 속성은 글자로 남는다. 가린 값은 변환 뒤에도 가려져 있다.
- 스크립트는 도면이 있는 장에만 고정된 둘이고, CSP는 그 파일 경로와 초기화 스크립트 해시 하나만 허용한다.
- 승인 화면 항목: 칸 제목과 번호 원 카드, 번호는 터미널과 같다. 앞 정본 줄은 지금·바뀐 뒤 두 칸이다.
"""
import base64
import hashlib
import re
from html.parser import HTMLParser

import md_html
import project_docs
import visual
from conftest import write
from test_sheet import NEW, page_of, task

FRAGMENT_TAGS = {"h3", "h4", "h5", "p", "br", "pre", "code", "strong", "span", "div", "table", "thead", "tbody", "tr", "th", "td",
                 "ul", "ol", "li", "figure", "details", "summary", "hr", "section"}
FRAGMENT_ATTRS = {"class", "start", "value", "open"}


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags, self.attrs, self.scripts, self.metas, self._in = [], [], [], [], None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs += attrs
        if tag == "script":
            self.scripts.append([dict(attrs), ""])
            self._in = self.scripts[-1]
        if tag == "meta":
            self.metas.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == "script":
            self._in = None

    def handle_data(self, data):
        if self._in is not None:
            self._in[1] += data


def rows_of(fragment):
    """[[칸 글]]: 표의 행마다 칸의 태그를 뺀 글."""
    return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[hd]>(.*?)</t[hd]>", row)] for row in re.findall(r"<tr>(.*?)</tr>", fragment)]


# ---------------------------------------------------------------- 변환기: 리뷰에서 깨지던 꼴

def test_pipe_inside_code_does_not_split_a_cell_and_rows_keep_the_head_width():
    out = md_html.to_html("| 결정 | 키 | 비고 |\n|---|---|---|\n| D-7 | `\"{R2 ETag}-w{폭}-{webp|same}\"` | 1 |\n"
                          "| D-8 | a \\| b | 2 | 남는 칸 |\n| D-9 | 적음 |")
    rows = rows_of(out)
    assert rows[0] == ["결정", "키", "비고"]
    assert rows[1] == ["D-7", '"{R2 ETag}-w{폭}-{webp|same}"', "1"]
    assert rows[2] == ["D-8", "a | b", "2 | 남는 칸"] and rows[3] == ["D-9", "적음", ""]
    assert "<code>&quot;" not in out and "<code>\"{R2 ETag}-w{폭}-{webp|same}\"</code>" in out


def test_bold_around_code_keeps_both():
    out = md_html.to_html("**[되돌릴 수 없는 단계 포함] 먼저 정해 주세요: `main` 앞감기**")
    assert out == '<p><strong><span class="tag">[되돌릴 수 없는 단계 포함]</span> 먼저 정해 주세요: <code>main</code> 앞감기</strong></p>'
    assert "**" not in md_html.to_html("| a |\n|---|\n| **바뀐 `a|b` 값** |")


def test_fence_table_and_diagram_inside_a_list_item_stay_in_the_item():
    out = md_html.to_html("- 단계\n  ```bash\n  npm run a\n  npm run b\n  ```\n- 표:\n  | a | b |\n  |---|---|\n  | 1 | 2 |\n"
                          "- 그림\n  ```mermaid\n  A-->B\n  ```\n- 다음")
    assert out.startswith("<ul><li>단계<pre>npm run a\nnpm run b</pre></li><li>표:<div class=\"table\">")
    assert rows_of(out) == [["a", "b"], ["1", "2"]]
    assert "<li>그림" + md_html.DIAGRAM_OPEN in out and "<pre>A--&gt;B</pre>" in out and out.endswith("<li>다음</li></ul>")


def test_broken_numbered_list_keeps_the_source_numbers():
    out = md_html.to_html("1. 하나\n\n문단\n\n2. 둘\n3. 셋\n\n- 글머리\n\n4. 넷\n6. 여섯")
    assert out.startswith("<ol><li>하나</li></ol><p>문단</p><ol start=\"2\"><li>둘</li><li>셋</li></ol>")
    assert out.endswith('<ol start="4"><li>넷</li><li value="6">여섯</li></ol>')


def test_long_fence_closes_only_on_a_fence_as_long():
    out = md_html.to_html("````markdown\n```mermaid\ngraph TD\n```\n뒤\n````\n끝")
    assert out == "<pre>```mermaid\ngraph TD\n```\n뒤</pre><p>끝</p>"
    assert md_html.DIAGRAM_OPEN not in out


def test_headings_keep_their_levels_and_paragraph_lines_stay_lines():
    out = md_html.to_html("# 하나\n## 둘\n### 셋\n#### 넷\n■ 마무리 리뷰\n■ 실행 지도: a\n\n문제: x\n원인: y")
    assert out == ("<h3>하나</h3><h4>둘</h4><h5>셋</h5><h5>넷</h5><p>■ 마무리 리뷰<br>■ 실행 지도: a</p>"
                   "<p>문제: x<br>원인: y</p>")


def test_diagram_has_a_note_and_open_source_until_it_is_drawn():
    out = md_html.to_html("```mermaid\nflowchart LR\n  A --> B\n```")
    assert out == (md_html.DIAGRAM_OPEN + '<p class="draw-note">' + md_html.DIAGRAM_FAILED + "</p><details open><summary>"
                   + md_html.DIAGRAM_SOURCE + "</summary><pre>flowchart LR\n  A --&gt; B</pre></details></figure>")
    assert md_html.DIAGRAM_OPEN not in md_html.to_html("```mermaid\nA\n```", mermaid=False)


# ---------------------------------------------------------------- 변환기: escape

HOSTILE = "<script>alert(1)</script><img src=x onerror=y>"


def test_hostile_text_stays_text_in_every_block():
    text = ("# 제목 {0}\n\n문단 {0} **굵게 {0}** `코드 {0}` [성질: {0}]\n\n| 칸 {0} |\n|---|\n| `{0}` {0} |\n\n- 항목 {0}\n  1. 아래 {0}\n\n"
            "```js\n{0}\n```\n\n```mermaid\nflowchart LR\n  A[\"{0}\"] --> B\n  click A \"javascript:alert(1)\"\n```\n\n"
            "    들여쓴 {0}\n\n- 선택지 (가)의 앞 정본 줄: a.md:1 | 지금: {0} | 바뀜: {0}\n").format(HOSTILE)
    out = md_html.to_html(text)
    page = Tags(out)
    assert set(page.tags) <= FRAGMENT_TAGS and {name for name, _ in page.attrs} <= FRAGMENT_ATTRS
    assert all(re.fullmatch(r"[\w -]*", value or "") for _, value in page.attrs)
    assert "<script" not in out and "<img" not in out and "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert out.count("&lt;img src=x onerror=y&gt;") >= 10


def test_pair_line_has_the_shape_project_docs_reads():
    line = "선택지 (나)의 앞 정본 줄: design\\a.md:12 | 지금: - 원천: R2다 | 바뀜: - 원천: 호스팅이다"
    pair = project_docs.PAIR_LINE.search(line)
    assert (pair.group(1), pair.group(2)) == ("- 원천: R2다", "- 원천: 호스팅이다")
    out = md_html.to_html("- " + line)
    assert '<div class="del"><span class="pair-label">지금</span> - 원천: R2다</div>' in out
    assert '<div class="add"><span class="pair-label">바뀐 뒤</span> - 원천: 호스팅이다</div>' in out
    assert '<div class="pair-head">선택지 (나)의 앞 정본 줄: design\\a.md:12</div>' in out


# ---------------------------------------------------------------- 한 장: 스크립트와 CSP

DESIGN = ("# 설계\n\n## 제안 도면\n```mermaid\nflowchart LR\n  A[\"password=hunter2 {0}\"] --> B\n```\n\n"
          "## 시험 표\n| 인수 기준 | 값 |\n|---|---|\n| AC-1 `x|y` | token: abc123secret |\n").format(HOSTILE)


def test_sheet_scripts_are_the_fixed_file_and_the_hashed_init(run_dir):
    write(run_dir.path / "design" / "list.md", DESIGN)
    task(run_dir, sections={"건드릴 파일": "- design/list.md"}, material="한 일 " + HOSTILE)
    text = page_of(run_dir)
    page = Tags(text)
    (src, _), (init, body) = page.scripts
    assert src == {"src": visual.MERMAID_SRC, "integrity": visual.MERMAID_SRI, "crossorigin": "anonymous"}
    assert re.fullmatch(r"https://cdnjs\.cloudflare\.com/ajax/libs/mermaid/\d+\.\d+\.\d+/mermaid\.min\.js", visual.MERMAID_SRC)
    assert visual.MERMAID_SRI.startswith("sha512-") and len(base64.b64decode(visual.MERMAID_SRI[7:])) == 64
    assert init == {} and body == visual.DIAGRAM_INIT
    digest = "sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
    csp = [m["content"] for m in page.metas if m.get("http-equiv") == "Content-Security-Policy"]
    assert csp == [visual.SHEET_CSP]
    rules = dict((part.split()[0], part.split()[1:]) for part in csp[0].split("; "))
    assert rules["default-src"] == ["'none'"] and rules["script-src"] == [visual.MERMAID_SRC, "'{}'".format(digest)]
    assert "connect-src" not in rules and rules["img-src"] == ["data:"]
    assert "securityLevel:'strict'" in body and "data-theme" in body and "useMaxWidth:false" in body
    assert text.count("<script") == 2 and text.index("<script") > text.index("</h1>")


def test_sheet_keeps_masked_values_masked_after_conversion(run_dir):
    write(run_dir.path / "design" / "list.md", DESIGN)
    task(run_dir, sections={"건드릴 파일": "- design/list.md"}, material="| 키 | 값 |\n|---|---|\n| a | password=hunter2 |")
    text = page_of(run_dir)
    assert "hunter2" not in text and "abc123secret" not in text
    assert "<td>password=[가림]</td>" in text and "password=[가림]" in text.split(md_html.DIAGRAM_OPEN)[1]
    assert "<script>alert(1)" not in text and "&lt;script&gt;alert(1)" in text


def test_sheet_without_a_diagram_has_no_script(run_dir):
    write(run_dir.path / "design" / "list.md", "## 시험 표\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```text\nflowchart\n```\n")
    task(run_dir, sections={"건드릴 파일": "- design/list.md"}, material="한 일")
    text = page_of(run_dir)
    assert "<script" not in text and md_html.DIAGRAM_OPEN not in text and "<td>1</td><td>2</td>" in text


# ---------------------------------------------------------------- 한 장: 요구사항 상세

SPEC = ("# 목록\n\n## 기능 요구사항\n| 번호 | 요구 | 정책 |\n|---|---|---|\n| FR-1 | 목록을 `a|b`로 본다 | P-1 |\n\n"
        "## 인수 기준\n| 번호 | 기준 | 표지 |\n|---|---|---|\n| AC-1 | FR-1: 빈 목록이면 안내 | [담당이 채움] |\n| AC-2 | FR-1: 정렬 | 없음 |\n")


def test_req_detail_sheet_shows_marked_rows_and_trace_as_tables(run_dir):
    write(run_dir.path / "spec" / "list.md", SPEC)
    task(run_dir, kind="req-detail", sections={"건드릴 파일": "- spec/list.md"})
    text = page_of(run_dir)
    head = text.split("<details>")[0]
    frs = head.split("<h3>기능 요구사항 1개</h3>")[1].split("<h3>")[0]
    assert rows_of(frs) == [["번호", "요구", "정책"], ["FR-1", "목록을 a|b로 본다", "P-1"]]
    marked = head.split("<h3>표지가 있는 인수 기준 1개</h3>")[1]
    assert rows_of(marked) == [["번호", "기준", "표지"], ["AC-1", "FR-1: 빈 목록이면 안내", "[담당이 채움]"]]
    trace = text.split("<summary>번호 추적표</summary>")[1].split("</details>")[0]
    assert rows_of(trace) == [["정책", "FR", "AC"], ["P-1", "FR-1", "AC-1, AC-2"]]
    assert "| FR-1 |" not in head


# ---------------------------------------------------------------- 한 장: 승인 화면 항목

def test_item_cards_have_cell_titles_numbers_and_nested_blocks(run_dir):
    decide = ("- 원천을 정해 주십시오\n  - 지금 상태: R2\n  - 선택지 (나)의 앞 정본 줄: design\\a.md:3 | 지금: 원천은 R2 | 바뀜: 원천은 호스팅\n"
              "  | 안 | 효과 |\n  |---|---|\n  | (가) | 그대로 |\n  | (나) | `FTP` |")
    task(run_dir, material="한 일", decide=decide, notify="- 알림 하나\n- 알림 둘", unverified="- [탐침] 원천 (나)에서는 멈춤")
    text = page_of(run_dir)
    part = text.split("<h2>{}</h2>".format(visual.HEAD_ITEMS_TITLE))[1]
    numbers = re.findall(r'<span class="no">(\d+)</span>', part)
    assert numbers == [str(n) for n in range(1, len(numbers) + 1)] and len(numbers) >= 4
    asked = re.search(r'<section class="cell ask"><h3>정해 주실 것 \(\d+\)</h3>(.*?)</section>', part).group(1)
    no = re.search(r'<span class="no">(\d+)</span><div class="text"><p>원천을 정해', asked).group(1)
    assert visual.HEAD_ITEMS_EXAMPLE.format(no, "가") in part.split("<section")[0]
    assert "<li>지금 상태: R2</li>" in asked and '<div class="pair">' in asked
    assert rows_of(asked) == [["안", "효과"], ["(가)", "그대로"], ["(나)", "FTP"]]
    assert '<section class="cell"><h3>알릴 것 (2)</h3>' in part and '<span class="tag">[탐침]</span>' in part


def test_item_lead_has_no_example_without_choices(run_dir):
    task(run_dir, material="한 일", notify="- 알림 하나", unverified="- 원천 (나)에서는 멈춤")
    text = page_of(run_dir)
    assert visual.HEAD_ITEMS_LEAD + visual.HEAD_ITEMS_PLAIN in text.replace("<code>[n]</code>", "`[n]`")
    assert "처럼 이 번호로" not in text


def test_deep_nesting_falls_back_to_escaped_pre():
    """목록 표시를 수백 개 이은 줄은 재귀 한도를 넘는다. 예외 대신 escape한 원문을 낸다(변경분 리뷰 C-01)."""
    text = "- " * 2000 + "<b>x</b>"
    out = md_html.to_html(text)
    assert out.startswith("<pre>") and "&lt;b&gt;" in out and "<b>" not in out
