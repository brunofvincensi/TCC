from flask_jwt_extended import create_access_token
from models.usuario import Usuario


class AuthService:

    @staticmethod
    def login(email, senha):
        """
        Realiza o login do usuário
        Retorna: (token, usuario_dict) ou (None, erro_mensagem)
        """
        if not email or not senha:
            return None, 'Email e senha são obrigatórios'

        usuario = Usuario.query.filter_by(email=email).first()

        if not usuario or not usuario.check_password(senha):
            return None, 'Credenciais inválidas'

        if not usuario.ativo:
            return None, 'Usuário inativo'

        access_token = create_access_token(identity=usuario.id)

        return access_token, usuario.to_dict()