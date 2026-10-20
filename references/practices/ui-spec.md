# 화면 설계서·와이어프레임 작성법

읽는 kind: `ui-design`, `change`.
UI 규약 task(`ui\rules.md`를 씀)를 쓸 때는 `references/practices/ui-spec/rules.md`의 「UI 규약」을 따른다.

화면 설계서의 목적은 "사용자가 무엇을 보고 무엇을 누르면 무엇이 되는지"를 소프트웨어 설계와 구현이 그대로 옮길 수 있게, 그리고 판정자가 파일만 보고 빠짐을 찾을 수 있게 적는 것이다. 보기 좋은지는 사람이 와이어프레임과 글자 배치도를 보고 정한다. 화면 id와 이동은 기획(`spec\brief.md` 「화면 흐름」)이 정했고 여기서 바꾸지 않는다.

## 설계서 형식 (`ui\{묶음}.md`)

```markdown
# 화면 설계: {묶음}

## 화면 목록
| 화면 id(기획) | 이름 | 목적 | 이번 변경 | 닿는 FR·AC |
|---|---|---|---|---|
| plan-board | 근무 계획 | 오늘·내일 계획을 본다 | 새로 그림 / 부분 변경 / 기존 그대로(파일:줄) | FR-P8, AC-P1 |

## 화면: {화면 id} {이름}
- 목적:
- 배치(위에서부터): {요소 id} … (좌우는 `|`로)
| 요소 id | 종류(제목/글/칸/버튼/목록/카드/대화상자/띠) | 보이는 것·문구 | 출처(용어/답/담당) | 닿는 FR·AC |
|---|---|---|---|---|
| plan-board.today | 카드 | 「오늘 근무 계획」 + 다섯 값, 없으면 「계획 없음」 | 용어 | FR-P8 |

### 상태
| 상태 | 보이는 것 | 해당 없음이면 이유 |
|---|---|---|
| 비어 있음 | 두 카드 모두 「계획 없음」 | |
| 읽는 중 | | 로컬 DB라 즉시 |
| 오류 | … | |
| 입력 검사 실패 | … | |
| 권한 없음 | … | |

### 조작
| 요소 id | 조작 | 결과 | 피드백 | 되돌리기 |
|---|---|---|---|---|
| plan-board.edit-tomorrow | 누름 | plan-edit(내일)로 이동 | — | 뒤로 |

### 시안 (둘 이상일 때만)
| 안 | 달라지는 요소 | 무엇이 다른지 한 줄 |
채택: (메인이 답을 받은 뒤 `채택: 안 (가) — {시각}`을 더한다)
```

- 요소 id는 `{화면 id}.{요소}`, 소문자·하이픈. 와이어프레임의 `data-el`과 글자까지 같다.
- 문구 출처: 개요 「용어」에 있는 대상은 그 이름 그대로(`용어`), 사용자 답(`답`), 담당이 새로 정함(`담당` — 알릴 결정).
- 상태 다섯은 화면마다 빠짐없이 적는다. 해당 없으면 이유 한 줄(판정자는 칸이 비었는지만 본다).
- 조작마다 결과가 없으면 그 요소는 왜 있는지 묻게 된다. 되돌릴 수 없는 조작(지우기, 보내기, 외부 앱 조작)은 확인 대화상자나 되돌리기를 적는다.
- **기존 화면 부분 변경**(웹 사이트의 한 구역을 고치는 변경 등): 바뀌는 화면만 절을 두고, 바뀌는 요소·상태만 적으며 나머지는 "기존 그대로(파일:줄)". 바뀌지 않는 상태 줄도 "기존 그대로"로 채운다.
- 정하지 않는 것: 구성 요소·클래스·ViewModel·저장 형식(design-doc). 요구사항에 없는 기능을 화면에 더하지 않는다(필요하면 「정해 주실 것」).

## 시안의 글자 배치도 (승인 화면 「정해 주실 것」 항목 안)

사용자는 결과 파일을 보지 못하므로 승인 화면만으로 고를 수 있어야 한다. 안마다 요소를 위에서부터 한 줄씩 쓴다. 좌우 배치는 `|`.

```
- 근무 계획 화면의 오늘·내일 카드 배치를 정해 주세요.
    (가) 위아래: [제목 근무 계획] / [오늘 카드] / [내일 카드] / [내일 계획 쓰기]
    (나) 탭: [제목 근무 계획] / [오늘 | 내일 탭] / [고른 날 카드] / [계획 쓰기]
    달라지는 것: (가)는 두 날이 한눈에, (나)는 카드가 커서 값이 잘 보임
    보는 방법: file:///{실행 폴더}/ui/wireframes/plan.html 의 data-variant="가"·"나"
    추천 (가): 폰 세로 화면에서 두 날을 함께 보는 일이 잦음(FR-P8)
```

## 와이어프레임 (`ui\wireframes\{묶음}.html`)

- 파일 하나로 브라우저에서 열린다. 외부 자원(CDN, 글꼴, 그림) 없음. 인라인 CSS만.
- 꾸밈 없는 선 그림이 기본: 회색 테두리, 검은 글자, 강조는 굵기와 테두리로. 색·글꼴은 `ui\rules.md`가 정한 것만(규약이 없으면 흑백).
- 화면마다 `<section data-screen="{화면 id}">` 하나, 요소마다 `data-el="{요소 id}"`. 상태는 같은 화면 블록을 `data-state="empty|loading|error|invalid|no-permission"`으로 더 그리고 요소 id는 같은 것을 다시 쓴다. 시안은 `data-variant="가|나"`(시안에만 있는 요소는 설계서 「시안」 표에 적는다).
- 틀 폭은 규약의 값. 틀 위에 화면 id·이름·상태·안을 글자로 적는다. 블록은 세로로 늘어놓는다.
- 실제 문구를 넣는다(lorem ipsum 금지). 긴 이름·많은 건수의 경우를 적어도 한 상태에 넣는다. 그림은 넣지 않는다(사진 자리는 테두리 상자와 「사진」 글자).
- 기존 화면 부분 변경이면 바뀌는 화면만 그리고, 바뀌지 않는 구역은 테두리 상자에 「기존 그대로」.

골격:

```html
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>화면 설계: {묶음}</title>
<style>
  body{font-family:sans-serif;color:#111;background:#fff;margin:16px}
  .screen{width:360px;border:2px solid #333;margin:0 0 32px;padding:12px}
  .label{font:12px monospace;color:#555;margin-bottom:4px}
  .el{border:1px dashed #999;margin:6px 0;padding:8px}
  .btn{display:inline-block;border:1px solid #333;padding:6px 12px}
</style></head><body>
<div class="label">plan-board 근무 계획 (기본, 안 가)</div>
<section class="screen" data-screen="plan-board" data-variant="가">
  <div class="el" data-el="plan-board.title">근무 계획</div>
  <div class="el" data-el="plan-board.today">오늘 근무 계획 … / 계획 없음</div>
  <div class="el btn" data-el="plan-board.edit-tomorrow">내일 계획 쓰기</div>
</section>
<div class="label">plan-board 근무 계획 (비어 있음)</div>
<section class="screen" data-screen="plan-board" data-state="empty">…</section>
</body></html>
```

## 판정자가 보는 것 (작성자도 미리 확인한다)
- 설계서의 화면 id·요소 id 집합 == 와이어프레임의 `data-screen`·`data-el` 집합(`grep -o 'data-el="[^"]*"' | sort -u`). 시안 전용 요소는 「시안」 표에.
- 화면마다 상태 다섯 줄(칸이 비지 않음), 조작마다 결과 칸, 기획 이동 표의 이동이 조작 표에 있음.
- 용어에 있는 대상을 다른 이름으로 부르지 않음. 요구사항 밖 요소 없음.
