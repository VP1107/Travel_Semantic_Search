import { useState, useCallback } from 'react'
import { PackageCard, HotelCard, ItineraryCard, VisaCard } from '../components/ResultCards.jsx'

const EXAMPLE_QUERIES = [
  'romantic beach honeymoon Goa',
  'family trip Kerala backwaters',
  'Himalaya trekking adventure',
  'Singapore visa requirements',
  'luxury resort spa Dubai',
  'ancient temples spiritual India',
]

const MODES = [
  { id: 'hybrid',   label: 'Hybrid',   icon: '⚡', dotClass: 'hybrid',   endpoint: '/api/search/hybrid'   },
  { id: 'semantic', label: 'Semantic',  icon: '🧠', dotClass: 'semantic', endpoint: '/api/search/semantic' },
  { id: 'keyword',  label: 'Keyword',   icon: '🔤', dotClass: 'keyword',  endpoint: '/api/search'          },
]

export default function SearchPage() {
  const [query, setQuery]     = useState('')
  const [mode, setMode]       = useState('hybrid')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [elapsed, setElapsed] = useState(null)

  const activeMode = MODES.find(m => m.id === mode)

  const doSearch = useCallback(async (q = query) => {
    if (!q.trim()) return
    setLoading(true)
    setError(null)
    const t0 = Date.now()
    try {
      const url = `${activeMode.endpoint}?q=${encodeURIComponent(q.trim())}&n=12`
      const res = await fetch(url)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Server error ${res.status}`)
      }
      const data = await res.json()
      setResults({ ...data, _mode: mode })
      setElapsed(((Date.now() - t0) / 1000).toFixed(2))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [query, activeMode, mode])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') doSearch()
  }

  const handleExample = (q) => {
    setQuery(q)
    doSearch(q)
  }

  const total = results
    ? (results.packages?.length ?? 0) + (results.hotels?.length ?? 0)
        + (results.itineraries?.length ?? 0) + (results.visa?.length ?? 0)
    : 0

  return (
    <>
      {/* Hero + Search */}
      <section className="hero">
        <div className="hero-badge">✦ AI-Powered Travel Search</div>
        <h1>Find Your Perfect<br />Travel Experience</h1>
        <p>Search 2,000+ packages, hotels, and destinations using natural language</p>

        <div className="search-container">
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              id="search-input"
              className="search-input"
              type="text"
              placeholder={`Search travel packages, hotels, destinations…`}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
            />
            <button
              id="search-btn"
              className="search-btn"
              onClick={() => doSearch()}
              disabled={loading || !query.trim()}
            >
              {loading ? '…' : 'Search'}
            </button>
          </div>

          {/* Mode toggle */}
          <div className="mode-toggle">
            {MODES.map(m => (
              <button
                key={m.id}
                id={`mode-${m.id}`}
                className={`mode-btn ${mode === m.id ? 'active' : ''}`}
                onClick={() => setMode(m.id)}
              >
                <span className={`mode-dot ${m.dotClass}`} />
                {m.icon} {m.label}
              </button>
            ))}
          </div>

          {/* Example queries */}
          {!results && !loading && (
            <div className="example-queries">
              {EXAMPLE_QUERIES.map((q, i) => (
                <button key={i} className="example-chip" onClick={() => handleExample(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Results */}
      <div className="results-area">
        {loading && (
          <div className="loading-dots">
            <div className="loading-dot" />
            <div className="loading-dot" />
            <div className="loading-dot" />
          </div>
        )}

        {error && (
          <div className="empty-state">
            <div className="empty-state-icon">⚠️</div>
            <h3>Search Error</h3>
            <p>{error}</p>
          </div>
        )}

        {results && !loading && (
          <>
            <div className="results-stats">
              <span className="results-count">{total} results</span>
              <span>for "{results.query}"</span>
              <span className={`badge badge-${results._mode}`}>
                {results._mode}
              </span>
              {elapsed && <span>{elapsed}s</span>}
            </div>

            {total === 0 && (
              <div className="empty-state">
                <div className="empty-state-icon">🔭</div>
                <h3>No results found</h3>
                <p>Try different keywords or switch to Semantic / Hybrid mode</p>
              </div>
            )}

            {results.packages?.length > 0 && (
              <>
                <div className="section-header">🧳 Packages ({results.packages.length})</div>
                <div className="cards-grid">
                  {results.packages.map((p, i) => (
                    <PackageCard key={p.hash_id ?? i} pkg={p} searchType={results._mode} />
                  ))}
                </div>
              </>
            )}

            {results.hotels?.length > 0 && (
              <>
                <div className="section-header">🏨 Hotels ({results.hotels.length})</div>
                <div className="cards-grid">
                  {results.hotels.map((h, i) => (
                    <HotelCard key={h.hotel_id ?? i} hotel={h} searchType={results._mode} />
                  ))}
                </div>
              </>
            )}

            {results.itineraries?.length > 0 && (
              <>
                <div className="section-header">🗺️ Itineraries ({results.itineraries.length})</div>
                <div className="cards-grid">
                  {results.itineraries.map((it, i) => (
                    <ItineraryCard key={it.itinerary_id ?? i} item={it} searchType={results._mode} />
                  ))}
                </div>
              </>
            )}

            {results.visa?.length > 0 && (
              <>
                <div className="section-header">🛂 Visa Info ({results.visa.length})</div>
                <div className="cards-grid">
                  {results.visa.map((v, i) => (
                    <VisaCard key={v.visa_id ?? i} visa={v} searchType={results._mode} />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </>
  )
}
