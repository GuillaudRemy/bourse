import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, nombre, sigma, prix, unite } from '../lib/format'
import { STATUTS } from '../lib/zones'
import { BadgeZone } from '../components/Jauge'
import { COMPOSANTES, score } from '../lib/score'

// Critere : [cle de la fiche, libelle, sens (min|max), unite d'affichage]
const CRITERES = [
  ['pente', 'Pente de la droite ≥', 'min', '%'], ['ecart_type', 'Écart-type ≤', 'max', '%'],
  ['position', 'Position dans le couloir ≤', 'max', 'σ'], ['note', 'Note de qualité ≥', 'min', ''],
  ['roic', 'ROIC moyen ≥', 'min', '%'], ['croissance_bpa_10', 'Croissance du BPA ≥', 'min', '%'],
  ['dette_nette_ebitda', 'Dette nette / EBITDA ≤', 'max', ''], ['per', 'PER ≤', 'max', ''],
  ['cherte_per', 'PER dans son histoire ≤ (0 = jamais aussi bas)', 'max', '%'],
  ['rendement_dividende', 'Rendement du dividende ≥', 'min', '%'], ['rsi', 'RSI ≤', 'max', ''],
  ['annees', 'Historique (années) ≥', 'min', ''],
]
const PRESETS = {
  'Belles entreprises sous leur droite': { pente: '8', position: '-1', note: '60', annees: '15' },
  'Qualité à prix raisonnable': { note: '70', cherte_per: '50', dette_nette_ebitda: '2' },
  'Rendement solide': { rendement_dividende: '3', note: '50', dette_nette_ebitda: '3' },
}
const lire = (v, u) => v === '' || v == null ? null : Number(String(v).replace(',', '.')) / (u === '%' ? 100 : 1)

export default function Screener() {
  const naviguer = useNavigate()
  const [lignes, setLignes] = useState(null)
  const [listes, setListes] = useState([])
  const [listeId, setListeId] = useState('')
  const [criteres, setCriteres] = useState({})
  const [fiable, setFiable] = useState(false)
  const [poids, setPoids] = useState(Object.fromEntries(Object.entries(COMPOSANTES).map(([k, c]) => [k, c.defaut])))
  const [filtres, setFiltres] = useState([])
  const [nomFiltre, setNomFiltre] = useState('')
  const [erreur, setErreur] = useState(null)

  useEffect(() => { api.listes.list().then(setListes).catch(() => {}); api.filtres.list().then(setFiltres).catch(() => {}) }, [])
  useEffect(() => { setLignes(null); api.screener(listeId || undefined).then(setLignes).catch(e => setErreur(e.message)) }, [listeId])

  const resultats = useMemo(() => (lignes ?? [])
    .filter(l => l.valeur.type === 'action')
    .filter(l => CRITERES.every(([cle, , sens, u]) => {
      const seuil = lire(criteres[cle], u)
      if (seuil === null) return true
      if (l[cle] == null) return false
      return sens === 'min' ? l[cle] >= seuil : l[cle] <= seuil
    }))
    .filter(l => !fiable || l.fiabilite === 'ok' || l.fiabilite === 'attention')
    .map(l => ({ ...l, score: score(l, poids) }))
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1)), [lignes, criteres, fiable, poids])

  const charger = f => { setCriteres(f.criteres ?? f); setPoids(p => f.poids ?? p); setFiable(!!f.fiable) }
  const enregistrer = async () => {
    try { await api.filtres.enregistrer(nomFiltre, { criteres, poids, fiable }); setFiltres(await api.filtres.list()) }
    catch (e) { setErreur(e.message) }
  }

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Screener</h1>
          <div className="page-sous-titre">Filtrer les actions suivies et les classer par un score qui combine tendance, position, qualité et prix</div>
        </div>
        <select className="champ" style={{ width: 'auto' }} value={listeId} onChange={e => setListeId(e.target.value)}>
          <option value="">Toutes les valeurs suivies</option>
          {listes.map(l => <option key={l.id} value={l.id}>Liste « {l.nom} » ({l.valeur_ids.length})</option>)}
        </select>
      </div>
      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      <div className="grille-2" style={{ gridTemplateColumns: 'minmax(280px, 1fr) minmax(0, 3fr)' }}>
        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Critères</div>
            <div className="carte-corps pile" style={{ gap: 8 }}>
              <div className="rangee" style={{ flexWrap: 'wrap' }}>
                {Object.keys(PRESETS).map(n => <button key={n} className="btn btn-mini" onClick={() => charger(PRESETS[n])}>{n}</button>)}
              </div>
              {CRITERES.map(([cle, libelle, , u]) => (
                <label key={cle} className="critere">
                  <span>{libelle}</span>
                  <input className="champ champ-mono" placeholder={u || '—'} value={criteres[cle] ?? ''} onChange={e => setCriteres({ ...criteres, [cle]: e.target.value })} />
                </label>
              ))}
              <label className="interrupteur"><input type="checkbox" checked={fiable} onChange={e => setFiable(e.target.checked)} /> Droite fiable ou « prudence » seulement</label>
              <button className="btn btn-mini btn-fantome" onClick={() => { setCriteres({}); setFiable(false) }}>Effacer les critères</button>
            </div>
          </div>
          <div className="carte">
            <div className="section-titre">Poids du score</div>
            <div className="carte-corps pile" style={{ gap: 8 }}>
              {Object.entries(COMPOSANTES).map(([cle, c]) => (
                <label key={cle} className="champ-groupe">
                  <span className="champ-label">{c.libelle} : <b>{poids[cle]}</b></span>
                  <input type="range" min="0" max="50" step="5" value={poids[cle]} onChange={e => setPoids({ ...poids, [cle]: Number(e.target.value) })} />
                </label>
              ))}
            </div>
          </div>
          <div className="carte">
            <div className="section-titre">Filtres enregistrés</div>
            {filtres.map(f => (
              <div key={f.id} className="signal">
                <button className="lien-poste" style={{ flex: 1 }} onClick={() => charger(f.criteres)}>{f.nom}</button>
                <button className="btn btn-mini btn-fantome" onClick={async () => { await api.filtres.supprimer(f.id); setFiltres(await api.filtres.list()) }}>×</button>
              </div>
            ))}
            <div className="graphique-barre" style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }}>
              <input className="champ" placeholder="Nom du filtre" value={nomFiltre} onChange={e => setNomFiltre(e.target.value)} />
              <button className="btn" disabled={!nomFiltre.trim()} onClick={enregistrer}>Enregistrer</button>
            </div>
          </div>
        </div>

        <div className="carte">
          <div className="graphique-barre">
            <b>{resultats.length}</b> action(s) sur {lignes?.filter(l => l.valeur.type === 'action').length ?? '…'}
            <span className="espaceur" />
            <button className="btn btn-mini" disabled={resultats.length < 2}
                    onClick={() => naviguer(`/comparer?ids=${resultats.slice(0, 6).map(l => l.valeur.id).join(',')}`)}>Comparer les 6 premières</button>
          </div>
          {lignes === null ? <div className="chargement">Chargement…</div> : (
            <div className="tableau-conteneur">
              <table className="tableau">
                <thead><tr><th>Valeur</th><th>Score</th><th>Cours</th><th>Pente</th><th>Écart-type</th><th>Position</th><th>Zone</th><th>Droite</th><th>Note</th><th>ROIC</th><th>PER</th><th>PER/histoire</th><th>Rdt div.</th><th>Dette/EBITDA</th></tr></thead>
                <tbody>
                  {resultats.map(l => (
                    <tr key={l.valeur.id} className="cliquable" onClick={() => naviguer(`/valeurs/${l.valeur.id}`)}>
                      <td className="texte"><Link className="lien-poste" to={`/valeurs/${l.valeur.id}`} onClick={e => e.stopPropagation()}>{l.valeur.nom}</Link><div className="valeur-symbole">{l.valeur.symbole}</div></td>
                      <td><span className="badge statut-ok" style={{ opacity: l.score == null ? 0.4 : 1 }}>{l.score ?? '—'}</span></td>
                      <td>{prix(l.dernier, unite(l.valeur))}</td>
                      <td>{pct(l.pente, { signe: true })}</td><td>{pct(l.ecart_type, { decimales: 0 })}</td>
                      <td>{sigma(l.position)}</td><td><BadgeZone zone={l.zone} /></td>
                      <td>{l.fiabilite ? <span className={`badge ${STATUTS[l.fiabilite].classe}`}>{STATUTS[l.fiabilite].libelle}</span> : '—'}</td>
                      <td>{l.note ?? '—'}</td><td>{pct(l.roic)}</td><td>{nombre(l.per, 1)}</td>
                      <td>{pct(l.cherte_per, { decimales: 0 })}</td><td>{pct(l.rendement_dividende)}</td><td>{nombre(l.dette_nette_ebitda, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="carte-corps discret">
            Une valeur sans la donnée d'un critère est écartée par ce critère. Le score ne remplace pas la lecture de la fiche : il aide à choisir lesquelles ouvrir.
          </div>
        </div>
      </div>
    </div>
  )
}
