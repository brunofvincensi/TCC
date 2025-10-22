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
