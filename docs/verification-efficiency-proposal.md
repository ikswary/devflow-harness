# 검증 효율 개선 보완안

상태: 아래 보완안을 검토한 뒤 사용자가 2026-10-21에 “ㅇㅋ 1.0.2 반영”으로 구현을 승인했다. 1.0.2는 선택형 비교 기록과 호출 지침 정정을 반영하며, 실제 재독·CI 축소는 적용하지 않는다. 분석 기준은 `main 92f1e53`, 플러그인 `1.0.1`이다.
이 문서의 “승인 뒤”·“이번 저장”은 제안 당시의 범위를 남긴 것이다. 실행 절차와 CLI의 정본은 `references/experiments/verification-shadow.md`이며, 개별 실험 시행에는 사전값과 해당 실행의 승인 기록이 필요하다.
추천은 A의 제한된 shadow 비교 준비, B의 현행 전체 검사 유지, C의 호출 기준 문구 정정이다. D는 기존 자동 실행의 설명 정정이다.
새 agent·task kind·상태·캐시 서비스는 추가하지 않는다. 기존 task 파일과 `journal.md`에 근거를 붙인다.

## 현재 계약과 바꾸려는 범위

| 항목 | 현재 근거 | 보완 결론 |
| --- | --- | --- |
| A 구현 읽기 판정 | `scripts/devflow_lib.py:416-435`, `references/registry/kinds.md:12-13` | 현재 조건을 유지한다. implementation은 조건부, fix는 항상 읽기 판정이다. |
| A 흐름 검증 | `references/kinds/verify.md:17-21,66-71` | AC 전 행 독립 판정·연결 검토는 유지한다. 알림 task 변경의 두 번째 전면 재독만 실험 대상으로 좁힌다. |
| A 표본 전환 조건 | `references/design-summary/decisions.md:14,26` | 원천 직접 검토와 숨은 예외의 실측을 요구한다. 판정 상속만으로 독립 검토를 대체하지 않는다. |
| B 마지막 merge | `references/kinds/merge/main-order.md:13-14` | 전체 CI를 새로 실행해 full-verify에 넘기는 시점을 유지한다. |
| B full-verify 입력 | `references/kinds/verify.md:25-28` | 합쳐진 후보의 전체 검사 결과를 받아야 한다. wrap-up을 기다리는 의존을 만들지 않는다. |
| B wrap-up | `references/kinds/wrap-up/main-order.md:8`, `references/kinds/wrap-up/run-check.md:5-7` | 문서 커밋 뒤 깨끗한 HEAD의 전체 CI를 유지한다. |
| B 배포 권위 | `scripts/task_set.py:308-355` | 최근 완료된 wrap-up의 commit·artifact가 이미 권위다. 이를 새 개선 효과로 주장하지 않는다. |
| C 호출 기준 | `references/main/selfcheck.md:7`, `scripts/devflow_lib.py:423-425` | 문서는 writes_code_dir, 프로그램은 run_judge를 사용한다. 문서를 프로그램과 맞춘다. |
| D machine_check | `scripts/task_set.py:913-916`, `references/main/selfcheck.md:3` | 메인이 상태 전이를 요청하면 스크립트가 자동 실행·기록한다. 신규 자동화가 아니다. |

현재 `judge.md`에는 기준별 확인 방법·근거·못 본 범위가 있지만 commit/diff와 완전한 영향 범위의 고정 식별이 없다(`references/formats/judge-file.md:12-19,28`).
시각만으로 후속 task의 변경 영향이나 원 판정의 누락을 배제할 수 없다. 기존 자료는 누락 필드를 추측해 채워 재사용하지 않는다.

## A 앞 판정 연결과 두 번째 재독의 범위

A의 최종 목표는 동일 범위를 반복 읽는 비용을 줄이는 것이다. 이번 추천 단계에서는 기존 전면 재독을 계속 수행한다.
향후 승격해도 AC 전 행의 코드·시험 직접 대조, task 사이 불일치, 새·변경·미확인 범위의 직접 검토는 줄이지 않는다.
`상속 가능`은 재독 후보 분류이며 AC의 `통과` 판정을 자동 생성하는 상태가 아니다.

### 단계별 책임

| 단계와 task | 담당 | 실행과 기록 |
| --- | --- | --- |
| 구현·수정 | code-writer | 기존 코드·시험·변이 지시를 쓴다. 자기 결과를 독립 증거로 선언하지 않는다. |
| 자체 검증 | read-judge | 기존 호출 조건대로 원본을 직접 읽고 아래 읽기 증거를 judge.md에 작성한다. |
| 자체 검증 | run-judge | 기존 독립 영향 검사·변이를 수행한다. 읽기 증거 부재를 실행 통과로 대신하지 않는다. |
| 커밋과 받아오기 | main·scripts | main이 대조를 요청하고 기록한다. 스크립트가 diff·commit·hash를 계산·비교한다. 불일치면 재판정한다. |
| flow-verify 준비 | main·collect.py | 기존 notified 목록과 해당 task·판정 경로, 고정 후보 commit, 그 사이 모든 commit을 전달한다. |
| flow-verify 작성 | verify-writer | 아래 분류를 전 행 적용한다. shadow에서는 후보 작성자와 현행 전면 검토 작성자를 별도 인스턴스로 호출한다. |
| flow-verify 자체 검증 | read-judge | shadow 독립 발견자와 최종 판정자를 별도 인스턴스로 호출한다. 최종 판정은 기존 gate를 따른다. |
| 결과 전이 | task_set.py·main | 기존 판정·승인·알림 계약을 유지한다. shadow 결과로 현재 gate를 통과시키지 않는다. |

### 최소 읽기 증거

`judge.md`에 `## 판정 대상과 범위`를 추가하는 설계를 제안한다. 기존 판정 표의 의미와 실패 처리 형식은 유지한다.
필수 필드는 아래와 같으며 빈 값·`없음`을 실제 확인 근거로 인정하지 않는다. 해당 없음은 이유와 검토자가 있어야 한다.

| 필드 | 값과 용도 |
| --- | --- |
| 대상 | run·round·task ID, 판정 계약 판본, 작업 폴더, base SHA, 검사 시 HEAD SHA |
| 변경 스냅샷 | tracked diff 파일 경로와 SHA-256, 새 파일·삭제·rename 목록 및 내용 식별; 모든 판정 대상 포함 |
| 기준 스냅샷 | task 판정 기준·AC·요구사항·설계의 파일 경로와 내용 hash |
| 기준별 실제 범위 | 기준 ID, 읽은 파일·심볼/절·행, 내용 hash, 직접 확인 방법, 판정, 못 본 범위 |
| 소비 경로 | 관련 호출자·공유 schema·auth·config·시험·의존성의 경로와 확인 범위; 불명은 명시 |
| 독립 근거 | 판정자 ID, 작성·수정 지시·수정 미참여, 판정 시각, 원본 근거 경로 |
| 커밋 대응 | 스크립트가 판정 snapshot→최종 task commit을 계산·대조하고, main이 명령·결과·시각을 journal에 기록 |

독립 판정자는 task 커밋 전에 실행되므로 아직 없는 최종 commit을 적도록 요구하지 않는다(`references/main/code-folder.md:8`).
main은 judge.md를 덮어쓰지 않는다. snapshot과 커밋 대응이 없거나 내용이 다르면 앞 판정은 상속 불가다.
줄 번호만 같거나 파일 이름이 같다는 것은 동일성 근거가 아니다. 변경된 행의 이동도 hash·심볼 대응으로 검증하지 못하면 무효다.

### 분류 순서와 무효화

verify-writer는 notified 목록의 모든 task와 각 기준에 다음 순서를 적용하고 `result.md`의 `재독 범위 표`에 이유를 쓴다.

1. 원 판정 없음·독립성 불명·기준별 범위 누락·판정불가·기록만 확인이면 `전면 재독`이다. 조건부 read-judge 미호출 task도 여기에 든다.
2. 원 판정 이후 후보까지 `git log`와 전체 diff를 확인한다. 원 task가 아닌 후속 task·받아오기·충돌 해결 변경도 포함한다.
3. 원천·기준·시험·설정·의존성·소비 경로가 바뀌면 해당 기준과 연결 범위를 `변경 재독`한다. 영향 경계를 못 정하면 task 전체로 넓힌다.
4. 승인된 요구·설계 변경, 결과가 같은 것으로 보이는 재작성, 작업 트리 오염, 누락 commit·새 파일은 상속을 무효화한다.
5. 앞 판정이 직접 검토했고 기준·원천·소비 경로가 모두 보존된 행만 `상속 후보`다. 독립 재독 표본은 후보 중에서 별도로 선정한다.
6. 어느 분류인지 불명이면 `전면 재독`이다. 판정에 필요한 원본 자체를 못 읽으면 `판정불가`이며 통과로 세지 않는다.

공유 schema·auth·config·권한·데이터 정합성·동시성·외부 I/O의 변경과 소비 경로는 초기 실험에서 축소 대상에서 제외한다.
동일 파일의 다른 task 변경을 “내 task 밖”으로 제외하지 않는다. 변경 목록과 경로 관계가 완전하다는 근거가 없으면 재독한다.
`재독 범위 표` 열은 `task/기준 | 앞 판정 경로·hash | 후보 commit | 후속 변경 | 분류 | 직접 읽을 범위 | 사유 | 독립 재독 선정 여부`로 고정한다.
숨은 예외 표에는 모든 notified task를 남긴다. 승격 뒤 읽지 않은 범위는 `미재독·상속 근거 있음`으로 쓰고 `숨은 예외 없음`으로 바꾸지 않는다.
알릴 것·확인 안 된 것의 전량 수집과 승인 화면 이관은 그대로 유지한다(`references/kinds/verify.md:19,51-52`).

### 앞 판정의 거짓음성을 잡는 독립 검토

완전한 증거가 있어도 원 판정이 틀릴 수 있다. 상속 후보에 대한 별도 직접 재독을 없애지 않는다.
shadow는 아래 실측 순서대로 후보 작성·독립 발견·현행 작성·최종 판정을 네 개의 별도 인스턴스가 한 번씩 반환하고 종료하는 실험 전용 단계다.
새 역할 종류나 task 상태를 만들지 않는다. 후보와 독립 발견을 고정하는 동안 같은 flow-verify task는 진행 상태를 유지한다.
main은 후보 작성자에게 전면 검토 결과를 주지 않고 독립 발견자에게 후보 분류·앞 판정·작성자 결과를 주지 않는다. 고정 후보·기준은 동일하다.
경로를 전달하지 않았다는 사실은 접근 차단 증거가 아니다. 격리된 입력 목록·컨텍스트와 실제 접근 기록을 남기지 못하면 품질 비교에서 제외한다.
상대 결과 선열람·고정 뒤 변경·격리 불명 사례는 운영 gate의 전면 검토에는 쓸 수 있지만 후보 품질을 입증하지 못한다.
승격 뒤 표본의 모집단은 모든 상속 후보 task다. 위험 유형·변경 크기 구간별 층과 추출 seed·비율·회전 규칙을 실험 전에 고정한다.
고위험 제외 대상·누락 근거는 표본이 아니라 항상 재독한다. 표본 밖 AC도 기존 전 행 독립 판정의 대상이다.
표본에서 중요한 누락 하나가 확인되면 해당 흐름의 상속 후보 전부를 재독하고 실험을 중단한다. 앞 판정을 수정해 누락을 숨기지 않는다.

## B 최종 전체 CI의 세 대안

| 대안 | 비용과 장점 | 안전과 변경 부담 | 결론 |
| --- | --- | --- | --- |
| 마지막 merge를 영향 검사로 축소하고 wrap-up으로 전체 CI 이동 | 반복 실행을 줄일 가능성; 실측 없음 | full-verify가 전체 결과를 못 받고 결함 발견이 마무리까지 늦어짐. 후행 wrap-up 의존은 순환 위험 | 제외 |
| 동일 최종 후보의 전체 독립 CI를 wrap-up에서 재사용 | 입력이 정말 같을 때만 한 번 절약 | 문서 커밋·재빌드·DB 변화로 적용률이 낮을 수 있음. 입력 식별·증거 검증·계약 변경 필요 | shadow 비교 후보 |
| 마지막 merge와 wrap-up의 새 전체 CI 유지 | 중복 실행 비용 유지; 변경 비용 최소 | 기존 발견 시점·배포 후보 확인·1.0.1 계약 보존 | 현재 추천 |

추천 이유: 반복으로 보이는 두 검사가 실제로 같은 후보·환경을 검사한다는 자료가 없다. 완화 비용보다 절감량이 큰지 먼저 확인한다.
현행 흐름은 `마지막 merge 전체 CI → full-verify → 필요 시 fix/reverify/merge → wrap-up 문서 커밋 → 전체 CI → 내보내기`다.
`full-verify → wrap-up → full-verify` 의존은 금지한다. 수정 뒤 재검증과 마지막 합치기도 기존 순서대로 수행한다.
단일 흐름에는 merge가 없으므로 wrap-up 전체 CI가 항상 실행된다. B의 절감 기회가 없음을 결과에 포함한다.

### 재사용 가능성의 shadow 판정

main은 wrap-up 문서 커밋 뒤 현재 후보를 고정하고, run-judge는 아래 비교를 judge-run.md의 별도 `재사용 가능성 관측` 절에 적는다.
이 절은 승인된 신규 실험 run에서만 선택적으로 작성한다. 누락은 관측 제외 사유이며 기존 gate를 차단하지 않는다.
결과는 `가능/불가/판정불가` 중 하나이며, 실제 판정에는 항상 새로 실행한 전체 CI만 쓴다. 앞 부분 검사들의 합집합은 전체 CI가 아니다.

| 비교 항목 | 가능 조건과 무효화 |
| --- | --- |
| 원천 실행 | 같은 run·round의 완료된 독립 run-judge 전체 CI; 원 판정·로그 hash와 작성자 독립 근거가 있어야 함 |
| 코드·시험 | 원 CI와 현재 HEAD의 full SHA 및 깨끗한 작업 트리, 시험 소스·추가 자료 hash가 정확히 같음 |
| 기준·명령 | recon 전체 명령 목록·옵션·순서·검사 범위·기준선·검증 정책 hash가 같음 |
| 설정·의존성 | 설정·lock·실제 설치 결과·런타임/도구 버전·환경 입력 식별이 같음; 비밀값은 출력하지 않음 |
| artifact | 원 CI가 검사한 실제 산출물 ID·digest와 내보낼 산출물이 같고 보존·조회 가능함; 재빌드 산출물은 불가 |
| 환경과 DB | 초기화 절차·seed·snapshot·schema 식별 및 실행 근거, 외부 상태의 동등성과 신선함이 증명됨 |
| 완결성 | 원 실행에 미실행·자원 대기·미해결 실패·판정불가가 없고 로그와 산출물 조회가 성공함 |

문서만 바뀌어도 commit이 다르면 불가다. 동일 tree·URL·명령 문자열·과거 통과만으로 가능이라 하지 않는다.
DB는 같은 초기화 명령 문자열로 부족하다. 원 검사 전 초기 상태와 현재 초기 상태의 snapshot/seed 식별·실행 로그가 모두 있어야 한다.
원 검사 후 외부 쓰기·배포·환경 변경의 부재를 관측할 수 없으면 fresh로 인정하지 않는다. 초기화 자체의 부작용과 비결정성도 검사한다.
현재 도구로 동일성을 증명하지 못하는 동적 외부 서비스·시간 의존 검사는 불가다. 새 인프라를 만들어 재사용률을 높이지 않는다.
기준선에서 허용한 실패가 있는 경우도 초기 재사용 실험에서는 제외한다. 기존 gate의 기준선 처리 자체를 바꾸는 것은 아니다.
검사 중 후보나 입력이 바뀌면 전체 판정을 무효로 하고 새 후보에서 재실행한다. 자원 사용 중은 실패가 아니라 기존 자원 대기다.

### 향후 B 승격에 필요한 명시적 계약 변경

`decisions.md:27`, `build-and-test.md:7`, `merge/main-order.md:14`, `wrap-up/run-check.md:5`의 “매번 새로”와 재사용은 충돌한다.
일반 영향 검사 재사용 허용(`decisions.md:15`)을 최종 후보 CI의 예외 승인으로 해석하지 않는다. 정책 변경 전까지 B 재사용은 금지다.
승격안을 승인할 경우에도 마지막 merge는 전체 CI를 새로 실행하고 full-verify는 그 전체 결과를 받는다. 예외는 wrap-up의 동일 후보 전체 CI 재사용뿐이다.
run-judge가 원 증거를 검증하고 wrap-up judge-run.md에 원 task·파일 hash·CI ID, 항목별 동일성, 확인 시각과 재사용 근거를 쓴다.
task_set.py는 누락·불일치·원본 접근 실패·부분 범위·재사용의 연쇄 참조를 거부한다. 거부되면 새 전체 CI를 실행한다.
`final_merge_candidate`의 판별·마지막 merge 전체 범위 가드는 유지한다. wrap-up의 새 실행/검증된 직접 참조를 구분하는 가드만 추가한다.
wrap-up 권위·exported_commit 대조·deploy-exec의 실제 배포 commit/artifact 동일성 및 배포 뒤 확인은 그대로 유지한다.
단순히 기존 가드를 제거하거나 `범위: 전체 검증`이라는 문장을 복사하는 구현은 허용하지 않는다.

## C 호출 기준 정정과 D 설명 정정

C의 제안 문구는 “등록표 run_judge가 always인 task에 실행 판정이 필요하다. 호출 시점은 각 kind의 실행 순서를 따른다”이다.
wrap-up은 문서 커밋 뒤, deploy-exec는 실제 배포 뒤 계획의 확인 단계에서 호출한다. 일반 자체검증 진입 때 일괄 선행 호출하지 않는다.
`scripts/devflow_lib.py:423-425`가 이미 등록표를 따르므로 C만을 위해 프로그램 로직을 바꾸지 않는다.
D는 상태 전이 요청자 main, 실제 검사·기록 주체 task_set.py라는 표시만 정정한다. 수동 override 지원은 그대로 둔다.

## 실측과 승격 및 중단 기준

측정 전 `run.md` 이번 실행의 값과 `decisions.md`에 실험 계획·사용자 선택을 기록하고 journal에 파일 hash를 남긴다.
필수 사전 값은 대상 저장소·작업 유형, 최소 독립 실행 수 N, 유형별 표본 수, 목표 절감량 S, 허용 추가 관리비 H, 최소 적용 가능률 E, 관측 종료일이다.
A는 숨은 예외 허용률 R과 신뢰수준 Q, 표본 추출 층·seed·비율·회전 주기도 고정한다. 숫자는 실측 없이 이 제안에서 확정하지 않는다.
필수 값이나 실험 승인이 비어 있으면 정책 승격은 미승인이다. 파일의 빈칸을 임의 기본값으로 실행하지 않는다.
N을 결과에 맞춰 줄이거나 S·R·Q를 결과를 본 뒤 바꾸면 해당 회차는 탐색 자료로만 남기고 새로운 계획으로 다시 측정한다.

1. A 후보: verify-writer 인스턴스는 앞 근거로 `result.md`의 후보 분류·축소 검토 절만 쓰고 종료한다. 같은 인스턴스로 전면 검토를 이어가지 않는다.
2. A 후보 고정: main의 요청으로 collect.py의 실험 보조 기능이 해당 절의 고정 사본·canonical hash·작성자·시각·입력 hash를 기록한다. main은 성공 결과만 journal에 연결한다.
3. A 독립 발견: 별도 read-judge가 후보 결과와 앞 판정 없이 notified task 전부의 원천을 읽고 `judge.md`의 독립 발견 절만 쓰고 종료한다. 스크립트가 2와 같은 방식으로 고정한다.
4. A 현행 작성: 두 고정 결과를 스크립트가 확인한 뒤 별도 verify-writer를 호출한다. 현행 전면 검토로 최종 result.md를 쓰고 종료한 뒤 기존 자체검증 전이를 요청한다.
5. A 최종 판정: 다시 별도 read-judge가 고정된 양쪽 결과와 최종 result.md를 대조하고 기존 gate용 judge.md를 쓴다. 차단·중요 누락 등은 원인 task별로 비교한다.
6. A 고정 계약: 사본은 task의 `shadow/candidate.md`·`shadow/baseline.md`, manifest는 같은 폴더에 둔다. UTF-8·LF·줄 끝 공백 보존으로 정규화한 본문의 SHA-256을 canonical hash로 정의한다.
7. A 재호출: collect.py가 단계 완료·인스턴스 ID 차이·고정 사본과 입력 hash를 다음 호출 전 및 최종 전이 전에 검사한다. 불일치면 비교 제외·현행 경로만 진행하며 자동 재측정하지 않는다.
8. B: 후보쌍별 가능 여부를 새 전체 CI 전에 스크립트로 고정하고 실제 전체 CI를 실행한다. 재사용가능 건수·원 CI 시간은 잠재 절감량이며 실제 절약으로 쓰지 않는다.
9. 비용: agent 사용량(관측 가능할 때), 검토/검사 시간, 자원 점유·대기, 근거 작성·대조 비용을 나눠 기록한다. main은 measure.md에 원 task 링크를 남기고 미관측 값을 0으로 채우지 않는다.

후보 운영비에는 근거 수집·hash 대조·분류·무효화·정상 표본 재독을 포함한다. shadow 전용 전면 대조·추가 호출/인스턴스·기존 경로 병행 비용은 별도 열에 둔다.
순절감은 동일 유형의 현행 운영비에서 후보 운영비를 뺀 값으로 추정하고, 실험 전체 지출도 함께 제시한다. 추가 대조 비용을 절감량에 섞지 않는다.
상속/CI 재사용 가능률이 사전 E 미만이면 기능 구축을 중단하고 현행을 유지한다. 적용 대상이 드문 문제를 새 증거 인프라로 확대하지 않는다.

승격은 A/B 각각 별도로 판단한다. N·유형별 표본을 충족하고, 순절감이 S 이상·관리비가 H 이하이며 아래 안전 기준을 모두 만족해야 한다.
A는 독립 대조에서 차단·중요 누락이 없어야 하고 숨은 예외율의 단측 신뢰상한이 사전 R 이하여야 한다. Q에서 사용할 계산법도 사전 고정한다.
같은 run 안 task를 독립 표본 수로 부풀리지 않는다. 실행 간 분산과 유형별 결과를 함께 제시하고 표본 부족은 결론 불가다.
B는 “가능”으로 분류한 모든 사례에서 새 전체 CI와 결론이 일치해야 한다. 상태 변화로 설명되더라도 가능 판정의 실패로 센다.
차단·중요 거짓음성, 가능 판정 뒤 CI 불일치, 원 근거 변조·불명, 후보/DB 동일성 오판이 하나라도 확인되면 즉시 축소 후보 사용을 중단한다.
main은 해당 흐름/후보를 전면 재독·새 전체 CI로 복귀시키고, 미완료 후속 task를 기존 의존으로 막으며 원인·영향을 기록한다.
원인 수정 뒤 자동 재개하지 않는다. 새 계획 승인과 새 측정 구간이 필요하다. 관측 기간 만료·절감 미달은 현행 유지로 종결한다.
안전·비용 기준 충족은 승격 제안의 근거다. 사용자 정책 승인과 계약 회귀 통과 없이는 실제 축소를 켜지 않는다.

## 판본 격리와 재개 및 회귀 기준

현재 판정 계약은 started_version으로 분기한다(`scripts/devflow_lib.py:386-388`). 진행 중 task와 완료된 judge 파일을 새 형식으로 덮어쓰지 않는다.
shadow는 기존 gate와 별도 절에만 기록한다. 신규 판본의 선택된 새 실행에서 시작하며 기존 실행에는 관측 필드를 소급 강제하지 않는다.
축소를 구현하는 판본은 1.0.1보다 큰 명시 버전 경계와 두 judge 정의의 새 def-version을 함께 둔다. 구판 기본 행동은 현행 유지다.
plugin·marketplace·런타임 adapter·DEF_VERSION_MIN을 같은 묶음으로 검증한다(`references/main/maintain.md:3-4`). 설치 중간 상태는 새 task 시작을 막는다.
재개 시 run/started_version·stage·고정 후보·증거 hash·sync_pending·자원 대기를 다시 읽는다. 근거가 낡으면 축소하지 않는다.
이미 실행한 외부 명령과 배포 쓰기 확인을 shadow 때문에 재실행하지 않는다. 기존 승인·재개 순서를 보존한다.

| 회귀 시나리오 | 반드시 확인할 결과 |
| --- | --- |
| read-judge 없는 알림 implementation, 기록만 확인·범위 누락 | 상속 불가·전면 재독, 자동 통과 없음 |
| 뒤 task의 공유 계약 변경·rename·새 파일·충돌 해결·기준 변경 | 영향 기준 무효화; 영향 불명은 task 전체 재독 |
| 앞 판정은 통과지만 실제 숨은 예외가 있는 고정 fixture | 독립 대조가 발견하고 축소 중단; 표본 결과를 무결함으로 확대하지 않음 |
| 전체 CI 일부만 실행, 후보 SHA/산출물 다름, 문서만 새 커밋 | 재사용 불가, 새 전체 CI; 마지막 merge 완료 가드 유지 |
| 같은 URL/seed 명령이나 다른 DB 상태, 외부 쓰기·도구 버전 변경 | 재사용 불가 또는 판정불가; 일반 통과로 바꾸지 않음 |
| 다중 흐름과 fixes의 마지막 merge, 단일 흐름 | full-verify는 선행 전체 결과 사용; 단일 흐름 wrap-up 전체 CI 실행 |
| wrap-up 참조만 있고 원 CI 없음·수정됨·대기·실패·참조 연쇄 | 새 계약의 완료 전이 거부, 새 CI로만 복구 |
| 배포 쌍끼리 같지만 최근 wrap-up과 다름 | 기존 deploy 유지 완료 거부 |
| 1.0.0/1.0.1 진행 task와 신규 task 혼재·재개·판정자 설치 불일치 | 구계약 보존, 새 시작의 버전 검증, 원 판정 미변경 |
| C와 D | wrap-up/deploy-exec 호출 필요·시점 보존; machine_check 자동/명시 override 회귀 보존 |

## 승인 뒤 구현할 대상 파일

이번 저장은 이 제안 파일뿐이다. 다음 목록은 구현 범위이며 현재 수정 지시가 아니다.

- A: `references/formats/judge-file.md`, `references/kinds/verify.md`, `references/design-summary/decisions.md`, `agents/read-judge.md`, `agents/verify-writer.md`.
- A의 근거 수집·형식 검증: `scripts/collect.py`, `scripts/devflow_lib.py`, `scripts/task_set.py`, `references/main/code-folder.md`, `references/formats/result-file.md`.
- C: `references/main/selfcheck.md` 문구만. D: 비교 화면의 책임 표시만; 자동 실행 로직 변경 없음.
- B 현행 유지: 실행 경로·가드 변경 없음. shadow 절 정의는 `references/formats/judge-run-file.md`, `agents/run-judge.md`, `references/kinds/wrap-up/run-check.md`.
- B 승격 승인 때만: `references/kinds/merge/main-order.md`, `references/kinds/wrap-up/main-order.md`, `references/kinds/wrap-up/run-check.md`, `references/practices/build-and-test.md`, `references/kinds/verify.md`, `references/design-summary/decisions.md`, `scripts/task_set.py`, `scripts/devflow_lib.py`의 계약 정합.
- 판본·형식 변경 공통: `scripts/kinds.py`, 생성 `references/registry/*`, 두 judge 정의, `.claude-plugin/plugin.json`, marketplace/adapter 대응 파일, `references/main/maintain.md`, `references/main/resume.md`.
- 회귀: `tests/py/test_transitions.py`, `tests/py/test_kind_table.py`, `tests/py/test_registry.py`, `tests/py/test_machine_check.py`, 필요 fixture와 읽기 비용 기대값(`tests/py/reading.py`), `docs/test-scenarios.md`.

남은 사용자 선택은 실험 시행 여부와 사전 측정값이다. 성능 향상 수치와 A/B 정책 승격은 아직 확정할 수 없다.

## 독립 재리뷰 기록 · 2026-10-21

- A: 별도 reviewer가 최초 결과 고정·호출 분리 누락을 지적했고, 4단계 인스턴스 분리·스크립트 검증·격리 증거·추가 비용을 보완한 뒤 문서 기준 통과했다.
- B/C/D: 다른 reviewer가 전체 CI 유지, 호출 시점, 자동 검사 책임, 판본 격리와 재개 계약을 대조해 문서 기준 통과했다.
- 판정 범위는 보완안의 타당성이다. 구현·실험·효과 측정·운영 전환을 검증한 결과가 아니다.
