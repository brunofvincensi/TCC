"""
Migration: Criar tabela hyperparameter_configs

Este script cria a tabela para armazenar configurações ótimas
de hiperparâmetros do AGMO por quantidade de ativos.

Para executar:
    cd backend
    python migrations/create_hyperparameter_config_table.py
"""

import sys
import os

# Adiciona o diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db


def create_hyperparameter_config_table():
    """Cria a tabela hyperparameter_configs."""

    app = create_app()

    with app.app_context():
        # Importa o model para garantir que está registrado
        from models import HyperparameterConfig

        print("\n" + "=" * 70)
        print("MIGRATION: Criar tabela hyperparameter_configs")
        print("=" * 70)

        try:
            # Verifica se a tabela já existe
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            if 'hyperparameter_configs' in tables:
                print("\n⚠️  Tabela 'hyperparameter_configs' já existe!")

                resposta = input("\nDeseja recriar a tabela? (s/n) [ATENÇÃO: Isso apagará todos os dados]: ")

                if resposta.lower() == 's':
                    print("\n🗑️  Dropando tabela existente...")
                    db.session.execute(db.text('DROP TABLE IF EXISTS hyperparameter_configs CASCADE'))
                    db.session.commit()
                    print("✅ Tabela antiga removida")
                else:
                    print("\n❌ Operação cancelada")
                    return

            # Cria a tabela
            print("\n🔨 Criando tabela 'hyperparameter_configs'...")

            db.create_all()

            print("✅ Tabela criada com sucesso!")

            # Mostra estrutura da tabela
            print("\n📋 Estrutura da tabela:")
            print("=" * 70)

            columns = inspector.get_columns('hyperparameter_configs')

            for col in columns:
                col_type = str(col['type'])
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"   {col['name']:30s} {col_type:20s} {nullable}")

            # Mostra constraints
            print("\n🔒 Constraints:")
            unique_constraints = inspector.get_unique_constraints('hyperparameter_configs')
            for uc in unique_constraints:
                print(f"   UNIQUE: {uc['column_names']}")

            print("\n" + "=" * 70)
            print("✅ MIGRATION CONCLUÍDA COM SUCESSO!")
            print("=" * 70)

            print("\n💡 Próximos passos:")
            print("   1. Execute o tuning adaptativo (exemplo_tuning.py → opção 6)")
            print("   2. O sistema automaticamente usará as configurações ótimas")
            print("   3. Verifique as configurações: SELECT * FROM hyperparameter_configs;")

        except Exception as e:
            print(f"\n❌ Erro ao criar tabela: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()


def rollback_migration():
    """Remove a tabela hyperparameter_configs."""

    app = create_app()

    with app.app_context():
        print("\n" + "=" * 70)
        print("ROLLBACK: Remover tabela hyperparameter_configs")
        print("=" * 70)

        resposta = input("\n⚠️  Tem certeza que deseja remover a tabela? (s/n): ")

        if resposta.lower() != 's':
            print("\n❌ Operação cancelada")
            return

        try:
            print("\n🗑️  Removendo tabela...")

            db.session.execute(db.text('DROP TABLE IF EXISTS hyperparameter_configs CASCADE'))
            db.session.commit()

            print("✅ Tabela removida com sucesso!")

        except Exception as e:
            print(f"\n❌ Erro ao remover tabela: {e}")
            db.session.rollback()


def show_table_info():
    """Mostra informações sobre a tabela."""

    app = create_app()

    with app.app_context():
        from models import HyperparameterConfig

        print("\n" + "=" * 70)
        print("INFORMAÇÕES: hyperparameter_configs")
        print("=" * 70)

        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            if 'hyperparameter_configs' not in tables:
                print("\n⚠️  Tabela 'hyperparameter_configs' não existe!")
                print("   Execute a migration primeiro: python migrations/create_hyperparameter_config_table.py")
                return

            # Conta registros
            count = db.session.query(HyperparameterConfig).count()

            print(f"\n📊 Total de configurações: {count}")

            if count > 0:
                print("\n📋 Configurações armazenadas:")
                print("=" * 70)

                configs = HyperparameterConfig.query.order_by(
                    HyperparameterConfig.num_ativos
                ).all()

                for config in configs:
                    status = "✅ ATIVA" if config.is_active else "❌ INATIVA"
                    print(f"\n   {status}")
                    print(f"   Ativos: {config.num_ativos}")
                    print(f"   Perfil: {config.nivel_risco}")
                    print(f"   População: {config.population_size}, Gerações: {config.generations}")
                    print(f"   Hypervolume: {config.hypervolume_mean:.6f} (±{config.hypervolume_std:.6f})")
                    print(f"   Tempo: {config.execution_time_mean:.2f}s (±{config.execution_time_std:.2f}s)")
                    print(f"   Data: {config.tuning_date.strftime('%Y-%m-%d %H:%M')}")

            else:
                print("\n   Nenhuma configuração armazenada ainda")
                print("   Execute o tuning adaptativo (exemplo_tuning.py → opção 6)")

        except Exception as e:
            print(f"\n❌ Erro: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MIGRATION TOOL - Hyperparameter Configs")
    print("=" * 70)

    print("\nEscolha uma opção:")
    print("1. Criar tabela (UP)")
    print("2. Remover tabela (DOWN)")
    print("3. Ver informações da tabela")
    print("0. Sair")

    escolha = input("\nOpção: ")

    if escolha == '1':
        create_hyperparameter_config_table()
    elif escolha == '2':
        rollback_migration()
    elif escolha == '3':
        show_table_info()
    elif escolha == '0':
        print("\nSaindo...")
    else:
        print("\n❌ Opção inválida!")
