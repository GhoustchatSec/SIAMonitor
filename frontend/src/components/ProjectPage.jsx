import React, { useEffect, useState } from 'react'
import { currentRoute, navigate } from '../router'
import { apiGet, apiPost, apiUpload } from '../api'
import { kcHasRole, kcProfile } from '../auth/keycloak'

export default function ProjectPage() {
  const { params } = currentRoute()
  const projectId = params.id ? Number(params.id) : null
  const isTeacher = kcHasRole('teacher')
  const meSub = kcProfile()?.sub

  const [project, setProject] = useState(null)
  const [members, setMembers] = useState([])
  const [milestones, setMilestones] = useState([])
  const [state, setState] = useState([]) 
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  // формы
  const [form, setForm] = useState({ name:'', description:'', repo_url:'', tracker_url:'', mobile_repo_url:'' })
  const [memSub, setMemSub] = useState(''); const [memRole, setMemRole] = useState('')

  const isLeadHere = project && project.lead_sub === meSub

  const loadExisting = async () => {
    setLoading(true); setErr('')
    try {
      const [p, m, ms, st] = await Promise.all([
        (projectId ? apiGet(`/api/projects/${projectId}`) : Promise.resolve(null)),
        projectId ? apiGet(`/api/projects/${projectId}/members`) : Promise.resolve([]),
        apiGet(`/api/milestones`),
        projectId ? apiGet(`/api/projects/${projectId}/milestones/with-state`) : Promise.resolve([]),
      ])
      if (projectId && !p) throw new Error('Project not found or no access')
      setProject(p); setMembers(m); setMilestones(ms); setState(st)
    } catch(e) { setErr(e.message || 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { loadExisting() }, [projectId])

  const createProject = async (e) => {
    e.preventDefault()
    try {
      const p = await apiPost('/api/projects', form)
      navigate(`/project?id=${p.id}`)
    } catch (e) { alert(e.message) }
  }

  const addMember = async (e) => {
    e.preventDefault()
    try {
      await apiPost(`/api/projects/${projectId}/members`, { member_sub: memSub, role_in_team: memRole })
      setMemSub(''); setMemRole(''); loadExisting()
    } catch (e) { alert(e.message) }
  }

  const uploadFiles = async (milestoneId, presFile, repFile) => {
    const fd = new FormData()
    if (presFile) fd.append('presentation', presFile)
    if (repFile) fd.append('report', repFile)
    await apiUpload(`/api/projects/${projectId}/milestones/${milestoneId}/files`, fd)
    await loadExisting()
  }

  const setGrade = async (milestoneId, grade) => {
    await apiPost(`/api/projects/${projectId}/milestones/${milestoneId}/grade`, { grade: Number(grade) })
    await loadExisting()
  }

  if (loading) return <div>Загрузка…</div>
  if (err) return <div style={{color:'red'}}>{String(err)}</div>

  
  if (!projectId) {
    return (
      <div>
        <button onClick={()=>navigate('/')}>&larr; Назад</button>
        <h2>Создать проект (для Team Lead)</h2>
        <form onSubmit={createProject} style={{display:'grid', gap:8, maxWidth:600}}>
          <input placeholder="Название" required value={form.name} onChange={e=>setForm({...form, name:e.target.value})}/>
          <textarea placeholder="Описание (≤3000)" value={form.description} onChange={e=>setForm({...form, description:e.target.value})} maxLength={3000}/>
          <input placeholder="Ссылка на Git (основной)" value={form.repo_url} onChange={e=>setForm({...form, repo_url:e.target.value})}/>
          <input placeholder="Ссылка на баг-трекер" value={form.tracker_url} onChange={e=>setForm({...form, tracker_url:e.target.value})}/>
          <input placeholder="Ссылка на Git мобильного приложения (обязателен при 5 участниках)" value={form.mobile_repo_url} onChange={e=>setForm({...form, mobile_repo_url:e.target.value})}/>
          <button type="submit">Создать</button>
        </form>
      </div>
    )
  }

  // Есть id — карточка проекта
  const teamCount = members.length
  return (
    <div>
      <button onClick={()=>navigate('/')}>&larr; Назад</button>
      <h2>{project?.name || `Проект #${projectId}`}</h2>
      <div style={{opacity:0.85}}>
        {project?.description || 'Без описания'}
      </div>
      <div style={{marginTop:8}}>
        {project?.repo_url && <>Git: <a href={project.repo_url} target="_blank" rel="noreferrer">{project.repo_url}</a><br/></>}
        {project?.tracker_url && <>Баг-трекер: <a href={project.tracker_url} target="_blank" rel="noreferrer">{project.tracker_url}</a><br/></>}
        {project?.mobile_repo_url && <>Git (мобильное): <a href={project.mobile_repo_url} target="_blank" rel="noreferrer">{project.mobile_repo_url}</a></>}
      </div>

      <h3 style={{marginTop:16}}>Участники ({teamCount}/5)</h3>
      <ul>
        {members.map(m => <li key={m.id}>{m.member_sub}{m.role_in_team ? ` (${m.role_in_team})` : ''}</li>)}
      </ul>
      {isLeadHere && (
        <form onSubmit={addMember} style={{display:'flex', gap:6, flexWrap:'wrap'}}>
          <input placeholder="student sub" required value={memSub} onChange={e=>setMemSub(e.target.value)}/>
          <input placeholder="роль" value={memRole} onChange={e=>setMemRole(e.target.value)}/>
          <button type="submit">Добавить участника</button>
          <div style={{fontSize:12, opacity:0.75}}>При 5 участниках «Git мобильного» обязателен</div>
        </form>
      )}

      <h3 style={{marginTop:16}}>Майлстоуны</h3>
      {!milestones.length ? <div>Пока нет опубликованных майлстоунов (их публикует преподаватель).</div> : (
        <table style={{borderCollapse:'collapse', width:'100%'}}>
          <thead>
            <tr>
              <th style={th}>Название</th>
              <th style={th}>Дедлайн</th>
              <th style={th}>Оценка (0..5)</th>
              <th style={th}>Файлы</th>
              {isTeacher && <th style={th}>Действия (teacher)</th>}
              <th style={th}>Загрузить (участники/teacher)</th>
            </tr>
          </thead>
          <tbody>
            {milestones.map(ms => {
              const st = state.find(s => s.milestone_id === ms.id) || {}
              return (
                <tr key={ms.id}>
                  <td style={td}>{ms.title}</td>
                  <td style={td}>{ms.deadline || '—'}</td>
                  <td style={td} title="оценка выставляется преподавателем">{st.grade ?? '—'}</td>
                  <td style={td}>
                    {st.presentation_path ? <div><a href="#" onClick={(e)=>e.preventDefault()}>Презентация</a></div> : <div>—</div>}
                    {st.report_path ? <div><a href="#" onClick={(e)=>e.preventDefault()}>Отчёт</a></div> : <div>—</div>}
                  </td>
                  {isTeacher && (
                    <td style={td}>
                      <GradeSetter milestoneId={ms.id} onSet={(g)=>setGrade(ms.id, g)}/>
                      {/* Кнопку "получить предложение по оценке" добавим (GitHub API) */}
                    </td>
                  )}
                  <td style={td}>
                    <FileUploader onUpload={(pres, rep)=>uploadFiles(ms.id, pres, rep)} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

const th = {borderBottom:'1px solid #ddd', textAlign:'left', padding:'6px 8px'}
const td = {borderBottom:'1px solid #eee', padding:'6px 8px'}

function FileUploader({ onUpload }) {
  const [p, setP] = useState(null)
  const [r, setR] = useState(null)
  return (
    <div style={{display:'flex', gap:6}}>
      <input type="file" onChange={e=>setP(e.target.files?.[0]||null)} title="Презентация"/>
      <input type="file" onChange={e=>setR(e.target.files?.[0]||null)} title="Отчёт"/>
      <button onClick={()=>onUpload(p, r)}>Загрузить</button>
    </div>
  )
}

function GradeSetter({ milestoneId, onSet }) {
  const [g, setG] = useState('')
  return (
    <div style={{display:'flex', gap:6}}>
      <input type="number" min="0" max="5" step="1" placeholder="0..5" value={g} onChange={e=>setG(e.target.value)} style={{width:64}}/>
      <button onClick={()=>g!=='' && onSet(g)}>Поставить</button>
    </div>
  )
}

