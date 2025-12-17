from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from models import db
from extensions import limiter
from routes import register_blueprints

# Variável global para manter referência ao scheduler
_price_scheduler = None

def _init_price_scheduler(app):
    """
    Inicializa o scheduler de atualização de preços.

    Args:
        app: Instância da aplicação Flask
    """
    global _price_scheduler

    try:
        from services.scheduler.price_scheduler import PriceUpdateScheduler
        from commands import update_daily_prices

        hour = app.config['PRICE_SCHEDULER_HOUR']
        minute = app.config['PRICE_SCHEDULER_MINUTE']

        _price_scheduler = PriceUpdateScheduler(app, update_daily_prices)
        _price_scheduler.start(hour=hour, minute=minute)

        print(f"Scheduler de preços iniciado!")
        print(f"   Horário: {hour:02d}:{minute:02d}")
        print(f"   Próxima execução: {_price_scheduler.get_next_run_time()}")
    except Exception as e:
        print(f"Erro ao inicializar scheduler de preços: {e}")
        print(f"   A aplicação continuará rodando sem o scheduler.")

def create_app(enable_scheduler=None):
    """Factory pattern para criar a aplicação"""
    app = Flask(__name__)

    # Habilitar CORS para o frontend (durante desenvolvimento permitir origens locais)
    # Ajuste a lista "origins" conforme necessário em produção
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://localhost:3000"]}}, supports_credentials=True)

    # Carregar configurações
    app.config.from_object(Config)

    # Inicializar extensões
    db.init_app(app)
    jwt = JWTManager(app)
    limiter.init_app(app)
    print(f"Rate limiter inicializado: {limiter}")
    print(f"   Storage: {limiter._storage}")
    print(f"   Estratégia: {limiter._strategy}")

    # Registrar blueprints
    register_blueprints(app)

    # Criar tabelas
    with app.app_context():
        db.create_all()

    # Inicializar scheduler de atualização de preços (se habilitado)
    if enable_scheduler is None:
        enable_scheduler = app.config['ENABLE_PRICE_SCHEDULER']

    if enable_scheduler:
        _init_price_scheduler(app)

    # Rota raiz com informações do projeto
    @app.route('/')
    def index():
        return jsonify({
            'projeto': app.config['APP_NAME'],
            'versao': app.config['APP_VERSION'],
            'status': 'online',
            'scheduler_ativo': _price_scheduler is not None and _price_scheduler.scheduler.running if _price_scheduler else False
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

    # Tratamento de erro de rate limiting
    @app.errorhandler(429)
    def rate_limit_handler(e):
        return jsonify({
            'erro': 'Muitas requisições',
            'mensagem': 'Você excedeu o limite de requisições. Tente novamente mais tarde.',
            'detalhes': str(e.description) if hasattr(e, 'description') else 'Limite excedido'
        }), 429

    return app


if __name__ == '__main__':
    app = create_app()
    print(f"🚀 Iniciando {app.config['APP_NAME']} v{app.config['APP_VERSION']}")
    app.run(debug=True)