from . import db
import enum

class AssetType(enum.Enum):
    STOCK = "Stock"
    FIXED_INCOME = "Fixed Income"
    UNDEFINED = "Undefined"


class Asset(db.Model):
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticker = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(AssetType), nullable=False, default=AssetType.UNDEFINED)
    sector = db.Column(db.String(100))

    price_history = db.relationship('PriceHistory', back_populates='asset', lazy=True,
                                       cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'ticker': self.ticker,
            'name': self.name,
            # When converting to dictionary, we get the value (the string) from the enum
            'type': self.type.value,
            'sector': self.sector
        }

class PriceHistory(db.Model):
    __tablename__ = 'price_history'

    # Chave primária composta
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date, nullable=False)
    closing_price = db.Column(db.Numeric(10, 2), nullable=False)
    monthly_variation = db.Column(db.Numeric(10, 6), nullable=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)

    # Relacionamento com Ativo
    asset = db.relationship('Asset', back_populates='price_history')

    def to_dict(self):
        return {
            'asset_id': self.asset_id,
            'date': self.date.isoformat(),
            'closing_price': str(self.closing_price),
            'monthly_variation': f"{float(self.monthly_variation):.6f}" if self.monthly_variation is not None else None
        }
