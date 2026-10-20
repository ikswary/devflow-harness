# 요구사항 상세 task: 메인 순서

읽는 때: 메인이 요구사항 상세 task(`req-detail`)를 다룰 때.

- 공통이 아닌 묶음의 설계 task는 공통 설계 task에 의존하게 한다(`depends_on`에 더한다). 화면 설계 task는 그 묶음의 상세와 UI 규약 task(`화면 설계 — UI 규약`, 기획이 새로 그리는 화면이 있고 `ui\rules.md`가 없을 때 행을 쓴다)에 의존한다(기획이 형제 제목으로 적는다). 상세를 띄울 때 메인은 프롬프트 「이번 지시에만 있는 것」에 그 묶음의 화면 설계 task id를 준다(상세가 설계 행의 `depends_on`에 적는다. 빠졌으면 자식을 만든 직후 `task_set.py {설계 id} depends_on=[…]`로 더하고 journal에 한 줄).
