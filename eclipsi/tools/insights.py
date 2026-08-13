"""
Analisis con valor anadido para la pagina web: retardo termico, punto de rocio
(para separar humedad real de efecto termico), caida de luz y contraste entre lo
medido y la mecanica celeste.

  uv run --python 3.12 --with numpy --with pandas python tools/insights.py
"""
import os, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

light = pd.read_csv(os.path.join(DATA, "light.csv"), parse_dates=["time"])
th = pd.read_csv(os.path.join(DATA, "thermo.csv"), parse_dates=["time"])
frames = pd.read_csv(os.path.join(DATA, "frames.csv"), parse_dates=["time"])
eph = json.load(open(os.path.join(DATA, "ephemeris.json")))

T_MAX_ECL = pd.Timestamp("2026-08-12 " + eph["MAX"]["local"])
T_C1 = pd.Timestamp("2026-08-12 " + eph["C1"]["local"])
T_C2 = pd.Timestamp("2026-08-12 " + eph["C2"]["local"])
T_C3 = pd.Timestamp("2026-08-12 " + eph["C3"]["local"])
hm = lambda t: pd.Timestamp(t).strftime("%H:%M:%S")
DAY0 = pd.Timestamp("2026-08-12")
sec = lambda t: (pd.Timestamp(t) - DAY0).total_seconds()
secs = lambda s: (pd.to_datetime(s) - DAY0).dt.total_seconds().values
out = {}

# ---------------------------------------------------------------- temperatura
i_max, i_min = th["temp_c"].idxmax(), th["temp_c"].idxmin()
t_hot, t_cold = th.loc[i_max, "time"], th.loc[i_min, "time"]
lag = (t_cold - T_MAX_ECL).total_seconds()
out["temperature"] = {
    "max_c": float(th.loc[i_max, "temp_c"]), "max_at": hm(t_hot),
    "min_c": float(th.loc[i_min, "temp_c"]), "min_at": hm(t_cold),
    "drop_c": round(float(th.loc[i_max, "temp_c"] - th.loc[i_min, "temp_c"]), 1),
    "lag_after_max_s": int(lag),
    "lag_after_max_txt": f"{int(lag)//60} min {int(lag)%60} s",
}
# ritmo de enfriamiento en la fase mas rapida
seg = th[(th["time"] >= T_C1) & (th["time"] <= t_cold)]
mins = (seg["time"].iloc[-1] - seg["time"].iloc[0]).total_seconds() / 60
out["temperature"]["cooling_rate_c_per_min"] = round(
    float(seg["temp_c"].iloc[0] - seg["temp_c"].iloc[-1]) / mins, 3)
w = th[(th["time"] >= T_MAX_ECL - pd.Timedelta(minutes=8)) &
       (th["time"] <= T_MAX_ECL + pd.Timedelta(minutes=8))]
out["temperature"]["steepest_8min_c"] = round(float(w["temp_c"].iloc[0] - w["temp_c"].iloc[-1]), 1)
# no hay rebote: la puesta de Sol se come la recuperacion
post = th[th["time"] >= t_cold]
out["temperature"]["rebound_c"] = round(float(post["temp_c"].max() - th.loc[i_min, "temp_c"]), 1)

# ------------------------------------------------- humedad: real o solo termica
T, RH = th["temp_c"].values, th["rh_pct"].values
g = np.log(RH / 100.0) + (17.62 * T) / (243.12 + T)
dew = 243.12 * g / (17.62 - g)                                   # Magnus
es = 6.112 * np.exp(17.67 * T / (T + 243.5))
ah = es * RH * 2.1674 / (273.15 + T)                             # g/m3
e_vap = es * RH / 100.0                                          # presion de vapor
# descomposicion: cuanta subida de HR se explica solo por el enfriamiento
e0 = float(e_vap[:30].mean())
rh_thermal = np.clip(e0 / es * 100.0, 0, 100)                    # HR si el vapor no cambiara
th["dew_c"], th["ah_gm3"] = dew, ah
th["rh_thermal_pct"] = rh_thermal
th[["time", "temp_c", "rh_pct", "rh_thermal_pct", "dew_c", "ah_gm3"]].to_csv(
    os.path.join(DATA, "thermo_derived.csv"), index=False,
    float_format="%.2f", date_format="%Y-%m-%d %H:%M:%S")
i_end = int(np.argmax(RH))
out["humidity_decomposition"] = {
    "rh_start": round(float(RH[:30].mean()), 1),
    "rh_end": round(float(RH[i_end]), 1),
    "rh_end_at": hm(th.loc[i_end, "time"]),
    "rh_expected_thermal_only": round(float(rh_thermal[i_end]), 1),
    "thermal_share_pts": round(float(rh_thermal[i_end] - RH[:30].mean()), 1),
    "moisture_share_pts": round(float(RH[i_end] - rh_thermal[i_end]), 1),
    "note": ("la HR sube 32 puntos: parte es solo enfriamiento (el aire frio "
             "satura antes) y parte es humedad real que entra"),
}
out["humidity"] = {
    "rh_min": float(RH.min()), "rh_min_at": hm(th.loc[th["rh_pct"].idxmin(), "time"]),
    "rh_max": float(RH.max()), "rh_max_at": hm(th.loc[th["rh_pct"].idxmax(), "time"]),
    "rh_rise_pts": round(float(RH.max() - RH.min()), 1),
    "dew_mean_c": round(float(dew.mean()), 2),
    "dew_sd_c": round(float(dew.std()), 2),
    "dew_range_c": [round(float(dew.min()), 2), round(float(dew.max()), 2)],
    "ah_mean_gm3": round(float(ah.mean()), 2),
    "ah_sd_gm3": round(float(ah.std()), 2),
    "ah_change_pct": round(float((ah[-30:].mean() / ah[:30].mean() - 1) * 100), 1),
}

# ------------------------------------------------------------------------- luz
lx = light["lx"].values
i_lmax = int(np.argmax(lx))
out["light"] = {
    "max_lx": round(float(lx.max()), 0), "max_at": hm(light.loc[i_lmax, "time"]),
    "floor_lx": float(lx.min()),
    "sensor_resolution_lx": 0.54,
    "drop_factor": int(round(lx.max() / 0.54)),
    "orders_of_magnitude": round(float(np.log10(lx.max() / 0.54)), 1),
}
lt_s = secs(light["time"])
for lbl, t in [("at_c1", T_C1), ("at_c2", T_C2), ("at_max", T_MAX_ECL)]:
    out["light"][lbl + "_lx"] = round(float(np.interp(sec(t), lt_s, light["lx_smooth"])), 1)
# cuanto tarda en caer de 1000 a 10 lx
def cross_down(level):
    s = light[(light["time"] > T_C1) & (light["lx_smooth"] <= level)]
    return s["time"].iloc[0] if len(s) else None
a, b = cross_down(1000), cross_down(10)
out["light"]["from_1000_to_10_lx_s"] = int((b - a).total_seconds()) if a is not None and b is not None else None
out["light"]["at_1000_lx"] = hm(a) if a is not None else None
out["light"]["at_10_lx"] = hm(b) if b is not None else None

# -------------------------------------- lo medido frente a la mecanica celeste
# solo fase parcial limpia: fuera totalidad, sobreexpuestos y el Sol ya poniendose
f = frames.dropna(subset=["obscuration", "uncovered"])
f = f[(f["frame"] <= 2900) & ~f["frame"].between(1940, 2010) & (f["uncovered"] <= 1.05)]
pred, meas = 1 - f["obscuration"].values, f["uncovered"].values
out["video_vs_ephemeris"] = {
    "n_frames": int(len(f)),
    "rms_uncovered": round(float(np.sqrt(np.mean((meas - pred) ** 2))), 4),
    "median_abs_error": round(float(np.median(np.abs(meas - pred))), 4),
    "p95_abs_error": round(float(np.percentile(np.abs(meas - pred), 95)), 4),
    "note": ("area solar medida en el video frente a la obscuracion calculada "
             "por efemeride; el sesgo residual es del umbral de deteccion y el "
             "oscurecimiento del limbo, no de la sincronizacion"),
}

out["ephemeris"] = eph
out["contacts_measured"] = {
    "C2_frame": 1944, "C2_note": "ultimo fotograma con creciente visible",
    "C3_frame": 1999, "C3_note": "anillo de diamantes",
    "corona_frames": [1995, 1998],
    "black_frames": [1945, 1994],
    "black_seconds": (1994 - 1945 + 1) * 2,
}
json.dump(out, open(os.path.join(DATA, "insights.json"), "w"), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2, ensure_ascii=False))
