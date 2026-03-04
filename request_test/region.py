import requests

url = "http://localhost:8000/modelos/regiones/"

regiones = [
    {
        "nombre": "Zona A",
        "imagen": "imagenes/region_1.jpg"
    },
    {
        "nombre": "Zona B",
        "imagen": "imagenes/region_2.jpg"
    }
]

for region in regiones:
    data = {
        "muestra": 1,  # ID de la muestra existente
        "nombre": region["nombre"]
    }

    files = {
        "imagen": open(region["imagen"], "rb")
    }

    response = requests.post(url, data=data, files=files)

    print("Creando:", region["nombre"])
    print("Status:", response.status_code)
    print(response.json())
    print("-" * 40)