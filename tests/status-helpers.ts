// 띠 마운트 시험의 도우미: 판정 JSON 만들기, common의 길로 판정 넣기, 띠 마운트, 그린 트리를 줄 목록으로.
// 판정·마운트 도우미는 panel의 panel-helpers.ts를 가져오지 않고 같은 규칙으로 따로 둔다. 지도의 task 줄 찾기·열 재기는
// 띠와 패널이 같은 모양이라 panel-helpers.ts의 것을 그대로 쓴다.
import { mock } from 'claude-code/testing'
import type { On } from 'claude-code'
import type { Engine, MockClock } from 'claude-code/testing'
import type { DashFlow, DashJudgment, DashTask } from '../types'

export { branchCol, cellOf, linked, symbolCol, taskRow } from './panel-helpers'

export const ROOT = 'D:/w'
export const W = 120

const FOLDED = ['완료', '보류', '백로그']

// task 기본값: class는 status로, group은 flow → block → 기타(panel 8.2와 같은 규칙).
export function task(p: Partial<DashTask> & { id: string }): DashTask {
  const t: DashTask = {
    title: '', kind: 'implementation', status: '대기', flow: '', block: '', group: '', parent: '', depends_on: [],
    class: 'remaining', start: null, reason_text: '', elapsed: null, waiting_user: '', running_agent: '',
    external_progress: '', approval_requested: '', started: '', created: '', approved: '', n_decide: '',
    ...p,
  }
  t.group = p.group ?? (t.flow || t.block || '기타')
  t.class = p.class ?? (FOLDED.includes(t.status) ? 'folded' : 'remaining')
  return t
}

export function flow(name: string, status = '진행', p: Partial<DashFlow> = {}): DashFlow {
  return { name, status, sync_pending: [], depends_on_flows: [], unreadable: false, ...p }
}

// common 3.2 꼴. counts·ready는 tasks에서 common C1 꼴로 센다(남은 task만 승인·할 일·에이전트, 접힌 것은 folded).
export function dash(tasks: DashTask[], p: Partial<DashJudgment> = {}): DashJudgment {
  const folded: DashJudgment['folded_by_group'] = {}
  const by: DashJudgment['counts']['by_status'] = { 대기: 0, 진행: 0, 자체검증: 0, 승인대기: 0, 완료: 0, 보류: 0, 백로그: 0 }
  for (const t of tasks) {
    by[t.status]++
    if (t.class !== 'folded') continue
    const g = (folded[t.group] ??= {})
    g[t.status] = (g[t.status] ?? 0) + 1
  }
  const rem = tasks.filter(t => t.class === 'remaining')
  return {
    schema: 1, now: '2026-10-06 10:00', workdir: ROOT, session: 'S1', message: null,
    run: { name: 'R1', dir: `${ROOT}/_workspace/R1`, status: '진행', run_md_unreadable: false, flow_cap: 2 },
    tasks, unreadable: [], flows: [], ready: rem.filter(t => t.start === 'ready').map(t => t.id), held: [], undecidable: [], queue: [],
    counts: {
      by_status: by, remaining: rem.length, folded: tasks.length - rem.length, unreadable: 0,
      approval: rem.filter(t => t.status === '승인대기').length,
      waiting_user: rem.filter(t => t.waiting_user !== '').length,
      running_agent: rem.filter(t => t.running_agent !== '').length,
      external_progress: rem.filter(t => t.external_progress !== '').length,
    },
    folded_by_group: folded, unclean: [],
    ...p,
  }
}

export type Fed = {
  clock: MockClock
  // 판정 스크립트가 다음에 낼 JSON. 바꾼 뒤 refeed로 넣는다.
  json: { value: unknown }
  // 시험의 ui.open이 받은 인자, ui.panes가 답할 열린 id.
  opened: unknown[]
  panes: string[]
}

// common 시험의 길(common.test.ts world·start): 시험의 on이 session·fs·process·시계를 대신 답하고,
// $.session.start 뒤 시계 600 ms로 판정이 상태에 들어간다. ui.open은 인자를 적고 열린 id로 둔다.
export async function feed($: Engine, on: On, json: unknown): Promise<Fed> {
  const f: Fed = { clock: mock.clock(on, { now: 30000 }), json: { value: json }, opened: [], panes: [] }
  on('session.root', () => ({ value: ROOT }))
  on('session.id', () => ({ value: 'S1' }))
  on('fs.exists', () => ({ value: true }))
  on('process.run', () => ({
    value: { exitCode: 0, stdout: JSON.stringify(f.json.value), stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  }))
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  on('skill.prompt', ($, e) => ({ text: e.text }))
  on('tool.call', () => ({ result: 'ran' }))
  on('turn.complete', () => ({ text: 'answer' }))
  on('ui.open', ($, e) => {
    f.opened.push({ ...e })
    if (!f.panes.includes(e.id)) f.panes.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('ui.panes', () => ({ value: f.panes.map(id => ({ id, title: id, isShown: true, isFocused: false, isPlaced: true })) as never }))
  // 엔진이 띠에 제 것을 그리지 않는 자리(d.ts AbovePrompt): 대시보드가 비키면 빈 Box.
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
    const { Box } = $.ui.resolve(e)
    return h(Box, {})
  })
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await f.clock.advance(600)
  return f
}

// 판정을 바꿔 넣음: 답을 바꾸고 도구 실행 하나를 일으켜 600 ms(파일이 바뀐 뒤 다시 그려지는 길).
export async function refeed($: Engine, f: Fed, json: unknown): Promise<void> {
  f.json.value = json
  await $.tool.call({ tool: 'Bash', command: 'echo hi' } as never)
  await f.clock.advance(600)
}

export async function mountBand($: Engine, width = W, opt: { hasSurvey?: boolean; maxRows?: number } = {}) {
  const maxRows = opt.maxRows ?? 40
  return $.ui.mount({
    plugin: 'devflow-harness',
    surface: 'terminal',
    component: 'AbovePrompt',
    props: {
      hasSurvey: opt.hasSurvey ?? false, isWorking: false, maxRows, bodyColumns: width,
      scroll: { offset: 0, bodyRows: maxRows - 1 }, view: {},
    },
  })
}

type Node = { type?: string; props?: Record<string, unknown>; children?: unknown[] }

const textOf = (n: Node) => (n.children ?? []).map(c => (typeof c === 'string' ? c : '')).join('')

const buttonText = (n: Node) => {
  const p = n.props ?? {}
  const label = String(p.label ?? textOf(n))
  return p.hotkey ? `${p.hotkey}: ${label}` : label
}

const buttonsText = (n: Node) => (n.children ?? []).filter(b => (b as Node).type === 'Button').map(b => buttonText(b as Node)).join('  ')

// 조각 하나의 글: Text면 글, 가로 Box면 Button마다 "{hotkey}: {label}"을 두 칸으로 이음.
const pieceText = (n: Node) => (n.type === 'Text' ? textOf(n) : buttonsText(n))

// 대시보드 트리면 맨 바깥 세로 Box의 자식들(위 테두리, 안쪽 줄들, 아래 테두리). 비켜서 시험의 빈 Box만 그려졌으면 null.
function bandChildren(tree: unknown): Node[] | null {
  const root = tree as Node | null | undefined
  if (!root || root.type !== 'Box' || root.props?.flexDirection !== 'column') return null
  return (root.children ?? []) as Node[]
}

// 안쪽 줄(가로 Box의 "│ "·가운데·"{채움} │")의 가운데 조각.
const middleOf = (row: Node) => (row.children ?? [])[1] as Node

// 8.1 bandLines: 위·아래 테두리 줄을 뺀 안쪽 줄마다 가운데 조각의 글(spec 용어의 안쪽 글, "띠의 줄").
// 대시보드 트리가 아니면 빈 목록.
export function bandLines(tree: unknown): string[] {
  const rows = bandChildren(tree)
  if (!rows) return []
  return rows.slice(1, -1).map(r => pieceText(middleOf(r)))
}

// 8.1 bandScreen: 테두리 줄을 포함한 줄마다 화면에 보이는 글. 테두리 줄은 그 Text의 글, 안쪽 줄은 세 조각을 이은 것.
// spec의 "화면 칸 수"·"띠 폭 이하"·테두리 줄·"띠 어디에도". 대시보드 트리가 아니면 빈 목록.
export function bandScreen(tree: unknown): string[] {
  const rows = bandChildren(tree)
  if (!rows) return []
  return rows.map(r => (r.type === 'Text' ? textOf(r) : (r.children ?? []).map(c => pieceText(c as Node)).join('')))
}

// 8.1 bandRowsOf: bandLines와 같은 줄마다 { text, dim }. dim은 가운데 Text의 dimColor가 참인지(버튼 줄은 거짓). spec의 "흐린 글씨".
export function bandRowsOf(tree: unknown): { text: string; dim: boolean }[] {
  const rows = bandChildren(tree)
  if (!rows) return []
  return rows.slice(1, -1).map(r => {
    const mid = middleOf(r)
    return { text: pieceText(mid), dim: mid.type === 'Text' && mid.props?.dimColor === true }
  })
}

export async function lines(ui: { drawn: () => Promise<unknown> }): Promise<string[]> {
  return bandLines(await ui.drawn())
}

export async function screen(ui: { drawn: () => Promise<unknown> }): Promise<string[]> {
  return bandScreen(await ui.drawn())
}
