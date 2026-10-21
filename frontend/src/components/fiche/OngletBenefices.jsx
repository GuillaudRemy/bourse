import { useState } from 'react'
import { pct, nombre } from '../../lib/format'
import GraphiqueBenefices from '../GraphiqueBenefices'
import Barres from '../Barres'
import { Stat } from './OngletRegression'

/** Verification n°2 de la methode : la pente est-elle portee par les benefices ? */
export default function OngletBenefices({ analyse }) {
  const [log, setLog] = useState(true)
  const b = analyse.benefices
  const reg = analyse.regression

  if (!b) {
    return (
      <div className="carte vide">
        Il faut au moins 3 années de BPA positif pour confronter le cours aux bénéfices.<br />
        Complétez l'historique dans l'onglet « Fondamentaux » (rapport PDF, tableur, saisie).
      </div>
    )
  }
  const droite = b.droite_bpa
  const ecartPentes = droite && reg ? reg.pente - droite.pente : null

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat libelle="Pente du cours" valeur={pct(reg?.pente, { signe: true })} detail={analyse.base_ajustee ? 'dividendes réinvestis' : 'hors dividendes'} />
        <Stat aide="bpa" libelle="Pente du BPA (droite)" valeur={pct(droite?.pente, { signe: true })}
              detail={droite ? `R² ${nombre(droite.r2, 2)} · ${b.annees.length} ans` : 'historique trop court'} />
        <Stat libelle="Écart des pentes" valeur={pct(ecartPentes, { signe: true })}
              classe={ecartPentes === null ? '' : Math.abs(ecartPentes) > 0.05 ? 'negatif' : 'positif'}
              detail="proche de 0 (+ le rendement) : pente saine" />
        <Stat aide="per" libelle="PER actuel / médian" valeur={`${nombre(b.per_actuel, 1)} / ${nombre(b.per_median, 1)}`}
              detail={`min ${nombre(b.per_min, 1)} · max ${nombre(b.per_max, 1)}`} />
        <Stat aide="renotation" libelle="Cours vs BPA × PER médian" valeur={pct(b.ecart_per_median, { signe: true })}
              classe={b.ecart_per_median > 0.2 ? 'negatif' : b.ecart_per_median < -0.2 ? 'positif' : ''}
              detail={b.ecart_per_median > 0 ? 'au-dessus de sa valeur habituelle' : 'en dessous de sa valeur habituelle'} />
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="graphique-barre">
            <label className="interrupteur">
              <input type="checkbox" checked={log} onChange={e => setLog(e.target.checked)} /> Échelle logarithmique
            </label>
            <span className="espaceur" />
            <span className="discret">Cours = BPA × PER</span>
          </div>
          <GraphiqueBenefices analyse={analyse} log={log} />
        </div>

        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Comment lire</div>
            <div className="carte-corps pile discret" style={{ fontSize: 12.5 }}>
              <p>La ligne verte est ce que vaudrait l'action si le marché la payait toujours son PER médian
                ({nombre(b.per_median, 1)} fois les bénéfices). Elle ne dépend que des bénéfices.</p>
              <p>Si le cours (bleu) la suit, la hausse vient de l'entreprise : la pente est reproductible.
                S'il s'en écarte durablement vers le haut, la hausse vient d'une <b>renotation</b> (PER qui monte) :
                elle ne se répétera pas. Vers le bas : méfiance du marché — belle entreprise mal-aimée, ou vrai problème ?</p>
              <p>Les pointillés verts bornent les PER extrêmes observés : sortir de cette bande est rare.</p>
            </div>
          </div>
          <div className="carte">
            <div className="section-titre">PER moyen par année</div>
            <div className="carte-corps">
              <Barres points={b.annees.map((a, i) => ({ x: a, y: b.per[i] }))} format={v => nombre(v, 1)} hauteur={100} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
