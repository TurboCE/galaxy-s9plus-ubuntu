// SPDX-License-Identifier: GPL-2.0-only
// Simple local Qt Sensors frontend; never synthesizes a heading.
import QtQuick 2.15
import QtQuick.Window 2.15
import QtSensors 5.15
Window {
 id: win; visible: true; width: 360; height: 580; title: "나침반"; color: "#f6f5f4"
 property real heading: 0
 property double lastSample: 0
 property bool usable: false
 Compass {
  id: sensor; active: true
  onActiveChanged: { if (!active) win.usable = false }
  onReadingChanged: {
   if (reading && reading.timestamp > 0 && isFinite(reading.azimuth)) {
    win.heading = reading.azimuth; win.lastSample = Date.now()
    win.usable = active && connectedToBackend
   }
  }
 }
 Timer { interval: 1000; repeat: true; running: true
  onTriggered: win.usable = sensor.active && sensor.connectedToBackend && win.lastSample > 0 && Date.now()-win.lastSample < 3000
 }
 Column {
  anchors.centerIn: parent; width: parent.width-40; spacing: 20
  Text { width: parent.width; text: "나침반"; font.pixelSize: 28; horizontalAlignment: Text.AlignHCenter }
  Rectangle { width: 230; height: 230; radius: 115; anchors.horizontalCenter: parent.horizontalCenter; color: "white"; border.color: "#c0bfbc"
   Text { anchors.top: parent.top; anchors.topMargin: 15; anchors.horizontalCenter: parent.horizontalCenter; text: win.usable ? "N" : ""; font.pixelSize: 22 }
   Text { anchors.centerIn: parent; text: win.usable ? "↑" : "—"; color: win.usable ? "#c01c28" : "#77767b"; font.pixelSize: 100; rotation: win.usable ? -win.heading : 0 }
  }
  Text { width: parent.width; text: win.usable ? win.heading.toFixed(0)+"°" : "센서 연결 대기"; font.pixelSize: 24; horizontalAlignment: Text.AlignHCenter }
  Text { width: parent.width; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 16; color: "#5e5c64"
   text: win.usable ? "방향 정확도는 센서 보정 상태에 따라 달라집니다." : "방향 센서가 Ubuntu에 연결되면 실제 방향을 표시합니다."
  }
 }
}
