# app/webdriver_init.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logging

def init_driver():
    options = Options()
    options.add_argument("--headless")  # Ejecutar sin abrir ventana
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Opcional: agrega user-agent personalizado si quieres
    # options.add_argument("user-agent=Mozilla/5.0 ...")

    try:
        driver = webdriver.Chrome(options=options)
        logging.info("WebDriver iniciado correctamente")
        return driver
    except Exception as e:
        logging.error(f"Error iniciando WebDriver: {e}")
        raise
