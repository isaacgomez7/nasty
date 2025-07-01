from app import db
from datetime import datetime

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False) # Incrementé un poco por si acaso
    embed_url = db.Column(db.String(500), nullable=False) # Esta es tu URL de reproducción local
    thumbnail = db.Column(db.String(500), nullable=True) # Permitir nulo si a veces falla el thumb
    preview_url = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(50), nullable=True) # Permitir nulo por si la categoría no se encuentra
    source = db.Column(db.String(50), nullable=True) # Permitir nulo
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    # --- CAMPOS NUEVOS Y ESENCIALES PARA SCRAPER v2 ---
    original_cleaned_url = db.Column(db.String(500), unique=True, index=True, nullable=True)
    original_page_url = db.Column(db.String(500), nullable=True) # URL de la página original del video
    # url_type = db.Column(db.String(50), nullable=True) # Opcional: para guardar 'embed' o 'direct'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
