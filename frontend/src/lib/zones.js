// @ts-check
// Les cinq zones du couloir de regression, du bas vers le haut.
export const ZONES = {
  opportunite_manifeste:   { libelle: 'Opportunité manifeste',   court: '< −2σ',     classe: 'zone-om' },
  sous_evalue:             { libelle: 'Sous-évalué',             court: '−2σ à −1σ', classe: 'zone-se' },
  normal:                  { libelle: 'Zone normale',            court: '−1σ à +1σ', classe: 'zone-n'  },
  surevalue:               { libelle: 'Surévalué',               court: '+1σ à +2σ', classe: 'zone-sv' },
  surevaluation_manifeste: { libelle: 'Surévaluation manifeste', court: '> +2σ',     classe: 'zone-sm' },
}

export const ORDRE_ZONES = Object.keys(ZONES)

export const STATUTS = {
  ok:        { libelle: 'Fiable',    classe: 'statut-ok' },
  inconnu:   { libelle: 'À compléter', classe: 'statut-inconnu' },
  attention: { libelle: 'Prudence',  classe: 'statut-attention' },
  alerte:    { libelle: 'Trompeuse', classe: 'statut-alerte' },
}

export const TYPES = {
  action: 'Action', indice: 'Indice', etf: 'ETF', matiere: 'Matière première', devise: 'Devise', taux: 'Taux', crypto: 'Cryptomonnaie',
}
/** Pas de droite de regression : une devise n'a pas de tendance de fond, un taux pas de croissance. */
export const SANS_DROITE = ['devise', 'taux']
