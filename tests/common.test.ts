// common 갱신의 시험.
// 시험의 on이 session·fs·process·시계를 대신 답하고, 함께 띄운 인라인 플러그인이 상태 judgment를 AbovePrompt에 그린 글로 본다.
import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import type { Engine, MockClock } from 'claude-code/testing'

const VIEW = {
  name: 'dash-view',
  register(on: On) {
    on('ui.render', { component: 'AbovePrompt' }, async ($, e) => {
      const { value } = await $.state.get({ plugin: 'devflow-harness', key: 'judgment' })
      const { Text } = $.ui.resolve(e)
      return h(Text, {}, JSON.stringify(value ?? null))
    })
  },
}

type Answer = { exitCode?: number; stdout?: string; stderr?: string; delayMs?: number }

type World = {
  clock: MockClock
  calls: string[][]
  answers: Answer[]
  sid: { value: string | null }
  hasWorkspace: { value: boolean }
}

const ROOT = 'D:/w'

function judgment(name: string | null, extra: Record<string, unknown> = {}) {
  return {
    schema: 1,
    now: '2026-10-06 10:00',
    workdir: ROOT,
    session: 'S1',
    message: name === null ? '이 세션이 진행하는 실행 없음' : null,
    run: name === null ? null : { name, dir: `${ROOT}/_workspace/${name}`, status: '진행', run_md_unreadable: false, flow_cap: 2 },
    tasks: [],
    ...extra,
  }
}

function ok(value: unknown, delayMs = 0): Answer {
  return { exitCode: 0, stdout: JSON.stringify(value), delayMs }
}

function world(on: On): World {
  const w: World = {
    clock: mock.clock(on, { now: 30000 }),
    calls: [],
    answers: [],
    sid: { value: 'S1' },
    hasWorkspace: { value: true },
  }
  on('session.root', () => ({ value: ROOT }))
  on('session.id', () => (w.sid.value === null ? { deny: 'no session' } : { value: w.sid.value }))
  on('fs.exists', () => ({ value: w.hasWorkspace.value }))
  on('process.run', async ($, e) => {
    w.calls.push([...e.argv])
    const a = w.answers.shift() ?? ok(judgment('R1'))
    if (a.delayMs) await w.clock.sleep(a.delayMs)
    return {
      value: {
        exitCode: a.exitCode ?? 0,
        stdout: a.stdout ?? '',
        stderr: a.stderr ?? '',
        isStdoutTruncated: false,
        isStderrTruncated: false,
      },
    }
  })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: 'ran' }))
  on('turn.complete', () => ({ text: 'answer' }))
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  on('skill.prompt', ($, e) => ({ text: e.text }))
  return w
}

async function start($: Engine, w: World) {
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await w.clock.settle()
}

async function shown($: Engine) {
  const ui = await $.ui.mount({ plugin: 'dash-view', surface: 'terminal', component: 'AbovePrompt', props: {} as never })
  const tree = (await ui.drawn()) as { children: string[] }
  await ui.unmount()
  return JSON.parse(tree.children.join(''))
}

function toolCall($: Engine) {
  return $.tool.call({ tool: 'Bash', command: 'echo hi' } as never)
}

function turnComplete($: Engine) {
  return $.turn.complete({ reason: 'answer', answer: 'a', durationMs: 1, isAborted: false, turnId: 't1' })
}

function sessionEnd($: Engine, reason: 'clear' | 'logout') {
  return $.session.end({ reason, sessionId: 'S1', resume: {} } as never)
}

test('(가) 시작 뒤 500 ms 안에 process.run 한 번, 인자는 python -B 스크립트 root --session', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  await start($, w)
  await w.clock.advance(499)
  expect(w.calls).toHaveLength(0)
  await w.clock.advance(1)
  expect(w.calls).toHaveLength(1)
  const argv = w.calls[0]!
  expect(argv.slice(0, 2)).toEqual(['python', '-B'])
  expect(argv[2]).toEndWith('/scripts/board_dash.py')
  expect(argv.slice(3)).toEqual([ROOT, '--session', 'S1'])
})

test('(나) tool.call 뒤 500 ms에 한 번 더 불리고 JSON이 다르면 그린 글이 바뀜', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  w.answers.push(ok(judgment('R1')), ok(judgment('R1', { tasks: [{ id: 'T2' }] })))
  await start($, w)
  await w.clock.advance(500)
  expect((await shown($)).result.tasks).toEqual([])
  const ran = await toolCall($)
  expect(ran).toMatchObject({ result: 'ran' })
  await w.clock.advance(499)
  expect(w.calls).toHaveLength(1)
  await w.clock.advance(1)
  expect(w.calls).toHaveLength(2)
  expect((await shown($)).result.tasks).toEqual([{ id: 'T2' }])
})

test('(다) 이벤트 없이 분 경계 + 1000 ms마다 한 번씩만 불리고 경과 글이 그려짐', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  const at = (text: string) => ok(judgment('R1', { tasks: [{ id: 'T2', elapsed: { kind: 'progress', text } }] }))
  w.answers.push(at('3분'), at('4분'), at('5분'))
  await start($, w)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(1)
  await w.clock.set(60999)
  expect(w.calls).toHaveLength(1)
  await w.clock.set(61000)
  expect(w.calls).toHaveLength(2)
  expect((await shown($)).result.tasks[0].elapsed.text).toBe('4분')
  await w.clock.set(120999)
  expect(w.calls).toHaveLength(2)
  await w.clock.set(121000)
  expect(w.calls).toHaveLength(3)
  expect((await shown($)).result.tasks[0].elapsed.text).toBe('5분')
})

test('(라) session.id가 거부하면 인자에 --session이 없음', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  w.sid.value = null
  await start($, w)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(1)
  expect(w.calls[0]).not.toContain('--session')
  expect(w.calls[0]!.slice(3)).toEqual([ROOT])
})

test('(마) 둘째 회차의 인자에 --shown {첫 JSON의 run.name}', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  w.answers.push(ok(judgment('R7')), ok(judgment('R7')))
  await start($, w)
  await w.clock.advance(500)
  expect(w.calls[0]).not.toContain('--shown')
  await toolCall($)
  await w.clock.advance(500)
  expect(w.calls[1]!.slice(3)).toEqual([ROOT, '--session', 'S1', '--shown', 'R7'])
})

test('(바) process.run이 종료 1이면 그린 글이 직전 결과 그대로이고 error가 비지 않음', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  const first = judgment('R1', { tasks: [{ id: 'T2' }] })
  w.answers.push(ok(first), { exitCode: 1, stderr: 'boom\nsecond line' })
  await start($, w)
  await w.clock.advance(500)
  const before = await shown($)
  expect(before.error).toBe('')
  await toolCall($)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(2)
  const after = await shown($)
  expect(after.result).toEqual(first)
  expect(after.error).toContain('1')
  expect(after.error).toContain('boom')
  expect(after.error).not.toContain('second line')
})

test('(사) 앞 process.run이 도는 동안 온 tool.call은 그동안 부르지 않고 끝난 뒤 500 ms 안에 한 번 더', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  w.answers.push(ok(judgment('R1'), 3000), ok(judgment('R1')))
  await start($, w)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(1)
  await toolCall($)
  await w.clock.advance(2999)
  expect(w.calls).toHaveLength(1)
  await w.clock.advance(1)
  expect(w.calls).toHaveLength(1)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(2)
})

test('(아) 500 ms 안에 tool.call 다섯이면 process.run은 한 번만', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  await start($, w)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(1)
  for (let i = 0; i < 5; i += 1) {
    await toolCall($)
    await w.clock.advance(90)
  }
  await w.clock.advance(1000)
  expect(w.calls).toHaveLength(2)
})

test('(자) turn.complete 뒤 500 ms에 한 번 불림', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  await start($, w)
  await w.clock.advance(500)
  const done = await turnComplete($)
  expect(done).toMatchObject({ text: 'answer' })
  await w.clock.advance(499)
  expect(w.calls).toHaveLength(1)
  await w.clock.advance(1)
  expect(w.calls).toHaveLength(2)
})

test('(차) session.end clear 뒤 500 ms에 한 번, --session은 그때 session.id가 답한 값', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  await start($, w)
  await w.clock.advance(500)
  w.sid.value = 'S2'
  await sessionEnd($, 'clear')
  await w.clock.advance(499)
  expect(w.calls).toHaveLength(1)
  await w.clock.advance(1)
  expect(w.calls).toHaveLength(2)
  expect(w.calls[1]!.slice(4, 6)).toEqual(['--session', 'S2'])
})

test('(카) clear가 아닌 session.end에는 불리지 않음', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  await start($, w)
  await w.clock.advance(500)
  await sessionEnd($, 'logout')
  await w.clock.advance(1000)
  expect(w.calls).toHaveLength(1)
})

test('(타) skill.prompt devflow-harness: text 그대로, 500 ms 뒤 한 번, invokedAt은 일으킨 때의 시계', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  await start($, w)
  await w.clock.advance(500)
  await w.clock.advance(1234)
  const raisedAt = w.clock.now()
  const out = await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: 'x' })
  expect(out).toEqual({ text: 'x' })
  expect((await shown($)).invokedAt).toBe(raisedAt)
  await w.clock.advance(499)
  expect(w.calls).toHaveLength(1)
  await w.clock.advance(1)
  expect(w.calls).toHaveLength(2)
  expect((await shown($)).invokedAt).toBe(raisedAt)
})

test('(파) 다른 스킬의 skill.prompt에는 부르지 않고 invokedAt 그대로', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  await start($, w)
  await w.clock.advance(500)
  const before = await shown($)
  const out = await $.skill.prompt({ skill: 'commit', text: 'x' })
  expect(out).toEqual({ text: 'x' })
  await w.clock.advance(1000)
  expect(w.calls).toHaveLength(1)
  const after = await shown($)
  expect(after.invokedAt).toBe(before.invokedAt)
  expect(after.invokedAt).toBeNull()
})

test('(하) (타) 뒤 clear면 invokedAt이 null이고 다음 회차가 result·error·at을 그 회차 값으로 적음', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  const next = judgment('R2', { tasks: [{ id: 'T9' }] })
  w.answers.push({ exitCode: 1, stderr: 'boom' }, ok(judgment('R1')), ok(next))
  await start($, w)
  await w.clock.advance(500)
  expect((await shown($)).error).not.toBe('')
  await $.skill.prompt({ skill: 'devflow-harness:devflow-harness', text: 'x' })
  await w.clock.advance(500)
  expect((await shown($)).invokedAt).not.toBeNull()
  await sessionEnd($, 'clear')
  expect((await shown($)).invokedAt).toBeNull()
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(3)
  const after = await shown($)
  expect(after.result).toEqual(next)
  expect(after.error).toBe('')
  expect(after.at).toBe(w.clock.now())
  expect(after.invokedAt).toBeNull()
})

test('_workspace가 없고 직전 결과도 같은 root·세션의 없음이면 스크립트를 다시 부르지 않음', { plugins: [VIEW] }, async ($, on) => {
  const w = world(on)
  w.hasWorkspace.value = false
  w.answers.push(ok(judgment(null)), ok(judgment(null)))
  await start($, w)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(1)
  await toolCall($)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(1)
  w.hasWorkspace.value = true
  await toolCall($)
  await w.clock.advance(500)
  expect(w.calls).toHaveLength(2)
})
