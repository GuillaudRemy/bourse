// @ts-check
import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { pct, prix } from '../lib/format'
import { Stat } from '../components/fiche/OngletRegression'
import GraphiqueLignes from '../components/GraphiqueLignes'

const euros = v => prix(v, '€')
const MODELES = {
  'Équilibré (25 / 25 / 25 / 25)': { actions: 25, obligations: 25, or: 25, fonds_euros: 25, monetaire: 0 },
  'Prudent': { actions: 20, obligations: 30, or: 10, fonds_euros: 40, monetaire: 0 },
  'Dynamique': { actions: 70, obligations: 15, or: 10, fonds_euros: 5, monetaire: 0 },
  '100 % actions': { actions: 100, obligations: 0, or: 0, fonds_euros: 0, monetaire: 0 },
}
const nombre = t => Number(String(t).replace(',', '.').replace(/\s/g, '')) || 0

/** Projection theorique d'un patrimoine : versements mensuels, repartition, fourchette de resultats. */
export default function Simulateur() {
  const [classes, setClasses] = useState(null)
  const [valeurs, setValeurs] = useState([])
  const [parts, setParts] = useState(MODELES['Équilibré (25 / 25 / 25 / 25)'])
  const [hyp, setHyp] = useState({})                 // {classe: {rendement, volatilite, source}}
  const [p, setP] = useState({ versement: '300', capital: '0', annees: 20, inflation: false })
  const [r, setR] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    api.simulateur.classes().then(c => {
      setClasses(c.classes); setValeurs(c.valeurs)
      setHyp(Object.fromEntries(Object.entries(c.classes).map(([k, x]) => [k, { rendement: x.rendement, volatilite: x.volatilite, source: null }])))
    }).catch(e => setErreur(e.message))
  }, [])

  const total = Object.values(parts).reduce((a, b) => a + nombre(b), 0)

  // Recalcul a chaque changement (apres une courte pause) : le calcul prend un dixieme de seconde.
  useEffect(() => {
    if (!classes || Math.abs(total - 100) > 0.01) return
    const minuterie = setTimeout(() => {
      api.simulateur.lancer({
        versement: nombre(p.versement), capital: nombre(p.capital), annees: p.annees, inflation: p.inflation ? 0.02 : 0,
        poches: Object.keys(classes).map(k => ({ classe: k, part: nombre(parts[k]) / 100, rendement: hyp[k].rendement, volatilite: hyp[k].volatilite })),
      }).then(x => { setR(x); setErreur(null) }).catch(e => setErreur(e.message))
    }, 300)
    return () => clearTimeout(minuterie)
  }, [classes, parts, hyp, p, total])

  const mesurer = async (classe, valeurId) => {
    if (!valeurId) {
      setHyp({ ...hyp, [classe]: { rendement: classes[classe].rendement, volatilite: classes[classe].volatilite, source: null } })
      return
    }
    try {
      const m = await api.simulateur.mesurer(valeurId)
      const nom = valeurs.find(v => String(v.id) === valeurId)?.nom
      setHyp({ ...hyp, [classe]: { rendement: m.rendement, volatilite: m.volatilite, source: valeurId,
                                   detail: `${nom}, ${m.debut.slice(0, 4)}–${m.fin.slice(0, 4)}${m.dividendes ? ', dividendes réinvestis' : ''}` } })
      setErreur(null)
    } catch (e) { setErreur(e.message) }
  }

  const courbe = useMemo(() => {
    if (!r) return null
    const debut = new Date()
    const jours = r.verse.map((_, m) => {
      const d = new Date(debut.getFullYear(), debut.getMonth() + m, 1)
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
    })
    return { jours, series: [
      { nom: 'Versé', valeurs: r.verse, couleur: '#9CA3AF', pointille: true },
      { nom: 'Pessimiste (1 chance sur 10 de faire moins)', valeurs: r.centiles['10'], couleur: '#DC2626' },
      { nom: 'Médian', valeurs: r.centiles['50'], couleur: '#4F46E5', epaisseur: 3 },
      { nom: 'Optimiste (1 chance sur 10 de faire mieux)', valeurs: r.centiles['90'], couleur: '#059669' },
    ] }
  }, [r])
  const fin = r?.jalons.at(-1)

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Simulateur de patrimoine</h1>
          <div className="page-sous-titre">Versements mensuels, répartition entre placements, fourchette de résultats sur 10 à 40 ans — une estimation grossière, pas une promesse</div>
        </div>
      </div>
      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}

      <div className="grille-2" style={{ alignItems: 'start', marginBottom: 16, gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 3fr)' }}>
        <div className="carte">
          <div className="section-titre">Versements</div>
          <div className="carte-corps pile">
            <div className="rangee">
              <label className="champ-groupe" style={{ flex: 1 }}><span className="champ-label">Versement mensuel (€)</span>
                <input className="champ champ-mono" value={p.versement} onChange={e => setP({ ...p, versement: e.target.value })} aria-label="Versement mensuel" /></label>
              <label className="champ-groupe" style={{ flex: 1 }}><span className="champ-label">Capital de départ (€)</span>
                <input className="champ champ-mono" value={p.capital} onChange={e => setP({ ...p, capital: e.target.value })} /></label>
            </div>
            <label className="champ-groupe"><span className="champ-label">Durée : <b className="mono">{p.annees} ans</b></span>
              <input type="range" min={5} max={40} step={1} value={p.annees} onChange={e => setP({ ...p, annees: Number(e.target.value) })} /></label>
            <label className="interrupteur"><input type="checkbox" checked={p.inflation} onChange={e => setP({ ...p, inflation: e.target.checked })} />
              En euros d'aujourd'hui (retire 2 % d'inflation par an)</label>
          </div>
        </div>

        <div className="carte">
          <div className="section-titre" style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <span>Répartition</span>
            <select className="champ" style={{ width: 'auto', textTransform: 'none', letterSpacing: 0 }} value="" onChange={e => e.target.value && setParts(MODELES[e.target.value])}>
              <option value="">Modèle…</option>{Object.keys(MODELES).map(m => <option key={m}>{m}</option>)}
            </select>
          </div>
          {classes && (
            <table className="tableau">
              <thead><tr><th>Placement</th><th>Part</th><th>Rendement / an</th><th>Volatilité</th><th style={{ textAlign: 'left' }}>Mesurer sur une valeur suivie</th></tr></thead>
              <tbody>
                {Object.entries(classes).map(([k, c]) => (
                  <tr key={k}>
                    <td className="texte">{c.libelle}</td>
                    <td><input className="champ champ-mono" style={{ width: 64, textAlign: 'right' }} value={parts[k]} aria-label={`Part ${c.libelle}`}
                               onChange={e => setParts({ ...parts, [k]: e.target.value })} /> %</td>
                    <td>{pct(hyp[k]?.rendement, { decimales: 1 })}</td>
                    <td>{c.volatilite === 0 && !hyp[k]?.source ? 'garanti' : pct(hyp[k]?.volatilite, { decimales: 0 })}</td>
                    <td className="texte">
                      {c.volatilite > 0 ? (
                        <select className="champ" style={{ width: '100%', maxWidth: 210, padding: '2px 4px' }} value={hyp[k]?.source ?? ''} onChange={e => mesurer(k, e.target.value)}
                                title={hyp[k]?.detail}>
                          <option value="">Hypothèse par défaut</option>
                          {valeurs.map(v => <option key={v.id} value={v.id}>{v.nom}</option>)}
                        </select>
                      ) : <span className="discret">taux fixe</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="carte-corps discret" style={{ fontSize: 12.5 }}>
            Total : <b className={Math.abs(total - 100) > 0.01 ? 'negatif' : ''}>{total} %</b>
            {Math.abs(total - 100) > 0.01 && ' — la répartition doit faire 100 %.'} Rééquilibrage chaque année.
            Hypothèses par défaut : ordres de grandeur historiques longs, avant frais et impôts. « Mesurer » remplace l'hypothèse
            par le rendement réel d'une de vos valeurs (dividendes réinvestis, en euros, 20 dernières années au plus).
          </div>
        </div>
      </div>

      {r && fin && (
        <>
          <div className="stat-grille" style={{ marginBottom: 16 }}>
            <Stat libelle={`Versé en ${fin.annees} ans`} valeur={euros(fin.verse)} detail={`dont ${euros(nombre(p.capital))} de départ`} />
            <Stat libelle="Résultat médian" valeur={euros(fin.p50)} detail={`une chance sur deux de faire mieux · gain ${euros(fin.p50 - fin.verse)}`} />
            <Stat libelle="Fourchette (8 chances sur 10)" valeur={`${euros(fin.p10)} – ${euros(fin.p90)}`} detail="entre le scénario pessimiste et l'optimiste" />
            <Stat libelle="Risque de finir sous les versements" valeur={pct(fin.proba_perte, { decimales: 0 })} classe={fin.proba_perte > 0.1 ? 'negatif' : ''}
                  detail={`rendement moyen attendu ${pct(r.rendement_moyen, { decimales: 1 })} / an`} />
          </div>
          <div className="carte" style={{ marginBottom: 16 }}>
            <div className="section-titre">Évolution possible du patrimoine</div>
            <GraphiqueLignes jours={courbe.jours} series={courbe.series} cle="simulateur" />
          </div>
          <div className="carte">
            <table className="tableau">
              <thead><tr><th>Horizon</th><th>Versé</th><th>Pessimiste</th><th>Prudent</th><th>Médian</th><th>Favorable</th><th>Optimiste</th><th>Sous les versements</th></tr></thead>
              <tbody>
                {r.jalons.map(j => (
                  <tr key={j.annees}>
                    <td>{j.annees} ans</td><td>{euros(j.verse)}</td><td>{euros(j.p10)}</td><td>{euros(j.p25)}</td>
                    <td><b>{euros(j.p50)}</b></td><td>{euros(j.p75)}</td><td>{euros(j.p90)}</td><td>{pct(j.proba_perte, { decimales: 0 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="carte-corps discret" style={{ fontSize: 12.5 }}>
              {r.trajectoires} trajectoires tirées au hasard à partir des rendements et volatilités ci-dessus (les placements sont
              corrélés entre eux). Pessimiste : 1 chance sur 10 de faire moins ; prudent : 1 sur 4 ; optimiste : 1 sur 10 de faire mieux.
              Les marchés ont connu des périodes pires que le scénario pessimiste : c'est un ordre de grandeur, pas une garantie.
              Ni frais, ni fiscalité, ni inflation (sauf si vous la retirez).
            </div>
          </div>
        </>
      )}
    </div>
  )
}
