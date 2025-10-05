import csv
import yfinance as yf
import pandas as pd
from models import db
from models.ativo import Ativo, HistoricoPrecos

# A função de registro não é mais necessária
# def register_commands(app):
#     ...

def seed_assets(app):
    """Lê o arquivo ativos.csv e popula a tabela de Ativos."""
    with app.app_context():
        try:
            print("Iniciando a população da tabela de ativos a partir de 'ativos.csv'...")
            # ... (o resto da lógica da função seed_assets continua exatamente a mesma)
            with open('backend/ativos.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ativo = Ativo.query.filter_by(ticker=row['ticker']).first()
                    if not ativo:
                        novo_ativo = Ativo(
                            ticker=row['ticker'],
                            nome=row['nome'],
                            tipo=row['tipo'],
                            setor=row.get('setor')
                        )
                        db.session.add(novo_ativo)
                        print(f"-> Ativo {row['ticker']} adicionado.")

                db.session.commit()
                print("\n✅ Tabela de ativos populada com sucesso!")
        except FileNotFoundError:
            print("\n❌ ERRO: O arquivo 'backend/ativos.csv' não foi encontrado.")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Ocorreu um erro inesperado: {e}")


def update_prices(app, full_history=False):
    """Busca o histórico MENSAL de preços ajustados por dividendos."""
    with app.app_context():
        ativos = Ativo.query.all()
        if not ativos:
            print("Nenhum ativo encontrado no banco. Execute 'setup' primeiro.")
            return

        periodo = "max" if full_history else "1y"
        print(f"\nIniciando atualização de preços MENSAIS (período: {periodo})...")

        for ativo in ativos:
            print(f"Buscando histórico para {ativo.ticker}...")
            try:
                dados = yf.download(
                    ativo.ticker + '.SA',
                    interval="1mo",
                    period=periodo,
                    progress=False,
                    auto_adjust=True
                )

                if dados.empty:
                    print(f"  - Nenhum dado retornado para {ativo.ticker}. Pulando.")
                    continue

                # Calcular variação mensal ANTES de resetar o índice
                dados['variacao_mensal'] = dados['Close'].pct_change()

                # Resetar o índice para transformar as datas em coluna
                dados = dados.reset_index()

                novos_registros = 0
                for index, row in dados.iterrows():
                    try:
                        # Extrair data - row é uma Series, então precisamos acessar com .iloc[0] se necessário
                        data_col = row['Date']

                        # Se for Series, pega o primeiro valor
                        if isinstance(data_col, pd.Series):
                            data_col = data_col.iloc[0]

                        # Converter para date
                        data_mes = pd.to_datetime(data_col).date()

                        # Verificar se já existe
                        existe = HistoricoPrecos.query.filter_by(id_ativo=ativo.id, data=data_mes).first()

                        if not existe:
                            # Extrair Close
                            close_val = row['Close']
                            if isinstance(close_val, pd.Series):
                                close_val = close_val.iloc[0]
                            preco_fechamento = float(close_val) if not pd.isna(close_val) else None

                            # Extrair variacao_mensal
                            var_val = row['variacao_mensal']
                            if isinstance(var_val, pd.Series):
                                var_val = var_val.iloc[0]
                            variacao = float(var_val) if not pd.isna(var_val) else None

                            novo_preco = HistoricoPrecos(
                                id_ativo=ativo.id,
                                data=data_mes,
                                preco_fechamento=preco_fechamento,
                                variacao_mensal=variacao
                            )
                            db.session.add(novo_preco)
                            novos_registros += 1

                    except Exception as e:
                        print(f"  - Erro ao processar linha {index}: {e}")
                        continue

                if novos_registros > 0:
                    db.session.commit()
                    print(f"  - {novos_registros} novos registros adicionados.")
                else:
                    print(f"  - Histórico já está atualizado.")

            except Exception as e:
                db.session.rollback()
                print(f"  - ❌ Erro ao buscar dados para {ativo.ticker}: {e}")

        print("\n✅ Atualização de preços mensais concluída!")