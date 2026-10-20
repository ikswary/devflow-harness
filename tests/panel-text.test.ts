// 화면 칸 셈과 줄이기·잇기의 시험(8.1 끝).
import { expect, test } from 'claude-code/testing'

import { cells, fitEnd, wrapParts } from '../hooks/panel-text'

// Python 3.12(unicodedata 15.0.0)로 잰 값. 표를 만든 명령:
//   python -c "import unicodedata as u,json;ss=['가','한글 제목','ㄱ','ᄀ','ᅡ','漢字','Ａ！','─│┌└├┬┴┼','…','·','abc XYZ 019','😀','🚀','✅','❤','진행 35분 · 못 띄움: 사용자 할 일 대기','T001 P1 지도·흐름 줄 그리기'];print(json.dumps([[s,sum(2 if u.east_asian_width(c) in 'WF' else 1 for c in s)] for s in ss],ensure_ascii=False))"
const MEASURED: [string, number][] = [
  ['가', 2], // 한글 음절
  ['한글 제목', 9],
  ['ㄱ', 2], // 호환 자모
  ['ᄀ', 2], // 첫소리 자모(W)
  ['ᅡ', 1], // 가운뎃소리 자모(N)
  ['漢字', 4], // CJK
  ['Ａ！', 4], // 전각(F)
  ['─│┌└├┬┴┼', 8], // 상자 문자(A)
  ['…', 1], // A
  ['·', 1], // A
  ['abc XYZ 019', 11], // ASCII
  ['😀', 2], // 이모지
  ['🚀', 2],
  ['✅', 2],
  ['❤', 1], // 이모지지만 N
  ['진행 35분 · 못 띄움: 사용자 할 일 대기', 38],
  ['T001 P1 지도·흐름 줄 그리기', 27],
]

test('cells: Python unicodedata로 잰 표와 같음', async () => {
  for (const [s, n] of MEASURED) expect([s, cells(s)]).toEqual([s, n])
})

test('fitEnd: 들어가면 그대로, 넘으면 width − 1칸까지 남기고 …', async () => {
  expect(fitEnd('abc', 3)).toBe('abc')
  expect(fitEnd('abcd', 3)).toBe('ab…')
  expect(fitEnd('한글제목', 7)).toBe('한글제…')
  // 넓은 글자가 경계에 걸리면 그 글자를 빼고 … (6칸 이하)
  expect(fitEnd('한글제목', 6)).toBe('한글…')
  expect(cells(fitEnd('한글제목', 6))).toBeLessThanOrEqual(6)
})

test('wrapParts: sep로 잇다 넘으면 새 줄에 indent칸, 넘는 조각은 글자 경계에서 끊음', async () => {
  expect(wrapParts(['aa', 'bb', 'cc'], ', ', 6, 2)).toEqual(['aa, bb', '  cc'])
  expect(wrapParts(['aa', 'bb'], ' · ', 20, 2)).toEqual(['aa · bb'])
  expect(wrapParts(['abcdefgh'], ' ', 4, 1)).toEqual(['abcd', ' efg', ' h'])
  const lines = wrapParts(['가나다라마바사', '아'], ', ', 6, 0)
  expect(lines).toEqual(['가나다', '라마바', '사, 아'])
  for (const l of lines) expect(cells(l)).toBeLessThanOrEqual(6)
})
