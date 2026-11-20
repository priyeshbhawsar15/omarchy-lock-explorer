import QtQuick
import QtMultimedia
import Quickshell
import "../WallpaperSpan.js" as WallpaperSpan

// Personal fork: the looping video Wallpaper draws, cropped from one canvas
// spanned across a configured monitor group (lock.wallpaperSpanGroups). Kept in
// its own file and loaded by URL, so designs still build without QtMultimedia.
Item {
  id: video

  property var lock: null
  property string videoUrl: ""
  property bool wants: false
  signal playbackFailed()

  // A paused frame stays on screen, e.g. a side monitor while the main one blanks.
  readonly property bool showing: player.hasVideo
    && (player.playbackState === MediaPlayer.PlayingState
        || player.playbackState === MediaPlayer.PausedState)

  readonly property string screenName: lock && lock.screenName ? String(lock.screenName) : ""
  readonly property var viewport: WallpaperSpan.viewport(screenName,
    Quickshell.screens.map(function(s) {
      return { name: s.name, x: s.x, y: s.y, width: s.width, height: s.height }
    }), lock ? lock.wallpaperSpanGroups : [])

  MediaPlayer {
    id: player
    source: video.videoUrl
    videoOutput: output
    loops: MediaPlayer.Infinite
    onSourceChanged: video.sync()
    onErrorOccurred: function(error, errorString) {
      console.warn("lock-explorer: cannot play", video.videoUrl, errorString)
      video.playbackFailed()
    }
  }

  Item {
    anchors.fill: parent
    clip: true
    opacity: video.showing ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

    VideoOutput {
      id: output
      width: parent.width * video.viewport.width
      height: parent.height * video.viewport.height
      x: parent.width * video.viewport.x
      y: parent.height * video.viewport.y
      fillMode: VideoOutput.PreserveAspectCrop
    }
  }

  function sync() {
    if (wants) player.play()
    else player.pause()
  }

  onWantsChanged: sync()
  Component.onCompleted: sync()
}
