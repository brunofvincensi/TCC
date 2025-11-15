from flask_jwt_extended import create_access_token
from models import Usuario


class AuthService:

    @staticmethod
    def login(email, password):
        """
        Realiza o login do usuário
        Retorna: (token, usuario_dict) ou (None, erro_mensagem)
        """
        if not email or not password:
            return None, 'Email e senha são obrigatórios'

        user = Usuario.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            return None, 'Credenciais inválidas'

        if not user.ativo:
            return None, 'Usuário inativo'

        access_token = create_access_token(identity=str(user.id))

        return access_token, user.to_dict()