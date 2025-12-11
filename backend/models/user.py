from . import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)

    portfolios = db.relationship('Portfolio', back_populates='user', cascade="all, delete-orphan")

    """Criptografa e define a senha do usuário"""
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

        """Verifica se a senha está correta"""
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'active': self.active
        }
