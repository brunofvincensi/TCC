import os

import pandas as pd
import requests
from models import db
from models.ativo import HistoricoPrecos

class AnbimaProcessor:
    """
    Processador para buscar dados de Índices de Mercado da ANBIMA via API oficial.
    """

    def __init__(self):
        self.base_url = "https://api.anbima.com.br/feed/precos-indices/v1"
        self.client_id = os.getenv("ANBIMA_CLIENT_ID")
        self.client_secret = os.getenv("ANBIMA_CLIENT_SECRET")
        self.access_token = None

    def _get_access_token(self):
        """Obtém o token de acesso da API ANBIMA usando OAuth2."""
        if not self.client_id or not self.client_secret:
            print("  - ❌ ERRO: Credenciais ANBIMA_CLIENT_ID e ANBIMA_CLIENT_SECRET não encontradas no .env")
            return False

        url = "https://api.anbima.com.br/oauth/access-token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()  # Lança um erro para respostas 4xx ou 5xx
            self.access_token = response.json()['access_token']
            print("  - Token de acesso ANBIMA obtido com sucesso.")
            return True
        except requests.RequestException as e:
            print(f"  - ❌ ERRO ao obter token de acesso ANBIMA: {e}")
            return False

    def process(self, ativo, app, full_history=False):
        """Busca o histórico de um índice da ANBIMA."""
        print(f"Buscando histórico ANBIMA API para o índice {ativo.ticker}...")

        # Obtém o token de acesso. Se já tiver um, não busca de novo na mesma execução.
        if not self.access_token:
            if not self._get_access_token():
                return  # Para a execução se não conseguir o token

        # Monta a URL para o endpoint de índices
        # A API retorna o histórico completo, então 'full_history' não é usado no request
        url = f"{self.base_url}/indices/{ativo.ticker}"
        headers = {
            'client_id': self.client_id,
            'access_token': self.access_token
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            dados_api = response.json()

            if not dados_api:
                print(f"  - Nenhum dado retornado para o índice {ativo.ticker}.")
                return

            # Processa os dados recebidos
            with self.app.app_context():
                # Converte a lista de JSON para um DataFrame do Pandas
                df = pd.DataFrame(dados_api)
                df['data'] = pd.to_datetime(df['data_referencia'], format='%d/%m/%Y')
                df = df.sort_values(by='data').set_index('data')

                # Converte o número do índice para float
                df['valor_indice'] = df['numero_indice'].str.replace('.', '').str.replace(',', '.').astype(float)

                # Resample para pegar o último valor de cada mês e calcular a variação
                df_mensal = df['valor_indice'].resample('M').last()
                df_mensal = df_mensal.to_frame()
                df_mensal['variacao_mensal'] = df_mensal['valor_indice'].pct_change()
                df_mensal.reset_index(inplace=True)

                novos_registros = 0
                for _, row in df_mensal.iterrows():
                    data_mes = row['data'].date()
                    existe = HistoricoPrecos.query.filter_by(id_ativo=ativo.id, data=data_mes).first()

                    if not existe and pd.notna(row['valor_indice']):
                        novo_preco = HistoricoPrecos(
                            id_ativo=ativo.id,
                            data=data_mes,
                            preco_fechamento=row['valor_indice'],
                            variacao_mensal=row['variacao_mensal'] if pd.notna(row['variacao_mensal']) else None
                        )
                        db.session.add(novo_preco)
                        novos_registros += 1

                if novos_registros > 0:
                    db.session.commit()
                    print(f"  - {novos_registros} novos registros mensais adicionados para {ativo.ticker}.")
                else:
                    print(f"  - Histórico de {ativo.ticker} já está atualizado.")

        except requests.RequestException as e:
            print(f"  - ❌ ERRO ao buscar dados do índice {ativo.ticker}: {e}")
            db.session.rollback()
