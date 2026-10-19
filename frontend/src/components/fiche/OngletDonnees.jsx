import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { TYPES } from '../../lib/zones'
import { date } from '../../lib/format'
import DepotFichier from '../DepotFichier'

const EXEMPLE = `date;ouverture;haut;bas;cloture;cloture_ajustee;volume
02/01/2003;31,20;31,85;31,02;31,70;12,41;1 523 400
03/01/2003;31,70;32,10;31,40;31,95;12,51;1 204 100
…`

export default function OngletDonnees({ analyse, recharger }) {
  const naviguer = useNavigate()
  const { valeur, stats } = analyse
  const [form, setForm] = useState({
    nom: valeur.nom, type: valeur.type, devise: valeur.devise ?? '', secteur: valeur.secteur ?? '',
    debut_regression: valeur.debut_regression ?? '', rupture: valeur.rupture, notes: valeur.notes ?? '',
  })
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const enregistrer = async e => {
    e.preventDefault()
    setErreur(null); setInfo(null)
    try {
      await api.valeurs.update(valeur.id, { ...form, debut_regression: form.debut_regression || null })
      setInfo('Réglages enregistrés.')
      await recharger()
    } catch (e) { setErreur(e.message) }
  }

  const importer = async fichier => {
    setOccupe(true); setErreur(null); setInfo(null)
    try { setInfo((await api.imports.cours(valeur.id, fichier)).message); await recharger() }
    catch (e) { setErreur(e.message) }
    finally { setOccupe(false) }
  }

  const supprimer = async () => {
    if (!confirm(`Supprimer « ${valeur.nom} », ses cours et ses fondamentaux ?`)) return
    try { await api.valeurs.remove(valeur.id); naviguer('/valeurs') }
    catch (e) { setErreur(e.message) }
  }

  const champ = cle => ({ value: form[cle], onChange: e => setForm({ ...form, [cle]: e.target.value }) })

  return (
    <div className="grille-2">
      <div className="pile" style={{ gap: 16 }}>
        <div className="carte">
          <div className="section-titre">Importer des cours</div>
          <div className="carte-corps pile">
            <div className="discret" style={{ fontSize: 12.5 }}>
              Pour une valeur qu'aucune API ne couvre, ou pour compléter un historique.
              Il faut au moins une colonne <b>date</b> et une colonne <b>clôture</b> ; les autres sont facultatives.
              Ajoutez une colonne <b>cloture_ajustee</b> (dividendes réinvestis) pour que la droite
              compte les dividendes. Séparateur <code>;</code> ou <code>,</code>, virgule décimale et dates
              françaises acceptées. Les séances déjà présentes sont remplacées.
            </div>
            <div className="code">{EXEMPLE}</div>
            {valeur.source === 'yahoo' && (
              <div className="info">Valeur suivie par Yahoo : une actualisation remplacera les séances importées aux mêmes dates.</div>
            )}
            <DepotFichier onFichier={importer} occupe={occupe} />
            {stats && (
              <div className="discret">
                Actuellement : cours du {date(stats.premier_jour)} au {date(stats.jour)}.
              </div>
            )}
          </div>
        </div>
        {erreur && <div className="erreur">{erreur}</div>}
        {info && <div className="succes">{info}</div>}
      </div>

      <form className="carte" onSubmit={enregistrer}>
        <div className="section-titre">Réglages</div>
        <div className="carte-corps pile">
          <div className="champ-groupe">
            <label className="champ-label">Nom</label>
            <input className="champ" required {...champ('nom')} />
          </div>
          <div className="rangee">
            <div className="champ-groupe" style={{ flex: 1 }}>
              <label className="champ-label">Type</label>
              <select className="champ" {...champ('type')}>
                {Object.entries(TYPES).map(([cle, libelle]) => <option key={cle} value={cle}>{libelle}</option>)}
              </select>
            </div>
            <div className="champ-groupe" style={{ width: 100 }}>
              <label className="champ-label">Devise</label>
              <input className="champ" {...champ('devise')} />
            </div>
          </div>
          <div className="champ-groupe">
            <label className="champ-label">Secteur</label>
            <input className="champ" {...champ('secteur')} />
          </div>
          <div className="champ-groupe">
            <label className="champ-label">Début de la droite de régression</label>
            <input type="date" className="champ" {...champ('debut_regression')} />
            <span className="discret">
              Vide : {analyse.debut_defaut.slice(0, 4)} ({valeur.type === 'indice'
                ? 'début du régime monétaire moderne'
                : 'après la bulle internet et l’entrée de la Chine à l’OMC'}).
              Banques et défense : partir plus tôt, leurs cycles sont plus longs.
            </span>
          </div>
          <label className="choix">
            <input type="checkbox" checked={form.rupture} onChange={e => setForm({ ...form, rupture: e.target.checked })} />
            <span>
              <b>Rupture : l'entreprise a changé de nature</b><br />
              <span className="discret">
                Nouveau modèle, métier disparu, structure de coûts changée pour de bon (ex. CGG → Viridien,
                Kodak, Orpea → Emeis). La droite passée ne décrit plus l'entreprise d'aujourd'hui.
              </span>
            </span>
          </label>
          <div className="champ-groupe">
            <label className="champ-label">Notes</label>
            <textarea className="champ" rows={4} {...champ('notes')} placeholder="Position concurrentielle, menaces, thèse d'investissement…" />
          </div>
          <div className="rangee">
            <button className="btn btn-primaire">Enregistrer</button>
            <span className="espaceur" />
            <button type="button" className="btn btn-danger" onClick={supprimer}>Supprimer la valeur</button>
          </div>
        </div>
      </form>
    </div>
  )
}
