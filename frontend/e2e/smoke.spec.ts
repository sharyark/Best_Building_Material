import { expect, test, type BrowserContext, type Page } from '@playwright/test'

/**
 * Browser smoke tests against a running stack (API with demo data + Vite dev server).
 * Login is rate-limited to 5/min/IP and refresh tokens rotate, so each role signs in ONCE and the tests
 * share that browser context (re-using a saved cookie file would trip the token-reuse protection).
 * If you re-run within a minute of a previous run, wait a minute first.
 */
const ADMIN = { phone: 'admin', password: 'admin12345' }
const MUNSHI = { phone: 'munshi', password: 'munshi12345' }

async function signIn(page: Page, who: { phone: string; password: string }, portal: 'admin' | 'accountant') {
  await page.goto(`/${portal}/login`)
  await page.getByLabel('Phone / username').fill(who.phone)
  await page.getByLabel('Password').fill(who.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening)/ })).toBeVisible()
}

/** Anything a user would see as an error in the browser console. */
function watchErrors(page: Page) {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
  page.on('console', (m) => {
    // 401 from /auth/refresh when nobody is signed in yet is expected; "aborted" fetches are navigations.
    if (m.type() === 'error' && !/favicon|status of 401|ERR_ABORTED/.test(m.text())) errors.push(`console: ${m.text()}`)
  })
  return errors
}

test.describe('signed out', () => {
  test('wrong password shows an error and stays on the login page', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByLabel('Phone / username').fill('admin')
    await page.getByLabel('Password').fill('definitely-wrong')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByText('Wrong phone or password')).toBeVisible()
    await expect(page).toHaveURL(/admin\/login/)
  })

  test('the munshi cannot sign in on the owner page', async ({ page }) => {
    await page.goto('/admin/login')
    await expect(page.getByRole('heading', { name: 'Owner sign-in' })).toBeVisible()
    await page.getByLabel('Phone / username').fill(MUNSHI.phone)
    await page.getByLabel('Password').fill(MUNSHI.password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByText(/This is an accountant account/)).toBeVisible()
    await expect(page).toHaveURL(/admin\/login/)
  })

  test('/login lets you choose a door; protected pages send you to a login page', async ({ page }) => {
    await page.goto('/payments')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByText('Who is signing in?')).toBeVisible()
    await page.getByText('Munshi (accountant)').click()
    await expect(page).toHaveURL(/accountant\/login/)
    await expect(page.getByRole('heading', { name: 'Munshi sign-in' })).toBeVisible()
  })
})

test.describe('admin', () => {
  test.describe.configure({ mode: 'serial' })
  let ctx: BrowserContext
  let page: Page
  let errors: string[]

  test.beforeAll(async ({ browser }) => {
    ctx = await browser.newContext({ viewport: { width: 1366, height: 800 } })
    page = await ctx.newPage()
    errors = watchErrors(page)
    await signIn(page, ADMIN, 'admin')
  })
  test.afterAll(async () => ctx.close())

  test('dashboard shows seeded demo numbers', async () => {
    await expect(page.getByText('Receivable: customers owe us')).toBeVisible()
    await expect(page.getByText('Biggest outstanding balances')).toBeVisible()
    await expect(page.getByText(/Rs [\d,]+\.\d{2}/).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'New challan' })).toBeVisible()
  })

  test('every page opens without console errors', async () => {
    const pages: [string, string][] = [
      ['/challans', 'Challans'], ['/purchases', 'Purchases into yard'], ['/rentals', 'Equipment rental'],
      ['/payments', 'Payments & receipts'], ['/expenses', 'Expenses & diesel'], ['/labour', 'Labour & wages'],
      ['/stock', 'Yard stock'], ['/invoices', 'Bills & invoices'], ['/masters', 'Masters'], ['/reports', 'Reports'],
      ['/admin/users', 'Users'], ['/admin/opening', 'Opening balances'], ['/admin/locks', 'Month lock'], ['/admin/audit', 'Audit log'],
    ]
    for (const [path, heading] of pages) {
      await page.goto(path)
      await expect(page.getByRole('heading', { name: heading, exact: true }), path).toBeVisible()
    }
    for (const key of ['khata', 'outstanding', 'cash-book', 'day-book', 'yard-stock', 'vehicle-pnl', 'material-margin', 'labour-cost', 'rental-income', 'profit-loss']) {
      await page.goto(`/reports/${key}`)
      await expect(page.locator('.ant-layout-content h3').first(), key).toBeVisible()
    }
    expect(errors).toEqual([])
  })

  test('reports render real data and export', async () => {
    await page.goto('/reports/vehicle-pnl')
    await expect(page.getByRole('columnheader', { name: 'Profit' })).toBeVisible()
    await expect(page.locator('.ant-table-row').first()).toBeVisible()
    // Headless Chromium has no PDF viewer, so assert on the response rather than the popup.
    const [res] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/reports/vehicle-pnl') && r.url().includes('format=pdf')),
      page.getByRole('button', { name: 'PDF' }).click(),
    ])
    expect(res.status()).toBe(200)
    expect(res.headers()['content-type']).toContain('application/pdf')
    expect((await res.body()).subarray(0, 4).toString()).toBe('%PDF')

    await page.goto('/reports/khata?party=1')
    await expect(page.getByText('Opening balance')).toBeVisible()
    await expect(page.getByRole('button', { name: /WhatsApp/ })).toBeEnabled()
  })

  test('masters list shows balances and lets you add a customer', async () => {
    await page.goto('/masters')
    await expect(page.getByRole('columnheader', { name: /Balance/ })).toBeVisible()
    await page.getByRole('button', { name: /Add customer/ }).click()
    const name = `E2E Customer ${Date.now()}`
    await page.getByLabel('Name', { exact: true }).fill(name)
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByText('Customer saved')).toBeVisible()
    await expect(page.getByText(name)).toBeVisible()
  })

  test('keyboard-first challan entry: type, Enter, save, form resets', async () => {
    await page.goto('/challans')
    await page.getByLabel('Customer', { exact: true }).fill('Khan')
    await page.keyboard.press('Enter')
    await page.getByLabel('Material', { exact: true }).fill('Rait')
    await page.keyboard.press('Enter')
    await page.getByLabel('Qty', { exact: true }).fill('1')
    // the rate fills itself from the customer's rate card (else the material default)
    await expect(page.getByLabel('Rate', { exact: true })).not.toHaveValue('', { timeout: 10_000 })
    await expect(page.getByText(/Yard stock: .* of Rait/)).toBeVisible()
    await page.getByLabel('Qty', { exact: true }).press('Enter')
    await expect(page.getByText(/Challan CH\/.* saved/)).toBeVisible()
    await expect(page.getByLabel('Qty', { exact: true })).toHaveValue('')
    await expect(page.getByLabel('Rate', { exact: true })).toHaveValue('')
    expect(errors).toEqual([])
  })

  test('a new customer can be added from inside the challan form and is selected', async () => {
    await page.goto('/challans')
    const name = `Quick Customer ${Date.now()}`
    await page.getByLabel('Customer', { exact: true }).fill(name)
    await page.getByRole('button', { name: /New customer/ }).click()
    await expect(page.getByLabel('Name', { exact: true })).toHaveValue(name)
    await page.getByLabel('Phone (also used for WhatsApp statements)').fill('0300-5550000')
    await page.getByRole('button', { name: 'Add customer' }).click()
    await expect(page.getByText('New customer added')).toBeVisible()
    await expect(page.locator('.ant-select-selection-item', { hasText: name })).toBeVisible()
    // and the new customer exists in the masters list with a zero balance
    await page.goto('/masters')
    await page.getByPlaceholder('Search customer…').fill(name)
    await expect(page.getByRole('row', { name: new RegExp(name) })).toContainText('0.00')
  })

  test('attendance grid: tap cells then save', async () => {
    await page.goto('/labour')
    await expect(page.getByText('Tap a cell to cycle')).toBeVisible()
    // Tapping a cell always changes it (cycles Present -> Half -> Absent), so this works on re-runs too.
    await page.locator('.ant-table-row').first().locator('.ant-tag').first().click()
    await page.getByRole('button', { name: /Save attendance/ }).click()
    await expect(page.getByText(/Saved \d+ attendance mark/)).toBeVisible()
  })

  test('void needs a reason', async () => {
    await page.goto('/challans')
    await page.getByRole('button', { name: 'Void' }).first().click()
    await page.getByRole('button', { name: 'Void it' }).click()
    await expect(page.getByText(/Give a reason/)).toBeVisible()
    await page.getByRole('textbox').last().fill('e2e test: entered by mistake')
    await page.getByRole('button', { name: 'Void it' }).click()
    await expect(page.getByText(/voided/)).toBeVisible()
  })

  test('audit log records what just happened', async () => {
    await page.goto('/admin/audit')
    await expect(page.locator('.ant-table-row').first()).toBeVisible()
    await expect(page.getByText('void', { exact: true }).first()).toBeVisible()
  })

  test('month lock page shows the books are balanced', async () => {
    await page.goto('/admin/locks')
    await expect(page.getByText('Books are balanced')).toBeVisible()
  })

  test('phone-sized screen: menu drawer works, page does not scroll sideways', async () => {
    await page.setViewportSize({ width: 390, height: 780 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Open menu' }).click()
    await page.getByRole('menuitem', { name: 'Reports' }).click()
    await expect(page.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(1)
  })
})

test.describe('accountant', () => {
  test('sees no Void, profit reports or Admin, and is blocked by URL too', async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 800 } })
    const page = await ctx.newPage()
    await signIn(page, MUNSHI, 'accountant')
    await expect(page.getByRole('menuitem', { name: 'Admin' })).toHaveCount(0)
    await page.goto('/challans')
    await expect(page.getByRole('heading', { name: 'Challans', exact: true })).toBeVisible()
    await expect(page.locator('.ant-table-row').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Void' })).toHaveCount(0)
    await page.goto('/reports')
    await expect(page.getByText('Party khata (customer / supplier)')).toBeVisible()
    await expect(page.getByText('Vehicle P&L')).toHaveCount(0)
    await page.goto('/admin/users')
    await expect(page.getByText('Not allowed')).toBeVisible()
    await page.goto('/reports/vehicle-pnl')
    await expect(page.getByText('Not allowed')).toBeVisible()
    await ctx.close()
  })
})
