// 흐름별 줄·의존 지도·버튼·여는 인자의 순수 함수 시험.
// 지도의 task 줄 찾기·열 재기는 마운트 시험과 같은 도우미(panel-helpers.ts)를 쓴다.
// 판정 JSON은 board_dash.py가 내는 꼴로 손으로 쓴다. 시험은 주어진 상황을 함수로 그려 결과 줄을 본다.
import { expect, test } from 'claude-code/testing'
import type { DashFlow, DashJudgment, DashState, DashTask } from '../types'

import {
  ALL, STATUS_MARK, buttonRows, laneLines, lanesOf, mapLines, mapRows, misalignOf, panelButtons, panelOpenArgs, shownSuffix,
  shownTitle, titlePrefix, titleSuffix, unitOf,
} from '../hooks/panel-map'
import type { CellExtra, PanelButton } from '../hooks/panel-map'
import { cells } from '../hooks/panel-text'
import { branchCol, cellOf, linked, symbolCol, taskRow } from './panel-helpers'

const FOLDED = ['완료', '보류', '백로그']

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

function flow(name: string, status: string, p: Partial<DashFlow> = {}): DashFlow {
  return { name, status, sync_pending: [], depends_on_flows: [], unreadable: false, ...p }
}

function dash(tasks: DashTask[], p: Partial<DashJudgment> = {}): DashJudgment {
  const folded: DashJudgment['folded_by_group'] = {}
  for (const t of tasks) {
    if (t.class !== 'folded') continue
    const by = (folded[t.group] ??= {})
    by[t.status] = (by[t.status] ?? 0) + 1
  }
  return {
    schema: 1, now: '2026-10-06 10:00', workdir: 'D:/w', session: 'S', message: null,
    run: { name: 'R1', dir: 'D:/w/_workspace/R1', status: '진행', run_md_unreadable: false, flow_cap: 2 },
    tasks, unreadable: [], flows: [], ready: [], held: [], undecidable: [], queue: [],
    counts: {
      by_status: { 대기: 0, 진행: 0, 자체검증: 0, 승인대기: 0, 완료: 0, 보류: 0, 백로그: 0 },
      remaining: 0, folded: 0, unreadable: 0, approval: 0, waiting_user: 0, running_agent: 0, external_progress: 0,
    },
    folded_by_group: folded, unclean: [],
    ...p,
  }
}

const OPT = { misalign: true, folded: true, expanded: false }

function laneOf(j: DashJudgment, name: string, width = 80, opt = OPT): string[] {
  return laneLines(j, lanesOf(j).find(l => l.name === name)!, width, opt)
}

// 패널의 panelExtra(P2)와 같은 꼴의 덧붙임: 시작 판단·경과 조각, 할 일·외부 작업 덧줄.
const panelLike: CellExtra = t => {
  const phrases: string[] = []
  if (t.start === 'ready') phrases.push(t.elapsed ? `시작 가능 ${t.elapsed.text}` : '시작 가능')
  else if (t.start === 'held') {
    phrases.push(`못 띄움: ${t.reason_text}`)
    if (t.elapsed) phrases.push(`기다림 ${t.elapsed.text}`)
  } else if (t.start === 'undecidable') phrases.push(`판정 못 함(${t.reason_text})`)
  else if (t.elapsed) phrases.push(`${t.elapsed.kind === 'approval' ? '승인 대기' : '진행'} ${t.elapsed.text}`)
  const lines: string[] = []
  if (t.waiting_user) lines.push(`할 일 대기: ${t.waiting_user}`)
  if (t.external_progress) lines.push(`외부 작업: ${t.external_progress}`)
  return { phrases, lines }
}

test('3.9 이름: ALL은 전체, unitOf는 없는 줄이면 전체', async () => {
  const j = dash([task({ id: 'T1', flow: 'a' })])
  expect(ALL).toBe('전체')
  expect(unitOf('a', lanesOf(j))).toBe('a')
  expect(unitOf('z', lanesOf(j))).toBe(ALL)
  expect(unitOf(ALL, lanesOf(j))).toBe(ALL)
})

test('3.5 예: 일곱 task를 W=80 mapLines(extra 없음)로 그린 줄이 설계의 예와 글자까지 같음', async () => {
  // 진행 T001, T001을 기다리는 T002·T003, T002를 기다리는 T004, T002·T003을 기다리는 T005(트리 부모 T003), 완료 T006을 기다리는 T007.
  const j = dash([
    task({ id: 'T001', status: '진행', title: '공통' }),
    task({ id: 'T002', depends_on: ['T001'], title: '패널' }),
    task({ id: 'T003', depends_on: ['T001'], title: '띠' }),
    task({ id: 'T004', depends_on: ['T002'], title: '패널 검증' }),
    task({ id: 'T005', depends_on: ['T002', 'T003'], title: '전체 검증' }),
    task({ id: 'T006', status: '완료', title: '질문' }),
    task({ id: 'T007', depends_on: ['T006'], title: '설계' }),
  ])
  // 설계 3.5의 예 그림 그대로(자식 둘과 손자, ├─·│·└─의 열, 함께 의존, 끝난 뿌리).
  expect(mapLines(j, ALL, 80)).toEqual([
    '> T001 공통  진행',
    '├─   T002 패널  대기',
    '│  └─   T004 패널 검증  대기',
    '└─   T003 띠  대기',
    '   └─   T005 전체 검증  대기 · 함께 의존: T002',
    '✓ T006 질문  완료',
    '└─   T007 설계  대기',
  ])
})

test('흐름별 줄: 요구사항·a·b·c 순서, a 진행·받아오기 대기 1, b 합쳐짐, c 폴더 없음, 요구사항 줄에 상태 없음', async () => {
  const j = dash([
    task({ id: 'T1', kind: 'req-detail', block: '요구사항' }),
    task({ id: 'T2', flow: 'a' }),
    task({ id: 'T3', flow: 'b' }),
  ], { flows: [flow('a', '진행', { sync_pending: ['x@1'] }), flow('b', '합쳐짐'), flow('c', '폴더 없음')] })
  const lanes = lanesOf(j)
  expect(lanes.map(l => l.name)).toEqual(['요구사항', 'a', 'b', 'c'])
  expect(lanes.map(l => l.isBlock)).toEqual([true, false, false, false])
  const heads = lanes.map(l => laneLines(j, l, 80, OPT)[0]!.split('  ')[0])
  expect(heads).toEqual(['요구사항', 'a', 'b', 'c'])
  expect(laneOf(j, 'a')[0]).toContain('진행')
  expect(laneOf(j, 'a')[0]).toContain('받아오기 대기 1')
  expect(laneOf(j, 'b')[0]).toContain('합쳐짐')
  expect(laneOf(j, 'c')[0]).toContain('폴더 없음')
  expect(laneOf(j, '요구사항')).toEqual(['요구사항'])
})

test('어긋남: a(진행, 합치기 완료)·b(합쳐짐, fix 진행)에 붙고 d(진행, 합치기 없음)에는 없음', async () => {
  const j = dash([
    task({ id: 'T1', kind: 'merge', status: '완료', flow: 'a' }),
    task({ id: 'T2', kind: 'fix', status: '진행', flow: 'b' }),
    task({ id: 'T3', kind: 'implementation', status: '진행', flow: 'd' }),
  ], { flows: [flow('a', '진행'), flow('b', '합쳐짐'), flow('d', '진행')] })
  const a = laneOf(j, 'a').join('\n')
  const b = laneOf(j, 'b').join('\n')
  expect(a).toContain('진행')
  expect(a).toContain('어긋남: 합치기 T1 완료')
  expect(b).toContain('합쳐짐')
  expect(b).toContain('어긋남: T2 진행')
  expect(laneOf(j, 'd').join('\n')).not.toContain('어긋남')
  expect(misalignOf(j, lanesOf(j).find(l => l.name === 'd')!)).toBeNull()
})

test('AC-6·AC-7 부모만·의존만·둘 다 적은 사본의 지도와 흐름 줄이 글자까지 같음', async () => {
  const copy = (parent: string, deps: string[]) => dash([
    task({ id: 'A', status: '완료', flow: 'a', title: '앞 일' }),
    task({ id: 'B', flow: 'a', title: '뒤 일', parent, depends_on: deps }),
  ])
  const draw = (j: DashJudgment) => [...mapLines(j, ALL, 80), ...laneOf(j, 'a')]
  const one = draw(copy('A', []))
  expect(draw(copy('', ['A']))).toEqual(one)
  expect(draw(copy('A', ['A']))).toEqual(one)
})

const AC8 = dash([
  task({ id: 'Z', status: '완료', flow: 'a' }),
  task({ id: 'A', status: '완료', flow: 'a', depends_on: ['Z'] }),
  task({ id: 'B', flow: 'a', depends_on: ['A'] }),
])

test('A(완료)·B의 task 줄이 있고 A에서 B까지 선이 이어지며 Z의 task 줄은 없음', async () => {
  const lines = mapLines(AC8, ALL, 80)
  expect(lines[taskRow(lines, 'A')]).toContain('완료')
  expect(taskRow(lines, 'B')).toBeGreaterThanOrEqual(0)
  expect(taskRow(lines, 'Z')).toBe(-1)
  expect(linked(lines, 'A', 'B')).toBe(true)
  expect(linked(lines, 'B', 'A')).toBe(false)
})

test('A의 task 줄이 B의 task 줄보다 위', async () => {
  const lines = mapLines(AC8, ALL, 80)
  expect(taskRow(lines, 'A')).toBeLessThan(taskRow(lines, 'B'))
})

test('남은 task가 없으면 지도는 "남은 task 없음" 한 줄', async () => {
  const j = dash([
    task({ id: 'T1', status: '완료', flow: 'a' }),
    task({ id: 'T2', status: '보류', flow: 'a', depends_on: ['T1'] }),
    task({ id: 'T3', status: '백로그', block: '기타' }),
  ])
  expect(mapLines(j, ALL, 80)).toEqual(['남은 task 없음'])
})

test('T1↔T2 고리: 고리 줄이 있고 두 칸이 그려짐', async () => {
  const j = dash([
    task({ id: 'T1', flow: 'a', depends_on: ['T2'] }),
    task({ id: 'T2', flow: 'a', depends_on: ['T1'] }),
  ])
  const lines = mapLines(j, ALL, 80)
  expect(lines[0]).toBe('의존 고리: T1 → T2 → T1')
  expect(taskRow(lines, 'T1')).toBeGreaterThan(0)
  expect(taskRow(lines, 'T2')).toBeGreaterThan(0)
  expect(mapLines(j, 'a', 80)[0]).toBe('의존 고리: T1 → T2 → T1')
})

test('접힌 개수: a 줄에 완료 3·보류 1, 백로그 없음, 접힌 넷의 id 없음', async () => {
  const j = dash([
    task({ id: 'T1', status: '완료', flow: 'a' }), task({ id: 'T2', status: '완료', flow: 'a' }),
    task({ id: 'T3', status: '완료', flow: 'a' }), task({ id: 'T4', status: '보류', flow: 'a' }),
    task({ id: 'T5', flow: 'a' }), task({ id: 'T6', flow: 'a' }),
  ], { flows: [flow('a', '진행')] })
  const a = laneOf(j, 'a').join('\n')
  expect(a).toContain('완료 3')
  expect(a).toContain('보류 1')
  expect(a).not.toContain('백로그')
  for (const id of ['T1', 'T2', 'T3', 'T4']) expect(a).not.toContain(id)
  // 펼치면 그 줄 아래 접힌 넷이 "{id} {status}"로 한 줄씩.
  const open = laneOf(j, 'a', 80, { ...OPT, expanded: true })
  expect(open.slice(1).map(l => l.trim())).toEqual(['T1 완료', 'T2 완료', 'T3 완료', 'T4 보류'])
})

const AC20 = [
  task({ id: 'A1', flow: 'a' }), task({ id: 'A2', flow: 'a' }),
  task({ id: 'B1', flow: 'b' }), task({ id: 'B2', flow: 'b' }),
]

test('처음 단위는 전체이고 남은 넷의 칸이 지도에 있음', async () => {
  const j = dash(AC20, { flows: [flow('a', '진행'), flow('b', '진행')] })
  expect(unitOf(ALL, lanesOf(j))).toBe(ALL)
  const lines = mapLines(j, ALL, 80)
  for (const id of ['A1', 'A2', 'B1', 'B2']) expect(taskRow(lines, id)).toBeGreaterThanOrEqual(0)
})

test('a를 고르면 a의 남은 둘만, A1 칸에 다른 흐름에 의존: B0(b), 흐름 줄은 a·b 모두', async () => {
  const j = dash([task({ id: 'B0', status: '완료', flow: 'b' }), ...AC20.map(t => (t.id === 'A1' ? { ...t, depends_on: ['B0'] } : t))],
    { flows: [flow('a', '진행'), flow('b', '진행')] })
  const lanes = lanesOf(j)
  expect(unitOf('a', lanes)).toBe('a')
  const lines = mapLines(j, 'a', 80)
  const ids = ['A1', 'A2', 'B0', 'B1', 'B2']
  expect(taskRow(lines, 'A1')).toBeGreaterThanOrEqual(0)
  expect(taskRow(lines, 'A2')).toBeGreaterThanOrEqual(0)
  for (const id of ['B0', 'B1', 'B2']) expect(taskRow(lines, id)).toBe(-1)
  expect(cellOf(lines, 'A1', ids).join('\n')).toContain('다른 흐름에 의존: B0(b)')
  expect(lanes.map(l => l.name)).toEqual(['b', 'a'])
  // 전체 지도에는 다른 흐름 덧줄이 없다.
  expect(mapLines(j, ALL, 80).join('\n')).not.toContain('다른 흐름에 의존')
})

test('한글 40자 제목·못 띄움 이유·경과가 있는 판정을 W=60·80으로: 모든 줄 cells ≤ W, 남은 id와 못 띄움 이유 조각이 칸에 있음', async () => {
  const long = (n: number) => '가나다라마바사아자차카타파하'.repeat(10).slice(0, n)
  const reasons = '흐름 상한 2, 폴더 사용 중, 받아오기 먼저, 안 합친 흐름: panel, status, 사용자 할 일 대기'
  const tasks = [
    task({ id: 'T1', title: long(40), status: '진행', flow: 'panel', elapsed: { kind: 'progress', text: '1일 3시간' } }),
    task({ id: 'T2', title: long(40), flow: 'panel', depends_on: ['T1'], start: 'held', reason_text: reasons, elapsed: { kind: 'start_wait', text: '2시간 5분' }, waiting_user: long(120) }),
    task({ id: 'T3', title: long(40), flow: 'status', depends_on: ['T1'], start: 'ready', elapsed: { kind: 'start_wait', text: '?' }, external_progress: long(80) }),
    task({ id: 'T4', title: long(40), status: '승인대기', flow: 'status', parent: 'T2', elapsed: { kind: 'approval', text: '35분' } }),
    task({ id: 'T5', title: long(40), kind: 'deploy-exec', flow: 'panel', parent: 'T3', depends_on: ['T4'], start: 'held', reason_text: '사용자 할 일 대기' }),
    task({ id: 'T6', title: long(40), status: '완료', flow: 'status' }),
  ]
  const j = dash(tasks, { flows: [flow('panel', '진행', { sync_pending: ['a@1', 'b@2'] }), flow('status', '폴더 없음')] })
  const ids = tasks.map(t => t.id)
  for (const w of [60, 80]) {
    for (const unit of [ALL, 'panel', 'status']) {
      const lines = mapLines(j, unit, w, panelLike)
      for (const l of lines) expect([w, l, cells(l) <= w]).toEqual([w, l, true])
    }
    for (const lane of lanesOf(j)) {
      for (const l of laneLines(j, lane, w, { ...OPT, expanded: true })) expect([w, l, cells(l) <= w]).toEqual([w, l, true])
    }
    const lines = mapLines(j, ALL, w, panelLike)
    for (const t of tasks.filter(x => x.class === 'remaining')) expect(taskRow(lines, t.id)).toBeGreaterThanOrEqual(0)
    for (const t of tasks.filter(x => x.start === 'held')) {
      const cell = cellOf(lines, t.id, ids)
      for (const piece of t.reason_text.split(', ')) expect([t.id, piece, cell.some(l => l.includes(piece))]).toEqual([t.id, piece, true])
    }
  }
})

// AC-29의 세 task. spec의 Given대로 한 줄(기타)에 두면 셋 중 둘이 " 패널"로 끝나 FR-4 (3)의 공통 뒷부분이 되고 T1 줄이
// "요구사항 상세"가 되어 Then과 어긋난다. 띠 AC-22와 같이 T1은 블록 요구사항, T2·T3은 블록 설계에 둔다
//(답에 따라 고침).
const AC29 = [
  task({ id: 'T1', status: '완료', block: '요구사항', title: '진행 대시보드 — 요구사항 상세: 패널' }),
  task({ id: 'T2', parent: 'T1', block: '설계', title: '진행 대시보드 — 설계: 패널' }),
  task({ id: 'T3', depends_on: ['T1'], block: '설계', title: '진행 대시보드 — 설계: 입력창 위 띠' }),
]

test('공통 앞부분을 뺀 보일 제목, 어디에도 "진행 대시보드" 없음', async () => {
  const j = dash(AC29)
  const lines = mapLines(j, ALL, 120)
  expect(lines[taskRow(lines, 'T1')]).toContain('요구사항 상세: 패널')
  expect(lines[taskRow(lines, 'T2')]).toContain('설계: 패널')
  expect(lines[taskRow(lines, 'T3')]).toContain('설계: 입력창 위 띠')
  expect(lines.join('\n')).not.toContain('진행 대시보드')
})

test('과반 규칙: 공통 앞부분은 셋이 공유하는 것, 표시 붙은 제목과 다른 제목은 그대로', async () => {
  const j = dash([
    task({ id: 'T1', title: '진행 대시보드 — 설계: 패널' }),
    task({ id: 'T2', title: '진행 대시보드 — 설계: 띠' }),
    task({ id: 'T3', title: '진행 대시보드 — 공통' }),
    task({ id: 'T4', title: '[백로그] 하네스 개선 — 의존 줄이기' }),
    task({ id: 'T5', title: '고객 문의 수정' }),
  ])
  const lines = mapLines(j, ALL, 120)
  const row = (id: string) => lines[taskRow(lines, id)]!
  expect(row('T1')).toContain('설계: 패널')
  expect(row('T1')).not.toContain('진행 대시보드')
  expect(row('T3')).toContain('공통')
  expect(row('T4')).toContain('[백로그] 하네스 개선 — 의존 줄이기')
  expect(row('T5')).toContain('고객 문의 수정')
})

test('다섯 벌: (가) 하나뿐 (나) 앞부분 없음 (다) 표시 다시 붙임 (라) 둘 다 공유 (마) 빈 제목과 a 고르기', async () => {
  const P = '진행 대시보드 — '
  const row = (lines: string[], id: string) => lines[taskRow(lines, id)]!
  const ga = mapLines(dash([task({ id: 'T1', title: P + '질문' })]), ALL, 120)
  expect(row(ga, 'T1')).toContain('진행 대시보드 — 질문')
  const na = mapLines(dash([task({ id: 'T1', title: '가 나' }), task({ id: 'T2', title: '다 라' })]), ALL, 120)
  expect(row(na, 'T1')).toContain('가 나')
  expect(row(na, 'T2')).toContain('다 라')
  const daTasks = [
    task({ id: 'T1', title: P + '설계', flow: 'a' }),
    task({ id: 'T2', title: P + '공통', flow: 'b' }),
    task({ id: 'T3', title: '[백로그] ' + P + '수정', flow: 'a' }),
  ]
  const da = mapLines(dash(daTasks), ALL, 120)
  expect(row(da, 'T3')).toContain('[백로그] 수정')
  expect(row(da, 'T3')).not.toContain('진행 대시보드')
  const ra = mapLines(dash([task({ id: 'T1', title: P + '요구사항 상세' }), task({ id: 'T2', title: P + '요약 줄' })]), ALL, 120)
  expect(row(ra, 'T1')).toContain('요구사항 상세')
  expect(row(ra, 'T2')).toContain('요약 줄')
  const ma = dash([...daTasks, task({ id: 'T4', title: '', flow: 'b' })])
  const all = mapLines(ma, ALL, 120)
  // 빈 제목은 id만: 의존 없는 대기 T4의 task 줄은 상태 기호, id, 줄 끝 상태 낱말.
  expect(row(all, 'T4')).toBe(`${STATUS_MARK['대기']} T4  대기`)
  const onA = mapLines(ma, 'a', 120)
  expect(row(onA, 'T1')).toContain('설계')
  expect(row(onA, 'T3')).toContain('[백로그] 수정')
  expect(row(onA, 'T1')).toBe(row(all, 'T1'))
  expect(titlePrefix(ma.tasks)).toBe(P)
  expect(shownTitle('[백로그] ' + P + '수정', P, '')).toBe('[백로그] 수정')
})

test('긴 제목은 칸 첫 줄 끝을 …로 줄이고 다음 줄로 잇지 않음(W=80)', async () => {
  const P = '진행 대시보드 — '
  const tail = '끝부분확인용글자열개'
  const body = '가나다라마바사아자차카타파하'.repeat(4).slice(0, 50) + tail
  const lines = mapLines(dash([task({ id: 'T1', title: P + body }), task({ id: 'T2', title: P + '공통' })]), ALL, 80)
  const t1 = lines[taskRow(lines, 'T1')]!
  expect(t1).toContain('…')
  expect(cells(t1)).toBeLessThanOrEqual(80)
  expect(lines.join('\n')).not.toContain(tail)
})

test('넘침 덧줄(함수, NFR-1): 31개에 의존하는 Z(W=60)는 트리 부모 P31 아래 한 줄, 제목 …, 함께 의존 30개는 덧줄로 내려 모두 있음', async () => {
  const ps = Array.from({ length: 31 }, (_, i) => `P${String(i + 1).padStart(2, '0')}`)
  const j = dash([...ps.map(id => task({ id, title: '앞 일' })), task({ id: 'Z', title: '모두 기다림', depends_on: ps })])
  const lines = mapLines(j, ALL, 60)
  for (const l of lines) expect([l, cells(l) <= 60]).toEqual([l, true])
  const z = cellOf(lines, 'Z', [...ps, 'Z'])
  expect(z[0]).toBe(`└─ ${STATUS_MARK['대기']} Z …  대기`)
  expect(linked(lines, 'P31', 'Z')).toBe(true)
  // 덧줄 글은 id 열 + 2(= 7열)부터이고, ", " 경계에서 이어진 줄을 다시 이으면 함께 의존 조각 그대로다.
  for (const l of z.slice(1)) expect(l.slice(0, 7)).toBe(' '.repeat(7))
  expect(z.slice(1).map(l => l.slice(7)).join(', ')).toBe(`함께 의존: ${ps.slice(0, 30).join(', ')}`)
})

// AC-39: 흐름 없는 block 설계의 완료 T001·자체검증 T002.
const AC39 = dash([
  task({ id: 'T001', kind: 'question', block: '설계', status: '완료', title: '질문 — 시험 리뷰 상위 10 지적 개선' }),
  task({ id: 'T002', kind: 'design', block: '설계', status: '자체검증', depends_on: ['T001'], title: '설계 — 시험 리뷰 상위 10 지적 개선' }),
])

test('(함수) 지도가 정확히 두 줄 "✓ T001 질문  완료"·"└─ ~ T002 설계  자체검증", 설계 줄에 공통 뒷부분, 지도에 시험 리뷰 없음', async () => {
  const lines = mapLines(AC39, ALL, 80)
  // spec 미리 보기 글자 그대로 적는다.
  expect(lines).toEqual(['✓ T001 질문  완료', '└─ ~ T002 설계  자체검증'])
  expect(branchCol(lines[1]!)).toBe(symbolCol(lines[0]!, 'T001'))
  expect(laneOf(AC39, '설계')[0]).toContain('설계 · 시험 리뷰 상위 10 지적 개선')
  expect(lines.join('\n')).not.toContain('시험 리뷰')
})

// AC-40: 의존 없는 대기 T1·진행 T2·자체검증 T3·승인대기 T4·대기 T5, 완료 T6·보류 T7·백로그 T8에 각각 의존하는 대기 T9·T10·T11.
const AC40 = dash([
  task({ id: 'T1', title: '하나' }), task({ id: 'T2', status: '진행', title: '둘' }), task({ id: 'T3', status: '자체검증', title: '셋' }),
  task({ id: 'T4', status: '승인대기', title: '넷' }), task({ id: 'T5', status: '대기', title: '다섯' }),
  task({ id: 'T6', status: '완료', title: '여섯' }), task({ id: 'T7', status: '보류', title: '일곱' }), task({ id: 'T8', status: '백로그', title: '여덟' }),
  task({ id: 'T9', depends_on: ['T6'], title: '아홉' }), task({ id: 'T10', depends_on: ['T7'], title: '열' }),
  task({ id: 'T11', depends_on: ['T8'], title: '열하나' }),
])

test('(함수) id 열한 개마다 task 줄 하나, id 앞 두 글자가 STATUS_MARK와 공백, T6·T7·T8 줄에 완료·보류·백로그', async () => {
  const lines = mapLines(AC40, ALL, 120)
  for (const t of AC40.tasks) {
    expect([t.id, lines.filter(l => taskRow([l], t.id) === 0).length]).toEqual([t.id, 1])
    const line = lines[taskRow(lines, t.id)]!
    const at = symbolCol(line, t.id)
    expect([t.id, line.slice(at, at + 2)]).toEqual([t.id, STATUS_MARK[t.status] + ' '])
  }
  for (const id of ['T6', 'T7', 'T8']) {
    const t = AC40.tasks.find(x => x.id === id)!
    expect(lines[taskRow(lines, id)]).toContain(t.status)
  }
})

test('(함수, 부분) mapRows의 dim: 끝난 T6·T7·T8의 task 줄만 참', async () => {
  const rows = mapRows(AC40, ALL, 120)
  const texts = rows.map(r => r.text)
  expect(mapLines(AC40, ALL, 120)).toEqual(texts)
  for (const t of AC40.tasks) expect([t.id, rows[taskRow(texts, t.id)]!.dim]).toEqual([t.id, t.class === 'folded'])
})

test('(함수) A1·A2를 기다리는 B: B 줄 하나가 A2 아래, ├·└가 A2의 기호 열, 함께 의존: A1, A1과는 선 없음', async () => {
  const lines = mapLines(dash([
    task({ id: 'A1', flow: 'a' }), task({ id: 'A2', flow: 'a' }), task({ id: 'B', flow: 'a', depends_on: ['A1', 'A2'] }),
  ]), ALL, 80)
  const b = taskRow(lines, 'B')
  expect(lines.filter(l => taskRow([l], 'B') === 0)).toHaveLength(1)
  expect(symbolCol(lines[taskRow(lines, 'A1')]!, 'A1')).toBe(0)
  expect(symbolCol(lines[taskRow(lines, 'A2')]!, 'A2')).toBe(0)
  expect(b).toBeGreaterThan(taskRow(lines, 'A2'))
  expect(branchCol(lines[b]!)).toBe(0)
  expect(lines[b]).toContain('함께 의존: A1')
  expect(linked(lines, 'A2', 'B')).toBe(true)
  expect(linked(lines, 'A1', 'B')).toBe(false)
})

test('(함수) 25 사슬 W=60: 모든 줄 ≤ 60, 25개 task 줄, 선 생략 줄은 T12·T23이고 기호가 0열, 끝 열넷 줄이 T12~T22 다음 T23~T25', async () => {
  const ids = Array.from({ length: 25 }, (_, i) => `T${String(i + 1).padStart(2, '0')}`)
  const j = dash(ids.map((id, i) => task({ id, depends_on: i === 0 ? [] : [ids[i - 1]!] })))
  const lines = mapLines(j, ALL, 60)
  for (const l of lines) expect([l, cells(l) <= 60]).toEqual([l, true])
  for (const id of ids) expect([id, taskRow(lines, id) >= 0]).toEqual([id, true])
  const cut = lines.filter(l => l.includes('선 생략: '))
  expect(cut.length).toBeGreaterThanOrEqual(1)
  for (const l of cut) {
    const t = j.tasks.find(x => taskRow([l], x.id) === 0)!
    expect([t.id, t.depends_on.includes(/선 생략: (\S+)/.exec(l)![1]!), symbolCol(l, t.id)]).toEqual([t.id, true, 0])
  }
  // 설계 R-5: 깊이 11(3·11 = 33 > 30)에서 떼므로 뗀 줄은 T12·T23이고, 뗀 부분 트리는 지도 맨 끝에 뗀 순서대로 놓인다.
  expect(cut.map(l => j.tasks.find(x => taskRow([l], x.id) === 0)!.id)).toEqual(['T12', 'T23'])
  expect(cut.map(l => /선 생략: (\S+)/.exec(l)![1])).toEqual(['T11', 'T22'])
  expect(lines.slice(-14).map(l => ids.find(id => taskRow([l], id) === 0))).toEqual(ids.slice(11))
})

test('(함수) 공통 뒷부분: (가) a 줄은 " — 묶음 하나", 보일 제목에서 빠짐 (나) " 시험", 남는 글자가 없으면 그대로, 보일 뒷부분', async () => {
  const ga = dash([
    task({ id: 'T1', flow: 'a', title: '가 — 묶음 하나' }), task({ id: 'T2', flow: 'a', title: '나 — 묶음 하나' }),
    task({ id: 'T3', flow: 'a', title: '다 — 다른 것' }),
    task({ id: 'T4', block: '요구사항', title: '라 — 묶음 둘' }), task({ id: 'T5', block: '요구사항', title: '마 — 묶음 둘' }),
  ], { flows: [flow('a', '진행')] })
  expect(titleSuffix(ga.tasks.filter(t => t.group === 'a'))).toBe(' — 묶음 하나')
  expect(laneOf(ga, 'a')[0]).toContain('a · 묶음 하나')
  expect(laneOf(ga, '요구사항')[0]).toContain('요구사항 · 묶음 둘')
  const gaLines = mapLines(ga, ALL, 120)
  const row = (lines: string[], id: string) => lines[taskRow(lines, id)]!
  expect(row(gaLines, 'T1')).toContain('가')
  expect(row(gaLines, 'T1')).not.toContain('묶음 하나')
  expect(row(gaLines, 'T3')).toContain('다 — 다른 것')
  expect(row(gaLines, 'T4')).toContain('라')
  expect(row(gaLines, 'T4')).not.toContain('묶음 둘')
  const na = dash([
    task({ id: 'T1', block: '설계', title: '진행 대시보드 — 설계 — 시험' }),
    task({ id: 'T2', block: '설계', title: '진행 대시보드 — 공통 — 시험' }),
    task({ id: 'T3', block: '설계', title: '— 시험' }),
  ])
  expect(titleSuffix(na.tasks)).toBe(' 시험')
  expect(shownSuffix(' — 시험')).toBe('시험')
  const naLines = mapLines(na, ALL, 120)
  expect(row(naLines, 'T1')).toContain('설계')
  for (const word of ['진행 대시보드', '설계 —', '시험']) expect([word, row(naLines, 'T1').includes(word)]).toEqual([word, false])
  expect(row(naLines, 'T3')).toContain('— 시험')
  expect(laneOf(na, '설계')[0]).toContain('· 시험')
})

const lanesN = (n: number) => lanesOf(dash(Array.from({ length: n }, (_, i) => task({ id: `T${i + 1}`, flow: `흐름${i + 1}` }))))

test('panelButtons: 줄 12개면 0, 1~9, a, b, c, 마지막 expand·e이고 줄 버튼에 e 없음. 줄 40개면 35번째부터 단축키 없음', async () => {
  const b12 = panelButtons(lanesN(12), false)
  expect(b12.map(b => b.hotkey)).toEqual(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'e'])
  expect(b12[0]).toEqual({ key: 'unit-all', hotkey: '0', label: '전체' })
  expect(b12[1]).toEqual({ key: 'unit-1', hotkey: '1', label: '흐름1' })
  expect(b12.at(-1)).toEqual({ key: 'expand', hotkey: 'e', label: '펼치기' })
  expect(b12.slice(1, -1).some(b => b.hotkey === 'e')).toBe(false)
  expect(panelButtons(lanesN(1), true).at(-1)!.label).toBe('접기')
  const b40 = panelButtons(lanesN(40), false).slice(1, -1)
  expect(b40[33]!.hotkey).toBe('z')
  expect(b40.slice(0, 34).every(b => b.hotkey !== undefined)).toBe(true)
  expect(b40.slice(34).every(b => b.hotkey === undefined)).toBe(true)
  expect(b40.slice(34).map(b => b.key)).toEqual(['unit-35', 'unit-36', 'unit-37', 'unit-38', 'unit-39', 'unit-40'])
})

test('buttonRows: W=60에서 버튼 줄마다 버튼 폭 합 + 사이 2칸 ≤ 60, 순서 그대로', async () => {
  const width = (b: PanelButton) => cells(b.hotkey ? `${b.hotkey}: ${b.label}` : b.label)
  const long = dash([task({ id: 'T1', flow: '아주 긴 흐름 이름'.repeat(8) }), ...Array.from({ length: 39 }, (_, i) => task({ id: `U${i}`, flow: `흐름${i}` }))])
  for (const buttons of [panelButtons(lanesN(12), false), panelButtons(lanesOf(long), false)]) {
    const rows = buttonRows(buttons, 60)
    expect(rows.length).toBeGreaterThan(1)
    for (const row of rows) expect(row.reduce((s, b) => s + width(b), 0) + 2 * (row.length - 1)).toBeLessThanOrEqual(60)
    expect(rows.flat().map(b => b.key)).toEqual(buttons.map(b => b.key))
  }
})

test('panelOpenArgs: state가 null이면 rows 3, 손으로 쓴 판정은 3.3 「여는 높이」 식으로 센 값, focus 없음', async () => {
  expect(panelOpenArgs(null, 84)).toEqual({ id: 'harness-panel', title: '하네스 진행', rows: 3 })
  const j = dash([
    task({ id: 'T1', status: '완료', flow: 'a', running_agent: 'code-T1' }),
    task({ id: 'T2', flow: 'a', depends_on: ['T1'], title: '뒤 일' }),
    task({ id: 'T3', status: '진행', flow: 'b', title: '다른 일' }),
  ], { flows: [flow('a', '진행'), flow('b', '진행'), flow('c', '폴더 없음')], unclean: [{ id: 'T1', keys: ['running_agent'] }] })
  const state: DashState = { result: j, error: '', at: 0, invokedAt: null }
  // columns 84 → W = 80. 손으로 센 줄 수:
  //   머리 1 + 오류 0
  //   + 버튼 줄 1 ("0: 전체" 7 + "1: a" 4 + "2: b" 4 + "3: c" 4 + "e: 펼치기" 9 + 사이 2칸×4 = 36 ≤ 80)
  //   + "흐름별 상태" 1 + 줄 3 (a "a  진행  완료 1", b "b  진행", c "c  폴더 없음", 각 한 줄)
  //   + "의존 지도" 1 + 지도 3 (T1·T2·T3마다 task 줄 하나, T1은 T2의 의존하는 task라 그려짐. 덧줄 없음)
  //   + 정리 안 된 값 2 (머리 1 + T1 한 줄) + 읽지 못함 0
  //   = 1 + 0 + 1 + 1 + 3 + 1 + 3 + 2 = 12
  const args = panelOpenArgs(state, 84)
  expect(args).toEqual({ id: 'harness-panel', title: '하네스 진행', rows: 12 })
  expect('focus' in args).toBe(false)
  // 판정 실패만 있고 결과가 없으면 1 + 1 → 하한 3. 실행이 없을 때도 1 + 오류.
  expect(panelOpenArgs({ result: null, error: 'x', at: 0, invokedAt: null }, 84).rows).toBe(3)
  expect(panelOpenArgs({ result: dash([], { run: null, message: '이 세션이 진행하는 실행 없음' }), error: '', at: 0, invokedAt: null }, 84).rows).toBe(3)
})
