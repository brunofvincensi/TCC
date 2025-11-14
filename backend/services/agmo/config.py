"""Configurações do sistema AGMO (Algoritmo Genético Multiobjetivo)."""

import os
from typing import Dict
import numpy as np


class AGMOConfig:
    """Configurações centralizadas para otimização de portfólio."""

    # Histórico e dados
    MINIMO_MESES_HISTORICO = int(os.getenv('AGMO_MIN_HISTORICO', '24'))
    MIN_ATIVOS = int(os.getenv('AGMO_MIN_ATIVOS', '5'))

    # Algoritmo genético
    DEFAULT_POPULATION_SIZE = int(os.getenv('AGMO_POPULATION_SIZE', '100'))
    DEFAULT_GENERATIONS = int(os.getenv('AGMO_GENERATIONS', '100'))

    # Operadores genéticos
    DEFAULT_CROSSOVER_ETA = float(os.getenv('AGMO_CROSSOVER_ETA', '10.0'))
    DEFAULT_MUTATION_ETA = float(os.getenv('AGMO_MUTATION_ETA', '10.0'))

    # Restrições de peso
    PESO_MIN_DEFAULT = float(os.getenv('AGMO_PESO_MIN', '0.01'))
    PESO_MAX_DEFAULT = float(os.getenv('AGMO_PESO_MAX', '0.30'))

    # CVaR
    ALPHA_CVAR = float(os.getenv('AGMO_ALPHA_CVAR', '0.05'))
    MIN_SAMPLES_CVAR = int(os.getenv('AGMO_MIN_SAMPLES_CVAR', '20'))

    # HHI (Herfindahl-Hirschman Index) por perfil
    HHI_THRESHOLDS: Dict[str, float] = {
        'conservador': float(os.getenv('AGMO_HHI_CONSERVADOR', '0.12')),
        'moderado': float(os.getenv('AGMO_HHI_MODERADO', '0.15')),
        'arrojado': float(os.getenv('AGMO_HHI_ARROJADO', '0.20'))
    }

    # Pesos para seleção de carteira por perfil [Retorno, Variância, CVaR]
    PESOS_SELECAO: Dict[str, np.ndarray] = {
        'conservador': np.array([0.2, 0.5, 0.3]),
        'moderado': np.array([0.4, 0.3, 0.3]),
        'arrojado': np.array([0.6, 0.2, 0.2])
    }

    # Pontos de referência R-NSGA2 [retorno_neg, variância, cvar]
    REFERENCE_POINTS: Dict[str, np.ndarray] = {
        'conservador': np.array([[0.3, 0.0, 0.0]]),
        'moderado': np.array([[0.0, 0.3, 0.3]]),
        'arrojado': np.array([[0.0, 0.3, 0.3]])
    }

    # R-NSGA2
    RNSGA2_EPSILON = float(os.getenv('AGMO_RNSGA2_EPSILON', '0.01'))
    RNSGA2_WEIGHTS = np.array([0.5, 0.25, 0.25])

    # Early stopping
    EARLY_STOPPING_FTOL = float(os.getenv('AGMO_EARLY_STOPPING_FTOL', '0.005'))
    EARLY_STOPPING_PERIOD = int(os.getenv('AGMO_EARLY_STOPPING_PERIOD', '40'))

    # Mutação
    MUTATION_REPLACE_PROB = float(os.getenv('AGMO_MUTATION_REPLACE_PROB', '0.3'))
    MUTATION_MAGNITUDE_FACTOR = float(os.getenv('AGMO_MUTATION_MAGNITUDE', '0.2'))

    # Validação
    PRAZO_MIN_ANOS = int(os.getenv('AGMO_PRAZO_MIN_ANOS', '1'))
    PRAZO_MAX_ANOS = int(os.getenv('AGMO_PRAZO_MAX_ANOS', '30'))

    # Tolerâncias numéricas
    PESO_TOLERANCIA = float(os.getenv('AGMO_PESO_TOLERANCIA', '1e-6'))
    PESO_MINIMO_COMPOSICAO = float(os.getenv('AGMO_PESO_MIN_COMPOSICAO', '0.001'))

    # Logging
    LOG_LEVEL = os.getenv('AGMO_LOG_LEVEL', 'INFO')
    VERBOSE_OPTIMIZATION = os.getenv('AGMO_VERBOSE', 'true').lower() == 'true'

    @classmethod
    def get_hhi_threshold(cls, nivel_risco: str) -> float:
        """Retorna threshold HHI para o perfil de risco."""
        return cls.HHI_THRESHOLDS.get(nivel_risco, cls.HHI_THRESHOLDS['moderado'])

    @classmethod
    def get_pesos_selecao(cls, nivel_risco: str) -> np.ndarray:
        """Retorna pesos de seleção para o perfil de risco."""
        return cls.PESOS_SELECAO.get(nivel_risco, cls.PESOS_SELECAO['moderado'])

    @classmethod
    def get_reference_points(cls, nivel_risco: str) -> np.ndarray:
        """Retorna pontos de referência R-NSGA2 para o perfil de risco."""
        return cls.REFERENCE_POINTS.get(nivel_risco, cls.REFERENCE_POINTS['moderado'])

    @classmethod
    def validate_prazo(cls, prazo_anos: int) -> bool:
        """Valida se o prazo está dentro dos limites."""
        return cls.PRAZO_MIN_ANOS <= prazo_anos <= cls.PRAZO_MAX_ANOS
