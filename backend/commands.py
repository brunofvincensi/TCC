import csv
from models import db
from models.asset import Asset, AssetType
from services.history_processor.yfinance_processor import YFinanceProcessor


def seed_assets(app):
    """Lê o arquivo ativos.csv e popula a tabela de Ativos."""
    with app.app_context():
        try:
            print("Iniciando a população da tabela de ativos a partir de 'ativos.csv'...")
            with open('ativos.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    asset = Asset.query.filter_by(ticker=row['ticker']).first()
                    if not asset:
                        new_asset = Asset(
                            ticker=row['ticker'],
                            name=row['nome'],
                            type=row['tipo'],
                            sector=row.get('setor')
                        )
                        db.session.add(new_asset)
                        print(f"-> Ativo {row['ticker']} adicionado.")

                db.session.commit()
                print("\nTabela de ativos populada com sucesso!")
        except FileNotFoundError:
            print("\nERRO: O arquivo 'ativos.csv' não foi encontrado.")
        except Exception as e:
            db.session.rollback()
            print(f"\nOcorreu um erro inesperado: {e}")

def update_prices(app):
    """
    Busca o histórico MENSAL de preços, escolhendo o processador correto para cada tipo de ativo.
    """
    with app.app_context():
        # Instancia as classes de processadores dos preços históricos
        yfinance_processor = YFinanceProcessor()

        assets = Asset.query.all()
        if not assets:
            print("Nenhum ativo encontrado no banco.")
            return

        print(f"\nIniciando atualização de preços mensais...")

        for asset in assets:
            if asset.type == AssetType.STOCK:
                yfinance_processor.process(asset)

        print("\nAtualização de preços mensais concluída!")

def update_daily_prices(app):
    """
    Atualiza os preços dos ativos com os dados mais recentes do dia.
    Esta função deve ser executada diariamente para manter os dados atualizados.
    """
    with app.app_context():
        yfinance_processor = YFinanceProcessor()

        assets = Asset.query.all()
        if not assets:
            print("Nenhum ativo encontrado no banco.")
            return

        print(f"\nIniciando atualização diária de preços...")

        updated_count = 0
        for asset in assets:
            if asset.type == AssetType.STOCK:
                try:
                    yfinance_processor.process_daily(asset)
                    updated_count += 1
                except Exception as e:
                    print(f"Erro ao atualizar {asset.ticker}: {e}")
                    continue

        print(f"\nAtualização diária concluída! {updated_count} ativos processados.")
