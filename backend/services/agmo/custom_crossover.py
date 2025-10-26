# services/agmo/simplex_operators.py

import numpy as np
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.sampling import Sampling

"""
SimplexSampling: População inicial gerada via distribuição de Dirichlet, garantindo distribuição uniforme no simplex*

SimplexCrossover: Utiliza interpolação convexa, preservando matematicamente a soma unitária*

SimplexMutation: Transfere peso entre dois ativos aleatórios, mantendo a soma constante*
"""
class SimplexSampling(Sampling):
    """
    Amostragem que gera população inicial no simplex (soma = 1)
    """

    def _do(self, problem, n_samples, **kwargs):
        """
        Gera n_samples indivíduos válidos (soma = 1)

        Usa distribuição de Dirichlet para gerar pontos
        uniformemente distribuídos no simplex
        """
        n_var = problem.n_var

        # Dirichlet(1,1,1,...) gera distribuição uniforme no simplex
        X = np.random.dirichlet(np.ones(n_var), size=n_samples)

        # Garantir limites do problema
        X = np.clip(X, problem.xl, problem.xu)

        # Re-normalizar após clip
        X = X / X.sum(axis=1, keepdims=True)

        return X


class SimplexCrossover(Crossover):
    """
    Crossover que mantém descendentes no simplex

    Usa interpolação convexa: filho = α*pai1 + (1-α)*pai2
    Isso SEMPRE resulta em soma = 1 se pais somam 1
    """

    def __init__(self, eta=15):
        """
        Args:
            eta: Parâmetro de distribuição do crossover
                 Maior = filhos mais próximos dos pais
        """
        super().__init__(2, 2)  # 2 pais → 2 filhos
        self.eta = eta

    def _do(self, problem, X, **kwargs):
        _, n_matings, n_var = X.shape
        Y = np.full((self.n_offsprings, n_matings, n_var), np.nan)

        for k in range(n_matings):
            # Extrair pais
            p1 = X[0, k].copy()
            p2 = X[1, k].copy()

            # Garantir que pais somam 1 (segurança)
            p1 = p1 / p1.sum()
            p2 = p2 / p2.sum()

            # Simulated Binary Crossover (SBX) adaptado para simplex
            u = np.random.random()

            if u <= 0.5:
                beta = (2.0 * u) ** (1.0 / (self.eta + 1.0))
            else:
                beta = (1.0 / (2.0 * (1.0 - u))) ** (1.0 / (self.eta + 1.0))

            # Gerar filhos por interpolação convexa
            c1 = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)
            c2 = 0.5 * ((1 - beta) * p1 + (1 + beta) * p2)

            # Garantir não-negatividade
            c1 = np.maximum(c1, 0)
            c2 = np.maximum(c2, 0)

            # Normalizar (preserva simplex)
            c1 = c1 / c1.sum()
            c2 = c2 / c2.sum()

            # Garantir limites do problema
            c1 = np.clip(c1, problem.xl, problem.xu)
            c2 = np.clip(c2, problem.xl, problem.xu)

            # Re-normalizar após clip
            c1 = c1 / c1.sum()
            c2 = c2 / c2.sum()

            Y[0, k] = c1
            Y[1, k] = c2

        return Y


class SimplexMutation(Mutation):
    """
    Mutação que mantém indivíduos no simplex

    Transfere peso entre dois ativos aleatórios
    """

    def __init__(self, eta=20):
        """
        Args:
            eta: Parâmetro de intensidade da mutação
                 Maior = mutações menores (mais conservador)
        """
        super().__init__()
        self.eta = eta

    def _do(self, problem, X, **kwargs):
        Y = X.copy()

        for i in range(len(X)):
            # Probabilidade de mutação por indivíduo
            # (pymoo já controla isso internamente)

            individuo = Y[i].copy()
            n_var = len(individuo)

            # Garantir que soma = 1
            individuo = individuo / individuo.sum()

            # Escolher DOIS genes aleatórios
            idx1, idx2 = np.random.choice(n_var, 2, replace=False)

            # Calcular delta usando distribuição polynomial
            u = np.random.random()

            if u < 0.5:
                delta_q = (2.0 * u) ** (1.0 / (self.eta + 1.0)) - 1.0
            else:
                delta_q = 1.0 - (2.0 * (1.0 - u)) ** (1.0 / (self.eta + 1.0))

            # Magnitude da transferência (até 20% do menor valor)
            magnitude = min(individuo[idx1], individuo[idx2]) * 0.2 * delta_q

            # Transferir peso
            individuo[idx1] = individuo[idx1] - magnitude
            individuo[idx2] = individuo[idx2] + magnitude

            # Garantir não-negatividade
            individuo = np.maximum(individuo, 0)

            # Normalizar (preserva simplex)
            individuo = individuo / individuo.sum()

            # Garantir limites do problema
            individuo = np.clip(individuo, problem.xl, problem.xu)

            # Re-normalizar após clip
            individuo = individuo / individuo.sum()

            Y[i] = individuo

        return Y