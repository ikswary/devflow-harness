// 패널이 그린 내용의 마운트 시험.
// 판정은 common의 길로 넣고 명령으로 연 Pane을 마운트해 그린 줄(linesOf)로 본다. 따로 적지 않으면 W=80.
import { expect, test } from 'claude-code/testing'

import { ALL, STATUS_MARK, mapLines } from '../hooks/panel-map'
import { cells } from '../hooks/panel-text'
import { panelExtra } from '../hooks/panel-view'
import type { DashJudgment } from '../types'
import { DASH as READY_FX, READY } from './panel-fx-ready'
import { DASH as RUN59 } from './panel-fx-run59'
import { DASH as RUN89 } from './panel-fx-run89'
import {
  branchCol, cellOf, dash, flow, keyOf, laneOf, laneSection, linesOf, linked, mapSection, mountPane, openPanel, readyLists,
  refeed, rowsOf, symbolCol, task, taskRow, uncleanSection,
} from './panel-helpers'

const idsOf = (j: DashJudgment) => j.tasks.map(t => t.id)
const cell = (lines: string[], j: DashJudgment, id: string) => cellOf(lines, id, idsOf(j))
const rowOf = (lines: string[], id: string) => mapSection(lines)[taskRow(mapSection(lines), id)] ?? ''

test('흐름별 줄: 요구사항·a·b·c 순서, a 진행·받아오기 대기 1, b 합쳐짐, c 폴더 없음, 요구사항 줄에 상태 없음', async ($, on) => {
  const j = dash([
    task({ id: 'T1', kind: 'req-detail', block: '요구사항' }),
    task({ id: 'T2', flow: 'a' }),
    task({ id: 'T3', flow: 'b' }),
  ], { flows: [flow('a', '진행', { sync_pending: ['x@1'] }), flow('b', '합쳐짐'), flow('c', '폴더 없음')] })
  const { lines } = await openPanel($, on, j)
  const heads = laneSection(lines).filter(l => !l.startsWith(' ')).map(l => l.split('  ')[0])
  expect(heads).toEqual(['요구사항', 'a', 'b', 'c'])
  expect(laneOf(lines, 'a')[0]).toContain('진행')
  expect(laneOf(lines, 'a')[0]).toContain('받아오기 대기 1')
  expect(laneOf(lines, 'b')[0]).toContain('합쳐짐')
  expect(laneOf(lines, 'c')[0]).toContain('폴더 없음')
  expect(laneOf(lines, '요구사항')).toEqual(['요구사항'])
})

test('어긋남: a(진행, 합치기 완료)·b(합쳐짐, fix 진행)에 붙고 d(진행, 합치기 없음)에는 없음', async ($, on) => {
  const j = dash([
    task({ id: 'T1', kind: 'merge', status: '완료', flow: 'a' }),
    task({ id: 'T2', kind: 'fix', status: '진행', flow: 'b' }),
    task({ id: 'T3', kind: 'implementation', status: '진행', flow: 'd' }),
  ], { flows: [flow('a', '진행'), flow('b', '합쳐짐'), flow('d', '진행')] })
  const { lines } = await openPanel($, on, j)
  const a = laneOf(lines, 'a').join('\n')
  const b = laneOf(lines, 'b').join('\n')
  expect(a).toContain('진행')
  expect(a).toContain('어긋남:')
  expect(b).toContain('합쳐짐')
  expect(b).toContain('어긋남:')
  expect(laneOf(lines, 'd').length).toBeGreaterThan(0)
  expect(laneOf(lines, 'd').join('\n')).not.toContain('어긋남')
})

const copy = (parent: string, deps: string[]) => dash([
  task({ id: 'A', status: '완료', flow: 'a', title: '앞 일' }),
  task({ id: 'B', flow: 'a', title: '뒤 일', parent, depends_on: deps }),
], { flows: [flow('a', '진행')] })

test('부모만 적은 사본 1과 의존만 적은 사본 2의 그린 내용이 글자까지 같음', async ($, on) => {
  const { w, ui, lines: one } = await openPanel($, on, copy('A', []))
  expect(linked(one, 'A', 'B')).toBe(true)
  await refeed($, w, copy('', ['A']))
  expect(linesOf(await ui.drawn())).toEqual(one)
})

test('둘 다 적은 사본 3의 그린 내용이 사본 1과 글자까지 같음', async ($, on) => {
  const { w, ui, lines: one } = await openPanel($, on, copy('A', []))
  await refeed($, w, copy('A', ['A']))
  expect(linesOf(await ui.drawn())).toEqual(one)
})

const AC8 = dash([
  task({ id: 'Z', status: '완료', flow: 'a' }),
  task({ id: 'A', status: '완료', flow: 'a', depends_on: ['Z'] }),
  task({ id: 'B', flow: 'a', depends_on: ['A'] }),
])

test('A(완료)·B의 task 줄이 있고 A에서 B까지 선이 이어지며 Z의 task 줄은 없음', async ($, on) => {
  const { lines } = await openPanel($, on, AC8)
  expect(rowOf(lines, 'A')).toContain('완료')
  expect(cell(lines, AC8, 'B').length).toBeGreaterThan(0)
  expect(cell(lines, AC8, 'Z')).toEqual([])
  expect(linked(lines, 'A', 'B')).toBe(true)
})

test('A의 task 줄이 B의 task 줄보다 위', async ($, on) => {
  const { lines } = await openPanel($, on, AC8)
  const map = mapSection(lines)
  expect(taskRow(map, 'A')).toBeGreaterThanOrEqual(0)
  expect(taskRow(map, 'A')).toBeLessThan(taskRow(map, 'B'))
})

test('남은 task가 없으면 지도 자리는 "남은 task 없음" 한 줄', async ($, on) => {
  const j = dash([
    task({ id: 'T1', status: '완료', flow: 'a' }),
    task({ id: 'T2', status: '보류', flow: 'a', depends_on: ['T1'] }),
    task({ id: 'T3', status: '백로그', block: '기타' }),
  ])
  const { lines } = await openPanel($, on, j)
  expect(mapSection(lines)).toEqual(['남은 task 없음'])
})

test('T1↔T2 고리: 고리 줄이 있고 두 칸이 그려짐', async ($, on) => {
  const j = dash([
    task({ id: 'T1', flow: 'a', depends_on: ['T2'] }),
    task({ id: 'T2', flow: 'a', depends_on: ['T1'] }),
  ])
  const { lines } = await openPanel($, on, j)
  const cycle = lines.filter(l => l === '의존 고리: T1 → T2 → T1' || l === '의존 고리: T2 → T1 → T2')
  expect(cycle).toHaveLength(1)
  expect(cell(lines, j, 'T1').length).toBeGreaterThan(0)
  expect(cell(lines, j, 'T2').length).toBeGreaterThan(0)
})

const AC12 = dash([
  task({ id: 'T1', status: '완료', flow: 'a' }), task({ id: 'T2', status: '완료', flow: 'a' }),
  task({ id: 'T3', status: '완료', flow: 'a' }), task({ id: 'T4', status: '보류', flow: 'a' }),
  task({ id: 'T5', flow: 'a' }), task({ id: 'T6', flow: 'a' }),
], { flows: [flow('a', '진행')] })

test('a 줄에 완료 3·보류 1, 백로그 없음, 흐름별 상태에 접힌 넷의 id 없음', async ($, on) => {
  const { lines } = await openPanel($, on, AC12)
  const a = laneOf(lines, 'a').join('\n')
  expect(a).toContain('완료 3')
  expect(a).toContain('보류 1')
  expect(a).not.toContain('백로그')
  const lanes = laneSection(lines).join('\n')
  for (const id of ['T1', 'T2', 'T3', 'T4']) expect([id, lanes.includes(id)]).toEqual([id, false])
})

test('생성 재료: --ready의 시작 가능 칸마다 "시작 가능", 못 띄움 칸마다 "못 띄움: {괄호 안}", 나머지 칸에는 둘 다 없음', async ($, on) => {
  const { lines } = await openPanel($, on, READY_FX)
  const lists = readyLists(READY)
  expect(lists.ready).toEqual(['T010'])
  expect(lists.held).toHaveLength(5)
  for (const id of lists.ready) expect([id, cell(lines, READY_FX, id).join('\n').includes('시작 가능')]).toEqual([id, true])
  for (const [id, why] of lists.held) {
    expect([id, cell(lines, READY_FX, id).some(l => l.includes(`못 띄움: ${why}`))]).toEqual([id, true])
    expect([id, cell(lines, READY_FX, id).join('\n').includes('시작 가능')]).toEqual([id, false])
  }
  const listed = new Set([...lists.ready, ...lists.held.map(h => h[0])])
  const others = idsOf(READY_FX).filter(id => !listed.has(id) && cell(lines, READY_FX, id).length > 0)
  expect(others.length).toBeGreaterThan(0)
  for (const id of others) {
    const text = cell(lines, READY_FX, id).join('\n')
    expect([id, text.includes('시작 가능'), text.includes('못 띄움')]).toEqual([id, false, false])
  }
})

test('E 칸에 "못 띄움: 사용자 할 일 대기"와 "할 일 대기: 비밀 파일 .dev.vars 준비", "시작 가능" 없음', async ($, on) => {
  const j = dash([
    task({ id: 'D', kind: 'deploy-plan', status: '완료' }),
    task({
      id: 'E', kind: 'deploy-exec', depends_on: ['D'], start: 'held', reason_text: '사용자 할 일 대기',
      elapsed: { kind: 'start_wait', text: '5분' }, waiting_user: '비밀 파일 .dev.vars 준비',
    }),
  ])
  const { lines } = await openPanel($, on, j)
  const e = cell(lines, j, 'E').join('\n')
  expect(e).toContain('못 띄움: 사용자 할 일 대기')
  expect(e).toContain('할 일 대기: 비밀 파일 .dev.vars 준비')
  expect(e).not.toContain('시작 가능')
})

test('한글 120자 할 일은 "할 일 대기: "로 시작해 "…"로 끝나는 한 줄, 화면 칸 80 이하', async ($, on) => {
  const long = '가나다라마바사아자차카타파하'.repeat(10).slice(0, 120)
  const j = dash([task({ id: 'U', status: '승인대기', elapsed: { kind: 'approval', text: '3분' }, waiting_user: long })])
  const { lines } = await openPanel($, on, j)
  // 덧줄은 선 글자(│·공백) 다음에 글이 온다.
  const todo = cell(lines, j, 'U').filter(l => /^[│ ]*할 일 대기: /.test(l))
  expect(todo).toHaveLength(1)
  expect(todo[0]!.endsWith('…')).toBe(true)
  expect(cells(todo[0]!)).toBeLessThanOrEqual(80)
})

test('경과: U "승인 대기 1시간 3분", U2 "승인 대기 ?", P "진행 ?", W·M에는 경과 앞말 없음', async ($, on) => {
  const j = dash([
    task({ id: 'U', status: '승인대기', approval_requested: '2026-10-06 08:57', elapsed: { kind: 'approval', text: '1시간 3분' } }),
    task({ id: 'U2', status: '승인대기', elapsed: { kind: 'approval', text: '?' } }),
    task({ id: 'P', status: '진행', elapsed: { kind: 'progress', text: '?' } }),
    task({ id: 'W', depends_on: ['U'] }),
    task({ id: 'M', status: '대기' }),
  ])
  const { lines } = await openPanel($, on, j)
  expect(cell(lines, j, 'U').join('\n')).toContain('승인 대기 1시간 3분')
  expect(cell(lines, j, 'U2').join('\n')).toContain('승인 대기 ?')
  expect(cell(lines, j, 'P').join('\n')).toContain('진행 ?')
  for (const id of ['W', 'M']) {
    const text = cell(lines, j, id).join('\n')
    expect(text.length).toBeGreaterThan(0)
    for (const word of ['승인 대기 ', '진행 ', '시작 가능 ']) expect([id, word, text.includes(word)]).toEqual([id, word, false])
  }
})

test('G 칸에 외부 작업, 정리 안 된 값에 D의 세 키, 그 부분에 M·awaiting_answer_apply 없음, D 칸에 외부 작업·할 일 대기 없음', async ($, on) => {
  const j = dash([
    task({ id: 'D', status: '완료', running_agent: 'code-T012', external_progress: '3/5', waiting_user: '키 발급' }),
    task({ id: 'G', status: '진행', depends_on: ['D'], elapsed: { kind: 'progress', text: '2분' }, external_progress: '승인됨, 실행 전' }),
    task({ id: 'M', status: '완료' }),
  ], { unclean: [{ id: 'D', keys: ['running_agent', 'external_progress', 'waiting_user'] }] })
  const { lines } = await openPanel($, on, j)
  expect(cell(lines, j, 'G').join('\n')).toContain('외부 작업: 승인됨, 실행 전')
  const unclean = uncleanSection(lines)
  expect(unclean).toContain('D: running_agent, external_progress, waiting_user')
  expect(unclean.join('\n')).not.toContain('M')
  expect(unclean.join('\n')).not.toContain('awaiting_answer_apply')
  const d = cell(lines, j, 'D').join('\n')
  expect(d.length).toBeGreaterThan(0)
  expect(d).not.toContain('외부 작업:')
  expect(d).not.toContain('할 일 대기:')
})

test('끝난 task에 남은 값이 없으면 "정리 안 된 값"이 없음', async ($, on) => {
  const j = dash([task({ id: 'D', status: '완료' }), task({ id: 'T', depends_on: ['D'] })])
  const { lines } = await openPanel($, on, j)
  expect(lines.some(l => l.includes('정리 안 된 값'))).toBe(false)
})

const AC20 = dash([
  task({ id: 'A1', flow: 'a' }), task({ id: 'A2', flow: 'a' }), task({ id: 'B1', flow: 'b' }), task({ id: 'B2', flow: 'b' }),
], { flows: [flow('a', '진행'), flow('b', '진행')] })

test('처음 열면 첫 줄 지도: 전체, 남은 넷의 칸', async ($, on) => {
  const { lines } = await openPanel($, on, AC20)
  expect(lines[0]).toContain('지도: 전체')
  for (const id of ['A1', 'A2', 'B1', 'B2']) expect([id, cell(lines, AC20, id).length > 0]).toEqual([id, true])
})

const P = '진행 대시보드 — '
const LONG40 = '가나다라마바사아자차카타파하'.repeat(4).slice(0, 40)
const AC24_TASKS = [
  task({ id: 'T1', title: LONG40, status: '진행', flow: 'panel', elapsed: { kind: 'progress', text: '1일 3시간' } }),
  task({
    id: 'T2', title: LONG40, flow: 'panel', depends_on: ['T1'], start: 'held',
    reason_text: '흐름 상한 2, 폴더 사용 중, 받아오기 먼저, 안 합친 흐름: panel, status, 사용자 할 일 대기',
    elapsed: { kind: 'start_wait', text: '2시간 5분' }, waiting_user: LONG40 + LONG40,
  }),
  task({ id: 'T3', title: LONG40, flow: 'status', depends_on: ['T1'], start: 'ready', elapsed: { kind: 'start_wait', text: '?' }, external_progress: LONG40 }),
  task({ id: 'T4', title: LONG40, status: '승인대기', flow: 'status', parent: 'T2', elapsed: { kind: 'approval', text: '35분' } }),
  task({ id: 'T5', title: LONG40, kind: 'deploy-exec', flow: 'panel', parent: 'T3', depends_on: ['T4'], start: 'held', reason_text: '사용자 할 일 대기' }),
  task({ id: 'T6', title: LONG40, status: '완료', flow: 'status' }),
]
const AC24 = dash(AC24_TASKS, { flows: [flow('panel', '진행', { sync_pending: ['a@1'] }), flow('status', '폴더 없음')] })

test('한글 40자 제목·못 띄움 이유·경과: W=60·80 모두 줄마다 화면 칸 ≤ W, 남은 id와 못 띄움 이유 조각이 그 칸에 있음', async ($, on) => {
  let mounted = (await openPanel($, on, AC24, 80)).ui
  for (const width of [80, 60]) {
    if (width === 60) {
      await mounted.unmount()
      mounted = await mountPane($, 60)
    }
    // 접힌 그림과 펼친 그림을 차례로 보고 다시 접는다.
    for (const pass of ['접힘', '펼침']) {
      const lines = linesOf(await mounted.drawn())
      for (const l of lines) expect([width, pass, l, cells(l) <= width]).toEqual([width, pass, l, true])
      for (const t of AC24_TASKS.filter(x => x.class === 'remaining')) expect([t.id, cell(lines, AC24, t.id).length > 0]).toEqual([t.id, true])
      for (const t of AC24_TASKS.filter(x => x.start === 'held')) {
        for (const piece of t.reason_text.split(', ')) {
          expect([width, t.id, piece, cell(lines, AC24, t.id).some(l => l.includes(piece))]).toEqual([width, t.id, piece, true])
        }
      }
      await mounted.press({ key: 'expand' })
    }
  }
})

test('큰 실행 사본(남은 task 0)을 W=80으로 그리면 24줄 이내', async ($, on) => {
  const { lines } = await openPanel($, on, RUN59)
  expect(RUN59.tasks.length).toBe(58)
  expect(RUN59.tasks.filter(t => t.class === 'remaining')).toHaveLength(0)
  expect(lines.length).toBeLessThanOrEqual(24)
})

test('큰 실행 사본과 완료 task 30개를 한 흐름에 더한 사본의 줄 수가 같음', async ($, on) => {
  const { w, ui, lines } = await openPanel($, on, RUN59)
  expect(RUN89.tasks.length).toBe(RUN59.tasks.length + 30)
  await refeed($, w, RUN89)
  const more = linesOf(await ui.drawn())
  expect(more.join('\n')).not.toEqual(lines.join('\n'))
  expect(more).toHaveLength(lines.length)
})

test('남은 40개(각자 의존 하나)를 패널 높이 10줄로 열어도 40개의 칸이 모두 있음', async ($, on) => {
  const ids = Array.from({ length: 40 }, (_, i) => `T${String(i + 1).padStart(2, '0')}`)
  const j = dash([task({ id: 'T00', status: '완료' }), ...ids.map((id, i) => task({ id, depends_on: [i === 0 ? 'T00' : ids[i - 1]!] }))])
  const { lines } = await openPanel($, on, j, 80, { bodyRows: 10 })
  for (const id of ids) expect([id, cell(lines, j, id).length > 0]).toEqual([id, true])
})

test('공통 앞부분을 뺀 보일 제목, 그린 내용 어디에도 "진행 대시보드" 없음(W=120)', async ($, on) => {
  // spec의 Given대로 한 줄(기타)에 두면 셋 중 둘이 " 패널"로 끝나 FR-4 (3)의 공통 뒷부분이 된다. 띠 AC-22와 같이 T1은 블록 요구사항,
  // T2·T3은 블록 설계에 둔다(답에 따라 고침).
  const j = dash([
    task({ id: 'T1', status: '완료', block: '요구사항', title: P + '요구사항 상세: 패널' }),
    task({ id: 'T2', parent: 'T1', block: '설계', title: P + '설계: 패널' }),
    task({ id: 'T3', depends_on: ['T1'], block: '설계', title: P + '설계: 입력창 위 띠' }),
  ])
  const { lines } = await openPanel($, on, j, 120)
  expect(rowOf(lines, 'T1')).toContain('요구사항 상세: 패널')
  expect(rowOf(lines, 'T2')).toContain('설계: 패널')
  expect(rowOf(lines, 'T3')).toContain('설계: 입력창 위 띠')
  expect(lines.join('\n')).not.toContain('진행 대시보드')
})

test('과반 규칙: 셋이 공유하는 앞부분을 빼고, 표시 붙은 제목과 다른 제목은 그대로(W=120)', async ($, on) => {
  const j = dash([
    task({ id: 'T1', title: P + '설계: 패널' }),
    task({ id: 'T2', title: P + '설계: 띠' }),
    task({ id: 'T3', title: P + '공통' }),
    task({ id: 'T4', title: '[백로그] 하네스 개선 — 의존 줄이기' }),
    task({ id: 'T5', title: '고객 문의 수정' }),
  ])
  const { lines } = await openPanel($, on, j, 120)
  expect(rowOf(lines, 'T1')).toContain('설계: 패널')
  expect(rowOf(lines, 'T1')).not.toContain('진행 대시보드')
  expect(rowOf(lines, 'T3')).toContain('공통')
  expect(rowOf(lines, 'T4')).toContain('[백로그] 하네스 개선 — 의존 줄이기')
  expect(rowOf(lines, 'T5')).toContain('고객 문의 수정')
})

test('다섯 벌: (가) 하나뿐 (나) 앞부분 없음 (다) 표시 다시 붙임 (라) 둘이 공유 (마) 빈 제목, b·a 고르기(W=120)', async ($, on) => {
  const ga = dash([task({ id: 'T1', title: P + '질문' })])
  const { w, ui, lines } = await openPanel($, on, ga, 120)
  expect(rowOf(lines, 'T1')).toContain('진행 대시보드 — 질문')
  const draw = async (j: DashJudgment) => {
    await refeed($, w, j)
    return linesOf(await ui.drawn())
  }
  const na = await draw(dash([task({ id: 'T1', title: '가 나' }), task({ id: 'T2', title: '다 라' })]))
  expect(rowOf(na, 'T1')).toContain('가 나')
  expect(rowOf(na, 'T2')).toContain('다 라')
  const daTasks = [
    task({ id: 'T1', title: P + '설계', flow: 'a' }),
    task({ id: 'T2', title: P + '공통', flow: 'b' }),
    task({ id: 'T3', title: '[백로그] ' + P + '수정', flow: 'a' }),
  ]
  const da = await draw(dash(daTasks))
  expect(rowOf(da, 'T3')).toContain('[백로그] 수정')
  expect(rowOf(da, 'T3')).not.toContain('진행 대시보드')
  const ra = await draw(dash([task({ id: 'T1', title: P + '요구사항 상세' }), task({ id: 'T2', title: P + '요약 줄' })]))
  expect(rowOf(ra, 'T1')).toContain('요구사항 상세')
  expect(rowOf(ra, 'T2')).toContain('요약 줄')
  const ma = dash([...daTasks, task({ id: 'T4', title: '', flow: 'b' })])
  const all = await draw(ma)
  // 빈 제목은 id만: 의존 없는 대기 T4의 task 줄은 상태 기호, id, 줄 끝 상태 낱말.
  expect(rowOf(all, 'T4')).toBe(`${STATUS_MARK['대기']} T4  대기`)
  await ui.press({ key: keyOf(await ui.drawn(), 'b') })
  const onB = linesOf(await ui.drawn())
  expect(onB[0]).toContain('지도: b')
  expect(rowOf(onB, 'T4')).toBe(`${STATUS_MARK['대기']} T4  대기`)
  expect(rowOf(onB, 'T2')).toContain('공통')
  await ui.press({ key: keyOf(await ui.drawn(), 'a') })
  const onA = linesOf(await ui.drawn())
  expect(onA[0]).toContain('지도: a')
  expect(rowOf(onA, 'T1')).toContain('설계')
  expect(rowOf(onA, 'T3')).toContain('[백로그] 수정')
  expect(rowOf(onA, 'T1')).toBe(rowOf(all, 'T1'))
  expect(rowOf(onA, 'T3')).toBe(rowOf(all, 'T3'))
})

test('긴 제목은 칸 첫 줄 끝을 …로 줄이고 다음 줄로 잇지 않음(W=80)', async ($, on) => {
  const tail = '끝부분확인용글자열개'
  const body = '가나다라마바사아자차카타파하'.repeat(4).slice(0, 50) + tail
  const j = dash([task({ id: 'T1', title: P + body }), task({ id: 'T2', title: P + '공통' })])
  const { lines } = await openPanel($, on, j)
  const t1 = rowOf(lines, 'T1')
  expect(t1).toContain('…')
  expect(cells(t1)).toBeLessThanOrEqual(80)
  expect(lines.join('\n')).not.toContain(tail)
})

test('실행이 없으면 C-1 문구 한 줄뿐', async ($, on) => {
  const { lines } = await openPanel($, on, dash([], { run: null, message: '이 세션이 진행하는 실행 없음' }))
  expect(lines).toEqual(['이 세션이 진행하는 실행 없음'])
})

test('판정 결과가 아직 없고 판정이 실패하면 "판정 결과 없음"과 "판정 실패:" 두 줄', async ($, on) => {
  const { lines } = await openPanel($, on, 'JSON이 아님')
  expect(lines[0]).toBe('판정 결과 없음')
  expect(lines[1]).toMatch(/^판정 실패: /)
  expect(lines).toHaveLength(2)
})

// 재현 재료: 선형 합동 난수로 만든 그래프(task 30~69개, 앞 task에 0.35 확률로 의존, 흐름 a·b).
function randomDash(seed: number): DashJudgment {
  let s = seed >>> 0
  const r = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32)
  const starts = ['ready', 'held', null] as const
  const n = 30 + Math.floor(r() * 40)
  const ts = []
  for (let i = 0; i < n; i++) {
    const id = `T${100 + i}`
    const deps = []
    for (let k = 0; k < i; k++) if (r() < 0.35) deps.push(`T${100 + k}`)
    const st = starts[Math.floor(r() * 3)]!
    ts.push(task({
      id, title: `제목 ${id}`, flow: r() < 0.5 ? 'a' : 'b', depends_on: deps,
      status: r() < 0.15 ? '완료' : '대기', start: st,
      reason_text: st === 'held' ? '흐름 상한 2, 받아오기 먼저, 안 합친 흐름: a, b, c' : '',
      waiting_user: r() < 0.3 ? '비밀 파일 준비 아주 긴 글자 '.repeat(3) : '',
      elapsed: r() < 0.5 ? { kind: 'start_wait', text: '1시간 0분' } : null,
    }))
  }
  return dash(ts, { flows: [flow('a', '진행'), flow('b', '진행')] })
}

// 띠·패널 같음의 비교 재료: task 줄의 차례마다 id, 선 글자와 상태 기호, 함께 의존·선 생략의 id 목록.
// 제목은 줄 끝 길이에 따라 줄이는 폭이 달라지고 패널은 경과 앞말이 있으면 상태 낱말을 빼므로 비교하지 않는다.
// 함께 의존·선 생략은 줄 끝에 있거나 넘침 덧줄로 내려가므로 칸(task 줄 + 덧줄)을 이어 읽는다. 패널 몫 조각과 덧줄에는 task id가 없다.
function treeShape(lines: string[], ids: string[]) {
  const order = ids.filter(id => taskRow(lines, id) >= 0).sort((a, b) => taskRow(lines, a) - taskRow(lines, b))
  return order.map(id => {
    const line = lines[taskRow(lines, id)]!
    const text = cellOf(lines, id, ids).join(' ')
    const idsAfter = (word: string, stop: string | null) => {
      const at = text.indexOf(word)
      if (at < 0) return []
      const rest = text.slice(at + word.length)
      const end = stop === null ? -1 : rest.indexOf(stop)
      return (end < 0 ? rest : rest.slice(0, end)).match(/T\d+/g) ?? []
    }
    return { id, lead: line.slice(0, symbolCol(line, id) + 1), together: idsAfter('함께 의존: ', '선 생략: '), cut: idsAfter('선 생략: ', null) }
  })
}

test('띠·패널 같음 선 생략이 있는 판정(task 39·W=50): 띠(extra 없음)와 패널(panelExtra)의 task 줄 차례·선 글자·함께 의존·선 생략이 같음', () => {
  const j = randomDash(4)
  const ids = idsOf(j)
  expect(ids).toHaveLength(39)
  const band = mapLines(j, ALL, 50)
  const pane = mapLines(j, ALL, 50, panelExtra)
  expect(band.some(l => l.includes('선 생략: '))).toBe(true)
  // 패널에는 띠에 없는 덧붙임이 실제로 있다(같음이 덧붙임 없는 두 그림의 비교가 아님).
  expect(pane.length).toBeGreaterThan(band.length)
  const b = treeShape(band, ids)
  expect(b.length).toBeGreaterThan(0)
  expect(treeShape(pane, ids)).toEqual(b)
})

test('띠·패널 같음 무작위 그래프 seed 1~20·W 50·60: task 줄 차례·선 글자·함께 의존·선 생략이 같음', () => {
  let cutCases = 0
  for (let seed = 1; seed <= 20; seed++) {
    const j = randomDash(seed)
    const ids = idsOf(j)
    for (const w of [50, 60]) {
      const band = mapLines(j, ALL, w)
      if (band.some(l => l.includes('선 생략: '))) cutCases++
      expect([seed, w, treeShape(mapLines(j, ALL, w, panelExtra), ids)]).toEqual([seed, w, treeShape(band, ids)])
    }
  }
  expect(cutCases).toBeGreaterThan(0)
})

// 주어진 상황: 흐름 없는 block 설계의 완료 T001·자체검증 T002.
const AC39 = dash([
  task({ id: 'T001', kind: 'question', block: '설계', status: '완료', title: '질문 — 시험 리뷰 상위 10 지적 개선' }),
  task({ id: 'T002', kind: 'design', block: '설계', status: '자체검증', depends_on: ['T001'], title: '설계 — 시험 리뷰 상위 10 지적 개선' }),
])

test('지도 부분이 정확히 "✓ T001 질문  완료"·"└─ ~ T002 설계  자체검증", 설계 줄에 공통 뒷부분, 지도에 시험 리뷰 없음', async ($, on) => {
  const { lines } = await openPanel($, on, AC39)
  const map = mapSection(lines)
  // spec 미리 보기 글자 그대로 적는다.
  expect(map).toEqual(['✓ T001 질문  완료', '└─ ~ T002 설계  자체검증'])
  expect(branchCol(map[1]!)).toBe(symbolCol(map[0]!, 'T001'))
  expect(laneOf(lines, '설계')[0]).toContain('설계 · 시험 리뷰 상위 10 지적 개선')
  expect(map.join('\n')).not.toContain('시험 리뷰')
})

// 주어진 상황: 의존 없는 대기 T1·진행 T2·자체검증 T3·승인대기 T4·대기 T5, 완료 T6·보류 T7·백로그 T8에 의존하는 대기 T9·T10·T11.
const AC40 = dash([
  task({ id: 'T1', title: '하나' }), task({ id: 'T2', status: '진행', title: '둘' }), task({ id: 'T3', status: '자체검증', title: '셋' }),
  task({ id: 'T4', status: '승인대기', title: '넷' }), task({ id: 'T5', status: '대기', title: '다섯' }),
  task({ id: 'T6', status: '완료', title: '여섯' }), task({ id: 'T7', status: '보류', title: '일곱' }), task({ id: 'T8', status: '백로그', title: '여덟' }),
  task({ id: 'T9', depends_on: ['T6'], title: '아홉' }), task({ id: 'T10', depends_on: ['T7'], title: '열' }),
  task({ id: 'T11', depends_on: ['T8'], title: '열하나' }),
])

test('W=120: id 열한 개마다 task 줄 하나, id 바로 앞 두 글자가 상태 기호와 공백, T6·T7·T8 줄에 완료·보류·백로그', async ($, on) => {
  const { lines } = await openPanel($, on, AC40, 120)
  const map = mapSection(lines)
  for (const t of AC40.tasks) {
    expect([t.id, map.filter(l => taskRow([l], t.id) === 0).length]).toEqual([t.id, 1])
    const line = map[taskRow(map, t.id)]!
    const at = symbolCol(line, t.id) + 2
    expect([t.id, line.slice(at - 2, at)]).toEqual([t.id, STATUS_MARK[t.status] + ' '])
  }
  expect(rowOf(lines, 'T6')).toContain('완료')
  expect(rowOf(lines, 'T7')).toContain('보류')
  expect(rowOf(lines, 'T8')).toContain('백로그')
})

test('AC-40의 실행, W=120: T6·T7·T8의 task 줄은 흐린 글씨, T1~T5·T9~T11의 task 줄은 흐린 글씨가 아님', async ($, on) => {
  const { ui } = await openPanel($, on, AC40, 120)
  const rows = rowsOf(await ui.drawn())
  const texts = rows.map(r => r.text)
  const map = mapSection(texts)
  const start = texts.indexOf('의존 지도') + 1
  for (const t of AC40.tasks) {
    const at = taskRow(map, t.id)
    expect([t.id, at >= 0]).toEqual([t.id, true])
    expect([t.id, rows[start + at]!.dim]).toEqual([t.id, ['T6', 'T7', 'T8'].includes(t.id)])
  }
})

test('W=80: B의 task 줄 하나, A1·A2 기호가 0열, B 줄이 A2 아래이고 ├·└가 A2의 기호 열, 함께 의존: A1, A2에서만 선', async ($, on) => {
  const { lines } = await openPanel($, on, dash([
    task({ id: 'A1', flow: 'a' }), task({ id: 'A2', flow: 'a' }), task({ id: 'B', flow: 'a', depends_on: ['A1', 'A2'] }),
  ], { flows: [flow('a', '진행')] }))
  const map = mapSection(lines)
  expect(map.filter(l => taskRow([l], 'B') === 0)).toHaveLength(1)
  expect(symbolCol(rowOf(lines, 'A1'), 'A1')).toBe(0)
  expect(symbolCol(rowOf(lines, 'A2'), 'A2')).toBe(0)
  expect(taskRow(map, 'B')).toBeGreaterThan(taskRow(map, 'A2'))
  expect(branchCol(rowOf(lines, 'B'))).toBe(0)
  expect(rowOf(lines, 'B')).toContain('함께 의존: A1')
  expect(linked(lines, 'A2', 'B')).toBe(true)
  expect(linked(lines, 'A1', 'B')).toBe(false)
})

test('W=60, 25 사슬: 지도 줄 cells ≤ 60, 25개 task 줄, 선 생략 줄마다 x가 depends_on에 있고 기호 0열(T12·T23, 끝 열넷 줄)', async ($, on) => {
  const ids = Array.from({ length: 25 }, (_, i) => `T${String(i + 1).padStart(2, '0')}`)
  const j = dash(ids.map((id, i) => task({ id, depends_on: i === 0 ? [] : [ids[i - 1]!] })))
  const { lines } = await openPanel($, on, j, 60)
  const map = mapSection(lines)
  for (const l of map) expect([l, cells(l) <= 60]).toEqual([l, true])
  for (const id of ids) expect([id, taskRow(map, id) >= 0]).toEqual([id, true])
  const cut = map.filter(l => l.includes('선 생략: '))
  expect(cut.length).toBeGreaterThanOrEqual(1)
  const owner = (l: string) => j.tasks.find(t => taskRow([l], t.id) === 0)!
  for (const l of cut) {
    const t = owner(l)
    expect([t.id, t.depends_on.includes(/선 생략: (\S+)/.exec(l)![1]!), symbolCol(l, t.id)]).toEqual([t.id, true, 0])
  }
  // 설계 R-5가 더 보는 것: 뗀 줄은 T12·T23, 지도 끝 열넷 줄이 T12 부분 트리(T12~T22) 다음 T23 부분 트리(T23~T25).
  expect(cut.map(l => owner(l).id)).toEqual(['T12', 'T23'])
  expect(map.slice(-14).map(l => ids.find(id => taskRow([l], id) === 0))).toEqual(ids.slice(11))
})

test('W=120 두 벌: (가) 줄마다 공통 뒷부분이 흐름 줄에 한 번, task 줄에서 빠짐 (나) 남는 글자가 없으면 그대로, 블록 줄에 · 시험', async ($, on) => {
  const ga = dash([
    task({ id: 'T1', flow: 'a', title: '가 — 묶음 하나' }), task({ id: 'T2', flow: 'a', title: '나 — 묶음 하나' }),
    task({ id: 'T3', flow: 'a', title: '다 — 다른 것' }),
    task({ id: 'T4', block: '요구사항', title: '라 — 묶음 둘' }), task({ id: 'T5', block: '요구사항', title: '마 — 묶음 둘' }),
  ], { flows: [flow('a', '진행')] })
  const { w, ui, lines } = await openPanel($, on, ga, 120)
  expect(rowOf(lines, 'T1')).toContain('가')
  expect(rowOf(lines, 'T1')).not.toContain('묶음 하나')
  expect(rowOf(lines, 'T3')).toContain('다 — 다른 것')
  expect(rowOf(lines, 'T4')).toContain('라')
  expect(rowOf(lines, 'T4')).not.toContain('묶음 둘')
  expect(laneOf(lines, 'a')[0]).toContain('a · 묶음 하나')
  expect(laneOf(lines, '요구사항')[0]).toContain('요구사항 · 묶음 둘')
  await refeed($, w, dash([
    task({ id: 'T1', block: '설계', title: '진행 대시보드 — 설계 — 시험' }),
    task({ id: 'T2', block: '설계', title: '진행 대시보드 — 공통 — 시험' }),
    task({ id: 'T3', block: '설계', title: '— 시험' }),
  ]))
  const na = linesOf(await ui.drawn())
  expect(rowOf(na, 'T1')).toContain('설계')
  for (const word of ['진행 대시보드', '설계 —', '시험']) expect([word, rowOf(na, 'T1').includes(word)]).toEqual([word, false])
  expect(rowOf(na, 'T3')).toContain('— 시험')
  expect(laneOf(na, '설계')[0]).toContain('· 시험')
})

test('3.6 예(설계 시험) W=80 패널: 줄 끝의 시작 판단·경과, 못 띄움 task의 할 일 덧줄이 7열부터', async ($, on) => {
  const j = dash([
    task({ id: 'T001', title: '설계: 띠', start: 'ready', elapsed: { kind: 'start_wait', text: '3분' } }),
    task({ id: 'T002', status: '승인대기', title: '설계: 패널', elapsed: { kind: 'approval', text: '1시간 2분' } }),
    task({ id: 'T003', status: '진행', title: '공통 C2', elapsed: { kind: 'progress', text: '35분' } }),
    task({
      id: 'T004', depends_on: ['T003'], title: '배포', start: 'held', reason_text: '사용자 할 일 대기',
      elapsed: { kind: 'start_wait', text: '10분' }, waiting_user: '비밀 파일 .dev.vars 준비',
    }),
  ])
  const { lines } = await openPanel($, on, j)
  // 설계 3.6의 예 그림 그대로.
  expect(mapSection(lines)).toEqual([
    '  T001 설계: 띠  대기 · 시작 가능 3분',
    '? T002 설계: 패널  승인 대기 1시간 2분',
    '> T003 공통 C2  진행 35분',
    '└─   T004 배포  대기 · 못 띄움: 사용자 할 일 대기 · 기다림 10분',
    '       할 일 대기: 비밀 파일 .dev.vars 준비',
  ])
})

test('덧줄의 │(설계 시험) W=80 패널: 할 일이 있는 진행 T001의 덧줄이 0열 │·글 4열, 그 아래 자식 T002·T003이 이어짐', async ($, on) => {
  const j = dash([
    task({ id: 'T001', status: '진행', title: '공통', waiting_user: '키 발급' }),
    task({ id: 'T002', depends_on: ['T001'], title: '패널' }),
    task({ id: 'T003', depends_on: ['T001'], title: '띠' }),
  ])
  const { lines } = await openPanel($, on, j)
  const map = mapSection(lines)
  const r = taskRow(map, 'T001')
  expect(map[r + 1]).toBe('│   할 일 대기: 키 발급')
  expect(map[r + 2]).toStartWith('├─   T002 ')
  expect(map[r + 3]).toStartWith('└─   T003 ')
  expect(linked(lines, 'T001', 'T002')).toBe(true)
  expect(linked(lines, 'T001', 'T003')).toBe(true)
})

test('넘침 덧줄(설계 시험) W=60: 줄 끝이 50칸을 넘는 못 띄움 task의 task 줄은 60칸 이하·제목 …, 뒤 조각은 덧줄에 있고 이유 전체가 칸에 있음', async ($, on) => {
  const reason = '안 합친 흐름: example-common, example-panel, example-status'
  const j = dash([task({ id: 'T1', title: '배포 계획 실행', start: 'held', reason_text: reason })])
  const { lines } = await openPanel($, on, j, 60)
  expect(cells(`대기 · 못 띄움: ${reason}`)).toBeGreaterThan(50)
  for (const l of mapSection(lines)) expect([l, cells(l) <= 60]).toEqual([l, true])
  const c = cell(lines, j, 'T1')
  expect(c[0]).toBe(`${STATUS_MARK['대기']} T1 …  대기`)
  expect(c.length).toBeGreaterThan(1)
  expect(c.slice(1).join('\n')).toContain('못 띄움: ')
  for (const piece of reason.split(', ')) expect([piece, c.slice(1).some(l => l.includes(piece))]).toEqual([piece, true])
})
