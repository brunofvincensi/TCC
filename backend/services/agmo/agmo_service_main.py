from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from app import create_app
from models import db, PriceHistory, Asset
from services.agmo.agmo_service import Nsga2OtimizacaoService

def _calculate_portfolio_return(app, portfolio: List[Dict],
                               start_date,
                               end_date) -> Tuple[float, List[float], pd.DataFrame]:
    """
    Calcula o retorno de uma carteira em um período específico

    Args:
        portfolio: Lista com composição da carteira
        start_date: Data inicial do período
        end_date: Data final do período

    Returns:
        Tupla com (retorno_total, lista_de_retornos_mensais, dataframe_com_datas)
    """
    with app.app_context():
        # Buscar retornos dos ativos no período
        asset_ids = [item['asset_id'] for item in portfolio]

        query = db.session.query(
            PriceHistory.date,
            PriceHistory.monthly_variation,
            Asset.ticker
        ).join(Asset, PriceHistory.asset_id == Asset.id) \
            .filter(
            PriceHistory.asset_id.in_(asset_ids),
            PriceHistory.date > start_date,
            PriceHistory.date <= end_date
        ) \
            .order_by(PriceHistory.date)

        df = pd.read_sql(query.statement, con=db.session.connection())

        if df.empty:
            return 0.0, [], pd.DataFrame()

        # Pivot para ter retornos por ativo
        df_returns = df.pivot(
            index='date',
            columns='ticker',
            values='monthly_variation'
        )

        # Calcular retorno ponderado da carteira
        weights_dict = {item['ticker']: item['weight'] for item in portfolio}

        monthly_returns = []
        dates = []
        for date_idx in df_returns.index:
            month_return = 0
            for ticker in df_returns.columns:
                if ticker in weights_dict:
                    asset_ret = df_returns.loc[date_idx, ticker]
                    if pd.notna(asset_ret):
                        month_return += weights_dict[ticker] * asset_ret

            monthly_returns.append(month_return)
            dates.append(date_idx)

        # Calcular retorno acumulado
        total_return = (1 + pd.Series(monthly_returns)).prod() - 1

        # Criar DataFrame com resultados
        df_result = pd.DataFrame({
            'data': dates,
            'retorno_mensal': monthly_returns
        })
        df_result.set_index('data', inplace=True)

        return float(total_return), monthly_returns, df_result


def save_backtest_chart(portfolio: List[Dict],
                            start_date,
                            end_date,
                            app,
                            file_name: str = None,
                            volatility_window: int = 6) -> str:
    """
    Gera e salva gráfico mostrando o retorno acumulado e a volatilidade da carteira ao longo do tempo.
    """
    import os
    from datetime import datetime

    print(f"\n{'='*70}")
    print(f"GERANDO GRÁFICO DE BACKTEST")
    print(f"{'='*70}")

    # Calcular retornos da carteira
    total_return, monthly_returns, df_returns = _calculate_portfolio_return(
        app, portfolio, start_date, end_date
    )

    if df_returns.empty:
        print("  Sem dados para gerar gráfico")
        return None

    # Calcular retorno acumulado
    df_returns['retorno_acumulado'] = (1 + df_returns['retorno_mensal']).cumprod() - 1

    # Calcular volatilidade rolling (anualizada)
    df_returns['volatilidade_rolling'] = (
        df_returns['retorno_mensal']
        .rolling(window=volatility_window, min_periods=1)
        .std() * np.sqrt(12) * 100  # Anualizada e em %
    )

    # Configurar figura com 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('Backtest da Carteira Otimizada', fontsize=16, fontweight='bold')

    # Gráfico 1: Retorno Acumulado
    ax1.plot(df_returns.index, df_returns['retorno_acumulado'] * 100,
             linewidth=2.5, color='#2E86AB', marker='o', markersize=4, label='Retorno Acumulado')
    ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5, linewidth=1)
    ax1.fill_between(df_returns.index, 0, df_returns['retorno_acumulado'] * 100,
                     alpha=0.3, color='#2E86AB')
    ax1.set_title('Retorno Acumulado da Carteira ao Longo do Tempo', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Data', fontsize=10)
    ax1.set_ylabel('Retorno Acumulado (%)', fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='upper left', fontsize=9)

    # Adicionar anotação com retorno total
    final_return = df_returns['retorno_acumulado'].iloc[-1] * 100
    ax1.annotate(f'Retorno Total: {final_return:+.2f}%',
                xy=(df_returns.index[-1], final_return),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                fontsize=9, fontweight='bold')

    # Gráfico 2: Volatilidade Rolling
    ax2.plot(df_returns.index, df_returns['volatilidade_rolling'],
             linewidth=2.5, color='#F18F01', marker='s', markersize=4, label=f'Volatilidade Rolling ({volatility_window} meses)')
    ax2.fill_between(df_returns.index, 0, df_returns['volatilidade_rolling'],
                     alpha=0.3, color='#F18F01')
    ax2.set_title(f'Volatilidade da Carteira ao Longo do Tempo (janela de {volatility_window} meses)',
                  fontsize=12, fontweight='bold')
    ax2.set_xlabel('Data', fontsize=10)
    ax2.set_ylabel('Volatilidade Anualizada (%)', fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='upper left', fontsize=9)

    # Adicionar linha de média de volatilidade
    mean_vol = df_returns['volatilidade_rolling'].mean()
    ax2.axhline(y=mean_vol, color='green', linestyle='--', alpha=0.7, linewidth=1.5,
                label=f'Média: {mean_vol:.2f}%')
    ax2.legend(loc='upper left', fontsize=9)

    plt.tight_layout()

    # Definir nome do arquivo
    if file_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f'backtest_carteira_{timestamp}.png'

    # Garantir que o diretório existe
    directory = os.path.dirname(file_name) if os.path.dirname(file_name) else '.'
    if not os.path.exists(directory) and directory != '.':
        os.makedirs(directory, exist_ok=True)

    # Salvar gráfico
    full_path = os.path.abspath(file_name)
    plt.savefig(full_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"  ✅ Gráfico salvo em: {full_path}")
    print(f"  📊 Métricas:")
    print(f"     Retorno Total: {final_return:+.2f}%")
    print(f"     Volatilidade Média: {mean_vol:.2f}%")
    print(f"     Sharpe Ratio: {(final_return/mean_vol):.3f}" if mean_vol > 0 else "     Sharpe Ratio: N/A")
    print(f"{'='*70}\n")

    return full_path

def optimize_current_portfolio(app):
    asset_ids = [14, 92, 67, 51, 96]
    service = Nsga2OtimizacaoService(app, [1, 10], "conservador", 10, show_chart=True, asset_ids=asset_ids)
    result = service.optimize(max_assets=10, use_optimal_config=False)

    # Informações adicionais
    print(f"\n📅 INFORMAÇÕES DO PERÍODO:")
    print(f"   Dados históricos: {result['periodo_inicio']} até {result['periodo_fim']}")
    print(f"   Total de meses: {result['num_meses']}")
    print(f"   Hiperparâmetros: Pop={result['hyperparameters_used']['population_size']}, "
          f"Gen={result['hyperparameters_used']['generations']}")

def backtest(app):
    from datetime import date
    backtest_date = date(2015, 1, 1)
    backtest_service = Nsga2OtimizacaoService(app, [1, 10], "conservador", 10, reference_date=backtest_date, show_chart=True)
    backtest_portfolio = backtest_service.optimize(max_assets=10)

    # Informações do backtest
    print(f"\nINFORMAÇÕES DO BACKTEST:")
    print(f"   Data de referência: {backtest_portfolio['data_referencia']}")
    print(f"   Dados históricos: {backtest_portfolio['periodo_inicio']} até {backtest_portfolio['periodo_fim']}")
    print(f"   Total de meses: {backtest_portfolio['num_meses']}")
    print(f"   Hiperparâmetros: Pop={backtest_portfolio['hyperparameters_used']['population_size']}, "
          f"Gen={backtest_portfolio['hyperparameters_used']['generations']}")

    end_date = date(2025, 10, 20)
    period_return, monthly_returns, df_returns = _calculate_portfolio_return(
        app,
        backtest_portfolio['composicao'],
        backtest_date,
        end_date
    )

    print(f"Retorno Acumulado: {period_return * 100:+.2f}%")

    # Gerar e salvar gráfico do backtest
    save_backtest_chart(
        backtest_portfolio['composicao'],
        backtest_date,
        end_date,
        app,
        file_name='backtest_exemplo.png'
    )


def main():
    """Função principal que interpreta os comandos."""
    app = create_app()

    # Exemplo 1: Otimização normal (sem backtest)
    optimize_current_portfolio(app)

    # Exemplo 2: Otimização com backtest (usando dados até uma data específica)
   # backtest(app)

if __name__ == "__main__":
    main()