// @ts-check
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { pct, nombre, ton } from '../../lib/format'

const AVIS = [['strongBuy', 'Achat fort', 'var(--z-om)'], ['buy', 'Achat', 'var(--z-se)'], ['hold', 'Conserver', 'var(--z-n)'],
  ['sell', 'Vente', 'var(--z-sv)'], ['strongSell', 'Vente forte', 'var(--z-sm)']]

/** Ce qu'attendent les analystes, confronte a la tendance des benefices passes. */
export default function Consensus({ valeurId, benefices }) {
  const [c, setC] = useState(null)
  useEffect(() => {
    let annule = false
    api.valeurs.consensus(valeurId).then(r => { if (!annule) setC(r) }).catch(e => { if (!annule) setC({ indisponible: e.message }) })
    return () => { annule = true }
  }, [valeurId])
  if (!c) return <div className="carte"><div className="section-titre">Prévisions des analystes</div><div className="chargement">Chargement…</div></div>
  if (c.indisponible) return <div className="carte"><div className="section-titre">Prévisions des analystes</div><p className="discret" style={{ padding: '12px 18px' }}>{c.indisponible}</p></div>

  const derniere = benefices?.annees?.at(-1)
  const droite = benefices?.droite_bpa
  const bpaDroite = annee => {
    const i = droite?.annees.indexOf(annee) ?? -1
    return i >= 0 ? droite.bpa[i] : null
  }
  const totalAvis = c.recommandations ? Object.values(c.recommandations).reduce((a, b) => a + b, 0) : 0
  const o = c.objectif

  return (
    <div className="carte">
      <div className="section-titre">Prévisions des analystes <span className="discret" style={{ textTransform: 'none', letterSpacing: 0 }}>· Yahoo Finance</span></div>
      {c.exercices.length > 0 && (
        <div className="tableau-conteneur">
          <table className="tableau">
            <thead><tr>
              <th>Exercice</th><th>BPA attendu</th><th>Fourchette</th><th>Croissance</th>
              <th title="BPA que donnerait la droite des bénéfices passés">Droite des BPA</th><th>Attendu vs droite</th>
              <th title="Évolution de la prévision moyenne depuis 90 jours">Révision 90 j</th><th>Analystes</th>
            </tr></thead>
            <tbody>
              {c.exercices.map(e => {
                const annee = derniere ? derniere + 1 + e.decalage : null
                const tendance = annee ? bpaDroite(annee) : null
                const ecart = tendance ? e.bpa / tendance - 1 : null
                return (
                  <tr key={e.decalage}>
                    <td className="texte">{annee ?? (e.decalage ? 'Exercice suivant' : 'Exercice en cours')}</td>
                    <td>{nombre(e.bpa, 2)}</td>
                    <td className="discret">{nombre(e.bas, 2)} – {nombre(e.haut, 2)}</td>
                    <td className={ton(e.croissance)}>{pct(e.croissance, { signe: true })}</td>
                    <td>{tendance ? nombre(tendance, 2) : '—'}</td>
                    <td className={ton(ecart)}>{pct(ecart, { signe: true })}</td>
                    <td className={ton(e.evolution_90j)}>{pct(e.evolution_90j, { signe: true })}
                      {e.hausses_30j != null && <span className="discret"> · ↑{e.hausses_30j} ↓{e.baisses_30j}</span>}</td>
                    <td>{e.analystes ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="grille-2" style={{ padding: '14px 18px', gap: 24 }}>
        {o?.mean != null && (
          <div>
            <div className="discret">Objectif de cours moyen à 12 mois</div>
            <div className="mono" style={{ fontSize: 18 }}>{nombre(o.mean, 2)} {c.devise}
              {o.current ? <span className={ton(o.mean / o.current - 1)} style={{ fontSize: 13 }}> ({pct(o.mean / o.current - 1, { signe: true })})</span> : null}
            </div>
            <div className="discret">de {nombre(o.low, 2)} à {nombre(o.high, 2)}</div>
          </div>
        )}
        {totalAvis > 0 && (
          <div>
            <div className="discret">Recommandations ({totalAvis} analystes)</div>
            <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', margin: '8px 0 6px' }}>
              {AVIS.map(([cle, , couleur]) => c.recommandations[cle] > 0 &&
                <div key={cle} style={{ flex: c.recommandations[cle], background: couleur }} title={`${cle} : ${c.recommandations[cle]}`} />)}
            </div>
            <div className="discret" style={{ fontSize: 11.5 }}>
              {AVIS.filter(([cle]) => c.recommandations[cle] > 0).map(([cle, libelle]) => `${libelle} ${c.recommandations[cle]}`).join(' · ')}
            </div>
          </div>
        )}
      </div>
      <p className="discret" style={{ padding: '0 18px 14px', fontSize: 12 }}>
        Les prévisions portent sur 1 à 2 ans, la droite sur 20 : un BPA attendu nettement sous la droite signale un trou d'air
        (ou une rupture) que le marché anticipe. Les analystes se trompent souvent aux retournements, et leurs révisions
        suivent les cours plus qu'elles ne les précèdent. Un repère, pas une boussole.
      </p>
    </div>
  )
}
