import React, { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'
import { kcHasRole } from '../auth/keycloak'
import { navigate } from '../router'

export default function Profile() {
  const isTeacher = kcHasRole('teacher')
  const isStudent = kcHasRole('student')

  const [me, setMe] = useState(null)
  const [saving, setSaving] = useState(false)
  const [mode, setMode] = useState('participant')

  useEffect(() => {
    apiGet('/api/profile').then(d => {
      setMe(d)
      if (d?.mode) setMode(d.mode)
    })
  }, [])

  if (!me) return <div>Загрузка…</div>

  const save = async (patch) => {
    setSaving(true)
    try {
      const body = { ...patch }
      // учителю запрещено менять mode и group_no — подстраховка
      if (isTeacher) {
        delete body.mode
        delete body.group_no
      }
      const res = await apiPost('/api/profile', body)
      setMe(res)
      if (res?.mode) setMode(res.mode)
    } catch (e) {
      alert('Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  // простые стили: ровная сетка и кнопки в линию
  const wrap = {
    maxWidth: 720,
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
    alignItems: 'center'
  }
  const full = { gridColumn: '1 / -1' }
  const label = { display: 'flex', flexDirection: 'column', gap: 6 }
  const input = { padding: '10px 12px', border: '1px solid #ddd', borderRadius: 8 }
  const h2 = { gridColumn: '1 / -1', margin: '0 0 8px 0' }
  const hint = { gridColumn: '1 / -1', marginTop: 8, fontSize: 13, opacity: 0.8 }

  return (
    <div>
      <h2 style={h2}>Личный кабинет</h2>

      <div style={wrap}>
        <div style={label}>
          <span>ФИО</span>
          <input style={input} value={me.full_name || ''} readOnly />
        </div>

        <div style={label}>
          <span>Email</span>
          <input style={input} value={me.email || ''} readOnly />
        </div>

        {isStudent && (
          <>
            <div style={label}>
              <span>Режим аккаунта</span>
              <select
                style={{ ...input, appearance: 'auto' }}
                value={mode}
                onChange={e => setMode(e.target.value)}
                onBlur={() => save({ mode })}
                onKeyDown={e => { if (e.key === 'Enter') save({ mode }) }}
              >
                <option value="participant">participant</option>
                <option value="lead">lead</option>
              </select>
            </div>

            <div style={label}>
              <span>Номер группы</span>
              <input
                style={input}
                value={me.group_no || ''}
                onChange={e => setMe({ ...me, group_no: e.target.value })}
                onBlur={() => save({ group_no: me.group_no || '' })}
                onKeyDown={e => { if (e.key === 'Enter') save({ group_no: me.group_no || '' }) }}
              />
            </div>
          </>
        )}

        <div style={{ ...label, ...full }}>
          <span>Telegram</span>
          <input
            style={input}
            placeholder="@username"
            value={me.tg || ''}
            onChange={e => setMe({ ...me, tg: e.target.value })}
            onBlur={() => save({ tg: me.tg || '' })}
            onKeyDown={e => { if (e.key === 'Enter') save({ tg: me.tg || '' }) }}
          />
        </div>

        <div style={hint}>
          Ваш UUID: <code>{me.sub}</code>
        </div>
      </div>
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

