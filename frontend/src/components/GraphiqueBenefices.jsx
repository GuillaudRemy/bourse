import { LineSeries, LineStyle, LineType } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'

const SANS = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }

/** Cours (sans dividendes) face a BPA x PER median, bande de PER min/max et droite du BPA. */
export default function GraphiqueBenefices({ analyse, log }) {
  const { benefices: b, valeur } = analyse

  const conteneur = useGraphique(chart => {
    chart.priceScale('right').applyOptions(echelle(log))
    const vert = couleur('--ok'), rouge = couleur('--c-droite')
    // Une valeur par annee, tenue toute l'annee (marches d'escalier).
    const annuel = valeurs => b.annees.map((a, i) => ({ time: `${a}-01-01`, value: valeurs[i] }))
      .concat([{ time: `${b.annees[b.annees.length - 1]}-12-31`, value: valeurs[valeurs.length - 1] }])

    chart.addSeries(LineSeries, { color: alpha(vert, 0.55), lineWidth: 1, lineStyle: LineStyle.Dashed, lineType: LineType.WithSteps, ...SANS })
      .setData(annuel(b.valeur_per_max))
    chart.addSeries(LineSeries, { color: alpha(vert, 0.55), lineWidth: 1, lineStyle: LineStyle.Dashed, lineType: LineType.WithSteps, ...SANS })
      .setData(annuel(b.valeur_per_min))
    chart.addSeries(LineSeries, { color: vert, lineWidth: 2, lineType: LineType.WithSteps, ...SANS })
      .setData(annuel(b.valeur_per_median))
    if (b.droite_bpa) {
      chart.addSeries(LineSeries, { color: rouge, lineWidth: 1.5, lineStyle: LineStyle.Dotted, ...SANS })
        // Annees connues seulement : sur l'axe des seances, des points futurs espaces d'un an feraient un coude.
        .setData(b.droite_bpa.annees.map((a, i) => ({ time: `${a}-07-01`, value: b.droite_bpa.bpa[i] * b.per_median }))
          .filter((_, i) => b.droite_bpa.annees[i] <= b.annees[b.annees.length - 1]))
    }
    chart.addSeries(LineSeries, { color: couleur('--c-cours'), lineWidth: 1.5, priceLineVisible: false })
      .setData(points(b.cours.jours, b.cours.valeurs))
    chart.timeScale().fitContent()
  }, [analyse, log], valeur.id)

  return (
    <>
      <div ref={conteneur} className="graphique" />
      <div className="legende">
        <span className="legende-item"><span className="legende-trait" style={{ borderColor: 'var(--c-cours)' }} />Cours (hors dividendes)</span>
        <span className="legende-item"><span className="legende-trait" style={{ borderColor: 'var(--ok)' }} />BPA × PER médian</span>
        <span className="legende-item"><span className="legende-trait pointille" style={{ borderColor: 'var(--ok)' }} />BPA × PER min / max</span>
        {b.droite_bpa && <span className="legende-item"><span className="legende-trait pointille" style={{ borderColor: 'var(--c-droite)' }} />Droite du BPA × PER médian</span>}
      </div>
    </>
  )
}
