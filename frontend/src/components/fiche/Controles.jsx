// @ts-check
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { STATUTS } from '../../lib/zones'
import { pct, date, dateHeure } from '../../lib/format'

const GRAVITES = { alerte: 'statut-alerte', attention: 'statut-attention', info: 'statut-inconnu' }

/** Controles de vraisemblance de la fiche : comptes, rendement total recalcule, corrections des sources. */
export default function Controles({ valeurId }) {
  const [c, setC] = useState(null)
  useEffect(() => { api.valeurs.controles(valeurId).then(setC).catch(() => setC(null)) }, [valeurId])
  if (!c) return null
  const rt = c.rendement_total
  return (
    <div className="carte">
      <div className="section-titre">Contrôles des données</div>
      <div className="carte-corps pile" style={{ gap: 12 }}>
        {c.echecs > 0 && (
          <div className="info" style={{ background: 'var(--alerte-bg)', color: 'var(--alerte-texte)' }}>
            {c.echecs} échec(s) d'actualisation d'affilée : {c.derniere_erreur}
          </div>
        )}
        {c.comptes && c.comptes.score != null && (
          <div>
            <div className="verif-titre">
              Comptes annuels : confiance <span className={`badge ${STATUTS[c.comptes.statut].classe}`}>{c.comptes.score} / 100</span>
            </div>
            <div className="discret" style={{ fontSize: 12.5 }}>
              {c.comptes.annees} années ({c.comptes.premiere}–{c.comptes.derniere}) · postes essentiels remplis à {pct(c.comptes.completude, { decimales: 0 })}
              {' '}· sources officielles (ESEF, SEC, saisie) pour {pct(c.comptes.officielles, { decimales: 0 })}
            </div>
            {c.comptes.controles.length > 0 ? (
              <ul style={{ margin: '6px 0 0 18px' }}>
                {c.comptes.controles.slice(0, 12).map((x, i) => (
                  <li key={i}><span className={`badge ${GRAVITES[x.gravite]}`}>{x.annee}</span> {x.texte}</li>
                ))}
              </ul>
            ) : <div className="discret">Aucune incohérence détectée (BPA, bilan, variations d'une année sur l'autre).</div>}
          </div>
        )}
        {rt && (
          <div>
            <div className="verif-titre">
              Rendement total recalculé : <span className={`badge ${STATUTS[rt.statut].classe}`}>écart {pct(rt.ecart_max, { signe: true, decimales: 1 })}</span>
            </div>
            <div className="discret" style={{ fontSize: 12.5 }}>
              Cours ajusté refait à partir des clôtures et de {rt.dividendes} dividendes (depuis le {date(rt.premier_dividende)}), comparé à celui
              de Yahoo qui sert à la droite. Plus grand écart le {date(rt.jour_ecart_max)}. Au-delà de 2 %, un dividende est
              probablement oublié, compté deux fois ou mal converti : la pente de la droite peut en être faussée.
            </div>
          </div>
        )}
        {c.contre_verification && (
          <div>
            <div className="verif-titre">
              Cours comparés à {c.contre_verification.source} :{' '}
              <span className={`badge ${STATUTS[c.contre_verification.statut].classe}`}>
                {c.contre_verification.desaccords ? `${c.contre_verification.desaccords} séance(s) en désaccord` : 'identiques'}
              </span>
            </div>
            <div className="discret" style={{ fontSize: 12.5 }}>
              {c.contre_verification.jours} séances communes depuis le {date(c.contre_verification.debut)} (vérifié le {date(c.contre_verification.le)})
              {c.contre_verification.desaccords > 0 && <> ; plus grand écart {pct(c.contre_verification.ecart_max, { signe: true })} le {date(c.contre_verification.jour_ecart_max)}</>}.
              Une seconde source officielle confirme (ou non) les clôtures de Yahoo sur les deux dernières années.
            </div>
          </div>
        )}
        <div>
          <div className="verif-titre">Corrections des sources (12 derniers mois)</div>
          {c.corrections.length ? (
            <ul style={{ margin: '6px 0 0 18px' }}>
              {c.corrections.slice(0, 15).map((x, i) => <li key={i}><span className="discret">{dateHeure(x.date)} · {x.type === 'cours' ? 'cours' : 'comptes'}</span> — {x.detail}</li>)}
            </ul>
          ) : <div className="discret">Aucune : les sources n'ont pas modifié après coup les données déjà enregistrées.</div>}
        </div>
      </div>
    </div>
  )
}
