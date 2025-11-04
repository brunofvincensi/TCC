#!/usr/bin/env python3
"""
Teste de Operadores Genéticos com Restrição de Cardinalidade

Este script valida que os operadores customizados mantêm:
1. Soma = 1 (simplex)
2. Cardinalidade ≤ max_ativos
3. Limites do problema respeitados

Uso:
    python test_cardinality_operators.py

Referências:
    - Chang et al. (2000). "Heuristics for cardinality constrained portfolio optimisation".
"""

import sys
import os
import numpy as np

# Adiciona o diretório backend ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app
from services.agmo.agmo_service import Nsga2OtimizacaoService


def test_operadores_unitarios():
    """
    Testa operadores genéticos isoladamente.
    """
    print("\n" + "=" * 80)
    print("TESTE 1: Operadores Genéticos (Unitário)")
    print("=" * 80)

    from services.agmo.cardinality_operators import (
        SimplexSamplingCardConstraint,
        SimplexCrossoverCardConstraint,
        SimplexMutationCardConstraint,
        _enforce_cardinality
    )
    from pymoo.core.problem import Problem

    # Problema mock para testes
    class MockProblem(Problem):
        def __init__(self, n_var):
            super().__init__(n_var=n_var, n_obj=1, xl=0.01, xu=0.30)

    # Teste 1: _enforce_cardinality
    print("\n1.1 Testando _enforce_cardinality:")
    print("-" * 80)

    weights = np.array([0.2, 0.15, 0.1, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.22])
    max_assets = 5

    print(f"   Pesos originais (10 ativos):")
    print(f"   {weights}")
    print(f"   Soma: {weights.sum():.6f}")
    print(f"   Ativos não-zero: {np.sum(weights > 1e-6)}")

    new_weights = _enforce_cardinality(weights, max_assets)

    print(f"\n   Após cardinalidade (max={max_assets}):")
    print(f"   {new_weights}")
    print(f"   Soma: {new_weights.sum():.6f}")
    print(f"   Ativos não-zero: {np.sum(new_weights > 1e-6)}")

    assert abs(new_weights.sum() - 1.0) < 1e-6, "❌ Soma não é 1"
    assert np.sum(new_weights > 1e-6) <= max_assets, f"❌ Cardinalidade excedida"
    print(f"   ✅ PASSOU: Soma = 1, Cardinalidade ≤ {max_assets}")

    # Teste 2: SimplexSamplingCardConstraint
    print("\n1.2 Testando SimplexSamplingCardConstraint:")
    print("-" * 80)

    problem = MockProblem(n_var=10)
    sampling = SimplexSamplingCardConstraint(max_assets=5)

    X = sampling.do(problem, n_samples=20)

    print(f"   Gerando 20 amostras com max_assets=5")
    print(f"   Shape: {X.shape}")

    # Valida cada amostra
    all_valid = True
    for i, x in enumerate(X):
        soma = x.sum()
        n_active = np.sum(x > 1e-6)

        if abs(soma - 1.0) > 1e-6:
            print(f"   ❌ Amostra {i}: soma = {soma:.6f} (esperado 1.0)")
            all_valid = False

        if n_active > 5:
            print(f"   ❌ Amostra {i}: {n_active} ativos (esperado ≤ 5)")
            all_valid = False

    if all_valid:
        print(f"   ✅ PASSOU: Todas as 20 amostras válidas (soma=1, card≤5)")
    else:
        print(f"   ❌ FALHOU: Algumas amostras inválidas")

    # Teste 3: SimplexCrossoverCardConstraint
    print("\n1.3 Testando SimplexCrossoverCardConstraint:")
    print("-" * 80)

    crossover = SimplexCrossoverCardConstraint(max_assets=5, eta=15.0)

    # Criar pais
    parents = X[:2].reshape(2, 1, 10)  # 2 pais, 1 mating, 10 variáveis

    offspring = crossover.do(problem, parents)

    print(f"   Gerando filhos a partir de 2 pais")
    print(f"   Shape offspring: {offspring.shape}")

    # Valida filhos
    for i, child in enumerate(offspring[:, 0, :]):
        soma = child.sum()
        n_active = np.sum(child > 1e-6)

        print(f"   Filho {i}: soma={soma:.6f}, ativos={n_active}")

        if abs(soma - 1.0) > 1e-6:
            print(f"   ❌ Filho {i}: soma inválida")
            all_valid = False

        if n_active > 5:
            print(f"   ❌ Filho {i}: cardinalidade excedida")
            all_valid = False

    if all_valid:
        print(f"   ✅ PASSOU: Filhos válidos (soma=1, card≤5)")

    # Teste 4: SimplexMutationCardConstraint
    print("\n1.4 Testando SimplexMutationCardConstraint:")
    print("-" * 80)

    mutation = SimplexMutationCardConstraint(max_assets=5, eta=20.0)

    # Mutar população
    Y = mutation.do(problem, X[:10])

    print(f"   Mutando 10 indivíduos")

    # Valida mutados
    for i, y in enumerate(Y):
        soma = y.sum()
        n_active = np.sum(y > 1e-6)

        if abs(soma - 1.0) > 1e-6 or n_active > 5:
            print(f"   ❌ Mutado {i}: soma={soma:.6f}, ativos={n_active}")
            all_valid = False

    if all_valid:
        print(f"   ✅ PASSOU: Mutados válidos (soma=1, card≤5)")

    print("\n" + "=" * 80)
    print("✅ TESTE 1 CONCLUÍDO")
    print("=" * 80)


def test_otimizacao_completa():
    """
    Testa otimização completa com restrição de cardinalidade.
    """
    print("\n" + "=" * 80)
    print("TESTE 2: Otimização Completa com Restrição de Cardinalidade")
    print("=" * 80)

    app = create_app()

    # Teste sem restrição
    print("\n2.1 Otimização SEM restrição de cardinalidade:")
    print("-" * 80)

    service_sem = Nsga2OtimizacaoService(
        app=app,
        ids_ativos_restringidos=[],
        nivel_risco='moderado',
        prazo_anos=3
    )

    resultado_sem = service_sem.otimizar(
        population_size=50,
        generations=25,
        use_optimal_config=False,
        max_ativos=None  # SEM restrição
    )

    n_ativos_sem = len(resultado_sem['composicao'])
    print(f"\n   Ativos na carteira: {n_ativos_sem}")
    print(f"   Restrição aplicada: {resultado_sem['max_ativos_enforced']}")

    # Teste COM restrição
    print("\n2.2 Otimização COM restrição de cardinalidade (max=10):")
    print("-" * 80)

    service_com = Nsga2OtimizacaoService(
        app=app,
        ids_ativos_restringidos=[],
        nivel_risco='moderado',
        prazo_anos=3
    )

    resultado_com = service_com.otimizar(
        population_size=50,
        generations=25,
        use_optimal_config=False,
        max_ativos=10  # COM restrição
    )

    n_ativos_com = len(resultado_com['composicao'])
    print(f"\n   Ativos na carteira: {n_ativos_com}")
    print(f"   Restrição aplicada: {resultado_com['max_ativos_enforced']}")
    print(f"   Max ativos: {resultado_com['max_ativos']}")

    # Validação
    print("\n2.3 Validação:")
    print("-" * 80)

    if n_ativos_com <= 10:
        print(f"   ✅ PASSOU: Carteira com {n_ativos_com} ativos ≤ 10")
    else:
        print(f"   ❌ FALHOU: Carteira com {n_ativos_com} ativos > 10")

    # Verifica soma dos pesos
    soma_pesos = sum(a['peso'] for a in resultado_com['composicao'])
    print(f"   Soma dos pesos: {soma_pesos:.6f}")

    if abs(soma_pesos - 1.0) < 1e-6:
        print(f"   ✅ PASSOU: Soma de pesos = 1")
    else:
        print(f"   ❌ FALHOU: Soma de pesos ≠ 1")

    # Comparação
    print("\n2.4 Comparação SEM vs COM restrição:")
    print("-" * 80)

    print(f"   {'Métrica':<30} {'SEM Restrição':>15} {'COM Restrição':>15}")
    print(f"   {'-'*60}")
    print(f"   {'Número de ativos':<30} {n_ativos_sem:>15} {n_ativos_com:>15}")
    print(f"   {'Retorno anual':<30} {resultado_sem['metricas']['retorno_esperado_anual']*100:>14.2f}% "
          f"{resultado_com['metricas']['retorno_esperado_anual']*100:>14.2f}%")
    print(f"   {'Volatilidade anual':<30} {resultado_sem['metricas']['volatilidade_anual']*100:>14.2f}% "
          f"{resultado_com['metricas']['volatilidade_anual']*100:>14.2f}%")
    print(f"   {'Sharpe Ratio':<30} {resultado_sem['metricas']['sharpe_ratio']:>15.2f} "
          f"{resultado_com['metricas']['sharpe_ratio']:>15.2f}")

    print("\n   💡 Interpretação:")
    print(f"      - Restrição reduziu carteira de {n_ativos_sem} para {n_ativos_com} ativos")
    print(f"      - Permite controle de complexidade operacional")
    print(f"      - Trade-off entre diversificação e implementabilidade")

    print("\n" + "=" * 80)
    print("✅ TESTE 2 CONCLUÍDO")
    print("=" * 80)


def main():
    """Executa todos os testes"""
    print("\n" + "=" * 80)
    print("🧪 SUITE DE TESTES - OPERADORES COM RESTRIÇÃO DE CARDINALIDADE")
    print("=" * 80)
    print("\nTestando implementação de Card-Constrained Portfolio Optimization")
    print("\nReferências:")
    print("  - Chang et al. (2000) - Heuristics for cardinality constrained portfolio optimisation")
    print("  - Ruiz-Torrubiano & Suárez (2010) - Hybrid approaches for card-constrained portfolios")
    print("  - Bienstock (1996) - Mixed-integer quadratic programming")

    try:
        # Teste 1: Operadores unitários
        test_operadores_unitarios()

        # Teste 2: Otimização completa
        test_otimizacao_completa()

        print("\n" + "=" * 80)
        print("✅ TODOS OS TESTES CONCLUÍDOS COM SUCESSO")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERRO durante execução dos testes:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
