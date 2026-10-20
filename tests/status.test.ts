// 입력창 위 띠의 마운트 시험. 판정은 common의 길로 넣고(status-helpers feed), 띠를 터미널 표면에 그려
// 그린 트리를 안쪽 글의 줄 목록(bandLines)과 테두리를 포함한 화면 줄(bandScreen)로 본다.
import { expect, test } from 'claude-code/testing'
import type { DashJudgment } from '../types'

import { ALL, STATUS_MARK, laneLines, lanesOf, mapLines, panelOpenArgs } from '../hooks/panel-map'
import { cells } from '../hooks/panel-text'
import { innerWidth, summaryLine } from '../hooks/status-view'
import { DASH_A, DASH_B, READY_B } from './status-fx-waiting-user'
import {
  W, bandRowsOf, branchCol, dash, feed, flow, lines, mountBand, refeed, screen, symbolCol, task, taskRow,
} from './status-helpers'

const LANE_OPT = { misalign: false, folded: false, expanded: false }
// 테두리 안쪽 폭: 띠의 요약·버튼·흐름 줄·지도는 이 폭으로 그려진다.
const IW = innerWidth(W)

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

// AC-12의 실행: 흐름 common(T040·T041)·panel(T044)에 남은 task.
function twoFlows(): DashJudgment {
  return dash([
    task({ id: 'T001', kind: 'design', status: '완료', block: '설계' }),
    task({ id: 'T040', flow: 'common', parent: 'T001', start: 'ready' }),
    task({ id: 'T041', flow: 'common', depends_on: ['T040'] }),
    task({ id: 'T044', flow: 'panel', depends_on: ['T040'] }),
  ], { flows: [flow('common'), flow('panel')] })
}

// twoFlows에서 task 하나(index)의 상태만 바꾼 판정(머리 파일 하나를 고쳐 다시 그려지는 경우).
function changedOne(index: number, status: DashJudgment['tasks'][number]['status']): DashJudgment {
  const j = twoFlows()
  j.tasks[index]!.status = status
  return dash(j.tasks, { flows: j.flows })
}

const COMMON_IDS = ['T040', 'T041']
const PANEL_ONLY = 'T044'
const SHUT_BUTTONS = 'm: 지도 펼치기  a: *전체  b: common  c: panel  p: 패널 열기'

// 지도에서 그 id의 task 줄(panel 8.1 taskRow). 없으면 undefined.
const idLine = (ls: string[], id: string) => ls[taskRow(ls, id)]

test('W=200: 위 테두리에 실행 이름, 첫 줄이 설계 8.3의 요약 줄과 글자까지 같고 실행 이름·자체검증이 없음', async ($, on) => {
  await feed($, on, ac1())
  const ui = await mountBand($, 200)
  const ls = await lines(ui)
  expect((await screen(ui))[0]).toContain('2026-10-06-demo')
  expect(ls[0]).toBe(AC1_LINE)
  for (const part of ['2026-10-06-demo', '자체검증']) expect(ls[0]).not.toContain(part)
})

test('완료 task의 running_agent·waiting_user는 수에 들지 않음: 에이전트 1, 할 일 대기 0, 접힘 6', async ($, on) => {
  const j = ac1()
  const tasks = [
    ...j.tasks,
    task({ id: 'T005', kind: 'design', status: '완료', running_agent: 'design-T005' }),
    task({ id: 'T006', kind: 'design', status: '완료', waiting_user: '비밀 파일 준비' }),
  ]
  await feed($, on, dash(tasks, { run: j.run }))
  const first = (await lines(await mountBand($, 200)))[0]!
  expect(first).toContain('에이전트 1')
  expect(first).toContain('할 일 대기 0')
  expect(first).toContain('접힘 6')
})

test('생성 재료: B는 A보다 시작 가능 1 작고 할 일 대기 1 크며, B의 시작 가능은 board.py --ready의 n', async ($, on) => {
  const num = (line: string, word: string) => Number(new RegExp(`${word} (\\d+)`).exec(line)![1])
  const f = await feed($, on, DASH_A)
  const ui = await mountBand($, 200)
  const a = (await lines(ui))[0]!
  await refeed($, f, DASH_B)
  const b = (await lines(ui))[0]!
  const n = Number(/지금 시작할 수 있는 task (\d+)개/.exec(READY_B)![1])
  expect(num(b, '시작 가능')).toBe(num(a, '시작 가능') - 1)
  expect(num(b, '할 일 대기')).toBe(num(a, '할 일 대기') + 1)
  expect(num(b, '시작 가능')).toBe(n)
})

test('승인대기 셋(65분 전, 20분 전, 요청 시각 없음): (가장 오래 1시간 5분)', async ($, on) => {
  await feed($, on, dash([
    task({ id: 'T1', status: '승인대기', approval_requested: '2026-10-06 08:55', elapsed: { kind: 'approval', text: '1시간 5분' } }),
    task({ id: 'T2', status: '승인대기', approval_requested: '2026-10-06 09:40', elapsed: { kind: 'approval', text: '20분' } }),
    task({ id: 'T3', status: '승인대기', elapsed: { kind: 'approval', text: '?' } }),
  ]))
  expect((await lines(await mountBand($)))[0]).toContain('승인 대기 3(가장 오래 1시간 5분)')
})

test('승인대기 하나, 요청 시각 없음: (가장 오래 ?)', async ($, on) => {
  await feed($, on, dash([task({ id: 'T1', status: '승인대기', elapsed: { kind: 'approval', text: '?' } })]))
  expect((await lines(await mountBand($)))[0]).toContain('승인 대기 1(가장 오래 ?)')
})

test('승인대기 없음: 승인 대기 0이 있고 가장 오래가 없음', async ($, on) => {
  await feed($, on, dash([task({ id: 'T1', start: 'ready' })]))
  const first = (await lines(await mountBand($)))[0]!
  expect(first).toContain('승인 대기 0')
  expect(first).not.toContain('가장 오래')
})

test('승인대기 하나, 경과 1일 3시간: (가장 오래 1일 3시간)', async ($, on) => {
  await feed($, on, dash([
    task({ id: 'T1', status: '승인대기', approval_requested: '2026-10-05 06:40', elapsed: { kind: 'approval', text: '1일 3시간' } }),
  ]))
  expect((await lines(await mountBand($)))[0]).toContain('(가장 오래 1일 3시간)')
})

test('안쪽 폭이 상태별 수만 빠지는 폭: 상태별 수 없고 승인 대기·할 일 대기·에이전트·시작 가능 있고 실행 이름 없음, 첫 줄 화면 cells ≤ W, 둘째 줄은 버튼 줄', async ($, on) => {
  const w = cells(AC1_LINE) - cells(' · 대기 3, 진행 1, 승인대기 2, 접힘 4') + 4
  await feed($, on, ac1())
  const ui = await mountBand($, w)
  const ls = await lines(ui)
  for (const part of ['승인 대기 2', '할 일 대기 0', '에이전트 1', '시작 가능 2']) expect(ls[0]).toContain(part)
  expect(ls[0]).not.toContain('대기 3')
  expect(ls[0]).not.toContain('접힘')
  expect(ls[0]).not.toContain('2026-10-06-demo')
  expect(cells((await screen(ui))[1]!)).toBeLessThanOrEqual(w)
  expect(ls[1]).toStartWith('m: 지도 펼치기')
})

test('W=20: 첫 줄에 실행 이름·에이전트·시작 가능·상태별 수·가장 오래 없고 …로 끝나며 위 테두리 줄과 첫 줄의 화면 cells ≤ 20', async ($, on) => {
  await feed($, on, ac1())
  const ui = await mountBand($, 20)
  const first = (await lines(ui))[0]!
  for (const part of ['2026-10-06-demo', '에이전트', '시작 가능', '대기 3', '가장 오래']) expect(first).not.toContain(part)
  expect(first).toEndWith('…')
  const sc = await screen(ui)
  expect(cells(sc[0]!)).toBeLessThanOrEqual(20)
  expect(cells(sc[1]!)).toBeLessThanOrEqual(20)
})

test('펼친 띠: 요약, 버튼 줄, 흐름 줄, 지도 차례이고 못 띄움 이유·할 일·외부 작업·경과 글자가 없음', async ($, on) => {
  const j = dash([
    task({ id: 'T040', flow: 'common', status: '진행', external_progress: '배포 명령 2/3 실행함', elapsed: { kind: 'progress', text: '35분' } }),
    task({ id: 'T041', flow: 'common', start: 'held', reason_text: '흐름 상한', elapsed: { kind: 'start_wait', text: '12분' } }),
    task({ id: 'T044', flow: 'panel', waiting_user: '비밀 파일 준비', elapsed: { kind: 'start_wait', text: '2시간 7분' } }),
    task({ id: 'T045', flow: 'panel', start: 'ready', elapsed: { kind: 'start_wait', text: '9분' } }),
  ], { flows: [flow('common'), flow('panel')], held: [{ id: 'T041', reason_text: '흐름 상한' }] })
  await feed($, on, j)
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  const ls = await lines(ui)
  const laneRows = lanesOf(j).flatMap(l => laneLines(j, l, IW, LANE_OPT))
  expect(ls).toEqual([summaryLine(j, IW), 'm: 지도 접기  a: *전체  b: common  c: panel  p: 패널 열기', ...laneRows, ...mapLines(j, ALL, IW)])
  expect(ls[2]).toStartWith('common')
  expect(ls[3]).toStartWith('panel')
  // 지도 부분의 첫 줄이 첫 task T040의 task 줄이다.
  expect(taskRow(ls.slice(2 + laneRows.length), 'T040')).toBe(0)
  const all = ls.join('\n')
  for (const word of ['흐름 상한', '비밀 파일 준비', '배포 명령 2/3 실행함', '35분', '12분', '2시간 7분', '9분']) expect(all).not.toContain(word)
})

test('남은 task 30, maxRows 12, 펼침: 첫 줄 요약, 둘째 줄 버튼 줄, 마지막 task id까지 자르지 않음', async ($, on) => {
  const ids = Array.from({ length: 30 }, (_, i) => `T${101 + i}`)
  const j = dash(ids.map((id, i) => task({ id, flow: 'common', depends_on: i === 0 ? [] : [ids[i - 1]!], start: i === 0 ? 'ready' : null })),
    { flows: [flow('common')] })
  await feed($, on, j)
  const ui = await mountBand($, W, { maxRows: 12 })
  await ui.press({ key: 'map-toggle' })
  const ls = await lines(ui)
  expect(ls[0]).toBe(summaryLine(j, IW))
  expect(ls[1]).toStartWith('m: 지도 접기')
  expect(ls.length).toBeGreaterThan(12)
  expect(idLine(ls, 'T130')).toBeDefined()
  // 테두리 줄도 같은 목록에 있다: 맨 위가 위 테두리, 맨 아래가 아래 테두리, T130 줄은 그 안쪽(안쪽 줄 번호 + 1)이다.
  const sc = await screen(ui)
  expect(sc[0]).toStartWith('╭─ ')
  expect(sc[sc.length - 1]).toStartWith('╰')
  expect(sc[sc.length - 1]).toEndWith('╯')
  expect(sc).toHaveLength(ls.length + 2)
  expect(sc[taskRow(ls, 'T130') + 1]).toContain(idLine(ls, 'T130')!)
})

test('흐름 common·panel, 처음 그림: 버튼 줄이 m 지도 펼치기, a *전체, b common, c panel, p 패널 열기', async ($, on) => {
  await feed($, on, twoFlows())
  expect((await lines(await mountBand($)))[1]).toBe(SHUT_BUTTONS)
})

test('흐름 없음(task flow 빈 값, block 있음, flows 빈 목록): 버튼 줄이 m·a·p뿐', async ($, on) => {
  await feed($, on, dash([task({ id: 'T1', kind: 'design', block: '설계', start: 'ready' }), task({ id: 'T2', kind: 'design', block: '설계' })]))
  expect((await lines(await mountBand($)))[1]).toBe('m: 지도 펼치기  a: *전체  p: 패널 열기')
})

test('펼침에서 common을 누르면 지도에 panel에만 있는 id가 없고 common 남은 id가 있으며 b: *common', async ($, on) => {
  await feed($, on, twoFlows())
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  await ui.press({ key: 'unit-1' })
  const ls = await lines(ui)
  expect(ls[1]).toContain('b: *common')
  const map = ls.slice(2)
  expect(idLine(map, PANEL_ONLY)).toBeUndefined()
  for (const id of COMMON_IDS) expect(idLine(map, id)).toBeDefined()
})

test('이어 전체를 누르면 두 흐름의 남은 id 모두와 a: *전체', async ($, on) => {
  await feed($, on, twoFlows())
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  await ui.press({ key: 'unit-1' })
  await ui.press({ key: 'unit-all' })
  const ls = await lines(ui)
  expect(ls[1]).toContain('a: *전체')
  for (const id of [...COMMON_IDS, PANEL_ONLY]) expect(idLine(ls.slice(2), id)).toBeDefined()
})

test('common을 고른 뒤 task 하나의 상태만 바뀐 판정으로 다시 그려도 b: *common, 지도는 common만', async ($, on) => {
  const f = await feed($, on, twoFlows())
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  await ui.press({ key: 'unit-1' })
  const changed = changedOne(2, '진행')
  await refeed($, f, changed)
  const ls = await lines(ui)
  expect(ls[0]).toBe(summaryLine(changed, IW))
  expect(ls[1]).toContain('b: *common')
  expect(idLine(ls.slice(2), PANEL_ONLY)).toBeUndefined()
  for (const id of COMMON_IDS) expect(idLine(ls.slice(2), id)).toBeDefined()
})

test('common을 고른 뒤 flows에서 common만 빠지면 common 버튼이 없고 a: *전체, 지도에 두 흐름의 남은 id 모두', async ($, on) => {
  const f = await feed($, on, twoFlows())
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  await ui.press({ key: 'unit-1' })
  await refeed($, f, dash(twoFlows().tasks, { flows: [flow('panel')] }))
  const ls = await lines(ui)
  expect(ls[1]).toBe('m: 지도 접기  a: *전체  b: panel  p: 패널 열기')
  for (const id of [...COMMON_IDS, PANEL_ONLY]) expect(idLine(ls.slice(2), id)).toBeDefined()
  // 전체로 돌아간 것이 저장되어 common이 다시 생겨도 고른 것은 전체다.
  await refeed($, f, twoFlows())
  expect((await lines(ui))[1]).toBe('m: 지도 접기  a: *전체  b: common  c: panel  p: 패널 열기')
})

test('그려진 뒤 hasSurvey 참으로 다시 마운트하면 빈 목록, 거짓이면 첫 줄 요약', async ($, on) => {
  const j = twoFlows()
  await feed($, on, j)
  const before = await mountBand($)
  expect((await lines(before))[0]).toBe(summaryLine(j, IW))
  await before.unmount()
  const survey = await mountBand($, W, { hasSurvey: true })
  expect(await lines(survey)).toEqual([])
  // 테두리 글자도 없다.
  expect(await screen(survey)).toEqual([])
  expect(await survey.findAll({ type: 'Button' })).toHaveLength(0)
  await survey.unmount()
  expect((await lines(await mountBand($, W, { hasSurvey: false })))[0]).toBe(summaryLine(j, IW))
})

// 엔진이 던진 훅을 건너뛰어도 같은 빈 목록이 되므로 이 시험은 비킴과 던짐을 가르지 못한다. 가드는 status-view.test의 bandReady 시험이 가른다.
test('3.2 run은 있고 flows가 없는 불완전한 판정: 띠가 빈 목록', async ($, on) => {
  const { flows: _flows, ...partial } = twoFlows()
  await feed($, on, partial)
  expect(await lines(await mountBand($))).toEqual([])
})

test('실행 없음 + devflow-harness 불림, W=80: 안쪽 줄은 그 문장 하나, 이름 없는 위 테두리·아래 테두리와 세 줄 모두 80칸, 버튼 없음', async ($, on) => {
  const f = await feed($, on, dash([], { run: null, message: '이 세션이 진행하는 실행 없음' }))
  await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: 'x' })
  await f.clock.advance(600)
  const ui = await mountBand($, 80)
  expect(await lines(ui)).toEqual(['이 세션이 진행하는 실행 없음'])
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
  const sc = await screen(ui)
  expect(sc).toHaveLength(3)
  expect(sc[0]).toBe('╭' + '─'.repeat(78) + '╮')
  expect(sc[1]).toStartWith('│ 이 세션이 진행하는 실행 없음')
  expect(sc[1]).toEndWith(' │')
  expect(sc[2]).toBe('╰' + '─'.repeat(78) + '╯')
  for (const l of sc) expect(cells(l)).toBe(80)
})

test('panel AC-29의 세 task, 펼침: 칸에 공통 앞부분을 뺀 제목, 둘째 줄부터 진행 대시보드 없음', async ($, on) => {
  await feed($, on, dash([
    task({ id: 'T1', kind: 'req-detail', status: '완료', block: '요구사항', title: '진행 대시보드 — 요구사항 상세: 패널' }),
    task({ id: 'T2', kind: 'design', block: '설계', parent: 'T1', start: 'ready', title: '진행 대시보드 — 설계: 패널' }),
    task({ id: 'T3', kind: 'design', block: '설계', depends_on: ['T1'], start: 'ready', title: '진행 대시보드 — 설계: 입력창 위 띠' }),
  ]))
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  const ls = await lines(ui)
  expect(idLine(ls, 'T1')).toContain('요구사항 상세: 패널')
  expect(idLine(ls, 'T2')).toContain('설계: 패널')
  expect(idLine(ls, 'T3')).toContain('설계: 입력창 위 띠')
  for (const l of ls.slice(1)) expect(l).not.toContain('진행 대시보드')
})

test('panel AC-32 실행 + 한글 40자 제목 대기 둘, W=60·80 펼침: 셋째 줄부터 아래 테두리까지 테두리 포함 cells ≤ W, T1 줄에 …, 끝 글자 없음, 남은 넷의 id', async ($, on) => {
  await feed($, on, dash([
    task({ id: 'T1', kind: 'design', block: '설계', start: 'ready', title: `진행 대시보드 — ${'가'.repeat(50)}끝부분확인용글자열개` }),
    task({ id: 'T2', kind: 'design', block: '설계', start: 'ready', title: '진행 대시보드 — 공통' }),
    task({ id: 'T3', kind: 'design', block: '설계', start: 'ready', title: `진행 대시보드 — ${'나'.repeat(40)}` }),
    task({ id: 'T4', kind: 'design', block: '설계', start: 'ready', title: `진행 대시보드 — ${'다'.repeat(40)}` }),
  ]))
  for (const w of [60, 80]) {
    const ui = await mountBand($, w)
    await ui.press({ key: 'map-toggle' })
    const ls = await lines(ui)
    const sc = await screen(ui)
    expect(ls.length).toBeGreaterThan(2)
    // 화면 줄 [0]은 위 테두리라 안쪽 셋째 줄은 [3]이다.
    expect(sc.length).toBe(ls.length + 2)
    for (const l of sc.slice(3)) expect(cells(l)).toBeLessThanOrEqual(w)
    expect(idLine(ls, 'T1')).toContain('…')
    expect(sc.join('\n')).not.toContain('끝부분확인용글자열개')
    for (const id of ['T1', 'T2', 'T3', 'T4']) expect(idLine(ls.slice(2), id)).toBeDefined()
    // 펼침은 모듈 변수라 다음 폭의 마운트 전에 접어 둔다.
    await ui.press({ key: 'map-toggle' })
    await ui.unmount()
  }
})

test('panel AC-39의 실행, W=80 펼침: 흐름 줄 다음 줄이 정확히 둘("✓ T001 질문  완료", "└─ ~ T002 설계  자체검증"), 그 밖에 시험 리뷰 없음', async ($, on) => {
  await feed($, on, dash([
    task({ id: 'T001', kind: 'question', block: '설계', status: '완료', title: '질문 — 시험 리뷰 상위 10 지적 개선' }),
    task({ id: 'T002', kind: 'design', block: '설계', status: '자체검증', depends_on: ['T001'], title: '설계 — 시험 리뷰 상위 10 지적 개선' }),
  ]))
  const ui = await mountBand($, 80)
  await ui.press({ key: 'map-toggle' })
  const ls = await lines(ui)
  // 요약, 버튼 줄, 흐름별 상태 줄(설계 블록 한 줄), 그다음 지도 두 줄.
  expect(ls[2]).toBe('설계 · 시험 리뷰 상위 10 지적 개선')
  const map = ls.slice(3)
  expect(map).toHaveLength(2)
  // spec 미리 보기 글자 그대로 적는다.
  expect(map[0]).toContain('✓ T001 질문  완료')
  expect(map[1]).toEndWith('└─ ~ T002 설계  자체검증')
  expect(branchCol(map[1]!)).toBe(symbolCol(map[0]!, 'T001'))
  expect(symbolCol(map[0]!, 'T001')).toBe(0)
  for (const l of map) expect(l).not.toContain('시험 리뷰')
})

test('panel AC-40의 실행, W=120 펼침: id 열한 개마다 task 줄 하나, id 앞 두 글자가 상태 기호와 공백, T2·T4 줄 끝은 상태 낱말, T6·T7·T8 task 줄만 흐린 글씨', async ($, on) => {
  const j = dash([
    task({ id: 'T1', title: '하나' }), task({ id: 'T2', status: '진행', title: '둘' }), task({ id: 'T3', status: '자체검증', title: '셋' }),
    task({ id: 'T4', status: '승인대기', title: '넷' }), task({ id: 'T5', status: '대기', title: '다섯' }),
    task({ id: 'T6', status: '완료', title: '여섯' }), task({ id: 'T7', status: '보류', title: '일곱' }), task({ id: 'T8', status: '백로그', title: '여덟' }),
    task({ id: 'T9', depends_on: ['T6'], title: '아홉' }), task({ id: 'T10', depends_on: ['T7'], title: '열' }),
    task({ id: 'T11', depends_on: ['T8'], title: '열하나' }),
  ])
  await feed($, on, j)
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  const ls = await lines(ui)
  for (const t of j.tasks) {
    expect([t.id, ls.filter(l => taskRow([l], t.id) === 0).length]).toEqual([t.id, 1])
    const line = idLine(ls, t.id)!
    const at = symbolCol(line, t.id) + 2
    expect([t.id, line.slice(at - 2, at)]).toEqual([t.id, STATUS_MARK[t.status] + ' '])
  }
  // 띠의 줄 끝은 상태 낱말뿐이다.
  expect(idLine(ls, 'T2')).toEndWith('진행')
  expect(idLine(ls, 'T4')).toEndWith('승인대기')
  // 끝난 task(완료·보류·백로그)의 task 줄만 흐린 글씨다.
  const rows = bandRowsOf(await ui.drawn())
  expect(rows.map(r => r.text)).toEqual(ls)
  for (const t of j.tasks) expect([t.id, rows[taskRow(ls, t.id)]!.dim]).toEqual([t.id, ['T6', 'T7', 'T8'].includes(t.id)])
})

test('실행 없음 + 불리지 않음: 도구 실행·턴 끝 뒤 600 ms에도 띠에 그린 글자가 없음', async ($, on) => {
  const f = await feed($, on, dash([], { run: null, message: '이 세션이 진행하는 실행 없음' }))
  await $.tool.call({ tool: 'Bash', command: 'echo hi' } as never)
  await $.turn.complete({ reason: 'answer', answer: 'a', durationMs: 1, isAborted: false, turnId: 't1' })
  await f.clock.advance(600)
  const ui = await mountBand($)
  expect(await lines(ui)).toEqual([])
  // 테두리 글자도 없다.
  expect(await screen(ui)).toEqual([])
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
})

test('common을 고르고 패널 열기를 두 번: ui.open 인자는 두 번 모두 panelOpenArgs 그대로(focus 없음), 열린 패널 하나, b: *common', async ($, on) => {
  const j = twoFlows()
  const f = await feed($, on, j)
  const ui = await mountBand($)
  await ui.press({ key: 'unit-1' })
  const want = panelOpenArgs({ result: j, error: '', at: 0, invokedAt: null }, W)
  expect(want).toMatchObject({ id: 'harness-panel', title: '하네스 진행' })
  for (let n = 1; n <= 2; n++) {
    await ui.press({ key: 'open-panel' })
    expect(f.opened).toHaveLength(n)
    expect(f.opened[n - 1]).toEqual(want)
    expect(f.opened[n - 1]).not.toHaveProperty('focus')
    // 시험의 $에는 ui.panes가 없어 시험의 ui.panes 훅이 답할 열린 id 목록으로 본다.
    expect(new Set(f.panes).size).toBe(1)
    expect((await lines(ui))[1]).toContain('b: *common')
  }
})

test('실행이 있고 devflow-harness가 불리고 판정이 바뀌어 다시 그려도 패널을 열지 않음', async ($, on) => {
  const f = await feed($, on, twoFlows())
  await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: 'x' })
  await f.clock.advance(600)
  const ui = await mountBand($)
  const changed = changedOne(1, '진행')
  await refeed($, f, changed)
  expect((await lines(ui))[0]).toBe(summaryLine(changed, IW))
  expect(f.opened).toHaveLength(0)
  expect(f.panes).toEqual([])
})

test('처음 그림: 줄이 둘(요약, 지도 펼치기 버튼이 있는 버튼 줄)이고 흐름 줄·남은 id가 없음', async ($, on) => {
  const j = twoFlows()
  await feed($, on, j)
  const ls = await lines(await mountBand($))
  expect(ls).toEqual([summaryLine(j, IW), SHUT_BUTTONS])
  for (const id of [...COMMON_IDS, PANEL_ONLY]) expect(ls.join('\n')).not.toContain(id)
  expect(ls.some(l => l.startsWith('common') || l.startsWith('panel'))).toBe(false)
})

test('지도 펼치기를 누르면 셋째 줄부터 common·panel 흐름 줄과 남은 id 모두, 첫 줄·둘째 줄은 그대로(m 글만 지도 접기)', async ($, on) => {
  await feed($, on, twoFlows())
  const ui = await mountBand($)
  const shut = await lines(ui)
  await ui.press({ key: 'map-toggle' })
  const ls = await lines(ui)
  expect(ls[0]).toBe(shut[0])
  expect(ls[1]).toBe(shut[1]!.replace('m: 지도 펼치기', 'm: 지도 접기'))
  for (const name of ['common', 'panel']) expect(ls.slice(2).some(l => l.startsWith(name))).toBe(true)
  for (const id of [...COMMON_IDS, PANEL_ONLY]) expect(idLine(ls.slice(2), id)).toBeDefined()
})

test('한 번 더 누르면 두 줄로 돌아가고 흐름 줄·남은 id가 없음', async ($, on) => {
  const j = twoFlows()
  await feed($, on, j)
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  await ui.press({ key: 'map-toggle' })
  const ls = await lines(ui)
  expect(ls).toEqual([summaryLine(j, IW), SHUT_BUTTONS])
  for (const id of [...COMMON_IDS, PANEL_ONLY]) expect(ls.join('\n')).not.toContain(id)
})

test('펼친 뒤 판정이 바뀌어 다시 그려도 흐름 줄과 남은 id가 그대로 있음', async ($, on) => {
  const f = await feed($, on, twoFlows())
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  const changed = changedOne(1, '진행')
  await refeed($, f, changed)
  const ls = await lines(ui)
  expect(ls[0]).toBe(summaryLine(changed, IW))
  expect(ls[1]).toStartWith('m: 지도 접기')
  for (const name of ['common', 'panel']) expect(ls.slice(2).some(l => l.startsWith(name))).toBe(true)
  for (const id of [...COMMON_IDS, PANEL_ONLY]) expect(idLine(ls.slice(2), id)).toBeDefined()
})

test('접은 채 common과 패널 열기를 누르면 매번 두 줄에 b: *common, 이어 펼치면 지도는 common만', async ($, on) => {
  await feed($, on, twoFlows())
  const ui = await mountBand($)
  for (const key of ['unit-1', 'open-panel']) {
    await ui.press({ key })
    const ls = await lines(ui)
    expect(ls).toHaveLength(2)
    expect(ls[1]).toBe('m: 지도 펼치기  a: 전체  b: *common  c: panel  p: 패널 열기')
  }
  await ui.press({ key: 'map-toggle' })
  const map = (await lines(ui)).slice(2)
  expect(idLine(map, PANEL_ONLY)).toBeUndefined()
  for (const id of COMMON_IDS) expect(idLine(map, id)).toBeDefined()
})

test('B-2 /clear 뒤에는 펼침·고른 흐름이 처음 값(접음·전체)으로 돌아감', async ($, on) => {
  const j = twoFlows()
  await feed($, on, j)
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  await ui.press({ key: 'unit-1' })
  expect((await lines(ui)).length).toBeGreaterThan(2)
  await $.session.end({ reason: 'clear', sessionId: 'S1', resume: {} } as never)
  expect(await lines(ui)).toEqual([summaryLine(j, IW), SHUT_BUTTONS])
})

// AC-34의 X: 실행 2026-01-01-sample-run-fixes, 승인대기 하나(common), 흐름 common·panel에 각각 남은 task.
const FRAMED_NAME = '2026-01-01-sample-run-fixes'
function framedRun(): DashJudgment {
  return dash([
    task({ id: 'T030', flow: 'common', status: '승인대기', approval_requested: '2026-10-06 09:48', elapsed: { kind: 'approval', text: '12분' } }),
    task({ id: 'T040', flow: 'common', start: 'ready' }),
    task({ id: 'T044', flow: 'panel', depends_on: ['T040'] }),
  ], {
    flows: [flow('common'), flow('panel')],
    run: { name: FRAMED_NAME, dir: `D:/w/_workspace/${FRAMED_NAME}`, status: '진행', run_md_unreadable: false, flow_cap: 2 },
  })
}
const FRAMED_IDS = ['T030', 'T040', 'T044']
const TOP_RE = /^╭─ 2026-01-01-sample-run-fixes ─+╮$/
const BOTTOM_RE = /^╰─+╯$/

test('W=120 처음 그림(접음): 테두리 포함 네 줄, 위 테두리에 실행 이름, 요약 줄에 실행 이름 없음, 네 줄 모두 120칸', async ($, on) => {
  await feed($, on, framedRun())
  const sc = await screen(await mountBand($))
  expect(sc).toHaveLength(4)
  expect(sc[0]).toMatch(TOP_RE)
  expect(sc[1]).toStartWith('│ 승인 대기')
  expect(sc[1]).toEndWith(' │')
  expect(sc[1]).not.toContain(FRAMED_NAME)
  expect(sc[2]).toStartWith('│ ')
  expect(sc[2]).toEndWith(' │')
  expect(sc[3]).toMatch(BOTTOM_RE)
  for (const l of sc) expect(cells(l)).toBe(120)
})

test('AC-34 뒤 지도 펼치기: 맨 첫·끝 줄은 AC-34의 테두리, 사이 줄은 모두 │ 로 시작해 │로 끝나고 흐름 줄과 남은 id 모두, 모든 줄 120칸', async ($, on) => {
  await feed($, on, framedRun())
  const ui = await mountBand($)
  await ui.press({ key: 'map-toggle' })
  const sc = await screen(ui)
  const ls = await lines(ui)
  expect(sc[0]).toMatch(TOP_RE)
  expect(sc[sc.length - 1]).toMatch(BOTTOM_RE)
  for (const l of sc.slice(1, -1)) {
    expect(l).toStartWith('│ ')
    expect(l).toEndWith(' │')
  }
  for (const name of ['common', 'panel']) expect(ls.some(l => l.startsWith(name))).toBe(true)
  for (const id of FRAMED_IDS) expect([id, taskRow(ls, id) >= 0]).toEqual([id, true])
  for (const l of sc) expect(cells(l)).toBe(120)
})

test('띠 폭 26·20·6: 위 테두리 줄이 날짜를 뗀 이름·끝 …·선만이고, 각 폭에서 모든 줄의 cells가 그 폭', async ($, on) => {
  await feed($, on, framedRun())
  const tops: [number, string][] = [[26, '╭─ sample-run-fixes ─────╮'], [20, '╭─ sample-run-fi… ─╮'], [6, '╭────╮']]
  for (const [w, top] of tops) {
    const ui = await mountBand($, w)
    const sc = await screen(ui)
    expect([w, sc[0]]).toEqual([w, top])
    for (const l of sc) expect([w, l, cells(l)]).toEqual([w, l, w])
    await ui.unmount()
  }
})
