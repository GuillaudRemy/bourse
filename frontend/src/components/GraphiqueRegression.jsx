import { LineSeries, LineStyle } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'

/** Cours (bleu) autour de sa droite de regression (rouge) et du couloir a ±1 et ±2 ecarts-types. */
export default function GraphiqueRegression({ analyse, log, afficherCone = false }) {
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

    // Cone de projection (90 % et 50 % des trajectoires simulees), a partir du dernier cours.
    const cone = analyse.projection?.cone
    if (cone && afficherCone) {
      const gris = couleur('--muted')
      const depart = regression.dernier
      const debutCone = cone.jours.findIndex(j => j > series.jours[series.jours.length - 1])
      for (const [cle, opacite, style] of [['p5', 0.5, LineStyle.Dotted], ['p95', 0.5, LineStyle.Dotted],
                                           ['p25', 0.8, LineStyle.Dashed], ['p75', 0.8, LineStyle.Dashed], ['p50', 0.9, LineStyle.Solid]]) {
        chart.addSeries(LineSeries, { color: alpha(gris, opacite), lineWidth: 1, lineStyle: style,
                                      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
          .setData(cone.jours.slice(debutCone).map((j, i) => ({ time: j, value: depart * cone[cle][i + debutCone] })))
      }
    }

    // On cadre sur la periode de la regression, projection comprise.
    chart.timeScale().setVisibleRange({ from: regression.debut, to: droite.jours[droite.jours.length - 1] })
  }, [analyse, log, afficherCone], valeur.id)

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
        {afficherCone && (
          <span className="legende-item">
            <span className="legende-trait pointille" style={{ borderColor: 'var(--muted)' }} />
            Projection : médiane, 50 % et 90 % des trajectoires
          </span>
        )}
      </div>
    </>
  )
}
