import yfinance as yf
import pandas as pd
from models import db
from models.ativo import HistoricoPrecos

class YFinanceProcessor:

    def process(self, ativo, app, full_history=False):
        periodo = "max"  # if full_history else "1y"
        print(f"\nIniciando atualização de preços MENSAIS (período: {periodo})...")

        print(f"Buscando histórico para {ativo.ticker}...")
        try:
            """Busca o histórico MENSAL de preços ajustados por dividendos."""
            dados = yf.download(
                ativo.ticker + '.SA',
                interval="1mo",
                period=periodo,
                progress=False,
                auto_adjust=True
            )

            if dados.empty:
                print(f"  - Nenhum dado retornado para {ativo.ticker}. Pulando.")
                return

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