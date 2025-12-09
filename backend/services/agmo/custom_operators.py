"""
Operadores Genéticos com Restrição de Cardinalidade para R-NSGA-II

Este módulo implementa operadores customizados (Sampling, Crossover, Mutation) que
garantem que TODAS as soluções geradas tenham no máximo K ativos com peso > 0.

Abordagem:
- Após cada operação genética, zerar ativos excedentes (menor peso)
- Renormalizar para soma = 1
- Garante que todo o espaço de busca respeita a cardinalidade
"""

import numpy as np
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.sampling import Sampling

def _enforce_cardinality(weights: np.ndarray, max_assets: int) -> np.ndarray:
    """
    Aplica restrição de cardinalidade zerando ativos excedentes.

    Estratégia:
    1. Identifica ativos com peso > 0
    2. Se exceder max_assets, zera os de menor peso
    3. Renormaliza para soma = 1

    Args:
        weights: Vetor de pesos (soma = 1)
        max_assets: Número máximo de ativos permitidos

    Returns:
        Vetor de pesos com no máximo max_assets ativos não-zero, soma = 1
    """
    n_var = len(weights)

    # Se não há restrição ou já atende, retorna
    if max_assets is None or max_assets >= n_var:
        return weights

    # Conta ativos com peso significativo (> 1e-6 para evitar erros numéricos)
    active_mask = weights > 1e-6
    n_active = np.sum(active_mask)

    # Se já está dentro do limite, retorna
    if n_active <= max_assets:
        return weights

    # Precisa reduzir: mantém top-K ativos por peso
    # Ordena índices por peso decrescente
    sorted_indices = np.argsort(-weights)

    # Cria novo vetor zerado
    new_weights = np.zeros(n_var)

    # Mantém apenas os top max_assets ativos
    for i in range(max_assets):
        idx = sorted_indices[i]
        new_weights[idx] = weights[idx]

    # Renormaliza para soma = 1
    weight_sum = new_weights.sum()
    if weight_sum > 0:
        new_weights = new_weights / weight_sum
    else:
        # Fallback: distribuição uniforme nos max_assets primeiros
        new_weights[sorted_indices[:max_assets]] = 1.0 / max_assets

    return new_weights


class SimplexSamplingCardConstraint(Sampling):
    """
    Amostragem inicial no simplex com restrição de cardinalidade.

    Gera população inicial onde cada indivíduo:
    - Soma = 1 (simplex)
    - Tem no máximo max_assets ativos com peso > 0

    Estratégia:
    1. Gera solução usando Dirichlet (distribuição uniforme no simplex)
    2. Aplica restrição de cardinalidade
    3. Garante limites do problema (peso_min, peso_max)

    Args:
        max_assets: Número máximo de ativos (None = sem restrição)
    """

    def __init__(self, max_assets: int = None):
        """
        Args:
            max_assets: Número máximo de ativos na carteira (None = sem limite)
        """
        super().__init__()
        self.max_assets = max_assets

    def _do(self, problem, n_samples, **kwargs):
        """
        Gera n_samples indivíduos válidos (soma = 1, max_assets ativos).

        Args:
            problem: Problema de otimização
            n_samples: Número de amostras a gerar

        Returns:
            Matriz (n_samples, n_var) com soluções válidas
        """
        n_var = problem.n_var

        X = np.zeros((n_samples, n_var))

        for i in range(n_samples):
            if self.max_assets is None or self.max_assets >= n_var:
                # Sem restrição de cardinalidade: usa Dirichlet padrão
                weights = np.random.dirichlet(np.ones(n_var))
            else:
                # Com restrição: gera apenas max_assets ativos
                # Escolhe quais ativos estarão ativos (amostragem sem reposição)
                active_indices = np.random.choice(n_var, size=self.max_assets, replace=False)

                # Gera pesos usando Dirichlet apenas para ativos selecionados
                active_weights = np.random.dirichlet(np.ones(self.max_assets))

                # Cria vetor completo
                weights = np.zeros(n_var)
                weights[active_indices] = active_weights

            # Garantir limites do problema
            weights = np.clip(weights, problem.xl, problem.xu)

            # Re-normalizar após clip
            weight_sum = weights.sum()
            if weight_sum > 0:
                weights = weights / weight_sum
            else:
                # Fallback: distribuição uniforme
                weights = np.ones(n_var) / n_var

            # Aplica restrição de cardinalidade (redundante, mas garante)
            weights = _enforce_cardinality(weights, self.max_assets)

            X[i] = weights

        return X


class SimplexCrossoverCardConstraint(Crossover):
    """
    Crossover no simplex com restrição de cardinalidade.

    Usa interpolação convexa: filho = α*pai1 + (1-α)*pai2
    Depois aplica restrição de cardinalidade.

    Propriedades matemáticas:
    - Interpolação convexa preserva soma = 1
    - Após cardinalidade, renormaliza para soma = 1

    Args:
        max_assets: Número máximo de ativos (None = sem restrição)
        eta: Parâmetro de distribuição (maior = filhos mais próximos dos pais)
    """

    def __init__(self, max_assets: int = None, eta: float = 15.0):
        """
        Args:
            max_assets: Número máximo de ativos na carteira
            eta: Parâmetro de distribuição do SBX (Simulated Binary Crossover)
        """
        super().__init__(2, 2)  # 2 pais → 2 filhos
        self.max_assets = max_assets
        self.eta = eta

    def _do(self, problem, X, **kwargs):
        """
        Realiza crossover entre pares de pais.

        Args:
            problem: Problema de otimização
            X: Pais (shape: 2, n_matings, n_var)

        Returns:
            Filhos (shape: 2, n_matings, n_var)
        """
        _, n_matings, n_var = X.shape
        Y = np.full((self.n_offsprings, n_matings, n_var), np.nan)

        for k in range(n_matings):
            # Extrair pais
            p1 = X[0, k].copy()
            p2 = X[1, k].copy()

            # Garantir que pais somam 1 (segurança)
            p1 = p1 / p1.sum()
            p2 = p2 / p2.sum()

            # Simulated Binary Crossover (SBX)
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

            # Aplica a restrição de cardinalidade
            c1 = _enforce_cardinality(c1, self.max_assets)
            c2 = _enforce_cardinality(c2, self.max_assets)

            # Garantir limites do problema
            c1 = np.clip(c1, problem.xl, problem.xu)
            c2 = np.clip(c2, problem.xl, problem.xu)

            # Re-normalizar após clip
            c1 = c1 / c1.sum()
            c2 = c2 / c2.sum()

            # Re-aplicar cardinalidade após clip (pode ter criado novos ativos)
            c1 = _enforce_cardinality(c1, self.max_assets)
            c2 = _enforce_cardinality(c2, self.max_assets)

            Y[0, k] = c1
            Y[1, k] = c2

        return Y


class SimplexMutationCardConstraint(Mutation):
    """
    Mutação no simplex com restrição de cardinalidade.

    Estratégias de mutação:
    1. Se dentro do limite: transfere peso entre ativos existentes
    2. Se no limite: pode substituir um ativo por outro
    3. Sempre mantém soma = 1 e cardinalidade ≤ max_assets

    Args:
        max_assets: Número máximo de ativos (None = sem restrição)
        eta: Parâmetro de intensidade (maior = mutações menores)
    """

    def __init__(self, max_assets: int = None, eta: float = 20.0):
        """
        Args:
            max_assets: Número máximo de ativos na carteira
            eta: Parâmetro de intensidade da mutação polynomial
        """
        super().__init__()
        self.max_assets = max_assets
        self.eta = eta

    def _do(self, problem, X, **kwargs):
        """
        Aplica mutação mantendo cardinalidade.

        Args:
            problem: Problema de otimização
            X: População (shape: n_individuals, n_var)

        Returns:
            População mutada
        """
        Y = X.copy()

        for i in range(len(X)):
            individual = Y[i].copy()
            n_var = len(individual)

            # Garantir que soma = 1
            individual = individual / individual.sum()

            # Identifica ativos ativos
            active_mask = individual > 1e-6
            active_indices = np.where(active_mask)[0]
            n_active = len(active_indices)

            # Probabilidade de substituir ativo vs transferir peso
            # 30% chance de substituir se no limite de cardinalidade
            replace_prob = 0.3 if (self.max_assets and n_active >= self.max_assets) else 0.0

            if np.random.random() < replace_prob and n_active > 1:
                # Mutação por substituição: troca um ativo ativo por um inativo
                inactive_indices = np.where(~active_mask)[0]

                if len(inactive_indices) > 0:
                    # Escolhe ativo para remover (menor peso)
                    remove_idx = active_indices[np.argmin(individual[active_indices])]

                    # Escolhe ativo para adicionar (aleatório)
                    add_idx = np.random.choice(inactive_indices)

                    # Transfere todo o peso
                    individual[add_idx] = individual[remove_idx]
                    individual[remove_idx] = 0.0
            else:
                # Mutação por transferência: move peso entre ativos
                if n_active >= 2:
                    # Escolhe dois ativos
                    idx1, idx2 = np.random.choice(active_indices, 2, replace=False)
                else:
                    # Se menos de 2 ativos, escolhe qualquer par
                    idx1, idx2 = np.random.choice(n_var, 2, replace=False)

                # Calcular delta usando distribuição polynomial
                u = np.random.random()

                if u < 0.5:
                    delta_q = (2.0 * u) ** (1.0 / (self.eta + 1.0)) - 1.0
                else:
                    delta_q = 1.0 - (2.0 * (1.0 - u)) ** (1.0 / (self.eta + 1.0))

                # Magnitude da transferência (até 20% do menor valor)
                magnitude = min(individual[idx1], individual[idx2]) * 0.2 * delta_q

                # Transferir peso
                individual[idx1] = individual[idx1] - magnitude
                individual[idx2] = individual[idx2] + magnitude

            # Garantir não-negatividade
            individual = np.maximum(individual, 0)

            # Normalizar (preserva simplex)
            weight_sum = individual.sum()
            if weight_sum > 0:
                individual = individual / weight_sum
            else:
                # Fallback
                individual = np.ones(n_var) / n_var

            # Aplica a restrição de cardinalidade
            individual = _enforce_cardinality(individual, self.max_assets)

            # Garantir limites do problema
            individual = np.clip(individual, problem.xl, problem.xu)

            # Re-normalizar após clip
            individual = individual / individual.sum()

            # Re-aplicar cardinalidade (pode ter criado novos ativos no clip)
            individual = _enforce_cardinality(individual, self.max_assets)

            Y[i] = individual

        return Y
