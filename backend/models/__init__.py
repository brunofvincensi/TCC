from flask_sqlalchemy import SQLAlchemy

# Inicializa a instância do DB
db = SQLAlchemy()

# Importe todos os seus modelos aqui para que o SQLAlchemy os "conheça"
# e consiga resolver os relacionamentos entre os arquivos.
from .usuario import Usuario
from .ativo import Ativo, HistoricoPrecos
from .carteira import Carteira, CarteiraAtivo, ParametrosOtimizacao, ParametrosRestricaoAtivo