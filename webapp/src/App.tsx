import { BrowserRouter } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: '#0f0f1a', color: '#fff', fontFamily: 'system-ui',
        flexDirection: 'column', gap: '1rem',
      }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700 }}>Research Platform</h1>
        <p style={{ color: '#888' }}>research.thalors.ai — Coming soon</p>
        <p style={{ color: '#555', fontSize: '0.875rem' }}>Backend API ready at /api/research/jobs</p>
      </div>
    </BrowserRouter>
  )
}

export default App
