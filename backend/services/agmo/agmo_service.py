from matplotlib import pyplot as plt
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.config import Config
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
from models.ativo import AssetType

DEFAULT_GEN_SIZE = 100
DEFAULT_POPULATION_SIZE = 100

MIN_ASSETS = 5

# Reference Points: onde queremos chegar (aspirações no espaço normalizado [0,1])
# - 0.0 = melhor valor possível (min risco / max retorno)
# - 1.0 = pior valor possível (max risco / min retorno)
REFERENCE_POINTS_CONFIG = {
    'conservador': np.array([[0.3, 0.05, 0.05]]),  # Aceita retorno pior, mas quer riscos ~0
    'moderado':    np.array([[0.3, 0.2, 0.2]]),  # Balanceado
    'arrojado':    np.array([[0.05, 0.3, 0.3]])   # Quer melhor retorno, aceita mais risco
}

# Weights para Achievement Scalarizing Function (ASF)
WEIGHTS_CONFIG = {
    'conservador': np.array([0.20, 0.40, 0.40]),  # Desvios em risco são 2x mais graves
    'moderado':    np.array([0.33, 0.34, 0.33]),  # Equilibrado
    'arrojado':    np.array([0.50, 0.25, 0.25])   # Desvios em retorno são 2x mais graves
}

# Pontos Ideal e Nadir TEÓRICOS para normalização consistente do R-Hypervolume
# Baseados em limites realistas para portfólios de ações brasileiras
# Formato: [retorno_esperado_mensal, volatilidade_mensal, max_drawdown]
#
# IDEAL POINT (melhor caso teórico):
# - Retorno esperado: -3% ao mês (negativo porque minimizamos -retorno)
# - Volatilidade: 0.5% ao mês (muito estável)
# - Max Drawdown: 2% (perda máxima pequena)
IDEAL_POINT_PORTFOLIO = np.array([-0.03, 0.005, 0.02])

# NADIR POINT (pior caso aceitável):
# - Retorno esperado: +1.5% ao mês (ruim, positivo porque minimizamos -retorno)
# - Volatilidade: 2.5% ao mês (muito volátil)
# - Max Drawdown: 18% (perda máxima grande)
NADIR_POINT_PORTFOLIO = np.array([0.015, 0.025, 0.18])
# ===============================================================

class ConvergenceCallback(Callback):
    """
    Callback do pymoo para rastrear métricas de convergência durante a otimização.
    """

    def __init__(self, convergence_tracker=None):
        """
        Args:
            convergence_tracker: Instância de ConvergenceTracker para registrar métricas
        """
        super().__init__()
        self.convergence_tracker = convergence_tracker

    def notify(self, algorithm):
        """
        Chamado a cada geração pelo pymoo.

        Args:
            algorithm: Instância do algoritmo com população atual
        """
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

class PersonalizedPortfolioProblem(ElementwiseProblem):

    """
    Problema de otimização de portfólio com 3 objetivos, personalizado
    pelo perfil de risco do usuário.
    """

    def __init__(self, mean_returns, covariance_matrix, returns_history, tickers, risk_level, max_assets, alpha=0.05, min_weight=0.01, max_weight=0.30):
        num_assets = len(mean_returns)
        # Limites por ativo
        xl = np.full(num_assets, min_weight)
        xu = np.full(num_assets, max_weight)

        portfolio_num_assets = min(num_assets, max_assets)

        n_ieq_constr = 1 if portfolio_num_assets >= 10 else 0

        # HHI (Herfindahl-Hirschman Index) Thresholds por Perfil de Risco
        # HHI = Σ(wi²), onde N_eff = 1/HHI (número efetivo de ativos)
        # Valores baseados em literatura de concentração de mercado e diversificação
        self.hhi_thresholds = {
            'conservador': 0.12,  # N_eff ≈ 8.3 ativos (baixa concentração)
            'moderado': 0.15,     # N_eff ≈ 6.7 ativos (concentração moderada)
            'arrojado': 0.20      # N_eff ≈ 5.0 ativos (concentração aceitável)
        }
        super().__init__(n_var=num_assets,
                         n_obj=3,
                         n_ieq_constr=0,
                         n_eq_constr=0, xl=xl, xu=xu)
        self.num_assets = num_assets
        self.portfolio_num_assets = portfolio_num_assets
        self.mu = mean_returns
        self.cov = covariance_matrix
        self.hist = returns_history
        self.tickers = tickers
        self.risk_level = risk_level
        self.alpha = alpha
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.hhi_max = self.hhi_thresholds.get(risk_level, 0.15)
        self.max_assets = max_assets

    def _calculate_cvar(self, weights):
        """
        Calcula o Conditional Value-at-Risk (CVaR) usando método empírico.

        CVaR_α = E[Perda | Perda ≥ VaR_α] ≈ média dos ⌈α·n⌉ piores retornos

        Referências:
            - Rockafellar & Uryasev (2000). "Optimization of conditional value-at-risk"
            - Acerbi & Tasche (2002). "On the coherence of expected shortfall"
        """
        # 1. Calcular retornos e perdas do portfolio
        portfolio_returns = self.hist @ weights
        losses = -portfolio_returns

        # 2. Filtrar valores inválidos
        valid_losses = losses[np.isfinite(losses)]
        n = len(valid_losses)

        # 3. Proteção para amostras pequenas
        if n < 20:
            return float(np.std(valid_losses))

        # 4. Calcular número de observações na cauda
        k = max(1, int(np.ceil(self.alpha * n)))

        # 5. CVaR = média dos k piores retornos (maiores perdas)
        sorted_losses = np.sort(valid_losses)
        tail = sorted_losses[-k:]  # Sempre exatamente k observações

        cvar = float(np.mean(tail))

        return cvar

    def _evaluate(self, x, out, *args, **kwargs):
        """Avalia uma única carteira"""

        # ========== DEBUG ==========
        # print(f"\n{'=' * 70}")
        # print(f"🔍 DEBUG _evaluate")
        # print(f"{'=' * 70}")
        #
        # print(f"\n📊 Vetor x (RAW - antes da normalização):")
        # print(f"   Shape: {x.shape}")
        # print(f"   Valores: {x}")
        # print(f"   Soma: {x.sum():.6f}")
        # print(f"   Min: {x.min():.6f}")
        # print(f"   Max: {x.max():.6f}")
        #
        # print(f"\n Mapeamento x → Ativos:")
        # for i, (ticker, peso_raw) in enumerate(zip(self.tickers, x)):
        #     print(f"   x[{i}] = {peso_raw:.6f} → {ticker}")

        """Avalia uma única carteira (x = vetor de pesos)."""
        weights = x

        # --- Objetivos ---
        # Obj 1: Retorno esperado (negativo porque o pymoo minimiza)
        expected_return = -np.dot(weights, self.mu)

        # Obj 2: Risco (variância)
        variance = np.dot(weights, self.cov @ weights)

        # Obj 3: Risco de cauda (CVaR)
        cvar = self._calculate_cvar(weights)

        out["F"] = [expected_return, variance, cvar]

        # if self.portfolio_num_assets >= 10:
        #     hhi = np.sum(weights ** 2)
        #     hhi_constraint = hhi - self.hhi_max
        #     out["G"] = [hhi_constraint]

class Nsga2OtimizacaoService:
    def __init__(self, app, restricted_asset_ids, risk_level, years_period=5, reference_date=None, start_date=None, asset_ids: List[int] = None, show_chart=False):
        """
        Serviço de otimização de carteira usando R-NSGA2 (Reference Point Based NSGA-II).

        R-NSGA2 permite guiar a busca durante a otimização usando pontos de referência
        customizados por perfil de risco, ao contrário do NSGA2 tradicional que só
        permite seleção após gerar todas as soluções não-dominadas.

        Args:
            app: Instância da aplicação Flask
            restricted_asset_ids: Lista de IDs de ativos a serem excluídos da otimização
            risk_level: Perfil de risco ('conservador', 'moderado', 'arrojado')
                        - conservador: Prioriza minimizar riscos (variância e CVaR)
                        - moderado: Busca equilíbrio entre retorno e risco
                        - arrojado: Prioriza maximizar retorno
            years_period: Prazo do investimento em anos
            reference_date: Data de referência para backtest (opcional). Se fornecida,
                           usa apenas dados históricos até essa data. Formato: datetime.date

        Referências:
            - Deb & Sundar (2006). "Reference point based multi-objective optimization using evolutionary algorithms"
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

            # Filtrar ações antes do pivot baseado no horizonte de investimento
            minimum_history_months = int(self.years_period * 12)

            print(f"\n{'=' * 70}")
            print(f"🔍 FILTRANDO ATIVOS POR HISTÓRICO MÍNIMO")
            print(f"{'=' * 70}")
            print(f"  Prazo de investimento: {self.years_period} anos")
            print(f"  Histórico mínimo requerido: {minimum_history_months} meses ({minimum_history_months/12:.1f} anos)")

            # Pivot sem dropna para analisar cada ativo
            df_returns_complete = df_history.pivot(
                index='date',
                columns='ticker',
                values='monthly_variation'
            )

            # Analisa quantidade de dados por ativo
            available_assets = df_returns_complete.columns.tolist()
            data_count = df_returns_complete.count()

            print(f"\n  📊 Análise de histórico por ativo:")
            print(f"  {'Ticker':<12} {'Meses':>8} {'Status':<20}")
            print(f"  {'-'*40}")

            valid_assets = []
            excluded_assets = []

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

            print(f"\n  ✅ Resultado do filtro:")
            print(f"     Ativos incluídos: {len(valid_assets)}")
            print(f"     Ativos excluídos: {len(excluded_assets)}")

            if excluded_assets:
                print(f"     Excluídos: {', '.join(excluded_assets)}")

            # Filtra o DataFrame original para incluir apenas ativos válidos
            df_history_filtered = df_history[df_history['ticker'].isin(valid_assets)]

            # Agora faz o pivot e dropna com segurança
            # Todos os ativos têm histórico >= mínimo, então dropna é consistente
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

            print(f"\n  ✅ Período histórico: {len(df_returns)} meses")
            print(f"  📅 De {df_returns.index.min()} até {df_returns.index.max()}")

            # Calcular estatísticas
            self.mean_returns = df_returns.mean()
            self.covariance_matrix = df_returns.cov()
            correlation_matrix = df_returns.corr()

            print(f"\n{'=' * 70}")
            print(f"📊 MATRIZ DE CORRELAÇÃO")
            print(f"{'=' * 70}")
            self._print_matrix(correlation_matrix, formato=".3f")

            # Análise da correlação
            self._analyze_correlation(correlation_matrix)

            print(f"\n{'=' * 70}")
            print(f"📊 MATRIZ DE COVARIÂNCIA (Mensal)")
            print(f"{'=' * 70}")
            self._print_matrix(self.covariance_matrix, formato=".6f")

            self.returns_history = df_returns

            # Estatísticas gerais
            print(f"\n{'=' * 70}")
            print(f"📊 ESTATÍSTICAS GERAIS")
            print(f"{'=' * 70}")
            print(f"  Retorno médio mensal: {self.mean_returns.mean() * 100:.2f}%")
            print(f"  Volatilidade média: {np.sqrt(np.diag(self.covariance_matrix)).mean() * 100:.2f}%")

            # Estatísticas por ativo
            print(f"\n  📈 Por Ativo:")
            for ticker in df_returns.columns:
                ret = self.mean_returns[ticker] * 100
                vol = np.sqrt(self.covariance_matrix.loc[ticker, ticker]) * 100
                sharpe = ret / vol if vol > 0 else 0
                print(f"     {ticker:8s} | Ret: {ret:6.2f}% | Vol: {vol:6.2f}% | Sharpe: {sharpe:5.2f}")

            print(f"\n  ✅ Dados preparados com sucesso!")

    def _analyze_correlation(self, correlation_matrix):
        """
        Analisa e printa insights da matriz de correlação
        """
        print(f"\n  🔍 Análise de Correlação:")

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
            print(f"\n  ⚠️  Pares com Correlação ALTA (> 0.8):")
            for pair, corr in high_correlations.head(5).items():
                print(f"     {pair[0]:8s} ↔ {pair[1]:8s}: {corr:.3f}")

        # Pares com correlação negativa (< -0.3)
        negative_correlations = correlations[correlations < -0.3].sort_values()
        if len(negative_correlations) > 0:
            print(f"\n  ✅ Pares com Correlação NEGATIVA (< -0.3) [Boa diversificação!]:")
            for pair, corr in negative_correlations.head(5).items():
                print(f"     {pair[0]:8s} ↔ {pair[1]:8s}: {corr:.3f}")

        # Aviso se tudo muito correlacionado
        if correlations.mean() > 0.7:
            print(f"\n  ⚠️  ATENÇÃO: Ativos muito correlacionados (média {correlations.mean():.2f})")
            print(f"     Considere adicionar ativos de outros setores para diversificação.")

    def _choose_best_portfolio(self, objectives, solutions):
        """
        Seleciona a melhor carteira da Fronteira de Pareto usando Achievement Scalarizing Function (ASF).

        Usa os mesmos reference points do R-NSGA2 para garantir consistência:
        o algoritmo busca soluções próximas ao reference point, e a seleção final
        escolhe a solução mais próxima a esse mesmo ponto.

        ASF(x, ref) = max_i { (f_i(x) - z_i) / w_i }
        Menor ASF = mais próximo do reference point = melhor solução
        """
        print(f"Selecionando a melhor solução para o perfil '{self.risk_level}'...")

        # Usa configuração centralizada (constantes do módulo)
        ref_point = REFERENCE_POINTS_CONFIG[self.risk_level][0]  # [0] extrai o primeiro array da matriz
        weights = WEIGHTS_CONFIG[self.risk_level]

        # Normaliza os objetivos para [0, 1]
        objectives_normalized = objectives.copy()
        for i in range(objectives.shape[1]):
            col = objectives[:, i]
            min_val, max_val = col.min(), col.max()

            if max_val - min_val > 1e-10:
                objectives_normalized[:, i] = (col - min_val) / (max_val - min_val)
            else:
                objectives_normalized[:, i] = 0.0

        # Calcula ASF para cada solução
        asf_values = []
        for obj in objectives_normalized:
            # ASF = max_i { (obj[i] - ref[i]) / weight[i] }
            # Menor ASF = mais próximo do reference point
            asf_components = (obj - ref_point) / weights
            asf = np.max(asf_components)
            asf_values.append(asf)

        asf_values = np.array(asf_values)

        # Seleciona solução com MENOR ASF (mais próxima do reference point)
        best_idx = np.argmin(asf_values)

        print(f"✅ Solução selecionada: índice {best_idx} (ASF = {asf_values[best_idx]:.4f})")
        print(f"   Objetivos normalizados: {objectives_normalized[best_idx]}")
        print(f"   Reference point alvo: {ref_point}")

        return solutions[best_idx]

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
                 crossover_eta: float = 10.0, mutation_eta: float = 10.0,
                 convergence_tracker=None, use_optimal_config: bool = True,
                 enable_early_stopping=False, max_assets: int = 20):

        if max_assets is not None and max_assets < MIN_ASSETS:
            raise ValueError(f"São necessários pelo menos {MIN_ASSETS} ativos para a otimização.")

        self._prepare_data()

        num_assets = len(self.assets_to_optimize)

        generations, population_size = self.get_hyperparameters(generations, num_assets, population_size, use_optimal_config)

        problem = self.get_problem(max_assets)

        algorithm = self.get_algorithm(crossover_eta, mutation_eta, population_size, max_assets)

        callback = self.get_callback(convergence_tracker)

        termination = self.get_termination(generations, enable_early_stopping)

        print(f"\n{'='*70}")
        print(f"🚀 EXECUTANDO OTIMIZAÇÃO R-NSGA2")
        print(f"{'='*70}")
        print(f"  Algoritmo: R-NSGA2 (Reference Point Based)")
        print(f"  População: {population_size}")
        print(f"  Gerações: {generations}")
        print(f"  Perfil de risco: {self.risk_level}")
        print(f"  Número de ativos disponíveis: {num_assets}")
        if max_assets:
            print(f"  ⚠️  RESTRIÇÃO DE CARDINALIDADE: máx. {max_assets} ativos na carteira")
            print(f"     Usando operadores genéticos com card-constraint")
        print(f"{'='*70}\n")

        result = minimize(problem, algorithm, termination,
                           callback=callback, verbose=True)
        print("🏁 Otimização R-NSGA2 concluída.")

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
            ax.set_title(f"Fronteira de Pareto - R-NSGA2 (Perfil: {self.risk_level})", fontsize=12)
            ax.grid(True, alpha=0.3)

            plt.colorbar(scatter, ax=ax, label="CVaR")
            plt.tight_layout()
            plt.show()

        # Os optimal_weights estão na ordem de self.tickers (colunas do DataFrame)
        # Mas self.assets_to_optimize pode estar em ordem diferente
        weights_by_ticker = {ticker: float(weight) for ticker, weight in zip(self.tickers, optimal_weights)}

        print(f"\n{'='*70}")
        print(f"🔗 MAPEAMENTO PESOS → ATIVOS")
        print(f"{'='*70}")
        print(f"  Ordem self.tickers (usado na otimização):")
        for i, ticker in enumerate(self.tickers):
            print(f"    [{i}] {ticker:8s} → peso: {optimal_weights[i]:.6f}")
        print(f"\n  Ordem self.assets_to_optimize (usado no resultado):")
        for i, asset in enumerate(self.assets_to_optimize):
            weight = weights_by_ticker.get(asset.ticker, 0)
            print(f"    [{i}] {asset.ticker:8s} → peso: {weight:.6f}")
        print(f"{'='*70}\n")

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

    def get_problem(self, max_assets) -> PersonalizedPortfolioProblem:
        return PersonalizedPortfolioProblem(
            mean_returns=self.mean_returns.values,
            covariance_matrix=self.covariance_matrix.values,
            returns_history=self.returns_history.values,
            tickers=self.tickers,
            risk_level=self.risk_level,
            max_assets=max_assets
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
        weights = WEIGHTS_CONFIG.get(self.risk_level)

        return RNSGA2(
            ref_points=ref_points,
            pop_size=population_size,
            crossover=crossover,
            mutation=mutation,
            sampling=sampling,
            epsilon=0.01,  # Controla o tamanho da região de interesse em torno dos pontos de referência
            normalization='front',  # Normaliza baseado na fronteira atual
            extreme_points_as_reference_points=False,  # Usa apenas nossos pontos customizados
            weights=weights  # Pesos variam por perfil de risco
        )

        # return NSGA2(pop_size=population_size, crossover=crossover,
        #     mutation=mutation,
        #     sampling=sampling)

    def get_hyperparameters(self, generations: int | None, num_assets: int, population_size: int | None,
                           use_optimal_config: bool):
        if use_optimal_config and (population_size is None or generations is None):
            print(f"\n{'=' * 70}")
            print(f"🔍 BUSCANDO CONFIGURAÇÃO ÓTIMA PARA {num_assets} ATIVOS")
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

                    print(f"  ✅ Configuração ótima encontrada no banco!")
                    print(f"  📊 População: {population_size}")
                    print(f"  📊 Gerações: {generations}")
                    print(f"  📅 Tuning realizado em: {optimal_config.tuning_date.strftime('%Y-%m-%d')}")
                    print(f"  🎯 Hypervolume médio: {optimal_config.hypervolume_mean:.6f}")
                    print(f"  ⏱️  Tempo médio esperado: {optimal_config.execution_time_mean:.2f}s")
                else:
                    print(f"  ⚠️  Configuração não encontrada. Usando valores padrão.")
                    if population_size is None:
                        population_size = DEFAULT_POPULATION_SIZE
                    if generations is None:
                        generations = DEFAULT_GEN_SIZE

        except Exception as e:
            print(f"  ⚠️  Erro ao buscar configuração: {e}")
            if population_size is None:
                population_size = DEFAULT_POPULATION_SIZE
            if generations is None:
                generations = DEFAULT_GEN_SIZE

        return population_size, generations

    def get_termination(self, generations, enable_early_stopping):
        if enable_early_stopping:
            from pymoo.termination import DefaultMultiObjectiveTermination

            termination = DefaultMultiObjectiveTermination(
                ftol=0.005, # Tolerância na mudança dos objetivos
                period=40,  # Janela de análise (gerações)
                n_max_gen=generations
            )

            print(f"  ⚡ Parada adaptativa:")
            print(f"     Máximo: {generations} gerações (do banco)")
            print(f"     Critério: ftol=0.005 (pode parar antes)")
            return termination
        else:
            print(f"  🎯 Gerações fixas: {generations} (do banco)")
            return ('n_gen', generations)

    def get_callback(self, convergence_tracker) -> ConvergenceCallback:
        if convergence_tracker is not None:
            callback = ConvergenceCallback(convergence_tracker)
        else:
            callback = ConvergenceCallback(None)
        return callback

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

def _calculate_portfolio_return(app, portfolio: List[Dict],
                               start_date,
                               end_date) -> Tuple[float, List[float], pd.DataFrame]:
    """
    Calcula o retorno de uma carteira em um período específico

    Args:
        portfolio: Lista com composição da carteira
        start_date: Data inicial do período
        end_date: Data final do período

    Returns:
        Tupla com (retorno_total, lista_de_retornos_mensais, dataframe_com_datas)
    """
    with app.app_context():
        # Buscar retornos dos ativos no período
        asset_ids = [item['asset_id'] for item in portfolio]

        query = db.session.query(
            PriceHistory.date,
            PriceHistory.monthly_variation,
            Asset.ticker
        ).join(Asset, PriceHistory.asset_id == Asset.id) \
            .filter(
            PriceHistory.asset_id.in_(asset_ids),
            PriceHistory.date > start_date,
            PriceHistory.date <= end_date
        ) \
            .order_by(PriceHistory.date)

        df = pd.read_sql(query.statement, con=db.session.connection())

        if df.empty:
            return 0.0, [], pd.DataFrame()

        # Pivot para ter retornos por ativo
        df_returns = df.pivot(
            index='date',
            columns='ticker',
            values='monthly_variation'
        )

        # Calcular retorno ponderado da carteira
        weights_dict = {item['ticker']: item['weight'] for item in portfolio}

        monthly_returns = []
        dates = []
        for date_idx in df_returns.index:
            month_return = 0
            for ticker in df_returns.columns:
                if ticker in weights_dict:
                    asset_ret = df_returns.loc[date_idx, ticker]
                    if pd.notna(asset_ret):
                        month_return += weights_dict[ticker] * asset_ret

            monthly_returns.append(month_return)
            dates.append(date_idx)

        # Calcular retorno acumulado
        total_return = (1 + pd.Series(monthly_returns)).prod() - 1

        # Criar DataFrame com resultados
        df_result = pd.DataFrame({
            'data': dates,
            'retorno_mensal': monthly_returns
        })
        df_result.set_index('data', inplace=True)

        return float(total_return), monthly_returns, df_result


def save_backtest_chart(portfolio: List[Dict],
                            start_date,
                            end_date,
                            app,
                            file_name: str = None,
                            volatility_window: int = 6) -> str:
    """
    Gera e salva gráfico mostrando o retorno acumulado e a volatilidade da carteira ao longo do tempo.

    Args:
        portfolio: Lista com composição da carteira otimizada
        start_date: Data inicial do backtest
        end_date: Data final do backtest
        app: Instância da aplicação Flask
        file_name: Nome do arquivo para salvar (opcional, gera automaticamente se None)
        volatility_window: Janela em meses para cálculo da volatilidade rolling (padrão: 6)

    Returns:
        Caminho completo do arquivo salvo
    """
    import os
    from datetime import datetime

    print(f"\n{'='*70}")
    print(f"📊 GERANDO GRÁFICO DE BACKTEST")
    print(f"{'='*70}")

    # Calcular retornos da carteira
    total_return, monthly_returns, df_returns = _calculate_portfolio_return(
        app, portfolio, start_date, end_date
    )

    if df_returns.empty:
        print("  ⚠️  Sem dados para gerar gráfico")
        return None

    # Calcular retorno acumulado
    df_returns['retorno_acumulado'] = (1 + df_returns['retorno_mensal']).cumprod() - 1

    # Calcular volatilidade rolling (anualizada)
    df_returns['volatilidade_rolling'] = (
        df_returns['retorno_mensal']
        .rolling(window=volatility_window, min_periods=1)
        .std() * np.sqrt(12) * 100  # Anualizada e em %
    )

    # Configurar figura com 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('Backtest da Carteira Otimizada', fontsize=16, fontweight='bold')

    # Gráfico 1: Retorno Acumulado
    ax1.plot(df_returns.index, df_returns['retorno_acumulado'] * 100,
             linewidth=2.5, color='#2E86AB', marker='o', markersize=4, label='Retorno Acumulado')
    ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5, linewidth=1)
    ax1.fill_between(df_returns.index, 0, df_returns['retorno_acumulado'] * 100,
                     alpha=0.3, color='#2E86AB')
    ax1.set_title('Retorno Acumulado da Carteira ao Longo do Tempo', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Data', fontsize=10)
    ax1.set_ylabel('Retorno Acumulado (%)', fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='upper left', fontsize=9)

    # Adicionar anotação com retorno total
    final_return = df_returns['retorno_acumulado'].iloc[-1] * 100
    ax1.annotate(f'Retorno Total: {final_return:+.2f}%',
                xy=(df_returns.index[-1], final_return),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                fontsize=9, fontweight='bold')

    # Gráfico 2: Volatilidade Rolling
    ax2.plot(df_returns.index, df_returns['volatilidade_rolling'],
             linewidth=2.5, color='#F18F01', marker='s', markersize=4, label=f'Volatilidade Rolling ({volatility_window} meses)')
    ax2.fill_between(df_returns.index, 0, df_returns['volatilidade_rolling'],
                     alpha=0.3, color='#F18F01')
    ax2.set_title(f'Volatilidade da Carteira ao Longo do Tempo (janela de {volatility_window} meses)',
                  fontsize=12, fontweight='bold')
    ax2.set_xlabel('Data', fontsize=10)
    ax2.set_ylabel('Volatilidade Anualizada (%)', fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='upper left', fontsize=9)

    # Adicionar linha de média de volatilidade
    mean_vol = df_returns['volatilidade_rolling'].mean()
    ax2.axhline(y=mean_vol, color='green', linestyle='--', alpha=0.7, linewidth=1.5,
                label=f'Média: {mean_vol:.2f}%')
    ax2.legend(loc='upper left', fontsize=9)

    plt.tight_layout()

    # Definir nome do arquivo
    if file_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f'backtest_carteira_{timestamp}.png'

    # Garantir que o diretório existe
    directory = os.path.dirname(file_name) if os.path.dirname(file_name) else '.'
    if not os.path.exists(directory) and directory != '.':
        os.makedirs(directory, exist_ok=True)

    # Salvar gráfico
    full_path = os.path.abspath(file_name)
    plt.savefig(full_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"  ✅ Gráfico salvo em: {full_path}")
    print(f"  📊 Métricas:")
    print(f"     Retorno Total: {final_return:+.2f}%")
    print(f"     Volatilidade Média: {mean_vol:.2f}%")
    print(f"     Sharpe Ratio: {(final_return/mean_vol):.3f}" if mean_vol > 0 else "     Sharpe Ratio: N/A")
    print(f"{'='*70}\n")

    return full_path


def optimize_current_portfolio(app):
    service = Nsga2OtimizacaoService(app, [1, 10], "conservador", 10, show_chart=True)
    result = service.optimize(max_assets=10, use_optimal_config=False)

    # Informações adicionais
    print(f"\n📅 INFORMAÇÕES DO PERÍODO:")
    print(f"   Dados históricos: {result['periodo_inicio']} até {result['periodo_fim']}")
    print(f"   Total de meses: {result['num_meses']}")
    print(f"   Hiperparâmetros: Pop={result['hyperparameters_used']['population_size']}, "
          f"Gen={result['hyperparameters_used']['generations']}")

def backtest(app):
    from datetime import date
    backtest_date = date(2015, 1, 1)
    backtest_service = Nsga2OtimizacaoService(app, [1, 10], "moderado", 10, reference_date=backtest_date, show_chart=True)
    backtest_portfolio = backtest_service.optimize(max_assets=10)

    # Informações do backtest
    print(f"\n📅 INFORMAÇÕES DO BACKTEST:")
    print(f"   Data de referência: {backtest_portfolio['data_referencia']}")
    print(f"   Dados históricos: {backtest_portfolio['periodo_inicio']} até {backtest_portfolio['periodo_fim']}")
    print(f"   Total de meses: {backtest_portfolio['num_meses']}")
    print(f"   Hiperparâmetros: Pop={backtest_portfolio['hyperparameters_used']['population_size']}, "
          f"Gen={backtest_portfolio['hyperparameters_used']['generations']}")

    end_date = date(2025, 10, 20)
    period_return, monthly_returns, df_returns = _calculate_portfolio_return(
        app,
        backtest_portfolio['composicao'],
        backtest_date,
        end_date
    )

    print(f"     Retorno Acumulado: {period_return * 100:+.2f}%")

    # Gerar e salvar gráfico do backtest
    save_backtest_chart(
        backtest_portfolio['composicao'],
        backtest_date,
        end_date,
        app,
        file_name='backtest_exemplo.png'
    )


def main():
    """Função principal que interpreta os comandos."""
    app = create_app()

    # Exemplo 1: Otimização normal (sem backtest)
    optimize_current_portfolio(app)

    # Exemplo 2: Otimização com backtest (usando dados até uma data específica)
   # backtest(app)


if __name__ == "__main__":
    main()

