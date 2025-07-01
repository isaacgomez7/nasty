#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Crear la carpeta instance si no existe
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)
        print(f"✅ Carpeta instance creada: {instance_dir}")
    
    # Tu línea original para mostrar rutas (muy útil para debug)
    print("🔍 RUTAS REGISTRADAS:")
    print(app.url_map)  # 👈 Muestra todas las rutas registradas en Flask
    print("-" * 50)
    
    # Información útil de inicio
    print("🚀 Iniciando aplicación NastyMood...")
    print("🌐 Servidor: http://localhost:5000")
    print("🔧 Modo: Desarrollo (DEBUG=True)")
    print("📁 Base de datos: instance/videos.db")
    print("👤 Admin: username='admin', password='admin123'")
    print("🛠️  Para detener: Ctrl+C")
    print("-" * 50)
    
    # Tu configuración original con pequeñas mejoras
    app.run(
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        threaded=True,      # Permite múltiples requests simultáneos
        use_reloader=True   # Reinicia automáticamente al detectar cambios
    )