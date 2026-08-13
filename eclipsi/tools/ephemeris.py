"""
Circunstancias reales del eclipse total del 2026-08-12 desde Anquela del Pedregal
(Guadalajara). Calcula C1..C4, magnitud, obscuracion y altura del Sol, y las
compara con lo medido en el video y en el sensor de luz.

uv run --python 3.12 --with skyfield --with numpy python tools/ephemeris.py
"""
import os, json
import numpy as np
from skyfield.api import load, wgs84
from skyfield.framelib import ecliptic_frame  # noqa: F401  (fuerza descarga de datos)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

LAT, LON, ELEV = 40.744444, -1.735556, 1284.0
SITE_NAME = "Anquela del Pedregal (Guadalajara)"

R_SUN_KM = 695700.0
R_MOON_KM = 1737.4

eph = load("de421.bsp")
ts = load.timescale()
earth, sun, moon = eph["earth"], eph["sun"], eph["moon"]
site = earth + wgs84.latlon(LAT, LON, elevation_m=ELEV)

# rejilla de 0.5 s cubriendo la tarde del 12/08/2026 (UTC)
t0 = ts.utc(2026, 8, 12, 17, 0, 0)
t1 = ts.utc(2026, 8, 12, 19, 30, 0)
n = int((t1.tt - t0.tt) * 86400 * 2) + 1
tt = ts.tt_jd(np.linspace(t0.tt, t1.tt, n))

s = site.at(tt).observe(sun).apparent()
m = site.at(tt).observe(moon).apparent()

sep = s.separation_from(m).degrees                      # separacion de centros
d_sun = s.distance().km
d_moon = m.distance().km
r_sun = np.degrees(np.arcsin(R_SUN_KM / d_sun))         # radios aparentes
r_moon = np.degrees(np.arcsin(R_MOON_KM / d_moon))
alt_sun = s.altaz()[0].degrees
az_sun = s.altaz()[1].degrees

secs = (tt.tt - t0.tt) * 86400.0

def cross(y, target, rising):
    """instantes (s desde t0) en que y cruza target"""
    d = y - target
    idx = np.nonzero(np.diff(np.sign(d)))[0]
    out = []
    for i in idx:
        if rising is not None and ((d[i + 1] > d[i]) != rising):
            continue
        f = -d[i] / (d[i + 1] - d[i])
        out.append(secs[i] + f * (secs[i + 1] - secs[i]))
    return out

ext = r_sun + r_moon          # tangencia exterior -> C1, C4
inn = np.abs(r_moon - r_sun)  # tangencia interior -> C2, C3

c_ext = cross(sep - ext, 0.0, None)
c_inn = cross(sep - inn, 0.0, None)
contacts = {}
if len(c_ext) >= 2:
    contacts["C1"], contacts["C4"] = min(c_ext), max(c_ext)
if len(c_inn) >= 2:
    contacts["C2"], contacts["C3"] = min(c_inn), max(c_inn)

imax = int(np.argmin(sep))
# refina el maximo con una parabola
if 0 < imax < len(sep) - 1:
    y0, y1_, y2 = sep[imax - 1], sep[imax], sep[imax + 1]
    dx = 0.5 * (y0 - y2) / (y0 - 2 * y1_ + y2)
else:
    dx = 0.0
t_max = secs[imax] + dx * (secs[1] - secs[0])
contacts["MAX"] = t_max

def obscuration(sep_deg, rs, rm):
    """fraccion del AREA del disco solar cubierta"""
    d, r, R = sep_deg, rs, rm
    if d >= r + R: return 0.0
    if d <= abs(R - r): return 1.0 if R >= r else (R * R) / (r * r)
    d2, r2, R2 = d * d, r * r, R * R
    a1 = np.arccos((d2 + r2 - R2) / (2 * d * r))
    a2 = np.arccos((d2 + R2 - r2) / (2 * d * R))
    area = r2 * (a1 - np.sin(2 * a1) / 2) + R2 * (a2 - np.sin(2 * a2) / 2)
    return float(area / (np.pi * r2))

def at(sec):
    i = float(np.interp(sec, secs, np.arange(len(secs))))
    lo, hi = int(i), min(int(i) + 1, len(secs) - 1)
    w = i - lo
    g = lambda a: a[lo] * (1 - w) + a[hi] * w
    return dict(sep=g(sep), r_sun=g(r_sun), r_moon=g(r_moon),
                alt=g(alt_sun), az=g(az_sun))

def local(sec):
    from datetime import timedelta
    d = t0.utc_datetime() + timedelta(seconds=float(sec) + 2 * 3600)
    return d.strftime("%H:%M:%S")

print(f"=== {SITE_NAME} ===")
print(f"    {LAT:.5f} N, {abs(LON):.5f} W, {ELEV:.0f} m\n")
print(f"{'evento':6} {'hora local':>11} {'alt Sol':>8} {'az':>7}  {'obsc':>7}")
res = {}
for k in ["C1", "C2", "MAX", "C3", "C4"]:
    if k not in contacts: continue
    sec = contacts[k]; v = at(sec)
    ob = obscuration(v["sep"], v["r_sun"], v["r_moon"])
    print(f"{k:6} {local(sec):>11} {v['alt']:7.2f}° {v['az']:6.1f}° {ob*100:6.2f}%")
    res[k] = dict(local=local(sec), alt=round(v["alt"], 2), az=round(v["az"], 1),
                  obscuration=round(ob, 5))

vmax = at(contacts["MAX"])
mag = (vmax["r_sun"] + vmax["r_moon"] - vmax["sep"]) / (2 * vmax["r_sun"])
print(f"\nmagnitud (max)            : {mag:.4f}")
print(f"radio aparente Sol / Luna : {vmax['r_sun']*60:.3f}' / {vmax['r_moon']*60:.3f}'")
if "C2" in contacts and "C3" in contacts:
    dur = contacts["C3"] - contacts["C2"]
    print(f"duracion de la totalidad  : {dur:.1f} s  ({int(dur//60)}m {dur%60:04.1f}s)")
    res["totality_s"] = round(dur, 1)
if "C1" in contacts and "C4" in contacts:
    print(f"duracion total del evento : {(contacts['C4']-contacts['C1'])/60:.1f} min")

# puesta de Sol
alt_after = alt_sun.copy()
iset = np.nonzero(np.diff(np.sign(alt_after)))[0]
if len(iset):
    i = iset[-1]
    f = -alt_after[i] / (alt_after[i + 1] - alt_after[i])
    print(f"puesta de Sol (alt=0)     : {local(secs[i] + f * (secs[i+1]-secs[i]))}")
    res["sunset"] = local(secs[i] + f * (secs[i + 1] - secs[i]))

print("\n=== comparacion con lo medido ===")
print(f"  maximo   calculado {res['MAX']['local']}   medido (curva de luz) 20:32:37")
if "C2" in res:
    print(f"  C2       calculado {res['C2']['local']}   medido (video, fot. 1944/1945) 20:31:48")
    print(f"  C3       calculado {res['C3']['local']}   medido (video, anillo fot. 1999) 20:33:36")

res["site"] = dict(name=SITE_NAME, lat=LAT, lon=LON, elev_m=ELEV)
res["magnitude"] = round(float(mag), 4)
json.dump(res, open(os.path.join(OUT, "ephemeris.json"), "w"), indent=2)

# curva de obscuracion cada 10 s, para la web
rows = []
for sec in np.arange(secs[0], secs[-1], 10.0):
    v = at(sec)
    rows.append((local(sec), round(obscuration(v["sep"], v["r_sun"], v["r_moon"]), 5),
                 round(v["alt"], 3)))
with open(os.path.join(OUT, "obscuration.csv"), "w") as f:
    f.write("time,obscuration,sun_alt_deg\n")
    for r in rows: f.write(f"{r[0]},{r[1]},{r[2]}\n")
print(f"\nescrito ephemeris.json y obscuration.csv ({len(rows)} filas)")
