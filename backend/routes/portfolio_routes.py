from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.asset import Asset
from services.agmo.optimization_service import OptimizationService
from models import db, Portfolio, OptimizationParameters, PortfolioAsset, ParameterAssetRestriction

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

    optimized_composition, message = OptimizationService.optimize_portfolio(parameters)

    if not optimized_composition:
        return jsonify({'erro': message}), 500

    try:
        new_portfolio = Portfolio(
            user_id=user_id,
            name=portfolio_info['nome'],
            description=portfolio_info.get('descricao')
        )

        new_parameters = OptimizationParameters(
            portfolio=new_portfolio,
            risk_profile_used=parameters.get('perfil_risco'),
            time_horizon_used=parameters.get('horizonte_tempo'),
            capital_used=parameters.get('capital')
        )

        # Salvar as restrições
        restricted_ids = parameters.get('restricoes_ativos', [])
        if restricted_ids:
            # Validação: Garante que todos os IDs fornecidos realmente existem no banco.
            restricted_assets = Asset.query.filter(Asset.id.in_(restricted_ids)).all()
            if len(restricted_assets) != len(restricted_ids):
                return jsonify({'erro': 'Um ou mais IDs de ativos para restrição são inválidos.'}), 400

            # Cria as associações
            for asset_obj in restricted_assets:
                restriction = ParameterAssetRestriction(
                    parameters=new_parameters,  # Associate with parameters object
                    asset=asset_obj  # Associate with asset object
                )
                db.session.add(restriction)

        # Adiciona a carteira e os parâmetros à sessão. As restrições serão adicionadas por cascata.
        db.session.add(new_portfolio)
        db.session.add(new_parameters)

        # Adiciona a composição (ativos e pesos) - precisa ser feito após o commit inicial
        # para que nova_carteira.id esteja disponível.
        db.session.flush()  # Ensures that new_portfolio.id is generated

        # Obtém o capital usado para calcular o valor monetário de cada ativo
        capital_usado = parameters.get('capital')

        for item in optimized_composition:
            # Calcula o valor monetário alocado no ativo
            valor_monetario = float(capital_usado) * float(item['weight']) if capital_usado else None

            association = PortfolioAsset(
                portfolio_id=new_portfolio.id,
                asset_id=item['asset_id'],
                weight=item['weight'],
                monetary_value=valor_monetario
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
    portfolios = Portfolio.query.filter_by(user_id=user_id).all()
    return jsonify([{"nome": c.name, "id": c.id} for c in portfolios]), 200


@carteira_bp.route('/carteiras/<int:id_carteira>', methods=['GET'])
@jwt_required()
def get_portfolio(id_carteira):
    """Busca uma carteira específica pelo ID."""
    user_id = get_jwt_identity()
    portfolio = Portfolio.query.filter_by(id=id_carteira, user_id=user_id).first()

    if not portfolio:
        return jsonify({'erro': 'Carteira não encontrada ou não pertence a este usuário'}), 404

    return jsonify(portfolio.to_dict()), 200


@carteira_bp.route('/carteiras/<int:id_carteira>', methods=['DELETE'])
@jwt_required()
def delete_portfolio(id_carteira):
    """Deleta uma carteira específica."""
    user_id = get_jwt_identity()
    portfolio = Portfolio.query.filter_by(id=id_carteira, user_id=user_id).first()

    if not portfolio:
        return jsonify({'erro': 'Carteira não encontrada ou não pertence a este usuário'}), 404

    try:
        db.session.delete(portfolio)
        db.session.commit()
        return jsonify({'mensagem': 'Carteira deletada com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao deletar carteira: {str(e)}'}), 500
