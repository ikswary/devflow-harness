## 하네스를 고칠 때

- 판정자 정의, 판정자 공통(`references/roles/judge.md`), 형식 파일 `references/formats/judge-file.md`·`judge-run-file.md`의 판정 파일 규칙을 바꾸면 두 정의의 `def-version` 표지와 `kinds.DEF_VERSION_MIN`을 함께 올린다. [RP-06]
- 판정자 계약 판본을 설치할 때 원본과 런타임 adapter에 plugin·marketplace 판본, 두 정의·`DEF_VERSION_MIN`을 한 묶음으로 반영한다. 중간 상태에서는 판본 비교와 `agent_def_problems`가 새 task 시작 전에 막아야 한다. `2026-10-21-isolation1` 계약과 기존 완료 판정 문서는 고치지 않는다. 1.0.2보다 앞서 시작한 진행 task는 현재 단계만 시작 당시 계약으로 끝내고, 새 필드가 없는 옛 결과는 재사용하거나 shadow에 소급 편입하지 않는다.
- 테스트 시나리오는 `docs/test-scenarios.md`에 있다.
- 하네스를 고치면 변경 하나마다 하네스 저장소(`${CLAUDE_PLUGIN_ROOT}`)에 커밋한다(판본은 `.claude-plugin/plugin.json`의 `version`이어서, 커밋 안 된 변경은 무엇이 바뀌었는지 판본으로 가릴 수 없다).
- 하네스를 고친 뒤 마른 시험(가짜 실행 폴더에서 보드·승인 화면·자식 만들기·재개만 돌려 보기)으로 확인한다. 변경 이력은 `CHANGELOG.md`.
