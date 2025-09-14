import React, { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'
import { kcHasRole } from '../auth/keycloak'
import { navigate } from '../router'

export default function Profile() {
  const [me, setMe] = useState(null)          
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  const isTeacher = kcHasRole('teacher')

  const load = () => {
    setLoading(true); setErr('')
    apiGet('/api/profile')
      .then(setMe)
      .catch(e => setErr(e.message || 'error'))
      .finally(()=>setLoading(false))
  }

  useEffect(() => { load() }, [])

  const save = async (patch) => {
    try {
      const next = await apiPost('/api/profile', { ...me, ...patch })
      setMe(next)
    } catch (e) { alert(e.message) }
  }

  if (loading) return <div>Загрузка…</div>
  if (err) return <div style={{color:'red'}}>{err}</div>
  if (!me) return <div>Нет данных</div>

  const isLead = me.mode === 'lead'

  return (
    <div>
      <h2>Личный кабинет</h2>

      <div style={{display:'grid', gap:8, maxWidth:500}}>
        <label>ФИО
          <input value={me.full_name || ''} onChange={e=>setMe({...me, full_name:e.target.value})} />
        </label>
        <label>Номер группы
          <input value={me.group_no || ''} onChange={e=>setMe({...me, group_no:e.target.value})} />
        </label>
        <label>Корп. почта
          <input value={me.email_corp || ''} onChange={e=>setMe({...me, email_corp:e.target.value})} />
        </label>
        <label>Telegram
          <input value={me.tg || ''} onChange={e=>setMe({...me, tg:e.target.value})} />
        </label>

        <div>
          Режим аккаунта:&nbsp;
          <select value={me.mode} onChange={e=>save({ mode: e.target.value })}>
            <option value="participant">participant</option>
            <option value="lead">lead</option>
          </select>
          <div style={{fontSize:12, opacity:0.8, marginTop:4}}>
            Переключение в режим lead «обнуляет» привязки к командам (по ТЗ).
          </div>
        </div>

        <div>
          <button onClick={()=>save({})}>Сохранить данные профиля</button>
          <span style={{marginLeft:8, fontSize:12, opacity:0.8}}>
            (смена пароля/сессий/аватара выполняется в Keycloak Account Console)
          </span>
        </div>
      </div>

      <hr style={{margin:'16px 0'}}/>

      <h3>Проект</h3>
      {isTeacher ? (
        <div>
          Вы — преподаватель. Перейдите к <a href="#/rating">рейтингу команд</a> или откройте любую карточку проекта из списка проектов.
        </div>
      ) : (
        <StudentProjectHints isLead={isLead}/>
      )}
    </div>
  )
}

function StudentProjectHints({ isLead }) {
  return (
    <div style={{display:'grid', gap:8}}>
      {isLead ? (
        <>
          <div>Режим: <b>Team Lead</b>.</div>
          <div>
            Если проект ещё не создан — <a href="#/project">создайте карточку проекта</a>.
            Если уже создан — откройте его карточку с детальной информацией.
          </div>
        </>
      ) : (
        <>
          <div>Режим: <b>Участник</b>.</div>
          <div>
            Если вы уже в команде — на главной появится ваш проект. Если нет — «Не участвует в проектах».
            Обращайтесь к своему lead для присоединения.
          </div>
        </>
      )}
    </div>
  )
}

