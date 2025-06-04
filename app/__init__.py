from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    # Create admin user if not exists
    with app.app_context():
        from app.models import User
        db.create_all()
        admin = User.query.filter_by(username=app.config['ADMIN_USERNAME']).first()
        if not admin:
            from werkzeug.security import generate_password_hash
            admin = User(
                username=app.config['ADMIN_USERNAME'],
                password=generate_password_hash(app.config['ADMIN_PASSWORD']),
                branch='main',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

    return app