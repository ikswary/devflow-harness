---
name: devflow-harness
description: "개발 작업을 task 단위로 흐르게 하는 새 개발 하네스(시험 운용 중). 요구사항 → 설계 → 구현 → 검증을 작은 task로 나누고, task마다 작성자가 아닌 에이전트가 자체 검증한 뒤 사람이 판단할 것만 승인받는다. 사용자가 'devflow-harness', 'devflow-harness 이어서'처럼 이름으로 부를 때만 사용한다. 이름 없이 온 기능 개발·버그 수정·'이어서' 요청은 하네스 없이 메인이 직접 처리하므로 이 스킬을 쓰지 않는다. 지금 다루는 요청은 새 기능·기능 변경, 버그 수정, 동작을 바꾸지 않는 변경, 배포만, 그리고 끝난 실행의 후속 요청('devflow-harness로 dev 배포')이다."
---

# devflow-harness 오케스트레이터

플러그인 폴더: `${CLAUDE_PLUGIN_ROOT}`. 이 문서와 이 문서가 가리키는 문서에 적힌 `references/…`·`scripts/…`·`agents/…`·`skills/…`·`docs/…` 경로는 이 폴더 기준이다.

## 원칙
메인 세션이 따르는 절차다. 설계의 이유와 결정 과정은 `references/design-summary.md`에 있고, 규칙이 답을 주지 않는 상황은 아래 원칙으로 판단한다.
1. **일은 task로 흐르고, 검증 한 번이 다루는 양은 task 하나다.** 크면 나눈다. 목표는 한 번의 검증에 올라가는 양을 작게 하는 것이고, 승인 횟수나 총 시간이 아니다.
2. **모든 task는 자체 검증을 거친다.** 통과 판정은 그 task의 작성·수정 지시·수정에 참여하지 않은 에이전트가 한다. 메인은 기계적 대조만 판정한다.
3. **부모의 결과 승인이 자식의 계획 승인을 겸한다. 고칠 것이나 더 할 것이 생기면 언제나 새 task다.** `완료`된 task는 다시 열지 않는다.
4. **파일이 진실이고 컨텍스트는 캐시다.** 결정·답·진행 위치는 대화로 전하기 전에 파일에 쓴다. 질문: "지금 이 대화가 사라져도 파일만으로 이어갈 수 있는가."
5. **컨텍스트는 예산이다.** 메인은 머리 파일과 승인 화면의 재료만 읽는다. 질문: "이 내용이 내 다음 결정에 필요한가, 파일에 두고 경로만 넘기면 되는가."
6. 기준·숫자·시점은 고정하지 않는다. `run.md` 「이번 실행의 값」에 적고 결과를 기록한다.

## 구성
- 에이전트 8의 모델은 `references/registry/agents.md`, 맡는 kind는 `references/registry/kinds.md`의 `writers`에 있고, 부르는 이름은 `devflow-harness:{에이전트}`다. code-writer는 충돌 해결도, release-writer는 배포의 기록을 쓰는 뒤 절반도 맡는다. read-judge는 읽고 대조하는 판정, run-judge는 빌드·테스트·변이 확인의 독립 실행과 배포 뒤 확인을 한다.
- 띄울 때 모델을 바꾸는 경우: design-writer는 결정이 여러 모듈·데이터 모델에 걸치면 `model: "fable"`, code-writer는 난이도 `단순`이면 `model: "sonnet"`.
- **실행 모드**: 서브에이전트 위임. task마다 수명이 짧은 에이전트를 백그라운드로 띄운다(`Agent(subagent_type, name: "{역할 줄임}-{task id}", prompt)`). 에이전트는 task 하나만 맡고 끝난다. 실행 중인 에이전트에 정정 메시지를 보내지 않는다(에이전트가 끝날 때 메인에게 보내는 반환 한 번은 이 금지 밖이다. `references/roles/agent.md` 「반환」). task 파일을 고친 뒤 새로 띄우거나, 끝난 뒤 그 산출물을 고치는 task(코드면 코드를 고치는 task)로 만든다.
- 다른 에이전트는 메인만 띄운다. 사용자에게 묻는 것도 메인만 한다(`AskUserQuestion`).

## 단계 파일
메인은 그 때에 아래 파일을 통째로 읽는다. 단계 파일끼리는 "n절"로 부르고 이 표로 찾는다.
| 절 | 파일 | 읽는 때 |
|---|---|---|
| 스크립트 | `references/main/scripts.md` | 스크립트를 돌릴 때 |
| 0. 시작과 재개(1~3·6·7) | `references/main/start.md` | 새 요청, 새 실행, 세션을 끝낼 때 |
| 0. 시작과 재개(4·5) | `references/main/resume.md` | 재개, 다시 열기 |
| 1. 루프 | `references/main/loop.md` | 늘 |
| 2. 자체 검증 | `references/main/selfcheck.md` | 작성자의 반환을 받은 뒤 판정할 때 |
| 3. 승인과 알림 | `references/main/approval.md` | 알리거나 승인을 물을 때, 답을 받은 턴 |
| 3. 승인과 알림 — 사용자 할 일 대기 | `references/main/waiting-user.md` | 「하실 일」로 넘길 때, 사용자가 했다고 답할 때 |
| 4. 자식 만들기 | `references/main/children.md` | 자식을 만들 때 |
| 5. 메인이 만드는 task | `references/main/new-task.md` | 메인이 task를 만들 때 |
| 6. 코드 폴더 | `references/main/code-folder.md` | 코드 폴더·브랜치, 기준선, 커밋, 받아오기 |
| 7. 메인이 실행하는 명령 | `references/main/commands.md` | 밖으로 나가는 명령, 오래 도는 명령, 권한 거부 |
| 8. 메인의 컨텍스트 | `references/main/context.md` | 늘 |
| 9. 실행의 끝 | `references/main/run-end.md` | 실행을 끝낼 때 |
| 오류 처리 | `references/main/errors.md` | 에이전트 실패·한도, 옛 task를 손볼 때 |
| 하네스를 고칠 때 | `references/main/maintain.md` | 하네스를 고칠 때 |
- 늘 읽는 것: 공통 계약 `references/core/contract.md`.
- 그 일을 할 때 읽는 것: 이름과 파일 형식 `references/core/formats.md`(목차)·`references/formats/`, 등록표 `references/core/registry.md`(목차)·`references/registry/`, task 종류별 정의 `references/kinds/{정의}.md`, 작성자 공통 규칙 `references/roles/writer.md`, 스크립트 `scripts/`, 새 실행의 정찰 `references/practices/project-recon.md`.
- 다루는 task의 kind에 `references/kinds/{정의}/main-order.md`가 있으면 읽는다.
