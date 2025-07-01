import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
import logging
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    if os.environ.get('FLASK_DEBUG') == '1':
        app.config['DEBUG'] = True
        is_production = False
    elif os.environ.get('FLASK_DEBUG') == '0':
        app.config['DEBUG'] = False
        is_production = True
    elif os.environ.get('FLASK_ENV') == 'production':
        app.config['DEBUG'] = False
        is_production = True
    elif os.environ.get('FLASK_ENV') == 'development':
        app.config['DEBUG'] = True
        is_production = False
    else:
        is_production = not app.debug 

    log_level_name = os.environ.get('LOG_LEVEL', 'INFO' if is_production else 'DEBUG').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    
    for handler in list(app.logger.handlers): app.logger.removeHandler(handler)
    werkzeug_logger = logging.getLogger('werkzeug')
    for handler in list(werkzeug_logger.handlers): werkzeug_logger.removeHandler(handler)
    
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    stream_handler.setFormatter(formatter)
    
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(log_level)
    
    werkzeug_logger.addHandler(stream_handler) 
    werkzeug_logger.setLevel(log_level) 
    werkzeug_logger.propagate = False 

    app.logger.info(f"Application starting. Flask app.debug: {app.debug}. Effective is_production: {is_production}. Log Level: {log_level_name}.")

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clave_secreta_muy_fuerte_y_aleatoria_por_defecto_dev_xyz123')
    if app.config['SECRET_KEY'] == 'una_clave_secreta_muy_fuerte_y_aleatoria_por_defecto_dev_xyz123':
        if is_production:
            app.logger.critical("CRITICAL: Using default SECRET_KEY in PRODUCTION. Set the SECRET_KEY environment variable.")
        else:
            app.logger.warning("WARNING: Using default SECRET_KEY for development. Set SECRET_KEY for production.")

    try:
        if not os.path.exists(app.instance_path):
            os.makedirs(app.instance_path)
            app.logger.info(f"Instance folder created at: {app.instance_path}")
    except OSError as e:
        app.logger.error(f"Error creating instance folder at {app.instance_path}: {e}")

    app.config['APPLICATION_ROOT'] = '/'
    app.config['PREFERRED_URL_SCHEME'] = 'http'
    app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME', None) 
    app.config['TEMPLATES_AUTO_RELOAD'] = not is_production
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(app.instance_path, 'videos.db'))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db) 
    csrf.init_app(app) 

    csp = {
        'default-src': ['\'self\''],
        'script-src': [
            '\'self\'', 
            'https://cdn.jsdelivr.net', 
            'https://vjs.zencdn.net',
            '\'unsafe-inline\''  
        ],
        'style-src': [
            '\'self\'', 
            'https://cdn.jsdelivr.net',
            'https://vjs.zencdn.net',   
            '\'unsafe-inline\'' 
        ],
        'img-src': [
            '\'self\'', 
            'data:',
            'https://*.externulls.com', # Para Beeg thumbnails (si lo vuelves a activar)
            '*' 
        ],
        'frame-src': [ 
            '*',
            'data:',
            'blob:',
            '\'self\'', 
            'https://www.youporn.com', 'https://*.youporn.com',
            'https://www.pornhub.com', 'https://*.pornhub.com',
            'https://www.xvideos.com', 'https://*.xvideos.com',
            'https://www.redtube.com', 'https://*.redtube.com',
            'https://spankbang.com', 'https://*.spankbang.com',
            'https://www.youtube.com',
            'https://pornrabbit.com', 'https://*.pornrabbit.com',
            'https://eporner.com', 'https://*.eporner.com',
            'https://www.eporner.com', 'https://*.eporner.com',
            'https://vjav.com', 'https://*.vjav.com',
        ],
        'font-src': [
            '\'self\'', 
            'https://cdn.jsdelivr.net', 
            'https://vjs.zencdn.net',
            'data:'  
        ],
        'object-src': ['\'none\''], 
        'media-src': [  
            '\'self\'',
            'https://*.xvideos-cdn.com',
            'https://*.phncdn.com', 
            'https://*.ypncdn.com', 
            'https://*.rtcdn.com',  
            'https://*.sb-cd.com', 
            'https://www.pornrabbit.com', # <--- AÑADIDO (sin comodín)
            'https://*.pornrabbit.com',
            'https://*.mjedge.net', 
            'https://vjav.com', 'https://*.vjav.com', 
            'https://*.ahcdn.com', 
            'blob:' 
        ],
        'connect-src': [ 
            '\'self\'',
            'https://*.xvideos-cdn.com',
            'https://*.phncdn.com', 
            'https://*.ypncdn.com',
            'https://*.rtcdn.com',
            'https://*.sb-cd.com',
            'https://www.pornrabbit.com', # <--- AÑADIDO (sin comodín)
            'https://*.pornrabbit.com',
            'https://*.mjedge.net',
            'https://vjav.com', 'https://*.vjav.com', 
            'https://*.ahcdn.com', 
            'blob:' 
        ],
        'worker-src': [ 
            '\'self\'',
            'blob:' 
        ]
    }
    
    talisman_options = {
        'content_security_policy': csp,
        'force_https': False,
        'force_https_permanent': False,
        'strict_transport_security': False,
        'session_cookie_secure': False,
        'frame_options': None,
        'content_security_policy_report_only': False
    }
    Talisman(app, **talisman_options)

    from .rutas import rutas_bp 
    app.register_blueprint(rutas_bp)

    with app.app_context():
        try:
            from .modelos import User 
            db.create_all() 
            if not User.query.filter_by(username='admin').first():
                from werkzeug.security import generate_password_hash
                admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
                if admin_password == 'admin123':
                    if is_production:
                        app.logger.critical("CRITICAL: Using default admin password in PRODUCTION. Set ADMIN_PASSWORD env variable.")
                    else:
                         app.logger.warning("WARNING: Using default admin password for development. Set ADMIN_PASSWORD for production.")
                
                hashed_password = generate_password_hash(admin_password, method='pbkdf2:sha256')
                admin_user = User(username='admin', password=hashed_password)
                db.session.add(admin_user)
                db.session.commit()
                app.logger.info("Admin user created/verified.")
            else:
                app.logger.info("Admin user already exists.")
        except Exception as e:
            app.logger.error(f"Error during DB initialization or admin creation: {e}", exc_info=True)

    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)

    @app.context_processor
    def inject_debug_mode():
        return dict(debug=app.debug) 
    
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template 
        try:
            return render_template('errors/404.html', error=error), 404
        except Exception:
            app.logger.warning("Template 'errors/404.html' not found or error rendering, using fallback.", exc_info=True)
            return "<h1>404 - Page Not Found</h1><p>Sorry, the page you are looking for does not exist.</p>", 404
    
    @app.errorhandler(500)
    def internal_server_error(error):
        from flask import render_template 
        try:
            db.session.rollback()
        except Exception as rb_error:
            app.logger.error(f"Error during rollback in 500 handler: {rb_error}", exc_info=True)
            
        app.logger.error(f"Internal Server Error (500): {error}", exc_info=True)
        try:
            return render_template('errors/500.html', error=error), 500
        except Exception:
            app.logger.warning("Template 'errors/500.html' not found or error rendering, using fallback.", exc_info=True)
            return "<h1>500 - Internal Server Error</h1><p>An unexpected error occurred. Please try again later.</p>", 500

    @app.after_request
    def add_extra_security_headers(response):
        if 'X-Content-Type-Options' not in response.headers:
            response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    app.logger.info(f"Flask app created. Flask app.debug: {app.debug}, Effective is_production: {is_production}.")
    return app
