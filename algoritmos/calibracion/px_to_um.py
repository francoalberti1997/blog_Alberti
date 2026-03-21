import matplotlib.pyplot as plt
import numpy as np

def marcar_recta(img):
    """
    Muestra la imagen y repite 3 veces el proceso de marcar una recta + ingresar longitud real.
    Devuelve el promedio de las 3 mediciones en µm/píxel.
    """
    print("=== CALIBRACIÓN INTERACTIVA (3 mediciones) ===")
    print("Para cada una de las 3 veces:")
    print("  1. Aparecerá la imagen")
    print("  2. Haz clic en los dos extremos de la regla / escala")
    print("  3. Ingresa la longitud real en µm cuando te lo pida")
    print("Cuando termines las 3, se calculará el promedio.\n")

    ratios = []

    for i in range(1, 2):
        print(f"\nMedición {i} de 3...")
        
        plt.figure(figsize=(10, 8))
        plt.imshow(img)
        plt.title(f"Medición {i}/3: Click en los extremos de la regla")
        plt.axis('off')
        
        points = plt.ginput(2, timeout=0)  # esperar 2 clicks
        plt.close()

        if len(points) < 2:
            print("No se seleccionaron 2 puntos. Saltando esta medición.")
            continue

        p1, p2 = np.array(points[0]), np.array(points[1])
        dist_pix = np.linalg.norm(p2 - p1)
        print(f"   Distancia medida: {dist_pix:.2f} px")

        while True:
            try:
                dist_um = float(input("   Ingrese distancia real en µm: "))
                if dist_um <= 0:
                    print("   Valor inválido, debe ser positivo.")
                    continue
                break
            except ValueError:
                print("   Ingresa un número válido.")

        ratio = dist_um / dist_pix
        ratios.append(ratio)
        print(f"   → Relación calculada: 1 px = {ratio:.4f} µm")

    if not ratios:
        raise ValueError("No se completó ninguna medición válida.")

    avg_ratio = np.mean(ratios)
    print(f"\nCalibración final (promedio de {len(ratios)} mediciones): {avg_ratio:.4f} µm/píxel")
    
    return avg_ratio