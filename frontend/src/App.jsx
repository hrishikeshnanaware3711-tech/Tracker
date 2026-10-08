import { useEffect, useMemo, useState } from 'react'
import { createEntry, getEntries, sendOtp, updateEntry, verifyOtp } from './api'

function AuthPage({ onLogin }) {
  const [step, setStep] = useState('phone')
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSend(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await sendOtp(phone)
      setStep('otp')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleVerify(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await verifyOtp(phone, code, name)
      localStorage.setItem('journal_token', result.access_token)
      localStorage.setItem('journal_user', JSON.stringify(result.user))
      onLogin(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-shell">
      <section className="paper-card auth-card">
        <div className="brand-mark">DJ</div>
        <p className="eyebrow">ONE PAGE AT A TIME</p>
        <h1>Daily Journal</h1>
        <p className="muted">A tiny private space for today's thoughts.</p>

        {step === 'phone' ? (
          <form onSubmit={handleSend} className="form-stack">
            <label>Mobile number</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="9876543210" inputMode="numeric" />
            <label>Name <span>(new users)</span></label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
            <button disabled={loading}>{loading ? 'Sending…' : 'Send OTP'}</button>
            <small>OTP is delivered through MiniMoth WhatsApp/SMS.</small>
          </form>
        ) : (
          <form onSubmit={handleVerify} className="form-stack">
            <label>6-digit OTP</label>
            <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="123456" inputMode="numeric" autoFocus />
            <button disabled={loading}>{loading ? 'Checking…' : 'Open Journal'}</button>
            <button type="button" className="ghost" onClick={() => setStep('phone')}>Change number</button>
            <small>Use the same number again to log in.</small>
          </form>
        )}

        {error && <div className="error-box">{error}</div>}
      </section>
    </main>
  )
}

function JournalPage({ user, token, onLogout }) {
  const [entries, setEntries] = useState([])
  const [selected, setSelected] = useState(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [busy, setBusy] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadEntries() {
    setBusy(true)
    setError('')
    try {
      const result = await getEntries(token)
      setEntries(result.entries)
    } catch (err) {
      setError(err.message)
      if (err.message.toLowerCase().includes('token') || err.message.toLowerCase().includes('session')) onLogout()
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { loadEntries() }, [])

  function newEntry() {
    setSelected(null)
    setTitle('')
    setContent('')
    setMessage('')
  }

  function openEntry(entry) {
    setSelected(entry)
    setTitle(entry.title)
    setContent(entry.content)
    setMessage('')
  }

  async function saveEntry(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')
    try {
      if (selected) {
        const updated = await updateEntry(token, selected.id, { title, content })
        setEntries(entries.map((item) => item.id === updated.id ? updated : item))
        setSelected(updated)
        setMessage('Entry updated.')
      } else {
        const created = await createEntry(token, { title, content })
        setEntries([created, ...entries])
        setSelected(created)
        setMessage('Entry saved.')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const dateLabel = useMemo(() => new Intl.DateTimeFormat('en-IN', { dateStyle: 'full' }).format(new Date()), [])

  return (
    <main className="journal-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">DAILY JOURNAL</p>
          <h2>Hi, {user?.name || 'there'}.</h2>
        </div>
        <button className="ghost top-logout" onClick={onLogout}>Log out</button>
      </header>

      <section className="journal-grid">
        <aside className="paper-card entries-panel">
          <div className="panel-title-row">
            <div>
              <p className="eyebrow">YOUR PAGES</p>
              <h3>Journal entries</h3>
            </div>
            <button className="small-button" onClick={newEntry}>+ New</button>
          </div>
          {busy ? <p className="muted">Loading pages…</p> : entries.length === 0 ? (
            <div className="empty-state">No entries yet.<br />Write the first page.</div>
          ) : entries.map((entry) => (
            <button key={entry.id} className={`entry-item ${selected?.id === entry.id ? 'selected' : ''}`} onClick={() => openEntry(entry)}>
              <strong>{entry.title}</strong>
              <span>{entry.content.slice(0, 70)}{entry.content.length > 70 ? '…' : ''}</span>
            </button>
          ))}
        </aside>

        <section className="paper-card editor-panel notebook-paper">
          <div className="date-stamp">{dateLabel}</div>
          <form onSubmit={saveEntry} className="editor-form">
            <input className="title-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Today's headline" maxLength="80" />
            <textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="What happened today? What did you learn?" maxLength="5000" />
            <div className="editor-footer">
              <span className="muted">{content.length}/5000</span>
              <button disabled={saving || !title.trim() || !content.trim()}>{saving ? 'Saving…' : selected ? 'Update page' : 'Save page'}</button>
            </div>
          </form>
          {message && <div className="success-box">{message}</div>}
          {error && <div className="error-box">{error}</div>}
        </section>
      </section>
    </main>
  )
}

function App() {
  const [session, setSession] = useState(() => ({
    token: localStorage.getItem('journal_token'),
    user: JSON.parse(localStorage.getItem('journal_user') || 'null'),
  }))

  function logout() {
    localStorage.removeItem('journal_token')
    localStorage.removeItem('journal_user')
    setSession({ token: null, user: null })
  }

  return session.token ? (
    <JournalPage token={session.token} user={session.user} onLogout={logout} />
  ) : (
    <AuthPage onLogin={(result) => setSession({ token: result.access_token, user: result.user })} />
  )
}

export default App
