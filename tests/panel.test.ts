// 패널 명령·여닫기·버튼 누름의 마운트 시험.
// 판정은 common의 길(process.run의 답)로 넣는다. 띠 길의 여는 호출과 닫기는 함께 띄운 BAND 플러그인이 한다(panel-helpers).
import { expect, test } from 'claude-code/testing'

import { panelOpenArgs } from '../hooks/panel-map'
import { panelRows } from '../hooks/panel-view'
import { DASH as RUN59 } from './panel-fx-run59'
import {
  BAND, bandOpen, cellOf, closePanel, dash, feedJudgment, flow, keyOf, laneOf, laneSection, linesOf, mapSection, mountPane,
  openPanel, peek, refeed, runCommand, sessionEnd, stateOf, task, toolCall, turnComplete, world,
} from './panel-helpers'

const R1 = dash([task({ id: 'T1', flow: 'a', title: '첫 일' })], { flows: [flow('a', '진행')] })

// AC-20·AC-21: a에 남은 둘, b에 남은 둘, A1이 b의 완료 task B0에 의존.
const AB_TASKS = [
  task({ id: 'B0', status: '완료', flow: 'b' }),
  task({ id: 'A1', flow: 'a', depends_on: ['B0'] }), task({ id: 'A2', flow: 'a' }),
  task({ id: 'B1', flow: 'b' }), task({ id: 'B2', flow: 'b' }),
]
const AB = dash(AB_TASKS, { flows: [flow('a', '진행'), flow('b', '진행')] })
const AB_IDS = AB_TASKS.map(t => t.id)
const has = (lines: string[], id: string) => cellOf(lines, id, AB_IDS).length > 0

test('등록: isInteractive false면 명령 등록 0, true면 harness-panel 1, 이어 /clear(session.end clear) 뒤 2', async ($, on) => {
  const w = world(on)
  await feedJudgment($, w, R1, false)
  expect(w.registered).toEqual([])
  await feedJudgment($, w, R1, true)
  expect(w.registered).toEqual(['harness-panel'])
  await sessionEnd($, 'clear')
  expect(w.registered).toEqual(['harness-panel', 'harness-panel'])
  await sessionEnd($, 'logout')
  expect(w.registered).toHaveLength(2)
})

test('여는 높이: panelOpenArgs(state, 84).rows가 panelRows(state, 전체·접힘, 80)의 줄 수와 같음(큰 실행 사본, 남은 task 0)', async ($, on) => {
  const state = stateOf(RUN59)
  const rows = panelRows(state, { unit: '전체', expanded: false }, 80)
  expect(panelOpenArgs(state, 84).rows).toBe(rows.length)
  const { w, lines } = await openPanel($, on, RUN59, 80)
  expect(w.opened[0]!.rows).toBe(rows.length)
  expect(lines).toHaveLength(rows.length)
})

test('명령 뒤 연 id가 harness-panel 하나, 패널 목록에 하나, 첫 줄에 R1과 지도: 전체', async ($, on) => {
  const { w, lines } = await openPanel($, on, R1)
  expect(w.opened.map(o => o.id)).toEqual(['harness-panel'])
  expect(w.opened[0]).toEqual(panelOpenArgs(stateOf(R1), 84))
  expect(w.panes).toEqual(['harness-panel'])
  expect(lines[0]).toContain('R1')
  expect(lines[0]).toContain('지도: 전체')
})

test('명령을 다시 입력해도 연 id 집합은 하나, 두 번째 여는 인자의 id도 harness-panel', async ($, on) => {
  const { w } = await openPanel($, on, R1)
  await runCommand($)
  expect(w.opened).toHaveLength(2)
  expect(w.opened[1]!.id).toBe('harness-panel')
  expect(new Set(w.opened.map(o => o.id)).size).toBe(1)
  expect(w.panes).toEqual(['harness-panel'])
})

test('명령·띠 버튼 없이 세션 시작, devflow-harness 두 번, 판정 바뀜, 도구 실행, 턴 끝, 61초 → 각 뒤 연 패널 0', async ($, on) => {
  const w = world(on)
  const none = () => {
    expect(w.opened).toEqual([])
    expect(w.panes).toEqual([])
  }
  await feedJudgment($, w, R1)
  none()
  await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: '/devflow-harness:devflow-harness' })
  await w.clock.advance(600)
  none()
  await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: 'Skill 도구' })
  await w.clock.advance(600)
  none()
  const runs = w.runs
  await refeed($, w, dash([task({ id: 'T1', flow: 'a', title: '첫 일', status: '진행' })], { flows: [flow('a', '진행')] }))
  expect(w.runs).toBe(runs + 1)
  none()
  await toolCall($)
  await w.clock.advance(600)
  none()
  await turnComplete($)
  await w.clock.advance(600)
  none()
  await w.clock.advance(61000)
  none()
})

test('펼치기: a 줄 아래 접힌 넷이 "{id} {status}"로 한 줄씩, 지도 그대로 / 다시 누르면 처음과 같음', async ($, on) => {
  const j = dash([
    task({ id: 'T1', status: '완료', flow: 'a' }), task({ id: 'T2', status: '완료', flow: 'a' }),
    task({ id: 'T3', status: '완료', flow: 'a' }), task({ id: 'T4', status: '보류', flow: 'a' }),
    task({ id: 'T5', flow: 'a' }), task({ id: 'T6', flow: 'a' }),
  ], { flows: [flow('a', '진행')] })
  const { ui, lines: before } = await openPanel($, on, j)
  await ui.press({ key: 'expand' })
  const open = linesOf(await ui.drawn())
  expect(laneOf(open, 'a').slice(1).map(l => l.trim())).toEqual(['T1 완료', 'T2 완료', 'T3 완료', 'T4 보류'])
  expect(mapSection(open)).toEqual(mapSection(before))
  await ui.press({ key: 'expand' })
  expect(linesOf(await ui.drawn())).toEqual(before)
})

test('a 버튼을 누르면 첫 줄 지도: a, a의 남은 둘만, A1 칸에 다른 흐름에 의존: B0(b), 흐름 줄 a·b 그대로', async ($, on) => {
  const { ui } = await openPanel($, on, AB)
  await ui.press({ key: keyOf(await ui.drawn(), 'a') })
  const lines = linesOf(await ui.drawn())
  expect(lines[0]).toContain('지도: a')
  expect(has(lines, 'A1')).toBe(true)
  expect(has(lines, 'A2')).toBe(true)
  for (const id of ['B0', 'B1', 'B2']) expect([id, has(lines, id)]).toEqual([id, false])
  expect(cellOf(lines, 'A1', AB_IDS).join('\n')).toContain('다른 흐름에 의존: B0(b)')
  expect(laneOf(lines, 'a').length).toBeGreaterThan(0)
  expect(laneOf(lines, 'b').length).toBeGreaterThan(0)
})

test('고른 단위: (1) 판정이 바뀌어도 지도: a (2) 전체를 누르면 지도: 전체와 넷 (3) a를 고르고 닫았다 열면 지도: 전체', { plugins: [BAND] }, async ($, on) => {
  const { w, ui } = await openPanel($, on, AB)
  const a = keyOf(await ui.drawn(), 'a')
  await ui.press({ key: a })
  await refeed($, w, dash(AB_TASKS.map(t => (t.id === 'A2' ? { ...t, status: '진행' as const } : t)), { flows: AB.flows }))
  const changed = linesOf(await ui.drawn())
  expect(changed[0]).toContain('지도: a')
  // 상태는 A2의 task 줄 끝에 있다(한 줄 트리).
  expect(cellOf(changed, 'A2', AB_IDS)[0]).toContain('진행')
  await ui.press({ key: 'unit-all' })
  const all = linesOf(await ui.drawn())
  expect(all[0]).toContain('지도: 전체')
  for (const id of ['A1', 'A2', 'B1', 'B2']) expect([id, has(all, id)]).toEqual([id, true])
  await ui.press({ key: a })
  expect(linesOf(await ui.drawn())[0]).toContain('지도: a')
  await ui.unmount()
  await closePanel($)
  expect(w.panes).toEqual([])
  await runCommand($)
  const again = await mountPane($)
  expect(linesOf(await again.drawn())[0]).toContain('지도: 전체')
})

test('(부분) 키보드를 가진 마운트에서 a·펼치기·전체를 누르면 각각 AC-21·AC-13·AC-20의 꼴', async ($, on) => {
  const { ui, lines: first } = await openPanel($, on, AB)
  await ui.press({ key: keyOf(await ui.drawn(), 'a') })
  const onA = linesOf(await ui.drawn())
  expect(onA[0]).toContain('지도: a')
  expect(['A1', 'A2', 'B0', 'B1', 'B2'].map(id => has(onA, id))).toEqual([true, true, false, false, false])
  await ui.press({ key: 'expand' })
  const open = linesOf(await ui.drawn())
  expect(laneOf(open, 'b').slice(1).map(l => l.trim())).toEqual(['B0 완료'])
  expect(mapSection(open)).toEqual(mapSection(onA))
  await ui.press({ key: 'unit-all' })
  const all = linesOf(await ui.drawn())
  expect(all[0]).toContain('지도: 전체')
  expect(['A1', 'A2', 'B1', 'B2'].every(id => has(all, id))).toBe(true)
  expect(mapSection(all)).toEqual(mapSection(first))
})

test('(부분) 열고 모든 단위·펼침을 누르고 닫는 동안 패널은 판정을 돌리지 않고 상태 judgment를 바꾸지 않음', { plugins: [BAND] }, async ($, on) => {
  const { w, ui } = await openPanel($, on, AB)
  const runs = w.runs
  const before = await peek($)
  for (const key of ['unit-1', 'unit-2', 'expand', 'unit-all', 'expand']) await ui.press({ key })
  await ui.unmount()
  await closePanel($)
  expect(w.runs).toBe(runs)
  expect(await peek($)).toBe(before)
})

test('(부분) 띠 길: panelOpenArgs(state, 200)로 연 인자가 harness-panel·하네스 진행·focus 없음·rows ≥ 3, dock 마운트 첫 줄 R1·지도: 전체', { plugins: [BAND] }, async ($, on) => {
  const w = world(on)
  await feedJudgment($, w, R1)
  await bandOpen($, 200)
  expect(w.opened).toHaveLength(1)
  const args = w.opened[0]!
  expect(args.id).toBe('harness-panel')
  expect(args.title).toBe('하네스 진행')
  expect('focus' in args).toBe(false)
  expect(args.rows).toBeGreaterThanOrEqual(3)
  const ui = await mountPane($, 196, { placement: 'dock' })
  const first = linesOf(await ui.drawn())[0]
  expect(first).toContain('R1')
  expect(first).toContain('지도: 전체')
})

test('(부분) 띠 길로 연 뒤 (1) 다시 열기 (2) devflow-harness → 연 id 집합 하나, (2) 뒤 여는 수 그대로', { plugins: [BAND] }, async ($, on) => {
  const w = world(on)
  await feedJudgment($, w, R1)
  await bandOpen($, 200)
  await bandOpen($, 200)
  expect(new Set(w.opened.map(o => o.id))).toEqual(new Set(['harness-panel']))
  expect(w.panes).toEqual(['harness-panel'])
  const n = w.opened.length
  await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: 'x' })
  await w.clock.advance(600)
  expect(w.opened).toHaveLength(n)
  expect(w.panes).toEqual(['harness-panel'])
})

test('(부분) a를 고른 패널을 닫은 뒤 (1) devflow-harness → 여는 수 그대로·목록 빔 (2) 띠 길로 열면 하나, 첫 줄 지도: 전체', { plugins: [BAND] }, async ($, on) => {
  const { w, ui } = await openPanel($, on, AB)
  await ui.press({ key: keyOf(await ui.drawn(), 'a') })
  expect(linesOf(await ui.drawn())[0]).toContain('지도: a')
  await ui.unmount()
  await closePanel($)
  expect(w.panes).toEqual([])
  const n = w.opened.length
  await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: 'x' })
  await w.clock.advance(600)
  expect(w.opened).toHaveLength(n)
  expect(w.panes).toEqual([])
  await bandOpen($, 120)
  expect(w.opened).toHaveLength(n + 1)
  expect(w.panes).toEqual(['harness-panel'])
  const again = await mountPane($)
  expect(linesOf(await again.drawn())[0]).toContain('지도: 전체')
})

test('(부분) 패널이 걸린 플러그인에서 devflow-harness의 스킬 글이 그대로', async ($, on) => {
  const w = world(on)
  await feedJudgment($, w, R1)
  const text = '스킬 글 원문\n둘째 줄'
  expect(await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text })).toEqual({ text })
})

test('흐름 줄이 없어지면 다음 그림에서 지도: 전체, 그 줄이 다시 생겨도 전체 그대로', async ($, on) => {
  const { w, ui } = await openPanel($, on, AB)
  await ui.press({ key: keyOf(await ui.drawn(), 'a') })
  await refeed($, w, dash(AB_TASKS.filter(t => t.flow !== 'a'), { flows: [flow('b', '진행')] }))
  const lines = linesOf(await ui.drawn())
  expect(lines[0]).toContain('지도: 전체')
  expect(laneSection(lines).some(l => l.startsWith('a'))).toBe(false)
  await refeed($, w, AB)
  expect(linesOf(await ui.drawn())[0]).toContain('지도: 전체')
})

// 패널은 엔진 틀만 쓰고 본문에 테두리를 그리지 않는다. 패널 코드는 바뀌지 않아 지금 코드에서 통과하는 것이 맞다.
test('실행 2026-01-01-sample-run-fixes, 패널이 닫힌 채 명령으로 열고 W=80: 그린 내용에 ╭·╮·╰·╯가 없고 첫 줄에 실행 이름과 지도: 전체', async ($, on) => {
  const name = '2026-01-01-sample-run-fixes'
  const w = world(on)
  await feedJudgment($, w, dash([task({ id: 'T1', flow: 'a', title: '첫 일' })], {
    flows: [flow('a', '진행')],
    run: { name, dir: `D:/w/_workspace/${name}`, status: '진행', run_md_unreadable: false, flow_cap: 2 },
  }))
  expect(w.panes).toEqual([])
  await runCommand($)
  const lines = linesOf(await (await mountPane($, 80)).drawn())
  expect(lines.length).toBeGreaterThan(1)
  for (const l of lines) for (const ch of ['╭', '╮', '╰', '╯']) expect([l, ch, l.includes(ch)]).toEqual([l, ch, false])
  expect(lines[0]).toContain(name)
  expect(lines[0]).toContain('지도: 전체')
})
