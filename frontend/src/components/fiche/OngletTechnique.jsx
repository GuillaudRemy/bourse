// @ts-check
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { pct, prix, nombre, date, ton, variation } from '../../lib/format'
import GraphiqueTechnique, { COULEURS_MM } from '../GraphiqueTechnique'
import { Stat, InterrupteurEuros } from './OngletRegression'

const CLE_OPTIONS = 'bourse.options-techniques.2'
const DEFAUT = {
  unite: 'jour', bougies: true, log: false, moyennes: true, mm: '20,50,200', periode_rsi: 14,
  bollinger: false, ichimoku: false, volume: true, rsi: true, macd: true, stochastique: false, adx: false, atr: false, obv: false,
}
const PANNEAUX = { bollinger: 'Bollinger', ichimoku: 'Ichimoku', moyennes: 'Moyennes mobiles', volume: 'Volume', rsi: 'RSI', macd: 'MACD',
                   stochastique: 'Stochastique', adx: 'ADX', atr: 'ATR', obv: 'OBV' }
const TRACES = { niveau: 'Niveau (support, résistance)', ligne: 'Droite de tendance (2 clics)', note: 'Note datée' }
const TRACES_COURTS = { niveau: 'Niveau', ligne: 'Droite', note: 'Note' }

/** Un trace en une ligne. */
function decrire(a) {
  const d = a.donnees
  if (a.type === 'niveau') return `Niveau ${nombre(d.prix, 2)}${d.texte ? ` — ${d.texte}` : ''}`
  if (a.type === 'ligne') return `Droite ${date(d.t1)} → ${date(d.t2)}`
  return `${date(d.jour)} : ${d.texte}`
}

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
  const [saisie, setSaisie] = useState(null)           // point place, en attente du texte : { jour, prix, texte }
  const [selection, setSelection] = useState(null)     // id du trace selectionne sur le graphique
  const carte = useRef(null)
  const [pleinEcran, setPleinEcran] = useState(false)

  // Echap quitte aussi le plein ecran : on suit le navigateur plutot que le bouton.
  useEffect(() => {
    const suivre = () => setPleinEcran(document.fullscreenElement === carte.current)
    document.addEventListener('fullscreenchange', suivre)
    return () => document.removeEventListener('fullscreenchange', suivre)
  }, [])
  const basculerPleinEcran = () => {
    const demande = pleinEcran ? document.exitFullscreen() : carte.current.requestFullscreen()
    demande.catch(e => setErreur(e.message))
  }

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

  const annuler = () => { setMode(null); setPremier(null); setSaisie(null) }
  const enregistrer = useCallback(async (type, donnees) => {
    await api.valeurs.annoter(valeur.id, { type, donnees })
    setPremier(null); setMode(null); setSaisie(null); chargerAnnotations()
  }, [valeur.id, chargerAnnotations])

  // Texte saisi dans la page, pas par prompt() : une fenetre du navigateur ferait quitter le plein ecran.
  const clic = useCallback(({ jour, prix: p }) => {
    if (mode === 'ligne') {
      if (premier) enregistrer('ligne', { t1: premier.jour, p1: premier.prix, t2: jour, p2: p })
      else setPremier({ jour, prix: p })
    } else if (mode) setSaisie({ jour, prix: p, texte: '' })
  }, [mode, premier, enregistrer])

  const validerSaisie = e => {
    e.preventDefault()
    if (mode === 'niveau') enregistrer('niveau', { prix: saisie.prix, texte: saisie.texte })
    else if (saisie.texte.trim()) enregistrer('note', { jour: saisie.jour, texte: saisie.texte.trim() })
  }

  const choisi = annotations.find(a => a.id === selection)
  const supprimer = useCallback(async id => {
    await api.valeurs.effacerAnnotation(valeur.id, id)
    setSelection(null); chargerAnnotations()
  }, [valeur.id, chargerAnnotations])
  useEffect(() => {
    if (!choisi) return
    const touche = e => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && !/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) supprimer(choisi.id)
    }
    document.addEventListener('keydown', touche)
    return () => document.removeEventListener('keydown', touche)
  }, [choisi, supprimer])

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat aide="rsi" libelle="RSI 14" valeur={nombre(stats.rsi, 0)} classe={stats.rsi >= 70 ? 'negatif' : stats.rsi <= 30 ? 'positif' : ''}
              detail={stats.rsi >= 70 ? 'surachat' : stats.rsi <= 30 ? 'survente' : 'neutre'} />
        <Stat aide="mm" libelle="Écart à la MM200" valeur={variation(stats.ecart_mm200, stats.en_points)} classe={ton(stats.ecart_mm200)} detail={`MM200 à ${prix(stats.mm200, devise)}`} />
        <Stat libelle="Volatilité (1 an)" valeur={pct(stats.volatilite, { decimales: 0 })} detail="annualisée" />
        <Stat libelle="Perte maximale" valeur={pct(stats.perte_max?.baisse)} classe="negatif"
              detail={stats.perte_max && `${date(stats.perte_max.sommet)} → ${date(stats.perte_max.creux)}`} />
        <Stat libelle="Depuis le 1er janvier" valeur={variation(stats.perf_ytd, stats.en_points)} classe={ton(stats.perf_ytd)} />
        <Stat libelle="1 an / 5 ans" valeur={variation(stats.perf_1an, stats.en_points)} classe={ton(stats.perf_1an)} detail={`5 ans : ${variation(stats.perf_5ans, stats.en_points)}`} />
      </div>

      <div className="grille-2">
        <div className="carte carte-plein-ecran" ref={carte}>
          <div className="graphique-barre">
            <div className="segments">
              {['jour', 'semaine', 'mois'].map(u => <button key={u} className={`segment${options.unite === u ? ' actif' : ''}`} onClick={() => changer('unite', u)}>{u[0].toUpperCase() + u.slice(1)}</button>)}
            </div>
            {/* Series BCE : une seule valeur par jour ou par mois, pas de bougies. */}
            {valeur.source !== 'bce' && <label className="interrupteur"><input type="checkbox" checked={options.bougies} onChange={e => changer('bougies', e.target.checked)} /> Bougies</label>}
            <label className="interrupteur"><input type="checkbox" checked={options.log} onChange={e => changer('log', e.target.checked)} /> Log</label>
            <label className="interrupteur" title="Périodes des moyennes mobiles, séparées par des virgules">Moyennes
              <input className="champ champ-mono" style={{ width: 110, padding: '3px 6px' }} value={options.mm} onChange={e => changer('mm', e.target.value)} /></label>
            <label className="interrupteur">RSI <input className="champ champ-mono" style={{ width: 46, padding: '3px 6px' }} value={options.periode_rsi} onChange={e => changer('periode_rsi', Number(e.target.value) || '')} /></label>
            <InterrupteurEuros valeur={valeur} enEuros={enEuros} setEnEuros={setEnEuros} />
            <span className="espaceur" />
            <button className="btn btn-mini" onClick={basculerPleinEcran} aria-label={pleinEcran ? 'Quitter le plein écran' : 'Plein écran'}
                    title={pleinEcran ? 'Quitter le plein écran (Échap)' : 'Plein écran'}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                <path d={pleinEcran ? 'M5 1v4H1M9 1v4h4M5 13V9H1M9 13V9h4' : 'M1 5V1h4M13 5V1H9M1 9v4h4M13 9v4H9'} />
              </svg>
            </button>
          </div>
          <div className="graphique-barre">
            {Object.entries(PANNEAUX).map(([cle, l]) => (
              <label key={cle} className="interrupteur"><input type="checkbox" checked={options[cle]} onChange={e => changer(cle, e.target.checked)} /> {l}</label>
            ))}
            {pleinEcran && (
              <>
                <span className="espaceur" />
                {Object.entries(TRACES_COURTS).map(([cle, l]) => (
                  <button key={cle} className={`btn btn-mini ${mode === cle ? 'btn-primaire' : 'btn-fantome'}`} title={TRACES[cle]}
                          onClick={() => { setMode(cle); setPremier(null); setSaisie(null); setSelection(null) }}>{l}</button>
                ))}
              </>
            )}
          </div>
          {erreur && <div className="erreur" style={{ margin: 12 }}>{erreur}</div>}
          <div className="graphique-zone">
            {mode && (
              <div className="trace-bulle">
                {saisie ? (
                  <form className="rangee" onSubmit={validerSaisie}>
                    <input className="champ" autoFocus aria-label="Texte du tracé" placeholder={mode === 'niveau' ? 'Libellé (facultatif)' : `Note au ${date(saisie.jour)}`}
                           value={saisie.texte} onChange={e => setSaisie({ ...saisie, texte: e.target.value })} />
                    <button className="btn btn-mini btn-primaire">OK</button>
                  </form>
                ) : <span>{mode === 'ligne' && premier ? `Premier point au ${date(premier.jour)} (${nombre(premier.prix, 2)}) : cliquez le second.` : `Cliquez sur le graphique pour placer : ${TRACES[mode].toLowerCase()}.`}</span>}
                <button className="btn btn-mini btn-fantome" onClick={annuler}>Annuler</button>
              </div>
            )}
            {!mode && choisi && (
              <div className="trace-bulle">
                <span>{decrire(choisi)}</span>
                <button className="btn btn-mini btn-danger" title="Touche Suppr" onClick={() => supprimer(choisi.id)}>Supprimer</button>
              </div>
            )}
            {t ? <GraphiqueTechnique t={t} options={valeur.source === 'bce' ? { ...options, bougies: false } : options} annotations={annotations}
                                     onClic={mode ? clic : null} onSelection={setSelection} selection={selection} cle={valeur.id} /> : <div className="chargement">Chargement…</div>}
          </div>
          {t && (
            <div className="legende">
              {options.moyennes && Object.keys(t.moyennes).map((n, i) => <span key={n} className="legende-item"><span className="legende-trait" style={{ borderColor: COULEURS_MM[i % COULEURS_MM.length] }} />MM{n}</span>)}
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
              {Object.entries(TRACES).map(([cle, l]) => <button key={cle} className={`btn btn-mini${mode === cle ? ' btn-primaire' : ''}`} onClick={() => { setMode(cle); setPremier(null); setSaisie(null); setSelection(null) }}>{l}</button>)}
            </div>
            {annotations.map(a => (
              <div key={a.id} className="signal">
                <span style={{ flex: 1 }}>{decrire(a)}</span>
                <button className="btn btn-mini btn-fantome" onClick={() => supprimer(a.id)}>×</button>
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
