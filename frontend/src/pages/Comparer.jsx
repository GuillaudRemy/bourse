import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, nombre, sigma, prix, unite } from '../lib/format'
import { STATUTS } from '../lib/zones'
import { BadgeZone } from '../components/Jauge'
import GraphiqueLignes, { COULEURS } from '../components/GraphiqueLignes'

const LIGNES = [
  ['Cours', l => prix(l.dernier, unite(l.valeur))], ['Performance 1 an', l => pct(l.perf_1an, { signe: true })],
  ['Performance 5 ans', l => pct(l.perf_5ans, { signe: true })], ['Pente de la droite', l => pct(l.pente, { signe: true })],
  ['Écart-type du couloir', l => pct(l.ecart_type, { decimales: 0 })], ['Position', l => sigma(l.position)],
  ['Zone', l => <BadgeZone zone={l.zone} />],
  ['Droite', l => l.fiabilite ? <span className={`badge ${STATUTS[l.fiabilite].classe}`}>{STATUTS[l.fiabilite].libelle}</span> : '—'],
  ['Volatilité 1 an', l => pct(l.volatilite, { decimales: 0 })], ['Note de qualité', l => l.note ?? '—'],
  ['ROIC moyen 5 ans', l => pct(l.roic)], ['Marge opérationnelle', l => pct(l.marge_operationnelle)],
  ['Croissance du BPA', l => pct(l.croissance_bpa_10, { signe: true })], ['Croissance du CA', l => pct(l.croissance_ca_10, { signe: true })],
  ['Dette nette / EBITDA', l => nombre(l.dette_nette_ebitda, 1)], ['Piotroski', l => l.piotroski ?? '—'],
  ['PER', l => nombre(l.per, 1)], ['PER dans son histoire', l => pct(l.cherte_per, { decimales: 0 })],
  ['VE / EBITDA', l => nombre(l.ve_ebitda, 1)], ['Rendement du FCF', l => pct(l.rendement_fcf)],
  ['Rendement du dividende', l => pct(l.rendement_dividende)], ['Croissance supposée (DCF inversé)', l => pct(l.dcf_inverse, { signe: true })],
]

export default function Comparer() {
  const [recherche, setRecherche] = useSearchParams()
  const ids = (recherche.get('ids') || '').split(',').filter(Boolean)
  const [valeurs, setValeurs] = useState([])
  const [reference, setReference] = useState('')
  const [annees, setAnnees] = useState(10)
  const [log, setLog] = useState(true)
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => { api.valeurs.list().then(v => {
    setValeurs(v)
    setReference(r => r || String(v.find(x => x.symbole === 'CAC.PA' || x.symbole === '^SP500TR')?.id ?? ''))
  }).catch(() => {}) }, [])
  useEffect(() => {
    if (!ids.length) { setDonnees(null); return }
    let actuelle = true          // une reponse plus ancienne ne doit pas ecraser la plus recente
    api.comparer({ ids: ids.join(','), annees, reference: reference || undefined })
      .then(d => { if (actuelle) { setDonnees(d); setErreur(null) } }).catch(e => actuelle && setErreur(e.message))
    return () => { actuelle = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recherche, annees, reference])

  const changer = nouveaux => setRecherche(nouveaux.length ? { ids: nouveaux.join(',') } : {})
  const nom = id => valeurs.find(v => String(v.id) === String(id))?.nom ?? id
  const choisis = ids.filter(id => donnees?.series[id])
  const base100 = useMemo(() => {
    const lignes = choisis.map(id => ({ nom: nom(id), valeurs: donnees.series[id] }))
    if (lignes.length && reference && donnees?.series[reference] && !ids.includes(reference)) {
      lignes.push({ nom: `${nom(reference)} (référence)`, valeurs: donnees.series[reference], couleur: '#9CA3AF', pointille: true, epaisseur: 1.5 })
    }
    return lignes
  }, [donnees, valeurs]) // eslint-disable-line react-hooks/exhaustive-deps
  const relatif = useMemo(() => donnees?.force_relative ? choisis.filter(id => donnees.force_relative[id]).map(id => ({ nom: nom(id), valeurs: donnees.force_relative[id] })) : null, [donnees, valeurs]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Comparer</h1>
          <div className="page-sous-titre">Base 100 dividendes réinvestis, force relative face à une référence, et chiffres côte à côte</div>
        </div>
      </div>
      <div className="carte" style={{ marginBottom: 16 }}>
        <div className="graphique-barre" style={{ flexWrap: 'wrap' }}>
          {ids.map((id, i) => (
            <span key={id} className="puce-valeur" style={{ borderColor: COULEURS[i % COULEURS.length] }}>
              {nom(id)} <button onClick={() => changer(ids.filter(x => x !== id))}>×</button>
            </span>
          ))}
          <select className="champ" style={{ width: 'auto' }} value="" onChange={e => e.target.value && changer([...ids, e.target.value].slice(0, 8))}>
            <option value="">+ Ajouter une valeur…</option>
            {valeurs.filter(v => !ids.includes(String(v.id))).map(v => <option key={v.id} value={v.id}>{v.nom}</option>)}
          </select>
          <span className="espaceur" />
          <label className="interrupteur">Référence
            <select className="champ" style={{ width: 'auto' }} value={reference} onChange={e => setReference(e.target.value)}>
              <option value="">aucune</option>{valeurs.map(v => <option key={v.id} value={v.id}>{v.nom}</option>)}
            </select>
          </label>
          <div className="segments">{[5, 10, 20].map(a => <button key={a} className={`segment${annees === a ? ' actif' : ''}`} onClick={() => setAnnees(a)}>{a} ans</button>)}</div>
          <label className="interrupteur"><input type="checkbox" checked={log} onChange={e => setLog(e.target.checked)} /> Log</label>
        </div>
      </div>
      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {!ids.length ? <div className="carte vide">Ajoutez au moins deux valeurs à comparer (ou sélectionnez-les dans le tableau des valeurs ou le screener).</div> : donnees && (
        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Base 100 au {donnees.debut.split('-').reverse().join('/')}</div>
            <GraphiqueLignes jours={donnees.jours} series={base100} log={log} cle="base100" />
          </div>
          {relatif?.length > 0 && (
            <div className="carte">
              <div className="section-titre">Force relative face à {nom(donnees.reference)} (monte = fait mieux que la référence)</div>
              <GraphiqueLignes jours={donnees.jours} series={relatif} log={false} cle="relatif" hauteur={260} />
            </div>
          )}
          <div className="carte">
            <div className="section-titre">Côte à côte</div>
            <div className="tableau-conteneur">
              <table className="tableau">
                <thead><tr><th />{choisis.map(id => <th key={id}><Link className="lien-poste" to={`/valeurs/${id}`}>{nom(id)}</Link></th>)}</tr></thead>
                <tbody>
                  {LIGNES.map(([libelle, f]) => (
                    <tr key={libelle}><td className="texte muet">{libelle}</td>{choisis.map(id => <td key={id}>{f(donnees.fiches[id])}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
