import numpy as np
import matplotlib.pyplot as plt
import cv2
import sys
import os
import random
import csv

# ─────────────────────────────────────────────
# IMPORT CALIBRACIÓN
# ─────────────────────────────────────────────
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from calibracion.calibracion import marcar_recta
from ASTM.E112.generador_boxes.generador_boxes import obtener_poligonos_desde_api

def generar_rectas_obb(
    mask_file: str,
    img_file: str,
    polygon_file: str = None,
    num_rectas_por_caja: int = 10,
    min_intercept_um: float = 0.8,
    edge_margin_ratio: float = 0.06,
    output_dir: str = "results",
    csv_output_file: str = "results/rectas_resultados.csv"
):
    """Genera rectas con visualización: Verde = recta completa | Rojo = segmentos usados | Azul = interceptos."""

    os.makedirs(output_dir, exist_ok=True)
    print(f"Iniciando generación de rectas para: {os.path.basename(mask_file)}")

    # CARGA MÁSCARA
    edge = cv2.imread(mask_file, cv2.IMREAD_GRAYSCALE)
    if edge is None:
        raise FileNotFoundError(f"No se pudo cargar la máscara: {mask_file}")

    edge = (edge > 127).astype(np.uint8)
    H_mask, W_mask = edge.shape
    print(f"Máscara cargada: {W_mask} x {H_mask} píxeles")

    # CALIBRACIÓN
    img_original = plt.imread(img_file)
    H_orig, W_orig = img_original.shape[:2]

    um_per_pix_original = marcar_recta(img_original)

    if um_per_pix_original is None or um_per_pix_original <= 0:
        raise ValueError("Calibración inválida.")

    long_side_original = max(H_orig, W_orig)
    long_side_mask = max(H_mask, H_mask)
    scale_factor = long_side_original / long_side_mask
    um_per_pix = um_per_pix_original * scale_factor

    # PARÁMETROS
    MIN_INTERCEPT_PX = min_intercept_um / um_per_pix
    MAX_INTERCEPT_PX = 0.65 * max(W_mask, H_mask)

    MAX_LINE_ATTEMPTS = 280
    MAX_GLOBAL_ATTEMPTS_PER_POLY = num_rectas_por_caja * 160

    # LEER POLÍGONOS
    polygons = []
    main_angles = []
    aspect_ratios = []

    if polygon_file is not None and os.path.exists(polygon_file):
        print(f"Cargando polígonos desde: {os.path.basename(polygon_file)}")
        with open(polygon_file, 'r') as f:
            lines = f.readlines()

        for line_idx, line in enumerate(lines):
            values = list(map(float, line.strip().split()))
            if len(values) < 5:
                continue
            coords = values[1:]
            if len(coords) % 2 != 0:
                continue

            poly_norm = np.array(coords).reshape(-1, 2)
            poly_px = (poly_norm * np.array([W_mask, H_mask])).astype(np.int32)

            if len(poly_px) >= 3 and not np.array_equal(poly_px[0], poly_px[-1]):
                poly_px = np.vstack([poly_px, poly_px[0]])

            polygons.append(poly_px)

            n = len(poly_px) - 1
            if n < 2:
                main_angles.append(0.0)
                aspect_ratios.append(1.0)
                continue

            sides = [np.linalg.norm(poly_px[i] - poly_px[(i + 1) % n]) for i in range(n)]
            longest_idx = np.argmax(sides)
            p1 = poly_px[longest_idx]
            p2 = poly_px[(longest_idx + 1) % n]
            angle = np.arctan2(p2[1] - p1[1], p2[0] - p1[0])

            width = np.ptp(poly_px[:, 0])
            height = np.ptp(poly_px[:, 1])
            aspect_ratio = max(width, height) / max(1.0, min(width, height))

            main_angles.append(angle)
            aspect_ratios.append(aspect_ratio)

    else:
        print("No se proporcionó polygon_file → Usando imagen completa")
        poly_full = np.array([[0,0],[W_mask-1,0],[W_mask-1,H_mask-1],[0,H_mask-1],[0,0]], dtype=np.int32)
        polygons = [poly_full]
        main_angles = [0.0]
        aspect_ratios = [1.0]

    # UTILIDADES
    def point_in_polygon(px, py, poly):
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if py > min(p1y, p2y):
                if py <= max(p1y, p2y):
                    if px <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                            if p1x == p2x or px <= xinters:
                                inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def get_random_point_in_polygon(poly):
        xs, ys = poly[:,0], poly[:,1]
        xmin, xmax = int(xs.min()), int(xs.max())
        ymin, ymax = int(ys.min()), int(ys.max())

        for _ in range(2500):
            cx = random.randint(xmin, xmax)
            cy = random.randint(ymin, ymax)
            if point_in_polygon(cx, cy, poly):
                return cx, cy
        return None, None

    # GENERACIÓN DE RECTA
    def generate_line_in_polygon(poly, main_angle, aspect_ratio):
        for _ in range(MAX_LINE_ATTEMPTS):
            cx, cy = get_random_point_in_polygon(poly)
            if cx is None:
                continue

            if aspect_ratio < 1.65:
                theta = random.uniform(0, np.pi)
                noise_deg = 40
            else:
                theta = main_angle
                noise_deg = 12 if aspect_ratio > 2.8 else 22

            theta += random.uniform(-noise_deg, noise_deg) * np.pi / 180

            dx, dy = np.cos(theta), np.sin(theta)
            L = max(W_mask, H_mask) * 1.3

            t = np.linspace(-L/2, L/2, int(L * 1.6))
            x_cand = np.round(cx + t * dx).astype(int)
            y_cand = np.round(cy + t * dy).astype(int)

            valid = (x_cand >= 0) & (x_cand < W_mask) & (y_cand >= 0) & (y_cand < H_mask)
            x_cand = x_cand[valid]
            y_cand = y_cand[valid]

            if len(x_cand) < 90:
                continue

            points_inside = [(x, y) for x, y in zip(x_cand, y_cand) if point_in_polygon(x, y, poly)]
            if len(points_inside) < 65:
                continue

            x_vals = np.array([p[0] for p in points_inside])
            y_vals = np.array([p[1] for p in points_inside])

            return x_vals, y_vals, float(cx), float(cy)

        return None, None, None, None

    # ANALIZAR LINEA (modificada)
    def analyze_line(x_vals, y_vals):
        line_pixels = edge[y_vals, x_vals]
        diff = np.diff(line_pixels)
        idx = np.where(diff != 0)[0] + 1

        if len(idx) < 2:
            return None

        segments = np.column_stack((idx[:-1], idx[1:]))
        valid_lengths_px = []
        total_intercept_length_px = 0.0
        intercept_points = []

        for s, e in segments:
            seg = line_pixels[s:e]
            if seg.mean() < 0.50:
                continue

            dx = x_vals[e-1] - x_vals[s]
            dy = y_vals[e-1] - y_vals[s]
            L_px = np.hypot(dx, dy)

            if MIN_INTERCEPT_PX <= L_px <= MAX_INTERCEPT_PX:
                valid_lengths_px.append(L_px)
                total_intercept_length_px += L_px
                intercept_points.append((x_vals[s], y_vals[s]))
                intercept_points.append((x_vals[e-1], y_vals[e-1]))

        if len(valid_lengths_px) < 1:
            return None

        n_granos = len(valid_lengths_px)
        segmento_medio_um = (total_intercept_length_px * um_per_pix) / n_granos
        valid_lengths_um = np.array(valid_lengths_px) * um_per_pix

        deriv = np.diff(line_pixels.astype(float))
        critical_idx = np.where(np.abs(deriv) < 1e-5)[0]
        critical_points = np.column_stack((x_vals[critical_idx], y_vals[critical_idx]))

        return (segments, valid_lengths_um, segmento_medio_um, 
                critical_points, np.array(intercept_points), total_intercept_length_px)

    # SCORING - MODIFICADO (prioriza rectas largas)
    def detect_triple_points(edge):
        kernel = np.ones((3, 3), dtype=np.uint8)
        neighbors = cv2.filter2D(edge, -1, kernel)
        triple_points = np.logical_and(edge == 1, neighbors == 4)
        y_pts, x_pts = np.where(triple_points)
        return np.column_stack((x_pts, y_pts))

    def min_distance(points_line, points_set):
        if len(points_set) == 0 or len(points_line) == 0:
            return 0.0
        dists = np.sqrt(((points_line[:, None, :] - points_set[None, :, :]) ** 2).sum(axis=2))
        return float(dists.min())

    def score_recta(segments, lengths_um, x_vals, y_vals, triple_points, critical_points, total_length_px):
        n = len(lengths_um)
        variabilidad_rel = float(lengths_um.std() / lengths_um.mean()) if len(lengths_um) > 1 else 999.0

        dist_min = np.minimum.reduce([x_vals, W_mask-x_vals, y_vals, H_mask-y_vals])
        dist_borde_rel = float(dist_min.mean() / min(W_mask, H_mask))
        penal_borde = 1.0 - float(dist_min.min() / min(W_mask, H_mask))

        pts_line = np.column_stack((x_vals, y_vals))
        dist_triple = min_distance(pts_line, triple_points) / min(W_mask, H_mask)
        dist_critico = min_distance(pts_line, critical_points) / min(W_mask, H_mask)

        # === BONUS POR LONGITUD TOTAL (nuevo) ===
        max_longitud_ref_px = max(W_mask, H_mask) * 0.68
        longitud_rel = total_length_px / max_longitud_ref_px
        bonus_longitud = 5.0 * longitud_rel                     # ← Ajusta este valor si quieres más/menos peso

        score = (
            1.2 * (n / 8) +
            20.5 * (1.0 - variabilidad_rel) +
            14.0 * dist_borde_rel +
            12.0 * dist_triple +
            9.0 * dist_critico +
            bonus_longitud -           # Prioridad a rectas largas
            40.0 * penal_borde
        )
        return score

    # PIPELINE PRINCIPAL
    all_rectas_data = []
    triple_points = detect_triple_points(edge)
    print(f"Puntos triples detectados: {len(triple_points)}")

    for poly_idx, (poly, main_angle, aspect) in enumerate(zip(polygons, main_angles, aspect_ratios)):
        print(f"Procesando polígono {poly_idx} | Aspect Ratio = {aspect:.2f}")
        rectas_data = []
        intentos = 0

        while len(rectas_data) < num_rectas_por_caja and intentos < MAX_GLOBAL_ATTEMPTS_PER_POLY:
            intentos += 1
            result = generate_line_in_polygon(poly, main_angle, aspect)
            if result[0] is None:
                continue

            x_vals, y_vals, cx, cy = result
            analysis = analyze_line(x_vals, y_vals)
            if analysis is None:
                continue

            (segments, lengths_um, segmento_medio_um, 
             critical_points, intercept_points, total_length_px) = analysis

            score = score_recta(segments, lengths_um, x_vals, y_vals, 
                               triple_points, critical_points, total_length_px)

            rectas_data.append({
                "x_vals": x_vals.tolist(),
                "y_vals": y_vals.tolist(),
                "score": float(score),
                "segments": segments.tolist(),
                "lengths_um": lengths_um.tolist(),
                "n": len(lengths_um),
                "mean_um": float(segmento_medio_um),
                "center_px": (int(cx), int(cy)),
                "poly_id": poly_idx,
                "intercept_points": intercept_points.tolist(),
                "total_length_um": float(total_length_px * um_per_pix)   # guardamos info útil
            })

        rectas_data = sorted(rectas_data, key=lambda x: x["score"], reverse=True)[:num_rectas_por_caja]
        all_rectas_data.extend(rectas_data)

        print(f" → {len(rectas_data)} rectas válidas generadas para polígono {poly_idx}")

    print(f"\nTotal de rectas generadas: {len(all_rectas_data)}")

    # VISUALIZACIÓN
    fig, ax = plt.subplots(figsize=(W_mask/90, H_mask/90), dpi=160)
    ax.imshow(edge, cmap='gray', alpha=0.25)

    for d in all_rectas_data:
        ax.plot(d["x_vals"], d["y_vals"], color='limegreen', linewidth=2.8, alpha=0.85)

        for s, e in d["segments"]:
            xs = np.array(d["x_vals"][s:e])
            ys = np.array(d["y_vals"][s:e])
            ax.plot(xs, ys, color='red', linewidth=4.2, alpha=0.95)

        if len(d["intercept_points"]) > 0:
            inter = np.array(d["intercept_points"])
            ax.scatter(inter[:, 0], inter[:, 1], color='blue', s=35, linewidth=0.8, 
                      edgecolors='white', zorder=5)

        for idx, (s, e) in enumerate(d["segments"]):
            xs = np.array(d["x_vals"][s:e])
            ys = np.array(d["y_vals"][s:e])
            if idx < len(d["lengths_um"]):
                xm = xs[len(xs)//2]
                ym = ys[len(ys)//2]
                dx = xs[-1] - xs[0]
                dy = ys[-1] - ys[0]
                norm = np.hypot(dx, dy)
                if norm == 0: continue
                nx = -dy / norm
                ny = dx / norm
                side = 1 if idx % 2 == 0 else -1
                offset = 12
                xt = xm + side * nx * offset
                yt = ym + side * ny * offset

                length_um = d["lengths_um"][idx]
                ax.text(xt, yt, f"{length_um:.2f} µm", color='yellow', fontsize=8,
                        ha='center', va='center',
                        bbox=dict(facecolor='black', alpha=0.65, pad=1.2, edgecolor='none'))

    plt.title(f"Rectas - Verde: Recta completa | Rojo: Segmentos usados | Azul: Interceptos\n{os.path.basename(mask_file)}", 
              fontsize=12)
    plt.axis('off')
    plt.savefig(f"{output_dir}/Copia_9.png", bbox_inches='tight', dpi=300)
    plt.close()

    # Segunda imagen de control
    fig2, ax2 = plt.subplots(figsize=(W_mask/90, H_mask/90), dpi=160)
    ax2.imshow(edge, cmap='gray', alpha=0.25)

    for poly in polygons:
        ax2.plot(poly[:, 0], poly[:, 1], color='cyan', linewidth=2.2, alpha=0.9)

    from collections import defaultdict
    rectas_por_poly = defaultdict(list)
    for d in all_rectas_data:
        rectas_por_poly[d["poly_id"]].append(d)

    MAX_RECTAS_VIS = 15
    for poly_id, rectas in rectas_por_poly.items():
        rectas_sorted = sorted(rectas, key=lambda x: x["score"], reverse=True)
        for d in rectas_sorted[:MAX_RECTAS_VIS]:
            ax2.plot(d["x_vals"], d["y_vals"], color='limegreen', linewidth=2.5, alpha=0.85)
            cx, cy = d["center_px"]
            ax2.scatter(cx, cy, color='yellow', s=30, edgecolors='black', zorder=5)

    for i, poly in enumerate(polygons):
        cx = int(np.mean(poly[:, 0]))
        cy = int(np.mean(poly[:, 1]))
        ax2.text(cx, cy, f"{i}", color='white', fontsize=10,
                ha='center', va='center', bbox=dict(facecolor='black', alpha=0.6, pad=2))

    plt.title("Cajas (cian) + rectas seleccionadas (verde)", fontsize=12)
    plt.axis('off')
    plt.savefig(f"{output_dir}/Copia_9.png", bbox_inches='tight', dpi=300)
    plt.close()

    # GUARDAR CSV
    file_exists = os.path.isfile(csv_output_file)
    with open(csv_output_file, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["n_segmentos", "segmento_medio_um", "center_x", "center_y",
                           "poly_id", "score", "total_length_um", "image_name"])

        for d in all_rectas_data:
            cx, cy = d["center_px"]
            writer.writerow([
                d["n"],
                f"{d['mean_um']:.3f}",
                cx, cy,
                d["poly_id"],
                f"{d['score']:.3f}",
                f"{d['total_length_um']:.2f}",
                os.path.basename(mask_file)
            ])

    print(f"CSV actualizado en: {csv_output_file}")
    print(f"Imágenes guardadas en: {output_dir}/")
    print("¡Pipeline completado exitosamente!\n")   

    return all_rectas_data

# ─────────────────────────────────────────────
# EJECUCIÓN
# ─────────────────────────────────────────────

# =========================================================
# GENERAR TXT DE POLÍGONOS
# =========================================================

polygon_txt = obtener_poligonos_desde_api(

    output_txt="images/labels/predicciones.txt",

    # ---- TEST MANUAL ----
    prediction_text="""
0 0.001302734375 0.6875 0.078125 0.725259765625 0.13671875 0.752603515625 0.09765625 0.893228515625 0.549478515625 0.891927734375 0.919271484375 0.872396484375 0.99609375 0.88671875 0.998046875 0.890625 0.997396484375 0.125 0 0.126302734375 0.001302734375 0.6875
"""
)

# =========================================================
# PIPELINE METALOGRÁFICO
# =========================================================

generar_rectas_obb(

    mask_file="images/mask/Copia_9_mask.jpg",

    img_file="images/img/Copia_9.jpg",

    polygon_file=polygon_txt,

    num_rectas_por_caja=300,

    min_intercept_um=10.0,

    edge_margin_ratio=0.06,

    output_dir="results",

    csv_output_file="results/Copia_9.csv"
)