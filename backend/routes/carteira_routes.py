from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.ativo import Ativo
from services.otimizacao_service import OtimizacaoService
from models import db, Carteira, ParametrosOtimizacao, CarteiraAtivo, ParametrosRestricaoAtivo

carteira_bp = Blueprint('carteiras', __name__)


@carteira_bp.route('/carteiras/otimizar', methods=['POST'])
@jwt_required()
def otimizar_e_criar_carteira():
    usuario_id = get_jwt_identity()
    data = request.get_json()

    parametros = data.get('parametros')
    info_carteira = data.get('info_carteira')
    if not parametros or not info_carteira or not info_carteira.get('nome'):
        return jsonify({'erro': 'A estrutura da requisição é inválida. Forneça `parametros` e `info_carteira`.'}), 400

    ativos_disponiveis = Ativo.query.all()
    if not ativos_disponiveis:
        return jsonify({'erro': 'Não há ativos cadastrados no sistema para otimização.'}), 500

    ativos_dict = [ativo.to_dict() for ativo in ativos_disponiveis]

    composicao_otimizada, mensagem = OtimizacaoService.otimizar_carteira(parametros, ativos_dict)

    if not composicao_otimizada:
        return jsonify({'erro': mensagem}), 500

    try:
        nova_carteira = Carteira(
            id_usuario=usuario_id,
            nome=info_carteira['nome'],
            descricao=info_carteira.get('descricao')
        )

        novos_parametros = ParametrosOtimizacao(
            carteira=nova_carteira,
            perfil_risco_usado=parametros.get('perfil_risco'),
            horizonte_tempo_usado=parametros.get('horizonte_tempo'),
            capital_usado=parametros.get('capital'),
            objetivos_usados=parametros.get('objetivos')
        )

        # --- LÓGICA ATUALIZADA PARA SALVAR RESTRIÇÕES ---
        ids_restritos = parametros.get('restricoes_ativos', [])
        if ids_restritos:
            # Validação: Garante que todos os IDs fornecidos realmente existem no banco.
            ativos_restringidos = Ativo.query.filter(Ativo.id.in_(ids_restritos)).all()
            if len(ativos_restringidos) != len(ids_restritos):
                return jsonify({'erro': 'Um ou mais IDs de ativos para restrição são inválidos.'}), 400

            # Cria as associações
            for ativo_obj in ativos_restringidos:
                restricao = ParametrosRestricaoAtivo(
                    parametros=novos_parametros,  # Associa ao objeto de parâmetros
                    ativo=ativo_obj  # Associa ao objeto do ativo
                )
                db.session.add(restricao)

        # Adiciona a carteira e os parâmetros à sessão. As restrições serão adicionadas por cascata.
        db.session.add(nova_carteira)
        db.session.add(novos_parametros)

        # Adiciona a composição (ativos e pesos) - precisa ser feito após o commit inicial
        # para que nova_carteira.id esteja disponível.
        db.session.flush()  # Garante que nova_carteira.id seja gerado

        for item in composicao_otimizada:
            associacao = CarteiraAtivo(
                id_carteira=nova_carteira.id,
                id_ativo=item['id_ativo'],
                peso=item['peso']
            )
            db.session.add(associacao)

        db.session.commit()

        return jsonify({
            'mensagem': 'Carteira otimizada e salva com sucesso!',
            'carteira': nova_carteira.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao salvar a carteira: {str(e)}'}), 500


@carteira_bp.route('/carteiras', methods=['GET'])
@jwt_required()
def listar_carteiras_usuario():
    """Lista todas as carteiras do usuário logado."""
    usuario_id = get_jwt_identity()
    carteiras = Carteira.query.filter_by(id_usuario=usuario_id).all()
    return jsonify([{"nome": c.nome, "id": c.id} for c in carteiras]), 200


@carteira_bp.route('/carteiras/<int:id_carteira>', methods=['GET'])
@jwt_required()
def buscar_carteira(id_carteira):
    """Busca uma carteira específica pelo ID."""
    usuario_id = get_jwt_identity()
    carteira = Carteira.query.filter_by(id=id_carteira, id_usuario=usuario_id).first()

    if not carteira:
        return jsonify({'erro': 'Carteira não encontrada ou não pertence a este usuário'}), 404

    return jsonify(carteira.to_dict()), 200


@carteira_bp.route('/carteiras/<int:id_carteira>', methods=['DELETE'])
@jwt_required()
def deletar_carteira(id_carteira):
    """Deleta uma carteira específica."""
    usuario_id = get_jwt_identity()
    carteira = Carteira.query.filter_by(id=id_carteira, id_usuario=usuario_id).first()

    if not carteira:
        return jsonify({'erro': 'Carteira não encontrada ou não pertence a este usuário'}), 404

    try:
        db.session.delete(carteira)
        db.session.commit()
        return jsonify({'mensagem': 'Carteira deletada com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao deletar carteira: {str(e)}'}), 500