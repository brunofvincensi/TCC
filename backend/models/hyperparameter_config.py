"""
Model para armazenar configurações ótimas de hiperparâmetros do AGMO.

Este modelo persiste os resultados do tuning de hiperparâmetros,
permitindo que o sistema use automaticamente a melhor configuração
baseada na quantidade de ativos sendo otimizados.
"""

from models import db
from datetime import datetime
from sqlalchemy import UniqueConstraint


class HyperparameterConfig(db.Model):
    """
    Armazena configurações ótimas de hiperparâmetros por quantidade de ativos.

    Cada registro representa a melhor combinação de população × gerações
    para um determinado número de ativos, determinada através de grid search.
    """

    __tablename__ = 'hyperparameter_configs'

    # Constraint: apenas uma configuração ótima por quantidade de ativos e perfil
    __table_args__ = (
        UniqueConstraint('num_assets', 'risk_level', name='uq_num_assets_risk_level'),
    )

    # Campos principais
    id = db.Column(db.Integer, primary_key=True)
    num_assets = db.Column(db.Integer, nullable=False, index=True,
                          comment='Number of assets for which this configuration is optimal')
    risk_level = db.Column(db.String(20), nullable=False, default='neutral',
                           comment='Risk profile (conservative, moderate, aggressive, neutral)')

    # Hiperparâmetros ótimos
    population_size = db.Column(db.Integer, nullable=False,
                               comment='Optimal population size')
    generations = db.Column(db.Integer, nullable=False,
                           comment='Optimal number of generations')
    crossover_eta = db.Column(db.Float, nullable=False, default=15.0,
                             comment='Crossover eta parameter')
    mutation_eta = db.Column(db.Float, nullable=False, default=20.0,
                            comment='Mutation eta parameter')

    # Métricas principais (apenas as 3 mais importantes!)
    hypervolume_mean = db.Column(db.Float, nullable=True,
                                comment='Average Hypervolume - Quality metric')
    execution_time_mean = db.Column(db.Float, nullable=True,
                                   comment='Average execution time in seconds')
    convergence_generation_mean = db.Column(db.Float, nullable=True,
                                           comment='Average generation where convergence occurred')

    # Metadados do tuning
    tuning_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           comment='Date when tuning was performed')

    # Informações adicionais
    notes = db.Column(db.Text, nullable=True,
                     comment='Observations about the tuning')
    is_active = db.Column(db.Boolean, nullable=False, default=True,
                         comment='Whether this configuration is active for use')

    def __repr__(self):
        hv_str = f"{self.hypervolume_mean:.6e}" if self.hypervolume_mean else "N/A"
        return (f"<HyperparameterConfig(assets={self.num_assets}, "
                f"pop={self.population_size}, gen={self.generations}, "
                f"HV={hv_str})>")

    def to_dict(self):
        """Converte para dicionário (apenas campos essenciais)."""
        return {
            'id': self.id,
            'num_assets': self.num_assets,
            'risk_level': self.risk_level,
            'population_size': self.population_size,
            'generations': self.generations,
            'crossover_eta': self.crossover_eta,
            'mutation_eta': self.mutation_eta,
            'hypervolume_mean': self.hypervolume_mean,
            'execution_time_mean': self.execution_time_mean,
            'convergence_generation_mean': self.convergence_generation_mean,
            'tuning_date': self.tuning_date.isoformat() if self.tuning_date else None,
            'notes': self.notes,
            'is_active': self.is_active
        }

    def get_efficiency_score(self) -> float:
        """
        Calcula o score de eficiência (trade-off qualidade × velocidade).

        Returns:
            Score de eficiência (hypervolume / tempo)
        """
        if self.execution_time_mean and self.execution_time_mean > 0:
            return self.hypervolume_mean / self.execution_time_mean
        return 0.0

    @staticmethod
    def get_optimal_config(num_assets: int, risk_level: str = 'neutral'):
        """
        Busca a configuração ótima para um número específico de ativos.

        Prioriza configurações com melhor trade-off qualidade × velocidade.

        Args:
            num_assets: Número de ativos
            risk_level: Perfil de risco (conservador, moderado, arrojado, neutro)

        Returns:
            HyperparameterConfig ou None se não encontrado
        """
        # Busca configuração exata
        config = HyperparameterConfig.query.filter_by(
            num_assets=num_assets,
            risk_level=risk_level,
            is_active=True
        ).first()

        if config:
            return config

        # Se não encontrar exata, busca a mais próxima (arredondamento)
        # Tenta +/- 2 ativos
        for offset in [0, 1, -1, 2, -2]:
            config = HyperparameterConfig.query.filter_by(
                num_assets=num_assets + offset,
                risk_level=risk_level,
                is_active=True
            ).first()
            if config:
                return config

        # Se ainda não encontrar, busca configuração neutra
        if risk_level != 'neutral':
            return HyperparameterConfig.get_optimal_config(num_assets, 'neutral')

        # Última tentativa: qualquer configuração próxima
        config = HyperparameterConfig.query.filter_by(
            is_active=True
        ).order_by(
            db.func.abs(HyperparameterConfig.num_assets - num_assets)
        ).first()

        return config

    @staticmethod
    def get_all_active():
        """Retorna todas as configurações ativas."""
        return HyperparameterConfig.query.filter_by(is_active=True).all()

    @staticmethod
    def deactivate_all_for_num_assets(num_assets: int, risk_level: str = None):
        """
        Desativa todas as configurações para um número de ativos.

        Útil quando um novo tuning é realizado e queremos substituir
        a configuração antiga.
        """
        query = HyperparameterConfig.query.filter_by(num_assets=num_assets)
        if risk_level:
            query = query.filter_by(risk_level=risk_level)

        configs = query.all()
        for config in configs:
            config.is_active = False

        db.session.commit()
        return len(configs)
