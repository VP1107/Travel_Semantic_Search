import { useState } from 'react'
import SearchPage from './pages/SearchPage.jsx'
import ChatPage from './pages/ChatPage.jsx'

export default function App() {
  const [page, setPage] = useState('search')

  return (
    <div className="app">
      {/* Navigation */}
      <nav className="navbar">
        <div className="navbar-inner">
          <a className="navbar-brand" href="#" onClick={() => setPage('search')}>
            <div className="navbar-logo">✈</div>
            <span className="navbar-title">TravelSearch AI</span>
          </a>
          <div className="navbar-nav">
            <button
              id="nav-search"
              className={`nav-btn ${page === 'search' ? 'active' : ''}`}
              onClick={() => setPage('search')}
            >
              🔍 Search
            </button>
            <button
              id="nav-chat"
              className={`nav-btn ${page === 'chat' ? 'active' : ''}`}
              onClick={() => setPage('chat')}
            >
              ✨ AI Assistant
            </button>
          </div>
        </div>
      </nav>

      {/* Pages */}
      {page === 'search' ? <SearchPage /> : <ChatPage />}
    </div>
  )
}
