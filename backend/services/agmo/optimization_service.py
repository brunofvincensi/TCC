"""
Serviço de Otimização de Carteiras - Interface para API

Este módulo fornece a interface entre as rotas da API e o serviço de otimização
AGMO (Algoritmo Genético Multiobjetivo). Ele mapeia os parâmetros da requisição
HTTP para os parâmetros esperados pelo Nsga2OtimizacaoService (R-NSGA2).

R-NSGA2 permite guiar a busca durante a otimização usando pontos de referência
customizados por perfil de risco, diferente do NSGA2 tradicional.

Autor: Sistema de Otimização de Portfólio - TCC
"""

from flask import current_app
from typing import Dict, List, Tuple, Optional
import logging

from .agmo_service import Nsga2OtimizacaoService, MIN_ASSETS

logger = logging.getLogger(__name__)


class OptimizationService:
    """
    Serviço de otimização de carteiras que integra com o AGMO.

    Este serviço serve como camada de abstração entre a API REST e o
    serviço de otimização AGMO, realizando:
    - Validação de parâmetros
    - Mapeamento de parâmetros da API para o AGMO
    - Tratamento de erros
    - Formatação de resultados
    """

    @staticmethod
    def optimize_portfolio(parameters: dict) -> Tuple[Optional[List[Dict]], str]:
        """
        Otimiza uma carteira de investimentos usando AGMO (R-NSGA2).

        R-NSGA2 usa pontos de referência para guiar a busca durante a otimização,
        direcionando as soluções para regiões específicas da fronteira de Pareto
        baseadas no perfil de risco do usuário.

        Args:
            parametros: Dicionário com parâmetros de otimização:
                - perfil_risco (str): 'conservador', 'moderado' ou 'arrojado'
                - horizonte_tempo (int): Prazo de investimento em anos
                - capital (float): Capital disponível (opcional, não usado na otimização)
                - objetivos (list): Lista de objetivos (opcional)
                - restricoes_ativos (list): Lista de IDs de ativos a serem excluídos
                - max_ativos (int, opcional): Número máximo de ativos na carteira

        Returns:
            Tupla contendo:
            - Lista de dicionários com composição da carteira (id_ativo, ticker, nome, peso)
              ou None em caso de erro
            - Mensagem de sucesso ou erro

        Raises:
            ValueError: Se os parâmetros forem inválidos
        """
        try:
            # ========== 1. VALIDAÇÃO DE PARÂMETROS ==========
            logger.info("Iniciando otimização de carteira")
            logger.debug(f"Parâmetros recebidos: {parameters}")

            # Valida perfil de risco
            risk_profile = parameters.get('perfil_risco', 'moderado').lower()
            if risk_profile not in ['conservador', 'moderado', 'arrojado']:
                return None, (
                    f"Perfil de risco inválido: '{risk_profile}'. "
                    f"Use 'conservador', 'moderado' ou 'arrojado'."
                )

            # Valida horizonte de tempo
            time_horizon = parameters.get('horizonte_tempo')
            if not time_horizon or not isinstance(time_horizon, (int, float)):
                return None, "Horizonte de tempo inválido. Informe o prazo em anos (número)."

            years_period = int(time_horizon)
            if years_period < 1 or years_period > 30:
                return None, f"Horizonte de tempo inválido: {years_period} anos. Use valores entre 1 e 30 anos."

            # ========== 2. MAPEAMENTO DE PARÂMETROS ==========

            # IDs de ativos restringidos (a serem excluídos da otimização)
            restricted_asset_ids = parameters.get('restricoes_ativos', [])
            if not isinstance(restricted_asset_ids, list):
                restricted_asset_ids = []

            logger.info(f"Ativos restringidos (excluídos): {restricted_asset_ids}")

            # Número máximo de ativos na carteira (restrição de cardinalidade)
            max_assets = parameters.get('max_ativos')
            if max_assets is not None:
                try:
                    max_assets = int(max_assets)
                    if max_assets < MIN_ASSETS:
                        return None, (
                            f"Número máximo de ativos ({max_assets}) não pode ser menor que "
                            f"o mínimo necessário ({MIN_ASSETS})."
                        )
                except (ValueError, TypeError):
                    return None, f"Número máximo de ativos inválido: {max_assets}"

            # Extrai IDs dos ativos disponíveis (para passar ao serviço AGMO)
            # Nota: O AGMO vai buscar todos os ativos do tipo ACAO automaticamente,
            # mas podemos passar uma lista específica se necessário
            asset_ids = None  # None = usar todos os ativos disponíveis do tipo ACAO

            # ========== 3. EXECUÇÃO DA OTIMIZAÇÃO ==========
            # Cria instância do serviço AGMO
            service = Nsga2OtimizacaoService(
                app=current_app._get_current_object(),
                restricted_asset_ids=restricted_asset_ids,
                risk_level=risk_profile,
                years_period=years_period,
                asset_ids=asset_ids
            )

            # Executa otimização
            result = service.optimize(
                use_optimal_config=True,
                max_assets=max_assets
            )

            # ========== 4. FORMATAÇÃO DO RESULTADO ==========
            composition = result['composicao']
            metrics = result['metricas']

            # Formata mensagem de sucesso
            message = (
                f"Carteira otimizada com sucesso! "
                f"{len(composition)} ativos selecionados. "
                f"Retorno esperado: {metrics['retorno_esperado_anual']*100:.2f}% a.a. | "
                f"Volatilidade: {metrics['volatilidade_anual']*100:.2f}% a.a. | "
                f"Sharpe: {metrics['sharpe_ratio']:.2f}"
            )

            return composition, message

        except ValueError as ve:
            # Erros de validação ou negócio
            logger.error(f"Erro de validação na otimização: {ve}")
            return None, f"Erro na otimização: {str(ve)}"

        except Exception as e:
            # Erros inesperados
            logger.exception("Erro inesperado durante a otimização")
            return None, f"Erro inesperado durante a otimização: {str(e)}"
