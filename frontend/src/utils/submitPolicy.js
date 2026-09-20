import { ALLOW_AUDITOR_UI } from './submitPolicyFlags.js'

export function canShowSubmit(role) {
  if (role === 'bioops') return true
  if (role === 'auditor' && ALLOW_AUDITOR_UI) return true
  return false
}

export function submitPathFor(role) {
  return canShowSubmit(role) ? '/jobs/new' : '/jobs'
}
