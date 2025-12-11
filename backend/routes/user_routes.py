from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User

usuario_bp = Blueprint('usuarios', __name__)

@usuario_bp.route('/usuarios', methods=['POST'])
def create_user():
    """CREATE - Criar novo usuário"""
    data = request.get_json()

    # Validações
    if not data or not data.get('nome') or not data.get('email') or not data.get('senha'):
        return jsonify({'erro': 'Nome, email e senha são obrigatórios'}), 400

    # Verificar se email já existe
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'erro': 'Email já cadastrado'}), 409

    # Criar novo usuário
    user = User(
        name=data['nome'],
        email=data['email']
    )
    user.set_password(data['senha'])

    try:
        db.session.add(user)
        db.session.commit()
        return jsonify({
            'mensagem': 'Usuário criado com sucesso',
            'usuario': user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500


@usuario_bp.route('/usuarios', methods=['GET'])
@jwt_required()
def list_users():
    """READ - Listar todos os usuários"""
    users = User.query.all()
    return jsonify({
        'usuarios': [u.to_dict() for u in users]
    }), 200


@usuario_bp.route('/usuarios/<int:id>', methods=['GET'])
@jwt_required()
def get_user(id):
    """READ - Buscar usuário por ID"""
    user = User.query.get(id)

    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    return jsonify(user.to_dict()), 200


@usuario_bp.route('/usuarios', methods=['PUT'])
@jwt_required()
def update_user():
    """UPDATE - Atualizar usuário"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    data = request.get_json()

    # Atualizar campos
    if 'nome' in data:
        user.name = data['nome']

    if 'email' in data:
        # Verificar se o novo email já existe em outro usuário
        email_exists = User.query.filter(
            User.email == data['email'],
            User.id != user_id
        ).first()

        if email_exists:
            return jsonify({'erro': 'Email já cadastrado'}), 409

        user.email = data['email']

    if 'senha' in data:
        user.set_password(data['senha'])

    if 'ativo' in data:
        user.active = data['ativo']

    try:
        db.session.commit()
        return jsonify({
            'mensagem': 'Usuário atualizado com sucesso',
            'usuario': user.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500


@usuario_bp.route('/usuarios', methods=['DELETE'])
@jwt_required()
def delete_user():
    """DELETE - Deletar usuário"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'mensagem': 'Usuário deletado com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500
