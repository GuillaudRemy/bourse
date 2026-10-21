// @ts-check
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

/** Regles d'alerte : celles d'une valeur (valeurId), ou toutes. */
/** @param {{ valeurId?: number, titre?: string }} props  (sans valeurId : toutes les regles) */
export default function AlertesValeur({ valeurId, titre = 'Alertes' }) {
  const [donnees, setDonnees] = useState(null)
  const [nouvelle, setNouvelle] = useState({ type: 'sigma_sous', seuil: '-1' })
  const [erreur, setErreur] = useState(null)

  const charger = useCallback(() => api.alertes.list(valeurId).then(setDonnees).catch(e => setErreur(e.message)), [valeurId])
  useEffect(() => { charger() }, [charger])

  const action = async fn => {
    setErreur(null)
    try { await fn(); await charger(); window.dispatchEvent(new Event('alertes-lues')) } catch (e) { setErreur(e.message) }
  }
  if (!donnees) return <div className="carte"><div className="chargement">Chargement…</div></div>
  const avecSeuil = donnees.types[nouvelle.type]?.unite !== null

  return (
    <div className="carte">
      <div className="section-titre">{titre}</div>
      {erreur && <div className="erreur" style={{ margin: 12 }}>{erreur}</div>}
      {donnees.alertes.length === 0 && <div className="carte-corps discret">Aucune règle.</div>}
      {donnees.alertes.map(a => (
        <div key={a.id} className="signal">
          <input type="checkbox" checked={a.active} title={a.active ? 'Active' : 'En pause'}
                 onChange={() => action(() => api.alertes.modifier(a.id, { ...a, active: !a.active }))} />
          <span style={{ flex: 1, opacity: a.active ? 1 : 0.5 }}>{valeurId ? '' : <b>{a.valeur} · </b>}{a.libelle}</span>
          {a.derniere && <span className="badge statut-attention" title="Condition vraie actuellement">en cours</span>}
          <button className="btn btn-mini btn-fantome" onClick={() => action(() => api.alertes.supprimer(a.id))}>×</button>
        </div>
      ))}
      {valeurId && (
        <form className="graphique-barre" style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }}
              onSubmit={e => { e.preventDefault(); action(() => api.alertes.creer({ valeur_id: valeurId, type: nouvelle.type, seuil: avecSeuil ? Number(String(nouvelle.seuil).replace(',', '.')) : null })) }}>
          <select className="champ" style={{ width: 'auto', flex: 1 }} value={nouvelle.type} onChange={e => setNouvelle({ ...nouvelle, type: e.target.value })}>
            {Object.entries(donnees.types).map(([cle, t]) => <option key={cle} value={cle}>{t.libelle}{t.unite ? ` … ${t.unite}` : ''}</option>)}
          </select>
          {avecSeuil && <input className="champ champ-mono" style={{ width: 90 }} value={nouvelle.seuil} onChange={e => setNouvelle({ ...nouvelle, seuil: e.target.value })} />}
          <button className="btn">Ajouter</button>
        </form>
      )}
    </div>
  )
}
