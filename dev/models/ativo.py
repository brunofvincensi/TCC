from models import db


class Ativo(db.Model):
    __tablename__ = 'ativos'

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # Ex: 'Ação', 'FII', 'Renda Fixa'
    setor = db.Column(db.String(100))
    moeda = db.Column(db.String(10), default='BRL')

    # Relacionamento: Um ativo pode ter vários preços históricos
    historico_precos = db.relationship('HistoricoPrecos', back_populates='ativo', lazy=True,
                                       cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'ticker': self.ticker,
            'nome': self.nome,
            'tipo': self.tipo,
            'setor': self.setor,
            'moeda': self.moeda
        }


class HistoricoPrecos(db.Model):
    __tablename__ = 'historico_precos'

    # Chave primária composta
    id_ativo = db.Column(db.Integer, db.ForeignKey('ativos.id'), primary_key=True)
    data = db.Column(db.Date, primary_key=True)

    preco_fechamento = db.Column(db.Numeric(10, 2), nullable=False)

    # Relacionamento com Ativo
    ativo = db.relationship('Ativo', back_populates='historico_precos')

    def to_dict(self):
        return {
            'id_ativo': self.id_ativo,
            'data': self.data.isoformat(),
            'preco_fechamento': str(self.preco_fechamento)
        }