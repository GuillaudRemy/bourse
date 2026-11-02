// @ts-check
/**
 * Traces de l'analyse technique : correspondance dates <-> pixels, dessin, selection et deplacement.
 *
 * Un trace est stocke en dates et en prix, jamais en barres : il reste au meme endroit quelle que soit
 * l'unite de temps (jour, semaine, mois). Une date tombant entre deux barres est interpolee ; au-dela de
 * la derniere seance, l'axe est prolonge par des barres vides (seances, vendredis ou fins de mois).
 */

/** Points a cliquer pour chaque outil. La mesure n'est pas enregistree. */
export const NB_POINTS = { niveau: 1, note: 1, ligne: 2, fibo: 2, rectangle: 2, mesure: 2, canal: 3 }
export const FIBO = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
export const TRACE = '#7C3AED', TRACE_CHOISI = '#DB2777'
export const TOLERANCE = 7      // pixels autour d'un trace pour le saisir
const POIGNEE = 9               // pixels autour d'une extremite pour la deplacer seule

const JOUR = 864e5
const enJours = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / JOUR
const enDate = n => new Date(Math.round(n) * JOUR).toISOString().slice(0, 10)
const arrondi = p => Number(p.toPrecision(6))
const FORMAT = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 })

/** Dates des barres a venir apres `dernier` : seances (lundi-vendredi), vendredis ou fins de mois. */
export function barresFutures(dernier, unite, combien) {
  const resultat = []
  let d = new Date(enJours(dernier) * JOUR)
  while (resultat.length < combien) {
    d = unite === 'mois' ? new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 2, 0))
      : new Date(d.getTime() + (unite === 'semaine' ? 7 : 1) * JOUR)
    if (unite === 'jour' && (d.getUTCDay() === 0 || d.getUTCDay() === 6)) continue
    resultat.push(d.toISOString().slice(0, 10))
  }
  return resultat
}

/** Date <-> indice de barre fractionnaire, sur `axe` (dates triees des barres, futur compris). */
export function axeTemps(axe) {
  const n = axe.map(enJours), der = n.length - 1
  const pasDebut = der > 0 ? n[1] - n[0] : 1, pasFin = der > 0 ? n[der] - n[der - 1] : 1
  const indice = date => {
    const j = enJours(date)
    if (j <= n[0]) return (j - n[0]) / pasDebut
    if (j >= n[der]) return der + (j - n[der]) / pasFin
    let bas = 0, haut = der
    while (haut - bas > 1) { const m = (bas + haut) >> 1; if (n[m] <= j) bas = m; else haut = m }
    return bas + (j - n[bas]) / (n[haut] - n[bas])
  }
  const date = l => {
    if (l <= 0) return enDate(n[0] + l * pasDebut)
    if (l >= der) return enDate(n[der] + (l - der) * pasFin)
    const i = Math.floor(l)
    return enDate(n[i] + (l - i) * (n[i + 1] - n[i]))
  }
  return { indice, date }
}

/**
 * Repere du panneau du cours : date -> x, prix -> y, et (x, y) -> { t, p }.
 * La bibliotheque ne convertit que des barres entieres : l'entre-deux est interpole ici.
 */
export function repere(echelleTemps, serie, axe) {
  const { indice, date } = axeTemps(axe)
  const ecart = () => {
    const a = echelleTemps.logicalToCoordinate(0), b = echelleTemps.logicalToCoordinate(1)
    return a === null || b === null ? null : b - a
  }
  const xIndice = l => {
    const base = Math.floor(l), x = echelleTemps.logicalToCoordinate(base), e = ecart()
    return x === null || e === null ? null : x + (l - base) * e
  }
  return {
    indice,
    x: t => xIndice(indice(t)),
    y: p => serie.priceToCoordinate(p),
    point: (x, y) => {
      const l = echelleTemps.coordinateToLogical(x), p = serie.coordinateToPrice(y)
      const xl = l === null ? null : echelleTemps.logicalToCoordinate(l), e = ecart()
      if (l === null || p === null || xl === null || !e) return null
      return { t: date(l + (x - xl) / e), p: arrondi(p) }
    },
  }
}

/** Donnees d'un trace a partir des points cliques (les derniers peuvent manquer, pour l'apercu). */
export function donneesDe(type, points) {
  const [a, b, c] = points
  if (type === 'niveau') return { prix: a.p }
  if (type === 'note') return { jour: a.t }
  const d = { t1: a.t, p1: a.p, t2: (b ?? a).t, p2: (b ?? a).p }
  return type === 'canal' && c ? { ...d, t3: c.t, p3: c.p } : d
}

export const niveauFibo = (d, r) => d.p2 - (d.p2 - d.p1) * r

/** « +12,3 % · 45 séances · 63 jours » entre les deux points d'une mesure. */
export function texteMesure(d, indice) {
  const variation = d.p2 / d.p1 - 1
  const seances = Math.round(Math.abs(indice(d.t2) - indice(d.t1)))
  const jours = Math.round(Math.abs(enJours(d.t2) - enJours(d.t1)))
  const pct = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1, signDisplay: 'exceptZero' }).format(variation * 100)
  return `${pct} % · ${seances} barre${seances > 1 ? 's' : ''} · ${jours} jour${jours > 1 ? 's' : ''}`
}

/** Distance de (x, y) a la droite passant par les points a et b ([x, y]). */
function distanceDroite(x, y, a, b) {
  const [x1, y1] = a, [x2, y2] = b
  return x1 === x2 && y1 === y2 ? Math.hypot(x - x1, y - y1) : Math.abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / Math.hypot(x2 - x1, y2 - y1)
}

/** Extremites deplacables d'un trace, en pixels, avec la facon de les mettre a jour. */
function poignees(a, r) {
  const d = a.donnees, liste = []
  const ajouter = (t, p, maj) => {
    const x = r.x(t), y = r.y(p)
    if (x !== null && y !== null) liste.push({ x, y, maj })
  }
  if (['ligne', 'fibo', 'canal', 'rectangle', 'mesure'].includes(a.type)) {
    ajouter(d.t1, d.p1, q => ({ ...d, t1: q.t, p1: q.p }))
    ajouter(d.t2, d.p2, q => ({ ...d, t2: q.t, p2: q.p }))
  }
  if (a.type === 'canal' && d.t3) ajouter(d.t3, d.p3, q => ({ ...d, t3: q.t, p3: q.p }))
  if (a.type === 'rectangle') {
    ajouter(d.t1, d.p2, q => ({ ...d, t1: q.t, p2: q.p }))
    ajouter(d.t2, d.p1, q => ({ ...d, t2: q.t, p1: q.p }))
  }
  return liste
}

/**
 * Ce que vise le point (x, y) sur le trace `a` : une extremite (pour la deplacer seule), le trace entier,
 * ou rien. `note(jour)` donne { x, y, largeur } de la fleche d'une note.
 */
export function viser(a, x, y, r, note) {
  const d = a.donnees
  const extremite = poignees(a, r).find(p => Math.hypot(x - p.x, y - p.y) <= POIGNEE)
  if (extremite) return { partie: extremite, distance: 0 }
  const P = poignees(a, r).map(p => [p.x, p.y])
  let distance = Infinity
  if (a.type === 'niveau') distance = Math.abs(y - (r.y(d.prix) ?? Infinity))
  if (a.type === 'ligne' && P.length === 2) distance = distanceDroite(x, y, P[0], P[1])
  if (a.type === 'canal' && P.length === 3) {
    const parallele = [P[2][0] + P[1][0] - P[0][0], P[2][1] + P[1][1] - P[0][1]]
    distance = Math.min(distanceDroite(x, y, P[0], P[1]), distanceDroite(x, y, P[2], parallele))
  }
  if (a.type === 'fibo' && P.length === 2 && x >= Math.min(P[0][0], P[1][0]) - TOLERANCE) {
    distance = Math.min(...FIBO.map(n => Math.abs(y - (r.y(niveauFibo(d, n)) ?? Infinity))))
  }
  if (a.type === 'rectangle' && P.length >= 2) {
    const [x1, x2] = [P[0][0], P[1][0]].sort((u, v) => u - v), [y1, y2] = [P[0][1], P[1][1]].sort((u, v) => u - v)
    if (x >= x1 - TOLERANCE && x <= x2 + TOLERANCE && y >= y1 - TOLERANCE && y <= y2 + TOLERANCE) distance = 0
  }
  if (a.type === 'note') {
    const f = note(d.jour)
    if (f && Math.abs(x - f.x) <= f.largeur && y >= f.y - 40 && y <= f.y + 4) distance = 0
  }
  return distance <= TOLERANCE ? { partie: 'tout', distance } : null
}

/** Nouvelles donnees du trace saisi par `partie`, la souris etant en (x, y) apres un deplacement de (dx, dy). */
export function deplacer(a, partie, x, y, dx, dy, r) {
  const d = a.donnees
  if (partie !== 'tout') {
    const q = r.point(x, y)
    return q ? partie.maj(q) : d
  }
  if (a.type === 'niveau') {
    const y0 = r.y(d.prix), q = y0 === null ? null : r.point(0, y0 + dy)
    return q ? { ...d, prix: q.p } : d
  }
  if (a.type === 'note') {
    const x0 = r.x(d.jour), q = x0 === null ? null : r.point(x0 + dx, 0)
    return q ? { ...d, jour: q.t } : d
  }
  const resultat = { ...d }
  for (const [kt, kp] of [['t1', 'p1'], ['t2', 'p2'], ['t3', 'p3']]) {
    if (!d[kt]) continue
    const x0 = r.x(d[kt]), y0 = r.y(d[kp]), q = x0 === null || y0 === null ? null : r.point(x0 + dx, y0 + dy)
    if (!q) return d
    resultat[kt] = q.t
    resultat[kp] = q.p
  }
  return resultat
}

/**
 * Primitive de la bibliotheque : dessine droites, canaux, Fibonacci, rectangles, la mesure et l'apercu du trace
 * en cours, sur le panneau du cours. Les niveaux et les notes, eux, sont des lignes de prix et des marqueurs.
 * `etat()` renvoie { r, liste, choisi, apercu, mesure }.
 */
export function primitiveTraces(etat) {
  const rendu = {
    draw(cible) {
      cible.useBitmapCoordinateSpace(({ context: c, bitmapSize, horizontalPixelRatio: rx, verticalPixelRatio: ry }) => {
        const { r, liste, choisi, apercu, mesure } = etat()
        const largeur = bitmapSize.width / rx
        const g = {
          trait(x1, y1, x2, y2, couleur, epaisseur = 2, tirets = false) {
            c.beginPath(); c.strokeStyle = couleur; c.lineWidth = epaisseur * ry
            c.setLineDash(tirets ? [5 * rx, 4 * rx] : [])
            c.moveTo(x1 * rx, y1 * ry); c.lineTo(x2 * rx, y2 * ry); c.stroke(); c.setLineDash([])
          },
          droite(a, b, couleur, epaisseur) {
            const [x1, y1] = a, [x2, y2] = b
            if (x1 === x2) { g.trait(x1, -1e4, x1, 1e4, couleur, epaisseur); return }
            const pente = (y2 - y1) / (x2 - x1)
            g.trait(0, y1 - x1 * pente, largeur, y1 + (largeur - x1) * pente, couleur, epaisseur)
          },
          texte(texte, x, y, couleur, fond = null) {
            c.font = `${12 * ry}px Inter, system-ui, sans-serif`
            if (fond) {
              const l = c.measureText(texte).width
              c.fillStyle = fond; c.fillRect(x * rx - 4 * rx, (y - 14) * ry, l + 8 * rx, 19 * ry)
            }
            c.fillStyle = couleur; c.fillText(texte, x * rx, y * ry)
          },
          poignee(x, y, couleur) {
            c.fillStyle = '#fff'; c.strokeStyle = couleur; c.lineWidth = 1.5 * ry
            c.fillRect((x - 4) * rx, (y - 4) * ry, 8 * rx, 8 * ry); c.strokeRect((x - 4) * rx, (y - 4) * ry, 8 * rx, 8 * ry)
          },
        }
        const elements = [...liste.map(a => [a, a.id === choisi]), ...(apercu ? [[apercu, true]] : []), ...(mesure ? [[mesure, false]] : [])]
        for (const [a, estChoisi] of elements) {
          if (a.type === 'niveau' || a.type === 'note') continue
          const couleur = estChoisi ? TRACE_CHOISI : TRACE, d = a.donnees
          const P = [[d.t1, d.p1], [d.t2, d.p2], [d.t3, d.p3]].filter(([t]) => t)
            .map(([t, p]) => [r.x(t), r.y(p)]).filter(([x, y]) => x !== null && y !== null)
          if (P.length < 2) continue
          if (a.type === 'ligne') g.droite(P[0], P[1], couleur, estChoisi ? 3 : 2)
          if (a.type === 'canal') {
            g.droite(P[0], P[1], couleur, estChoisi ? 3 : 2)
            if (P[2] && P[0][0] !== P[1][0]) {
              const pente = (P[1][1] - P[0][1]) / (P[1][0] - P[0][0]), decalage = P[2][1] - (P[0][1] + (P[2][0] - P[0][0]) * pente)
              g.droite([P[0][0], P[0][1] + decalage], [P[1][0], P[1][1] + decalage], couleur, estChoisi ? 3 : 2)
              const y0 = P[0][1] - P[0][0] * pente, y1 = y0 + largeur * pente
              c.beginPath(); c.fillStyle = couleur + '14'
              c.moveTo(0, y0 * ry); c.lineTo(largeur * rx, y1 * ry); c.lineTo(largeur * rx, (y1 + decalage) * ry); c.lineTo(0, (y0 + decalage) * ry)
              c.fill()
            }
          }
          if (a.type === 'fibo') {
            const x0 = Math.min(P[0][0], P[1][0])
            g.trait(P[0][0], P[0][1], P[1][0], P[1][1], couleur, 1, true)
            for (const n of FIBO) {
              const prix = niveauFibo(d, n), y = r.y(prix)
              if (y === null) continue
              g.trait(x0, y, largeur, y, couleur, n === 0 || n === 1 ? 1.5 : 1)
              g.texte(`${FORMAT.format(n * 100)} % · ${FORMAT.format(prix)}`, x0 + 4, y - 4, couleur)
            }
          }
          if (a.type === 'rectangle') {
            const [x1, x2] = [P[0][0], P[1][0]], [y1, y2] = [P[0][1], P[1][1]]
            c.fillStyle = couleur + '1A'; c.fillRect(Math.min(x1, x2) * rx, Math.min(y1, y2) * ry, Math.abs(x2 - x1) * rx, Math.abs(y2 - y1) * ry)
            c.strokeStyle = couleur; c.lineWidth = (estChoisi ? 2 : 1.5) * ry
            c.strokeRect(Math.min(x1, x2) * rx, Math.min(y1, y2) * ry, Math.abs(x2 - x1) * rx, Math.abs(y2 - y1) * ry)
          }
          if (a.type === 'mesure') {
            const hausse = d.p2 >= d.p1, teinte = hausse ? '#059669' : '#DC2626'
            const [x1, x2] = [P[0][0], P[1][0]], [y1, y2] = [P[0][1], P[1][1]]
            c.fillStyle = teinte + '1F'; c.fillRect(Math.min(x1, x2) * rx, Math.min(y1, y2) * ry, Math.abs(x2 - x1) * rx, Math.abs(y2 - y1) * ry)
            g.trait(x1, y1, x2, y2, teinte, 1.5)
            g.texte(texteMesure(d, r.indice), Math.min(x1, x2) + 6, Math.min(y1, y2) - 8, '#fff', teinte)
          }
          if (estChoisi && a !== apercu) for (const p of poignees(a, r)) g.poignee(p.x, p.y, couleur)
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
