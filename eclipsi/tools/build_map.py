"""
Construeix data/map.json: contorn de la peninsula (Natural Earth, domini public)
i la FRANJA DE TOTALITAT calculada, no dibuixada a ma.

La franja surt d'avaluar en una reixa de punts la magnitud maxima de l'eclipsi
(separacio angular Sol-Lluna contra els radis aparents, la mateixa geometria que
tools/ephemeris.py) i extreure'n la frontera magnitud = 1.

  uv run --python 3.12 --with skyfield --with numpy --with matplotlib python tools/build_map.py
  ... --bench   nomes cronometra una reixa petita
"""
import os, sys, json, math, ssl, urllib.request, time
import numpy as np
from skyfield.api import load, wgs84

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "build", "ne_50m_admin_0_countries.geojson")
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
          "master/geojson/ne_50m_admin_0_countries.geojson")

R_SUN_KM, R_MOON_KM = 695700.0, 1737.4
SITE = (40.744444, -1.735556, 1284.0)          # Anquela del Pedregal
LON0, LON1, LAT0, LAT1 = -10.0, 4.5, 35.0, 44.2
LAT_REF = 40.0

CITIES = [("Madrid", 40.4168, -3.7038), ("Barcelona", 41.3874, 2.1686),
          ("Valencia", 39.4699, -0.3763), ("Bilbao", 43.2630, -2.9350),
          ("Terol", 40.3456, -1.1065), ("Burgos", 42.3439, -3.6969),
          ("Saragossa", 41.6488, -0.8891)]


# ---------------------------------------------------------------- contorn
def fetch_countries():
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        req = urllib.request.Request(NE_URL, headers={"User-Agent": "eclipsi-build/1.0"})
        with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()) as r:
            open(CACHE, "wb").write(r.read())
        print(f"  descarregat Natural Earth 50m ({os.path.getsize(CACHE)//1024} kB)")
    else:
        print("  Natural Earth en memoria cau")
    return json.load(open(CACHE, encoding="utf-8"))


def rdp(pts, eps):
    """Simplificacio Douglas-Peucker."""
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0]), np.array(pts[-1])
    ab = b - a
    n = np.hypot(*ab)
    P = np.array(pts)
    if n == 0:
        d = np.hypot(*(P - a).T)
    else:
        q = P - a                                  # producte vectorial 2D a ma
        d = np.abs(ab[0] * q[:, 1] - ab[1] * q[:, 0]) / n
    i = int(np.argmax(d))
    if d[i] > eps:
        return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [pts[0], pts[-1]]


def in_view(ring):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return not (max(xs) < LON0 - 1 or min(xs) > LON1 + 1
                or max(ys) < LAT0 - 1 or min(ys) > LAT1 + 1)


def land_paths(gj):
    want = {"Spain", "Portugal", "France", "Andorra", "Morocco", "Algeria"}
    out = []
    for f in gj["features"]:
        p = f["properties"]
        nm = p.get("NAME") or p.get("ADMIN")
        if nm not in want:
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = [(float(x), float(y)) for x, y in poly[0]]
            if not in_view(ring) or len(ring) < 4:
                continue
            simp = rdp(ring, 0.02)
            if len(simp) >= 4:
                out.append({"name": nm, "ring": simp})
    return out


# ------------------------------------------------------- franja de totalitat
def magnitude_grid(step, t_coarse=60.0, verbose=True):
    eph = load("de421.bsp")
    ts = load.timescale()
    earth, sun, moon = eph["earth"], eph["sun"], eph["moon"]

    t0 = ts.utc(2026, 8, 12, 17, 50, 0)
    t1 = ts.utc(2026, 8, 12, 19, 10, 0)
    n = int((t1.tt - t0.tt) * 86400 / t_coarse) + 1
    tt = ts.tt_jd(np.linspace(t0.tt, t1.tt, n))

    lons = np.arange(LON0, LON1 + 1e-9, step)
    lats = np.arange(LAT0, LAT1 + 1e-9, step)
    mag = np.zeros((len(lats), len(lons)))
    dur = np.zeros((len(lats), len(lons)))
    t_start = time.time()

    for i, la in enumerate(lats):
        for j, lo in enumerate(lons):
            site = earth + wgs84.latlon(la, lo)
            a = site.at(tt)
            s, m = a.observe(sun).apparent(), a.observe(moon).apparent()
            sep = s.separation_from(m).degrees
            rs = np.degrees(np.arcsin(R_SUN_KM / s.distance().km))
            rm = np.degrees(np.arcsin(R_MOON_KM / m.distance().km))
            g = (rs + rm - sep) / (2 * rs)
            k = int(np.argmax(g))
            # refinament de +-1 pas gruixut a 4 s
            lo_i, hi_i = max(0, k - 1), min(n - 1, k + 1)
            tf = ts.tt_jd(np.linspace(tt.tt[lo_i], tt.tt[hi_i],
                                      max(3, int((hi_i - lo_i) * t_coarse / 4) + 1)))
            af = site.at(tf)
            sf, mf = af.observe(sun).apparent(), af.observe(moon).apparent()
            sepf = sf.separation_from(mf).degrees
            rsf = np.degrees(np.arcsin(R_SUN_KM / sf.distance().km))
            rmf = np.degrees(np.arcsin(R_MOON_KM / mf.distance().km))
            gf = (rsf + rmf - sepf) / (2 * rsf)
            mag[i, j] = gf.max()
            tot = sepf <= (rmf - rsf)
            if tot.any():
                span = (tf.tt[tot].max() - tf.tt[tot].min()) * 86400
                dur[i, j] = span
        if verbose and i % 5 == 0:
            el = time.time() - t_start
            print(f"    fila {i+1}/{len(lats)}  {el:.0f}s transcorreguts", flush=True)
    return lons, lats, mag, dur


def contour_paths(lons, lats, mag, level=1.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    cs = ax.contour(lons, lats, mag, levels=[level])
    segs = []
    for p in cs.get_paths():
        v = p.vertices
        if len(v) >= 3:
            segs.append([(float(x), float(y)) for x, y in v])
    plt.close(fig)
    return segs


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


# ---------------------------------------------------------------- projeccio
W, H = 1000.0, None
def project(lon, lat):
    k = math.cos(math.radians(LAT_REF))
    x = (lon - LON0) * k
    y = (LAT1 - lat)
    sx = W / ((LON1 - LON0) * k)
    return x * sx, y * sx


def to_path(ring, close=True):
    d = []
    for i, (lo, la) in enumerate(ring):
        x, y = project(lo, la)
        d.append(("M" if i == 0 else "L") + f"{x:.1f} {y:.1f}")
    return " ".join(d) + (" Z" if close else "")


def main():
    bench = "--bench" in sys.argv
    os.makedirs(DATA, exist_ok=True)

    print("1) contorn")
    land = land_paths(fetch_countries())
    print(f"   {len(land)} poligons dins la vista")

    print("2) franja de totalitat")
    step = 1.0 if bench else 0.1
    t0 = time.time()
    lons, lats, mag, dur = magnitude_grid(step)
    print(f"   reixa {mag.shape} en {time.time()-t0:.0f} s  (magnitud max {mag.max():.4f})")
    if bench:
        print("   BENCH acabat"); return

    segs = contour_paths(lons, lats, mag, 1.0)
    print(f"   {len(segs)} segments de frontera")

    # --- comprovacio de correccio: el punt d'observacio ha de caure dins
    inside = any(point_in_poly((SITE[1], SITE[0]), s) for s in segs)
    d_here = float(np.interp(SITE[0], lats, dur[:, int(np.argmin(np.abs(lons - SITE[1])))]))
    print(f"   Anquela dins la franja: {inside}   durada interpolada: {d_here:.0f} s")
    if not inside:
        print("   !! ERROR: el punt d'observacio cau FORA de la franja calculada")

    _, _, W2, H2 = 0, 0, *project(LON1, LAT0)
    out = {
        "viewBox": [0, 0, round(W2, 1), round(H2, 1)],
        "bounds": {"lon": [LON0, LON1], "lat": [LAT0, LAT1]},
        "land": [{"name": p["name"], "d": to_path(p["ring"])} for p in land],
        "totality": [to_path(s, close=True) for s in segs],
        "site": {"name": "Anquela del Pedregal", "lat": SITE[0], "lon": SITE[1],
                 "xy": [round(v, 1) for v in project(SITE[1], SITE[0])],
                 "inside_band": bool(inside), "totality_s": round(d_here, 1)},
        "cities": [{"name": n, "xy": [round(v, 1) for v in project(lo, la)]}
                   for n, la, lo in CITIES],
    }
    json.dump(out, open(os.path.join(DATA, "map.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"   escrit map.json ({os.path.getsize(os.path.join(DATA,'map.json'))//1024} kB)")


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
