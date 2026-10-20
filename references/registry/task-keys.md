## 5. 머리 파일 키와 본문 절

| 키 | 채우는 길 | 목록 |
| --- | --- | --- |
| id | kv | — |
| title | kv | — |
| kind | option | — |
| block | kv | — |
| status | option | — |
| parent | kv | — |
| depends_on | kv | 예 |
| flow | kv | — |
| difficulty | kv | — |
| closes_ac | kv | 예 |
| partial_ac | kv | 예 |
| one_line | kv | — |
| origin | script | — |
| cause_task | kv | — |
| fix_generation | script | — |
| commit | kv | — |
| running_agent | kv | — |
| waiting_user | kv | — |
| retry | option | — |
| started_version | script | — |
| rules | script | — |
| machine_check | selfcheck | — |
| done_via | script | — |
| criteria_amended | script | — |
| judge_method | kv | — |
| approval_mode | kv | — |
| n_decide | kv | — |
| n_todo | kv | — |
| n_notify | kv | — |
| n_unverified | kv | — |
| n_children | kv | — |
| split_criterion | kv | — |
| shrunk_reason | kv | — |
| awaiting_answer_apply | kv | — |
| external_progress | kv | — |
| stage | kv | — |
| exported_commit | script | — |
| partial_flow | kv | — |
| deploy_outcome | kv | — |
| deployed_commit | kv | — |
| created | script | — |
| started | script | — |
| approval_requested | script | — |
| approved | script | — |

| 순서 | 본문 절 | 채우는 쪽 |
| --- | --- | --- |
| 1 | 범위 | row |
| 2 | 판정 기준 | row, own |
| 3 | 판정 기준 정정 | own |
| 4 | 재시도 범위 | own |
| 5 | 건드릴 파일 | row |
| 6 | 시그니처와 결정 번호 | row |
| 7 | 정본의 절 | row |
| 8 | 영향받는 task와 처리 | main |
| 9 | 넘길 이상 신호 | main |
| 10 | 표 밖 전이 | own |
| 11 | 승인 기록 | own |

