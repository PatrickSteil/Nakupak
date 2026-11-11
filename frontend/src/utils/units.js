export const UNITS = [
  { value: 'x',  step: 1,   defaultQty: 1 },
  { value: 'g',  step: 100, defaultQty: 100 },
  { value: 'kg', step: 0.5, defaultQty: 0.5 },
  { value: 'ml', step: 100, defaultQty: 100 },
  { value: 'l',  step: 0.5, defaultQty: 0.5 },
  { value: 'el', step: 1,   defaultQty: 1 },
  { value: 'tl', step: 1,   defaultQty: 1 },
]

export function getUnit(value) {
  return UNITS.find(u => u.value === value) || UNITS[0]
}

export function formatQuantity(quantity, unit) {
  // Remove trailing zeros for clean display
  const num = parseFloat(quantity.toFixed(2))
  return `${num}${unit}`
}
