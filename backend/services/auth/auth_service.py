from flask_jwt_extended import create_access_token
from models import User


class AuthService:

    @staticmethod
    def login(email, password):
        """
        Performs user login
        Returns: (token, user_dict) or (None, error_message)
        """
        if not email or not password:
            return None, 'Email e senha são obrigatórios'

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            return None, 'Credenciais inválidas'

        if not user.active:
            return None, 'Usuário inativo'

        access_token = create_access_token(identity=str(user.id))

        return access_token, user.to_dict()
