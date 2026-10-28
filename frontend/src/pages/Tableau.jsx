// @ts-check
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, prix, nombre, sigma, ton, dateHeure, unite } from '../lib/format'
import { TYPES } from '../lib/zones'

const sansAccents = t => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
import Jauge, { BadgeZone } from '../components/Jauge'
import AjouterValeur from '../components/AjouterValeur'
import ImporterIndice from '../components/ImporterIndice'

const COLONNES = [
  { cle: 'nom',            libelle: 'Valeur',      valeur: l => l.valeur.nom.toLowerCase() },
  { cle: 'dernier',        libelle: 'Cours',       valeur: l => l.dernier },
  { cle: 'variation_jour', libelle: 'Jour',        valeur: l => l.variation_jour },
  { cle: 'perf_1an',       libelle: '1 an',        valeur: l => l.perf_1an },
  { cle: 'capitalisation', libelle: 'Capitalisation', valeur: l => l.capitalisation_eur, aide: 'Valeur en bourse de l’entreprise (cours × nombre d’actions), convertie en euros pour comparer toutes les valeurs.' },
  { cle: 'pente',          libelle: 'Pente / an',  valeur: l => l.pente,      aide: 'Rythme de croisière : croissance annuelle de la droite de régression, dividendes réinvestis.' },
  { cle: 'per',            libelle: 'PER',         valeur: l => l.per,        aide: 'Cours ÷ bénéfice par action : le nombre d’années de bénéfices que coûte l’action.' },
  { cle: 'position',       libelle: 'Position',    valeur: l => l.position,   aide: 'Écart du cours à sa droite, en nombre d’écarts-types.' },
  { cle: 'zone',           libelle: 'Zone',        valeur: l => l.position },
  { cle: 'rsi',            libelle: 'RSI 14',      valeur: l => l.rsi },
  { cle: 'ecart_mm200',    libelle: 'vs MM200',    valeur: l => l.ecart_mm200 },
]

/** 103,2 Md€ · 850 M€ */
function capitalisation(euros) {
  if (euros == null) return <span className="muet">—</span>
  const [diviseur, suffixe, decimales] = euros >= 1e9 ? [1e9, 'Md€', euros >= 1e11 ? 0 : 1] : [1e6, 'M€', 0]
  return `${(euros / diviseur).toLocaleString('fr-FR', { maximumFractionDigits: decimales })} ${suffixe}`
}

export default function Tableau() {
  const naviguer = useNavigate()
  const [lignes, setLignes] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [recherche, setRecherche] = useSearchParams()
  const [ajout, setAjout] = useState(() => recherche.get('ajouter') !== null)
  const [progression, setProgression] = useState(null)
  const [tri, setTri] = useState({ cle: 'position', sens: 1 })
  const [filtre, setFiltre] = useState('tous')
  const [listes, setListes] = useState([])
  const [listeId, setListeId] = useState('')
  const [selection, setSelection] = useState(new Set())
  const [importIndice, setImportIndice] = useState(false)
  const [texte, setTexte] = useState('')            // recherche dans les valeurs suivies
  const [page, setPage] = useState(1)
  const [parPage, setParPage] = useState(50)
  useEffect(() => {
    api.reglages.list().then(r => {
      const n = Number(r.find(x => x.cle === 'valeurs_par_page')?.valeur)
      if ([20, 50, 100].includes(n)) setParPage(n)
    }).catch(() => {})
  }, [])
  const changerParPage = n => { setParPage(n); setPage(1); api.reglages.ecrire('valeurs_par_page', String(n)).catch(() => {}) }
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

  const actualiserTout = async (mode = 'cours') => {
    setInfo(null)
    try { setProgression(await api.valeurs.actualiserTout(mode)) }
    catch (e) { setErreur(e.message) }
  }
  const enCours = progression?.en_cours

  const triees = useMemo(() => {
    if (!lignes) return []
    const colonne = COLONNES.find(c => c.cle === tri.cle)
    return lignes
      .filter(l => filtre === 'tous' || l.valeur.type === filtre)
      .filter(l => !listeId || listes.find(x => String(x.id) === listeId)?.valeur_ids.includes(l.valeur.id))
      .filter(l => !texte.trim() || sansAccents(`${l.valeur.nom} ${l.valeur.symbole} ${l.valeur.isin ?? ''} ${l.valeur.secteur ?? ''}`)
        .includes(sansAccents(texte.trim())))
      .sort((a, b) => {
        const va = colonne.valeur(a), vb = colonne.valeur(b)
        // Les valeurs sans donnee vont toujours en bas.
        if (va === null || va === undefined) return 1
        if (vb === null || vb === undefined) return -1
        return (va < vb ? -1 : va > vb ? 1 : 0) * tri.sens
      })
  }, [lignes, tri, filtre, listeId, listes, texte])
  const pages = Math.max(1, Math.ceil(triees.length / parPage))
  const pageAffichee = Math.min(page, pages)
  const affichees = triees.slice((pageAffichee - 1) * parPage, pageAffichee * parPage)

  const trier = cle => setTri(t => ({ cle, sens: t.cle === cle ? -t.sens : 1 }))
  const supprimer = async () => {
    try {
      const ids = [...selection]
      const { noms, operations } = await api.valeurs.supprimer(ids)
      const liste = noms.length > 12 ? `${noms.slice(0, 12).join(', ')}… (+${noms.length - 12})` : noms.join(', ')
      const message = `Supprimer ${noms.length} valeur(s) ?\n\n${liste}\n\nLeurs cours, comptes, journal et alertes seront effacés.`
        + (operations ? `\n\nAttention : ${operations} opération(s) du portefeuille portent sur ces valeurs. Elles seront conservées mais ne seront plus rattachées à une valeur (positions incomplètes).` : '')
      if (!window.confirm(message)) return
      const r = await api.valeurs.supprimer(ids, true)
      setSelection(new Set()); setInfo(`${r.supprimees} valeur(s) supprimée(s).`); chargerListes(); charger()
    } catch (e) { setErreur(e.message) }
  }
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
          <button className="btn" onClick={() => actualiserTout('cours')} disabled={enCours || !lignes?.length}
                  title="Rapide : seulement les séances depuis la dernière mise à jour (l'historique est rechargé pour une valeur si un dividende ou une division l'exige)">
            {enCours && progression?.mode !== 'complet' ? 'Actualisation…' : 'Actualiser les cours'}
          </button>
          <button className="btn" onClick={() => actualiserTout('complet')} disabled={enCours || !lignes?.length}
                  title="Long : historique complet des cours, comptes annuels, fiche et calendrier de toutes les valeurs">
            {enCours && progression?.mode === 'complet' ? 'Mise à jour complète…' : 'Tout mettre à jour'}
          </button>
          <button className="btn" onClick={() => setImportIndice(true)}>Importer un indice</button>
          <button className="btn btn-primaire" onClick={() => setAjout(true)}>+ Ajouter une valeur</button>
        </div>
      </div>

      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {enCours && (
        <div className="carte carte-corps" style={{ marginBottom: 12 }}>
          <div className="rangee" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <span>{progression.mode === 'complet' ? 'Mise à jour complète' : 'Actualisation des cours'} : <b>{progression.courant ?? '…'}</b></span>
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
              <button key={cle} className={`segment${filtre === cle ? ' actif' : ''}`} onClick={() => { setFiltre(cle); setPage(1) }}>
                {libelle}
              </button>
            ))}
          </div>
          <select className="champ" style={{ width: 'auto' }} value={listeId} onChange={e => { setListeId(e.target.value); setPage(1) }}>
            <option value="">Toutes les listes</option>
            {listes.map(l => <option key={l.id} value={l.id}>{l.nom} ({l.valeur_ids.length})</option>)}
          </select>
          <input className="champ" type="search" style={{ width: 230 }} placeholder="Rechercher (nom, symbole, ISIN, secteur)…"
                 value={texte} onChange={e => { setTexte(e.target.value); setPage(1) }} aria-label="Rechercher dans les valeurs" />
          <span className="espaceur" />
          {selection.size > 0 ? (
            <>
              <span className="discret">{selection.size} sélectionnée(s)</span>
              {triees.length > affichees.length && triees.some(l => !selection.has(l.valeur.id)) && (
                <button className="btn btn-mini btn-fantome" onClick={() => setSelection(new Set([...selection, ...triees.map(l => l.valeur.id)]))}>
                  Sélectionner les {triees.length} résultats
                </button>
              )}
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
              <button className="btn btn-mini btn-danger" onClick={supprimer}>Supprimer</button>
              <button className="btn btn-mini btn-fantome" onClick={() => setSelection(new Set())}>Annuler</button>
            </>
          ) : <span className="discret">Cliquez un en-tête pour trier · une ligne pour ouvrir la fiche · cochez pour comparer, ranger dans une liste ou supprimer</span>}
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
                  <th style={{ width: 28 }} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" title="Tout cocher (lignes affichées)" aria-label="Tout cocher"
                           checked={affichees.length > 0 && affichees.every(l => selection.has(l.valeur.id))}
                           onChange={e => {
                             const n = new Set(selection)
                             affichees.forEach(l => e.target.checked ? n.add(l.valeur.id) : n.delete(l.valeur.id))
                             setSelection(n)
                           }} />
                  </th>
                  {COLONNES.map(c => (
                    <th key={c.cle} className={`triable${c.cle === 'nom' ? ' texte' : ''}`} title={c.aide} onClick={() => trier(c.cle)}>
                      {c.libelle}{tri.cle === c.cle ? (tri.sens > 0 ? ' ↑' : ' ↓') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {affichees.map(l => (
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
                    <td>{capitalisation(l.capitalisation_eur)}</td>
                    <td className={ton(l.pente)}>{pct(l.pente, { signe: true })}</td>
                    <td>{l.per != null && l.per > 0 ? nombre(l.per, 1) : <span className="muet">—</span>}</td>
                    <td>
                      <div className="rangee" style={{ justifyContent: 'flex-end' }}>
                        <span style={{ minWidth: 62 }}>{sigma(l.position)}</span>
                        <Jauge position={l.position} />
                      </div>
                    </td>
                    <td><BadgeZone zone={l.zone} /></td>
                    <td className={l.rsi >= 70 ? 'negatif' : l.rsi <= 30 ? 'positif' : ''}>{nombre(l.rsi, 0)}</td>
                    <td className={ton(l.ecart_mm200)}>{pct(l.ecart_mm200, { signe: true })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!triees.length && <div className="vide">Aucune valeur ne correspond à « {texte} ».</div>}
          </div>
        )}
        {lignes?.length > 0 && (
          <div className="graphique-barre pagination" style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }}>
            <span className="discret">
              {triees.length ? `${(pageAffichee - 1) * parPage + 1}–${(pageAffichee - 1) * parPage + affichees.length} sur ${triees.length}` : '0 valeur'}
              {triees.length < lignes.length ? ` (${lignes.length} suivies)` : ''}
            </span>
            <span className="espaceur" />
            <button className="btn btn-mini" disabled={pageAffichee <= 1} onClick={() => setPage(1)}>«</button>
            <button className="btn btn-mini" disabled={pageAffichee <= 1} onClick={() => setPage(pageAffichee - 1)}>Précédente</button>
            <span className="mono">page {pageAffichee} / {pages}</span>
            <button className="btn btn-mini" disabled={pageAffichee >= pages} onClick={() => setPage(pageAffichee + 1)}>Suivante</button>
            <button className="btn btn-mini" disabled={pageAffichee >= pages} onClick={() => setPage(pages)}>»</button>
            <select className="champ" style={{ width: 'auto' }} value={parPage} onChange={e => changerParPage(Number(e.target.value))}
                    title="Aussi réglable dans Réglages">
              {[20, 50, 100].map(n => <option key={n} value={n}>{n} par page</option>)}
            </select>
          </div>
        )}
      </div>

      {importIndice && <ImporterIndice onFermer={message => { setImportIndice(false); if (message) { setInfo(message); chargerListes(); setProgression({ en_cours: true }) } charger() }} />}
      {ajout && (
        <AjouterValeur
          texteInitial={recherche.get('ajouter') ?? ''}
          onFermer={() => { setAjout(false); setRecherche({}) }}
          onAjoutee={(valeur, aImporter) => {
            setAjout(false)
            naviguer(`/valeurs/${valeur.id}${aImporter ? '?onglet=donnees' : ''}`)
          }}
        />
      )}
    </div>
  )
}
