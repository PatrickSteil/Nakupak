import { createApp, nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import { vi } from 'vitest'

// Render the modal inline (the real one teleports and animates)
vi.mock('../BaseModal.vue', () => ({
  default: { props: ['show', 'title'], template: '<div><slot /><slot name="footer" /></div>' },
}))

import AddRecipeModal from '../AddRecipeModal.vue'

const i18n = createI18n({
  legacy: false, locale: 'en', missingWarn: false, fallbackWarn: false,
  messages: { en: { recipes: { addToList: 'Add {count}× to list' }, common: { cancel: 'Cancel' } } },
})

async function mountModal() {
  const confirmed = []
  const el = document.createElement('div')
  document.body.appendChild(el)
  const app = createApp(AddRecipeModal, {
    show: true,
    recipe: { id: 1, name: 'Leek soup' },
    onConfirm: (n) => confirmed.push(n),
  })
  app.use(i18n)
  app.mount(el)
  await nextTick()
  const buttons = () => [...el.querySelectorAll('button')]
  return { el, app, confirmed, buttons, input: el.querySelector('input') }
}

describe('AddRecipeModal', () => {
  afterEach(() => { document.body.innerHTML = '' })

  it('starts at 1 and confirms with the chosen count', async () => {
    const { buttons, input, confirmed, app } = await mountModal()
    expect(input.value).toBe('1')
    const [minus, plus, , add] = buttons()
    plus.click(); plus.click()
    await nextTick()
    expect(input.value).toBe('3')
    expect(add.textContent).toContain('Add 3× to list')
    add.click()
    expect(confirmed).toEqual([3])
    minus.click()
    app.unmount()
  })

  it('never goes below 1 and clamps typed values', async () => {
    const { buttons, input } = await mountModal()
    buttons()[0].click()
    await nextTick()
    expect(input.value).toBe('1')
    input.value = '500'
    input.dispatchEvent(new Event('change'))
    await nextTick()
    expect(input.value).toBe('99')
    input.value = ''
    input.dispatchEvent(new Event('change'))
    await nextTick()
    expect(input.value).toBe('1')
  })
})
