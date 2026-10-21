import { useCallback, useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { date, prix, dateHeure } from '../../lib/format'
import DepotFichier from '../DepotFichier'

const TYPES = { achat: 'Achat', renforcement: 'Renforcement', allegement: 'Allègement', vente: 'Vente', attente: 'Attente' }
const VERDICTS = { bonne: 'Bonne décision', mauvaise: 'Mauvaise décision', neutre: 'Neutre' }
const CHAMPS = [
  ['pourquoi', 'Pourquoi cette entreprise ?', 'Ce qu’elle fait, pourquoi elle gagnera plus d’argent dans 10 ans…'],
  ['avantage', 'Avantage concurrentiel durable', 'Marque, coûts, réseau, brevets, position dominante…'],
  ['risques', 'Risques', 'Ce qui pourrait mal tourner : concurrence, dette, technologie, réglementation…'],
  ['conditions', 'Ce qui me ferait vendre', 'Thèse invalidée si… (rupture, dette, perte d’avantage, cours très au-dessus de la droite)'],
]
const aujourdhui = () => new Date().toISOString().slice(0, 10)

export default function OngletJournal({ analyse }) {
  const id = analyse.valeur.id
  const devise = analyse.valeur.devise
  const [these, setThese] = useState(null)
  const [decisions, setDecisions] = useState([])
  const [pieces, setPieces] = useState([])
  const [nouvelle, setNouvelle] = useState({ jour: aujourdhui(), type: 'achat', prix: analyse.stats?.dernier ? analyse.stats.dernier.toFixed(2) : '', raison: '' })
  const [message, setMessage] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    const [t, d, p] = await Promise.all([api.journal.these(id), api.journal.decisions(id), api.journal.pieces(id)])
    setThese(t); setDecisions(d); setPieces(p)
  }, [id])
  useEffect(() => { charger().catch(e => setErreur(e.message)) }, [charger])

  const action = async (fn, succes) => {
    setOccupe(true); setErreur(null); setMessage(null)
    try { await fn(); if (succes) setMessage(succes); await charger() }
    catch (e) { setErreur(e.message) } finally { setOccupe(false) }
  }

  if (!these) return <div className="chargement">Chargement…</div>

  const nombre_ = v => v === '' || v === null ? null : Number(String(v).replace(',', '.'))
  const enregistrerThese = () => action(() => api.journal.ecrireThese(id, {
    ...these, prix_achat: nombre_(these.prix_achat), prix_vente: nombre_(these.prix_vente),
  }), 'Thèse enregistrée.')
  const repondues = Object.values(these.checklist).filter(r => r === 'oui').length

  return (
    <div className="pile" style={{ gap: 16 }}>
      {erreur && <div className="erreur">{erreur}</div>}
      {message && <div className="succes">{message}</div>}
      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Thèse d'investissement {these.maj_le && <span className="discret">· modifiée {dateHeure(these.maj_le)}</span>}</div>
          <div className="carte-corps pile">
            <div className="discret" style={{ fontSize: 12.5 }}>
              Écrire sa thèse avant d'acheter oblige à savoir pourquoi on achète — et permet, plus tard, de savoir si l'on avait raison.
            </div>
            {CHAMPS.map(([cle, libelle, aide]) => (
              <div key={cle} className="champ-groupe">
                <label className="champ-label">{libelle}</label>
                <textarea className="champ" rows={3} placeholder={aide} value={these[cle] ?? ''}
                          onChange={e => setThese({ ...these, [cle]: e.target.value })} />
              </div>
            ))}
            <div className="rangee">
              <div className="champ-groupe" style={{ flex: 1 }}>
                <label className="champ-label">Prix d'achat visé ({devise})</label>
                <input className="champ champ-mono" value={these.prix_achat ?? ''} onChange={e => setThese({ ...these, prix_achat: e.target.value })} />
              </div>
              <div className="champ-groupe" style={{ flex: 1 }}>
                <label className="champ-label">Prix de vente visé ({devise})</label>
                <input className="champ champ-mono" value={these.prix_vente ?? ''} onChange={e => setThese({ ...these, prix_vente: e.target.value })} />
              </div>
            </div>
            <button className="btn btn-primaire" onClick={enregistrerThese} disabled={occupe}>Enregistrer la thèse</button>
          </div>
        </div>

        <div className="carte">
          <div className="section-titre">Checklist avant d'acheter — {repondues} / {these.questions.length} « oui »</div>
          {these.questions.map(q => (
            <div key={q} className="question">
              <span>{q}</span>
              <div className="segments">
                {['oui', '?', 'non'].map(r => (
                  <button key={r} className={`segment${(these.checklist[q] ?? '?') === r ? ' actif' : ''}`}
                          onClick={() => setThese({ ...these, checklist: { ...these.checklist, [q]: r } })}>{r}</button>
                ))}
              </div>
            </div>
          ))}
          <div className="carte-corps discret">Pensez à enregistrer la thèse pour garder vos réponses.</div>
        </div>
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Décisions et relecture</div>
          <form className="carte-corps pile" style={{ borderBottom: '1px solid var(--border)' }}
                onSubmit={e => { e.preventDefault(); action(() => api.journal.ajouterDecision(id, { ...nouvelle, prix: nombre_(nouvelle.prix) }), 'Décision notée.').then(() => setNouvelle({ ...nouvelle, raison: '' })) }}>
            <div className="rangee" style={{ flexWrap: 'wrap' }}>
              <input type="date" className="champ" style={{ width: 150 }} value={nouvelle.jour} onChange={e => setNouvelle({ ...nouvelle, jour: e.target.value })} />
              <select className="champ" style={{ width: 150 }} value={nouvelle.type} onChange={e => setNouvelle({ ...nouvelle, type: e.target.value })}>
                {Object.entries(TYPES).map(([c, l]) => <option key={c} value={c}>{l}</option>)}
              </select>
              <input className="champ champ-mono" style={{ width: 120 }} placeholder="Prix" value={nouvelle.prix} onChange={e => setNouvelle({ ...nouvelle, prix: e.target.value })} />
            </div>
            <textarea className="champ" rows={2} placeholder="Pourquoi maintenant ? (position dans le couloir, comptes, actualité…)"
                      value={nouvelle.raison} onChange={e => setNouvelle({ ...nouvelle, raison: e.target.value })} />
            <button className="btn btn-primaire" disabled={occupe}>Noter la décision</button>
          </form>
          {decisions.length === 0 && <div className="vide">Aucune décision notée.</div>}
          {decisions.map(d => <Decision key={d.id} d={d} devise={devise} cours={analyse.stats?.dernier}
                                        enregistrer={data => action(() => api.journal.modifierDecision(id, d.id, data), 'Relecture enregistrée.')}
                                        supprimer={() => confirm('Supprimer cette décision ?') && action(() => api.journal.supprimerDecision(id, d.id))} />)}
        </div>

        <div className="carte">
          <div className="section-titre">Documents</div>
          <div className="carte-corps pile">
            <DepotFichier onFichier={f => action(() => api.journal.ajouterPiece(id, f), 'Document ajouté.')} occupe={occupe}
                          accept="*/*" libelle="Rapport annuel, présentation, note… (glisser ou cliquer)" />
          </div>
          {pieces.map(p => (
            <div key={p.id} className="signal">
              <a className="lien-poste" href={api.journal.lienPiece(id, p.id)} target="_blank" rel="noreferrer" style={{ flex: 1 }}>{p.nom}</a>
              <span className="discret">{(p.taille / 1024).toFixed(0)} ko · {dateHeure(p.created_at)}</span>
              <button className="btn btn-mini btn-fantome" onClick={() => confirm(`Supprimer « ${p.nom} » ?`) && action(() => api.journal.supprimerPiece(id, p.id))}>×</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Decision({ d, devise, cours, enregistrer, supprimer }) {
  const [relecture, setRelecture] = useState(d.relecture ?? '')
  const [verdict, setVerdict] = useState(d.verdict ?? '')
  const evolution = d.prix && cours ? cours / d.prix - 1 : null
  return (
    <div className="decision">
      <div className="rangee" style={{ justifyContent: 'space-between' }}>
        <span><b>{TYPES[d.type]}</b> · {date(d.jour)}{d.prix ? ` · ${prix(d.prix, devise)}` : ''}
          {evolution !== null && <span className={evolution >= 0 ? 'positif' : 'negatif'}> · depuis : {(evolution * 100).toFixed(1).replace('.', ',')} %</span>}
        </span>
        <button className="btn btn-mini btn-fantome" onClick={supprimer}>×</button>
      </div>
      {d.raison && <div className="verif-texte" style={{ whiteSpace: 'pre-wrap' }}>{d.raison}</div>}
      <div className="rangee" style={{ marginTop: 6 }}>
        <input className="champ" placeholder="Relecture a posteriori : avais-je raison, et pour les bonnes raisons ?" value={relecture} onChange={e => setRelecture(e.target.value)} />
        <select className="champ" style={{ width: 170 }} value={verdict} onChange={e => setVerdict(e.target.value)}>
          <option value="">— verdict —</option>
          {Object.entries(VERDICTS).map(([c, l]) => <option key={c} value={c}>{l}</option>)}
        </select>
        <button className="btn btn-mini" onClick={() => enregistrer({ ...d, relecture: relecture || null, verdict: verdict || null })}>OK</button>
      </div>
    </div>
  )
}
