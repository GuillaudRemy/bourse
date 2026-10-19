import { useEffect, useRef } from 'react'
import { createChart, PriceScaleMode, CrosshairMode } from 'lightweight-charts'

const css = nom => getComputedStyle(document.documentElement).getPropertyValue(nom).trim()

const FORMAT = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 })

/** Options communes a tous les graphiques, lues dans les tokens CSS. */
export function optionsCommunes() {
  return {
    autoSize: true,
    layout: {
      background: { color: css('--surface') },
      textColor: css('--muted'),
      fontFamily: css('--f-mono'),
      fontSize: 11,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: '#F2F3F5' },
      horzLines: { color: '#F2F3F5' },
    },
    rightPriceScale: { borderColor: css('--border') },
    timeScale: { borderColor: css('--border'), minBarSpacing: 0.05 },
    crosshair: { mode: CrosshairMode.Normal },
    localization: { locale: 'fr-FR', priceFormatter: p => FORMAT.format(p) },
  }
}

export const couleur = css

/** '#DC2626', 0.5 -> 'rgba(220, 38, 38, 0.5)' */
export function alpha(hex, a) {
  const n = parseInt(hex.replace('#', ''), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}

/** Serie {jours, valeurs} -> points du graphique, sans les trous. */
export function points(jours, valeurs) {
  const resultat = []
  for (let i = 0; i < jours.length; i++) {
    if (valeurs[i] !== null && valeurs[i] !== undefined) resultat.push({ time: jours[i], value: valeurs[i] })
  }
  return resultat
}

export const echelle = log => ({ mode: log ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal })

/**
 * Cree le graphique dans `conteneur` avec `construire(chart)`, et le reconstruit
 * quand `deps` changent. La fenetre de temps visible est conservee d'une
 * reconstruction a l'autre, sauf si `cle` change (autre valeur affichee).
 */
export function useGraphique(construire, deps, cle) {
  const conteneur = useRef(null)
  const fenetre = useRef(null)
  const derniereCle = useRef(cle)

  useEffect(() => {
    if (!conteneur.current) return
    if (derniereCle.current !== cle) { fenetre.current = null; derniereCle.current = cle }

    const chart = createChart(conteneur.current, optionsCommunes())
    construire(chart)   // fixe aussi la fenetre par defaut
    if (fenetre.current) {
      try { chart.timeScale().setVisibleRange(fenetre.current) } catch { /* plage hors donnees */ }
    }
    // La fenetre n'est memorisee qu'une fois le graphique affiche : le double montage
    // du mode strict de React la lirait avant que la fenetre par defaut soit appliquee.
    let affiche = false
    const image = requestAnimationFrame(() => { affiche = true })
    return () => {
      cancelAnimationFrame(image)
      if (affiche) fenetre.current = chart.timeScale().getVisibleRange()
      chart.remove()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return conteneur
}
