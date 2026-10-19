import { LineSeries, LineStyle } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'

/** Cours (bleu) autour de sa droite de regression (rouge) et du couloir a ±1 et ±2 ecarts-types. */
export default function GraphiqueRegression({ analyse, log }) {
  const { series, regression, base_ajustee, valeur } = analyse

  const conteneur = useGraphique(chart => {
    chart.priceScale('right').applyOptions(echelle(log))
    const rouge = couleur('--c-droite')
    const { droite } = regression

    const bande = (cle, style, opacite) => chart.addSeries(LineSeries, {
      color: alpha(rouge, opacite), lineWidth: 1, lineStyle: style,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    }).setData(points(droite.jours, droite[cle]))

    bande('p2', LineStyle.Dotted, 0.6)
    bande('p1', LineStyle.Dashed, 0.8)
    bande('m1', LineStyle.Dashed, 0.8)
    bande('m2', LineStyle.Dotted, 0.6)
    chart.addSeries(LineSeries, {
      color: rouge, lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false,
    }).setData(points(droite.jours, droite.centre))

    chart.addSeries(LineSeries, { color: couleur('--c-cours'), lineWidth: 1.5, priceLineVisible: false })
      .setData(points(series.jours, base_ajustee ? series.ajuste : series.cloture))

    // On cadre sur la periode de la regression, projection comprise.
    chart.timeScale().setVisibleRange({ from: regression.debut, to: droite.jours[droite.jours.length - 1] })
  }, [analyse, log], valeur.id)

  return (
    <>
      <div ref={conteneur} className="graphique" />
      <div className="legende">
        <span className="legende-item">
          <span className="legende-trait" style={{ borderColor: 'var(--c-cours)' }} />
          Cours {base_ajustee ? 'dividendes réinvestis' : 'de clôture'}
        </span>
        <span className="legende-item">
          <span className="legende-trait" style={{ borderColor: 'var(--c-droite)' }} />
          Droite de régression (tendance de fond)
        </span>
        <span className="legende-item">
          <span className="legende-trait pointille" style={{ borderColor: 'var(--c-droite)' }} />
          ±1 et ±2 écarts-types
        </span>
      </div>
    </>
  )
}
