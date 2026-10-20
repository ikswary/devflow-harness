// 판정 갱신: 이벤트와 분 타이머로 scripts/board_dash.py를 돌려 상태 judgment 하나에 넣는다.
// 그리기는 status·panel이 같은 상태를 읽어 한다.
import { read, update } from 'claude-code'
import type { EngineInterface, On } from 'claude-code'

import type { DashJudgment, DashState } from '../types'

const judgmentRef = { plugin: 'devflow-harness', key: 'judgment' } as const

const BATCH_MS = 500
const MINUTE_MS = 60000
const MINUTE_LAG_MS = 1000
const RUN_TIMEOUT_MS = 10000
const EMPTY: DashState = { result: null, error: '', at: 0, invokedAt: null }

// 모듈 변수: 다시 불러오면 처음 값이 되고, 옛 타이머도 함께 사라진다(reference.md:61-62).
let batch: { cancel: () => void } | null = null
let minute: { cancel: () => void } | null = null
let running = false
let dirty = false

export function registerCommon(on: On): void {
  on('session.start', async ($, e, next) => {
    const r = await next(e)
    schedule($)
    await armMinute($)
    return r
  })

  on('tool.call', async ($, e, next) => {
    const r = await next(e)
    schedule($)
    return r
  })

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    schedule($)
    return r
  })

  on('session.end', { reason: 'clear' }, async ($, e, next) => {
    const r = await next(e)
    await update($, judgmentRef, s => ({ ...EMPTY, ...s, invokedAt: null }))
    schedule($)
    return r
  })

  on('skill.prompt', { skill: 'devflow-harness:devflow-harness' }, async ($, e, next) => {
    const r = await next(e)
    const now = await $.clock.now()
    await update($, judgmentRef, s => ({ ...EMPTY, ...s, invokedAt: now }))
    schedule($)
    return r
  })
}

// 첫 이벤트부터 500 ms 뒤 판정 한 번. 그 사이 이벤트는 같은 회차다.
function schedule($: EngineInterface): void {
  if (batch !== null) return
  batch = $.clock.after(BATCH_MS, () => {
    batch = null
    void run($)
  })
}

// 판정이 도는 중이면 끝난 뒤 한 번 더 돌린다.
async function run($: EngineInterface): Promise<void> {
  if (running) {
    dirty = true
    return
  }
  running = true
  try {
    await refresh($)
  } finally {
    running = false
    if (dirty) {
      dirty = false
      schedule($)
    }
  }
}

// 지역 시각의 분이 바뀐 뒤 1초에 묶음 없이 판정한다. epoch ms의 분 경계는 지역 시각의 분 경계와 같다.
async function armMinute($: EngineInterface): Promise<void> {
  minute?.cancel()
  const now = await $.clock.now()
  minute = $.clock.after(MINUTE_MS - (now % MINUTE_MS) + MINUTE_LAG_MS, () => {
    void run($)
    void armMinute($)
  })
}

// 판정 한 번. 실패하면 직전 result를 두고 error와 시각만 적는다. invokedAt은 건드리지 않는다.
async function refresh($: EngineInterface): Promise<void> {
  const prev = (await read($, judgmentRef)) ?? EMPTY
  let result = prev.result
  let error = ''
  try {
    const root = await $.session.root()
    let sid = ''
    try {
      sid = (await $.session.id()).trim()
    } catch {
      sid = ''
    }
    const last = prev.result
    const idle = last !== null && last.run === null && last.workdir === root && last.session === (sid || null)
    if (idle && !(await $.fs.exists(`${root}/_workspace`))) return

    const argv = ['python', '-B', `${$.plugin.root}/scripts/board_dash.py`, root]
    if (sid) argv.push('--session', sid)
    if (last?.run) argv.push('--shown', last.run.name)
    const ran = await $.process.run(argv, { timeoutMs: RUN_TIMEOUT_MS })
    const stderr = ran.stderr.split(/\r?\n/)[0] ?? ''
    if (ran.exitCode !== 0) {
      error = `종료 ${ran.exitCode} ${stderr}`.trim()
    } else {
      const parsed = parseJudgment(ran.stdout)
      if (parsed === null) error = `판정 JSON을 읽지 못함 ${stderr}`.trim()
      else result = parsed
    }
  } catch (err) {
    error = `거부 ${String(err instanceof Error ? err.message : err).split(/\r?\n/)[0]}`
  }
  if (error === prev.error && JSON.stringify(result) === JSON.stringify(prev.result)) return
  const at = await $.clock.now()
  await update($, judgmentRef, s => ({ ...EMPTY, ...s, result, error, at }))
}

function parseJudgment(text: string): DashJudgment | null {
  try {
    const value = JSON.parse(text)
    return value !== null && typeof value === 'object' && value.schema === 1 ? (value as DashJudgment) : null
  } catch {
    return null
  }
}
