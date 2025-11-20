"""
Serviço de Tuning Especializado para R-NSGA-II

Este serviço entende o comportamento específico do R-NSGA-II:
- Hipervolume pode cair durante convergência (normal)
- Foca em região específica baseada no reference point
- Métricas de convergência adaptadas para busca focal
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from datetime import datetime
from pathlib import Path
import logging
import time

# Configurar matplotlib para backend thread-safe
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from services.agmo.agmo_service import Nsga2OtimizacaoService
from services.agmo.tuning.quality_metrics import ConvergenceTracker
from models import db, Asset
from models.ativo import AssetType

logger = logging.getLogger(__name__)

# Estilo dos gráficos
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10


class RNSGA2TuningService:
    """
    Serviço de tuning para R-NSGA-II com foco em análise de convergência.
    """

    def __init__(self, app):
        """
        Inicializa o serviço de tuning.

        Args:
            app: Instância da aplicação Flask
        """
        self.app = app

    def run_tuning_grid(
        self,
        asset_quantities: List[int],
        population_sizes: List[int],
        generation_counts: List[int],
        n_runs: int = 3,
        risk_level: str = 'moderado'
    ) -> pd.DataFrame:
        """
        Executa grid search testando todas combinações de hiperparâmetros.

        Para cada configuração, captura a evolução completa do hipervolume
        ao longo das gerações, permitindo visualizar o comportamento de
        convergência do R-NSGA-II.

        Args:
            asset_quantities: Lista de quantidades de ativos a testar
            population_sizes: Lista de tamanhos de população
            generation_counts: Lista de números de gerações
            n_runs: Número de execuções por configuração
            risk_level: Perfil de risco

        Returns:
            DataFrame com resultados consolidados
        """
        logger.info("="*70)
        logger.info("INICIANDO R-NSGA-II TUNING GRID SEARCH")
        logger.info("="*70)
        logger.info(f"Quantidades de ativos: {asset_quantities}")
        logger.info(f"Populações: {population_sizes}")
        logger.info(f"Gerações: {generation_counts}")
        logger.info(f"Execuções por config: {n_runs}")
        logger.info(f"Perfil de risco: {risk_level}")

        total_configs = len(asset_quantities) * len(population_sizes) * len(generation_counts) * n_runs
        logger.info(f"\nTotal de execuções: {total_configs}")

        results = []
        config_num = 0

        for num_assets in asset_quantities:
            logger.info(f"\n{'='*70}")
            logger.info(f"Testando com {num_assets} ativos")
            logger.info(f"{'='*70}")

            # Busca ativos
            with self.app.app_context():
                assets = db.session.query(Asset).filter(
                    Asset.type == AssetType.STOCK
                ).limit(num_assets).all()

                if len(assets) < num_assets:
                    logger.warning(f"Apenas {len(assets)} ativos disponíveis. Pulando {num_assets}.")
                    continue

                ids_assets = [a.id for a in assets]
                tickers = [a.ticker for a in assets]

            logger.info(f"Ativos selecionados: {', '.join(tickers)}")

            for pop_size in population_sizes:
                for generations in generation_counts:
                    logger.info(f"\n--- Config: Pop={pop_size}, Gen={generations} ---")

                    for run in range(n_runs):
                        config_num += 1
                        logger.info(f"Execução {run+1}/{n_runs} (Total: {config_num}/{total_configs})")

                        try:
                            result = self._run_single_config(
                                ids_assets=ids_assets,
                                pop_size=pop_size,
                                generations=generations,
                                run_number=run + 1,
                                risk_level=risk_level
                            )

                            result.update({
                                'num_assets': num_assets,
                                'population_size': pop_size,
                                'generations': generations,
                                'run_number': run + 1
                            })

                            results.append(result)

                            logger.info(f"✓ HV final: {result['final_hv']:.6f}, "
                                      f"Tempo: {result['execution_time']:.2f}s")

                        except Exception as e:
                            logger.error(f"Erro na execução: {e}")
                            logger.exception("Detalhes:")
                            continue

        if not results:
            logger.error("Nenhum resultado obtido!")
            return pd.DataFrame()

        # Converte para DataFrame
        df_results = pd.DataFrame(results)

        # Salva resultados
        self._save_results(df_results)

        # Gera gráficos
        self._plot_hv_evolution(df_results)
        self._plot_summary_comparison(df_results)

        logger.info(f"\n{'='*70}")
        logger.info("TUNING CONCLUÍDO!")
        logger.info(f"{'='*70}")

        return df_results

    def _run_single_config(
        self,
        ids_assets: List[int],
        pop_size: int,
        generations: int,
        run_number: int,
        risk_level: str
    ) -> Dict:
        """
        Executa uma única configuração e captura métricas detalhadas.

        Returns:
            Dict com:
            - hv_history: Lista de HV por geração
            - final_hv: HV final
            - execution_time: Tempo total
            - convergence_gen: Geração de convergência (ou None)
        """
        start_time = time.time()

        # Cria serviço de otimização
        otimizacao_service = Nsga2OtimizacaoService(
            app=self.app,
            restricted_asset_ids=[],
            risk_level=risk_level,
            asset_ids=ids_assets
        )

        # Cria tracker de convergência
        convergence_tracker = ConvergenceTracker()

        # Executa otimização
        otimizacao_service.optimize(
            generations=generations,
            population_size=pop_size,
            convergence_tracker=convergence_tracker,
            use_optimal_config=False
        )

        execution_time = time.time() - start_time

        # Extrai métricas
        history = convergence_tracker.get_history()
        hv_history = history['hypervolume']

        # HV final
        final_hv = hv_history[-1] if hv_history else 0.0

        # Detecta convergência
        convergence_gen = convergence_tracker.get_convergence_generation()

        # HV máximo atingido (pode ser antes do final no R-NSGA-II)
        max_hv = max(hv_history) if hv_history else 0.0
        max_hv_gen = hv_history.index(max_hv) if hv_history and max_hv in hv_history else None

        return {
            'hv_history': hv_history,
            'final_hv': final_hv,
            'max_hv': max_hv,
            'max_hv_generation': max_hv_gen,
            'execution_time': execution_time,
            'convergence_generation': convergence_gen,
        }

    def _plot_hv_evolution(self, df_results: pd.DataFrame):
        """
        Gera gráficos de evolução de HV para todas as configurações.

        Cria um gráfico por quantidade de ativos, mostrando todas as
        combinações de população e gerações.
        """
        output_dir = Path('rnsga2_tuning_results')
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Agrupa por quantidade de ativos
        for num_assets in df_results['num_assets'].unique():
            df_assets = df_results[df_results['num_assets'] == num_assets]

            fig, ax = plt.subplots(figsize=(14, 8))

            # Plota cada configuração
            for _, row in df_assets.iterrows():
                hv_history = row['hv_history']
                generations = list(range(len(hv_history)))

                label = (f"Pop{row['population_size']}_Gen{row['generations']}_"
                        f"Run{row['run_number']}")

                ax.plot(generations, hv_history, alpha=0.6, linewidth=1.5, label=label)

            ax.set_xlabel('Geração', fontsize=12)
            ax.set_ylabel('Hypervolume', fontsize=12)
            ax.set_title(
                f'Evolução do Hypervolume - {num_assets} Ativos\n'
                f'R-NSGA-II: Note o padrão de convergência focal',
                fontsize=14, fontweight='bold'
            )
            ax.grid(True, alpha=0.3)
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)

            plt.tight_layout()

            filename = output_dir / f'hv_evolution_{num_assets}assets_{timestamp}.png'
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            logger.info(f"📊 Gráfico salvo: {filename}")
            plt.close()

    def _plot_summary_comparison(self, df_results: pd.DataFrame):
        """
        Gera gráficos de comparação consolidada entre configurações.
        """
        output_dir = Path('rnsga2_tuning_results')
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Calcula médias por configuração
        summary = df_results.groupby(['num_assets', 'population_size', 'generations']).agg({
            'final_hv': ['mean', 'std'],
            'max_hv': ['mean', 'std'],
            'execution_time': ['mean', 'std'],
            'convergence_generation': 'mean'
        }).reset_index()

        # Achata nomes de colunas
        summary.columns = ['_'.join(col).strip('_') if col[1] else col[0]
                          for col in summary.columns.values]

        # Gráfico: HV Final vs Tempo de Execução
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        # Subplot 1: HV Final
        ax = axes[0]
        for num_assets in summary['num_assets'].unique():
            subset = summary[summary['num_assets'] == num_assets]

            for pop_size in subset['population_size'].unique():
                data = subset[subset['population_size'] == pop_size]

                ax.errorbar(
                    data['generations'],
                    data['final_hv_mean'],
                    yerr=data['final_hv_std'],
                    marker='o',
                    capsize=5,
                    label=f'{num_assets} assets, Pop {pop_size}'
                )

        ax.set_xlabel('Número de Gerações')
        ax.set_ylabel('Hypervolume Final (média)')
        ax.set_title('HV Final por Configuração')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Subplot 2: Tempo de Execução
        ax = axes[1]
        for num_assets in summary['num_assets'].unique():
            subset = summary[summary['num_assets'] == num_assets]

            for pop_size in subset['population_size'].unique():
                data = subset[subset['population_size'] == pop_size]

                ax.errorbar(
                    data['generations'],
                    data['execution_time_mean'],
                    yerr=data['execution_time_std'],
                    marker='s',
                    capsize=5,
                    label=f'{num_assets} assets, Pop {pop_size}'
                )

        ax.set_xlabel('Número de Gerações')
        ax.set_ylabel('Tempo de Execução (s)')
        ax.set_title('Tempo por Configuração')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        filename = output_dir / f'summary_comparison_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        logger.info(f"📊 Comparação salva: {filename}")
        plt.close()

    def _save_results(self, df_results: pd.DataFrame):
        """
        Salva resultados em CSV.
        """
        output_dir = Path('rnsga2_tuning_results')
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Remove coluna hv_history para salvar CSV (é lista)
        df_to_save = df_results.drop(columns=['hv_history'])

        filename = output_dir / f'tuning_results_{timestamp}.csv'
        df_to_save.to_csv(filename, index=False)
        logger.info(f"💾 Resultados salvos: {filename}")

        # Salva históricos de HV separadamente (JSON)
        import json
        hv_histories = {}
        for idx, row in df_results.iterrows():
            key = f"assets{row['num_assets']}_pop{row['population_size']}_gen{row['generations']}_run{row['run_number']}"
            hv_histories[key] = row['hv_history']

        filename_json = output_dir / f'hv_histories_{timestamp}.json'
        with open(filename_json, 'w') as f:
            json.dump(hv_histories, f, indent=2)
        logger.info(f"💾 Históricos HV salvos: {filename_json}")
