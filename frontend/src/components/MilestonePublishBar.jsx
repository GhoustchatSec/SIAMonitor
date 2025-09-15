import React, { useState } from 'react'
import { apiPost } from '../api'
import { kcHasRole } from '../auth/keycloak'

export default function MilestonePublishBar({ onPublished }) {
  const isTeacher = kcHasRole('teacher')
  const [title, setTitle] = useState('')
  const [deadline, setDeadline] = useState('') // YYYY-MM-DD
  const [busy, setBusy] = useState(false)

  if (!isTeacher) return null

  const submit = async (e) => {
    e.preventDefault()
    if (!title.trim()) return alert('Укажите название майлстоуна')
    setBusy(true)
    try {
      await apiPost('/api/milestones', {
        title: title.trim(),
        deadline: deadline || null
      })
      setTitle(''); setDeadline('')
      onPublished?.()
      alert('Майлстоун опубликован')
    } catch (e) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} style={{
      display:'flex', gap:8, alignItems:'center',
      padding:'8px', border:'1px solid #ddd', borderRadius:8, marginTop:8
    }}>
      <input
        placeholder="Название майлстоуна"
        value={title}
        onChange={e=>setTitle(e.target.value)}
        required
      />
      <input
        placeholder="Дедлайн (YYYY-MM-DD)"
        value={deadline}
        onChange={e=>setDeadline(e.target.value)}
        pattern="\d{4}-\d{2}-\d{2}"
        title="Формат YYYY-MM-DD"
      />
      <button type="submit" disabled={busy}>
        {busy ? 'Публикую…' : 'Опубликовать'}
      </button>
    </form>
  )
}

