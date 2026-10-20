## 7. 에이전트에 주는 프롬프트의 틀

작성자:
```
task: {task id} {제목} ({kind})
task 폴더: {절대 경로}
머리 파일: {절대 경로}\task.md  ← 범위와 판정 기준의 원천
task 정의: {등록표 `definition` 칸의 정의 파일 경로}
부모: {부모 task 폴더 절대 경로} (result.md와 task.md의 승인 기록)
실행 전체 결정: {절대 경로}\decisions.md
정본: {머리 파일 「정본의 절」이 가리키는 파일}
정찰: {절대 경로}\recon.md
(코드 task) 코드 폴더: {절대 경로} / 흐름 규약: {절대 경로}\conventions.md
결과를 쓸 곳: {task 폴더}\result.md
이번 지시에만 있는 것: {없으면 "없음"}
```

읽기 판정:
```
판정할 task: {task id} {제목} ({kind})
머리 파일: {절대 경로}\task.md  ← 판정 기준
task 정의: {등록표 `definition` 칸의 정의 파일 경로} (전체), …\references\roles\writer.md
원 산출물: {정본의 절 / 코드 폴더와 변경 범위 / 테스트 파일 / 로그. 화면 설계는 「건드릴 파일」의 ui 정본과 와이어프레임, 대조 원천으로 기획 「화면 흐름」·상세 정본·개요 「용어」·ui\rules.md}
작성자 결과: {task 폴더}\result.md  ← 판정을 마친 뒤 대조용으로만 연다
판정을 쓸 곳: {task 폴더}\judge.md
```

실행 판정:
```
판정할 task: {task id}
코드 폴더: {절대 경로}
정찰(명령과 기준선): {절대 경로}\recon.md
돌릴 것: {빌드, 관련 테스트 명령}
변이 확인: {task 폴더}\result.md 「변이 확인 지시」 절
판정을 쓸 곳: {task 폴더}\judge-run.md
로그를 쓸 곳: {task 폴더}\logs\
```
