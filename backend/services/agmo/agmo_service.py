from pymoo.config import Config
from services.agmo.custom_crossover import SimplexCrossover, SimplexMutation, SimplexSampling

Config.warnings['not_compiled'] = False

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.core.callback import Callback
from otimizacao_utils import _printar_matriz

from app import create_app
from models import db, Ativo, HistoricoPrecos
from models.ativo import TipoAtivo

import matplotlib.pyplot as plt

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

    def __init__(self, retornos_medios, matriz_covariancia, historico_retornos, tickers, nivel_risco, alpha=0.05, peso_min=0.01, peso_max=0.30):
        n_ativos = len(retornos_medios)
        # ✅ Limites por ativo
        xl = np.full(n_ativos, peso_min)
        xu = np.full(n_ativos, peso_max)
        # n_ieq_constr=numero de restrições / n_eq_constr=numero de restrições de soma
        super().__init__(n_var=n_ativos,
                         n_obj=3,
                         n_ieq_constr=1,
                         n_eq_constr=0,
                         xl=0.01, xu=1)
        self.mu = retornos_medios
        self.cov = matriz_covariancia
        self.hist = historico_retornos
        self.tickers = tickers
        self.nivel_risco = nivel_risco
        self.alpha = alpha
        self.peso_min = peso_min
        self.peso_max = peso_max

    def _calcular_cvar(self, pesos):
        """Calcula o Conditional Value-at-Risk para uma dada carteira."""
        retornos_portfolio = self.hist @ pesos
        perdas = -retornos_portfolio
        perdas_validas = perdas[np.isfinite(perdas)]

        if len(perdas_validas) < 20:  # ✅ Mínimo de dados
            return np.std(perdas_validas)  # Fallback para desvio padrão

        perdas_ordenadas = np.sort(perdas_validas)
        k = max(1, int(self.alpha * len(perdas_ordenadas)))  # ✅ Mínimo de 1

        # CVaR = média das perdas acima do VaR
        cvar = perdas_ordenadas[-k:].mean()
        return cvar

    def _evaluate(self, x, out, *args, **kwargs):
        """Avalia uma única carteira"""

        # # ========== DEBUG ==========
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

        # --- AJUSTE DOS OBJETIVOS PELO PERFIL DE RISCO ---
        # Penaliza mais o risco para perfis conservadores e menos para arrojados.
        # Isso "empurra" o algoritmo para as regiões da Fronteira de Pareto desejadas.
        if self.nivel_risco == 'conservador':
            variancia *= 1.5
            cvar *= 2.0
        elif self.nivel_risco == 'arrojado':
            variancia *= 0.8
            cvar *= 0.8
        # Para 'moderado', não fazemos nada (peso 1.0)

        # ✅ Diversificação: nenhum ativo deve ter mais que peso_max
        restricao_concentracao = np.max(pesos) - self.peso_max

        # Restrição de IGUALDADE (soma = 1)
        restricao_eq = np.sum(pesos) - 1.0  # h(x) = 0

        out["F"] = [retorno, variancia, cvar]
        out["G"] =  [restricao_concentracao] # ✅ Restrição de concentração
       # out["H"] = [restricao_eq]  # ✅ Restrição de igualdade

# --------------------------------------------------------------------------
# 2. SERVIÇO PRINCIPAL DE OTIMIZAÇÃO
#    Ele agora orquestra o processo usando os parâmetros do usuário.
# --------------------------------------------------------------------------
class Nsga2OtimizacaoService:
    def __init__(self, app, ids_ativos_restringidos, nivel_risco, prazo_anos, data_referencia=None, data_inicio=None):
        """
        Serviço de otimização de carteira usando NSGA-II.

        Args:
            app: Instância da aplicação Flask
            ids_ativos_restringidos: Lista de IDs de ativos a serem excluídos da otimização
            nivel_risco: Perfil de risco ('conservador', 'moderado', 'arrojado')
            prazo_anos: Prazo do investimento em anos
            data_referencia: Data de referência para backtest (opcional). Se fornecida,
                           usa apenas dados históricos até essa data. Formato: datetime.date
        """
        self.app = app
        self.ids_ativos_restringidos = ids_ativos_restringidos
        self.nivel_risco = nivel_risco
        self.prazo_anos = prazo_anos
        self.data_referencia = data_referencia
        # Data inicial da janela de análise
        self.data_inicio = data_inicio
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
            self.ativos_para_otimizar = query_ativos.all()
            if len(self.ativos_para_otimizar) < 3:  # Mínimo para 3 objetivos
                raise ValueError("São necessários pelo menos 3 ativos do tipo 'Ação' para a otimização.")

            ids_para_otimizar = [a.id for a in self.ativos_para_otimizar]
            query_historico = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
                .filter(HistoricoPrecos.id_ativo.in_(ids_para_otimizar))

            # ✅ BACKTEST: Se data_referencia foi fornecida, filtra apenas dados até essa data
            if self.data_referencia is not None:
                if self.data_inicio is not None:
                    query_historico = query_historico.filter(HistoricoPrecos.data >= self.data_inicio)

                query_historico = query_historico.filter(HistoricoPrecos.data <= self.data_referencia)
                print(f"  📅 MODO BACKTEST: Usando dados até {self.data_referencia}")

            query_historico = query_historico.order_by(HistoricoPrecos.data)

            # ✅ CORREÇÃO: Usar connection em vez de bind
            df_historico = pd.read_sql(
                query_historico.statement,
                con=db.session.connection()
            )
            if df_historico.empty:
                raise ValueError("Sem histórico para os ativos selecionados.")

            # ✅ FILTRO INTELIGENTE DE ATIVOS POR HISTÓRICO MÍNIMO
            # Problema: ações com histórico curto fazem .dropna() eliminar dados de ações com histórico longo
            # Solução: Filtrar ações antes do pivot baseado no horizonte de investimento

            # Calcula histórico mínimo necessário
            # Usa margem de 1.5x o prazo para ter mais dados de qualidade
            MARGEM_SEGURANCA = 1.5
            MINIMO_ABSOLUTO_MESES = 24  # Mínimo de 2 anos mesmo para prazos curtos

            historico_minimo_meses = max(
                int(self.prazo_anos * 12 * MARGEM_SEGURANCA),
                MINIMO_ABSOLUTO_MESES
            )

            print(f"\n{'=' * 70}")
            print(f"🔍 FILTRANDO ATIVOS POR HISTÓRICO MÍNIMO")
            print(f"{'=' * 70}")
            print(f"  Prazo de investimento: {self.prazo_anos} anos")
            print(f"  Histórico mínimo requerido: {historico_minimo_meses} meses ({historico_minimo_meses/12:.1f} anos)")
            print(f"  Margem de segurança: {MARGEM_SEGURANCA}x")

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

            # Validação: precisamos de pelo menos 3 ativos
            if len(ativos_validos) < 3:
                raise ValueError(
                    f"Ativos insuficientes após filtro de histórico!\n"
                    f"  Requerido: 3 ativos\n"
                    f"  Disponível: {len(ativos_validos)} ativos\n"
                    f"  Histórico mínimo: {historico_minimo_meses} meses\n\n"
                    f"Sugestões:\n"
                    f"  1. Reduza o prazo de investimento (atual: {self.prazo_anos} anos)\n"
                    f"  2. Adicione ativos com mais histórico ao universo\n"
                    f"  3. Use um período de análise mais recente (data_inicio)"
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
            _printar_matriz(matriz_corr, formato=".3f")

            # Análise da correlação
            self._analisar_correlacao(matriz_corr)

            # ✅ PRINTAR MATRIZ DE COVARIÂNCIA
            print(f"\n{'=' * 70}")
            print(f"📊 MATRIZ DE COVARIÂNCIA (Mensal)")
            print(f"{'=' * 70}")
            _printar_matriz(self.matriz_covariancia, formato=".6f")

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
        scores = ((objetivos_norm[:, 0] * pesos[0]) - (objetivos_norm[:, 1] * pesos[1]))
              #    - (objetivos_norm[:, 2] * pesos[2]))

        # O índice da carteira com o maior score é a nossa escolha.
        idx_melhor = np.argmax(scores)
        return solucoes[idx_melhor]

    def otimizar(self, population_size: int = 100, generations: int = 50,
                 crossover_eta: float = 15.0, mutation_eta: float = 20.0,
                 convergence_tracker=None):
        """
        Orquestra o processo completo de otimização personalizada.

        Args:
            population_size: Tamanho da população para o NSGA-II
            generations: Número de gerações
            crossover_eta: Parâmetro eta do crossover
            mutation_eta: Parâmetro eta da mutação
            convergence_tracker: Instância de ConvergenceTracker para rastrear convergência (opcional)

        Returns:
            dict: Dicionário contendo:
                - composicao: Lista de dicionários com id_ativo, ticker e peso
                - data_referencia: Data de referência usada (None se não for backtest)
                - periodo_inicio: Data inicial dos dados históricos usados
                - periodo_fim: Data final dos dados históricos usados
                - num_meses: Número de meses de dados históricos utilizados
        """
        self._preparar_dados()

        problema = PersonalizedPortfolioProblem(
            retornos_medios=self.retornos_medios.values,
            matriz_covariancia=self.matriz_covariancia.values,
            historico_retornos=self.historico_retornos.values,
            tickers = self.tickers,
            nivel_risco=self.nivel_risco
        )

        sampling = SimplexSampling()
        crossover = SimplexCrossover(eta=crossover_eta)
        mutation = SimplexMutation(eta=mutation_eta)

        algoritmo = NSGA2(pop_size=population_size, crossover=crossover,
                         mutation=mutation, sampling=sampling)

        # Prepara callback se tracker foi fornecido
        callback = None
        if convergence_tracker is not None:
            callback = ConvergenceCallback(convergence_tracker)

        resultado = minimize(problema, algoritmo, ('n_gen', generations),
                           callback=callback, verbose=True)
        print("🏁 Otimização NSGA-II concluída.")

        if resultado.X is None:
            raise ValueError("O algoritmo não conseguiu encontrar nenhuma solução.")

        # Seleciona a melhor carteira da fronteira de Pareto
        pesos_otimos = self._escolher_melhor_carteira(resultado.F, resultado.X)

        F = resultado.F
        plt.scatter(F[:, 1], -F[:, 0], c=F[:, 2], cmap='viridis')
        plt.xlabel("Risco (variância)")
        plt.ylabel("Retorno esperado")
        plt.colorbar(label="CVaR")
        plt.title("Fronteira de Pareto - NSGA-II")
        plt.show()

        composicao_final = []
        for i, ativo in enumerate(self.ativos_para_otimizar):
            peso = pesos_otimos[i]
            if peso > 0.001:  # Ignora pesos insignificantes
                composicao_final.append({
                    'id_ativo': ativo.id,
                    'ticker': ativo.ticker,
                    'nome': ativo.nome,
                    'peso': float(peso)
                })

        # Normalizar pesos para soma = 1
        soma_pesos = sum(item['peso'] for item in composicao_final)
        for item in composicao_final:
            item['peso'] = item['peso'] / soma_pesos

        print(f"  ✅ Carteira otimizada com {len(composicao_final)} ativos")

        # ✅ RETORNA informações adicionais sobre o período usado (útil para backtest)
        resultado = {
            'composicao': composicao_final,
            'data_referencia': self.data_referencia,
            'periodo_inicio': self.historico_retornos.index.min(),
            'periodo_fim': self.historico_retornos.index.max(),
            'num_meses': len(self.historico_retornos),
            'modo_backtest': self.data_referencia is not None
        }

        return resultado


def _calcular_retorno_carteira(app, carteira: List[Dict],
                               data_inicio,
                               data_fim) -> Tuple[float, List[float]]:
    """
    Calcula o retorno de uma carteira em um período específico

    Args:
        carteira: Lista com composição da carteira
        data_inicio: Data inicial do período
        data_fim: Data final do período

    Returns:
        Tupla com (retorno_total, lista_de_retornos_mensais)
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
            return 0.0, []

        # Pivot para ter retornos por ativo
        df_retornos = df.pivot(
            index='data',
            columns='ticker',
            values='variacao_mensal'
        )

        # Calcular retorno ponderado da carteira
        pesos_dict = {item['ticker']: item['peso'] for item in carteira}

        retornos_mensais = []
        for data_idx in df_retornos.index:
            retorno_mes = 0
            for ticker in df_retornos.columns:
                if ticker in pesos_dict:
                    ret_ativo = df_retornos.loc[data_idx, ticker]
                    if pd.notna(ret_ativo):
                        retorno_mes += pesos_dict[ticker] * ret_ativo

            retornos_mensais.append(retorno_mes)

        # Calcular retorno acumulado
        retorno_total = (1 + pd.Series(retornos_mensais)).prod() - 1

        return float(retorno_total), retornos_mensais


def otimizar_carteira_atual(app):
    print("\n" + "=" * 80)
    print("EXEMPLO 1: Otimização normal (usando todos os dados disponíveis)")
    print("=" * 80)
    service = Nsga2OtimizacaoService(app, [1], "conservador", 2)
    resultado = service.otimizar()
    print(f"\n✅ Resultado:")
    print(f"   Composição: {resultado['composicao']}")
    print(f"   Período: {resultado['periodo_inicio']} até {resultado['periodo_fim']}")
    print(f"   Meses: {resultado['num_meses']}")

def backtest(app):
    from datetime import date
    print("\n" + "=" * 80)
    print("EXEMPLO 2: Otimização com BACKTEST (dados até 2023-12-31)")
    print("=" * 80)
    data_backtest = date(2023, 1, 1)
    service_backtest = Nsga2OtimizacaoService(app, [1], "moderado", 2, data_referencia=data_backtest)
    carteira_backtest = service_backtest.otimizar()
    print(f"\n✅ Resultado do Backtest:")
    print(f"   Composição: {carteira_backtest['composicao']}")
    print(f"   Data de referência: {carteira_backtest['data_referencia']}")
    print(f"   Período: {carteira_backtest['periodo_inicio']} até {carteira_backtest['periodo_fim']}")
    print(f"   Meses: {carteira_backtest['num_meses']}")
    print(f"   Modo Backtest: {carteira_backtest['modo_backtest']}")

    dataFim = date(2025, 10, 20)
    retorno_periodo, retornos_mensais = _calcular_retorno_carteira(
        app,
        carteira_backtest['composicao'],
        data_backtest,
        dataFim
    )

    print(f"     Retorno Acumulado: {retorno_periodo * 100:+.2f}%")


def main():
    """Função principal que interpreta os comandos."""
    app = create_app()

    # Exemplo 1: Otimização normal (sem backtest)
   # otimizar_carteira_atual(app)

    # Exemplo 2: Otimização com backtest (usando dados até uma data específica)
    backtest(app)


if __name__ == "__main__":
    main()

