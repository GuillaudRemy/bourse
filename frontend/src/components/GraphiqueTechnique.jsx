// @ts-check
import { useEffect, useRef } from 'react'
import { CandlestickSeries, HistogramSeries, LineSeries, LineStyle, createSeriesMarkers } from 'lightweight-charts'
import { useGraphique, points, echelle, couleur, alpha } from '../lib/graphique'
import { NB_POINTS, TRACE, TRACE_CHOISI, barresFutures, deplacer, donneesDe, primitiveTraces, repere, texteMesure, viser } from '../lib/traces'

const SANS = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }
export const COULEURS_MM = ['#F59E0B', '#8B5CF6', '#0F766E', '#DB2777', '#0891B2', '#65A30D']

const enTexte = t => typeof t === 'string' ? t
  : `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`

const FUTUR = 0.08          // part du graphique laissee vide a droite, pour voir ou menent les traces
const BARRES_FUTURES = { jour: 260, semaine: 104, mois: 36 }      // un a trois ans d'axe apres la derniere seance

/**
 * Cours (bougies ou ligne), moyennes, Bollinger, Ichimoku, traces ; indicateurs dans des panneaux dessous.
 *
 * Traces : avec un `mode` (outil choisi), chaque clic pose un point ; quand il y en a assez, `onPlacer(type, points)`
 * (ou, pour la mesure, `onMesure(texte)`), et `onEtape(n)` entre-temps. Sans mode, un clic sur un trace le selectionne
 * (`onSelection`) et le glisser le deplace (`onDeplacer(id, donnees)`), en entier ou par une extremite.
 * Les traces se dessinent sur le graphique deja construit et ne comptent pas dans l'echelle : la courbe ne bouge pas.
 */
export default function GraphiqueTechnique({ t, options, annotations = [], mode = null, selection = null,
                                             onPlacer, onEtape, onMesure, onSelection, onDeplacer, cle }) {
  const scene = useRef(null)
  const actuels = useRef({ annotations, mode, selection, onPlacer, onEtape, onMesure, onSelection, onDeplacer })
  useEffect(() => { actuels.current = { annotations, mode, selection, onPlacer, onEtape, onMesure, onSelection, onDeplacer } })

  /** Remet le dessin en accord avec les traces (et le brouillon d'un deplacement en cours). */
  const peindre = () => {
    const s = scene.current
    if (!s) return
    const { annotations: liste, selection: choisi, mode: outil } = actuels.current
    s.liste = liste.map(a => s.brouillon.has(a.id) ? { ...a, donnees: s.brouillon.get(a.id) } : a)
    s.choisi = choisi
    const vus = new Set()
    for (const a of s.liste.filter(x => x.type === 'niveau')) {
      vus.add(a.id)
      const c = a.id === choisi
      const reglage = { price: a.donnees.prix, color: c ? TRACE_CHOISI : TRACE, lineWidth: c ? 2 : 1,
                        lineStyle: c ? LineStyle.Solid : LineStyle.Dashed, axisLabelVisible: true, title: a.donnees.texte || '' }
      const ligne = s.niveaux.get(a.id)
      if (ligne) ligne.applyOptions(reglage)
      else s.niveaux.set(a.id, s.principale.createPriceLine(reglage))
    }
    for (const [id, ligne] of s.niveaux) if (!vus.has(id)) { s.principale.removePriceLine(ligne); s.niveaux.delete(id) }
    s.marqueurs.setMarkers(s.liste.filter(a => a.type === 'note')
      .map(a => ({ time: s.barre(a.donnees.jour), position: 'aboveBar', shape: 'arrowDown', text: a.donnees.texte,
                   color: a.id === choisi ? TRACE_CHOISI : TRACE }))
      .sort((x, y) => x.time.localeCompare(y.time)))
    s.apercu = outil && outil !== 'niveau' && outil !== 'note' && s.points.length && s.curseur
      ? { type: outil, donnees: donneesDe(outil, [...s.points, s.curseur]) } : null
    s.primitive.actualiser?.()
  }

  const conteneur = useGraphique(chart => {
    const { jours } = t
    const futures = barresFutures(jours[jours.length - 1], t.unite, BARRES_FUTURES[t.unite] ?? 260)
    const vides = futures.map(time => ({ time }))      // l'axe du temps continue apres la derniere seance
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
      principale.setData([...bougies, ...vides])
    } else {
      principale = chart.addSeries(LineSeries, { color: couleur('--c-cours'), lineWidth: 1.5 })
      principale.setData([...points(jours, t.cloture), ...vides])
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
    const axe = [...jours, ...futures]
    const indices = new Map(jours.map((j, i) => [j, i]))
    const s = {
      chart, principale, r: repere(echelleTemps, principale, axe),
      marqueurs: createSeriesMarkers(principale, [], { autoScale: false }), niveaux: new Map(),
      liste: [], choisi: null, brouillon: new Map(), points: [], curseur: null, apercu: null, mesure: null,
      // Barre qui porte une note : la derniere a la date de la note ou avant (le futur n'a pas de barre).
      barre: jour => jours.findLast(j => j <= jour) ?? jours[0],
    }
    // Fleche d'une note, pour la saisir a la souris : au-dessus du plus haut de sa barre.
    s.fleche = jour => {
      const b = s.barre(jour), i = indices.get(b), x = echelleTemps.timeToCoordinate(b)
      const y = principale.priceToCoordinate(t.haut[i] ?? t.cloture[i])
      const e = (echelleTemps.logicalToCoordinate(1) ?? 0) - (echelleTemps.logicalToCoordinate(0) ?? 0)
      return x === null || y === null ? null : { x, y, largeur: Math.max(6, e / 2) }
    }
    s.primitive = primitiveTraces(() => s)
    principale.attachPrimitive(s.primitive)
    scene.current = s

    const fin = jours[jours.length - 1]
    const debut = new Date(fin)
    debut.setFullYear(debut.getFullYear() - ({ jour: 2, semaine: 8, mois: 25 }[t.unite] ?? 2))
    const defaut = { from: debut.toISOString().slice(0, 10), to: fin }
    chart.timeScale().setVisibleRange(defaut)

    return retablie => {
      // Vue calee sur la derniere seance : un peu d'avenir a droite, pour lire le prolongement des traces.
      // Calcul sur les dates : la fenetre logique n'existe pas encore tant que le graphique n'a pas sa taille.
      const vue = retablie ?? defaut, dernier = jours.length - 1
      if (enTexte(vue.to) !== jours[dernier]) return
      const premier = Math.max(0, jours.findIndex(j => j >= enTexte(vue.from)))
      echelleTemps.setVisibleLogicalRange({ from: premier, to: dernier + (dernier - premier) * FUTUR })
    }
  }, [t, options], cle)

  useEffect(() => { scene.current?.brouillon.clear() }, [annotations])
  useEffect(() => {
    const s = scene.current
    if (!s) return
    s.points = []; s.curseur = null
    if (mode !== 'mesure') s.mesure = null
  }, [mode])
  useEffect(peindre, [t, options, annotations, selection, mode])

  // Souris : poser les points, selectionner, glisser. Ecoute en phase de capture : quand un trace est saisi,
  // le graphique ne recoit pas l'appui et ne defile pas.
  useEffect(() => {
    const boite = conteneur.current
    if (!boite) return
    let appui = null, glisse = null
    const position = e => {
      const r = boite.getBoundingClientRect(), s = scene.current
      const x = e.clientX - r.left, y = e.clientY - r.top
      const dansCours = s && x <= s.chart.timeScale().width() && y <= (s.chart.panes()[0]?.getHeight() ?? 0)
      return { x, y, dansCours }
    }
    const viserTrace = (x, y) => {
      const s = scene.current
      let meilleur = null
      for (const a of s.liste) {
        const v = viser(a, x, y, s.r, s.fleche)
        if (v && (!meilleur || v.distance < meilleur.distance)) meilleur = { ...v, a }
      }
      return meilleur
    }
    const clic = (x, y) => {
      const s = scene.current, { mode: outil, onSelection: choisir } = actuels.current
      if (!outil) { choisir?.(viserTrace(x, y)?.a.id ?? null); return }
      const q = s.r.point(x, y)
      if (!q) return
      if (outil === 'mesure' && !s.points.length) s.mesure = null
      s.points.push(q)
      if (s.points.length < NB_POINTS[outil]) { actuels.current.onEtape?.(s.points.length); peindre(); return }
      const pts = s.points
      s.points = []; s.curseur = null
      actuels.current.onEtape?.(0)
      if (outil === 'mesure') {
        s.mesure = { type: 'mesure', donnees: donneesDe('mesure', pts) }
        actuels.current.onMesure?.(texteMesure(s.mesure.donnees, s.r.indice))
        peindre()
      } else actuels.current.onPlacer?.(outil, pts)
    }
    const appuyer = e => {
      if (e.button !== 0 || !scene.current) return
      const { x, y, dansCours } = position(e)
      appui = { x, y, dansCours }
      if (!dansCours || actuels.current.mode) return
      const v = viserTrace(x, y)
      if (!v) return
      e.stopPropagation(); e.preventDefault()
      glisse = { a: v.a, partie: v.partie, x0: x, y0: y, bouge: false, donnees: v.a.donnees }
    }
    const bouger = e => {
      const s = scene.current
      if (!s) return
      const { x, y, dansCours } = position(e)
      if (glisse) {
        if (Math.hypot(x - glisse.x0, y - glisse.y0) > 2) glisse.bouge = true
        if (!glisse.bouge) return
        glisse.donnees = deplacer(glisse.a, glisse.partie, x, y, x - glisse.x0, y - glisse.y0, s.r)
        s.brouillon.set(glisse.a.id, glisse.donnees)
        peindre()
        return
      }
      if (e.target instanceof Node && !boite.contains(e.target)) return
      const outil = actuels.current.mode
      if (outil) {
        s.curseur = dansCours ? s.r.point(x, y) : null
        if (s.points.length) peindre()
      }
      const v = !outil && dansCours ? viserTrace(x, y) : null
      boite.style.cursor = outil ? 'crosshair' : v ? (v.partie === 'tout' ? 'move' : 'grab') : ''
    }
    const relacher = e => {
      if (glisse) {
        const { a, bouge, donnees } = glisse
        glisse = null; appui = null
        actuels.current.onSelection?.(a.id)
        if (bouge) actuels.current.onDeplacer?.(a.id, donnees)
        return
      }
      if (!appui) return
      const { x, y } = position(e), depart = appui
      appui = null
      if (Math.hypot(x - depart.x, y - depart.y) > 4) return       // le graphique a defile : pas un clic
      if (depart.dansCours) clic(x, y)
      else if (!actuels.current.mode) actuels.current.onSelection?.(null)
    }
    const sortir = () => { const s = scene.current; if (s?.curseur) { s.curseur = null; peindre() } }
    boite.addEventListener('mousedown', appuyer, true)
    boite.addEventListener('mouseleave', sortir)
    window.addEventListener('mousemove', bouger)
    window.addEventListener('mouseup', relacher)
    return () => {
      boite.removeEventListener('mousedown', appuyer, true)
      boite.removeEventListener('mouseleave', sortir)
      window.removeEventListener('mousemove', bouger)
      window.removeEventListener('mouseup', relacher)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return <div ref={conteneur} className="graphique haut" />
}
