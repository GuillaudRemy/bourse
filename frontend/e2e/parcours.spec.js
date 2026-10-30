import { test, expect } from '@playwright/test'

// 24 ans de cours synthetiques a +10 %/an, au format d'un export francais.
function csvCours() {
  const lignes = ['Date;Clôture;Volume']
  const debut = Date.UTC(2002, 0, 2)
  let graine = 42
  const hasard = () => { graine = (graine * 16807) % 2147483647; return graine / 2147483647 - 0.5 }
  let bruit = 0
  for (let j = 0; j < 24 * 365; j++) {
    const jour = new Date(debut + j * 86400000)
    if (jour.getUTCDay() === 0 || jour.getUTCDay() === 6) continue
    bruit = 0.98 * bruit + 0.02 * hasard() * 2
    const cours = 50 * Math.exp(Math.log(1.10) * j / 365.25 + bruit)
    const d = `${String(jour.getUTCDate()).padStart(2, '0')}/${String(jour.getUTCMonth() + 1).padStart(2, '0')}/${jour.getUTCFullYear()}`
    lignes.push(`${d};${cours.toFixed(4).replace('.', ',')};1000`)
  }
  return lignes.join('\n')
}

let id
test.beforeAll(async ({ request }) => {
  const existante = (await (await request.get('/api/valeurs')).json()).find(v => v.symbole === 'TEST.PA')
  if (existante) { id = existante.id; return }
  const r = await request.post('/api/valeurs', { data: { symbole: 'TEST.PA', nom: 'Essai SA', source: 'import', type: 'action', devise: 'EUR' } })
  expect(r.ok()).toBeTruthy()
  id = (await r.json()).id
  const imp = await request.post(`/api/valeurs/${id}/import/cours`, {
    multipart: { fichier: { name: 'cours.csv', mimeType: 'text/csv', buffer: Buffer.from(csvCours()) } },
  })
  expect(imp.ok()).toBeTruthy()
})

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('bourse.bienvenue-vue', 'oui'))
  page.on('pageerror', e => { throw e })
})

test('visite guidée au premier lancement', async ({ browser }) => {
  const page = await browser.newPage()
  await page.goto('/accueil')
  await expect(page.getByText('Bienvenue')).toBeVisible()
  await page.getByRole('button', { name: 'Passer' }).click()
  await page.reload()
  await expect(page.getByText('Bienvenue')).toHaveCount(0)
})

test('fiche : droite de régression et analyse technique', async ({ page }) => {
  await page.goto(`/valeurs/${id}`)
  await expect(page.getByRole('heading', { name: 'Essai SA' })).toBeVisible()
  const pente = page.locator('.stat', { hasText: 'Pente' }).locator('.stat-valeur')
  await expect(pente).toContainText('%')
  const valeur = parseFloat((await pente.textContent()).replace(',', '.').replace(/[^\d.+-]/g, ''))
  expect(valeur).toBeGreaterThan(7)
  expect(valeur).toBeLessThan(13)
  await expect(page.locator('.graphique canvas').first()).toBeVisible()
  await page.getByRole('button', { name: 'Analyse technique' }).click()
  await expect(page.getByText('RSI 14')).toBeVisible()
})

test('recherche Ctrl+K ouvre une valeur', async ({ page }) => {
  await page.goto('/accueil')
  await page.keyboard.press('Control+k')
  await page.keyboard.type('essai')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(new RegExp(`/valeurs/${id}$`))
})

test('thème sombre et glossaire', async ({ page }) => {
  await page.goto('/glossaire')
  await page.getByPlaceholder('Chercher un terme…').fill('piotroski')
  await expect(page.getByText('Score de Piotroski')).toBeVisible()
  await page.getByTitle(/^Thème/).click()
  await page.getByTitle(/^Thème/).click()
  const theme = await page.evaluate(() => document.documentElement.dataset.theme)
  expect(['clair', 'sombre']).toContain(theme)
})

test('portefeuille : compte, achat et frais calculés', async ({ page, request }) => {
  const compte = await (await request.post('/api/portefeuille/comptes', { data: { nom: 'CTO essai', type: 'CTO', frais_fixe: 1, frais_pct: 0.001 } })).json()
  const achat = await request.post('/api/portefeuille/transactions', {
    data: { compte_id: compte.id, valeur_id: id, jour: '2024-03-01', type: 'achat', quantite: 10, prix: 100 },
  })
  expect(achat.ok()).toBeTruthy()
  expect((await achat.json()).frais).toBeCloseTo(2, 5)        // 1 € + 0,1 % de 1 000 €
  await page.goto('/portefeuille')
  await expect(page.getByText('Essai SA').first()).toBeVisible()
})

test('à propos et exports', async ({ page, request }) => {
  await page.goto('/a-propos')
  await expect(page.getByText('Contenu de la base')).toBeVisible()
  expect((await request.get('/api/diagnostic.zip')).ok()).toBeTruthy()
  expect((await request.get(`/api/valeurs/${id}/export.xlsx`)).ok()).toBeTruthy()
})

test('suppression groupée depuis le tableau des valeurs', async ({ page, request }) => {
  for (const s of ['JETABLE1', 'JETABLE2']) await request.post('/api/valeurs', { data: { symbole: s, nom: `Jetable ${s}`, source: 'import' } })
  await page.goto('/valeurs')
  for (const s of ['JETABLE1', 'JETABLE2']) await page.locator('tr', { hasText: s }).locator('input[type=checkbox]').check()
  await expect(page.getByText('2 sélectionnée(s)')).toBeVisible()
  page.once('dialog', d => { expect(d.message()).toContain('Supprimer 2 valeur(s)'); d.accept() })
  await page.getByRole('button', { name: 'Supprimer' }).click()
  await expect(page.getByText('2 valeur(s) supprimée(s).')).toBeVisible()
  await expect(page.locator('tr', { hasText: 'JETABLE1' })).toHaveCount(0)
  await expect(page.locator('tr', { hasText: 'Essai SA' })).toHaveCount(1)
})

test('menu à 5 entrées, listes déroulantes et anciennes adresses', async ({ page }) => {
  await page.goto('/accueil')
  const menu = page.locator('.nav-liens .nav-lien')
  await expect(menu).toHaveText([/Aujourd’hui/, /Marchés/, /Portefeuille/, /Outils/, /Aide/])
  await menu.filter({ hasText: 'Marchés' }).click()
  await expect(page).toHaveURL(/\/valeurs$/)
  await expect(page.locator('.menu-deroulant')).toHaveCount(0)
  await menu.filter({ hasText: 'Outils' }).click()
  await expect(page.locator('.menu-entree')).toHaveText(['Screener', 'Comparer', 'Calendrier', 'Alertes',
    'Simulateur de patrimoine', 'Backtest', 'Couverture des données'])
  await page.keyboard.press('Escape')                             // se referme sans changer de page
  await expect(page.locator('.menu-deroulant')).toHaveCount(0)
  await menu.filter({ hasText: 'Outils' }).click()
  await page.locator('.menu-entree', { hasText: 'Screener' }).click()
  await expect(page).toHaveURL(/\/screener$/)
  await expect(page.locator('.menu-deroulant')).toHaveCount(0)
  await expect(menu.filter({ hasText: 'Outils' })).toHaveClass(/actif/)
  await page.goto('/calendrier')                                  // adresse d'avant la 0.6.0
  await expect(menu.filter({ hasText: 'Outils' })).toHaveClass(/actif/)
  await page.getByRole('link', { name: 'Réglages' }).click()
  await expect(page).toHaveURL(/\/reglages$/)
  await expect(page.getByText('Prime de risque des actions (%)')).toBeVisible()
})

test('tableau des valeurs : les colonnes ne bougent pas', async ({ page, request }) => {
  const noms = ['A', 'Une société au nom vraiment très très long pour tester la coupure SA', 'Moyenne', 'BB', 'Groupe Industriel',
    'C', 'Dd', 'Ee international', 'Ff', 'Gg', 'Hh holding', 'Ii', 'Jj', 'Kk', 'Ll', 'Mm', 'Nn', 'Oo', 'Pp', 'Qq', 'Rr', 'Ss']
  const existantes = (await (await request.get('/api/valeurs')).json()).map(v => v.symbole)
  for (const [i, nom] of noms.entries()) {
    if (existantes.includes(`COL${i}`)) continue
    await request.post('/api/valeurs', { data: { symbole: `COL${i}`, nom, source: 'import', type: i % 3 ? 'action' : 'etf', devise: 'EUR' } })
  }
  await request.put('/api/reglages/valeurs_par_page', { data: { valeur: '20' } })
  await page.goto('/valeurs')
  const positions = async () => page.locator('.tableau thead th').evaluateAll(ths => ths.map(th => Math.round(th.getBoundingClientRect().left)))
  await expect(page.locator('.tableau tbody tr')).toHaveCount(20)
  const avant = await positions()
  await page.locator('th', { hasText: 'PER' }).click()
  expect(await positions()).toEqual(avant)
  await page.locator('th', { hasText: 'Valeur' }).click()
  expect(await positions()).toEqual(avant)
  await page.getByRole('button', { name: 'Suivante' }).click()
  expect(await positions()).toEqual(avant)
  await page.getByLabel('Rechercher dans les valeurs').fill('long')
  expect(await positions()).toEqual(avant)
  // Nom trop long : coupe, en entier au survol.
  const cellule = page.locator('td.texte', { hasText: 'Une société' })
  await expect(cellule).toHaveAttribute('title', noms[1])
  expect(await cellule.evaluate(td => td.scrollWidth <= td.clientWidth + 1)).toBeTruthy()
  await request.put('/api/reglages/valeurs_par_page', { data: { valeur: '50' } })
})

test('simulateur de patrimoine et couverture des données', async ({ page }) => {
  await page.goto('/simulateur')
  await expect(page.getByText('Résultat médian')).toBeVisible()
  await page.getByLabel('Part Actions (monde)').fill('40')
  await expect(page.getByText('la répartition doit faire 100 %')).toBeVisible()
  await page.locator('select', { hasText: 'Modèle…' }).selectOption('Dynamique')
  await expect(page.getByText('la répartition doit faire 100 %')).toHaveCount(0)
  await page.goto('/donnees')
  await expect(page.getByRole('heading', { name: 'Couverture des données' })).toBeVisible()
  await expect(page.locator('.tableau tbody tr').first()).toBeVisible()
})
