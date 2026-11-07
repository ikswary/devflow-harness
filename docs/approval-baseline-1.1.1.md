# 승인 체계 1.1.1 기준값

`docs/approval-learning-proposal.md` 10절의 비교 기준이다. M0-4에서 스크립트로 다시 세어 고정했고, M0 코드 리뷰(옛 꼴 답 줄과 `결과 승인` 경로의 누락)로 세는 법을 고쳐 다시 냈다(`scripts/collect.py {실행} --baseline`, 2026-11-05). A11에서 도장의 이의에 `고침`, `판단 안 됨`을 더해 다시 냈고(2026-11-06), 실행 이름은 더하지 않았다. 실행 폴더는 읽기만 했다.

**세는 법**

- 답: `완료` task의 승인 기록 가운데 따옴표 안 글이 있고, 지점이 `알림`·`점검 확인`이 아니며, 메인 판단(`[메인]`, `(메인 보충`)이 아닌 **줄 수**. 위임으로 닫은 줄(`승인|위임 {층}`, `추천 닫음|위임 L1`)도 뺀다(옛 실행에는 없다). 칸 없는 옛 꼴 한 줄에 답이 여럿이어도 한 줄로 세므로 옛 실행의 값은 낮게 나온다. 위임 뒤 메인이 고른 줄이 표지 없이 적힌 옛 실행은 답으로 세므로 그 값은 높게 나온다. 따옴표가 답이 아닌 인용인 줄은 가려내지 않았다.
- 묻는 승인: 사람이 답한 `완료` task. `approval_mode: 승인`이거나, 그 값이 비어 있고(`결과 승인` 기록은 이 값을 채우지 않는다) 사람 답 줄이 있는 것. 아래 일괄은 뺀다.
- 일괄: 사람 답 줄의 따옴표 안이 모두 일괄 위임의 말(`이후 전체`, `나머지 자동`, `자동 승인` 등)인 task.
- 도장(10절 P5): 묻는 승인 가운데 `n_decide`, `n_todo`가 0이고 사람 답 줄의 지점·결정 칸(칸 없는 옛 꼴은 줄 전체)에 되물음·이의·고칠·고침·판단 안 됨이 없는 것. 칸이 빈 task는 도장으로 세지 않는다(`zero_decision_approvals`와 같다).
- 코드 승인뿐: 코드 도장 가운데 사람 답 줄이 모두 승인인 것. 화면 밖 선택을 답한 task(예: `변이 권한 거부 | 메인이 직접 돌림`)를 뺀 좁은 값이다.
- 코드: 구현 kind와 `fix`.
- 폴더 대기: 흐름별 `flow_wait`의 합(분). 사람이 자리를 비운 구간이 섞인다.

| 실행 | 완료 task | 답 | 답/task | 묻는 승인 | 일괄 | 도장 | 코드 승인 | 코드 도장 | 코드 승인뿐 | 폴더 대기(분) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 실행 01 | 42 | 86 | 2.05 | 36 | 0 | 8 | 12 | 5 | 4 | 32 |
| 실행 02 | 14 | 11 | 0.79 | 7 | 0 | 0 | 1 | 0 | 0 | 0 |
| 실행 03 | 2 | 10 | 5.00 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| 실행 04 | 73 | 139 | 1.90 | 51 | 0 | 5 | 5 | 0 | 0 | 0 |
| 실행 05 | 31 | 47 | 1.52 | 21 | 0 | 6 | 1 | 0 | 0 | 0 |
| 실행 06 | 21 | 29 | 1.38 | 11 | 0 | 3 | 2 | 0 | 0 | 0 |
| 실행 07 | 101 | 165 | 1.63 | 56 | 0 | 27 | 10 | 8 | 6 | 17 |
| 실행 08 | 99 | 152 | 1.54 | 45 | 30 | 20 | 19 | 9 | 7 | 1772 |
| 실행 09 | 85 | 126 | 1.48 | 47 | 0 | 13 | 5 | 1 | 1 | 0 |
| 실행 10 | 14 | 24 | 1.71 | 12 | 0 | 4 | 1 | 1 | 1 | 0 |
| 실행 11 | 1 | 6 | 6.00 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 실행 12 | 113 | 133 | 1.18 | 42 | 22 | 23 | 23 | 17 | 7 | 331 |
| 실행 13 | 85 | 99 | 1.16 | 49 | 0 | 37 | 23 | 20 | 15 | 131 |
| **합** | 681 | 1027 | 1.51 | 380 | 52 | 146 | 102 | 61 | 41 | 2283 |

실행이 13개인 것은 설계안 11.1절의 "열둘"을 쓴 뒤 끝난 실행이 있기 때문이다(`실행 10`).

**설계안 2.1절과의 대조**: 코드 61/102(60%)이고 2.1절은 63/98(64%)이다. A11 앞의 값은 64/102(63%)였고, 사람 답 줄의 `고침`, `판단 안 됨`을 이의로 세면서 줄었다. task별로 맞춰 보지는 않았으므로 남은 차이의 원인은 모른다. 답/task는 합 1.51이고, mcp 값은 위 표의 행이다(설계안 10절의 참고 값 약 1.6은 어림이다).

P1(구조 쪽 코드 확인 곳)은 옛 실행에 판단 기록이 없어 잴 수 없다. 첫 값은 규칙을 쌓는 판의 첫 실제 실행이다.

## 1.2.0 칸의 세는 법

`python scripts/collect.py {실행} --measure`의 멈춤 다음 줄이다(10절과 11.1절 경계 표의 1.2.0 칸). 실행 폴더를 읽기만 하고, 관문과 판정은 이 값을 읽지 않는다. 못 읽은 값은 0이나 없음이 아니라 `재지 못함`이다.

- 답, 질문 꼴별 답: `완료` task의 사람 답 줄. 지점 칸으로 task 승인, 정해 주실 것, 명령 단계, 코드 확인, 시험 변화, 리뷰 이의, 하실 일, 이해 되물음, 이의 되물음으로 가르고 못 가르면 `그 밖`이다. 옛 실행은 지점이 `답`뿐이거나 칸이 없는 줄이 많아 `그 밖`이 크다. 1.2.0은 규칙 몫이 없어 답 전체가 P3의 `그 밖`이다.
- 읽을 줄: 묻는 승인의 마지막 `screen-shown.md`와 `cards\`의 처음 낸 카드, 폴더 표의 줄 수. 화면을 다시 물었으면 마지막 판만 잰다. 옛 실행은 이 파일이 없어 재지 못함이고, 기준은 A-R 문단대로 사본에 `screen.py`를 돌려 만든다.
- 흐름당 읽을 줄: 흐름마다 묻는 승인의 화면과 그 흐름 task의 카드를 합한 값의 최댓값. 화면이 빠진 묻는 승인이 있는 흐름은 값이 낮으므로 최댓값에서 빼고 수를 적는다. 흐름 밖 task는 넣지 않는다.
- 마무리 리뷰: 마무리 task마다 `wrap-review.md`의 줄 수.
- 리뷰 자료 없음: 1.2.0부터 시작한 task의 `screen-shown.md`에서 `! 리뷰 자료 없음`으로 시작하는 줄이 있는 화면 수. 다시 물은 화면은 마지막 판만 본다.
- 가림: 1.2.0부터 시작한 task에 남은 `sheet.html`의 `{n}줄을 가렸습니다.`와 카드의 `비밀값 꼴 {n}줄 가림`. 터미널 출력은 남지 않아 세지 않는다. 한 장을 다시 내면 마지막 판만 남는다.
- 코드 확인, 곳 답: `places.md`의 `처리`, `답`과 머리의 `재지 못함`. 판단마다 답이 갈리면 `섞임`이다. 코드 도장은 곳 답 가운데 `문제 없음`과 `나머지 남김`이고, 위 표의 코드 도장과 단위가 달라 직접 견주지 않는다.
- 곳당 시간: `cards\{키}.shown.md`의 파일 시각에서 곳 답 `--record` 시각까지. 자리를 비운 시간이 섞인다. 복사로 파일 시각이 답보다 늦어지면 재지 못함이다. 카드의 `--full` 요청은 기록이 없어 재지 못함으로 내고, `--tree`는 폴더 표 파일로 센다. 보안 곳(`보안: 예`)은 수와 시간을 따로 낸다(A-R 사전 기준).
- 숨은 판단: 끝난 1.2.0 코드 task `judge.md` 「판단 대조」의 `숨은 판단:` 줄 수. `[설계:]`가 어디에도 없어 옮긴 줄만 가르는 꼴이 없으므로 판정자가 새로 찾은 줄까지 든 값이고, 줄에 그렇다고 적는다.
- 코드 의견: 곳마다 `의견`과 그 곳의 답. `의견 없음`은 판정자가 `코드 의견:`을 쓰지 않은 곳이다.
- 흐름 리뷰 도장: `n_decide` 0에 이의가 없는 묻는 흐름 리뷰를 `n_todo`가 0인 것과 아닌 것으로 나눈다.
- 전·후: `judge-run.md` 「흐름 리뷰 전·후」의 흐름별 상태와 이유. 고른 시나리오보다 결과가 적으면 일부다.
- 멈춤의 결과 없이 반환: journal의 `결과 없이 반환`에서 같은 task의 `이어 씀`까지 분의 합과 닫히지 않은 수. 재개 수는 바로 뒤에 `정정: 앞의 … 재개 줄`이 있는 줄을 뺀다. 표지 없이 지나간 멈춤은 재지 못한다.
- 계약별 리뷰, 직접 내린 판단: 1.2.0부터 시작한 묻는 task를 등록표 `review`로 묶어 물은 때부터 답한 때까지의 중앙값, 바꾼 답, 이해 되물음, 도장과 「정해 주실 것」 답을 센다.
- 설계 승인, 책임 경계, 한 장 이의, 시험 변화, 설계 뿌리 결함: 기록에 있는 값만 세고(`뿌리: 설계` 줄, 미룬 실물 확인, 시험 변화 줄과 답), 기록 칸이 없는 값은 `재지 못함`으로 적는다. 접근 이의는 이의 전체로 세므로 넘치게 센다.
- 작업 칸: 칸 2 이상인 실행에만 나온다. 칸 수, 재시도, 판정불가 환경, 넣기 충돌, 넣은 뒤 확인 실패.
- 알림으로 바꾼 것: 1.2.0부터 시작한 task의 `approval_mode: 알림`. 받아오기 충돌 수정과 뒤에 문제가 드러난 수는 기록 칸이 없어 재지 못함이다. 마무리의 이의는 어느 칸에서 나왔는지 가리지 못한다.
- 위임: `decisions.md`의 위임 줄(같은 원문이 이어지면 하나), 그 앞 위임 뒤로 받은 승인 줄 수, `[메인]` 줄 수.

## 행위자별 읽는 양

`python tests/py/reading.py budget`의 출력이다. 칸은 행위자, 상한, 지금 값이다. `넘음` 행은 `PENDING_OVER`로 관리되며 이번 변경에서 생기지 않았다.

```
requirements-writer:question 32165 32296 넘음
requirements-writer:req-overview 37209 35947
requirements-writer:brief 43580 40307
requirements-writer:req-detail 37507 36482
requirements-writer:change:req-overview 39251 38877
requirements-writer:change:req-detail 39549 39412
requirements-writer:change:brief 43557 42801
cause-writer:root-cause 48494 44988
cause-writer:question 46754 43601
design-writer:design 55214 54844
design-writer:ui-design 55933 52855
design-writer:change:design 59694 59727 넘음
design-writer:change:ui-design 60413 57738
design-writer:question 42802 39106
code-writer:implementation 54645 50887
code-writer:fix 54645 50887
code-writer:fe-implementation 58737 58788 넘음
code-writer:be-implementation 50187 50238 넘음
code-writer:probe 38176 38227 넘음
verify-writer:flow-verify 47398 44778
verify-writer:full-verify 47398 44778
verify-writer:reverify 47398 44778
release-writer:wrap-up 41637 38191
release-writer:deploy-plan 50122 49363
release-writer:deploy-exec 47793 40661
infra-writer:infra-design 39126 39175 넘음
infra-writer:probe 35814 35863 넘음
infra-writer:change:infra-design 40651 40695 넘음
read-judge:question 33056 32018
read-judge:req-overview 35055 33716
read-judge:req-detail 35353 34251
read-judge:brief 39361 37640
read-judge:ui-design 40296 39196
read-judge:change:req-overview 39535 38599
read-judge:change:req-detail 39833 39134
read-judge:change:brief 43841 42523
read-judge:change:design 50347 52639 넘음
read-judge:change:ui-design 44776 44079
read-judge:design 51164 52793 넘음
read-judge:implementation 45220 43791
read-judge:fix 45220 43791
read-judge:root-cause 40492 38442
read-judge:flow-verify 47504 45262
read-judge:full-verify 47504 45262
read-judge:reverify 47504 45262
read-judge:merge 37916 32401
read-judge:wrap-up 37212 34244
read-judge:deploy-plan 46348 45416
read-judge:deploy-exec 43368 36714
read-judge:infra-design 35580 35617 넘음
read-judge:change:infra-design 39179 39211 넘음
read-judge:probe 32270 32305 넘음
read-judge:fe-implementation 43797 43832 넘음
read-judge:be-implementation 43107 43142 넘음
run-judge:implementation 31302 31592 넘음
run-judge:fix 31302 31592 넘음
run-judge:root-cause 30136 30426 넘음
run-judge:merge 30136 30426 넘음
run-judge:wrap-up 30822 31110 넘음
run-judge:deploy-exec 31840 32125 넘음
run-judge:fe-implementation 31616 31592
run-judge:be-implementation 31616 31592
```
