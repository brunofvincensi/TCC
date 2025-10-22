import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize

from app import create_app
from models import db, Ativo, HistoricoPrecos
from models.ativo import TipoAtivo

import matplotlib.pyplot as plt

# --------------------------------------------------------------------------
# 1. CLASSE DO PROBLEMA PARA O PYMOO
#    Agora ela recebe os parâmetros do usuário para guiar a otimização.
# --------------------------------------------------------------------------
class PersonalizedPortfolioProblem(ElementwiseProblem):
    """
    Problema de otimização de portfólio com 3 objetivos, personalizado
    pelo perfil de risco do usuário.
    """

    def __init__(self, retornos_medios, matriz_covariancia, historico_retornos, nivel_risco='moderado', alpha=0.05, peso_min=0.01, peso_max=0.30):
        n_ativos = len(retornos_medios)
        # ✅ Limites por ativo
        xl = np.full(n_ativos, peso_min)
        xu = np.full(n_ativos, peso_max)
        super().__init__(n_var=n_ativos, n_obj=3, n_ieq_constr=1, xl=0.01, xu=1)
        self.mu = retornos_medios
        self.cov = matriz_covariancia
        self.hist = historico_retornos
        self.nivel_risco = nivel_risco
        self.alpha = alpha
        self.peso_min = peso_min
        self.peso_max = peso_max


    # Serve para "consertar/ajustar" as soluções
    def repair(self, x, **kwargs):
        # Remove valores negativos (caso mutação ou crossover gerem)
        x = np.maximum(x, 0)

        # Normaliza para que a soma dos pesos = 1
        soma = np.sum(x)
        if soma == 0:
            # caso extremo: todos zeros → distribui igualmente
            x = np.ones_like(x) / len(x)
        else:
            x = x / soma

        return x

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
        """Avalia uma única carteira (x = vetor de pesos)."""
        # Garante que os pesos sejam positivos e que a soma seja 1 (normalização)
        pesos = x
        # pesos = np.maximum(x, 0)
        # if pesos.sum() == 0:
        #     pesos = np.ones_like(pesos) / len(pesos)
        # pesos /= pesos.sum()

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

        # --- Restrição ---
        # A soma dos pesos deve ser igual a 1. Formatado como g(x) <= 0.
        restricao = np.abs(np.sum(pesos) - 1.0) - 1e-6  # Usamos uma pequena tolerância

        # ✅ Diversificação: nenhum ativo deve ter mais que peso_max
        restricao_concentracao = np.max(pesos) - self.peso_max

        out["F"] = [retorno, variancia, cvar]
        # sem restrição para o algorimo conseguir uma solução ótima
     #   out["G"] =  [restricao] #[restricao, restricao_concentracao]
        out["G"] =  [restricao_concentracao] #[restricao, restricao_concentracao]

# --------------------------------------------------------------------------
# 2. SERVIÇO PRINCIPAL DE OTIMIZAÇÃO
#    Ele agora orquestra o processo usando os parâmetros do usuário.
# --------------------------------------------------------------------------
class Nsga2OtimizacaoService:
    def __init__(self, app, ids_ativos_restringidos, nivel_risco, prazo_anos):
        self.app = app
        self.ids_ativos_restringidos = ids_ativos_restringidos
        self.nivel_risco = nivel_risco
        self.prazo_anos = prazo_anos
        self.ativos_para_otimizar = []
        self.retornos_medios = None
        self.matriz_covariancia = None
        self.historico_retornos = None

    def _ajustar_covariancia_pelo_prazo(self, cov, prazo_anos):
        """
        Ajusta risco pelo prazo com transição inteligente:
        - Curto prazo (< 3 anos): mantém risco original
        - Médio prazo (3-10 anos): transição gradual
        - Longo prazo (> 10 anos): suavização forte
        """
        if prazo_anos <= 0:
            return cov

        # Curva de ajuste não-linear
        if prazo_anos <= 3:
            fator = 1.0  # Sem ajuste
        elif prazo_anos <= 10:
            # Transição suave entre 1.0 e suavização
            t = (prazo_anos - 3) / 7  # 0 a 1
            fator = 1.0 - (0.7 * t)  # 1.0 → 0.3
        else:
            # Longo prazo: suavização forte
            fator = 1 / np.sqrt(prazo_anos / 3)  # Normalizado por 3 anos

        print(f"  Ajuste temporal ({prazo_anos} anos): Fator de risco = {fator:.2f}x")
        return cov * fator

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
                .filter(HistoricoPrecos.id_ativo.in_(ids_para_otimizar)) \
                .order_by(HistoricoPrecos.data)

            # ✅ CORREÇÃO: Usar connection em vez de bind
            df_historico = pd.read_sql(
                query_historico.statement,
                con=db.session.connection()
            )
            if df_historico.empty:
                raise ValueError("Sem histórico para os ativos selecionados.")

            # Limita os históricos para o ativo que tem o histórico mais curto
            df_retornos = df_historico.pivot(index='data', columns='ticker', values='variacao_mensal').dropna()

            self.retornos_medios = df_retornos.mean()
            matriz_cov_mensal = df_retornos.cov()

            # Matriz de confusão
            print(matriz_cov_mensal)

            # --- APLICAÇÃO DO AJUSTE PELO PRAZO ---
            print(f"Ajustando matriz de covariância para um prazo de {self.prazo_anos} anos.")
            self.matriz_covariancia = self._ajustar_covariancia_pelo_prazo(matriz_cov_mensal, self.prazo_anos)

            self.historico_retornos = df_retornos
            print("✅ Dados preparados e ajustados pelo prazo.")

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
        scores = (objetivos_norm[:, 0] * pesos[0]) - (objetivos_norm[:, 1] * pesos[1]) - (
                    objetivos_norm[:, 2] * pesos[2])

        # O índice da carteira com o maior score é a nossa escolha.
        idx_melhor = np.argmax(scores)
        return solucoes[idx_melhor]

    def otimizar(self):
        """Orquestra o processo completo de otimização personalizada."""
        self._preparar_dados()

        problema = PersonalizedPortfolioProblem(
            retornos_medios=self.retornos_medios.values,
            matriz_covariancia=self.matriz_covariancia.values,
            historico_retornos=self.historico_retornos.values,
            nivel_risco=self.nivel_risco
        )

        algoritmo = NSGA2(pop_size=300)
        resultado = minimize(problema, algoritmo, ('n_gen', 200), verbose=True)
        print("🏁 Otimização NSGA-II concluída.")

        if resultado.X is None:
            raise ValueError("O algoritmo não conseguiu encontrar nenhuma solução.")

        # Seleciona a melhor carteira da fronteira de Pareto
        pesos_otimos = self._escolher_melhor_carteira(resultado.F, resultado.X)

        # Ajustar para já retornar certo, limitar em 1 no processamento
      #  pesos_otimos = resultado.X[10]
        pesos_otimos = np.maximum(pesos_otimos, 0)
        pesos_otimos /= pesos_otimos.sum()

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
                    'peso': float(peso)
                })

        return composicao_final



def main():
    """Função principal que interpreta os comandos."""
    app = create_app()
    serivice = Nsga2OtimizacaoService(app, [1], "moderado", 10)
    carteira = serivice.otimizar()
    print(carteira);


if __name__ == "__main__":
    main()

