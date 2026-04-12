import sys
import numpy as np
import matplotlib.pyplot as plt
import cv2
import os
import random
import requests
import io
from pathlib import Path
from matplotlib.patches import Rectangle
import matplotlib.cm as cm


def generar_grilla_intercepciones_constantes(
    img_file: str,
    mask_file: str,
    num_rectas_objetivo: int = 100,
    grid_rows: int = 14,
    grid_cols: int = 14,
    min_intercept_um: float = 0.8,
    safety_margin_px: int = 5,
    max_global_attempts: int = None,
    pesos: dict = None,
) -> dict:
    """
    Genera rectas de longitud CONSTANTE.
    Visualización: Solo 20 rectas con colores distintos, rectas más finas y texto más pequeño.
    """
    if pesos is None:
        pesos = {
            'intercepciones': 10.0, 'distancia': 3.0, 'variabilidad': 0.5,
            'borde': 15.0, 'triple': 8.0, 'critico': 10.0, 'borde_critico': 50.0,
        }

    if max_global_attempts is None:
        max_global_attempts = num_rectas_objetivo * 40

    # Cargar máscara desde Cloudinary
    mask_url = mask_file.url if hasattr(mask_file, 'url') else str(mask_file)
    response = requests.get(mask_url)
    response.raise_for_status()
    mask_array = np.frombuffer(response.content, np.uint8)
    edge = cv2.imdecode(mask_array, cv2.IMREAD_GRAYSCALE)

    if edge is None:
        raise FileNotFoundError(f"No se pudo leer la máscara: {mask_file}")

    edge = (edge > 127).astype(np.uint8)
    H, W = edge.shape

    VALID_X_MIN = safety_margin_px
    VALID_X_MAX = W - 1 - safety_margin_px
    VALID_Y_MIN = safety_margin_px
    VALID_Y_MAX = H - 1 - safety_margin_px

    CENTER_VALID_X_MIN = safety_margin_px * 2
    CENTER_VALID_X_MAX = W - 1 - safety_margin_px * 2
    CENTER_VALID_Y_MIN = safety_margin_px * 2
    CENTER_VALID_Y_MAX = H - 1 - safety_margin_px * 2

    fixed_length_px = min(W, H) - 2 * safety_margin_px - 60

    # ====================== FUNCIONES AUXILIARES ======================
    def generate_line_fixed_length_safe(length_px):
        max_attempts = 300
        for _ in range(max_attempts):
            xc = random.randint(CENTER_VALID_X_MIN, CENTER_VALID_X_MAX)
            yc = random.randint(CENTER_VALID_Y_MIN, CENTER_VALID_Y_MAX)
            theta = random.uniform(0, np.pi)
            dx, dy = np.cos(theta), np.sin(theta)
            half_len = length_px / 2.0

            x1 = xc - dx * half_len
            y1 = yc - dy * half_len
            x2 = xc + dx * half_len
            y2 = yc + dy * half_len

            if (x1 < VALID_X_MIN or x1 > VALID_X_MAX or y1 < VALID_Y_MIN or y1 > VALID_Y_MAX or
                x2 < VALID_X_MIN or x2 > VALID_X_MAX or y2 < VALID_Y_MIN or y2 > VALID_Y_MAX):
                continue

            n_points = int(length_px) + 1
            x_vals = np.linspace(x1, x2, n_points).round().astype(int)
            y_vals = np.linspace(y1, y2, n_points).round().astype(int)

            if (x_vals.min() < VALID_X_MIN or x_vals.max() > VALID_X_MAX or
                y_vals.min() < VALID_Y_MIN or y_vals.max() > VALID_Y_MAX):
                continue

            return x_vals, y_vals, xc, yc
        return None, None, None, None

    def analyze_line(x_vals, y_vals):
        line_pixels = edge[y_vals, x_vals]
        diff = np.diff(line_pixels)
        idx = np.where(diff != 0)[0] + 1
        if len(idx) < 2:
            return None
        segments = np.column_stack((idx[:-1], idx[1:]))
        valid_lengths = []
        for s, e in segments:
            seg = line_pixels[s:e]
            if seg.mean() < 0.6:
                continue
            dx, dy = x_vals[e] - x_vals[s], y_vals[e] - y_vals[s]
            L_px = np.hypot(dx, dy)
            valid_lengths.append(L_px)
        if len(valid_lengths) < 1:
            return None
        valid_lengths = np.array(valid_lengths)
        med = np.median(valid_lengths)
        valid_lengths = valid_lengths[valid_lengths > 0.3 * med]
        if len(valid_lengths) == 0:
            return None

        deriv = np.diff(line_pixels.astype(float))
        critical_idx = np.where(np.abs(deriv) < 1e-5)[0]
        critical_points = np.column_stack((x_vals[critical_idx], y_vals[critical_idx]))

        return segments, valid_lengths, critical_points

    def detect_triple_points(edge):
        kernel = np.ones((3,3), dtype=np.uint8)
        neighbors = cv2.filter2D(edge, -1, kernel)
        triple = np.logical_and(edge == 1, neighbors == 4)
        y_pts, x_pts = np.where(triple)
        return np.column_stack((x_pts, y_pts))

    def min_distance(points_line, points_set):
        if len(points_set) == 0 or len(points_line) == 0:
            return 0.0
        diff = points_line[:, None, :] - points_set[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        return dists.min()

    def score_recta(segments, lengths_px, x_vals, y_vals, triple_points, critical_points):
        n = len(lengths_px)
        centers = segments.mean(axis=1) / len(x_vals)
        dist_media_rel = np.diff(centers).mean() if len(centers) > 1 else 0
        variabilidad_rel = lengths_px.std() / lengths_px.mean() if len(lengths_px) > 0 else 999
        dist_min = np.minimum.reduce([x_vals, W-x_vals, y_vals, H-y_vals])
        dist_borde_rel = dist_min.mean() / min(W, H)
        penal_borde = 1 - (dist_min.min() / min(W, H))
        pts_line = np.column_stack((x_vals, y_vals))
        dist_triple = min_distance(pts_line, triple_points) / min(W, H)
        dist_critico = min_distance(pts_line, critical_points) / min(W, H)

        score = (
            pesos['intercepciones'] * (n / 10) +
            pesos['distancia']    * dist_media_rel -
            pesos['variabilidad'] * variabilidad_rel +
            pesos['borde']        * dist_borde_rel +
            pesos['triple']       * dist_triple +
            pesos['critico']      * dist_critico -
            pesos['borde_critico']* penal_borde
        )
        return score

    # ====================== PIPELINE PRINCIPAL ======================
    rectas_data = []
    intentos = 0
    all_intercept_lengths_px = []

    triple_points = detect_triple_points(edge)

    while len(rectas_data) < num_rectas_objetivo and intentos < max_global_attempts:
        intentos += 1
        x_vals, y_vals, xc, yc = generate_line_fixed_length_safe(fixed_length_px)
        if x_vals is None:
            continue

        analysis = analyze_line(x_vals, y_vals)
        if analysis is None:
            continue

        segments, lengths_px, critical_points = analysis
        score = score_recta(segments, lengths_px, x_vals, y_vals, triple_points, critical_points)

        rectas_data.append({
            "x_vals": x_vals,
            "y_vals": y_vals,
            "score": score,
            "segments": segments,
            "lengths_px": lengths_px,
            "n": len(lengths_px),
            "mean_px": lengths_px.mean() if len(lengths_px) > 0 else 0,
            "center": (xc, yc)
        })

        all_intercept_lengths_px.extend(lengths_px)

    # Seleccionamos las MEJORES 10 rectas para visualización
    rectas_data = sorted(rectas_data, key=lambda x: x["score"], reverse=True)
    rectas_to_show = rectas_data[:10]

    # ====================== CÁLCULO DE QUANTILES ======================
    if all_intercept_lengths_px:
        quantiles = np.quantile(
            all_intercept_lengths_px,
            np.linspace(0.1, 1.0, 10)
        ).round(4).tolist()

        distribution_quantiles = {
            f"q{int(p*100)}": q for p, q in zip(np.linspace(0.1, 1.0, 10), quantiles)
        }
    else:
        distribution_quantiles = {}

    # Estadísticas globales
    means_px = [d["mean_px"] for d in rectas_data if d["mean_px"] > 0]
    mean_global_px = float(np.mean(means_px)) if means_px else None
    std_global_px = float(np.std(means_px, ddof=1)) if len(means_px) > 1 else 0.0

    diam_mean_px = mean_global_px * 1.5 if mean_global_px is not None else None
    diam_std_px = std_global_px * 1.5 if std_global_px is not None else None

    eficiencia = len(rectas_data) / intentos if intentos > 0 else 0
    if eficiencia < 0.1:
        return {
            "mean_grain_size_um": None,
            "std_grain_size_um": None,
            "is_valid": False,
            "all_intercept_lengths_px": [],
            "distribution_quantiles": {},
            "visualization_bytes": None
        }

    # ====================== VISUALIZACIÓN - AJUSTES SOLICITADOS ======================
    fig, ax = plt.subplots(figsize=(W/100, H/100), dpi=160)
    ax.imshow(edge, cmap='gray', alpha=0.25)

    # Marco de margen
    ax.add_patch(Rectangle(
        (safety_margin_px, safety_margin_px),
        W - 2*safety_margin_px, H - 2*safety_margin_px,
        linewidth=1.4, edgecolor='darkred', facecolor='none', linestyle='--', alpha=0.6
    ))

    # Colormap para colores distintos
    colors = cm.get_cmap('tab10')(np.linspace(0, 1, 10))

    for i, d in enumerate(rectas_to_show):
        color = colors[i % 10]
        
        # Recta completa - MÁS FINA
        ax.plot(d["x_vals"], d["y_vals"], color=color, alpha=0.40, lw=1.0)

        # Segmentos válidos - MÁS FINOS
        for s, e in d["segments"]:
            seg_x = d["x_vals"][s:e]
            seg_y = d["y_vals"][s:e]
            length_px = np.hypot(seg_x[-1]-seg_x[0], seg_y[-1]-seg_y[0])
            length_um = length_px * 1.5   # Factor diámetro

            # Segmento más fino
            ax.plot(seg_x, seg_y, color=color, lw=2.2, alpha=0.95)
            
            # Punto 20
            ax.scatter(seg_x[-1], seg_y[-1], s=10, color=color, edgecolor='black', zorder=10)
            
            # Texto con medida - FUENTE MÁS CHICA
            if length_um > 5:
                mid_x = (seg_x[0] + seg_x[-1]) / 2
                mid_y = (seg_y[0] + seg_y[-1]) / 2
                ax.text(mid_x + 2, mid_y + 2, f"{length_um:.1f}µm", 
                        color='white', fontsize=2.5, fontweight='bold',  # ← Fuente más chica
                        bbox=dict(facecolor=color, alpha=0.75, edgecolor='none', pad=0.8))

    ax.set_title(f"10 de 100 Rectas de longitud constante • Medidas de segmentos en µm", 
                 fontsize=12, pad=10)   # Título también un poco más chico
    ax.axis("off")

    # Guardar en memoria para Cloudinary
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02, dpi=220)
    buf.seek(0)
    visualization_bytes = buf.getvalue()
    plt.close(fig)

    # ====================== RETORNO ======================
    return {
        "mean_grain_size_um": diam_mean_px,
        "std_grain_size_um": diam_std_px,
        "is_valid": True,
        "all_intercept_lengths_px": all_intercept_lengths_px,
        "distribution_quantiles": distribution_quantiles,
        "visualization_bytes": visualization_bytes
    }