// 흐름별 상태 줄과 의존 지도를 글자 줄로 만드는 순수 함수, 버튼 목록·버튼 줄 나누기, 패널을 여는 인자.
// 띠(status)와 패널이 함께 쓴다. $를 쓰지 않고 claude-code에서는 타입만 가져온다. 판정은 다시 하지 않고 판정 JSON 값 그대로 쓴다.
import type { DashFlow, DashJudgment, DashState, DashStatus, DashTask } from '../types'
import { cells, fitEnd, wrapParts } from './panel-text'

export const ALL = '전체'

export type Lane = { name: string; flow?: DashFlow; isBlock: boolean }

export type CellExtra = (t: DashTask, unit: string) => { phrases: string[]; lines: string[] }

export type PanelButton = { key: string; hotkey?: string; label: string }

const FOLDED_STATES = ['완료', '보류', '백로그'] as const
const AFTER_MERGE = ['폴더 없음', '진행', '검증 끝남']
const NO_FOLDER = ['폴더 없음', '합쳐짐', '폴더 지움']
const WRITE_KINDS = ['implementation', 'fix', 'merge', 'root-cause']
// 줄 버튼의 단축키: 1~9 다음 a~z에서 e(펼치기) 뺌.
const LANE_HOTKEYS = [...'123456789', ...'abcdfghijklmnopqrstuvwxyz']

function unique<T>(xs: T[]): T[] {
  return xs.filter((x, i) => xs.indexOf(x) === i)
}

// task 순서로 group이 처음 나온 줄, 그다음 줄이 없는 flow.md 이름을 이름순.
export function lanesOf(j: DashJudgment): Lane[] {
  const names = unique(j.tasks.map(t => t.group))
  const rest = unique(j.flows.map(f => f.name).filter(n => !names.includes(n))).sort()
  return [...names, ...rest].map(name => {
    const flow = j.flows.find(f => f.name === name)
    return flow ? { name, flow, isBlock: false } : { name, isBlock: true }
  })
}

// (가) 합치기가 끝났는데 합쳐짐·폴더 지움이 아님, (나) 폴더가 없다는데 코드 폴더에 쓰는 task가 돎. 둘 다면 (가).
export function misalignOf(j: DashJudgment, lane: Lane): string | null {
  const f = lane.flow
  if (!f || f.unreadable) return null
  const same = j.tasks.filter(t => t.flow === lane.name)
  if (AFTER_MERGE.includes(f.status)) {
    const m = same.find(t => t.kind === 'merge' && t.status === '완료')
    if (m) return `어긋남: 합치기 ${m.id} 완료`
  }
  if (NO_FOLDER.includes(f.status)) {
    const w = same.find(t => WRITE_KINDS.includes(t.kind) && (t.status === '진행' || t.status === '자체검증'))
    if (w) return `어긋남: ${w.id} ${w.status}`
  }
  return null
}

// 조각 사이 두 칸, W를 넘으면 조각 경계에서 잇고 두 칸 들여씀. 펼치면 그 줄의 접힌 task를 한 줄씩.
// 줄 이름 조각에는 그 줄의 공통 뒷부분을 " · {보일 뒷부분}"으로 붙인다.
export function laneLines(j: DashJudgment, lane: Lane, width: number,
  opt: { misalign: boolean; folded: boolean; expanded: boolean }): string[] {
  const suffix = shownSuffix(laneSuffix(j, lane.name))
  const parts = [suffix === '' ? lane.name : `${lane.name} · ${suffix}`]
  const f = lane.flow
  if (f) {
    parts.push(f.unreadable ? 'flow.md 읽지 못함' : f.status)
    if (f.sync_pending.length > 0) parts.push(`받아오기 대기 ${f.sync_pending.length}`)
  }
  if (opt.misalign) parts.push(misalignOf(j, lane) ?? '')
  if (opt.folded) {
    const by = j.folded_by_group[lane.name] ?? {}
    parts.push(FOLDED_STATES.filter(s => (by[s] ?? 0) > 0).map(s => `${s} ${by[s]}`).join(' · '))
  }
  const fitted = parts.filter(p => p !== '').map((p, i) => fitEnd(p, i === 0 ? width : width - 2))
  const lines = wrapParts(fitted, '  ', width, 2)
  if (opt.expanded) {
    for (const t of j.tasks) {
      if (t.class !== 'folded' || t.group !== lane.name) continue
      lines.push(fitEnd(`  ${t.id} ${t.status}${t.title === '' ? '' : ' ' + t.title}`, width))
    }
  }
  return lines
}

// 고른 줄이 지금 줄 목록에 없으면 전체.
export function unitOf(unit: string, lanes: Lane[]): string {
  return lanes.some(l => l.name === unit) ? unit : ALL
}

const MARK = /^(\[[^\]]*\])\s+/

function splitMark(title: string): [string, string] {
  const m = MARK.exec(title)
  return m ? [m[1]!, title.slice(m[0].length)] : ['', title]
}

// 공통 앞부분: 셀 제목 과반(둘 이상)이 함께 시작하는, 공백으로 끝나는 앞부분 가운데 가장 많은 것(같으면 가장 긴 것).
export function titlePrefix(tasks: DashTask[]): string {
  const titles = tasks.map(t => splitMark(t.title)[1]).filter(s => s !== '')
  const seen = new Set<string>()
  let best = ''
  let bestN = 0
  for (const s of titles) {
    for (let i = 0; i < s.length; i++) {
      if (!/\s/.test(s[i]!)) continue
      const cand = s.slice(0, i + 1)
      if (seen.has(cand)) continue
      seen.add(cand)
      const n = titles.filter(x => x.startsWith(cand)).length
      if (n < 2 || n * 2 <= titles.length) continue
      if (n > bestN || (n === bestN && cand.length > best.length)) {
        best = cand
        bestN = n
      }
    }
  }
  return best
}

// 공통 뒷부분: 앞부분과 대칭. 셀 제목 과반(둘 이상)이 함께 끝나는, 공백으로 시작하는 뒷부분 가운데 가장 많은 것(같으면 가장 긴 것).
export function titleSuffix(tasks: DashTask[]): string {
  const titles = tasks.map(t => splitMark(t.title)[1]).filter(s => s !== '')
  const seen = new Set<string>()
  let best = ''
  let bestN = 0
  for (const s of titles) {
    for (let i = 0; i < s.length; i++) {
      if (!/\s/.test(s[i]!)) continue
      const cand = s.slice(i)
      if (seen.has(cand)) continue
      seen.add(cand)
      const n = titles.filter(x => x.endsWith(cand)).length
      if (n < 2 || n * 2 <= titles.length) continue
      if (n > bestN || (n === bestN && cand.length > best.length)) {
        best = cand
        bestN = n
      }
    }
  }
  return best
}

// 줄(group)마다 그 줄에 든 모든 읽힌 task로 센 공통 뒷부분. 흐름 줄과 지도가 같은 값을 쓴다.
export function laneSuffix(j: DashJudgment, group: string): string {
  return titleSuffix(j.tasks.filter(t => t.group === group))
}

const SEPS_HEAD = /^[\s—\-:·]+/
const SEPS_TAIL = /[\s—\-:·]+$/

// 흐름 줄에 보일 뒷부분: 맨 앞의 공백·구분 기호를 뗀 것.
export function shownSuffix(suffix: string): string {
  return suffix.replace(SEPS_HEAD, '')
}

// 보일 제목: 앞부분을 빼고, 남은 것이 뒷부분으로 끝나면 그것도 빼고, 끝의 공백·구분 기호를 뗌. 남는 글자가 없으면 셀 제목 그대로.
export function shownTitle(title: string, prefix: string, suffix: string): string {
  const [mark, cell] = splitMark(title)
  let shown = prefix !== '' && cell.startsWith(prefix) ? cell.slice(prefix.length) : cell
  if (suffix !== '' && shown.endsWith(suffix)) shown = shown.slice(0, shown.length - suffix.length)
  shown = shown.replace(SEPS_TAIL, '')
  if (shown === '') shown = cell
  return mark === '' ? shown : `${mark} ${shown}`
}

// 상태 기호. 대기는 공백 한 칸.
export const STATUS_MARK: Record<DashStatus, string> = {
  완료: '✓', 자체검증: '~', 진행: '>', 승인대기: '?', 대기: ' ', 보류: '-', 백로그: 'b',
}

type Graph = { nodes: DashTask[]; edges: [string, string][] }

type Ctx = {
  j: DashJudgment
  byId: Map<string, DashTask>
  order: Map<string, number>
  preds: (t: DashTask) => string[]
}

function ctxOf(j: DashJudgment): Ctx {
  const byId = new Map(j.tasks.map(t => [t.id, t] as const))
  const order = new Map(j.tasks.map((t, i) => [t.id, i] as const))
  const preds = (t: DashTask) => unique([t.parent, ...t.depends_on].filter(id => id !== '' && byId.has(id)))
  return { j, byId, order, preds }
}

// 그릴 task와 선: 전체면 남은 task와 그 preds, 줄이면 그 줄의 남은 task와 같은 줄의 preds.
function graphOf(c: Ctx, unit: string): Graph {
  const inUnit = (t: DashTask) => unit === ALL || t.group === unit
  const inN = new Set<string>()
  for (const t of c.j.tasks) {
    if (t.class !== 'remaining' || !inUnit(t)) continue
    inN.add(t.id)
    for (const p of c.preds(t)) if (inUnit(c.byId.get(p)!)) inN.add(p)
  }
  const nodes = c.j.tasks.filter(t => inN.has(t.id))
  const edges: [string, string][] = []
  for (const b of nodes) for (const a of c.preds(b)) if (inN.has(a)) edges.push([a, b.id])
  return { nodes, edges }
}

// 강하게 이어진 묶음(Tarjan, 시작 순서는 task 순서). 묶음 안은 task 순서.
function componentsOf(c: Ctx, g: Graph): string[][] {
  const succ = new Map<string, string[]>(g.nodes.map(t => [t.id, []]))
  for (const [a, b] of g.edges) succ.get(a)!.push(b)
  const index = new Map<string, number>()
  const low = new Map<string, number>()
  const stack: string[] = []
  const onStack = new Set<string>()
  const comps: string[][] = []
  let next = 0
  const visit = (v: string) => {
    index.set(v, next)
    low.set(v, next)
    next++
    stack.push(v)
    onStack.add(v)
    for (const w of succ.get(v)!) {
      if (!index.has(w)) {
        visit(w)
        low.set(v, Math.min(low.get(v)!, low.get(w)!))
      } else if (onStack.has(w)) {
        low.set(v, Math.min(low.get(v)!, index.get(w)!))
      }
    }
    if (low.get(v) === index.get(v)) {
      const comp: string[] = []
      let w: string
      do {
        w = stack.pop()!
        onStack.delete(w)
        comp.push(w)
      } while (w !== v)
      comps.push(comp.sort((x, y) => c.order.get(x)! - c.order.get(y)!))
    }
  }
  for (const t of g.nodes) if (!index.has(t.id)) visit(t.id)
  return comps.sort((x, y) => c.order.get(x[0]!)! - c.order.get(y[0]!)!)
}

// 고리: 실행 전체의 선으로 찾은 묶음마다 한 줄. 첫 task에서 preds 방향으로 돌아오는 가장 짧은 길.
function cycleLines(c: Ctx, width: number): string[] {
  const g = graphOf(c, ALL)
  const out: string[] = []
  for (const comp of componentsOf(c, g)) {
    const x = comp[0]!
    const selfLoop = g.edges.some(([a, b]) => a === x && b === x)
    if (comp.length < 2 && !selfLoop) continue
    const inComp = new Set(comp)
    const step = (id: string) => c.preds(c.byId.get(id)!).filter(p => inComp.has(p))
      .sort((p, q) => c.order.get(p)! - c.order.get(q)!)
    const prev = new Map<string, string>()
    const queue = [x]
    let path: string[] = []
    for (let i = 0; i < queue.length && path.length === 0; i++) {
      const cur = queue[i]!
      for (const nb of step(cur)) {
        if (nb === x) {
          const back = [cur]
          while (back[0] !== x) back.unshift(prev.get(back[0]!)!)
          path = [...back, x]
          break
        }
        if (!prev.has(nb) && nb !== x) {
          prev.set(nb, cur)
          queue.push(nb)
        }
      }
    }
    out.push(...wrapParts([`의존 고리: ${path[0]}`, ...path.slice(1)], ' → ', width, 2))
  }
  return out
}

const noSpace = (s: string) => s.replace(/\s/g, '')

// 넘침 덧줄 잇기: " · " 경계, 그래도 넘는 조각은 ", " 경계, 그래도 넘으면 글자 경계(줄이지 않음).
function wrapPhrases(phrases: string[], width: number): string[] {
  const out: string[] = []
  let cur: string | null = null
  for (const p of phrases) {
    if (cells(p) > width) {
      if (cur !== null) out.push(cur)
      const sub = wrapParts(p.split(', '), ', ', width, 0)
      out.push(...sub.slice(0, -1))
      cur = sub[sub.length - 1] ?? null
    } else if (cur === null) {
      cur = p
    } else if (cells(cur + ' · ' + p) <= width) {
      cur = cur + ' · ' + p
    } else {
      out.push(cur)
      cur = p
    }
  }
  if (cur !== null) out.push(cur)
  return out
}

export type MapRow = { text: string; dim: boolean }

type Tree = { roots: DashTask[]; kids: Map<string, DashTask[]>; together: Map<string, string[]> }

// 트리 부모: 그리는 단위의 preds 가운데 다른 묶음에 든 것 중 task 순서로 마지막. 나머지(같은 묶음 포함)는 함께 의존.
function treeOf(c: Ctx, g: Graph): Tree {
  const compOf = new Map<string, number>()
  componentsOf(c, g).forEach((comp, i) => comp.forEach(id => compOf.set(id, i)))
  const inN = new Set(g.nodes.map(t => t.id))
  const kids = new Map<string, DashTask[]>(g.nodes.map(t => [t.id, []]))
  const together = new Map<string, string[]>()
  const roots: DashTask[] = []
  for (const b of g.nodes) {
    const ps = c.preds(b).filter(p => inN.has(p)).sort((x, y) => c.order.get(x)! - c.order.get(y)!)
    const up = ps.filter(p => compOf.get(p) !== compOf.get(b.id)).at(-1)
    if (up === undefined) roots.push(b)
    else kids.get(up)!.push(b)
    together.set(b.id, ps.filter(p => p !== up))
  }
  return { roots, kids, together }
}

// 의존 지도: 고리 줄, 그다음 task마다 task 줄 하나와 덧줄(깊이 우선). 그릴 task가 없으면 "남은 task 없음".
// 넘침은 깊이와 W에만 의존하므로 extra가 있든 없든 같은 task를 뗀다.
export function mapRows(j: DashJudgment, unit: string, width: number, extra?: CellExtra): MapRow[] {
  const c = ctxOf(j)
  const cycles = cycleLines(c, width).map(text => ({ text, dim: false }))
  const u = unitOf(unit, lanesOf(j))
  const g = graphOf(c, u)
  if (g.nodes.length === 0) return [...cycles, { text: '남은 task 없음', dim: false }]
  const tree = treeOf(c, g)
  const prefix = titlePrefix(j.tasks)
  const suffixes = new Map<string, string>()
  const suffixOf = (group: string) => {
    if (!suffixes.has(group)) suffixes.set(group, laneSuffix(j, group))
    return suffixes.get(group)!
  }
  const join = (ps: string[]) => ps.join(' · ')

  // task 줄과 덧줄. lead는 task 줄의 선 글자, more는 덧줄의 선 글자(글은 id 열 + 2부터), from은 뗀 task의 트리 부모.
  const linesOf = (t: DashTask, lead: string, more: string, from: string): string[] => {
    const remaining = t.class === 'remaining'
    const ex = remaining && extra ? extra(t, u) : { phrases: [], lines: [] }
    const dropStatus = ex.phrases.some(p => noSpace(p).startsWith(noSpace(t.status)))
    const tail = [...(dropStatus ? [] : [t.status]), ...ex.phrases]
    const together = tree.together.get(t.id)!
    if (together.length > 0) tail.push(`함께 의존: ${together.join(', ')}`)
    if (remaining && u !== ALL) {
      const others = c.preds(t).map(p => c.byId.get(p)!).filter(p => p.group !== u).map(p => `${p.id}(${p.group})`)
      if (others.length > 0) tail.push(`다른 흐름에 의존: ${others.join(', ')}`)
    }
    if (from !== '') tail.push(`선 생략: ${from}`)
    // 폭: 제목을 "…" 하나까지 줄이고, 그래도 넘으면 줄 끝 조각을 앞에서부터 들어가는 만큼만 남기고 나머지를 덧줄로.
    const head = `${lead}${STATUS_MARK[t.status]} ${t.id}`
    const title = shownTitle(t.title, prefix, suffixOf(t.group))
    const room = width - cells(head) - (title === '' ? 0 : 1) - 2 - cells(join(tail))
    const shown = title !== '' && cells(title) > room ? fitEnd(title, Math.max(1, room)) : title
    let kept = tail
    if (room < (title === '' ? 0 : 1)) {
      const fixed = width - cells(head) - (shown === '' ? 0 : 1 + cells(shown)) - 2
      let n = 0
      while (n < tail.length && cells(join(tail.slice(0, n + 1))) <= fixed) n++
      kept = tail.slice(0, n)
    }
    const out = [head + (shown === '' ? '' : ' ' + shown) + (kept.length === 0 ? '' : '  ' + join(kept))]
    const w = width - cells(more)
    for (const l of wrapPhrases(tail.slice(kept.length), w)) out.push(more + l)
    for (const l of ex.lines) out.push(more + fitEnd(l, w))
    return out
  }

  const cap = Math.max(0, width - 30)
  const rows: MapRow[] = []
  const cut: { t: DashTask; from: string }[] = []
  // rails: 깊이 1 ~ d − 1의 조상마다 뒤 형제가 있는가. last: 마지막 자식인가(뿌리면 null). 자식을 3칸 더 들여 쓰면 cap을 넘을 때는
  // 자식을 모두 떼어 맨 끝에 뗀 순서대로 뿌리처럼 둔다.
  const place = (t: DashTask, rails: boolean[], last: boolean | null, from: string) => {
    const depth = last === null ? 0 : rails.length + 1
    let kids = tree.kids.get(t.id)!
    if (kids.length > 0 && 3 * (depth + 1) > cap) {
      for (const k of kids) cut.push({ t: k, from: t.id })
      kids = []
    }
    const guide = rails.map(r => (r ? '│  ' : '   ')).join('')
    const lead = last === null ? '' : guide + (last ? '└─ ' : '├─ ')
    const more = (last === null ? '' : guide + (last ? '   ' : '│  ')) + (kids.length > 0 ? '│' : ' ') + '   '
    for (const text of linesOf(t, lead, more, from)) rows.push({ text, dim: t.class === 'folded' })
    const next = last === null ? [] : [...rails, !last]
    kids.forEach((k, i) => place(k, next, i === kids.length - 1, ''))
  }
  for (const r of tree.roots) place(r, [], null, '')
  for (let i = 0; i < cut.length; i++) place(cut[i]!.t, [], null, cut[i]!.from)
  return [...cycles, ...rows]
}

// mapRows의 글자 줄만(panelOpenArgs와 글자 줄만 보는 시험이 씀).
export function mapLines(j: DashJudgment, unit: string, width: number, extra?: CellExtra): string[] {
  return mapRows(j, unit, width, extra).map(r => r.text)
}

// 전체, 줄마다 하나, 펼치기/접기.
export function panelButtons(lanes: Lane[], expanded: boolean): PanelButton[] {
  return [
    { key: 'unit-all', hotkey: '0', label: ALL },
    ...lanes.map((l, i): PanelButton => i < LANE_HOTKEYS.length
      ? { key: `unit-${i + 1}`, hotkey: LANE_HOTKEYS[i]!, label: l.name }
      : { key: `unit-${i + 1}`, label: l.name }),
    { key: 'expand', hotkey: 'e', label: expanded ? '접기' : '펼치기' },
  ]
}

const buttonText = (b: PanelButton) => (b.hotkey ? `${b.hotkey}: ${b.label}` : b.label)

// 버튼 폭은 터미널이 그리는 "{hotkey}: {label}", 버튼 사이 2칸. 버튼 하나가 W − 3을 넘으면 label을 줄임.
export function buttonRows(buttons: PanelButton[], width: number): PanelButton[][] {
  const rows: PanelButton[][] = []
  let row: PanelButton[] = []
  let used = 0
  for (const b0 of buttons) {
    const over = cells(buttonText(b0)) - (width - 3)
    const b = over > 0 ? { ...b0, label: fitEnd(b0.label, cells(b0.label) - over) } : b0
    const w = cells(buttonText(b))
    if (row.length > 0 && used + 2 + w > width) {
      rows.push(row)
      row = []
      used = 0
    }
    used += (row.length > 0 ? 2 : 0) + w
    row.push(b)
  }
  if (row.length > 0) rows.push(row)
  return rows
}

// 여는 높이: 접힌 전체 지도로 센 줄 수(패널 몫 덧줄은 세지 않는 하한). focus는 넘기지 않는다.
export function panelOpenArgs(state: DashState | null, columns: number):
  { id: 'harness-panel'; title: '하네스 진행'; rows: number } {
  const width = Math.max(20, columns - 4)
  const j = state?.result ?? null
  let n = 1 + (state && state.error !== '' ? 1 : 0)
  if (j && j.run) {
    const lanes = lanesOf(j)
    n += buttonRows(panelButtons(lanes, false), width).length
    n += 1 + lanes.reduce((s, l) => s + laneLines(j, l, width, { misalign: true, folded: true, expanded: false }).length, 0)
    n += 1 + mapLines(j, ALL, width).length
    if (j.unclean.length > 0) n += 1 + j.unclean.length
    if (j.unreadable.length > 0) n += 1 + j.unreadable.length
  }
  return { id: 'harness-panel', title: '하네스 진행', rows: Math.max(3, n) }
}
