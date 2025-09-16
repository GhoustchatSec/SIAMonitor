import React, { useEffect, useState } from 'react'
import { apiGet } from '../api'
import { kcHasRole } from '../auth/keycloak'
import { navigate } from '../router'

export default function Home() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [me, setMe] = useState(null)

  const isTeacher = kcHasRole('teacher')
  const isStudent = kcHasRole('student')

  useEffect(() => {
    setLoading(true); setErr('')
    Promise.all([
      apiGet('/api/projects'),
      apiGet('/api/profile')  // нужно, чтобы узнать mode (lead/participant)
    ])
      .then(([projects, profile]) => {
        setItems(projects || [])
        setMe(profile || null)
      })
      .catch(e => setErr(e.message || 'error'))
      .finally(() => setLoading(false))
  }, [])

  const canCreateProject = isStudent && me?.mode === 'lead'

  return (
    <div>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
        <h2 style={{margin:0}}>{isTeacher ? 'Все проекты' : 'Мои проекты'}</h2>
        {canCreateProject && (
          // Никаких prompt — просто переводим на страницу с полноценной формой (есть поле Описание)
          <button onClick={() => navigate('/project')} style={{cursor:'pointer'}}>Создать проект</button>
        )}
      </div>

      {loading ? <div>Загрузка…</div> : err ? <div style={{color:'red'}}>{err}</div> : (
        items.length ? (
          <ul>
            {items.map(p => (
              <li key={p.id} style={{marginBottom:8}}>
                <a href={`#/project?id=${p.id}`} style={{fontWeight:600}}>{p.name}</a>
                {p.description ? <div style={{opacity:0.8, fontSize:13}}>{p.description}</div> : null}
              </li>
            ))}
          </ul>
        ) : <div>Проектов пока нет</div>
      )}

      {!isTeacher && (
        <div style={{marginTop:12}}>
          <a href="#/profile">Перейти в ЛК (lead может создать проект)</a>
        </div>
      )}
      {isTeacher && (
        <div style={{marginTop:12}}>
          <a href="#/rating">Перейти к рейтингу команд</a>
        </div>
      )}
    </div>
  )
}

