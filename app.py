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
    try:
        import openai
        
        # Obter a chave da API
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            logging.error("OPENAI_API_KEY não está configurada")
            return jsonify({'resposta': 'Erro: Chave da API OpenAI não configurada. Contate o administrador.'}), 500
        
        # Verificar a versão da biblioteca OpenAI e inicializar o cliente adequadamente
        comando = request.json.get('comando')
        
        try:
            # Tente o método mais recente (OpenAI v1.x)
            client = openai.OpenAI(api_key=api_key)
            
            resposta = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Você é um assistente odontológico. Sempre responda apenas com o comando necessário, como: listar_pacientes, cadastrar_paciente Nome Idade Sexo, ou cancelar_agendamento Nome Data. Não forneça explicações."},
                    {"role": "user", "content": comando}
                ]
            )
            
            acao = resposta.choices[0].message.content.strip().lower()
            
        except (AttributeError, TypeError):
            # Fallback para o método antigo (OpenAI v0.x)
            logging.info("Usando API OpenAI legada")
            resposta = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Você é um assistente odontológico. Sempre responda apenas com o comando necessário, como: listar_pacientes, cadastrar_paciente Nome Idade Sexo, ou cancelar_agendamento Nome Data. Não forneça explicações."},
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
                
                # Verificar se já existe um paciente com o mesmo nome
                paciente_existente = Paciente.query.filter(Paciente.nome == nome).first()
                if paciente_existente:
                    texto_resposta = f"Paciente {nome} já existe no sistema."
                else:
                    novo = Paciente(nome=nome, idade=idade, sexo=sexo, telefone="-")
                    db.session.add(novo)
                    db.session.commit()
                    texto_resposta = f"Paciente {nome} cadastrado com sucesso!"
            except Exception as e:
                texto_resposta = f"Erro ao cadastrar: {str(e)}. Use: cadastrar_paciente Nome Idade Sexo"
                
        elif "cancelar_agendamento" in acao:
            try:
                # Extrair nome e data
                partes = acao.replace("cancelar_agendamento", "").strip().split()
                if len(partes) < 2:
                    texto_resposta = "Formato inválido. Use: cancelar_agendamento Nome YYYY-MM-DD"
                else:
                    nome = partes[0]
                    data_str = partes[1]
                    
                    # Buscar o paciente
                    paciente = Paciente.query.filter(Paciente.nome.like(f"%{nome}%")).first()
                    if not paciente:
                        texto_resposta = f"Paciente {nome} não encontrado."
                    else:
                        # Converter string para data
                        try:
                            data = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
                        except ValueError:
                            texto_resposta = "Formato de data inválido. Use YYYY-MM-DD"
                            return jsonify({'resposta': texto_resposta})
                        
                        # Buscar agendamento
                        agendamento = Agenda.query.filter_by(
                            paciente_id=paciente.id,
                            data_agenda=data
                        ).first()
                        
                        if not agendamento:
                            texto_resposta = f"Nenhum agendamento encontrado para {nome} na data {data_str}."
                        else:
                            # Excluir agendamento
                            db.session.delete(agendamento)
                            db.session.commit()
                            texto_resposta = f"Agendamento de {nome} para {data_str} cancelado com sucesso."
            except Exception as e:
                db.session.rollback()
                texto_resposta = f"Erro ao cancelar agendamento: {str(e)}"
                
        else:
            texto_resposta = "Comando não reconhecido. Exemplos: 'listar_pacientes', 'cadastrar_paciente João 30 M', 'cancelar_agendamento João 2025-04-01'."
            
        return jsonify({'resposta': texto_resposta})
        
    except Exception as e:
        logging.error(f"Erro ao processar comando: {str(e)}")
        return jsonify({'resposta': f"Erro ao processar comando: {str(e)}"}), 500

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
        try:
            # Verificar se os dados vieram como JSON ou como form data
            if request.is_json:
                dados = request.json
            else:
                dados = request.form
            
            # Obter dados do formulário/JSON
            nome = dados.get('nome')
            idade = dados.get('idade')
            sexo = dados.get('sexo')
            telefone = dados.get('telefone', '-')
            
            # Validar apenas o nome como obrigatório
            if not nome:
                if request.is_json:
                    return jsonify({'erro': 'O campo nome é obrigatório.'}), 400
                else:
                    return render_template('novo_paciente.html', erro="O campo nome é obrigatório.")
            
            # Converter idade para inteiro se fornecida
            idade_int = None
            if idade:
                try:
                    idade_int = int(idade)
                except (ValueError, TypeError):
                    idade_int = 0  # Valor padrão se não for possível converter
            
            # Criar novo paciente
            novo_paciente = Paciente(
                nome=nome,
                idade=idade_int,
                sexo=sexo or '-',  # Valor padrão se não fornecido
                telefone=telefone or '-'  # Valor padrão se não fornecido
            )
            
            # Salvar no banco de dados
            db.session.add(novo_paciente)
            db.session.commit()
            
            # Registrar no log
            logging.info(f"Novo paciente cadastrado: {nome}")
            
            # Responder de acordo com o tipo de requisição
            if request.is_json:
                return jsonify({
                    'id': novo_paciente.id,
                    'status': 'Paciente cadastrado com sucesso'
                })
            else:
                # Redirecionar para a lista de pacientes
                return redirect(url_for('admin_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao cadastrar paciente: {str(e)}")
            
            if request.is_json:
                return jsonify({'erro': f"Erro ao cadastrar: {str(e)}"}), 500
            else:
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

# Rota para listar pacientes (API)
@app.route('/pacientes')
def listar_pacientes():
    try:
        # Obter parâmetros de filtro (opcional)
        sexo = request.args.get('sexo')
        idade = request.args.get('idade')
        
        # Construir a query base
        query = Paciente.query
        
        # Aplicar filtros se fornecidos
        if sexo:
            query = query.filter(Paciente.sexo == sexo)
        if idade:
            try:
                idade = int(idade)
                query = query.filter(Paciente.idade == idade)
            except (TypeError, ValueError):
                pass
        
        # Executar a query
        pacientes = query.all()
        
        # Converter para JSON
        resultado = []
        for p in pacientes:
            resultado.append({
                'id': p.id,
                'nome': p.nome,
                'idade': p.idade,
                'sexo': p.sexo,
                'telefone': p.telefone
            })
        
        # Registrar no log
        logging.info(f"API: Listagem de pacientes retornou {len(resultado)} resultados")
        
        # Retornar como JSON
        return jsonify(resultado)
    
    except Exception as e:
        logging.error(f"Erro ao listar pacientes via API: {str(e)}")
        return jsonify({'erro': 'Erro interno do servidor'}), 500

# Rota para buscar paciente por nome
@app.route('/paciente/nome/<nome>')
def buscar_paciente_nome(nome):
    try:
        # Busca pacientes que contenham o nome fornecido
        pacientes = Paciente.query.filter(Paciente.nome.like(f'%{nome}%')).all()
        
        if not pacientes:
            return jsonify({'mensagem': 'Nenhum paciente encontrado com esse nome'}), 404
        
        # Converter para JSON
        resultado = []
        for p in pacientes:
            # Buscar prontuários do paciente
            prontuarios_lista = []
            for pront in p.prontuarios:
                prontuarios_lista.append({
                    'data_consulta': pront.data_consulta.strftime('%Y-%m-%d') if pront.data_consulta else None,
                    'diagnostico': pront.diagnostico,
                    'procedimento': pront.procedimento,
                    'prescricao': pront.prescricao,
                    'recomendacoes': pront.recomendacoes,
                    'anexos': pront.anexos
                })
            
            resultado.append({
                'id': p.id,
                'nome': p.nome,
                'idade': p.idade,
                'sexo': p.sexo,
                'telefone': p.telefone,
                'prontuarios': prontuarios_lista
            })
        
        logging.info(f"API: Busca por nome '{nome}' retornou {len(resultado)} resultados")
        return jsonify(resultado)
    
    except Exception as e:
        logging.error(f"Erro ao buscar paciente por nome: {str(e)}")
        return jsonify({'erro': 'Erro interno do servidor'}), 500

# Rota para buscar paciente por ID
@app.route('/paciente/<int:id>')
def buscar_paciente_id(id):
    try:
        paciente = Paciente.query.get_or_404(id)
        
        # Buscar prontuários do paciente
        prontuarios_lista = []
        for pront in paciente.prontuarios:
            prontuarios_lista.append({
                'data_consulta': pront.data_consulta.strftime('%Y-%m-%d') if pront.data_consulta else None,
                'diagnostico': pront.diagnostico,
                'procedimento': pront.procedimento,
                'prescricao': pront.prescricao,
                'recomendacoes': pront.recomendacoes,
                'anexos': pront.anexos
            })
        
        resultado = {
            'nome': paciente.nome,
            'idade': paciente.idade,
            'sexo': paciente.sexo,
            'telefone': paciente.telefone,
            'prontuarios': prontuarios_lista
        }
        
        logging.info(f"API: Busca por ID {id} retornou paciente {paciente.nome}")
        return jsonify(resultado)
    
    except Exception as e:
        logging.error(f"Erro ao buscar paciente por ID: {str(e)}")
        return jsonify({'erro': 'Erro interno do servidor'}), 500

# Rota para gerenciar agenda
@app.route('/agenda', methods=['GET', 'POST'])
def agenda():
    if request.method == 'GET':
        try:
            # Obter data do parâmetro de consulta
            data_str = request.args.get('data')
            if not data_str:
                return jsonify({'erro': 'Parâmetro data é obrigatório'}), 400
            
            # Converter string para data
            try:
                data = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'erro': 'Formato de data inválido. Use YYYY-MM-DD'}), 400
            
            # Buscar agendamentos para a data
            agendamentos = Agenda.query.filter(Agenda.data_agenda == data).all()
            
            # Converter para JSON
            resultado = []
            for a in agendamentos:
                paciente = Paciente.query.get(a.paciente_id)
                resultado.append({
                    'paciente': paciente.nome if paciente else 'Paciente não encontrado',
                    'data_agenda': a.data_agenda.strftime('%Y-%m-%d'),
                    'observacoes': a.observacoes
                })
            
            logging.info(f"API: Listagem de agenda para {data_str} retornou {len(resultado)} agendamentos")
            return jsonify(resultado)
        
        except Exception as e:
            logging.error(f"Erro ao listar agenda: {str(e)}")
            return jsonify({'erro': 'Erro interno do servidor'}), 500
    
    elif request.method == 'POST':
        try:
            # Obter dados do corpo da requisição
            dados = request.json
            
            # Validar dados
            if not dados or 'paciente_id' not in dados or 'data_agenda' not in dados:
                return jsonify({'erro': 'Dados incompletos. Forneça paciente_id e data_agenda'}), 400
            
            # Verificar se o paciente existe
            paciente = Paciente.query.get(dados['paciente_id'])
            if not paciente:
                return jsonify({'erro': 'Paciente não encontrado'}), 404
            
            # Converter string para data
            try:
                data_agenda = datetime.datetime.strptime(dados['data_agenda'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'erro': 'Formato de data inválido. Use YYYY-MM-DD'}), 400
            
            # Criar novo agendamento
            agendamento = Agenda(
                paciente_id=dados['paciente_id'],
                data_agenda=data_agenda,
                observacoes=dados.get('observacoes', '')
            )
            
            # Salvar no banco de dados
            db.session.add(agendamento)
            db.session.commit()
            
            logging.info(f"API: Novo agendamento criado para paciente {paciente.nome} em {dados['data_agenda']}")
            return jsonify({'status': 'Consulta agendada com sucesso'})
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao agendar consulta: {str(e)}")
            return jsonify({'erro': 'Erro interno do servidor'}), 500

# Rota para criar prontuário
@app.route('/prontuario', methods=['POST'])
def criar_prontuario_api():
    try:
        # Obter dados do corpo da requisição
        dados = request.json
        
        # Validar dados
        if not dados or 'paciente_id' not in dados:
            return jsonify({'erro': 'Dados incompletos. Forneça pelo menos paciente_id'}), 400
        
        # Verificar se o paciente existe
        paciente = Paciente.query.get(dados['paciente_id'])
        if not paciente:
            return jsonify({'erro': 'Paciente não encontrado'}), 404
        
        # Processar anexos se existirem
        anexos_str = ""
        if 'anexos' in dados and dados['anexos']:
            anexos_lista = []
            for anexo in dados['anexos']:
                if 'descricao' in anexo and 'link' in anexo:
                    anexos_lista.append(f"{anexo['descricao']}: {anexo['link']}")
            anexos_str = "\n".join(anexos_lista)
        
        # Processar prescrição se existir
        prescricao_str = ""
        if 'prescricao' in dados and dados['prescricao']:
            if isinstance(dados['prescricao'], list):
                prescricao_str = "\n".join(dados['prescricao'])
            else:
                prescricao_str = dados['prescricao']
        
        # Criar novo prontuário
        prontuario = Prontuario(
            paciente_id=dados['paciente_id'],
            data_consulta=datetime.date.today(),
            diagnostico=dados.get('diagnostico', ''),
            procedimento=dados.get('procedimento', ''),
            prescricao=prescricao_str,
            recomendacoes=dados.get('recomendacoes', ''),
            anexos=anexos_str
        )
        
        # Salvar no banco de dados
        db.session.add(prontuario)
        db.session.commit()
        
        logging.info(f"API: Novo prontuário criado para paciente {paciente.nome}")
        return jsonify({'status': 'Prontuário criado com sucesso'})
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar prontuário: {str(e)}")
        return jsonify({'erro': 'Erro interno do servidor'}), 500

@app.route('/paciente', methods=['POST'])
def criar_paciente_api():
    try:
        # Obter dados do corpo da requisição
        dados = request.json
        
        # Validar apenas o nome como obrigatório
        if not dados or 'nome' not in dados or not dados['nome']:
            return jsonify({'erro': 'O campo nome é obrigatório.'}), 400
        
        # Verificar se já existe um paciente com o mesmo nome
        paciente_existente = Paciente.query.filter(Paciente.nome == dados['nome']).first()
        if paciente_existente:
            # Se já existe, atualiza os dados em vez de criar um novo
            if 'idade' in dados and dados['idade']:
                try:
                    paciente_existente.idade = int(dados['idade'])
                except (ValueError, TypeError):
                    pass  # Ignora se não for possível converter
            
            if 'sexo' in dados and dados['sexo']:
                paciente_existente.sexo = dados['sexo']
            
            if 'telefone' in dados and dados['telefone']:
                paciente_existente.telefone = dados['telefone']
            
            # Salvar alterações
            db.session.commit()
            
            logging.info(f"API: Paciente existente atualizado: {paciente_existente.nome} (ID: {paciente_existente.id})")
            return jsonify({
                'id': paciente_existente.id,
                'status': 'Paciente atualizado com sucesso',
                'acao': 'atualizado'
            })
        
        # Se não existe, cria um novo paciente
        # Converter idade para inteiro se fornecida
        idade_int = None
        if 'idade' in dados and dados['idade']:
            try:
                idade_int = int(dados['idade'])
            except (ValueError, TypeError):
                idade_int = 0  # Valor padrão se não for possível converter
        
        # Criar novo paciente
        novo_paciente = Paciente(
            nome=dados['nome'],
            idade=idade_int,
            sexo=dados.get('sexo', '-'),  # Valor padrão se não fornecido
            telefone=dados.get('telefone', '-')  # Valor padrão se não fornecido
        )
        
        # Salvar no banco de dados
        db.session.add(novo_paciente)
        db.session.commit()
        
        # Registrar no log
        logging.info(f"API: Novo paciente cadastrado: {dados['nome']}")
        
        return jsonify({
            'id': novo_paciente.id,
            'status': 'Paciente cadastrado com sucesso',
            'acao': 'criado'
        })
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao cadastrar/atualizar paciente via API: {str(e)}")
        return jsonify({'erro': f"Erro ao processar: {str(e)}"}), 500

@app.route('/paciente/atualizar', methods=['PUT', 'POST'])
def atualizar_paciente_api():
    try:
        # Obter dados do corpo da requisição
        dados = request.json
        
        # Validar dados
        if not dados or 'nome' not in dados or not dados['nome']:
            return jsonify({'erro': 'O campo nome é obrigatório.'}), 400
        
        # Buscar paciente pelo nome (exato)
        paciente = Paciente.query.filter(Paciente.nome == dados['nome']).first()
        
        # Se não encontrar com nome exato, tenta buscar por nome similar
        if not paciente:
            pacientes_similares = Paciente.query.filter(Paciente.nome.like(f"%{dados['nome']}%")).all()
            if pacientes_similares:
                # Se encontrar apenas um paciente similar, usa ele
                if len(pacientes_similares) == 1:
                    paciente = pacientes_similares[0]
                else:
                    # Se encontrar múltiplos, retorna erro com lista de pacientes encontrados
                    return jsonify({
                        'erro': 'Múltiplos pacientes encontrados com nome similar',
                        'pacientes': [{'id': p.id, 'nome': p.nome} for p in pacientes_similares]
                    }), 409  # Conflict
        
        # Se não encontrou nenhum paciente, cria um novo
        if not paciente:
            # Converter idade para inteiro se fornecida
            idade_int = None
            if 'idade' in dados and dados['idade']:
                try:
                    idade_int = int(dados['idade'])
                except (ValueError, TypeError):
                    idade_int = 0
            
            # Criar novo paciente
            paciente = Paciente(
                nome=dados['nome'],
                idade=idade_int,
                sexo=dados.get('sexo', '-'),
                telefone=dados.get('telefone', '-')
            )
            db.session.add(paciente)
            db.session.commit()
            
            logging.info(f"API: Novo paciente cadastrado: {dados['nome']}")
            return jsonify({
                'id': paciente.id,
                'status': 'Paciente cadastrado com sucesso',
                'acao': 'criado'
            })
        
        # Atualizar dados do paciente existente
        if 'idade' in dados and dados['idade']:
            try:
                paciente.idade = int(dados['idade'])
            except (ValueError, TypeError):
                pass  # Ignora se não for possível converter
        
        if 'sexo' in dados and dados['sexo']:
            paciente.sexo = dados['sexo']
        
        if 'telefone' in dados and dados['telefone']:
            paciente.telefone = dados['telefone']
        
        # Salvar alterações
        db.session.commit()
        
        logging.info(f"API: Paciente atualizado: {paciente.nome} (ID: {paciente.id})")
        return jsonify({
            'id': paciente.id,
            'status': 'Paciente atualizado com sucesso',
            'acao': 'atualizado'
        })
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao atualizar paciente via API: {str(e)}")
        return jsonify({'erro': f"Erro ao atualizar: {str(e)}"}), 500

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
