import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, prix, nombre, sigma, ton, dateHeure, unite } from '../lib/format'
import { STATUTS, TYPES } from '../lib/zones'
import Jauge, { BadgeZone } from '../components/Jauge'
import AjouterValeur from '../components/AjouterValeur'
import ImporterIndice from '../components/ImporterIndice'

const COLONNES = [
  { cle: 'nom',            libelle: 'Valeur',      valeur: l => l.valeur.nom.toLowerCase() },
  { cle: 'dernier',        libelle: 'Cours',       valeur: l => l.dernier },
  { cle: 'variation_jour', libelle: 'Jour',        valeur: l => l.variation_jour },
  { cle: 'perf_1an',       libelle: '1 an',        valeur: l => l.perf_1an },
  { cle: 'pente',          libelle: 'Pente / an',  valeur: l => l.pente,      aide: 'Rythme de croisière : croissance annuelle de la droite de régression, dividendes réinvestis.' },
  { cle: 'ecart_type',     libelle: 'Écart-type',  valeur: l => l.ecart_type, aide: 'Largeur du couloir : plus il est large, plus l’action est nerveuse.' },
  { cle: 'position',       libelle: 'Position',    valeur: l => l.position,   aide: 'Écart du cours à sa droite, en nombre d’écarts-types.' },
  { cle: 'zone',           libelle: 'Zone',        valeur: l => l.position },
  { cle: 'rsi',            libelle: 'RSI 14',      valeur: l => l.rsi },
  { cle: 'ecart_mm200',    libelle: 'vs MM200',    valeur: l => l.ecart_mm200 },
  { cle: 'fiabilite',      libelle: 'Droite',      valeur: l => ['ok', 'inconnu', 'attention', 'alerte'].indexOf(l.fiabilite), aide: 'Les trois vérifications : historique ≥ 20 ans, pente portée par les bénéfices, pas de rupture.' },
]

export default function Tableau() {
  const naviguer = useNavigate()
  const [lignes, setLignes] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [ajout, setAjout] = useState(false)
  const [progression, setProgression] = useState(null)
  const [tri, setTri] = useState({ cle: 'position', sens: 1 })
  const [filtre, setFiltre] = useState('tous')
  const [listes, setListes] = useState([])
  const [listeId, setListeId] = useState('')
  const [selection, setSelection] = useState(new Set())
  const [importIndice, setImportIndice] = useState(false)
  const chargerListes = useCallback(() => api.listes.list().then(setListes).catch(() => {}), [])
  useEffect(() => { chargerListes() }, [chargerListes])

  const charger = useCallback(async () => {
    try { setLignes(await api.valeurs.synthese()); setErreur(null) }
    catch (e) { setErreur(e.message); setLignes(l => l ?? []) }
  }, [])

  useEffect(() => { charger() }, [charger])

  // Suivi de l'actualisation en tache de fond (lancee ici ou automatiquement au demarrage).
  useEffect(() => {
    let actif = true, minuterie = null
    const suivre = async () => {
      try {
        const etat = await api.valeurs.actualisation()
        if (!actif) return
        setProgression(etat)
        if (etat.en_cours) minuterie = setTimeout(suivre, 1500)
        else if (etat.fin) {
          charger()
          const problemes = [...etat.echecs, ...etat.avertissements]
          setInfo(`${etat.faits} valeur(s) actualisée(s).` + (problemes.length ? ` ${problemes.join(' · ')}` : ''))
        }
      } catch { /* serveur momentanement injoignable : on reessaiera au prochain clic */ }
    }
    if (progression === null || progression.en_cours) suivre()
    return () => { actif = false; clearTimeout(minuterie) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [progression?.en_cours])

  const actualiserTout = async () => {
    setInfo(null)
    try { setProgression(await api.valeurs.actualiserTout()) }
    catch (e) { setErreur(e.message) }
  }
  const enCours = progression?.en_cours

  const triees = useMemo(() => {
    if (!lignes) return []
    const colonne = COLONNES.find(c => c.cle === tri.cle)
    return lignes
      .filter(l => filtre === 'tous' || l.valeur.type === filtre)
      .filter(l => !listeId || listes.find(x => String(x.id) === listeId)?.valeur_ids.includes(l.valeur.id))
      .sort((a, b) => {
        const va = colonne.valeur(a), vb = colonne.valeur(b)
        // Les valeurs sans donnee vont toujours en bas.
        if (va === null || va === undefined) return 1
        if (vb === null || vb === undefined) return -1
        return (va < vb ? -1 : va > vb ? 1 : 0) * tri.sens
      })
  }, [lignes, tri, filtre, listeId, listes])

  const trier = cle => setTri(t => ({ cle, sens: t.cle === cle ? -t.sens : 1 }))
  const derniereMaj = lignes?.map(l => l.valeur.maj_le).filter(Boolean).sort().pop()

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Valeurs suivies</h1>
          <div className="page-sous-titre">
            Tendance de fond, position dans le couloir et indicateurs techniques
            · actualisé {dateHeure(derniereMaj)}
          </div>
        </div>
        <div className="rangee">
          <button className="btn" onClick={actualiserTout} disabled={enCours || !lignes?.length}>
            {enCours ? 'Actualisation…' : 'Tout actualiser'}
          </button>
          <button className="btn" onClick={() => setImportIndice(true)}>Importer un indice</button>
          <button className="btn btn-primaire" onClick={() => setAjout(true)}>+ Ajouter une valeur</button>
        </div>
      </div>

      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {enCours && (
        <div className="carte carte-corps" style={{ marginBottom: 12 }}>
          <div className="rangee" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <span>Actualisation : <b>{progression.courant ?? '…'}</b></span>
            <span className="mono discret">{progression.faits} / {progression.total}</span>
          </div>
          <div className="barre"><div className="barre-remplie" style={{ width: `${(progression.faits / Math.max(1, progression.total)) * 100}%`, background: 'var(--accent)' }} /></div>
        </div>
      )}
      {info && !enCours && <div className="succes" style={{ marginBottom: 12 }}>{info}</div>}

      <div className="carte">
        <div className="graphique-barre">
          <div className="segments">
            {[['tous', 'Toutes'], ...Object.entries(TYPES)].map(([cle, libelle]) => (
              <button key={cle} className={`segment${filtre === cle ? ' actif' : ''}`} onClick={() => setFiltre(cle)}>
                {libelle}
              </button>
            ))}
          </div>
          <select className="champ" style={{ width: 'auto' }} value={listeId} onChange={e => setListeId(e.target.value)}>
            <option value="">Toutes les listes</option>
            {listes.map(l => <option key={l.id} value={l.id}>{l.nom} ({l.valeur_ids.length})</option>)}
          </select>
          <span className="espaceur" />
          {selection.size > 0 ? (
            <>
              <span className="discret">{selection.size} sélectionnée(s)</span>
              <button className="btn btn-mini" disabled={selection.size < 2} onClick={() => naviguer(`/comparer?ids=${[...selection].slice(0, 8).join(',')}`)}>Comparer</button>
              <button className="btn btn-mini" onClick={async () => {
                const nom = prompt('Ajouter à quelle liste ? (nom existant ou nouveau)')
                if (!nom) return
                let liste = listes.find(l => l.nom === nom.trim())
                if (!liste) liste = await api.listes.creer(nom.trim())
                await api.listes.ajouter(liste.id, [...selection]); setSelection(new Set()); chargerListes()
                setInfo(`Ajoutée(s) à la liste « ${liste.nom} ».`)
              }}>Ajouter à une liste</button>
              {listeId && <button className="btn btn-mini" onClick={async () => {
                for (const id of selection) await api.listes.retirer(listeId, id)
                setSelection(new Set()); chargerListes()
              }}>Retirer de la liste</button>}
            </>
          ) : <span className="discret">Cliquez un en-tête pour trier · une ligne pour ouvrir la fiche · cochez pour comparer</span>}
        </div>

        {lignes === null ? (
          <div className="chargement">Chargement…</div>
        ) : !lignes.length ? (
          <div className="vide">
            Aucune valeur suivie pour l'instant.<br />
            <button className="btn btn-primaire" style={{ marginTop: 12 }} onClick={() => setAjout(true)}>
              Ajouter une première valeur
            </button>
          </div>
        ) : (
          <div className="tableau-conteneur">
            <table className="tableau">
              <thead>
                <tr>
                  <th style={{ width: 28 }} />
                  {COLONNES.map(c => (
                    <th key={c.cle} className="triable" title={c.aide} onClick={() => trier(c.cle)}>
                      {c.libelle}{tri.cle === c.cle ? (tri.sens > 0 ? ' ↑' : ' ↓') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {triees.map(l => (
                  <tr key={l.valeur.id} className="cliquable" onClick={() => naviguer(`/valeurs/${l.valeur.id}`)}>
                    <td onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selection.has(l.valeur.id)} onChange={() => {
                        const n = new Set(selection); n.has(l.valeur.id) ? n.delete(l.valeur.id) : n.add(l.valeur.id); setSelection(n)
                      }} />
                    </td>
                    <td className="texte">
                      <div className="valeur-nom">
                        {l.valeur.nom}
                        {l.qualite === 'alerte' && <span className="badge statut-alerte" style={{ marginLeft: 6 }} title="Données de cours suspectes : voir l'onglet Données de la fiche">données suspectes</span>}
                      </div>
                      <div className="valeur-symbole">
                        {l.valeur.symbole} · {TYPES[l.valeur.type]}{l.valeur.source === 'import' ? ' · importé' : ''}
                      </div>
                    </td>
                    <td>{prix(l.dernier, unite(l.valeur))}</td>
                    <td className={ton(l.variation_jour)}>{pct(l.variation_jour, { signe: true, decimales: 2 })}</td>
                    <td className={ton(l.perf_1an)}>{pct(l.perf_1an, { signe: true })}</td>
                    <td className={ton(l.pente)}>{pct(l.pente, { signe: true })}</td>
                    <td>{pct(l.ecart_type, { decimales: 0 })}</td>
                    <td>
                      <div className="rangee" style={{ justifyContent: 'flex-end' }}>
                        <span style={{ minWidth: 62 }}>{sigma(l.position)}</span>
                        <Jauge position={l.position} />
                      </div>
                    </td>
                    <td><BadgeZone zone={l.zone} /></td>
                    <td className={l.rsi >= 70 ? 'negatif' : l.rsi <= 30 ? 'positif' : ''}>{nombre(l.rsi, 0)}</td>
                    <td className={ton(l.ecart_mm200)}>{pct(l.ecart_mm200, { signe: true })}</td>
                    <td>
                      {l.fiabilite
                        ? <span className={`badge ${STATUTS[l.fiabilite].classe}`}>{STATUTS[l.fiabilite].libelle}</span>
                        : <span className="muet">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {importIndice && <ImporterIndice onFermer={message => { setImportIndice(false); if (message) { setInfo(message); chargerListes(); setProgression({ en_cours: true }) } charger() }} />}
      {ajout && (
        <AjouterValeur
          onFermer={() => setAjout(false)}
          onAjoutee={(valeur, aImporter) => {
            setAjout(false)
            naviguer(`/valeurs/${valeur.id}${aImporter ? '?onglet=donnees' : ''}`)
          }}
        />
      )}
    </div>
  )
}
