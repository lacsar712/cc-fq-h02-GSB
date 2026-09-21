export function canShowSubmit(role) {
  return role === 'bioops'
}

export function submitPathFor(role) {
  return canShowSubmit(role) ? '/jobs/new' : '/jobs'
}
