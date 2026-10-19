import { CandlestickSeries, HistogramSeries, LineSeries, LineStyle } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'

const SANS_ETIQUETTE = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }

/** Cours avec moyennes mobiles et Bollinger, puis volume, RSI et MACD dans des panneaux dessous. */
export default function GraphiqueTechnique({ analyse, options }) {
  const { series, indicateurs: ind, valeur } = analyse

  const conteneur = useGraphique(chart => {
    const { jours } = series
    const vert = couleur('--ok'), rouge = couleur('--danger')
    chart.priceScale('right').applyOptions(echelle(options.log))

    // ── Panneau 0 : cours ──
    const ohlc = series.ouverture.some(v => v !== null) && series.haut.some(v => v !== null)
    if (options.bougies && ohlc) {
      const bougies = []
      for (let i = 0; i < jours.length; i++) {
        const c = series.cloture[i]
        if (c === null) continue
        const o = series.ouverture[i] ?? c
        bougies.push({ time: jours[i], open: o, high: series.haut[i] ?? Math.max(o, c), low: series.bas[i] ?? Math.min(o, c), close: c })
      }
      chart.addSeries(CandlestickSeries, {
        upColor: vert, downColor: rouge, borderVisible: false, wickUpColor: vert, wickDownColor: rouge,
      }).setData(bougies)
    } else {
      chart.addSeries(LineSeries, { color: couleur('--c-cours'), lineWidth: 1.5 })
        .setData(points(jours, series.cloture))
    }

    if (options.bollinger) {
      for (const cle of ['bollinger_haut', 'bollinger_bas']) {
        chart.addSeries(LineSeries, { color: '#94A3B8', lineWidth: 1, lineStyle: LineStyle.Dashed, ...SANS_ETIQUETTE })
          .setData(points(jours, ind[cle]))
      }
    }
    for (const [cle, var_] of [['mm20', '--c-mm20'], ['mm50', '--c-mm50'], ['mm200', '--c-mm200']]) {
      if (options[cle]) {
        chart.addSeries(LineSeries, { color: couleur(var_), lineWidth: 1.5, ...SANS_ETIQUETTE })
          .setData(points(jours, ind[cle]))
      }
    }

    if (options.volume && series.volume.some(v => v)) {
      const volume = chart.addSeries(HistogramSeries, {
        priceScaleId: 'volume', priceFormat: { type: 'volume' }, ...SANS_ETIQUETTE,
      })
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
      volume.setData(jours.map((t, i) => ({
        time: t, value: series.volume[i] ?? 0,
        color: (series.cloture[i] ?? 0) >= (series.cloture[i - 1] ?? 0) ? alpha(vert, 0.35) : alpha(rouge, 0.35),
      })))
    }

    // ── Panneau 1 : RSI ──
    let panneau = 1
    if (options.rsi) {
      const rsi = chart.addSeries(LineSeries, { color: '#7C3AED', lineWidth: 1.5, priceLineVisible: false }, panneau)
      rsi.setData(points(jours, ind.rsi))
      for (const niveau of [70, 30]) {
        rsi.createPriceLine({ price: niveau, color: '#9CA3AF', lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true })
      }
      panneau++
    }

    // ── Panneau 2 : MACD ──
    if (options.macd) {
      chart.addSeries(HistogramSeries, { ...SANS_ETIQUETTE }, panneau).setData(
        jours.map((t, i) => ind.macd_histogramme[i] === null ? { time: t } : {
          time: t, value: ind.macd_histogramme[i], color: ind.macd_histogramme[i] >= 0 ? alpha(vert, 0.6) : alpha(rouge, 0.6),
        }),
      )
      chart.addSeries(LineSeries, { color: couleur('--c-cours'), lineWidth: 1.5, ...SANS_ETIQUETTE }, panneau)
        .setData(points(jours, ind.macd))
      chart.addSeries(LineSeries, { color: '#F97316', lineWidth: 1, ...SANS_ETIQUETTE }, panneau)
        .setData(points(jours, ind.macd_signal))
    }

    const panneaux = chart.panes()
    panneaux[0]?.setStretchFactor(3)
    panneaux.slice(1).forEach(p => p.setStretchFactor(1))

    // Par defaut : les deux dernieres annees, lisibles en bougies.
    const fin = jours[jours.length - 1]
    const debut = new Date(fin); debut.setFullYear(debut.getFullYear() - 2)
    chart.timeScale().setVisibleRange({ from: debut.toISOString().slice(0, 10), to: fin })
  }, [analyse, options], valeur.id)

  return (
    <>
      <div ref={conteneur} className="graphique haut" />
      <div className="legende">
        {options.mm20  && <Trait couleur="var(--c-mm20)"  texte="MM20" />}
        {options.mm50  && <Trait couleur="var(--c-mm50)"  texte="MM50" />}
        {options.mm200 && <Trait couleur="var(--c-mm200)" texte="MM200" />}
        {options.bollinger && <Trait couleur="#94A3B8" texte="Bollinger (20, 2)" pointille />}
        {options.rsi  && <Trait couleur="#7C3AED" texte="RSI 14 (70 / 30)" />}
        {options.macd && <Trait couleur="var(--c-cours)" texte="MACD (12, 26)" />}
        {options.macd && <Trait couleur="#F97316" texte="Signal (9)" />}
      </div>
    </>
  )
}

function Trait({ couleur, texte, pointille }) {
  return (
    <span className="legende-item">
      <span className={`legende-trait${pointille ? ' pointille' : ''}`} style={{ borderColor: couleur }} />
      {texte}
    </span>
  )
}
