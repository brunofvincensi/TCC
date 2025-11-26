"""
Exemplo de Uso: Tracking e Visualização de Convergência do R-NSGA2

Este script demonstra como usar o ConvergenceTracker para monitorar a evolução
do R-Hypervolume durante a otimização e gerar gráficos de convergência.
"""

import sys
import os

# Adiciona o diretório backend ao path para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from app import create_app
from services.agmo.agmo_service import (
    Nsga2OtimizacaoService,
    REFERENCE_POINTS_CONFIG,
    WEIGHTS_CONFIG,
    IDEAL_POINT_PORTFOLIO,
    NADIR_POINT_PORTFOLIO
)
from services.agmo.tuning import (
    ConvergenceTracker,
    plot_convergence_evolution,
    plot_hypervolume_only,
    print_convergence_summary
)
from models.hyperparameter_config import HyperparameterConfig
from models import db
import time
import numpy as np


def exemplo_simples():
    """
    Exemplo simples: otimização com tracking de convergência e visualização.
    """
    print(f"\n{'='*80}")
    print(f"📊 EXEMPLO: Tracking de R-Hypervolume durante Otimização")
    print(f"{'='*80}\n")

    # Cria aplicação Flask
    app = create_app()

    # Configuração
    risk_level = 'moderado'
    years_period = 10
    max_assets = 10

    # Cria o serviço de otimização
    service = Nsga2OtimizacaoService(
        app=app,
        restricted_asset_ids=[],
        risk_level=risk_level,
        years_period=years_period,
        show_chart=False  # Não mostra gráfico de Pareto durante execução
    )

    # Cria o ConvergenceTracker com configuração apropriada para R-NSGA2
    print(f"🎯 Criando ConvergenceTracker para R-NSGA2...")
    print(f"   Perfil de risco: {risk_level}")
    print(f"   Usando R-Hypervolume (R2 indicator)")

    tracker = ConvergenceTracker(
        reference_points_rnsga2=REFERENCE_POINTS_CONFIG[risk_level],
        weights=WEIGHTS_CONFIG[risk_level]
    )

    print(f"   ✅ Tracker criado com sucesso!\n")

    # Executa otimização COM tracking
    print(f"🚀 Iniciando otimização com tracking de convergência...\n")

    result = service.optimize(
        population_size=100,
        generations=200,
        convergence_tracker=tracker,  # Passa o tracker para o serviço
        max_assets=60,
        use_optimal_config=False
    )

    print(f"\n✅ Otimização concluída!")

    # Obtém histórico de métricas
    history = tracker.get_history()

    # Imprime resumo estatístico
    print_convergence_summary(history)

    # Verifica convergência
    if tracker.has_converged(window=10, threshold=0.01):
        conv_gen = tracker.get_convergence_generation(window=10, threshold=0.01)
        print(f"✅ Algoritmo convergiu na geração {conv_gen}")
    else:
        print(f"⚠️  Algoritmo não convergiu completamente")

    # Gera gráficos
    print(f"\n📊 Gerando gráficos de convergência...")

    # 1. Gráfico completo com todas as métricas
    plot_convergence_evolution(
        history=history,
        title=f"Evolução da Convergência - R-NSGA2 ({risk_level.capitalize()})",
        save_path=f'convergence_full_{risk_level}.png',
        show_plot=False  # Não mostra, apenas salva
    )

    # 2. Gráfico focado no R-Hypervolume
    plot_hypervolume_only(
        history=history,
        title=f"Evolução do R-Hypervolume - {risk_level.capitalize()}",
        save_path=f'r_hypervolume_{risk_level}.png',
        show_plot=False
    )

    print(f"\n✅ Exemplo concluído com sucesso!")
    print(f"   Verifique os arquivos PNG gerados no diretório atual.")


def exemplo_comparacao_multiplas_execucoes():
    """
    Exemplo avançado: compara a convergência de múltiplas execuções para diferentes
    quantidades de ativos e salva a melhor configuração no banco de dados.

    Para cada quantidade de ativos:
    - Testa diferentes configurações de população e gerações
    - Executa cada configuração 3 vezes para obter média (evitar outliers)
    - Calcula o melhor trade-off (hypervolume/tempo)
    - Salva a melhor configuração na tabela HyperparameterConfig
    """
    from services.agmo.tuning import plot_multiple_runs_comparison

    print(f"\n{'='*80}")
    print(f"📊 EXEMPLO: Comparação de Múltiplas Execuções por Quantidade de Ativos")
    print(f"{'='*80}\n")

    app = create_app()
    risk_level = 'moderado'

    # # Array de quantidades de ativos para testar
    # asset_quantities = [10, 20, 30, 40, 50, 60]
    #
    # # Configurações de população e gerações para testar
    # configs = [
    #     {'pop': 50, 'gen': 100},
    #     {'pop': 100, 'gen': 100},
    #     {'pop': 100, 'gen': 150},
    #     {'pop': 150, 'gen': 150},
    # ]

    # Array de quantidades de ativos para testar
    asset_quantities = [60]

    # Configurações de população e gerações para testar
    configs = [
        {'pop': 50, 'gen': 100},
        {'pop': 150, 'gen': 150},
    ]

    # Usa pontos de referência TEÓRICOS fixos para normalização consistente
    # Isso evita que o R-Hypervolume caia quando o R-NSGA2 elimina diversidade
    # (comportamento esperado do algoritmo ao convergir para o reference point)
    fixed_ideal_point = IDEAL_POINT_PORTFOLIO.copy()
    fixed_nadir_point = NADIR_POINT_PORTFOLIO.copy()

    print(f"\n📐 USANDO PONTOS DE REFERÊNCIA TEÓRICOS FIXOS:")
    print(f"   Ideal point (melhor caso teórico): {fixed_ideal_point}")
    print(f"     Retorno: {-fixed_ideal_point[0]*100:.2f}%/mês")
    print(f"     Volatilidade: {fixed_ideal_point[1]*100:.3f}%/mês")
    print(f"     Max Drawdown: {fixed_ideal_point[2]*100:.1f}%")
    print(f"\n   Nadir point (pior caso aceitável): {fixed_nadir_point}")
    print(f"     Retorno: {-fixed_nadir_point[0]*100:.2f}%/mês")
    print(f"     Volatilidade: {fixed_nadir_point[1]*100:.3f}%/mês")
    print(f"     Max Drawdown: {fixed_nadir_point[2]*100:.1f}%")
    print(f"\n   🔒 Estes valores serão FIXOS para todas as comparações!")
    print(f"   ✅ R-Hypervolume não cairá artificialmente ao convergir\n")

    # Para cada quantidade de ativos
    for num_assets in asset_quantities:
        print(f"\n{'='*80}")
        print(f"🎯 TESTANDO COM {num_assets} ATIVOS")
        print(f"{'='*80}\n")

        # Armazena resultados de todas as configurações para esta quantidade de ativos
        config_results = []

        # Testa cada configuração
        for config_idx, config in enumerate(configs, 1):
            pop_size = config['pop']
            gen_count = config['gen']
            config_label = f'Pop={pop_size}, Gen={gen_count}'

            print(f"\n📋 Configuração {config_idx}/{len(configs)}: {config_label}")
            print(f"   Executando 3 vezes para obter média...")

            # Armazena resultados das 3 execuções
            run_hypervolumes = []
            run_execution_times = []
            run_convergence_gens = []
            run_histories = []

            # Executa 3 vezes a mesma configuração
            for run_num in range(1, 21):
                print(f"\n   🔄 Execução {run_num}/3...")

                service = Nsga2OtimizacaoService(
                    app=app,
                    restricted_asset_ids=[],
                    risk_level=risk_level,
                    years_period=10,
                    show_chart=False
                )

                tracker = ConvergenceTracker(
                    reference_points_rnsga2=REFERENCE_POINTS_CONFIG[risk_level],
                    weights=WEIGHTS_CONFIG[risk_level],
                    fixed_ideal_point=fixed_ideal_point,
                    fixed_nadir_point=fixed_nadir_point
                )

                # Mede tempo de execução
                start_time = time.time()

                result = service.optimize(
                    population_size=pop_size,
                    generations=gen_count,
                    convergence_tracker=tracker,
                    max_assets=num_assets,
                    use_optimal_config=False
                )

                execution_time = time.time() - start_time

                # Obtém métricas
                history = tracker.get_history()
                run_histories.append(history)

                # Hypervolume final
                final_hypervolume = history['r_hypervolume'][-1] if history['r_hypervolume'] else 0
                run_hypervolumes.append(final_hypervolume)

                # Tempo de execução
                run_execution_times.append(execution_time)

                # Geração de convergência
                if tracker.has_converged(window=10, threshold=0.01):
                    conv_gen = tracker.get_convergence_generation(window=10, threshold=0.01)
                    run_convergence_gens.append(conv_gen)
                else:
                    run_convergence_gens.append(gen_count)  # Não convergiu

                print(f"      ✅ HV: {final_hypervolume:.6e}, Tempo: {execution_time:.2f}s, Conv: Gen {run_convergence_gens[-1]}")

            # Calcula médias das 3 execuções
            mean_hypervolume = np.mean(run_hypervolumes)
            mean_execution_time = np.mean(run_execution_times)
            mean_convergence_gen = np.mean(run_convergence_gens)

            # Calcula trade-off (quanto maior, melhor)
            trade_off_score = mean_hypervolume / mean_execution_time if mean_execution_time > 0 else 0

            print(f"\n   📊 MÉDIAS DA CONFIGURAÇÃO:")
            print(f"      Hypervolume: {mean_hypervolume:.6e}")
            print(f"      Tempo: {mean_execution_time:.2f}s")
            print(f"      Convergência: Gen {mean_convergence_gen:.1f}")
            print(f"      Trade-off Score: {trade_off_score:.6e}")

            # Armazena resultado desta configuração
            config_results.append({
                'population_size': pop_size,
                'generations': gen_count,
                'hypervolume_mean': mean_hypervolume,
                'execution_time_mean': mean_execution_time,
                'convergence_generation_mean': mean_convergence_gen,
                'trade_off_score': trade_off_score,
                'label': config_label,
                'histories': run_histories
            })

        # Mostra resumo de TODAS as configurações testadas
        print(f"\n{'='*80}")
        print(f"📊 RESUMO DE TODAS AS CONFIGURAÇÕES ({num_assets} ATIVOS):")
        print(f"{'='*80}\n")

        for i, result in enumerate(config_results, 1):
            print(f"{i}. {result['label']}:")
            print(f"   Hypervolume médio:  {result['hypervolume_mean']:.6e}")
            print(f"   Tempo médio:        {result['execution_time_mean']:.2f}s")
            print(f"   Convergência média: Gen {result['convergence_generation_mean']:.1f}")
            print(f"   Trade-off Score:    {result['trade_off_score']:.6e}")
            print()

        # Encontra a melhor configuração (maior trade-off)
        best_config = max(config_results, key=lambda x: x['trade_off_score'])
        best_idx = config_results.index(best_config) + 1

        print(f"{'='*80}")
        print(f"🏆 MELHOR CONFIGURAÇÃO: #{best_idx} - {best_config['label']}")
        print(f"   População: {best_config['population_size']}")
        print(f"   Gerações: {best_config['generations']}")
        print(f"   Hypervolume médio: {best_config['hypervolume_mean']:.6e}")
        print(f"   Tempo médio: {best_config['execution_time_mean']:.2f}s")
        print(f"   Convergência média: Gen {best_config['convergence_generation_mean']:.1f}")
        print(f"   Trade-off Score: {best_config['trade_off_score']:.6e}")
        print(f"{'='*80}\n")

        # Salva a melhor configuração no banco de dados
        with app.app_context():
            try:
                # Desativa configurações antigas para esta quantidade de ativos
                HyperparameterConfig.deactivate_all_for_num_assets(
                    num_assets=num_assets,
                    risk_level=risk_level
                )

                # Cria nova configuração
                new_config = HyperparameterConfig(
                    num_assets=num_assets,
                    risk_level=risk_level,
                    population_size=best_config['population_size'],
                    generations=best_config['generations'],
                    crossover_eta=15.0,  # Valores padrão
                    mutation_eta=20.0,   # Valores padrão
                    hypervolume_mean=best_config['hypervolume_mean'],
                    execution_time_mean=best_config['execution_time_mean'],
                    convergence_generation_mean=best_config['convergence_generation_mean'],
                    notes=f"Tuning automático - Trade-off score: {best_config['trade_off_score']:.6e}",
                    is_active=True
                )

                db.session.add(new_config)
                db.session.commit()

                print(f"✅ Configuração salva no banco de dados (ID: {new_config.id})")

            except Exception as e:
                print(f"❌ Erro ao salvar configuração: {e}")
                db.session.rollback()

        # Gera gráfico de comparação para esta quantidade de ativos
        print(f"\n📊 Gerando gráfico de comparação para {num_assets} ativos...")

        # Calcula histórico médio das 3 execuções para cada configuração
        averaged_histories = []
        labels = []

        for result in config_results:
            # Pega os 3 históricos desta configuração
            histories_for_config = result['histories']

            # Calcula a média dos R-Hypervolumes nas mesmas gerações
            # Assume que todos têm o mesmo número de gerações
            avg_history = {
                'generation': histories_for_config[0]['generation'].copy(),
                'r_hypervolume': [],
                'spread': [],
                'spacing': [],
                'pareto_size': [],
                'best_fitness': []
            }

            # Para cada geração, calcula a média entre as 3 execuções
            num_generations = len(histories_for_config[0]['generation'])
            for gen_idx in range(num_generations):
                # Média do R-Hypervolume
                hvs = [h['r_hypervolume'][gen_idx] for h in histories_for_config]
                avg_history['r_hypervolume'].append(np.mean(hvs))

                # Média das outras métricas
                spreads = [h['spread'][gen_idx] for h in histories_for_config]
                avg_history['spread'].append(np.mean(spreads))

                spacings = [h['spacing'][gen_idx] for h in histories_for_config]
                avg_history['spacing'].append(np.mean(spacings))

                sizes = [h['pareto_size'][gen_idx] for h in histories_for_config]
                avg_history['pareto_size'].append(np.mean(sizes))

                fitness = [h['best_fitness'][gen_idx] for h in histories_for_config]
                avg_history['best_fitness'].append(np.mean(fitness))

            averaged_histories.append(avg_history)
            labels.append(f"{result['label']} (média de 3 runs)")

        plot_multiple_runs_comparison(
            histories=averaged_histories,
            labels=labels,
            title=f"Comparação de Configurações - {num_assets} Ativos (Média de 3 Execuções)",
            save_path=f'comparison_{num_assets}_assets.png',
            show_plot=False
        )

        print(f"   ✅ Gráfico salvo: comparison_{num_assets}_assets.png")

    print(f"\n{'='*80}")
    print(f"✅ TUNING COMPLETO!")
    print(f"   Todas as configurações ótimas foram salvas no banco de dados.")
    print(f"   Gráficos de comparação foram gerados para cada quantidade de ativos.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Exemplos de Tracking de Convergência')
    parser.add_argument('--exemplo', type=str, default='simples',
                       choices=['simples', 'comparacao'],
                       help='Qual exemplo executar')

    args = parser.parse_args()

    if args.exemplo == 'simples':
        exemplo_simples()
    elif args.exemplo == 'comparacao':
        exemplo_comparacao_multiplas_execucoes()
    else:
        print(f"Exemplo '{args.exemplo}' não encontrado")
        print(f"Use: simples ou comparacao")
