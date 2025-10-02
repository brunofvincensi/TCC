# Define que os alvos não são nomes de arquivos, mas sim receitas de comandos.
# Isso evita conflitos se um arquivo com o mesmo nome existir.
.PHONY: help setup run update db-init db-migrate db-upgrade

# Se "make" for executado sem um alvo, o primeiro da lista (help) será o padrão.
default: help

# Exibe uma mensagem de ajuda com os principais comandos disponíveis.
help:
	@echo "----------------------------------------------------"
	@echo "     Painel de Controle do Projeto de Otimização    "
	@echo "----------------------------------------------------"
	@echo "Comandos disponíveis:"
	@echo "  make setup      - 🚀 Configura o ambiente pela primeira vez."
	@echo "  make run        - ▶️  Inicia a API Flask em modo de desenvolvimento."
	@echo "  make update     - 🔄 Atualiza os preços dos ativos (últimos 5 dias)."
	@echo ""
	@echo "Comandos de Banco de Dados (com Flask-Migrate):"
	@echo "  make db-init    - Inicia o controle de migrações (executar uma vez)."
	@echo "  make db-migrate - Gera um novo arquivo de migração após mudanças nos models."
	@echo "  make db-upgrade - Aplica as migrações ao banco de dados."
	@echo "----------------------------------------------------"

# Executa a sequência completa para configurar o projeto do zero.
setup:
	@echo "🚀 Configurando o ambiente pela primeira vez..."
	# PASSO 1: Aplica as migrações do banco de dados. (Descomente quando usar Flask-Migrate)
	# @make db-upgrade
	@echo "\n1/2 - Populando a tabela de ativos a partir do CSV..."
	flask seed-assets
	@echo "\n2/2 - Buscando o histórico COMPLETO de preços (pode demorar)..."
	flask update-prices --full-history
	@echo "\n✅ Ambiente configurado com sucesso!"

# Atalho para iniciar o servidor de desenvolvimento.
run:
	@echo "▶️  Iniciando a API em http://127.0.0.1:5000 ..."
	flask run

# Executa a atualização diária de preços (busca um histórico curto).
update:
	@echo "🔄 Atualizando os preços dos ativos (últimos 5 dias)..."
	flask update-prices
	@echo "✅ Preços atualizados."

# --- Comandos para Gerenciamento de Migrações de Banco de Dados ---
# Estes comandos são para serem usados com a extensão Flask-Migrate,
# que é a maneira profissional de gerenciar alterações na estrutura do seu banco (models).

# Inicializa o diretório de migrações. Só precisa ser executado uma vez na vida do projeto.
db-init:
	@echo "Initializing migrations..."
	flask db init

# Gera um novo arquivo de migração automaticamente após você alterar seus models.
db-migrate:
	@echo "Generating new migration..."
	flask db migrate -m "Nova migração"

# Aplica as migrações pendentes ao banco de dados.
db-upgrade:
	@echo "Applying migrations..."
	flask db upgrade