// 입력창 위 띠: 판정 상태 judgment를 읽어 요약 줄·버튼 줄·(펼침이면) 흐름별 상태와 의존 지도를 둥근 테두리 안에 그리고,
// 버튼 누름과 /clear 뒤 처음 값을 다룬다.
// 줄 목록과 테두리는 status-view의 순수 함수가 만들고 여기서는 요소로 바꾸기만 한다. 판정 갱신은 common 몫이라 상태에 쓰지 않는다.
import { read } from 'claude-code'
import type { On } from 'claude-code'

import { ALL, panelOpenArgs, unitOf } from './panel-map'
import { bandFrame, bandLanes, bandReady, bandRows, innerWidth, noRunLine } from './status-view'
import type { FramedRow } from './status-view'

const judgmentRef = { plugin: 'devflow-harness', key: 'judgment' } as const

// 모듈 변수: 다시 불러오면 처음 값(접음·전체). 패널의 단위와 따로다.
let expanded = false
let unit = ALL

export const registerStatus = (on: On) => {
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const s = await read($, judgmentRef)
    const j = s?.result ?? null
    const width = e.props.bodyColumns
    const { Box, Button, Text } = $.ui.resolve(e)
    // 테두리 줄은 Text 하나, 안쪽 줄은 가로 Box에 "│ "·가운데·"{채움} │" 세 조각. 흐림은 가운데 Text에만 두고
    // 테두리 글자에는 색·흐림을 주지 않는다. 실행 없음 한 줄에는 버튼이 없어 onPress를 부르지 않는다.
    const draw = (framed: FramedRow[], onPress: (key: string) => () => Promise<void> = () => async () => {}) => (
      <Box flexDirection="column">
        {framed.map(row => row.kind === 'edge'
          ? <Text>{row.text}</Text>
          : (
            <Box flexDirection="row">
              <Text>{'│ '}</Text>
              {row.kind === 'text'
                ? <Text dimColor={row.dim === true}>{row.text}</Text>
                : (
                  <Box flexDirection="row" columnGap={2}>
                    {row.buttons.map(b => b.hotkey
                      ? <Button key={b.key} hotkey={b.hotkey} plain onPress={onPress(b.key)}>{b.label}</Button>
                      : <Button key={b.key} plain onPress={onPress(b.key)}>{b.label}</Button>)}
                  </Box>
                )}
              <Text>{row.fill + ' │'}</Text>
            </Box>
          ))}
      </Box>
    )

    // 흐름·수가 빠진 불완전한 판정은 그리지 않고 비킨다(common 시험의 인라인 플러그인이 이 자리에 그린다).
    if (j?.run && !bandReady(j)) return next(e)

    if (j?.run) {
      const lanes = bandLanes(j)
      // 고른 흐름이 사라졌으면 전체로 되돌려 저장한다.
      unit = unitOf(unit, lanes)
      const columns = e.viewport?.columns ?? width
      // 누름: 펼침은 map-toggle만 바꾼다. 패널 열기는 펼침도 지도 단위도 그대로 둔다.
      const onPress = (key: string) => async () => {
        if (key === 'open-panel') {
          await $.ui.open(panelOpenArgs(await read($, judgmentRef), columns))
          return
        }
        if (key === 'map-toggle') expanded = !expanded
        else if (key === 'unit-all') unit = ALL
        else unit = lanes[Number(key.slice('unit-'.length)) - 1]?.name ?? ALL
        $.ui.invalidate('ui.render')
      }
      // 안의 줄은 테두리 안쪽 폭으로 그리고 위 테두리에 실행 이름을 둔다.
      const rows = bandRows(j, { unit, expanded }, innerWidth(width))
      return draw(bandFrame(j.run.name, rows, width), onPress)
    }

    // 실행이 없으면 이 세션에서 불렸을 때만 한 줄을 이름 없는 테두리로 감싼 세 줄, 버튼 없음. 안 불렸으면 그리지 않음.
    if (s?.invokedAt != null) {
      return draw(bandFrame(null, [{ kind: 'text', text: noRunLine(s, innerWidth(width)) }], width))
    }
    return next(e)
  })

  // /clear 뒤는 새 세션이라 처음 그림이 접음·전체가 되게 되돌린다.
  on('session.end', { reason: 'clear' }, async ($, e, next) => {
    const r = await next(e)
    expanded = false
    unit = ALL
    $.ui.invalidate('ui.render')
    return r
  })
}
