## 2. 실행 폴더

```
run.md            실행 머리 (메인)
decisions.md      실행 전체 결정 (메인)
journal.md        실행 경과, 덧붙이기 전용 (메인)
recon.md          프로젝트 정찰, 기준선, 잠금·합치기 관례 (메인)
spec\overview.md, spec\{묶음}.md      요구사항 정본
spec\brief.md                         기획 정본 (개요 뒤·상세 앞. 요구사항 블록이 있는 실행에 늘)
ui\rules.md, ui\{묶음}.md             화면 정본 (UI 규약, 묶음별 화면 설계서. 화면이 있는 묶음만)
ui\wireframes\{묶음}.html             와이어프레임 (화면 설계 작성자. 제품 코드가 아님)
design\{흐름}.md                      설계 정본
tasks\{id}\task.md      머리 (스크립트: spawn_children.py·task_set.py)
tasks\{id}\criteria.orig.md, criteria.amend{n}.md, criteria.ack.md   만들 때의 판정 기준, 판정 기준 정정, R2 점검 확인 때의 판정 기준 (스크립트)
tasks\{id}\result.md    결과 (작성자). result.pre-screen.md는 「승인 화면」만 다시 쓰기 전의 사본 (스크립트)
tasks\{id}\judge.md     읽기 판정 (읽기 판정자), judge-run.md 실행 판정 (실행 판정자). 늘 최신 판정
tasks\{id}\judge.r{n}.md, judge-run.r{n}.md   재판정 전에 보관한 n번째 판정 (`task_set.py --archive-judge`)
tasks\{id}\main-run.md  메인이 규칙대로 직접 한 일(직접 실행, 기계 대조, 준비된 선택지 반영) (메인)
tasks\{id}\exec.md      밖으로 나간 명령의 기록 (exec.py). approved-cmds-{지점}.md 승인 때 얼린 명령 (exec.py)
tasks\{id}\uncommitted.patch   보류로 치운 커밋 안 된 변경 (메인, 사용자가 고를 때만)
tasks\{id}\revised\     변경 task가 쓴 정본의 고친 판 (작성자)
tasks\{id}\logs\        원시 로그
flows\{흐름}\flow.md         (첫 코드 task 행과 함께 spawn_children.py가 만들고, 메인이 폴더를 만들 때 고침)
flows\{흐름}\conventions.md  (스크립트)
```
