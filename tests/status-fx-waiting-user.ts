// 시험 재료: 사용자 할 일 대기(waiting_user)가 있는 실행과 없는 실행의 판정. 손으로 고치지 않는다.
// DASH_A·DASH_B: 사본 ac3a·ac3b(ac3b만 의존이 풀린 대기 task T010에 waiting_user)에 돌린 board_dash.py의 판정.
// READY_B: ac3b에 돌린 board.py --ready의 출력.
import type { DashJudgment } from '../types'

export const DASH_A: DashJudgment = {
  "schema": 1,
  "now": "2026-10-06 10:00",
  "workdir": "D:\\workspace\\myapp\\_workspace\\2026-01-01-example\\tasks\\T001\\dryrun\\ac3a",
  "session": "S",
  "message": null,
  "run": {
    "name": "X",
    "dir": "D:\\workspace\\myapp\\_workspace\\2026-01-01-example\\tasks\\T001\\dryrun\\ac3a\\_workspace\\X",
    "status": "진행",
    "run_md_unreadable": false,
    "flow_cap": 2
  },
  "tasks": [
    {
      "id": "T001",
      "title": "설계",
      "kind": "design",
      "status": "완료",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "",
      "depends_on": [],
      "class": "folded",
      "start": null,
      "reason_text": "",
      "elapsed": null,
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "2026-10-06 09:00",
      "n_decide": ""
    },
    {
      "id": "T010",
      "title": "설계 갈래 하나",
      "kind": "design",
      "status": "대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [],
      "class": "remaining",
      "start": "ready",
      "reason_text": "",
      "elapsed": {
        "kind": "start_wait",
        "text": "1시간 0분"
      },
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": ""
    },
    {
      "id": "T011",
      "title": "설계 갈래 둘",
      "kind": "design",
      "status": "대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [],
      "class": "remaining",
      "start": "ready",
      "reason_text": "",
      "elapsed": {
        "kind": "start_wait",
        "text": "1시간 0분"
      },
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": ""
    },
    {
      "id": "T020",
      "title": "설계 갈래 셋",
      "kind": "design",
      "status": "승인대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [],
      "class": "remaining",
      "start": null,
      "reason_text": "",
      "elapsed": {
        "kind": "approval",
        "text": "30분"
      },
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "2026-10-06 09:30",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": "0"
    },
    {
      "id": "T030",
      "title": "설계 갈래 넷",
      "kind": "design",
      "status": "대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [
        "T020"
      ],
      "class": "remaining",
      "start": null,
      "reason_text": "",
      "elapsed": null,
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": ""
    }
  ],
  "unreadable": [],
  "flows": [],
  "ready": [
    "T010",
    "T011"
  ],
  "held": [],
  "undecidable": [],
  "queue": [
    "T020"
  ],
  "counts": {
    "by_status": {
      "대기": 3,
      "진행": 0,
      "자체검증": 0,
      "승인대기": 1,
      "완료": 1,
      "보류": 0,
      "백로그": 0
    },
    "remaining": 4,
    "folded": 1,
    "unreadable": 0,
    "approval": 1,
    "waiting_user": 0,
    "running_agent": 0,
    "external_progress": 0
  },
  "folded_by_group": {
    "기타": {
      "완료": 1
    }
  },
  "unclean": []
}

export const DASH_B: DashJudgment = {
  "schema": 1,
  "now": "2026-10-06 10:00",
  "workdir": "D:\\workspace\\myapp\\_workspace\\2026-01-01-example\\tasks\\T001\\dryrun\\ac3b",
  "session": "S",
  "message": null,
  "run": {
    "name": "X",
    "dir": "D:\\workspace\\myapp\\_workspace\\2026-01-01-example\\tasks\\T001\\dryrun\\ac3b\\_workspace\\X",
    "status": "진행",
    "run_md_unreadable": false,
    "flow_cap": 2
  },
  "tasks": [
    {
      "id": "T001",
      "title": "설계",
      "kind": "design",
      "status": "완료",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "",
      "depends_on": [],
      "class": "folded",
      "start": null,
      "reason_text": "",
      "elapsed": null,
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "2026-10-06 09:00",
      "n_decide": ""
    },
    {
      "id": "T010",
      "title": "설계 갈래 하나",
      "kind": "design",
      "status": "대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [],
      "class": "remaining",
      "start": "held",
      "reason_text": "사용자 할 일 대기",
      "elapsed": {
        "kind": "start_wait",
        "text": "1시간 0분"
      },
      "waiting_user": "비밀 파일 준비",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": ""
    },
    {
      "id": "T011",
      "title": "설계 갈래 둘",
      "kind": "design",
      "status": "대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [],
      "class": "remaining",
      "start": "ready",
      "reason_text": "",
      "elapsed": {
        "kind": "start_wait",
        "text": "1시간 0분"
      },
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": ""
    },
    {
      "id": "T020",
      "title": "설계 갈래 셋",
      "kind": "design",
      "status": "승인대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [],
      "class": "remaining",
      "start": null,
      "reason_text": "",
      "elapsed": {
        "kind": "approval",
        "text": "30분"
      },
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "2026-10-06 09:30",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": "0"
    },
    {
      "id": "T030",
      "title": "설계 갈래 넷",
      "kind": "design",
      "status": "대기",
      "flow": "",
      "block": "",
      "group": "기타",
      "parent": "T001",
      "depends_on": [
        "T020"
      ],
      "class": "remaining",
      "start": null,
      "reason_text": "",
      "elapsed": null,
      "waiting_user": "",
      "running_agent": "",
      "external_progress": "",
      "approval_requested": "",
      "started": "",
      "created": "",
      "approved": "",
      "n_decide": ""
    }
  ],
  "unreadable": [],
  "flows": [],
  "ready": [
    "T011"
  ],
  "held": [
    {
      "id": "T010",
      "reason_text": "사용자 할 일 대기"
    }
  ],
  "undecidable": [],
  "queue": [
    "T020"
  ],
  "counts": {
    "by_status": {
      "대기": 3,
      "진행": 0,
      "자체검증": 0,
      "승인대기": 1,
      "완료": 1,
      "보류": 0,
      "백로그": 0
    },
    "remaining": 4,
    "folded": 1,
    "unreadable": 0,
    "approval": 1,
    "waiting_user": 1,
    "running_agent": 0,
    "external_progress": 0
  },
  "folded_by_group": {
    "기타": {
      "완료": 1
    }
  },
  "unclean": []
}

export const READY_B = "지금 시작할 수 있는 task 1개\n- T011 설계 갈래 둘 [design]\n의존은 풀렸지만 지금은 못 띄움 1개(공유 자원 잠금은 메인이 따로 본다)\n- T010 설계 갈래 하나 [design] (사용자 할 일 대기)"
