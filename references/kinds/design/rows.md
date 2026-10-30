# 설계 task: 자식 행의 kind와 인프라 결정

읽는 때: 설계 task가 자식 행을 쓰거나 판정자가 자식 목록·결정 지도를 볼 때.

- 코드 행의 kind: `closes_ac`에 화면 id가 붙은 인수 기준이 있으면 `fe-implementation`(화면과 서버가 섞이면 나누거나 fe), 서버 코드는 `be-implementation`(공용 형식을 만들거나 바꾸면 「시그니처와 결정 번호」에 `[계약]`), 그 밖(마이그레이션·배포 설정 포함)은 `implementation`. 문서만 건드리는 행이 앞 행의 결과를 쓰면 `depends_on`에 적는다.
- 「확인 안 된 것」에 `[탐침]`을 붙인 가정마다 `probe` 행이 있다. 표시했는데 행이 없으면 실패.
- 결정 지도에 `[Q1]`·`[Q3]`이 붙은 결정이 있는데 실행에 `infra-design` task가 없으면 실패. 있으면 `design\infra.md`와 어긋나는 결정이 실패.
