import sys
from app import create_app
from commands import seed_assets, update_prices, update_daily_prices


def main():
    """Função principal que interpreta os comandos."""
    # Cria a instância da aplicação Flask
    app = create_app()

    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "setup":
        print("Populando os ativos do arquivo .csv...")
        seed_assets(app)
        print("\nAtivos populados!")

        print("Atualizando os preços dos ativos...")
        update_prices(app)
        print("\nPreços atualizados.")

    elif command == "run":
        print("Iniciando a API...")
        # Para rodar o servidor, usamos o método run do próprio app
        app.run(debug=True)

    elif command == "update-daily":
        print("Executando atualização diária de preços...")
        update_daily_prices(app)
        print("\nAtualização diária concluída!")

    else:
        print(f"\nComando '{command}' não reconhecido.")


if __name__ == "__main__":
    main()