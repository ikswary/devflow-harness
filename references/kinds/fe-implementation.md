# 화면 구현 task (`fe-implementation`)

화면 코드(화면 정본의 화면과 요소)를 쓴다. 화면 id가 붙은 인수 기준을 닫는 구현 행은 이 kind다. 읽기 판정은 늘 붙는다.

## 먼저 읽을 것
`${CLAUDE_PLUGIN_ROOT}/references/practices/code-task.md`(코드 task 공통), `${CLAUDE_PLUGIN_ROOT}/references/practices/code-judgment.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/implementation-practice.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/build-and-test.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/ui-spec.md`(요소 id 줄), 화면 정본 `ui\{묶음}.md`(채택 줄 포함. 없으면 설계 「화면」 절), 개요 「용어」, 설계 정본의 해당 절, 흐름 규약 파일(있으면).

판정자: `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/code-task.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/code-judgment.md`

## 하는 일
방법 문서 「코드 task 공통」의 같은 절을 따르고, 더해서:
1. 화면 정본의 요소 id를 시험 표식(웹 `data-testid`, 안드로이드 `testTag`)으로 코드에 둔다.
2. 채택 시안만 구현한다.
3. 보이는 문구는 개요 「용어」와 화면 정본 그대로 쓴다.

## 승인 화면
방법 문서 「코드 task 공통」의 같은 절을 따른다.

## 자식 목록
자식 kind: 없음

## 자식 행 계약
없음

## 자체 검증 (실행 판정 + 읽기 판정)
메인 순서와 실행 판정(빌드·관련 테스트·변이 확인)의 절차는 구현 task의 것을 함께 쓴다(실행 판정 파일은 실행 판정자 정의가 가리킨다). 읽기 판정은 늘 붙고, 방법 문서 「코드 task 공통」 「판정」의 3~5에 더해 다음을 본다.
6. 이 행이 맡은 화면의 요소 집합(다시 만드는 화면은 조작 표 요소 칸의 요소 id)과 코드의 시험 표식 집합이 같다(`grep`으로 뽑아 대조한다. 「기존 그대로」 요소는 뺀다).
7. 닫는 인수 기준의 상태(비어 있음·읽는 중·오류·입력 검사 실패·권한 없음 가운데 인수 기준이 닫는 것)마다, 그리고 다시 만드는 화면은 이 행이 닫는 조작 표 행 가운데 관찰 방법이 시험인 행마다 시험이 그 표식으로 단언한다.
8. 보이는 문구가 개요 「용어」·화면 정본과 같다.
9. 채택 줄과 다른 시안을 구현하지 않았다.

캡처 판정은 없다.

판정 기준의 문장: 방법 문서 「코드 task 공통」 「판정」의 문장 / (화면 정본이 있는 묶음의 화면 task) "화면 정본 `ui\{묶음}.md`의 그 화면 요소 집합(다시 만드는 화면은 조작 표의 요소 칸)의 요소 id가 코드에 시험 표식(안드로이드 `testTag`, 웹 `data-testid`)으로 있고, 그 화면이 닫는 인수 기준의 화면 시험이 그 표식으로 단언함"(읽기 판정이 붙을 때 판정자가 본다. 상태 다섯을 모두 시험하라는 뜻이 아니다 — 인수 기준이 닫는 것만).
