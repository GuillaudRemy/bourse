// @ts-check
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { date } from '../lib/format'

const TYPES = { resultats: ['Résultats', 'statut-attention'], detachement: ['Détachement', 'statut-ok'], paiement: ['Paiement', 'statut-inconnu'] }

export default function Calendrier() {
  const [evenements, setEvenements] = useState(null)
  const [passes, setPasses] = useState(false)
  const [erreur, setErreur] = useState(null)
  useEffect(() => {
    api.calendrier({ jours_avant: passes ? 365 : 0, jours_apres: 120 }).then(setEvenements).catch(e => setErreur(e.message))
  }, [passes])

  const aujourdhui = new Date().toISOString().slice(0, 10)
  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Calendrier</h1>
          <div className="page-sous-titre">Publications de résultats et dividendes des valeurs suivies (dates fournies par Yahoo, à confirmer)</div>
        </div>
        <label className="interrupteur"><input type="checkbox" checked={passes} onChange={e => setPasses(e.target.checked)} /> Afficher l'année écoulée</label>
      </div>
      {erreur && <div className="erreur">{erreur}</div>}
      <div className="carte">
        {evenements === null ? <div className="chargement">Chargement…</div> : evenements.length === 0 ? (
          <div className="vide">Aucun événement. Les dates arrivent avec l'actualisation des valeurs.</div>
        ) : (
          <table className="tableau">
            <thead><tr><th>Date</th><th style={{ textAlign: 'left' }}>Valeur</th><th style={{ textAlign: 'left' }}>Événement</th><th style={{ textAlign: 'left' }}>Détail</th></tr></thead>
            <tbody>
              {evenements.map((e, i) => (
                <tr key={i} style={{ opacity: e.jour < aujourdhui ? 0.55 : 1 }}>
                  <td style={{ textAlign: 'left' }}>{date(e.jour)}</td>
                  <td className="texte"><Link className="lien-poste" to={`/valeurs/${e.valeur_id}`}>{e.nom}</Link> <span className="valeur-symbole">{e.symbole}</span></td>
                  <td className="texte"><span className={`badge ${TYPES[e.type]?.[1] ?? ''}`}>{TYPES[e.type]?.[0] ?? e.type}</span></td>
                  <td className="texte muet">{e.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
