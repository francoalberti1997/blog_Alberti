import requests

url = "http://localhost:8000/metalografia/micrografias/"

micrografias = [
    {
        "nombre": "Micro 100x",
        "imagen": "../imagenes/micro_1.jpg"
    },
    {
        "nombre": "Micro 500x",
        "imagen": "../imagenes/micro_2.jpg"
    },
    {
        "nombre": "Micro 1000x",
        "imagen": "../imagenes/micro_3.jpg"
    }
]

for micro in micrografias:
    data = {
        "region": 1,  # ID de la región existente
        "nombre": micro["nombre"]
    }

    files = {
        "imagen": open(micro["imagen"], "rb")
    }

    response = requests.post(url, data=data, files=files)

    print("Creando:", micro["nombre"])
    print("Status:", response.status_code)
    print(response.json())
    print("-" * 40)