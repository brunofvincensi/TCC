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
    WEIGHTS_CONFIG
)
from services.agmo.tuning import (
    ConvergenceTracker
)
from models.hyperparameter_config import HyperparameterConfig
from models import db, Asset, AssetType
import time
import numpy as np

def exemplo_comparacao_multiplas_execucoes():
    """
    Exemplo avançado: compara a convergência de múltiplas execuções para diferentes
    quantidades de ativos e salva a melhor configuração no banco de dados.

    Para cada quantidade de ativos:
    - Testa diferentes configurações de população e gerações
    - Executa cada configuração X vezes para obter média (evitar outliers)
    - Calcula o melhor trade-off (hypervolume/tempo)
    - Salva a melhor configuração na tabela HyperparameterConfig
    """
    from services.agmo.tuning import plot_multiple_runs_comparison

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
        {'pop': 100, 'gen': 50},
        {'pop': 150, 'gen': 150},
    ]

    # Para cada quantidade de ativos
    for num_assets in asset_quantities:
        with app.app_context():
            asset_ids = [row[0] for row in db.session.query(Asset.id).filter(Asset.type == AssetType.STOCK).limit(num_assets).all()]

        print(f"\nCalculando pontos de referência fixos...")
        print(f"   Executando configuração de referência para estabelecer baseline...")

        # Executa uma configuração de referência para estimar ideal_point e nadir_point
        # Usa a maior configuração para obter os melhores resultados possíveis
        reference_service = Nsga2OtimizacaoService(
            app=app,
            restricted_asset_ids=[],
            risk_level=risk_level,
            years_period=5,
            show_chart=False,
            asset_ids=asset_ids
        )

        reference_tracker = ConvergenceTracker(
            reference_points_rnsga2=REFERENCE_POINTS_CONFIG[risk_level],
            weights=WEIGHTS_CONFIG
        )

        # Executa com a maior quantidade de ativos e melhor configuração
        reference_service.optimize(
            population_size=150,
            generations=200,  # Mais gerações para garantir boa convergência
            convergence_tracker=reference_tracker,
            max_assets=num_assets,
            use_optimal_config=False
        )

        # Extrai os pontos de referência fixos do tracker de referência
        # - ideal_point: mínimo acumulado (melhor caso)
        # - nadir_point: máximo acumulado (pior caso)
        fixed_ideal_point = reference_tracker.ideal_point.copy()
        fixed_nadir_point = reference_tracker.nadir_point.copy()

        print(f"\n   Pontos de referência calculados:")
        print(f"      Ideal point: {fixed_ideal_point}")
        print(f"      Nadir point: {fixed_nadir_point}")

        print(f"\n{'='*80}")
        print(f"Testando com {num_assets} ativos")
        print(f"{'='*80}\n")

        # Armazena resultados de todas as configurações para esta quantidade de ativos
        config_results = []

        # Testa cada configuração
        for config_idx, config in enumerate(configs, 1):
            pop_size = config['pop']
            gen_count = config['gen']
            config_label = f'Pop={pop_size}, Gen={gen_count}'

            print(f"\nConfiguração {config_idx}/{len(configs)}: {config_label}")
            print(f"   Executando 10 vezes para obter média...")

            # Armazena resultados das 3 execuções
            run_hypervolumes = []
            run_execution_times = []
            run_convergence_gens = []
            run_histories = []

            # Executa 10 vezes a mesma configuração
            for run_num in range(1, 11):
                print(f"\nExecução {run_num}/10...")

                service = Nsga2OtimizacaoService(
                    app=app,
                    restricted_asset_ids=[],
                    risk_level=risk_level,
                    years_period=5,
                    show_chart=False,
                    fixed_ideal_point=fixed_ideal_point,
                    fixed_nadir_point=fixed_nadir_point,
                    asset_ids=asset_ids
                )

                tracker = ConvergenceTracker(
                    reference_points_rnsga2=REFERENCE_POINTS_CONFIG[risk_level],
                    weights=WEIGHTS_CONFIG,
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

                # Printa os valores reais dos objetivos (sem normalização)
                if hasattr(tracker, '_all_pareto_fronts') and len(tracker._all_pareto_fronts) > 0:
                    all_fronts = np.vstack(tracker._all_pareto_fronts)
                    print(f"         Min observado: {np.min(all_fronts, axis=0)}")
                    print(f"         Max observado: {np.max(all_fronts, axis=0)}")
                    print(f"         Ideal fixo: {fixed_ideal_point}")
                    print(f"         Nadir fixo: {fixed_nadir_point}")

                # Hypervolume final
                final_hypervolume = history['r_hypervolume'][-1] if history['r_hypervolume'] else 0
                run_hypervolumes.append(final_hypervolume)

                # Tempo de execução
                run_execution_times.append(execution_time)

                # Geração de convergência
                if tracker.has_converged(window=10, threshold=0.01):
                    conv_gen = tracker.get_convergence_generation(window=10, threshold=0.01)
                    run_convergence_gens.append(conv_gen if conv_gen is not None else gen_count)
                else:
                    run_convergence_gens.append(gen_count)

                print(f"HV: {final_hypervolume:.6e}, Tempo: {execution_time:.2f}s, Conv: Gen {run_convergence_gens[-1]}")

            # Calcula médias das 3 execuções
            mean_hypervolume = np.mean(run_hypervolumes)
            mean_execution_time = np.mean(run_execution_times)
            valid_conv_gens = [g for g in run_convergence_gens if g is not None]
            mean_convergence_gen = np.mean(valid_conv_gens) if valid_conv_gens else gen_count

            # Calcula trade-off (quanto maior, melhor)
            trade_off_score = mean_hypervolume / mean_execution_time if mean_execution_time > 0 else 0

            print(f"\n Mádias da configuração:")
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

        # Mostra resumo de todas as configurações testadas
        for i, result in enumerate(config_results, 1):
            print(f"{i}. {result['label']}:")
            print(f"   Hypervolume médio:  {result['hypervolume_mean']:.6e}")
            print(f"   Tempo médio:        {result['execution_time_mean']:.2f}s")
            print(f"   Convergência média: Gen {result['convergence_generation_mean']:.1f}")
            print(f"   Trade-off Score:    {result['trade_off_score']:.6e}")
            print()

        # Função para comparar configurações priorizando hipervolume
        def compare_configs(config1, config2):
            """
            Compara duas configurações priorizando hipervolume.
            Retorna config1 se for melhor, config2 caso contrário.
            """
            hv1 = config1['hypervolume_mean']
            hv2 = config2['hypervolume_mean']
            time1 = config1['execution_time_mean']
            time2 = config2['execution_time_mean']

            # Calcula diferença relativa entre hipervolumes
            # Usa o maior hipervolume como base para a comparação percentual
            max_hv = max(hv1, hv2)
            if max_hv > 0:
                relative_diff = abs(hv1 - hv2) / max_hv
            else:
                relative_diff = 0

            # Se hipervolumes são 90% iguais, considera o tempo
            if relative_diff <= 0.10:
                # Hipervolumes muito próximos, escolhe pelo menor tempo
                return config1 if time1 <= time2 else config2
            else:
                # Hipervolumes diferentes, escolhe pelo maior hipervolume
                return config1 if hv1 > hv2 else config2

        # Encontra a melhor configuração usando comparação customizada
        from functools import reduce
        best_config = reduce(compare_configs, config_results)
        best_idx = config_results.index(best_config) + 1

        # Explica o critério de seleção
        print(f"\n{'='*80}")
        print(f"Critérios de seleção:")
        print(f"   ✓ Prioridade: HIPERVOLUME (qualidade da solução)")
        print(f"   ✓ Tempo só é considerado se hipervolumes forem 90% iguais")
        print(f"   ✓ Diferença tolerada: ≤ 10% entre hipervolumes")

        # Verifica se houve empate de hipervolume na escolha final
        if len(config_results) > 1:
            # Compara a melhor com a segunda melhor para ver se foi por tempo ou hipervolume
            other_configs = [c for c in config_results if c != best_config]
            for other in other_configs:
                max_hv = max(best_config['hypervolume_mean'], other['hypervolume_mean'])
                if max_hv > 0:
                    rel_diff = abs(best_config['hypervolume_mean'] - other['hypervolume_mean']) / max_hv
                    if rel_diff <= 0.10:
                        print(f"  Hipervolume similar detectado (±{rel_diff*100:.1f}%), tempo foi considerado")
                        break
        print(f"{'='*80}")

        print(f"MELHOR CONFIGURAÇÃO: #{best_idx} - {best_config['label']}")
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

                print(f"Configuração salva no banco de dados (ID: {new_config.id})")

            except Exception as e:
                print(f"Erro ao salvar configuração: {e}")
                db.session.rollback()

        # Gera gráfico de comparação para esta quantidade de ativos
        print(f"\nGerando gráfico de comparação para {num_assets} ativos...")

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
            labels.append(f"{result['label']} (média de 10 runs)")

        plot_multiple_runs_comparison(
            histories=averaged_histories,
            labels=labels,
            title=f"Comparação de Configurações - {num_assets} Ativos (Média de 10 Execuções)",
            save_path=f'comparison_{num_assets}_assets.png',
            show_plot=False
        )

        print(f"   Gráfico salvo: comparison_{num_assets}_assets.png")

    print(f"\n{'='*80}")
    print(f"TUNING COMPLETO!")
    print(f"   Todas as configurações ótimas foram salvas no banco de dados.")
    print(f"   Gráficos de comparação foram gerados para cada quantidade de ativos.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    exemplo_comparacao_multiplas_execucoes()
