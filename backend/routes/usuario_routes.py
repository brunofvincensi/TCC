from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Usuario

usuario_bp = Blueprint('usuarios', __name__)

@usuario_bp.route('/usuarios', methods=['POST'])
def criar_usuario():
    """CREATE - Criar novo usuário"""
    data = request.get_json()

    # Validações
    if not data or not data.get('nome') or not data.get('email') or not data.get('senha'):
        return jsonify({'erro': 'Nome, email e senha são obrigatórios'}), 400

    # Verificar se email já existe
    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({'erro': 'Email já cadastrado'}), 409

    # Criar novo usuário
    usuario = Usuario(
        nome=data['nome'],
        email=data['email']
    )
    usuario.set_password(data['senha'])

    try:
        db.session.add(usuario)
        db.session.commit()
        return jsonify({
            'mensagem': 'Usuário criado com sucesso',
            'usuario': usuario.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500


@usuario_bp.route('/usuarios', methods=['GET'])
@jwt_required()
def listar_usuarios():
    """READ - Listar todos os usuários"""
    usuarios = Usuario.query.all()
    return jsonify({
        'usuarios': [u.to_dict() for u in usuarios]
    }), 200


@usuario_bp.route('/usuarios/<int:id>', methods=['GET'])
@jwt_required()
def buscar_usuario(id):
    """READ - Buscar usuário por ID"""
    usuario = Usuario.query.get(id)

    if not usuario:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    return jsonify(usuario.to_dict()), 200


@usuario_bp.route('/usuarios', methods=['PUT'])
@jwt_required()
def atualizar_usuario():
    """UPDATE - Atualizar usuário"""
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)

    if not usuario:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    data = request.get_json()

    # Atualizar campos
    if 'nome' in data:
        usuario.nome = data['nome']

    if 'email' in data:
        # Verificar se o novo email já existe em outro usuário
        email_existe = Usuario.query.filter(
            Usuario.email == data['email'],
            Usuario.id != usuario_id
        ).first()

        if email_existe:
            return jsonify({'erro': 'Email já cadastrado'}), 409

        usuario.email = data['email']

    if 'senha' in data:
        usuario.set_password(data['senha'])

    if 'ativo' in data:
        usuario.ativo = data['ativo']

    try:
        db.session.commit()
        return jsonify({
            'mensagem': 'Usuário atualizado com sucesso',
            'usuario': usuario.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500


@usuario_bp.route('/usuarios', methods=['DELETE'])
@jwt_required()
def deletar_usuario():
    """DELETE - Deletar usuário"""
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)

    if not usuario:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    try:
        db.session.delete(usuario)
        db.session.commit()
        return jsonify({'mensagem': 'Usuário deletado com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500