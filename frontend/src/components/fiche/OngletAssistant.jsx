// @ts-check
import { useEffect, useRef, useState } from 'react'
import { api, flux } from '../../lib/api'

const TON = { positif: 'positif', 'négatif': 'negatif', neutre: '' }
const EXEMPLES = ['Pourquoi la note de qualité est-elle à ce niveau ?', 'La droite est-elle fiable pour cette valeur ?',
  "L'action est-elle chère par rapport à son histoire ?", 'Quels points faibles ressortent des comptes ?']

/** Le modele ecrit en Markdown : seul le gras est rendu (le reste reste lisible tel quel). */
const texteRiche = t => t.split(/\*\*(.+?)\*\*/g).map((morceau, i) => i % 2 ? <b key={i}>{morceau}</b> : morceau)

const pages = p => p?.length ? <span className="discret"> (p. {p.join(', ')})</span> : null

function Liste({ titre, points }) {
  if (!points?.length) return null
  return (
    <div>
      <div className="verif-titre">{titre}</div>
      <ul style={{ margin: '4px 0 0 18px' }}>{points.map((p, i) => <li key={i}>{p.texte}{pages(p.pages)}</li>)}</ul>
    </div>
  )
}

function Rapport({ r }) {
  return (
    <div className="pile" style={{ gap: 12 }}>
      <span className="discret">{r.pages_lues?.length} pages lues sur {r.pages_total} · {r.points?.length} points relevés</span>
      <p>{r.resume}</p>
      <Liste titre="Signaux à examiner (vérification n°3 : l'entreprise reste-t-elle fidèle à elle-même ?)" points={r.signaux_rupture} />
      <Liste titre="Risques" points={r.risques} />
      <Liste titre="Stratégie" points={r.strategie} />
      <Liste titre="Perspectives" points={r.perspectives} />
      <p className="discret" style={{ fontSize: 12 }}>L'assistant relève des faits sans pouvoir juger leur portée (une cession
        ancienne et marginale peut y figurer) : à vous d'apprécier s'ils changent la nature de l'entreprise.</p>
      {r.questions?.length > 0 && (
        <div>
          <div className="verif-titre">À vérifier soi-même dans le document</div>
          <ul style={{ margin: '4px 0 0 18px' }}>{r.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

function Actualites({ r }) {
  return (
    <div className="pile" style={{ gap: 10 }}>
      <div><span className="badge">Ton : {r.ton_general}</span></div>
      <p>{r.synthese}</p>
      <ul style={{ margin: '0 0 0 18px' }}>
        {r.points?.map((p, i) => <li key={i} className={TON[p.ton] ?? ''}>{p.texte}</li>)}
      </ul>
      {r.a_verifier?.length > 0 && <div className="discret">À vérifier : {r.a_verifier.join(' · ')}</div>}
      <details className="discret"><summary>{r.articles?.length} titres lus</summary>
        <ul style={{ margin: '4px 0 0 18px' }}>{r.articles?.map((a, i) =>
          <li key={i}><a href={a.lien} target="_blank" rel="noreferrer">{a.titre}</a> · {a.source}</li>)}</ul>
      </details>
    </div>
  )
}

/** Assistant local (Ollama) : rien ne sort de l'ordinateur. Une aide de lecture, jamais une decision. */
export default function OngletAssistant({ analyse, etat }) {
  const id = analyse.valeur.id
  const [historique, setHistorique] = useState([])
  const [question, setQuestion] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [analyses, setAnalyses] = useState([])
  const [pieces, setPieces] = useState([])
  const [travail, setTravail] = useState(null)
  const [occupe, setOccupe] = useState(null)
  const [erreur, setErreur] = useState(null)
  const fin = useRef(null)

  const charger = () => {
    api.assistant.analyses(id).then(setAnalyses).catch(e => setErreur(e.message))
    api.journal.pieces(id).then(p => setPieces(p.filter(x => x.type_mime === 'application/pdf' || x.nom.toLowerCase().endsWith('.pdf'))))
      .catch(() => {})
  }
  useEffect(charger, [id])

  // Suivi de la lecture d'un rapport (quelques minutes).
  useEffect(() => {
    if (!travail?.id || travail.termine) return
    const minuterie = setTimeout(async () => {
      try {
        const t = await api.assistant.travail(travail.id)
        setTravail({ ...t, id: travail.id })
        if (t.termine) { if (t.erreur) setErreur(`Lecture impossible : ${t.erreur}`); charger() }
      } catch (e) { setErreur(e.message); setTravail(null) }
    }, 2000)
    return () => clearTimeout(minuterie)
  }, [travail])                   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fin.current?.scrollIntoView({ block: 'nearest' }) }, [historique])

  const demander = async texte => {
    const q = (texte ?? question).trim()
    if (!q || enCours) return
    setQuestion(''); setErreur(null); setEnCours(true)
    const avant = [...historique, { role: 'user', contenu: q }]
    setHistorique([...avant, { role: 'assistant', contenu: '' }])
    try {
      await flux(`/valeurs/${id}/assistant/question`, { question: q, historique },
        t => setHistorique([...avant, { role: 'assistant', contenu: t }]))
    } catch (e) { setErreur(e.message); setHistorique(avant) }
    finally { setEnCours(false) }
  }
  const lancer = async promesse => {
    setErreur(null)
    try { const { travail: t } = await promesse; setTravail({ id: t, etape: 'Démarrage', fait: 0, total: 0 }) }
    catch (e) { setErreur(e.message) }
  }
  const actualites = async () => {
    setOccupe('actualites'); setErreur(null)
    try { await api.assistant.actualites(id); charger() } catch (e) { setErreur(e.message) } finally { setOccupe(null) }
  }
  const supprimer = async a => { await api.assistant.supprimer(id, a); charger() }
  const lecture = travail && !travail.termine

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="info">
        Assistant local ({etat.modele}) : il fonctionne entièrement sur cet ordinateur, rien n'est envoyé sur internet.
        Il peut se tromper ou mal lire un document : vérifiez toujours dans la source (pages citées). Une aide de lecture, pas un conseil.
      </div>
      {erreur && <div className="erreur">{erreur}</div>}

      <div className="grille-2" style={{ alignItems: 'start' }}>
        <div className="carte">
          <div className="section-titre">Questions sur cette fiche</div>
          <div className="carte-corps pile" style={{ gap: 10 }}>
            {historique.length === 0 && (
              <div className="pile" style={{ gap: 6 }}>
                <span className="discret">L'assistant répond à partir des chiffres calculés par l'application. Par exemple :</span>
                {EXEMPLES.map(e => <button key={e} className="btn btn-mini" style={{ alignSelf: 'flex-start' }} onClick={() => demander(e)}>{e}</button>)}
              </div>
            )}
            {historique.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'bulle-question' : 'bulle-reponse'}>
                {m.contenu ? (m.role === 'assistant' ? texteRiche(m.contenu) : m.contenu) : (enCours && i === historique.length - 1 ? <span className="discret">Réflexion…</span> : null)}
              </div>
            ))}
            <div ref={fin} />
            <form className="rangee" onSubmit={e => { e.preventDefault(); demander() }}>
              <input className="champ" style={{ flex: 1 }} value={question} onChange={e => setQuestion(e.target.value)}
                     placeholder="Votre question…" disabled={enCours} />
              <button className="btn btn-primaire" disabled={enCours || !question.trim()}>Demander</button>
            </form>
            {historique.length > 0 && <button className="btn btn-mini btn-fantome" style={{ alignSelf: 'flex-start' }} onClick={() => setHistorique([])}>Nouvelle conversation</button>}
          </div>
        </div>

        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Lire un rapport annuel</div>
            <div className="carte-corps pile" style={{ gap: 10 }}>
              <span className="discret" style={{ fontSize: 12.5 }}>
                Risques, stratégie, perspectives et signaux de rupture (vérification n°3), avec les pages. Le PDF est rangé dans
                le journal. Compter quelques minutes pour un document de 300 pages.
              </span>
              {lecture ? (
                <div className="pile" style={{ gap: 6 }}>
                  <div>{travail.etape}{travail.total ? ` · ${travail.fait} / ${travail.total}` : ''}</div>
                  <div className="barre-progression"><div style={{ width: `${travail.total ? 100 * travail.fait / travail.total : 5}%` }} /></div>
                </div>
              ) : (
                <div className="rangee">
                  <label className="btn btn-primaire">
                    Choisir un PDF…
                    <input type="file" accept="application/pdf,.pdf" hidden
                           onChange={e => e.target.files?.[0] && lancer(api.assistant.lireRapport(id, e.target.files[0]))} />
                  </label>
                  {pieces.length > 0 && (
                    <select className="champ" style={{ width: 'auto' }} value="" onChange={e => e.target.value && lancer(api.assistant.relirePiece(id, e.target.value))}>
                      <option value="">ou un PDF du journal…</option>
                      {pieces.map(p => <option key={p.id} value={p.id}>{p.nom}</option>)}
                    </select>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="carte">
            <div className="section-titre">Actualités récentes</div>
            <div className="carte-corps rangee">
              <span className="discret" style={{ flex: 1, fontSize: 12.5 }}>Synthèse des titres des 60 derniers jours (les titres seulement, pas les articles).</span>
              <button className="btn" disabled={occupe === 'actualites'} onClick={actualites}>{occupe === 'actualites' ? 'Lecture…' : 'Résumer'}</button>
            </div>
          </div>
        </div>
      </div>

      {analyses.map(a => (
        <div key={a.id} className="carte">
          <div className="section-titre" style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <span>{a.type === 'rapport' ? 'Rapport' : 'Actualités'} · {a.titre}</span>
            <span className="discret" style={{ textTransform: 'none', letterSpacing: 0 }}>
              {new Date(a.date).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })} · {a.modele}
              {a.duree ? ` · ${Math.round(a.duree)} s` : ''}
              {' '}<button className="btn btn-mini btn-fantome" onClick={() => supprimer(a.id)}>×</button>
            </span>
          </div>
          <div className="carte-corps">{a.type === 'rapport' ? <Rapport r={a.resultat} /> : <Actualites r={a.resultat} />}</div>
        </div>
      ))}
    </div>
  )
}
