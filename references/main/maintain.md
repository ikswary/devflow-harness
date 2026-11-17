## 하네스를 고칠 때

- 판정자 정의, 판정자 공통(`references/roles/judge.md`), 형식 파일 `references/formats/judge-file.md`·`judge-run-file.md`의 판정 파일 규칙을 바꾸면 두 정의의 `def-version` 표지와 `kinds.DEF_VERSION_MIN`을 함께 올린다. [RP-06]
- 판정자 계약 판본을 설치할 때 원본과 런타임 adapter에 plugin·marketplace 판본, 두 정의·`DEF_VERSION_MIN`을 한 묶음으로 반영한다. 중간 상태에서는 판본 비교와 `agent_def_problems`가 새 task 시작 전에 막아야 한다. `2026-10-21-isolation1` 계약과 기존 완료 판정 문서는 고치지 않는다. 1.0.2보다 앞서 시작한 진행 task는 현재 단계만 시작 당시 계약으로 끝내고, 새 필드가 없는 옛 결과는 재사용하거나 shadow에 소급 편입하지 않는다.
- 테스트 시나리오는 `docs/test-scenarios.md`에 있다.
- 하네스를 고치면 변경 하나마다 하네스 저장소(`${CLAUDE_PLUGIN_ROOT}`)에 커밋한다(판본은 `.claude-plugin/plugin.json`의 `version`이어서, 커밋 안 된 변경은 무엇이 바뀌었는지 판본으로 가릴 수 없다).
- 전체 시험은 공용 venv python으로 `-m pytest -q -p no:cacheprovider -n auto`(병렬, `requirements-dev.txt`의 pytest-xdist). 커밋 전에 돌린다.
- 하네스를 고친 뒤 마른 시험(가짜 실행 폴더에서 보드·승인 화면·자식 만들기·재개만 돌려 보기)으로 확인한다. 변경 이력은 `CHANGELOG.md`.
- 판을 낼 때 `tests/py/reading.py`의 `BASELINE`을 그때 값(`python tests/py/reading.py budget`의 지금 값)으로 다시 잡고 `test_read_budget.py`의 `PENDING_OVER`를 비운다. 한 판 안의 증가는 `GROWTH` 몫까지이고, 넘기면 사유를 달아 보류한다(2026-11-17 사용자 결정).
- 고치는 원칙과 판을 낼 때의 점검(`claude plugin validate --strict .`, `claude plugin details devflow-harness`, 목적 시험)은 `docs/plugin-practices.md`다. 결함(스크립트가 문서대로 돌지 않음)은 바로 고치고 고치기 전에 실패하는 시험을 붙인다. 새 규칙은 같은 신호가 두 번 나올 때 넣고, 처음 본 신호는 CHANGELOG에 다음 판 후보로 적는다. 같은 규칙을 문서와 스크립트에 두면 둘을 묶는 시험을 둔다.
