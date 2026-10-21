import { CandlestickSeries, HistogramSeries, LineSeries, LineStyle, createSeriesMarkers } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'

const SANS = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }
export const COULEURS_MM = ['#F59E0B', '#8B5CF6', '#0F766E', '#DB2777', '#0891B2', '#65A30D']

const enTexte = t => typeof t === 'string' ? t
  : `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`

/** Cours (bougies ou ligne), moyennes, Bollinger, Ichimoku, annotations ; indicateurs dans des panneaux dessous. */
export default function GraphiqueTechnique({ t, options, annotations = [], onClic, cle }) {
  const conteneur = useGraphique(chart => {
    const { jours } = t
    const vert = couleur('--ok'), rouge = couleur('--danger')
    chart.priceScale('right').applyOptions(echelle(options.log))

    let principale
    if (options.bougies && t.haut.some(v => v !== null)) {
      const bougies = []
      for (let i = 0; i < jours.length; i++) {
        const c = t.cloture[i]
        if (c === null) continue
        const o = t.ouverture[i] ?? c
        bougies.push({ time: jours[i], open: o, high: t.haut[i] ?? Math.max(o, c), low: t.bas[i] ?? Math.min(o, c), close: c })
      }
      principale = chart.addSeries(CandlestickSeries, { upColor: vert, downColor: rouge, borderVisible: false, wickUpColor: vert, wickDownColor: rouge })
      principale.setData(bougies)
    } else {
      principale = chart.addSeries(LineSeries, { color: couleur('--c-cours'), lineWidth: 1.5 })
      principale.setData(points(jours, t.cloture))
    }

    if (options.bollinger) {
      for (const cleB of ['bollinger_haut', 'bollinger_bas']) {
        chart.addSeries(LineSeries, { color: '#94A3B8', lineWidth: 1, lineStyle: LineStyle.Dashed, ...SANS }).setData(points(jours, t[cleB]))
      }
    }
    if (options.ichimoku) {
      // Le nuage est projete de 26 periodes vers l'avant : on decale les valeurs sur l'axe.
      const decale = valeurs => jours.map((j, i) => ({ time: j, value: valeurs[i - 26] })).filter(p => p.value != null)
      chart.addSeries(LineSeries, { color: alpha('#059669', 0.7), lineWidth: 1, ...SANS }).setData(decale(t.ichimoku.senkou_a))
      chart.addSeries(LineSeries, { color: alpha('#DC2626', 0.7), lineWidth: 1, ...SANS }).setData(decale(t.ichimoku.senkou_b))
      chart.addSeries(LineSeries, { color: '#2563EB', lineWidth: 1, ...SANS }).setData(points(jours, t.ichimoku.tenkan))
      chart.addSeries(LineSeries, { color: '#9333EA', lineWidth: 1, ...SANS }).setData(points(jours, t.ichimoku.kijun))
    }
    Object.entries(t.moyennes).forEach(([, valeurs], i) => {
      chart.addSeries(LineSeries, { color: COULEURS_MM[i % COULEURS_MM.length], lineWidth: 1.5, ...SANS }).setData(points(jours, valeurs))
    })

    // Annotations : niveaux (lignes horizontales), lignes de tendance, notes datees.
    const notes = []
    for (const a of annotations) {
      const d = a.donnees
      if (a.type === 'niveau') principale.createPriceLine({ price: d.prix, color: '#7C3AED', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: d.texte || '' })
      if (a.type === 'ligne') {
        const [p1, p2] = [{ time: d.t1, value: d.p1 }, { time: d.t2, value: d.p2 }].sort((x, y) => x.time.localeCompare(y.time))
        if (p1.time !== p2.time) chart.addSeries(LineSeries, { color: '#7C3AED', lineWidth: 2, ...SANS }).setData([p1, p2])
      }
      if (a.type === 'note') notes.push({ time: d.jour, position: 'aboveBar', color: '#7C3AED', shape: 'arrowDown', text: d.texte })
    }
    if (notes.length) createSeriesMarkers(principale, notes.sort((x, y) => x.time.localeCompare(y.time)))

    if (options.volume && t.volume.some(v => v)) {
      const volume = chart.addSeries(HistogramSeries, { priceScaleId: 'volume', priceFormat: { type: 'volume' }, ...SANS })
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
      volume.setData(jours.map((j, i) => ({ time: j, value: t.volume[i] ?? 0,
        color: (t.cloture[i] ?? 0) >= (t.cloture[i - 1] ?? 0) ? alpha(vert, 0.35) : alpha(rouge, 0.35) })))
    }

    let panneau = 1
    const ajouter = (series, niveaux = []) => {
      series.forEach(([valeurs, coul, type]) => {
        const s = chart.addSeries(type === 'histo' ? HistogramSeries : LineSeries, { color: coul, lineWidth: 1.5, ...SANS, lastValueVisible: true }, panneau)
        s.setData(type === 'histo'
          ? jours.map((j, i) => valeurs[i] === null ? { time: j } : { time: j, value: valeurs[i], color: valeurs[i] >= 0 ? alpha(vert, 0.6) : alpha(rouge, 0.6) })
          : points(jours, valeurs))
        niveaux.forEach(n => s.createPriceLine({ price: n, color: '#9CA3AF', lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true }))
        niveaux = []
      })
      panneau++
    }
    if (options.rsi) ajouter([[t.rsi, '#7C3AED']], [70, 30])
    if (options.macd) ajouter([[t.macd_histogramme, null, 'histo'], [t.macd, couleur('--c-cours')], [t.macd_signal, '#F97316']])
    if (options.stochastique) ajouter([[t.stochastique_k, '#0891B2'], [t.stochastique_d, '#F97316']], [80, 20])
    if (options.adx) ajouter([[t.adx, '#111827'], [t.di_plus, vert], [t.di_moins, rouge]], [25])
    if (options.atr) ajouter([[t.atr, '#DB2777']])
    if (options.obv) ajouter([[t.obv, '#65A30D']])

    const panneaux = chart.panes()
    panneaux[0]?.setStretchFactor(3)
    panneaux.slice(1).forEach(p => p.setStretchFactor(1))

    if (onClic) {
      chart.subscribeClick(param => {
        if (!param.time || !param.point) return
        const prix = principale.coordinateToPrice(param.point.y)
        if (prix !== null) onClic({ jour: enTexte(param.time), prix: Math.round(prix * 100) / 100 })
      })
    }

    const fin = jours[jours.length - 1]
    const debut = new Date(fin)
    debut.setFullYear(debut.getFullYear() - ({ jour: 2, semaine: 8, mois: 25 }[t.unite] ?? 2))
    chart.timeScale().setVisibleRange({ from: debut.toISOString().slice(0, 10), to: fin })
  }, [t, options, annotations, onClic], cle)

  return <div ref={conteneur} className="graphique haut" style={{ cursor: onClic ? 'crosshair' : undefined }} />
}
