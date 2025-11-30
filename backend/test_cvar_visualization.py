"""
Script de teste para visualização do CVaR
Demonstra como o CVaR varia entre diferentes soluções da primeira geração
"""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from pymoo.algorithms.moo.rnsga2 import RNSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.core.callback import Callback
from pymoo.config import Config

Config.warnings['not_compiled'] = False

# Importar operadores customizados
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.agmo.custom_operators import (
    SimplexSamplingCardConstraint,
    SimplexCrossoverCardConstraint,
    SimplexMutationCardConstraint
)

class TestPortfolioProblem(ElementwiseProblem):
    """Versão simplificada do problema para teste"""

    def __init__(self, mean_returns, covariance_matrix, returns_history, tickers, alpha=0.05):
        num_assets = len(mean_returns)
        min_weight = 0.01
        max_weight = 0.30
        xl = np.full(num_assets, min_weight)
        xu = np.full(num_assets, max_weight)

        super().__init__(n_var=num_assets, n_obj=3, xl=xl, xu=xu)
        self.num_assets = num_assets
        self.mu = mean_returns
        self.cov = covariance_matrix
        self.hist = returns_history
        self.tickers = tickers
        self.alpha = alpha

    def _calculate_cvar(self, weights):
        """Calcula o CVaR"""
        portfolio_returns = self.hist @ weights
        losses = -portfolio_returns
        valid_losses = losses[np.isfinite(losses)]
        n = len(valid_losses)

        if n < 20:
            return float(np.std(valid_losses))

        k = max(1, int(np.ceil(self.alpha * n)))
        sorted_losses = np.sort(valid_losses)
        tail = sorted_losses[-k:]
        return float(np.mean(tail))

    def visualize_cvar(self, weights, solution_id, save_path=None):
        """Visualiza a distribuição de perdas e o cálculo do CVaR"""
        portfolio_returns = self.hist @ weights
        losses = -portfolio_returns
        valid_losses = losses[np.isfinite(losses)]
        n = len(valid_losses)

        k = max(1, int(np.ceil(self.alpha * n)))
        sorted_losses = np.sort(valid_losses)
        var = sorted_losses[-k]
        cvar = np.mean(sorted_losses[-k:])

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Subplot 1: Histograma de perdas
        ax1.hist(valid_losses, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
        ax1.axvline(var, color='orange', linestyle='--', linewidth=2,
                   label=f'VaR ({self.alpha*100:.0f}%) = {var:.4f}')
        ax1.axvline(cvar, color='red', linestyle='-', linewidth=2,
                   label=f'CVaR = {cvar:.4f}')
        ax1.axvspan(var, valid_losses.max(), alpha=0.3, color='red',
                   label='Cauda (piores retornos)')

        ax1.set_xlabel('Perdas (retornos negativos)', fontsize=11)
        ax1.set_ylabel('Frequência', fontsize=11)
        ax1.set_title(f'Distribuição de Perdas - Solução #{solution_id}',
                     fontsize=12, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)

        # Subplot 2: Pesos da carteira
        significant_weights = [(ticker, w) for ticker, w in zip(self.tickers, weights) if w > 0.001]
        significant_weights.sort(key=lambda x: x[1], reverse=True)

        if significant_weights:
            tickers_sig = [t for t, w in significant_weights]
            weights_sig = [w for t, w in significant_weights]

            colors = plt.cm.viridis(np.linspace(0, 1, len(tickers_sig)))
            ax2.barh(tickers_sig, weights_sig, color=colors, edgecolor='black')

            for i, (ticker, weight) in enumerate(significant_weights):
                ax2.text(weight, i, f' {weight*100:.1f}%', va='center', fontsize=9)

            ax2.set_xlabel('Peso na Carteira', fontsize=11)
            ax2.set_title(f'Composição da Carteira - Solução #{solution_id}',
                         fontsize=12, fontweight='bold')
            ax2.set_xlim(0, max(weights_sig) * 1.15)
            ax2.grid(True, alpha=0.3, axis='x')

        expected_return = -np.dot(weights, self.mu)
        variance = np.dot(weights, self.cov @ weights)

        info_text = (
            f'Retorno Esperado: {-expected_return*100:.2f}%\n'
            f'Variância: {variance:.6f}\n'
            f'CVaR: {cvar:.4f}\n'
            f'Nº ativos: {len(significant_weights)}'
        )

        fig.text(0.5, 0.02, info_text, ha='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout(rect=[0, 0.08, 1, 1])

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"  💾 Visualização salva em: {save_path}")

        plt.close()
        return cvar

    def _evaluate(self, x, out, *args, **kwargs):
        """Avalia uma única carteira"""
        weights = x
        expected_return = -np.dot(weights, self.mu)
        variance = np.dot(weights, self.cov @ weights)
        cvar = self._calculate_cvar(weights)
        out["F"] = [expected_return, variance, cvar]


class CVarVisualizationCallback(Callback):
    """Callback para visualizar CVaR na primeira geração"""

    def __init__(self, problem, output_dir='cvar_visualizations'):
        super().__init__()
        self.problem = problem
        self.output_dir = output_dir
        self.first_gen_visualized = False

    def notify(self, algorithm):
        if not self.first_gen_visualized and algorithm.n_gen == 1:
            self._visualize_first_generation(algorithm)
            self.first_gen_visualized = True

    def _visualize_first_generation(self, algorithm):
        """Cria visualizações do CVaR para algumas soluções"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        print(f"\n{'='*70}")
        print(f"📊 GERANDO VISUALIZAÇÕES DE CVaR DA PRIMEIRA GERAÇÃO")
        print(f"{'='*70}")

        population = algorithm.pop
        X = population.get("X")
        F = population.get("F")

        # Selecionar soluções interessantes
        indices = []
        labels = []

        indices.append(np.argmin(F[:, 0]))
        labels.append("Melhor_Retorno")

        indices.append(np.argmin(F[:, 1]))
        labels.append("Menor_Variancia")

        indices.append(np.argmin(F[:, 2]))
        labels.append("Menor_CVaR")

        np.random.seed(42)
        indices.append(np.random.randint(0, len(X)))
        labels.append("Aleatoria")

        F_normalized = (F - F.min(axis=0)) / (F.max(axis=0) - F.min(axis=0) + 1e-10)
        distances = np.linalg.norm(F_normalized - 0.5, axis=1)
        indices.append(np.argmin(distances))
        # Remover duplicatas
        seen = set()
        unique_indices = []
        unique_labels = []
        for idx, label in zip(indices, labels):
            if idx not in seen:
                seen.add(idx)
                unique_indices.append(idx)
                unique_labels.append(label)

        print(f"  Visualizando {len(unique_indices)} soluções distintas...")

        for i, (idx, label) in enumerate(zip(unique_indices, unique_labels), 1):
            weights = X[idx]
            save_path = os.path.join(self.output_dir, f'cvar_gen1_sol{i}_{label}.png')

            print(f"\n  [{i}/{len(unique_indices)}] Solução #{idx} ({label}):")
            print(f"     Retorno: {-F[idx, 0]*100:.2f}%")
            print(f"     Variância: {F[idx, 1]:.6f}")
            print(f"     CVaR: {F[idx, 2]:.4f}")

            self.problem.visualize_cvar(weights, f"{idx}_{label}", save_path)

        print(f"\n  ✅ {len(unique_indices)} visualizações salvas em: {self.output_dir}/")
        print(f"{'='*70}\n")


def generate_synthetic_data(n_assets=10, n_months=120):
    """Gera dados sintéticos para teste"""
    print("\n📊 Gerando dados sintéticos para teste...")

    # Tickers fictícios
    tickers = [f'ASSET{i+1}' for i in range(n_assets)]

    # Retornos aleatórios com alguma estrutura
    np.random.seed(42)
    returns = np.random.multivariate_normal(
        mean=np.random.uniform(0.005, 0.02, n_assets),
        cov=np.random.uniform(0.0001, 0.001, (n_assets, n_assets)) *
            np.eye(n_assets) + 0.0001,
        size=n_months
    )

    mean_returns = returns.mean(axis=0)
    covariance_matrix = np.cov(returns.T)

    print(f"  ✅ Dados gerados:")
    print(f"     Ativos: {n_assets}")
    print(f"     Meses de histórico: {n_months}")
    print(f"     Retorno médio: {mean_returns.mean()*100:.2f}%")

    return mean_returns, covariance_matrix, returns, tickers


def main():
    """Função principal de teste"""
    print("="*70)
    print("🧪 TESTE DE VISUALIZAÇÃO DE CVaR")
    print("="*70)

    # Gerar dados sintéticos
    mean_returns, cov_matrix, returns_history, tickers = generate_synthetic_data(
        n_assets=10, n_months=120
    )

    # Criar problema
    problem = TestPortfolioProblem(
        mean_returns=mean_returns,
        covariance_matrix=cov_matrix,
        returns_history=returns_history,
        tickers=tickers
    )

    # Criar algoritmo
    ref_point = np.array([[0.3, 0.2, 0.2]])  # Perfil moderado

    sampling = SimplexSamplingCardConstraint(max_assets=8)
    crossover = SimplexCrossoverCardConstraint(max_assets=8, eta=15.0)
    mutation = SimplexMutationCardConstraint(max_assets=8, eta=15.0)

    algorithm = RNSGA2(
        ref_points=ref_point,
        pop_size=50,
        crossover=crossover,
        mutation=mutation,
        sampling=sampling,
        epsilon=0.01,
        extreme_points_as_reference_points=False,
        normalization="front",
    )

    # Criar callback
    callback = CVarVisualizationCallback(problem=problem)

    # Executar otimização
    print("\n🚀 Executando otimização...")
    result = minimize(
        problem,
        algorithm,
        ('n_gen', 10),  # Apenas 10 gerações para teste rápido
        callback=callback,
        verbose=True
    )

    print("\n✅ Teste concluído!")
    print(f"\nAs visualizações foram salvas no diretório: cvar_visualizations/")
    print("\nEssas imagens ilustram como o CVaR varia entre diferentes soluções,")
    print("mostrando que não é possível pré-calcular o CVaR pois ele depende")
    print("dos pesos específicos de cada solução candidata.")


if __name__ == "__main__":
    main()
