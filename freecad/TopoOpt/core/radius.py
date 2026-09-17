# SPDX-License-Identifier: LGPL-3.0-or-later
"""The filter radius.

beso takes **2 x the mean element size** for ``"auto"``.  On a graded mesh (fine and
coarse areas, as Netgen and Gmsh produce them) the largest elements are further apart
than that value: single elements then have no neighbour in the radius, the "simple"
filter stops and beso reports convergence at the end although nothing was filtered
(measured case: beso's "auto" 3.395 mm left 2 elements without neighbours, the robust
value 4.244 mm = 2.5 x mean left none).

The robust radius is therefore the **smallest multiple of the mean element size at
which every element of the design space still has a neighbour**.  This module does not
calculate elements or neighbourhoods itself - beso does that (see
``beso/CHANGES-TopoOpt.md``); here only the multiples are tried out.
"""

from . import beso as beso_modul

#: multiples of the mean element size, tried in this order
FAKTOREN = (2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
#: beso's own rule ("auto" in beso_conf.py)
BESO_AUTO = 2.0


def gelesen(inp_pfad, alle_domains, design_domains):
    """Element sizes and centres of the design space, read by beso.

    ``alle_domains`` are the element sets of the input file, ``design_domains`` the ones
    that are optimized.  Returns a dict with ``mittel`` (mean element size), ``maximum``,
    ``anzahl`` (number of elements) and the data beso needs for the neighbourhood
    (``cg``, ``cg_min``, ``cg_max``, ``opt_domains``).  Empty dict if nothing was found.
    """
    lib, filters = beso_modul.module()
    domains_from_config = list(alle_domains)
    domain_optimized = {name: (name in design_domains) for name in domains_from_config}
    gelesen_inp = lib.import_inp(inp_pfad, domains_from_config, domain_optimized, False)
    nodes, elements, opt_domains = gelesen_inp[0], gelesen_inp[1], gelesen_inp[3]
    cg, cg_min, cg_max = lib.elm_volume_cg(inp_pfad, nodes, elements)[:3]
    groessen = filters.find_size_elm(elements, nodes)
    werte = [groessen[en] for en in opt_domains if groessen.get(en, 0) > 0]
    if not werte:
        return {}
    return {"mittel": sum(werte) / len(werte), "maximum": max(werte), "anzahl": len(werte),
            "cg": cg, "cg_min": cg_min, "cg_max": cg_max, "opt_domains": opt_domains}


def ohne_nachbarn_beso(daten, radius):
    """Elements without a neighbour, counted by beso itself (prepare2s).

    Kept for the comparison in the tests: this is the reference the fast check has to
    match.
    """
    lib, filters = beso_modul.module()
    # beso_main.py starts these as empty dicts and hands them to prepare2s
    weight_factor2 = {}
    near_elm = {}
    weight_factor2, near_elm = filters.prepare2s(daten["cg"], daten["cg_min"], daten["cg_max"],
                                                 radius, daten["opt_domains"],
                                                 weight_factor2, near_elm)
    return [en for en in daten["opt_domains"] if not near_elm.get(en)]


def ohne_nachbarn(daten, radius):
    """Elements without a neighbour in the radius.

    Same rule as beso (``prepare2s``): the centres of two elements count as neighbours
    when their distance is **smaller** than the radius; beso also looks into the
    neighbouring cells of its grid (cell size = radius, so +-1 cell is enough).

    Difference to beso: beso builds the whole neighbourhood (measured: 11.8 million
    pairs and 10.0 s for 58,871 elements), this check stops at the first neighbour and
    stores nothing.  Same result, only the answer to "is every element fine?" - the
    test compares both.
    """
    zellen = {}
    for en in daten["opt_domains"]:
        c = daten["cg"][en]
        zellen.setdefault((int(c[0] // radius), int(c[1] // radius), int(c[2] // radius)),
                          []).append(en)
    grenze = radius * radius
    fehlend = []
    for en in daten["opt_domains"]:
        c = daten["cg"][en]
        zx, zy, zz = int(c[0] // radius), int(c[1] // radius), int(c[2] // radius)
        gefunden = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for en2 in zellen.get((zx + dx, zy + dy, zz + dz), ()):
                        if en2 == en:
                            continue
                        c2 = daten["cg"][en2]
                        if ((c[0] - c2[0]) ** 2 + (c[1] - c2[1]) ** 2
                                + (c[2] - c2[2]) ** 2) < grenze:
                            gefunden = True
                            break
                    if gefunden:
                        break
                if gefunden:
                    break
            if gefunden:
                break
        if not gefunden:
            fehlend.append(en)
    return fehlend


def robust(daten):
    """Smallest multiple of the mean size at which no element is left without one.

    Returns a dict with ``faktor``, ``radius`` and ``ohne_nachbarn`` (0 when a multiple
    worked).  An empty dict when there are no element data.
    """
    if not daten:
        return {}
    fehlend = []
    for faktor in FAKTOREN:
        fehlend = ohne_nachbarn(daten, faktor * daten["mittel"])
        if not fehlend:
            return {"faktor": faktor, "radius": faktor * daten["mittel"], "ohne_nachbarn": 0}
    return {"faktor": FAKTOREN[-1], "radius": FAKTOREN[-1] * daten["mittel"],
            "ohne_nachbarn": len(fehlend)}
