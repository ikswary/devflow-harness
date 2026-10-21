# B: 전체 CI 재사용 가능성 shadow

이 문서는 `verification-shadow.md`가 허용한 B 실행의 wrap-up에서만 읽는다. 재사용 가능성을 관측하지만 전체 CI를 생략하지 않는다.

## 관측 시점과 명령

문서 변경을 커밋한 깨끗한 HEAD에서 새 전체 CI를 시작하기 전에 run-judge가 원 CI와 현재 후보의 증거를 확인한다. 메인은 관측을 먼저 고정한다.

```text
python ${CLAUDE_PLUGIN_ROOT}/scripts/collect.py RUN --shadow-b-freeze TASK --observation OBS.json
```

위 명칭은 public 명령 스키마이며 실제 관측값 예시가 아니다. `OBS.json`은 `basis:{}`, `source_ci:{full_sha,input_sha256,artifact_digest,db_state_sha256,commands_sha256,environment_sha256,complete:true,independent:true}`, `current:{code_dir,full_sha,input_sha256,artifact_digest,db_state_sha256,commands_sha256,environment_sha256}`, `candidate_pair:{source_task,current_task}`, `observed_at`, `full_ci_started_at:null`, `evidence_files:[{role,path,sha256}]`를 요구한다. evidence role은 `source_ci_log`, `artifact`, `db_state`, `installed_environment`, `commands`, `input_manifest`를 모두 포함하고 raw hash를 쓴다. 관측 뒤 새 전체 CI를 실행하며 실제 재사용 값은 항상 false다.

관측 절 누락·고정 실패는 관측 제외 사유일 뿐 기존 gate를 막지 않는다. 이미 CI가 시작됐거나 관측 뒤 후보·입력이 바뀌면 비교에서 제외하고 새 전체 CI 결과만 사용한다. `observed_at`과 실제 `full_ci_started_at`은 timezone이 있는 ISO-8601이어야 하며 시작 시각이 관측보다 뒤여야 한다. 기계 기록은 `identity_verified:false`, `actual_reuse:false`를 유지한다.

## 기계 상태와 독립 판정

자동 고정은 필수 식별자가 실제로 다르면 `impossible`, 필요조건이 맞으면 `indeterminate`만 기록한다. 자동으로 `possible`을 만들지 않는다. 아래 근거가 모두 독립 대조된 경우에만 run-judge가 새 전체 CI 뒤 `judge-run.md`에 `shadow-b-conclusion: possible`을 쓴다. 다른 결론은 `impossible|indeterminate`다. 이 결론은 wrap-up이 `완료`이고 기존 독립 judge gate와 「최종 배포 후보 CI」의 전체 검증 commit·artifact가 현재 관측과 일치한 뒤에만 관측값으로 저장한다.

- 같은 run·round의 완료된 독립 run-judge 전체 CI이며 원 판정·로그 hash와 독립 근거를 읽을 수 있다.
- 원 CI와 현재 HEAD의 full SHA, 깨끗한 작업 트리, 시험 소스·추가 자료 hash가 같다.
- recon의 전체 명령 목록·옵션·순서·범위·기준선·검증 정책 hash가 같다.
- 설정, lock, 실제 설치 결과, 런타임·도구 버전과 비밀값을 제외한 환경 입력 식별이 같다.
- 원 CI artifact ID·digest가 현재 내보낼 artifact와 같고 보존·조회된다. 재빌드 산출물은 같다고 추정하지 않는다.
- 환경·DB의 초기화 절차, seed, snapshot, schema 식별과 실행 근거가 같고, 원 검사 뒤 외부 쓰기·배포·환경 변경 부재와 신선함이 증명된다.
- 원 실행에 미실행·자원 대기·미해결 실패·판정불가가 없고 로그와 산출물을 조회할 수 있다.

문서만 바뀌어도 full SHA가 다르면 `불가`다. 동일 tree·URL·명령 문자열·과거 통과는 충분하지 않다. 동적 외부 서비스·시간 의존 상태의 동등성과 신선함을 현재 근거로 증명하지 못하면 `불가` 또는 `판정불가`다. 기준선 허용 실패가 있는 사례도 초기 실험 비교에서 제외한다.

## 유지할 실행과 측정

사전 관측을 고정한 뒤 wrap-up 전체 CI를 새로 모두 실행해 `judge-run.md`의 최종 배포 후보 commit·artifact를 남긴다. 마지막 merge의 전체 CI와 full-verify 입력도 기존 시점을 유지한다. 앞 부분 검사 합집합이나 참조 연쇄로 대신하지 않는다.

원 CI 시간, 새 CI 시간, 근거 대조 시간, 자원 점유·대기와 독립 결론별 수는 `verification-shadow-measure.md`대로 기록한다. `possible` 건수와 원 CI 시간은 잠재 절감량이며 실제 절약이 아니다. 단일 흐름처럼 비교할 원 merge CI가 없으면 절감 기회 없음으로 기록한다.

독립 `possible` 사례에서 새 CI 결과가 하나라도 다르거나 후보·DB 동일성 오판, 원 근거 변조·불명이 확인되면 B 관측을 중단한다. 기계 상태가 `indeterminate`(`necessary_conditions_match:true`)이고 CI 시작 시각이 사전 관측보다 뒤이며 marker가 있을 때만 `reviewer_conclusion`과 `reviewer_judge_path/hash`를 덧붙인다. 저장 뒤 원 evidence가 바뀌거나 삭제되거나, judge marker·전체 CI gate·commit/artifact·timezone 시각 근거가 더는 맞지 않으면 저장한 독립 결론을 무효화한다. E·N·유형별 수·S·H를 충족해도 별도 정책 승인 전에는 재사용을 켜지 않는다.
