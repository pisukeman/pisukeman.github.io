"""
Eclipsi 2026-08-12 — exporta las tres fuentes a CSV con marca de tiempo absoluta
y deja todo sobre el mismo eje temporal (hora local, UTC+02:00).

Uso:
  uv run --python 3.12 --with numpy --with pandas --with xlrd --with openpyxl python tools/export_data.py
"""
import os, json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

# ----------------------------------------------------------------------------
# Sincronizacion (ver docs/SYNC.md)
#
# El video se ancla a la EFEMERIDE: la mitad de la totalidad observada en el
# video (fotograma 1971,5) es el maximo calculado para Anquela del Pedregal,
# 20:31:24. Con 2,000 s/fotograma los contactos C2 y C3 medidos caen a 1944,5 y
# 1998,5, y la efemeride los predice en 1946,0 y 1997,0: concuerdan dentro de
# 1,5 fotogramas, lo que fija el fotograma 0 con ~5 s de incertidumbre.
#
# El reloj del movil (sensor de luz) va ADELANTADO 55,5 s. Medido ajustando
# lx(t) = tendencia_suave(t) x (1 - obscuracion(t + off)) contra la efemeride:
# el minimo del residuo es nitido en off = -55,5 s (rms 0,049 frente a 0,096
# sin corregir). Probablemente sea el mapeo de phyphox entre el reloj del
# sensor y la hora del sistema. El registrador Elitech se toma como correcto.
# ----------------------------------------------------------------------------
FRAME0 = datetime.fromisoformat("2026-08-12 19:25:41")  # hora del fotograma 0
SEC_PER_FRAME = 2.0                                     # cadencia del timelapse
N_FRAMES = 3011
LIGHT_CLOCK_OFFSET_S = -55.5                            # correccion del reloj del movil
LAST_USEFUL_FRAME = 2975                                # a partir de aqui el Sol ya se puso

def frame_time(f):
    return FRAME0 + timedelta(seconds=f * SEC_PER_FRAME)

# ----------------------------------------------------------------------------
# 1) Luz (phyphox) -> 1 muestra/s
# ----------------------------------------------------------------------------
xl = pd.ExcelFile(os.path.join(HERE, "luminosity.xls"), engine="xlrd")
mt = xl.parse("Metadata Time", header=0)
start_txt = str(mt.iloc[0, 3])            # "2026-08-12 19:15:14.141 UTC+02:00"
LIGHT_START = datetime.fromisoformat(start_txt.split(" UTC")[0])

light = xl.parse("Light", header=0)
light.columns = ["t_rel", "lx"]
light = light.astype(float)
light["time"] = [LIGHT_START + timedelta(seconds=s + LIGHT_CLOCK_OFFSET_S)
                 for s in light["t_rel"]]
light["lx_smooth"] = light["lx"].rolling(15, center=True, min_periods=1).median()
light[["time", "t_rel", "lx", "lx_smooth"]].to_csv(
    os.path.join(DATA, "light.csv"), index=False, float_format="%.3f",
    date_format="%Y-%m-%d %H:%M:%S.%f")

# ----------------------------------------------------------------------------
# 2) Temperatura / humedad (Elitech RC-51H) -> 1 muestra/10 s
# ----------------------------------------------------------------------------
xt = pd.ExcelFile(os.path.join(HERE, "temp_humedad.xls"), engine="openpyxl")
th = xt.parse("Lista", header=0)
th.columns = ["n", "time", "temp_c", "rh_pct"]
th["time"] = pd.to_datetime(th["time"])
for c in ("temp_c", "rh_pct"):
    th[c] = th[c].astype(str).str.replace(",", ".").astype(float)
th[["time", "temp_c", "rh_pct"]].to_csv(
    os.path.join(DATA, "thermo.csv"), index=False, float_format="%.1f",
    date_format="%Y-%m-%d %H:%M:%S")

# ----------------------------------------------------------------------------
# 3) Indice de fotogramas: tiempo absoluto + metricas medidas sobre el video
# ----------------------------------------------------------------------------
stats_path = os.path.join(HERE, "build", "framestats.json")
frames = pd.DataFrame({"frame": np.arange(N_FRAMES)})
frames["time"] = [frame_time(f) for f in frames["frame"]]
if os.path.exists(stats_path):
    st = pd.DataFrame(json.load(open(stats_path)))
    full = float(np.median(st["area"][:250]))
    frames["sun_area_px"] = st["area"].values
    frames["uncovered"] = (st["area"] / full).clip(0, None).values
    frames["frame_max"] = st["max"].values
    frames["frame_mean"] = st["mean"].values

# interpola las metricas al instante de cada fotograma
li = light.set_index("time")["lx_smooth"]
frames["lx"] = np.interp(frames["time"].astype("int64"),
                         li.index.astype("int64"), li.values,
                         left=np.nan, right=np.nan)
ti = th.set_index("time")
for col, out in (("temp_c", "temp_c"), ("rh_pct", "rh_pct")):
    frames[out] = np.interp(frames["time"].astype("int64"),
                            ti.index.astype("int64"), ti[col].values,
                            left=np.nan, right=np.nan)

# obscuracion y altura del Sol calculadas (tools/ephemeris.py)
obs_path = os.path.join(DATA, "obscuration.csv")
if os.path.exists(obs_path):
    ob = pd.read_csv(obs_path)
    ob["time"] = pd.to_datetime("2026-08-12 " + ob["time"])
    for col in ("obscuration", "sun_alt_deg"):
        frames[col] = np.interp(frames["time"].astype("int64"),
                                ob["time"].astype("int64"), ob[col].values,
                                left=np.nan, right=np.nan)

frames.to_csv(os.path.join(DATA, "frames.csv"), index=False, float_format="%.4f",
              date_format="%Y-%m-%d %H:%M:%S")

# ----------------------------------------------------------------------------
# Resumen
# ----------------------------------------------------------------------------
summary = {
    "sync": {
        "frame0_local": FRAME0.isoformat(),
        "sec_per_frame": SEC_PER_FRAME,
        "n_frames": N_FRAMES,
        "last_frame_local": frame_time(N_FRAMES - 1).isoformat(),
        "last_useful_frame": LAST_USEFUL_FRAME,
        "last_useful_local": frame_time(LAST_USEFUL_FRAME).isoformat(),
        "light_clock_offset_s": LIGHT_CLOCK_OFFSET_S,
    },
    "light": {
        "start": light["time"].iloc[0].isoformat(),
        "end": light["time"].iloc[-1].isoformat(),
        "n": int(len(light)),
        "max_lx": float(light["lx"].max()),
    },
    "thermo": {
        "start": th["time"].iloc[0].isoformat(),
        "end": th["time"].iloc[-1].isoformat(),
        "n": int(len(th)),
        "temp_max": float(th["temp_c"].max()),
        "temp_max_at": th.loc[th["temp_c"].idxmax(), "time"].isoformat(),
        "temp_min": float(th["temp_c"].min()),
        "temp_min_at": th.loc[th["temp_c"].idxmin(), "time"].isoformat(),
        "rh_min": float(th["rh_pct"].min()),
        "rh_max": float(th["rh_pct"].max()),
    },
}
json.dump(summary, open(os.path.join(DATA, "summary.json"), "w"), indent=2)
print(json.dumps(summary, indent=2))
print("\nescrito en", DATA)
