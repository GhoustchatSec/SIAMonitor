import Keycloak from 'keycloak-js'

const keycloak = new Keycloak({
  url: `${window.location.origin}/auth`,
  realm: 'siamonitor',
  clientId: 'frontend',
})

let _autorefreshTimer = null

export function initKeycloak(onReady, { initTimeoutMs = 4000 } = {}) {
  if (_autorefreshTimer) clearInterval(_autorefreshTimer)

  const withTimeout = (p, ms) => new Promise((res, rej) => {
    const t = setTimeout(() => rej(new Error('kc_init_timeout')), ms)
    p.then(v => { clearTimeout(t); res(v) })
     .catch(e => { clearTimeout(t); rej(e) })
  })

  withTimeout(keycloak.init({
    onLoad: 'check-sso',
    pkceMethod: 'S256',
    checkLoginIframe: false,
    silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
    silentCheckSsoFallback: true,
    redirectUri: window.location.origin,
    enableLogging: true,
  }), initTimeoutMs)
  .then(authenticated => {
    onReady(keycloak, authenticated)
    _autorefreshTimer = setInterval(() => {
      keycloak.updateToken(60).catch(() => keycloak.login())
    }, 30000)
  })
  .catch(() => {
    
    onReady(keycloak, false)
  })
}

export const kcLogin   = () => keycloak.login({ redirectUri: window.location.origin })
export const kcLogout  = () => keycloak.logout({ redirectUri: window.location.origin })
export const kcToken   = () => keycloak.token
export const kcProfile = () => keycloak.tokenParsed || {}
export function kcHasRole(role) {
  const roles = keycloak.tokenParsed?.realm_access?.roles || []
  return roles.includes(role)
}

