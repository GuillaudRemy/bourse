// @ts-check
// Preferences d'affichage, propres a cet ordinateur : theme et taille du texte.
const CLE = 'bourse.apparence'
export const THEMES = { auto: 'Automatique', clair: 'Clair', sombre: 'Sombre' }
export const TAILLES = { normal: ['Normale', 1], grand: ['Grande', 1.12], tres_grand: ['Très grande', 1.25] }

export function lire() {
  try { return { theme: 'auto', taille: 'normal', ...JSON.parse(localStorage.getItem(CLE) || '{}') } }
  catch { return { theme: 'auto', taille: 'normal' } }
}

const sombreSysteme = () => window.matchMedia?.('(prefers-color-scheme: dark)').matches

export function appliquer(preferences = lire()) {
  const theme = preferences.theme === 'auto' ? (sombreSysteme() ? 'sombre' : 'clair') : preferences.theme
  const racine = document.documentElement
  const avant = racine.dataset.theme
  racine.dataset.theme = theme
  // Le zoom agrandit tout (texte, graphiques, boutons) en gardant les proportions.
  racine.style.zoom = String(TAILLES[preferences.taille]?.[1] ?? 1)
  if (avant && avant !== theme) window.dispatchEvent(new Event('bourse-theme'))
}

export function enregistrer(preferences) {
  try { localStorage.setItem(CLE, JSON.stringify(preferences)) } catch { /* stockage indisponible */ }
  appliquer(preferences)
  window.dispatchEvent(new Event('bourse-apparence'))
}

export function initialiser() {
  appliquer()
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => appliquer())
}
