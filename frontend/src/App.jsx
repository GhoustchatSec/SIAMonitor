import React, { useEffect, useState } from 'react'
import { initKeycloak, kcLogin, kcLogout, kcToken, kcProfile, kcHasRole } from './auth/keycloak.js'
import { currentRoute, navigate } from './router.js'
import Home from './components/Home.jsx'
import Profile from './components/Profile.jsx'
import ProjectPage from './components/ProjectPage.jsx'
import Rating from './components/Rating.jsx'

export default function App() {
  const [ready, setReady] = useState(false)
  const [authed, setAuthed] = useState(false)
  const [route, setRoute] = useState(currentRoute())
  const [me, setMe] = useState(null)

  useEffect(() => {
    initKeycloak((kc, authenticated) => {
      setAuthed(!!authenticated)
      setReady(true)
      if (authenticated) {
        fetch('/api/me', { headers: { Authorization: `Bearer ${kcToken()}` } })
          .then(r => r.json()).then(setMe).catch(()=>{})
      }
    }, { initTimeoutMs: 4000 })
  }, [])

  useEffect(() => {
    const onHash = () => setRoute(currentRoute())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (!ready) return <div style={{fontFamily:'system-ui', padding:20}}>Загрузка…</div>

  const isTeacher = kcHasRole('teacher')
  const isStudent = kcHasRole('student')

  return (
    <div style={{fontFamily:'system-ui', padding:20, maxWidth:980}}>
      <header style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
        <h1 style={{margin:0, fontSize:24, cursor:'pointer'}} onClick={()=>navigate('/')}>SIAMonitor</h1>
        <nav style={{display:'flex', gap:10}}>
          {authed && <a href="#/">Проекты</a>}
          {authed && <a href="#/profile">ЛК</a>}
          {authed && isTeacher && <a href="#/rating">Рейтинг</a>}
        </nav>
        <div>
          {authed ? <button onClick={kcLogout}>Выйти</button> : <button onClick={kcLogin}>Войти</button>}
        </div>
      </header>

      {authed ? (
        <>
          {route.path === '/' && <Home />}
          {route.path === '/profile' && <Profile />}
          {route.path === '/project' && <ProjectPage />}
          {route.path === '/rating' && <Rating />}
        </>
      ) : (
        <div>Пожалуйста, войдите.</div>
      )}
    </div>
  )
}

