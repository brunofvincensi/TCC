def register_blueprints(app):
    """Registra todos os blueprints na aplicação"""
    from routes.auth_routes import auth_bp
    from routes.user_routes import usuario_bp
    from routes.asset_routes import ativo_bp
    from routes.portfolio_routes import carteira_bp
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(usuario_bp, url_prefix='/api')
    app.register_blueprint(ativo_bp, url_prefix='/api')
    app.register_blueprint(carteira_bp, url_prefix='/api')