export function currentRoute() {
  const hash = window.location.hash || '#/'
  const [path, qs] = hash.slice(1).split('?')
  const params = Object.fromEntries(new URLSearchParams(qs || ''))
  return { path, params }
}
export function navigate(path) { window.location.hash = path }

