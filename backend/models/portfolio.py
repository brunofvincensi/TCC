from . import db

# Tabela de associação para o relacionamento N:N entre Carteira e Ativo
class PortfolioAsset(db.Model):
    __tablename__ = 'portfolio_assets'

    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), primary_key=True)
    weight = db.Column(db.Numeric(5, 4), nullable=False)  # Ex: 0.2500 (represents 25%)
    monetary_value = db.Column(db.Numeric(15, 2), nullable=True)  # Monetary value allocated in the asset

    asset = db.relationship('Asset', backref='associated_portfolios')
    portfolio = db.relationship('Portfolio', back_populates='composition')

    def to_dict(self):
        """Retorna dicionário com chaves em português para o frontend"""
        return {
            'ticker': self.asset.ticker,
            'nome_ativo': self.asset.name,  # Traduzido de asset_name
            'peso': f"{float(self.weight):.4f}",  # Traduzido de weight
            'valor_monetario': f"{float(self.monetary_value):.2f}" if self.monetary_value else None  # Traduzido de monetary_value
        }


class Portfolio(db.Model):
    __tablename__ = 'portfolios'

    id = db.Column(db.Integer, primary_key=True)
    # Relacionamentos
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', back_populates='portfolios')
    parameters = db.relationship('OptimizationParameters', back_populates='portfolio', uselist=False,
                                 cascade="all, delete-orphan")
    composition = db.relationship('PortfolioAsset', back_populates='portfolio', cascade="all, delete-orphan")

    def to_dict(self):
        """Retorna dicionário com chaves em português para o frontend"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'nome': self.name,  # Traduzido de name
            'descricao': self.description,  # Traduzido de description
            'data_criacao': self.created_at.isoformat(),  # Traduzido de created_at
            'parametros': self.parameters.to_dict() if self.parameters else None,  # Traduzido de parameters
            'composicao': [item.to_dict() for item in self.composition]  # Traduzido de composition
        }


class ParameterAssetRestriction(db.Model):
    __tablename__ = 'parameter_asset_restrictions'

    # Composite primary key with foreign keys
    parameters_id = db.Column(db.Integer, db.ForeignKey('optimization_parameters.id'), primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), primary_key=True)

    # Relationships to facilitate access
    asset = db.relationship('Asset')
    parameters = db.relationship('OptimizationParameters', back_populates='restrictions')


class OptimizationParameters(db.Model):
    __tablename__ = 'optimization_parameters'

    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False, unique=True)
    risk_profile_used = db.Column(db.String(50))
    time_horizon_used = db.Column(db.Integer)
    capital_used = db.Column(db.Numeric(15, 2))

    # Relacionamento 1:1 com Carteira
    portfolio = db.relationship('Portfolio', back_populates='parameters')

    # Relacionamento 1:N com a tabela de associação
    restrictions = db.relationship('ParameterAssetRestriction', back_populates='parameters', cascade="all, delete-orphan")

    def to_dict(self):
        """Retorna dicionário com chaves em português para o frontend"""
        return {
            'perfil_risco_usado': self.risk_profile_used,  # Traduzido de risk_profile_used
            'horizonte_tempo_usado': self.time_horizon_used,  # Traduzido de time_horizon_used
            'capital_usado': str(self.capital_used) if self.capital_used else None,  # Traduzido de capital_used
            # Returns a simple list of restricted asset IDs - traduzido de restricted_asset_ids
            'restricoes_ativos_ids': [restriction.asset_id for restriction in self.restrictions]
        }
