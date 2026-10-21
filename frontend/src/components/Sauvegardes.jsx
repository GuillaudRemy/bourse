// @ts-check
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const taille = o => `${(o / 1e6).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Mo`
const quand = iso => new Date(iso).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })

/** Copies de la base (locales et dossier externe) : sauvegarder maintenant, restaurer. */
export default function Sauvegardes() {
  const [infos, setInfos] = useState(null)
  const [message, setMessage] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const charger = () => api.systeme.sauvegardes().then(setInfos).catch(e => setMessage(e.message))
  useEffect(() => { charger() }, [])

  const agir = async action => {
    setOccupe(true); setMessage(null)
    try { setMessage((await action()).message); await charger() }
    catch (e) { setMessage(e.message) }
    finally { setOccupe(false) }
  }
  const restaurer = copie => {
    if (window.confirm(`Remplacer toutes les données actuelles par la copie du ${quand(copie.date)} ?\n\n`
      + "L'état actuel est d'abord mis de côté (copie « avant-restauration »), on peut donc revenir en arrière.")) {
      agir(() => api.systeme.restaurer(copie.chemin))
    }
  }
  if (!infos) return null
  return (
    <div className="carte" style={{ marginTop: 20 }}>
      <div className="section-titre" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Sauvegardes</span>
        <button className="btn btn-mini" disabled={occupe} onClick={() => agir(api.systeme.sauvegarder)}>Sauvegarder maintenant</button>
      </div>
      <p className="discret" style={{ padding: '10px 18px 0' }}>
        Une copie est faite chaque jour au démarrage (30 gardées).{' '}
        {infos.externe
          ? <>Elle est aussi déposée dans <span className="mono">{infos.externe}</span> (10 gardées).</>
          : <>Pour en garder aussi une copie hors de cet ordinateur, indiquez un dossier synchronisé dans <a href="/reglages">Réglages</a>.</>}
      </p>
      {message && <div className="discret" style={{ padding: '8px 18px', color: 'var(--accent)' }}>{message}</div>}
      <div className="tableau-conteneur">
        <table className="tableau">
          <thead><tr><th>Copie</th><th>Emplacement</th><th>Date</th><th>Taille</th><th /></tr></thead>
          <tbody>
            {infos.copies.slice(0, 15).map(c => (
              <tr key={c.chemin}>
                <td className="texte mono">{c.nom}</td>
                <td className="texte">{c.emplacement === 'externe' ? 'Dossier externe' : 'Cet ordinateur'}</td>
                <td>{quand(c.date)}</td>
                <td>{taille(c.taille)}</td>
                <td><button className="btn btn-mini" disabled={occupe} onClick={() => restaurer(c)}>Restaurer</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
