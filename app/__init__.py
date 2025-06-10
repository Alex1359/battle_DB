from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
from app.filters import register_filters

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Регистрация пользовательских фильтров Jinja2
    from app.filters import init_app as init_filters
    init_filters(app)
    register_filters(app)
    
    # Регистрация роутов
    from app.routes import init_app as init_routes
    init_routes(app)
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)
    

    return app