// @ts-check
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { STATUTS, TYPES } from '../lib/zones'
import { date, dateHeure } from '../lib/format'
import { Stat } from '../components/fiche/OngletRegression'

const SOURCES = { yahoo: 'Yahoo', esef: 'ESEF', sec: 'SEC', manuel: 'saisie', import: 'import', pdf: 'PDF' }
const annees = (debut, fin) => debut && fin ? Math.round((Date.parse(fin) - Date.parse(debut)) / (365.25 * 864e5)) : 0

/** Ce que l'application sait de chaque valeur : profondeur des cours et des comptes, sources, incidents. */
export default function Couverture() {
  const [d, setD] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [filtre, setFiltre] = useState('tous')
  useEffect(() => { api.couverture().then(setD).catch(e => setErreur(e.message)) }, [])

  const lignes = useMemo(() => (d?.valeurs ?? []).filter(v =>
    filtre === 'tous' || (filtre === 'problemes' && (v.echecs || v.qualite_cours === 'alerte' || v.comptes_statut === 'alerte' || v.corrections_90j))
    || (filtre === 'sans_comptes' && v.type === 'action' && v.comptes_annees < 5)), [d, filtre])
  const nom = Object.fromEntries((d?.valeurs ?? []).map(v => [v.id, v.nom]))
  const actions = d?.valeurs.filter(v => v.type === 'action') ?? []

  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Couverture des données</h1>
          <div className="page-sous-titre">Profondeur de l'historique, sources des comptes, identifiants et incidents, valeur par valeur</div>
        </div>
      </div>
      {erreur && <div className="erreur">{erreur}</div>}
      {!d ? <div className="chargement">Chargement…</div> : (
        <>
          <div className="stat-grille" style={{ marginBottom: 16 }}>
            <Stat libelle="Valeurs suivies" valeur={d.valeurs.length} detail={`dont ${actions.length} actions`} />
            <Stat libelle="Actions avec 10 ans de comptes ou plus" valeur={actions.filter(v => v.comptes_annees >= 10).length}
                  detail={`${actions.filter(v => v.comptes_annees < 5).length} en ont moins de 5`} />
            <Stat libelle="Comptes de confiance moyenne ou faible" valeur={actions.filter(v => v.comptes_statut && v.comptes_statut !== 'ok').length}
                  detail="score sous 70 / 100" />
            <Stat libelle="Incidents" valeur={d.valeurs.filter(v => v.echecs).length} detail={`valeurs en échec · ${d.corrections.length} correction(s) des sources en 90 jours`} />
          </div>
          <div className="carte" style={{ marginBottom: 16 }}>
            <div className="graphique-barre">
              <div className="segments">
                {[['tous', 'Toutes'], ['problemes', 'À surveiller'], ['sans_comptes', 'Actions avec peu de comptes']].map(([k, l]) => (
                  <button key={k} className={`segment${filtre === k ? ' actif' : ''}`} onClick={() => setFiltre(k)}>{l}</button>
                ))}
              </div>
            </div>
            <div className="tableau-conteneur">
              <table className="tableau tableau-fixe" style={{ minWidth: 1300 }}>
                <colgroup><col />{[130, 90, 120, 90, 100, 130, 96, 250].map((l, i) => <col key={i} style={{ width: l }} />)}</colgroup>
                <thead><tr><th>Valeur</th><th>Type</th><th>Cours</th><th>Qualité cours</th><th>Comptes</th><th>Confiance</th><th style={{ textAlign: 'left' }}>Sources</th><th>Dividendes</th><th style={{ textAlign: 'left' }}>Incidents</th></tr></thead>
                <tbody>
                  {lignes.map(v => (
                    <tr key={v.id}>
                      <td className="texte" title={v.nom}><Link className="lien-poste" to={`/valeurs/${v.id}?onglet=donnees`}>{v.nom}</Link>
                        <div className="valeur-symbole">{v.symbole}{v.isin ? ` · ${v.isin}` : ''}{v.lei ? ' · LEI' : ''}{v.cik ? ' · CIK' : ''}</div></td>
                      <td className="texte">{TYPES[v.type]}</td>
                      <td title={v.cours_debut ? `du ${date(v.cours_debut)} au ${date(v.cours_fin)} (${v.seances} séances)` : ''}>
                        {v.cours_debut ? `${annees(v.cours_debut, v.cours_fin)} ans` : '—'}<div className="valeur-symbole">depuis {v.cours_debut?.slice(0, 4) ?? '—'}</div></td>
                      <td>{v.qualite_cours ? <span className={`badge ${STATUTS[v.qualite_cours].classe}`}>{STATUTS[v.qualite_cours].libelle}</span> : '—'}</td>
                      <td>{v.type !== 'action' ? <span className="muet">—</span> : v.comptes_annees ? `${v.comptes_annees} ans` : <span className="negatif">aucun</span>}
                        {v.comptes_premiere && <div className="valeur-symbole">{v.comptes_premiere}–{v.comptes_derniere}</div>}</td>
                      <td>{v.comptes_score != null ? <span className={`badge ${STATUTS[v.comptes_statut].classe}`}>{v.comptes_score} / 100</span> : '—'}</td>
                      <td className="texte">{v.sources_comptes.map(s => SOURCES[s] ?? s).join(', ') || '—'}</td>
                      <td>{v.dividendes || '—'}</td>
                      <td className="texte" title={v.derniere_erreur ?? ''}>
                        {v.echecs ? <span className="negatif">{v.echecs} échec(s)</span> : null}
                        {v.corrections_90j ? <span className="discret"> {v.corrections_90j} correction(s)</span> : null}
                        {v.contre_verification?.desaccords > 0 && <span className="negatif"> cours ≠ {v.contre_verification.source} ({v.contre_verification.desaccords} j)</span>}
                        {!v.echecs && !v.corrections_90j && !v.contre_verification?.desaccords && <span className="discret">
                          {v.contre_verification ? `cours = ${v.contre_verification.source} · ` : ''}maj {dateHeure(v.maj_le)}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {d.corrections.length > 0 && (
            <div className="carte">
              <div className="section-titre">Corrections des sources (90 derniers jours)</div>
              <div className="carte-corps">
                <ul style={{ margin: '0 0 0 18px' }}>
                  {d.corrections.map((c, i) => <li key={i}><span className="discret">{dateHeure(c.date)}</span> · <b>{nom[c.valeur_id]}</b> — {c.detail}</li>)}
                </ul>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
