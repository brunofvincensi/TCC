import click
import csv
import yfinance as yf
from flask.cli import with_appcontext
from models import db
from models.ativo import Ativo, HistoricoPrecos


def register_commands(app):
    """Função para registrar os comandos na aplicação Flask."""
    app.cli.add_command(seed_assets)
    app.cli.add_command(update_prices)


@click.command(name='seed-assets')
@with_appcontext
def seed_assets():
    """
    Lê o arquivo ativos.csv na raiz do projeto e popula a tabela de Ativos.
    Este comando é idempotente: ele não duplicará ativos que já existem.
    """
    try:
        print("Iniciando a população da tabela de ativos a partir de 'ativos.csv'...")
        with open('ativos.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Verifica se o ativo já existe no banco de dados para não duplicar
                ativo = Ativo.query.filter_by(ticker=row['ticker']).first()
                if not ativo:
                    novo_ativo = Ativo(
                        ticker=row['ticker'],
                        nome=row['nome'],
                        tipo=row['tipo'],
                        setor=row.get('setor')  # .get() é mais seguro se a coluna for opcional
                    )
                    db.session.add(novo_ativo)
                    print(f"-> Ativo {row['ticker']} adicionado.")

            db.session.commit()
            print("\n✅ Tabela de ativos populada com sucesso!")

    except FileNotFoundError:
        print("\n❌ ERRO: O arquivo 'ativos.csv' não foi encontrado na raiz do projeto.")
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Ocorreu um erro inesperado: {e}")


@click.command(name='update-prices')
@click.option('--full-history', is_flag=True,
              help="Busca todo o histórico de preços. Por padrão, busca apenas os últimos 5 dias.")
@with_appcontext
def update_prices(full_history):
    """
    Busca e atualiza o histórico de preços para todos os ativos cadastrados no banco.
    Este comando também é idempotente: não duplicará preços para datas que já existem.
    """
    ativos = Ativo.query.all()
    if not ativos:
        print("Nenhum ativo encontrado no banco de dados. Execute 'flask seed-assets' primeiro.")
        return

    periodo = "max" if full_history else "5d"
    print(f"\nIniciando atualização de preços (período: {periodo}) para {len(ativos)} ativos...")

    for ativo in ativos:
        print(f"Buscando histórico para {ativo.ticker}...")
        try:
            # Baixa os dados do Yahoo Finance
            dados = yf.download(ativo.ticker, period=periodo, progress=False, auto_adjust=True)

            if dados.empty:
                print(f"  - Nenhum dado retornado para {ativo.ticker}. Pulando.")
                continue

            # Itera sobre os dados e insere no banco
            novos_registros = 0
            for index, row in dados.iterrows():
                data = index.date()
                preco_fechamento = row['Close']

                # Verifica se o registro já existe para não duplicar
                existe = HistoricoPrecos.query.filter_by(id_ativo=ativo.id, data=data).first()
                if not existe:
                    novo_preco = HistoricoPrecos(
                        id_ativo=ativo.id,
                        data=data,
                        preco_fechamento=preco_fechamento
                    )
                    db.session.add(novo_preco)
                    novos_registros += 1

            if novos_registros > 0:
                db.session.commit()
                print(f"  - {novos_registros} novos registros de preço adicionados para {ativo.ticker}.")
            else:
                print(f"  - Histórico de {ativo.ticker} já está atualizado.")

        except Exception as e:
            db.session.rollback()
            print(f"  - ❌ Erro ao buscar dados para {ativo.ticker}: {e}")

    print("\n✅ Atualização de preços concluída!")