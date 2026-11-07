# 배포 계획 task: 메인 순서

읽는 때: 메인이 배포 계획 task(`deploy-plan`)를 다룰 때.

- **배포 실행의 환경 순서**: 배포 계획이 승인되어 배포 실행 task를 만들 때, 같은 실행에 이 환경 뒤에 가는 환경(운영)의 배포 실행 task가 이미 있으면 그 `depends_on`에 지금 만든 id를 더한다. 이 환경이 뒤 환경이고 앞 환경의 배포 실행 task가 이미 있으면 지금 만든 task의 `depends_on`에 더한다(`spawn_children.py`는 아직 없는 id를 받지 않아 행에 적을 수 없다). `journal.md`에 한 줄.
- **재사용**: 시작 전에 머리 파일 `split_criterion`에 `환경 dev`나 `환경 운영`을 적는다(제목에서 추측하지 않는다). 빠뜨려 `!` 줄이 나왔으면 작성자를 띄우기 전에 `task_set.py {실행 폴더} {id} split_criterion="환경 dev"`로 적고 `deploy_reuse.py {실행 폴더} {id} --decide`를 다시 부른다. `대기→진행`에서 `task_set.py`가 항목마다 재사용을 가르고 한 줄을 낸다. 그 줄을 사용자에게 보인다. 작성자에게 `tasks\{id}\reuse.md`를 경로로 준다. 재사용이면 판정 기준은 `references/kinds/deploy-plan/reuse.md` 「자체 검증」이다. 사람이 처음부터 쓰라고 하면 `deploy_reuse.py {실행 폴더} {id} --fresh "원문"`. 절차서 저장은 배포 실행이 `유지`로 `완료`될 때 스크립트가 한다.
