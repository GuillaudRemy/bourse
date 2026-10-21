// @ts-check
import { useEffect } from 'react'

/**
 * @param {{ titre: React.ReactNode, onFermer: () => void, children?: React.ReactNode, pied?: React.ReactNode, large?: boolean }} props
 */
export default function Modale({ titre, onFermer, children, pied, large = false }) {
  useEffect(() => {
    const surTouche = e => { if (e.key === 'Escape') onFermer() }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [onFermer])

  return (
    <div className="modale-fond" onMouseDown={e => e.target === e.currentTarget && onFermer()}>
      <div className={`modale${large ? ' modale-large' : ''}`}>
        <div className="modale-entete">
          <div className="modale-titre">{titre}</div>
          <button className="btn btn-fantome btn-mini" onClick={onFermer}>Fermer</button>
        </div>
        <div className="modale-corps">{children}</div>
        {pied && <div className="modale-pied">{pied}</div>}
      </div>
    </div>
  )
}
