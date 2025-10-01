from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.auth_service import AuthService
from models.usuario import Usuario

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Endpoint de login"""
    data = request.get_json()

    email = data.get('email') if data else None
    senha = data.get('senha') if data else None

    token, resultado = AuthService.login(email, senha)

    if token:
        return jsonify({
            'token': token,
            'usuario': resultado
        }), 200
    else:
        return jsonify({'erro': resultado}), 401


@auth_bp.route('/perfil', methods=['GET'])
@jwt_required()
def perfil():
    """Retorna o perfil do usuário logado"""
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)

    if not usuario:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    return jsonify(usuario.to_dict()), 200