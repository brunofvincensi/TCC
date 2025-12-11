"""
Exemplo de uso integrado do backtest com gráficos e comparação com benchmark.
"""

from datetime import date
from app import create_app
from services.agmo.agmo_service import (
    Nsga2OtimizacaoService
)
from services.agmo.comparision.benchmark_comparison import BenchmarkComparison


def complete_example():
    """
    Exemplo completo: Backtest + Gráficos + Comparação com Benchmark
    """
    app = create_app()

    # Data de referência para otimização (simula que estamos nessa data)
    reference_date = date(2015, 1, 1)

    # Data final do backtest (avalia desempenho até essa data)
    end_date_backtest = date(2024, 12, 31)

    # Parâmetros da otimização
    restricted_asset_ids = []
    risk_level = 'conservador'
    years_period = 10
    max_assets = 10

    # Ticker do benchmark para comparação (dados obtidos via Yahoo Finance)
    ticker_benchmark = '^BVSP'  # Ibovespa

    print(f"  Data de referência (otimização): {reference_date}")
    print(f"  Data final (backtest): {end_date_backtest}")
    print(f"  Perfil de risco: {risk_level}")
    print(f"  Prazo: {years_period} anos")
    print(f"  Máximo de ativos: {max_assets}")
    print(f"  Benchmark: {ticker_benchmark}")

    print("─" * 80)

    service = Nsga2OtimizacaoService(
        app=app,
        restricted_asset_ids=restricted_asset_ids,
        risk_level=risk_level,
        years_period=years_period,
        reference_date=reference_date
    )

    resultado_otimizacao = service.optimize(
        max_assets=max_assets,
        use_optimal_config=False  # Usar config padrão para exemplo
    )

    portfolio_otimizada = resultado_otimizacao['composicao']

    print("\nComparando com benchmark")
    print("─" * 80)

    comparador = BenchmarkComparison(app)

    metricas_comparativas = comparador.generate_complete_report(
        portfolio=portfolio_otimizada,
        benchmark_ticker=ticker_benchmark,
        start_date=reference_date,
        end_date=end_date_backtest,
        save_chart=True
    )

    print("\n" + "=" * 80)
    print("RESUMO FINAL")
    print("=" * 80)

    print(f"\nDesempenho da portfolio:")
    print(f"   Retorno Total: {metricas_comparativas['portfolio']['retorno_total']*100:+.2f}%")
    print(f"   Retorno Anualizado: {metricas_comparativas['portfolio']['retorno_anualizado']*100:+.2f}%")
    print(f"   Volatilidade Anualizada: {metricas_comparativas['portfolio']['volatilidade_anualizada']*100:.2f}%")
    print(f"   Sharpe Ratio: {metricas_comparativas['portfolio']['sharpe_ratio']:.3f}")

    print(f"\nDesempenho do Benchmark ({ticker_benchmark}):")
    print(f"   Retorno Total: {metricas_comparativas['benchmark']['retorno_total']*100:+.2f}%")
    print(f"   Retorno Anualizado: {metricas_comparativas['benchmark']['retorno_anualizado']*100:+.2f}%")
    print(f"   Volatilidade Anualizada: {metricas_comparativas['benchmark']['volatilidade_anualizada']*100:.2f}%")
    print(f"   Sharpe Ratio: {metricas_comparativas['benchmark']['sharpe_ratio']:.3f}")

    print(f"\nMétricas Comparativas:")
    print(f"   Alpha: {metricas_comparativas['comparativas']['alpha']*100:+.2f}%")
    print(f"   Beta: {metricas_comparativas['comparativas']['beta']:.3f}")

    # Conclusão
    alpha = metricas_comparativas['comparativas']['alpha']
    if alpha > 0:
        print(f"\nA carteira SUPEROU o benchmark em {alpha*100:.2f}% ao ano!")
    else:
        print(f"\nO benchmark SUPEROU a portfolio em {abs(alpha)*100:.2f}% ao ano")

    print(f"\nArquivos Gerados:")
    if 'grafico_path' in metricas_comparativas:
        print(f"   • Comparação com benchmark: {metricas_comparativas['grafico_path']}")

    print("\n" + "=" * 80)
    print("🎉 Análise completa concluída com sucesso!")
    print("=" * 80 + "\n")

    return {
        'portfolio': portfolio_otimizada,
        'metricas': metricas_comparativas,
        'graficos': {
            'comparacao': metricas_comparativas.get('grafico_path')
        }
    }

if __name__ == "__main__":
    complete_example()
