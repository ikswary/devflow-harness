# 서버 구현 task (`be-implementation`)

서버 코드(경로·요청·응답·저장·오류 코드)를 쓴다. 마이그레이션·배포 설정은 이 kind가 아니라 구현 task 행 몫이다(막지 않는다. 인프라 경로를 건드리면 알림으로 지나가지 않는다).

## 먼저 읽을 것
`${CLAUDE_PLUGIN_ROOT}/references/practices/code-task.md`(코드 task 공통), `${CLAUDE_PLUGIN_ROOT}/references/practices/implementation-practice.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/build-and-test.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`, 설계 정본 「공용 형식」과 해당 절, 흐름 규약 파일(있으면).

판정자: `${CLAUDE_PLUGIN_ROOT}/references/practices/test-rules.md`, `${CLAUDE_PLUGIN_ROOT}/references/practices/code-task.md`

## 하는 일
방법 문서 「코드 task 공통」의 같은 절을 따르고, 더해서 머리 파일 「시그니처와 결정 번호」에 `[계약]`이 있는 행은 설계 「공용 형식」의 그 항목(경로·요청·응답·오류 코드)을 그대로 쓰고 그 항목을 단언하는 계약 시험을 둔다.

## 승인 화면
방법 문서 「코드 task 공통」의 같은 절을 따른다.

## 자식 목록
자식 kind: 없음

## 자식 행 계약
없음

## 자체 검증 (실행 판정 + 읽기 판정: 조건)
메인 순서와 실행 판정(빌드·관련 테스트·변이 확인)의 절차는 구현 task의 것을 함께 쓴다(실행 판정 파일은 실행 판정자 정의가 가리킨다). 읽기 판정은 구현 task의 조건 셋에 더해 머리 파일 「시그니처와 결정 번호」에 `[계약]`이 있을 때 붙는다(`[계약]` 조건). 읽기 판정은 방법 문서 「코드 task 공통」 「판정」의 3~5에 더해 다음을 본다.
6. `[계약]` 항목마다 코드의 경로·필드·오류 코드가 설계 「공용 형식」과 같다.
7. 계약 시험이 그 항목을 단언한다.

판정 기준의 문장: 방법 문서 「코드 task 공통」 「판정」의 문장.
