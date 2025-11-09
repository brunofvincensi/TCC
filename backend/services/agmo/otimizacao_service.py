"""
Serviço de Otimização de Carteiras - Interface para API

Este módulo fornece a interface entre as rotas da API e o serviço de otimização
AGMO (Algoritmo Genético Multiobjetivo). Ele mapeia os parâmetros da requisição
HTTP para os parâmetros esperados pelo Nsga2OtimizacaoService.

Autor: Sistema de Otimização de Portfólio - TCC
"""

from flask import current_app
from typing import Dict, List, Tuple, Optional
import logging

from .agmo_service import Nsga2OtimizacaoService, MIN_ATIVOS

logger = logging.getLogger(__name__)


class OtimizacaoService:
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
    def otimizar_carteira(parametros: dict) -> Tuple[Optional[List[Dict]], str]:
        """
        Otimiza uma carteira de investimentos usando AGMO (NSGA-II).

        Args:
            parametros: Dicionário com parâmetros de otimização:
                - perfil_risco (str): 'conservador', 'moderado' ou 'arrojado'
                - horizonte_tempo (int): Prazo de investimento em anos
                - capital (float): Capital disponível (opcional, não usado na otimização)
                - objetivos (list): Lista de objetivos (opcional)
                - restricoes_ativos (list): Lista de IDs de ativos a serem excluídos
                - max_ativos (int, opcional): Número máximo de ativos na carteira
                - use_optimal_config (bool, opcional): Se deve usar configuração ótima do banco
                - population_size (int, opcional): Tamanho da população do AG
                - generations (int, opcional): Número de gerações do AG

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
            logger.debug(f"Parâmetros recebidos: {parametros}")
            logger.debug(f"Número de ativos disponíveis: {len(ativos_disponiveis)}")

            # Valida perfil de risco
            perfil_risco = parametros.get('perfil_risco', 'moderado').lower()
            if perfil_risco not in ['conservador', 'moderado', 'arrojado']:
                return None, (
                    f"Perfil de risco inválido: '{perfil_risco}'. "
                    f"Use 'conservador', 'moderado' ou 'arrojado'."
                )

            # Valida horizonte de tempo
            horizonte_tempo = parametros.get('horizonte_tempo')
            if not horizonte_tempo or not isinstance(horizonte_tempo, (int, float)):
                return None, "Horizonte de tempo inválido. Informe o prazo em anos (número)."

            prazo_anos = int(horizonte_tempo)
            if prazo_anos < 1 or prazo_anos > 30:
                return None, f"Horizonte de tempo inválido: {prazo_anos} anos. Use valores entre 1 e 30 anos."

            # ========== 2. MAPEAMENTO DE PARÂMETROS ==========

            # IDs de ativos restringidos (a serem excluídos da otimização)
            ids_ativos_restringidos = parametros.get('restricoes_ativos', [])
            if not isinstance(ids_ativos_restringidos, list):
                ids_ativos_restringidos = []

            logger.info(f"Ativos restringidos (excluídos): {ids_ativos_restringidos}")

            # Número máximo de ativos na carteira (restrição de cardinalidade)
            max_ativos = parametros.get('max_ativos')
            if max_ativos is not None:
                try:
                    max_ativos = int(max_ativos)
                    if max_ativos < MIN_ATIVOS:
                        return None, (
                            f"Número máximo de ativos ({max_ativos}) não pode ser menor que "
                            f"o mínimo necessário ({MIN_ATIVOS})."
                        )
                except (ValueError, TypeError):
                    return None, f"Número máximo de ativos inválido: {max_ativos}"

            # Hiperparâmetros opcionais do algoritmo genético
            use_optimal_config = parametros.get('use_optimal_config', True)
            population_size = parametros.get('population_size')  # None = auto
            generations = parametros.get('generations')  # None = auto

            # Extrai IDs dos ativos disponíveis (para passar ao serviço AGMO)
            # Nota: O AGMO vai buscar todos os ativos do tipo ACAO automaticamente,
            # mas podemos passar uma lista específica se necessário
            ids_ativos = None  # None = usar todos os ativos disponíveis do tipo ACAO

            # ========== 3. EXECUÇÃO DA OTIMIZAÇÃO ==========
            logger.info("=" * 70)
            logger.info("INICIANDO OTIMIZAÇÃO AGMO (NSGA-II)")
            logger.info("=" * 70)
            logger.info(f"  Perfil de risco: {perfil_risco}")
            logger.info(f"  Horizonte: {prazo_anos} anos")
            logger.info(f"  Ativos restringidos: {len(ids_ativos_restringidos)}")
            if max_ativos:
                logger.info(f"  Máx. ativos na carteira: {max_ativos}")
            logger.info("=" * 70)

            # Cria instância do serviço AGMO
            service = Nsga2OtimizacaoService(
                app=current_app._get_current_object(),  # Instância Flask
                ids_ativos_restringidos=ids_ativos_restringidos,
                nivel_risco=perfil_risco,
                prazo_anos=prazo_anos,
                data_referencia=None,  # Para backtest, usar parâmetro específico
                data_inicio=None,
                ids_ativos=ids_ativos
            )

            # Executa otimização
            resultado = service.otimizar(
                population_size=population_size,
                generations=generations,
                use_optimal_config=use_optimal_config,
                max_ativos=max_ativos
            )

            # ========== 4. FORMATAÇÃO DO RESULTADO ==========
            composicao = resultado['composicao']
            metricas = resultado['metricas']

            logger.info("=" * 70)
            logger.info("OTIMIZAÇÃO CONCLUÍDA COM SUCESSO")
            logger.info("=" * 70)
            logger.info(f"  Carteira com {len(composicao)} ativos")
            logger.info(f"  Retorno esperado anual: {metricas['retorno_esperado_anual']*100:.2f}%")
            logger.info(f"  Volatilidade anual: {metricas['volatilidade_anual']*100:.2f}%")
            logger.info(f"  Índice de Sharpe: {metricas['sharpe_ratio']:.2f}")
            logger.info("=" * 70)

            # Formata mensagem de sucesso
            mensagem = (
                f"Carteira otimizada com sucesso! "
                f"{len(composicao)} ativos selecionados. "
                f"Retorno esperado: {metricas['retorno_esperado_anual']*100:.2f}% a.a. | "
                f"Volatilidade: {metricas['volatilidade_anual']*100:.2f}% a.a. | "
                f"Sharpe: {metricas['sharpe_ratio']:.2f}"
            )

            return composicao, mensagem

        except ValueError as ve:
            # Erros de validação ou negócio
            logger.error(f"Erro de validação na otimização: {ve}")
            return None, f"Erro na otimização: {str(ve)}"

        except Exception as e:
            # Erros inesperados
            logger.exception("Erro inesperado durante a otimização")
            return None, f"Erro inesperado durante a otimização: {str(e)}"
