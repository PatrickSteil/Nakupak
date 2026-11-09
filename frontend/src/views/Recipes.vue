<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useListStore } from '../stores/list'
import { useToastStore } from '../stores/toast'
import { recipes as recipesApi, items as itemsApi } from '../services/api'
import { Pencil, Trash2, Plus, Download, Upload, FileDown } from 'lucide-vue-next'
import { marked } from 'marked'
import PageLayout from '../components/PageLayout.vue'
import AnimatedList from '../components/AnimatedList.vue'
import RecipeModal from '../components/RecipeModal.vue'
import ImportRecipeModal from '../components/ImportRecipeModal.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import EmptyState from '../components/EmptyState.vue'
import ItemBadge from '../components/ItemBadge.vue'
import IconButton from '../components/IconButton.vue'
import CollectionCard from '../components/CollectionCard.vue'
import AppButton from '../components/AppButton.vue'

marked.setOptions({ breaks: true })

const { t } = useI18n()
const listStore = useListStore()
const toastStore = useToastStore()

const showModal = ref(false)
const editingRecipe = ref(null)
const showImportModal = ref(false)
const preselectedItemIds = ref([])
const pendingIngredients = ref([])
const prefilledName = ref('')
const prefilledDescription = ref('')
const prefilledImageUrl = ref('')
const expandedRecipes = ref(new Set())
const jsonInput = ref(null)

const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

onMounted(async () => {
  await Promise.all([
    listStore.fetchRecipes(),
    listStore.fetchItems(),
  ])
})

function startCreate() {
  editingRecipe.value = null
  preselectedItemIds.value = []
  pendingIngredients.value = []
  prefilledName.value = ''
  prefilledDescription.value = ''
  prefilledImageUrl.value = ''
  showModal.value = true
}

function toggleExpanded(recipeId) {
  if (expandedRecipes.value.has(recipeId)) {
    expandedRecipes.value.delete(recipeId)
  } else {
    expandedRecipes.value.add(recipeId)
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked(text)
}

async function handleImported(data) {
  showImportModal.value = false

  // Match existing items by name, keep unmatched as pending (no item creation yet)
  const matched = []
  const pending = []

  for (const ing of data.ingredients) {
    const existing = listStore.items.find(i => i.name.toLowerCase() === ing.name.toLowerCase())
    if (existing) {
      matched.push({ item_id: existing.id, quantity: ing.quantity, unit: ing.unit })
    } else {
      pending.push({ name: ing.name, quantity: ing.quantity, unit: ing.unit })
    }
  }

  preselectedItemIds.value = matched
  pendingIngredients.value = pending
  prefilledName.value = data.name || ''
  prefilledDescription.value = data.description || ''
  prefilledImageUrl.value = data.image_url || ''
  editingRecipe.value = null
  showModal.value = true
}

function downloadJson(doc, filename) {
  const blob = new Blob([JSON.stringify(doc, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function exportRecipe(recipe) {
  const { data } = await recipesApi.exportOne(recipe.id)
  const slug = recipe.name.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'recipe'
  downloadJson(data, `${slug}.json`)
}

async function exportAllRecipes() {
  const { data } = await recipesApi.exportAll()
  downloadJson(data, 'nakupak-recipes.json')
}

async function handleJsonFile(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  try {
    // Merge all selected files into one document; each file may hold the full
    // document, a list of recipes, or a single recipe
    const recipes = []
    for (const file of files) {
      const doc = JSON.parse(await file.text())
      if (Array.isArray(doc)) recipes.push(...doc)
      else if (doc && Array.isArray(doc.recipes)) recipes.push(...doc.recipes)
      else recipes.push(doc)
    }
    const { data } = await recipesApi.importJson({ recipes })
    await Promise.all([listStore.fetchRecipes(), listStore.fetchItems()])
    toastStore.show(t('recipes.importedJson', { count: data.length }))
  } catch (e) {
    toastStore.show(t('recipes.importJsonError'))
  }
}

function startEdit(recipe) {
  editingRecipe.value = recipe
  showModal.value = true
}

async function handleSave(data) {
  // Create items for any pending ingredients (from import)
  const allItems = [...data.items]
  if (data.pendingIngredients?.length) {
    for (const ing of data.pendingIngredients) {
      const { data: created } = await itemsApi.create({ name: ing.name })
      allItems.push({ item_id: created.id, quantity: ing.quantity, unit: ing.unit })
    }
    await listStore.fetchItems()
  }

  const payload = {
    name: data.name,
    description: data.description,
    image_url: data.image_url,
    items: allItems,
  }

  if (data.id) {
    await recipesApi.update(data.id, payload)
  } else {
    await recipesApi.create(payload)
  }
  await listStore.fetchRecipes()
  showModal.value = false
}

function confirmDeleteRecipe(recipe) {
  deleteTarget.value = recipe
  showDeleteConfirm.value = true
}

async function handleDeleteConfirm() {
  await recipesApi.delete(deleteTarget.value.id)
  await listStore.fetchRecipes()
  showDeleteConfirm.value = false
  deleteTarget.value = null
}

async function addIngredientToList(pi) {
  await listStore.addItem(pi.item_id, pi.quantity, pi.unit || 'x')
  toastStore.show(t('items.addedToList'), { items: [{ name: pi.item?.name, quantity: pi.quantity }] })
}

async function addRecipeToList(recipe) {
  await listStore.addRecipe(recipe.id)
  const items = recipe.recipe_items?.map(pi => ({
    name: pi.item?.name,
    quantity: pi.quantity,
  })) || []
  toastStore.show(t('recipes.added', { name: recipe.name }), { items })
}
</script>

<template>
  <PageLayout :title="t('recipes.title')">
    <EmptyState v-if="listStore.recipes.length === 0" :title="t('recipes.emptyTitle')" :subtitle="t('recipes.emptySubtitle')" />

    <AnimatedList :items="listStore.recipes" v-slot="{ item: recipe }">
      <CollectionCard class="mb-4" :expanded="expandedRecipes.has(recipe.id)">
        <template #header>
          <div class="flex items-center gap-3 cursor-pointer" @click="toggleExpanded(recipe.id)">
            <img v-if="recipe.image_url" :src="recipe.image_url" class="w-10 h-10 rounded-full object-cover flex-shrink-0" />
            <h3 class="flex-1 text-base font-medium text-text truncate">{{ recipe.name }}</h3>
          </div>
        </template>
        <template #actions>
          <IconButton @click.stop="addRecipeToList(recipe)">
            <Plus class="w-5 h-5" />
          </IconButton>
          <IconButton :title="t('recipes.exportJson')" @click.stop="exportRecipe(recipe)">
            <FileDown class="w-5 h-5" />
          </IconButton>
          <IconButton @click.stop="startEdit(recipe)">
            <Pencil class="w-5 h-5" />
          </IconButton>
          <IconButton @click.stop="confirmDeleteRecipe(recipe)">
            <Trash2 class="w-5 h-5" />
          </IconButton>
        </template>

        <template v-if="expandedRecipes.has(recipe.id)">
          <div v-if="recipe.image_url" class="w-full mb-3">
            <img :src="recipe.image_url" class="w-full aspect-video object-cover rounded-lg" />
          </div>
          <div
            v-if="recipe.description"
            class="w-full mb-3 text-sm text-text-secondary prose prose-sm max-w-none"
            v-html="renderMarkdown(recipe.description)"
          ></div>
          <ItemBadge
            v-for="pi in recipe.recipe_items"
            :key="pi.item_id"
            :name="pi.item?.name"
            :count="pi.quantity"
            :unit="pi.unit || 'x'"
            clickable
            @click="addIngredientToList(pi)"
          />
        </template>
      </CollectionCard>
    </AnimatedList>

    <RecipeModal
      :show="showModal"
      :edit-recipe="editingRecipe"
      :preselected-item-ids="preselectedItemIds"
      :pending-ingredients="pendingIngredients"
      :prefilled-name="prefilledName"
      :prefilled-description="prefilledDescription"
      :prefilled-image-url="prefilledImageUrl"
      @close="showModal = false"
      @save="handleSave"
    />

    <ImportRecipeModal
      :show="showImportModal"
      @close="showImportModal = false"
      @imported="handleImported"
    />

    <ConfirmModal
      :show="showDeleteConfirm"
      :title="t('recipes.deleteRecipe')"
      :message="t('recipes.deleteRecipeMessage', { name: deleteTarget?.name })"
      :confirm-text="t('common.delete')"
      :confirm-danger="true"
      @close="showDeleteConfirm = false"
      @confirm="handleDeleteConfirm"
    />

    <template #fab>
      <div class="flex gap-2">
        <input ref="jsonInput" type="file" multiple accept="application/json,.json" class="hidden" @change="handleJsonFile" />
        <AppButton variant="outline" fab :title="t('recipes.exportAll')" @click="exportAllRecipes">
          <FileDown class="w-4 h-4" />
        </AppButton>
        <AppButton variant="outline" fab :title="t('recipes.importJson')" @click="jsonInput.click()">
          <Upload class="w-4 h-4" />
        </AppButton>
        <AppButton variant="outline" fab @click="showImportModal = true">
          <Download class="w-4 h-4" />
          {{ t('recipes.importRecipe') }}
        </AppButton>
        <AppButton fab @click="startCreate">
          {{ t('recipes.newRecipe') }}
        </AppButton>
      </div>
    </template>
  </PageLayout>
</template>
