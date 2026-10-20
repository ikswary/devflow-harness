## 5. 메인이 만드는 task

부모가 행을 쓰지 않는 task는 메인이 `task_set.py {실행 폴더} new`로 머리 파일을 만든다. 메인이 쓰는 판정 기준도 공통 계약 「판정 기준은 확인할 수 있어야 한다」를 따른다(「판정 시점의 사실」).
- 명령을 돌려 판정하는 기준(빌드, 테스트, 린트, 정적 검사)은 "기준선 밖 실패 0"처럼 `recon.md` 기준선과 비교하는 문장으로 쓴다. [RP-04]

| task | 범위 | 판정 기준 |
|---|---|---|
| 질문(T001) | 요청 원문 | `references/kinds/question.md` |
| 변경 | 계기(사용자 원문 또는 지적의 위치를 `origin`에. 사용자 답이면 `new --from-answer {task id}`가 채움) | `references/kinds/change.md`: 계기가 그대로 반영됐는가, 그 블록 기준 가운데 바뀐 절, 영향받는 task 목록(정본만. 코드를 고치면 `fix`이고 `references/kinds/implementation.md`. `--from-answer`가 kind를 정한다) |
| 합치기 | 그 흐름 브랜치의 커밋 전부 | `references/kinds/merge.md` |
| 원인 분석(실행 도중 원인 모르는 실패) | 실패의 기록 위치 | `references/kinds/root-cause.md` |
| 받아오기 충돌·실패의 수정(`fix`) | 받아온 출처와 충돌 파일·실패 테스트 | `references/kinds/merge.md` 「하는 일」(받아오기 5), 일반 수정 task와 같은 자체 검증(읽기 판정 받음) |
| 「묻는다」 지적의 수정(답을 받은 뒤)과 그 재검증 | 지적 ID와 답 | 수정은 `references/kinds/implementation.md`, 재검증은 `references/kinds/verify.md`(`--ready`의 「재검증 없는 수정」이 빠진 재검증을 보인다) |
| 배포 다시 계획(`deploy-plan`, 환경마다 하나) | 낡은 계획 task와 새로 올릴 커밋 | `references/kinds/deploy-plan.md`. 언제: 배포 계획이 승인된 뒤 그 커밋 이후 코드가 개발 기준 브랜치에 들어가 다시 올려야 할 때(앞 환경 배포 뒤 확인 실패 → 수정 등). 아직 끝나지 않은 그 커밋의 배포 계획·실행 task는 `보류`로 닫고 이유와 새 task id를 적는다. 승인은 그 커밋의 배포에만 유효하므로 계획을 고치는 변경 task가 아니라 새 task다(배포 계획은 정본이 아니다) |
| 기획(`brief`, 흐름 없음) — 과도기 | 개요 정본(이번 회차 묶음만), 질문 답, `decisions.md`, 요청이 가리키는 문서·캡처 경로 | `references/kinds/brief.md` 「자체 검증」. 언제: 요구사항 개요가 기획 행 없이 끝났을 때. `depends_on` = 개요와 아직 안 끝난 개요 변경 task. 상세 행이 이미 있으면 기획은 상세 행을 쓰지 않고(범위에 그 id들을 적는다) 화면 설계·UI 규약 행만 쓰며, 상세가 옛 규칙으로 이미 화면 설계 행을 썼으면 그 묶음의 화면 설계 행도 쓰지 않는다 |
| 화면 설계(`ui-design`) — 상세가 기획의 화면 유무를 뒤집었을 때 | 그 묶음의 화면 목록(기획)과 상세 정본 | `references/kinds/ui-design.md` 「자체 검증」. `depends_on` = 그 상세(와 UI 규약 task). 만든 직후 그 묶음 설계 task의 `depends_on`에 더한다. 반대로 화면이 없어진 묶음의 화면 설계 task는 `--reason`으로 `보류` |
