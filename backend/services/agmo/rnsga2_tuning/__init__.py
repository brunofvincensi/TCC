"""
R-NSGA2 Tuning Module

Módulo especializado para análise e tuning de hiperparâmetros do R-NSGA-II.

Diferente do tuning genérico, este módulo entende o comportamento específico
do R-NSGA-II (Reference Point Based NSGA-II), onde o hipervolume pode cair
durante a convergência para o ponto de referência (comportamento esperado).
"""

from .rnsga2_tuning_service import RNSGA2TuningService

__all__ = ['RNSGA2TuningService']
