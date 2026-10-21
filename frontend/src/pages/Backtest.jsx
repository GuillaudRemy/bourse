import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, date } from '../lib/format'
import { Stat } from '../components/fiche/OngletRegression'
import GraphiqueLignes from '../components/GraphiqueLignes'

const REGLES = {
  'Acheter sous −1σ, vendre au-dessus de +1σ': { achat: -1, vente: 1, depart_investi: false },
  'Investi, alléger au-dessus de +2σ, racheter sur la droite': { achat: 0, vente: 2, depart_investi: true },
  'Acheter seulement sous −2σ, vendre au-dessus de +2σ': { achat: -2, vente: 2, depart_investi: false },
}

export default function Backtest() {
  const [valeurs, setValeurs] = useState([])
  const [listes, setListes] = useState([])
  const [cible, setCible] = useState('tout')            // 'tout' | 'liste:ID' | ID de valeur
  const [p, setP] = useState({ achat: -1, vente: 1, depart_investi: false, frais: '', annees_min: 10, fenetre: '' })
  const [r, setR] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    api.valeurs.list().then(v => setValeurs(v.filter(x => x.type === 'action'))).catch(() => {})
    api.listes.list().then(setListes).catch(() => {})
  }, [])

  const lancer = async () => {
    setOccupe(true); setErreur(null); setR(null)
    const opts = { achat: p.achat, vente: p.vente, depart_investi: p.depart_investi || undefined, annees_min: p.annees_min,
                   fenetre: p.fenetre || undefined, frais: p.frais === '' ? undefined : Number(String(p.frais).replace(',', '.')) / 100 }
    try {
      if (cible === 'tout' || cible.startsWith('liste:')) {
        setR({ univers: await api.backtest(null, { ...opts, liste_id: cible.startsWith('liste:') ? cible.slice(6) : undefined }) })
      } else {
        setR({ valeur: await api.backtest(cible, opts) })
      }
    } catch (e) { setErreur(e.message) } finally { setOccupe(false) }
  }

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Backtest</h1>
          <div className="page-sous-titre">La méthode aurait-elle marché ? Droite recalculée chaque mois avec les seuls cours connus à cette date (sans biais d'anticipation)</div>
        </div>
      </div>
      <div className="carte" style={{ marginBottom: 16 }}>
        <div className="carte-corps pile">
          <div className="rangee" style={{ flexWrap: 'wrap' }}>
            <select className="champ" style={{ width: 'auto' }} value={cible} onChange={e => setCible(e.target.value)}>
              <option value="tout">Toutes les actions suivies</option>
              {listes.map(l => <option key={l.id} value={`liste:${l.id}`}>Liste « {l.nom} »</option>)}
              <optgroup label="Une valeur">{valeurs.map(v => <option key={v.id} value={v.id}>{v.nom}</option>)}</optgroup>
            </select>
            {Object.entries(REGLES).map(([n, regle]) => <button key={n} className="btn btn-mini" onClick={() => setP({ ...p, ...regle })}>{n}</button>)}
          </div>
          <div className="rangee" style={{ flexWrap: 'wrap', gap: 14 }}>
            <label className="interrupteur">Acheter si position ≤ <input className="champ champ-mono" style={{ width: 64 }} value={p.achat} onChange={e => setP({ ...p, achat: e.target.value })} /> σ</label>
            <label className="interrupteur">Vendre si position ≥ <input className="champ champ-mono" style={{ width: 64 }} value={p.vente} onChange={e => setP({ ...p, vente: e.target.value })} /> σ</label>
            <label className="interrupteur"><input type="checkbox" checked={p.depart_investi} onChange={e => setP({ ...p, depart_investi: e.target.checked })} /> Investi dès le départ</label>
            <label className="interrupteur">Frais par ordre <input className="champ champ-mono" style={{ width: 64 }} placeholder="auto" value={p.frais} onChange={e => setP({ ...p, frais: e.target.value })} /> %</label>
            <label className="interrupteur">Historique avant la 1ʳᵉ décision <input className="champ champ-mono" style={{ width: 52 }} value={p.annees_min} onChange={e => setP({ ...p, annees_min: e.target.value })} /> ans</label>
            <label className="interrupteur">Droite sur les <input className="champ champ-mono" style={{ width: 52 }} placeholder="tout" value={p.fenetre} onChange={e => setP({ ...p, fenetre: e.target.value })} /> dernières années</label>
            <button className="btn btn-primaire" onClick={lancer} disabled={occupe}>{occupe ? 'Calcul…' : 'Lancer'}</button>
          </div>
          <div className="discret">Frais « auto » : courtage par défaut des Réglages, ramené à un ordre type, plus la TTF (0,4 %) à l'achat des actions françaises de plus d'un milliard.</div>
        </div>
      </div>
      {erreur && <div className="erreur">{erreur}</div>}
      {r?.univers && <ResultatUnivers r={r.univers} />}
      {r?.valeur && <ResultatValeur r={r.valeur} />}
    </div>
  )
}

function Comparaison({ s, c }) {
  return (
    <div className="stat-grille">
      <Stat libelle="Rendement annuel : règle / conserver" valeur={`${pct(s.rendement_annuel, { signe: true })} / ${pct(c.rendement_annuel, { signe: true })}`}
            classe={s.rendement_annuel >= c.rendement_annuel ? 'positif' : 'negatif'} />
      <Stat libelle="Perte maximale : règle / conserver" valeur={`${pct(s.perte_max, { decimales: 0 })} / ${pct(c.perte_max, { decimales: 0 })}`} />
      <Stat libelle="Volatilité : règle / conserver" valeur={`${pct(s.volatilite, { decimales: 0 })} / ${pct(c.volatilite, { decimales: 0 })}`} />
    </div>
  )
}

function ResultatValeur({ r }) {
  return (
    <div className="pile" style={{ gap: 16 }}>
      <Comparaison s={r.strategie} c={r.conserver} />
      <div className="carte">
        <div className="section-titre">Capital (1 € au départ, {date(r.debut)}) — règle et « acheter et conserver » · investi {pct(r.temps_investi, { decimales: 0 })} du temps · frais {pct(r.frais_achat, { decimales: 2 })} à l'achat, {pct(r.frais_vente, { decimales: 2 })} à la vente</div>
        <GraphiqueLignes jours={r.courbe.jours} log series={[{ nom: 'Conserver', valeurs: r.courbe.conserver, couleur: '#9CA3AF' }, { nom: 'Règle', valeurs: r.courbe.strategie }]} cle="backtest" />
      </div>
      <div className="carte">
        <div className="section-titre">Opérations ({r.operations.length})</div>
        {r.operations.map((o, i) => <div key={i} className="signal"><span className={`signal-point ${o.type === 'achat' ? 'hausse' : 'baisse'}`} /><span className="mono" style={{ minWidth: 90 }}>{date(o.jour)}</span><span>{o.type === 'achat' ? 'Achat' : 'Vente'} à {o.position.toFixed(2).replace('.', ',')} σ</span></div>)}
      </div>
    </div>
  )
}

function ResultatUnivers({ r }) {
  const s = r.resume
  if (!s.valeurs) return <div className="carte vide">Aucune valeur avec assez d'historique.</div>
  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat libelle="Rendement annuel moyen : règle / conserver" valeur={`${pct(s.rendement_strategie, { signe: true })} / ${pct(s.rendement_conserver, { signe: true })}`}
              classe={s.rendement_strategie >= s.rendement_conserver ? 'positif' : 'negatif'} detail={`${s.valeurs} valeur(s), moyenne équipondérée`} />
        <Stat libelle="La règle fait mieux sur" valeur={pct(s.part_gagnante, { decimales: 0 })} detail={`écart médian ${pct(s.ecart_median, { signe: true })}/an`} />
        <Stat libelle="Perte maximale moyenne" valeur={`${pct(s.perte_max_strategie, { decimales: 0 })} / ${pct(s.perte_max_conserver, { decimales: 0 })}`} detail="règle / conserver" />
        <Stat libelle="Temps investi" valeur={pct(s.temps_investi, { decimales: 0 })} detail="le reste en liquidités" />
      </div>
      <div className="carte">
        <table className="tableau">
          <thead><tr><th>Valeur</th><th>Depuis</th><th>Règle /an</th><th>Conserver /an</th><th>Perte max règle</th><th>Perte max conserver</th><th>Investi</th><th>Opérations</th></tr></thead>
          <tbody>
            {r.valeurs.map(v => (
              <tr key={v.id}>
                <td className="texte"><Link className="lien-poste" to={`/valeurs/${v.id}`}>{v.nom}</Link></td>
                {v.trop_court ? <td colSpan={7} className="muet">historique trop court</td> : <>
                  <td>{date(v.debut)}</td>
                  <td className={v.strategie.rendement_annuel >= v.conserver.rendement_annuel ? 'positif' : 'negatif'}>{pct(v.strategie.rendement_annuel, { signe: true })}</td>
                  <td>{pct(v.conserver.rendement_annuel, { signe: true })}</td>
                  <td>{pct(v.strategie.perte_max, { decimales: 0 })}</td><td>{pct(v.conserver.perte_max, { decimales: 0 })}</td>
                  <td>{pct(v.temps_investi, { decimales: 0 })}</td><td>{v.operations}</td>
                </>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="discret">
        Attention au biais du survivant : les valeurs testées sont celles que vous suivez aujourd'hui, donc celles qui ont survécu.
        Les entreprises disparues ou sorties des indices manquent, ce qui embellit « acheter et conserver » comme la règle.
      </div>
    </div>
  )
}
