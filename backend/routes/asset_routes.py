from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from models import db, Asset

ativo_bp = Blueprint('ativos', __name__)


# Rota para criar um novo ativo (ex: para popular o banco)
@ativo_bp.route('/ativos', methods=['POST'])
@jwt_required()
def create_asset():
    data = request.get_json()
    if not data or not data.get('ticker') or not data.get('nome') or not data.get('tipo'):
        return jsonify({'erro': 'Ticker, nome e tipo são obrigatórios'}), 400

    if Asset.query.filter_by(ticker=data['ticker']).first():
        return jsonify({'erro': 'Ticker já cadastrado'}), 409

    new_asset = Asset(
        ticker=data['ticker'],
        name=data['nome'],
        type=data['tipo'],
        sector=data.get('setor')
    )

    db.session.add(new_asset)
    db.session.commit()

    return jsonify({
        'mensagem': 'Ativo criado com sucesso',
        'ativo': new_asset.to_dict()
    }), 201


# Rota para listar todos os ativos disponíveis
@ativo_bp.route('/ativos', methods=['GET'])
@jwt_required()
def list_assets():
    assets = Asset.query.all()
    return jsonify([asset.to_dict() for asset in assets]), 200
