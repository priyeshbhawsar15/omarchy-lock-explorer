import QtQuick
import QtQuick.Effects
import QtMultimedia
import qs.Commons

Item {
  id: wall

  property var lock: null
  property real blur: 0.85
  property real dim: 0.08
  property real contrast: -0.05
  property bool vignette: true
  property real vignetteTop: 0.35
  property real vignetteMiddle: 0.10
  property real vignetteBottom: 0.45

  readonly property string videoUrl: lock && lock.videoUrl ? lock.videoUrl : ""
  readonly property bool wants: (lock && lock.videoPlaying !== undefined ? lock.videoPlaying : true) && visible && videoUrl.length > 0 && !failed
  property bool failed: false
  readonly property bool showing: player.hasVideo && (player.playbackState === MediaPlayer.PlayingState || player.playbackState === MediaPlayer.PausedState)

  readonly property string screenName: lock && lock.screenName ? String(lock.screenName) : ""
  readonly property var spanGroup: ["DP-6", "DP-4"]
  readonly property int screenIndex: spanGroup.indexOf(screenName)
  readonly property bool isSpanned: screenIndex >= 0 && spanGroup.length > 1
  readonly property int totalScreens: isSpanned ? spanGroup.length : 1

  Rectangle {
    anchors.fill: parent
    color: Color.background
  }

  Image {
    id: image
    anchors.fill: parent
    source: (wall.lock && wall.lock.loadBackground) ? wall.lock.fileUrl(wall.lock.backgroundPath) : ""
    fillMode: Image.PreserveAspectCrop
    asynchronous: true
    // The url ends in ?v=backgroundVersion, so a new wallpaper is a new url and
    // this cannot serve a stale one. Sharing it matters in the explorer, where
    // every preview would otherwise decode the same file on its own.
    cache: true
    sourceSize.width: width
    sourceSize.height: height
    visible: wall.blur <= 0 && !wall.showing
  }

  MultiEffect {
    anchors.fill: image
    source: image
    // Hidden until the image decodes: with a broken wallpaper (e.g. WebP
    // without qt6-imageformats) the effect paints its empty source as solid
    // black, hiding the theme-color fallback underneath.
    visible: wall.blur > 0 && image.status === Image.Ready && !wall.showing
    autoPaddingEnabled: false
    blurEnabled: wall.blur > 0 && image.status === Image.Ready
    blur: wall.blur
    blurMax: 96
    blurMultiplier: 1.25
    contrast: wall.contrast
    brightness: -wall.dim
  }

  MediaPlayer {
    id: player
    source: wall.videoUrl
    videoOutput: output
    loops: MediaPlayer.Infinite
    onSourceChanged: { wall.failed = false; wall.sync() }
    onErrorOccurred: function(error, errorString) {
      wall.failed = true
      console.warn("lock-explorer: cannot play", wall.videoUrl, errorString)
    }
  }

  Item {
    id: videoContainer
    anchors.fill: parent
    clip: true
    visible: wall.wants
    opacity: wall.showing ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

    VideoOutput {
      id: output
      width: wall.isSpanned ? parent.width * wall.totalScreens : parent.width
      height: parent.height
      x: wall.isSpanned ? -parent.width * wall.screenIndex : 0
      fillMode: wall.isSpanned ? VideoOutput.Stretch : VideoOutput.PreserveAspectCrop
    }
  }

  function sync() {
    if (wants) player.play()
    else player.pause()
  }

  onWantsChanged: sync()
  Component.onCompleted: sync()

  Rectangle {
    anchors.fill: parent
    color: "black"
    visible: wall.showing
    opacity: wall.dim
  }

  Rectangle {
    anchors.fill: parent
    visible: wall.vignette
    gradient: Gradient {
      GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, wall.vignetteTop) }
      GradientStop { position: 0.45; color: Qt.rgba(0, 0, 0, wall.vignetteMiddle) }
      GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, wall.vignetteBottom) }
    }
  }
}
