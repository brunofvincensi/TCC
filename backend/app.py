from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from config import Config
from models import db
from routes import register_blueprints

def create_app():
    """Factory pattern para criar a aplicação"""
    app = Flask(__name__)

    # Carregar configurações
    app.config.from_object(Config)

    # Inicializar extensões
    db.init_app(app)
    jwt = JWTManager(app)

    # Registrar blueprints
    register_blueprints(app)

    # Registras os comandos via terminal
    # register_commands(app)

    # Criar tabelas
    with app.app_context():
        db.create_all()

    # Rota raiz com informações do projeto
    @app.route('/')
    def index():
        return jsonify({
            'projeto': app.config['APP_NAME'],
            'versao': app.config['APP_VERSION'],
            'status': 'online'
        })

    # Tratamento de erros JWT
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'erro': 'Token expirado'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'erro': 'Token inválido'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'erro': 'Token ausente'}), 401

    return app


if __name__ == '__main__':
    app = create_app()
    print(f"🚀 Iniciando {app.config['APP_NAME']} v{app.config['APP_VERSION']}")
    app.run(debug=True)