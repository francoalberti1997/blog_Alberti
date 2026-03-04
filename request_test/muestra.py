import requests

url = "https://francoalberti97.pythonanywhere.com/modelos/muestras/"

data = {
    "nombre": "Muestra 1",
    "material": "Acero",
    "informacion": "Ensayo metalográfico",
    "fecha": "2026-03-04"
}

files = {
    "imagen": open("../imagenes/muestra.jpg", "rb")
}

response = requests.post(url, data=data, files=files)

print("Status:", response.status_code)
print(response.text)