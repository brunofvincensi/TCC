"""
Módulo de Tuning e Análise de Convergência para AGMO

Este módulo contém ferramentas para:
- Cálculo de métricas de qualidade (Hypervolume, R-Hypervolume, etc.)
- Tracking de convergência durante a otimização
- Visualização da evolução das métricas
"""

from .quality_metrics import QualityMetrics, ConvergenceTracker
from .convergence_visualization import (
    plot_convergence_evolution,
    plot_hypervolume_only,
    plot_multiple_runs_comparison,
    print_convergence_summary
)

__all__ = [
    'QualityMetrics',
    'ConvergenceTracker',
    'plot_convergence_evolution',
    'plot_hypervolume_only',
    'plot_multiple_runs_comparison',
    'print_convergence_summary',
]
