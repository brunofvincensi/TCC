from matplotlib import pyplot as plt
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.config import Config

from services.agmo.asf_calculator import compute_asf
from services.agmo.custom_operators import (
    SimplexSamplingCardConstraint,
    SimplexCrossoverCardConstraint,
    SimplexMutationCardConstraint
)

Config.warnings['not_compiled'] = False

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.rnsga2 import RNSGA2
from pymoo.optimize import minimize
from pymoo.core.callback import Callback

from app import create_app
from models import db, Asset, PriceHistory
from models.asset import AssetType

DEFAULT_GEN_SIZE = 100
DEFAULT_POPULATION_SIZE = 150

MIN_ASSETS = 5

# Reference Points: onde queremos chegar (aspirações no espaço normalizado [0,1])
# - 0.0 = melhor valor possível (min risco / max retorno)
# - 1.0 = pior valor possível (max risco / min retorno)
REFERENCE_POINTS_CONFIG = {
    'conservador': np.array([[0.3, 0.05, 0.05]]),  # Aceita retorno pior, mas quer menos riscos
    'moderado':    np.array([[0.3, 0.2, 0.2]]),  # Balanceado
    'arrojado':    np.array([[0.05, 0.25, 0.25]])   # Quer melhor retorno, aceita mais risco
}

WEIGHTS_CONFIG = np.array([0.33, 0.34, 0.33])


class ConvergenceCallback(Callback):
    """
    Callback do pymoo para rastrear métricas de convergência durante a otimização.
    """

    def __init__(self, convergence_tracker=None, visualize_cvar_first_gen=False,
                 problem=None, output_dir='cvar_visualizations'):
        """
        Args:
            convergence_tracker: Instância de ConvergenceTracker para registrar métricas
            visualize_cvar_first_gen: Se True, cria visualizações do CVaR na primeira geração
            problem: Instância do problema (necessário para visualização)
            output_dir: Diretório onde salvar as visualizações
        """
        super().__init__()
        self.convergence_tracker = convergence_tracker
        self.visualize_cvar_first_gen = visualize_cvar_first_gen
        self.problem = problem
        self.output_dir = output_dir
        self.first_gen_visualized = False

    def notify(self, algorithm):
        """
        Chamado a cada geração pelo pymoo.

        Args:
            algorithm: Instância do algoritmo com população atual
        """
        # Visualizar CVaR na primeira geração
        if self.visualize_cvar_first_gen and not self.first_gen_visualized and algorithm.n_gen == 1:
            self._visualize_first_generation(algorithm)
            self.first_gen_visualized = True

        if self.convergence_tracker is None:
            return

        # Extrai fronteira de Pareto atual
        if hasattr(algorithm, 'opt') and algorithm.opt is not None:
            pareto_front = algorithm.opt.get("F")
        else:
            # Se não há Pareto, usa toda a população
            pareto_front = algorithm.pop.get("F")

        # Fitness de toda a população
        population_fitness = algorithm.pop.get("F")

        # Atualiza o tracker
        self.convergence_tracker.update(
            generation=algorithm.n_gen,
            pareto_front=pareto_front,
            population_fitness=population_fitness
        )

    def _visualize_first_generation(self, algorithm):
        """
        Cria visualizações do CVaR para algumas soluções da primeira geração.
        """
        import os

        if self.problem is None:
            print("  ⚠️  Problema não fornecido, não é possível visualizar CVaR")
            return

        # Criar diretório se não existir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        print(f"\n{'='*70}")
        print(f"📊 GERANDO VISUALIZAÇÕES DE CVaR DA PRIMEIRA GERAÇÃO")
        print(f"{'='*70}")

        # Pegar população da primeira geração
        population = algorithm.pop
        X = population.get("X")  # Soluções (pesos)
        F = population.get("F")  # Objetivos

        indices_to_visualize = []
        labels = []

        # Melhor retorno
        idx_best_return = np.argmin(F[:, 0])
        indices_to_visualize.append(idx_best_return)
        labels.append("Melhor_Retorno")

        # Menor variância
        idx_min_variance = np.argmin(F[:, 1])
        indices_to_visualize.append(idx_min_variance)
        labels.append("Menor_Variancia")

        # Menor CVaR
        idx_min_cvar = np.argmin(F[:, 2])
        indices_to_visualize.append(idx_min_cvar)
        labels.append("Menor_CVaR")

        # Solução aleatória
        np.random.seed(42)
        idx_random = np.random.randint(0, len(X))
        indices_to_visualize.append(idx_random)
        labels.append("Aleatoria")

        # Solução balanceada (mais próxima da mediana em todas as dimensões)
        F_normalized = (F - F.min(axis=0)) / (F.max(axis=0) - F.min(axis=0) + 1e-10)
        distances_to_center = np.linalg.norm(F_normalized - 0.5, axis=1)
        idx_balanced = np.argmin(distances_to_center)
        indices_to_visualize.append(idx_balanced)
        labels.append("Balanceada")

        # Remover duplicatas mantendo a ordem e os labels correspondentes
        seen = set()
        unique_indices = []
        unique_labels = []
        for idx, label in zip(indices_to_visualize, labels):
            if idx not in seen:
                seen.add(idx)
                unique_indices.append(idx)
                unique_labels.append(label)

        print(f"  Visualizando {len(unique_indices)} soluções distintas...")

        # Criar visualizações
        for i, (idx, label) in enumerate(zip(unique_indices, unique_labels), 1):
            weights = X[idx]
            save_path = os.path.join(self.output_dir, f'cvar_gen1_sol{i}_{label}.png')

            print(f"\n  [{i}/{len(unique_indices)}] Solução #{idx} ({label}):")
            print(f"     Retorno: {-F[idx, 0]*100:.2f}%")
            print(f"     Variância: {F[idx, 1]:.6f}")
            print(f"     CVaR: {F[idx, 2]:.4f}")

            self.problem.visualize_cvar(weights, f"{idx}_{label}", save_path)

        print(f"\n  {len(unique_indices)} visualizações salvas em: {self.output_dir}/")
        print(f"{'='*70}\n")

class PersonalizedPortfolioProblem(ElementwiseProblem):

    """
    Problema de otimização de portfólio com 3 objetivos, personalizado
    pelo perfil de risco do usuário.
    """

    def __init__(self, mean_returns, covariance_matrix, returns_history, tickers, risk_level, alpha=0.05, min_weight=0.01, max_weight=0.30):
        num_assets = len(mean_returns)
        # Limites por ativo
        xl = np.full(num_assets, min_weight)
        xu = np.full(num_assets, max_weight)

        super().__init__(n_var=num_assets, n_obj=3, xl=xl, xu=xu)
        self.num_assets = num_assets
        self.mu = mean_returns
        self.cov = covariance_matrix
        self.hist = returns_history
        self.tickers = tickers
        self.risk_level = risk_level
        self.alpha = alpha
        self.min_weight = min_weight
        self.max_weight = max_weight

    def _calculate_cvar(self, weights):
        """
        Calcula o Conditional Value-at-Risk (CVaR) usando método empírico.
        CVaR_α = E[Perda | Perda ≥ VaR_α] ≈ média dos ⌈α·n⌉ piores retornos
        """
        # 1. Calcular retornos e perdas do portfolio
        portfolio_returns = self.hist @ weights
        losses = -portfolio_returns

        # 2. Filtrar valores inválidos
        valid_losses = losses[np.isfinite(losses)]
        n = len(valid_losses)


        # 4. Calcular número de observações na cauda
        k = max(1, int(np.ceil(self.alpha * n)))

        # 5. CVaR = média dos k piores retornos (maiores perdas)
        sorted_losses = np.sort(valid_losses)
        tail = sorted_losses[-k:]  # Sempre exatamente k observações

        return float(np.mean(tail))

    def _evaluate(self, x, out, *args, **kwargs):
        """Avalia uma única carteira (x = vetor de pesos)."""

        # ========== DEBUG ==========
        # print(f"\n{'=' * 70}")
        # print(f"DEBUG _evaluate")
        # print(f"{'=' * 70}")
        #
        # print(f"\nVetor x (RAW - antes da normalização):")
        # print(f"   Shape: {x.shape}")
        # print(f"   Valores: {x}")
        # print(f"   Soma: {x.sum():.6f}")
        # print(f"   Min: {x.min():.6f}")
        # print(f"   Max: {x.max():.6f}")
        #
        # print(f"\n Mapeamento x → Ativos:")
        # for i, (ticker, peso_raw) in enumerate(zip(self.tickers, x)):
        #     print(f"   x[{i}] = {peso_raw:.6f} → {ticker}")

        weights = x

        # --- Objetivos ---
        # Obj 1: Retorno esperado (negativo porque o pymoo minimiza)
        expected_return = -np.dot(weights, self.mu)

        # Obj 2: Risco (variância)
        variance = np.dot(weights, self.cov @ weights)

        # Obj 3: Risco de cauda (CVaR)
        cvar = self._calculate_cvar(weights)

        out["F"] = [expected_return, variance, cvar]

    def visualize_cvar(self, weights, solution_id, save_path=None):
        """
        Visualiza a distribuição de perdas e o cálculo do CVaR para uma solução específica.

        Args:
            weights: Vetor de pesos da solução
            solution_id: Identificador da solução (para título)
            save_path: Caminho para salvar a imagem (opcional)
        """
        # Calcular retornos e perdas
        portfolio_returns = self.hist @ weights
        losses = -portfolio_returns
        valid_losses = losses[np.isfinite(losses)]
        n = len(valid_losses)

        # Calcular CVaR
        k = max(1, int(np.ceil(self.alpha * n)))
        sorted_losses = np.sort(valid_losses)
        var = sorted_losses[-k]  # VaR é o k-ésimo pior retorno
        cvar = np.mean(sorted_losses[-k:])

        # Criar figura
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Subplot 1: Histograma de perdas
        ax1.hist(valid_losses, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
        ax1.axvline(var, color='orange', linestyle='--', linewidth=2, label=f'VaR ({self.alpha*100:.0f}%) = {var:.4f}')
        ax1.axvline(cvar, color='red', linestyle='-', linewidth=2, label=f'CVaR = {cvar:.4f}')

        # Marcar a região da cauda
        ax1.axvspan(var, valid_losses.max(), alpha=0.3, color='red', label='Cauda (piores retornos)')

        ax1.set_xlabel('Perdas (retornos negativos)', fontsize=11)
        ax1.set_ylabel('Frequência', fontsize=11)
        ax1.set_title(f'Distribuição de Perdas', fontsize=12, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)

        # Subplot 2: Pesos da carteira
        # Filtrar apenas ativos com peso significativo
        significant_weights = [(ticker, w) for ticker, w in zip(self.tickers, weights) if w > 0.001]
        significant_weights.sort(key=lambda x: x[1], reverse=True)

        if significant_weights:
            tickers_sig = [t for t, w in significant_weights]
            weights_sig = [w for t, w in significant_weights]

            colors = plt.cm.viridis(np.linspace(0, 1, len(tickers_sig)))
            bars = ax2.barh(tickers_sig, weights_sig, color=colors, edgecolor='black')

            # Adicionar valores nas barras
            for i, (ticker, weight) in enumerate(significant_weights):
                ax2.text(weight, i, f' {weight*100:.1f}%', va='center', fontsize=9)

            ax2.set_xlabel('Peso na Carteira', fontsize=11)
            ax2.set_title(f'Composição da Carteira', fontsize=12, fontweight='bold')
            ax2.set_xlim(0, max(weights_sig) * 1.15)
            ax2.grid(True, alpha=0.3, axis='x')

        # Adicionar informações da solução
        expected_return = -np.dot(weights, self.mu)
        variance = np.dot(weights, self.cov @ weights)

        info_text = (
            f'CVaR: {cvar:.4f}\n'
            f'Nº ativos: {len(significant_weights)}'
        )

        fig.text(0.5, 0.02, info_text, ha='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout(rect=[0, 0.08, 1, 1])

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"  💾 Visualização salva em: {save_path}")

        plt.close()

        return cvar

class Nsga2OtimizacaoService:
    def __init__(self, app, restricted_asset_ids, risk_level, years_period=3, reference_date=None, start_date=None, asset_ids: List[int] = None, show_chart=False,
                 fixed_nadir_point=None, fixed_ideal_point=None):
        """
        Serviço de otimização de carteira usando R-NSGA2 (Reference Point Based NSGA-II).
        """
        self.app = app
        self.restricted_asset_ids = restricted_asset_ids
        self.asset_ids = asset_ids
        self.risk_level = risk_level
        self.years_period = years_period
        self.reference_date = reference_date
        # Data inicial da janela de análise
        self.start_date = start_date
        self.show_chart = show_chart
        self.assets_to_optimize = []
        self.mean_returns = None
        self.covariance_matrix = None
        self.returns_history = None
        self.tickers = None
        self.fixed_nadir_point = fixed_nadir_point
        self.fixed_ideal_point = fixed_ideal_point

    def _prepare_data(self):
        """Busca dados e aplica o ajuste de risco pelo prazo."""
        with self.app.app_context():
            assets_query = db.session.query(Asset).filter(
                ~Asset.id.in_(self.restricted_asset_ids),
                Asset.type == AssetType.STOCK
            )
            if self.asset_ids:
                assets_query = assets_query.filter(Asset.id.in_(self.asset_ids))

            self.assets_to_optimize = assets_query.all()
            if len(self.assets_to_optimize) < MIN_ASSETS:
                raise ValueError(f"São necessários pelo menos {MIN_ASSETS} ativos para a otimização.")

            ids_to_optimize = [a.id for a in self.assets_to_optimize]
            history_query = db.session.query(
                PriceHistory.date,
                PriceHistory.monthly_variation,
                Asset.ticker
            ).join(Asset, PriceHistory.asset_id == Asset.id) \
                .filter(PriceHistory.asset_id.in_(ids_to_optimize))

            # Se reference_date foi fornecida, filtra apenas dados até essa data
            if self.reference_date is not None:
                if self.start_date is not None:
                    history_query = history_query.filter(PriceHistory.date >= self.start_date)

                history_query = history_query.filter(PriceHistory.date <= self.reference_date)
                print(f"Usando dados até {self.reference_date}")

            history_query = history_query.order_by(PriceHistory.date)

            df_history = pd.read_sql(
                history_query.statement,
                con=db.session.connection()
            )
            if df_history.empty:
                raise ValueError("Sem histórico para os ativos selecionados.")

            df_returns_complete = df_history.pivot(
                index='date',
                columns='ticker',
                values='monthly_variation'
            )

            # Analisa quantidade de dados por ativo
            available_assets = df_returns_complete.columns.tolist()
            data_count = df_returns_complete.count()

            print(f"\n Análise de histórico por ativo:")
            print(f"  {'Ticker':<12} {'Meses':>8} {'Status':<20}")
            print(f"  {'-'*40}")

            valid_assets = []
            excluded_assets = []

            # Filtrar ações baseado no horizonte de investimento
            minimum_history_months = int(self.years_period * 12)

            print(f"\n{'=' * 70}")
            print(f"🔍 FILTRANDO ATIVOS POR HISTÓRICO MÍNIMO")
            print(f"{'=' * 70}")
            print(f"  Prazo de investimento: {self.years_period} anos")
            print(f"  Histórico mínimo requerido: {minimum_history_months} meses ({minimum_history_months/12:.1f} anos)")

            for ticker in available_assets:
                available_months = data_count[ticker]

                if available_months >= minimum_history_months:
                    status = "✅ Incluído"
                    valid_assets.append(ticker)
                else:
                    status = f"❌ Excluído ({available_months}/{minimum_history_months})"
                    excluded_assets.append(ticker)

                print(f"  {ticker:<12} {available_months:>8} {status:<20}")

            if len(valid_assets) < MIN_ASSETS:
                raise ValueError(f" Reduza o prazo de investimento (atual: {self.years_period} anos)\n")

            print(f"\n  Resultado do filtro:")
            print(f"     Ativos incluídos: {len(valid_assets)}")
            print(f"     Ativos excluídos: {len(excluded_assets)}")

            if excluded_assets:
                print(f"     Excluídos: {', '.join(excluded_assets)}")

            # Filtra o DataFrame original para incluir apenas ativos válidos
            df_history_filtered = df_history[df_history['ticker'].isin(valid_assets)]

            # Todos os ativos têm histórico >= mínimo, então dropna pode ser usado
            df_returns = df_history_filtered.pivot(
                index='date',
                columns='ticker',
                values='monthly_variation'
            ).dropna()

            self.tickers = df_returns.columns.tolist()

            # Atualiza lista de ativos para otimizar (remove os excluídos)
            self.assets_to_optimize = [
                a for a in self.assets_to_optimize
                if a.ticker in self.tickers
            ]

            # Validação para garantir que todos os tickers em self.tickers têm um ativo correspondente
            asset_tickers = {a.ticker for a in self.assets_to_optimize}
            missing_tickers = set(self.tickers) - asset_tickers
            if missing_tickers:
                raise ValueError(
                    f"Inconsistência detectada: Tickers no DataFrame sem ativo correspondente: {missing_tickers}"
                )

            # Validação para garantir que os tamanhos correspondem
            if len(self.assets_to_optimize) != len(self.tickers):
                raise ValueError(
                    f"Inconsistência detectada: {len(self.assets_to_optimize)} ativos, "
                    f"mas {len(self.tickers)} tickers no DataFrame!"
                )

            # Validação de dados suficientes
            if len(df_returns) < minimum_history_months:
                raise ValueError(f"Dados históricos insuficientes após alinhamento!")

            if self.reference_date is not None:
                print(f"Usando APENAS dados históricos até a data {self.reference_date}")

            print(f"\n  Período histórico: {len(df_returns)} meses")
            print(f"    De {df_returns.index.min()} até {df_returns.index.max()}")

            # Calcular estatísticas
            self.mean_returns = df_returns.mean()
            self.covariance_matrix = df_returns.cov()
            correlation_matrix = df_returns.corr()

            print(f"\n{'=' * 70}")
            print(f"MATRIZ DE CORRELAÇÃO")
            print(f"{'=' * 70}")
            self._print_matrix(correlation_matrix, formato=".3f")

            # Análise da correlação
            self._analyze_correlation(correlation_matrix)

            print(f"\n{'=' * 70}")
            print(f"MATRIZ DE COVARIÂNCIA (Mensal)")
            print(f"{'=' * 70}")
            self._print_matrix(self.covariance_matrix, formato=".6f")

            self.returns_history = df_returns

            # Estatísticas gerais
            print(f"\n{'=' * 70}")
            print(f"ESTATÍSTICAS GERAIS")
            print(f"{'=' * 70}")
            print(f"  Retorno médio mensal: {self.mean_returns.mean() * 100:.2f}%")
            print(f"  Volatilidade média: {np.sqrt(np.diag(self.covariance_matrix)).mean() * 100:.2f}%")

            # Estatísticas por ativo
            print(f"\nPor Ativo:")
            for ticker in df_returns.columns:
                ret = self.mean_returns[ticker] * 100
                vol = np.sqrt(self.covariance_matrix.loc[ticker, ticker]) * 100
                sharpe = ret / vol if vol > 0 else 0
                print(f"     {ticker:8s} | Ret: {ret:6.2f}% | Vol: {vol:6.2f}% | Sharpe: {sharpe:5.2f}")

            print(f"\n  Dados preparados com sucesso!")

    def _analyze_correlation(self, correlation_matrix):
        """
        Analisa e printa insights da matriz de correlação
        """
        print(f"\n  Análise de Correlação:")

        # Extrair apenas metade superior (sem diagonal)
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
        correlations = correlation_matrix.where(mask).stack()

        # Estatísticas
        print(f"     Correlação Média: {correlations.mean():.3f}")
        print(f"     Correlação Máxima: {correlations.max():.3f}")
        print(f"     Correlação Mínima: {correlations.min():.3f}")

        # Pares com correlação muito alta (> 0.8)
        high_correlations = correlations[correlations > 0.8].sort_values(ascending=False)
        if len(high_correlations) > 0:
            print(f"\n  Pares com Correlação ALTA (> 0.8):")
            for pair, corr in high_correlations.head(5).items():
                print(f"     {pair[0]:8s} ↔ {pair[1]:8s}: {corr:.3f}")

        # Pares com correlação negativa (< -0.3)
        negative_correlations = correlations[correlations < -0.3].sort_values()
        if len(negative_correlations) > 0:
            print(f"\n  Pares com Correlação NEGATIVA (< -0.3) [Boa diversificação!]:")
            for pair, corr in negative_correlations.head(5).items():
                print(f"     {pair[0]:8s} ↔ {pair[1]:8s}: {corr:.3f}")

        # Aviso se tudo muito correlacionado
        if correlations.mean() > 0.7:
            print(f"\n  ATENÇÃO: Ativos muito correlacionados (média {correlations.mean():.2f})")
            print(f"     Considere adicionar ativos de outros setores para diversificação.")

    def _choose_best_portfolio(self, objectives, solutions):
        """
        Seleciona a melhor carteira da Fronteira de Pareto usando Achievement Scalarizing Function (ASF).

        Usa os mesmos reference points do R-NSGA2 para garantir consistência:
        o algoritmo busca soluções próximas ao reference point, e a seleção final
        escolhe a solução mais próxima a esse mesmo ponto.

        Menor ASF = mais próximo do reference point = melhor solução
        """
        print(f"\n{'='*80}")
        print(f"SELEÇÃO DA MELHOR CARTEIRA - PERFIL '{self.risk_level.upper()}'")
        print(f"{'='*80}")

        # Usa configuração centralizada (constantes do módulo)
        ref_point = REFERENCE_POINTS_CONFIG[self.risk_level][0]  # [0] extrai o primeiro array da matriz
        weights = WEIGHTS_CONFIG

        # Informações sobre o reference point
        print(f"\nREFERENCE POINT:")
        print(f"   Perfil: {self.risk_level}")
        print(f"   Retorno: {ref_point[0]:.3f}")
        print(f"   Variância: {ref_point[1]:.3f}")
        print(f"   CVaR: {ref_point[2]:.3f}")

        # Análise dos objetivos NÃO normalizados
        print(f"\n{'─'*80}")
        print(f"ANÁLISE DOS OBJETIVOS (VALORES ORIGINAIS):")
        print(f"{'─'*80}")
        print(f"   {'Objetivo':<20} {'Mínimo':>15} {'Máximo':>15} {'Amplitude':>15}")
        print(f"   {'-'*70}")

        obj_names = ['Retorno (negativo)', 'Variância', 'CVaR']
        for i in range(objectives.shape[1]):
            col = objectives[:, i]
            min_val, max_val = col.min(), col.max()
            amplitude = max_val - min_val
            print(f"   {obj_names[i]:<20} {min_val:>15.6f} {max_val:>15.6f} {amplitude:>15.6f}")

        # Normaliza os objetivos para [0, 1]
        objectives_normalized = objectives.copy()
        normalization_info = []

        for i in range(objectives.shape[1]):
            col = objectives[:, i]
            min_val, max_val = col.min(), col.max()

            if max_val - min_val > 1e-10:
                objectives_normalized[:, i] = (col - min_val) / (max_val - min_val)
                normalization_info.append((min_val, max_val))
            else:
                objectives_normalized[:, i] = 0.0
                normalization_info.append((min_val, max_val))

        # Calcula ASF para cada solução
        asf_values = [compute_asf(obj, ref_point, weights)
                      for obj in objectives_normalized]

        # Seleciona solução com MENOR ASF (mais próxima do reference point)
        best_idx = np.argmin(asf_values)

        # Informações sobre as soluções e ASF
        print(f"\n{'─'*80}")
        print(f"CÁLCULO DA ASF (Achievement Scalarizing Function):")
        print(f"{'─'*80}")
        print(f"   Total de soluções na Fronteira de Pareto: {len(objectives)}")

        # Mostra estatísticas dos valores de ASF
        asf_array = np.array(asf_values)
        print(f"\n   Estatísticas dos valores de ASF:")
        print(f"   {'Métrica':<20} {'Valor':>15}")
        print(f"   {'-'*40}")
        print(f"   {'Mínimo (MELHOR)':<20} {asf_array.min():>15.6f}")
        print(f"   {'Máximo (PIOR)':<20} {asf_array.max():>15.6f}")
        print(f"   {'Média':<20} {asf_array.mean():>15.6f}")
        print(f"   {'Mediana':<20} {np.median(asf_array):>15.6f}")
        print(f"   {'Desvio Padrão':<20} {asf_array.std():>15.6f}")

        # Mostra as top 5 soluções
        top_5_indices = np.argsort(asf_values)[:5]

        print(f"\n{'─'*80}")
        print(f"TOP 5 SOLUÇÕES (menor ASF = melhor):")
        print(f"{'─'*80}")
        print(f"   {'Rank':<6} {'ASF':<12} {'Retorno':<12} {'Variância':<12} {'CVaR':<12} {'Ativos':>8}")
        print(f"   {'-'*75}")

        for rank, idx in enumerate(top_5_indices, 1):
            asf_val = asf_values[idx]
            ret = -objectives[idx, 0]  # Negativo porque está negado
            var = objectives[idx, 1]
            cvar = objectives[idx, 2]
            n_assets = np.sum(solutions[idx] > 0.001)

            marker = "👑" if rank == 1 else f"{rank}."
            print(f"   {marker:<6} {asf_val:<12.6f} {ret:<12.6f} {var:<12.6f} {cvar:<12.6f} {n_assets:>8}")

        # Informações detalhadas da solução escolhida
        print(f"\n{'='*80}")
        print(f"SOLUÇÃO ESCOLHIDA (Índice {best_idx}):")
        print(f"{'='*80}")

        best_obj = objectives[best_idx]
        best_obj_norm = objectives_normalized[best_idx]
        best_asf = asf_values[best_idx]

        print(f"\n   Valores Originais:")
        print(f"   {'Objetivo':<20} {'Valor':>15}")
        print(f"   {'-'*40}")
        print(f"   {'Retorno Esperado':<20} {-best_obj[0]:>15.6f}")
        print(f"   {'Variância':<20} {best_obj[1]:>15.6f}")
        print(f"   {'CVaR':<20} {best_obj[2]:>15.6f}")

        print(f"\n   Valores Normalizados [0,1]:")
        print(f"   {'Objetivo':<20} {'Normalizado':>15} {'Reference':>15} {'Diferença':>15}")
        print(f"   {'-'*70}")
        for i, name in enumerate(obj_names):
            diff = abs(best_obj_norm[i] - ref_point[i])
            print(f"   {name:<20} {best_obj_norm[i]:>15.6f} {ref_point[i]:>15.6f} {diff:>15.6f}")

        print(f"\n   ASF (distância ao reference point): {best_asf:.6f}")
        print(f"   Número de ativos na carteira: {np.sum(solutions[best_idx] > 0.001)}")

        # Gera visualização gráfica
        self._visualize_portfolio_selection(
            objectives, objectives_normalized, solutions,
            ref_point, weights, asf_values, best_idx,
            normalization_info
        )

        print(f"{'='*80}\n")

        return solutions[best_idx]

    def _visualize_portfolio_selection(self, objectives, objectives_normalized, solutions,
                                       ref_point, weights, asf_values, best_idx, normalization_info):
        """
        Cria visualização detalhada do processo de seleção da melhor carteira.
        """
        import os
        from datetime import datetime

        # Criar diretório se não existir
        output_dir = 'portfolio_selection_visualizations'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'portfolio_selection_{self.risk_level}_{timestamp}.png'
        filepath = os.path.join(output_dir, filename)

        # Criar figura com 6 subplots
        fig = plt.figure(figsize=(20, 14))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # Título principal
        fig.suptitle(f'Processo de Seleção da Melhor Carteira - Perfil: {self.risk_level.upper()}',
                    fontsize=18, fontweight='bold', y=0.98)

        # ===== SUBPLOT 1: Fronteira de Pareto 3D (Objetivos Originais) =====
        ax1 = fig.add_subplot(gs[0, :2], projection='3d')

        # Plotar todas as soluções
        scatter = ax1.scatter(objectives[:, 1], -objectives[:, 0], objectives[:, 2],
                            c=asf_values, cmap='viridis', s=50, alpha=0.6, edgecolors='black', linewidth=0.5)

        # Destacar a melhor solução
        ax1.scatter([objectives[best_idx, 1]], [-objectives[best_idx, 0]], [objectives[best_idx, 2]],
                   c='red', s=300, marker='*', edgecolors='black', linewidth=2, label='Melhor Solução', zorder=10)

        ax1.set_xlabel('Variância (Risco)', fontsize=10, labelpad=10)
        ax1.set_ylabel('Retorno Esperado', fontsize=10, labelpad=10)
        ax1.set_zlabel('CVaR (Risco de Cauda)', fontsize=10, labelpad=10)
        ax1.set_title('Fronteira de Pareto (Valores Originais)', fontsize=12, fontweight='bold', pad=20)
        ax1.legend(loc='upper left', fontsize=9)

        cbar1 = plt.colorbar(scatter, ax=ax1, pad=0.1, shrink=0.6)
        cbar1.set_label('Valor ASF', fontsize=9)

        # ===== SUBPLOT 2: Espaço Normalizado 3D =====
        ax3 = fig.add_subplot(gs[1, :2], projection='3d')

        # Plotar soluções normalizadas
        scatter3 = ax3.scatter(objectives_normalized[:, 1], objectives_normalized[:, 0],
                              objectives_normalized[:, 2], c=asf_values, cmap='viridis',
                              s=50, alpha=0.6, edgecolors='black', linewidth=0.5)

        # Reference point
        ax3.scatter([ref_point[1]], [ref_point[0]], [ref_point[2]],
                   c='gold', s=100, marker='D', edgecolors='black', linewidth=2,
                   label='Reference Point', zorder=10)

        # Melhor solução
        ax3.scatter([objectives_normalized[best_idx, 1]], [objectives_normalized[best_idx, 0]],
                   [objectives_normalized[best_idx, 2]], c='red', s=150, marker='*',
                   edgecolors='black', linewidth=2, label='Melhor Solução', zorder=10)

        # Linha conectando reference point à melhor solução
        ax3.plot([ref_point[1], objectives_normalized[best_idx, 1]],
                [ref_point[0], objectives_normalized[best_idx, 0]],
                [ref_point[2], objectives_normalized[best_idx, 2]],
                'r--', linewidth=2, alpha=0.7, label='Distância ASF')

        ax3.set_xlabel('Variância Norm.', fontsize=10, labelpad=10)
        ax3.set_ylabel('Retorno Norm.', fontsize=10, labelpad=10)
        ax3.set_zlabel('CVaR Norm.', fontsize=10, labelpad=10)
        ax3.set_title('Espaço Normalizado [0,1] com Reference Point', fontsize=12, fontweight='bold', pad=20)
        ax3.legend(loc='upper left', fontsize=8)

        # Salvar figura
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"\n📊 Visualização salva em: {os.path.abspath(filepath)}")

    def _print_matrix(self, matrix, formato=".3f"):
        """
        Printa matriz formatada com cores

        Args:
            matrix: DataFrame pandas com a matriz
            titulo: Título da matriz
            formato: Formato dos números (ex: ".3f")
        """
        tickers = matrix.columns.tolist()
        n = len(tickers)

        # Cabeçalho
        header = "        "
        for ticker in tickers:
            header += f"{ticker:>10s} "
        print(header)
        print("  " + "-" * (11 * n + 8))

        # Linhas
        for i, row_ticker in enumerate(tickers):
            line = f"  {row_ticker:6s} |"

            for j, col_ticker in enumerate(tickers):
                value = matrix.iloc[i, j]

                # Colorir diagonal
                if i == j:
                    line += f" {value:>9{formato}}*"  # Asterisco na diagonal
                else:
                    line += f" {value:>9{formato}} "

            print(line)

        print()

    def optimize(self, population_size: int = None, generations: int = None,
                 crossover_eta: float = 15.0, mutation_eta: float = 15.0,
                 convergence_tracker=None, use_optimal_config: bool = True, max_assets: int = 20,
                 visualize_cvar: bool = False, cvar_output_dir: str = 'cvar_visualizations'):

        if max_assets is not None and max_assets < MIN_ASSETS:
            raise ValueError(f"São necessários pelo menos {MIN_ASSETS} ativos para a otimização.")

        self._prepare_data()

        num_assets = len(self.assets_to_optimize)

        generations, population_size = self.get_hyperparameters(generations, num_assets, population_size, use_optimal_config)

        problem = self.get_problem()

        algorithm = self.get_algorithm(crossover_eta, mutation_eta, population_size, max_assets)

        callback = self.get_callback(convergence_tracker, visualize_cvar, problem, cvar_output_dir)

        termination = self.get_termination(generations)

        print(f"\n{'='*70}")
        print(f"Executando a otimização do R-NSGA2")
        print(f"{'='*70}")
        print(f"  Algoritmo: R-NSGA2 (Reference Point Based)")
        print(f"  População: {population_size}")
        print(f"  Gerações: {generations}")
        print(f"  Perfil de risco: {self.risk_level}")
        print(f"  Número de ativos disponíveis: {num_assets}")

        result = minimize(problem, algorithm, termination,
                           callback=callback, verbose=True)
        print("Otimização R-NSGA2 concluída.")

        if result.X is None:
            raise ValueError("O algoritmo não conseguiu encontrar nenhuma solução.")

        # Seleciona a melhor carteira da fronteira de Pareto
        optimal_weights = self._choose_best_portfolio(result.opt.get("F"), result.opt.get("X"))

        # Garante que os tamanhos correspondem
        if len(optimal_weights) != len(self.tickers):
            raise ValueError(
                f"Inconsistência detectada: optimal_weights tem {len(optimal_weights)} elementos, "
                f"mas self.tickers tem {len(self.tickers)} elementos!"
            )

        if self.show_chart:
            F = result.F

            # Limites fixos para comparação entre diferentes execuções
            X_LIMIT = (0.001, 0.012)  # Variância (risco)
            Y_LIMIT = (0.014, 0.032)  # Retorno esperado
            CVAR_LIMIT = (0.075, 0.10)  # CVaR

            fig, ax = plt.subplots(figsize=(10, 8))

            scatter = ax.scatter(
                F[:, 1],  # Variância (eixo X)
                -F[:, 0],  # Retorno (eixo Y, invertido)
                c=F[:, 2],  # CVaR (cor)
                cmap='viridis',
                s=80,  # Tamanho dos pontos
                alpha=0.7,
                vmin=CVAR_LIMIT[0],  # Limite mínimo da escala de cor
                vmax=CVAR_LIMIT[1]  # Limite máximo da escala de cor
            )

            # Aplicar limites fixos aos eixos
            ax.set_xlim(X_LIMIT)
            ax.set_ylim(Y_LIMIT)

            ax.set_xlabel("Risco (variância)", fontsize=11)
            ax.set_ylabel("Retorno esperado", fontsize=11)
            ax.set_title(f"Fronteira de Pareto - R-NSGA-II (Perfil: {self.risk_level})", fontsize=12)
            ax.grid(True, alpha=0.3)

            plt.colorbar(scatter, ax=ax, label="CVaR")
            plt.tight_layout()
            plt.show()

        # Os optimal_weights estão na ordem de self.tickers (colunas do DataFrame)
        # Mas self.assets_to_optimize pode estar em ordem diferente
        weights_by_ticker = {ticker: float(weight) for ticker, weight in zip(self.tickers, optimal_weights)}

        final_composition = []
        for asset in self.assets_to_optimize:
            weight = weights_by_ticker.get(asset.ticker, 0)
            if weight > 0.001:  # Ignora pesos insignificantes
                final_composition.append({
                    'asset_id': asset.id,
                    'ticker': asset.ticker,
                    'name': asset.name,
                    'weight': weight
                })

        # Normalizar pesos para soma = 1
        weights_sum = sum(item['weight'] for item in final_composition)
        for item in final_composition:
            item['weight'] = item['weight'] / weights_sum

        # Calcula métricas da carteira otimizada
        expected_return = np.dot(optimal_weights, self.mean_returns.values)
        portfolio_risk = np.sqrt(np.dot(optimal_weights, self.covariance_matrix.values @ optimal_weights))
        sharpe_ratio = expected_return / portfolio_risk if portfolio_risk > 0 else 0

        # Adiciona métricas ao resultado
        metrics = {
            'retorno_esperado_mensal': float(expected_return),
            'retorno_esperado_anual': float(expected_return * 12),
            'volatilidade_mensal': float(portfolio_risk),
            'volatilidade_anual': float(portfolio_risk * np.sqrt(12)),
            'sharpe_ratio': float(sharpe_ratio)
        }

        # Apresentação formatada dos resultados
        self._print_optimization_result(final_composition, metrics)

        # Retorna as informações adicionais sobre o período usado (útil para backtest)
        optimization_result = {
            'composicao': final_composition,
            'metricas': metrics,
            'data_referencia': self.reference_date,
            'periodo_inicio': self.returns_history.index.min(),
            'periodo_fim': self.returns_history.index.max(),
            'num_meses': len(self.returns_history),
            'modo_backtest': self.reference_date is not None,
            'max_ativos_enforced': max_assets is not None,
            'max_ativos': max_assets,
            'hyperparameters_used': {
                'population_size': population_size,
                'generations': generations,
                'crossover_eta': crossover_eta,
                'mutation_eta': mutation_eta,
                'num_assets': num_assets,
                'max_assets': max_assets
            }
        }

        return optimization_result

    def get_problem(self) -> PersonalizedPortfolioProblem:
        return PersonalizedPortfolioProblem(
            mean_returns=self.mean_returns.values,
            covariance_matrix=self.covariance_matrix.values,
            returns_history=self.returns_history.values,
            tickers=self.tickers,
            risk_level=self.risk_level
        )

    def get_algorithm(self, crossover_eta: float, mutation_eta: float,
                     population_size: int, max_assets: int = None) -> NSGA2:
        """
        Cria algoritmo R-NSGA2 com operadores apropriados e pontos de referência
        customizados por perfil de risco.

        R-NSGA2 guia a busca durante a otimização usando pontos de referência,
        direcionando as soluções para regiões específicas da fronteira de Pareto.
        """

        # Operadores customizados com restrição de cardinalidade
        sampling = SimplexSamplingCardConstraint(max_assets=max_assets)
        crossover = SimplexCrossoverCardConstraint(max_assets=max_assets, eta=crossover_eta)
        mutation = SimplexMutationCardConstraint(max_assets=max_assets, eta=mutation_eta)

        # Usa configuração centralizada (constantes do módulo)
        ref_points = REFERENCE_POINTS_CONFIG.get(self.risk_level)

        # Parâmetros comuns a todas as execuções
        common_args = dict(
            ref_points=ref_points,
            pop_size=population_size,
            crossover=crossover,
            mutation=mutation,
            sampling=sampling,
            epsilon=0.01,
            extreme_points_as_reference_points=False,
            weights=WEIGHTS_CONFIG,
        )

        # Se bounds fixos foram fornecidos → usar bounded normalization
        if self.fixed_ideal_point is not None and self.fixed_nadir_point is not None:
            return RNSGA2(
                **common_args,
                normalization="bounded",
                ideal_point=self.fixed_ideal_point,
                nadir_point=self.fixed_nadir_point,
            )

        # Caso contrário → normalização dinâmica por geração
        return RNSGA2(
            **common_args,
            normalization="front",
        )

        # return NSGA2(pop_size=population_size, crossover=crossover,
        #     mutation=mutation,
        #     sampling=sampling)

    def get_hyperparameters(self, generations: int | None, num_assets: int, population_size: int | None,
                           use_optimal_config: bool):
        if use_optimal_config and (population_size is None or generations is None):
            print(f"\n{'=' * 70}")
            print(f"Buscando configuração ótima para {num_assets} ativos")
            print(f"{'=' * 70}")

            population_size, generations = self.get_hyperparameter_config(num_assets, population_size, generations)

        # Garante valores padrão se ainda None
        if population_size is None:
            population_size = DEFAULT_POPULATION_SIZE
        if generations is None:
            generations = DEFAULT_GEN_SIZE
        return generations, population_size

    """
    Busca os hiperparâmetros com base da quantidade de ativos da carteira
    """
    def get_hyperparameter_config(self, num_assets, population_size, generations):
        try:
            from models import HyperparameterConfig

            with self.app.app_context():
                optimal_config = HyperparameterConfig.get_optimal_config(
                    num_assets=num_assets,
                    risk_level=self.risk_level
                )

                if optimal_config:
                    if population_size is None:
                        population_size = optimal_config.population_size
                    if generations is None:
                        generations = optimal_config.generations
                    print(f"  Configuração ótima encontrada no banco!")
                    print(f"  População: {population_size}")
                    print(f"  Gerações: {generations}")
                else:
                    print(f"  Configuração não encontrada. Usando valores padrão.")
                    if population_size is None:
                        population_size = DEFAULT_POPULATION_SIZE
                    if generations is None:
                        generations = DEFAULT_GEN_SIZE

        except Exception as e:
            print(f"  Erro ao buscar configuração: {e}")
            if population_size is None:
                population_size = DEFAULT_POPULATION_SIZE
            if generations is None:
                generations = DEFAULT_GEN_SIZE

        return population_size, generations

    def get_termination(self, generations):
        return ('n_gen', generations)


    def get_callback(self, convergence_tracker, visualize_cvar=False,
                    problem=None, cvar_output_dir='cvar_visualizations') -> ConvergenceCallback:
        return ConvergenceCallback(
            convergence_tracker=convergence_tracker,
            visualize_cvar_first_gen=visualize_cvar,
            problem=problem,
            output_dir=cvar_output_dir
        )

    def _print_optimization_result(self, composition: List[Dict], metrics: Dict):
        """
        Apresenta os resultados da otimização de forma formatada e profissional.

        Args:
            composition: Lista com composição da carteira
            metrics: Dicionário com métricas calculadas
        """
        print(f"\n{'='*80}")
        print(f"📊 RESULTADO DA OTIMIZAÇÃO")
        print(f"{'='*80}")

        # 1. Composição da Carteira (Tabela)
        print(f"\n💼 COMPOSIÇÃO DA CARTEIRA ({len(composition)} ativos):")
        print(f"{'─'*80}")
        print(f"{'#':<4} {'Ticker':<10} {'Nome':<35} {'Peso':>10} {'Barra':>15}")
        print(f"{'─'*80}")

        # Ordena por peso (maior para menor)
        sorted_composition = sorted(composition, key=lambda x: x['weight'], reverse=True)

        for i, asset in enumerate(sorted_composition, 1):
            ticker = asset['ticker']
            name = asset['name'][:32] + '...' if len(asset['name']) > 35 else asset['name']
            weight = asset['weight']
            weight_pct = weight * 100

            # Barra visual
            bar_size = int(weight * 50)  # Máximo 50 caracteres
            bar = '█' * bar_size

            print(f"{i:<4} {ticker:<10} {name:<35} {weight_pct:>9.2f}% {bar:>15}")

        print(f"{'─'*80}")
        print(f"{'TOTAL':<50} {100.0:>9.2f}%")
        print(f"{'─'*80}")

        # 2. Métricas de Performance
        print(f"\n📈 MÉTRICAS DE PERFORMANCE:")
        print(f"{'─'*80}")

        monthly_ret = metrics['retorno_esperado_mensal'] * 100
        annual_ret = metrics['retorno_esperado_anual'] * 100
        monthly_vol = metrics['volatilidade_mensal'] * 100
        annual_vol = metrics['volatilidade_anual'] * 100
        sharpe = metrics['sharpe_ratio']

        print(f"   Retorno Esperado (mensal):  {monthly_ret:>8.2f}%")
        print(f"   Retorno Esperado (anual):   {annual_ret:>8.2f}%")
        print(f"   Volatilidade (mensal):      {monthly_vol:>8.2f}%")
        print(f"   Volatilidade (anual):       {annual_vol:>8.2f}%")
        print(f"   Índice de Sharpe:           {sharpe:>8.2f}")

        print(f"{'─'*80}")

        print(f"\n✅ Otimização concluída com sucesso!")
        print(f"{'='*80}\n")

