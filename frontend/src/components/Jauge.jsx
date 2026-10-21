// @ts-check
import { ZONES } from '../lib/zones'

const BORNE = 3   // la jauge va de -3σ a +3σ

/** Position du cours dans son couloir de regression. */
export default function Jauge({ position, grande = false }) {
  if (position === null || position === undefined) return <span className="muet">—</span>
  const gauche = ((Math.max(-BORNE, Math.min(BORNE, position)) + BORNE) / (2 * BORNE)) * 100
  return (
    <div>
      <span className={`jauge${grande ? ' grande' : ''}`} title={`${position.toFixed(2)} écart-type`}>
        <span className="jauge-curseur" style={{ left: `${gauche}%` }} />
      </span>
      {grande && (
        <div className="jauge-graduations">
          <span>−3σ</span><span>−2σ</span><span>−1σ</span><span>0</span><span>+1σ</span><span>+2σ</span><span>+3σ</span>
        </div>
      )}
    </div>
  )
}

export function BadgeZone({ zone }) {
  const z = ZONES[zone]
  if (!z) return <span className="muet">—</span>
  return <span className={`badge ${z.classe}`}>{z.libelle}</span>
}
