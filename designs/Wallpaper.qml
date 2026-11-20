import QtQuick
import QtQuick.Effects
import qs.Commons
import qs.Commons as Commons

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

  // What is drawn: the design's blur and dim, as the wallpaper setting on the
  // lock (see DesignBase) adjusts them.
  readonly property real shownBlur: wall.lock && wall.lock.wallpaperBlur !== undefined && wall.lock.wallpaperBlur >= 0
                                    ? wall.lock.wallpaperBlur : wall.blur
  readonly property real shownDim: Math.max(0, Math.min(0.9, wall.dim
                                   + (wall.lock && wall.lock.wallpaperDim !== undefined ? wall.lock.wallpaperDim : 0)))

  // Personal fork: every design plays the active video wallpaper (spanned
  // across lock.wallpaperSpanGroups) over the still picture. The player lives
  // in SpanVideo.qml and is built only while this item's window is mapped, so
  // unmapped previews and lock surfaces don't keep a decoder (and dGPU) awake.
  readonly property string videoUrl: lock && lock.videoUrl ? lock.videoUrl : ""
  property bool failed: false
  readonly property bool mapped: visible && Window.window !== null && Window.window.visible
  readonly property bool wants: (lock && lock.videoPlaying !== undefined ? lock.videoPlaying : true)
                                && visible && videoUrl.length > 0 && !failed
  readonly property bool showing: videoLoader.item ? videoLoader.item.showing : false
  onVideoUrlChanged: failed = false

  Rectangle {
    anchors.fill: parent
    color: Commons.Color.background
  }

  // A new wallpaper (a theme change) fades in over the one before instead of
  // leaving an empty frame while it decodes: the last picture that finished
  // loading stays underneath until the new one has faded in.
  property string heldUrl: ""
  readonly property bool anyReady: image.status === Image.Ready || held.status === Image.Ready

  Item {
    id: stack
    anchors.fill: parent
    visible: wall.shownBlur <= 0 && !wall.showing

    Image {
      id: held
      anchors.fill: parent
      source: wall.heldUrl
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: true
      sourceSize.width: width
      sourceSize.height: height
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
      opacity: status === Image.Ready ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: wall.heldUrl.length > 0 ? 300 : 0 } }
      onStatusChanged: if (status === Image.Ready) heldTimer.restart()
    }

    Timer {
      id: heldTimer
      interval: 320
      onTriggered: wall.heldUrl = String(image.source)
    }
  }

  MultiEffect {
    anchors.fill: stack
    source: stack
    // Hidden until a picture has decoded: with a broken wallpaper (e.g. WebP
    // without qt6-imageformats) the effect paints its empty source as solid
    // black, hiding the theme-color fallback underneath.
    visible: wall.shownBlur > 0 && wall.anyReady && !wall.showing
    autoPaddingEnabled: false
    blurEnabled: wall.shownBlur > 0 && wall.anyReady
    blur: wall.shownBlur
    blurMax: 96
    blurMultiplier: 1.25
    contrast: wall.contrast
    brightness: -wall.shownDim
  }

  Loader {
    id: videoLoader
    anchors.fill: parent
    active: wall.mapped && wall.videoUrl.length > 0 && !wall.failed
    source: Qt.resolvedUrl("SpanVideo.qml")
    onLoaded: {
      item.lock = Qt.binding(function() { return wall.lock })
      item.videoUrl = Qt.binding(function() { return wall.videoUrl })
      item.wants = Qt.binding(function() { return wall.wants })
    }
    // Without QtMultimedia the component cannot build; keep the still picture.
    onStatusChanged: if (status === Loader.Error) wall.failed = true
  }

  Connections {
    target: videoLoader.item
    function onPlaybackFailed() { wall.failed = true }
  }

  Rectangle {
    anchors.fill: parent
    color: "black"
    visible: wall.showing
    opacity: wall.shownDim
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
