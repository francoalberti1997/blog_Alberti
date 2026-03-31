import sys

import numpy as np
import matplotlib.pyplot as plt
import cv2
import os
import random
import csv
from pathlib import Path
import requests
import numpy as np
import cv2

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
from calibracion.px_to_um import marcar_recta
marcar_recta = None  


def generar_grilla_intercepciones_constantes(
    img_file: str,
    mask_file: str,
    # output_dir: str = "results",
    num_rectas_objetivo: int = 100,
    grid_rows: int = 14,
    grid_cols: int = 14,
    min_intercept_um: float = 0.8,
    safety_margin_px: int = 5,
    max_global_attempts: int = None,
    pesos: dict = None,
) -> dict:
    """
    Genera rectas de longitud CONSTANTE con margen de seguridad fijo respecto a todos los bordes.
    Exporta CSV con información de segmentos y guarda visualización.

    Args:
        img_file: Ruta a la imagen original (para calibración µm/px)
        mask_file: Ruta a la máscara binaria de bordes/grano
        output_dir: Carpeta donde guardar resultados (se crea si no existe)
        num_rectas_objetivo: Cantidad deseada de rectas
        grid_rows, grid_cols: Solo informativos por ahora (no se usan en grilla regular)
        min_intercept_um: Longitud mínima de intercepto aceptable [µm]
        safety_margin_px: Margen mínimo en píxeles a TODOS los bordes
        max_global_attempts: Límite de intentos globales (default = num_rectas * 40)
        pesos: Diccionario con los pesos de la función de score (opcional)

    Returns:
        dict con:
            - 'rectas': lista de diccionarios con cada recta
            - 'um_per_pix': factor de conversión
            - 'fixed_length_px': longitud fija usada
            - 'success': bool
            - 'n_validas': cantidad de rectas generadas
    """
    # ─── Configuración por defecto ───────────────────────────────────────
    if pesos is None:
        pesos = {
            'intercepciones': 10.0,
            'distancia': 3.0,
            'variabilidad': 0.5,
            'borde': 15.0,
            'triple': 8.0,
            'critico': 10.0,
            'borde_critico': 50.0,
        }

    if max_global_attempts is None:
        max_global_attempts = num_rectas_objetivo * 40

    # os.makedirs(output_dir, exist_ok=True)
    

    # edge = cv2.imread(mask_file, cv2.IMREAD_GRAYSCALE)

    # edge = cv2.imdecode(
    #     np.fromfile(mask_file, dtype=np.uint8),
    #     cv2.IMREAD_GRAYSCALE
    # )
    
    print(f"Intentando leer máscara desde archivo: {mask_file}")
    
    mask_url = mask_file.url

    response = requests.get(mask_url)

    print(f"Respuesta HTTP: {response.status_code} para URL: {mask_url}")

    response.raise_for_status()

    mask_array = np.frombuffer(response.content, np.uint8)

    edge = cv2.imdecode(mask_array, cv2.IMREAD_GRAYSCALE)
    print(f"Leída máscara desde URL: {mask_url}")

    if edge is None:
        raise FileNotFoundError(f"No se pudo leer la máscara: {mask_file}")

    edge = (edge > 127).astype(np.uint8)
    H, W = edge.shape
    print(f"Imagen máscara: {W} × {H}")

    # Zonas válidas
    VALID_X_MIN = safety_margin_px
    VALID_X_MAX = W - 1 - safety_margin_px
    VALID_Y_MIN = safety_margin_px
    VALID_Y_MAX = H - 1 - safety_margin_px

    CENTER_VALID_X_MIN = safety_margin_px * 2
    CENTER_VALID_X_MAX = W - 1 - safety_margin_px * 2
    CENTER_VALID_Y_MIN = safety_margin_px * 2
    CENTER_VALID_Y_MAX = H - 1 - safety_margin_px * 2

    # ─── Calibración µm/px ───────────────────────────────────────────────
    print("Calibrando factor µm/px...")
    try:
        print(f"Descargando imagen original para calibración...")

        img_url = img_file.url if hasattr(img_file, "url") else img_file

        response = requests.get(img_url)
        response.raise_for_status()

        img_array = np.frombuffer(response.content, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)

        if img is None:
            raise ValueError("No se pudo decodificar la imagen original")

        print("Imagen original cargada correctamente")

    except Exception as e:
        print(f"Error en calibración: {e}")
 

    # ─── Longitud fija conservadora ──────────────────────────────────────
    fixed_length_px = min(W, H) - 2 * safety_margin_px - 60
    # print(f"Longitud fija por recta: {fixed_length_px:.1f} px  ≈ {fixed_length_px * um_per_pix:.1f} µm")

    # ─── Funciones auxiliares ────────────────────────────────────────────
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

            if (x1 < VALID_X_MIN or x1 > VALID_X_MAX or
                y1 < VALID_Y_MIN or y1 > VALID_Y_MAX or
                x2 < VALID_X_MIN or x2 > VALID_X_MAX or
                y2 < VALID_Y_MIN or y2 > VALID_Y_MAX):
                continue

            n_points = int(length_px) + 1
            x_vals = np.linspace(x1, x2, n_points).round().astype(int)
            y_vals = np.linspace(y1, y2, n_points).round().astype(int)

            if (x_vals.min() < VALID_X_MIN or x_vals.max() > VALID_X_MAX or
                y_vals.min() < VALID_Y_MIN or y_vals.max() > VALID_Y_MAX):
                continue

            return x_vals, y_vals, xc, yc

        print("  No se pudo generar recta segura tras muchos intentos")
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
            dx, dy = x_vals[e]-x_vals[s], y_vals[e]-y_vals[s]
            L = np.hypot(dx, dy)
            # if L < min_intercept_px:
            #     continue
            valid_lengths.append(L)
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


    def score_recta(segments, lengths_um, x_vals, y_vals, triple_points, critical_points):
        n = len(lengths_um)
        centers = segments.mean(axis=1) / len(x_vals)
        dist_media_rel = np.diff(centers).mean() if len(centers) > 1 else 0
        variabilidad_rel = lengths_um.std() / lengths_um.mean() if len(lengths_um) > 0 else 999
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

    # ─── Pipeline principal ──────────────────────────────────────────────
    rectas_data = []
    intentos = 0

    triple_points = detect_triple_points(edge)
    print(f"Puntos triples detectados: {len(triple_points)}")

    while len(rectas_data) < num_rectas_objetivo and intentos < max_global_attempts:
        intentos += 1
        x_vals, y_vals, xc, yc = generate_line_fixed_length_safe(fixed_length_px)
        if x_vals is None:
            continue

        analysis = analyze_line(x_vals, y_vals)
        if analysis is None:
            continue

        segments, lengths_um, critical_points = analysis
        score = score_recta(segments, lengths_um, x_vals, y_vals, triple_points, critical_points)

        rectas_data.append({
            "x_vals": x_vals,
            "y_vals": y_vals,
            "score": score,
            "segments": segments,
            "lengths_um": lengths_um,
            "n": len(lengths_um),
            "mean_um": lengths_um.mean() if len(lengths_um) > 0 else 0,
            # "total_length_um": fixed_length_px * um_per_pix,
            "center": (xc, yc)
        })

    # Seleccionamos las mejores
    rectas_data = sorted(rectas_data, key=lambda x: x["score"], reverse=True)[:num_rectas_objetivo]
    
    eficiencia = len(rectas_data) / intentos

    eficiencia_minima = 0.1  # ajustable

    if intentos > 0:
        eficiencia = len(rectas_data) / intentos
    else:
        eficiencia = 0

    if eficiencia < eficiencia_minima:
        print("Falla: máscara de baja calidad (ineficiente)")
        return {
            "mean_grain_size_um": None,
            "std_grain_size_um": None,
            "is_valid":False
        }

    # ─── Visualización ───────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(W/100, H/100), dpi=140)
    ax.imshow(edge, cmap='gray', alpha=0.25)

    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle(
        (safety_margin_px, safety_margin_px),
        W - 2*safety_margin_px,
        H - 2*safety_margin_px,
        linewidth=1.4, edgecolor='darkred', facecolor='none', linestyle='--', alpha=0.6
    ))

    for d in rectas_data:
        ax.plot(d["x_vals"], d["y_vals"], color='black', alpha=0.55, lw=1.4)
        xm, ym = d["center"]
        # ax.text(xm, ym + 18, f"{d['total_length_um']:.0f} µm",
        #         color='white', fontsize=8, ha='center',
        #         bbox=dict(facecolor='black', alpha=0.7, pad=1.5))
        for s, e in d["segments"]:
            ax.plot(d["x_vals"][s:e], d["y_vals"][s:e], color='red', lw=2.5)
            ax.scatter(d["x_vals"][[s,e]], d["y_vals"][[s,e]],
                       s=30, marker='o', color='yellow', edgecolor='black', zorder=10)

    ax.set_title(f"Rectas LONGITUD CONSTANTE = {fixed_length_px:.0f} px   |   margen {safety_margin_px} px")
    ax.axis("off")

    # vis_path = os.path.join(output_dir, "rectas_intercepciones_constantes.png")
    # plt.savefig(vis_path, bbox_inches=0, pad_inches=0, dpi=200)
    plt.close()

    
    # ─── Estadísticas globales ───────────────────────────────

    means = [d["mean_um"] for d in rectas_data if d["mean_um"] > 0]

    if len(means) > 0:
        mean_global = float(np.mean(means))
        std_global = float(np.std(means, ddof=1)) if len(means) > 1 else 0.0
    else:
        mean_global = None
        std_global = None
    
    diam_mean = mean_global * 1.5 if mean_global is not None else None
    diam_std = std_global * 1.5 if std_global is not None else None

    return {
        "mean_grain_size_um": diam_mean,
        "std_grain_size_um": diam_std,
        "is_valid":True
    }
