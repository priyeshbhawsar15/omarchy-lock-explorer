import QtQuick
import qs.Commons

// The same job as Wallpaper, with video support unified in Wallpaper.
Item {
  id: wall

  property var lock: null
  property real dim: 0.25
  property bool vignette: true
  property real vignetteTop: 0.35
  property real vignetteMiddle: 0.10
  property real vignetteBottom: 0.45

  property bool playing: true

  Wallpaper {
    anchors.fill: parent
    lock: wall.lock
    blur: 0
    dim: wall.dim
    vignette: wall.vignette
    vignetteTop: wall.vignetteTop
    vignetteMiddle: wall.vignetteMiddle
    vignetteBottom: wall.vignetteBottom
  }
}
