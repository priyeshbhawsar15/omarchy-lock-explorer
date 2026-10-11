// Opt-in workaround for HDMI drivers that fail after locked display sleep.
function keepDisplaysOn(config, pluginId, screens) {
  var entries = config && Array.isArray(config.plugins) ? config.plugins : []
  var enabled = false
  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i]
    if (entry && entry.id === pluginId && entry.keepDisplaysOnWithHdmi === true) enabled = true
  }
  if (!enabled) return false
  for (var j = 0; screens && j < screens.length; j++) {
    var screen = screens[j]
    if (screen && /^HDMI-A-[0-9]+$/.test(String(screen.name || ""))) return true
  }
  return false
}

function bounded(value, fallback, low, high) {
  var n = Number(value)
  return value === undefined || value === null || value === "" || !isFinite(n)
    ? fallback : Math.max(low, Math.min(high, Math.round(n)))
}

function settings(config) {
  config = config || {}
  var main = String(config.main || "DP-6")
  var legacyTint = bounded(Number(config.overlayOpacity) * 100, 90, 0, 100)
  return {
    main: main,
    sides: (Array.isArray(config.sides) ? config.sides : ["DP-5", "DP-4"])
      .filter(function(s) { return s && s !== main }),
    mainTimeoutMs: bounded(config.mainTimeoutMs, bounded(config.offMs, 60000, 1000, 3600000), 1000, 3600000),
    sideTimeoutMs: bounded(config.sideTimeoutMs, bounded(config.dimMs, 300000, 1000, 3600000), 1000, 3600000),
    mainTint: bounded(config.mainTint, 100, 0, 100),
    sideTint: bounded(config.sideTint, legacyTint, 0, 100)
  }
}

function updateSettings(config, field, value) {
  var timeout = field === "mainTimeoutMs" || field === "sideTimeoutMs"
  if (!timeout && field !== "mainTint" && field !== "sideTint") return null
  var text = String(value === undefined || value === null ? "" : value).trim()
  var number = Number(text)
  if (!text || !isFinite(number) || Math.round(number) !== number
      || number < (timeout ? 1000 : 0) || number > (timeout ? 3600000 : 100)) return null
  var next = {}
  for (var key in config) next[key] = config[key]
  next[field] = number
  return next
}

function expire(phase, group) {
  if (phase === "both" || (phase !== "wake" && phase !== group)) return "both"
  return group
}

function nextPhase(desired, applied, wakePending) {
  if (wakePending) return "wake"
  return desired === applied ? "" : desired
}

// Literal optical black, independent of the theme palette.
function dimOverlayOpacity(config, phase, monitor, locked) {
  if (!locked || !config) return 0
  // Compatibility for old callers; the current service uses independent phases.
  if (phase === "dim" && config.sideTint === undefined) {
    var sides = config.sides || ["DP-4", "DP-6"]
    if (monitor === String(config.main || "DP-5") || sides.indexOf(monitor) === -1) return 0
    var value = config.overlayOpacity === undefined ? 0.35 : Number(config.overlayOpacity)
    return isFinite(value) ? Math.max(0, Math.min(0.95, value)) : 0.35
  }
  var cfg = settings(config)
  if (monitor === cfg.main && (phase === "main" || phase === "both")) return cfg.mainTint / 100
  if (cfg.sides.indexOf(monitor) >= 0 && (phase === "sides" || phase === "both" || phase === "dim")) return cfg.sideTint / 100
  return 0
}

if (typeof module !== "undefined") module.exports = {
  keepDisplaysOn: keepDisplaysOn,
  dimOverlayOpacity: dimOverlayOpacity,
  settings: settings,
  updateSettings: updateSettings,
  expire: expire,
  nextPhase: nextPhase
}
