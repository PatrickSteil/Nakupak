import { createApp, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { vi } from 'vitest'

vi.mock('../../services/api', () => ({
  shoppingList: {}, items: {}, recipes: {}, pool: {}, sessions: {},
  categories: { list: vi.fn(), reorder: vi.fn().mockResolvedValue({}) },
}))

import CategoryManagerModal from '../CategoryManagerModal.vue'
import { useListStore } from '../../stores/list'
import { categories as categoriesApi } from '../../services/api'

const i18n = createI18n({ legacy: false, locale: 'en', missingWarn: false, fallbackWarn: false, messages: { en: {} } })

async function mountModal() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useListStore().categories = [
    { id: 1, name: 'A', color: '#000', sort_order: 0 },
    { id: 2, name: 'B', color: '#000', sort_order: 1 },
    { id: 3, name: 'C', color: '#000', sort_order: 2 },
  ]
  const el = document.createElement('div')
  document.body.appendChild(el)
  const app = createApp(CategoryManagerModal, { show: true })
  app.use(pinia).use(i18n)
  app.component('BaseModal', { template: '<div><slot /></div>' })
  app.mount(el)
  await new Promise(r => setTimeout(r, 50))
  return { el, app, ids: () => [...document.querySelectorAll('[data-category-id]')].map(r => r.dataset.categoryId) }
}

// jsdom has no layout: pretend each row is 40px tall, stacked in DOM order
function layoutRows(el) {
  document.querySelectorAll('[data-category-id]').forEach((row, i) => {
    row.getBoundingClientRect = () => ({ top: i * 40, height: 40 })
  })
}

const moveTo = (y) => window.dispatchEvent(Object.assign(new Event('pointermove'), { clientY: y }))
const grip = (el, i) => document.querySelectorAll('[data-category-id] span.touch-none')[i]

describe('CategoryManagerModal drag and drop', () => {
  it('reorders live while dragging and persists on release', async () => {
    categoriesApi.reorder.mockClear()
    const { el, app, ids } = await mountModal()
    layoutRows(el)
    grip(el, 0).dispatchEvent(new Event('pointerdown', { cancelable: true }))
    moveTo(110) // past the middle of the last row
    await nextTick()
    expect(ids()).toEqual(['2', '3', '1'])
    window.dispatchEvent(new Event('pointerup'))
    await vi.waitFor(() => expect(categoriesApi.reorder).toHaveBeenCalledWith([2, 3, 1]))
    app.unmount()
  })

  it('does not persist when dropped in place', async () => {
    categoriesApi.reorder.mockClear()
    const { el, app } = await mountModal()
    layoutRows(el)
    grip(el, 1).dispatchEvent(new Event('pointerdown', { cancelable: true }))
    moveTo(60)
    window.dispatchEvent(new Event('pointerup'))
    await nextTick()
    expect(categoriesApi.reorder).not.toHaveBeenCalled()
    app.unmount()
  })
})
