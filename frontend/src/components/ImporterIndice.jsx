// @ts-check
import { useEffect, useState } from 'react'
import Modale from './Modale'
import { api } from '../lib/api'

/** Ajoute d'un coup tout ou partie des composants d'un indice (CAC 40, S&P 500…). */
export default function ImporterIndice({ onFermer }) {
  const [univers, setUnivers] = useState([])
  const [cle, setCle] = useState('cac40')
  const [membres, setMembres] = useState(null)
  const [choisis, setChoisis] = useState(new Set())
  const [liste, setListe] = useState('')
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  useEffect(() => { api.univers.list().then(setUnivers).catch(e => setErreur(e.message)) }, [])
  useEffect(() => {
    setMembres(null); setErreur(null)
    api.univers.composition(cle).then(m => {
      setMembres(m); setChoisis(new Set(m.filter(x => !x.valeur_id).map(x => x.symbole)))
      setListe(univers.find(u => u.cle === cle)?.nom ?? '')
    }).catch(e => setErreur(e.message))
  }, [cle, univers])

  const basculer = s => { const n = new Set(choisis); n.has(s) ? n.delete(s) : n.add(s); setChoisis(n) }
  const importer = async () => {
    setOccupe(true)
    try { onFermer((await api.univers.importer(cle, [...choisis, ...membres.filter(m => m.valeur_id).map(m => m.symbole)], liste || null)).message) }
    catch (e) { setErreur(e.message); setOccupe(false) }
  }

  return (
    <Modale titre="Importer les valeurs d'un indice" large onFermer={() => onFermer()}
            pied={<><button className="btn" onClick={() => onFermer()}>Annuler</button>
              <button className="btn btn-primaire" onClick={importer} disabled={occupe || !membres}>Ajouter {choisis.size} valeur(s)</button></>}>
      <div className="rangee">
        <div className="segments">{univers.map(u => <button key={u.cle} className={`segment${cle === u.cle ? ' actif' : ''}`} onClick={() => setCle(u.cle)}>{u.nom}</button>)}</div>
        <span className="espaceur" />
        <label className="interrupteur">Ranger dans la liste <input className="champ" style={{ width: 160 }} value={liste} onChange={e => setListe(e.target.value)} /></label>
      </div>
      <div className="discret">
        Composition actuelle (Wikipédia). Les données de chaque valeur se téléchargent ensuite en arrière-plan : comptez quelques
        secondes par valeur (environ 25 minutes pour les 500 valeurs du S&P 500). Les sociétés américaines utilisent les comptes SEC
        (e-mail de contact à renseigner dans les Réglages).
      </div>
      {erreur && <div className="erreur">{erreur}</div>}
      {!membres ? <div className="chargement">Chargement…</div> : (
        <>
          <div className="rangee">
            <button className="btn btn-mini" onClick={() => setChoisis(new Set(membres.filter(m => !m.valeur_id).map(m => m.symbole)))}>Tout cocher</button>
            <button className="btn btn-mini" onClick={() => setChoisis(new Set())}>Tout décocher</button>
          </div>
          <div className="grille-membres">
            {membres.map(m => (
              <label key={m.symbole} className="choix" style={{ opacity: m.valeur_id ? 0.5 : 1 }}>
                <input type="checkbox" disabled={!!m.valeur_id} checked={!!m.valeur_id || choisis.has(m.symbole)} onChange={() => basculer(m.symbole)} />
                <span><b>{m.nom}</b> <span className="valeur-symbole">{m.symbole}</span>{m.valeur_id && <span className="discret"> · déjà suivie</span>}</span>
              </label>
            ))}
          </div>
        </>
      )}
    </Modale>
  )
}
