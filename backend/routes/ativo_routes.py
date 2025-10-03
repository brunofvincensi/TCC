from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from models import db, Ativo

ativo_bp = Blueprint('ativos', __name__)


# Rota para criar um novo ativo (ex: para popular o banco)
@ativo_bp.route('/ativos', methods=['POST'])
@jwt_required()
def criar_ativo():
    data = request.get_json()
    if not data or not data.get('ticker') or not data.get('nome') or not data.get('tipo'):
        return jsonify({'erro': 'Ticker, nome e tipo são obrigatórios'}), 400

    if Ativo.query.filter_by(ticker=data['ticker']).first():
        return jsonify({'erro': 'Ticker já cadastrado'}), 409

    novo_ativo = Ativo(
        ticker=data['ticker'],
        nome=data['nome'],
        tipo=data['tipo'],
        setor=data.get('setor'),
        moeda=data.get('moeda', 'BRL')
    )

    db.session.add(novo_ativo)
    db.session.commit()

    return jsonify({
        'mensagem': 'Ativo criado com sucesso',
        'ativo': novo_ativo.to_dict()
    }), 201


# Rota para listar todos os ativos disponíveis
@ativo_bp.route('/ativos', methods=['GET'])
@jwt_required()
def listar_ativos():
    ativos = Ativo.query.all()
    return jsonify([ativo.to_dict() for ativo in ativos]), 200