export function normalizeForSearch(str) {
  return str.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

export function stripEmoji(str) {
  return str.replace(/^[\p{Emoji_Presentation}\p{Extended_Pictographic}\s]+/u, '')
}

export function nameCompare(a, b) {
  return stripEmoji(a).localeCompare(stripEmoji(b), undefined, { sensitivity: 'base' })
}

// Store-route order: explicit sort_order first, name as tie-breaker
export function categoryCompare(a, b) {
  return ((a?.sort_order ?? 0) - (b?.sort_order ?? 0)) || nameCompare(a?.name || '', b?.name || '')
}
