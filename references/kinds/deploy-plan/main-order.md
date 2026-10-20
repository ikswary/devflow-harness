# 배포 계획 task: 메인 순서

읽는 때: 메인이 배포 계획 task(`deploy-plan`)를 다룰 때.

- **배포 실행의 환경 순서**: 배포 계획이 승인되어 배포 실행 task를 만들 때, 같은 실행에 이 환경 뒤에 가는 환경(운영)의 배포 실행 task가 이미 있으면 그 `depends_on`에 지금 만든 id를 더한다. 이 환경이 뒤 환경이고 앞 환경의 배포 실행 task가 이미 있으면 지금 만든 task의 `depends_on`에 더한다(`spawn_children.py`는 아직 없는 id를 받지 않아 행에 적을 수 없다). `journal.md`에 한 줄.
