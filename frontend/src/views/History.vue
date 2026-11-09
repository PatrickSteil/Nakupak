<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useListStore } from '../stores/list'
import { useToastStore } from '../stores/toast'
import { Plus, Trash2 } from 'lucide-vue-next'
import PageLayout from '../components/PageLayout.vue'
import AnimatedList from '../components/AnimatedList.vue'
import ItemBadge from '../components/ItemBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import IconButton from '../components/IconButton.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import CollectionCard from '../components/CollectionCard.vue'

const { t, locale } = useI18n()
const listStore = useListStore()
const toastStore = useToastStore()

const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

onMounted(async () => {
  await Promise.all([
    listStore.fetchSessions(),
    listStore.fetchItems(),
  ])
})

function getItemName(sessionItem) {
  if (sessionItem.item_id) {
    const item = listStore.items.find(i => i.id === sessionItem.item_id)
    if (item) return item.name
  }
  return sessionItem.item_name
}

function formatDate(dateString) {
  const date = new Date(dateString)
  const loc = { cs: 'cs-CZ', de: 'de-DE' }[locale.value] || 'en-US'
  return date.toLocaleDateString(loc, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function ensureItemId(sessionItem) {
  if (sessionItem.item_id) {
    const exists = listStore.items.find(i => i.id === sessionItem.item_id)
    if (exists) return sessionItem.item_id
  }
  const item = await listStore.createItem(sessionItem.item_name, null)
  await listStore.fetchItems()
  return item.id
}

async function addSessionToList(session) {
  if (!session.session_items?.length) return

  const itemsToAdd = []
  for (const i of session.session_items) {
    const itemId = await ensureItemId(i)
    itemsToAdd.push({ item_id: itemId, quantity: i.quantity, unit: i.unit || 'x' })
  }

  await listStore.addItems(itemsToAdd)

  const items = session.session_items.map(i => ({
    name: getItemName(i),
    quantity: i.quantity,
  }))

  toastStore.show(t('history.addedToList'), { items })
}

function confirmDelete(session) {
  deleteTarget.value = session
  showDeleteConfirm.value = true
}

async function handleDeleteConfirm() {
  await listStore.deleteSession(deleteTarget.value.id)
  showDeleteConfirm.value = false
  deleteTarget.value = null
}

async function addItemToList(sessionItem) {
  const itemId = await ensureItemId(sessionItem)
  await listStore.addItem(itemId, sessionItem.quantity, sessionItem.unit || 'x')

  toastStore.show(t('history.addedToList'), {
    items: [{ name: getItemName(sessionItem), quantity: sessionItem.quantity }]
  })
}
</script>

<template>
  <PageLayout :title="t('history.title')">
    <EmptyState v-if="listStore.sessions.length === 0" :title="t('history.emptyTitle')" :subtitle="t('history.emptySubtitle')" />

    <div v-else class="flex flex-col gap-3">
      <AnimatedList :items="listStore.sessions" v-slot="{ item: session }">
        <CollectionCard expanded>
          <template #header>
            <span class="font-medium text-text truncate">{{ formatDate(session.completed_at) }}</span>
          </template>
          <template #actions>
            <IconButton @click="addSessionToList(session)">
              <Plus class="w-5 h-5" />
            </IconButton>
            <IconButton @click="confirmDelete(session)">
              <Trash2 class="w-5 h-5" />
            </IconButton>
          </template>
          <ItemBadge
            v-for="item in session.session_items"
            :key="item.id"
            :name="getItemName(item)"
            :count="item.quantity"
            :unit="item.unit || 'x'"
            clickable
            @click="addItemToList(item)"
          />
        </CollectionCard>
      </AnimatedList>
    </div>
    <ConfirmModal
      :show="showDeleteConfirm"
      :title="t('history.deleteSession')"
      :message="t('history.deleteSessionMessage')"
      :confirm-text="t('common.delete')"
      :confirm-danger="true"
      @close="showDeleteConfirm = false"
      @confirm="handleDeleteConfirm"
    />
  </PageLayout>
</template>
