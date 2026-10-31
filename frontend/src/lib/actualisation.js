// @ts-check
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

/**
 * Suit l'actualisation de fond, qu'elle vienne d'un bouton, du demarrage ou de la veille horaire.
 * `surFin(etat)` est appele a la fin de chaque actualisation survenue pendant que la page est ouverte.
 */
export function useActualisation(surFin) {
  const [etat, setEtat] = useState(null)
  const [relance, setRelance] = useState(0)
  const derniereFin = useRef(undefined)
  const rappel = useRef(surFin)
  useEffect(() => { rappel.current = surFin })

  useEffect(() => {
    let actif = true, minuterie = null
    const suivre = async () => {
      let delai = 30000
      try {
        const e = await api.valeurs.actualisation()
        if (!actif) return
        setEtat(e)
        if (derniereFin.current !== undefined && e.fin && e.fin !== derniereFin.current) rappel.current(e)
        derniereFin.current = e.fin
        if (e.en_cours) delai = 1500
      } catch { /* serveur momentanement injoignable : prochain essai au tour suivant */ }
      if (actif) minuterie = setTimeout(suivre, delai)
    }
    suivre()
    return () => { actif = false; clearTimeout(minuterie) }
  }, [relance])

  const suivreMaintenant = useCallback(() => setRelance(n => n + 1), [])
  const lancer = useCallback(async mode => { setEtat(await api.valeurs.actualiserTout(mode)); suivreMaintenant() }, [suivreMaintenant])
  return { etat, lancer, suivreMaintenant }
}
