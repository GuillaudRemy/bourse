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
