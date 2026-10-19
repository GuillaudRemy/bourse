const nf = (min, max) => new Intl.NumberFormat('fr-FR', { minimumFractionDigits: min, maximumFractionDigits: max })
const N0 = nf(0, 0), N1 = nf(1, 1), N2 = nf(2, 2)

const absent = v => v === null || v === undefined || Number.isNaN(v)

export function pct(v, { signe = false, decimales = 1 } = {}) {
  if (absent(v)) return '—'
  const texte = (decimales === 0 ? N0 : decimales === 2 ? N2 : N1).format(v * 100) + ' %'
  return signe && v > 0 ? '+' + texte : texte
}

export function nombre(v, decimales = 2) {
  if (absent(v)) return '—'
  return (decimales === 0 ? N0 : decimales === 1 ? N1 : N2).format(v)
}

export function prix(v, devise) {
  if (absent(v)) return '—'
  const texte = (Math.abs(v) >= 1000 ? N0 : N2).format(v)
  return devise ? `${texte} ${devise}` : texte
}

/** 1 234 567 890 -> « 1,23 Md » */
export function grand(v) {
  if (absent(v)) return '—'
  const a = Math.abs(v)
  if (a >= 1e12) return N2.format(v / 1e12) + ' T'
  if (a >= 1e9)  return N2.format(v / 1e9) + ' Md'
  if (a >= 1e6)  return N1.format(v / 1e6) + ' M'
  if (a >= 1e3)  return N1.format(v / 1e3) + ' k'
  return N2.format(v)
}

export function sigma(v) {
  if (absent(v)) return '—'
  return (v > 0 ? '+' : '') + N2.format(v) + ' σ'
}

export function date(iso) {
  if (!iso) return '—'
  const [a, m, j] = iso.slice(0, 10).split('-')
  return `${j}/${m}/${a}`
}

export function dateHeure(iso) {
  if (!iso) return 'jamais'
  return new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
    .toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

/** Classe de couleur pour un nombre signe. */
export const ton = v => absent(v) || v === 0 ? '' : v > 0 ? 'positif' : 'negatif'
