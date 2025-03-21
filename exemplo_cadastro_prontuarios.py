import requests

# URL do endpoint de cadastro de pacientes
URL = 'https://leandrolealwisemadness.pythonanywhere.com/novo_paciente'

# Dados dos pacientes da base atual
pacientes = [
    {"nome": "Ana Carolina Mendes", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Bruno Silva Rocha", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Camila Ferreira Lopes", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Daniel Costa Almeida", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Fernanda Souza Lima", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Gustavo Henrique Ramos", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Juliana Martins Pereira", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Lucas Andrade Torres", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Mariana Oliveira Duarte", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Rafael Pinto Barros", "idade": None, "sexo": "Não informado", "telefone": "Não informado"},
    {"nome": "Samuel Lopes Leal", "idade": 17, "sexo": "Não informado", "telefone": "Não informado"}
]

# Enviar dados via POST
for paciente in pacientes:
    response = requests.post(URL, data=paciente)
    if response.status_code == 200:
        print(f"Paciente {paciente['nome']} cadastrado com sucesso!")
    else:
        print(f"Erro ao cadastrar {paciente['nome']}: {response.status_code}")
