import QtQuick
import QtQuick.Controls
import qs.Commons

Column {
  id: root
  property var settings: ({})
  signal settingEdited(string field, int value)
  spacing: Style.space(10)

  Text {
    text: "Monitor timeouts and tint"
    color: Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.heading
    font.weight: Font.DemiBold
  }
  Text {
    width: parent.width
    text: "Each timeout starts when you lock or stop interacting. Activity restores both groups."
    wrapMode: Text.WordWrap
    color: Color.muted
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
  }

  Repeater {
    model: [
      { group: "Main monitor", timeout: "mainTimeoutMs", tint: "mainTint" },
      { group: "Side monitors", timeout: "sideTimeoutMs", tint: "sideTint" }
    ]
    Column {
      id: group
      required property var modelData
      width: root.width
      spacing: Style.space(6)

      Text {
        text: group.modelData.group + " · " + (group.modelData.tint === "mainTint"
          ? (root.settings.main || "") : (root.settings.sides || []).join(", "))
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
      }
      Row {
        spacing: Style.space(12)
        Text {
          width: Style.space(100)
          anchors.verticalCenter: parent.verticalCenter
          text: "Timeout"
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
        Rectangle {
          width: Style.space(90)
          height: Style.space(32)
          radius: Style.cornerRadius
          color: Color.background
          border.width: 1
          border.color: timeoutInput.activeFocus ? Color.accent : Color.muted
          TextInput {
            id: timeoutInput
            objectName: group.modelData.timeout
            anchors.fill: parent
            anchors.margins: Style.space(6)
            verticalAlignment: TextInput.AlignVCenter
            text: String(Math.round(root.settings[group.modelData.timeout] / 1000))
            color: Color.foreground
            selectionColor: Color.accent
            selectedTextColor: Color.background
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            selectByMouse: true
            validator: IntValidator { bottom: 1; top: 3600 }
            Accessible.name: group.modelData.group + " timeout in seconds"
            onEditingFinished: {
              if (acceptableInput) root.settingEdited(group.modelData.timeout, Number(text) * 1000)
              text = Qt.binding(function() { return String(Math.round(root.settings[group.modelData.timeout] / 1000)) })
            }
          }
        }
        Text {
          anchors.verticalCenter: parent.verticalCenter
          text: "seconds (1–3600)"
          color: Color.muted
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
      }
      Row {
        width: parent.width
        spacing: Style.space(12)
        Text {
          width: Style.space(100)
          anchors.verticalCenter: parent.verticalCenter
          text: "Black tint"
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
        Slider {
          id: tintSlider
          objectName: group.modelData.tint
          width: Math.max(Style.space(80), Math.min(Style.space(240), group.width - Style.space(180)))
          height: Style.space(32)
          from: 0
          to: 100
          stepSize: 1
          snapMode: Slider.SnapAlways
          value: root.settings[group.modelData.tint] || 0
          Accessible.name: group.modelData.group + " black tint percentage"
          onMoved: root.settingEdited(group.modelData.tint, Math.round(value))
          background: Rectangle {
            x: tintSlider.leftPadding
            y: (tintSlider.height - height) / 2
            width: tintSlider.availableWidth
            height: Style.space(4)
            radius: height / 2
            color: Color.muted
            Rectangle {
              width: tintSlider.visualPosition * parent.width
              height: parent.height
              radius: parent.radius
              color: Color.accent
            }
          }
          handle: Rectangle {
            x: tintSlider.leftPadding + tintSlider.visualPosition * (tintSlider.availableWidth - width)
            y: (tintSlider.height - height) / 2
            width: Style.space(18)
            height: width
            radius: width / 2
            color: Color.accent
            border.width: tintSlider.activeFocus ? 2 : 0
            border.color: Color.foreground
          }
        }
        Text {
          width: Style.space(48)
          anchors.verticalCenter: parent.verticalCenter
          text: Math.round(tintSlider.value) + "%"
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
      }
    }
  }
  Text {
    width: parent.width
    text: "0% leaves the image visible. 100% turns that monitor group off after its timeout."
    wrapMode: Text.WordWrap
    color: Color.muted
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
  }
}
