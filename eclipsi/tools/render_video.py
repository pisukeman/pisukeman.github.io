"""
Monta el video resumen del eclipse: fotograma del Seestar arriba y las tres
metricas dibujandose debajo, todo sobre el mismo reloj real.

Todo sale de una TABLA DE EDICION (EDL) que asocia cada fotograma de salida a
(fotograma origen, hora real). Las graficas y el reloj se dibujan desde la hora
real, no desde el numero de fotograma, asi que ralentizar, congelar o descartar
fotogramas no descuadra nada.

  uv run --python 3.12 --with numpy --with pandas --with matplotlib --with pillow \
      python tools/render_video.py [--preview]

--preview  renderiza solo unos pocos fotogramas sueltos a build/preview/*.png
"""
import os, sys, json, subprocess
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, BUILD = os.path.join(HERE, "data"), os.path.join(HERE, "build")
SRC_VIDEO = os.path.join(HERE, "video.mp4")

_np = os.environ.get("FFMPEG_DIR", "")
FFMPEG = os.path.join(_np, "ffmpeg.exe") if _np else "ffmpeg"

# ---------------------------------------------------------------- sincronizacion
FRAME0 = datetime.fromisoformat("2026-08-12 19:25:41")
SPF = 2.0
def t_of(fr): return FRAME0 + timedelta(seconds=fr * SPF)

# ------------------------------------------------------------------- geometria
OUT_W, OUT_H = 1080, 1920
IMG_H, BAR_H, PANEL_H = 1000, 120, 200          # 1000 + 120 + 4x200 = 1920
IMG_TRIM = 40                                    # recorte vertical tras escalar a 1080
SRC_W, SRC_H = 1080, 1920
CROP_X, CROP_Y, CROP_S = 20, 456, 1000          # recorte cuadrado centrado en el disco

PLOT_L, PLOT_W, PLOT_T, PLOT_H = 96, 952, 32, 138
RECT = [PLOT_L / OUT_W, (PANEL_H - PLOT_T - PLOT_H) / PANEL_H,
        PLOT_W / OUT_W, PLOT_H / PANEL_H]

BG      = "#0f1216"
INK     = "#e8edf3"
INK_DIM = "#8d97a4"
GRID    = "#232a33"
C_LUX, C_TEMP, C_RH = "#B4901F", "#D6455D", "#4A9AC9"      # paleta validada

# ------------------------------------------------------------- plan de montaje
#   (primer fotograma, ultimo fotograma, fotogramas de salida por cada uno)
SEGMENTS = [
    (   0, 1944, 1.0),    # parcial de entrada, tiempo real de timelapse
    (1945, 1994, 2.4),    # totalidad en negro, ralentizada
    (1995, 1998, 30.0),   # corona: 1 s por fotograma
    (1999, 2000, 36.0),   # anillo de diamantes: 1,2 s
    (2001, 2003, 12.0),   # sobreexpuestos: 0,4 s
    (2004, 2975, 1.0),    # parcial de salida
]
TAIL_HOLD = 60            # 2 s congelado al final
EXCLUDE = set()           # fotogramas descartados -> se mantiene el ultimo bueno
FPS = 30

# --------------------------------------------------------------- normalizacion
# GAIN_MAX bajo a proposito: con el Sol ya poniendose, amplificar x9 solo saca ruido
# del sensor. Con x4 los ultimos fotogramas se apagan como se apagaron de verdad.
NORMALIZE, TARGET, ALPHA, GAIN_MAX, BLACK_P = True, 238.0, 0.75, 4.0, 12.0


def build_edl():
    """[(fotograma_origen, hora_real)] por cada fotograma de salida."""
    edl, acc, last_good = [], 0.0, None
    for a, b, rep in SEGMENTS:
        for src in range(a, b + 1):
            acc += rep
            n = int(acc)
            acc -= n
            if n <= 0:
                continue
            shown = last_good if src in EXCLUDE else src
            if src not in EXCLUDE:
                last_good = src
            if shown is None:
                continue
            for k in range(n):
                edl.append((shown, t_of(src + k / n)))
    if edl:
        s, t = edl[-1]
        edl += [(s, t)] * TAIL_HOLD
    return edl


def label_for(src, t, eph):
    if 1945 <= src <= 1994: return "TOTALIDAD", "el filtro solar seguia puesto"
    if 1995 <= src <= 1998: return "TOTALIDAD", "corona solar"
    if 1999 <= src <= 2000: return "TERCER CONTACTO", "anillo de diamantes"
    if 2001 <= src <= 2003: return "TERCER CONTACTO", "reaparece la fotosfera"
    hm = t.strftime("%H:%M:%S")
    if hm < eph["C1"]["local"]: return "ANTES DEL ECLIPSE", "disco solar integro"
    if hm < eph["C2"]["local"]: return "PARCIAL", "la Luna entra en el disco"
    if hm < eph["C3"]["local"]: return "TOTALIDAD", ""
    if hm < eph.get("C4", {}).get("local", "23:59:59"): return "PARCIAL", "la Luna sale del disco"
    return "PUESTA DE SOL", ""


# --------------------------------------------------------------------- paneles
DAY0 = pd.Timestamp("2026-08-12")
def ep(d):   return (pd.Timestamp(d) - DAY0).total_seconds()
def unep(s): return (DAY0 + pd.Timedelta(seconds=float(s))).strftime("%H:%M")


def render_panel(t_s, v, ylim, ylog, color, title, unit, xticks, xlim,
                 show_x=False, yticks=None, ylabels=None):
    """Devuelve (fondo RGB, curva RGBA) de 1080x240."""
    def fig():
        f = plt.figure(figsize=(OUT_W / 100, PANEL_H / 100), dpi=100)
        a = f.add_axes(RECT)
        a.set_xlim(*xlim)
        a.set_ylim(*ylim)
        if ylog: a.set_yscale("log")
        return f, a

    f, a = fig()                                    # ---- fondo
    f.patch.set_facecolor(BG); a.set_facecolor(BG)
    a.grid(True, color=GRID, lw=0.8, zorder=0)
    for s in a.spines.values(): s.set_color(GRID); s.set_linewidth(0.8)
    a.tick_params(colors=INK_DIM, labelsize=12, length=3, width=0.8)
    a.set_xticks(xticks)
    a.set_xticklabels([unep(x) for x in xticks] if show_x else [""] * len(xticks))
    if yticks is not None:
        a.set_yticks(yticks); a.set_yticklabels(ylabels or [str(y) for y in yticks])
        a.minorticks_off()
    a.text(0.004, 1.03, title, transform=a.transAxes, color=INK, fontsize=15,
           fontweight="bold", va="bottom", ha="left")
    a.text(0.30, 1.04, unit, transform=a.transAxes, color=INK_DIM,
           fontsize=12, va="bottom", ha="left")
    f.canvas.draw()
    bg = np.asarray(f.canvas.buffer_rgba())[:, :, :3].copy()
    plt.close(f)

    f, a = fig()                                    # ---- curva sola
    f.patch.set_alpha(0); a.patch.set_alpha(0)
    for s in a.spines.values(): s.set_visible(False)
    a.set_xticks([]); a.set_yticks([])
    a.plot(t_s, v, color=color, lw=2.0, solid_capstyle="round", zorder=3)
    f.canvas.draw()
    curve = np.asarray(f.canvas.buffer_rgba()).copy()
    plt.close(f)
    return bg, curve


def main():
    preview = "--preview" in sys.argv
    eph = json.load(open(os.path.join(DATA, "ephemeris.json")))
    light = pd.read_csv(os.path.join(DATA, "light.csv"), parse_dates=["time"])
    th = pd.read_csv(os.path.join(DATA, "thermo.csv"), parse_dates=["time"])

    edl = build_edl()
    T0, T1 = edl[0][1], edl[-1][1]
    xlim = (ep(T0), ep(T1))
    xticks = [ep(datetime(2026, 8, 12, h, m))
              for h in (19, 20, 21) for m in (0, 15, 30, 45)]
    xticks = [x for x in xticks if xlim[0] < x < xlim[1]]

    def series(df, col):
        m = (df["time"] >= T0 - timedelta(seconds=30)) & (df["time"] <= T1 + timedelta(seconds=30))
        d = df[m].dropna(subset=[col])
        return np.array([ep(x) for x in d["time"]]), d[col].values.astype(float)

    # se dibuja el dato CRUDO de phyphox, sin suavizar (los picos son sombras reales)
    lt_t, lt_v = series(light, "lx")
    lt_v = np.clip(lt_v, 0.55, None)                       # suelo del sensor (0,54 lx)
    th_t, th_c = series(th, "temp_c")
    _,    th_r = series(th, "rh_pct")

    LUX_LIM, LIN_LIM = (0.5, 16000), (0.0, 12500.0)
    T_LIM, R_LIM = (26.0, 38.5), (15.0, 52.0)
    panels = [
        render_panel(lt_t, lt_v, LUX_LIM, True, C_LUX, "Iluminancia", "lux · escala logaritmica",
                     xticks, xlim, yticks=[1, 10, 100, 1000, 10000],
                     ylabels=["1", "10", "100", "1.000", "10.000"]),
        render_panel(lt_t, lt_v, LIN_LIM, False, C_LUX, "Iluminancia", "lux · escala lineal",
                     xticks, xlim, yticks=[0, 4000, 8000, 12000],
                     ylabels=["0", "4.000", "8.000", "12.000"]),
        render_panel(th_t, th_c, T_LIM, False, C_TEMP, "Temperatura", "grados centigrados",
                     xticks, xlim, yticks=[27, 30, 33, 36]),
        render_panel(th_t, th_r, R_LIM, False, C_RH, "Humedad relativa", "por ciento",
                     xticks, xlim, show_x=True, yticks=[20, 30, 40, 50]),
    ]

    def xpix(t): return PLOT_L + PLOT_W * (ep(t) - xlim[0]) / (xlim[1] - xlim[0])
    def ypix(v, lim, log):
        if log:
            f = (np.log10(max(v, lim[0])) - np.log10(lim[0])) / (np.log10(lim[1]) - np.log10(lim[0]))
        else:
            f = (v - lim[0]) / (lim[1] - lim[0])
        return PLOT_T + PLOT_H * (1 - np.clip(f, 0, 1))

    fdir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    F_BIG = ImageFont.truetype(os.path.join(fdir, "DejaVuSans-Bold.ttf"), 54)
    F_MED = ImageFont.truetype(os.path.join(fdir, "DejaVuSans-Bold.ttf"), 24)
    F_SM  = ImageFont.truetype(os.path.join(fdir, "DejaVuSans.ttf"), 18)
    F_XS  = ImageFont.truetype(os.path.join(fdir, "DejaVuSans.ttf"), 15)
    F_VAL = ImageFont.truetype(os.path.join(fdir, "DejaVuSans-Bold.ttf"), 23)

    specs = [(LUX_LIM, True, C_LUX, lt_t, lt_v, "{:,.0f} lx"),
             (LIN_LIM, False, C_LUX, lt_t, lt_v, "{:,.0f} lx"),
             (T_LIM, False, C_TEMP, th_t, th_c, "{:.1f} °C"),
             (R_LIM, False, C_RH, th_t, th_r, "{:.1f} %")]

    def normalize(img):
        """Devuelve (imagen, ganancia aplicada). La ganancia se muestra en pantalla:
        el brillo de la imagen NO es una medida, la curva de lux si lo es."""
        if not NORMALIZE: return img, 1.0
        p = np.percentile(img[::4, ::4], 99.7)
        if p < BLACK_P: return img, 1.0
        g = min((TARGET / max(p, 1.0)) ** ALPHA, GAIN_MAX)
        if g <= 1.02: return img, 1.0
        return np.clip(img.astype(np.float32) * g, 0, 255).astype(np.uint8), float(g)

    def compose(src_img, t, src):
        canvas = np.zeros((OUT_H, OUT_W, 3), np.uint8)
        canvas[:] = np.array([15, 18, 22], np.uint8)
        sq = src_img[CROP_Y:CROP_Y + CROP_S, CROP_X:CROP_X + CROP_S]
        sq, gain = normalize(sq)
        im = Image.fromarray(sq).resize((OUT_W, OUT_W), Image.LANCZOS)
        canvas[0:IMG_H] = np.asarray(im)[IMG_TRIM:IMG_TRIM + IMG_H]

        xc = int(round(xpix(t)))
        for i, (bg, curve) in enumerate(panels):
            y0 = IMG_H + BAR_H + i * PANEL_H
            panel = bg.copy()
            c = curve[:, :xc]
            al = c[:, :, 3:4].astype(np.float32) / 255.0
            panel[:, :xc] = (panel[:, :xc] * (1 - al) + c[:, :, :3] * al).astype(np.uint8)
            canvas[y0:y0 + PANEL_H] = panel

        img = Image.fromarray(canvas)
        d = ImageDraw.Draw(img)

        # barra de informacion
        by = IMG_H
        d.rectangle([0, by, OUT_W, by + BAR_H], fill="#0b0e12")
        d.line([0, by, OUT_W, by], fill=GRID, width=2)
        d.text((28, by + 28), t.strftime("%H:%M:%S"), font=F_BIG, fill=INK)
        d.text((320, by + 26), "hora local · 12 agosto 2026", font=F_SM, fill=INK_DIM)
        d.text((320, by + 52), "Anquela del Pedregal · Seestar S50", font=F_SM, fill=INK_DIM)
        # el realce aplicado a la imagen se declara: no es una medida fotometrica
        d.text((320, by + 80),
               ("imagen sin realzar" if gain <= 1.02 else f"imagen realzada x{gain:.1f}"),
               font=F_XS, fill="#6b7480")
        head, sub = label_for(src, t, eph)
        col = "#e8b4bc" if "TOTALIDAD" in head or "CONTACTO" in head else INK_DIM
        d.text((OUT_W - 28, by + 28), head, font=F_MED, fill=col, anchor="ra")
        if sub:
            d.text((OUT_W - 28, by + 64), sub, font=F_SM, fill=INK_DIM, anchor="ra")

        # cabezal + valor actual en cada panel
        te = ep(t)
        for i, (lim, log, color, ts, vs, fmt) in enumerate(specs):
            y0 = IMG_H + BAR_H + i * PANEL_H
            d.line([xc, y0 + PLOT_T, xc, y0 + PLOT_T + PLOT_H], fill="#39424e", width=1)
            if ts[0] <= te <= ts[-1]:
                v = float(np.interp(te, ts, vs))
                yy = y0 + ypix(v, lim, log)
                d.ellipse([xc - 6, yy - 6, xc + 6, yy + 6], fill=color, outline=BG, width=2)
                txt = fmt.format(v).replace(",", ".")
                if log and v <= 0.6: txt = "< 1 lx"
                d.text((OUT_W - 34, y0 + 6), txt, font=F_VAL, fill=INK, anchor="ra")
        return np.asarray(img)

    # ------------------------------------------------------------------ preview
    if preview:
        os.makedirs(os.path.join(BUILD, "preview"), exist_ok=True)
        want = [0, 900, 1800, 1944, 1970, 1996, 1999, 2001, 2400, 2900, 2975]
        sel = "+".join(f"eq(n\\,{w})" for w in want)
        p = subprocess.run([FFMPEG, "-v", "error", "-i", SRC_VIDEO, "-vf", f"select='{sel}'",
                            "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)
        arr = np.frombuffer(p.stdout, np.uint8).reshape(-1, SRC_H, SRC_W, 3)
        idx = {s: k for k, (s, _) in enumerate(edl)}
        for w, im in zip(want, arr):
            t = edl[idx[w]][1] if w in idx else t_of(w)
            Image.fromarray(compose(im, t, w)).save(
                os.path.join(BUILD, "preview", f"out_{w:04d}.png"))
            print("preview", w, t.strftime("%H:%M:%S"))
        return

    # ------------------------------------------------------------- render completo
    last_src = max(s for s, _ in edl)
    dec = subprocess.Popen(
        [FFMPEG, "-v", "error", "-i", SRC_VIDEO, "-vf", f"select='lte(n\\,{last_src})'",
         "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, bufsize=10 ** 8)
    out_path = os.path.join(HERE, "eclipsi_resumen.mp4")
    enc = subprocess.Popen(
        [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path],
        stdin=subprocess.PIPE, bufsize=10 ** 8)

    nbytes = SRC_W * SRC_H * 3
    cur, img = -1, None
    for i, (src, t) in enumerate(edl):
        while cur < src:
            buf = dec.stdout.read(nbytes)
            if len(buf) < nbytes:
                raise RuntimeError(f"fin inesperado del video en {cur}")
            img = np.frombuffer(buf, np.uint8).reshape(SRC_H, SRC_W, 3)
            cur += 1
        enc.stdin.write(compose(img, t, src).tobytes())
        if i % 200 == 0:
            print(f"  {i}/{len(edl)}  fot.{src}  {t:%H:%M:%S}", flush=True)
    enc.stdin.close(); enc.wait(); dec.wait()
    print(f"\nlisto: {out_path}  ({len(edl)} fotogramas, {len(edl)/FPS:.1f} s)")
    print(f"tamano: {os.path.getsize(out_path)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
