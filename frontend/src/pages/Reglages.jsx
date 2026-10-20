import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function Reglages() {
  const [reglages, setReglages] = useState(null)
  const [brouillon, setBrouillon] = useState({})
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)

  useEffect(() => {
    api.reglages.list().then(r => {
      setReglages(r)
      setBrouillon(Object.fromEntries(r.map(x => [x.cle, x.secret ? '' : x.valeur])))
    }).catch(e => setErreur(e.message))
  }, [])

  const enregistrer = async cle => {
    setErreur(null); setInfo(null)
    try { setReglages(await api.reglages.ecrire(cle, brouillon[cle])); setInfo('Réglage enregistré.') }
    catch (e) { setErreur(e.message) }
  }

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Réglages</h1>
          <div className="page-sous-titre">Sources de données et préférences</div>
        </div>
      </div>
      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {info && <div className="succes" style={{ marginBottom: 12 }}>{info}</div>}
      <div className="carte" style={{ maxWidth: 760 }}>
        {reglages === null ? <div className="chargement">Chargement…</div> : reglages.map(r => (
          <form key={r.cle} className="carte-corps pile" style={{ borderBottom: '1px solid var(--border)' }}
                onSubmit={e => { e.preventDefault(); enregistrer(r.cle) }}>
            <label className="champ-label" htmlFor={r.cle}>{r.libelle}</label>
            <div className="discret" style={{ fontSize: 12.5 }}>{r.aide}</div>
            <div className="rangee">
              <input id={r.cle} className="champ" type={r.secret ? 'password' : 'text'}
                     placeholder={r.secret && r.valeur ? 'déjà renseigné — saisir pour remplacer' : r.defaut}
                     value={brouillon[r.cle] ?? ''} onChange={e => setBrouillon({ ...brouillon, [r.cle]: e.target.value })} />
              <button className="btn btn-primaire">Enregistrer</button>
            </div>
          </form>
        ))}
      </div>
    </div>
  )
}
