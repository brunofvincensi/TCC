# backend/services/otimizacao_service.py

import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from models import *
from models.ativo import TipoAtivo


class Nsga2OtimizacaoService:
    """
    Serviço que encapsula a lógica de otimização de portfólio usando NSGA-II,
    agora com três objetivos: retorno, variância e CVaR.
    """

    def __init__(self, app, ids_ativos_disponiveis, ids_ativos_restringidos=[]):
        self.app = app
        self.ids_ativos_disponiveis = ids_ativos_disponiveis
        self.ids_ativos_restringidos = ids_ativos_restringidos
        self.ativos_para_otimizar = []
        self.retornos_medios = None
        self.matriz_covariancia = None
        self.historico_retornos = None  # <-- adicionamos o histórico completo

    def _preparar_dados(self):
        """
        Busca os dados históricos no banco e calcula retorno médio e covariância.
        """
        with self.app.app_context():
            # Filtra os ativos elegíveis (exemplo: apenas ações)
            query_ativos = db.session.query(Ativo).filter(
                Ativo.id.in_(self.ids_ativos_disponiveis),
                ~Ativo.id.in_(self.ids_ativos_restringidos),
                Ativo.tipo == TipoAtivo.ACAO
            )
            self.ativos_para_otimizar = query_ativos.all()

            if len(self.ativos_para_otimizar) < 2:
                raise ValueError("São necessários pelo menos 2 ativos do tipo 'Ação'.")

            ids_para_otimizar = [a.id for a in self.ativos_para_otimizar]

            # Busca o histórico de variações mensais
            query_historico = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
             .filter(HistoricoPrecos.id_ativo.in_(ids_para_otimizar)) \
             .order_by(HistoricoPrecos.data)

            df_historico = pd.read_sql(query_historico.statement, db.session.bind)
            if df_historico.empty:
                raise ValueError("Sem histórico disponível para os ativos selecionados.")

            # Pivota: cada coluna é um ativo, índice é data
            df_retornos = df_historico.pivot(index='data', columns='ticker', values='variacao_mensal')
            df_retornos = df_retornos.dropna(how='any')  # evita NaN

            # Calcula médias e covariância
            self.retornos_medios = df_retornos.mean()
            self.matriz_covariancia = df_retornos.cov()
            self.historico_retornos = df_retornos

            print("✅ Dados preparados.")
            print("Ativos:", self.retornos_medios.index.tolist())

    def otimizar(self):
        """Executa o NSGA-II com 3 objetivos: retorno, risco e CVaR."""
        self._preparar_dados()

        n_ativos = len(self.ativos_para_otimizar)
        print(f"Iniciando otimização com {n_ativos} ativos...")

        # Define o problema (Elementwise)
        problema = PortfolioProblem(
            retornos_medios=self.retornos_medios.values,
            matriz_covariancia=self.matriz_covariancia.values,
            historico_retornos=self.historico_retornos.values
        )

        # Instancia o NSGA-II
        algoritmo = NSGA2(pop_size=100)

        # Executa a otimização
        resultado = minimize(
            problema,
            algoritmo,
            ('n_gen', 200),
            verbose=True
        )
        print("🏁 Otimização concluída.")

        # Filtra carteiras que atendem à restrição (soma dos pesos ≈ 1)
        solucoes = resultado.X
        objetivos = resultado.F
        restricoes = resultado.G

        solucoes_viaveis = solucoes[np.abs(restricoes[:, 0]) <= 1e-3]
        objetivos_viaveis = objetivos[np.abs(restricoes[:, 0]) <= 1e-3]

        if len(solucoes_viaveis) == 0:
            raise ValueError("Nenhuma solução viável encontrada.")

        # Seleciona a carteira de menor risco (variância)
        idx_menor_risco = np.argmin(objetivos_viaveis[:, 1])
        pesos_otimos = solucoes_viaveis[idx_menor_risco]

        # Monta o resultado final
        composicao_final = []
        for i, ativo in enumerate(self.ativos_para_otimizar):
            peso = pesos_otimos[i]
            if peso > 0.001:
                composicao_final.append({
                    'id_ativo': ativo.id,
                    'ticker': ativo.ticker,
                    'peso': float(peso)
                })

        return composicao_final


class PortfolioProblem(ElementwiseProblem):
    """
    Problema de otimização de portfólio com 3 objetivos:
    1. Maximizar retorno esperado
    2. Minimizar variância
    3. Minimizar CVaR (Conditional Value-at-Risk)
    """

    def __init__(self, retornos_medios, matriz_covariancia, historico_retornos, alpha=0.05):
        n_ativos = len(retornos_medios)
        super().__init__(n_var=n_ativos, n_obj=3, n_ieq_constr=1, xl=0.0, xu=1.0)
        self.mu = retornos_medios
        self.cov = matriz_covariancia
        self.hist = historico_retornos
        self.alpha = alpha

    def _evaluate(self, x, out, *args, **kwargs):
        """
        Avalia uma única carteira (x = vetor de pesos).
        Calcula:
          - Retorno esperado
          - Variância
          - CVaR
          - Restrição de soma dos pesos (≈ 1)
        """
        w = np.maximum(x, 0)
        if w.sum() == 0:
            w = np.ones_like(w) / len(w)
        w /= w.sum()  # normaliza

        # Objetivo 1: retorno esperado (negativo para o pymoo minimizar)
        retorno = -np.dot(w, self.mu)

        # Objetivo 2: risco (variância)
        variancia = np.dot(w, self.cov @ w)

        # Objetivo 3: CVaR (expected shortfall)
        # Calcula retornos da carteira ao longo do tempo
        retornos_portfolio = self.hist @ w
        perdas = -retornos_portfolio  # perdas positivas
        perdas_ordenadas = np.sort(perdas)
        k = int(np.ceil(self.alpha * len(perdas_ordenadas)))
        cvar = np.mean(perdas_ordenadas[:k])  # média das piores perdas

        # Restrição: soma dos pesos = 1
        restricao = np.sum(w) - 1.0

        out["F"] = [retorno, variancia, cvar]
        out["G"] = [restricao]
