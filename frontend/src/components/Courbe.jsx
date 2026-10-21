import { pct } from '../lib/format'

/** Petite courbe SVG : x = annees, y = valeurs (en %), avec la ligne de reference `ref`. */
export default function Courbe({ points, format = v => pct(v), ref: reference, hauteur = 140, couleur = 'var(--accent)' }) {
  const valides = points.filter(p => p.y !== null && p.y !== undefined)
  if (valides.length < 2) return <div className="discret">Pas assez d'historique.</div>
  const L = 600, H = hauteur, marge = { g: 46, d: 10, h: 10, b: 22 }
  const xs = valides.map(p => p.x), ys = valides.map(p => p.y)
  if (reference !== undefined) ys.push(reference)
  const xmin = Math.min(...xs), xmax = Math.max(...xs)
  let ymin = Math.min(...ys), ymax = Math.max(...ys)
  const pad = (ymax - ymin) * 0.12 || 0.01
  ymin -= pad; ymax += pad
  const X = x => marge.g + ((x - xmin) / (xmax - xmin || 1)) * (L - marge.g - marge.d)
  const Y = y => marge.h + (1 - (y - ymin) / (ymax - ymin)) * (H - marge.h - marge.b)
  const chemin = valides.map((p, i) => `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(' ')
  const graduations = [ymin + pad, (ymin + ymax) / 2, ymax - pad]
  const pas = Math.max(1, Math.ceil(valides.length / 8))

  return (
    <svg viewBox={`0 0 ${L} ${H}`} style={{ width: '100%', height: 'auto' }} role="img">
      {graduations.map((g, i) => (
        <g key={i}>
          <line x1={marge.g} x2={L - marge.d} y1={Y(g)} y2={Y(g)} stroke="var(--border)" strokeWidth="1" />
          <text x={marge.g - 6} y={Y(g) + 4} textAnchor="end" fontSize="10" fill="var(--faint)" fontFamily="var(--f-mono)">{format(g)}</text>
        </g>
      ))}
      {reference !== undefined && (
        <line x1={marge.g} x2={L - marge.d} y1={Y(reference)} y2={Y(reference)} stroke="var(--c-droite)" strokeDasharray="4 3" strokeWidth="1.2" />
      )}
      <path d={chemin} fill="none" stroke={couleur} strokeWidth="2" />
      {valides.map((p, i) => (
        <g key={p.x}>
          <circle cx={X(p.x)} cy={Y(p.y)} r="2.6" fill={couleur}><title>{`${p.x} : ${format(p.y)}`}</title></circle>
          {i % pas === 0 && <text x={X(p.x)} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--faint)" fontFamily="var(--f-mono)">{p.x}</text>}
        </g>
      ))}
    </svg>
  )
}
