// 패널 명령 /harness-panel, 여닫기, 버튼 누름, Pane 그리기.
// 패널은 명령 훅에서만 연다(띠의 여는 버튼은 status.tsx 몫). 판정은 읽기만 하고 실행 폴더에 쓰지 않는다.
import { read } from 'claude-code'
import type { EngineInterface, On } from 'claude-code'

import { ALL, lanesOf, panelOpenArgs, unitOf } from './panel-map'
import { panelRows } from './panel-view'

const judgmentRef = { plugin: 'devflow-harness', key: 'judgment' } as const

const COMMAND = { name: 'harness-panel', description: '하네스 진행 패널(흐름별 상태와 의존 지도)', immediate: true }

// 모듈 변수: 지도 단위와 펼침. 패널을 닫으면 처음 값, 다시 불러와도 처음 값이다.
let unit = ALL
let expanded = false

// 등록이 거부되면 명령만 없고, 같은 훅 사슬에 있는 판정 갱신(common의 session.start·session.end)은 그대로 돈다.
// 거부를 밖으로 던지면 플러그인의 그 이벤트 훅 전체가 건너뛰어져 띠·패널의 판정까지 멈춘다.
async function registerCommand($: EngineInterface): Promise<void> {
  try {
    await $.command.register(COMMAND)
  } catch {
    // 명령이 없으면 띠의 패널 열기 버튼으로 연다.
  }
}

export const registerPanel = (on: On) => {
  on('session.start', { isInteractive: true }, async ($, e, next) => {
    await registerCommand($)
    return next(e)
  })

  // /clear 뒤에는 session.start가 오지 않으므로 명령을 다시 등록한다.
  on('session.end', { reason: 'clear' }, async ($, e, next) => {
    const r = await next(e)
    await registerCommand($)
    return r
  })

  on('command.run', { command: 'harness-panel' }, async ($, e) => {
    const panes = await $.ui.panes()
    if (!panes.some(p => p.id === 'harness-panel')) {
      unit = ALL
      expanded = false
    }
    const state = await read($, judgmentRef)
    await $.ui.open(panelOpenArgs(state ?? null, e.presentation.columns))
    return {}
  })

  on('ui.close', { id: 'harness-panel' }, async ($, e, next) => {
    const r = await next(e)
    unit = ALL
    expanded = false
    return r
  })

  on('ui.render', { component: 'Pane', requestId: 'harness-panel' }, async ($, e) => {
    const state = (await read($, judgmentRef)) ?? null
    const lanes = state?.result ? lanesOf(state.result) : []
    if (state?.result && unitOf(unit, lanes) !== unit) unit = ALL
    const rows = panelRows(state, { unit, expanded }, e.props.bodyColumns)
    const { Box, Button, Text } = $.ui.resolve(e)
    const press = (key: string) => {
      if (key === 'expand') expanded = !expanded
      else if (key === 'unit-all') unit = ALL
      else unit = lanes[Number(key.slice('unit-'.length)) - 1]?.name ?? ALL
      void $.ui.invalidate('ui.render')
    }
    return (
      <Box flexDirection="column">
        {rows.map(row => row.kind === 'text'
          ? <Text dimColor={row.dim === true}>{row.text}</Text>
          : (
            <Box flexDirection="row" columnGap={2}>
              {row.buttons.map(b => <Button key={b.key} hotkey={b.hotkey} plain onPress={() => press(b.key)}>{b.label}</Button>)}
            </Box>
          ))}
      </Box>
    )
  })
}
