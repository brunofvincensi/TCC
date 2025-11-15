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
from models import db, Ativo, HistoricoPrecos
from models.ativo import TipoAtivo

DEFAULT_GEN_SIZE = 100
DEFAULT_POPULATION_SIZE = 100

MIN_ATIVOS = 5

# --------------------------------------------------------------------------
# 0. CALLBACK PARA RASTREAMENTO DE CONVERGÊNCIA
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# 1. CLASSE DO PROBLEMA PARA O PYMOO
#    Agora ela recebe os parâmetros do usuário para guiar a otimização.
# --------------------------------------------------------------------------
class PersonalizedPortfolioProblem(ElementwiseProblem):

    """
    Problema de otimização de portfólio com 3 objetivos, personalizado
    pelo perfil de risco do usuário.
    """

    def __init__(self, retornos_medios, matriz_covariancia, historico_retornos, tickers, nivel_risco, max_ativos, alpha=0.05, peso_min=0.01, peso_max=0.30):
        n_ativos = len(retornos_medios)
        # Limites por ativo
        xl = np.full(n_ativos, peso_min)
        xu = np.full(n_ativos, peso_max)

        n_ativos_carteira = min(n_ativos, max_ativos)

        n_ieq_constr = 1 if n_ativos_carteira >= 10 else 0

        # HHI (Herfindahl-Hirschman Index) Thresholds por Perfil de Risco
        # HHI = Σ(wi²), onde N_eff = 1/HHI (número efetivo de ativos)
        # Valores baseados em literatura de concentração de mercado e diversificação
        self.hhi_thresholds = {
            'conservador': 0.12,  # N_eff ≈ 8.3 ativos (baixa concentração)
            'moderado': 0.15,     # N_eff ≈ 6.7 ativos (concentração moderada)
            'arrojado': 0.20      # N_eff ≈ 5.0 ativos (concentração aceitável)
        }
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
        self.hhi_max = self.hhi_thresholds.get(nivel_risco, 0.15)
        self.max_ativos = max_ativos

    def _calcular_cvar(self, pesos):
        """
        Calcula o Conditional Value-at-Risk (CVaR) usando método empírico.

        CVaR_α = E[Perda | Perda ≥ VaR_α] ≈ média dos ⌈α·n⌉ piores retornos

        Referências:
            - Rockafellar & Uryasev (2000). "Optimization of conditional value-at-risk"
            - Acerbi & Tasche (2002). "On the coherence of expected shortfall"
        """
        # 1. Calcular retornos e perdas do portfolio
        retornos_portfolio = self.hist @ pesos
        perdas = -retornos_portfolio

        # 2. Filtrar valores inválidos
        perdas_validas = perdas[np.isfinite(perdas)]
        n = len(perdas_validas)

        # 3. Proteção para amostras pequenas
        if n < 20:
            return float(np.std(perdas_validas))

        # 4. Calcular número de observações na cauda
        k = max(1, int(np.ceil(self.alpha * n)))

        # 5. CVaR = média dos k piores retornos (maiores perdas)
        perdas_ordenadas = np.sort(perdas_validas)
        cauda = perdas_ordenadas[-k:]  # Sempre exatamente k observações

        cvar = float(np.mean(cauda))

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
        # print(f"\n💼 Mapeamento x → Ativos:")
        # for i, (ticker, peso_raw) in enumerate(zip(self.tickers, x)):
        #     print(f"   x[{i}] = {peso_raw:.6f} → {ticker}")

        """Avalia uma única carteira (x = vetor de pesos)."""
        pesos = x

        # --- Objetivos ---
        # Obj 1: Retorno esperado (negativo porque o pymoo minimiza)
        retorno = -np.dot(pesos, self.mu)

        # Obj 2: Risco (variância)
        variancia = np.dot(pesos, self.cov @ pesos)

        # Obj 3: Risco de cauda (CVaR)
        cvar = self._calcular_cvar(pesos)

        out["F"] = [retorno, variancia, cvar]

        if self.n_ativos_carteira >= 10:
            hhi = np.sum(pesos ** 2)
            restricao_hhi = hhi - self.hhi_max
            out["G"] = [restricao_hhi]

# --------------------------------------------------------------------------
# 2. SERVIÇO PRINCIPAL DE OTIMIZAÇÃO
#    Ele agora orquestra o processo usando os parâmetros do usuário.
# --------------------------------------------------------------------------
class Nsga2OtimizacaoService:
    def __init__(self, app, ids_ativos_restringidos, nivel_risco, prazo_anos=5, data_referencia=None, data_inicio=None, ids_ativos: List[int] = None, exibir_grafico=False):
        """
        Serviço de otimização de carteira usando R-NSGA2 (Reference Point Based NSGA-II).

        R-NSGA2 permite guiar a busca durante a otimização usando pontos de referência
        customizados por perfil de risco, ao contrário do NSGA2 tradicional que só
        permite seleção após gerar todas as soluções não-dominadas.

        Args:
            app: Instância da aplicação Flask
            ids_ativos_restringidos: Lista de IDs de ativos a serem excluídos da otimização
            nivel_risco: Perfil de risco ('conservador', 'moderado', 'arrojado')
                        - conservador: Prioriza minimizar riscos (variância e CVaR)
                        - moderado: Busca equilíbrio entre retorno e risco
                        - arrojado: Prioriza maximizar retorno
            prazo_anos: Prazo do investimento em anos
            data_referencia: Data de referência para backtest (opcional). Se fornecida,
                           usa apenas dados históricos até essa data. Formato: datetime.date

        Referências:
            - Deb & Sundar (2006). "Reference point based multi-objective optimization using evolutionary algorithms"
        """
        self.app = app
        self.ids_ativos_restringidos = ids_ativos_restringidos
        self.ids_ativos = ids_ativos
        self.nivel_risco = nivel_risco
        self.prazo_anos = prazo_anos
        self.data_referencia = data_referencia
        # Data inicial da janela de análise
        self.data_inicio = data_inicio
        self.exibir_grafico = exibir_grafico
        self.ativos_para_otimizar = []
        self.retornos_medios = None
        self.matriz_covariancia = None
        self.historico_retornos = None
        self.tickers = None

    def _preparar_dados(self):

        """Busca dados e aplica o ajuste de risco pelo prazo."""
        with self.app.app_context():
            query_ativos = db.session.query(Ativo).filter(
                ~Ativo.id.in_(self.ids_ativos_restringidos),
                Ativo.tipo == TipoAtivo.ACAO
            )
            if self.ids_ativos:
                query_ativos = query_ativos.filter(Ativo.id.in_(self.ids_ativos))

            self.ativos_para_otimizar = query_ativos.all()
            if len(self.ativos_para_otimizar) < MIN_ATIVOS:  # Mínimo para 3 objetivos
                raise ValueError(f"São necessários pelo menos {MIN_ATIVOS} ativos do tipo 'Ação' para a otimização.")

            ids_para_otimizar = [a.id for a in self.ativos_para_otimizar]
            query_historico = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
                .filter(HistoricoPrecos.id_ativo.in_(ids_para_otimizar))

            # BACKTEST: Se data_referencia foi fornecida, filtra apenas dados até essa data
            if self.data_referencia is not None:
                if self.data_inicio is not None:
                    query_historico = query_historico.filter(HistoricoPrecos.data >= self.data_inicio)

                query_historico = query_historico.filter(HistoricoPrecos.data <= self.data_referencia)
                print(f"  📅 MODO BACKTEST: Usando dados até {self.data_referencia}")

            query_historico = query_historico.order_by(HistoricoPrecos.data)

            df_historico = pd.read_sql(
                query_historico.statement,
                con=db.session.connection()
            )
            if df_historico.empty:
                raise ValueError("Sem histórico para os ativos selecionados.")

            # FILTRO INTELIGENTE DE ATIVOS POR HISTÓRICO MÍNIMO
            # Problema: ações com histórico curto fazem .dropna() eliminar dados de ações com histórico longo
            # Solução: Filtrar ações antes do pivot baseado no horizonte de investimento

            MINIMO_ABSOLUTO_MESES = 24  # Mínimo de 2 anos mesmo para prazos curtos

            historico_minimo_meses = max(
                int(self.prazo_anos * 12),
                MINIMO_ABSOLUTO_MESES
            )

            print(f"\n{'=' * 70}")
            print(f"🔍 FILTRANDO ATIVOS POR HISTÓRICO MÍNIMO")
            print(f"{'=' * 70}")
            print(f"  Prazo de investimento: {self.prazo_anos} anos")
            print(f"  Histórico mínimo requerido: {historico_minimo_meses} meses ({historico_minimo_meses/12:.1f} anos)")

            # Pivot sem dropna para analisar cada ativo
            df_retornos_completo = df_historico.pivot(
                index='data',
                columns='ticker',
                values='variacao_mensal'
            )

            # Analisa quantidade de dados por ativo
            ativos_disponiveis = df_retornos_completo.columns.tolist()
            contagem_dados = df_retornos_completo.count()

            print(f"\n  📊 Análise de histórico por ativo:")
            print(f"  {'Ticker':<12} {'Meses':>8} {'Status':<20}")
            print(f"  {'-'*40}")

            ativos_validos = []
            ativos_excluidos = []

            for ticker in ativos_disponiveis:
                meses_disponiveis = contagem_dados[ticker]

                if meses_disponiveis >= historico_minimo_meses:
                    status = "✅ Incluído"
                    ativos_validos.append(ticker)
                else:
                    status = f"❌ Excluído ({meses_disponiveis}/{historico_minimo_meses})"
                    ativos_excluidos.append(ticker)

                print(f"  {ticker:<12} {meses_disponiveis:>8} {status:<20}")

            if len(ativos_validos) < MIN_ATIVOS:
                raise ValueError(
                    f"Ativos insuficientes após filtro de histórico!\n"
                    f"  Requerido: {MIN_ATIVOS} ativos\n"
                    f"  Disponível: {len(ativos_validos)} ativos\n"
                    f"  Histórico mínimo: {historico_minimo_meses} meses\n\n"
                    f"Sugestões:\n"
                    f"  1. Reduza o prazo de investimento (atual: {self.prazo_anos} anos)\n"
                )

            print(f"\n  ✅ Resultado do filtro:")
            print(f"     Ativos incluídos: {len(ativos_validos)}")
            print(f"     Ativos excluídos: {len(ativos_excluidos)}")

            if ativos_excluidos:
                print(f"     Excluídos: {', '.join(ativos_excluidos)}")

            # Filtra o DataFrame original para incluir apenas ativos válidos
            df_historico_filtrado = df_historico[df_historico['ticker'].isin(ativos_validos)]

            # Agora faz o pivot e dropna com segurança
            # Todos os ativos têm histórico >= mínimo, então dropna é consistente
            df_retornos = df_historico_filtrado.pivot(
                index='data',
                columns='ticker',
                values='variacao_mensal'
            ).dropna()

            self.tickers = df_retornos.columns.tolist()

            # Atualiza lista de ativos para otimizar (remove os excluídos)
            self.ativos_para_otimizar = [
                a for a in self.ativos_para_otimizar
                if a.ticker in self.tickers
            ]

            # ✅ VALIDAÇÃO: Garante que todos os tickers em self.tickers têm um ativo correspondente
            tickers_ativos = {a.ticker for a in self.ativos_para_otimizar}
            tickers_faltantes = set(self.tickers) - tickers_ativos
            if tickers_faltantes:
                raise ValueError(
                    f"Inconsistência detectada: Tickers no DataFrame sem ativo correspondente: {tickers_faltantes}"
                )

            # ✅ VALIDAÇÃO: Garante que os tamanhos correspondem
            if len(self.ativos_para_otimizar) != len(self.tickers):
                raise ValueError(
                    f"Inconsistência detectada: {len(self.ativos_para_otimizar)} ativos, "
                    f"mas {len(self.tickers)} tickers no DataFrame!"
                )

            # ✅ Validação de dados suficientes
            if len(df_retornos) < historico_minimo_meses:
                raise ValueError(
                    f"Dados históricos insuficientes após alinhamento!\n"
                    f"  Encontrados: {len(df_retornos)} meses\n"
                    f"  Necessário: {historico_minimo_meses} meses\n\n"
                    f"Isso geralmente acontece quando o período de sobreposição entre "
                    f"os ativos é muito curto."
                )

            if self.data_referencia is not None:
                print(f"\n{'=' * 70}")
                print(f"📅 MODO BACKTEST ATIVADO")
                print(f"{'=' * 70}")
                print(f"  Data de referência: {self.data_referencia}")
                print(f"  ⚠️  Usando APENAS dados históricos até essa data")

            print(f"\n  ✅ Período histórico: {len(df_retornos)} meses")
            print(f"  📅 De {df_retornos.index.min()} até {df_retornos.index.max()}")

            # Calcular estatísticas
            self.retornos_medios = df_retornos.mean()
            self.matriz_covariancia = df_retornos.cov()
            matriz_corr = df_retornos.corr()

            # ✅ PRINTAR MATRIZ DE CORRELAÇÃO
            print(f"\n{'=' * 70}")
            print(f"📊 MATRIZ DE CORRELAÇÃO")
            print(f"{'=' * 70}")
            self._printar_matriz(matriz_corr, formato=".3f")

            # Análise da correlação
            self._analisar_correlacao(matriz_corr)

            # ✅ PRINTAR MATRIZ DE COVARIÂNCIA
            print(f"\n{'=' * 70}")
            print(f"📊 MATRIZ DE COVARIÂNCIA (Mensal)")
            print(f"{'=' * 70}")
            self._printar_matriz(self.matriz_covariancia, formato=".6f")

            self.historico_retornos = df_retornos

            # Estatísticas gerais
            print(f"\n{'=' * 70}")
            print(f"📊 ESTATÍSTICAS GERAIS")
            print(f"{'=' * 70}")
            print(f"  Retorno médio mensal: {self.retornos_medios.mean() * 100:.2f}%")
            print(f"  Volatilidade média: {np.sqrt(np.diag(self.matriz_covariancia)).mean() * 100:.2f}%")

            # Estatísticas por ativo
            print(f"\n  📈 Por Ativo:")
            for ticker in df_retornos.columns:
                ret = self.retornos_medios[ticker] * 100
                vol = np.sqrt(self.matriz_covariancia.loc[ticker, ticker]) * 100
                sharpe = ret / vol if vol > 0 else 0
                print(f"     {ticker:8s} | Ret: {ret:6.2f}% | Vol: {vol:6.2f}% | Sharpe: {sharpe:5.2f}")

            print(f"\n  ✅ Dados preparados com sucesso!")

    def _analisar_correlacao(self, matriz_corr):
        """
        Analisa e printa insights da matriz de correlação
        """
        print(f"\n  🔍 Análise de Correlação:")

        # Extrair apenas metade superior (sem diagonal)
        mask = np.triu(np.ones_like(matriz_corr, dtype=bool), k=1)
        correlacoes = matriz_corr.where(mask).stack()

        # Estatísticas
        print(f"     Correlação Média: {correlacoes.mean():.3f}")
        print(f"     Correlação Máxima: {correlacoes.max():.3f}")
        print(f"     Correlação Mínima: {correlacoes.min():.3f}")

        # Pares com correlação muito alta (> 0.8)
        altas = correlacoes[correlacoes > 0.8].sort_values(ascending=False)
        if len(altas) > 0:
            print(f"\n  ⚠️  Pares com Correlação ALTA (> 0.8):")
            for par, corr in altas.head(5).items():
                print(f"     {par[0]:8s} ↔ {par[1]:8s}: {corr:.3f}")

        # Pares com correlação negativa (< -0.3)
        negativas = correlacoes[correlacoes < -0.3].sort_values()
        if len(negativas) > 0:
            print(f"\n  ✅ Pares com Correlação NEGATIVA (< -0.3) [Boa diversificação!]:")
            for par, corr in negativas.head(5).items():
                print(f"     {par[0]:8s} ↔ {par[1]:8s}: {corr:.3f}")

        # Aviso se tudo muito correlacionado
        if correlacoes.mean() > 0.7:
            print(f"\n  ⚠️  ATENÇÃO: Ativos muito correlacionados (média {correlacoes.mean():.2f})")
            print(f"     Considere adicionar ativos de outros setores para diversificação.")

    def _escolher_melhor_carteira(self, objetivos, solucoes):
        """Seleciona a melhor carteira da Fronteira de Pareto com base no perfil de risco."""
        print(f"Selecionando a melhor solução para o perfil '{self.nivel_risco}'...")

        # Normaliza os objetivos para que fiquem na mesma escala (0 a 1)
        # Obj 0 (Retorno) é negativo, então invertemos o sinal para normalizar
        # Inverte retorno (era negativo)
        objetivos = objetivos.copy()
        objetivos[:, 0] = -objetivos[:, 0]

        # Normalização mais robusta
        objetivos_norm = np.zeros_like(objetivos)
        for i in range(objetivos.shape[1]):
            col = objetivos[:, i]
            min_val, max_val = col.min(), col.max()

            if max_val - min_val > 1e-10:  # Evita divisão por zero
                objetivos_norm[:, i] = (col - min_val) / (max_val - min_val)
            else:
                objetivos_norm[:, i] = 0.5  # Valor neutro

        # Pesos para cada objetivo [Retorno, Variância, CVaR]
        pesos_perfil = {
            'conservador': np.array([0.2, 0.5, 0.3]),  # Prioriza minimizar riscos
            'moderado': np.array([0.4, 0.3, 0.3]),  # Equilibrado
            'arrojado': np.array([0.6, 0.2, 0.2])  # Prioriza maximizar retorno
        }
        pesos = pesos_perfil[self.nivel_risco]

        # Calcula um "score" para cada carteira.
        # Queremos maximizar o retorno (objetivo 0) e minimizar os outros (1 e 2).
        scores = ((objetivos_norm[:, 0] * pesos[0]) - (objetivos_norm[:, 1] * pesos[1])
                  - (objetivos_norm[:, 2] * pesos[2]))

        # O índice da carteira com o maior score é a nossa escolha.
        idx_melhor = np.argmax(scores)
        return solucoes[idx_melhor]

    def _printar_matriz(self, matriz, formato=".3f"):
        """
        Printa matriz formatada com cores

        Args:
            matriz: DataFrame pandas com a matriz
            titulo: Título da matriz
            formato: Formato dos números (ex: ".3f")
        """
        tickers = matriz.columns.tolist()
        n = len(tickers)

        # Cabeçalho
        header = "        "
        for ticker in tickers:
            header += f"{ticker:>10s} "
        print(header)
        print("  " + "-" * (11 * n + 8))

        # Linhas
        for i, ticker_linha in enumerate(tickers):
            linha = f"  {ticker_linha:6s} |"

            for j, ticker_coluna in enumerate(tickers):
                valor = matriz.iloc[i, j]

                # Colorir diagonal
                if i == j:
                    linha += f" {valor:>9{formato}}*"  # Asterisco na diagonal
                else:
                    linha += f" {valor:>9{formato}} "

            print(linha)

        print()

    def otimizar(self, population_size: int = None, generations: int = None,
                 crossover_eta: float = 10.0, mutation_eta: float = 10.0,
                 convergence_tracker=None, use_optimal_config: bool = True,
                 enable_early_stopping=False, max_ativos: int = 20):
        """
        Orquestra o processo completo de otimização personalizada.

        Args:
            population_size: Tamanho da população para o NSGA-II (None = auto-lookup)
            generations: Número de gerações (None = auto-lookup)
            crossover_eta: Parâmetro eta do crossover
            mutation_eta: Parâmetro eta da mutação
            convergence_tracker: Instância de ConvergenceTracker para rastrear convergência (opcional)
            use_optimal_config: Se True, tenta buscar configuração ótima do banco de dados
            enable_early_stopping: Se True, cria um critério de parada complementar ao numero máximo de gerações
            max_ativos: Número máximo de ativos na carteira (None = sem restrição).
                       Quando especificado, usa operadores genéticos com restrição de cardinalidade.

        Returns:
            dict: Dicionário contendo:
                - composicao: Lista de dicionários com id_ativo, ticker e peso
                - data_referencia: Data de referência usada (None se não for backtest)
                - periodo_inicio: Data inicial dos dados históricos usados
                - periodo_fim: Data final dos dados históricos usados
                - num_meses: Número de meses de dados históricos utilizados
                - hyperparameters_used: Hiperparâmetros utilizados
                - max_ativos_enforced: Se restrição de cardinalidade foi aplicada

        Referências (restrição de cardinalidade):
            - Chang et al. (2000). "Heuristics for cardinality constrained portfolio optimisation".
              Computers & Operations Research, 27(13), 1271-1302.
            - Ruiz-Torrubiano & Suárez (2010). "Hybrid approaches and dimensionality reduction
              for portfolio selection with cardinality constraints".
              IEEE Computational Intelligence Magazine, 5(2), 92-107.
        """

        if max_ativos is not None and max_ativos < MIN_ATIVOS:
            raise ValueError(f"São necessários pelo menos {MIN_ATIVOS} ativos do tipo 'Ação' para a otimização.")

        self._preparar_dados()

        num_ativos = len(self.ativos_para_otimizar)

        generations, population_size = self.get_hiperparameters(generations, num_ativos, population_size, use_optimal_config)

        problem = self.get_problem(max_ativos)

        algorithm = self.get_algorithm(crossover_eta, mutation_eta, population_size, max_ativos)

        callback = self.get_callback(convergence_tracker)

        termination = self.get_termination(generations, enable_early_stopping)

        print(f"\n{'='*70}")
        print(f"🚀 EXECUTANDO OTIMIZAÇÃO R-NSGA2")
        print(f"{'='*70}")
        print(f"  Algoritmo: R-NSGA2 (Reference Point Based)")
        print(f"  População: {population_size}")
        print(f"  Gerações: {generations}")
        print(f"  Perfil de risco: {self.nivel_risco}")
        print(f"  Número de ativos disponíveis: {num_ativos}")
        if max_ativos:
            print(f"  ⚠️  RESTRIÇÃO DE CARDINALIDADE: máx. {max_ativos} ativos na carteira")
            print(f"     Usando operadores genéticos com card-constraint")
        print(f"{'='*70}\n")

        resultado = minimize(problem, algorithm, termination,
                           callback=callback, verbose=True)
        print("🏁 Otimização R-NSGA2 concluída.")

        if resultado.X is None:
            raise ValueError("O algoritmo não conseguiu encontrar nenhuma solução.")

        # Seleciona a melhor carteira da fronteira de Pareto
        pesos_otimos = self._escolher_melhor_carteira(resultado.opt.get("F"), resultado.opt.get("X"))

        # ✅ VALIDAÇÃO: Garante que os tamanhos correspondem
        if len(pesos_otimos) != len(self.tickers):
            raise ValueError(
                f"Inconsistência detectada: pesos_otimos tem {len(pesos_otimos)} elementos, "
                f"mas self.tickers tem {len(self.tickers)} elementos!"
            )

        # if self.exibir_grafico:
        #     F = resultado.F
        #     plt.scatter(F[:, 1], -F[:, 0], c=F[:, 2], cmap='viridis')
        #     plt.xlabel("Risco (variância)")
        #     plt.ylabel("Retorno esperado")
        #     plt.colorbar(label="CVaR")
        #     plt.title(f"Fronteira de Pareto - R-NSGA2 (Perfil: {self.nivel_risco})")
        #     plt.show()

        if self.exibir_grafico:
            F = resultado.F

            # # Limites fixos para comparação entre diferentes execuções
            # # Ajuste estes valores conforme necessário baseado nos seus dados
            # LIMITE_X = (0.001, 0.012)  # Variância (risco)
            # LIMITE_Y = (0.014, 0.032)  # Retorno esperado
            # LIMITE_CVAR = (0.075, 0.10)  # CVaR

            LIMITE_X = (0.001, 0.012)  # Variância (risco)
            LIMITE_Y = (0.014, 0.032)  # Retorno esperado
            LIMITE_CVAR = (0.075, 0.10)  # CVaR

            fig, ax = plt.subplots(figsize=(10, 8))

            scatter = ax.scatter(
                F[:, 1],  # Variância (eixo X)
                -F[:, 0],  # Retorno (eixo Y, invertido)
                c=F[:, 2],  # CVaR (cor)
                cmap='viridis',
                s=80,  # Tamanho dos pontos
                alpha=0.7,
                vmin=LIMITE_CVAR[0],  # Limite mínimo da escala de cor
                vmax=LIMITE_CVAR[1]  # Limite máximo da escala de cor
            )

            # Aplicar limites fixos aos eixos
            ax.set_xlim(LIMITE_X)
            ax.set_ylim(LIMITE_Y)

            ax.set_xlabel("Risco (variância)", fontsize=11)
            ax.set_ylabel("Retorno esperado", fontsize=11)
            ax.set_title(f"Fronteira de Pareto - R-NSGA2 (Perfil: {self.nivel_risco})", fontsize=12)
            ax.grid(True, alpha=0.3)

            plt.colorbar(scatter, ax=ax, label="CVaR")
            plt.tight_layout()
            plt.show()

        # Os pesos_otimos estão na ordem de self.tickers (colunas do DataFrame)
        # Mas self.ativos_para_otimizar pode estar em ordem diferente
        pesos_por_ticker = {ticker: float(peso) for ticker, peso in zip(self.tickers, pesos_otimos)}

        print(f"\n{'='*70}")
        print(f"🔗 MAPEAMENTO PESOS → ATIVOS")
        print(f"{'='*70}")
        print(f"  Ordem self.tickers (usado na otimização):")
        for i, ticker in enumerate(self.tickers):
            print(f"    [{i}] {ticker:8s} → peso: {pesos_otimos[i]:.6f}")
        print(f"\n  Ordem self.ativos_para_otimizar (usado no resultado):")
        for i, ativo in enumerate(self.ativos_para_otimizar):
            peso = pesos_por_ticker.get(ativo.ticker, 0)
            print(f"    [{i}] {ativo.ticker:8s} → peso: {peso:.6f}")
        print(f"{'='*70}\n")

        composicao_final = []
        for ativo in self.ativos_para_otimizar:
            peso = pesos_por_ticker.get(ativo.ticker, 0)
            if peso > 0.001:  # Ignora pesos insignificantes
                composicao_final.append({
                    'id_ativo': ativo.id,
                    'ticker': ativo.ticker,
                    'nome': ativo.nome,
                    'peso': peso
                })

        # Normalizar pesos para soma = 1
        soma_pesos = sum(item['peso'] for item in composicao_final)
        for item in composicao_final:
            item['peso'] = item['peso'] / soma_pesos

        # Calcula métricas da carteira otimizada
        retorno_esperado = np.dot(pesos_otimos, self.retornos_medios.values)
        risco_carteira = np.sqrt(np.dot(pesos_otimos, self.matriz_covariancia.values @ pesos_otimos))
        sharpe_ratio = retorno_esperado / risco_carteira if risco_carteira > 0 else 0

        # Adiciona métricas ao resultado
        metricas = {
            'retorno_esperado_mensal': float(retorno_esperado),
            'retorno_esperado_anual': float(retorno_esperado * 12),
            'volatilidade_mensal': float(risco_carteira),
            'volatilidade_anual': float(risco_carteira * np.sqrt(12)),
            'sharpe_ratio': float(sharpe_ratio)
        }

        # Apresentação formatada dos resultados
        self._printar_resultado_otimizacao(composicao_final, metricas)

        # Retorna as informações adicionais sobre o período usado (útil para backtest)
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
        """
        Cria algoritmo R-NSGA2 com operadores apropriados e pontos de referência
        customizados por perfil de risco.

        R-NSGA2 guia a busca durante a otimização usando pontos de referência,
        direcionando as soluções para regiões específicas da fronteira de Pareto.

        Se max_ativos for especificado, usa operadores com restrição de cardinalidade.

        Args:
            crossover_eta: Parâmetro eta do crossover
            mutation_eta: Parâmetro eta da mutação
            population_size: Tamanho da população
            max_ativos: Número máximo de ativos (None = sem restrição)

        Returns:
            Instância do R-NSGA2 configurada

        Referências:
            - Deb & Sundar (2006). "Reference point based multi-objective optimization using evolutionary algorithms"
            - Molina et al. (2009). "Preference incorporation to solve many-objective airfoil design problems"
        """

        # Operadores customizados com restrição de cardinalidade
        sampling = SimplexSamplingCardConstraint(max_assets=max_ativos)
        crossover = SimplexCrossoverCardConstraint(max_assets=max_ativos, eta=crossover_eta)
        mutation = SimplexMutationCardConstraint(max_assets=max_ativos, eta=mutation_eta)

        # Pontos de referência por perfil
        # Cada linha é um ponto no espaço de objetivos [retorno_neg, variância, cvar]
        # reference_points_config = {            'conservador': np.array([
        #         [0.3, 0.0, 0.0],  # Prioridade máxima: minimizar variância e CVaR
        #         [0.2, 0.1, 0.1],  # Aceitável: pequeno aumento de risco
        #         [0.1, 0.2, 0.2],  # Tolerável: risco moderado
        #     ]),
        #     'moderado': np.array([
        #         [0.1, 0.2, 0.2],  # Bom retorno com risco controlado
        #         [0.2, 0.3, 0.3],  # Balanceado
        #         [0.3, 0.1, 0.1],  # Foco em retorno quando risco é baixo
        #     ]),
        #     'arrojado': np.array([
        #         [0.0, 0.3, 0.3],  # Prioridade máxima: maximizar retorno
        #         [0.0, 0.5, 0.5],  # Aceita risco alto para máximo retorno
        #         [0.1, 0.4, 0.4],  # Bom retorno com risco alto
        #     ])
        #
        # }

        reference_points_config = {
            'conservador': np.array([
                [0.3, 0.0, 0.0],  # Prioridade máxima: minimizar variância e CVaR
            ]),
            'moderado': np.array([
                [0.0, 0.3, 0.3],  # Balanceado
            ]),
            'arrojado': np.array([
                [0.0, 0.3, 0.3],  # Bom retorno com risco alto
            ])
        }

        ref_points = reference_points_config.get(self.nivel_risco)

        return RNSGA2(
            ref_points=ref_points,
            pop_size=population_size,
            crossover=crossover,
            mutation=mutation,
            sampling=sampling,
            epsilon=0.01,  # Controla o tamanho da região de interesse em torno dos pontos de referência
            normalization='front',  # Normaliza baseado na fronteira atual
            extreme_points_as_reference_points=False,  # Usa apenas nossos pontos customizados
            weights=np.array([0.5, 0.25, 0.25])  # Pesos para Achievement Scalarizing Function
        )

        # return NSGA2(pop_size=population_size, crossover=crossover,
        #     mutation=mutation,
        #     sampling=sampling)

    def get_hiperparameters(self, generations: int | None, num_ativos: int, population_size: int | None,
                           use_optimal_config: bool):
        if use_optimal_config and (population_size is None or generations is None):
            print(f"\n{'=' * 70}")
            print(f"🔍 BUSCANDO CONFIGURAÇÃO ÓTIMA PARA {num_ativos} ATIVOS")
            print(f"{'=' * 70}")

            population_size, generations = self.get_hyperparameter_config(num_ativos, population_size, generations)

        # Garante valores padrão se ainda None
        if population_size is None:
            population_size = DEFAULT_POPULATION_SIZE
        if generations is None:
            generations = DEFAULT_GEN_SIZE
        return generations, population_size

    """
    Busca os hiperparâmetros com base da quantidade de ativos da carteira
    """
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

    def _printar_resultado_otimizacao(self, composicao: List[Dict], metricas: Dict):
        """
        Apresenta os resultados da otimização de forma formatada e profissional.

        Args:
            composicao: Lista com composição da carteira
            metricas: Dicionário com métricas calculadas
        """
        print(f"\n{'='*80}")
        print(f"📊 RESULTADO DA OTIMIZAÇÃO")
        print(f"{'='*80}")

        # 1. Composição da Carteira (Tabela)
        print(f"\n💼 COMPOSIÇÃO DA CARTEIRA ({len(composicao)} ativos):")
        print(f"{'─'*80}")
        print(f"{'#':<4} {'Ticker':<10} {'Nome':<35} {'Peso':>10} {'Barra':>15}")
        print(f"{'─'*80}")

        # Ordena por peso (maior para menor)
        composicao_ordenada = sorted(composicao, key=lambda x: x['peso'], reverse=True)

        for i, ativo in enumerate(composicao_ordenada, 1):
            ticker = ativo['ticker']
            nome = ativo['nome'][:32] + '...' if len(ativo['nome']) > 35 else ativo['nome']
            peso = ativo['peso']
            peso_pct = peso * 100

            # Barra visual
            barra_size = int(peso * 50)  # Máximo 50 caracteres
            barra = '█' * barra_size

            print(f"{i:<4} {ticker:<10} {nome:<35} {peso_pct:>9.2f}% {barra:>15}")

        print(f"{'─'*80}")
        print(f"{'TOTAL':<50} {100.0:>9.2f}%")
        print(f"{'─'*80}")

        # 2. Métricas de Performance
        print(f"\n📈 MÉTRICAS DE PERFORMANCE:")
        print(f"{'─'*80}")

        ret_mensal = metricas['retorno_esperado_mensal'] * 100
        ret_anual = metricas['retorno_esperado_anual'] * 100
        vol_mensal = metricas['volatilidade_mensal'] * 100
        vol_anual = metricas['volatilidade_anual'] * 100
        sharpe = metricas['sharpe_ratio']

        print(f"   Retorno Esperado (mensal):  {ret_mensal:>8.2f}%")
        print(f"   Retorno Esperado (anual):   {ret_anual:>8.2f}%")
        print(f"   Volatilidade (mensal):      {vol_mensal:>8.2f}%")
        print(f"   Volatilidade (anual):       {vol_anual:>8.2f}%")
        print(f"   Índice de Sharpe:           {sharpe:>8.2f}")

        print(f"{'─'*80}")

        # 3. Concentração
        print(f"\n🎯 ANÁLISE DE CONCENTRAÇÃO:")
        print(f"{'─'*80}")

        top_3_peso = sum(a['peso'] for a in composicao_ordenada[:3]) * 100
        max_peso = composicao_ordenada[0]['peso'] * 100
        min_peso = composicao_ordenada[-1]['peso'] * 100

        print(f"   Top 3 ativos concentram:    {top_3_peso:>8.2f}%")
        print(f"   Maior alocação individual:  {max_peso:>8.2f}% ({composicao_ordenada[0]['ticker']})")
        print(f"   Menor alocação individual:  {min_peso:>8.2f}% ({composicao_ordenada[-1]['ticker']})")

        # Avaliação de diversificação
        if top_3_peso > 70:
            print(f"   ⚠️  Alta concentração - Considere diversificar")
        elif top_3_peso < 40:
            print(f"   ✅ Boa diversificação")
        else:
            print(f"   ℹ️  Diversificação moderada")

        print(f"{'─'*80}")

        print(f"\n✅ Otimização concluída com sucesso!")
        print(f"{'='*80}\n")


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

    Args:
        carteira: Lista com composição da carteira otimizada
        data_inicio: Data inicial do backtest
        data_fim: Data final do backtest
        app: Instância da aplicação Flask
        nome_arquivo: Nome do arquivo para salvar (opcional, gera automaticamente se None)
        janela_volatilidade: Janela em meses para cálculo da volatilidade rolling (padrão: 6)

    Returns:
        Caminho completo do arquivo salvo
    """
    import os
    from datetime import datetime

    print(f"\n{'='*70}")
    print(f"📊 GERANDO GRÁFICO DE BACKTEST")
    print(f"{'='*70}")

    # Calcular retornos da carteira
    retorno_total, retornos_mensais, df_retornos = _calcular_retorno_carteira(
        app, carteira, data_inicio, data_fim
    )

    if df_retornos.empty:
        print("  ⚠️  Sem dados para gerar gráfico")
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
    print(f"\n📅 INFORMAÇÕES DO BACKTEST:")
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

