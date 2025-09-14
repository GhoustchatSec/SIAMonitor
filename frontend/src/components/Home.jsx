import React, { useEffect, useState } from 'react'
import { apiGet } from '../api'
import { kcHasRole } from '../auth/keycloak'
import { navigate } from '../router'

export default function Home() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const isTeacher = kcHasRole('teacher')

  useEffect(() => {
    setLoading(true); setErr('')
    apiGet('/api/projects')
      .then(setItems)
      .catch(e => setErr(e.message || 'error'))
      .finally(()=>setLoading(false))
  }, [])

  return (
    <div>
      <h2>{isTeacher ? 'Все проекты' : 'Мои проекты'}</h2>
      {loading ? <div>Загрузка…</div> : err ? <div style={{color:'red'}}>{err}</div> : (
        items.length ? (
          <ul>
            {items.map(p => (
              <li key={p.id}>
                <a href={`#/project?id=${p.id}`}>{p.name}</a>
              </li>
            ))}
          </ul>
        ) : (
          <div style={{opacity:0.7}}>
            {isTeacher ? 'Пока нет проектов.' : 'Не участвует в проектах.'}
          </div>
        )
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

