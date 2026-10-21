import { LineSeries } from 'lightweight-charts'
import { useGraphique, echelle } from '../lib/graphique'

export const COULEURS = ['#4F46E5', '#DC2626', '#059669', '#D97706', '#7C3AED', '#0891B2', '#DB2777', '#65A30D', '#6B7280']

/** Plusieurs series sur un meme axe du temps (base 100, force relative…). */
export default function GraphiqueLignes({ jours, series, log = false, cle, hauteur = 380 }) {
  const conteneur = useGraphique(chart => {
    chart.priceScale('right').applyOptions(echelle(log))
    series.forEach((s, i) => {
      chart.addSeries(LineSeries, { color: s.couleur ?? COULEURS[i % COULEURS.length], lineWidth: s.epaisseur ?? 2, title: s.nom,
                                    lineStyle: s.pointille ? 2 : 0, priceLineVisible: false })
        .setData(jours.map((t, j) => ({ time: t, value: s.valeurs[j] })).filter(p => p.value != null))
    })
    chart.timeScale().fitContent()
  }, [jours, series, log], cle)
  return <div ref={conteneur} className="graphique" style={{ height: hauteur }} />
}
