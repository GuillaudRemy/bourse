// @ts-check
import { LineSeries, LineStyle } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'

/** Cours (bleu) autour de sa droite de regression (rouge) et du couloir a ±1 et ±2 ecarts-types. */
export default function GraphiqueRegression({ analyse, log, afficherCone = false }) {
  const { series, regression, base_ajustee, valeur } = analyse

  const conteneur = useGraphique(chart => {
    chart.priceScale('right').applyOptions(echelle(log))
    const rouge = couleur('--c-droite')
    // Au-dela de 10 ans de seances : un point par semaine (graphique plus leger, rendu identique).
    const reduit = series.jours.length > 2600
    // Les cours gardes tombent sur les memes dates que les points de la droite (un tous les 5 jours
    // de bourse) : l'axe du temps, qui avance d'un cran par point, reste alors regulier.
    const datesDroite = new Set(regression.droite.jours)
    const garder = (j, i, tab) => !reduit || i === tab.length - 1
      || (j < regression.debut ? i % 5 === 0 : datesDroite.has(series.jours[i]))
    const jours = series.jours.filter((j, i, tab) => garder(j, i, tab))
    const prixCours = (base_ajustee ? series.ajuste : series.cloture).filter((_, i, tab) => garder(series.jours[i], i, tab))
    // La projection de la droite est quotidienne : on l'echantillonne comme les cours pour un axe regulier.
    const dernierJour = series.jours[series.jours.length - 1]
    const indexFutur = regression.droite.jours.findIndex(j => j > dernierJour)
    const droite = Object.fromEntries(Object.entries(regression.droite).map(([cle, valeurs]) => [cle,
      valeurs.filter((_, i) => indexFutur < 0 || i < indexFutur || !reduit || (i - indexFutur) % 5 === 0)]))

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
      .setData(points(jours, prixCours))

    // Cone de projection (90 % et 50 % des trajectoires simulees), a partir du dernier cours.
    const cone = analyse.projection?.cone
    if (cone && afficherCone) {
      const gris = couleur('--muted')
      const depart = regression.dernier
      // Le cone est mensuel : on l'interpole (en logarithme) aux dates de la projection de la droite,
      // pour qu'il avance au meme rythme que le reste du graphique.
      const t = j => new Date(j).getTime()
      const futur = droite.jours.filter(j => j > dernierJour && j <= cone.jours[cone.jours.length - 1])
      const interpoler = (valeurs, j) => {
        const x = t(j)
        if (x <= t(cone.jours[0])) return Math.exp(Math.log(valeurs[0]) * (x - t(dernierJour)) / (t(cone.jours[0]) - t(dernierJour)))
        const k = cone.jours.findIndex(c => t(c) >= x)
        const [a, b] = [t(cone.jours[k - 1]), t(cone.jours[k])]
        return Math.exp(Math.log(valeurs[k - 1]) + (Math.log(valeurs[k]) - Math.log(valeurs[k - 1])) * (x - a) / (b - a))
      }
      for (const [cle, opacite, style] of [['p5', 0.5, LineStyle.Dotted], ['p95', 0.5, LineStyle.Dotted],
                                           ['p25', 0.8, LineStyle.Dashed], ['p75', 0.8, LineStyle.Dashed], ['p50', 0.9, LineStyle.Solid]]) {
        chart.addSeries(LineSeries, { color: alpha(gris, opacite), lineWidth: 1, lineStyle: style,
                                      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
          .setData([{ time: dernierJour, value: depart }, ...futur.map(j => ({ time: j, value: depart * interpoler(cone[cle], j) }))])
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
