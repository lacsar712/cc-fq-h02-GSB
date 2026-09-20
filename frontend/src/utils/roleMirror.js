import { canShowSubmit } from './submitPolicy.js'

export function mirrorCapabilities(auth) {
  return {
    canSubmit: canShowSubmit(auth?.role),
    isAuditor: auth?.role === 'auditor',
    isBioops: auth?.role === 'bioops',
  }
}
