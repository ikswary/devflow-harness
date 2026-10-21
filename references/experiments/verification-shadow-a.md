# A: 앞 판정 연결 shadow

이 문서는 `verification-shadow.md`가 허용한 A 실행에서만 읽는다. 목표는 flow-verify의 두 번째 전면 재독을 줄일 후보를 측정하는 것이며, 이번 판의 전면 재독·AC 전 행 직접 판정·알림 전량 이관은 줄이지 않는다.

## 후보 분류

notified 목록의 모든 task와 기준을 아래 순서로 분류하고 `result.md`의 「재독 범위 표」에 쓴다.

1. 원 판정 없음, 독립성 불명, 기준별 실제 범위·snapshot 누락, 판정불가, 기록만 확인, 조건부 read-judge 미호출이면 `전면 재독`이다.
2. 원 판정 뒤 후보 commit까지 모든 commit과 diff를 본다. 후속 task, 받아오기, 충돌 해결, rename, 새·삭제 파일도 포함한다.
3. 원천·기준·시험·설정·의존성·소비 경로가 바뀌면 해당 기준과 연결 범위는 `변경 재독`이다. 경계를 증명하지 못하면 task 전체를 다시 읽는다.
4. 승인된 요구·설계 변경, 결과가 같아 보이는 재작성, 작업 트리 오염, 누락 commit은 앞 판정 연결을 무효화한다.
5. 앞 판정이 원천을 직접 봤고 기준·원천·소비 경로가 모두 보존된 행만 `상속 후보`다. 이는 자동 통과가 아니다.
6. 불명은 `전면 재독`, 원본을 못 읽으면 `판정불가`다.

공유 schema·auth·config·권한·데이터 정합성·동시성·외부 I/O 변경과 소비 경로, 근거 누락은 축소 후보에서 제외한다. 동일 파일의 다른 task 변경도 영향 밖으로 추정하지 않는다.

표 열은 `task/기준 | 앞 판정 경로·hash | 후보 commit | 후속 변경 | 분류 | 직접 읽을 범위 | 사유 | 독립 재독 선정 여부`다. 숨은 예외 표에는 모든 notified task를 남긴다.

## 판정 snapshot

A 실행의 읽기 판정 `judge.md` 「판정 대상과 범위」에는 대상(run·round·task·계약 판본·작업 폴더·base/HEAD SHA), 변경 snapshot(tracked diff 경로/hash와 새·삭제·rename), 기준 snapshot(기준·AC·요구사항·설계 경로/hash), 기준별 실제 범위(파일·심볼/절·행·hash·확인 방법·판정·못 본 범위), 소비 경로(호출자·공유 schema·auth·config·시험·의존성), 독립 근거(판정자 ID·작성/수정 미참여·시각·원본)를 쓴다.

빈 값·근거 없는 `없음`은 동일성 근거가 아니다. 해당 없음은 이유와 확인자를 쓴다. 후속 변경·누락·hash 불일치·소비 경계 불명은 전면 재독한다. 판정 시 아직 없는 최종 commit을 판정자에게 요구하지 않고, task commit 뒤 스크립트가 snapshot 대응을 검증·기록한다.

## 네 단계

각 단계는 서로 다른 instance가 한 번 반환하고 종료한다. 순서는 `candidate → baseline → current → final`이다.

1. **candidate / verify-writer**: 앞 판정 근거로 후보 분류와 축소 검토 절만 `result.md`에 쓰고 종료한다. `--shadow-open`, `--shadow-freeze`로 `shadow\candidate.md`와 manifest를 고정한다.
2. **baseline / read-judge**: candidate 분류·앞 판정·작성자 결과를 받지 않고 notified task 전부의 원천을 직접 읽어 독립 발견 절만 쓴다. `shadow\baseline.md`를 고정한다.
3. 메인이 `--shadow-check`를 실행한다. 명령은 candidate·baseline의 `frozen`과 고정 사본, current/final 원본, 각 단계 입력·evidence·접근 로그의 hash, 기준/복사 원천·Git snapshot을 다시 대조해 상태와 final 비교 자격을 출력한다. 로그의 무결성은 실제 접근·격리의 입증과 구분하며, 그 의미는 final 판정자가 확인한다.
4. **current / verify-writer**: 고정 확인 뒤 기존 flow-verify 전면 검토로 최종 `result.md`를 한 번 쓴다. 자기 task 폴더 밖은 고치지 않고, 모든 notified task를 다시 읽고 AC 전 행을 직접 판정한다.
5. **final / read-judge**: 고정된 candidate·baseline과 최종 `result.md`, 실제 runtime 원본·각 hash·instance·컨텍스트·도구 접근 근거를 위치별로 대조하고 기존 gate용 `judge.md`를 한 번 쓴다. 원인 task별 차단·중요 누락도 비교한다.

각 stage의 `output_path`는 realpath 기준으로 자기 task의 candidate/current `result.md`, baseline/final `judge.md`와 정확히 같아야 한다. 기계 상태 `status:frozen`은 `evidence_path`, `evidence_sha256`, `access_log_path`, `access_log_sha256`, 자기선언 `accessed_path_claims`, `isolation_verified:false`, `comparison_eligibility:unproven`을 보존한다. 자기선언만 있거나 원본 접근을 독립 대조하지 못하면 `unproven` 또는 `indeterminate`이며 품질 비교에서 제외한다.

final은 `judge.md`에 `shadow-review-conclusion: proven|unproven|indeterminate`를 쓰고, EVIDENCE의 `reviewer_conclusion:{conclusion,citations:[{path,sha256,location}]}`로 원본을 인용한다. citation은 네 단계의 input 사본·접근 로그, final 전 세 단계의 evidence와 결과 원본 또는 고정 사본을 모두 포함하고, `judge.md` 본문에 각 `path#location`을 적는다. final `judge.md` 첫 줄의 실제 판정자 ID는 final open의 instance와 같고 `rjudge-`로 시작해야 한다. marker·instance·citation 원본 raw hash가 모두 맞는 `proven`만 `comparison_eligibility:proven-by-final-read-judge`가 된다. `frozen/observed`는 무결성 상태이고 판정 결론이 아니다. current와 final의 일반 gate는 제외하지 않는다.

## 표본과 중단

모집단은 모든 상속 후보 task다. 계획의 위험 유형·변경 크기 `strata`, `seed`, `ratio`, `rotation`, R, Q, `calculation`으로 표본을 뽑는다. 추출은 결과 전에 고정하고, 같은 run의 여러 task를 독립 실행 수로 부풀리지 않는다.

후보 추가 작성, 독립 baseline, current 전면 재독, final 대조와 근거 수집·분류·무효화·정상 표본 재독 비용은 `verification-shadow-measure.md`대로 나눠 기록한다.

독립 대조에서 차단·중요 거짓음성 하나, 원 근거 변조·불명, 격리 위반이 나오면 해당 흐름의 상속 후보를 전면 재독하고 A 관측을 중단한다. 숨은 예외율 단측 신뢰상한이 계획 R 이하인지 계획 Q·계산법으로 판단한다. 원인 수정 뒤 자동 재개하지 않는다.
