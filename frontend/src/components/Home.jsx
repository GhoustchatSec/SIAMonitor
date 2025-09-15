import React, { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'
import { kcHasRole } from '../auth/keycloak'
import { navigate } from '../router'

export default function Home() {
  const isTeacher = kcHasRole('teacher')
  const isStudent = kcHasRole('student')

  const [me, setMe] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let mounted = true
    Promise.all([
      apiGet('/api/profile'),
      apiGet('/api/projects')
    ]).then(([profile, projects]) => {
      if (!mounted) return
      setMe(profile)
      setItems(projects || [])
      setLoading(false)
    }).catch(e => {
      if (!mounted) return
      setErr('Не удалось загрузить данные')
      setLoading(false)
    })
    return () => { mounted = false }
  }, [])

  const canCreateProject = isStudent && me?.mode === 'lead'

  const createProject = async () => {
    const name = prompt('Название проекта')
    if (!name) return
    try {
      const p = await apiPost('/api/projects', { name })
      navigate(`/project?id=${p.id}`)
    } catch (e) {
      alert('Не удалось создать проект')
    }
  }

  return (
    <div>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
        <h2 style={{margin:0}}>{isTeacher ? 'Все проекты' : 'Мои проекты'}</h2>
        {canCreateProject && (
          <button onClick={createProject} style={{cursor:'pointer'}}>Создать проект</button>
        )}
      </div>

      {loading ? <div>Загрузка…</div> : err ? <div style={{color:'red'}}>{err}</div> : (
        items.length ? (
          <ul>
            {items.map(p => (
              <li key={p.id}>
                <a href={`#/project?id=${p.id}`}>{p.name}</a>
              </li>
            ))}
          </ul>
        ) : <div>Проектов пока нет</div>
      )}
    </div>
  )
}

