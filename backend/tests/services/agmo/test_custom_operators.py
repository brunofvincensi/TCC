"""Testes para operadores genéticos customizados."""

import numpy as np
import pytest
from unittest.mock import Mock

from services.agmo.custom_operators import (
    _enforce_cardinality,
    SimplexSamplingCardConstraint,
    SimplexCrossoverCardConstraint,
    SimplexMutationCardConstraint
)


class TestEnforceCardinality:
    """Testes para função de aplicação de cardinalidade."""

    def test_mantém_soma_um(self):
        """Verifica se a soma dos pesos permanece 1 após aplicar cardinalidade."""
        weights = np.random.dirichlet(np.ones(10))
        result = _enforce_cardinality(weights, max_assets=5)
        assert np.isclose(result.sum(), 1.0), "Soma deve ser 1"

    def test_respeita_cardinalidade(self):
        """Verifica se número de ativos não excede limite."""
        weights = np.random.dirichlet(np.ones(10))
        max_assets = 5
        result = _enforce_cardinality(weights, max_assets=max_assets)
        n_active = np.sum(result > 1e-6)
        assert n_active <= max_assets, f"Deve ter no máximo {max_assets} ativos"

    def test_mantém_top_k_ativos(self):
        """Verifica se mantém os K ativos com maiores pesos."""
        weights = np.array([0.1, 0.2, 0.3, 0.15, 0.25])
        weights = weights / weights.sum()
        max_assets = 3
        result = _enforce_cardinality(weights, max_assets=max_assets)

        # Deve manter os 3 maiores: índices 2, 4, 1
        assert result[2] > 0, "Maior peso deve estar ativo"
        assert result[4] > 0, "Segundo maior deve estar ativo"
        assert result[1] > 0, "Terceiro maior deve estar ativo"
        assert result[0] == 0, "Menor peso deve ser zero"
        assert result[3] == 0, "Quarto maior deve ser zero"

    def test_sem_restrição_quando_max_assets_none(self):
        """Verifica que não aplica restrição quando max_assets é None."""
        weights = np.random.dirichlet(np.ones(10))
        result = _enforce_cardinality(weights, max_assets=None)
        np.testing.assert_array_almost_equal(weights, result)

    def test_sem_restrição_quando_max_assets_maior_que_n_var(self):
        """Verifica que não aplica restrição quando max_assets >= n_var."""
        weights = np.random.dirichlet(np.ones(10))
        result = _enforce_cardinality(weights, max_assets=15)
        np.testing.assert_array_almost_equal(weights, result)

    def test_normalização_correta(self):
        """Verifica normalização após redução de ativos."""
        weights = np.array([0.1, 0.2, 0.3, 0.2, 0.2])
        result = _enforce_cardinality(weights, max_assets=2)

        assert np.isclose(result.sum(), 1.0)
        # Deve manter apenas os 2 maiores (índices 2 e 1/3/4)
        assert np.sum(result > 1e-6) == 2


class TestSimplexSamplingCardConstraint:
    """Testes para amostragem inicial com restrição de cardinalidade."""

    def create_mock_problem(self, n_var=10):
        """Cria problema mock para testes."""
        problem = Mock()
        problem.n_var = n_var
        problem.xl = np.full(n_var, 0.01)
        problem.xu = np.full(n_var, 0.30)
        return problem

    def test_gera_quantidade_correta_de_amostras(self):
        """Verifica se gera número correto de indivíduos."""
        sampler = SimplexSamplingCardConstraint(max_assets=5)
        problem = self.create_mock_problem(n_var=10)
        n_samples = 20

        X = sampler._do(problem, n_samples)
        assert X.shape == (n_samples, 10)

    def test_todas_amostras_somam_um(self):
        """Verifica se todas as amostras somam 1."""
        sampler = SimplexSamplingCardConstraint(max_assets=5)
        problem = self.create_mock_problem(n_var=10)

        X = sampler._do(problem, 50)
        somas = X.sum(axis=1)
        assert np.allclose(somas, 1.0), "Todas as amostras devem somar 1"

    def test_respeita_cardinalidade(self):
        """Verifica se amostras respeitam restrição de cardinalidade."""
        max_assets = 5
        sampler = SimplexSamplingCardConstraint(max_assets=max_assets)
        problem = self.create_mock_problem(n_var=10)

        X = sampler._do(problem, 50)
        for i in range(len(X)):
            n_active = np.sum(X[i] > 1e-6)
            assert n_active <= max_assets, f"Amostra {i} excede cardinalidade"

    def test_respeita_limites_do_problema(self):
        """Verifica se amostras respeitam peso_min e peso_max."""
        sampler = SimplexSamplingCardConstraint(max_assets=5)
        problem = self.create_mock_problem(n_var=10)

        X = sampler._do(problem, 50)
        assert np.all(X >= problem.xl), "Pesos abaixo do mínimo"
        assert np.all(X <= problem.xu), "Pesos acima do máximo"


class TestSimplexCrossoverCardConstraint:
    """Testes para crossover com restrição de cardinalidade."""

    def create_mock_problem(self, n_var=10):
        """Cria problema mock para testes."""
        problem = Mock()
        problem.n_var = n_var
        problem.xl = np.full(n_var, 0.01)
        problem.xu = np.full(n_var, 0.30)
        return problem

    def test_gera_dois_filhos(self):
        """Verifica se crossover gera 2 filhos."""
        crossover = SimplexCrossoverCardConstraint(max_assets=5, eta=15.0)
        problem = self.create_mock_problem(n_var=10)

        # Criar pais (shape: 2, 1, 10)
        p1 = np.random.dirichlet(np.ones(10))
        p2 = np.random.dirichlet(np.ones(10))
        X = np.array([[p1], [p2]])

        Y = crossover._do(problem, X)
        assert Y.shape == (2, 1, 10), "Deve gerar 2 filhos"

    def test_filhos_somam_um(self):
        """Verifica se filhos somam 1."""
        crossover = SimplexCrossoverCardConstraint(max_assets=5, eta=15.0)
        problem = self.create_mock_problem(n_var=10)

        p1 = np.random.dirichlet(np.ones(10))
        p2 = np.random.dirichlet(np.ones(10))
        X = np.array([[p1], [p2]])

        Y = crossover._do(problem, X)
        assert np.isclose(Y[0, 0].sum(), 1.0), "Filho 1 deve somar 1"
        assert np.isclose(Y[1, 0].sum(), 1.0), "Filho 2 deve somar 1"

    def test_filhos_respeitam_cardinalidade(self):
        """Verifica se filhos respeitam restrição de cardinalidade."""
        max_assets = 5
        crossover = SimplexCrossoverCardConstraint(max_assets=max_assets, eta=15.0)
        problem = self.create_mock_problem(n_var=10)

        p1 = np.random.dirichlet(np.ones(10))
        p2 = np.random.dirichlet(np.ones(10))
        X = np.array([[p1], [p2]])

        Y = crossover._do(problem, X)
        n_active_c1 = np.sum(Y[0, 0] > 1e-6)
        n_active_c2 = np.sum(Y[1, 0] > 1e-6)

        assert n_active_c1 <= max_assets, "Filho 1 excede cardinalidade"
        assert n_active_c2 <= max_assets, "Filho 2 excede cardinalidade"


class TestSimplexMutationCardConstraint:
    """Testes para mutação com restrição de cardinalidade."""

    def create_mock_problem(self, n_var=10):
        """Cria problema mock para testes."""
        problem = Mock()
        problem.n_var = n_var
        problem.xl = np.full(n_var, 0.01)
        problem.xu = np.full(n_var, 0.30)
        return problem

    def test_mantém_forma_da_populacao(self):
        """Verifica se mutação mantém forma da população."""
        mutation = SimplexMutationCardConstraint(max_assets=5, eta=20.0)
        problem = self.create_mock_problem(n_var=10)

        X = np.array([np.random.dirichlet(np.ones(10)) for _ in range(20)])
        Y = mutation._do(problem, X)

        assert Y.shape == X.shape, "Forma deve ser mantida"

    def test_mutacao_mantem_soma_um(self):
        """Verifica se indivíduos mutados somam 1."""
        mutation = SimplexMutationCardConstraint(max_assets=5, eta=20.0)
        problem = self.create_mock_problem(n_var=10)

        X = np.array([np.random.dirichlet(np.ones(10)) for _ in range(20)])
        Y = mutation._do(problem, X)

        somas = Y.sum(axis=1)
        assert np.allclose(somas, 1.0), "Todos devem somar 1 após mutação"

    def test_mutacao_respeita_cardinalidade(self):
        """Verifica se mutação respeita restrição de cardinalidade."""
        max_assets = 5
        mutation = SimplexMutationCardConstraint(max_assets=max_assets, eta=20.0)
        problem = self.create_mock_problem(n_var=10)

        X = np.array([np.random.dirichlet(np.ones(10)) for _ in range(20)])
        Y = mutation._do(problem, X)

        for i in range(len(Y)):
            n_active = np.sum(Y[i] > 1e-6)
            assert n_active <= max_assets, f"Indivíduo {i} excede cardinalidade"

    def test_mutacao_altera_individuo(self):
        """Verifica se mutação realmente altera indivíduos (probabilística)."""
        np.random.seed(42)  # Para reprodutibilidade
        mutation = SimplexMutationCardConstraint(max_assets=5, eta=20.0)
        problem = self.create_mock_problem(n_var=10)

        X = np.array([np.random.dirichlet(np.ones(10)) for _ in range(50)])
        Y = mutation._do(problem, X.copy())

        # Pelo menos alguns indivíduos devem ter sido alterados
        n_alterados = 0
        for i in range(len(X)):
            if not np.allclose(X[i], Y[i]):
                n_alterados += 1

        assert n_alterados > 0, "Mutação deve alterar pelo menos alguns indivíduos"
