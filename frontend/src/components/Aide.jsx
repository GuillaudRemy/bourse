import { useState } from 'react'
import { GLOSSAIRE } from '../lib/glossaire'

/** Petit « ? » : survol ou clic affiche la definition du terme. */
export default function Aide({ terme }) {
  const [ouvert, setOuvert] = useState(false)
  const entree = GLOSSAIRE[terme]
  if (!entree) return null
  return (
    <span className="aide" onMouseEnter={() => setOuvert(true)} onMouseLeave={() => setOuvert(false)}
          onClick={e => { e.stopPropagation(); setOuvert(o => !o) }} role="button" tabIndex={0} aria-label={`Définition : ${entree[0]}`}>
      ?
      {ouvert && <span className="aide-bulle" role="tooltip"><b>{entree[0]}</b><br />{entree[1]}</span>}
    </span>
  )
}
