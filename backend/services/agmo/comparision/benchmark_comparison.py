"""
Módulo para comparação de carteiras com benchmarks de mercado.

Este módulo fornece ferramentas para comparar o desempenho de carteiras otimizadas
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
from typing import List, Dict, Tuple, Optional
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from app import create_app
from models import db, Ativo, HistoricoPrecos


class BenchmarkComparison:
    """
    Classe para comparar carteiras otimizadas com benchmarks de mercado.

    Permite comparar métricas como:
    - Retorno acumulado
    - Volatilidade
    - Sharpe Ratio
    - Alpha (retorno acima do benchmark)
    - Beta (sensibilidade ao mercado)
    - Tracking Error
    - Information Ratio
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
        o primeiro dia de cada mês (compatível com os dados da carteira).

        Args:
            ticker_benchmark: Ticker do benchmark (ex: '^BVSP' para Ibovespa)
            data_inicio: Data inicial
            data_fim: Data final

        Returns:
            DataFrame com retornos mensais do benchmark
        """
        print(f"\n  🌐 Buscando dados do benchmark '{ticker_benchmark}' via Yahoo Finance...")

        try:
            # Ajustar datas para cobrir o período completo
            # Começar do primeiro dia do mês de data_inicio
            data_inicio_ajustada = data_inicio.replace(day=1)

            # Adicionar buffer no fim para garantir cobertura completa
            data_fim_ajustada = data_fim + relativedelta(months=1)

            # Baixar dados mensais do Yahoo Finance
            # ✅ Usando interval="1mo" como no yfinance_processor
            # Isso retorna automaticamente o primeiro dia de cada mês
            df_precos = yf.download(
                ticker_benchmark,
                start=data_inicio_ajustada,
                end=data_fim_ajustada,
                interval="1mo",  # Dados mensais (primeiro dia do mês)
                progress=False,
                auto_adjust=True  # Ajuste automático por dividendos/splits
            )

            if df_precos.empty:
                raise ValueError(
                    f"Não foi possível obter dados do Yahoo Finance para '{ticker_benchmark}'.\n"
                    f"Verifique se o ticker está correto.\n"
                    f"Exemplos: '^BVSP' (Ibovespa), '^GSPC' (S&P 500), '^DJI' (Dow Jones)"
                )

            # Calcular variação mensal ANTES de resetar o índice
            # (mesma lógica do yfinance_processor)
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
                    if data_mes < data_inicio or data_mes > data_fim:
                        continue

                    # Extrair variacao_mensal
                    var_val = row['variacao_mensal']
                    if isinstance(var_val, pd.Series):
                        var_val = var_val.iloc[0]
                    variacao = float(var_val) if not pd.isna(var_val) else None

                    if variacao is not None:  # Pula NaN (primeiro mês)
                        dados_processados.append({
                            'data': data_mes,
                            'variacao_mensal': variacao
                        })

                except Exception as e:
                    print(f"    ⚠️  Erro ao processar linha {index}: {e}")
                    continue

            if not dados_processados:
                raise ValueError(
                    f"Sem dados do benchmark '{ticker_benchmark}' após processamento "
                    f"para o período {data_inicio} até {data_fim}."
                )

            # Criar DataFrame final
            df_resultado = pd.DataFrame(dados_processados)
            df_resultado.set_index('data', inplace=True)

            print(f"  ✅ Dados do benchmark obtidos: {len(df_resultado)} meses")
            print(f"  📅 Período: {df_resultado.index[0]} até {df_resultado.index[-1]}")
            print(f"  📊 Usando primeiro dia do mês (compatível com yfinance_processor)")

            return df_resultado

        except Exception as e:
            raise ValueError(
                f"Erro ao buscar dados do benchmark '{ticker_benchmark}': {str(e)}\n\n"
                f"Dicas:\n"
                f"  • Verifique sua conexão com a internet\n"
                f"  • Confirme que o ticker está correto\n"
                f"  • Tickers comuns:\n"
                f"    - ^BVSP: Ibovespa (Brasil)\n"
                f"    - ^GSPC: S&P 500 (EUA)\n"
                f"    - ^DJI: Dow Jones (EUA)\n"
                f"    - ^IXIC: NASDAQ (EUA)\n"
                f"    - ^FTSE: FTSE 100 (Reino Unido)"
            )

    def _calculate_portfolio_returns(self, portfolio: List[Dict],
                                    start_date: date,
                                    end_date: date) -> pd.DataFrame:
        """
        Calcula os retornos mensais de uma carteira.

        Args:
            carteira: Lista com composição da carteira
            data_inicio: Data inicial
            data_fim: Data final

        Returns:
            DataFrame com retornos mensais da carteira
        """
        with self.app.app_context():
            ids_ativos = [item['id_ativo'] for item in carteira]
            pesos_dict = {item['ticker']: item['peso'] for item in carteira}

            # Buscar retornos dos ativos
            query = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
                .filter(
                    HistoricoPrecos.id_ativo.in_(ids_ativos),
                    HistoricoPrecos.data >= data_inicio,
                    HistoricoPrecos.data <= data_fim
                ) \
                .order_by(HistoricoPrecos.data)

            df = pd.read_sql(query.statement, con=db.session.connection())

            if df.empty:
                raise ValueError("Sem dados históricos para os ativos da carteira.")

            # Pivot para ter retornos por ativo
            df_retornos = df.pivot(
                index='data',
                columns='ticker',
                values='variacao_mensal'
            )

            # Calcular retorno ponderado da carteira
            retornos_carteira = []
            datas = []

            for data_idx in df_retornos.index:
                retorno_mes = 0
                for ticker in df_retornos.columns:
                    if ticker in pesos_dict:
                        ret_ativo = df_retornos.loc[data_idx, ticker]
                        if pd.notna(ret_ativo):
                            retorno_mes += pesos_dict[ticker] * ret_ativo

                retornos_carteira.append(retorno_mes)
                datas.append(data_idx)

            # Criar DataFrame
            df_resultado = pd.DataFrame({
                'data': datas,
                'retorno_mensal': retornos_carteira
            })
            df_resultado.set_index('data', inplace=True)

            return df_resultado

    def _fetch_individual_assets_data(self, portfolio: List[Dict],
                                         start_date: date,
                                         end_date: date) -> Tuple[pd.DataFrame, List[Dict]]:
        """
        Busca dados históricos de retorno de cada ativo individual da carteira.

        Args:
            carteira: Lista com composição da carteira
            data_inicio: Data inicial
            data_fim: Data final

        Returns:
            Tupla contendo:
            - DataFrame com retornos mensais de cada ativo (colunas = tickers)
            - Lista com informações dos ativos ordenados por peso decrescente
        """
        with self.app.app_context():
            ids_ativos = [item['id_ativo'] for item in carteira]

            # Criar dicionário com informações completas dos ativos
            ativos_info = {
                item['ticker']: {
                    'ticker': item['ticker'],
                    'nome': item.get('nome', item['ticker']),
                    'peso': item['peso']
                }
                for item in carteira
            }

            # Buscar retornos dos ativos
            query = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
                .filter(
                    HistoricoPrecos.id_ativo.in_(ids_ativos),
                    HistoricoPrecos.data >= data_inicio,
                    HistoricoPrecos.data <= data_fim
                ) \
                .order_by(HistoricoPrecos.data)

            df = pd.read_sql(query.statement, con=db.session.connection())

            if df.empty:
                raise ValueError("Sem dados históricos para os ativos da carteira.")

            # Pivot para ter retornos por ativo
            df_retornos = df.pivot(
                index='data',
                columns='ticker',
                values='variacao_mensal'
            )

            # Ordenar ativos por peso decrescente
            ativos_ordenados = sorted(
                ativos_info.values(),
                key=lambda x: x['peso'],
                reverse=True
            )

            return df_retornos, ativos_ordenados

    def generate_assets_evolution_chart(self,
                                      portfolio: List[Dict],
                                      start_date: date,
                                      end_date: date,
                                      file_name: str = None) -> str:
        """
        Gera gráfico mostrando a evolução do retorno acumulado de cada ativo
        individual da carteira AGMO, com sumário lateral mostrando a participação
        de cada ativo.

        Args:
            carteira: Lista com composição da carteira (deve incluir 'nome' de cada ativo)
            data_inicio: Data inicial
            data_fim: Data final
            nome_arquivo: Nome do arquivo para salvar (opcional)

        Returns:
            Caminho do arquivo salvo
        """
        print(f"\n{'='*70}")
        print(f"📊 GERANDO GRÁFICO DE EVOLUÇÃO DOS ATIVOS DA CARTEIRA")
        print(f"{'='*70}")

        # Buscar dados dos ativos
        df_retornos, ativos_ordenados = self._buscar_dados_ativos_individuais(
            carteira, data_inicio, data_fim
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
        ax_grafico.set_title('Evolução dos Ativos da Carteira AGMO',
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
        ax_sumario.text(0.5, 0.95, 'Composição da Carteira',
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
            peso = ativo_info['peso']
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
            ax_sumario.text(0.70, y_pos, f"{peso*100:.2f}%", ha='right', va='top',
                           fontsize=8, color='black',
                           transform=ax_sumario.transAxes)

            # Barra de peso (usando caracteres Unicode)
            # Normalizar peso para escala de 0 a 15 caracteres
            max_chars = 12
            num_chars = int(peso * 100 / (max([a['peso'] for a in ativos_ordenados]) * 100) * max_chars)
            barra = '█' * max(num_chars, 1)  # Mínimo 1 caractere

            ax_sumario.text(0.80, y_pos, barra, ha='left', va='top',
                           fontsize=8, color=cor, family='monospace',
                           transform=ax_sumario.transAxes)

            y_pos -= y_step

        # Adicionar rodapé com total
        ax_sumario.plot([0.1, 0.9], [y_pos + y_step * 0.2, y_pos + y_step * 0.2],
                       'k-', lw=0.5, transform=ax_sumario.transAxes)

        total_peso = sum([a['peso'] for a in ativos_ordenados])
        ax_sumario.text(0.5, y_pos, f"Total: {total_peso*100:.2f}%",
                       ha='center', va='top', fontsize=9, fontweight='bold',
                       transform=ax_sumario.transAxes)

        # Ajustar layout manualmente (tight_layout causa warning com axis('off'))
        plt.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.08, wspace=0.25)

        # Salvar gráfico
        if nome_arquivo is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f'evolucao_ativos_carteira_{timestamp}.png'

        output_dir = Path('comparison_results')
        output_dir.mkdir(exist_ok=True)

        caminho_completo = output_dir / nome_arquivo
        plt.savefig(caminho_completo, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"  ✅ Gráfico de evolução dos ativos salvo em: {caminho_completo}")
        print(f"{'='*70}\n")

        return str(caminho_completo)

    def calculate_comparative_metrics(self,
                                       portfolio: List[Dict],
                                       benchmark_ticker: str,
                                       start_date: date,
                                       end_date: date) -> Dict:
        """
        Calcula métricas comparativas entre a carteira e o benchmark.

        Args:
            carteira: Lista com composição da carteira
            ticker_benchmark: Ticker do benchmark (ex: '^BVSP')
            data_inicio: Data inicial da comparação
            data_fim: Data final da comparação

        Returns:
            Dicionário com métricas comparativas
        """
        print(f"\n{'='*70}")
        print(f"📊 CALCULANDO MÉTRICAS COMPARATIVAS")
        print(f"{'='*70}")
        print(f"  Benchmark: {ticker_benchmark}")
        print(f"  Período: {data_inicio} até {data_fim}")

        # Buscar dados
        df_benchmark = self._buscar_dados_benchmark(ticker_benchmark, data_inicio, data_fim)
        df_carteira = self._calcular_retornos_carteira(carteira, data_inicio, data_fim)

        # Alinhar datas (pegar apenas datas comuns)
        datas_comuns = df_benchmark.index.intersection(df_carteira.index)

        if len(datas_comuns) == 0:
            raise ValueError("Não há datas em comum entre a carteira e o benchmark.")

        retornos_bench = df_benchmark.loc[datas_comuns, 'variacao_mensal'].values
        retornos_cart = df_carteira.loc[datas_comuns, 'retorno_mensal'].values

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

        # 1. Retornos
        retorno_total_cart = (1 + pd.Series(retornos_cart)).prod() - 1
        retorno_total_bench = (1 + pd.Series(retornos_bench)).prod() - 1
        retorno_medio_cart = np.mean(retornos_cart) * 12  # Anualizado
        retorno_medio_bench = np.mean(retornos_bench) * 12  # Anualizado

        # 2. Volatilidade
        vol_cart = np.std(retornos_cart) * np.sqrt(12)  # Anualizada
        vol_bench = np.std(retornos_bench) * np.sqrt(12)  # Anualizada

        # 3. Sharpe Ratio (assumindo taxa livre de risco = 0 para simplificar)
        sharpe_cart = retorno_medio_cart / vol_cart if vol_cart > 0 else 0
        sharpe_bench = retorno_medio_bench / vol_bench if vol_bench > 0 else 0

        # 4. Alpha (retorno acima do benchmark)
        alpha = retorno_medio_cart - retorno_medio_bench

        # 5. Beta (sensibilidade ao mercado)
        # Beta = Cov(R_cart, R_bench) / Var(R_bench)
        cov_matrix = np.cov(retornos_cart, retornos_bench)
        beta = cov_matrix[0, 1] / cov_matrix[1, 1] if cov_matrix[1, 1] != 0 else 0

        # 6. Tracking Error (volatilidade do excess return)
        excess_returns = retornos_cart - retornos_bench
        tracking_error = np.std(excess_returns) * np.sqrt(12)  # Anualizado

        # 7. Information Ratio (Alpha / Tracking Error)
        information_ratio = alpha / tracking_error if tracking_error > 0 else 0

        # 8. Correlação
        correlacao = np.corrcoef(retornos_cart, retornos_bench)[0, 1]

        # 9. Drawdown máximo
        def calcular_max_drawdown(retornos):
            valores_acumulados = (1 + pd.Series(retornos)).cumprod()
            pico = valores_acumulados.expanding(min_periods=1).max()
            drawdown = (valores_acumulados - pico) / pico
            return drawdown.min()

        max_dd_cart = calcular_max_drawdown(retornos_cart)
        max_dd_bench = calcular_max_drawdown(retornos_bench)

        metricas = {
            'carteira': {
                'retorno_total': float(retorno_total_cart),
                'retorno_anualizado': float(retorno_medio_cart),
                'volatilidade_anualizada': float(vol_cart),
                'sharpe_ratio': float(sharpe_cart),
                'max_drawdown': float(max_dd_cart)
            },
            'benchmark': {
                'ticker': ticker_benchmark,
                'retorno_total': float(retorno_total_bench),
                'retorno_anualizado': float(retorno_medio_bench),
                'volatilidade_anualizada': float(vol_bench),
                'sharpe_ratio': float(sharpe_bench),
                'max_drawdown': float(max_dd_bench)
            },
            'comparativas': {
                'alpha': float(alpha),
                'beta': float(beta),
                'tracking_error': float(tracking_error),
                'information_ratio': float(information_ratio),
                'correlacao': float(correlacao)
            },
            'periodo': {
                'data_inicio': data_inicio.isoformat(),
                'data_fim': data_fim.isoformat(),
                'num_meses': len(datas_comuns)
            }
        }

        self._imprimir_metricas(metricas)

        return metricas

    def _print_metrics(self, metrics: Dict):
        """Imprime as métricas de forma formatada"""
        print(f"\n{'─'*70}")
        print(f"📈 MÉTRICAS DA CARTEIRA:")
        print(f"{'─'*70}")
        print(f"  Retorno Total:           {metricas['carteira']['retorno_total']*100:>8.2f}%")
        print(f"  Retorno Anualizado:      {metricas['carteira']['retorno_anualizado']*100:>8.2f}%")
        print(f"  Volatilidade Anualizada: {metricas['carteira']['volatilidade_anualizada']*100:>8.2f}%")
        print(f"  Sharpe Ratio:            {metricas['carteira']['sharpe_ratio']:>8.3f}")
        print(f"  Max Drawdown:            {metricas['carteira']['max_drawdown']*100:>8.2f}%")

        print(f"\n{'─'*70}")
        print(f"📊 MÉTRICAS DO BENCHMARK ({metricas['benchmark']['ticker']}):")
        print(f"{'─'*70}")
        print(f"  Retorno Total:           {metricas['benchmark']['retorno_total']*100:>8.2f}%")
        print(f"  Retorno Anualizado:      {metricas['benchmark']['retorno_anualizado']*100:>8.2f}%")
        print(f"  Volatilidade Anualizada: {metricas['benchmark']['volatilidade_anualizada']*100:>8.2f}%")
        print(f"  Sharpe Ratio:            {metricas['benchmark']['sharpe_ratio']:>8.3f}")
        print(f"  Max Drawdown:            {metricas['benchmark']['max_drawdown']*100:>8.2f}%")

        print(f"\n{'─'*70}")
        print(f"🔍 MÉTRICAS COMPARATIVAS:")
        print(f"{'─'*70}")
        print(f"  Alpha (vs benchmark):    {metricas['comparativas']['alpha']*100:>8.2f}%")
        print(f"  Beta:                    {metricas['comparativas']['beta']:>8.3f}")
        print(f"  Tracking Error:          {metricas['comparativas']['tracking_error']*100:>8.2f}%")
        print(f"  Information Ratio:       {metricas['comparativas']['information_ratio']:>8.3f}")
        print(f"  Correlação:              {metricas['comparativas']['correlacao']:>8.3f}")

        # Interpretação
        print(f"\n{'─'*70}")
        print(f"💡 INTERPRETAÇÃO:")
        print(f"{'─'*70}")

        alpha = metricas['comparativas']['alpha']
        if alpha > 0.02:  # 2% ao ano
            print(f"  ✅ Alpha positivo significativo: Carteira supera o benchmark")
        elif alpha > 0:
            print(f"  ✅ Alpha positivo: Carteira supera o benchmark marginalmente")
        elif alpha > -0.02:
            print(f"  ⚠️  Alpha próximo de zero: Desempenho similar ao benchmark")
        else:
            print(f"  ❌ Alpha negativo: Benchmark supera a carteira")

        beta = metricas['comparativas']['beta']
        if beta > 1.2:
            print(f"  ⚠️  Beta alto ({beta:.2f}): Carteira mais volátil que o mercado")
        elif beta > 0.8:
            print(f"  ✅ Beta moderado ({beta:.2f}): Carteira com volatilidade similar ao mercado")
        else:
            print(f"  ℹ️  Beta baixo ({beta:.2f}): Carteira menos volátil que o mercado")

        ir = metricas['comparativas']['information_ratio']
        if ir > 0.5:
            print(f"  ✅ Information Ratio alto: Excelente retorno ajustado por tracking error")
        elif ir > 0:
            print(f"  ℹ️  Information Ratio positivo: Retorno adicional compensa o risco")
        else:
            print(f"  ⚠️  Information Ratio negativo: Retorno não compensa o risco adicional")

        print(f"{'─'*70}\n")

    def generate_comparison_chart(self,
                                file_name: str = None,
                                benchmark_ticker: str = None) -> str:
        """
        Gera gráfico comparando a carteira com o benchmark.

        Args:
            nome_arquivo: Nome do arquivo para salvar (opcional)
            ticker_benchmark: Nome do benchmark para exibir no gráfico

        Returns:
            Caminho do arquivo salvo
        """
        if self.benchmark_data is None or self.portfolio_data is None:
            raise ValueError(
                "Execute calcular_metricas_comparativas() antes de gerar o gráfico."
            )

        print(f"\n{'='*70}")
        print(f"📊 GERANDO GRÁFICO COMPARATIVO")
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
                    label='Carteira Otimizada')
        ax1.plot(datas, self.benchmark_data['retorno_acumulado'] * 100,
                    linewidth=2.5, color='#F18F01', marker='s', markersize=3,
                    label=f'Benchmark ({ticker_benchmark or "Índice"})')
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

        ax1.annotate(f'Carteira: {ret_final_cart:+.2f}%',
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
                label='Carteira Otimizada')
        ax2.plot(datas, vol_bench_rolling,
                linewidth=2.5, color='#F18F01', marker='s', markersize=3,
                label=f'Benchmark ({ticker_benchmark or "Índice"})')
        ax2.set_title(f'Volatilidade Rolante ({janela} meses, anualizada)', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Data', fontsize=10)
        ax2.set_ylabel('Volatilidade (%)', fontsize=10)
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.legend(loc='upper left', fontsize=9)
        ax2.tick_params(axis='x', rotation=45)

        # Adicionar anotações com volatilidade média
        ax2.annotate(f'Média Carteira: {vol_media_cart:.2f}%',
                    xy=(0.02, 0.95), xycoords='axes fraction',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='#2E86AB', alpha=0.7),
                    fontsize=8, fontweight='bold', color='white',
                    va='top')

        ax2.annotate(f'Média Benchmark: {vol_media_bench:.2f}%',
                    xy=(0.02, 0.85), xycoords='axes fraction',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='#F18F01', alpha=0.7),
                    fontsize=8, fontweight='bold', color='white',
                    va='top')

        # ====================================================================
        # Gráfico 3: Retornos Mensais Comparados
        # ====================================================================
        x = np.arange(len(datas))
        width = 0.35

        ax3.bar(x - width/2, self.portfolio_data['retorno'] * 100, width,
                   label='Carteira', color='#2E86AB', alpha=0.7)
        ax3.bar(x + width/2, self.benchmark_data['retorno'] * 100, width,
                   label=f'Benchmark ({ticker_benchmark or "Índice"})', color='#F18F01', alpha=0.7)
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax3.set_title('Retornos Mensais Comparados', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Período', fontsize=10)
        ax3.set_ylabel('Retorno Mensal (%)', fontsize=10)
        ax3.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax3.legend(loc='upper left', fontsize=9)

        # Ajustar layout
        plt.tight_layout()

        # Salvar gráfico
        if nome_arquivo is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f'comparacao_benchmark_{timestamp}.png'

        output_dir = Path('comparison_results')
        output_dir.mkdir(exist_ok=True)

        caminho_completo = output_dir / nome_arquivo
        plt.savefig(caminho_completo, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"  ✅ Gráfico comparativo salvo em: {caminho_completo}")
        print(f"{'='*70}\n")

        return caminho_completo

    def generate_complete_report(self,
                                portfolio: List[Dict],
                                benchmark_ticker: str,
                                start_date: date,
                                end_date: date,
                                save_chart: bool = True) -> Dict:
        """
        Gera relatório completo comparando a carteira com o benchmark.

        Args:
            carteira: Lista com composição da carteira
            ticker_benchmark: Ticker do benchmark
            data_inicio: Data inicial
            data_fim: Data final
            salvar_grafico: Se True, gera e salva gráfico

        Returns:
            Dicionário com todas as métricas
        """
        # Calcular métricas
        metricas = self.calcular_metricas_comparativas(
            carteira, ticker_benchmark, data_inicio, data_fim
        )

        # Gerar gráficos se solicitado
        if salvar_grafico:
            # Gráfico comparativo entre carteira e benchmark
            caminho_grafico = self.gerar_grafico_comparacao(
                ticker_benchmark=ticker_benchmark
            )
            metricas['grafico_path'] = caminho_grafico

            # Gráfico de evolução dos ativos individuais da carteira
            caminho_grafico_ativos = self.gerar_grafico_evolucao_ativos(
                carteira=carteira,
                data_inicio=data_inicio,
                data_fim=data_fim
            )
            metricas['grafico_ativos_path'] = caminho_grafico_ativos

        return metricas


def example_usage():
    """
    Exemplo de uso da classe BenchmarkComparison

    Os dados do benchmark são obtidos automaticamente do Yahoo Finance.
    Não é necessário ter o índice cadastrado no banco de dados!
    """
    from datetime import date

    app = create_app()

    print("\n" + "=" * 70)
    print("📊 EXEMPLO: Comparação de Carteira com Benchmark")
    print("=" * 70)
    print("💡 Os dados do benchmark serão obtidos via Yahoo Finance")
    print("   Não precisa cadastrar o índice no banco!\n")

    # Exemplo de composição de carteira
    carteira_exemplo = [
        {'id_ativo': 1, 'ticker': 'PETR4', 'peso': 0.3},
        {'id_ativo': 2, 'ticker': 'VALE3', 'peso': 0.3},
        {'id_ativo': 3, 'ticker': 'ITUB4', 'peso': 0.4}
    ]

    # Criar serviço de comparação
    comparador = BenchmarkComparison(app)

    # Gerar relatório completo
    metricas = comparador.gerar_relatorio_completo(
        carteira=carteira_exemplo,
        ticker_benchmark='^BVSP',  # Ibovespa - busca automática via yfinance
        data_inicio=date(2020, 1, 1),
        data_fim=date(2024, 12, 31),
        salvar_grafico=True
    )

    print("\n✅ Relatório completo gerado com sucesso!")
    return metricas


if __name__ == "__main__":
    exemplo_uso()
