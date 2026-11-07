## 2. 실행 폴더

```
run.md            실행 머리 (메인). docs_base_commit: 기준본을 뜬 시작 커밋 (project_docs.py)
decisions.md      실행 전체 결정 (메인)
journal.md        실행 경과, 덧붙이기 전용 (메인)
recon.md          프로젝트 정찰, 기준선, 잠금·합치기 관례 (메인)
baseline-run.md   기준선 측정 (실행 판정자)
run-map.md        실행 지도 (visual.py --run. 읽는 자료이고, 정본과 어긋나면 다시 만든다)
spec\overview.md, spec\{묶음}.md      요구사항 정본
spec\brief.md                         기획 정본 (개요 뒤·상세 앞. 요구사항 블록이 있는 실행에 늘)
ui\rules.md, ui\{묶음}.md             화면 정본 (UI 규약, 묶음별 화면 설계서. 화면이 있는 묶음만)
ui\wireframes\{묶음}.html             와이어프레임 (화면 설계 작성자. 제품 코드가 아님)
design\{흐름}.md                      설계 정본
design\infra.md                       인프라 결정 정본 (실행에 하나)
base\docs\…                           프로젝트 문서의 기준본. 고치지 않는다 (project_docs.py. 방법 문서 `project-docs`)
approved\hashes.md, approved\{정본 경로}   승인 해시와 그때의 사본 (task 완료 전이, apply_revision.py). approved\asked\{id}\ 물을 때의 판
generated-cache\    코드 끝별 생성 명령 결과 (project_docs.py)
inserted\docs\…, inserted-ours\docs\…     넣은 글과 넣기 전 프로젝트 쪽 글 (project_docs.py --insert)
tasks\{id}\task.md      머리 (스크립트: spawn_children.py·task_set.py)
tasks\{id}\criteria.orig.md, criteria.amend{n}.md, criteria.ack.md   만들 때의 판정 기준, 판정 기준 정정, R2 점검 확인 때의 판정 기준 (스크립트)
tasks\{id}\result.md    결과 (작성자). result.pre-screen.md는 「승인 화면」만 다시 쓰기 전의 사본 (스크립트)
tasks\{id}\judge.md     읽기 판정 (읽기 판정자), judge-run.md 실행 판정 (실행 판정자). 늘 최신 판정
tasks\{id}\judge.r{n}.md, judge-run.r{n}.md   재판정 전에 보관한 n번째 판정 (`task_set.py --archive-judge`)
tasks\{id}\judge.plan.md  탐침 계획 단계의 읽기 판정 (`stage=기록` 때 `task_set.py`가 judge.md를 옮김)
tasks\{id}\screen-main.md  승인 화면의 메인용 블록(이상 신호, 확인 방법) 전문 (screen.py). screen-shown.md 사람에게 물은 화면 (--save). sheet.html 브라우저 한 장 (visual.py --sheet)
tasks\{id}\review.md   흐름 리뷰의 접어 둔 근거: 인수 기준 표, 알림 task의 칸 모음 (screen.py). review-head.md 보인 칸 8, 9 (visual.py)
tasks\{id}\docs-insert.md  넣을 산출물 표, docs-choice.md 같은 절 두 곳의 답 (project_docs.py --insert). wrap-review.md  실행 전체 요약 (visual.py --wrap-review). approved-cmds-실행.md 사람 답 없이 얼린 고정 꼴 (exec.py)
tasks\{id}\places.md   코드 확인 곳과 처리 (screen.py --places, task_set.py --record). cards\{키}.shown.md 처음 낸 카드, cards\{키}.tree.md 낸 폴더 표 (screen.py --card)
tasks\{id}\main-run.md  메인이 규칙대로 직접 한 일(직접 실행, 기계 대조, 준비된 선택지 반영) (메인)
tasks\{id}\exec.md      밖으로 나간 명령의 기록 (exec.py). approved-cmds-{지점}.md 승인 때 얼린 명령 (exec.py)
tasks\{id}\design-copy\ 코드 task가 시작할 때 뜬 「정본의 절」 사본과 hashes.md (task_set.py)
tasks\{id}\parked.patch, repro.patch   치운 커밋 안 된 변경 (task_set.py --park. 옛 task의 보류는 uncommitted.patch)
tasks\{id}\revised\     변경 task가 쓴 정본의 고친 판 (작성자)
tasks\{id}\logs\        원시 로그
flows\{흐름}\flow.md         (첫 코드 task 행과 함께 spawn_children.py가 만들고, 메인이 폴더를 만들 때 고침)
flows\{흐름}\conventions.md  (스크립트)
flows\{흐름}\insert-checks\{id}.md  칸의 커밋을 cherry-pick으로 넣은 뒤 확인 (실행 판정자)
```

실행 밖: `_workspace\policies\docs-state.md` 작성 문서의 지키는 경로, 기준 커밋, 닫힌 위험 항목 (project_docs.py).
