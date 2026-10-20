// 진행 대시보드 플러그인의 상태 계약. $.state 키는 여기 한 곳에만 선언한다.
// DashJudgment는 scripts/board_dash.py가 내는 판정 JSON schema 1을 그대로 옮긴 것이다.

export type DashStatus = '대기' | '진행' | '자체검증' | '승인대기' | '완료' | '보류' | '백로그'

export type DashElapsed = { kind: 'approval' | 'progress' | 'start_wait'; text: string }

export type DashTask = {
  id: string
  title: string
  kind: string
  status: DashStatus
  flow: string
  block: string
  group: string
  parent: string
  depends_on: string[]
  class: 'remaining' | 'folded'
  start: 'ready' | 'held' | 'undecidable' | null
  reason_text: string
  elapsed: DashElapsed | null
  waiting_user: string
  running_agent: string
  external_progress: string
  approval_requested: string
  started: string
  created: string
  approved: string
  n_decide: string
}

export type DashRun = { name: string; dir: string; status: string; run_md_unreadable: boolean; flow_cap: number }

export type DashFlow = { name: string; status: string; sync_pending: string[]; depends_on_flows: string[]; unreadable: boolean }

export type DashCounts = {
  by_status: Record<DashStatus, number>
  remaining: number
  folded: number
  unreadable: number
  approval: number
  waiting_user: number
  running_agent: number
  external_progress: number
}

export type DashJudgment = {
  schema: 1
  now: string
  workdir: string
  session: string | null
  message: null | '이 세션이 진행하는 실행 없음' | '세션 id를 알 수 없어 실행을 고르지 못함'
  run: DashRun | null
  tasks: DashTask[]
  unreadable: { id: string; why: 'UTF-8 아님' | '머리 없음' | 'status 값' }[]
  flows: DashFlow[]
  ready: string[]
  held: { id: string; reason_text: string }[]
  undecidable: { id: string; reason_text: string }[]
  queue: string[]
  counts: DashCounts
  folded_by_group: Record<string, Partial<Record<DashStatus, number>>>
  unclean: { id: string; keys: string[] }[]
}

// result: 마지막으로 성공한 판정(아직 없으면 null). error: 마지막 회차가 실패했으면 한 줄, 성공하면 ''.
// at: result·error를 적은 회차의 시각(epoch ms). invokedAt: devflow-harness가 불린 때(epoch ms), /clear 뒤 null.
export type DashState = { result: DashJudgment | null; error: string; at: number; invokedAt: number | null }

declare module 'claude-code' {
  interface PluginState {
    'devflow-harness': { judgment: DashState }
  }
}
