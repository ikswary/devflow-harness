// 입력창 위 띠의 줄을 만드는 순수 함수: 요약 줄, 띠의 흐름과 버튼, 띠 전체 줄 목록, 실행 없음 한 줄, 그것을 감싸는 테두리.
// $를 쓰지 않고 claude-code에서는 아무것도 가져오지 않는다. 판정은 다시 하지 않고 판정 JSON 값 그대로 쓴다.
// 흐름 줄·지도·버튼 줄 나누기·칸 셈은 panel P1의 panel-map·panel-text를 불러 쓴다(고치지 않음).
import type { DashJudgment, DashState } from '../types'
import { ALL, buttonRows, laneLines, lanesOf, laneSuffix, mapRows, shownSuffix, unitOf } from './panel-map'
import type { Lane, PanelButton } from './panel-map'
import { cells, fitEnd } from './panel-text'

export type BandView = { unit: string; expanded: boolean }

export type Row = { kind: 'text'; text: string; dim?: boolean } | { kind: 'buttons'; buttons: PanelButton[] }

const SHOWN_STATES = ['대기', '진행', '자체검증', '승인대기'] as const
// 흐름 버튼의 단축키: 흐름 차례로 a(전체)·e(패널의 펼치기)·m(지도)·p(패널 열기)를 뺀 소문자. 넘는 흐름은 단축키 없음.
const LANE_HOTKEYS = [...'bcdfghijklnoqrstuvwxyz']
// 띠의 흐름별 상태 줄: 이름·flow.md 상태·받아오기 대기만.
const LANE_OPT = { misalign: false, folded: false, expanded: false }
// 엔진이 plain 버튼을 그리는 꼴(reference.md:94): 단축키가 있으면 "{hotkey}: {label}", 없으면 이름만.
const buttonText = (b: PanelButton) => (b.hotkey ? `${b.hotkey}: ${b.label}` : b.label)

// 승인대기이고 approval_requested가 있고 경과가 "?"가 아닌 task 가운데 approval_requested가 가장 이른 것의 경과. 없으면 "?".
function oldestApproval(j: DashJudgment): string {
  const known = j.tasks.filter(t => t.status === '승인대기' && t.approval_requested !== '' && t.elapsed && t.elapsed.text !== '?')
  if (known.length === 0) return '?'
  return known.reduce((a, b) => (b.approval_requested < a.approval_requested ? b : a)).elapsed!.text
}

// 띠를 그릴 만큼 온전한 판정인가. flows·counts가 없으면(판정 스크립트와 플러그인의 판본이 어긋남) 띠는 비킨다.
export function bandReady(j: DashJudgment): boolean {
  return Array.isArray(j.flows) && !!j.counts
}

// 승인 대기 · 할 일 대기 · 에이전트 · 시작 가능 · 상태별 수(실행 이름은 위 테두리). 폭을 넘으면 상태별 수 → 시작 가능 → 에이전트 → (가장 오래 …) 차례로 빼고, 그래도 넘으면 끝을 "…"로.
export function summaryLine(j: DashJudgment, width: number): string {
  const c = j.counts
  const byStatus = [
    ...SHOWN_STATES.filter(s => c.by_status[s] > 0).map(s => `${s} ${c.by_status[s]}`),
    ...(c.folded > 0 ? [`접힘 ${c.folded}`] : []),
    ...(c.unreadable > 0 ? [`읽지 못함 ${c.unreadable}`] : []),
  ].join(', ')
  const oldest = c.approval > 0 ? `(가장 오래 ${oldestApproval(j)})` : ''
  const compose = (drop: number) => [
    `승인 대기 ${c.approval}${drop < 4 ? oldest : ''}`,
    `할 일 대기 ${c.waiting_user}`,
    drop < 3 ? `에이전트 ${c.running_agent}` : '',
    drop < 2 ? `시작 가능 ${j.ready.length}` : '',
    drop < 1 ? byStatus : '',
  ].filter(p => p !== '').join(' · ')
  for (let drop = 0; drop <= 4; drop++) {
    const line = compose(drop)
    if (cells(line) <= width) return line
  }
  return fitEnd(compose(4), width)
}

// 띠의 지도 단위 버튼을 둘 흐름 = flow.md 항목이 있는 줄. 차례는 lanesOf 그대로.
export function bandLanes(j: DashJudgment): Lane[] {
  return lanesOf(j).filter(l => !l.isBlock)
}

// 지도 펼치기/접기, 전체, 흐름마다 하나, 패널 열기. 고른 단위 앞에 "*". 접음과 펼침은 map-toggle의 label만 다름.
export function bandButtons(lanes: Lane[], unit: string, expanded: boolean): PanelButton[] {
  const mark = (name: string) => (unit === name ? '*' : '') + name
  return [
    { key: 'map-toggle', hotkey: 'm', label: expanded ? '지도 접기' : '지도 펼치기' },
    { key: 'unit-all', hotkey: 'a', label: mark(ALL) },
    ...lanes.map((l, i): PanelButton => i < LANE_HOTKEYS.length
      ? { key: `unit-${i + 1}`, hotkey: LANE_HOTKEYS[i]!, label: mark(l.name) }
      : { key: `unit-${i + 1}`, label: mark(l.name) }),
    { key: 'open-panel', hotkey: 'p', label: '패널 열기' },
  ]
}

// 띠의 흐름별 상태 줄을 그릴 줄: flow.md가 있는 흐름과, 공통 뒷부분을 실은 블록 줄.
// 이름만 남는 블록·기타 줄은 묶음이 생길 때마다 늘어나므로 뺀다.
export function bandLaneRows(j: DashJudgment): Lane[] {
  return lanesOf(j).filter(l => !l.isBlock || shownSuffix(laneSuffix(j, l.name)) !== '')
}

// 요약 줄, 버튼 줄들, (펼침이면) bandLaneRows(j)의 흐름별 상태 줄들과 의존 지도. 높이로 자르지 않는다.
// 지도 줄만 흐림 여부를 mapRows에서 그대로 받는다(끝난 task의 줄). width는 테두리 안쪽 폭이다.
// 나눈 뒤에도 글이 폭보다 넓은 버튼(단축키가 있으면 4칸보다 줄지 않음)은 단축키 없이 이름만 줄인다(폭 4 미만에서만).
export function bandRows(j: DashJudgment, view: BandView, width: number): Row[] {
  const lanes = bandLanes(j)
  const unit = unitOf(view.unit, lanes)
  const rows: Row[] = [{ kind: 'text', text: summaryLine(j, width) }]
  for (const buttons of buttonRows(bandButtons(lanes, unit, view.expanded), width)) {
    rows.push({ kind: 'buttons', buttons: buttons.map(b => (cells(buttonText(b)) > width ? { key: b.key, label: fitEnd(b.label, width) } : b)) })
  }
  if (!view.expanded) return rows
  for (const lane of bandLaneRows(j)) {
    for (const text of laneLines(j, lane, width, LANE_OPT)) rows.push({ kind: 'text', text })
  }
  for (const { text, dim } of mapRows(j, unit, width)) rows.push({ kind: 'text', text, dim })
  return rows
}

// 실행이 없고 이 세션에서 불렸을 때의 한 줄. 판정이 있으면 그 message, 없으면 "판정 결과 없음".
export function noRunLine(s: DashState | null, width: number): string {
  return fitEnd(s?.result?.message ?? '판정 결과 없음', width)
}

// 테두리 안쪽 폭. 테두리 글자 2칸과 그 안쪽 빈 칸 2칸을 뺀다.
export function innerWidth(width: number): number {
  return Math.max(0, width - 4)
}

// "╭─ {이름} ─…╮". 이름 자리는 width − 6. 넘치면 앞 날짜(YYYY-MM-DD-)를 먼저 떼고, 그래도 넘치면 끝을 "…"로.
// 자리가 1칸도 없거나 이름이 없으면(실행 없음) 선만.
export function frameTop(name: string | null, width: number): string {
  const room = width - 6
  if (name === null || room < 1) return '╭' + '─'.repeat(Math.max(0, width - 2)) + '╮'
  const undated = name.replace(/^\d{4}-\d{2}-\d{2}-/, '') || name
  const shown = cells(name) <= room ? name : fitEnd(undated, room)
  const head = `╭─ ${shown} `
  return head + '─'.repeat(width - 1 - cells(head)) + '╮'
}

// "╰─…╯".
export function frameBottom(width: number): string {
  return '╰' + '─'.repeat(Math.max(0, width - 2)) + '╯'
}

// 테두리를 두른 줄: 위·아래 테두리(edge)와 안쪽 줄. 안쪽 줄의 fill은 "│ "·가운데·"{fill} │"이 띠 폭이 되게 채울 공백이다.
export type FramedRow = { kind: 'edge'; text: string }
  | { kind: 'text'; text: string; dim?: boolean; fill: string }
  | { kind: 'buttons'; buttons: PanelButton[]; fill: string }

// 위 테두리, rows의 줄마다 안쪽 줄, 아래 테두리. 버튼 줄의 칸 수는 버튼 글의 합 + 사이 2칸(columnGap 2).
// 안쪽 글이 안쪽 폭보다 넓으면 채움은 없고 그 줄은 띠 폭을 넘는다.
export function bandFrame(name: string | null, rows: Row[], width: number): FramedRow[] {
  const inner = innerWidth(width)
  const fill = (c: number) => ' '.repeat(Math.max(0, inner - c))
  return [
    { kind: 'edge', text: frameTop(name, width) },
    ...rows.map((r): FramedRow => (r.kind === 'text'
      ? { ...r, fill: fill(cells(r.text)) }
      : { ...r, fill: fill(r.buttons.reduce((n, b) => n + cells(buttonText(b)), 0) + 2 * (r.buttons.length - 1)) })),
    { kind: 'edge', text: frameBottom(width) },
  ]
}
