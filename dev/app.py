"""
App de Web Scraping com controle de execução
Suporta modos BUY_&_HOLD (execução única) e DAY_TRADE (execução diária às 22h)
"""

import time
import schedule
from datetime import datetime, timedelta
from enum import Enum
import argparse
import logging
import sys

# Importa módulos utilitários para consulta de ações, banco de dados e serviços de notícias
from utils import yahoo_finance
from utils.database import initialize_database
from utils.news_service import get_news_service
from web_scraping.exame import web_scrapping as exame_web_scrapping
from web_scraping.infomoney import web_scrapping as infomoney_web_scrapping

# Ticker que será utilizado para coleta de informações
TICKER = "VALE3"  # Exemplos: BBAS3, PETR4, VALE3, ITUB4, FIQE3, ITSA4, EGIE3, SAPR4

# Configuração de logging para registrar eventos no terminal e em arquivo
logging.basicConfig(
    level=logging.INFO,  # Nível mínimo de log
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato do log
    handlers=[
        logging.FileHandler('web_scraping.log'),  # Salva em arquivo
        logging.StreamHandler(sys.stdout)         # Mostra no console
    ]
)

# Definição dos modos de operação disponíveis
class TradingMode(Enum):
    BUY_AND_HOLD = "BUY_&_HOLD"  # Executa scraping apenas uma vez
    DAY_TRADE = "DAY_TRADE"      # Executa scraping diariamente às 22h

class WebScrapingApp:
    def __init__(self, mode: TradingMode):
        """Inicializa a aplicação de scraping"""
        self.mode = mode
        self.running = False
        self.news_service = get_news_service()

    def web_scrapping_exame(self, trading_mode, ticker_id, company_name):
        """Executa o scraping do site Exame"""
        try:
            logging.info("Executando web scraping - Exame")
            # Chama função do módulo exame.py para coletar dados
            success = exame_web_scrapping(trading_mode, TICKER, ticker_id, company_name, self.news_service)

            if success:
                print("✅ Web scraping Exame executado com sucesso")
                logging.info("Web scraping Exame concluído")
                return True
            else:
                print("❌ Web scraping Exame falhou")
                logging.error("Web scraping Exame falhou")
                return False
        except Exception as e:
            logging.error(f"Erro no web scraping Exame: {e}")
            return False

    def web_scrapping_info_money(self, trading_mode, ticker_id, company_name):
        """Executa o scraping do site InfoMoney (simulado por enquanto)"""
        try:
            logging.info("Executando web scraping - InfoMoney")
            # Chama função do módulo exame.py para coletar dados
            success = infomoney_web_scrapping(trading_mode, TICKER, ticker_id, company_name, self.news_service)
            if success:
                print("✅ Web scraping InfoMoney executado com sucesso")
                logging.info("Web scraping InfoMoney concluído")
                return True
            else:
                print("❌ Web scraping InfoMoney falhou")
                logging.error("Web scraping InfoMoney falhou")
                return False
        except Exception as e:
            logging.error(f"Erro no web scraping InfoMoney: {e}")
            return False

    def execute_scraping(self, trading_mode, ticker_id, company_name):
        """Executa todos os scrapers (Exame e InfoMoney)"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚀 Iniciando execução - {timestamp}")
        logging.info(f"Iniciando execução do scraping - Modo: {self.mode.value}")

        # Executa cada scraping individual
        success_exame = self.web_scrapping_exame(trading_mode, ticker_id, company_name)
        success_info_money = self.web_scrapping_info_money(trading_mode, ticker_id, company_name)

        # Verifica resultado final
        if success_exame and success_info_money:
            print("✅ Todas as execuções concluídas com sucesso!")
            logging.info("Execução completa bem-sucedida")
        else:
            print("❌ Algumas execuções falharam. Verifique os logs.")
            logging.warning("Execução completa com falhas")

    def run_buy_and_hold(self, trading_mode, ticker_id, company_name):
        """Executa scraping apenas uma vez (modo BUY & HOLD)"""
        print(f"📊 Modo BUY & HOLD selecionado")
        print("Executando uma única vez...")
        self.execute_scraping(trading_mode, ticker_id, company_name)
        print("\n🏁 Execução finalizada. Aplicação encerrada.")

    def run_day_trade(self, trading_mode, ticker_id, company_name):
        """Executa scraping todos os dias às 22h (modo DAY TRADE)"""
        print(f"📈 Modo DAY TRADE selecionado")
        print("A aplicação ficará rodando infinitamente...")
        print("Execução programada para todos os dias às 22:00")

        # Executa imediatamente na primeira execução
        print("\n🔄 Executando pela primeira vez...")
        self.execute_scraping(trading_mode, ticker_id, company_name)

        # Agenda execução diária às 22:00
        schedule.every().day.at("22:00").do(self.execute_scraping)

        self.running = True

        # Loop infinito para manter aplicação ativa
        print(f"\n⏰ Próxima execução agendada para hoje às 22:00")
        print("Pressione Ctrl+C para interromper a aplicação")

        try:
            while self.running:
                schedule.run_pending()  # Verifica se há execução pendente
                time.sleep(60)          # Checa a cada 1 minuto
        except KeyboardInterrupt:
            # Permite encerrar manualmente com Ctrl+C
            print("\n🛑 Aplicação interrompida pelo usuário")
            self.stop()

    def stop(self):
        """Interrompe execução contínua"""
        self.running = False
        logging.info("Aplicação interrompida")

    def get_next_execution_time(self):
        """Retorna horário da próxima execução às 22h"""
        now = datetime.now()
        today_22 = now.replace(hour=22, minute=0, second=0, microsecond=0)

        # Se já passou das 22h, agenda para o dia seguinte
        if now < today_22:
            return today_22
        else:
            return today_22 + timedelta(days=1)

def main():
    # Configuração de argumentos de linha de comando
    parser = argparse.ArgumentParser(description='App de Web Scraping')
    parser.add_argument(
        'mode',
        choices=['BUY_&_HOLD', 'DAY_TRADE'],
        help='Modo de operação: BUY_&_HOLD (execução única) ou DAY_TRADE (execução diária)'
    )

    args = parser.parse_args()

    # Inicializa conexão com banco de dados
    print("🔧 Initializing database connection...")
    if not initialize_database():
        print("❌ Failed to initialize database. Please check your MySQL connection.")
        logging.error("Database initialization failed")
        return
    print("✅ Database initialized successfully")

    # Converte string recebida para enum
    mode = TradingMode(args.mode)

    # Recupera ID e nome da empresa pelo ticker
    ticker_id, company_name = yahoo_finance.get_ativo(TICKER, get_news_service())

    # Cria instância da aplicação de scraping
    app = WebScrapingApp(mode)

    # Cabeçalho visual
    print("=" * 60)
    print("WEB SCRAPING")
    print("=" * 60)

    # Executa conforme modo escolhido
    if mode == TradingMode.BUY_AND_HOLD:
        app.run_buy_and_hold(TradingMode.BUY_AND_HOLD, ticker_id, company_name)
    elif mode == TradingMode.DAY_TRADE:
        app.run_day_trade(TradingMode.DAY_TRADE, ticker_id, company_name)

# Ponto de entrada da aplicação
if __name__ == "__main__":
    main()
