from . import db

# Tabela de associação para o relacionamento N:N entre Carteira e Ativo
class CarteiraAtivo(db.Model):
    __tablename__ = 'carteira_ativos'

    id_carteira = db.Column(db.Integer, db.ForeignKey('carteiras.id'), primary_key=True)
    id_ativo = db.Column(db.Integer, db.ForeignKey('ativos.id'), primary_key=True)
    peso = db.Column(db.Numeric(5, 4), nullable=False)  # Ex: 0.2500 (representa 25%)

    ativo = db.relationship('Ativo', backref='carteiras_associadas')
    carteira = db.relationship('Carteira', back_populates='composicao')

    def to_dict(self):
        return {
            'ticker': self.ativo.ticker,
            'nome_ativo': self.ativo.nome,
            'peso': f"{float(self.peso):.4f}"
        }


class Carteira(db.Model):
    __tablename__ = 'carteiras'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    data_criacao = db.Column(db.DateTime, server_default=db.func.now())

    # Relacionamentos
    usuario = db.relationship('Usuario', back_populates='carteiras')
    parametros = db.relationship('ParametrosOtimizacao', back_populates='carteira', uselist=False,
                                 cascade="all, delete-orphan")
    composicao = db.relationship('CarteiraAtivo', back_populates='carteira', cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'id_usuario': self.id_usuario,
            'nome': self.nome,
            'descricao': self.descricao,
            'data_criacao': self.data_criacao.isoformat(),
            'parametros': self.parametros.to_dict() if self.parametros else None,
            'composicao': [item.to_dict() for item in self.composicao]
        }


class ParametrosRestricaoAtivo(db.Model):
    __tablename__ = 'parametros_restricoes_ativos'

    # Chave primária composta com chaves estrangeiras
    id_parametros = db.Column(db.Integer, db.ForeignKey('parametros_otimizacao.id'), primary_key=True)
    id_ativo = db.Column(db.Integer, db.ForeignKey('ativos.id'), primary_key=True)

    # Relacionamentos para facilitar o acesso
    ativo = db.relationship('Ativo')
    parametros = db.relationship('ParametrosOtimizacao', back_populates='restricoes')


class ParametrosOtimizacao(db.Model):
    __tablename__ = 'parametros_otimizacao'

    id = db.Column(db.Integer, primary_key=True)
    id_carteira = db.Column(db.Integer, db.ForeignKey('carteiras.id'), nullable=False, unique=True)
    perfil_risco_usado = db.Column(db.String(50))
    horizonte_tempo_usado = db.Column(db.Integer)
    capital_usado = db.Column(db.Numeric(15, 2))
    objetivos_usados = db.Column(db.Text)

    # Relacionamento 1:1 com Carteira
    carteira = db.relationship('Carteira', back_populates='parametros')

    # Relacionamento 1:N com a tabela de associação
    restricoes = db.relationship('ParametrosRestricaoAtivo', back_populates='parametros', cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'perfil_risco_usado': self.perfil_risco_usado,
            'horizonte_tempo_usado': self.horizonte_tempo_usado,
            'capital_usado': str(self.capital_usado) if self.capital_usado else None,
            'objetivos_usados': self.objetivos_usados,
            # Retorna uma lista simples de IDs dos ativos restringidos
            'restricoes_ativos_ids': [restricao.id_ativo for restricao in self.restricoes]
        }