from pymoo.termination.default import DefaultMultiObjectiveTermination


def _printar_matriz(matriz, formato=".3f"):
    """
    Printa matriz formatada com cores

    Args:
        matriz: DataFrame pandas com a matriz
        titulo: Título da matriz
        formato: Formato dos números (ex: ".3f")
    """
    tickers = matriz.columns.tolist()
    n = len(tickers)

    # Cabeçalho
    header = "        "
    for ticker in tickers:
        header += f"{ticker:>10s} "
    print(header)
    print("  " + "-" * (11 * n + 8))

    # Linhas
    for i, ticker_linha in enumerate(tickers):
        linha = f"  {ticker_linha:6s} |"

        for j, ticker_coluna in enumerate(tickers):
            valor = matriz.iloc[i, j]

            # Colorir diagonal
            if i == j:
                linha += f" {valor:>9{formato}}*"  # Asterisco na diagonal
            else:
                linha += f" {valor:>9{formato}} "

        print(linha)

    print()

def calcular_geracoes_maximas(n_ativos: int, pop_size: int) -> int:
    """
    Calcula número máximo de gerações baseado na complexidade.

    Regras:
    - Mais ativos = mais gerações necessárias
    - Total de avaliações ≈ 5000-15000 é um bom alvo
    """
    # Alvos de avaliações baseados na complexidade
    if n_ativos < 10:
        alvo_avaliacoes = 5000
    elif n_ativos < 20:
        alvo_avaliacoes = 8000
    else:
        alvo_avaliacoes = 12000

    n_gen = max(100, int(alvo_avaliacoes / pop_size))

    print(f"  🔄 Gerações máximas: {n_gen} (≈ {n_gen * pop_size} avaliações)")
    return n_gen

def criar_criterio_parada(n_gen_max: int, n_objetivos: int = 3):
    """
    Cria critério de parada multi-objetivo adaptativo.

    Para de executar quando:
    1. Atingir n_gen_max gerações, OU
    2. Não houver melhoria significativa por N gerações consecutivas
    """
    # Para 3 objetivos, usamos tolerância mais relaxada
    termination = DefaultMultiObjectiveTermination(
        xtol=1e-8,  # Tolerância nas variáveis
        cvtol=1e-6,  # Tolerância nas restrições
        ftol=0.0025,  # Tolerância nos objetivos (0.25%)
        period=30,  # Avaliar convergência a cada 30 gerações
        n_max_gen=n_gen_max,  # Máximo de gerações
        n_max_evals=None  # Sem limite de avaliações (controlado por n_gen)
    )

    print(f"  ⏱️  Critério de parada configurado:")
    print(f"      - Máximo: {n_gen_max} gerações")
    print(f"      - Parada antecipada: se melhoria < 0.25% por 30 gerações")

    return termination