"""
Análise: Por que BBDC4 domina a carteira otimizada?
====================================================

Este script investiga o papel de cada ativo nos 3 objetivos:
1. Retorno
2. Volatilidade (Variância)
3. CVaR (Risco de Cauda)
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from app import create_app
from models import db, Ativo, HistoricoPrecos
from models.ativo import TipoAtivo


def analisar_cvar_por_ativo(app):
    """
    Calcula o CVaR individual de cada ativo para entender
    por que BBDC4 foi escolhido.
    """
    print("\n" + "=" * 80)
    print("🔍 ANÁLISE: Por que BBDC4 domina?")
    print("=" * 80)

    with app.app_context():
        # Busca ativos e histórico
        ativos = db.session.query(Ativo).filter(
            Ativo.tipo == TipoAtivo.ACAO
        ).all()

        if not ativos:
            print("Nenhum ativo encontrado")
            return

        ids_ativos = [a.id for a in ativos]

        # Busca histórico
        query = db.session.query(
            HistoricoPrecos.data,
            HistoricoPrecos.variacao_mensal,
            Ativo.ticker
        ).join(Ativo, HistoricoPrecos.id_ativo == Ativo.id) \
            .filter(HistoricoPrecos.id_ativo.in_(ids_ativos)) \
            .order_by(HistoricoPrecos.data)

        df = pd.read_sql(query.statement, con=db.session.connection())

        if df.empty:
            print("Sem dados históricos")
            return

        # Pivot
        df_retornos = df.pivot(
            index='data',
            columns='ticker',
            values='variacao_mensal'
        ).dropna()

        # Calcula métricas por ativo
        resultados = []

        for ticker in df_retornos.columns:
            retornos = df_retornos[ticker].values

            # Retorno médio
            ret_medio = np.mean(retornos) * 100  # %

            # Volatilidade
            volatilidade = np.std(retornos) * 100  # %

            # CVaR (5% piores cenários)
            alpha = 0.05
            perdas = -retornos  # Inverte sinal
            perdas_validas = perdas[np.isfinite(perdas)]
            k = max(1, int(np.ceil(alpha * len(perdas_validas))))
            perdas_ordenadas = np.sort(perdas_validas)
            cauda = perdas_ordenadas[-k:]  # k piores
            cvar = np.mean(cauda) * 100  # %

            # Sharpe
            sharpe = ret_medio / volatilidade if volatilidade > 0 else 0

            # Downside deviation (volatilidade dos retornos negativos)
            retornos_negativos = retornos[retornos < 0]
            downside_vol = np.std(retornos_negativos) * 100 if len(retornos_negativos) > 0 else 0

            # Assimetria (skewness)
            from scipy.stats import skew
            assimetria = skew(retornos)

            # Curtose (kurtosis)
            from scipy.stats import kurtosis
            curtose = kurtosis(retornos)

            resultados.append({
                'ticker': ticker,
                'retorno_mensal': ret_medio,
                'volatilidade': volatilidade,
                'cvar_5': cvar,
                'sharpe': sharpe,
                'downside_vol': downside_vol,
                'assimetria': assimetria,
                'curtose': curtose
            })

        # DataFrame de resultados
        df_resultados = pd.DataFrame(resultados)

        # Ordena por CVaR (menor = melhor)
        df_resultados = df_resultados.sort_values('cvar_5')

        print("\n📊 RANKING POR CVaR (Risco de Cauda - 5% piores cenários)")
        print("=" * 80)
        print(f"{'Rank':<5} {'Ticker':<10} {'CVaR':<10} {'Retorno':<12} {'Vol':<10} {'Sharpe':<10}")
        print("-" * 80)

        for i, row in df_resultados.iterrows():
            # Destaca BBDC4
            destaque = " ← ALTO PESO!" if row['ticker'] == 'BBDC4' else ""

            print(f"{df_resultados.index.get_loc(i) + 1:<5} "
                  f"{row['ticker']:<10} "
                  f"{row['cvar_5']:>8.2f}% "
                  f"{row['retorno_mensal']:>10.2f}% "
                  f"{row['volatilidade']:>8.2f}% "
                  f"{row['sharpe']:>8.2f}"
                  f"{destaque}")

        # Análise específica do BBDC4
        bbdc4 = df_resultados[df_resultados['ticker'] == 'BBDC4'].iloc[0]

        print("\n" + "=" * 80)
        print("🔬 ANÁLISE DETALHADA: BBDC4")
        print("=" * 80)

        # Posição nos rankings
        rank_cvar = df_resultados.index.get_loc(
            df_resultados[df_resultados['ticker'] == 'BBDC4'].index[0]
        ) + 1

        df_por_retorno = df_resultados.sort_values('retorno_mensal', ascending=False)
        rank_retorno = df_por_retorno.index.get_loc(
            df_por_retorno[df_por_retorno['ticker'] == 'BBDC4'].index[0]
        ) + 1

        df_por_vol = df_resultados.sort_values('volatilidade')
        rank_vol = df_por_vol.index.get_loc(
            df_por_vol[df_por_vol['ticker'] == 'BBDC4'].index[0]
        ) + 1

        df_por_sharpe = df_resultados.sort_values('sharpe', ascending=False)
        rank_sharpe = df_por_sharpe.index.get_loc(
            df_por_sharpe[df_por_sharpe['ticker'] == 'BBDC4'].index[0]
        ) + 1

        print(f"\n📊 Métricas:")
        print(f"   Retorno Mensal:    {bbdc4['retorno_mensal']:>6.2f}%  (Rank: {rank_retorno}/16)")
        print(f"   Volatilidade:      {bbdc4['volatilidade']:>6.2f}%  (Rank: {rank_vol}/16)")
        print(f"   CVaR (5%):         {bbdc4['cvar_5']:>6.2f}%  (Rank: {rank_cvar}/16) ← CHAVE!")
        print(f"   Sharpe Ratio:      {bbdc4['sharpe']:>6.2f}   (Rank: {rank_sharpe}/16)")
        print(f"   Downside Vol:      {bbdc4['downside_vol']:>6.2f}%")
        print(f"   Assimetria:        {bbdc4['assimetria']:>6.2f}")
        print(f"   Curtose:           {bbdc4['curtose']:>6.2f}")

        print(f"\n💡 INTERPRETAÇÃO:")

        if rank_cvar <= 8:  # Top metade em CVaR
            print(f"   ✅ BBDC4 está no TOP {rank_cvar} em CVaR (menor risco de cauda)")
            print(f"   → Isso explica o alto peso! O algoritmo PRIORIZOU redução")
            print(f"     de risco extremo sobre retorno médio.")
        else:
            print(f"   ⚠️  BBDC4 NÃO está no top de CVaR (rank {rank_cvar})")
            print(f"   → Investigar outros fatores (correlações, HHI, perfil de risco)")

        # Análise de assimetria e curtose
        if bbdc4['assimetria'] > -0.5:
            print(f"\n   ✅ Distribuição pouco assimétrica (poucos outliers negativos)")
        else:
            print(f"\n   ⚠️  Distribuição com cauda negativa (mais crashes)")

        if bbdc4['curtose'] < 3:
            print(f"   ✅ Curtose baixa (retornos comportados)")
        else:
            print(f"   ⚠️  Curtose alta (eventos extremos frequentes)")

        # Comparação com os "melhores" ativos
        print("\n" + "=" * 80)
        print("🤔 Por que NÃO escolheu os de melhor Sharpe?")
        print("=" * 80)

        top_sharpe = df_resultados.nlargest(5, 'sharpe')

        print(f"\n{'Ticker':<10} {'Sharpe':<10} {'CVaR':<10} {'Por que peso baixo?'}")
        print("-" * 80)

        for _, row in top_sharpe.iterrows():
            ticker = row['ticker']
            sharpe = row['sharpe']
            cvar = row['cvar_5']

            # Busca peso na carteira (você precisaria passar isso)
            # Por enquanto, vou fazer uma análise genérica

            if cvar > bbdc4['cvar_5']:
                motivo = "CVaR maior (mais risco extremo)"
            elif row['volatilidade'] > bbdc4['volatilidade']:
                motivo = "Volatilidade maior"
            else:
                motivo = "Possivelmente correlações/HHI"

            print(f"{ticker:<10} {sharpe:>8.2f} {cvar:>8.2f}% {motivo}")

        # Recomendações
        print("\n" + "=" * 80)
        print("💡 RECOMENDAÇÕES PARA INVESTIGAR MAIS")
        print("=" * 80)

        print("\n1. Rode a otimização com PESOS nos objetivos:")
        print("   • Se priorizar RETORNO → BBDC4 deve ter peso menor")
        print("   • Se priorizar CVaR → BBDC4 mantém peso alto")

        print("\n2. Visualize a Fronteira de Pareto:")
        print("   • Veja onde está a solução escolhida")
        print("   • Compare trade-offs")

        print("\n3. Teste diferentes perfis de risco:")
        print("   • Arrojado → deveria reduzir BBDC4")
        print("   • Conservador → deveria aumentar BBDC4")

        print("\n4. Analise as correlações:")
        print("   • BBDC4 tem alta correlação com ITUB4, ITSA4, BBAS3")
        print("   • Mas baixa com SUZB3, EMBR3, VALE3")
        print("   • Pode estar ajudando na diversificação setorial")

        return df_resultados


def criar_carteira_controle(df_metricas):
    """
    Cria uma carteira de controle usando apenas Sharpe Ratio
    para comparar com a carteira AGMO.
    """
    print("\n" + "=" * 80)
    print("📊 CARTEIRA DE CONTROLE (Apenas Sharpe)")
    print("=" * 80)

    # Normaliza Sharpe para criar pesos
    df_positivos = df_metricas[df_metricas['sharpe'] > 0].copy()
    df_positivos['peso'] = df_positivos['sharpe'] / df_positivos['sharpe'].sum()

    # Ordena por peso
    df_positivos = df_positivos.sort_values('peso', ascending=False)

    print("\nSe otimizasse APENAS por Sharpe Ratio:")
    print(f"{'Rank':<5} {'Ticker':<10} {'Peso':<10} {'Sharpe':<10}")
    print("-" * 50)

    for i, (_, row) in enumerate(df_positivos.head(10).iterrows(), 1):
        destaque = " ← DEVERIA TER MAIS!" if row['ticker'] == 'BBDC4' else ""
        print(f"{i:<5} {row['ticker']:<10} {row['peso'] * 100:>8.2f}% {row['sharpe']:>8.2f}{destaque}")

    # Compara
    bbdc4_sharpe_peso = df_positivos[df_positivos['ticker'] == 'BBDC4']['peso'].values[0] * 100

    print(f"\n📊 Comparação BBDC4:")
    print(f"   Peso por Sharpe:     {bbdc4_sharpe_peso:>6.2f}%")
    print(f"   Peso AGMO (real):    17.30%")
    print(f"   Diferença:           {17.30 - bbdc4_sharpe_peso:>+6.2f}%")

    if 17.30 > bbdc4_sharpe_peso * 2:
        print(f"\n   ⚠️  BBDC4 tem mais que o DOBRO do peso esperado!")
        print(f"   → Algoritmo está PRIORIZANDO algo além de Sharpe")
        print(f"   → Provavelmente: CVaR (risco de cauda)")


if __name__ == "__main__":
    app = create_app()

    # Análise principal
    df_metricas = analisar_cvar_por_ativo(app)

    # Carteira controle
    if df_metricas is not None:
        criar_carteira_controle(df_metricas)

    print("\n" + "=" * 80)
    print("✅ ANÁLISE CONCLUÍDA")
    print("=" * 80)

    print("\n🎯 CONCLUSÃO PROVÁVEL:")
    print("   O algoritmo escolheu BBDC4 porque ele oferece o melhor")
    print("   TRADE-OFF entre os 3 objetivos simultâneos:")
    print("   • Retorno: Ruim (0.67%)")
    print("   • Volatilidade: OK (9.35%)")
    print("   • CVaR: Provavelmente BOM (menor risco de cauda)")
    print("\n   Isso é uma característica da otimização MULTIOBJETIVO!")
    print("   Não necessariamente um bug. 😊")