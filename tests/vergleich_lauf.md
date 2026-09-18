# Ehrlicher Vergleich: Original-beso · alte Workbench · neue Workbench

Gemessen am 18.09.2026 auf diesem Rechner. Verglichen werden die drei Stände, die es
wirklich gibt – nicht einzelne Skripte:

| Kürzel | Was genau |
|---|---|
| **original** | frischer Klon von `github.com/calculix/beso`, HEAD `5056d30`, **unverändert** |
| **prototyp** | `vendor/beso` der alten Workbench (mit deren eigenen Umbauten: Gitter-Dict in `prepare2s`, numpy-Matrix, 241 Zeilen Unterschied) |
| **addon** | gebündeltes beso des Addons (Original + unsere 3 Fixes + Dickenprüfung) |

## 1. Vorbereitungszeit (das Stück, das der Prototyp umgebaut hat)

Modell: `FEMMeshNetgen001.inp`, 12,8 MB, 84.395 Volumenelemente, 22.464.332 Nachbarpaare,
Element-Set `MaterialSolid001Solid` (`tests/vergleich_varianten.py`)

| Variante | Netz lesen | Volumen/CG | Elementgrößen | **Nachbarschaftsgitter** | Summe |
|---|---|---|---|---|---|
| original | 0,36 s | 3,41 s | 0,12 s | **27,6 s** | 31,5 s |
| prototyp | 0,36 s | 3,38 s | 0,12 s | **104,9 s** | 108,7 s |
| addon | 0,36 s | 3,39 s | 0,12 s | **26,8 s** | 30,7 s |

→ **Original und Addon sind gleich schnell** (26,8 zu 27,6 s, 3 % Streuung), der Prototyp
ist beim 3D-Netz **3,8× langsamer**.  Alle drei finden exakt dieselbe mittlere
Elementgröße (1,3343 mm) und dieselbe Zahl Nachbarpaare – die Umbauten ändern die
Rechnung also nicht, beim großen 3D-Netz kosten sie aber Zeit.

## 2. Kompletter Lauf auf einem echten Modell (`tests/vergleich_lauf.py`)

Basis ist ein **echter, früher gelaufener Arbeitsordner** der alten Workbench
(Modell `FEMMeshNetgen.inp`, 58.871 Elemente, Konfiguration der alten Workbench:
`filter_list = [['simple', 2.3214]]`, `mass_goal_ratio = 0.6`, `iterations_limit = 3`).
In drei Kopien wurde nur die beso-Kopie ausgetauscht und `path` angepasst.

| Variante | Gesamtzeit | Rückgabewert | Massen der Iterationen 0–3 |
|---|---|---|---|
| original | 97,2 s | 0 | 5,233986579481923e-05 · 5,076871505084876e-05 · 5,0006983356593286e-05 · 4,925693374653859e-05 |
| prototyp | 95,2 s | 0 | **identisch** |
| addon | 95,7 s | 0 | **identisch** |

→ **Bit-identische Massen** bei allen drei Ständen und **gleiche Laufzeit** (Unterschied
unter 2 %, also Messrauschen).  Die neue Workbench rechnet damit nachweislich genau so
wie das Original-Makro und wie die alte Workbench.

## 3. Einordnung

* Unsere 3 Fixes kosten **keine** Rechenzeit – der Einzelvergleich original ↔ addon
  liegt innerhalb der Streuung (und ist beim 3D-Netz sogar minimal schneller).
* Der Umbau im Prototyp bringt **keinen** Geschwindigkeitsvorteil gegenüber dem Original;
  beim großen 3D-Netz kostet er deutlich Zeit.
* Ehrliche Grenzen: je ein Modell pro Aussage, ein Lauf je Variante, keine Aussage über
  andere Netze, Netzwerkspeicher oder andere Rechner.  Gemessen auf demselben Gerät zur
  selben Zeit, damit die Zahlen vergleichbar sind.
