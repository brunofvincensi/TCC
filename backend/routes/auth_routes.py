from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.auth.auth_service import AuthService
from models import User
from extensions import limiter
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data = request.get_json()

    email = data.get('email') if data else None
    password = data.get('senha') if data else None

    token, result = AuthService.login(email, password)

    if token:
        return jsonify({
            'token': token,
            'usuario': result
        }), 200
    else:
        return jsonify({'erro': result}), 401


@auth_bp.route('/perfil', methods=['GET'])
@jwt_required()
def profile():
    """Retorna o perfil do usuário logado"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    return jsonify(user.to_dict()), 200
