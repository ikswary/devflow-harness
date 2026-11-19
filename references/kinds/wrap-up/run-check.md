# 마무리 task: 실행 판정

읽는 때: 실행 판정자가 마무리 task(`wrap-up`)의 내보낼 commit을 검증할 때.

- 메인이 문서 변경까지 커밋한 흐름·통합 폴더의 깨끗한 HEAD에서, 실행 승인 전에 최종 CI를 돌린다. 먼저 `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_set.py {실행 폴더} {id} --inherit-ci`로 원천을 본다.
  - 같은 코드: 합치기 원천은 commit이 `문서 커밋 전 끝`(`{base}`), 코드 task 원천은 `git rev-parse {base}^{tree}`가 그 tree이고, `git diff --name-only {base} HEAD`가 이 마무리의 문서 커밋 파일뿐이다.
  - 같으면 `recon.md` 「문서를 읽는 검사」, 생성 대조, 결과물을 시험하면 HEAD 빌드만 돌리고 `- 범위: 이어받은 전체 검증`, `- 이어받은 CI: {원천 id} {commit}`, `- 그 뒤 바뀐 파일: {n}개({경로})`를 쓴다.
  - 원천이 없거나 다르면 전체 검증을 새로 돌리고 `- 범위: 전체 검증`이다.
- `judge-run.md`의 공통 두 절과 `## 최종 배포 후보 CI`를 쓴다. `검증 commit`은 검사한 HEAD의 전체 해시, `검증 artifact`는 `judge-run.md` 서식의 값이다.
- 프로젝트 설정에 생성 명령이 있으면 `project_docs.py {실행 폴더} {id} --generate {폴더} --check`도 돌린다. 다르면 「통과 못 한 기준」이다. 명령이 실패했거나 시간을 넘긴 것은 사유만 판정 파일에 적는다.
- 실패하면 그 시험만 프롬프트가 준 문서 커밋 전 끝에서 다시 돌려 `## 최종 CI 실패 원인`에 `- 원인: 문서`(그 끝은 통과)나 `코드`(그 끝도 실패)와 근거를 쓴다.
