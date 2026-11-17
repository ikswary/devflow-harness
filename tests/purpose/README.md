# 목적 시험 (행동 회귀)

하네스를 고친 판이 사람에게 판단 재료를 실제로 주는지 본다. 지난 실행의 task 하나를 그 task가 시작할 때의 상태로
되돌린 사본에서 작성자 → 판정 → 화면을 실제 스크립트로 다시 돌리고, 결과를 모르는 승인자가 화면만 읽고 답한 것을
로컬 정답지와 대조한다. 원칙은 `docs/plugin-practices.md` 4절 「행동 회귀」다.

전체 pytest는 이 폴더를 모으지 않는다(시험 파일 이름 꼴이 없음). 준비 스크립트 자체는 `tests/py/test_purpose_setup.py`가
가짜 자료로 시험한다.

## 언제 돌리는가

- 판을 낼 때(`docs/plugin-practices.md` 5절 5번).
- 모델이 바뀔 때(에이전트 정의의 `model`이 고정이므로, 새 모델에서 같은 task를 다시 돈다).

## 자료와 정답지

자료와 정답지는 저장소에 두지 않는다. 자료에는 다른 프로젝트의 코드와 실행 기록이 들어 있고, 정답지가 저장소에 있으면
에이전트가 읽어 시험이 무효가 된다. 저장소 밖 로컬 폴더에 두고 경로로 넘긴다.

```
{자료 폴더}/
  {TID}/code/                  대상 프로젝트 코드 사본(그 task가 시작할 때의 커밋)
  {TID}/run/                   실행 폴더 사본(tasks/, flows/, decisions.md, recon.md …)
  {TID}/prior-run/decisions.md 앞 실행의 결정(머리 파일이 상대 경로로 가리킴)
{원래 run.md}                  원래 실행의 run.md(「요청 원문」·「이번 실행의 값」을 옮김)
{정답지}                       판단 지점과 그때의 실제 답. 에이전트에게 주지 않는다
```

## 준비

```
python tests/purpose/setup_task.py --data {자료 폴더} --task {TID} --out {출력 폴더} --source-run-md {원래 run.md} --run-name {실행 이름} --prior-name {앞 실행 이름}
```

- `--run-name`·`--prior-name`: 원래 실행 폴더 이름과 앞 실행 폴더 이름. 머리 파일이 `_workspace/{앞 실행 이름}/decisions.md`를
  상대 경로로 가리키므로 원래 이름 그대로 준다.
- 만드는 것: `{출력 폴더}/{TID}/code`(시험용 git 커밋 하나, `_workspace/`는 git에서 뺌), 실행 폴더
  `code/_workspace/{실행 이름}`, 표지 파일 `{출력 폴더}/{TID}/.purpose-sandbox`.
- 대상 task보다 늦게 만든 task, 대상 task의 결과·판정·묻기 흔적을 지우고, 머리 파일을 시작 때로 되돌린다
  (`started_version`과 run.md `harness_version`은 이 저장소 판본).
- 다시 돌리면 표지가 있는 출력 폴더만 지우고 새로 만든다. 표지 없는 폴더가 있거나, `--out`이 이 저장소 안이면서
  `_workspace/` 밖이면 종료 3으로 거부한다. 자료 꼴이 아니어도 종료 3이다.
- 코드 사본이 비어 있으면 `! 코드 사본이 비었음` 줄을 내고 빈 커밋을 만든다. 작성자가 코드를 읽어야 하는 task면 돌리기 전에
  자료의 코드 사본을 채운다.

## 차례

`{실행}`은 준비가 마지막 줄 `준비됨:`에 낸 실행 폴더다. 스크립트는 이 저장소의 `scripts/`를 쓴다.

1. 준비(위 명령).
2. `python scripts/run_position.py {실행}` 출력을 작성자 프롬프트의 `실행 위치:`에 넣는다.
3. 작성자: 하네스 프롬프트 틀(`references/formats/prompt.md`)에 `tests/purpose/prompts.md` 「작성자에게 덧붙일 것」을 더해 띄운다.
4. `python scripts/task_set.py {실행} {TID} --status 자체검증`
5. `python scripts/task_set.py {실행} {TID} --judge-start {판정자 이름}`
6. 읽기 판정자: 프롬프트 틀에 「판정자에게 덧붙일 것」을 더해 띄운다(1.3.0부터는 사실 검사를 먼저, `references/main/selfcheck.md`).
7. `python scripts/task_set.py {실행} {TID} --status 승인대기` 뒤 `python scripts/screen.py {실행} {TID} --save`로 화면을
   `tasks/{TID}/screen-shown.md`에 남긴다(재시도가 나면 하네스 차례대로 재작성·재판정을 먼저 돈다).
8. 결과를 모르는 승인자: 「결과를 모르는 승인자 지시문」을 그대로 준다. 화면 파일과 화면이 가리키는 펼침 경로만 읽게 한다.
9. 승인자의 답을 로컬 정답지와 대조하고, 비교 기록은 저장소 밖 작업 문서에 남긴다. 하네스를 고쳤으면 `CHANGELOG.md`에 행을 더한다.

- 비교는 고치기 전 판과 고친 판을 같은 task로 돌린다(원칙 문서 4절 「기준선과 나란히」).
- 저장소에 다른 프로젝트 이름과 사용자 경로를 쓰지 않는다. `tests/py/test_strings.py`가 일반 꼴을 보고, 비공개 낱말은 환경
  변수 `DEVFLOW_FORBIDDEN`(쉼표로 나눔)에 넣어 함께 본다.
