import sys
from app import create_app
from commands import seed_assets, update_prices  # Importe as funções diretamente


def print_help():
    """Exibe a mensagem de ajuda."""
    # ... (código da função print_help continua o mesmo) ...
    print("----------------------------------------------------")
    print("     Gerenciador de Tarefas do Projeto de Otimização    ")
    print("----------------------------------------------------")
    print("Use: python manage.py [comando]")
    print("\nComandos disponíveis:")
    print("  setup      - 🚀 Configura o ambiente pela primeira vez.")
    print("  run        - ▶️  Inicia a API Flask em modo de desenvolvimento.")
    print("  update     - 🔄 Atualiza os preços dos ativos (último ano).")
    print("----------------------------------------------------")


def main():
    """Função principal que interpreta os comandos."""
    # Cria a instância da aplicação Flask
    app = create_app()

    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "setup":
        print("🚀 Configurando o ambiente pela primeira vez...")
        seed_assets(app)
      #  update_prices(app, full_history=True)
        print("\n✅ Ambiente configurado com sucesso!")

    elif command == "run":
        print("▶️  Iniciando a API em http://127.0.0.1:5000 ...")
        # Para rodar o servidor, usamos o método run do próprio app
        app.run(debug=True)

    elif command == "update":
        print("🔄 Atualizando os preços dos ativos (último ano)...")
        update_prices(app, full_history=False)
        print("\n✅ Preços atualizados.")

    elif command == "help":
        print_help()

    else:
        print(f"\nComando '{command}' não reconhecido.")
        print_help()


if __name__ == "__main__":
    main()