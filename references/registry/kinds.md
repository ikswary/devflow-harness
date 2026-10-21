## 1. kind 17

| kind | block | definition | writers | read_judge | run_judge | notify | stages | writes_code_dir | auto_depends_in_flow | needs_touch_files | writes_canon | readback | commit_required | verify_family | glyph | children | engine_hooks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| question | 질문 | question.md | requirements-writer, cause-writer, design-writer | always | never | 네 칸 모두 0 (`all_cells`) | — | — | — | — | 예 | — | — | — | Q | req-overview, root-cause, design | — |
| brief | 기획 | brief.md | requirements-writer | always | never | 승인만 (`none`) | — | — | — | — | 예 | — | — | — | B | req-detail, ui-design, design | — |
| req-overview | 요구사항 | req-overview.md | requirements-writer | always | never | 승인만 (`none`) | — | — | — | — | 예 | — | — | — | Q | brief | — |
| req-detail | 요구사항 | req-detail.md | requirements-writer | always | never | 승인만 (`none`) | — | — | — | — | 예 | — | — | — | Q | design | — |
| root-cause | 원인 분석 | root-cause.md | cause-writer | always | always | 승인만 (`none`) | — | 예 | — | — | — | — | — | — | C | implementation, flow-verify, wrap-up, design | code_dir_writes |
| ui-design | 설계 | ui-design.md | design-writer | always | never | 승인만 (`none`) | — | — | — | — | 예 | — | — | — | U | design | — |
| design | 설계 | design.md | design-writer | always | never | 승인만 (`none`) | — | — | — | — | 예 | — | — | — | S | implementation, flow-verify, full-verify, wrap-up, deploy-plan | — |
| implementation | 구현 | implementation.md | code-writer | conditional | always | 「정해」「하실」 0, origin 사용자면 불가 (`by_decide`) | — | 예 | 예 | 예 | — | 예 | 예 | — | (빈 글자) | — | machine_check, required_judges, flow_auto_depends, touch_files, readback, from_answer, flow_md |
| fix | 구현 | implementation.md | code-writer | always | always | 「정해」「하실」 0, origin 사용자면 불가 (`by_decide`) | — | 예 | 예 | 예 | — | 예 | 예 | — | F | — | fix_generation, machine_check, required_judges, flow_auto_depends, touch_files, readback, from_answer, flow_md |
| change | (빈 값) | change.md | requirements-writer, design-writer | always | never | 「정해」「하실」 0, origin 사용자면 불가 (`by_decide`) | — | — | — | — | 예 | — | — | — | X | — | canon_check, replace, from_answer |
| flow-verify | 검증 | verify.md | verify-writer | always | never | 승인만 (`none`) | — | — | — | — | — | — | — | 예 | V | fix, reverify | start_condition, child_generation_zero |
| reverify | 검증 | verify.md | verify-writer | always | never | 네 칸 모두 0 (`all_cells`) | — | — | — | — | — | — | — | 예 | R | fix, reverify | start_condition, generation_plus_one, over_cap_backlog |
| merge | 구현 | merge.md | main, code-writer | conditional | always | 단계 (`all_cells`) | 실행승인, 실행, 결과승인, 끝 | 예 | — | — | — | — | rules2 | — | M | — | stage_rule, exec_points, merge_condition, required_judges |
| full-verify | 검증 | verify.md | verify-writer | always | never | 승인만 (`none`) | — | — | — | — | — | — | — | 예 | V | fix, reverify | start_condition, generation_zero |
| wrap-up | 마무리 | wrap-up.md | release-writer, main | always | always | 단계 (`none`) | 실행승인, 실행, 결과승인, 끝 | — | — | — | — | — | — | — | W | — | stage_rule, exec_points, exported_commit, start_condition, collect_input |
| deploy-plan | 배포 | deploy-plan.md | release-writer | always | never | 불가 (`never`) | — | — | — | — | — | — | — | — | D | deploy-exec | exec_reads_plan_cmd |
| deploy-exec | 배포 | deploy-exec.md | main, run-judge, release-writer | conditional | always | 단계 (`never`) | 사전조건, 직전확인, 명령, 확인, 결과승인, 브랜치, 기록, 넣기승인, 넣기, 끝 | — | — | — | — | — | — | — | E | — | stage_rule, exec_parent_plan, deploy_outcome |

알림 칸: 낱말은 `stages`가 있으면 단계, 없으면 `notify` 값의 낱말(괄호 안이 `notify` 값).

