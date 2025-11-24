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
    ConvergenceTracker,
    plot_convergence_evolution,
    plot_hypervolume_only,
    print_convergence_summary
)


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
        weights=WEIGHTS_CONFIG[risk_level],
        use_r_hv=True  # Usa R-HV ao invés de HV tradicional
    )

    print(f"   ✅ Tracker criado com sucesso!\n")

    # Executa otimização COM tracking
    print(f"🚀 Iniciando otimização com tracking de convergência...\n")

    result = service.optimize(
        population_size=100,
        generations=200,
        convergence_tracker=tracker,  # Passa o tracker para o serviço
        max_assets=20,
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
    Exemplo avançado: compara a convergência de múltiplas execuções.
    """
    from services.agmo.tuning import plot_multiple_runs_comparison

    print(f"\n{'='*80}")
    print(f"📊 EXEMPLO: Comparação de Múltiplas Execuções")
    print(f"{'='*80}\n")

    app = create_app()
    risk_level = 'moderado'

    # Lista para armazenar históricos
    histories = []
    labels = []

    # Executa 3 vezes com diferentes configurações
    configs = [
        {'pop': 50, 'gen': 100, 'label': 'Pop=50, Gen=100'},
        {'pop': 100, 'gen': 100, 'label': 'Pop=100, Gen=100'},
        {'pop': 100, 'gen': 150, 'label': 'Pop=100, Gen=150'},
    ]

    for config in configs:
        print(f"\n🚀 Executando: {config['label']}...")

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
            use_r_hv=True
        )

        result = service.optimize(
            population_size=config['pop'],
            generations=config['gen'],
            convergence_tracker=tracker,
            max_assets=10,
            use_optimal_config=False
        )

        histories.append(tracker.get_history())
        labels.append(config['label'])

        print(f"   ✅ Concluído!")

    # Gera gráfico de comparação
    print(f"\n📊 Gerando gráfico de comparação...")
    plot_multiple_runs_comparison(
        histories=histories,
        labels=labels,
        title="Comparação de Configurações - R-Hypervolume",
        save_path='comparison_configs.png',
        show_plot=False
    )

    print(f"\n✅ Comparação concluída!")
    print(f"   Verifique o arquivo 'comparison_configs.png'")


def exemplo_analise_perfis_risco():
    """
    Exemplo: compara a convergência entre diferentes perfis de risco.
    """
    from services.agmo.tuning import plot_multiple_runs_comparison

    print(f"\n{'='*80}")
    print(f"📊 EXEMPLO: Análise de Perfis de Risco")
    print(f"{'='*80}\n")

    app = create_app()

    histories = []
    labels = []

    # Testa cada perfil de risco
    risk_levels = ['conservador', 'moderado', 'arrojado']

    for risk_level in risk_levels:
        print(f"\n🚀 Executando perfil: {risk_level.upper()}...")

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
            use_r_hv=True
        )

        result = service.optimize(
            population_size=100,
            generations=100,
            convergence_tracker=tracker,
            max_assets=10,
            use_optimal_config=False
        )

        histories.append(tracker.get_history())
        labels.append(risk_level.capitalize())

        # Imprime resumo
        print_convergence_summary(tracker.get_history())

    # Gera gráfico de comparação
    print(f"\n📊 Gerando gráfico de comparação entre perfis...")
    plot_multiple_runs_comparison(
        histories=histories,
        labels=labels,
        title="Comparação de Perfis de Risco - R-Hypervolume",
        save_path='comparison_risk_profiles.png',
        show_plot=False
    )

    print(f"\n✅ Análise concluída!")
    print(f"   Verifique o arquivo 'comparison_risk_profiles.png'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Exemplos de Tracking de Convergência')
    parser.add_argument('--exemplo', type=str, default='simples',
                       choices=['simples', 'comparacao', 'perfis'],
                       help='Qual exemplo executar')

    args = parser.parse_args()

    if args.exemplo == 'simples':
        exemplo_simples()
    elif args.exemplo == 'comparacao':
        exemplo_comparacao_multiplas_execucoes()
    elif args.exemplo == 'perfis':
        exemplo_analise_perfis_risco()
    else:
        print(f"❌ Exemplo '{args.exemplo}' não encontrado")
        print(f"   Use: simples, comparacao, ou perfis")
