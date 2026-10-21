// @ts-check
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { pct, prix, nombre, date, ton } from '../../lib/format'
import GraphiqueTechnique, { COULEURS_MM } from '../GraphiqueTechnique'
import { Stat, InterrupteurEuros } from './OngletRegression'

const CLE_OPTIONS = 'bourse.options-techniques.2'
const DEFAUT = {
  unite: 'jour', bougies: true, log: false, mm: '20,50,200', periode_rsi: 14,
  bollinger: false, ichimoku: false, volume: true, rsi: true, macd: true, stochastique: false, adx: false, atr: false, obv: false,
}
const PANNEAUX = { bollinger: 'Bollinger', ichimoku: 'Ichimoku', volume: 'Volume', rsi: 'RSI', macd: 'MACD',
                   stochastique: 'Stochastique', adx: 'ADX', atr: 'ATR', obv: 'OBV' }
const TRACES = { niveau: 'Niveau (support, résistance)', ligne: 'Ligne de tendance (2 clics)', note: 'Note datée' }

function lireOptions() {
  try { return { ...DEFAUT, ...JSON.parse(localStorage.getItem(CLE_OPTIONS) || '{}') } } catch { return DEFAUT }
}

export default function OngletTechnique({ analyse, enEuros, setEnEuros }) {
  const { stats, signaux, valeur } = analyse
  const devise = analyse.devise_affichee
  const [options, setOptions] = useState(lireOptions)
  const [t, setT] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [annotations, setAnnotations] = useState([])
  const [mode, setMode] = useState(null)               // trace en cours : niveau | ligne | note
  const [premier, setPremier] = useState(null)         // premier point d'une ligne de tendance

  const changer = (cle, v) => {
    const suivantes = { ...options, [cle]: v }
    setOptions(suivantes)
    try { localStorage.setItem(CLE_OPTIONS, JSON.stringify(suivantes)) } catch { /* stockage indisponible */ }
  }

  useEffect(() => {
    const minuterie = setTimeout(() => {
      const mm = options.mm.split(/[,; ]+/).map(Number).filter(n => n > 0 && n <= 400).slice(0, 6).join(',') || '20,50,200'
      api.valeurs.technique(valeur.id, { unite: options.unite, mm, rsi: options.periode_rsi || 14 })
        .then(r => { setT(r); setErreur(null) }).catch(e => setErreur(e.message))
    }, 250)
    return () => clearTimeout(minuterie)
  }, [valeur.id, options.unite, options.mm, options.periode_rsi])

  const chargerAnnotations = useCallback(() => api.valeurs.annotations(valeur.id).then(setAnnotations).catch(() => {}), [valeur.id])
  useEffect(() => { chargerAnnotations() }, [chargerAnnotations])

  const clic = useCallback(async ({ jour, prix: p }) => {
    if (!mode) return
    let donnees = null
    if (mode === 'niveau') donnees = { prix: p, texte: prompt('Libellé du niveau (facultatif)', '') ?? '' }
    else if (mode === 'note') { const texte = prompt(`Note au ${date(jour)}`); if (!texte) return; donnees = { jour, texte } }
    else if (!premier) { setPremier({ jour, prix: p }); return }
    else donnees = { t1: premier.jour, p1: premier.prix, t2: jour, p2: p }
    await api.valeurs.annoter(valeur.id, { type: mode, donnees })
    setPremier(null); setMode(null); chargerAnnotations()
  }, [mode, premier, valeur.id, chargerAnnotations])

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat aide="rsi" libelle="RSI 14" valeur={nombre(stats.rsi, 0)} classe={stats.rsi >= 70 ? 'negatif' : stats.rsi <= 30 ? 'positif' : ''}
              detail={stats.rsi >= 70 ? 'surachat' : stats.rsi <= 30 ? 'survente' : 'neutre'} />
        <Stat aide="mm" libelle="Écart à la MM200" valeur={pct(stats.ecart_mm200, { signe: true })} classe={ton(stats.ecart_mm200)} detail={`MM200 à ${prix(stats.mm200, devise)}`} />
        <Stat libelle="Volatilité (1 an)" valeur={pct(stats.volatilite, { decimales: 0 })} detail="annualisée" />
        <Stat libelle="Perte maximale" valeur={pct(stats.perte_max?.baisse)} classe="negatif"
              detail={stats.perte_max && `${date(stats.perte_max.sommet)} → ${date(stats.perte_max.creux)}`} />
        <Stat libelle="Depuis le 1er janvier" valeur={pct(stats.perf_ytd, { signe: true })} classe={ton(stats.perf_ytd)} />
        <Stat libelle="1 an / 5 ans" valeur={pct(stats.perf_1an, { signe: true })} classe={ton(stats.perf_1an)} detail={`5 ans : ${pct(stats.perf_5ans, { signe: true })}`} />
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="graphique-barre">
            <div className="segments">
              {['jour', 'semaine', 'mois'].map(u => <button key={u} className={`segment${options.unite === u ? ' actif' : ''}`} onClick={() => changer('unite', u)}>{u[0].toUpperCase() + u.slice(1)}</button>)}
            </div>
            <label className="interrupteur"><input type="checkbox" checked={options.bougies} onChange={e => changer('bougies', e.target.checked)} /> Bougies</label>
            <label className="interrupteur"><input type="checkbox" checked={options.log} onChange={e => changer('log', e.target.checked)} /> Log</label>
            <label className="interrupteur" title="Périodes des moyennes mobiles, séparées par des virgules">Moyennes
              <input className="champ champ-mono" style={{ width: 110, padding: '3px 6px' }} value={options.mm} onChange={e => changer('mm', e.target.value)} /></label>
            <label className="interrupteur">RSI <input className="champ champ-mono" style={{ width: 46, padding: '3px 6px' }} value={options.periode_rsi} onChange={e => changer('periode_rsi', Number(e.target.value) || '')} /></label>
            <InterrupteurEuros valeur={valeur} enEuros={enEuros} setEnEuros={setEnEuros} />
          </div>
          <div className="graphique-barre">
            {Object.entries(PANNEAUX).map(([cle, l]) => (
              <label key={cle} className="interrupteur"><input type="checkbox" checked={options[cle]} onChange={e => changer(cle, e.target.checked)} /> {l}</label>
            ))}
          </div>
          {erreur && <div className="erreur" style={{ margin: 12 }}>{erreur}</div>}
          {mode && (
            <div className="info" style={{ margin: '10px 14px 0' }}>
              <span>{mode === 'ligne' && premier ? `Premier point au ${date(premier.jour)} (${nombre(premier.prix, 2)}) : cliquez le second.` : `Cliquez sur le graphique pour placer : ${TRACES[mode].toLowerCase()}.`}</span>
              <button className="btn btn-mini" onClick={() => { setMode(null); setPremier(null) }}>Annuler</button>
            </div>
          )}
          {t ? <GraphiqueTechnique t={t} options={options} annotations={annotations} onClic={mode ? clic : null} cle={valeur.id} /> : <div className="chargement">Chargement…</div>}
          {t && (
            <div className="legende">
              {Object.keys(t.moyennes).map((n, i) => <span key={n} className="legende-item"><span className="legende-trait" style={{ borderColor: COULEURS_MM[i % COULEURS_MM.length] }} />MM{n}</span>)}
              {options.ichimoku && <span className="legende-item">Ichimoku : tenkan (bleu), kijun (violet), nuage décalé (vert/rouge)</span>}
              {options.adx && <span className="legende-item">ADX &gt; 25 : tendance marquée</span>}
            </div>
          )}
        </div>

        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Signaux</div>
            {signaux.map((s, i) => <div key={i} className="signal"><span className={`signal-point ${s.ton}`} />{s.texte}</div>)}
          </div>
          <div className="carte">
            <div className="section-titre">Tracés</div>
            <div className="carte-corps rangee" style={{ flexWrap: 'wrap' }}>
              {Object.entries(TRACES).map(([cle, l]) => <button key={cle} className={`btn btn-mini${mode === cle ? ' btn-primaire' : ''}`} onClick={() => { setMode(cle); setPremier(null) }}>{l}</button>)}
            </div>
            {annotations.map(a => (
              <div key={a.id} className="signal">
                <span style={{ flex: 1 }}>
                  {a.type === 'niveau' && `Niveau ${nombre(a.donnees.prix, 2)}${a.donnees.texte ? ` — ${a.donnees.texte}` : ''}`}
                  {a.type === 'ligne' && `Ligne ${date(a.donnees.t1)} → ${date(a.donnees.t2)}`}
                  {a.type === 'note' && `${date(a.donnees.jour)} : ${a.donnees.texte}`}
                </span>
                <button className="btn btn-mini btn-fantome" onClick={async () => { await api.valeurs.effacerAnnotation(valeur.id, a.id); chargerAnnotations() }}>×</button>
              </div>
            ))}
          </div>
          <div className="carte">
            <div className="section-titre">Repères</div>
            <dl className="liste-cle">
              <div><dt>MM50</dt><dd>{prix(stats.mm50, devise)}</dd></div>
              <div><dt>MM200</dt><dd>{prix(stats.mm200, devise)}</dd></div>
              <div><dt>Plus haut 52 semaines</dt><dd>{prix(stats.plus_haut_52s, devise)}</dd></div>
              <div><dt>Plus bas 52 semaines</dt><dd>{prix(stats.plus_bas_52s, devise)}</dd></div>
              <div><dt>Performance annualisée</dt><dd>{pct(stats.perf_annuelle, { signe: true })}</dd></div>
              <div><dt>Historique depuis</dt><dd>{date(stats.premier_jour)}</dd></div>
            </dl>
          </div>
          <div className="discret">
            Les indicateurs techniques lisent le court terme. Pour un investisseur de long terme, ils aident à choisir le moment d'entrée
            une fois la valeur sélectionnée par sa droite et ses comptes. Les périodes s'appliquent à l'unité choisie (MM20 en semaines = 20 semaines).
          </div>
        </div>
      </div>
    </div>
  )
}
