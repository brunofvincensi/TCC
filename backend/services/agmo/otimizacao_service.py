from flask import current_app
from typing import Dict, List, Tuple, Optional
import logging

from .agmo_service import Nsga2OtimizacaoService
from .config import AGMOConfig

logger = logging.getLogger(__name__)


class OtimizacaoService:
    """Serviço de interface entre API e AGMO para otimização de carteiras."""

    @staticmethod
    def otimizar_carteira(parametros: dict) -> Tuple[Optional[List[Dict]], str]:
        """Otimiza carteira usando R-NSGA2 com parâmetros fornecidos pela API."""
        try:
            perfil_risco = parametros.get('perfil_risco', 'moderado').lower()
            if perfil_risco not in ['conservador', 'moderado', 'arrojado']:
                return None, f"Perfil de risco inválido: '{perfil_risco}'"

            horizonte_tempo = parametros.get('horizonte_tempo')
            if not horizonte_tempo or not isinstance(horizonte_tempo, (int, float)):
                return None, "Horizonte de tempo inválido"

            prazo_anos = int(horizonte_tempo)
            if not AGMOConfig.validate_prazo(prazo_anos):
                return None, f"Horizonte de tempo inválido: {prazo_anos} anos. Use entre {AGMOConfig.PRAZO_MIN_ANOS} e {AGMOConfig.PRAZO_MAX_ANOS}."

            ids_ativos_restringidos = parametros.get('restricoes_ativos', [])
            if not isinstance(ids_ativos_restringidos, list):
                ids_ativos_restringidos = []

            max_ativos = parametros.get('max_ativos')
            if max_ativos is not None:
                try:
                    max_ativos = int(max_ativos)
                    if max_ativos < AGMOConfig.MIN_ATIVOS:
                        return None, f"Máx. ativos ({max_ativos}) < mínimo ({AGMOConfig.MIN_ATIVOS})"
                except (ValueError, TypeError):
                    return None, f"Número máximo de ativos inválido: {max_ativos}"

            use_optimal_config = parametros.get('use_optimal_config', True)
            population_size = parametros.get('population_size')
            generations = parametros.get('generations')
            ids_ativos = None

            service = Nsga2OtimizacaoService(
                app=current_app._get_current_object(),
                ids_ativos_restringidos=ids_ativos_restringidos,
                nivel_risco=perfil_risco,
                prazo_anos=prazo_anos,
                data_referencia=None,
                data_inicio=None,
                ids_ativos=ids_ativos
            )

            resultado = service.otimizar(
                population_size=population_size,
                generations=generations,
                use_optimal_config=use_optimal_config,
                max_ativos=max_ativos
            )

            composicao = resultado['composicao']
            metricas = resultado['metricas']

            mensagem = (
                f"Carteira otimizada: {len(composicao)} ativos. "
                f"Retorno: {metricas['retorno_esperado_anual']*100:.2f}% a.a. | "
                f"Volatilidade: {metricas['volatilidade_anual']*100:.2f}% a.a. | "
                f"Sharpe: {metricas['sharpe_ratio']:.2f}"
            )

            return composicao, mensagem

        except ValueError as ve:
            logger.error(f"Erro de validação: {ve}")
            return None, f"Erro: {str(ve)}"

        except Exception as e:
            logger.exception("Erro inesperado")
            return None, f"Erro inesperado: {str(e)}"
