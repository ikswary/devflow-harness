// 시험 재료: task 10개짜리 실행 사본에 board_dash.py와 board.py --ready를 돌린 출력. 손으로 고치지 않는다.
import type { DashJudgment } from '../types'

export const DASH = {
  "schema": 1,
  "now": "2026-10-06 10:00",
  "workdir": "ac14",
  "session": "S",
  "message": null,
  "run": {"name": "F14", "dir": "ac14\\_workspace\\F14", "status": "진행", "run_md_unreadable": false, "flow_cap": 2},
  "tasks": [
    {"id": "T001", "title": "제목 T001", "kind": "design", "status": "완료", "flow": "", "block": "", "group": "기타", "parent": "", "depends_on": [], "class": "folded", "start": null, "reason_text": "", "elapsed": null, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "2026-10-06 09:00", "n_decide": ""},
    {"id": "T002", "title": "제목 T002", "kind": "implementation", "status": "진행", "flow": "a", "block": "", "group": "a", "parent": "T001", "depends_on": [], "class": "remaining", "start": null, "reason_text": "", "elapsed": {"kind": "progress", "text": "50분"}, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "2026-10-06 09:10", "created": "", "approved": "", "n_decide": ""},
    {"id": "T003", "title": "제목 T003", "kind": "implementation", "status": "자체검증", "flow": "b", "block": "", "group": "b", "parent": "T001", "depends_on": [], "class": "remaining", "start": null, "reason_text": "", "elapsed": {"kind": "progress", "text": "?"}, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "", "n_decide": ""},
    {"id": "T010", "title": "제목 T010", "kind": "design", "status": "대기", "flow": "", "block": "", "group": "기타", "parent": "T001", "depends_on": [], "class": "remaining", "start": "ready", "reason_text": "", "elapsed": {"kind": "start_wait", "text": "1시간 0분"}, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "", "n_decide": ""},
    {"id": "T011", "title": "제목 T011", "kind": "implementation", "status": "대기", "flow": "a", "block": "", "group": "a", "parent": "T001", "depends_on": [], "class": "remaining", "start": "held", "reason_text": "폴더 사용 중", "elapsed": {"kind": "start_wait", "text": "1시간 0분"}, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "", "n_decide": ""},
    {"id": "T012", "title": "제목 T012", "kind": "implementation", "status": "대기", "flow": "c", "block": "", "group": "c", "parent": "T001", "depends_on": [], "class": "remaining", "start": "held", "reason_text": "받아오기 먼저, 흐름 상한 2", "elapsed": {"kind": "start_wait", "text": "1시간 0분"}, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "", "n_decide": ""},
    {"id": "T013", "title": "제목 T013", "kind": "implementation", "status": "대기", "flow": "d", "block": "", "group": "d", "parent": "T001", "depends_on": [], "class": "remaining", "start": "held", "reason_text": "흐름 상한 2", "elapsed": {"kind": "start_wait", "text": "1시간 0분"}, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "", "n_decide": ""},
    {"id": "T014", "title": "제목 T014", "kind": "full-verify", "status": "대기", "flow": "", "block": "", "group": "기타", "parent": "T001", "depends_on": [], "class": "remaining", "start": "held", "reason_text": "안 합친 흐름: a, b, c, d", "elapsed": {"kind": "start_wait", "text": "1시간 0분"}, "waiting_user": "", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "", "n_decide": ""},
    {"id": "T015", "title": "제목 T015", "kind": "design", "status": "대기", "flow": "", "block": "", "group": "기타", "parent": "T001", "depends_on": [], "class": "remaining", "start": "held", "reason_text": "사용자 할 일 대기", "elapsed": {"kind": "start_wait", "text": "1시간 0분"}, "waiting_user": "비밀 파일 준비", "running_agent": "", "external_progress": "", "approval_requested": "", "started": "", "created": "", "approved": "", "n_decide": ""},
  ],
  "unreadable": [],
  "flows": [{"name": "a", "status": "진행", "sync_pending": [], "depends_on_flows": [], "unreadable": false}, {"name": "b", "status": "진행", "sync_pending": [], "depends_on_flows": [], "unreadable": false}, {"name": "c", "status": "진행", "sync_pending": ["T016"], "depends_on_flows": [], "unreadable": false}, {"name": "d", "status": "진행", "sync_pending": [], "depends_on_flows": [], "unreadable": false}],
  "ready": ["T010"],
  "held": [{"id": "T011", "reason_text": "폴더 사용 중"}, {"id": "T012", "reason_text": "받아오기 먼저, 흐름 상한 2"}, {"id": "T013", "reason_text": "흐름 상한 2"}, {"id": "T014", "reason_text": "안 합친 흐름: a, b, c, d"}, {"id": "T015", "reason_text": "사용자 할 일 대기"}],
  "undecidable": [],
  "queue": [],
  "counts": {"by_status": {"대기": 6, "진행": 1, "자체검증": 1, "승인대기": 0, "완료": 1, "보류": 0, "백로그": 0}, "remaining": 8, "folded": 1, "unreadable": 0, "approval": 0, "waiting_user": 1, "running_agent": 0, "external_progress": 0},
  "folded_by_group": {"기타": {"완료": 1}},
  "unclean": [],
} as DashJudgment

export const READY = "지금 시작할 수 있는 task 1개\n- T010 제목 T010 [design]\n의존은 풀렸지만 지금은 못 띄움 5개(공유 자원 잠금은 메인이 따로 본다)\n- T011 제목 T011 [implementation] (폴더 사용 중)\n- T012 제목 T012 [implementation] (받아오기 먼저, 흐름 상한 2)\n- T013 제목 T013 [implementation] (흐름 상한 2)\n- T014 제목 T014 [full-verify] (안 합친 흐름: a, b, c, d)\n- T015 제목 T015 [design] (사용자 할 일 대기)\n"
