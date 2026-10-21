// @ts-check
/** Petit graphique en barres (une barre par annee), barres negatives vers le bas. */
export default function Barres({ points, format, hauteur = 120 }) {
  const valeurs = points.map(p => p.y).filter(v => v !== null && v !== undefined)
  if (!valeurs.length) return <div className="discret">Aucune donnée pour ce poste.</div>
  const max = Math.max(0, ...valeurs), min = Math.min(0, ...valeurs)
  const etendue = max - min || 1
  const zero = (max / etendue) * hauteur

  return (
    <div className="barres" style={{ height: hauteur + 34 }}>
      {points.map(({ x, y }) => {
        const present = y !== null && y !== undefined
        const h = present ? Math.max(1, (Math.abs(y) / etendue) * hauteur) : 0
        return (
          <div key={x} className="barres-colonne" title={present ? `${x} : ${format(y)}` : `${x} : —`}>
            <div className="barres-zone" style={{ height: hauteur }}>
              {present && (
                <div className={`barres-barre${y < 0 ? ' negative' : ''}`}
                     style={y >= 0 ? { bottom: hauteur - zero, height: h } : { top: zero, height: h }} />
              )}
            </div>
            <div className="barres-x">{String(x).slice(2)}</div>
          </div>
        )
      })}
    </div>
  )
}
