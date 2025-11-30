"""
Exemplo de uso integrado do backtest com gráficos e comparação com benchmark.
"""

from datetime import date
from app import create_app
from services.agmo.agmo_service import (
    Nsga2OtimizacaoService,
    save_backtest_chart
)
from services.agmo.comparision.benchmark_comparison import BenchmarkComparison


def complete_example():
    """
    Exemplo completo: Backtest + Gráficos + Comparação com Benchmark
    """
    app = create_app()

    print("\n" + "=" * 80)
    print("🚀 EXEMPLO COMPLETO: BACKTEST COM COMPARAÇÃO DE BENCHMARK")
    print("=" * 80)

    print("\n📋 PASSO 1: Definindo parâmetros do backtest")
    print("─" * 80)

    # Data de referência para otimização (simula que estamos nessa data)
    reference_date = date(2015, 1, 1)

    # Data final do backtest (avalia desempenho até essa data)
    end_date_backtest = date(2024, 12, 31)

    # Parâmetros da otimização
    restricted_asset_ids = []  # Sem restrições de ativos
    risk_level = 'conservador'  # Perfil de risco
    years_period = 10  # Prazo de investimento
    max_assets = 10  # Máximo de ativos no portfolio

    # Ticker do benchmark para comparação (dados obtidos via Yahoo Finance)
    ticker_benchmark = '^BVSP'  # Ibovespa - busca automática via yfinance

    print(f"  Data de referência (otimização): {reference_date}")
    print(f"  Data final (backtest): {end_date_backtest}")
    print(f"  Perfil de risco: {risk_level}")
    print(f"  Prazo: {years_period} anos")
    print(f"  Máximo de ativos: {max_assets}")
    print(f"  Benchmark: {ticker_benchmark}")

    print("\n📊 PASSO 2: Otimizando portfolio")
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

    print(f"\n  ✅ portfolio otimizada com {len(portfolio_otimizada)} ativos")
    print(f"  📅 Dados usados: {resultado_otimizacao['periodo_inicio']} até "
          f"{resultado_otimizacao['periodo_fim']}")

    # Mostrar composição
    print(f"\n  💼 Composição da portfolio:")
    for item in sorted(portfolio_otimizada, key=lambda x: x['weight'], reverse=True):
        print(f"     {item['ticker']:8s} - {item['weight']*100:6.2f}%")

    print("\n📈 PASSO 3: Gerando gráfico de retorno e volatilidade")
    print("─" * 80)

    caminho_grafico_backtest = save_backtest_chart(
        portfolio=portfolio_otimizada,
        start_date=reference_date,
        end_date=end_date_backtest,
        app=app,
        file_name='backtest_retorno_volatilidade.png',
        volatility_window=6  # Janela de 6 meses para volatilidade rolling
    )

    # ========================================================================
    # PASSO 4: COMPARAR COM BENCHMARK
    # ========================================================================
    print("\n🔍 PASSO 4: Comparando com benchmark")
    print("─" * 80)
    print("  💡 Os dados do benchmark serão obtidos automaticamente do Yahoo Finance")
    print("     Não é necessário ter o índice cadastrado no banco de dados!")

    comparador = BenchmarkComparison(app)

    metricas_comparativas = comparador.generate_complete_report(
        portfolio=portfolio_otimizada,
        benchmark_ticker=ticker_benchmark,
        start_date=reference_date,
        end_date=end_date_backtest,
        save_chart=True
    )

    print("\n" + "=" * 80)
    print("✅ RESUMO FINAL")
    print("=" * 80)

    print(f"\n📊 Desempenho da portfolio:")
    print(f"   Retorno Total: {metricas_comparativas['portfolio']['retorno_total']*100:+.2f}%")
    print(f"   Retorno Anualizado: {metricas_comparativas['portfolio']['retorno_anualizado']*100:+.2f}%")
    print(f"   Volatilidade Anualizada: {metricas_comparativas['portfolio']['volatilidade_anualizada']*100:.2f}%")
    print(f"   Sharpe Ratio: {metricas_comparativas['portfolio']['sharpe_ratio']:.3f}")

    print(f"\n📈 Desempenho do Benchmark ({ticker_benchmark}):")
    print(f"   Retorno Total: {metricas_comparativas['benchmark']['retorno_total']*100:+.2f}%")
    print(f"   Retorno Anualizado: {metricas_comparativas['benchmark']['retorno_anualizado']*100:+.2f}%")
    print(f"   Volatilidade Anualizada: {metricas_comparativas['benchmark']['volatilidade_anualizada']*100:.2f}%")
    print(f"   Sharpe Ratio: {metricas_comparativas['benchmark']['sharpe_ratio']:.3f}")

    print(f"\n🎯 Métricas Comparativas:")
    print(f"   Alpha: {metricas_comparativas['comparativas']['alpha']*100:+.2f}%")
    print(f"   Beta: {metricas_comparativas['comparativas']['beta']:.3f}")
    print(f"   Information Ratio: {metricas_comparativas['comparativas']['information_ratio']:.3f}")

    # Conclusão
    alpha = metricas_comparativas['comparativas']['alpha']
    if alpha > 0:
        print(f"\n   ✅ A portfolio SUPEROU o benchmark em {alpha*100:.2f}% ao ano!")
    else:
        print(f"\n   ⚠️  O benchmark SUPEROU a portfolio em {abs(alpha)*100:.2f}% ao ano")

    print(f"\n📁 Arquivos Gerados:")
    print(f"   • Backtest (retorno/volatilidade): {caminho_grafico_backtest}")
    if 'grafico_path' in metricas_comparativas:
        print(f"   • Comparação com benchmark: {metricas_comparativas['grafico_path']}")

    print("\n" + "=" * 80)
    print("🎉 Análise completa concluída com sucesso!")
    print("=" * 80 + "\n")

    return {
        'portfolio': portfolio_otimizada,
        'metricas': metricas_comparativas,
        'graficos': {
            'backtest': caminho_grafico_backtest,
            'comparacao': metricas_comparativas.get('grafico_path')
        }
    }


def simple_backtest_example():
    """
    Exemplo simples: Apenas backtest com gráfico
    """
    app = create_app()

    print("\n" + "=" * 80)
    print("📊 EXEMPLO SIMPLES: BACKTEST COM GRÁFICO")
    print("=" * 80)

    # Otimizar portfolio
    reference_date = date(2020, 1, 1)
    service = Nsga2OtimizacaoService(
        app=app,
        restricted_asset_ids=[],
        risk_level='moderado',
        years_period=5,
        reference_date=reference_date
    )

    resultado = service.optimize(max_assets=10, use_optimal_config=False)

    # Gerar gráfico
    end_date = date(2024, 12, 31)
    save_backtest_chart(
        portfolio=resultado['composicao'],
        start_date=reference_date,
        end_date=end_date,
        app=app
    )

    print("\n✅ Backtest concluído! Verifique o gráfico gerado.\n")


if __name__ == "__main__":
    # Escolha qual exemplo executar:

    # Exemplo completo (backtest + gráficos + comparação)
    complete_example()

    # Apenas o backtest:
    # simple_backtest_example()
