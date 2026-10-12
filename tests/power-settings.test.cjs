const { test } = require('node:test')
const assert = require('node:assert/strict')
const power = require('../DisplayPower.js')
const config = { main: 'DP-6', sides: ['DP-5', 'DP-4'], mainTimeoutMs: 60000, sideTimeoutMs: 300000, mainTint: 100, sideTint: 90 }

test('normalization forwards hardware-off outputs to the power helper', () => {
  const settings = power.settings({...config, ddcPowerOffMonitors: ['DP-5', 'DP-4']})
  assert.deepEqual(settings.ddcPowerOffMonitors, ['DP-5', 'DP-4'])
  assert.deepEqual(power.settings(config).ddcPowerOffMonitors, [])
})

test('deadlines remain independent in either order', () => {
  assert.equal(power.expire('wake', 'sides'), 'sides')
  assert.equal(power.expire('sides', 'main'), 'both')
  assert.equal(power.expire('wake', 'main'), 'main')
  assert.equal(power.expire('main', 'sides'), 'both')
})
test('activity wake is required before a newer deadline action', () => {
  // A side-off command is still running when activity queues wake; the
  // 1-second main deadline expires before that command returns.
  assert.equal(power.nextPhase('main', 'sides', true), 'wake')
  // Only after wake completes may the new main deadline take effect.
  assert.equal(power.nextPhase('main', 'wake', false), 'main')
  assert.equal(power.nextPhase('main', 'main', false), '')
  // A failed wake remains required even if the latest policy was applied.
  assert.equal(power.nextPhase('main', 'main', true), 'wake')
})
test('overlay applies only to its group after its own deadline', () => {
  assert.equal(power.dimOverlayOpacity(config, 'wake', 'DP-4', true), 0)
  assert.equal(power.dimOverlayOpacity(config, 'main', 'DP-4', true), 0)
  assert.equal(power.dimOverlayOpacity(config, 'sides', 'DP-4', true), 0.9)
  assert.equal(power.dimOverlayOpacity(config, 'sides', 'DP-6', true), 0)
  assert.equal(power.dimOverlayOpacity({...config, mainTint: 40}, 'main', 'DP-6', true), 0.4)
  assert.equal(power.dimOverlayOpacity(config, 'both', 'other', true), 0)
  assert.equal(power.dimOverlayOpacity(config, 'both', 'DP-4', false), 0)
})
test('0 and 100 percent are honored without artificial clamping', () => {
  assert.equal(power.dimOverlayOpacity({...config, sideTint: 0}, 'sides', 'DP-4', true), 0)
  assert.equal(power.dimOverlayOpacity({...config, sideTint: 100}, 'sides', 'DP-4', true), 1)
})
test('settings edits preserve monitor layout and other settings', () => {
  assert.deepEqual(power.updateSettings({...config, custom: 'keep'}, 'sideTint', '25'), {...config, custom: 'keep', sideTint: 25})
  assert.deepEqual(power.updateSettings(config, 'mainTimeoutMs', 12000), {...config, mainTimeoutMs: 12000})
  assert.equal(config.sideTint, 90)
})
test('invalid values and unknown fields are rejected', () => {
  for (const value of ['', 'invalid', -1, 101, 1.5])
    assert.equal(power.updateSettings(config, 'mainTint', value), null)
  for (const value of [0, 999, 3600001, Infinity])
    assert.equal(power.updateSettings(config, 'sideTimeoutMs', value), null)
  assert.equal(power.updateSettings(config, 'main', 'DP-5'), null)
})
test('legacy timeouts migrate without losing their durations', () => {
  const settings = power.settings({ main: 'DP-6', sides: ['DP-4'], offMs: 45000, dimMs: 120000, overlayOpacity: 0.5 })
  assert.equal(settings.mainTimeoutMs, 45000)
  assert.equal(settings.sideTimeoutMs, 120000)
  assert.equal(settings.sideTint, 50)
  assert.equal(settings.mainTint, 100)
})
