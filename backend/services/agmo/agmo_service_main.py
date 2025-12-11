from datetime import date, datetime
from pathlib import Path
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


def generate_assets_evolution_chart(app,
                                  portfolio: List[Dict],
                                  start_date: date,
                                  end_date: date,
                                  file_name: str = None) -> str:
    """
    Gera gráfico mostrando a evolução do retorno acumulado de cada ativo
    individual da portfolio AGMO, com sumário lateral mostrando a participação
    de cada ativo.
    """
    print(f"\n{'='*70}")
    print(f"GERANDO GRÁFICO DE EVOLUÇÃO DOS ATIVOS DA CARTEIRA")
    print(f"{'='*70}")

    # Buscar dados dos ativo s
    df_retornos, ativos_ordenados = _fetch_individual_assets_data(app,
        portfolio, start_date, end_date
    )

    # Calcular retorno acumulado para cada ativo
    df_retorno_acumulado = (1 + df_retornos).cumprod() - 1

    # Calcular retorno acumulado final de cada ativo para o sumário
    retorno_final_por_ticker = {}
    for ticker in df_retorno_acumulado.columns:
        retorno_final = df_retorno_acumulado[ticker].iloc[-1] * 100  # em %
        retorno_final_por_ticker[ticker] = retorno_final

    # Configurar cores distintas para cada ativo (usando uma paleta de cores)
    num_ativos = len(ativos_ordenados)
    cores = plt.cm.tab20(np.linspace(0, 1, num_ativos))

    # Criar figura com layout customizado
    # 70% para o gráfico, 30% para o sumário
    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(1, 2, width_ratios=[7, 3], hspace=0.3, wspace=0.3)

    ax_grafico = fig.add_subplot(gs[0, 0])
    ax_sumario = fig.add_subplot(gs[0, 1])

    # Criar mapeamento ticker -> cor
    ticker_cor = {}
    for i, ativo_info in enumerate(ativos_ordenados):
        ticker_cor[ativo_info['ticker']] = cores[i]

    # Plotar linhas do gráfico
    datas = df_retorno_acumulado.index

    for ticker in df_retorno_acumulado.columns:
        if ticker in ticker_cor:
            ax_grafico.plot(
                datas,
                df_retorno_acumulado[ticker] * 100,
                linewidth=2,
                color=ticker_cor[ticker],
                label=ticker,
                alpha=0.8
            )

    # Configurar gráfico
    ax_grafico.axhline(y=0, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax_grafico.set_title('Evolução dos Ativos da portfolio AGMO',
                        fontsize=14, fontweight='bold', pad=20)
    ax_grafico.set_xlabel('Data', fontsize=11)
    ax_grafico.set_ylabel('Retorno Acumulado (%)', fontsize=11)
    ax_grafico.grid(True, alpha=0.3, linestyle='--')

    # Rotacionar labels do eixo X para melhor legibilidade
    ax_grafico.tick_params(axis='x', rotation=45)

    # ====================================================================
    # CRIAR SUMÁRIO LATERAL
    # ====================================================================
    ax_sumario.axis('off')  # Desligar eixos

    # Título do sumário
    ax_sumario.text(0.5, 0.95, 'Composição da portfolio',
                   ha='center', va='top', fontsize=12, fontweight='bold',
                   transform=ax_sumario.transAxes)

    # Desenhar linha separadora
    ax_sumario.plot([0.1, 0.9], [0.92, 0.92], 'k-', lw=1,
                   transform=ax_sumario.transAxes)

    # Configurações do sumário
    y_start = 0.88
    y_step = 0.85 / (num_ativos + 1)  # Espaçamento dinâmico

    # Cabeçalho
    y_pos = y_start
    ax_sumario.text(0.05, y_pos, '#', ha='left', va='top',
                   fontsize=9, fontweight='bold',
                   transform=ax_sumario.transAxes)
    ax_sumario.text(0.15, y_pos, 'Ticker', ha='left', va='top',
                   fontsize=9, fontweight='bold',
                   transform=ax_sumario.transAxes)
    ax_sumario.text(0.50, y_pos, 'Retorno', ha='right', va='top',
                   fontsize=9, fontweight='bold',
                   transform=ax_sumario.transAxes)
    ax_sumario.text(0.70, y_pos, 'Peso', ha='right', va='top',
                   fontsize=9, fontweight='bold',
                   transform=ax_sumario.transAxes)
    ax_sumario.text(0.80, y_pos, 'Barra', ha='left', va='top',
                   fontsize=9, fontweight='bold',
                   transform=ax_sumario.transAxes)

    y_pos -= y_step * 0.3

    # Listar ativos
    for i, ativo_info in enumerate(ativos_ordenados, start=1):
        ticker = ativo_info['ticker']
        weight = ativo_info['weight']
        cor = ticker_cor[ticker]
        retorno = retorno_final_por_ticker.get(ticker, 0)

        # Número
        ax_sumario.text(0.05, y_pos, f"{i}", ha='left', va='top',
                       fontsize=8, color='black',
                       transform=ax_sumario.transAxes)

        # Ticker (com cor do ativo)
        ax_sumario.text(0.15, y_pos, ticker, ha='left', va='top',
                       fontsize=8, fontweight='bold', color=cor,
                       transform=ax_sumario.transAxes)

        # Retorno acumulado
        ax_sumario.text(0.50, y_pos, f"{retorno:+.2f}%", ha='right', va='top',
                       fontsize=8, color='black',
                       transform=ax_sumario.transAxes)

        # Peso percentual
        ax_sumario.text(0.70, y_pos, f"{weight*100:.2f}%", ha='right', va='top',
                       fontsize=8, color='black',
                       transform=ax_sumario.transAxes)

        # Barra de peso (usando caracteres Unicode)
        # Normalizar peso para escala de 0 a 15 caracteres
        max_chars = 12
        num_chars = int(weight * 100 / (max([a['weight'] for a in ativos_ordenados]) * 100) * max_chars)
        barra = '█' * max(num_chars, 1)  # Mínimo 1 caractere

        ax_sumario.text(0.80, y_pos, barra, ha='left', va='top',
                       fontsize=8, color=cor, family='monospace',
                       transform=ax_sumario.transAxes)

        y_pos -= y_step

    # Adicionar rodapé com total
    ax_sumario.plot([0.1, 0.9], [y_pos + y_step * 0.2, y_pos + y_step * 0.2],
                   'k-', lw=0.5, transform=ax_sumario.transAxes)

    total_peso = sum([a['weight'] for a in ativos_ordenados])
    ax_sumario.text(0.5, y_pos, f"Total: {total_peso*100:.2f}%",
                   ha='center', va='top', fontsize=9, fontweight='bold',
                   transform=ax_sumario.transAxes)

    # Ajustar layout manualmente (tight_layout causa warning com axis('off'))
    plt.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.08, wspace=0.25)

    # Salvar gráfico
    if file_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f'evolucao_ativos_portfolio_{timestamp}.png'

    output_dir = Path('comparison_results')
    output_dir.mkdir(exist_ok=True)

    full_path = output_dir / file_name
    plt.savefig(full_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"  ✅ Gráfico de evolução dos ativos salvo em: {full_path}")
    print(f"{'='*70}\n")

    return str(full_path)

def _fetch_individual_assets_data(app, portfolio: List[Dict],
                                     start_date: date,
                                     end_date: date) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Busca dados históricos de retorno de cada ativo individual da portfolio.

    Args:
        portfolio: Lista com composição da portfolio
        start_date: Data inicial
        end_date: Data final

    Returns:
        Tupla contendo:
        - DataFrame com retornos mensais de cada ativo (colunas = tickers)
        - Lista com informações dos ativos ordenados por peso decrescente
    """
    with app.app_context():
        ids_ativos = [item['asset_id'] for item in portfolio]

        # Criar dicionário com informações completas dos ativos
        ativos_info = {
            item['ticker']: {
                'ticker': item['ticker'],
                'nome': item.get('name', item['ticker']),
                'weight': item['weight']
            }
            for item in portfolio
        }

        # Buscar retornos dos ativos
        query = db.session.query(
            PriceHistory.date,
            PriceHistory.monthly_variation,
            Asset.ticker
        ).join(Asset, PriceHistory.asset_id == Asset.id) \
            .filter(
                PriceHistory.asset_id.in_(ids_ativos),
                PriceHistory.date >= start_date,
                PriceHistory.date <= end_date
            ) \
            .order_by(PriceHistory.date)

        df = pd.read_sql(query.statement, con=db.session.connection())

        if df.empty:
            raise ValueError("Sem dados históricos para os ativos da portfolio.")

        # Pivot para ter retornos por ativo
        df_retornos = df.pivot(
            index='date',
            columns='ticker',
            values='monthly_variation'
        )

        # Ordenar ativos por peso decrescente
        ativos_ordenados = sorted(
            ativos_info.values(),
            key=lambda x: x['weight'],
            reverse=True
        )

        return df_retornos, ativos_ordenados


def optimize_current_portfolio(app):
    asset_ids = [14, 92, 67, 51, 86]
    service = Nsga2OtimizacaoService(app, [1, 10], "moderado", 10, show_chart=True, asset_ids=asset_ids)
    result = service.optimize(max_assets=10, use_optimal_config=False)

    generate_assets_evolution_chart(app, result['composicao'], start_date=date(2002, 1, 1),
        end_date=date(2024, 12, 31))

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