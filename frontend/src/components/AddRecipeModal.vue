<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Minus, Plus } from 'lucide-vue-next'
import BaseModal from './BaseModal.vue'
import AppButton from './AppButton.vue'
import IconButton from './IconButton.vue'

const { t } = useI18n()

const props = defineProps({
  show: Boolean,
  recipe: Object,
})

const emit = defineEmits(['close', 'confirm'])

const MAX = 99
const count = ref(1)

watch(() => props.show, (open) => {
  if (open) count.value = 1
})

function setCount(value) {
  const n = Math.round(Number(value))
  count.value = Number.isFinite(n) ? Math.min(MAX, Math.max(1, n)) : 1
}

function confirm() {
  emit('confirm', count.value)
}
</script>

<template>
  <BaseModal :show="show" :title="recipe?.name" @close="emit('close')">
    <label class="block text-sm font-medium mb-3 text-text-secondary">{{ t('recipes.howMany') }}</label>
    <div class="flex items-center justify-center gap-3">
      <IconButton :disabled="count <= 1" :title="t('recipes.fewer')" @click="setCount(count - 1)">
        <Minus class="w-5 h-5" />
      </IconButton>
      <input
        :value="count"
        type="number"
        inputmode="numeric"
        min="1"
        :max="MAX"
        class="w-20 px-3 py-2 text-center text-lg border border-border rounded-lg bg-surface text-text focus:outline-none focus:border-primary"
        @change="setCount($event.target.value)"
        @keydown.enter="confirm"
      />
      <IconButton :disabled="count >= MAX" :title="t('recipes.more')" @click="setCount(count + 1)">
        <Plus class="w-5 h-5" />
      </IconButton>
    </div>

    <template #footer>
      <AppButton variant="secondary" @click="emit('close')">
        {{ t('common.cancel') }}
      </AppButton>
      <AppButton @click="confirm">
        {{ t('recipes.addToList', { count }) }}
      </AppButton>
    </template>
  </BaseModal>
</template>
