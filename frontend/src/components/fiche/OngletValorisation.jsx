import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { pct, prix, nombre, grand, unite } from '../../lib/format'
import { Stat } from './OngletRegression'

const MULTIPLES = [
  ['per', 'PER', 'x'], ['ve_ebitda', 'VE / EBITDA', 'x'], ['ve_ebit', 'VE / EBIT', 'x'], ['ve_ca', 'VE / CA', 'x'],
  ['p_b', 'Cours / actif net (P/B)', 'x'], ['p_fcf', 'Cours / FCF', 'x'],
  ['rendement_fcf', 'Rendement du FCF', 'pct'], ['rendement_dividende', 'Rendement du dividende', 'pct'],
]
const f = (v, type) => v === null || v === undefined ? '—' : type === 'pct' ? pct(v) : nombre(v, 1)

const CURSEURS = [
  ['croissance', 'Croissance des flux (10 premières années)', -0.05, 0.25, 0.005],
  ['actualisation', 'Rendement exigé (taux d’actualisation)', 0.05, 0.15, 0.005],
  ['terminale', 'Croissance perpétuelle ensuite', 0, 0.04, 0.0025],
]

export default function OngletValorisation({ analyse }) {
  const v = analyse.valorisation
  const devise = unite(analyse.valeur)
  const [hyp, setHyp] = useState(v?.modeles?.hypotheses ?? null)
  const [modeles, setModeles] = useState(v?.modeles ?? null)
  const [secteur, setSecteur] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => { api.valeurs.secteur(analyse.valeur.id).then(setSecteur).catch(() => {}) }, [analyse.valeur.id])

  // Recalcul des modeles quand les hypotheses changent (apres une courte pause).
  useEffect(() => {
    if (!hyp || hyp === v?.modeles?.hypotheses) return
    const minuterie = setTimeout(() => {
      api.valeurs.valorisation(analyse.valeur.id, {
        croissance: hyp.croissance, actualisation: hyp.actualisation, terminale: hyp.terminale, annees: hyp.annees,
      }).then(m => { setModeles(m); setErreur(null) }).catch(e => setErreur(e.message))
    }, 300)
    return () => clearTimeout(minuterie)
  }, [hyp, analyse.valeur.id, v])

  if (!v) return <div className="carte vide">Pas encore de comptes annuels : actualisez la valeur ou importez ses comptes.</div>
  if (v.indisponible) return <div className="carte vide">{v.indisponible}</div>

  const { actuels, historique } = v.multiples
  const cours = modeles.cours
  const fourchette = modeles.fourchette

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat libelle="Fourchette de valeur" valeur={fourchette ? `${prix(fourchette.bas)} – ${prix(fourchette.haut)}` : '—'}
              detail={`cours ${prix(cours, devise)} · médiane ${fourchette ? prix(fourchette.mediane) : '—'}`} />
        <Stat libelle="Croissance que le cours suppose" valeur={pct(modeles.dcf_inverse, { signe: true })}
              detail={`DCF inversé : FCF par an pendant ${modeles.hypotheses.annees} ans`} />
        <Stat libelle="PEG" valeur={nombre(modeles.peg, 2)} detail="PER ÷ croissance du BPA (≈ 1 : raisonnable)" />
        <Stat libelle="Capitalisation" valeur={grand(actuels.capitalisation)} detail={`valeur d'entreprise ${grand(actuels.valeur_entreprise)}`} />
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Multiples — par rapport à leur propre histoire</div>
          <div className="tableau-conteneur">
            <table className="tableau">
              <thead>
                <tr><th>Multiple</th><th>Actuel</th><th>Médiane historique</th><th>Min – max</th><th style={{ textAlign: 'center' }}>Position</th><th>Médiane secteur</th></tr>
              </thead>
              <tbody>
                {MULTIPLES.map(([cle, libelle, type]) => {
                  const h = historique[cle]
                  return (
                    <tr key={cle}>
                      <td className="texte">{libelle}</td>
                      <td>{f(actuels[cle], type)}</td>
                      <td>{f(h?.mediane, type)}</td>
                      <td className="muet">{h ? `${f(h.min, type)} – ${f(h.max, type)}` : '—'}</td>
                      <td style={{ textAlign: 'center' }}>{h ? <Cherte valeur={h.cherte} /> : <span className="muet">—</span>}</td>
                      <td>{f(secteur?.medianes?.[cle], type)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="carte-corps discret">
            Position : où se situe le multiple actuel dans son historique (fin d'année, jusqu'à 20 ans) —
            à gauche, l'action n'a presque jamais été aussi bon marché ; à droite, presque jamais aussi chère.
            Médiane secteur : parmi les valeurs que vous suivez dans le secteur « {secteur?.secteur ?? '—'} »
            ({secteur?.valeurs?.length ?? 0} valeur(s)).
          </div>
        </div>

        <div className="carte">
          <div className="section-titre">Valeur intrinsèque — vos hypothèses</div>
          <div className="carte-corps pile">
            {CURSEURS.map(([cle, libelle, min, max, pas]) => (
              <label key={cle} className="champ-groupe">
                <span className="champ-label">{libelle} : <b className="mono">{pct(hyp[cle], { decimales: 1 })}</b></span>
                <input type="range" min={min} max={max} step={pas} value={hyp[cle]}
                       onChange={e => setHyp({ ...hyp, [cle]: Number(e.target.value) })} />
              </label>
            ))}
            {erreur && <div className="erreur">{erreur}</div>}
          </div>
          {modeles.modeles.map(m => (
            <div key={m.cle} className="verif">
              <span className={`verif-icone ${m.marge_securite > 0.2 ? 'statut-ok' : m.marge_securite > -0.1 ? 'statut-attention' : 'statut-alerte'}`}>
                {m.marge_securite > 0 ? '+' : '−'}
              </span>
              <div style={{ flex: 1 }}>
                <div className="verif-titre">{m.nom} : {prix(m.valeur, devise)} <span className={m.marge_securite > 0 ? 'positif' : 'negatif'}>({pct(m.marge_securite, { signe: true })})</span></div>
                <div className="verif-texte">{m.detail}</div>
              </div>
            </div>
          ))}
          <div className="carte-corps discret">
            Une valeur intrinsèque dépend entièrement de ses hypothèses : regardez la fourchette, et surtout la
            croissance que le cours suppose (DCF inversé) — est-elle crédible au vu des comptes ?
          </div>
        </div>
      </div>
    </div>
  )
}

function Cherte({ valeur }) {
  const couleur = valeur >= 0.8 ? 'var(--z-sm)' : valeur >= 0.6 ? 'var(--z-sv)' : valeur <= 0.2 ? 'var(--z-om)' : valeur <= 0.4 ? 'var(--z-se)' : '#9CA3AF'
  return (
    <span className="cherte" title={`plus cher que ${Math.round(valeur * 100)} % de son historique`}>
      <span className="cherte-curseur" style={{ left: `${valeur * 100}%`, background: couleur }} />
    </span>
  )
}
