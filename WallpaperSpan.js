// Ratios relative to this surface, in logical pixels (after rotation/scale).
function viewport(name, screens, groups) {
  var single = { width: 1, height: 1, x: 0, y: 0 }
  if (!name || !Array.isArray(groups)) return single
  var group = groups.find(function(g) { return Array.isArray(g) && g.indexOf(name) >= 0 })
  if (!group) return single
  var members = screens.filter(function(s) {
    return s && group.indexOf(s.name) >= 0 && s.width > 0 && s.height > 0
  })
  var current = members.find(function(s) { return s.name === name })
  if (!current || members.length < 2) return single
  var left = Math.min.apply(null, members.map(function(s) { return s.x }))
  var top = Math.min.apply(null, members.map(function(s) { return s.y }))
  var right = Math.max.apply(null, members.map(function(s) { return s.x + s.width }))
  var bottom = Math.max.apply(null, members.map(function(s) { return s.y + s.height }))
  return {
    width: (right - left) / current.width,
    height: (bottom - top) / current.height,
    x: (left - current.x) / current.width,
    y: (top - current.y) / current.height
  }
}

if (typeof module !== "undefined") module.exports = { viewport: viewport }
