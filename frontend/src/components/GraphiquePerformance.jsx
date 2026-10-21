// @ts-check
import { LineSeries } from 'lightweight-charts'
import { useGraphique, couleur } from '../lib/graphique'

/** Performance cumulee (TWR) du portefeuille et de l'indice de reference, en %. */
export default function GraphiquePerformance({ serie }) {
  const conteneur = useGraphique(chart => {
    const enPct = v => `${v > 0 ? '+' : ''}${(v * 100).toFixed(0)} %`
    chart.applyOptions({ localization: { locale: 'fr-FR', priceFormatter: enPct } })
    const format = { type: 'custom', formatter: enPct }
    const pts = valeurs => serie.jours.map((t, i) => ({ time: t, value: valeurs[i] }))
    chart.addSeries(LineSeries, { color: couleur('--accent'), lineWidth: 2, priceFormat: format }).setData(pts(serie.portefeuille))
    if (serie.reference) {
      chart.addSeries(LineSeries, { color: couleur('--muted'), lineWidth: 1.5, priceFormat: format }).setData(pts(serie.reference))
    }
    chart.timeScale().fitContent()
  }, [serie], 'performance')
  return <div ref={conteneur} className="graphique" style={{ height: 300 }} />
}
