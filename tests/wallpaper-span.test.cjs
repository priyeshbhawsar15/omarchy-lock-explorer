const { test } = require('node:test')
const assert = require('node:assert/strict')
const { viewport } = require('../WallpaperSpan.js')

const screens = [
  { name: 'DP-6', x: 0, y: 0, width: 2560, height: 1440 },
  { name: 'DP-5', x: 2560, y: 0, width: 1080, height: 1920 },
  { name: 'DP-4', x: 3640, y: 0, width: 1080, height: 1920 },
]
const groups = [['DP-5', 'DP-4']]
const single = { width: 1, height: 1, x: 0, y: 0 }

test('main monitor shows the full wallpaper independently', () => {
  assert.deepEqual(viewport('DP-6', screens, groups), single)
})
test('portrait sides show consecutive halves of one aspect-preserving canvas', () => {
  assert.deepEqual(viewport('DP-5', screens, groups), { width: 2, height: 1, x: 0, y: 0 })
  assert.deepEqual(viewport('DP-4', screens, groups), { width: 2, height: 1, x: -1, y: 0 })
})
test('group ordering does not reverse the physical monitor layout', () => {
  assert.deepEqual(viewport('DP-4', screens, [['DP-4', 'DP-5']]), { width: 2, height: 1, x: -1, y: 0 })
})
test('disconnected companion and previews use the whole wallpaper', () => {
  assert.deepEqual(viewport('DP-5', screens.slice(0, 2), groups), single)
  assert.deepEqual(viewport('', screens, groups), single)
  assert.deepEqual(viewport('DP-5', screens, null), single)
})
test('unequal screens and vertical offsets share the same canvas', () => {
  const mixed = [
    { name: 'left', x: -1200, y: 200, width: 1200, height: 1600 },
    { name: 'right', x: 0, y: 0, width: 2400, height: 1800 },
  ]
  assert.deepEqual(viewport('left', mixed, [['left', 'right']]), { width: 3, height: 1.125, x: 0, y: -0.125 })
  assert.deepEqual(viewport('right', mixed, [['left', 'right']]), { width: 1.5, height: 1, x: -0.5, y: 0 })
})
