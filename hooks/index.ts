import type { Register } from 'claude-code'

import { registerCommon } from './common'
import { registerPanel } from './panel'
import { registerStatus } from './status'

export const register: Register = (on, options) => {
  registerCommon(on)
  registerStatus(on)
  registerPanel(on)
}
