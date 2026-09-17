# SPDX-License-Identifier: LGPL-3.0-or-later
"""The live chart of a running optimization.

A small widget that draws the mass over the iterations (with the target mass as a
dashed line).  It paints itself with QPainter - no extra window and no plotting
library, so it stays fast while FreeCAD has to stay responsive.  Instead of the
matplotlib window of the first prototype the chart sits right in the assistant at
about 90 px height.
"""

from PySide import QtCore, QtGui, QtWidgets

FARBE_LINIE = "#2e7d32"      # the mass curve
FARBE_ZIEL = "#b07000"       # dashed line of the target mass
FARBE_TEXT = "#808080"
RAND = 6                     # margin inside the widget


class VerlaufWidget(QtWidgets.QWidget):
    """Masse über Iterationen - klein, schnell, ohne Fremdbibliothek."""

    def __init__(self, hoehe=90):
        super(VerlaufWidget, self).__init__()
        self.setMinimumHeight(hoehe)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.massen = []      # [(iteration, masse), ...]
        self.ziel = None
        self.setToolTip("Masse je Iteration - die gestrichelte Linie ist die Zielmasse")

    def setze_daten(self, massen, ziel=None):
        """Neue Werte übernehmen und neu zeichnen."""
        self.massen = list(massen or [])
        self.ziel = ziel
        self.update()

    def paintEvent(self, _event):
        maler = QtGui.QPainter(self)
        maler.setRenderHint(QtGui.QPainter.Antialiasing)
        breite = self.width() - 2 * RAND
        hoehe = self.height() - 2 * RAND
        if breite <= 10 or hoehe <= 10:
            return
        if not self.massen:
            maler.setPen(QtGui.QPen(QtGui.QColor(FARBE_TEXT)))
            maler.drawText(self.rect(), QtCore.Qt.AlignCenter, "noch keine Iteration")
            return

        werte = [masse for _, masse in self.massen]
        oben = max(werte + ([self.ziel] if self.ziel else []))
        unten = min(werte + ([self.ziel] if self.ziel else []))
        spanne = (oben - unten) or 1.0
        anzahl = max(len(werte) - 1, 1)

        def punkt(index, masse):
            x = RAND + breite * (index / anzahl)
            y = RAND + hoehe * (1.0 - (masse - unten) / spanne)
            return QtCore.QPointF(x, y)

        # Zielmasse als gestrichelte Linie
        if self.ziel:
            stift = QtGui.QPen(QtGui.QColor(FARBE_ZIEL))
            stift.setStyle(QtCore.Qt.DashLine)
            maler.setPen(stift)
            y = RAND + hoehe * (1.0 - (self.ziel - unten) / spanne)
            maler.drawLine(QtCore.QPointF(RAND, y), QtCore.QPointF(RAND + breite, y))

        # die Massekurve
        maler.setPen(QtGui.QPen(QtGui.QColor(FARBE_LINIE), 2))
        pfad = QtGui.QPainterPath(punkt(0, werte[0]))
        for index, masse in enumerate(werte[1:], start=1):
            pfad.lineTo(punkt(index, masse))
        maler.drawPath(pfad)

        # Achsenbeschriftung
        maler.setPen(QtGui.QPen(QtGui.QColor(FARBE_TEXT)))
        schrift = maler.font()
        schrift.setPointSizeF(max(schrift.pointSizeF() - 1.5, 6.5))
        maler.setFont(schrift)
        maler.drawText(QtCore.QRectF(RAND, RAND - 2, breite, 12), QtCore.Qt.AlignLeft,
                       "%.0f" % oben)
        maler.drawText(QtCore.QRectF(RAND, RAND + hoehe - 12, breite, 12), QtCore.Qt.AlignLeft,
                       "%.0f" % unten)
        maler.drawText(QtCore.QRectF(RAND, RAND + hoehe - 12, breite, 12), QtCore.Qt.AlignRight,
                       "Iteration %d" % self.massen[-1][0])
