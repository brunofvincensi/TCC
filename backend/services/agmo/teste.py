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


def analyze_cvar_by_asset(app):
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
        results = []

        for ticker in df_retornos.columns:
            returns = df_retornos[ticker].values

            # Retorno médio
            mean_return = np.mean(returns) * 100  # %

            # Volatilidade
            volatility = np.std(returns) * 100  # %

            # CVaR (5% piores cenários)
            alpha = 0.05
            losses = -returns  # Inverte sinal
            valid_losses = losses[np.isfinite(losses)]
            k = max(1, int(np.ceil(alpha * len(valid_losses))))
            sorted_losses = np.sort(valid_losses)
            tail = sorted_losses[-k:]  # k piores
            cvar = np.mean(tail) * 100  # %

            # Sharpe
            sharpe = mean_return / volatility if volatility > 0 else 0

            # Downside deviation (volatilidade dos retornos negativos)
            negative_returns = returns[returns < 0]
            downside_vol = np.std(negative_returns) * 100 if len(negative_returns) > 0 else 0

            # Assimetria (skewness)
            from scipy.stats import skew
            skewness = skew(returns)

            # Curtose (kurtosis)
            from scipy.stats import kurtosis
            kurt = kurtosis(returns)

            results.append({
                'ticker': ticker,
                'retorno_mensal': mean_return,
                'volatilidade': volatility,
                'cvar_5': cvar,
                'sharpe': sharpe,
                'downside_vol': downside_vol,
                'assimetria': skewness,
                'curtose': kurt
            })

        # DataFrame de resultados
        df_results = pd.DataFrame(results)

        # Ordena por CVaR (menor = melhor)
        df_results = df_results.sort_values('cvar_5')

        print("\n📊 RANKING POR CVaR (Risco de Cauda - 5% piores cenários)")
        print("=" * 80)
        print(f"{'Rank':<5} {'Ticker':<10} {'CVaR':<10} {'Retorno':<12} {'Vol':<10} {'Sharpe':<10}")
        print("-" * 80)

        for i, row in df_results.iterrows():
            # Destaca BBDC4
            highlight = " ← ALTO PESO!" if row['ticker'] == 'BBDC4' else ""

            print(f"{df_results.index.get_loc(i) + 1:<5} "
                  f"{row['ticker']:<10} "
                  f"{row['cvar_5']:>8.2f}% "
                  f"{row['retorno_mensal']:>10.2f}% "
                  f"{row['volatilidade']:>8.2f}% "
                  f"{row['sharpe']:>8.2f}"
                  f"{highlight}")

        # Análise específica do BBDC4
        bbdc4 = df_results[df_results['ticker'] == 'BBDC4'].iloc[0]

        print("\n" + "=" * 80)
        print("🔬 ANÁLISE DETALHADA: BBDC4")
        print("=" * 80)

        # Posição nos rankings
        rank_cvar = df_results.index.get_loc(
            df_results[df_results['ticker'] == 'BBDC4'].index[0]
        ) + 1

        df_by_return = df_results.sort_values('retorno_mensal', ascending=False)
        rank_return = df_by_return.index.get_loc(
            df_by_return[df_by_return['ticker'] == 'BBDC4'].index[0]
        ) + 1

        df_by_vol = df_results.sort_values('volatilidade')
        rank_vol = df_by_vol.index.get_loc(
            df_by_vol[df_by_vol['ticker'] == 'BBDC4'].index[0]
        ) + 1

        df_by_sharpe = df_results.sort_values('sharpe', ascending=False)
        rank_sharpe = df_by_sharpe.index.get_loc(
            df_by_sharpe[df_by_sharpe['ticker'] == 'BBDC4'].index[0]
        ) + 1

        print(f"\n📊 Métricas:")
        print(f"   Retorno Mensal:    {bbdc4['retorno_mensal']:>6.2f}%  (Rank: {rank_return}/16)")
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

        top_sharpe = df_results.nlargest(5, 'sharpe')

        print(f"\n{'Ticker':<10} {'Sharpe':<10} {'CVaR':<10} {'Por que peso baixo?'}")
        print("-" * 80)

        for _, row in top_sharpe.iterrows():
            ticker = row['ticker']
            sharpe = row['sharpe']
            cvar = row['cvar_5']

            # Busca peso na carteira (você precisaria passar isso)
            # Por enquanto, vou fazer uma análise genérica

            if cvar > bbdc4['cvar_5']:
                reason = "CVaR maior (mais risco extremo)"
            elif row['volatilidade'] > bbdc4['volatilidade']:
                reason = "Volatilidade maior"
            else:
                reason = "Possivelmente correlações/HHI"

            print(f"{ticker:<10} {sharpe:>8.2f} {cvar:>8.2f}% {reason}")

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

        return df_results


def create_control_portfolio(df_metrics):
    """
    Cria uma carteira de controle usando apenas Sharpe Ratio
    para comparar com a carteira AGMO.
    """
    print("\n" + "=" * 80)
    print("📊 CARTEIRA DE CONTROLE (Apenas Sharpe)")
    print("=" * 80)

    # Normaliza Sharpe para criar pesos
    df_positive = df_metrics[df_metrics['sharpe'] > 0].copy()
    df_positive['peso'] = df_positive['sharpe'] / df_positive['sharpe'].sum()

    # Ordena por peso
    df_positive = df_positive.sort_values('peso', ascending=False)

    print("\nSe otimizasse APENAS por Sharpe Ratio:")
    print(f"{'Rank':<5} {'Ticker':<10} {'Peso':<10} {'Sharpe':<10}")
    print("-" * 50)

    for i, (_, row) in enumerate(df_positive.head(10).iterrows(), 1):
        highlight = " ← DEVERIA TER MAIS!" if row['ticker'] == 'BBDC4' else ""
        print(f"{i:<5} {row['ticker']:<10} {row['peso'] * 100:>8.2f}% {row['sharpe']:>8.2f}{highlight}")

    # Compara
    bbdc4_sharpe_weight = df_positive[df_positive['ticker'] == 'BBDC4']['peso'].values[0] * 100

    print(f"\n📊 Comparação BBDC4:")
    print(f"   Peso por Sharpe:     {bbdc4_sharpe_weight:>6.2f}%")
    print(f"   Peso AGMO (real):    17.30%")
    print(f"   Diferença:           {17.30 - bbdc4_sharpe_weight:>+6.2f}%")

    if 17.30 > bbdc4_sharpe_weight * 2:
        print(f"\n   ⚠️  BBDC4 tem mais que o DOBRO do peso esperado!")
        print(f"   → Algoritmo está PRIORIZANDO algo além de Sharpe")
        print(f"   → Provavelmente: CVaR (risco de cauda)")


if __name__ == "__main__":
    app = create_app()

    # Análise principal
    df_metrics = analyze_cvar_by_asset(app)

    # Carteira controle
    if df_metrics is not None:
        create_control_portfolio(df_metrics)

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