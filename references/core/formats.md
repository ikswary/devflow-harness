# devflow-harness 이름과 형식

스크립트(`scripts/`)와 에이전트가 함께 의존하는 형식이다. 여기를 고치면 스크립트도 함께 고친다. 메인과 모든 에이전트가 읽는다.

절마다 한 파일이다(5절만 읽기 판정 꼴과 실행 판정 몫 두 파일). "formats.md n절"은 아래 표의 n절 파일이다. 독자마다 읽는 파일은 `references/registry/readers.md`에 있다.

| 절 | 파일 |
| --- | --- |
| 1. 이름 | `references/formats/names.md` |
| 2. 실행 폴더 | `references/formats/run-folder.md` |
| 3. 머리 파일 `task.md` | `references/formats/task-file.md` |
| 4. 결과 파일 `result.md` (작성자) | `references/formats/result-file.md` |
| 5. 판정 파일 `judge.md` (읽기 판정) | `references/formats/judge-file.md` |
| 5. 판정 파일 — 실행 판정 몫 `judge-run.md` | `references/formats/judge-run-file.md` |
| 6. 그 밖의 파일 | `references/formats/run-files.md` |
| 7. 에이전트에 주는 프롬프트의 틀 | `references/formats/prompt.md` |
| 8. 에이전트의 반환 | `references/formats/return.md` |
