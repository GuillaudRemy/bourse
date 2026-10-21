import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { dateHeure } from '../lib/format'
import AlertesValeur from '../components/AlertesValeur'

export default function Alertes() {
  const [declenchements, setDeclenchements] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)

  const charger = useCallback(() => api.alertes.declenchements().then(setDeclenchements).catch(e => setErreur(e.message)), [])
  useEffect(() => { charger() }, [charger])

  const toutLu = async () => {
    await api.alertes.marquerLues(); await charger()
    window.dispatchEvent(new Event('alertes-lues'))
  }
  const essai = async () => {
    try {
      const r = await api.alertes.essai()
      setInfo(r.canaux.length ? `Notification envoyée : ${r.canaux.join(', ')}.` : 'Aucun canal actif : activez les notifications ou l’e-mail dans les Réglages.')
    } catch (e) { setErreur(e.message) }
  }

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Alertes</h1>
          <div className="page-sous-titre">Vérifiées à chaque actualisation ; une alerte se déclenche quand sa condition devient vraie.</div>
        </div>
        <div className="rangee">
          <button className="btn" onClick={essai}>Tester les notifications</button>
          <button className="btn" onClick={toutLu} disabled={!declenchements?.non_lus}>Tout marquer comme lu</button>
        </div>
      </div>
      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {info && <div className="succes" style={{ marginBottom: 12 }}>{info}</div>}
      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Déclenchements</div>
          {declenchements?.liste.length === 0 && <div className="vide">Aucune alerte déclenchée pour l'instant.</div>}
          {declenchements?.liste.map(d => (
            <div key={d.id} className="signal">
              <span className={`signal-point ${d.lu ? 'neutre' : 'baisse'}`} />
              <span style={{ flex: 1, fontWeight: d.lu ? 400 : 600 }}>
                {d.valeur_id ? <Link className="lien-poste" to={`/valeurs/${d.valeur_id}`}>{d.message}</Link> : d.message}
              </span>
              <span className="discret">{dateHeure(d.moment)}</span>
            </div>
          ))}
        </div>
        <AlertesValeur titre="Toutes les règles" />
      </div>
    </div>
  )
}
