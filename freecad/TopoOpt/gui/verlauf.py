# SPDX-License-Identifier: LGPL-3.0-or-later
"""Live charts of a running optimization - an own window in FreeCAD.

Same idea as the first prototype and like CfdOF: FreeCAD's own Plot module
(``Mod/Plot``) shows matplotlib as an MDI child window, a QTimer redraws it every
1.5 s, so the charts follow the run.

Four charts in one window (drawn from the iteration table in beso's log file):

1. mass in percent of the first mass (dashed line = target mass)
2. FI_mean and FI_max (dashed line at 1.0 = limit)
3. overloaded elements (FI_violated)
4. mean energy density

The values come from ``core/lauf.py``, so this module only draws.
"""

import time

from PySide import QtCore

FARBEN = {
    "mass": "#1f77b4",
    "ziel": "#7f7f7f",
    "fi_mean": "#2ca02c",
    "fi_max": "#d62728",
    "fi_verletzt": "#ff7f0e",
    "grenze": "#7f7f7f",
    "ener": "#9467bd",
}
FENSTERTITEL = "Topology optimization - history"
# Höhe der vier Diagramme im Fenster (unten, dann nach oben)
POSITIONEN = ((0.14, 0.07, 0.82, 0.18), (0.14, 0.29, 0.82, 0.18),
              (0.14, 0.51, 0.82, 0.18), (0.14, 0.73, 0.82, 0.18))


class Verlauf(object):
    """Sammelt die Iterationswerte und zeichnet sie in ein Plot-Fenster."""

    def __init__(self, titel=FENSTERTITEL, zielmasse=None):
        self.titel = titel
        self.zielmasse = zielmasse
        self.werte = []                  # [(iteration, dict), ...]
        self.geschlossen = False
        self.laeuft = False
        self._fenster = None
        self._achsen = []
        self._start_zeit = None
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.zeichne)
        self._timer.start(1500)

    # ------------------------------------------------------------------ Daten
    def setze_werte(self, werte):
        self.werte = list(werte or [])

    def zuruecksetzen(self):
        self.werte = []
        self.geschlossen = False
        self._start_zeit = time.time()

    # ---------------------------------------------------------------- Fenster
    def anzeigen(self):
        """Fenster zeigen (anlegen, wenn es noch keines gibt)."""
        self.geschlossen = False
        fenster = self._sorge_fuer_fenster()
        self.zeichne(erzwingen=True)
        return fenster

    def schliessen(self):
        """Nach einem Lauf: den Timer anhalten (das Fenster bleibt offen)."""
        self._timer.stop()

    def _sorge_fuer_fenster(self):
        if self._fenster is not None:
            return self._fenster
        try:
            from FreeCAD.Plot import Plot
        except Exception:
            return None
        try:
            fenster = Plot.figure(self.titel)
        except Exception:
            return None
        if fenster is None:
            return None
        self._fenster = fenster
        try:
            fenster.destroyed.connect(self._fenster_zu)
        except Exception:
            pass
        # Wichtig: auch die vom Plot-Modul angelegte erste Achse auf ihre Position
        # legen - sie liegt sonst über die ganze Fensterhöhe.
        fig = fenster.fig
        self._achsen = [fenster.axes]
        try:
            fenster.axes.set_position(POSITIONEN[0])
        except Exception:
            pass
        for rect in POSITIONEN[1:]:
            try:
                self._achsen.append(fig.add_axes(rect))
            except Exception:
                pass
        return self._fenster

    def _fenster_zu(self, *_):
        """Vom Nutzer geschlossen - nicht ungefragt neu aufziehen."""
        self._fenster = None
        self._achsen = []
        self.geschlossen = True

    # --------------------------------------------------------------- Zeichnen
    def zeichne(self, erzwingen=False):
        if not self.werte:
            if (self.laeuft or erzwingen) and not self.geschlossen:
                self._warte_hinweis()
            return
        if self.geschlossen and not erzwingen:
            return
        fenster = self._sorge_fuer_fenster()
        if fenster is None or len(self._achsen) < 4:
            return

        for achse, rect in zip(self._achsen, POSITIONEN):
            try:
                achse.set_position(list(rect))
            except Exception:
                pass

        iterationen = [i for i, _ in self.werte]

        def spalte(name):
            return [(werte.get(name) if werte else None) for _, werte in self.werte]

        massen = spalte("mass")
        fi_mean = spalte("fi_mean")
        fi_max = spalte("fi_max")
        ueberlastet = spalte("fi_violated")
        energien = spalte("ener")

        # 1) Masse in Prozent
        achse = self._achsen[3]
        achse.cla()
        achse.set_ylabel("Mass [%]", fontsize=8)
        achse.tick_params(labelsize=7, labelbottom=False)
        start = next((m for m in massen if m), None)
        if start:
            achse.plot(iterationen,
                       [100.0 * (m / start if m else float("nan")) for m in massen],
                       color=FARBEN["mass"], lw=1.2, marker="o", markersize=2.5)
            if self.zielmasse:
                achse.axhline(100.0 * self.zielmasse, color=FARBEN["ziel"], ls="--", lw=1)
        achse.grid(True, alpha=0.3)
        achse.set_title("Optimization history", fontsize=9)

        # 2) Auslastung
        achse = self._achsen[2]
        achse.cla()
        achse.set_ylabel("FI", fontsize=8)
        achse.tick_params(labelsize=7, labelbottom=False)
        if any(v is not None for v in fi_mean):
            achse.plot(iterationen, fi_mean, color=FARBEN["fi_mean"], lw=1.2, marker="o",
                       markersize=2.2, label="FI_mean")
        if any(v is not None for v in fi_max):
            achse.plot(iterationen, fi_max, color=FARBEN["fi_max"], lw=1.2, marker="o",
                       markersize=2.2, label="FI_max")
            achse.axhline(1.0, color=FARBEN["grenze"], ls="--", lw=1, label="limit 1.0")
            achse.legend(loc="upper right", fontsize=7)
        else:
            achse.text(0.5, 0.5, "no failure index in this run", ha="center", va="center",
                       fontsize=7, color="#666666", transform=achse.transAxes)
        achse.grid(True, alpha=0.3)

        # 3) überlastete Elemente
        achse = self._achsen[1]
        achse.cla()
        achse.set_ylabel("overloaded", fontsize=8)
        achse.tick_params(labelsize=7, labelbottom=False)
        if any(v is not None for v in ueberlastet):
            werte = [0 if v is None else v for v in ueberlastet]
            achse.step(iterationen, werte, where="post", color=FARBEN["fi_verletzt"], lw=1.2,
                       marker="o", markersize=2.2)
            achse.set_ylim(bottom=-0.5)
        else:
            achse.text(0.5, 0.5, "no failure index in this run", ha="center", va="center",
                       fontsize=7, color="#666666", transform=achse.transAxes)
        achse.grid(True, alpha=0.3)

        # 4) Energiedichte
        achse = self._achsen[0]
        achse.cla()
        achse.set_xlabel("iteration", fontsize=8)
        achse.set_ylabel("energy density", fontsize=8)
        achse.tick_params(labelsize=7)
        if any(v is not None for v in energien):
            achse.plot(iterationen, energien, color=FARBEN["ener"], lw=1.2, marker="o",
                       markersize=2.2)
        achse.grid(True, alpha=0.3)

        try:
            fenster.fig.canvas.draw()
        except Exception:
            pass

    def _warte_hinweis(self):
        """Platzhalter, solange die erste Iteration noch läuft."""
        fenster = self._sorge_fuer_fenster()
        if fenster is None or not self._achsen:
            return
        for achse in self._achsen:
            try:
                achse.cla()
            except Exception:
                pass
        achse = self._achsen[0]
        gelaufen = ""
        if self._start_zeit:
            sekunden = int(max(0, time.time() - self._start_zeit))
            gelaufen = "Optimization running for %d:%02d\n" % (sekunden // 60, sekunden % 60)
        achse.text(0.5, 0.55,
                   gelaufen + "no iteration finished yet - the preparation is running:\n"
                   "reading the input file and building the filter neighbourhood",
                   ha="center", va="center", fontsize=8, transform=achse.transAxes)
        achse.text(0.5, 0.28,
                   "The first iteration of a fine mesh takes a while.\n"
                   "After that one point is added per iteration.",
                   ha="center", va="center", fontsize=7.5, color="#666666",
                   transform=achse.transAxes)
        try:
            fenster.fig.canvas.draw()
        except Exception:
            pass
