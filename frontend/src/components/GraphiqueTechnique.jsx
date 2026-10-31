// @ts-check
import { useEffect, useRef } from 'react'
import { CandlestickSeries, HistogramSeries, LineSeries, LineStyle, createSeriesMarkers } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'

const SANS = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }
export const COULEURS_MM = ['#F59E0B', '#8B5CF6', '#0F766E', '#DB2777', '#0891B2', '#65A30D']
const TRACE = '#7C3AED', TRACE_CHOISI = '#DB2777'
const TOLERANCE = 7        // pixels autour d'un trace pour le selectionner

const enTexte = t => typeof t === 'string' ? t
  : `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`

const FUTUR = 0.08          // part du graphique laissee vide a droite, pour voir ou mene une droite de tendance

/** Distance en pixels du point (x, y) a la droite passant par (x1, y1) et (x2, y2). */
function distanceDroite(x, y, droite) {
  const [x1, y1, x2, y2] = droite
  return Math.abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / Math.hypot(x2 - x1, y2 - y1)
}

/**
 * Droites de tendance infinies : dessinees directement sur le panneau du cours, d'un bord a l'autre.
 * Elles ne sont pas des series, donc ni donnees en plus, ni effet sur l'echelle.
 * `pixels(droite)` donne [x1, y1, x2, y2] ou null ; `droites()` la liste a dessiner.
 */
function primitiveDroites(pixels, droites) {
  const rendu = {
    draw(cible) {
      cible.useBitmapCoordinateSpace(({ context, bitmapSize, horizontalPixelRatio: rx, verticalPixelRatio: ry }) => {
        const largeur = bitmapSize.width / rx
        for (const d of droites()) {
          const p = pixels(d)
          if (!p) continue
          const [x1, y1, x2, y2] = p, pente = (y2 - y1) / (x2 - x1)
          context.beginPath()
          context.strokeStyle = d.choisie ? TRACE_CHOISI : TRACE
          context.lineWidth = (d.choisie ? 3 : 2) * ry
          context.moveTo(0, (y1 - x1 * pente) * ry)
          context.lineTo(bitmapSize.width, (y1 + (largeur - x1) * pente) * ry)
          context.stroke()
        }
      })
    },
  }
  return {
    actualiser: null,
    attached({ requestUpdate }) { this.actualiser = requestUpdate },
    detached() { this.actualiser = null },
    updateAllViews() {},
    paneViews() { return [{ renderer: () => rendu }] },
  }
}

/**
 * Cours (bougies ou ligne), moyennes, Bollinger, Ichimoku, annotations ; indicateurs dans des panneaux dessous.
 * `onClic` : un trace est en cours, le clic le place. Sinon, le clic selectionne le trace vise (`onSelection`).
 * Les traces se dessinent sur le graphique deja construit : tracer ou selectionner ne le reconstruit jamais,
 * et ils ne comptent pas dans l'echelle des prix, donc la courbe ne bouge pas.
 */
export default function GraphiqueTechnique({ t, options, annotations = [], onClic, onSelection, selection = null, cle }) {
  const scene = useRef(null)
  const actuels = useRef({ annotations, onClic, onSelection })
  useEffect(() => { actuels.current = { annotations, onClic, onSelection } })

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
    if (options.moyennes) {
      Object.entries(t.moyennes).forEach(([, valeurs], i) => {
        chart.addSeries(LineSeries, { color: COULEURS_MM[i % COULEURS_MM.length], lineWidth: 1.5, ...SANS }).setData(points(jours, valeurs))
      })
    }

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
    panneaux[0]?.setStretchFactor(6)      // indicateurs discrets : le cours garde l'essentiel de la hauteur
    panneaux.slice(1).forEach(p => p.setStretchFactor(1))

    const echelleTemps = chart.timeScale()
    const abscisse = jour => echelleTemps.timeToCoordinate(jours.findLast(j => j <= jour) ?? jours[0])
    const pixels = d => {
      const p = [abscisse(d.t1), principale.priceToCoordinate(d.p1), abscisse(d.t2), principale.priceToCoordinate(d.p2)]
      return p.every(v => v !== null) && p[0] !== p[2] ? p : null
    }
    const s = { chart, principale, marqueurs: createSeriesMarkers(principale, [], { autoScale: false }), niveaux: new Map(), droites: [], notes: [] }
    s.primitive = primitiveDroites(pixels, () => s.droites)
    principale.attachPrimitive(s.primitive)
    scene.current = s

    // Le trace le plus proche du point, dans le panneau du cours.
    const tracePres = ({ x, y }) => {
      let meilleur = null, plusPres = TOLERANCE
      for (const a of actuels.current.annotations) {
        const d = a.donnees
        let distance = Infinity
        if (a.type === 'niveau') distance = Math.abs(y - (principale.priceToCoordinate(d.prix) ?? Infinity))
        if (a.type === 'note') distance = Math.abs(x - (abscisse(d.jour) ?? Infinity))
        if (a.type === 'ligne') {
          const p = pixels(d)
          if (p) distance = distanceDroite(x, y, p)
        }
        if (distance <= plusPres) { meilleur = a; plusPres = distance }
      }
      return meilleur
    }

    chart.subscribeClick(param => {
      if (!param.point) return
      const { onClic: placer, onSelection: choisir } = actuels.current
      if (!placer) {
        choisir?.(param.paneIndex ? null : tracePres(param.point)?.id ?? null)
        return
      }
      if (!param.time) return
      const prix = principale.coordinateToPrice(param.point.y)
      if (prix !== null) placer({ jour: enTexte(param.time), prix: Math.round(prix * 100) / 100 })
    })
    chart.subscribeCrosshairMove(param => {
      const { onClic: placer } = actuels.current
      conteneur.current.style.cursor = placer ? 'crosshair' : param.point && !param.paneIndex && tracePres(param.point) ? 'pointer' : ''
    })

    const fin = jours[jours.length - 1]
    const debut = new Date(fin)
    debut.setFullYear(debut.getFullYear() - ({ jour: 2, semaine: 8, mois: 25 }[t.unite] ?? 2))
    const defaut = { from: debut.toISOString().slice(0, 10), to: fin }
    chart.timeScale().setVisibleRange(defaut)

    return retablie => {
      // Vue calee sur la derniere seance : un peu de vide a droite, pour lire le prolongement des droites.
      // Calcul sur les dates : la fenetre logique n'existe pas encore tant que le graphique n'a pas sa taille.
      const vue = retablie ?? defaut, dernier = jours.length - 1
      if (enTexte(vue.to) < jours[dernier]) return
      const premier = Math.max(0, jours.findIndex(j => j >= enTexte(vue.from)))
      echelleTemps.setVisibleLogicalRange({ from: premier, to: dernier + (dernier - premier) * FUTUR })
    }
  }, [t, options], cle)

  // Niveaux (lignes horizontales), lignes de tendance, notes datees.
  useEffect(() => {
    const s = scene.current
    if (!s) return
    s.niveaux.forEach(l => s.principale.removePriceLine(l))
    s.niveaux.clear(); s.droites = []; s.notes = []
    for (const a of annotations) {
      const d = a.donnees
      if (a.type === 'niveau') s.niveaux.set(a.id, s.principale.createPriceLine({ price: d.prix, color: TRACE, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: d.texte || '' }))
      if (a.type === 'ligne') s.droites.push({ ...d, id: a.id })
      if (a.type === 'note') s.notes.push({ id: a.id, time: d.jour, position: 'aboveBar', shape: 'arrowDown', text: d.texte })
    }
    s.notes.sort((x, y) => x.time.localeCompare(y.time))
  }, [t, options, annotations])

  // Le trace selectionne change de couleur, sur place.
  useEffect(() => {
    const s = scene.current
    if (!s) return
    s.niveaux.forEach((l, id) => { const c = id === selection; l.applyOptions({ color: c ? TRACE_CHOISI : TRACE, lineWidth: c ? 2 : 1, lineStyle: c ? LineStyle.Solid : LineStyle.Dashed }) })
    s.droites.forEach(d => { d.choisie = d.id === selection })
    s.primitive.actualiser?.()
    s.marqueurs.setMarkers(s.notes.map(n => ({ ...n, color: n.id === selection ? TRACE_CHOISI : TRACE })))
  }, [t, options, annotations, selection])

  return <div ref={conteneur} className="graphique haut" style={{ cursor: onClic ? 'crosshair' : undefined }} />
}
