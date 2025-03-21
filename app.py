from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
import logging

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prontuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuração de logs
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

@app.before_request
def log_request_info():
    logging.info(f"[REQUEST] {request.method} {request.path} | Params: {request.args} | JSON: {request.get_json(silent=True)}")

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

# ROTAS DE API E WEB
@app.route('/api/paciente/nome/<string:nome>')
def api_paciente_nome(nome):
    pacientes = Paciente.query.filter(Paciente.nome.ilike(f"%{nome}%")).all()
    if not pacientes:
        return jsonify({'error': 'Paciente não encontrado'}), 404
    resultado = []
    for paciente in pacientes:
        prontuarios = []
        for pront in paciente.prontuarios:
            prontuarios.append({
                "data_consulta": pront.data_consulta.strftime('%Y-%m-%d'),
                "diagnostico": pront.diagnostico,
                "procedimento": pront.procedimento,
                "prescricao": pront.prescricao,
                "recomendacoes": pront.recomendacoes,
                "anexos": pront.anexos
            })
        resultado.append({
            "id": paciente.id,
            "nome": paciente.nome,
            "idade": paciente.idade,
            "sexo": paciente.sexo,
            "telefone": paciente.telefone,
            "prontuarios": prontuarios
        })
    return jsonify(resultado)

@app.route('/api/pacientes')
def api_listar_pacientes():
    sexo = request.args.get('sexo')
    idade = request.args.get('idade')
    query = Paciente.query
    if sexo:
        query = query.filter(Paciente.sexo.ilike(f"%{sexo}%"))
    if idade:
        query = query.filter(Paciente.idade == int(idade))
    pacientes = query.all()
    resultado = []
    for paciente in pacientes:
        resultado.append({
            "id": paciente.id,
            "nome": paciente.nome,
            "idade": paciente.idade,
            "sexo": paciente.sexo,
            "telefone": paciente.telefone
        })
    return jsonify(resultado)

@app.route('/api/prontuario', methods=['POST'])
def api_prontuario():
    data = request.json
    paciente = Paciente.query.get(data['paciente_id'])
    if not paciente:
        return jsonify({'error': 'Paciente não encontrado'}), 404
    pront = Prontuario(
        paciente_id=paciente.id,
        data_consulta=datetime.date.today(),
        diagnostico=data.get('diagnostico'),
        procedimento=data.get('procedimento'),
        prescricao="\n".join(data.get('prescricao', [])),
        recomendacoes=data.get('recomendacoes'),
        anexos="\n".join([anexo['link'] for anexo in data.get('anexos', [])])
    )
    db.session.add(pront)
    db.session.commit()
    logging.info('Prontuário criado com sucesso.')
    return jsonify({'status': 'Prontuário salvo com sucesso'})

@app.route('/api/agenda', methods=['POST'])
def api_agendar():
    data = request.json
    paciente = Paciente.query.get(data['paciente_id'])
    if not paciente:
        return jsonify({'error': 'Paciente não encontrado'}), 404
    nova_agenda = Agenda(
        paciente_id=paciente.id,
        data_agenda=datetime.datetime.strptime(data['data_agenda'], "%Y-%m-%d").date(),
        observacoes=data.get('observacoes', '')
    )
    db.session.add(nova_agenda)
    db.session.commit()
    logging.info('Consulta agendada com sucesso.')
    return jsonify({'status': 'Consulta agendada com sucesso'})

@app.route('/api/agenda')
def api_agenda():
    data = request.args.get('data')
    data_dt = datetime.datetime.strptime(data, "%Y-%m-%d").date()
    consultas = Agenda.query.filter_by(data_agenda=data_dt).all()
    resultado = []
    for consulta in consultas:
        paciente = Paciente.query.get(consulta.paciente_id)
        resultado.append({
            "paciente": paciente.nome,
            "data_agenda": consulta.data_agenda.strftime('%Y-%m-%d'),
            "observacoes": consulta.observacoes
        })
    return jsonify(resultado)

# Interface web básica
@app.route('/')
def index():
    pacientes = Paciente.query.all()
    return render_template('index.html', pacientes=pacientes)

@app.route('/privacy')
def privacy_policy():
    return send_from_directory(os.path.dirname(__file__), 'privacy.html', mimetype='text/html')

@app.route('/admin/logs')
def view_logs():
    try:
        with open('app.log', 'r') as log_file:
            content = log_file.read()
        return f"<pre>{content}</pre>"
    except FileNotFoundError:
        return "<p>Arquivo de log ainda não foi criado.</p>"

@app.route('/.well-known/ai-plugin.json')
def serve_manifest():
    return send_from_directory(os.path.dirname(__file__), 'ai-plugin.json', mimetype='application/json')

@app.route('/openapi.yaml')
def serve_openapi():
    return send_from_directory(os.path.dirname(__file__), 'openapi.yaml', mimetype='text/yaml')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
