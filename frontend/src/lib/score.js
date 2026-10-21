// Score composite du screener : chaque composante est ramenee entre 0 et 1, puis ponderee.
const borne = v => Math.max(0, Math.min(1, v))
const FIABILITE = { ok: 1, attention: 0.6, inconnu: 0.5, alerte: 0 }

export const COMPOSANTES = {
  tendance:     { libelle: 'Tendance (pente et fiabilité de la droite)', defaut: 30 },
  position:     { libelle: 'Position dans le couloir (bas = mieux)', defaut: 25 },
  qualite:      { libelle: 'Qualité (note sur les comptes)', defaut: 25 },
  valorisation: { libelle: 'Valorisation (PER face à son histoire)', defaut: 20 },
}

export function composantes(l) {
  return {
    tendance: l.pente == null ? null : borne(l.pente / 0.15) * 0.6 + (FIABILITE[l.fiabilite] ?? 0.5) * 0.4,
    position: l.position == null ? null : borne((2 - l.position) / 4),
    qualite: l.note == null ? null : l.note / 100,
    valorisation: l.cherte_per == null ? null : 1 - l.cherte_per,
  }
}

/** Moyenne ponderee des composantes disponibles, sur 100. */
export function score(l, poids) {
  const c = composantes(l)
  let total = 0, somme = 0
  for (const [cle, v] of Object.entries(c)) {
    if (v === null || !poids[cle]) continue
    total += v * poids[cle]; somme += poids[cle]
  }
  return somme ? Math.round((total / somme) * 100) : null
}
