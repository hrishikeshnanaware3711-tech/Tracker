const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || data.message || 'Something went wrong')
  return data
}

export function sendOtp(phone) {
  return request('/auth/send-otp', { method: 'POST', body: JSON.stringify({ phone }) })
}

export function verifyOtp(phone, code, name) {
  return request('/auth/verify-otp', {
    method: 'POST',
    body: JSON.stringify({ phone, code, name: name || null }),
  })
}

export function getEntries(token) {
  return request('/entries', { headers: { Authorization: `Bearer ${token}` } })
}

export function createEntry(token, entry) {
  return request('/entries', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(entry),
  })
}

export function updateEntry(token, id, entry) {
  return request(`/entries/${id}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(entry),
  })
}
