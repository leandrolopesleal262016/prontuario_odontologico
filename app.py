from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
import logging
import webbrowser
import threading
import time
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prontuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# MODELS
class Paciente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    idade = db.Column(db.Integer)
    sexo = db.Column(db.String(20))
    telefone = db.Column(db.String(20))
    prontuarios = db.relationship('Prontuario', backref='paciente', lazy=True)

class Prontuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)
    data_consulta = db.Column(db.Date, default=datetime.date.today)
    diagnostico = db.Column(db.Text)
    procedimento = db.Column(db.Text)
    prescricao = db.Column(db.Text)
    recomendacoes = db.Column(db.Text)
    anexos = db.Column(db.Text)

class Agenda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)
    data_agenda = db.Column(db.Date, nullable=False)
    observacoes = db.Column(db.Text)

# ROTAS
@app.route('/')
def index():
    return redirect(url_for('admin_dashboard'))

@app.route('/assistente')
def assistente_voz():
    return render_template('voice_assistant.html')

@app.route('/processar_comando', methods=['POST'])
def processar_comando():
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    comando = request.json.get('comando')

    # O GPT só devolve a "ação"
    resposta = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "Você é um assistente odontológico. Sempre responda apenas com o comando necessário, como: listar_pacientes, ou cadastrar_paciente Nome Idade Sexo. Não forneça explicações."},
            {"role": "user", "content": comando}
        ]
    )

    acao = resposta.choices[0].message.content.strip().lower()
    texto_resposta = ""

    if "listar_pacientes" in acao:
        pacientes = Paciente.query.all()
        lista = ", ".join([p.nome for p in pacientes])
        texto_resposta = f"Pacientes cadastrados: {lista if lista else 'Nenhum paciente encontrado.'}"

    elif "cadastrar_paciente" in acao:
        try:
            partes = acao.replace("cadastrar_paciente", "").strip().split()
            nome = partes[0]
            idade = int(partes[1])
            sexo = partes[2].capitalize()
            novo = Paciente(nome=nome, idade=idade, sexo=sexo, telefone="-")
            db.session.add(novo)
            db.session.commit()
            texto_resposta = f"Paciente {nome} cadastrado com sucesso!"
        except Exception as e:
            texto_resposta = "Erro ao cadastrar. Use: cadastrar_paciente Nome Idade Sexo"

    else:
        texto_resposta = "Comando não reconhecido. Exemplo: 'listar_pacientes' ou 'cadastrar_paciente João 30 M'."

    return jsonify({'resposta': texto_resposta})

# Adicione estas novas rotas ao seu arquivo app.py

@app.route('/paciente/<int:paciente_id>/prontuarios')
def ver_prontuarios(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    prontuarios = Prontuario.query.filter_by(paciente_id=paciente_id).order_by(Prontuario.data_consulta.desc()).all()
    return render_template('prontuarios.html', paciente=paciente, prontuarios=prontuarios)

@app.route('/paciente/<int:paciente_id>/editar', methods=['GET', 'POST'])
def editar_paciente(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    
    if request.method == 'POST':
        paciente.nome = request.form.get('nome')
        paciente.idade = request.form.get('idade')
        paciente.sexo = request.form.get('sexo')
        paciente.telefone = request.form.get('telefone', '-')
        
        try:
            db.session.commit()
            logging.info(f"Paciente ID {paciente_id} atualizado: {paciente.nome}")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao atualizar paciente: {str(e)}")
            return render_template('editar_paciente.html', paciente=paciente, erro=f"Erro ao atualizar: {str(e)}")
    
    return render_template('editar_paciente.html', paciente=paciente)

@app.route('/paciente/<int:paciente_id>/excluir', methods=['GET', 'POST'])
def excluir_paciente(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    
    if request.method == 'POST':
        try:
            # Primeiro excluir todos os prontuários associados
            Prontuario.query.filter_by(paciente_id=paciente_id).delete()
            
            # Depois excluir o paciente
            db.session.delete(paciente)
            db.session.commit()
            
            logging.info(f"Paciente ID {paciente_id} excluído: {paciente.nome}")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao excluir paciente: {str(e)}")
            return render_template('excluir_paciente.html', paciente=paciente, erro=f"Erro ao excluir: {str(e)}")
    
    return render_template('excluir_paciente.html', paciente=paciente)

@app.route('/paciente/<int:paciente_id>/novo_prontuario', methods=['GET', 'POST'])
def novo_prontuario(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    
    if request.method == 'POST':
        try:
            prontuario = Prontuario(
                paciente_id=paciente_id,
                data_consulta=datetime.datetime.strptime(request.form.get('data_consulta'), '%Y-%m-%d').date(),
                diagnostico=request.form.get('diagnostico', ''),
                procedimento=request.form.get('procedimento', ''),
                prescricao=request.form.get('prescricao', ''),
                recomendacoes=request.form.get('recomendacoes', ''),
                anexos=request.form.get('anexos', '')
            )
            
            db.session.add(prontuario)
            db.session.commit()
            
            logging.info(f"Novo prontuário criado para paciente ID {paciente_id}")
            return redirect(url_for('ver_prontuarios', paciente_id=paciente_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao criar prontuário: {str(e)}")
            return render_template('novo_prontuario.html', paciente=paciente, erro=f"Erro ao criar prontuário: {str(e)}", today=datetime.date.today().strftime('%Y-%m-%d'))
    
    return render_template('novo_prontuario.html', paciente=paciente, today=datetime.date.today().strftime('%Y-%m-%d'))

# Adicione esta rota para compatibilidade
@app.route('/paciente/<int:paciente_id>/novo_prontuario', methods=['GET', 'POST'])
def novo_prontuario_alt(paciente_id):
    # Redireciona para a rota original
    return redirect(url_for('novo_prontuario', paciente_id=paciente_id))

@app.route('/admin')
def admin_dashboard():
    try:
        pacientes = Paciente.query.all()
        
        # Depuração
        print(f"Número de pacientes encontrados: {len(pacientes)}")
        for p in pacientes:
            print(f"Paciente ID: {p.id}, Nome: {p.nome}")
        
        # Verifica explicitamente se a lista está vazia
        if not pacientes:
            print("Lista de pacientes está vazia!")
            # Tenta buscar novamente
            db.session.commit()
            pacientes = Paciente.query.all()
        
        # Converte para lista Python para garantir que não é um objeto SQLAlchemy
        pacientes_lista = []
        for p in pacientes:
            pacientes_lista.append({
                'id': p.id,
                'nome': p.nome,
                'idade': p.idade,
                'sexo': p.sexo,
                'telefone': p.telefone
            })
        
        print(f"Lista convertida: {pacientes_lista}")
        
        # CORREÇÃO: Passa a lista convertida para o template
        return render_template('admin_dashboard.html', pacientes=pacientes_lista)
    except Exception as e:
        logging.error(f"Erro ao carregar dashboard: {str(e)}")
        db.session.rollback()
        pacientes = Paciente.query.all()
        
        # Também converte aqui no caso de exceção
        pacientes_lista = []
        for p in pacientes:
            pacientes_lista.append({
                'id': p.id,
                'nome': p.nome,
                'idade': p.idade,
                'sexo': p.sexo,
                'telefone': p.telefone
            })
            
        return render_template('admin_dashboard.html', pacientes=pacientes_lista)

# Função para inicializar o banco de dados
def initialize_database(app):
    with app.app_context():
        # Força a criação das tabelas
        db.create_all()
        
        # Força uma operação de leitura para "acordar" a conexão
        try:
            count = Paciente.query.count()
            logging.info(f"Banco de dados inicializado. {count} pacientes encontrados.")
            
            # Força uma operação de commit para garantir que a sessão está ativa
            db.session.commit()
            
            # Busca todos os pacientes para verificar
            pacientes = Paciente.query.all()
            for p in pacientes:
                logging.info(f"Paciente carregado: ID={p.id}, Nome={p.nome}")
                
            return True
        except Exception as e:
            logging.error(f"Erro ao inicializar banco de dados: {str(e)}")
            return False

@app.route('/admin/logs')
def view_logs():
    try:
        with open('app.log', 'r') as log_file:
            logs = log_file.readlines()
        return render_template('logs.html', logs=logs)
    except FileNotFoundError:
        return "<p>Arquivo de log ainda não foi criado.</p>"

@app.route('/privacy')
def privacy_policy():
    return send_from_directory(os.path.dirname(__file__), 'privacy.html', mimetype='text/html')

@app.route('/.well-known/ai-plugin.json')
def serve_manifest():
    return send_from_directory(os.path.dirname(__file__), 'ai-plugin.json', mimetype='application/json')

@app.route('/openapi.yaml')
def serve_openapi():
    return send_from_directory(os.path.dirname(__file__), 'openapi.yaml', mimetype='text/yaml')

@app.route('/novo_paciente', methods=['GET', 'POST'])
def novo_paciente():
    if request.method == 'POST':
        # Obter dados do formulário
        nome = request.form.get('nome')
        idade = request.form.get('idade')
        sexo = request.form.get('sexo')
        telefone = request.form.get('telefone', '-')
        
        # Validar dados
        if not nome or not idade or not sexo:
            return render_template('novo_paciente.html', erro="Todos os campos obrigatórios devem ser preenchidos.")
        
        try:
            # Criar novo paciente
            novo_paciente = Paciente(
                nome=nome,
                idade=int(idade),
                sexo=sexo,
                telefone=telefone
            )
            
            # Salvar no banco de dados
            db.session.add(novo_paciente)
            db.session.commit()
            
            # Registrar no log
            logging.info(f"Novo paciente cadastrado: {nome}")
            
            # Redirecionar para a lista de pacientes
            return redirect(url_for('admin_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao cadastrar paciente: {str(e)}")
            return render_template('novo_paciente.html', erro=f"Erro ao cadastrar: {str(e)}")
    
    # Se for GET, apenas exibe o formulário
    return render_template('novo_paciente.html')

@app.route('/debug/pacientes')
def debug_pacientes():
    try:
        pacientes = Paciente.query.all()
        result = []
        for p in pacientes:
            result.append({
                'id': p.id,
                'nome': p.nome,
                'idade': p.idade,
                'sexo': p.sexo,
                'telefone': p.telefone
            })
        return jsonify(pacientes=result)
    except Exception as e:
        return jsonify(error=str(e))

def open_browser():
    """Função para abrir o navegador após um pequeno atraso"""
    time.sleep(1.5)  # Aguarda 1.5 segundos para o servidor iniciar
    webbrowser.open('http://127.0.0.1:5000/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Adicione aqui a lógica de inicialização do banco de dados
        try:
            # Força uma consulta para verificar a conexão
            pacientes_count = Paciente.query.count()
            logging.info(f"Banco de dados inicializado com sucesso. {pacientes_count} pacientes encontrados.")
        except Exception as e:
            logging.error(f"Erro ao inicializar banco de dados: {str(e)}")
            # Tenta recriar as tabelas se necessário
            db.create_all()
            logging.info("Tabelas do banco de dados recriadas.")
    
    # Inicia uma thread para abrir o navegador
    threading.Thread(target=open_browser).start()
    
    # Inicia o servidor Flask
    app.run(debug=True)
