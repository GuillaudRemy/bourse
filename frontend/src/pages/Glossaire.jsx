// @ts-check
import { useState } from 'react'
import { GLOSSAIRE } from '../lib/glossaire'

const sansAccents = t => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

export default function Glossaire() {
  const [filtre, setFiltre] = useState('')
  const entrees = Object.values(GLOSSAIRE)
    .filter(([terme, def]) => !filtre || sansAccents(`${terme} ${def}`).includes(sansAccents(filtre)))
    .sort((a, b) => a[0].localeCompare(b[0], 'fr'))
  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Glossaire</h1>
          <div className="page-sous-titre">Les termes de l'application, en quelques lignes ({Object.keys(GLOSSAIRE).length} définitions)</div>
        </div>
        <input className="champ" style={{ width: 260 }} placeholder="Chercher un terme…" value={filtre} onChange={e => setFiltre(e.target.value)} autoFocus />
      </div>
      <div className="carte" style={{ maxWidth: 900 }}>
        {entrees.map(([terme, def]) => (
          <div key={terme} className="verif"><div><div className="verif-titre">{terme}</div><div className="verif-texte" style={{ fontSize: 13.5 }}>{def}</div></div></div>
        ))}
      </div>
    </div>
  )
}
