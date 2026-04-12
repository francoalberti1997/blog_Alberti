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
from scipy.stats import gaussian_kde
from reportlab.platypus import Image as RLImage
from PIL import Image as PILImage
import seaborn as sns
from reportlab.platypus import Image
from metalografia.models import Micrografia
from reportlab.platypus import Image
from PIL import Image
from django.http import Http404
import tempfile
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
from uuid import uuid4   


import numpy as np
import matplotlib.pyplot as plt
import os
from django.conf import settings

def create_crystals_distribution_plot(data, title="", highlight_value=None, highlight_label=None, 
                                      highlight_color='red', umbral=400):
    """
    Crea histograma + KDE con áreas coloreadas:
    - Azul claro: Sinterizado (< 400 µm)
    - Naranja: Electrofundido (≥ 400 µm)
    - Línea roja punteada: Media de la región
    """
    if len(data) < 3:
        raise ValueError("No hay suficientes datos para generar el gráfico con KDE")

    data = np.array(data)

    # Estadísticos
    mean_d = np.mean(data)
    std_d = np.std(data)
    xmin = np.min(data)
    xmax = np.max(data)

    # KDE (curva suave)
    kde = gaussian_kde(data)
    x_vals = np.linspace(xmin - 0.05*(xmax - xmin), xmax + 0.05*(xmax - xmin), 1000)
    y_vals = kde(x_vals)

    # Área total bajo la curva
    area_total = np.trapezoid(y_vals, x_vals)
    mask_sinter = x_vals < umbral
    mask_electro = x_vals >= umbral

    area_sinter = np.trapezoid(y_vals[mask_sinter], x_vals[mask_sinter])
    area_electro = np.trapezoid(y_vals[mask_electro], x_vals[mask_electro])

    pct_area_sinter = (area_sinter / area_total * 100) if area_total > 0 else 0
    pct_area_electro = (area_electro / area_total * 100) if area_total > 0 else 0

    # Porcentaje real de puntos
    pct_sinter = np.sum(data < umbral) / len(data) * 100
    pct_electro = 100 - pct_sinter

    # ====================== GRÁFICO ======================
    plt.figure(figsize=(11, 7), dpi=180)

    # Histograma base (transparente)
    plt.hist(data, bins=25, density=True, alpha=0.25,
             color='lightgray', edgecolor='black', label='_nolegend_')

    # KDE completa
    plt.plot(x_vals, y_vals, color='black', linewidth=2.5, label='KDE')

    # Áreas coloreadas
    plt.fill_between(x_vals[mask_sinter], y_vals[mask_sinter], color='#3498db', alpha=0.45,
                     label=f"Sinterizada (< {umbral} µm)\n"
                           f"Área KDE: {pct_area_sinter:.1f}%\n"
                           f"Puntos: {pct_sinter:.1f}%")

    plt.fill_between(x_vals[mask_electro], y_vals[mask_electro], color='#e67e22', alpha=0.45,
                     label=f"Electrofundida (≥ {umbral} µm)\n"
                           f"Área KDE: {pct_area_electro:.1f}%\n"
                           f"Puntos: {pct_electro:.1f}%")

    # Línea del umbral
    plt.axvline(umbral, color='black', linestyle='--', linewidth=2.2, label=f'Umbral = {umbral} µm')

    # Media de la región (rojo)
    if highlight_value is not None:
        plt.axvline(highlight_value, color=highlight_color, linestyle='--', linewidth=3.5,
                    label=highlight_label or f'Media región = {highlight_value:.2f} µm')

    # # Media general
    # plt.axvline(mean_d, color='darkblue', linestyle='-', linewidth=2.8,
    #             label=f'Media general = {mean_d:.2f} µm')

    # Etiquetas y estilo
    plt.xlabel("Tamaño de cristal (µm)", fontsize=13)
    plt.ylabel("Densidad de probabilidad", fontsize=13)
    plt.title(title, fontsize=14, fontweight='bold', pad=20)

    plt.xlim(xmin - 5, xmax + 5)
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.legend(fontsize=13.5, framealpha=0.95, loc='upper right')

    # Estadísticas en el gráfico
    plt.text(0.02, 0.96,
             f"Media: {mean_d:.2f} µm\n",
            #  f"Desv. Est.: {std_d:.2f} µm",
             transform=plt.gca().transAxes,
             fontsize=11,
             verticalalignment='top',
             bbox=dict(boxstyle="round,pad=0.6", facecolor='white', alpha=0.9))

    plt.tight_layout()

    # Guardar
    os.makedirs(os.path.join(settings.MEDIA_ROOT, 'temp_plots'), exist_ok=True)
    filename = f"crystals_dist_{uuid4().hex[:16]}.png"
    save_path = os.path.join(settings.MEDIA_ROOT, 'temp_plots', filename)

    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()

    return save_path


def create_distribution_plot(data, title="Distribución de tamaños de grano", xlabel="Tamaño (µm)", ylabel="Frecuencia", bins=15, save_path=None):
    """
    Crea un histograma de distribución y guarda la imagen.
    Retorna la ruta absoluta del archivo PNG generado.
    """
    if len(data) == 0:
        return None

    # Configuración visual bonita
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    
    ax = sns.histplot(data, bins=bins, kde=True, color="#2C3E50", edgecolor="black", alpha=0.8)
    
    ax.set_title(title, fontsize=14, pad=20)
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    
    # Añadir media y mediana
    mean = data.mean()
    ax.axvline(mean, color='red', linestyle='--', linewidth=2, label=f'Media: {mean:.1f} µm')
    ax.legend()

    plt.tight_layout()

    # Guardar en carpeta temporal
    if save_path is None:
        temp_dir = "temp_plots"  # o usa settings.MEDIA_ROOT + "/temp_plots"
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"dist_plot_{uuid4().hex[:12]}.png"
        save_path = os.path.join(temp_dir, filename)

    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()   # Importante: liberar memoria

    return os.path.abspath(save_path)


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


# ================== CALIDADES ======================
GRAIN_QUALITIES = [
    (0, 90),       # Calidad 1
    (100, 200),    # Calidad 2
    (200, 250),    # Calidad 3
    (300, 350),    # Calidad 4
    (400, 500),    # Calidad 5
    (550, 600),    # Calidad 6
    (600, 700),    # Calidad 7
    (700, 800),    # Calidad 8
    (800, 900),    # Calidad 9
    (901, float("inf")),  # Calidad 10
]


def get_quality(size):
    for i, (low, high) in enumerate(GRAIN_QUALITIES, start=1):
        if low <= size <= high:
            return i
    return None

def create_quality_distribution_plot(qualities_list, 
                                     title="Distribución de Calidades de Grano",
                                     xlabel="Calidad de Grano",
                                     ylabel="Frecuencia",
                                     save_path=None):
    """
    Histograma de barras DISCRETO: Frecuencia (eje Y) contra Calidad (eje X = 1 a 10).
    Usa el mismo estilo bonito que create_distribution_plot (seaborn + grid + valores en barras).
    """
    if not qualities_list:
        return None

    import matplotlib.pyplot as plt
    import seaborn as sns
    from collections import Counter
    from uuid import uuid4
    import os

    count = Counter(qualities_list)
    qualities = list(range(1, 11))
    frequencies = [count.get(q, 0) for q in qualities]

    # Configuración visual idéntica a create_distribution_plot
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    
    ax = sns.barplot(x=qualities, y=frequencies, 
                     color="#2C3E50", edgecolor="black", alpha=0.85)
    
    ax.set_title(title, fontsize=14, pad=20)
    ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_xticks(qualities)

    # Valores encima de cada barra
    for i, freq in enumerate(frequencies):
        if freq > 0:
            ax.text(i, freq + max(frequencies)*0.02, f'{int(freq)}',
                    ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.tight_layout()

    # Guardar en carpeta temporal (igual que create_distribution_plot)
    if save_path is None:
        temp_dir = "temp_plots"
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"quality_dist_plot_{uuid4().hex[:12]}.png"
        save_path = os.path.join(temp_dir, filename)

    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()

    return os.path.abspath(save_path)


def create_intercept_distribution_plot(data, title="", highlight_value=None, highlight_label=None,
                                       highlight_color='red'):
    """
    Crea histograma + KDE para LONGITUD MEDIA DE INTERCEPTO (µm)
    - Ideal para acero con método de interceptos (ASTM E112)
    - Sin ninguna referencia a 'calidad' ni a números ASTM
    """
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from collections import Counter
    from uuid import uuid4
    import os
    from django.conf import settings


    data = np.array(data)

    # Estadísticos
    mean_val = np.mean(data)
    std_val = np.std(data)
    xmin = np.min(data)
    xmax = np.max(data)

    # ====================== GRÁFICO ======================
    plt.figure(figsize=(11, 7), dpi=180)
    sns.set_style("whitegrid")

    # Histograma base
    plt.hist(data, bins=25, density=True, alpha=0.30,
             color='lightgray', edgecolor='black')

    # KDE (curva suave)
    sns.kdeplot(data, color='black', linewidth=2.8, label='KDE')

    # Media de la región (línea roja gruesa)
    if highlight_value is not None:
        plt.axvline(highlight_value, color=highlight_color, linestyle='--', linewidth=3.5,
                    label=highlight_label or f'Media = {highlight_value:.2f} µm')

    # Media general (opcional - descomentar si querés)
    # plt.axvline(mean_val, color='darkblue', linestyle='-', linewidth=2.5,
    #             label=f'Media general = {mean_val:.2f} µm')

    plt.xlabel("Longitud media de intercepto (µm)", fontsize=13, fontweight='bold')
    plt.ylabel("Densidad de probabilidad", fontsize=13, fontweight='bold')
    plt.title(title or "Distribución de Longitud de Intercepto", fontsize=14, pad=20)

    plt.xlim(xmin - 5, xmax + 5)
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.legend(fontsize=12.5, framealpha=0.95, loc='upper right')

    # Texto con estadísticos
    plt.text(0.02, 0.96,
             f"Media: {mean_val:.2f} µm\n",
            transform=plt.gca().transAxes,
             fontsize=11.5,
             verticalalignment='top',
             bbox=dict(boxstyle="round,pad=0.6", facecolor='white', alpha=0.92))

    plt.tight_layout()

    # Guardar
    os.makedirs(os.path.join(settings.MEDIA_ROOT, 'temp_plots'), exist_ok=True)
    filename = f"intercept_dist_{uuid4().hex[:16]}.png"
    save_path = os.path.join(settings.MEDIA_ROOT, 'temp_plots', filename)

    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()

    return save_path