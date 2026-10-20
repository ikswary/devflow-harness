// 띠의 요약 줄·버튼·줄 목록·테두리의 순수 함수 시험.
// 판정 JSON은 board_dash.py가 내는 꼴로 손으로 쓴다. 시험은 주어진 상황을 함수로 그려 결과 줄을 본다.
import { expect, test } from 'claude-code/testing'
import type { DashFlow, DashJudgment, DashState, DashTask } from '../types'

import { ALL, buttonRows, laneLines, mapRows } from '../hooks/panel-map'
import { cells } from '../hooks/panel-text'
import {
  bandButtons, bandFrame, bandLaneRows, bandLanes, bandReady, bandRows, frameBottom, frameTop, innerWidth, noRunLine, summaryLine,
} from '../hooks/status-view'
import type { Row } from '../hooks/status-view'
import { DASH_A, DASH_B, READY_B } from './status-fx-waiting-user'
import { taskRow } from './status-helpers'

const FOLDED = ['완료', '보류', '백로그']
const LANE_OPT = { misalign: false, folded: false, expanded: false }

function task(p: Partial<DashTask> & { id: string }): DashTask {
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

function flow(name: string, status = '진행', p: Partial<DashFlow> = {}): DashFlow {
  return { name, status, sync_pending: [], depends_on_flows: [], unreadable: false, ...p }
}

// counts는 tasks에서 common C1 꼴로 센다(남은 task만 approval·waiting_user·running_agent, 접힌 것은 folded).
function dash(tasks: DashTask[], p: Partial<DashJudgment> = {}): DashJudgment {
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
    schema: 1, now: '2026-10-06 10:00', workdir: 'D:/w', session: 'S', message: null,
    run: { name: 'R1', dir: 'D:/w/_workspace/R1', status: '진행', run_md_unreadable: false, flow_cap: 2 },
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

// AC-1의 X: 승인대기 2(요청 시각 없음), 대기 3(의존이 풀린 design 둘, 안 풀린 하나), 진행 1(에이전트), 완료 4, 흐름 없음.
function ac1(): DashJudgment {
  const unknown = { kind: 'approval' as const, text: '?' }
  return dash([
    task({ id: 'T001', kind: 'design', status: '완료' }),
    task({ id: 'T002', kind: 'design', status: '완료', parent: 'T001' }),
    task({ id: 'T003', kind: 'design', status: '완료', parent: 'T001' }),
    task({ id: 'T004', kind: 'design', status: '완료', parent: 'T001' }),
    task({ id: 'T010', kind: 'design', status: '승인대기', parent: 'T001', elapsed: unknown }),
    task({ id: 'T011', kind: 'design', status: '승인대기', parent: 'T001', elapsed: unknown }),
    task({ id: 'T020', kind: 'design', status: '대기', parent: 'T001', start: 'ready' }),
    task({ id: 'T021', kind: 'design', status: '대기', parent: 'T001', start: 'ready' }),
    task({ id: 'T022', kind: 'design', status: '대기', depends_on: ['T010'] }),
    task({ id: 'T030', kind: 'design', status: '진행', parent: 'T001', running_agent: 'design-T030' }),
  ], { run: { name: '2026-10-06-demo', dir: 'D:/w/_workspace/2026-10-06-demo', status: '진행', run_md_unreadable: false, flow_cap: 2 } })
}

const AC1_LINE = '승인 대기 2(가장 오래 ?) · 할 일 대기 0 · 에이전트 1 · 시작 가능 2 · 대기 3, 진행 1, 승인대기 2, 접힘 4'

// AC-12의 실행: 흐름 common·panel에 각각 남은 task.
function twoFlows(): DashJudgment {
  return dash([
    task({ id: 'T001', kind: 'design', status: '완료', block: '설계' }),
    task({ id: 'T040', flow: 'common', parent: 'T001', start: 'ready' }),
    task({ id: 'T041', flow: 'common', depends_on: ['T040'] }),
    task({ id: 'T044', flow: 'panel', depends_on: ['T040'] }),
  ], { flows: [flow('common'), flow('panel')] })
}

const buttonTexts = (bs: { hotkey?: string; label: string }[]) => bs.map(b => (b.hotkey ? `${b.hotkey}: ${b.label}` : b.label))
const texts = (rows: Row[]) => rows.map(r => (r.kind === 'text' ? r.text : buttonTexts(r.buttons).join('  ')))
// 펼친 띠의 셋째 줄부터: bandLaneRows의 흐름 줄(흐림 없음)과 mapRows의 지도 줄(흐림 그대로), W=120.
const openRows = (j: DashJudgment, unit: string): Row[] => [
  ...bandLaneRows(j).flatMap(l => laneLines(j, l, 120, LANE_OPT)).map((text): Row => ({ kind: 'text', text })),
  ...mapRows(j, unit, 120).map(({ text, dim }): Row => ({ kind: 'text', text, dim })),
]

test('요약 줄(W=200): 설계 8.3의 줄과 글자까지 같고 자체검증이 없음', async () => {
  const line = summaryLine(ac1(), 200)
  expect(line).toBe(AC1_LINE)
  expect(line).not.toContain('자체검증')
})

test('완료 task의 running_agent·waiting_user는 수에 들지 않고 접힘 6', async () => {
  const j = ac1()
  j.tasks.push(
    task({ id: 'T005', kind: 'design', status: '완료', running_agent: 'x' }),
    task({ id: 'T006', kind: 'design', status: '완료', waiting_user: 'y' }),
  )
  const line = summaryLine(dash(j.tasks, { run: j.run }), 200)
  expect(line).toContain('에이전트 1')
  expect(line).toContain('할 일 대기 0')
  expect(line).toContain('접힘 6')
})

test('재료: DASH_B는 DASH_A보다 시작 가능 1 작고 할 일 대기 1 크며, 시작 가능 수가 READY_B의 n과 같음', async () => {
  const num = (line: string, word: string) => Number(new RegExp(`${word} (\\d+)`).exec(line)![1])
  const a = summaryLine(DASH_A, 200)
  const b = summaryLine(DASH_B, 200)
  const n = Number(/지금 시작할 수 있는 task (\d+)개/.exec(READY_B)![1])
  expect(num(b, '시작 가능')).toBe(n)
  expect(num(b, '시작 가능')).toBe(num(a, '시작 가능') - 1)
  expect(num(b, '할 일 대기')).toBe(num(a, '할 일 대기') + 1)
})

test('AC-4·AC-7 가장 오래: 요청 시각이 가장 이른 승인대기의 경과, 요청 시각 없거나 ?인 것은 건넘', async () => {
  const j = dash([
    task({ id: 'T1', status: '승인대기', approval_requested: '2026-10-06 08:55', elapsed: { kind: 'approval', text: '1시간 5분' } }),
    task({ id: 'T2', status: '승인대기', approval_requested: '2026-10-06 09:40', elapsed: { kind: 'approval', text: '20분' } }),
    task({ id: 'T3', status: '승인대기', elapsed: { kind: 'approval', text: '?' } }),
    task({ id: 'T4', status: '승인대기', approval_requested: '2026-10-05 07:00', elapsed: { kind: 'approval', text: '?' } }),
  ])
  expect(summaryLine(j, 200)).toContain('승인 대기 4(가장 오래 1시간 5분)')
  const one = dash([task({ id: 'T1', status: '승인대기', approval_requested: '2026-10-05 07:00', elapsed: { kind: 'approval', text: '1일 3시간' } })])
  expect(summaryLine(one, 200)).toContain('(가장 오래 1일 3시간)')
})

test('AC-5·AC-6 요청 시각 없는 승인대기 하나면 (가장 오래 ?), 승인대기가 없으면 가장 오래 없음', async () => {
  expect(summaryLine(dash([task({ id: 'T1', status: '승인대기' })]), 200)).toContain('승인 대기 1(가장 오래 ?)')
  const none = summaryLine(dash([task({ id: 'T1' })]), 200)
  expect(none).toContain('승인 대기 0')
  expect(none).not.toContain('가장 오래')
})

test('상태별 수: 대기·진행·자체검증·승인대기 차례, 그다음 접힘·읽지 못함, 0은 뺌', async () => {
  const j = dash([
    task({ id: 'T1', status: '진행' }), task({ id: 'T2', status: '자체검증' }), task({ id: 'T3', status: '보류' }),
  ])
  j.counts.unreadable = 2
  expect(summaryLine(j, 200)).toEndWith(' · 진행 1, 자체검증 1, 접힘 1, 읽지 못함 2')
  expect(summaryLine(dash([]), 200)).toBe('승인 대기 0 · 할 일 대기 0 · 에이전트 0 · 시작 가능 0')
})

test('상태별 수만 빠지는 폭: 상태별 수 없고 나머지 다섯 있고 cells ≤ W', async () => {
  const w = cells(AC1_LINE) - cells(' · 대기 3, 진행 1, 승인대기 2, 접힘 4')
  const line = summaryLine(ac1(), w)
  expect(line).toBe('승인 대기 2(가장 오래 ?) · 할 일 대기 0 · 에이전트 1 · 시작 가능 2')
  for (const part of ['승인 대기 2', '할 일 대기 0', '에이전트 1', '시작 가능 2']) expect(line).toContain(part)
  expect(line).not.toContain('대기 3')
  expect(cells(line)).toBeLessThanOrEqual(w)
  expect(summaryLine(ac1(), w - 1)).not.toContain('시작 가능')
})

test('줄이기 차례: 상태별 수 → 시작 가능 → 에이전트 → (가장 오래 …)', async () => {
  const j = ac1()
  const steps = [
    '승인 대기 2(가장 오래 ?) · 할 일 대기 0 · 에이전트 1 · 시작 가능 2',
    '승인 대기 2(가장 오래 ?) · 할 일 대기 0 · 에이전트 1',
    '승인 대기 2(가장 오래 ?) · 할 일 대기 0',
    '승인 대기 2 · 할 일 대기 0',
  ]
  for (const s of steps) expect(summaryLine(j, cells(s))).toBe(s)
})

test('W=20: …로 끝나고 cells ≤ 20, 실행 이름·에이전트·시작 가능·상태별 수·가장 오래 없음', async () => {
  const line = summaryLine(ac1(), 20)
  expect(line).toEndWith('…')
  expect(cells(line)).toBeLessThanOrEqual(20)
  for (const part of ['2026-10-06-demo', '에이전트', '시작 가능', '대기 3', '가장 오래']) expect(line).not.toContain(part)
})

test('흐름 common·panel: 버튼이 m 지도 펼치기, a *전체, b common, c panel, p 패널 열기', async () => {
  const j = twoFlows()
  expect(buttonTexts(bandButtons(bandLanes(j), ALL, false))).toEqual(['m: 지도 펼치기', 'a: *전체', 'b: common', 'c: panel', 'p: 패널 열기'])
  expect(bandButtons(bandLanes(j), ALL, false).map(b => b.key)).toEqual(['map-toggle', 'unit-all', 'unit-1', 'unit-2', 'open-panel'])
})

test('흐름 없음(flow 빈 값, block 있음, flows 빈 목록): 버튼이 m·a·p 셋뿐', async () => {
  const j = dash([task({ id: 'T1', kind: 'design', block: '설계' }), task({ id: 'T2', kind: 'design', block: '설계' })])
  expect(bandLanes(j)).toEqual([])
  expect(buttonTexts(bandButtons(bandLanes(j), ALL, false))).toEqual(['m: 지도 펼치기', 'a: *전체', 'p: 패널 열기'])
})

test('버튼: 펼침은 map-toggle의 label만 다르고, 고른 흐름에 *, 흐름 23번째부터 단축키 없음', async () => {
  const lanes = bandLanes(twoFlows())
  const shut = bandButtons(lanes, 'common', false)
  const open = bandButtons(lanes, 'common', true)
  expect(open.map(b => b.key)).toEqual(shut.map(b => b.key))
  expect(open.map(b => b.hotkey)).toEqual(shut.map(b => b.hotkey))
  expect(buttonTexts(open)).toEqual(['m: 지도 접기', 'a: 전체', 'b: *common', 'c: panel', 'p: 패널 열기'])
  const many = Array.from({ length: 25 }, (_, i) => ({ name: `f${i + 1}`, isBlock: false }))
  const hk = bandButtons(many, ALL, false).filter(b => b.key.startsWith('unit-') && b.key !== 'unit-all').map(b => b.hotkey)
  expect(hk.slice(0, 22).join('')).toBe('bcdfghijklnoqrstuvwxyz')
  expect(hk.slice(22)).toEqual([undefined, undefined, undefined])
})

test('AC-27·AC-28 줄 목록: 접음은 요약·버튼 두 줄, 펼침은 셋째 줄부터 bandLaneRows의 흐름 줄과 mapRows(전체, 흐림 포함)', async () => {
  const j = twoFlows()
  const shut = bandRows(j, { unit: ALL, expanded: false }, 120)
  expect(shut.map(r => r.kind)).toEqual(['text', 'buttons'])
  expect(texts(shut)).toEqual([summaryLine(j, 120), 'm: 지도 펼치기  a: *전체  b: common  c: panel  p: 패널 열기'])
  const open = bandRows(j, { unit: ALL, expanded: true }, 120)
  expect(texts(open).slice(0, 2)).toEqual([summaryLine(j, 120), 'm: 지도 접기  a: *전체  b: common  c: panel  p: 패널 열기'])
  expect(open.slice(2).every(r => r.kind === 'text')).toBe(true)
  expect(open.slice(2)).toEqual(openRows(j, ALL))
  // 끝난 T001(완료)의 지도 줄은 흐림이 참으로 넘어온다.
  const dimmed = texts(open.filter(r => r.kind === 'text' && r.dim === true))
  expect(dimmed).toHaveLength(1)
  expect(taskRow(dimmed, 'T001')).toBe(0)
  // 남은 셋의 task 줄은 펼침의 지도 부분(셋째 줄부터)에만 있다.
  for (const id of ['T040', 'T041', 'T044']) {
    expect([id, taskRow(texts(shut), id)]).toEqual([id, -1])
    expect([id, taskRow(texts(open), id) >= 2]).toEqual([id, true])
  }
})

test('고른 흐름: 지도는 그 흐름만, 사라진 흐름이면 전체', async () => {
  const j = twoFlows()
  const oneRows = bandRows(j, { unit: 'common', expanded: true }, 120)
  const one = texts(oneRows)
  expect(one[1]).toContain('b: *common')
  expect(oneRows.slice(2)).toEqual(openRows(j, 'common'))
  expect(one.join('\n')).not.toContain('T044')
  for (const id of ['T040', 'T041']) expect([id, taskRow(one, id) >= 2]).toEqual([id, true])
  const gone = texts(bandRows(j, { unit: 'harness', expanded: false }, 120))
  expect(gone[1]).toContain('a: *전체')
  // 블록 줄 이름은 띠의 지도 단위가 아님: 전체로 그림.
  expect(bandRows(j, { unit: '설계', expanded: true }, 120).slice(2)).toEqual(openRows(j, ALL))
})

test('흐름 common과 block 설계인 흐름 없는 남은 task: 펼친 띠에 common 줄은 있고 이름만인 설계 줄은 없음', async () => {
  const j = dash([
    task({ id: 'T040', flow: 'common', start: 'ready' }),
    task({ id: 'T050', kind: 'design', block: '설계' }),
  ], { flows: [flow('common')] })
  const rows = bandRows(j, { unit: ALL, expanded: true }, 120)
  const nButtons = rows.filter(r => r.kind === 'buttons').length
  const laneRows = texts(rows).slice(1 + nButtons, 1 + nButtons + 1)
  expect(laneRows[0]!.startsWith('common')).toBe(true)
  expect(texts(rows).some(t => t.startsWith('설계'))).toBe(false)
  expect(bandButtons(bandLanes(j), ALL, false).map(b => b.label)).not.toContain('설계')
})

test('flow.md 없이 블록·기타 묶음만 있는 실행: 펼친 띠에 이름만 있는 줄이 없음', async () => {
  const j = dash([
    task({ id: 'T001', kind: 'question', status: '완료', block: '질문' }),
    task({ id: 'T005', kind: 'req-detail', block: '요구사항' }),
    task({ id: 'T009', kind: 'change' }),
    task({ id: 'T010', kind: 'design', flow: 'common', block: '설계' }),
  ])
  const rows = bandRows(j, { unit: ALL, expanded: true }, 120)
  for (const name of ['질문', '요구사항', '기타', 'common']) expect([name, texts(rows).includes(name)]).toEqual([name, false])
  expect(rows.slice(2)).toEqual(openRows(j, ALL))
})

test('버튼 줄 나누기: 좁으면 버튼 줄이 여러 줄이고 요약은 한 줄', async () => {
  const j = dash([], { flows: ['common', 'harness', 'panel', 'status'].map(n => flow(n)) })
  const rows = bandRows(j, { unit: ALL, expanded: false }, 60)
  expect(rows[0]!.kind).toBe('text')
  expect(rows.length).toBeGreaterThan(2)
  expect(rows.slice(1).every(r => r.kind === 'buttons')).toBe(true)
  expect(rows.slice(1).flatMap(r => (r.kind === 'buttons' ? r.buttons.map(b => b.key) : []))).toEqual(
    ['map-toggle', 'unit-all', 'unit-1', 'unit-2', 'unit-3', 'unit-4', 'open-panel'])
  for (const t of texts(rows)) expect(cells(t)).toBeLessThanOrEqual(60)
})

test('noRunLine: 판정의 message, 판정이 없으면 판정 결과 없음, 폭을 넘으면 …', async () => {
  const j = dash([], { run: null, message: '이 세션이 진행하는 실행 없음' })
  const s: DashState = { result: j, error: '', at: 0, invokedAt: 1 }
  expect(noRunLine(s, 120)).toBe('이 세션이 진행하는 실행 없음')
  expect(noRunLine(null, 120)).toBe('판정 결과 없음')
  expect(noRunLine({ result: null, error: 'x', at: 0, invokedAt: 1 }, 120)).toBe('판정 결과 없음')
  const short = noRunLine(s, 10)
  expect(short).toEndWith('…')
  expect(cells(short)).toBeLessThanOrEqual(10)
})

// 마운트 시험은 엔진이 던진 훅을 건너뛰어 '비킴'과 '던짐'이 같은 빈 목록이 되므로, 가드는 여기서 가른다.
test('3.2 bandReady: flows 없음·counts 없음·둘 다 없음은 거짓, 둘 다 있으면 참', async () => {
  const j = dash([], { flows: [flow('status')] })
  const { flows: _f, ...noFlows } = j
  const { counts: _c, ...noCounts } = j
  const { flows: _f2, counts: _c2, ...neither } = j
  expect(bandReady(noFlows as DashJudgment)).toBe(false)
  expect(bandReady(noCounts as DashJudgment)).toBe(false)
  expect(bandReady(neither as DashJudgment)).toBe(false)
  expect(bandReady(j)).toBe(true)
  expect(bandReady(dash([]))).toBe(true)
})

const RUN_NAME = '2026-01-01-sample-run-fixes'

test('3.5.1·B-20 frameTop: 이름이 넘치면 날짜를 먼저 떼고 끝을 …, 자리가 없거나 이름이 없으면 선만. frameBottom, innerWidth', async () => {
  expect(frameTop(RUN_NAME, 26)).toBe('╭─ sample-run-fixes ─────╮')
  expect(frameTop(RUN_NAME, 20)).toBe('╭─ sample-run-fi… ─╮')
  expect(frameTop(RUN_NAME, 6)).toBe('╭────╮')
  expect(frameTop(RUN_NAME, 7)).toBe('╭─ … ─╮')
  // 이름 자리 33 − 6 = 27 = 이름 칸 수: 날짜를 떼지 않는다.
  expect(frameTop(RUN_NAME, 33)).toBe('╭─ 2026-01-01-sample-run-fixes ─╮')
  expect(frameTop(null, 80)).toBe('╭' + '─'.repeat(78) + '╮')
  expect(frameBottom(80)).toBe('╰' + '─'.repeat(78) + '╯')
  for (const w of [26, 20, 6, 7, 33]) expect([w, cells(frameTop(RUN_NAME, w))]).toEqual([w, w])
  expect(innerWidth(3)).toBe(0)
  expect(innerWidth(80)).toBe(76)
})

test('3.5.1·B-23 bandFrame: 첫·끝은 테두리, 글 줄 채움 = 안쪽 폭 − 글 칸 수, 버튼 줄은 버튼 글 + 사이 2칸으로 셈, 넓은 글은 채움 없음', async () => {
  const rows: Row[] = [
    { kind: 'text', text: '가나', dim: true },
    { kind: 'buttons', buttons: [{ key: 'unit-all', hotkey: 'a', label: '전체' }, { key: 'unit-24', label: '*panel' }] },
    { kind: 'text', text: 'x'.repeat(30) },
  ]
  const framed = bandFrame('R1', rows, 20)
  expect(framed).toHaveLength(5)
  expect(framed[0]).toEqual({ kind: 'edge', text: frameTop('R1', 20) })
  expect(framed[4]).toEqual({ kind: 'edge', text: frameBottom(20) })
  // 안쪽 폭 16: 글 "가나" 4칸 → 채움 12, 흐림은 그대로.
  expect(framed[1]).toEqual({ kind: 'text', text: '가나', dim: true, fill: ' '.repeat(12) })
  // 버튼 줄: "a: 전체" 7 + 2 + "*panel" 6 = 15 → 채움 1.
  expect(framed[2]).toEqual({ ...rows[1]!, fill: ' ' })
  // 안쪽 폭보다 넓은 글(30칸): 채움 없음.
  expect(framed[3]).toEqual({ kind: 'text', text: 'x'.repeat(30), fill: '' })
})

test('B-22 bandRows: 안쪽 폭 2에서 버튼은 단축키 없이 이름이 …, 안쪽 폭 76에서는 buttonRows 그대로', async () => {
  const j = twoFlows()
  const view = { unit: ALL, expanded: false }
  const narrow = bandRows(j, view, 2).flatMap(r => (r.kind === 'buttons' ? r.buttons : []))
  expect(narrow.map(b => b.key)).toEqual(['map-toggle', 'unit-all', 'unit-1', 'unit-2', 'open-panel'])
  for (const b of narrow) expect(b).toEqual({ key: b.key, label: '…' })
  const wide = bandRows(j, view, 76).filter(r => r.kind === 'buttons')
  expect(wide).toEqual(buttonRows(bandButtons(bandLanes(j), ALL, false), 76).map(buttons => ({ kind: 'buttons', buttons })))
  expect(texts(wide)).toEqual(['m: 지도 펼치기  a: *전체  b: common  c: panel  p: 패널 열기'])
})
