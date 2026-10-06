const { test } = require('node:test')
const assert = require('node:assert/strict')
const { dimOverlayOpacity } = require('../DisplayPower.js')
const config = { main: 'DP-5', sides: ['DP-4', 'DP-6'], overlayOpacity: 0.35 }

for (const monitor of ['DP-4', 'DP-6']) {
  test(`${monitor} dims only in the locked dim phase`, () => {
    assert.equal(dimOverlayOpacity(config, 'dim', monitor, true), 0.35)
    assert.equal(dimOverlayOpacity(config, 'off', monitor, true), 0)
    assert.equal(dimOverlayOpacity(config, 'wake', monitor, true), 0)
    assert.equal(dimOverlayOpacity(config, 'dim', monitor, false), 0)
  })
}
test('main and unrelated outputs never receive the overlay', () => {
  for (const monitor of ['DP-5', 'HDMI-A-1', ''])
    assert.equal(dimOverlayOpacity(config, 'dim', monitor, true), 0)
})
test('defaults and invalid opacity are safe', () => {
  assert.equal(dimOverlayOpacity({}, 'dim', 'DP-6', true), 0.35)
  assert.equal(dimOverlayOpacity(null, 'dim', 'DP-6', true), 0)
  assert.equal(dimOverlayOpacity({...config, overlayOpacity: 'bad'}, 'dim', 'DP-4', true), 0.35)
  assert.equal(dimOverlayOpacity({...config, overlayOpacity: 2}, 'dim', 'DP-4', true), 0.95)
  assert.equal(dimOverlayOpacity({...config, overlayOpacity: -1}, 'dim', 'DP-4', true), 0)
})
