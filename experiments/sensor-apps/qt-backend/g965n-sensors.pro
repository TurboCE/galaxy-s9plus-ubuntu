# SPDX-License-Identifier: GPL-2.0-only
TEMPLATE = lib
CONFIG += plugin c++17
QT += network sensors
QT -= gui
TARGET = qtsensors_g965n
SOURCES += plugin.cpp
