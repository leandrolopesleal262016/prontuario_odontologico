from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prontuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

# ROTAS PRINCIPAIS
@app.route('/')
def index():
    pacientes = Paciente.query.all()
    return render_template('index.html', pacientes=pacientes)

@app.route('/paciente/<int:id>')
def prontuario(id):
    paciente = Paciente.query.get_or_404(id)
    return render_template('prontuario.html', paciente=paciente)

@app.route('/novo_paciente', methods=['POST'])
def novo_paciente():
    nome = request.form['nome']
    idade = request.form['idade']
    sexo = request.form['sexo']
    telefone = request.form['telefone']
    novo = Paciente(nome=nome, idade=idade, sexo=sexo, telefone=telefone)
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/paciente/<int:id>/novo_prontuario', methods=['POST'])
def novo_prontuario(id):
    paciente = Paciente.query.get_or_404(id)
    diagnostico = request.form['diagnostico']
    procedimento = request.form['procedimento']
    prescricao = request.form['prescricao']
    recomendacoes = request.form['recomendacoes']
    anexos = request.form['anexos']

    pront = Prontuario(
        paciente_id=paciente.id,
        data_consulta=datetime.date.today(),
        diagnostico=diagnostico,
        procedimento=procedimento,
        prescricao=prescricao,
        recomendacoes=recomendacoes,
        anexos=anexos
    )
    db.session.add(pront)
    db.session.commit()
    return redirect(url_for('prontuario', id=paciente.id))

# API PARA INTEGRAÇÃO COM GPT
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
    return jsonify({'status': 'Prontuário salvo com sucesso'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

#arquivo principal

