# SPDX-License-Identifier: LGPL-3.0-or-later
"""Misst die Vorbereitungszeit einer beso-Kopie (Aufruf aus vergleich_varianten.py).

Parameter: <beso-ordner> <inp-datei> <elset>
Gibt eine Zeile mit den Zeiten aus, damit der Rahmen sie einsammeln kann.
Jede Variante laeuft in einem eigenen Prozess, weil jede ihr eigenes
beso_lib/beso_filters mitbringt.
"""
import os
import sys
import time

beso_ordner, inp, elset = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, beso_ordner)

import beso_filters                          # noqa: E402
import beso_lib                              # noqa: E402

t0 = time.time()
gelesen = beso_lib.import_inp(inp, [elset], {elset: True}, False)
t_import = time.time() - t0
nodes, elements, opt_domains = gelesen[0], gelesen[1], gelesen[3]

t0 = time.time()
cg, cg_min, cg_max = beso_lib.elm_volume_cg(inp, nodes, elements)[:3]
t_cg = time.time() - t0

t0 = time.time()
groessen = beso_filters.find_size_elm(elements, nodes)
t_size = time.time() - t0
mittel = sum(groessen[en] for en in opt_domains) / len(opt_domains)

t0 = time.time()
weight_factor2, near_elm = beso_filters.prepare2s(cg, cg_min, cg_max, 2.0 * mittel, opt_domains,
                                                 {}, {})
t_prep = time.time() - t0

print("MESSUNG|%.2f|%.2f|%.2f|%.2f|%d|%d|%.4f"
      % (t_import, t_cg, t_size, t_prep, len(opt_domains),
         sum(len(v) for v in near_elm.values()), mittel), flush=True)
sys.stdout.flush()
os._exit(0)
