import csv
from models import db
from models.ativo import Ativo, TipoAtivo
from services.history_processor.yfinance_processor import YFinanceProcessor


def seed_assets(app):
    """Lê o arquivo ativos.csv e popula a tabela de Ativos."""
    with app.app_context():
        try:
            print("Iniciando a população da tabela de ativos a partir de 'ativos.csv'...")
            with open('ativos.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    asset = Ativo.query.filter_by(ticker=row['ticker']).first()
                    if not asset:
                        new_asset = Ativo(
                            ticker=row['ticker'],
                            nome=row['nome'],
                            tipo=row['tipo'],
                            setor=row.get('setor')
                        )
                        db.session.add(new_asset)
                        print(f"-> Ativo {row['ticker']} adicionado.")

                db.session.commit()
                print("\n✅ Tabela de ativos populada com sucesso!")
        except FileNotFoundError:
            print("\n❌ ERRO: O arquivo 'ativos.csv' não foi encontrado.")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Ocorreu um erro inesperado: {e}")

def update_prices(app):
    """
    Busca o histórico MENSAL de preços, escolhendo o processador correto para cada tipo de ativo.
    """
    with app.app_context():
        # Instancia as classes de processadores dos preços históricos
        yfinance_processor = YFinanceProcessor()

        assets = Ativo.query.all()
        if not assets:
            print("Nenhum ativo encontrado no banco.")
            return

        print(f"\nIniciando atualização de preços mensais...")

        for asset in assets:
            if asset.tipo == TipoAtivo.ACAO:
                yfinance_processor.process(asset)

        print("\n✅ Atualização de preços mensais concluída!")