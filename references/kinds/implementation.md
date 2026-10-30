# 구현 task (`implementation`), 수정 task (`fix`)

머리 파일이 정한 범위의 코드와 테스트를 쓴다. 검증 지적을 고치는 수정 task와 사용자 답으로 코드를 고치는 수정 task(`origin: 사용자 …`)도 이 정의를 따른다. 옛 실행의 코드를 고치는 `change`도 이 정의로 한다.

## 먼저 읽을 것
`${CLAUDE_PLUGIN_ROOT}/references/practices/implementation-practice.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/build-and-test.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/code-task.md`(코드 task 공통), 설계 정본의 해당 절, 흐름 규약 파일(있으면). 수정 task면 경우 파일 `references/kinds/implementation/fix.md`도.

판정자: `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/code-task.md`

## 하는 일
방법 문서 「코드 task 공통」의 같은 절을 따른다.

## 승인 화면
방법 문서 「코드 task 공통」의 같은 절을 따른다.

## 자식 목록
자식 kind: 없음

## 자식 행 계약
없음

## 자체 검증 (실행 판정 + 읽기 판정: 조건)
메인이 하는 순서(1 기계 대조, 3 읽기 판정이 붙는 조건)는 `references/kinds/implementation/main-order.md`, 2 실행 판정(독립 최종 검사인 빌드·관련 테스트·변이 확인)의 절차는 `references/kinds/implementation/run-check.md`에 있다.
3~5와 판정 기준의 문장은 방법 문서 「코드 task 공통」 「판정」.
