/* Result card components for packages, hotels, itineraries, and visa */

/* ── Package Card ──────────────────────────────────────────── */
export function PackageCard({ pkg, searchType }) {
  const score = searchType === 'hybrid'
    ? `RRF ${pkg.rrf_score?.toFixed(4)}`
    : pkg.distance != null
      ? `dist ${pkg.distance?.toFixed(3)}`
      : null

  const source = pkg.rank_source

  return (
    <div className="card card-enter">
      <span className="card-type-icon">🧳</span>
      <div className="card-tag">✦ Package</div>
      <h3 className="card-title">{pkg.title}</h3>
      {pkg.sub_title && <p className="card-subtitle">{pkg.sub_title}</p>}
      <p className="card-desc">{pkg.short_description}</p>

      <div className="card-meta">
        {pkg.duration_days > 0 && (
          <span className="meta-chip">📅 {pkg.duration_days}D</span>
        )}
        {pkg.category && (
          <span className="meta-chip">{pkg.category}</span>
        )}
        {pkg.is_popular && (
          <span className="meta-chip" style={{ color: 'var(--color-gold)' }}>⭐ Popular</span>
        )}
        {pkg.destinations?.slice(0, 2).map((d, i) => (
          <span key={i} className="meta-chip">📍 {d.split(' > ').pop()}</span>
        ))}
        {pkg.types?.slice(0, 2).map((t, i) => (
          <span key={i} className="meta-chip">{t}</span>
        ))}
      </div>

      <div className="card-footer">
        {score && <span className="score-badge">{score}</span>}
        {source && (
          <span className={`source-badge source-${source}`}>{source}</span>
        )}
      </div>
    </div>
  )
}

/* ── Hotel Card ─────────────────────────────────────────────── */
export function HotelCard({ hotel, searchType }) {
  const score = searchType === 'hybrid'
    ? `RRF ${hotel.rrf_score?.toFixed(4)}`
    : hotel.distance != null
      ? `dist ${hotel.distance?.toFixed(3)}`
      : null

  const source = hotel.rank_source

  return (
    <div className="card card-enter">
      <span className="card-type-icon">🏨</span>
      <div className="card-tag">✦ Hotel</div>
      <h3 className="card-title">{hotel.name}</h3>
      <p className="card-subtitle">
        {hotel.city}{hotel.region && hotel.region !== hotel.city ? `, ${hotel.region}` : ''}
      </p>
      <p className="card-desc">{hotel.short_description}</p>

      <div className="card-meta">
        {hotel.rating && <span className="meta-chip">⭐ {hotel.rating}</span>}
        {hotel.facilities?.slice(0, 4).map((f, i) => (
          <span key={i} className="meta-chip">{f}</span>
        ))}
      </div>

      <div className="card-footer">
        {score && <span className="score-badge">{score}</span>}
        {source && (
          <span className={`source-badge source-${source}`}>{source}</span>
        )}
      </div>
    </div>
  )
}

/* ── Itinerary Card ─────────────────────────────────────────── */
export function ItineraryCard({ item, searchType }) {
  const score = searchType === 'hybrid'
    ? `RRF ${item.rrf_score?.toFixed(4)}`
    : item.distance != null
      ? `dist ${item.distance?.toFixed(3)}`
      : null

  const source = item.rank_source

  return (
    <div className="card card-enter">
      <span className="card-type-icon">🗺️</span>
      <div className="card-tag">✦ Itinerary</div>
      <p className="card-subtitle" style={{ marginBottom: 6 }}>
        {item.package_title} — Day {item.day}
      </p>
      <h3 className="card-title">{item.title}</h3>
      <p className="card-desc">{item.details_snippet || item.details}</p>

      <div className="card-footer">
        {score && <span className="score-badge">{score}</span>}
        {source && (
          <span className={`source-badge source-${source}`}>{source}</span>
        )}
      </div>
    </div>
  )
}

/* ── Visa Card ──────────────────────────────────────────────── */
export function VisaCard({ visa, searchType }) {
  const score = searchType === 'hybrid'
    ? `RRF ${visa.rrf_score?.toFixed(4)}`
    : visa.distance != null
      ? `dist ${visa.distance?.toFixed(3)}`
      : null

  const source = visa.rank_source

  return (
    <div className="card card-enter">
      <span className="card-type-icon">🛂</span>
      <div className="card-tag">✦ Visa</div>
      <h3 className="card-title">{visa.country}</h3>
      <p className="card-desc">{visa.requirements_snippet || visa.requirements}</p>

      <div className="card-footer">
        {score && <span className="score-badge">{score}</span>}
        {source && (
          <span className={`source-badge source-${source}`}>{source}</span>
        )}
      </div>
    </div>
  )
}
