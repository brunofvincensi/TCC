from flask_sqlalchemy import SQLAlchemy

# Inicializa a instância do DB
db = SQLAlchemy()

# Importe todos os seus modelos aqui para que o SQLAlchemy os "conheça"
# e consiga resolver os relacionamentos entre os arquivos.
from .usuario import User
from .ativo import Asset, PriceHistory, AssetType
from .carteira import Portfolio, PortfolioAsset, OptimizationParameters, ParameterAssetRestriction
from .hyperparameter_config import HyperparameterConfig
