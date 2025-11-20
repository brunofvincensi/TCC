"""
Exemplo de Uso do R-NSGA-II Tuning

Script para executar análise de tuning específica para R-NSGA-II.

Este script entende que o hipervolume pode cair durante a convergência
(comportamento esperado do R-NSGA-II ao focar no reference point).
"""

import sys
import os
import logging
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app import create_app
from services.agmo.rnsga2_tuning import RNSGA2TuningService

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Executa análise de tuning para R-NSGA-II.
    """
    print("\n" + "=" * 80)
    print("R-NSGA-II HYPERPARAMETER TUNING")
    print("=" * 80)
    print("\n📌 Objetivo:")
    print("   Analisar o comportamento de convergência do R-NSGA-II com")
    print("   diferentes combinações de hiperparâmetros.")
    print("\n🔬 O que este script faz:")
    print("   - Testa múltiplas combinações de:")
    print("     • Quantidade de ativos")
    print("     • Tamanho da população")
    print("     • Número de gerações")
    print("   - Captura evolução do Hypervolume em cada geração")
    print("   - Gera gráficos mostrando padrões de convergência")
    print("   - Identifica configurações ótimas")
    print("\n⚠️  IMPORTANTE sobre R-NSGA-II:")
    print("   O HV pode CAIR durante execução (normal!)")
    print("   Isso ocorre porque o R-NSGA-II foca em uma região específica")
    print("   baseada no reference point, perdendo diversidade temporariamente.")
    print()

    # Configurações de teste
    print("=" * 80)
    print("CONFIGURAÇÃO DO TESTE")
    print("=" * 80)
    print()

    # Opções pré-definidas
    print("Escolha o perfil de teste:")
    print()
    print("1. 🚀 TESTE RÁPIDO (5-10 min)")
    print("   - 1 quantidade de ativos (5)")
    print("   - 2 populações (50, 100)")
    print("   - 2 gerações (25, 50)")
    print("   - 2 execuções por config")
    print("   - Total: 8 execuções")
    print()
    print("2. 📊 TESTE PADRÃO (30-60 min)")
    print("   - 2 quantidades de ativos (5, 10)")
    print("   - 3 populações (50, 100, 150)")
    print("   - 3 gerações (25, 50, 100)")
    print("   - 3 execuções por config")
    print("   - Total: 54 execuções")
    print()
    print("3. 🔬 TESTE COMPLETO (2-4 horas)")
    print("   - 3 quantidades de ativos (5, 10, 15)")
    print("   - 4 populações (50, 100, 150, 200)")
    print("   - 4 gerações (25, 50, 100, 150)")
    print("   - 3 execuções por config")
    print("   - Total: 144 execuções")
    print()
    print("4. ⚙️  PERSONALIZADO")
    print()

    choice = input("Digite sua escolha (1-4): ").strip()

    if choice == '1':
        asset_quantities = [10]
        population_sizes = [50, 100]
        generation_counts = [25, 50]
        n_runs = 2
    elif choice == '2':
        asset_quantities = [90]
        population_sizes = [50, 100, 150]
        generation_counts = [25, 50, 100]
        n_runs = 1
    elif choice == '3':
        asset_quantities = [5, 10, 15]
        population_sizes = [50, 100, 150, 200]
        generation_counts = [25, 50, 100, 150]
        n_runs = 3
    elif choice == '4':
        print("\n--- Configuração Personalizada ---")
        asset_quantities = [int(x) for x in input("Quantidades de ativos (separados por espaço): ").split()]
        population_sizes = [int(x) for x in input("Tamanhos de população (separados por espaço): ").split()]
        generation_counts = [int(x) for x in input("Números de gerações (separados por espaço): ").split()]
        n_runs = int(input("Execuções por configuração: "))
    else:
        print("❌ Opção inválida!")
        return

    # Resumo
    total_configs = len(asset_quantities) * len(population_sizes) * len(generation_counts) * n_runs
    print()
    print("=" * 80)
    print("RESUMO DA CONFIGURAÇÃO")
    print("=" * 80)
    print(f"Quantidades de ativos: {asset_quantities}")
    print(f"Tamanhos de população: {population_sizes}")
    print(f"Números de gerações: {generation_counts}")
    print(f"Execuções por config: {n_runs}")
    print(f"\n📊 Total de execuções: {total_configs}")
    print()

    # Confirmação
    confirm = input("Deseja continuar? (s/n): ").strip().lower()
    if confirm != 's':
        print("\n❌ Operação cancelada.")
        return

    # Executa tuning
    print()
    print("=" * 80)
    print("INICIANDO TUNING...")
    print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    print("=" * 80)
    print()

    app = create_app()
    tuning_service = RNSGA2TuningService(app)

    try:
        df_results = tuning_service.run_tuning_grid(
            asset_quantities=asset_quantities,
            population_sizes=population_sizes,
            generation_counts=generation_counts,
            n_runs=n_runs,
            risk_level='moderado',
            save_to_db=True  # Salva configurações ótimas no banco
        )

        print()
        print("=" * 80)
        print("✅ TUNING CONCLUÍDO COM SUCESSO!")
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        print("=" * 80)
        print()

        # Mostra resumo
        if not df_results.empty:
            print("📊 RESUMO DOS RESULTADOS:")
            print()

            # Agrupa e mostra médias
            summary = df_results.groupby(['num_assets', 'population_size', 'generations']).agg({
                'final_hv': ['mean', 'std'],
                'max_hv': 'mean',
                'execution_time': 'mean',
                'convergence_generation': 'mean'
            }).round(4)

            print(summary)
            print()

            print("📁 ARQUIVOS GERADOS:")
            print("   - rnsga2_tuning_results/tuning_results_*.csv")
            print("   - rnsga2_tuning_results/hv_histories_*.json")
            print("   - rnsga2_tuning_results/hv_evolution_*assets_*.png")
            print("   - rnsga2_tuning_results/summary_comparison_*.png")
            print()

            print("💾 BANCO DE DADOS:")
            print("   - Configurações ótimas salvas na tabela hyperparameter_configs")
            print("   - Sistema usará automaticamente para otimizações futuras")
            print()

            print("💡 PRÓXIMOS PASSOS:")
            print("   1. Analise os gráficos de evolução de HV")
            print("   2. Identifique o ponto de convergência em cada configuração")
            print("   3. Compare HV máximo vs HV final (normal diferença no R-NSGA-II)")
            print("   4. As melhores configurações já estão salvas no banco!")
            print()

    except Exception as e:
        logger.exception("Erro durante o tuning:")
        print()
        print("=" * 80)
        print("❌ ERRO DURANTE EXECUÇÃO")
        print("=" * 80)
        print(f"Erro: {e}")
        print()
        print("Verifique os logs acima para mais detalhes.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação interrompida pelo usuário.")
    except Exception as e:
        logger.exception("Erro fatal:")
        print(f"\n❌ Erro fatal: {e}")
