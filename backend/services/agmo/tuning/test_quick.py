"""
Teste rápido para verificar o funcionamento do ConvergenceTracker
"""

import numpy as np
from quality_metrics import ConvergenceTracker, QualityMetrics
from convergence_visualization import plot_hypervolume_only, print_convergence_summary

# Cria configuração de teste (simulando R-NSGA2 para perfil moderado)
reference_points = np.array([[0.2, 0.3, 0.3]])
weights = np.array([0.33, 0.34, 0.33])

# Cria tracker
tracker = ConvergenceTracker(
    reference_points_rnsga2=reference_points,
    weights=weights,
    use_r_hv=True
)

print("✅ ConvergenceTracker criado com sucesso!")
print(f"   Usando R-Hypervolume: {tracker.use_r_hv}")
print(f"   Chave de histórico: {tracker.hv_key}")

# Simula algumas gerações
print("\n🔄 Simulando gerações...")

for gen in range(20):
    # Gera fronteira de Pareto simulada (valores aleatórios decrescentes)
    n_solutions = np.random.randint(10, 30)

    # Simula melhoria ao longo das gerações
    base = 1.0 - (gen * 0.03)  # Melhora 3% por geração
    noise = np.random.rand(n_solutions, 3) * 0.1

    pareto_front = np.maximum(base + noise, 0.01)  # Garante valores positivos
    population_fitness = pareto_front.copy()

    # Atualiza tracker
    tracker.update(gen, pareto_front, population_fitness)

    if gen % 5 == 0:
        hv = tracker.history[tracker.hv_key][-1]
        print(f"   Geração {gen:2d}: R-HV = {hv:.6e}")

print("\n✅ Simulação concluída!")

# Imprime resumo
print_convergence_summary(tracker.get_history())

# Gera gráfico
print("\n📊 Gerando gráfico...")
plot_hypervolume_only(
    tracker.get_history(),
    title="Teste: Evolução do R-Hypervolume (Simulado)",
    save_path='test_r_hypervolume.png',
    show_plot=False
)

print("\n✅ Teste concluído! Verifique o arquivo 'test_r_hypervolume.png'")
