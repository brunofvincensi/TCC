import yfinance as yf
import pandas as pd
from models import db
from models.ativo import HistoricoPrecos

class YFinanceProcessor:

    def process(self, asset):
        period = "max"
        print(f"\nIniciando atualização de preços MENSAIS (período: {period})...")

        print(f"Buscando histórico para {asset.ticker}...")
        try:
            """Busca o histórico mensal de preços ajustados por dividendos."""
            data = yf.download(
                asset.ticker + '.SA',
                interval="1mo",
                period=period,
                progress=False,
                auto_adjust=True
            )

            if data.empty:
                print(f"  - Nenhum dado retornado para {asset.ticker}. Pulando.")
                return

            # Calcular variação mensal antes de resetar o índice
            data['variacao_mensal'] = data['Close'].pct_change()

            # Resetar o índice para transformar as datas em coluna
            data = data.reset_index()

            new_records = 0
            for index, row in data.iterrows():
                try:
                    # Extrair data - row é uma Series, então precisamos acessar com .iloc[0] se necessário
                    date_col = row['Date']

                    # Se for Series, pega o primeiro valor
                    if isinstance(date_col, pd.Series):
                        date_col = date_col.iloc[0]

                    # Converter para date
                    month_date = pd.to_datetime(date_col).date()

                    # Verificar se já existe
                    exists = HistoricoPrecos.query.filter_by(id_ativo=asset.id, data=month_date).first()

                    if not exists:
                        # Extrair Close
                        close_val = row['Close']
                        if isinstance(close_val, pd.Series):
                            close_val = close_val.iloc[0]
                        closing_price = float(close_val) if not pd.isna(close_val) else None

                        # Extrair variacao_mensal
                        var_val = row['variacao_mensal']
                        if isinstance(var_val, pd.Series):
                            var_val = var_val.iloc[0]
                        variation = float(var_val) if not pd.isna(var_val) else None

                        new_price = HistoricoPrecos(
                            id_ativo=asset.id,
                            data=month_date,
                            preco_fechamento=closing_price,
                            variacao_mensal=variation
                        )
                        db.session.add(new_price)
                        new_records += 1

                except Exception as e:
                    print(f"  - Erro ao processar linha {index}: {e}")
                    continue

            if new_records > 0:
                db.session.commit()
                print(f"  - {new_records} novos registros adicionados.")
            else:
                print(f"  - Histórico já está atualizado.")

        except Exception as e:
            db.session.rollback()
            print(f"  - ❌ Erro ao buscar dados para {asset.ticker}: {e}")


        print("\n✅ Atualização de preços mensais concluída!")