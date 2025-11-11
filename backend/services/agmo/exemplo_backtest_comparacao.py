"""
Exemplo de uso integrado do backtest com gráficos e comparação com benchmark.

Este exemplo demonstra como:
1. Executar um backtest de carteira otimizada
2. Gerar gráficos de retorno e volatilidade
3. Comparar a carteira com um benchmark (ex: Ibovespa)
"""

from datetime import date
from app import create_app
from services.agmo.agmo_service import (
    Nsga2OtimizacaoService,
    salvar_grafico_backtest
)
from services.agmo.benchmark_comparison import BenchmarkComparison


def exemplo_completo():
    """
    Exemplo completo: Backtest + Gráficos + Comparação com Benchmark
    """
    app = create_app()

    print("\n" + "=" * 80)
    print("🚀 EXEMPLO COMPLETO: BACKTEST COM COMPARAÇÃO DE BENCHMARK")
    print("=" * 80)

    # ========================================================================
    # PASSO 1: DEFINIR PARÂMETROS DO BACKTEST
    # ========================================================================
    print("\n📋 PASSO 1: Definindo parâmetros do backtest")
    print("─" * 80)

    # Data de referência para otimização (simula que estamos nessa data)
    data_referencia = date(2015, 1, 1)

    # Data final do backtest (avalia desempenho até essa data)
    data_fim_backtest = date(2024, 12, 31)

    # Parâmetros da otimização
    ids_ativos_restringidos = []  # Sem restrições de ativos
    nivel_risco = 'conservador'  # Perfil de risco
    prazo_anos = 10  # Prazo de investimento
    max_ativos_carteira = 10  # Máximo de ativos na carteira

    # Ticker do benchmark para comparação (dados obtidos via Yahoo Finance)
    ticker_benchmark = '^BVSP'  # Ibovespa - busca automática via yfinance

    print(f"  Data de referência (otimização): {data_referencia}")
    print(f"  Data final (backtest): {data_fim_backtest}")
    print(f"  Perfil de risco: {nivel_risco}")
    print(f"  Prazo: {prazo_anos} anos")
    print(f"  Máximo de ativos: {max_ativos_carteira}")
    print(f"  Benchmark: {ticker_benchmark}")

    # ========================================================================
    # PASSO 2: OTIMIZAR CARTEIRA (usando dados até data_referencia)
    # ========================================================================
    print("\n📊 PASSO 2: Otimizando carteira")
    print("─" * 80)

    service = Nsga2OtimizacaoService(
        app=app,
        ids_ativos_restringidos=ids_ativos_restringidos,
        nivel_risco=nivel_risco,
        prazo_anos=prazo_anos,
        data_referencia=data_referencia  # ✅ Modo backtest ativado
    )

    resultado_otimizacao = service.otimizar(
        max_ativos=max_ativos_carteira,
        use_optimal_config=False  # Usar config padrão para exemplo
    )

    carteira_otimizada = resultado_otimizacao['composicao']

    print(f"\n  ✅ Carteira otimizada com {len(carteira_otimizada)} ativos")
    print(f"  📅 Dados usados: {resultado_otimizacao['periodo_inicio']} até "
          f"{resultado_otimizacao['periodo_fim']}")

    # Mostrar composição
    print(f"\n  💼 Composição da Carteira:")
    for item in sorted(carteira_otimizada, key=lambda x: x['peso'], reverse=True):
        print(f"     {item['ticker']:8s} - {item['peso']*100:6.2f}%")

    # ========================================================================
    # PASSO 3: GERAR GRÁFICO DE BACKTEST (Retorno e Volatilidade)
    # ========================================================================
    print("\n📈 PASSO 3: Gerando gráfico de retorno e volatilidade")
    print("─" * 80)

    caminho_grafico_backtest = salvar_grafico_backtest(
        carteira=carteira_otimizada,
        data_inicio=data_referencia,
        data_fim=data_fim_backtest,
        app=app,
        nome_arquivo='backtest_retorno_volatilidade.png',
        janela_volatilidade=6  # Janela de 6 meses para volatilidade rolling
    )

    # ========================================================================
    # PASSO 4: COMPARAR COM BENCHMARK
    # ========================================================================
    print("\n🔍 PASSO 4: Comparando com benchmark")
    print("─" * 80)
    print("  💡 Os dados do benchmark serão obtidos automaticamente do Yahoo Finance")
    print("     Não é necessário ter o índice cadastrado no banco de dados!")

    comparador = BenchmarkComparison(app)

    metricas_comparativas = comparador.gerar_relatorio_completo(
        carteira=carteira_otimizada,
        ticker_benchmark=ticker_benchmark,
        data_inicio=data_referencia,
        data_fim=data_fim_backtest,
        salvar_grafico=True
    )

    # ========================================================================
    # PASSO 5: RESUMO FINAL
    # ========================================================================
    print("\n" + "=" * 80)
    print("✅ RESUMO FINAL")
    print("=" * 80)

    print(f"\n📊 Desempenho da Carteira:")
    print(f"   Retorno Total: {metricas_comparativas['carteira']['retorno_total']*100:+.2f}%")
    print(f"   Retorno Anualizado: {metricas_comparativas['carteira']['retorno_anualizado']*100:+.2f}%")
    print(f"   Volatilidade Anualizada: {metricas_comparativas['carteira']['volatilidade_anualizada']*100:.2f}%")
    print(f"   Sharpe Ratio: {metricas_comparativas['carteira']['sharpe_ratio']:.3f}")

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
        print(f"\n   ✅ A carteira SUPEROU o benchmark em {alpha*100:.2f}% ao ano!")
    else:
        print(f"\n   ⚠️  O benchmark SUPEROU a carteira em {abs(alpha)*100:.2f}% ao ano")

    print(f"\n📁 Arquivos Gerados:")
    print(f"   • Backtest (retorno/volatilidade): {caminho_grafico_backtest}")
    if 'grafico_path' in metricas_comparativas:
        print(f"   • Comparação com benchmark: {metricas_comparativas['grafico_path']}")

    print("\n" + "=" * 80)
    print("🎉 Análise completa concluída com sucesso!")
    print("=" * 80 + "\n")

    return {
        'carteira': carteira_otimizada,
        'metricas': metricas_comparativas,
        'graficos': {
            'backtest': caminho_grafico_backtest,
            'comparacao': metricas_comparativas.get('grafico_path')
        }
    }


def exemplo_simples_backtest():
    """
    Exemplo simples: Apenas backtest com gráfico
    """
    app = create_app()

    print("\n" + "=" * 80)
    print("📊 EXEMPLO SIMPLES: BACKTEST COM GRÁFICO")
    print("=" * 80)

    # Otimizar carteira
    data_referencia = date(2020, 1, 1)
    service = Nsga2OtimizacaoService(
        app=app,
        ids_ativos_restringidos=[],
        nivel_risco='moderado',
        prazo_anos=5,
        data_referencia=data_referencia
    )

    resultado = service.otimizar(max_ativos=10, use_optimal_config=False)

    # Gerar gráfico
    data_fim = date(2024, 12, 31)
    salvar_grafico_backtest(
        carteira=resultado['composicao'],
        data_inicio=data_referencia,
        data_fim=data_fim,
        app=app
    )

    print("\n✅ Backtest concluído! Verifique o gráfico gerado.\n")


def exemplo_simples_comparacao():
    """
    Exemplo simples: Apenas comparação com benchmark

    Nota: Os dados do benchmark são obtidos automaticamente via Yahoo Finance.
          Não é necessário ter o índice cadastrado no banco de dados!
    """
    app = create_app()

    print("\n" + "=" * 80)
    print("🔍 EXEMPLO SIMPLES: COMPARAÇÃO COM BENCHMARK")
    print("=" * 80)

    # Carteira exemplo (substitua pela sua carteira otimizada)
    carteira_exemplo = [
        {'id_ativo': 1, 'ticker': 'PETR4', 'peso': 0.3},
        {'id_ativo': 2, 'ticker': 'VALE3', 'peso': 0.3},
        {'id_ativo': 3, 'ticker': 'ITUB4', 'peso': 0.4}
    ]

    # Comparar com Ibovespa - dados obtidos automaticamente do Yahoo Finance
    comparador = BenchmarkComparison(app)
    metricas = comparador.gerar_relatorio_completo(
        carteira=carteira_exemplo,
        ticker_benchmark='^BVSP',  # Busca automática via yfinance
        data_inicio=date(2020, 1, 1),
        data_fim=date(2024, 12, 31),
        salvar_grafico=True
    )

    print("\n✅ Comparação concluída! Verifique o gráfico gerado.\n")


if __name__ == "__main__":
    # Escolha qual exemplo executar:

    # Exemplo completo (backtest + gráficos + comparação)
    exemplo_completo()

    # Ou exemplos simples:
    # exemplo_simples_backtest()
    # exemplo_simples_comparacao()
