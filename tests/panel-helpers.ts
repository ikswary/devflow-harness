// 패널 마운트 시험의 보조 함수.
// 판정은 common의 길(process.run의 답 → $.state judgment)로 넣고, Pane을 마운트해 그린 트리를 글자 줄로 꺼낸다.
import { mock } from 'claude-code/testing'
import type { On } from 'claude-code'
import type { Engine, MockClock } from 'claude-code/testing'

import type { DashFlow, DashJudgment, DashState, DashTask } from '../types'
import { panelOpenArgs } from '../hooks/panel-map'

const ROOT = 'D:/w'
const FOLDED = ['완료', '보류', '백로그']

// ---- 판정 JSON ----

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

export function flow(name: string, status: string, p: Partial<DashFlow> = {}): DashFlow {
  return { name, status, sync_pending: [], depends_on_flows: [], unreadable: false, ...p }
}

// 기본값(빈 목록)과 합친 판정. 접힌 개수는 tasks에서 센다.
export function dash(tasks: DashTask[], p: Partial<DashJudgment> = {}): DashJudgment {
  const folded: DashJudgment['folded_by_group'] = {}
  for (const t of tasks) {
    if (t.class !== 'folded') continue
    const by = (folded[t.group] ??= {})
    by[t.status] = (by[t.status] ?? 0) + 1
  }
  return {
    schema: 1, now: '2026-10-06 10:00', workdir: ROOT, session: 'S', message: null,
    run: { name: 'R1', dir: `${ROOT}/_workspace/R1`, status: '진행', run_md_unreadable: false, flow_cap: 2 },
    tasks, unreadable: [], flows: [], ready: [], held: [], undecidable: [], queue: [],
    counts: {
      by_status: { 대기: 0, 진행: 0, 자체검증: 0, 승인대기: 0, 완료: 0, 보류: 0, 백로그: 0 },
      remaining: 0, folded: 0, unreadable: 0, approval: 0, waiting_user: 0, running_agent: 0, external_progress: 0,
    },
    folded_by_group: folded, unclean: [],
    ...p,
  }
}

export function stateOf(j: DashJudgment): DashState {
  return { result: j, error: '', at: 0, invokedAt: null }
}

// ---- 시험 세계: 엔진 대신 답하는 훅들 ----

export type OpenArgs = { id: string; title?: string; rows?: number; focus?: boolean }

export type World = {
  clock: MockClock
  json: { value: unknown }
  opened: OpenArgs[]
  panes: string[]
  registered: string[]
  runs: number
}

// session·process·명령 등록·패널 열기를 답한다. ui.open은 연 id를 panes에 넣고, ui.close는 panes에서 뺀다.
export function world(on: On): World {
  const w: World = { clock: mock.clock(on, { now: 30000 }), json: { value: null }, opened: [], panes: [], registered: [], runs: 0 }
  on('session.root', () => ({ value: ROOT }))
  on('session.id', () => ({ value: 'S' }))
  on('fs.exists', () => ({ value: true }))
  on('process.run', () => {
    w.runs += 1
    const stdout = JSON.stringify(w.json.value)
    return { value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  on('command.register', ($, e) => {
    w.registered.push(e.name)
    return { value: { command: e.name } }
  })
  on('ui.open', ($, e) => {
    w.opened.push({ ...e })
    if (!w.panes.includes(e.id)) w.panes.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('ui.panes', () => ({ value: w.panes.map(id => ({ id, isPlaced: true })) }))
  on('ui.close', ($, e) => {
    w.panes = w.panes.filter(id => id !== e.id)
    return { value: null }
  })
  on('skill.prompt', ($, e) => ({ text: e.text }))
  on('tool.call', () => ({ result: 'ran' }))
  on('turn.complete', () => ({ text: 'answer' }))
  return w
}

// 시험에 함께 띄우는 플러그인. 시험 도구의 엔진 쪽 $에는 ui.open·ui.close가 없어서 이 플러그인의 명령으로 부른다.
// 이 플러그인은 따로 불러와져 시험 파일의 가져오기를 쓰지 못하므로 여는 인자는 시험이 만들어 넘긴다(bandOpen).
// band-open: args의 JSON(panelOpenArgs의 값)으로 연다. close-panel: 사람이 닫는 것 대신 $.ui.close로 닫는다.
// panel.tsx의 ui.close 훅은 같은 id로 받는다(origin은 plugin). peek: 상태 judgment를 글로 돌려준다.
export const BAND = {
  name: 'band-like',
  register(on: On) {
    on('command.run', { command: 'band-open' }, async ($, e) => {
      await $.ui.open(JSON.parse(e.args))
      return {}
    })
    on('command.run', { command: 'close-panel' }, async $ => {
      await $.ui.close({ id: 'harness-panel' })
      return {}
    })
    on('command.run', { command: 'peek' }, async $ => {
      const { value } = await $.state.get({ plugin: 'devflow-harness', key: 'judgment' })
      return { text: JSON.stringify(value ?? null) }
    })
  },
}

// 8.2 feedJudgment: 세션을 시작해 common이 판정을 한 번 돌리게 한다.
export async function feedJudgment($: Engine, w: World, json: unknown, isInteractive = true): Promise<void> {
  w.json.value = json
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive })
  await w.clock.advance(600)
}

// 같은 세션에서 판정을 바꿔 넣는다: 도구 실행 하나 뒤 common의 묶음 회차.
export async function refeed($: Engine, w: World, json: unknown): Promise<void> {
  w.json.value = json
  await toolCall($)
  await w.clock.advance(600)
}

export function toolCall($: Engine) {
  return $.tool.call({ tool: 'Bash', command: 'echo hi' } as never)
}

export function turnComplete($: Engine) {
  return $.turn.complete({ reason: 'answer', answer: 'a', durationMs: 1, isAborted: false, turnId: 't1' })
}

export function sessionEnd($: Engine, reason: 'clear' | 'logout') {
  return $.session.end({ reason, sessionId: 'S', resume: {} } as never)
}

// 사용자가 /harness-panel을 입력한 것. columns는 터미널 폭.
export function runCommand($: Engine, columns = 84) {
  return $.command.run({ command: 'harness-panel', args: '', presentation: { columns } } as never)
}

function bandCommand($: Engine, command: string, args = '') {
  return $.command.run({ command, args, presentation: { columns: 84 } } as never)
}

export const closePanel = ($: Engine) => bandCommand($, 'close-panel')
export const peek = async ($: Engine) => ((await bandCommand($, 'peek')) as { text: string }).text

// 띠의 패널 열기 버튼(status.tsx onPress)과 같은 인자: 지금 상태로 panelOpenArgs(state, columns).
export async function bandOpen($: Engine, columns: number) {
  const state = JSON.parse(await peek($)) as DashState | null
  return bandCommand($, 'band-open', JSON.stringify(panelOpenArgs(state, columns)))
}

// 판정을 넣고 명령으로 연 패널을 폭 width로 마운트한다(사용자가 /harness-panel을 입력한 것).
export async function openPanel($: Engine, on: On, j: unknown, width = 80, p: { bodyRows?: number } = {}) {
  const w = world(on)
  await feedJudgment($, w, j)
  await runCommand($, width + 4)
  const ui = await mountPane($, width, p)
  return { w, ui, lines: linesOf(await ui.drawn()) }
}

export function mountPane($: Engine, width = 80, p: { placement?: string; bodyRows?: number } = {}) {
  return $.ui.mount({
    plugin: 'devflow-harness', surface: 'terminal', component: 'Pane', requestId: 'harness-panel',
    props: {
      title: '하네스 진행', isFocused: true, bodyColumns: width, placement: p.placement ?? 'inline',
      scroll: { bodyRows: p.bodyRows ?? 40 }, view: {},
    },
  } as never)
}

// ---- 그린 내용 ----

type Node = { type: string; props?: Record<string, unknown>; children?: unknown[] }

// 맨 바깥 세로 Box의 자식마다 한 줄. Text는 글을 이은 것, 가로 Box는 버튼마다 "{hotkey}: {label}"을 두 칸으로 이은 것.
export function linesOf(tree: unknown): string[] {
  const root = tree as Node
  return (root.children ?? []).map(c => {
    const n = c as Node
    if (n.type === 'Text') return (n.children ?? []).map(String).join('')
    return (n.children ?? []).map(b => {
      const props = (b as Node).props ?? {}
      return props.hotkey ? `${props.hotkey}: ${props.label}` : String(props.label)
    }).join('  ')
  })
}

// 8.1 rowsOf: linesOf와 같은 줄마다 { text, dim }. dim은 그 Text의 dimColor가 참인지(버튼 줄은 거짓). spec의 "흐린 글씨".
export function rowsOf(tree: unknown): { text: string; dim: boolean }[] {
  const texts = linesOf(tree)
  return ((tree as Node).children ?? []).map((c, i) => {
    const n = c as Node
    return { text: texts[i]!, dim: n.type === 'Text' && n.props?.dimColor === true }
  })
}

// 그린 트리의 버튼 key 목록(줄 순서대로).
export function buttonsOf(tree: unknown): { key: string; label: string; hotkey?: string }[] {
  const out: { key: string; label: string; hotkey?: string }[] = []
  for (const c of (tree as Node).children ?? []) {
    for (const b of (c as Node).type === 'Box' ? (c as Node).children ?? [] : []) {
      const props = (b as Node).props ?? {}
      out.push({ key: String(props.key), label: String(props.label), hotkey: props.hotkey as string | undefined })
    }
  }
  return out
}

export function keyOf(tree: unknown, label: string): string {
  const b = buttonsOf(tree).find(x => x.label === label)
  if (!b) throw new Error(`버튼 없음: ${label}`)
  return b.key
}

function between(lines: string[], head: string, ends: string[]): string[] {
  const start = lines.indexOf(head)
  if (start < 0) return []
  const rest = lines.slice(start + 1)
  const end = rest.findIndex(l => ends.includes(l))
  return end < 0 ? rest : rest.slice(0, end)
}

export function mapSection(lines: string[]): string[] {
  return between(lines, '의존 지도', ['정리 안 된 값', '읽지 못함'])
}

export function laneSection(lines: string[]): string[] {
  return between(lines, '흐름별 상태', ['의존 지도'])
}

export function uncleanSection(lines: string[]): string[] {
  return between(lines, '정리 안 된 값', ['읽지 못함'])
}

// 흐름별 상태 부분에서 줄 이름이 name인 줄(뒤에 공통 뒷부분 " · …"이 붙을 수 있음)과 그 아래 들여쓴 줄(이어진 줄·펼친 접힌 task).
export function laneOf(lines: string[], name: string): string[] {
  const sec = laneSection(lines)
  const start = sec.findIndex(l => l === name || l.startsWith(name + '  ') || l.startsWith(name + ' · '))
  if (start < 0) return []
  const end = sec.slice(start + 1).findIndex(l => !l.startsWith(' '))
  return sec.slice(start, end < 0 ? sec.length : start + 1 + end)
}

// 패널의 그린 내용이면 의존 지도 부분, 아니면(mapLines의 줄, 띠의 줄) 받은 줄 그대로.
const mapOf = (lines: string[]) => (lines.includes('의존 지도') ? mapSection(lines) : lines)

// id는 글자·숫자뿐이라 정규식에 그대로 넣는다. 상태 기호의 -는 글자 모음 맨 끝에 둬 범위로 읽히지 않게 한다.
const taskLine = (id: string) => new RegExp(`^((?:│  |   |├─ |└─ )*)[✓~>?xb -] ${id}( |$)`)

// 8.1 spec의 "task 줄": 선 글자 조각 0개 이상, 상태 기호, 공백, id로 시작하는 첫 줄 번호. 없으면 −1.
export function taskRow(map: string[], id: string): number {
  const re = taskLine(id)
  return map.findIndex(l => re.test(l))
}

// 그 task 줄에서 상태 기호의 열(선 글자는 1칸 글자뿐이라 번호 = 열). 그 task 줄이 아니면 −1.
export function symbolCol(line: string, id: string): number {
  const m = taskLine(id).exec(line)
  return m ? m[1]!.length : -1
}

// 줄의 ├·└ 열. 없으면 −1.
export function branchCol(line: string): number {
  return line.search(/[├└]/)
}

// spec의 "task의 칸": task 줄부터 다른 task(ids)의 task 줄 앞까지(task 줄 + 덧줄). 칸이 없으면 빈 목록.
export function cellOf(lines: string[], id: string, ids: string[]): string[] {
  const map = mapOf(lines)
  const start = taskRow(map, id)
  if (start < 0) return []
  const next = ids.filter(o => o !== id).map(o => taskRow(map, o)).filter(r => r > start)
  return map.slice(start, next.length > 0 ? Math.min(...next) : map.length)
}

// 8.1 linked: a가 b의 트리 부모이고 선이 이어짐. a 줄이 b 줄보다 위, b 줄의 ├·└가 a의 상태 기호 열 c에 있고,
// 그 사이 모든 줄의 c열이 │ 또는 ├.
export function linked(lines: string[], a: string, b: string): boolean {
  const map = mapOf(lines)
  const ra = taskRow(map, a)
  const rb = taskRow(map, b)
  if (ra < 0 || rb <= ra) return false
  const c = symbolCol(map[ra]!, a)
  if (branchCol(map[rb]!) !== c) return false
  for (let r = ra + 1; r < rb; r++) if (!['│', '├'].includes(map[r]![c] ?? '')) return false
  return true
}

// 8.4 AC-14: --ready 출력에서 "- " 줄의 둘째 낱말과 줄 끝 괄호 안 글자.
export function readyLists(ready: string): { ready: string[]; held: [string, string][] } {
  const out = { ready: [] as string[], held: [] as [string, string][] }
  let part: 'ready' | 'held' | null = null
  for (const line of ready.split(/\r?\n/)) {
    if (line.startsWith('지금 시작할 수 있는 task')) part = 'ready'
    else if (line.startsWith('의존은 풀렸지만 지금은 못 띄움')) part = 'held'
    else if (line.startsWith('- ') && part === 'ready') out.ready.push(line.split(' ')[1]!)
    else if (line.startsWith('- ') && part === 'held') out.held.push([line.split(' ')[1]!, /\(([^()]*)\)$/.exec(line)![1]!])
  }
  return out
}
