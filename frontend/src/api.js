import { kcToken } from './auth/keycloak.js'

async function handle(r) {
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export function apiGet(path) {
  return fetch(path, {
    headers: { Authorization: `Bearer ${kcToken()}` },
    cache: 'no-store',
  }).then(handle)
}

export function apiPost(path, body) {
  return fetch(path, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${kcToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  }).then(handle)
}

export function apiUpload(path, formData) {
  return fetch(path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${kcToken()}` },
    body: formData,
  }).then(handle)
}

