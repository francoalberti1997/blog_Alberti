import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import cv2
import io
import random
import requests
from pathlib import Path
from collections import defaultdict

def load_image(img_input):
    """Carga imágenes desde Cloudinary, URL o path local"""
    if hasattr(img_input, 'url'):
        url = img_input.url
    elif isinstance(img_input, str):
        if img_input.startswith(('http://', 'https://')):
            url = img_input
        else:
            return plt.imread(img_input)
    else:
        return plt.imread(str(img_input))

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        img_array = np.frombuffer(response.content, np.uint8)
        img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    except Exception as e:
        raise ValueError(f"Error cargando imagen: {e}")


def generar_rectas_obb_produccion(
    img_file,
    mask_file=None,
    polygon_file: str = None,
    num_rectas_por_caja: int = 70,
    min_intercept_um: float = 5.0,
) -> dict:
    """
    Versión FINAL para producción - Genera rectas en TODAS las cajas OBB.
    """

    # ====================== CARGA DE IMÁGENES ======================
    img_original = load_image(img_file)
    H_orig, W_orig = img_original.shape[:2]

    if mask_file is not None:
        edge = load_image(mask_file)
        if len(edge.shape) == 3:
            edge = cv2.cvtColor(edge, cv2.COLOR_RGB2GRAY)
        _, edge = cv2.threshold(edge, 127, 255, cv2.THRESH_BINARY)
        edge = (edge > 127).astype(np.uint8)
        H_mask, W_mask = edge.shape
    else:
        edge = np.ones((H_orig, W_orig), dtype=np.uint8)
        H_mask, W_mask = H_orig, W_orig

    # ====================== CALIBRACIÓN ======================
    um_per_pix = 1.0
    MIN_INTERCEPT_PX = min_intercept_um / um_per_pix
    MAX_INTERCEPT_PX = 0.65 * max(W_mask, H_mask)

    # ====================== CARGA DE OBB (4 puntos) ======================
    polygons = []
    main_angles = []
    aspect_ratios = []

    if polygon_file and os.path.exists(polygon_file):
        print(f"✅ Cargando OBB desde: {polygon_file}")
        with open(polygon_file, 'r') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        for line in lines:
            try:
                values = list(map(float, line.split()))
                if len(values) < 9:
                    continue
                coords = values[1:9]
                poly_norm = np.array(coords).reshape(4, 2)
                poly_px = (poly_norm * np.array([W_mask, H_mask])).astype(np.int32)

                if not np.array_equal(poly_px[0], poly_px[-1]):
                    poly_px = np.vstack([poly_px, poly_px[0]])
                polygons.append(poly_px)

                n = len(poly_px) - 1
                sides = [np.linalg.norm(poly_px[i] - poly_px[(i + 1) % n]) for i in range(n)]
                longest_idx = np.argmax(sides)
                p1 = poly_px[longest_idx]
                p2 = poly_px[(longest_idx + 1) % n]
                angle = np.arctan2(p2[1] - p1[1], p2[0] - p1[0])

                width = float(np.ptp(poly_px[:, 0]))
                height = float(np.ptp(poly_px[:, 1]))
                aspect = max(width, height) / max(1.0, min(width, height))

                main_angles.append(angle)
                aspect_ratios.append(aspect)
            except:
                continue

        print(f"✅ {len(polygons)} cajas OBB cargadas")
    else:
        print("⚠️ No polygon_file → Usando imagen completa")
        poly_full = np.array([[0,0],[W_mask-1,0],[W_mask-1,H_mask-1],[0,H_mask-1],[0,0]], dtype=np.int32)
        polygons = [poly_full]
        main_angles = [0.0]
        aspect_ratios = [1.0]

    # ====================== FUNCIONES AUXILIARES ======================
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
        for _ in range(3500):
            cx = random.randint(xmin, xmax)
            cy = random.randint(ymin, ymax)
            if point_in_polygon(cx, cy, poly):
                return cx, cy
        return None, None

    def generate_line_in_polygon(poly, main_angle, aspect_ratio):
        MAX_LINE_ATTEMPTS = 350
        for _ in range(MAX_LINE_ATTEMPTS):
            cx, cy = get_random_point_in_polygon(poly)
            if cx is None: continue

            if aspect_ratio < 1.65:
                theta = random.uniform(0, np.pi)
                noise_deg = 45
            else:
                theta = main_angle
                noise_deg = 15 if aspect_ratio > 2.8 else 25

            theta += random.uniform(-noise_deg, noise_deg) * np.pi / 180
            dx, dy = np.cos(theta), np.sin(theta)
            L = max(W_mask, H_mask) * 1.4

            t = np.linspace(-L/2, L/2, int(L * 1.8))
            x_cand = np.round(cx + t * dx).astype(int)
            y_cand = np.round(cy + t * dy).astype(int)

            valid = (x_cand >= 0) & (x_cand < W_mask) & (y_cand >= 0) & (y_cand < H_mask)
            x_cand = x_cand[valid]
            y_cand = y_cand[valid]

            if len(x_cand) < 80: continue
            points_inside = [(x, y) for x, y in zip(x_cand, y_cand) if point_in_polygon(x, y, poly)]
            if len(points_inside) < 55: continue

            x_vals = np.array([p[0] for p in points_inside])
            y_vals = np.array([p[1] for p in points_inside])
            return x_vals, y_vals, float(cx), float(cy)
        return None, None, None, None

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
            if seg.mean() < 0.50: continue
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

        valid_lengths_um = np.array(valid_lengths_px) * um_per_pix
        n_granos = len(valid_lengths_um)
        segmento_medio_um = (total_intercept_length_px * um_per_pix) / n_granos

        return (segments, valid_lengths_um, segmento_medio_um, 
                None, np.array(intercept_points), total_intercept_length_px)

    def detect_triple_points(edge):
        kernel = np.ones((3, 3), dtype=np.uint8)
        neighbors = cv2.filter2D(edge, -1, kernel)
        triple = np.logical_and(edge == 1, neighbors == 4)
        y_pts, x_pts = np.where(triple)
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
        dist_critico = 0.5

        max_longitud_ref_px = max(W_mask, H_mask) * 0.68
        longitud_rel = total_length_px / max_longitud_ref_px
        bonus_longitud = 5.0 * longitud_rel

        score = (
            1.2 * (n / 8) +
            20.5 * (1.0 - variabilidad_rel) +
            14.0 * dist_borde_rel +
            12.0 * dist_triple +
            9.0 * dist_critico +
            bonus_longitud -
            40.0 * penal_borde
        )
        return score

    # ====================== PIPELINE PRINCIPAL ======================
    all_rectas_data = []
    triple_points = detect_triple_points(edge)

    for poly_idx, (poly, main_angle, aspect) in enumerate(zip(polygons, main_angles, aspect_ratios)):
        print(f"→ Procesando caja {poly_idx} | Aspect Ratio = {aspect:.2f}")
        rectas_data = []
        intentos = 0
        MAX_GLOBAL = num_rectas_por_caja * 180

        while len(rectas_data) < num_rectas_por_caja and intentos < MAX_GLOBAL:
            intentos += 1
            result = generate_line_in_polygon(poly, main_angle, aspect)
            if result[0] is None:
                continue

            x_vals, y_vals, cx, cy = result
            analysis = analyze_line(x_vals, y_vals)
            if analysis is None:
                continue

            segments, lengths_um, segmento_medio_um, _, intercept_points, total_length_px = analysis
            score = score_recta(segments, lengths_um, x_vals, y_vals, triple_points, None, total_length_px)

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
                "total_length_um": float(total_length_px * um_per_pix)
            })

        rectas_data = sorted(rectas_data, key=lambda x: x["score"], reverse=True)[:num_rectas_por_caja]
        all_rectas_data.extend(rectas_data)
        print(f"   → {len(rectas_data)} rectas válidas en caja {poly_idx}")

    print(f"Total rectas generadas: {len(all_rectas_data)}")

    # ====================== ESTADÍSTICAS ======================
    all_lengths_um = [l for d in all_rectas_data for l in d.get("lengths_um", [])]

    if len(all_lengths_um) < 10:
        return {
            "mean_grain_size_um": None,
            "std_grain_size_um": None,
            "is_valid": False,
            "distribution_quantiles": {},
            "visualization_bytes": None,
            "num_rectas": 0
        }

    all_lengths_um = np.array(all_lengths_um)
    mean_um = float(all_lengths_um.mean()) * 1.5
    std_um = float(all_lengths_um.std(ddof=1))

    quantiles = np.quantile(all_lengths_um, np.linspace(0.1, 1.0, 10)).round(4).tolist()
    distribution_quantiles = {f"q{int(p*100)}": q for p, q in zip(np.linspace(0.1, 1.0, 10), quantiles)}

    # ====================== VISUALIZACIÓN - SOLO 5 RECTAS POR CAJA ======================
    fig, ax = plt.subplots(figsize=(W_mask/90, H_mask/90), dpi=200)
    ax.imshow(edge, cmap='gray', alpha=0.35)

    # Agrupar rectas por caja
    rectas_por_caja = defaultdict(list)
    for d in all_rectas_data:
        rectas_por_caja[d["poly_id"]].append(d)

    # Dibujar cajas y máximo 5 rectas por caja
    for i, poly in enumerate(polygons):
        # Caja
        ax.plot(poly[:, 0], poly[:, 1], color='cyan', linewidth=3.0, alpha=0.95)
        cx = int(np.mean(poly[:, 0]))
        cy = int(np.mean(poly[:, 1]))
        ax.text(cx, cy, str(i), color='yellow', fontsize=13, ha='center', va='center',
                bbox=dict(facecolor='black', alpha=0.8, pad=5))

        # Solo 5 mejores rectas por caja
        rectas_caja = rectas_por_caja.get(i, [])
        for d in rectas_caja[:5]:   # ← Aquí limitamos a 5 por caja
            ax.plot(d["x_vals"], d["y_vals"], color='limegreen', lw=1.8, alpha=0.8)
            for s, e in d["segments"]:
                ax.plot(d["x_vals"][s:e], d["y_vals"][s:e], color='red', lw=3.5, alpha=0.95)

    ax.set_title(f"Rectas OBB • Máximo 5 rectas por caja • Total: {len(all_rectas_data)}", 
                 fontsize=13, pad=20)
    ax.axis("off")

    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=260)
    buf.seek(0)
    visualization_bytes = buf.getvalue()
    plt.close(fig)

    return {
        "mean_grain_size_um": mean_um,
        "std_grain_size_um": std_um,
        "is_valid": True,
        "distribution_quantiles": distribution_quantiles,
        "visualization_bytes": visualization_bytes,
        "num_rectas": len(all_rectas_data)
    }
    