// @ts-check
import { useState } from 'react'
import Modale from './Modale'
import { nombre } from '../lib/format'

const UNITES = [[1, 'unités'], [1e3, 'milliers'], [1e6, 'millions'], [1e9, 'milliards']]

/** Relecture d'une extraction PDF : l'utilisateur corrige, coche, puis valide. */
export default function RelecturePdf({ proposition, onValider, onFermer }) {
  const [multiplicateur, setMultiplicateur] = useState(proposition.multiplicateur)
  const [postes, setPostes] = useState(proposition.postes.map(p => ({ ...p, garde: true })))
  const [occupe, setOccupe] = useState(false)

  const modifier = (i, annee, texte) => {
    const v = parseFloat(String(texte).replace(/\s/g, '').replace(',', '.'))
    setPostes(postes.map((p, j) => j !== i ? p : { ...p, valeurs: { ...p.valeurs, [annee]: Number.isNaN(v) ? null : v } }))
  }

  const valider = async () => {
    const annees = {}
    for (const p of postes.filter(p => p.garde)) {
      for (const [annee, v] of Object.entries(p.valeurs)) {
        if (v === null) continue
        annees[annee] ??= {}
        annees[annee][p.cle] = p.unite === 'monnaie' ? v * multiplicateur : v
      }
    }
    setOccupe(true)
    try { await onValider(annees) } finally { setOccupe(false) }
  }

  return (
    <Modale titre="Relire l'extraction du rapport" onFermer={onFermer} large
            pied={<>
              <button className="btn" onClick={onFermer}>Annuler</button>
              <button className="btn btn-primaire" onClick={valider} disabled={occupe || !postes.some(p => p.garde)}>
                Enregistrer les postes cochés
              </button>
            </>}>
      <div className="discret" style={{ fontSize: 12.5 }}>
        Vérifiez chaque chiffre avec la page indiquée : une extraction de PDF peut se tromper de ligne ou de colonne.
        Les montants sont multipliés par l'unité choisie ; les chiffres par action ne le sont pas.
      </div>
      <label className="interrupteur">
        Montants exprimés en
        <select className="champ" style={{ width: 'auto' }} value={multiplicateur} onChange={e => setMultiplicateur(Number(e.target.value))}>
          {UNITES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      <div className="tableau-conteneur">
        <table className="tableau">
          <thead>
            <tr>
              <th />
              <th style={{ textAlign: 'left' }}>Poste reconnu</th>
              {proposition.annees.map(a => <th key={a}>{a}</th>)}
              <th>Page</th>
            </tr>
          </thead>
          <tbody>
            {postes.map((p, i) => (
              <tr key={p.cle} style={{ opacity: p.garde ? 1 : 0.45 }}>
                <td><input type="checkbox" checked={p.garde} onChange={() => setPostes(postes.map((x, j) => j === i ? { ...x, garde: !x.garde } : x))} /></td>
                <td className="texte" style={{ textAlign: 'left' }} title={`Ligne lue : « ${p.ligne} »`}>
                  <div style={{ fontWeight: 500 }}>{p.libelle}</div>
                  <div className="discret">« {p.ligne} »</div>
                </td>
                {proposition.annees.map(a => (
                  <td key={a}>
                    <input className="champ-cellule" defaultValue={p.valeurs[a] === undefined || p.valeurs[a] === null ? '' : nombre(p.valeurs[a], 2)}
                           onBlur={e => modifier(i, a, e.target.value)} />
                  </td>
                ))}
                <td>{p.page}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modale>
  )
}
