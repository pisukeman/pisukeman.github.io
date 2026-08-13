"""
Genera lo que consume la pagina: series.json (datos remuestreados) y la galeria
de fotogramas recortados y normalizados.

  uv run --python 3.12 --with numpy --with pandas --with pillow python tools/export_web_assets.py
"""
import os, json, subprocess
import numpy as np
import pandas as pd
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, WEB = os.path.join(HERE, "data"), os.path.join(HERE, "assets")
os.makedirs(WEB, exist_ok=True)
_np = os.environ.get("FFMPEG_DIR", "")
FFMPEG = os.path.join(_np, "ffmpeg.exe") if _np else "ffmpeg"
SRC_W, SRC_H = 1080, 1920
CROP_X, CROP_Y, CROP_S = 20, 456, 1000
DAY0 = pd.Timestamp("2026-08-12")
mins = lambda s: (pd.to_datetime(s) - DAY0).dt.total_seconds().values / 60.0

# ----------------------------------------------------------------- series.json
light = pd.read_csv(os.path.join(DATA, "light.csv"), parse_dates=["time"])
th = pd.read_csv(os.path.join(DATA, "thermo_derived.csv"), parse_dates=["time"])
frames = pd.read_csv(os.path.join(DATA, "frames.csv"), parse_dates=["time"])
insights = json.load(open(os.path.join(DATA, "insights.json"), encoding="utf-8"))

L = light                                             # crudo, 1 Hz, sin diezmar ni suavizar
r2 = lambda a, n=2: [round(float(x), n) for x in a]
f = frames[(frames["frame"] <= 2900) & (frames["uncovered"] <= 1.05)].iloc[::8]

series = {
    "light":  {"t": r2(mins(L["time"]), 3), "lx": r2(np.clip(L["lx"], 0.4, None), 2)},
    "thermo": {"t": r2(mins(th["time"]), 3), "temp": r2(th["temp_c"], 1),
               "rh": r2(th["rh_pct"], 1), "rh_th": r2(th["rh_thermal_pct"], 1),
               "dew": r2(th["dew_c"], 2)},
    "sun":    {"t": r2(mins(f["time"]), 3),
               "measured": r2(f["uncovered"], 4),
               "computed": r2(1 - f["obscuration"], 4)},
    "insights": insights,
}
json.dump(series, open(os.path.join(DATA, "series.json"), "w"), separators=(",", ":"))
print("series.json:", os.path.getsize(os.path.join(DATA, "series.json")) // 1024, "kB",
      "| luz", len(series["light"]["t"]), "| termo", len(series["thermo"]["t"]),
      "| sol", len(series["sun"]["t"]))

# --------------------------------------------------------------- galeria
GALLERY = [
    (0,    "19:25:41", "Disc solar sencer, amb taques visibles. Onze minuts abans del primer contacte."),
    (318,  "19:36:17", "Primer contacte. La Lluna toca la vora del disc; a ull nu encara no es nota."),
    (700,  "19:49:21", "El mos ja és inconfusible."),
    (1200, "20:05:41", "Gairebé mig disc cobert."),
    (1700, "20:22:21", "La creixent s'estreny de pressa en els últims minuts."),
    (1944, "20:30:29", "Últim fotograma amb fotosfera visible, quatre segons abans del segon contacte."),
    (1970, "20:31:22", "Totalitat. Negre absolut: el filtre solar encara hi era posat."),
    (1996, "20:32:14", "Corona solar i protuberàncies, amb el filtre per fi retirat."),
    (1999, "20:32:20", "Anell de diamants: reapareix la fotosfera al tercer contacte."),
    (2100, "20:35:42", "Fina creixent de nou, ara per la banda contrària."),
    (2600, "20:52:21", "El Sol, ja baix, s'envermelleix camí de l'horitzó."),
    (2900, "21:02:21", "Últims fotogrames útils abans que el Sol es pongui."),
]
NORMALIZE, TARGET, ALPHA, GAIN_MAX, BLACK_P = True, 238.0, 0.75, 4.0, 12.0  # igual que el video

sel = "+".join(f"eq(n\\,{g[0]})" for g in GALLERY)
p = subprocess.run([FFMPEG, "-v", "error", "-i", os.path.join(HERE, "video.mp4"),
                    "-vf", f"select='{sel}'", "-vsync", "0",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
arr = np.frombuffer(p.stdout, np.uint8).reshape(-1, SRC_H, SRC_W, 3)
manifest = []
for (fr, t, cap), im in zip(GALLERY, arr):
    sq = im[CROP_Y:CROP_Y + CROP_S, CROP_X:CROP_X + CROP_S]
    q = np.percentile(sq[::4, ::4], 99.7)
    if NORMALIZE and q >= BLACK_P:
        g = min((TARGET / max(q, 1.0)) ** ALPHA, GAIN_MAX)
        if g > 1.02:
            sq = np.clip(sq.astype(np.float32) * g, 0, 255).astype(np.uint8)
    name = f"f{fr:04d}.jpg"
    Image.fromarray(sq).resize((760, 760), Image.LANCZOS).save(
        os.path.join(WEB, name), quality=86, optimize=True)
    manifest.append({"frame": fr, "time": t, "file": f"assets/{name}", "caption": cap})
# encoding explicit: sense aixo, a Windows json.dump escriuria en cp1252 i el
# navegador, que llegeix UTF-8, veuria els accents trencats
json.dump(manifest, open(os.path.join(DATA, "gallery.json"), "w", encoding="utf-8"),
          indent=1, ensure_ascii=False)
tot = sum(os.path.getsize(os.path.join(WEB, m["file"].split("/")[1])) for m in manifest)
print(f"galeria: {len(manifest)} imagenes, {tot/1024:.0f} kB")

# ----------------------------------------------------------------------------
# Portada + fulls d'sprites per a l'explorador interactiu de la pagina catalana
# ----------------------------------------------------------------------------
FRAME0 = pd.Timestamp("2026-08-12 19:25:41")
SPF, TILE, COLS, ROWS = 2.0, 320, 6, 6
PER = COLS * ROWS
SCRUB = os.path.join(WEB, "scrub")
os.makedirs(SCRUB, exist_ok=True)

# cada 10 fotogrames, i tots els de la totalitat perque no se saltin els bons
wanted = sorted(set(range(0, 2976, 10)) | set(range(1940, 2006)))
print(f"\nexplorador: {len(wanted)} fotogrames -> {-(-len(wanted)//PER)} fulls de {COLS}x{ROWS}")

# es retalla a resolucio completa perque el percentil del realc coincideixi amb el video
proc = subprocess.Popen(
    [FFMPEG, "-v", "error", "-i", os.path.join(HERE, "video.mp4"),
     "-vf", "select='" + "+".join(f"eq(n\\,{f})" for f in wanted) + f"',crop={CROP_S}:{CROP_S}:{CROP_X}:{CROP_Y}",
     "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
    stdout=subprocess.PIPE, bufsize=10 ** 8)

nbytes = CROP_S * CROP_S * 3
sheet = Image.new("RGB", (TILE * COLS, TILE * ROWS), (10, 12, 16))
sheets_written = 0
for i, fr in enumerate(wanted):
    buf = proc.stdout.read(nbytes)
    if len(buf) < nbytes:
        raise RuntimeError(f"el video s'ha acabat abans d'hora al fotograma {fr}")
    sq = np.frombuffer(buf, np.uint8).reshape(CROP_S, CROP_S, 3)
    q = np.percentile(sq[::4, ::4], 99.7)
    if NORMALIZE and q >= BLACK_P:
        g = min((TARGET / max(q, 1.0)) ** ALPHA, GAIN_MAX)
        if g > 1.02:
            sq = np.clip(sq.astype(np.float32) * g, 0, 255).astype(np.uint8)
    k = i % PER
    sheet.paste(Image.fromarray(sq).resize((TILE, TILE), Image.LANCZOS),
                ((k % COLS) * TILE, (k // COLS) * TILE))
    if k == PER - 1 or i == len(wanted) - 1:
        sheet.save(os.path.join(SCRUB, f"s{i // PER:02d}.jpg"), quality=82, optimize=True)
        sheets_written += 1
        sheet = Image.new("RGB", (TILE * COLS, TILE * ROWS), (10, 12, 16))
proc.stdout.close(); proc.wait()

mins = [round(((FRAME0 + pd.Timedelta(seconds=f * SPF)) - DAY0).total_seconds() / 60.0, 3)
        for f in wanted]
json.dump({"tile": TILE, "cols": COLS, "rows": ROWS, "per": PER,
           "sheets": sheets_written, "f": wanted, "t": mins},
          open(os.path.join(DATA, "scrub.json"), "w"), separators=(",", ":"))
sz = sum(os.path.getsize(os.path.join(SCRUB, f)) for f in os.listdir(SCRUB))
print(f"  {sheets_written} fulls, {sz/1024/1024:.1f} MB")

# portada: el fotograma 1996 (la corona) a mes resolucio
p = subprocess.run([FFMPEG, "-v", "error", "-i", os.path.join(HERE, "video.mp4"),
                    "-vf", f"select='eq(n\\,1996)',crop={CROP_S}:{CROP_S}:{CROP_X}:{CROP_Y}",
                    "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                   capture_output=True)
hero = np.frombuffer(p.stdout[:nbytes], np.uint8).reshape(CROP_S, CROP_S, 3)
Image.fromarray(hero).resize((1200, 1200), Image.LANCZOS).save(
    os.path.join(WEB, "hero.jpg"), quality=88, optimize=True)
print(f"  portada hero.jpg {os.path.getsize(os.path.join(WEB,'hero.jpg'))//1024} kB")
