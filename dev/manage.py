import sys
import os


def print_help():
    """Exibe a mensagem de ajuda com os comandos disponíveis."""
    print("----------------------------------------------------")
    print("     Gerenciador de Tarefas do Projeto de Otimização    ")
    print("----------------------------------------------------")
    print("Use: python manage.py [comando]")
    print("\nComandos disponíveis:")
    print("  setup      - 🚀 Configura o ambiente pela primeira vez.")
    print("  run        - ▶️  Inicia a API Flask em modo de desenvolvimento.")
    print("  update     - 🔄 Atualiza os preços dos ativos (últimos 5 dias).")
    print("----------------------------------------------------")


def run_command(command_string):
    """Executa um comando no terminal e verifica se houve erro."""
    print(f"\n> Executando: {command_string}")
    exit_code = os.system(command_string)
    if exit_code != 0:
        print(f"\n❌ ERRO: O comando '{command_string}' falhou com o código de saída {exit_code}.")
        sys.exit(exit_code)  # Interrompe o script se um comando falhar


def main():
    """Função principal que interpreta os comandos da linha de comando."""

    # Pega o comando do terminal (ex: 'setup', 'run', etc.)
    # sys.argv é a lista de argumentos, sendo o primeiro o nome do script.
    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "setup":
        print("🚀 Configurando o ambiente pela primeira vez...")
        run_command("flask seed-assets")
        print("\nBuscando o histórico COMPLETO de preços (pode demorar)...")
        run_command("flask update-prices --full-history")
        print("\n✅ Ambiente configurado com sucesso!")

    elif command == "run":
        print("▶️  Iniciando a API em http://127.0.0.1:5000 ...")
        # O comando 'flask run' prende o terminal, então ele deve ser o último.
        os.system("flask run")

    elif command == "update":
        print("🔄 Atualizando os preços dos ativos (últimos 5 dias)...")
        run_command("flask update-prices")
        print("\n✅ Preços atualizados.")

    elif command == "help":
        print_help()

    else:
        print(f"\nComando '{command}' não reconhecido.")
        print_help()


if __name__ == "__main__":
    main()