"""
Exemplo simples de uso do serviço de backtesting

Este script demonstra como usar o BacktestService para:
1. Testar a estratégia em um período específico
2. Obter uma carteira otimizada para uma data no passado
3. Ver o desempenho da carteira ao longo do tempo
"""

from datetime import datetime
from backtest_service import BacktestService
from app import create_app


def teste_carteira_data_especifica():
    """
    Exemplo 1: Obter carteira otimizada para uma data específica no passado
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 1: CARTEIRA PARA DATA ESPECÍFICA")
    print("=" * 80)
    
    app = create_app()
    backtest = BacktestService(app)
    
    # Definir data de referência (ex: 01/01/2023)
    data_referencia = datetime(2023, 1, 1)
    
    # Otimizar carteira usando apenas dados até essa data
    carteira = backtest._otimizar_carteira_historica(
        data_referencia=data_referencia,
        ids_ativos_restringidos=[],  # Sem restrições
        nivel_risco='moderado',
        janela_meses=36  # Usar 3 anos de histórico
    )
    
    print(f"\n📅 Carteira Otimizada para {data_referencia.strftime('%d/%m/%Y')}:")
    print(f"{'─' * 80}")
    print(f"{'Ticker':<10} {'Nome':<30} {'Peso':<10}")
    print(f"{'─' * 80}")
    
    for item in sorted(carteira, key=lambda x: x['peso'], reverse=True):
        print(f"{item['ticker']:<10} {item['nome']:<30} {item['peso']*100:>6.2f}%")
    
    print(f"{'─' * 80}")
    print(f"Total de ativos: {len(carteira)}")
    print(f"Soma dos pesos: {sum(item['peso'] for item in carteira):.4f}")


def teste_backtest_periodo():
    """
    Exemplo 2: Backtest completo em um período
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 2: BACKTEST COMPLETO")
    print("=" * 80)
    
    app = create_app()
    backtest = BacktestService(app)
    
    # Definir período do backtest
    data_inicio = datetime(2022, 1, 1)
    data_fim = datetime(2024, 12, 31)
    
    # Executar backtest
    resultados = backtest.executar_backtest(
        data_inicio=data_inicio,
        data_fim=data_fim,
        ids_ativos_restringidos=[],
        nivel_risco='moderado',
        frequencia_rebalanceamento_meses=6,  # Rebalancear a cada 6 meses
        janela_otimizacao_meses=36  # Usar 3 anos de histórico
    )
    
    # Gerar relatório com gráficos
    metricas = backtest.gerar_relatorio(salvar_graficos=True)
    
    print(f"\n📊 RESUMO FINAL:")
    print(f"{'─' * 80}")
    for chave, valor in metricas.items():
        chave_formatada = chave.replace('_', ' ').title()
        print(f"{chave_formatada:<35} {valor}")


def teste_comparacao_perfis():
    """
    Exemplo 3: Comparar diferentes perfis de risco
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 3: COMPARAÇÃO DE PERFIS DE RISCO")
    print("=" * 80)
    
    app = create_app()
    
    # Período do teste
    data_inicio = datetime(2022, 1, 1)
    data_fim = datetime(2024, 12, 31)
    
    perfis = ['conservador', 'moderado', 'arrojado']
    resultados_perfis = {}
    
    for perfil in perfis:
        print(f"\n🎯 Testando perfil: {perfil.upper()}")
        print(f"{'─' * 80}")
        
        backtest = BacktestService(app)
        
        resultados = backtest.executar_backtest(
            data_inicio=data_inicio,
            data_fim=data_fim,
            ids_ativos_restringidos=[],
            nivel_risco=perfil,
            frequencia_rebalanceamento_meses=6,
            janela_otimizacao_meses=36
        )
        
        # Armazenar métricas
        if resultados:
            retorno_total = resultados[-1].retorno_acumulado
            retornos = [r.retorno_periodo for r in resultados]
            import numpy as np
            volatilidade = np.std(retornos) * np.sqrt(12)  # Anualizada
            
            resultados_perfis[perfil] = {
                'retorno': retorno_total,
                'volatilidade': volatilidade,
                'sharpe': retorno_total / volatilidade if volatilidade > 0 else 0
            }
    
    # Comparar resultados
    print(f"\n{'=' * 80}")
    print("📊 COMPARAÇÃO DE PERFIS")
    print(f"{'=' * 80}")
    print(f"{'Perfil':<15} {'Retorno':<15} {'Volatilidade':<15} {'Sharpe':<15}")
    print(f"{'─' * 80}")
    
    for perfil, metricas in resultados_perfis.items():
        print(f"{perfil.capitalize():<15} "
              f"{metricas['retorno']*100:>6.2f}%{' '*7} "
              f"{metricas['volatilidade']*100:>6.2f}%{' '*7} "
              f"{metricas['sharpe']:>6.4f}")


def teste_rapido():
    """
    Exemplo 4: Teste rápido com período curto
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 4: TESTE RÁPIDO")
    print("=" * 80)
    
    app = create_app()
    backtest = BacktestService(app)
    
    # Período curto
    data_inicio = datetime(2023, 1, 1)
    data_fim = datetime(2024, 6, 30)
    
    resultados = backtest.executar_backtest(
        data_inicio=data_inicio,
        data_fim=data_fim,
        ids_ativos_restringidos=[],
        nivel_risco='moderado',
        frequencia_rebalanceamento_meses=3,  # Rebalancear a cada 3 meses
        janela_otimizacao_meses=24  # Usar 2 anos de histórico
    )
    
    # Mostrar evolução da carteira
    print(f"\n📈 EVOLUÇÃO DA CARTEIRA:")
    print(f"{'─' * 80}")
    
    for i, resultado in enumerate(resultados, 1):
        print(f"\nPeríodo {i} - {resultado.data_referencia.strftime('%d/%m/%Y')}")
        print(f"  Retorno: {resultado.retorno_periodo * 100:+.2f}%")
        print(f"  Retorno Acumulado: {resultado.retorno_acumulado * 100:+.2f}%")
        print(f"  Top 3 Ativos:")
        
        for item in sorted(resultado.carteira, key=lambda x: x['peso'], reverse=True)[:3]:
            print(f"    • {item['ticker']:8s} - {item['peso']*100:6.2f}%")


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 80)
    print("SISTEMA DE BACKTESTING - MENU DE EXEMPLOS")
    print("=" * 80)
    print("\nEscolha uma opção:")
    print("1 - Carteira para data específica")
    print("2 - Backtest completo com relatório")
    print("3 - Comparação de perfis de risco")
    print("4 - Teste rápido")
    print("0 - Executar todos")
    
    escolha = input("\nOpção: ").strip()
    
    if escolha == "1":
        teste_carteira_data_especifica()
    elif escolha == "2":
        teste_backtest_periodo()
    elif escolha == "3":
        teste_comparacao_perfis()
    elif escolha == "4":
        teste_rapido()
    elif escolha == "0":
        teste_carteira_data_especifica()
        teste_backtest_periodo()
        teste_comparacao_perfis()
        teste_rapido()
    else:
        print("❌ Opção inválida!")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("✅ EXECUÇÃO CONCLUÍDA")
    print("=" * 80)
