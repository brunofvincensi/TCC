
import yfinance as yf
import pandas as pd
from calendar import monthrange
from models import db
from models.asset import PriceHistory


class YFinanceProcessor:
    """
    Processador de dados históricos de preços usando Yahoo Finance.

    Suporta tanto carga inicial de histórico completo quanto atualização
    incremental diária de preços.
    """

    def _download_data(self, ticker, interval, period=None, start=None, end=None):
        """
        Baixa dados do Yahoo Finance com parâmetros configuráveis.
        """
        try:
            params = {
                'interval': interval,
                'progress': False,
                'auto_adjust': True
            }

            if period:
                params['period'] = period
            else:
                if start:
                    params['start'] = start
                if end:
                    params['end'] = end

            return yf.download(ticker + '.SA', **params)
        except Exception as e:
            print(f"  - Erro ao baixar dados: {e}")
            return pd.DataFrame()

    def _extract_value(self, row, column):
        """
        Extrai valor de uma célula do DataFrame de forma segura.
        Trata casos onde o valor pode ser uma Series ou valor escalar.
        """
        value = row[column]

        # Se for Series, pega o primeiro valor
        if isinstance(value, pd.Series):
            value = value.iloc[0]

        # Converte para float se não for NaN
        if pd.isna(value):
            return None

        return float(value)

    def _get_month_end_date(self, date):
        """
        Normaliza uma data para o último dia do mês.
        """
        _, last_day = monthrange(date.year, date.month)
        return date.replace(day=last_day)

    def _calculate_Variation(self, ticker, target_date):
        """
        Calcula a variação percentual mensal até uma data específica.

        Busca dados do primeiro dia do mês até a data alvo e calcula
        a variação percentual entre primeiro e último preço.
        """
        month_start = target_date.replace(day=1)
        month_data = self._download_data(
            ticker,
            interval="1d",
            start=month_start,
            end=target_date
        )

        if month_data.empty or len(month_data) < 2:
            return None

        first_price = month_data['Close'].iloc[0]
        last_price = month_data['Close'].iloc[-1]

        if pd.isna(first_price) or pd.isna(last_price) or first_price == 0:
            return None

        return float((last_price - first_price) / first_price)

    def _upsert_price_record(self, asset, date, price, variation):
        """
        Insere ou atualiza um registro de preço no banco de dados.
        """
        existing = PriceHistory.query.filter_by(
            asset_id=asset.id,
            date=date
        ).first()

        if existing:
            existing.closing_price = price
            if variation is not None:
                existing.Variation = variation
            db.session.commit()
            return 'updated'

        # Criar novo registro
        new_price = PriceHistory(
            asset_id=asset.id,
            date=date,
            closing_price=price,
            Variation=variation
        )
        db.session.add(new_price)
        return 'inserted'

    def process(self, asset):
        """
        Carrega histórico completo mensal de preços do ativo.

        Usado para carga inicial ou recarga completa do histórico.
        Baixa dados mensais desde o início e popula a tabela historico_precos.
        """
        period = "max"
        print(f"\nBuscando histórico para {asset.ticker}...")

        try:
            # Download de dados mensais históricos
            data = self._download_data(asset.ticker, interval="1mo", period=period)

            if data.empty:
                print(f"  - Nenhum dado retornado para {asset.ticker}. Pulando.")
                return

            # Calcular variação mensal
            data['Variation'] = data['Close'].pct_change()

            # Resetar índice para transformar datas em coluna
            data = data.reset_index()

            new_records = 0
            for index, row in data.iterrows():
                try:
                    # Extrair data
                    date_col = row['Date']
                    if isinstance(date_col, pd.Series):
                        date_col = date_col.iloc[0]
                    month_date = pd.to_datetime(date_col).date()

                    # Extrair valores
                    closing_price = self._extract_value(row, 'Close')
                    variation = self._extract_value(row, 'Variation')

                    # Inserir apenas novos registros (não atualiza existentes)
                    result = self._upsert_price_record(
                        asset, month_date, closing_price, variation
                    )

                    if result == 'inserted':
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
            print(f"  - Erro ao buscar dados para {asset.ticker}: {e}")

    def process_daily(self, asset):
        """
        Atualiza o histórico com os dados mais recentes do dia.

        Usado para atualização incremental diária. Busca o último preço
        disponível, calcula a variação mensal atualizada e atualiza o
        registro do mês atual (ou cria se for mês novo).
        """
        print(f"\nAtualizando preços diários para {asset.ticker}...")

        try:
            # Busca dados dos últimos 10 dias para garantir dias úteis
            data = self._download_data(asset.ticker, interval="1d", period="10d")

            if data.empty:
                print(f"  - Nenhum dado retornado para {asset.ticker}. Pulando.")
                return

            # Resetar índice
            data = data.reset_index()

            if len(data) == 0:
                print(f"  - Nenhum dado disponível para {asset.ticker}.")
                return

            # Pegar último dia útil
            last_row = data.tail(1).reset_index(drop=True).iloc[0]

            # Extrair data
            date_col = last_row['Date']
            if isinstance(date_col, pd.Series):
                date_col = date_col.iloc[0]
            last_date = pd.to_datetime(date_col).date()

            # Extrair preço de fechamento
            closing_price = self._extract_value(last_row, 'Close')

            if closing_price is None:
                print(f"  - Preço de fechamento inválido para {asset.ticker}. Pulando.")
                return

            # Calcular variação mensal
            variation = self._calculate_Variation(asset.ticker, last_date)

            # Normalizar para último dia do mês
            month_end_date = self._get_month_end_date(last_date)

            # Atualizar ou inserir registro
            result = self._upsert_price_record(
                asset, month_end_date, closing_price, variation,
            )

            if result == 'updated':
                print(f"  - Registro atualizado para {last_date} (mês {month_end_date}): R$ {closing_price:.2f}")
            elif result == 'inserted':
                db.session.commit()
                print(f"  - Novo registro criado para {last_date} (mês {month_end_date}): R$ {closing_price:.2f}")

        except Exception as e:
            db.session.rollback()
            print(f"Erro ao atualizar dados para {asset.ticker}: {e}")
