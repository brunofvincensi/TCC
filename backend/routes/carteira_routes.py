from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.ativo import Ativo
from services.agmo.otimizacao_service import OtimizacaoService
from models import db, Carteira, ParametrosOtimizacao, CarteiraAtivo, ParametrosRestricaoAtivo

carteira_bp = Blueprint('carteiras', __name__)


@carteira_bp.route('/carteiras/otimizar', methods=['POST'])
@jwt_required()
def optimize_and_create_portfolio():
    user_id = get_jwt_identity()
    data = request.get_json()

    parameters = data.get('parametros')
    portfolio_info = data.get('info_carteira')
    if not parameters or not portfolio_info or not portfolio_info.get('nome'):
        return jsonify({'erro': 'A estrutura da requisição é inválida. Forneça `parametros` e `info_carteira`.'}), 400

    optimized_composition, message = OtimizacaoService.optimize_portfolio(parameters)

    if not optimized_composition:
        return jsonify({'erro': message}), 500

    try:
        new_portfolio = Carteira(
            id_usuario=user_id,
            nome=portfolio_info['nome'],
            descricao=portfolio_info.get('descricao')
        )

        new_parameters = ParametrosOtimizacao(
            carteira=new_portfolio,
            perfil_risco_usado=parameters.get('perfil_risco'),
            horizonte_tempo_usado=parameters.get('horizonte_tempo'),
            capital_usado=parameters.get('capital'),
            objetivos_usados=parameters.get('objetivos')
        )

        # Salvar as restrições
        restricted_ids = parameters.get('restricoes_ativos', [])
        if restricted_ids:
            # Validação: Garante que todos os IDs fornecidos realmente existem no banco.
            restricted_assets = Ativo.query.filter(Ativo.id.in_(restricted_ids)).all()
            if len(restricted_assets) != len(restricted_ids):
                return jsonify({'erro': 'Um ou mais IDs de ativos para restrição são inválidos.'}), 400

            # Cria as associações
            for asset_obj in restricted_assets:
                restriction = ParametrosRestricaoAtivo(
                    parametros=new_parameters,  # Associa ao objeto de parâmetros
                    ativo=asset_obj  # Associa ao objeto do ativo
                )
                db.session.add(restriction)

        # Adiciona a carteira e os parâmetros à sessão. As restrições serão adicionadas por cascata.
        db.session.add(new_portfolio)
        db.session.add(new_parameters)

        # Adiciona a composição (ativos e pesos) - precisa ser feito após o commit inicial
        # para que nova_carteira.id esteja disponível.
        db.session.flush()  # Garante que nova_carteira.id seja gerado

        for item in optimized_composition:
            association = CarteiraAtivo(
                id_carteira=new_portfolio.id,
                id_ativo=item['id_ativo'],
                peso=item['peso']
            )
            db.session.add(association)

        db.session.commit()

        return jsonify({
            'mensagem': 'Carteira otimizada e salva com sucesso!',
            'carteira': new_portfolio.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao salvar a carteira: {str(e)}'}), 500


@carteira_bp.route('/carteiras', methods=['GET'])
@jwt_required()
def list_user_portfolios():
    """Lista todas as carteiras do usuário logado."""
    user_id = get_jwt_identity()
    portfolios = Carteira.query.filter_by(id_usuario=user_id).all()
    return jsonify([{"nome": c.nome, "id": c.id} for c in portfolios]), 200


@carteira_bp.route('/carteiras/<int:id_carteira>', methods=['GET'])
@jwt_required()
def get_portfolio(id_carteira):
    """Busca uma carteira específica pelo ID."""
    user_id = get_jwt_identity()
    portfolio = Carteira.query.filter_by(id=id_carteira, id_usuario=user_id).first()

    if not portfolio:
        return jsonify({'erro': 'Carteira não encontrada ou não pertence a este usuário'}), 404

    return jsonify(portfolio.to_dict()), 200


@carteira_bp.route('/carteiras/<int:id_carteira>', methods=['DELETE'])
@jwt_required()
def delete_portfolio(id_carteira):
    """Deleta uma carteira específica."""
    user_id = get_jwt_identity()
    portfolio = Carteira.query.filter_by(id=id_carteira, id_usuario=user_id).first()

    if not portfolio:
        return jsonify({'erro': 'Carteira não encontrada ou não pertence a este usuário'}), 404

    try:
        db.session.delete(portfolio)
        db.session.commit()
        return jsonify({'mensagem': 'Carteira deletada com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao deletar carteira: {str(e)}'}), 500