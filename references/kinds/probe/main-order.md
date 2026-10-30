# 탐침 task: 메인 순서

읽는 때: 메인이 탐침 task(`probe`)를 다룰 때.

- **작성자 고르기**: 부모 kind로 고른다. 부모가 인프라 결정(`infra-design`)이면 `devflow-harness:infra-writer`(인스턴스 `infra-{id}`), 그 밖(`design`)이면 `devflow-harness:code-writer`(인스턴스 `code-{id}`). 머리 파일 키로 고르지 않는다.
- **명령 폴더**: 머리 파일 `flow`의 `flow.md` `dir`이 있으면 그 폴더, 없으면 원래 폴더.

순서(전이는 `task_set.py {실행 폴더} {id} …`):
1. `--status 진행` 뒤 작성자를 띄워 계획을 쓰게 한다.
2. `--status 자체검증`, 읽기 판정(계획 단계 기준).
3. `--status 승인대기 stage=실행승인`. 답을 받으면 `--status 진행 stage=실행 --record …`(실행승인의 명령을 얼린다).
4. 얼린 줄마다 `exec.py … --step 실행승인:{n}`. `[사용자 실행]` 줄은 사용자가 돌리고 결과를 `--user-result`로 적는다.
5. `stage=기록`(판정 파일이 `judge.plan.md`로 옮겨진다) 뒤 같은 작성자 종류를 인스턴스 `{줄임}-{id}-rec`로 띄워 기록을 쓰게 한다.
6. `--status 자체검증`, 읽기 판정(기록 단계 기준).
7. `screen.py`가 "알림 조건: 충족"이면 `--status 완료 stage=끝 --record "알림|…"`, 아니면 `--status 승인대기 stage=결과승인`. 답 뒤 `--status 완료 stage=끝 --record …`.
8. 거짓 가정을 고치기로 답했으면 메인이 만드는 task 표의 탐침 거짓 변경 행으로 변경 task를 만든다(`origin` = 탐침 task와 가정 번호).

- **재개**: `stage`와 `exec.md`로 어디까지 했는지 보고 이어 간다.
