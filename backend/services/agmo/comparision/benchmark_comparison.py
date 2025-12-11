"""
Módulo para comparação de portfolios com benchmarks de mercado.

Este módulo fornece ferramentas para comparar o desempenho de portfolios otimizadas
com índices de mercado como Ibovespa, permitindo avaliar se a estratégia de otimização
está gerando alpha (retorno acima do benchmark).

Os dados dos benchmarks são obtidos automaticamente do Yahoo Finance usando yfinance,
não sendo necessário popular o banco de dados com histórico dos índices.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from typing import List, Dict, Tuple
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from app import create_app
from models import db, Asset, PriceHistory


class BenchmarkComparison:
    """
    Classe para comparar portfolios otimizadas com benchmarks de mercado.
    """

    def __init__(self, app):
        """
        Inicializa o serviço de comparação com benchmarks.

        Args:
            app: Instância da aplicação Flask
        """
        self.app = app
        self.benchmark_data = None
        self.portfolio_data = None

    def _fetch_benchmark_data(self, benchmark_ticker: str,
                                start_date: date,
                                end_date: date) -> pd.DataFrame:
        """
        Busca dados históricos de um benchmark específico usando Yahoo Finance.

        Usa a mesma lógica do yfinance_processor: interval="1mo" que retorna
        o primeiro dia de cada mês (compatível com os dados da portfolio).
        """
        print(f"\n Buscando dados do benchmark '{benchmark_ticker}' via Yahoo Finance...")

        try:
            # Ajustar datas para cobrir o período completo
            # Começar do primeiro dia do mês de start_date
            start_date_ajustada = start_date.replace(day=1)

            # Adicionar mais um mês para garantir cobertura completa
            end_date_ajustada = end_date + relativedelta(months=1)

            # Baixar dados mensais do Yahoo Finance
            df_precos = yf.download(
                benchmark_ticker,
                start=start_date_ajustada,
                end=end_date_ajustada,
                interval="1mo",  # Dados mensais (primeiro dia do mês)
                progress=False,
                auto_adjust=True  # Ajuste automático por dividendos/splits
            )

            if df_precos.empty:
                raise ValueError(f"Não foi possível obter dados do Yahoo Finance para '{benchmark_ticker}'.\n")

            # Calcular variação mensal antes de resetar o índice
            df_precos['variacao_mensal'] = df_precos['Close'].pct_change()

            # Resetar índice para transformar datas em coluna
            df_precos = df_precos.reset_index()

            # Processar datas e criar DataFrame final
            dados_processados = []

            for index, row in df_precos.iterrows():
                try:
                    # Extrair data
                    data_col = row['Date']
                    if isinstance(data_col, pd.Series):
                        data_col = data_col.iloc[0]

                    # Converter para date (primeiro dia do mês)
                    data_mes = pd.to_datetime(data_col).date()

                    # Filtrar pelo período solicitado
                    if data_mes < start_date or data_mes > end_date:
                        continue

                    # Extrair variacao_mensal
                    var_val = row['variacao_mensal']
                    if isinstance(var_val, pd.Series):
                        var_val = var_val.iloc[0]
                    variacao = float(var_val) if not pd.isna(var_val) else None

                    if variacao is not None:
                        dados_processados.append({
                            'data': data_mes,
                            'variacao_mensal': variacao
                        })

                except Exception as e:
                    print(f"Erro ao processar linha {index}: {e}")
                    continue

            if not dados_processados:
                raise ValueError(
                    f"Sem dados do benchmark '{benchmark_ticker}' após processamento "
                    f"para o período {start_date} até {end_date}."
                )

            # Criar DataFrame final
            df_resultado = pd.DataFrame(dados_processados)
            df_resultado.set_index('data', inplace=True)

            print(f"Dados do benchmark obtidos: {len(df_resultado)} meses")
            print(f"Período: {df_resultado.index[0]} até {df_resultado.index[-1]}")

            return df_resultado

        except Exception as e:
            raise ValueError(
                f"Erro ao buscar dados do benchmark '{benchmark_ticker}': {str(e)}\n\n"
            )

    def _calculate_portfolio_returns(self, portfolio: List[Dict],
                                    start_date: date,
                                    end_date: date) -> pd.DataFrame:
        """
        Calcula os retornos mensais de uma portfolio.

        Args:
            portfolio: Lista com composição da portfolio
            start_date: Data inicial
            end_date: Data final

        Returns:
            DataFrame com retornos mensais da portfolio
        """
        with self.app.app_context():
            ids_ativos = [item['asset_id'] for item in portfolio]
            pesos_dict = {item['ticker']: item['weight'] for item in portfolio}

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

            # Calcular retorno ponderado da portfolio
            retornos_portfolio = []
            datas = []

            for data_idx in df_retornos.index:
                retorno_mes = 0
                for ticker in df_retornos.columns:
                    if ticker in pesos_dict:
                        ret_ativo = df_retornos.loc[data_idx, ticker]
                        if pd.notna(ret_ativo):
                            retorno_mes += pesos_dict[ticker] * ret_ativo

                retornos_portfolio.append(retorno_mes)
                datas.append(data_idx)

            # Criar DataFrame
            df_resultado = pd.DataFrame({
                'data': datas,
                'retorno_mensal': retornos_portfolio
            })
            df_resultado.set_index('data', inplace=True)

            return df_resultado

    def _fetch_individual_assets_data(self, portfolio: List[Dict],
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
        with self.app.app_context():
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

    def calculate_comparative_metrics(self,
                                       portfolio: List[Dict],
                                       benchmark_ticker: str,
                                       start_date: date,
                                       end_date: date) -> Dict:
        """
        Calcula métricas comparativas entre a portfolio e o benchmark.
        """
        print(f"  Benchmark: {benchmark_ticker}")
        print(f"  Período: {start_date} até {end_date}")

        # Buscar dados
        df_benchmark = self._fetch_benchmark_data(benchmark_ticker, start_date, end_date)
        df_portfolio = self._calculate_portfolio_returns(portfolio, start_date, end_date)

        # Alinhar datas (pegar apenas datas comuns)
        datas_comuns = df_benchmark.index.intersection(df_portfolio.index)

        if len(datas_comuns) == 0:
            raise ValueError("Não há datas em comum entre a portfolio e o benchmark.")

        retornos_bench = df_benchmark.loc[datas_comuns, 'variacao_mensal'].values
        retornos_cart = df_portfolio.loc[datas_comuns, 'retorno_mensal'].values

        retornos_bench_series = pd.Series(retornos_bench, index=datas_comuns)
        retornos_cart_series = pd.Series(retornos_cart, index=datas_comuns)

        self.benchmark_data = pd.DataFrame({
            'retorno': retornos_bench_series,
            'retorno_acumulado': (1 + retornos_bench_series).cumprod() - 1
        }, index=datas_comuns)

        self.portfolio_data = pd.DataFrame({
            'retorno': retornos_cart_series,
            'retorno_acumulado': (1 + retornos_cart_series).cumprod() - 1
        }, index=datas_comuns)

        # Retornos
        retorno_total_cart = (1 + pd.Series(retornos_cart)).prod() - 1
        retorno_total_bench = (1 + pd.Series(retornos_bench)).prod() - 1
        retorno_medio_cart = np.mean(retornos_cart) * 12  # Anualizado
        retorno_medio_bench = np.mean(retornos_bench) * 12  # Anualizado

        # Volatilidade
        vol_cart = np.std(retornos_cart) * np.sqrt(12)  # Anualizada
        vol_bench = np.std(retornos_bench) * np.sqrt(12)  # Anualizada

        # Sharpe Ratio (assumindo taxa livre de risco = 0 para simplificar)
        sharpe_cart = retorno_medio_cart / vol_cart if vol_cart > 0 else 0
        sharpe_bench = retorno_medio_bench / vol_bench if vol_bench > 0 else 0

        # Alpha (retorno acima do benchmark)
        alpha = retorno_medio_cart - retorno_medio_bench

        # Beta (sensibilidade ao mercado)
        # Beta = Cov(R_cart, R_bench) / Var(R_bench)
        cov_matrix = np.cov(retornos_cart, retornos_bench)
        beta = cov_matrix[0, 1] / cov_matrix[1, 1] if cov_matrix[1, 1] != 0 else 0

        # Correlação
        correlacao = np.corrcoef(retornos_cart, retornos_bench)[0, 1]

        # Drawdown máximo
        def calcular_max_drawdown(retornos):
            valores_acumulados = (1 + pd.Series(retornos)).cumprod()
            pico = valores_acumulados.expanding(min_periods=1).max()
            drawdown = (valores_acumulados - pico) / pico
            return drawdown.min()

        max_dd_cart = calcular_max_drawdown(retornos_cart)
        max_dd_bench = calcular_max_drawdown(retornos_bench)

        metrics = {
            'portfolio': {
                'retorno_total': float(retorno_total_cart),
                'retorno_anualizado': float(retorno_medio_cart),
                'volatilidade_anualizada': float(vol_cart),
                'sharpe_ratio': float(sharpe_cart),
                'max_drawdown': float(max_dd_cart)
            },
            'benchmark': {
                'ticker': benchmark_ticker,
                'retorno_total': float(retorno_total_bench),
                'retorno_anualizado': float(retorno_medio_bench),
                'volatilidade_anualizada': float(vol_bench),
                'sharpe_ratio': float(sharpe_bench),
                'max_drawdown': float(max_dd_bench)
            },
            'comparativas': {
                'alpha': float(alpha),
                'beta': float(beta),
                'correlacao': float(correlacao)
            },
            'periodo': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'num_meses': len(datas_comuns)
            }
        }

        self._print_metrics(metrics)

        return metrics

    def _print_metrics(self, metrics: Dict):
        """Imprime as métricas de forma formatada"""
        print(f"\n{'─'*70}")
        print(f"Métricas da carteira:")
        print(f"{'─'*70}")
        print(f"  Retorno Total:           {metrics['portfolio']['retorno_total']*100:>8.2f}%")
        print(f"  Retorno Anualizado:      {metrics['portfolio']['retorno_anualizado']*100:>8.2f}%")
        print(f"  Volatilidade Anualizada: {metrics['portfolio']['volatilidade_anualizada']*100:>8.2f}%")
        print(f"  Sharpe Ratio:            {metrics['portfolio']['sharpe_ratio']:>8.3f}")
        print(f"  Max Drawdown:            {metrics['portfolio']['max_drawdown']*100:>8.2f}%")

        print(f"\n{'─'*70}")
        print(f"Métricas do benchmark ({metrics['benchmark']['ticker']}):")
        print(f"{'─'*70}")
        print(f"  Retorno Total:           {metrics['benchmark']['retorno_total']*100:>8.2f}%")
        print(f"  Retorno Anualizado:      {metrics['benchmark']['retorno_anualizado']*100:>8.2f}%")
        print(f"  Volatilidade Anualizada: {metrics['benchmark']['volatilidade_anualizada']*100:>8.2f}%")
        print(f"  Sharpe Ratio:            {metrics['benchmark']['sharpe_ratio']:>8.3f}")
        print(f"  Max Drawdown:            {metrics['benchmark']['max_drawdown']*100:>8.2f}%")

        print(f"{'─'*70}")
        print(f"  Correlação:              {metrics['comparativas']['correlacao']:>8.3f}")


    def generate_comparison_chart(self,
                                file_name: str = None,
                                benchmark_ticker: str = None) -> str:
        """
        Gera gráfico comparando a portfolio com o benchmark.
        """
        if self.benchmark_data is None or self.portfolio_data is None:
            raise ValueError(
                "Execute calcular_metrics_comparativas() antes de gerar o gráfico."
            )

        print(f"\n{'='*70}")
        print(f"GERANDO GRÁFICO COMPARATIVO")
        print(f"{'='*70}")

        # Configurar figura com 3 subplots verticais
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 16))
        fig.suptitle('Comparação: Carteira vs Benchmark', fontsize=16, fontweight='bold')

        datas = self.portfolio_data.index

        # ====================================================================
        # Gráfico 1: Retorno Acumulado
        # ====================================================================
        ax1.plot(datas, self.portfolio_data['retorno_acumulado'] * 100,
                    linewidth=2.5, color='#2E86AB', marker='o', markersize=3,
                    label='portfolio Otimizada')
        ax1.plot(datas, self.benchmark_data['retorno_acumulado'] * 100,
                    linewidth=2.5, color='#F18F01', marker='s', markersize=3,
                    label=f'Benchmark ({benchmark_ticker or "Índice"})')
        ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5, linewidth=1)
        ax1.set_title('Retorno Acumulado ao Longo do Tempo', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Data', fontsize=10)
        ax1.set_ylabel('Retorno Acumulado (%)', fontsize=10)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.legend(loc='upper left', fontsize=9)
        ax1.tick_params(axis='x', rotation=45)

        # Adicionar anotações com retornos finais
        ret_final_cart = self.portfolio_data['retorno_acumulado'].iloc[-1] * 100
        ret_final_bench = self.benchmark_data['retorno_acumulado'].iloc[-1] * 100

        ax1.annotate(f'portfolio: {ret_final_cart:+.2f}%',
                        xy=(datas[-1], ret_final_cart),
                        xytext=(10, 10), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='#2E86AB', alpha=0.7),
                        fontsize=8, fontweight='bold', color='white')

        ax1.annotate(f'Benchmark: {ret_final_bench:+.2f}%',
                        xy=(datas[-1], ret_final_bench),
                        xytext=(10, -20), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='#F18F01', alpha=0.7),
                        fontsize=8, fontweight='bold', color='white')

        # ====================================================================
        # Gráfico 2: Volatilidade Rolante (6 meses, anualizada)
        # ====================================================================
        janela = 6  # 6 meses de janela rolante

        # Calcular volatilidade rolante anualizada
        vol_cart_rolling = self.portfolio_data['retorno'].rolling(window=janela).std() * np.sqrt(12) * 100
        vol_bench_rolling = self.benchmark_data['retorno'].rolling(window=janela).std() * np.sqrt(12) * 100

        # Calcular volatilidade média do período (para o sumário)
        vol_media_cart = vol_cart_rolling.mean()
        vol_media_bench = vol_bench_rolling.mean()

        ax2.plot(datas, vol_cart_rolling,
                linewidth=2.5, color='#2E86AB', marker='o', markersize=3,
                label='portfolio Otimizada')
        ax2.plot(datas, vol_bench_rolling,
                linewidth=2.5, color='#F18F01', marker='s', markersize=3,
                label=f'Benchmark ({benchmark_ticker or "Índice"})')
        ax2.set_title('Volatilidade', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Data', fontsize=10)
        ax2.set_ylabel('Volatilidade (%)', fontsize=10)
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.legend(loc='upper left', fontsize=9)
        ax2.tick_params(axis='x', rotation=45)

        # Adicionar anotações com volatilidade média
        ax2.annotate(f'Média portfolio: {vol_media_cart:.2f}%',
                    xy=(0.98, 0.95), xycoords='axes fraction',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='#2E86AB', alpha=0.7),
                    fontsize=8, fontweight='bold', color='white',
                    va='top', ha='right')

        ax2.annotate(f'Média Benchmark: {vol_media_bench:.2f}%',
                    xy=(0.98, 0.85), xycoords='axes fraction',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='#F18F01', alpha=0.7),
                    fontsize=8, fontweight='bold', color='white',
                    va='top', ha='right')

        # ====================================================================
        # Gráfico 3: Retornos Mensais Comparados
        # ====================================================================
        x = np.arange(len(datas))
        width = 0.35

        ax3.bar(x - width/2, self.portfolio_data['retorno'] * 100, width,
                   label='portfolio', color='#2E86AB', alpha=0.7)
        ax3.bar(x + width/2, self.benchmark_data['retorno'] * 100, width,
                   label=f'Benchmark ({benchmark_ticker or "Índice"})', color='#F18F01', alpha=0.7)
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax3.set_title('Retornos Mensais Comparados', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Período', fontsize=10)
        ax3.set_ylabel('Retorno Mensal (%)', fontsize=10)
        ax3.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax3.legend(loc='upper left', fontsize=9)

        # Ajustar layout
        plt.tight_layout()

        # Salvar gráfico
        if file_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f'comparacao_benchmark_{timestamp}.png'

        output_dir = Path('comparison_results')
        output_dir.mkdir(exist_ok=True)

        absolute_path = output_dir / file_name
        plt.savefig(absolute_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"  Gráfico comparativo salvo em: {absolute_path}")
        print(f"{'='*70}\n")

        return absolute_path

    def generate_complete_report(self,
                                portfolio: List[Dict],
                                benchmark_ticker: str,
                                start_date: date,
                                end_date: date,
                                save_chart: bool = True) -> Dict:
        """
        Gera relatório completo comparando a portfolio com o benchmark.
        """
        # Calcular métricas
        metrics = self.calculate_comparative_metrics(portfolio, benchmark_ticker, start_date, end_date)

        # Gerar gráficos se solicitado
        if save_chart:
            # Gráfico comparativo entre portfolio e benchmark
            caminho_grafico = self.generate_comparison_chart(
                benchmark_ticker=benchmark_ticker
            )
            metrics['grafico_path'] = caminho_grafico

            # Gráfico de evolução dos ativos individuais da portfolio
            assets_evolution_chart = self.generate_assets_evolution_chart(
                portfolio=portfolio,
                start_date=start_date,
                end_date=end_date
            )
            metrics['grafico_ativos_path'] = assets_evolution_chart

        return metrics

    def generate_assets_evolution_chart(self,
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

        # Buscar dados dos ativos
        df_retornos, ativos_ordenados = self._fetch_individual_assets_data(
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
