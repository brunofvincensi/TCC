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
        UniqueConstraint('num_ativos', 'nivel_risco', name='uq_num_ativos_nivel_risco'),
    )

    # Campos principais
    id = db.Column(db.Integer, primary_key=True)
    num_ativos = db.Column(db.Integer, nullable=False, index=True,
                          comment='Número de ativos para o qual esta configuração é ótima')
    nivel_risco = db.Column(db.String(20), nullable=False, default='neutro',
                           comment='Perfil de risco (conservador, moderado, arrojado, neutro)')

    # Hiperparâmetros ótimos
    population_size = db.Column(db.Integer, nullable=False,
                               comment='Tamanho ótimo da população')
    generations = db.Column(db.Integer, nullable=False,
                           comment='Número ótimo de gerações')
    crossover_eta = db.Column(db.Float, nullable=False, default=15.0,
                             comment='Parâmetro eta do crossover')
    mutation_eta = db.Column(db.Float, nullable=False, default=20.0,
                            comment='Parâmetro eta da mutação')

    # Métricas de qualidade obtidas
    hypervolume_mean = db.Column(db.Float, nullable=True,
                                comment='Hypervolume médio obtido')
    hypervolume_std = db.Column(db.Float, nullable=True,
                               comment='Desvio padrão do Hypervolume')
    spread_mean = db.Column(db.Float, nullable=True,
                           comment='Spread médio')
    spread_std = db.Column(db.Float, nullable=True,
                          comment='Desvio padrão do Spread')
    spacing_mean = db.Column(db.Float, nullable=True,
                            comment='Spacing médio')
    spacing_std = db.Column(db.Float, nullable=True,
                           comment='Desvio padrão do Spacing')
    pareto_size_mean = db.Column(db.Float, nullable=True,
                                comment='Tamanho médio da fronteira de Pareto')

    # Informações de performance
    execution_time_mean = db.Column(db.Float, nullable=True,
                                   comment='Tempo médio de execução (segundos)')
    execution_time_std = db.Column(db.Float, nullable=True,
                                  comment='Desvio padrão do tempo de execução')
    convergence_generation_mean = db.Column(db.Float, nullable=True,
                                           comment='Geração média de convergência')

    # Metadados do tuning
    n_runs = db.Column(db.Integer, nullable=True,
                      comment='Número de execuções utilizadas no tuning')
    n_configurations_tested = db.Column(db.Integer, nullable=True,
                                       comment='Número total de configurações testadas')
    tuning_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           comment='Data em que o tuning foi realizado')

    # Informações adicionais
    notes = db.Column(db.Text, nullable=True,
                     comment='Observações sobre o tuning')
    is_active = db.Column(db.Boolean, nullable=False, default=True,
                         comment='Se esta configuração está ativa para uso')

    def __repr__(self):
        return (f"<HyperparameterConfig(num_ativos={self.num_ativos}, "
                f"nivel_risco={self.nivel_risco}, "
                f"pop={self.population_size}, gen={self.generations}, "
                f"HV={self.hypervolume_mean:.4f})>")

    def to_dict(self):
        """Converte para dicionário."""
        return {
            'id': self.id,
            'num_ativos': self.num_ativos,
            'nivel_risco': self.nivel_risco,
            'population_size': self.population_size,
            'generations': self.generations,
            'crossover_eta': self.crossover_eta,
            'mutation_eta': self.mutation_eta,
            'hypervolume_mean': self.hypervolume_mean,
            'hypervolume_std': self.hypervolume_std,
            'spread_mean': self.spread_mean,
            'spread_std': self.spread_std,
            'spacing_mean': self.spacing_mean,
            'spacing_std': self.spacing_std,
            'pareto_size_mean': self.pareto_size_mean,
            'execution_time_mean': self.execution_time_mean,
            'execution_time_std': self.execution_time_std,
            'convergence_generation_mean': self.convergence_generation_mean,
            'n_runs': self.n_runs,
            'n_configurations_tested': self.n_configurations_tested,
            'tuning_date': self.tuning_date.isoformat() if self.tuning_date else None,
            'notes': self.notes,
            'is_active': self.is_active
        }

    @staticmethod
    def get_optimal_config(num_ativos: int, nivel_risco: str = 'neutro'):
        """
        Busca a configuração ótima para um número específico de ativos.

        Args:
            num_ativos: Número de ativos
            nivel_risco: Perfil de risco (conservador, moderado, arrojado, neutro)

        Returns:
            HyperparameterConfig ou None se não encontrado
        """
        # Busca configuração exata
        config = HyperparameterConfig.query.filter_by(
            num_ativos=num_ativos,
            nivel_risco=nivel_risco,
            is_active=True
        ).first()

        if config:
            return config

        # Se não encontrar exata, busca a mais próxima (arredondamento)
        # Tenta +/- 2 ativos
        for offset in [0, 1, -1, 2, -2]:
            config = HyperparameterConfig.query.filter_by(
                num_ativos=num_ativos + offset,
                nivel_risco=nivel_risco,
                is_active=True
            ).first()
            if config:
                return config

        # Se ainda não encontrar, busca configuração neutra
        if nivel_risco != 'neutro':
            return HyperparameterConfig.get_optimal_config(num_ativos, 'neutro')

        # Última tentativa: qualquer configuração próxima
        config = HyperparameterConfig.query.filter_by(
            is_active=True
        ).order_by(
            db.func.abs(HyperparameterConfig.num_ativos - num_ativos)
        ).first()

        return config

    @staticmethod
    def get_all_active():
        """Retorna todas as configurações ativas."""
        return HyperparameterConfig.query.filter_by(is_active=True).all()

    @staticmethod
    def deactivate_all_for_num_ativos(num_ativos: int, nivel_risco: str = None):
        """
        Desativa todas as configurações para um número de ativos.

        Útil quando um novo tuning é realizado e queremos substituir
        a configuração antiga.
        """
        query = HyperparameterConfig.query.filter_by(num_ativos=num_ativos)
        if nivel_risco:
            query = query.filter_by(nivel_risco=nivel_risco)

        configs = query.all()
        for config in configs:
            config.is_active = False

        db.session.commit()
        return len(configs)
