# 검증 효율 shadow 실험

이 문서는 평상시 필독 문서가 아니다. 하네스 1.0.2에서 새로 만든 실행이 사용자 승인과 완전한 계획값으로 `A`, `B` 또는 `A,B`를 선택했을 때만 메인과 해당 실험 인스턴스가 읽는다. 기존 실행·다시 연 실행에 소급하지 않는다.

## 바뀌지 않는 gate

- implementation 읽기 판정은 등록표 조건부, fix는 항상이다. flow-verify는 AC 전 행을 코드·시험에서 직접 판정하고 notified task 전부를 다시 읽는다.
- 마지막 merge와 wrap-up은 각각 기존 시점의 전체 CI를 새로 실행한다. B 독립 결론이 `possible`이어도 실행을 생략하지 않는다.
- 새 role·task kind·상태를 만들지 않는다. shadow 산출물은 일반 `result.md`·`judge.md`·`judge-run.md`와 task의 `shadow\` 사본을 쓰며 기존 승인·완료 전이를 대신하지 않는다.
- 실험은 효과를 관측할 뿐 정책을 승격하지 않는다. 승격에는 별도 사용자 승인과 계약 회귀가 필요하다.

## 시작 조건과 계획

task가 하나도 없는 신규 run에서만 아래를 순서대로 한다.

1. 사용자가 실험 시행과 사전 측정값을 승인한다. `run.md` 「검증 효율 실험」의 정확한 집합과 `decisions.md` 승인 근거가 계획과 같아야 한다.
2. 루트에 `shadow-plan.json`을 한 번 만든다. 필수 구조는 `experiments:["A"]|["B"]|["A","B"]`, `repository`, `work_type`, `approval_evidence`, `N`, `counts_by_type`, `S:{value,unit}`, `H:{value,unit}`, `E`, `end_date`, A 선택 시 `A:{R,Q,strata[],seed,ratio,rotation,calculation}`이다.
3. 빈 값·임의 기본값·결과를 본 뒤 바꾼 N/S/H/E/R/Q/계산법은 실행 근거가 아니다. 계획 hash와 사용자 선택을 journal에 기록한다.
4. 메인이 초기화한다.

```text
python ${CLAUDE_PLUGIN_ROOT}/scripts/collect.py RUN --shadow-init PLAN.json
```

초기화가 거부되면 실험을 실행하지 않고 기존 gate만 진행한다. A 절차는 `verification-shadow-a.md`, B 절차는 `verification-shadow-b.md`다.

## 공통 고정 명령

```text
python ${CLAUDE_PLUGIN_ROOT}/scripts/collect.py RUN --shadow-inputs TASK SPEC.json OUT.json
python ${CLAUDE_PLUGIN_ROOT}/scripts/collect.py RUN --shadow-open TASK STAGE --instance ID --inputs INPUTS.json
python ${CLAUDE_PLUGIN_ROOT}/scripts/collect.py RUN --shadow-freeze TASK STAGE --evidence EVIDENCE.json
python ${CLAUDE_PLUGIN_ROOT}/scripts/collect.py RUN --shadow-check TASK
```

위 명칭은 public 명령 스키마이며 실제 계획값 예시가 아니다. `SPEC.json`은 `code_dir`, `criteria_paths`, `copy_paths`, `context`, `allowed_paths`를 받고 스크립트가 실제 모집단·HEAD·tracked/untracked·삭제/rename·hash를 가진 `INPUTS.json`을 만든다. `INPUTS.json` 필수 필드는 `candidate_sha`(40자리), `code_dir`, `git_snapshot:{head_sha,files:[{path,status,sha256|null}]}`, `population`, `criteria:[{path,sha256,section}]`, `copies:[{path,sha256,section}]`, `context:[]`, `allowed_paths:[]`다. 자기 task의 criteria는 `section:"판정 기준"`이며 `sha256`은 그 절 제목 다음부터 다음 `##` 앞까지 원문 body의 줄바꿈만 LF로 바꾼 값이다. 다른 criteria와 copies는 빈 section과 파일 전체 canonical hash를 쓴다.

`EVIDENCE.json` 필수 필드는 `output_path`, `input_sha256`, `context:[]`, `access_log_path`, `access_log_sha256`, `accessed_paths:[]`, `isolation_provider`, `isolation_session_id`, `peer_result_accessed:false`다. 접근 로그 원본은 `{paths:[...]}` JSON이며 raw hash가 맞고 `paths`가 `accessed_paths`와 순서까지 정확히 같아야 한다. 동결 때 이 목록의 허용 범위와 상대 결과 접근도 대조한다. 세부 타입은 설치된 `collect.py` 계약을 따르고 문서가 임의 기본값을 만들지 않는다.

스크립트는 최초 결과 사본·hash, 입력 목록·컨텍스트·접근 로그 원본 hash·instance ID를 고정한다. 문서 canonical hash는 UTF-8, LF, 줄 끝 공백을 보존하고, Git 본문·runtime 증거는 raw bytes hash를 쓴다. 이 기계 상태는 무결성 기록이며 실제 도구 접근·격리를 입증하지 않는다.

고정 뒤 변경, 상대 결과 선열람, 단계 중복 반환, instance 재사용, 입력 hash 불일치, 격리 불명은 품질 비교에서 제외한다. 운영 gate의 전면 검토와 전체 CI는 그대로 진행한다. 자동으로 재측정하지 않는다.

## 측정과 종료

집계·표본 고정·비용 분리·독립 최종 판정은 `verification-shadow-measure.md`를 따른다. 필수값 미충족이나 기간 만료는 현행 유지이며, 메인은 집계만 하고 승격 결론을 내리지 않는다.
