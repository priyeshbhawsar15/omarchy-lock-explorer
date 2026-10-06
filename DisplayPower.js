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

// Optical attenuation is independent of theme colors and never affects main.
function dimOverlayOpacity(config, phase, monitor, locked) {
  if (!locked || !config || phase !== "dim") return 0
  var sides = config.sides || ["DP-4", "DP-6"]
  if (monitor === String(config.main || "DP-5") || sides.indexOf(monitor) === -1) return 0
  var value = config.overlayOpacity === undefined ? 0.35 : Number(config.overlayOpacity)
  return isFinite(value) ? Math.max(0, Math.min(0.95, value)) : 0.35
}

if (typeof module !== "undefined") module.exports = {
  keepDisplaysOn: keepDisplaysOn,
  dimOverlayOpacity: dimOverlayOpacity
}
