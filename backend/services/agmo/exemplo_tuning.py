"""
Exemplos de Uso do Sistema de Tuning de Hiperparâmetros

Este script demonstra como utilizar o HyperparameterTuningService para:
1. Analisar convergência do algoritmo
2. Realizar grid search de hiperparâmetros
3. Encontrar a configuração ótima

Para executar:
    python exemplo_tuning.py

Autor: Sistema de Otimização de Portfólio - TCC
"""

import sys
import os
import logging
from datetime import datetime

# Adiciona o diretório raiz ao path para importações
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app
from models import db, Ativo
from services.agmo.hyperparameter_tuning_service import HyperparameterTuningService

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def exemplo_1_analise_convergencia():
    """
    Exemplo 1: Análise de Convergência

    Analisa como o algoritmo converge ao longo das gerações.
    Útil para determinar o número mínimo de gerações necessárias.
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 1: ANÁLISE DE CONVERGÊNCIA")
    print("=" * 80)
    print("\nObjetivo: Determinar quantas gerações são necessárias para convergência\n")

    app = create_app()

    # Busca alguns ativos para teste
    with app.app_context():
        ativos = db.session.query(Ativo).limit(10).all()
        ids_ativos = [a.id for a in ativos]
        print(f"Usando {len(ids_ativos)} ativos para análise: {[a.ticker for a in ativos]}\n")

    # Cria o serviço de tuning
    tuning_service = HyperparameterTuningService(app)

    # Executa análise de convergência
    print("Executando análise de convergência...")
    print("- População: 100")
    print("- Gerações máximas: 200")
    print("- Execuções: 5 (para análise estatística)")
    print("\nIsso pode levar alguns minutos...\n")

    try:
        resultados = tuning_service.convergence_analysis(
            ids_ativos=ids_ativos,
            nivel_risco='moderado',
            max_generations=50,
            population_size=100,
            n_runs=1
        )

        print("\n✅ Análise concluída!")
        print(f"\n📊 Resultados:")
        print(f"   - Número de execuções: {resultados['n_runs']}")
        print(f"   - Geração média de convergência: {resultados['convergence_mean']:.1f}")
        print(f"   - Desvio padrão: {resultados['convergence_std']:.1f}")
        print(f"\n💡 Recomendação: Use pelo menos {int(resultados['convergence_mean'] + resultados['convergence_std'])} gerações")
        print(f"\n📁 Gráficos salvos em: tuning_results/")

    except Exception as e:
        logger.error(f"Erro na análise de convergência: {e}")
        raise

def exemplo_2_grid_search_completo():
    """
    Exemplo 2: Grid Search Completo (para TCC)

    Teste abrangente para inclusão no TCC.
    Testa mais configurações e executa mais vezes para resultados robustos.
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 3: GRID SEARCH COMPLETO (PARA TCC)")
    print("=" * 80)
    print("\nObjetivo: Análise abrangente para fundamentar escolha de hiperparâmetros\n")

    app = create_app()

    # Busca ativos
    with app.app_context():
        ativos = db.session.query(Ativo).limit(15).all()
        ids_ativos = [a.id for a in ativos]
        print(f"Usando {len(ids_ativos)} ativos: {[a.ticker for a in ativos]}\n")

    # Cria o serviço
    tuning_service = HyperparameterTuningService(app)

    # Configurações abrangentes
    population_sizes = [50, 100, 150, 200, 300]
    generation_counts = [25, 50, 75, 100, 150, 200]

    print("Configurações a testar:")
    print(f"   - Tamanhos de população: {population_sizes}")
    print(f"   - Números de gerações: {generation_counts}")
    print(f"   - Execuções por configuração: 10 (para análise estatística robusta)")
    print(f"   - Total de execuções: {len(population_sizes) * len(generation_counts) * 10}")
    print("\n⚠️  ATENÇÃO: Isso pode levar HORAS para completar!")
    print("   Considere executar em um servidor ou durante a noite.\n")

    resposta = input("Deseja continuar? (s/n): ")
    if resposta.lower() != 's':
        print("Operação cancelada.")
        return

    try:
        summary = tuning_service.grid_search(
            ids_ativos=ids_ativos,
            population_sizes=population_sizes,
            generation_counts=generation_counts,
            n_runs=10,
            time_limit=None  # Sem limite de tempo
        )

        print("\n✅ Grid Search Completo concluído!")
        print(f"\n📊 Resumo dos Resultados:")
        print(summary.to_string())

        # Análise detalhada
        best = summary.iloc[0]
        print(f"\n🏆 Configuração Ótima:")
        print(f"   - População: {int(best['population_size'])}")
        print(f"   - Gerações: {int(best['generations'])}")
        print(f"   - Hypervolume: {best['final_hypervolume_mean']:.6f} (±{best['final_hypervolume_std']:.6f})")
        print(f"   - Spread: {best['final_spread_mean']:.6f} (±{best['final_spread_std']:.6f})")
        print(f"   - Spacing: {best['final_spacing_mean']:.6f} (±{best['final_spacing_std']:.6f})")
        print(f"   - Tamanho Pareto: {best['pareto_size_mean']:.1f} (±{best['pareto_size_std']:.1f})")
        print(f"   - Tempo médio: {best['execution_time_mean']:.2f}s (±{best['execution_time_std']:.2f}s)")

        # Exporta todos os resultados
        filename = tuning_service.export_results()
        print(f"\n📁 Todos os resultados exportados para: {filename}")
        print(f"📁 Gráficos e tabelas em: tuning_results/")

        print("\n💡 Recomendações para o TCC:")
        print("   1. Use os gráficos gerados para o capítulo de metodologia")
        print("   2. Inclua a tabela de resultados completa em um apêndice")
        print("   3. Discuta o trade-off qualidade vs tempo computacional")
        print("   4. Compare diferentes perfis de risco com a configuração ótima")

    except Exception as e:
        logger.error(f"Erro no grid search completo: {e}")
        raise

def exemplo_3_quick_test():
    """
    Exemplo 3: Teste Rápido

    Teste rápido apenas para validar que tudo está funcionando.
    Ideal para desenvolvimento e debugging.
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 5: TESTE RÁPIDO (DESENVOLVIMENTO)")
    print("=" * 80)
    print("\nObjetivo: Validar que o sistema está funcionando corretamente\n")

    app = create_app()

    # Busca ativos
    with app.app_context():
        ativos = db.session.query(Ativo).limit(5).all()
        ids_ativos = [a.id for a in ativos]
        print(f"Usando apenas {len(ids_ativos)} ativos para teste rápido\n")

    tuning_service = HyperparameterTuningService(app)

    print("Executando teste rápido:")
    print("   - População: [50, 100]")
    print("   - Gerações: [25, 50]")
    print("   - 2 execuções por configuração")
    print("\nIsso deve levar apenas alguns minutos...\n")

    try:
        summary = tuning_service.grid_search(
            ids_ativos=ids_ativos,
            population_sizes=[50, 100],
            generation_counts=[25, 50],
            n_runs=2
        )

        print("\n✅ Teste rápido concluído com sucesso!")
        print(f"\n📊 Resultados:")
        print(summary.to_string())

        best_config = tuning_service.get_best_configuration()
        print(f"\n🏆 Melhor configuração: {best_config}")

    except Exception as e:
        logger.error(f"Erro no teste rápido: {e}")
        raise


def exemplo_4_tuning_adaptativo():
    """
    Exemplo 4: Tuning Adaptativo por Quantidade de Ativos

    Este é o exemplo MAIS IMPORTANTE para otimização de performance!
    Determina automaticamente a melhor configuração para cada quantidade
    de ativos, salvando no banco para uso futuro.
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 6: TUNING ADAPTATIVO POR QUANTIDADE DE ATIVOS")
    print("=" * 80)
    print("\nObjetivo: Determinar configuração ótima para diferentes números de ativos\n")
    print("⚡ ESTE EXEMPLO OTIMIZA O TEMPO DE EXECUÇÃO FUTURO!")
    print("   Depois de executar, o sistema automaticamente usará a")
    print("   configuração ótima baseada no número de ativos.\n")

    app = create_app()

    tuning_service = HyperparameterTuningService(app)

    # Configurações do tuning
    asset_ranges = [10, 15, 20]  # Quantidades de ativos a testar
    population_sizes = [50, 100, 200, 300]
    generation_counts = [25, 50, 100, 200]

    # asset_ranges = [5, 10]  # Quantidades de ativos a testar
    # population_sizes = [50, 100]
    # generation_counts = [25, 50]

    n_runs = 3  # Para análise estatística robusta

    print("📋 Configuração do Tuning Adaptativo:")
    print(f"   - Quantidades de ativos: {asset_ranges}")
    print(f"   - Populações: {population_sizes}")
    print(f"   - Gerações: {generation_counts}")
    print(f"   - Execuções por configuração: {n_runs}")
    print(f"\n   Total de otimizações:")
    print(f"   {len(asset_ranges)} ativos × {len(population_sizes)} pop × "
          f"{len(generation_counts)} gen × {n_runs} runs")
    print(f"   = {len(asset_ranges) * len(population_sizes) * len(generation_counts) * n_runs} execuções")
    print(f"\n⏱️  Estimativa de tempo: 4-8 HORAS")
    print(f"   Recomendação: Execute durante a noite ou fim de semana\n")

    resposta = input("Deseja continuar? (s/n): ")
    if resposta.lower() != 's':
        print("Operação cancelada.")
        return

    try:
        print("\n🚀 Iniciando Tuning Adaptativo...\n")
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

        df_optimal = tuning_service.adaptive_tuning_by_num_assets(
            asset_ranges=asset_ranges,
            nivel_risco='moderado',
            population_sizes=population_sizes,
            generation_counts=generation_counts,
            n_runs=n_runs,
            save_to_db=True
        )

        print("\n" + "=" * 80)
        print("✅ TUNING ADAPTATIVO CONCLUÍDO COM SUCESSO!")
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        print("=" * 80)

        if not df_optimal.empty:
            print("\n📊 Configurações Ótimas Encontradas:\n")
            print(df_optimal[[
                'num_ativos', 'population_size', 'generations',
                'hypervolume_mean', 'execution_time_mean'
            ]].to_string(index=False))

            print("\n💡 Próximos Passos:")
            print("   1. Essas configurações foram salvas no banco de dados")
            print("   2. Quando você otimizar carteiras, o sistema automaticamente")
            print("      usará a melhor configuração baseada no número de ativos")
            print("   3. Exemplo:")
            print("      - 5 ativos → usa config ótima para 5 ativos")
            print("      - 12 ativos → usa config ótima para 10 ativos (mais próxima)")
            print("      - 18 ativos → usa config ótima para 20 ativos (mais próxima)")

            print("\n🎯 Benefícios:")
            print("   - Otimizações mais rápidas para poucos ativos")
            print("   - Melhor qualidade para muitos ativos")
            print("   - Zero configuração manual necessária!")

        print(f"\n📁 Arquivos gerados:")
        print(f"   - CSV: tuning_results/adaptive_tuning_*.csv")
        print(f"   - Gráfico: tuning_results/adaptive_tuning_plot_*.png")
        print(f"   - Banco de dados: hyperparameter_configs (tabela)")

    except Exception as e:
        logger.error(f"Erro no tuning adaptativo: {e}")
        raise


def exemplo_5_testar_auto_lookup():
    """
    Exemplo 5: Testar Auto-Lookup de Configurações

    Demonstra como o sistema busca automaticamente a melhor configuração.
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 7: TESTE DE AUTO-LOOKUP")
    print("=" * 80)
    print("\nObjetivo: Demonstrar busca automática de configurações ótimas\n")

    app = create_app()

    # Testa com diferentes quantidades de ativos
    test_quantities = [5, 8, 12, 18, 22]

    print("🔍 Testando auto-lookup para diferentes quantidades de ativos:\n")

    for num_ativos in test_quantities:
        print(f"\n{'='*60}")
        print(f"Testando com {num_ativos} ativos:")
        print(f"{'='*60}")

        # Busca configuração do banco
        with app.app_context():
            from models import HyperparameterConfig

            config = HyperparameterConfig.get_optimal_config(
                num_ativos=num_ativos,
                nivel_risco='neutro'
            )

            if config:
                print(f"✅ Configuração encontrada!")
                print(f"   📊 População: {config.population_size}")
                print(f"   📊 Gerações: {config.generations}")
                print(f"   🎯 Configuração baseada em: {config.num_ativos} ativos")
                print(f"   📅 Tuning realizado em: {config.tuning_date.strftime('%Y-%m-%d')}")
                print(f"   ⏱️  Tempo esperado: {config.execution_time_mean:.2f}s")
            else:
                print(f"⚠️  Configuração não encontrada")
                print(f"   Será usado: População=100, Gerações=50 (padrão)")

    print("\n" + "=" * 80)
    print("💡 Como funciona o Auto-Lookup:")
    print("=" * 80)
    print("1. Sistema recebe pedido de otimização com N ativos")
    print("2. Busca no banco configuração para N ativos")
    print("3. Se não encontrar exata, busca a mais próxima (±2 ativos)")
    print("4. Se ainda não encontrar, usa configuração padrão")
    print("5. Otimização executa com parâmetros ótimos automaticamente!")
    print("\n✅ ZERO configuração manual necessária!")


def menu_principal():
    """Menu principal para escolher qual exemplo executar."""
    print("\n" + "=" * 80)
    print("SISTEMA DE TUNING DE HIPERPARÂMETROS - EXEMPLOS")
    print("=" * 80)
    print("\nEscolha o exemplo que deseja executar:\n")
    print("1. Análise de Convergência (recomendado para começar)")
    print("2. Grid Search Completo (para TCC - DEMORADO)")
    print("3. Teste Rápido (validação)")
    print("4. Tuning Adaptativo por Quantidade de Ativos ⚡ RECOMENDADO!")
    print("5. Testar Auto-Lookup de Configurações")
    print("0. Sair")

    escolha = input("\nDigite o número do exemplo: ")

    exemplos = {
        '1': exemplo_1_analise_convergencia,
        '2': exemplo_2_grid_search_completo,
        '3': exemplo_3_quick_test,
        '4': exemplo_4_tuning_adaptativo,
        '5': exemplo_5_testar_auto_lookup,
    }

    if escolha in exemplos:
        try:
            exemplos[escolha]()
        except KeyboardInterrupt:
            print("\n\n⚠️  Operação interrompida pelo usuário.")
        except Exception as e:
            print(f"\n❌ Erro durante execução: {e}")
            logger.exception("Erro detalhado:")
    elif escolha == '0':
        print("\nSaindo...")
    else:
        print("\n❌ Opção inválida!")


if __name__ == "__main__":
    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\n\nPrograma encerrado pelo usuário.")
    except Exception as e:
        logger.exception("Erro fatal:")
        print(f"\n❌ Erro fatal: {e}")
