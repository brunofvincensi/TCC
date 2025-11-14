from matplotlib import pyplot as plt
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.config import Config
from services.agmo.custom_operators import (
    SimplexSamplingCardConstraint,
    SimplexCrossoverCardConstraint,
    SimplexMutationCardConstraint
)
from services.agmo.config import AGMOConfig

Config.warnings['not_compiled'] = False

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.rnsga2 import RNSGA2
from pymoo.optimize import minimize
from pymoo.core.callback import Callback

from app import create_app
from models import db, Ativo, HistoricoPrecos
from models.ativo import TipoAtivo

class ConvergenceCallback(Callback):
    """Rastreia métricas de convergência durante a otimização."""

    def __init__(self, convergence_tracker=None):
        super().__init__()
        self.convergence_tracker = convergence_tracker

    def notify(self, algorithm):
        if self.convergence_tracker is None:
            return

        if hasattr(algorithm, 'opt') and algorithm.opt is not None:
            pareto_front = algorithm.opt.get("F")
        else:
            pareto_front = algorithm.pop.get("F")

        population_fitness = algorithm.pop.get("F")

        self.convergence_tracker.update(
            generation=algorithm.n_gen,
            pareto_front=pareto_front,
            population_fitness=population_fitness
        )

class PersonalizedPortfolioProblem(ElementwiseProblem):
    """Otimização multiobjetivo de portfólio com restrições por perfil de risco."""

    def __init__(self, retornos_medios, matriz_covariancia, historico_retornos, tickers, nivel_risco, max_ativos,
                 alpha=None, peso_min=None, peso_max=None):
        alpha = alpha or AGMOConfig.ALPHA_CVAR
        peso_min = peso_min or AGMOConfig.PESO_MIN_DEFAULT
        peso_max = peso_max or AGMOConfig.PESO_MAX_DEFAULT

        n_ativos = len(retornos_medios)
        xl = np.full(n_ativos, peso_min)
        xu = np.full(n_ativos, peso_max)

        n_ativos_carteira = min(n_ativos, max_ativos)
        n_ieq_constr = 1 if n_ativos_carteira >= 10 else 0

        super().__init__(n_var=n_ativos,
                         n_obj=3,
                         n_ieq_constr=n_ieq_constr,
                         n_eq_constr=0, xl=xl, xu=xu)
        self.n_ativos = n_ativos
        self.n_ativos_carteira = n_ativos_carteira
        self.mu = retornos_medios
        self.cov = matriz_covariancia
        self.hist = historico_retornos
        self.tickers = tickers
        self.nivel_risco = nivel_risco
        self.alpha = alpha
        self.peso_min = peso_min
        self.peso_max = peso_max
        self.hhi_max = AGMOConfig.get_hhi_threshold(nivel_risco)
        self.max_ativos = max_ativos

    def _calcular_cvar(self, pesos):
        """Calcula CVaR (Conditional Value-at-Risk) usando método empírico."""
        retornos_portfolio = self.hist @ pesos
        perdas = -retornos_portfolio
        perdas_validas = perdas[np.isfinite(perdas)]
        n = len(perdas_validas)

        if n < AGMOConfig.MIN_SAMPLES_CVAR:
            return float(np.std(perdas_validas))

        k = max(1, int(np.ceil(self.alpha * n)))
        perdas_ordenadas = np.sort(perdas_validas)
        cauda = perdas_ordenadas[-k:]

        return float(np.mean(cauda))

    def _evaluate(self, x, out, *args, **kwargs):
        """Avalia carteira calculando objetivos: retorno, variância e CVaR."""
        pesos = x

        retorno = -np.dot(pesos, self.mu)
        variancia = np.dot(pesos, self.cov @ pesos)
        cvar = self._calcular_cvar(pesos)

        out["F"] = [retorno, variancia, cvar]

        if self.n_ativos_carteira >= 10:
            hhi = np.sum(pesos ** 2)
            restricao_hhi = hhi - self.hhi_max
            out["G"] = [restricao_hhi]

class Nsga2OtimizacaoService:
    """Serviço de otimização usando R-NSGA2 com pontos de referência por perfil de risco."""

    def __init__(self, app, ids_ativos_restringidos, nivel_risco, prazo_anos=5, data_referencia=None, data_inicio=None, ids_ativos: List[int] = None, exibir_grafico=False):
        self.app = app
        self.ids_ativos_restringidos = ids_ativos_restringidos
        self.ids_ativos = ids_ativos
        self.nivel_risco = nivel_risco
        self.prazo_anos = prazo_anos
        self.data_referencia = data_referencia
        self.data_inicio = data_inicio
        self.exibir_grafico = exibir_grafico
        self.ativos_para_otimizar = []
        self.retornos_medios = None
        self.matriz_covariancia = None
        self.historico_retornos = None
        self.tickers = None

    def _preparar_dados(self):
        """Busca dados históricos e calcula estatísticas."""
        with self.app.app_context():
            query_ativos = db.session.query(Ativo).filter(
                ~Ativo.id.in_(self.ids_ativos_restringidos),
                Ativo.tipo == TipoAtivo.ACAO
            )
            if self.ids_ativos:
                query_ativos = query_ativos.filter(Ativo.id.in_(self.ids_ativos))

            self.ativos_para_otimizar = query_ativos.all()
            if len(self.ativos_para_otimizar) < AGMOConfig.MIN_ATIVOS:
                raise ValueError(f"São necessários pelo menos {AGMOConfig.MIN_ATIVOS} ativos do tipo 'Ação' para a otimização.")

            ids_para_otimizar = [a.id for a in self.ativos_para_otimizar]
            query_historico = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
                .filter(HistoricoPrecos.id_ativo.in_(ids_para_otimizar))

            if self.data_referencia is not None:
                if self.data_inicio is not None:
                    query_historico = query_historico.filter(HistoricoPrecos.data >= self.data_inicio)
                query_historico = query_historico.filter(HistoricoPrecos.data <= self.data_referencia)

            query_historico = query_historico.order_by(HistoricoPrecos.data)

            df_historico = pd.read_sql(
                query_historico.statement,
                con=db.session.connection()
            )
            if df_historico.empty:
                raise ValueError("Sem histórico para os ativos selecionados.")

            historico_minimo_meses = max(int(self.prazo_anos * 12), AGMOConfig.MINIMO_MESES_HISTORICO)

            df_retornos_completo = df_historico.pivot(
                index='data',
                columns='ticker',
                values='variacao_mensal'
            )

            ativos_disponiveis = df_retornos_completo.columns.tolist()
            contagem_dados = df_retornos_completo.count()

            ativos_validos = [t for t in ativos_disponiveis if contagem_dados[t] >= historico_minimo_meses]
            ativos_excluidos = [t for t in ativos_disponiveis if contagem_dados[t] < historico_minimo_meses]

            if len(ativos_validos) < AGMOConfig.MIN_ATIVOS:
                raise ValueError(
                    f"Ativos insuficientes após filtro de histórico. "
                    f"Requerido: {AGMOConfig.MIN_ATIVOS}, Disponível: {len(ativos_validos)}"
                )

            df_historico_filtrado = df_historico[df_historico['ticker'].isin(ativos_validos)]
            df_retornos = df_historico_filtrado.pivot(
                index='data',
                columns='ticker',
                values='variacao_mensal'
            ).dropna()

            self.tickers = df_retornos.columns.tolist()
            self.ativos_para_otimizar = [a for a in self.ativos_para_otimizar if a.ticker in self.tickers]

            tickers_ativos = {a.ticker for a in self.ativos_para_otimizar}
            tickers_faltantes = set(self.tickers) - tickers_ativos
            if tickers_faltantes:
                raise ValueError(f"Tickers sem ativo correspondente: {tickers_faltantes}")

            if len(self.ativos_para_otimizar) != len(self.tickers):
                raise ValueError(
                    f"Inconsistência: {len(self.ativos_para_otimizar)} ativos, "
                    f"mas {len(self.tickers)} tickers"
                )

            if len(df_retornos) < historico_minimo_meses:
                raise ValueError(
                    f"Dados insuficientes após alinhamento. "
                    f"Encontrados: {len(df_retornos)}, Necessário: {historico_minimo_meses}"
                )

            self.retornos_medios = df_retornos.mean()
            self.matriz_covariancia = df_retornos.cov()
            self.historico_retornos = df_retornos

    def _escolher_melhor_carteira(self, objetivos, solucoes):
        """Seleciona melhor carteira da Fronteira de Pareto baseado no perfil de risco."""
        objetivos = objetivos.copy()
        objetivos[:, 0] = -objetivos[:, 0]

        objetivos_norm = np.zeros_like(objetivos)
        for i in range(objetivos.shape[1]):
            col = objetivos[:, i]
            min_val, max_val = col.min(), col.max()
            if max_val - min_val > 1e-10:
                objetivos_norm[:, i] = (col - min_val) / (max_val - min_val)
            else:
                objetivos_norm[:, i] = 0.5

        pesos = AGMOConfig.get_pesos_selecao(self.nivel_risco)

        scores = ((objetivos_norm[:, 0] * pesos[0]) - (objetivos_norm[:, 1] * pesos[1])
                  - (objetivos_norm[:, 2] * pesos[2]))

        idx_melhor = np.argmax(scores)
        return solucoes[idx_melhor]

    def otimizar(self, population_size: int = None, generations: int = None,
                 crossover_eta: float = None, mutation_eta: float = None,
                 convergence_tracker=None, use_optimal_config: bool = True,
                 enable_early_stopping=False, max_ativos: int = 20):
        """Executa otimização de carteira usando R-NSGA2."""

        crossover_eta = crossover_eta or AGMOConfig.DEFAULT_CROSSOVER_ETA
        mutation_eta = mutation_eta or AGMOConfig.DEFAULT_MUTATION_ETA

        if max_ativos is not None and max_ativos < AGMOConfig.MIN_ATIVOS:
            raise ValueError(f"São necessários pelo menos {AGMOConfig.MIN_ATIVOS} ativos do tipo 'Ação' para a otimização.")

        self._preparar_dados()

        num_ativos = len(self.ativos_para_otimizar)

        generations, population_size = self.get_hiperparameters(generations, num_ativos, population_size, use_optimal_config)

        problem = self.get_problem(max_ativos)
        algorithm = self.get_algorithm(crossover_eta, mutation_eta, population_size, max_ativos)
        callback = self.get_callback(convergence_tracker)
        termination = self.get_termination(generations, enable_early_stopping)

        resultado = minimize(problem, algorithm, termination, callback=callback, verbose=True)

        if resultado.X is None:
            raise ValueError("O algoritmo não conseguiu encontrar nenhuma solução.")

        pesos_otimos = self._escolher_melhor_carteira(resultado.opt.get("F"), resultado.opt.get("X"))

        if len(pesos_otimos) != len(self.tickers):
            raise ValueError(
                f"Inconsistência: pesos_otimos={len(pesos_otimos)}, tickers={len(self.tickers)}"
            )

        if self.exibir_grafico:
            F = resultado.F
            LIMITE_X = (0.001, 0.012)
            LIMITE_Y = (0.014, 0.032)
            LIMITE_CVAR = (0.075, 0.10)

            fig, ax = plt.subplots(figsize=(10, 8))
            scatter = ax.scatter(F[:, 1], -F[:, 0], c=F[:, 2], cmap='viridis',
                               s=80, alpha=0.7, vmin=LIMITE_CVAR[0], vmax=LIMITE_CVAR[1])
            ax.set_xlim(LIMITE_X)
            ax.set_ylim(LIMITE_Y)
            ax.set_xlabel("Risco (variância)", fontsize=11)
            ax.set_ylabel("Retorno esperado", fontsize=11)
            ax.set_title(f"Fronteira de Pareto - R-NSGA2 (Perfil: {self.nivel_risco})", fontsize=12)
            ax.grid(True, alpha=0.3)
            plt.colorbar(scatter, ax=ax, label="CVaR")
            plt.tight_layout()
            plt.show()

        pesos_por_ticker = {ticker: float(peso) for ticker, peso in zip(self.tickers, pesos_otimos)}

        composicao_final = []
        for ativo in self.ativos_para_otimizar:
            peso = pesos_por_ticker.get(ativo.ticker, 0)
            if peso > AGMOConfig.PESO_MINIMO_COMPOSICAO:
                composicao_final.append({
                    'id_ativo': ativo.id,
                    'ticker': ativo.ticker,
                    'nome': ativo.nome,
                    'peso': peso
                })

        soma_pesos = sum(item['peso'] for item in composicao_final)
        for item in composicao_final:
            item['peso'] = item['peso'] / soma_pesos

        retorno_esperado = np.dot(pesos_otimos, self.retornos_medios.values)
        risco_carteira = np.sqrt(np.dot(pesos_otimos, self.matriz_covariancia.values @ pesos_otimos))
        sharpe_ratio = retorno_esperado / risco_carteira if risco_carteira > 0 else 0

        metricas = {
            'retorno_esperado_mensal': float(retorno_esperado),
            'retorno_esperado_anual': float(retorno_esperado * 12),
            'volatilidade_mensal': float(risco_carteira),
            'volatilidade_anual': float(risco_carteira * np.sqrt(12)),
            'sharpe_ratio': float(sharpe_ratio)
        }

        resultado = {
            'composicao': composicao_final,
            'metricas': metricas,
            'data_referencia': self.data_referencia,
            'periodo_inicio': self.historico_retornos.index.min(),
            'periodo_fim': self.historico_retornos.index.max(),
            'num_meses': len(self.historico_retornos),
            'modo_backtest': self.data_referencia is not None,
            'max_ativos_enforced': max_ativos is not None,
            'max_ativos': max_ativos,
            'hyperparameters_used': {
                'population_size': population_size,
                'generations': generations,
                'crossover_eta': crossover_eta,
                'mutation_eta': mutation_eta,
                'num_ativos': num_ativos,
                'max_ativos': max_ativos
            }
        }

        return resultado

    def get_problem(self, max_ativos) -> PersonalizedPortfolioProblem:
        return PersonalizedPortfolioProblem(
            retornos_medios=self.retornos_medios.values,
            matriz_covariancia=self.matriz_covariancia.values,
            historico_retornos=self.historico_retornos.values,
            tickers=self.tickers,
            nivel_risco=self.nivel_risco,
            max_ativos=max_ativos
        )

    def get_algorithm(self, crossover_eta: float, mutation_eta: float,
                     population_size: int, max_ativos: int = None) -> NSGA2:
        """Configura algoritmo R-NSGA2 com operadores customizados."""
        sampling = SimplexSamplingCardConstraint(max_assets=max_ativos)
        crossover = SimplexCrossoverCardConstraint(max_assets=max_ativos, eta=crossover_eta)
        mutation = SimplexMutationCardConstraint(max_assets=max_ativos, eta=mutation_eta)

        ref_points = AGMOConfig.get_reference_points(self.nivel_risco)

        return RNSGA2(
            ref_points=ref_points,
            pop_size=population_size,
            crossover=crossover,
            mutation=mutation,
            sampling=sampling,
            epsilon=AGMOConfig.RNSGA2_EPSILON,
            normalization='front',
            extreme_points_as_reference_points=False,
            weights=AGMOConfig.RNSGA2_WEIGHTS
        )

    def get_hiperparameters(self, generations: int | None, num_ativos: int, population_size: int | None,
                           use_optimal_config: bool):
        if use_optimal_config and (population_size is None or generations is None):
            population_size, generations = self.get_hyperparameter_config(num_ativos, population_size, generations)

        if population_size is None:
            population_size = AGMOConfig.DEFAULT_POPULATION_SIZE
        if generations is None:
            generations = AGMOConfig.DEFAULT_GENERATIONS
        return generations, population_size

    def get_hyperparameter_config(self, num_ativos, population_size, generations):
        try:
            from models import HyperparameterConfig

            with self.app.app_context():
                optimal_config = HyperparameterConfig.get_optimal_config(
                    num_ativos=num_ativos,
                    nivel_risco=self.nivel_risco
                )

                if optimal_config:
                    if population_size is None:
                        population_size = optimal_config.population_size
                    if generations is None:
                        generations = optimal_config.generations
                else:
                    if population_size is None:
                        population_size = AGMOConfig.DEFAULT_POPULATION_SIZE
                    if generations is None:
                        generations = AGMOConfig.DEFAULT_GENERATIONS

        except Exception as e:
            if population_size is None:
                population_size = AGMOConfig.DEFAULT_POPULATION_SIZE
            if generations is None:
                generations = AGMOConfig.DEFAULT_GENERATIONS

        return population_size, generations

    def get_termination(self, generations, enable_early_stopping):
        if enable_early_stopping:
            from pymoo.termination import DefaultMultiObjectiveTermination
            return DefaultMultiObjectiveTermination(
                ftol=AGMOConfig.EARLY_STOPPING_FTOL,
                period=AGMOConfig.EARLY_STOPPING_PERIOD,
                n_max_gen=generations
            )
        else:
            return ('n_gen', generations)

    def get_callback(self, convergence_tracker) -> ConvergenceCallback:
        return ConvergenceCallback(convergence_tracker)


def _calcular_retorno_carteira(app, carteira: List[Dict],
                               data_inicio,
                               data_fim) -> Tuple[float, List[float], pd.DataFrame]:
    """
    Calcula o retorno de uma carteira em um período específico

    Args:
        carteira: Lista com composição da carteira
        data_inicio: Data inicial do período
        data_fim: Data final do período

    Returns:
        Tupla com (retorno_total, lista_de_retornos_mensais, dataframe_com_datas)
    """
    with app.app_context():
        # Buscar retornos dos ativos no período
        ids_ativos = [item['id_ativo'] for item in carteira]

        query = db.session.query(
            HistoricoPrecos.data,
            HistoricoPrecos.variacao_mensal,
            Ativo.ticker
        ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
            .filter(
            HistoricoPrecos.id_ativo.in_(ids_ativos),
            HistoricoPrecos.data > data_inicio,
            HistoricoPrecos.data <= data_fim
        ) \
            .order_by(HistoricoPrecos.data)

        df = pd.read_sql(query.statement, con=db.session.connection())

        if df.empty:
            return 0.0, [], pd.DataFrame()

        # Pivot para ter retornos por ativo
        df_retornos = df.pivot(
            index='data',
            columns='ticker',
            values='variacao_mensal'
        )

        # Calcular retorno ponderado da carteira
        pesos_dict = {item['ticker']: item['peso'] for item in carteira}

        retornos_mensais = []
        datas = []
        for data_idx in df_retornos.index:
            retorno_mes = 0
            for ticker in df_retornos.columns:
                if ticker in pesos_dict:
                    ret_ativo = df_retornos.loc[data_idx, ticker]
                    if pd.notna(ret_ativo):
                        retorno_mes += pesos_dict[ticker] * ret_ativo

            retornos_mensais.append(retorno_mes)
            datas.append(data_idx)

        # Calcular retorno acumulado
        retorno_total = (1 + pd.Series(retornos_mensais)).prod() - 1

        # Criar DataFrame com resultados
        df_resultado = pd.DataFrame({
            'data': datas,
            'retorno_mensal': retornos_mensais
        })
        df_resultado.set_index('data', inplace=True)

        return float(retorno_total), retornos_mensais, df_resultado


def salvar_grafico_backtest(carteira: List[Dict],
                            data_inicio,
                            data_fim,
                            app,
                            nome_arquivo: str = None,
                            janela_volatilidade: int = 6) -> str:
    """
    Gera e salva gráfico mostrando o retorno acumulado e a volatilidade da carteira ao longo do tempo.
    """
    import os
    from datetime import datetime

    print(f"\n{'='*70}")
    print(f"GERANDO GRÁFICO DE BACKTEST")
    print(f"{'='*70}")

    # Calcular retornos da carteira
    retorno_total, retornos_mensais, df_retornos = _calcular_retorno_carteira(
        app, carteira, data_inicio, data_fim
    )

    if df_retornos.empty:
        print("Sem dados para gerar gráfico")
        return None

    # Calcular retorno acumulado
    df_retornos['retorno_acumulado'] = (1 + df_retornos['retorno_mensal']).cumprod() - 1

    # Calcular volatilidade rolling (anualizada)
    df_retornos['volatilidade_rolling'] = (
        df_retornos['retorno_mensal']
        .rolling(window=janela_volatilidade, min_periods=1)
        .std() * np.sqrt(12) * 100  # Anualizada e em %
    )

    # Configurar figura com 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('Backtest da Carteira Otimizada', fontsize=16, fontweight='bold')

    # Gráfico 1: Retorno Acumulado
    ax1.plot(df_retornos.index, df_retornos['retorno_acumulado'] * 100,
             linewidth=2.5, color='#2E86AB', marker='o', markersize=4, label='Retorno Acumulado')
    ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5, linewidth=1)
    ax1.fill_between(df_retornos.index, 0, df_retornos['retorno_acumulado'] * 100,
                     alpha=0.3, color='#2E86AB')
    ax1.set_title('Retorno Acumulado da Carteira ao Longo do Tempo', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Data', fontsize=10)
    ax1.set_ylabel('Retorno Acumulado (%)', fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='upper left', fontsize=9)

    # Adicionar anotação com retorno total
    retorno_final = df_retornos['retorno_acumulado'].iloc[-1] * 100
    ax1.annotate(f'Retorno Total: {retorno_final:+.2f}%',
                xy=(df_retornos.index[-1], retorno_final),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                fontsize=9, fontweight='bold')

    # Gráfico 2: Volatilidade Rolling
    ax2.plot(df_retornos.index, df_retornos['volatilidade_rolling'],
             linewidth=2.5, color='#F18F01', marker='s', markersize=4, label=f'Volatilidade Rolling ({janela_volatilidade} meses)')
    ax2.fill_between(df_retornos.index, 0, df_retornos['volatilidade_rolling'],
                     alpha=0.3, color='#F18F01')
    ax2.set_title(f'Volatilidade da Carteira ao Longo do Tempo (janela de {janela_volatilidade} meses)',
                  fontsize=12, fontweight='bold')
    ax2.set_xlabel('Data', fontsize=10)
    ax2.set_ylabel('Volatilidade Anualizada (%)', fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='upper left', fontsize=9)

    # Adicionar linha de média de volatilidade
    vol_media = df_retornos['volatilidade_rolling'].mean()
    ax2.axhline(y=vol_media, color='green', linestyle='--', alpha=0.7, linewidth=1.5,
                label=f'Média: {vol_media:.2f}%')
    ax2.legend(loc='upper left', fontsize=9)

    plt.tight_layout()

    # Definir nome do arquivo
    if nome_arquivo is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f'backtest_carteira_{timestamp}.png'

    # Garantir que o diretório existe
    diretorio = os.path.dirname(nome_arquivo) if os.path.dirname(nome_arquivo) else '.'
    if not os.path.exists(diretorio) and diretorio != '.':
        os.makedirs(diretorio, exist_ok=True)

    # Salvar gráfico
    caminho_completo = os.path.abspath(nome_arquivo)
    plt.savefig(caminho_completo, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"  ✅ Gráfico salvo em: {caminho_completo}")
    print(f"  📊 Métricas:")
    print(f"     Retorno Total: {retorno_final:+.2f}%")
    print(f"     Volatilidade Média: {vol_media:.2f}%")
    print(f"     Sharpe Ratio: {(retorno_final/vol_media):.3f}" if vol_media > 0 else "     Sharpe Ratio: N/A")
    print(f"{'='*70}\n")

    return caminho_completo


def otimizar_carteira_atual(app):
    service = Nsga2OtimizacaoService(app, [1], "moderado", 10, exibir_grafico=True)
    resultado = service.otimizar(max_ativos=10, use_optimal_config=False)

    # Informações adicionais
    print(f"\n📅 INFORMAÇÕES DO PERÍODO:")
    print(f"   Dados históricos: {resultado['periodo_inicio']} até {resultado['periodo_fim']}")
    print(f"   Total de meses: {resultado['num_meses']}")
    print(f"   Hiperparâmetros: Pop={resultado['hyperparameters_used']['population_size']}, "
          f"Gen={resultado['hyperparameters_used']['generations']}")

def backtest(app):
    from datetime import date
    data_backtest = date(2015, 1, 1)
    service_backtest = Nsga2OtimizacaoService(app, [1, 10], "moderado", 10, data_referencia=data_backtest, exibir_grafico=True)
    carteira_backtest = service_backtest.otimizar(max_ativos=10)

    # Informações do backtest
    print(f"\nINFORMAÇÕES DO BACKTEST:")
    print(f"   Data de referência: {carteira_backtest['data_referencia']}")
    print(f"   Dados históricos: {carteira_backtest['periodo_inicio']} até {carteira_backtest['periodo_fim']}")
    print(f"   Total de meses: {carteira_backtest['num_meses']}")
    print(f"   Hiperparâmetros: Pop={carteira_backtest['hyperparameters_used']['population_size']}, "
          f"Gen={carteira_backtest['hyperparameters_used']['generations']}")

    dataFim = date(2025, 10, 20)
    retorno_periodo, retornos_mensais, df_retornos = _calcular_retorno_carteira(
        app,
        carteira_backtest['composicao'],
        data_backtest,
        dataFim
    )

    print(f"     Retorno Acumulado: {retorno_periodo * 100:+.2f}%")

    # Gerar e salvar gráfico do backtest
    salvar_grafico_backtest(
        carteira_backtest['composicao'],
        data_backtest,
        dataFim,
        app,
        nome_arquivo='backtest_exemplo.png'
    )


def main():
    """Função principal que interpreta os comandos."""
    app = create_app()

    # Exemplo 1: Otimização normal (sem backtest)
 #   otimizar_carteira_atual(app)

    # Exemplo 2: Otimização com backtest (usando dados até uma data específica)
    backtest(app)


if __name__ == "__main__":
    main()

