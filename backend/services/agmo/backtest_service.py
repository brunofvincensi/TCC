from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import seaborn as sns

from app import create_app
from models import db, Ativo, HistoricoPrecos
from models.ativo import TipoAtivo
from services.agmo.teste_final import Nsga2OtimizacaoService, PersonalizedPortfolioProblem
from services.agmo.custom_crossover import SimplexCrossover, SimplexMutation, SimplexSampling
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize


class BacktestResult:
    """Classe para armazenar resultados de um período de backtest"""
    
    def __init__(self, data_referencia: datetime, carteira: List[Dict], 
                 retorno_periodo: float, retorno_acumulado: float,
                 volatilidade: float, sharpe: float):
        self.data_referencia = data_referencia
        self.carteira = carteira
        self.retorno_periodo = retorno_periodo
        self.retorno_acumulado = retorno_acumulado
        self.volatilidade = volatilidade
        self.sharpe = sharpe
        
    def to_dict(self):
        return {
            'data_referencia': self.data_referencia.strftime('%Y-%m-%d'),
            'carteira': self.carteira,
            'metricas': {
                'retorno_periodo': f"{self.retorno_periodo * 100:.2f}%",
                'retorno_acumulado': f"{self.retorno_acumulado * 100:.2f}%",
                'volatilidade': f"{self.volatilidade * 100:.2f}%",
                'sharpe': f"{self.sharpe:.4f}"
            }
        }


class BacktestService:
    """
    Serviço de backtesting para o AGMO
    
    Permite testar a estratégia de otimização em diferentes períodos históricos,
    simulando como a carteira teria performado no passado.
    """
    
    def __init__(self, app):
        self.app = app
        self.resultados: List[BacktestResult] = []
        
    def _buscar_dados_ate_data(self, data_referencia: datetime, 
                                ids_ativos_restringidos: List[int],
                                janela_meses: int = 36) -> Tuple[List[Ativo], pd.DataFrame]:
        """
        Busca dados históricos disponíveis até uma data de referência específica
        
        Args:
            data_referencia: Data limite para os dados históricos
            ids_ativos_restringidos: IDs de ativos que devem ser excluídos
            janela_meses: Número de meses de histórico a considerar (padrão: 36 meses = 3 anos)
            
        Returns:
            Tupla com (lista de ativos, DataFrame com retornos)
        """
        with self.app.app_context():
            # Data inicial da janela de análise
            data_inicio = data_referencia - relativedelta(months=janela_meses)
            
            print(f"\n{'=' * 70}")
            print(f"📅 BUSCANDO DADOS HISTÓRICOS")
            print(f"{'=' * 70}")
            print(f"  Data Início: {data_inicio.strftime('%Y-%m-%d')}")
            print(f"  Data Fim: {data_referencia.strftime('%Y-%m-%d')}")
            print(f"  Janela: {janela_meses} meses")
            
            # Buscar ativos elegíveis
            query_ativos = db.session.query(Ativo).filter(
                ~Ativo.id.in_(ids_ativos_restringidos) if ids_ativos_restringidos else True,
                Ativo.tipo == TipoAtivo.ACAO
            )
            ativos_candidatos = query_ativos.all()
            
            if len(ativos_candidatos) < 3:
                raise ValueError("São necessários pelo menos 3 ativos para o backtest.")
            
            # Buscar histórico até a data de referência
            ids_candidatos = [a.id for a in ativos_candidatos]
            query_historico = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker,
                Ativo.id
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
                .filter(
                    HistoricoPrecos.id_ativo.in_(ids_candidatos),
                    HistoricoPrecos.data >= data_inicio.date(),
                    HistoricoPrecos.data <= data_referencia.date()
                ) \
                .order_by(HistoricoPrecos.data)
            
            df_historico = pd.read_sql(
                query_historico.statement,
                con=db.session.connection()
            )
            
            if df_historico.empty:
                raise ValueError(f"Sem histórico disponível até {data_referencia.strftime('%Y-%m-%d')}")
            
            # Pivot para ter retornos por ativo
            df_retornos = df_historico.pivot(
                index='data', 
                columns='ticker', 
                values='variacao_mensal'
            ).dropna()
            
            # Filtrar apenas ativos com histórico completo
            ativos_validos = df_retornos.columns.tolist()
            ativos_finais = [a for a in ativos_candidatos if a.ticker in ativos_validos]
            
            if len(ativos_finais) < 3:
                raise ValueError(f"Apenas {len(ativos_finais)} ativos têm histórico completo no período.")
            
            print(f"  ✅ Ativos com histórico completo: {len(ativos_finais)}")
            print(f"  📊 Registros por ativo: {len(df_retornos)}")
            
            return ativos_finais, df_retornos
    
    def _otimizar_carteira_historica(self, data_referencia: datetime,
                                     ids_ativos_restringidos: List[int],
                                     nivel_risco: str,
                                     janela_meses: int = 36) -> List[Dict]:
        """
        Otimiza uma carteira usando apenas dados disponíveis até uma data específica
        
        Args:
            data_referencia: Data de referência para o backtest
            ids_ativos_restringidos: IDs de ativos a excluir
            nivel_risco: Perfil de risco (conservador, moderado, arrojado)
            janela_meses: Janela de histórico a considerar
            
        Returns:
            Lista com a composição da carteira otimizada
        """
        print(f"\n{'=' * 70}")
        print(f"🎯 OTIMIZANDO CARTEIRA PARA {data_referencia.strftime('%Y-%m-%d')}")
        print(f"{'=' * 70}")
        
        # Buscar dados históricos até a data de referência
        ativos_disponiveis, df_retornos = self._buscar_dados_ate_data(
            data_referencia, 
            ids_ativos_restringidos,
            janela_meses
        )
        
        tickers = df_retornos.columns.tolist()
        retornos_medios = df_retornos.mean().values
        matriz_covariancia = df_retornos.cov().values
        historico_retornos = df_retornos.values
        
        # Criar problema de otimização
        problema = PersonalizedPortfolioProblem(
            retornos_medios=retornos_medios,
            matriz_covariancia=matriz_covariancia,
            historico_retornos=historico_retornos,
            tickers=tickers,
            nivel_risco=nivel_risco
        )
        
        # Configurar e executar algoritmo
        sampling = SimplexSampling()
        crossover = SimplexCrossover(eta=15)
        mutation = SimplexMutation(eta=20)
        
        algoritmo = NSGA2(
            pop_size=100, 
            crossover=crossover, 
            mutation=mutation, 
            sampling=sampling
        )
        
        resultado = minimize(
            problema, 
            algoritmo, 
            ('n_gen', 50), 
            verbose=False
        )
        
        if resultado.X is None:
            raise ValueError("Algoritmo não encontrou solução.")
        
        # Escolher melhor carteira baseada no perfil de risco
        pesos_otimos = self._escolher_melhor_carteira(
            resultado.F, 
            resultado.X, 
            nivel_risco
        )
        
        # Montar composição final
        composicao = []
        for i, ativo in enumerate(ativos_disponiveis):
            peso = pesos_otimos[i]
            if peso > 0.001:  # Filtrar pesos insignificantes
                composicao.append({
                    'id_ativo': ativo.id,
                    'ticker': ativo.ticker,
                    'nome': ativo.nome,
                    'peso': float(peso)
                })
        
        # Normalizar pesos para soma = 1
        soma_pesos = sum(item['peso'] for item in composicao)
        for item in composicao:
            item['peso'] = item['peso'] / soma_pesos
        
        print(f"  ✅ Carteira otimizada com {len(composicao)} ativos")
        
        return composicao
    
    def _escolher_melhor_carteira(self, objetivos: np.ndarray, 
                                   solucoes: np.ndarray, 
                                   nivel_risco: str) -> np.ndarray:
        """
        Seleciona a melhor carteira da Fronteira de Pareto
        """
        objetivos = objetivos.copy()
        objetivos[:, 0] = -objetivos[:, 0]  # Inverte retorno
        
        # Normalização
        objetivos_norm = np.zeros_like(objetivos)
        for i in range(objetivos.shape[1]):
            col = objetivos[:, i]
            min_val, max_val = col.min(), col.max()
            
            if max_val - min_val > 1e-10:
                objetivos_norm[:, i] = (col - min_val) / (max_val - min_val)
            else:
                objetivos_norm[:, i] = 0.5
        
        # Pesos por perfil
        pesos_perfil = {
            'conservador': np.array([0.2, 0.4, 0.4]),
            'moderado': np.array([0.4, 0.3, 0.3]),
            'arrojado': np.array([0.6, 0.2, 0.2])
        }
        pesos = pesos_perfil[nivel_risco]
        
        # Calcular scores
        scores = (
            (objetivos_norm[:, 0] * pesos[0]) - 
            (objetivos_norm[:, 1] * pesos[1]) - 
            (objetivos_norm[:, 2] * pesos[2])
        )
        
        idx_melhor = np.argmax(scores)
        return solucoes[idx_melhor]
    
    def _calcular_retorno_carteira(self, carteira: List[Dict], 
                                    data_inicio: datetime,
                                    data_fim: datetime) -> Tuple[float, List[float]]:
        """
        Calcula o retorno de uma carteira em um período específico
        
        Args:
            carteira: Lista com composição da carteira
            data_inicio: Data inicial do período
            data_fim: Data final do período
            
        Returns:
            Tupla com (retorno_total, lista_de_retornos_mensais)
        """
        with self.app.app_context():
            # Buscar retornos dos ativos no período
            ids_ativos = [item['id_ativo'] for item in carteira]
            
            query = db.session.query(
                HistoricoPrecos.data,
                HistoricoPrecos.variacao_mensal,
                Ativo.ticker
            ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
                .filter(
                    HistoricoPrecos.id_ativo.in_(ids_ativos),
                    HistoricoPrecos.data > data_inicio.date(),
                    HistoricoPrecos.data <= data_fim.date()
                ) \
                .order_by(HistoricoPrecos.data)
            
            df = pd.read_sql(query.statement, con=db.session.connection())
            
            if df.empty:
                return 0.0, []
            
            # Pivot para ter retornos por ativo
            df_retornos = df.pivot(
                index='data',
                columns='ticker',
                values='variacao_mensal'
            )
            
            # Calcular retorno ponderado da carteira
            pesos_dict = {item['ticker']: item['peso'] for item in carteira}
            
            retornos_mensais = []
            for data_idx in df_retornos.index:
                retorno_mes = 0
                for ticker in df_retornos.columns:
                    if ticker in pesos_dict:
                        ret_ativo = df_retornos.loc[data_idx, ticker]
                        if pd.notna(ret_ativo):
                            retorno_mes += pesos_dict[ticker] * ret_ativo
                
                retornos_mensais.append(retorno_mes)
            
            # Calcular retorno acumulado
            retorno_total = (1 + pd.Series(retornos_mensais)).prod() - 1
            
            return float(retorno_total), retornos_mensais
    
    def executar_backtest(self, 
                         data_inicio: datetime,
                         data_fim: datetime,
                         ids_ativos_restringidos: Optional[List[int]] = None,
                         nivel_risco: str = 'moderado',
                         frequencia_rebalanceamento_meses: int = 6,
                         janela_otimizacao_meses: int = 36) -> List[BacktestResult]:
        """
        Executa backtest completo em um período
        
        Args:
            data_inicio: Data inicial do backtest
            data_fim: Data final do backtest
            ids_ativos_restringidos: IDs de ativos a excluir
            nivel_risco: Perfil de risco (conservador, moderado, arrojado)
            frequencia_rebalanceamento_meses: Frequência de rebalanceamento em meses
            janela_otimizacao_meses: Janela de histórico para otimização
            
        Returns:
            Lista de BacktestResult com os resultados de cada período
        """
        print(f"\n{'=' * 70}")
        print(f"🚀 INICIANDO BACKTEST")
        print(f"{'=' * 70}")
        print(f"  Período: {data_inicio.strftime('%Y-%m-%d')} até {data_fim.strftime('%Y-%m-%d')}")
        print(f"  Perfil de Risco: {nivel_risco}")
        print(f"  Rebalanceamento: a cada {frequencia_rebalanceamento_meses} meses")
        print(f"  Janela de Otimização: {janela_otimizacao_meses} meses")
        
        if ids_ativos_restringidos is None:
            ids_ativos_restringidos = []
        
        self.resultados = []
        retorno_acumulado_total = 0.0
        
        # Gerar datas de rebalanceamento
        datas_rebalanceamento = []
        data_atual = data_inicio
        while data_atual <= data_fim:
            datas_rebalanceamento.append(data_atual)
            data_atual = data_atual + relativedelta(months=frequencia_rebalanceamento_meses)
        
        # Adicionar data final se não estiver incluída
        if datas_rebalanceamento[-1] != data_fim:
            datas_rebalanceamento.append(data_fim)
        
        print(f"\n  📅 Datas de Rebalanceamento: {len(datas_rebalanceamento)}")
        
        carteira_atual = None
        
        for i in range(len(datas_rebalanceamento) - 1):
            data_rebalanceamento = datas_rebalanceamento[i]
            data_proxima = datas_rebalanceamento[i + 1]
            
            print(f"\n{'─' * 70}")
            print(f"📊 PERÍODO {i + 1}/{len(datas_rebalanceamento) - 1}")
            print(f"{'─' * 70}")
            
            # Otimizar carteira na data de rebalanceamento
            try:
                carteira_atual = self._otimizar_carteira_historica(
                    data_rebalanceamento,
                    ids_ativos_restringidos,
                    nivel_risco,
                    janela_otimizacao_meses
                )
                
                print(f"\n  💼 Composição da Carteira:")
                for item in sorted(carteira_atual, key=lambda x: x['peso'], reverse=True):
                    print(f"     {item['ticker']:8s} - {item['peso']*100:6.2f}%")
                
            except Exception as e:
                print(f"  ❌ Erro ao otimizar carteira: {e}")
                continue
            
            # Calcular retorno no período até o próximo rebalanceamento
            try:
                retorno_periodo, retornos_mensais = self._calcular_retorno_carteira(
                    carteira_atual,
                    data_rebalanceamento,
                    data_proxima
                )
                
                # Calcular métricas
                retorno_acumulado_total = (1 + retorno_acumulado_total) * (1 + retorno_periodo) - 1
                
                if retornos_mensais:
                    volatilidade = np.std(retornos_mensais) * np.sqrt(12)  # Anualizada
                    retorno_medio = np.mean(retornos_mensais) * 12  # Anualizado
                    sharpe = retorno_medio / volatilidade if volatilidade > 0 else 0
                else:
                    volatilidade = 0
                    sharpe = 0
                
                # Criar resultado
                resultado = BacktestResult(
                    data_referencia=data_rebalanceamento,
                    carteira=carteira_atual,
                    retorno_periodo=retorno_periodo,
                    retorno_acumulado=retorno_acumulado_total,
                    volatilidade=volatilidade,
                    sharpe=sharpe
                )
                
                self.resultados.append(resultado)
                
                print(f"\n  📈 Métricas do Período:")
                print(f"     Retorno: {retorno_periodo * 100:+.2f}%")
                print(f"     Retorno Acumulado: {retorno_acumulado_total * 100:+.2f}%")
                print(f"     Volatilidade: {volatilidade * 100:.2f}%")
                print(f"     Sharpe: {sharpe:.4f}")
                
            except Exception as e:
                print(f"  ❌ Erro ao calcular retorno: {e}")
                continue
        
        print(f"\n{'=' * 70}")
        print(f"✅ BACKTEST CONCLUÍDO")
        print(f"{'=' * 70}")
        print(f"  Retorno Total: {retorno_acumulado_total * 100:+.2f}%")
        print(f"  Número de Rebalanceamentos: {len(self.resultados)}")
        
        return self.resultados
    
    def gerar_relatorio(self, salvar_graficos: bool = True) -> Dict:
        """
        Gera relatório completo do backtest com gráficos
        
        Args:
            salvar_graficos: Se True, salva os gráficos em arquivos
            
        Returns:
            Dicionário com métricas consolidadas
        """
        if not self.resultados:
            raise ValueError("Execute o backtest antes de gerar o relatório.")
        
        print(f"\n{'=' * 70}")
        print(f"📊 GERANDO RELATÓRIO DO BACKTEST")
        print(f"{'=' * 70}")
        
        # Extrair séries temporais
        datas = [r.data_referencia for r in self.resultados]
        retornos_acumulados = [r.retorno_acumulado for r in self.resultados]
        retornos_periodo = [r.retorno_periodo for r in self.resultados]
        volatilidades = [r.volatilidade for r in self.resultados]
        sharpes = [r.sharpe for r in self.resultados]
        
        # Calcular métricas consolidadas
        retorno_total = retornos_acumulados[-1] if retornos_acumulados else 0
        retorno_medio = np.mean(retornos_periodo)
        volatilidade_media = np.mean(volatilidades)
        sharpe_medio = np.mean(sharpes)
        max_drawdown = self._calcular_max_drawdown(retornos_acumulados)
        
        metricas = {
            'retorno_total': f"{retorno_total * 100:.2f}%",
            'retorno_medio_periodo': f"{retorno_medio * 100:.2f}%",
            'volatilidade_media': f"{volatilidade_media * 100:.2f}%",
            'sharpe_medio': f"{sharpe_medio:.4f}",
            'max_drawdown': f"{max_drawdown * 100:.2f}%",
            'num_rebalanceamentos': len(self.resultados)
        }
        
        print(f"\n  📈 Métricas Consolidadas:")
        for chave, valor in metricas.items():
            print(f"     {chave}: {valor}")
        
        # Gerar gráficos
        if salvar_graficos:
            self._plotar_resultados(datas, retornos_acumulados, retornos_periodo, 
                                    volatilidades, sharpes)
        
        return metricas
    
    def _calcular_max_drawdown(self, retornos_acumulados: List[float]) -> float:
        """Calcula o máximo drawdown da série de retornos"""
        valores = [(1 + r) for r in retornos_acumulados]
        pico = valores[0]
        max_dd = 0
        
        for valor in valores:
            if valor > pico:
                pico = valor
            dd = (pico - valor) / pico
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _plotar_resultados(self, datas, retornos_acumulados, retornos_periodo,
                           volatilidades, sharpes):
        """Gera gráficos dos resultados do backtest"""
        
        # Configurar estilo
        sns.set_style("whitegrid")
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle('Resultados do Backtest', fontsize=16, fontweight='bold')
        
        # Gráfico 1: Retorno Acumulado
        axes[0, 0].plot(datas, [r * 100 for r in retornos_acumulados], 
                       linewidth=2, color='#2E86AB', marker='o')
        axes[0, 0].set_title('Retorno Acumulado ao Longo do Tempo')
        axes[0, 0].set_xlabel('Data')
        axes[0, 0].set_ylabel('Retorno Acumulado (%)')
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].axhline(y=0, color='red', linestyle='--', alpha=0.5)
        
        # Gráfico 2: Retorno por Período
        cores = ['green' if r > 0 else 'red' for r in retornos_periodo]
        axes[0, 1].bar(range(len(retornos_periodo)), 
                      [r * 100 for r in retornos_periodo],
                      color=cores, alpha=0.7)
        axes[0, 1].set_title('Retorno por Período de Rebalanceamento')
        axes[0, 1].set_xlabel('Período')
        axes[0, 1].set_ylabel('Retorno (%)')
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        # Gráfico 3: Volatilidade
        axes[1, 0].plot(datas, [v * 100 for v in volatilidades],
                       linewidth=2, color='#F18F01', marker='s')
        axes[1, 0].set_title('Volatilidade ao Longo do Tempo')
        axes[1, 0].set_xlabel('Data')
        axes[1, 0].set_ylabel('Volatilidade Anualizada (%)')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Gráfico 4: Sharpe Ratio
        axes[1, 1].plot(datas, sharpes, linewidth=2, 
                       color='#A23B72', marker='^')
        axes[1, 1].set_title('Sharpe Ratio ao Longo do Tempo')
        axes[1, 1].set_xlabel('Data')
        axes[1, 1].set_ylabel('Sharpe Ratio')
        axes[1, 1].grid(True, alpha=0.3)
        axes[1, 1].axhline(y=0, color='red', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        # Salvar gráfico
        nome_arquivo = f'backtest_resultados_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(nome_arquivo, dpi=300, bbox_inches='tight')
        print(f"\n  💾 Gráficos salvos em: {nome_arquivo}")
        
        plt.show()


def exemplo_uso():
    """Exemplo de como usar o serviço de backtesting"""
    
    app = create_app()
    
    # Configurar parâmetros do backtest
    data_inicio = datetime(2020, 1, 1)
    data_fim = datetime(2024, 12, 31)
    ids_ativos_restringidos = []  # Sem restrições
    nivel_risco = 'moderado'
    frequencia_rebalanceamento = 6  # Rebalancear a cada 6 meses
    janela_otimizacao = 36  # Usar 3 anos de histórico
    
    # Criar serviço e executar backtest
    backtest = BacktestService(app)
    
    resultados = backtest.executar_backtest(
        data_inicio=data_inicio,
        data_fim=data_fim,
        ids_ativos_restringidos=ids_ativos_restringidos,
        nivel_risco=nivel_risco,
        frequencia_rebalanceamento_meses=frequencia_rebalanceamento,
        janela_otimizacao_meses=janela_otimizacao
    )
    
    # Gerar relatório
    metricas = backtest.gerar_relatorio(salvar_graficos=True)
    
    # Exibir resultados detalhados
    print(f"\n{'=' * 70}")
    print(f"📋 RESULTADOS DETALHADOS")
    print(f"{'=' * 70}")
    
    for i, resultado in enumerate(resultados, 1):
        print(f"\n  Período {i} - {resultado.data_referencia.strftime('%Y-%m-%d')}")
        print(f"  Composição:")
        for item in sorted(resultado.carteira, key=lambda x: x['peso'], reverse=True)[:5]:
            print(f"    {item['ticker']:8s} - {item['peso']*100:6.2f}%")
        print(f"  Retorno Período: {resultado.retorno_periodo * 100:+.2f}%")
        print(f"  Retorno Acumulado: {resultado.retorno_acumulado * 100:+.2f}%")


if __name__ == "__main__":
    exemplo_uso()
