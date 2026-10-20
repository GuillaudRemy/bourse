import { useEffect, useState } from 'react'
import { api } from './api'

// Catalogue des postes financiers (backend/db/champs.py), charge une seule fois.
let promesse = null

export function useChamps() {
  const [champs, setChamps] = useState([])
  useEffect(() => {
    promesse ??= api.champs().catch(e => { promesse = null; throw e })
    promesse.then(setChamps).catch(() => {})
  }, [])
  return champs
}

export const ETATS = [
  { cle: 'resultat', libelle: 'Compte de résultat' },
  { cle: 'bilan',    libelle: 'Bilan' },
  { cle: 'flux',     libelle: 'Flux de trésorerie' },
  { cle: 'action',   libelle: 'Par action' },
]

export const SOURCES = {
  manuel: { libelle: 'Saisie manuelle', classe: 'src-manuel' },
  import: { libelle: 'Import (fichier ou tableur)', classe: 'src-manuel' },
  pdf:    { libelle: 'Rapport annuel PDF', classe: 'src-manuel' },
  esef:   { libelle: 'ESEF — rapport officiel européen', classe: 'src-officiel' },
  sec:    { libelle: 'SEC — rapport officiel américain', classe: 'src-officiel' },
  yahoo:  { libelle: 'Yahoo Finance', classe: 'src-yahoo' },
  calcul: { libelle: 'Calculé (EBIT + amortissements)', classe: 'src-calcul' },
}
