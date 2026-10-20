// 패널이 그린 내용 전체를 줄(Row) 목록으로 만든다.
// $를 쓰지 않는 순수 함수다. 판정은 다시 하지 않고 판정 JSON 값 그대로 쓴다.
import type { DashState } from '../types'
import { buttonRows, laneLines, lanesOf, mapRows, panelButtons, unitOf } from './panel-map'
import type { CellExtra, PanelButton } from './panel-map'
import { cells, fitEnd, wrapParts } from './panel-text'

export type Row = { kind: 'text'; text: string; dim?: boolean } | { kind: 'buttons'; buttons: PanelButton[] }

const UNCLEAN_KEYS = ['running_agent', 'external_progress', 'waiting_user']

// 패널의 칸 덧붙임: 둘째 줄의 시작 판단·경과 조각, 할 일·외부 작업 덧줄. 상태 낱말은 mapLines가 붙인다.
export const panelExtra: CellExtra = t => {
  const phrases: string[] = []
  if (t.start === 'ready') {
    phrases.push(t.elapsed ? `시작 가능 ${t.elapsed.text}` : '시작 가능')
  } else if (t.start === 'held') {
    phrases.push(`못 띄움: ${t.reason_text}`)
    if (t.elapsed) phrases.push(`기다림 ${t.elapsed.text}`)
  } else if (t.start === 'undecidable') {
    phrases.push(`판정 못 함(${t.reason_text})`)
  } else if (t.elapsed?.kind === 'approval') {
    phrases.push(`승인 대기 ${t.elapsed.text}`)
  } else if (t.elapsed?.kind === 'progress') {
    phrases.push(`진행 ${t.elapsed.text}`)
  }
  const lines: string[] = []
  if (t.waiting_user !== '') lines.push(`할 일 대기: ${t.waiting_user}`)
  if (t.external_progress !== '') lines.push(`외부 작업: ${t.external_progress}`)
  return { phrases, lines }
}

const text = (s: string): Row => ({ kind: 'text', text: s })

// 머리 줄, 오류 줄, 버튼 줄, 흐름별 상태, 의존 지도, 정리 안 된 값, 읽지 못함. 고른 줄이 없어졌으면 전체로 그린다.
export function panelRows(state: DashState | null, view: { unit: string; expanded: boolean }, width: number): Row[] {
  const error = state && state.error !== '' ? [text(fitEnd(`판정 실패: ${state.error}`, width))] : []
  const j = state?.result ?? null
  if (j === null) return [text('판정 결과 없음'), ...error]
  if (j.run === null) return [text(j.message ?? ''), ...error]

  const lanes = lanesOf(j)
  const unit = unitOf(view.unit, lanes)
  const tail = ` · 지도: ${unit}${j.run.run_md_unreadable ? ' · run.md 읽지 못함' : ''}`
  const rows: Row[] = [text(fitEnd(j.run.name, Math.max(1, width - cells(tail))) + tail), ...error]
  for (const buttons of buttonRows(panelButtons(lanes, view.expanded), width)) rows.push({ kind: 'buttons', buttons })

  rows.push(text('흐름별 상태'))
  for (const lane of lanes) {
    for (const l of laneLines(j, lane, width, { misalign: true, folded: true, expanded: view.expanded })) rows.push(text(l))
  }
  rows.push(text('의존 지도'))
  // 끝난 task의 줄은 흐리게: 흐림 여부는 mapRows가 정한 값 그대로 넘긴다.
  for (const r of mapRows(j, unit, width, panelExtra)) rows.push({ kind: 'text', text: r.text, dim: r.dim })

  if (j.unclean.length > 0) {
    rows.push(text('정리 안 된 값'))
    for (const u of j.unclean) {
      const keys = UNCLEAN_KEYS.filter(k => u.keys.includes(k))
      for (const l of wrapParts([`${u.id}: ${keys[0] ?? ''}`, ...keys.slice(1)], ', ', width, 2)) rows.push(text(l))
    }
  }
  if (j.unreadable.length > 0) {
    rows.push(text('읽지 못함'))
    for (const u of j.unreadable) rows.push(text(fitEnd(`${u.id}: ${u.why}`, width)))
  }
  return rows
}
