# reports/utils.py
import os
import tempfile
import numpy as np
from collections import Counter, defaultdict
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from reportlab.platypus import Image
from reportlab.lib.units import cm
from metalografia.models import Micrografia
from reportlab.platypus import Image
from PIL import Image
import numpy as np

from reportlab.platypus import Image as RLImage
from PIL import Image as PILImage

# ====================== CALIDADES FIJAS ======================
CALIDADES_FIJAS = [
    {"id": 1, "tipo": "sinterizado", "min": 40,  "max": 90,   "label": "Calidad 1: 40–90 µm"},
    {"id": 2, "tipo": "sinterizado", "min": 100, "max": 200,  "label": "Calidad 2: 100–200 µm"},
    {"id": 3, "tipo": "sinterizado", "min": 200, "max": 250,  "label": "Calidad 3: 200–250 µm"},
    {"id": 4, "tipo": "sinterizado", "min": 300, "max": 350,  "label": "Calidad 4: 300–350 µm"},
    {"id": 5, "tipo": "electrofundido", "min": 400, "max": 500,  "label": "Calidad 5: 400–500 µm"},
    {"id": 6, "tipo": "electrofundido", "min": 550, "max": 600,  "label": "Calidad 6: 550–600 µm"},
    {"id": 7, "tipo": "electrofundido", "min": 600, "max": 700,  "label": "Calidad 7: 600–700 µm"},
    {"id": 8, "tipo": "electrofundido", "min": 700, "max": 800,  "label": "Calidad 8: 700–800 µm"},
    {"id": 9, "tipo": "electrofundido", "min": 800, "max": 900,  "label": "Calidad 9: 800–900 µm"},
    {"id": 10,"tipo": "electrofundido", "min": 901, "max": 99999,"label": "Calidad 10: >900 µm"},
]


def assign_calidad(tc_um):
    for cal in CALIDADES_FIJAS:
        if cal["min"] <= tc_um <= cal["max"]:
            return cal
    if tc_um > 900:
        return next(c for c in CALIDADES_FIJAS if c["id"] == 10)
    if tc_um < 40:
        return next(c for c in CALIDADES_FIJAS if c["id"] == 1)
    return min(CALIDADES_FIJAS, key=lambda c: abs(tc_um - c["min"]))


def assign_tipo(tc_um):
    return "sinterizado" if tc_um <= 400 else "electrofundido"


def create_distribution_plot(values):
    if len(values) == 0:
        return None

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        fig, ax = plt.subplots(figsize=(14, 8.5), dpi=190)

        ax.hist(values, bins=np.arange(0, max(1250, values.max() + 150), 50),
                color="#4682B4", edgecolor="white", alpha=0.82, linewidth=0.8, zorder=3)

        if len(values) > 10:
            from scipy.stats import gaussian_kde

            kde = gaussian_kde(values)
            x_range = np.linspace(0, max(1250, values.max() + 150), 600)
            ax.plot(x_range, kde(x_range) * len(values) * 50,
                    color="#C62828", linewidth=3.5, linestyle="-", alpha=0.9,
                    label="Densidad estimada", zorder=4)

        key_boundaries = [350, 450, 900]
        for x in key_boundaries:
            ax.axvline(x, color="#666666", linestyle="--", linewidth=1.8, alpha=0.7, zorder=2)

        quality_centers = {
            65: "Calidad 1", 150: "Calidad 2", 225: "Calidad 3", 325: "Calidad 4",
            450: "Calidad 5", 575: "Calidad 6", 650: "Calidad 7", 750: "Calidad 8",
            850: "Calidad 9", 1100: "Calidad 10"
        }
        fixed_y_pos = ax.get_ylim()[1] * 0.75
        for x, label in quality_centers.items():
            ax.text(x, fixed_y_pos, label,
                    fontsize=17, fontweight='bold', color="#1a3c5e",
                    ha='center', va='bottom', rotation=90,
                    bbox=dict(facecolor='white', alpha=0.92, edgecolor='none', pad=4.2))

        max_x = max(1250, values.max() + 150)
        ax.set_xticks(np.arange(0, max_x + 100, 100))
        ax.set_xticklabels([f"{int(x)}" for x in np.arange(0, max_x + 100, 100)], fontsize=16)

        ax.set_xlabel("Tamaño medio de cristal (µm)", fontsize=24, labelpad=18)
        ax.set_ylabel("Frecuencia", fontsize=24, labelpad=18)
        ax.set_title("Distribución del tamaño de cristal por calidad",
                     fontsize=30, pad=32, weight='bold', color="#0f2b4a")

        ax.legend(fontsize=20, loc="upper right", frameon=True,
                  edgecolor="#bbbbbb", facecolor="white", framealpha=0.98)

        ax.grid(True, axis='y', alpha=0.4, linestyle="--", color="#dddddd")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(axis='both', which='major', labelsize=18, pad=10)
        ax.set_xlim(0, max_x)

        plt.tight_layout()
        plt.savefig(tmp.name, dpi=190, bbox_inches="tight", pad_inches=0.5)
        plt.close(fig)

        return tmp.name


def image_keep_aspect(path, max_width_cm, max_height_cm):
    img = PILImage.open(path)
    w, h = img.size
    aspect = w / h

    max_w = max_width_cm * cm
    max_h = max_height_cm * cm

    if (max_w / aspect) <= max_h:
        width = max_w
        height = max_w / aspect
    else:
        height = max_h
        width = max_h * aspect

    return RLImage(path, width=width, height=height)

import numpy as np
from django.http import Http404


# def get_um_by_px(obj_id: int, um_per_pix_original) -> float:
#     """
#     Calcula los micrómetros por píxel después de redimensionar la imagen a 512x512.
#     """
#     # 1. Buscar la micrografía de forma segura
#     micrografia = Micrografia.objects.filter(id=obj_id).first()
    
#     if micrografia is None:
#         raise Http404(f"No existe Micrografia con id = {obj_id}")

#     print(f"Micrografía encontrada: {micrografia.id}")

#     if not micrografia.imagen:
#         raise ValueError(f"La micrografía {obj_id} no tiene imagen asociada")

#     # 2. Convertir el valor que viene del frontend a float (¡esto soluciona el error!)
#     try:
#         um_per_pix_original = float(um_per_pix_original)
#     except (TypeError, ValueError):
#         raise ValueError(f"um_by_px_original debe ser un número válido. Recibido: {um_per_pix_original}")

#     # 3. Obtener dimensiones originales de la   
#     with Image.open(micrografia.imagen.url) as img:
#         original_width, original_height = img.size   # Mejor usar .size que convertir a array

#     # 4. Calcular factor de escalado
#     max_side_original = max(original_width, original_height)
#     scale_factor = max_side_original / 512.0

#     # 5. Cálculo final
#     um_per_pix = um_per_pix_original * scale_factor

#     print(f"Original: {max_side_original}px | Scale: {scale_factor:.3f} | µm/px final: {um_per_pix:.4f}")

#     return round(um_per_pix, 4)


def get_um_by_px(obj_id: int, um_per_pix_original) -> float:
    micrografia = Micrografia.objects.filter(id=obj_id).first()
    
    if micrografia is None:
        raise Http404(f"No existe Micrografia con id = {obj_id}")

    if not micrografia.imagen:
        raise ValueError(f"La micrografía {obj_id} no tiene imagen asociada")

    try:
        um_per_pix_original = float(um_per_pix_original)
    except (TypeError, ValueError):
        raise ValueError(f"um_by_px_original inválido: {um_per_pix_original}")

    # 🔴 FIX ACA
    import requests
    from io import BytesIO

    response = requests.get(micrografia.imagen.url)
    img = Image.open(BytesIO(response.content))
    original_width, original_height = img.size

    max_side_original = max(original_width, original_height)
    scale_factor = max_side_original / 512.0

    um_per_pix = um_per_pix_original * scale_factor

    return round(um_per_pix, 4)
