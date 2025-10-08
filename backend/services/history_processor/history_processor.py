from abc import ABC, abstractmethod  # 1. Importe ABC e abstractmethod

# 2. Crie a Classe Base Abstrata (nossa "interface")
class HistoryProcessor(ABC):
    """
    Define a interface comum para todos os processadores de histórico de ativos.
    """
    def __init__(self, app):
        # Todas as implementações receberão o 'app' no construtor.
        self.app = app

    @abstractmethod
    def process(self, ativo, full_history=False):
        """
        Método que deve ser implementado por todas as subclasses.
        Ele executa a lógica de busca e salvamento dos dados históricos.
        """
        pass