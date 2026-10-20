# 질문 task (`question`)

부모가 없는 시작 task(요구사항 개요, 원인 분석, 동작을 바꾸지 않는 변경의 설계) 앞에 온다. 그 블록의 작성 역할이 맡는다. 서브에이전트는 사용자에게 직접 묻지 못하므로, 물을 것을 결과로 내고 메인이 묻는다.

## 먼저 읽을 것
- 원인 분석 작성자(`cause-writer`): `${CLAUDE_PLUGIN_ROOT}/references/practices/root-cause-analysis.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/build-and-test.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`
- 설계 작성자(`design-writer`): `${CLAUDE_PLUGIN_ROOT}/references/practices/design-doc.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`
- 요구사항 작성자(`requirements-writer`): 없음

## 하는 일
1. 요청 원문(`run.md`)과 정찰 파일, 관련 코드를 읽는다.
2. 본 작업을 시작하기 전에 사용자가 정해야 하는 것을 뽑는다. 코드나 요청문에서 답이 나오는 것은 묻지 않고 스스로 확인한다.
3. 질문마다 선택지와 추천과 이유를 쓴다.

## 승인 화면
- 정해 주실 것: 질문(한 번에 따져 볼 수 있는 양만. 많으면 본 작업의 큰 갈래를 가르는 것부터)
- 알릴 것: 코드에서 스스로 확인해 묻지 않은 것 가운데 사용자가 알아야 하는 것
- 나머지 칸: `- 없음`

이 task의 승인이 곧 사용자의 답이다. 답은 이 task의 머리 파일 「승인 기록」에 적히고 본 task가 읽는다.

질문 task는 물을 것이 없으면 작성자가 「정해 주실 것」을 `- 없음`으로 두고 "물을 것이 없다"고 반환하며, 네 칸(정해 주실 것·하실 일·알릴 것·확인 안 된 것)이 모두 `- 없음`이고 통과 못 한 기준·판정불가가 없으면(`screen.py` "알림 조건: 충족") 알림으로 지나가고 메인이 본 task를 시작한다. [RP-09]

## 자식 목록
자식 kind: `req-overview`, `root-cause`, `design`

본 task 하나(`kind`는 `req-overview`, `root-cause`, `design` 가운데 시작 task 표가 정한 것). 범위는 요청 원문, 판정 기준은 해당 task 정의의 「자체 검증」.

## 자식 행 계약
없음

## 자체 검증 (읽기 판정)
1. 질문마다 선택지와 추천과 이유가 있다.
2. 코드나 요청문에서 답이 나오는 질문이 섞이지 않았다(판정자가 질문마다 요청문과 정찰 파일에서 답을 찾아 본다).
3. 질문 하나만 읽고 무엇을 고르는지, 고르면 무엇이 달라지는지 알 수 있다.
