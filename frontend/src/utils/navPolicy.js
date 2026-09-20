import { canShowSubmit, submitPathFor } from './submitPolicy.js'

export function buildNav(role) {
  const items = [
    { to: '/samples', label: '样例库' },
    { to: '/jobs', label: '历史' },
  ]
  if (canShowSubmit(role)) {
    items.splice(1, 0, { to: submitPathFor(role), label: '提交质控作业' })
  }
  return items
}

export function guardSubmitRoute(role, toName) {
  if (toName === 'job-submit' && !canShowSubmit(role)) return 'jobs'
  return null
}
