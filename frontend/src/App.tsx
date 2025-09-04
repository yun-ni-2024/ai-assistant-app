import { useEffect, useState } from 'react'

export function App() {
  const [health, setHealth] = useState<string>('Loading...')

  useEffect(() => {
    // Proxy will route /api to backend http://127.0.0.1:8000
    fetch('/api/healthz')
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setHealth(`Status: ${data.status}, Version: ${data.version}`)
      })
      .catch((err) => setHealth(`Error: ${err.message}`))
  }, [])

  return (
    <div style={{
      maxWidth: 720,
      margin: '40px auto',
      padding: '24px',
      fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif'
    }}>
      <h1>AI Assistant</h1>
      <p>Backend health: {health}</p>
    </div>
  )
}


