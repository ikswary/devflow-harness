## 1. 이름

| 대상 | 규칙 | 예 |
|---|---|---|
| 실행 폴더 | `{호출한 폴더}\_workspace\{YYYY-MM-DD}-{짧은 영문 슬러그}` | `_workspace\2026-01-01-example` |
| task id | `T` + 세 자리 일련번호. 실행 안에서 만든 순서 | `T007` |
| task 폴더 | `tasks\{task id}\` | `tasks\T007\` |
| 묶음·흐름 이름 | 짧은 영문 소문자와 하이픈. 공통은 `common` | `contact-form` |
| 통합 브랜치 | `harness/{슬러그}/integration` | `harness/example/integration` |
| 흐름 브랜치 | `harness/{슬러그}/{흐름}` | `harness/example/common` |
| 수정 흐름 | 흐름 이름 `fixes`. 다시 연 회차(`run.md` `round` n ≥ 2)의 수정·통합 흐름은 `fixes-r{n}`·`integration-r{n}` | `harness/example/fixes` |
| 배포 폴더 흐름 | 배포만으로 시작할 때 `deploy-{n}`(n은 이 실행에서 몇 번째 배포 폴더인지, 1부터. 다시 연 실행에서 겹치지 않게) | `harness/example/deploy-1` |
| 코드 폴더 | `{저장소 폴더 이름}-{슬러그}-{흐름 또는 integration}`. 저장소 폴더 옆에 둔다 | `myapp-example-common` |
| 에이전트 인스턴스 | `{역할 줄임}-{task id}` (다시 띄우면 `-r{n}`을 붙인다) | `code-T012`, `rjudge-T012`, `code-T012-r1` |

역할 줄임: `req`(devflow-harness:requirements-writer), `cause`(devflow-harness:cause-writer), `design`(devflow-harness:design-writer), `code`(devflow-harness:code-writer), `verify`(devflow-harness:verify-writer), `release`(devflow-harness:release-writer), `rjudge`(devflow-harness:read-judge), `xjudge`(devflow-harness:run-judge).

흐름이 하나뿐인 실행도 흐름 브랜치는 `harness/{슬러그}/{흐름}`이고 통합 브랜치는 없다.

`harness/{슬러그}` 자체는 브랜치로 만들지 않는다. git은 `a`라는 브랜치가 있으면 `a/b`를 만들 수 없어서, 통합 브랜치나 흐름 하나짜리 브랜치를 그 이름으로 두면 흐름 브랜치나 실행 도중에 생기는 `fixes` 흐름을 만들지 못한다.
