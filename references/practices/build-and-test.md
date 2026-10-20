# 빌드·테스트 실행과 보고

읽는 kind: `question`, `root-cause`, `implementation`, `fix`. 실행 판정자도 읽는다.

## 명령 고르기
- 먼저 `recon.md`의 명령을 쓴다. 없으면 아래 기본값을 쓰고 보고서에 "recon에 없음"이라고 적는다.

| 스택 | 빌드 | 테스트 전체 | 좁혀서 실행 |
|---|---|---|---|
| Gradle | `./gradlew build -x test` | `./gradlew test` | `./gradlew :{모듈}:test --tests '{FQCN}'` |
| Gradle(모듈별 독립) | `cd {모듈} && ./gradlew build -x test` | `cd {모듈} && ./gradlew test` | 동일 |
| Maven | `./mvnw -q package -DskipTests` | `./mvnw test` | `./mvnw test -Dtest={클래스}` |
| Python | - | `python -m pytest -q` | `python -m pytest {경로}::{이름}` |
| Node | `npm run build`(있을 때) | `npm test` | 프레임워크별(`npx vitest run {파일}`, `npx jest {파일}`) |

- 품질 도구가 설정돼 있으면 함께 돌린다: ktlint(`./gradlew ktlintCheck`), detekt, checkstyle, spotless(`spotlessCheck`), ruff, eslint, `tsc --noEmit`.
- Gradle 전체 테스트는 Bash 타임아웃을 600000ms로 준다. 더 걸리면 모듈별로 나눈다.
- 테스트 보고서 위치: Gradle `build/reports/tests/test/index.html`, `build/test-results/test/*.xml`(실패 상세는 XML에서 찾는다).
- vitest 4 이상은 에이전트 환경에서 기본 리포터가 `agent`라 통과한 시험과 재시도 표시를 출력하지 않는다. JSON 리포터에도 재시도 횟수가 없다. 재시도를 보려면 `--reporter=verbose`를 붙이거나(재시도된 시험 끝에 `(retry xN)`) recon의 「재시도 기록」 방법을 쓴다.

## 흔들림과 재시도
- "흔들림 없음", "재시도 0", "간헐 실패 0"은 그 계층에 재시도가 꺼져 있거나 재시도 기록(리포터 출력, 결과 파일의 재시도 칸)을 실제로 봤을 때만 쓴다. 재시도가 켜져 있는데 기록을 볼 수단이 없으면 "흔들림 판정불가(재시도 기록 없음)"로 쓴다. 재시도로 통과한 시험은 통과로 세되 이름을 보고한다.
- 재시도 설정은 설정 파일의 `retry`·`retries`와 시험별 옵션(`{ retry: n }`)을 모두 찾는다.

## 단계 순서
1. 잠금 밖 단계(recon의 설치 확인 명령이 있으면 그것, 타입 검사, 린트, 단위)를 먼저 돌린다.
2. 여기서 **모듈·패키지를 찾지 못한다는 오류**(`Cannot find module`, `TS2307`, `ERR_MODULE_NOT_FOUND`, `ModuleNotFoundError`, `No module named`, recon 설치 확인 명령의 실패)가 나오면 잠금 단계(빌드 뒤 공유 자원 시험)를 시작하지 않고 "판정불가(설치 불일치, 의존성 설치 필요)"로 보고한다. 이 규칙은 계획의 "실패해도 다음 명령을 계속" 지시보다 앞선다. 그 밖의 실패(코드의 타입 오류, 단언 실패)는 계획대로 계속한다.
3. 빌드 산출물을 읽는 시험은 빌드 뒤에 돌린다(recon의 명령 순서).
설치 확인 명령은 프로젝트마다 다르므로 recon 「폴더 준비」에 둔다.

## 기존 실패와 새 실패 구분
구현 전부터 실패하던 테스트를 새 결함으로 보고하면 판정이 왜곡된다. 실패가 나오면 `git stash`로 되돌려 보지 말고(작업 트리를 건드리므로) 다음으로 구분한다:
- 실패 테스트가 이번 변경 파일과 관련된 클래스를 대상으로 하는가
- 실행 결과가 이전 판정 기록(기준선 등)에 이미 실패로 기록돼 있는가
구분할 수 없으면 "기존/신규 불명"으로 적는다.

건너뜀과 돌지 않음(앞 실패로 실행되지 않은 시험) 수도 기준선과 대조한다. 늘었으면 늘어난 시험 이름을 적는다. 건너뛰고 녹색으로 끝난 실행은 그 시험을 확인한 것이 아니다.

## 자리 표시·디버그 코드 검사
변경 파일(`git diff --name-only` + 새 파일)에 대해서만:
```bash
git diff -U0 | grep -nE '^\+.*(TODO|FIXME|XXX|println\(|System\.out\.print|console\.log|print\(|debugger|@Disabled|\.only\(|pytest\.mark\.skip|NotImplementedError)'
```
발견 항목은 실제 문제인지(예: 원래 쓰는 로깅 방식인지) 한 줄로 판단을 붙여 보고한다.

## 보고 형식
```markdown
## 실행 결과
| 검사 | 명령 | 결과 | 시간 |
|---|---|---|---|
| 빌드 | ... | 성공/실패/판정불가 | 1m20s |
| 테스트 | ... | 142 통과 / 2 실패 / 3 건너뜀 / 0 돌지 않음 | |
| 재시도 | (본 방법: 리포터·파일 / 볼 수단 없음) | n건(시험 이름) / 판정불가 | |

## 실패 상세 (상위 10건, 나머지는 "외 N건")
- `{테스트 FQCN}` — {핵심 에러 한 줄} ({파일:줄}) — 신규/기존/불명

원시 로그: {프롬프트가 준 경로 | 없음}

## 판정 (요청받은 경우)
| 기준 | 판정 | 근거 |
```
