import { useEffect, useRef, useState } from 'react'
import { pct, nombre, grand } from '../../lib/format'
import Barres from '../Barres'
import { Stat } from './OngletRegression'

const RATIOS = [
  { titre: 'Marges', lignes: [
    ['marge_brute', 'Marge brute', 'pct'], ['marge_ebitda', 'Marge EBITDA', 'pct'],
    ['marge_operationnelle', 'Marge opérationnelle', 'pct'], ['marge_nette', 'Marge nette', 'pct']] },
  { titre: 'Rentabilité', lignes: [
    ['roe', 'ROE (capitaux propres)', 'pct'], ['roic', 'ROIC (capital investi)', 'pct'], ['roce', 'ROCE (capital employé)', 'pct'],
    ['rotation_actifs', "Rotation de l'actif", 'x']] },
  { titre: 'Solidité', lignes: [
    ['dette_nette', 'Dette nette', 'grand'], ['dette_nette_ebitda', 'Dette nette / EBITDA', 'x'],
    ['gearing', 'Gearing (dette nette / fonds propres)', 'pct'], ['couverture_interets', 'Couverture des intérêts', 'x'],
    ['liquidite', 'Liquidité (actifs / passifs courants)', 'x']] },
  { titre: 'Trésorerie et actionnaires', lignes: [
    ['fcf', 'Free cash flow', 'grand'], ['fcf_par_action', 'FCF par action', 'nombre'],
    ['conversion_fcf', 'FCF / bénéfice net', 'pct'], ['capex_ca', 'Capex / CA', 'pct'],
    ['payout', 'Taux de distribution', 'pct'], ['dilution', "Variation du nombre d'actions", 'pct']] },
]
const FORMATS = { pct: v => pct(v), x: v => nombre(v, 2), grand, nombre: v => nombre(v, 2) }

export default function OngletQualite({ analyse }) {
  const comptes = analyse.comptes
  const [selection, setSelection] = useState('roic')
  const defilement = useRef(null)
  useEffect(() => {
    if (defilement.current) defilement.current.scrollLeft = defilement.current.scrollWidth
  }, [comptes])

  if (!comptes) {
    return <div className="carte vide">Pas encore de comptes annuels : actualisez la valeur ou importez ses comptes.</div>
  }
  const { synthese: s, note, piotroski, altman, beneish, ratios } = comptes
  const annees = ratios.map(r => r.annee)
  const ligneChoisie = RATIOS.flatMap(g => g.lignes).find(l => l[0] === selection)
  const p = piotroski[piotroski.length - 1], z = altman[altman.length - 1], m = beneish[beneish.length - 1]

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat libelle="Note de qualité" valeur={note.note === null ? '—' : `${note.note} / 100`}
              classe={note.note >= 70 ? 'positif' : note.note !== null && note.note < 40 ? 'negatif' : ''}
              detail={note.note === null ? 'comptes insuffisants' : note.provisoire ? `provisoire : ${note.annees} ans de comptes` : `sur ${note.annees} ans de comptes`} />
        <Stat libelle="Piotroski F-score" valeur={p ? `${p.score} / ${p.sur}` : '—'}
              detail={p ? `${p.annee} · ${p.lecture ?? 'données partielles'}` : 'comptes insuffisants'} />
        <Stat libelle="Altman Z-score" valeur={z?.z != null ? nombre(z.z, 2) : '—'}
              classe={z?.zone === 'détresse' ? 'negatif' : z?.zone === 'sûre' ? 'positif' : ''}
              detail={z?.z != null ? `${z.annee} · zone ${z.zone}` : 'données manquantes'} />
        <Stat libelle="Beneish M-score" valeur={m?.m != null ? nombre(m.m, 2) : '—'}
              classe={m?.vigilance ? 'negatif' : ''}
              detail={m?.m != null ? (m.vigilance ? 'au-dessus de −1,78 : vigilance' : 'pas de signe de manipulation') : 'données manquantes'} />
        <Stat libelle="Dividende sans baisse" valeur={s.dividende_sans_baisse ?? '—'} detail="années consécutives" />
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Note de qualité — détail</div>
          {note.criteres.map(c => (
            <div key={c.nom} className="verif">
              <span className={`verif-icone ${c.points === null ? 'statut-inconnu' : c.points >= c.plafond * 0.66 ? 'statut-ok' : c.points > 0 ? 'statut-attention' : 'statut-alerte'}`}>
                {c.points === null ? '?' : c.points}
              </span>
              <div style={{ flex: 1 }}>
                <div className="verif-titre">{c.nom} <span className="discret">/ {c.plafond}</span></div>
                <div className="verif-texte">
                  {c.valeur === null ? 'Donnée insuffisante — non comptée.' : `Valeur : ${c.nom.includes('dette') ? nombre(c.valeur, 2) : pct(c.valeur)}`} · repère : {c.repere}
                </div>
              </div>
            </div>
          ))}
          <div className="carte-corps discret">
            Note sur les critères calculables uniquement ; elle reste provisoire tant que les comptes couvrent moins de 8 ans.
            Les seuils sont ceux de l'investissement « qualité » : une note n'est qu'un résumé, les comptes priment.
          </div>
        </div>

        <div className="pile" style={{ gap: 16 }}>
          {p && (
            <div className="carte">
              <div className="section-titre">Piotroski {p.annee} — {p.score} / {p.sur}</div>
              {p.criteres.map(c => (
                <div key={c.nom} className="signal">
                  <span className={`signal-point ${c.ok === null ? 'neutre' : c.ok ? 'hausse' : 'baisse'}`} />
                  <span>{c.nom}</span>
                </div>
              ))}
            </div>
          )}
          <div className="carte">
            <div className="section-titre">Croissance annuelle</div>
            <dl className="liste-cle">
              <div><dt>Chiffre d'affaires 5 / 10 ans</dt><dd>{pct(s.croissance_ca_5, { signe: true })} / {pct(s.croissance_ca_10, { signe: true })}</dd></div>
              <div><dt>BPA 5 / 10 ans</dt><dd>{pct(s.croissance_bpa_5, { signe: true })} / {pct(s.croissance_bpa_10, { signe: true })}</dd></div>
              <div><dt>Free cash flow 10 ans</dt><dd>{pct(s.croissance_fcf_10, { signe: true })}</dd></div>
              <div><dt>Dividende 10 ans</dt><dd>{pct(s.croissance_dividende_10, { signe: true })}</dd></div>
              <div><dt>Marge opérationnelle moyenne ({s.annees_marge} ans)</dt><dd>{pct(s.marge_operationnelle_moyenne_10)} ± {pct(s.stabilite_marge_10)}</dd></div>
            </dl>
          </div>
        </div>
      </div>

      <div className="carte">
        <div className="section-titre">Ratios par année — cliquez un ratio pour son graphique</div>
        {ligneChoisie && (
          <div className="carte-corps" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="discret" style={{ marginBottom: 6 }}>{ligneChoisie[1]}</div>
            <Barres points={ratios.map(r => ({ x: r.annee, y: r[selection] }))} format={FORMATS[ligneChoisie[2]]} />
          </div>
        )}
        <div className="tableau-conteneur" ref={defilement}>
          <table className="tableau tableau-etats">
            <thead>
              <tr><th>Ratio</th>{annees.map(a => <th key={a}>{a}</th>)}</tr>
            </thead>
            <tbody>
              {RATIOS.map(groupe => [
                <tr key={groupe.titre}><td className="texte groupe-ratios" colSpan={annees.length + 1}>{groupe.titre}</td></tr>,
                ...groupe.lignes.map(([cle, libelle, format]) => (
                  <tr key={cle} className={selection === cle ? 'ligne-choisie' : ''}>
                    <td className="texte"><button className="lien-poste" onClick={() => setSelection(cle)}>{libelle}</button></td>
                    {ratios.map(r => <td key={r.annee}>{r[cle] === null ? '—' : FORMATS[format](r[cle])}</td>)}
                  </tr>
                )),
              ])}
            </tbody>
          </table>
        </div>
        <div className="carte-corps discret">
          ROIC calculé avec un impôt théorique de 25 % (les comptes stockés ne détaillent pas l'impôt). Un « — » signale une donnée
          absente : complétez les comptes dans l'onglet « Fondamentaux ».
        </div>
      </div>
    </div>
  )
}
