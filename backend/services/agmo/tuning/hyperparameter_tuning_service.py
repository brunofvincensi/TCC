"""
Serviço de Otimização de Hiperparâmetros para AGMO

Este módulo implementa análises sistemáticas para determinar os melhores
hiperparâmetros do algoritmo genético multiobjetivo (AGMO), incluindo:
- Análise de convergência
- Grid search de hiperparâmetros
- Validação estatística com múltiplas execuções
- Geração de relatórios e visualizações

Autor: Sistema de Otimização de Portfólio - TCC
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging
import time
import json
from pathlib import Path

# Configurar matplotlib para usar backend não-interativo (thread-safe)
# IMPORTANTE: Deve ser configurado ANTES de importar pyplot
import matplotlib
matplotlib.use('Agg')  # Backend sem GUI, seguro para threads
import matplotlib.pyplot as plt

import seaborn as sns
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from .quality_metrics import QualityMetrics, ConvergenceTracker
from services.agmo.agmo_service import (
    Nsga2OtimizacaoService,
    REFERENCE_POINTS_CONFIG,
    WEIGHTS_CONFIG
)

logger = logging.getLogger(__name__)

# Configuração de estilo para gráficos
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10


@dataclass
class HyperparameterConfig:
    """Configuração de hiperparâmetros para teste."""
    population_size: int
    generations: int
    crossover_eta: float = 15.0
    mutation_eta: float = 20.0

    def __str__(self):
        return f"pop{self.population_size}_gen{self.generations}"


@dataclass
class TuningResult:
    """Resultado de uma execução de tuning (simplificado - apenas métricas essenciais)."""
    config: HyperparameterConfig
    run_number: int
    execution_time: float
    final_hypervolume: float
    convergence_generation: Optional[int]

    def to_dict(self):
        """Converte para dicionário."""
        result = asdict(self)
        result['config'] = str(self.config)
        return result


class HyperparameterTuningService:
    """
    Serviço para otimização de hiperparâmetros do AGMO.
    """

    def __init__(self, app=None):
        """
        Inicializa o serviço de tuning.

        Args:
            app: Instância Flask (opcional, para acesso ao banco de dados)
        """
        self.app = app
        self.results: List[TuningResult] = []
        self.metrics_calculator = QualityMetrics()

    def convergence_analysis(
        self,
        ids_assets: List[int],
        risk_level: str = 'moderado',
        max_generations: int = 200,
        population_size: int = 100,
        n_runs: int = 5
    ) -> Dict:
        """
        Analisa a convergência do algoritmo ao longo das gerações.
        """
        logger.info(f"Iniciando análise de convergência: {n_runs} execuções, "
                   f"{max_generations} gerações, população {population_size}")

        # Prepara dados para otimização
        service = Nsga2OtimizacaoService(self.app, [], risk_level, 10, asset_ids=ids_assets)

        # Obtém pontos de referência do R-NSGA2 para o perfil de risco (configuração centralizada)
        ref_points = REFERENCE_POINTS_CONFIG.get(risk_level)

        # Múltiplas execuções para análise estatística
        all_runs = []
        for run in range(n_runs):
            logger.info(f"Executando run {run + 1}/{n_runs}")

            # Executa otimização com tracking de convergência usando R-HV
            convergence_tracker = ConvergenceTracker(
                reference_points_rnsga2=ref_points,
                use_r_hv=True
            )

            result = service.optimize(
                population_size=population_size,
                generations=max_generations,
                convergence_tracker=convergence_tracker
            )

            all_runs.append({
                'run': run + 1,
                'history': convergence_tracker.get_history(),
                'convergence_gen': convergence_tracker.get_convergence_generation()
            })

        # Análise estatística dos resultados
        analysis = self._analyze_convergence_runs(all_runs)

        # Gera visualizações
        self._plot_convergence_analysis(analysis, population_size, max_generations)

        return analysis

    def grid_search(
        self,
        ids_assets: List[int],
        population_sizes: List[int] = None,
        generation_counts: List[int] = None,
        n_runs: int = 3,
        time_limit: Optional[float] = None,
        risk_level: str = 'moderado'
    ) -> pd.DataFrame:
        """
        Realiza grid search para encontrar os melhores hiperparâmetros.

        Args:
            ids_assets: IDs dos ativos para otimização
            population_sizes: Lista de tamanhos de população para testar
            generation_counts: Lista de números de gerações para testar
            n_runs: Número de execuções por configuração
            time_limit: Tempo máximo total em segundos (opcional)

        Returns:
            DataFrame com resultados do grid search
        """
        if population_sizes is None:
            population_sizes = [50, 100, 200, 300]

        if generation_counts is None:
            generation_counts = [25, 50, 100, 150]

        logger.info(f"Iniciando Grid Search: {len(population_sizes)} pop sizes × "
                   f"{len(generation_counts)} gen counts × {n_runs} runs = "
                   f"{len(population_sizes) * len(generation_counts) * n_runs} execuções")

        # Prepara configurações
        configs = []
        for pop_size in population_sizes:
            for gen_count in generation_counts:
                configs.append(HyperparameterConfig(
                    population_size=pop_size,
                    generations=gen_count
                ))

        # Executa todas as configurações
        start_time = time.time()
        results = []

        for config_idx, config in enumerate(configs):
            if time_limit and (time.time() - start_time) > time_limit:
                logger.warning(f"Tempo limite atingido. Parando grid search.")
                break

            logger.info(f"Testando configuração {config_idx + 1}/{len(configs)}: {config}")

            for run in range(n_runs):
                try:
                    print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                    result = self._run_single_optimization(
                        config=config,
                        ids_assets=ids_assets,
                        run_number=run + 1,
                        max_assets=10,
                        risk_level=risk_level
                    )
                    results.append(result)
                    self.results.append(result)

                except Exception as e:
                    logger.error(f"Erro na execução {run + 1} de {config}: {e}")
                    continue

        # Converte para DataFrame
        df_results = pd.DataFrame([r.to_dict() for r in results])

        # Análise estatística agregada
        summary = self._create_summary_statistics(df_results)

        # Gera visualizações
        self._plot_grid_search_results(df_results, summary)

        return summary

    def _run_single_optimization(
        self,
        config: HyperparameterConfig,
        ids_assets: List[int],
        run_number: int,
        max_assets: int = None,
        risk_level: str = 'moderado'
    ) -> TuningResult:

        """
        Executa uma única otimização com uma configuração específica.
        """
        service = Nsga2OtimizacaoService(self.app, [], risk_level, asset_ids=ids_assets, years_period=3)

        # Obtém pontos de referência do R-NSGA2 para o perfil de risco
        ref_points = REFERENCE_POINTS_CONFIG.get(risk_level)

        convergence_tracker = ConvergenceTracker(
            reference_points_rnsga2=ref_points,
            use_r_hv=True
        )

        start_time = time.time()

        # Executa otimização
        result = service.optimize(
            population_size=config.population_size,
            generations=config.generations,
            convergence_tracker=convergence_tracker,
            max_assets=max_assets
        )

        execution_time = time.time() - start_time

        # Extrai apenas as métricas essenciais
        history = convergence_tracker.get_history()

        # Usa a chave correta (r_hypervolume ou hypervolume)
        hv_key = convergence_tracker.hv_key
        final_hv = history[hv_key][-1] if history[hv_key] else 0

        return TuningResult(
            config=config,
            run_number=run_number,
            execution_time=execution_time,
            final_hypervolume=final_hv,
            convergence_generation=convergence_tracker.get_convergence_generation()
        )

    def _analyze_convergence_runs(self, all_runs: List[Dict]) -> Dict:
        """
        Analisa estatisticamente múltiplas execuções de convergência.

        Args:
            all_runs: Lista de resultados de execuções

        Returns:
            Dicionário com análise estatística
        """
        # Extrai gerações de convergência
        convergence_gens = [r['convergence_gen'] for r in all_runs
                           if r['convergence_gen'] is not None]

        # Detecta qual chave de hypervolume está sendo usada
        first_history = all_runs[0]['history']
        hv_key = 'r_hypervolume' if 'r_hypervolume' in first_history else 'hypervolume'

        # Calcula métricas ao longo das gerações (média e desvio padrão)
        max_gen = max(len(r['history']['generation']) for r in all_runs)

        metrics_over_time = {
            'generation': list(range(max_gen)),
            f'{hv_key}_mean': [],
            f'{hv_key}_std': [],
            'spread_mean': [],
            'spread_std': [],
            'spacing_mean': [],
            'spacing_std': [],
            'pareto_size_mean': [],
            'pareto_size_std': [],
        }

        for gen in range(max_gen):
            hv_values = []
            spread_values = []
            spacing_values = []
            size_values = []

            for run in all_runs:
                history = run['history']
                if gen < len(history['generation']):
                    hv_values.append(history[hv_key][gen])
                    spread_values.append(history['spread'][gen])
                    spacing_values.append(history['spacing'][gen])
                    size_values.append(history['pareto_size'][gen])

            metrics_over_time[f'{hv_key}_mean'].append(np.mean(hv_values))
            metrics_over_time[f'{hv_key}_std'].append(np.std(hv_values))
            metrics_over_time['spread_mean'].append(np.mean(spread_values))
            metrics_over_time['spread_std'].append(np.std(spread_values))
            metrics_over_time['spacing_mean'].append(np.mean(spacing_values))
            metrics_over_time['spacing_std'].append(np.std(spacing_values))
            metrics_over_time['pareto_size_mean'].append(np.mean(size_values))
            metrics_over_time['pareto_size_std'].append(np.std(size_values))

        return {
            'n_runs': len(all_runs),
            'convergence_generations': convergence_gens,
            'convergence_mean': np.mean(convergence_gens) if convergence_gens else None,
            'convergence_std': np.std(convergence_gens) if convergence_gens else None,
            'metrics_over_time': metrics_over_time,
            'raw_runs': all_runs,
            'hv_key': hv_key  # Adiciona a chave usada para referência
        }

    def _create_summary_statistics(self, df_results: pd.DataFrame) -> pd.DataFrame:
        """
        Cria estatísticas sumarizadas do grid search (apenas métricas essenciais).

        Args:
            df_results: DataFrame com resultados brutos

        Returns:
            DataFrame com estatísticas agregadas por configuração
        """
        # Extrai população e gerações da string de config
        df_results['population_size'] = df_results['config'].str.extract(r'pop(\d+)').astype(int)
        df_results['generations'] = df_results['config'].str.extract(r'gen(\d+)').astype(int)

        # Agrupa por configuração - apenas métricas essenciais
        summary = df_results.groupby(['population_size', 'generations']).agg({
            'final_hypervolume': ['mean', 'std'],
            'execution_time': ['mean'],
            'convergence_generation': ['mean']
        }).reset_index()

        # Renomeia colunas
        summary.columns = ['_'.join(col).strip('_') for col in summary.columns.values]

        # Ordena por hypervolume médio (decrescente)
        summary = summary.sort_values('final_hypervolume_mean', ascending=False)

        return summary

    def _plot_convergence_analysis(self, analysis: Dict,
                                   population_size: int,
                                   max_generations: int):
        """
        Gera gráficos de análise de convergência.

        Args:
            analysis: Resultados da análise de convergência
            population_size: Tamanho da população usado
            max_generations: Número máximo de gerações
        """
        metrics = analysis['metrics_over_time']
        n_runs = analysis['n_runs']
        hv_key = analysis.get('hv_key', 'hypervolume')

        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        # Define título apropriado baseado na métrica usada
        hv_label = 'R-Hypervolume (R2)' if hv_key == 'r_hypervolume' else 'Hypervolume'
        fig.suptitle(f'Análise de Convergência ({hv_label}) - População: {population_size}, '
                    f'{n_runs} execuções', fontsize=14, fontweight='bold')

        generations = metrics['generation']

        # 1. Hypervolume (ou R-Hypervolume)
        ax = axes[0, 0]
        mean = metrics[f'{hv_key}_mean']
        std = metrics[f'{hv_key}_std']
        ax.plot(generations, mean, 'b-', linewidth=2, label='Média')
        ax.fill_between(generations, np.array(mean) - np.array(std),
                       np.array(mean) + np.array(std), alpha=0.3)
        ax.set_xlabel('Geração')
        ax.set_ylabel(hv_label)
        ax.set_title(f'Evolução do {hv_label}')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 2. Spread
        ax = axes[0, 1]
        mean = metrics['spread_mean']
        std = metrics['spread_std']
        ax.plot(generations, mean, 'g-', linewidth=2, label='Média')
        ax.fill_between(generations, np.array(mean) - np.array(std),
                       np.array(mean) + np.array(std), alpha=0.3, color='g')
        ax.set_xlabel('Geração')
        ax.set_ylabel('Spread')
        ax.set_title('Evolução do Spread (Diversidade)')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 3. Spacing
        ax = axes[1, 0]
        mean = metrics['spacing_mean']
        std = metrics['spacing_std']
        ax.plot(generations, mean, 'r-', linewidth=2, label='Média')
        ax.fill_between(generations, np.array(mean) - np.array(std),
                       np.array(mean) + np.array(std), alpha=0.3, color='r')
        ax.set_xlabel('Geração')
        ax.set_ylabel('Spacing')
        ax.set_title('Evolução do Spacing (Uniformidade)')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 4. Tamanho da Fronteira de Pareto
        ax = axes[1, 1]
        mean = metrics['pareto_size_mean']
        std = metrics['pareto_size_std']
        ax.plot(generations, mean, 'm-', linewidth=2, label='Média')
        ax.fill_between(generations, np.array(mean) - np.array(std),
                       np.array(mean) + np.array(std), alpha=0.3, color='m')
        ax.set_xlabel('Geração')
        ax.set_ylabel('Número de Soluções')
        ax.set_title('Tamanho da Fronteira de Pareto')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # Salva figura
        output_dir = Path('tuning_results')
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_dir / f'convergence_analysis_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        logger.info(f"Gráfico de convergência salvo em: {filename}")

        plt.close()

        # Histograma de gerações de convergência
        if analysis['convergence_generations']:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(analysis['convergence_generations'], bins=20, edgecolor='black', alpha=0.7)
            ax.axvline(analysis['convergence_mean'], color='r', linestyle='--',
                      linewidth=2, label=f'Média: {analysis["convergence_mean"]:.1f}')
            ax.set_xlabel('Geração de Convergência')
            ax.set_ylabel('Frequência')
            ax.set_title(f'Distribuição das Gerações de Convergência ({n_runs} execuções)')
            ax.legend()
            ax.grid(True, alpha=0.3)

            filename = output_dir / f'convergence_histogram_{timestamp}.png'
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            logger.info(f"Histograma de convergência salvo em: {filename}")
            plt.close()

    def _plot_grid_search_results(self, df_results: pd.DataFrame,
                                  summary: pd.DataFrame):
        """
        Gera visualizações simplificadas dos resultados do grid search.

        Args:
            df_results: DataFrame com resultados brutos
            summary: DataFrame com estatísticas sumarizadas
        """
        output_dir = Path('tuning_results')
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 1. Heatmap de Hypervolume médio
        pivot_hv = summary.pivot(index='generations', columns='population_size',
                                 values='final_hypervolume_mean')

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(pivot_hv, annot=True, fmt='.6e', cmap='YlGnBu', ax=ax)
        ax.set_title('Hypervolume Médio por Configuração', fontsize=14, fontweight='bold')
        ax.set_xlabel('Tamanho da População')
        ax.set_ylabel('Número de Gerações')

        filename = output_dir / f'grid_search_heatmap_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        logger.info(f"Heatmap salvo em: {filename}")
        plt.close()

        # 2. Trade-off Qualidade vs Tempo (simplificado - sem barras de erro)
        fig, ax = plt.subplots(figsize=(10, 6))

        for pop_size in summary['population_size'].unique():
            subset = summary[summary['population_size'] == pop_size]
            ax.plot(subset['execution_time_mean'], subset['final_hypervolume_mean'],
                   'o-', markersize=8, linewidth=2, label=f'Pop {pop_size}')

        ax.set_xlabel('Tempo de Execução Médio (s)')
        ax.set_ylabel('Hypervolume Médio')
        ax.set_title('Trade-off: Qualidade vs Tempo de Execução',
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)

        filename = output_dir / f'quality_vs_time_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        logger.info(f"Gráfico de trade-off salvo em: {filename}")
        plt.close()

        # 3. Salva tabela de resultados
        filename_csv = output_dir / f'grid_search_summary_{timestamp}.csv'
        summary.to_csv(filename_csv, index=False)
        logger.info(f"Tabela de resultados salva em: {filename_csv}")

    def export_results(self, filename: str = None) -> str:
        """
        Exporta todos os resultados para arquivo JSON.

        Args:
            filename: Nome do arquivo (opcional)

        Returns:
            Caminho do arquivo salvo
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'tuning_results/all_results_{timestamp}.json'

        Path(filename).parent.mkdir(exist_ok=True)

        results_dict = [r.to_dict() for r in self.results]

        with open(filename, 'w') as f:
            json.dump(results_dict, f, indent=2)

        logger.info(f"Resultados exportados para: {filename}")
        return filename

    def get_best_configuration(self) -> Optional[HyperparameterConfig]:
        """
        Retorna a melhor configuração priorizando fortemente o Hypervolume.

        Lógica de seleção:
        1. Prioridade MÁXIMA: Hypervolume (qualidade das soluções)
        2. Tempo só é considerado como desempate se HVs forem 90% similares
           (diferença <= 10%)

        Isso garante que a qualidade das soluções sempre venha em primeiro lugar,
        e velocidade só importa quando não há perda significativa de qualidade.

        Returns:
            Melhor configuração de hiperparâmetros (maior HV, tempo secundário)
        """
        if not self.results:
            return None

        # Agrupa resultados por configuração
        config_scores = {}
        for result in self.results:
            config_str = str(result.config)
            if config_str not in config_scores:
                config_scores[config_str] = {
                    'config': result.config,
                    'hypervolumes': [],
                    'execution_times': []
                }
            config_scores[config_str]['hypervolumes'].append(result.final_hypervolume)
            config_scores[config_str]['execution_times'].append(result.execution_time)

        # Seleciona melhor configuração priorizando HV
        # Tempo só é considerado se HVs forem 90% similares (diferença <= 10%)
        best_config = None
        best_hv = -float('inf')
        best_time = float('inf')

        # Calcula médias para cada configuração
        config_metrics = []
        for config_str, data in config_scores.items():
            mean_hv = np.mean(data['hypervolumes'])
            mean_time = np.mean(data['execution_times'])
            config_metrics.append({
                'config': data['config'],
                'mean_hv': mean_hv,
                'mean_time': mean_time,
                'config_str': config_str
            })
            logger.debug(f"Config {config_str}: HV={mean_hv:.6e}, Time={mean_time:.2f}s")

        # Ordena por HV (decrescente)
        config_metrics.sort(key=lambda x: x['mean_hv'], reverse=True)

        # Seleciona o melhor
        for i, metrics in enumerate(config_metrics):
            if i == 0:
                # Primeiro (maior HV) é sempre candidato
                best_config = metrics['config']
                best_hv = metrics['mean_hv']
                best_time = metrics['mean_time']
            else:
                # Verifica se HV é 90% similar ao melhor (diferença <= 10%)
                hv_similarity = abs(metrics['mean_hv'] - best_hv) / best_hv if best_hv > 0 else 1.0

                if hv_similarity <= 0.10 and metrics['mean_time'] < best_time:
                    # HVs são 90% similares E este é mais rápido
                    logger.info(f"⚡ Trade-off tempo: HV similar ({hv_similarity*100:.1f}% diff), "
                               f"mas {best_time/metrics['mean_time']:.2f}x mais rápido")
                    best_config = metrics['config']
                    best_hv = metrics['mean_hv']
                    best_time = metrics['mean_time']
                else:
                    # HVs não são similares, prioriza qualidade
                    break

        logger.info(f"✅ Melhor configuração (prioridade: HV >> tempo): {best_config}")
        logger.info(f"   HV médio: {best_hv:.6e}")
        logger.info(f"   Tempo médio: {best_time:.2f}s")

        return best_config

    def _tune_single_asset_quantity(
        self,
        num_assets: int,
        risk_level: str,
        population_sizes: List[int],
        generation_counts: List[int],
        n_runs: int
    ) -> Optional[Dict]:
        """
        Executa tuning para uma quantidade específica de ativos.

        Esta função é projetada para ser executada em paralelo.

        Args:
            num_assets: Quantidade de ativos a testar
            risk_level: Perfil de risco
            population_sizes: Lista de tamanhos de população
            generation_counts: Lista de números de gerações
            n_runs: Número de execuções por configuração

        Returns:
            Dicionário com configuração ótima ou None em caso de erro
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 [Thread {num_assets}] Testando com {num_assets} ativos")
        logger.info(f"{'='*70}")

        try:
            # Busca ativos do banco para teste
            with self.app.app_context():
                from models import db, Asset
                from models.ativo import AssetType

                assets = db.session.query(Asset).filter(Asset.type == AssetType.STOCK).limit(num_assets).all()

                if len(assets) < num_assets:
                    logger.warning(f"⚠️  [Thread {num_assets}] Apenas {len(assets)} ativos disponíveis. Pulando.")
                    return None

                ids_assets = [a.id for a in assets]

            # Executa grid search para esta quantidade de ativos
            logger.info(f"🚀 [Thread {num_assets}] Iniciando grid search...")
            start_time = time.time()

            summary = self.grid_search(
                ids_assets=ids_assets,
                population_sizes=population_sizes,
                generation_counts=generation_counts,
                n_runs=n_runs,
                risk_level=risk_level
            )

            elapsed = time.time() - start_time
            logger.info(f"✅ [Thread {num_assets}] Grid search concluído em {elapsed/60:.1f} minutos")

            # Extrai melhor configuração
            if not summary.empty:
                best = summary.iloc[0]

                optimal_config = {
                    'num_assets': num_assets,
                    'risk_level': risk_level,
                    'population_size': int(best['population_size']),
                    'generations': int(best['generations']),
                    'crossover_eta': 15.0,
                    'mutation_eta': 20.0,
                    'hypervolume_mean': float(best['final_hypervolume_mean']),
                    'execution_time_mean': float(best['execution_time_mean']),
                    'convergence_generation_mean': float(best.get('convergence_generation_mean', 0)) if pd.notna(best.get('convergence_generation_mean')) else None
                }

                logger.info(f"\n🏆 [Thread {num_assets}] Melhor configuração:")
                logger.info(f"   População: {optimal_config['population_size']}")
                logger.info(f"   Gerações: {optimal_config['generations']}")
                logger.info(f"   Hypervolume: {optimal_config['hypervolume_mean']:.6e}")
                logger.info(f"   Tempo: {optimal_config['execution_time_mean']:.2f}s")
                logger.info(f"   Eficiência: {optimal_config['hypervolume_mean']/optimal_config['execution_time_mean']:.6e}")

                return optimal_config
            else:
                logger.warning(f"⚠️  [Thread {num_assets}] Nenhum resultado obtido")
                return None

        except Exception as e:
            logger.error(f"❌ [Thread {num_assets}] Erro: {e}")
            logger.exception(f"Detalhes do erro para {num_assets} ativos:")
            return None

    def adaptive_tuning_by_num_assets(
        self,
        asset_ranges: List[int] = None,
        risk_level: str = 'moderado',
        population_sizes: List[int] = None,
        generation_counts: List[int] = None,
        n_runs: int = 3,
        save_to_db: bool = True
    ) -> pd.DataFrame:
        """
        Realiza tuning adaptativo para diferentes quantidades de ativos.

        Este método executa grid search para múltiplas quantidades de ativos,
        determinando a configuração ótima para cada uma. Isso permite que o
        sistema use automaticamente hiperparâmetros apropriados baseados na
        complexidade do problema (número de ativos).

        Args:
            asset_ranges: Lista com quantidades de ativos a testar
                         (default: [5, 10, 15, 20])
            risk_level: Perfil de risco
            population_sizes: Lista de tamanhos de população
                            (default: [50, 100, 150, 200, 300])
            generation_counts: Lista de números de gerações
                             (default: [25, 50, 75, 100, 150, 200])
            n_runs: Número de execuções por configuração
            save_to_db: Se deve salvar resultados no banco de dados

        Returns:
            DataFrame com configurações ótimas por quantidade de ativos
        """
        if asset_ranges is None:
            asset_ranges = [10, 15, 20]

        if population_sizes is None:
            population_sizes = [50, 100, 150, 200, 300]

        if generation_counts is None:
            generation_counts = [25, 50, 75, 100, 150, 200]

        logger.info(f"Iniciando Tuning Adaptativo por Quantidade de Ativos (PARALELO)")
        logger.info(f"  Quantidades de ativos: {asset_ranges}")
        logger.info(f"  Populações: {population_sizes}")
        logger.info(f"  Gerações: {generation_counts}")
        logger.info(f"  Execuções por config: {n_runs}")
        logger.info(f"  Perfil de risco: {risk_level}")
        logger.info(f"  🚀 Threads paralelas: {len(asset_ranges)}")

        optimal_configs = []

        # Usa ThreadPoolExecutor para executar tunings em paralelo
        # Cada quantidade de ativos roda em uma thread separada
        with ThreadPoolExecutor(max_workers=len(asset_ranges)) as executor:
            # Submete todas as tarefas
            future_to_num_assets = {
                executor.submit(
                    self._tune_single_asset_quantity,
                    num_assets,
                    risk_level,
                    population_sizes,
                    generation_counts,
                    n_runs
                ): num_assets
                for num_assets in asset_ranges
            }

            logger.info(f"\n🚀 Todas as {len(asset_ranges)} threads iniciadas!")
            logger.info(f"⏳ Aguardando conclusão... (isso pode levar várias horas)")

            # Coleta resultados conforme vão sendo completados
            completed_count = 0
            for future in as_completed(future_to_num_assets):
                num_assets = future_to_num_assets[future]
                completed_count += 1

                try:
                    result = future.result()
                    if result:
                        optimal_configs.append(result)
                        logger.info(f"\n📊 Progresso: {completed_count}/{len(asset_ranges)} testes concluídos")
                    else:
                        logger.warning(f"⚠️  Thread {num_assets}: Sem resultado")
                except Exception as e:
                    logger.error(f"❌ Thread {num_assets}: Exceção - {e}")
                    logger.exception(f"Detalhes da exceção:")

        logger.info(f"\n✅ Todas as threads finalizadas!")
        logger.info(f"   Configurações encontradas: {len(optimal_configs)}/{len(asset_ranges)}")

        # Converte para DataFrame
        df_optimal = pd.DataFrame(optimal_configs)

        if df_optimal.empty:
            logger.warning("Nenhuma configuração ótima foi encontrada!")
            return df_optimal

        # Salva no banco de dados se solicitado
        if save_to_db and self.app:
            self.save_optimal_configs_to_db(df_optimal)

        # Salva em arquivo também
        output_dir = Path('tuning_results')
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_dir / f'adaptive_tuning_{timestamp}.csv'
        df_optimal.to_csv(filename, index=False)
        logger.info(f"\n📁 Configurações ótimas salvas em: {filename}")

        # Gera visualização
        self._plot_adaptive_tuning_results(df_optimal)

        return df_optimal

    def save_optimal_configs_to_db(self, df_optimal: pd.DataFrame):
        """
        Salva configurações ótimas no banco de dados.

        Args:
            df_optimal: DataFrame com configurações ótimas
        """
        if not self.app:
            logger.warning("App não disponível. Não é possível salvar no banco.")
            return

        with self.app.app_context():
            from models import db, HyperparameterConfig

            saved_count = 0
            updated_count = 0

            for _, row in df_optimal.iterrows():
                num_assets = int(row['num_assets'])
                risk_level = row['risk_level']

                # Verifica se já existe configuração para esta quantidade
                existing = HyperparameterConfig.query.filter_by(
                    num_assets=num_assets,
                    risk_level=risk_level
                ).first()

                if existing:
                    # Desativa a antiga
                    existing.is_active = False
                    updated_count += 1

                # Cria nova configuração (apenas campos essenciais)
                new_config = HyperparameterConfig(
                    num_assets=num_assets,
                    risk_level=risk_level,
                    population_size=int(row['population_size']),
                    generations=int(row['generations']),
                    crossover_eta=float(row['crossover_eta']),
                    mutation_eta=float(row['mutation_eta']),
                    hypervolume_mean=float(row['hypervolume_mean']),
                    execution_time_mean=float(row['execution_time_mean']),
                    convergence_generation_mean=float(row['convergence_generation_mean']) if pd.notna(row.get('convergence_generation_mean')) else None,
                    tuning_date=datetime.utcnow(),
                    notes=f"Adaptive tuning - simplified metrics",
                    is_active=True
                )

                db.session.add(new_config)
                saved_count += 1

            db.session.commit()

            logger.info(f"\n✅ Configurações salvas no banco de dados:")
            logger.info(f"   Novas: {saved_count}")
            logger.info(f"   Atualizadas: {updated_count}")

    def _plot_adaptive_tuning_results(self, df_optimal: pd.DataFrame):
        """
        Gera visualizações simplificadas dos resultados do tuning adaptativo.

        Args:
            df_optimal: DataFrame com configurações ótimas
        """
        if df_optimal.empty:
            return

        output_dir = Path('tuning_results')
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Gráfico simplificado: 3 subplots em vez de 4
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        fig.suptitle('Tuning Adaptativo - Métricas Essenciais',
                    fontsize=14, fontweight='bold')

        # 1. População ótima vs Número de ativos
        ax = axes[0]
        ax.plot(df_optimal['num_assets'], df_optimal['population_size'],
               'o-', markersize=10, linewidth=2, color='steelblue')
        ax.set_xlabel('Número de Ativos')
        ax.set_ylabel('População Ótima')
        ax.set_title('População Ótima')
        ax.grid(True, alpha=0.3)

        # 2. Gerações ótimas vs Número de ativos
        ax = axes[1]
        ax.plot(df_optimal['num_assets'], df_optimal['generations'],
               'o-', markersize=10, linewidth=2, color='forestgreen')
        ax.set_xlabel('Número de Ativos')
        ax.set_ylabel('Gerações Ótimas')
        ax.set_title('Gerações Ótimas')
        ax.grid(True, alpha=0.3)

        # 3. Hypervolume vs Tempo (Trade-off Qualidade × Velocidade)
        ax = axes[2]
        scatter = ax.scatter(df_optimal['execution_time_mean'],
                           df_optimal['hypervolume_mean'],
                           s=df_optimal['num_assets']*20,  # Tamanho = num ativos
                           c=df_optimal['num_assets'],     # Cor = num ativos
                           cmap='viridis', alpha=0.7, edgecolors='black')
        ax.set_xlabel('Tempo de Execução (s)')
        ax.set_ylabel('Hypervolume (Qualidade)')
        ax.set_title('Trade-off Qualidade × Velocidade')
        ax.grid(True, alpha=0.3)

        # Adiciona colorbar para mostrar número de ativos
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Nº Ativos')

        plt.tight_layout()

        filename = output_dir / f'adaptive_tuning_plot_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        logger.info(f"📊 Gráfico salvo em: {filename}")
        plt.close()

    @staticmethod
    def get_optimal_config_from_db(num_assets: int, risk_level: str = 'neutro',
                                   app=None):
        """
        Busca configuração ótima do banco de dados.

        Args:
            num_assets: Número de ativos
            risk_level: Perfil de risco
            app: Instância Flask

        Returns:
            Dicionário com hiperparâmetros ou None
        """
        if not app:
            return None

        with app.app_context():
            from models import HyperparameterConfig

            config = HyperparameterConfig.get_optimal_config(num_assets, risk_level)

            if config:
                logger.info(f"✅ Usando configuração ótima do banco para "
                          f"{num_assets} ativos (perfil: {risk_level})")
                logger.info(f"   População: {config.population_size}, "
                          f"Gerações: {config.generations}")

                return {
                    'population_size': config.population_size,
                    'generations': config.generations,
                    'crossover_eta': config.crossover_eta,
                    'mutation_eta': config.mutation_eta
                }

            logger.warning(f"⚠️  Configuração não encontrada para {num_assets} ativos. "
                         f"Usando valores padrão.")
            return None
