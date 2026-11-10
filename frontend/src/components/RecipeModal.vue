<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useListStore } from '../stores/list'
import { getUnit } from '../utils/units'
import { recipes as recipesApi } from '../services/api'
import { X, ListPlus } from 'lucide-vue-next'
import BaseModal from './BaseModal.vue'
import AppButton from './AppButton.vue'
import ItemCardList from './ItemCardList.vue'
import ItemSearchPicker from './ItemSearchPicker.vue'

const { t } = useI18n()

const props = defineProps({
  show: Boolean,
  editRecipe: Object,
  // Optional starting values for a new recipe (e.g. from a URL import)
  prefill: Object,
})

const emit = defineEmits(['close', 'save'])

const listStore = useListStore()

const recipeName = ref('')
const recipeDescription = ref('')
const recipeImageUrl = ref('')
const selectedItems = ref([])
const pasteText = ref('')
const pasting = ref(false)
const pasteError = ref('')
const uploading = ref(false)
const fileInput = ref(null)

const title = computed(() => props.editRecipe ? t('common.editRecipe') : t('common.newRecipe'))
const buttonText = computed(() => props.editRecipe ? t('common.save') : t('common.create'))

watch(() => props.show, (newVal) => {
  if (newVal) {
    if (props.editRecipe) {
      recipeName.value = props.editRecipe.name
      recipeDescription.value = props.editRecipe.description || ''
      recipeImageUrl.value = props.editRecipe.image_url || ''
      selectedItems.value = props.editRecipe.recipe_items.map(pi => ({
        item_id: pi.item_id,
        quantity: pi.quantity,
        unit: pi.unit || 'x',
      }))
    } else {
      recipeName.value = props.prefill?.name || ''
      recipeDescription.value = props.prefill?.description || ''
      recipeImageUrl.value = props.prefill?.image_url || ''
      selectedItems.value = []
    }
    pasteText.value = props.editRecipe ? '' : (props.prefill?.ingredientsText || '')
    pasteError.value = ''
  }
})

// Paste "2 l Milch\n300 g Mehl": the server parses it, existing items are matched
// by name and missing ones are created (the server suggests a category for them).
async function addPastedIngredients() {
  if (!pasteText.value.trim()) return
  pasting.value = true
  pasteError.value = ''
  try {
    const { data: rows } = await recipesApi.parseIngredients(pasteText.value)
    for (const row of rows) {
      let itemId = row.item_id
      if (!itemId) {
        const created = await listStore.createItem(row.name, null)
        itemId = created.id
      }
      const existing = selectedItems.value.find(i => i.item_id === itemId)
      if (existing) {
        existing.quantity = row.quantity
        existing.unit = row.unit
      } else {
        selectedItems.value.push({ item_id: itemId, quantity: row.quantity, unit: row.unit })
      }
    }
    pasteText.value = ''
  } catch (e) {
    pasteError.value = t('common.pasteError')
  } finally {
    pasting.value = false
  }
}

async function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const { data } = await recipesApi.uploadImage(file)
    recipeImageUrl.value = data.image_url
  } catch {
    // ignore upload errors
  } finally {
    uploading.value = false
  }
}

function clearImage() {
  recipeImageUrl.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

function addItem(item) {
  if (!selectedItems.value.some(i => i.item_id === item.id)) {
    selectedItems.value.push({ item_id: item.id, quantity: 1, unit: 'x' })
  }
}

function getItem(itemId) {
  return listStore.items.find(i => i.id === itemId)
}

function handleIncrement(si) {
  const step = getUnit(si.unit || 'x').step
  si.quantity += step
}

function handleDecrement(si) {
  const u = getUnit(si.unit || 'x')
  const newQty = si.quantity - u.step
  if (newQty < u.step) {
    handleRemoveItem(si)
  } else {
    si.quantity = newQty
  }
}

function handleUpdateQuantity(si, newQty) {
  if (newQty <= 0) {
    handleRemoveItem(si)
  } else {
    si.quantity = newQty
  }
}

function handleRemoveItem(si) {
  const index = selectedItems.value.indexOf(si)
  if (index >= 0) selectedItems.value.splice(index, 1)
}

function handleChangeUnit(si, newUnit) {
  si.unit = newUnit
}

function save() {
  emit('save', {
    id: props.editRecipe?.id,
    name: recipeName.value,
    description: recipeDescription.value || null,
    image_url: recipeImageUrl.value || null,
    items: selectedItems.value,
  })
}

function close() {
  emit('close')
}
</script>

<template>
  <BaseModal :show="show" :title="title" @close="close">
    <div class="mb-4">
      <label class="block text-sm font-medium mb-2 text-text-secondary">{{ t('common.name') }}</label>
      <input
        v-model="recipeName"
        type="text"
        :placeholder="t('common.recipeNamePlaceholder')"
        class="w-full px-4 py-3 border border-border rounded-lg text-base bg-surface text-text focus:outline-none focus:border-primary"
      />
    </div>

    <div class="mb-4">
      <label class="block text-sm font-medium mb-2 text-text-secondary">{{ t('common.image') }}</label>
      <div v-if="recipeImageUrl" class="relative mb-2">
        <img
          :src="recipeImageUrl"
          class="w-full aspect-video object-cover rounded-lg"
        />
        <button
          class="absolute top-2 right-2 p-1 bg-black/50 rounded-full text-white hover:bg-black/70"
          @click="clearImage"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        class="w-full text-sm text-text-secondary file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border file:border-border file:text-sm file:font-medium file:bg-surface-secondary file:text-text hover:file:opacity-80"
        :disabled="uploading"
        @change="handleFileSelect"
      />
    </div>

    <div class="mb-4">
      <label class="block text-sm font-medium mb-2 text-text-secondary">{{ t('common.description') }}</label>
      <textarea
        v-model="recipeDescription"
        :placeholder="t('common.descriptionPlaceholder')"
        rows="3"
        class="w-full px-4 py-3 border border-border rounded-lg text-base bg-surface text-text focus:outline-none focus:border-primary resize-y text-sm"
      />
    </div>

    <div class="mb-4">
      <label class="block text-sm font-medium mb-2 text-text-secondary">{{ t('common.itemsLabel') }}</label>
      <div v-if="selectedItems.length > 0" class="mb-3">
        <ItemCardList
          :items="[
            ...selectedItems.map(si => ({
              id: si.item_id,
              item: getItem(si.item_id),
              quantity: si.quantity,
              unit: si.unit || 'x',
              _raw: si,
            })),
          ]"
          @increment="(entry) => handleIncrement(entry._raw)"
          @decrement="(entry) => handleDecrement(entry._raw)"
          @change-unit="(entry, unit) => handleChangeUnit(entry._raw, unit)"
          @update-quantity="(entry, qty) => handleUpdateQuantity(entry._raw, qty)"
          @remove="(entry) => handleRemoveItem(entry._raw)"
        />
      </div>
      <ItemSearchPicker
        :placeholder="t('common.searchItems')"
        @select="addItem"
        @create="addItem"
      />
    </div>

    <div class="mb-4">
      <label class="block text-sm font-medium mb-2 text-text-secondary">{{ t('common.pasteIngredients') }}</label>
      <textarea
        v-model="pasteText"
        :placeholder="t('common.pastePlaceholder')"
        rows="4"
        class="w-full px-4 py-3 border border-border rounded-lg text-base bg-surface text-text focus:outline-none focus:border-primary resize-y text-sm"
      />
      <p v-if="pasteError" class="mt-2 text-sm text-red-600 dark:text-red-400">{{ pasteError }}</p>
      <AppButton variant="secondary" class="mt-2" :disabled="pasting || !pasteText.trim()" @click="addPastedIngredients">
        <ListPlus class="w-4 h-4" />
        {{ t('common.addPasted') }}
      </AppButton>
    </div>

    <template #footer>
      <AppButton variant="secondary" @click="close">
        {{ t('common.cancel') }}
      </AppButton>
      <AppButton @click="save" :disabled="!recipeName">
        {{ buttonText }}
      </AppButton>
    </template>
  </BaseModal>
</template>
