import requests

# URL da sua API
url = "https://leandrolealwisemadness.pythonanywhere.com/api/prontuario"

# Payload (os dados do prontuário)
data = {
    "paciente_id": 1,
    "diagnostico": "Cárie profunda no dente 26 com abscesso periapical.",
    "procedimento": "Realizada abertura endodôntica e drenagem do abscesso.",
    "prescricao": [
        "Amoxicilina 500mg 8/8h por 7 dias",
        "Ibuprofeno 600mg 8/8h por 3 dias"
    ],
    "recomendacoes": "Retorno em 7 dias para continuidade do tratamento.",
    "anexos": [
        {"descricao": "Radiografia periapical dente 26", "link": "https://minha-clinica.com/exames/rx-dente26.png"}
    ]
}

# Fazendo o POST
response = requests.post(url, json=data)

# Verificando resposta
print("Status Code:", response.status_code)
print("Resposta:", response.json())
