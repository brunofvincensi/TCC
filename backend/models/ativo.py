from . import db
import enum  # 1. Importe a biblioteca nativa de Enum

# 2. Crie a classe Enum com os tipos de ativo permitidos
class TipoAtivo(enum.Enum):
    ACAO = "Ação"
    RENDA_FIXA = "Renda Fixa"
    INDEFINIDO = "Indefinito"


class Ativo(db.Model):
    __tablename__ = 'ativos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticker = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.Enum(TipoAtivo), nullable=False, default=TipoAtivo.INDEFINIDO)
    setor = db.Column(db.String(100))
    moeda = db.Column(db.String(10), default='BRL')

    historico_precos = db.relationship('HistoricoPrecos', back_populates='ativo', lazy=True,
                                       cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'ticker': self.ticker,
            'nome': self.nome,
            # Ao converter para dicionário, pegamos o valor (a string) do enum
            'tipo': self.tipo.value,
            'setor': self.setor,
            'moeda': self.moeda
        }

class HistoricoPrecos(db.Model):
    __tablename__ = 'historico_precos'

    # Chave primária composta
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # A data representará o último dia do mês para o qual o preço foi fechado
    data = db.Column(db.Date, nullable=False)
    preco_fechamento = db.Column(db.Numeric(10, 2), nullable=False)
    # Armazena a rentabilidade percentual do mês (ex: 0.05 para 5%)
    variacao_mensal = db.Column(db.Numeric(10, 6), nullable=True)
    id_ativo = db.Column(db.Integer, db.ForeignKey('ativos.id'), nullable=False)

    # Relacionamento com Ativo
    ativo = db.relationship('Ativo', back_populates='historico_precos')

    def to_dict(self):
        return {
            'id_ativo': self.id_ativo,
            'data': self.data.isoformat(),
            'preco_fechamento': str(self.preco_fechamento),
            'variacao_mensal': f"{float(self.variacao_mensal):.6f}" if self.variacao_mensal is not None else None
        }