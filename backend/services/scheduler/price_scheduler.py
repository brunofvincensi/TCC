"""
Scheduler para atualização automática de preços de ativos.

Este módulo implementa um agendador que executa a atualização diária
de preços dos ativos. Por padrão, a atualização ocorre às 23:00 (11 PM)
de cada dia, garantindo que os dados do dia estejam disponíveis.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceUpdateScheduler:
    """
    Gerencia o agendamento de atualizações de preços dos ativos.

    O scheduler executa a atualização diária de preços às 23:00,
    utilizando APScheduler para garantir execução confiável e persistente.
    """

    def __init__(self, app, update_function):
        """
        Inicializa o scheduler.

        Args:
            app: Instância da aplicação Flask
            update_function: Função que será executada para atualizar os preços
        """
        self.app = app
        self.update_function = update_function
        self.scheduler = BackgroundScheduler(
            daemon=True,
            timezone='America/Sao_Paulo'
        )

    def _job_wrapper(self):
        """
        Wrapper que executa o job com o contexto da aplicação Flask.
        """
        logger.info("Iniciando atualização agendada de preços...")
        try:
            self.update_function(self.app)
            logger.info("Atualização agendada de preços concluída com sucesso!")
        except Exception as e:
            logger.error(f"Erro durante atualização agendada de preços: {e}")

    def start(self, hour=23, minute=0):
        """
        Inicia o scheduler com o horário configurado.
        """
        if self.scheduler.running:
            logger.warning("Scheduler já está em execução.")
            return

        # Adicionar job com trigger cron para executar diariamente
        trigger = CronTrigger(hour=hour, minute=minute, timezone='America/Sao_Paulo')

        self.scheduler.add_job(
            func=self._job_wrapper,
            trigger=trigger,
            id='daily_price_update',
            name='Atualização Diária de Preços',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(f"Scheduler iniciado! Atualização diária de preços agendada para {hour:02d}:{minute:02d}")
        logger.info(f"Próxima execução: {self.get_next_run_time()}")

    def stop(self):
        """Para o scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler parado.")
        else:
            logger.warning("Scheduler não está em execução.")

    def get_next_run_time(self):
        """
        Retorna a data/hora da próxima execução agendada.

        Returns:
            datetime ou None se não houver jobs agendados
        """
        job = self.scheduler.get_job('daily_price_update')
        if job:
            return job.next_run_time
        return None

    def run_now(self):
        """
        Executa a atualização de preços imediatamente (fora do agendamento).
        Útil para testes ou atualizações manuais.
        """
        logger.info("Executando atualização de preços manualmente...")
        self._job_wrapper()

    def get_status(self):
        """
        Retorna o status atual do scheduler.
        """
        job = self.scheduler.get_job('daily_price_update')

        return {
            'running': self.scheduler.running,
            'next_run_time': self.get_next_run_time(),
            'job_exists': job is not None
        }
