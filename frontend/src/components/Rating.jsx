import React, { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'
import { navigate } from '../router'
import { kcHasRole } from '../auth/keycloak'

export default function Rating() {
  const isTeacher = kcHasRole('teacher')

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setErr(null)
    apiGet('/api/rating')
      .then((data) => {
        if (!mounted) return
        // Ожидаем: [{ project_id, project_name, team_size, avg_grade, grades: [] }]
        if (!Array.isArray(data)) throw new Error('Некорректный ответ сервера')
        setRows(data)
      })
      .catch((e) => {
        if (!mounted) return
        setErr(e?.message || 'Не удалось загрузить рейтинг')
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })
    return () => { mounted = false }
  }, [])

  const wipeAll = async () => {
    if (!isTeacher) return
    const first = window.confirm(
      'ВНИМАНИЕ! Это удалит ВСЕ данные (проекты, майлстоуны, оценки, файлы, профили студентов). Продолжить?'
    )
    if (!first) return
    const text = window.prompt('Для подтверждения введите: УДАЛИТЬ ВСЁ')
    if (text !== 'УДАЛИТЬ ВСЁ') return

    try {
      await apiPost('/api/admin/wipe', {})
      alert('Очистка выполнена. Страница будет перезагружена.')
      window.location.reload()
    } catch (e) {
      alert('Ошибка очистки: ' + (e?.message || 'unknown'))
    }
  }

  return (
    <div>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
        <h2 style={{margin:0}}>Рейтинг команд</h2>
        {isTeacher && (
          <button
            onClick={wipeAll}
            title="Удалить все данные, кроме преподавателей"
            style={{background:'#b00020', color:'#fff', border:'none', padding:'8px 12px', borderRadius:8, cursor:'pointer'}}
          >
            Очистить данные
          </button>
        )}
      </div>

      {loading && <div>Загрузка…</div>}
      {!loading && err && <div style={{color:'red'}}>Ошибка: {err}</div>}

      {!loading && !err && (
        <table border="0" cellPadding="8" style={{borderCollapse:'collapse', width:'100%'}}>
          <thead>
            <tr style={{textAlign:'left', borderBottom:'1px solid #eee'}}>
              <th>ID</th>
              <th>Команда</th>
              <th>Человек</th>
              <th>Оценки (по майлстоунам)</th>
              <th>Средняя</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((r) => (
              <tr key={r.project_id} style={{borderBottom:'1px solid #f2f2f2'}}>
                <td>{r.project_id}</td>
                <td>{r.project_name}</td>
                <td>{r.team_size}</td>
                <td>{Array.isArray(r.grades) && r.grades.length ? r.grades.join(', ') : '—'}</td>
                <td>{typeof r.avg_grade === 'number' ? r.avg_grade.toFixed(2) : '—'}</td>
                <td style={td}><a href={`#/project?id=${r.project_id}`}>Открыть</a></td>
              </tr>
            )) : (
              <tr><td colSpan={5} style={{opacity:0.7}}>Нет данных</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}

const th = {borderBottom:'1px solid #ddd', textAlign:'left', padding:'6px 8px'}
const td = {borderBottom:'1px solid #eee', padding:'6px 8px'}

