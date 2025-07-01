from collections import Counter
import logging
import time
import random
import re
import uuid
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

import yt_dlp
from app import db # Assuming app.py initializes db
from app.modelos import Video # Assuming modelos.py defines Video
from app.webdriver_init import init_driver

logger = logging.getLogger(__name__)

def clean_original_url(url_str):
    """Normaliza y limpia una URL (de página de video o embed real) para la deduplicación."""
    if not isinstance(url_str, str):
        return None
    try:
        parsed_url = urlparse(url_str)
        query_params = parse_qs(parsed_url.query)
        
        # Mantener parámetros esenciales para embed
        essential_params = {
            'autoplay': query_params.get('autoplay', ['0'])[0],
            'controls': query_params.get('controls', ['1'])[0],
            'mute': query_params.get('mute', ['0'])[0],
            'loop': query_params.get('loop', ['0'])[0],
            'start': query_params.get('start', ['0'])[0]
        }
        
        # Eliminar parámetros de tracking y otros no esenciales
        params_to_filter = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'session_id', 'ss', 'ref', 'referrer', 'token', 'h', 'hash', 'sig', 
            'kt_utmk', 'kt_st', 'kt_pk', 'pk_campaign', 'pk_kwd', 'piwik_campaign', 'piwik_kwd',
            'ad_id', 'campaign_id', 'gclid', 'fbclid', 'msclkid', 'mc_eid', 'mc_cid',
            'expire', 'expires', 'validfrom', 'validto', 'timestamp', 'ts', 't', 'time',
            '_ga', '_gl', 'yclid', 'ysclid', 'zenid',
            'playlist', 'share', 'volume', 'quality', 'q', 'format', 'fmt', 'speed',
            'stretch', 'aspect_ratio', 'ar', 'size', 'width', 'height', 'w', 'h',
            'color', 'theme', 'ui', 'logo', 'branding', 'showinfo', 'related', 'iv_load_policy',
            'cc_load_policy', 'hl', 'language', 'lang', 'locale', 'origin', 'ps', 'no_redirect'
        ]
        
        filtered_query_params = {k: v for k, v in query_params.items() 
                                if k.lower() not in params_to_filter}
        
        # Actualizar con parámetros esenciales
        filtered_query_params.update(essential_params)
        
        scheme = parsed_url.scheme if parsed_url.scheme else 'https'
        netloc = parsed_url.netloc.replace('www.', '')
        path = parsed_url.path
        
        if path and not os.path.splitext(path)[1] and not path.endswith('/'):
            path += '/'
        
        cleaned_query = urlencode(filtered_query_params, doseq=True)
        return urlunparse((scheme, netloc, path, parsed_url.params, cleaned_query, '')).lower()
    except Exception as e:
        logger.error(f"Error cleaning original URL '{url_str}': {e}", exc_info=True)
        return None

def handle_redirection(driver, original_url):
    try:
        current_url = driver.current_url
        if current_url != original_url and urlparse(current_url).netloc == urlparse(original_url).netloc:
            logger.info(f"Redirected from {original_url} to {current_url}")
        return current_url
    except Exception as e:
        logger.warning(f"Error manejando redirección para {original_url}: {e}")
        return original_url

def handle_age_verification(driver, url, age_verification_selectors=None):
    try:
        if age_verification_selectors is None:
            age_verification_selectors = []

        for selector in age_verification_selectors:
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                if btn and btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    logger.info(f"✅ Click en verificación edad: {selector} en {url}")
                    time.sleep(random.uniform(3, 5))
                    return True
            except TimeoutException:
                continue

        text_selectors = ["Enter", "18", "Accept", "Yes, I am over 18", "I am 18 or older", "Confirm"]
        for text in text_selectors:
            try:
                buttons = driver.find_elements(By.XPATH, f"//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                        time.sleep(0.2)
                        driver.execute_script("arguments[0].click();", btn)
                        logger.info(f"✅ Clic en botón verificación por texto: '{text}' en {url}")
                        time.sleep(random.uniform(3, 5))
                        return True
                links = driver.find_elements(By.XPATH, f"//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                for link_el in links:
                    if link_el.is_displayed() and link_el.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView(true);", link_el)
                        time.sleep(0.2)
                        driver.execute_script("arguments[0].click();", link_el)
                        logger.info(f"✅ Clic en enlace verificación por texto: '{text}' en {url}")
                        time.sleep(random.uniform(3, 5))
                        return True
            except Exception as e:
                logger.warning(f"⚠️ Error clic por texto '{text}' en {url}: {e}")
                continue

        logger.info(f"ℹ️ No se encontró/manejó verificación de edad explícita en {url}")
        return True
    except TimeoutException:
        logger.error(f"⛔ Timeout general esperando elementos para verificación de edad en {url}")
        return False
    except Exception as e:
        logger.error(f"⛔ Error manejando verificación edad en {url}: {e}")
        return False

def get_direct_video_url(embed_url, driver=None):
    if not embed_url:
        return None
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best[ext=m3u8]/best',
        'noplaylist': True,
        'simulate': True,
        'geturl': True,
        'logger': logger,
        'socket_timeout': 30,
        'nocheckcertificate': True,
        'extract_flat': True,
        'no_color': True,
        'age_limit': 0,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(embed_url, download=False)
            if info and 'url' in info:
                return info['url']
            elif info and 'formats' in info and info['formats']:
                # Intentar obtener la mejor calidad de video disponible
                formats = info['formats']
                for f in formats:
                    if f.get('ext') in ['mp4', 'm3u8'] and f.get('url'):
                        return f['url']
                # Si no encontramos mp4 o m3u8, usar cualquier formato disponible
                return formats[-1].get('url')
    except Exception as e:
        logger.warning(f"yt-dlp: No se pudo obtener URL directa para {embed_url}: {e}")
    return None

def generate_video_player_url(original_embed_url_o_pagina, source_site_name):
    if not original_embed_url_o_pagina:
        return None
    
    # Si es una URL absoluta, usarla directamente
    if original_embed_url_o_pagina.startswith('http'):
        return original_embed_url_o_pagina
    
    # Si es una URL relativa, convertirla a absoluta usando el dominio correspondiente
    if original_embed_url_o_pagina.startswith('//'):
        return 'https:' + original_embed_url_o_pagina
    elif original_embed_url_o_pagina.startswith('/'):
        domain_map = {
            "YouPorn": "https://www.youporn.com",
            "Pornhub": "https://www.pornhub.com",
            "Xvideos": "https://www.xvideos.com",
            "RedTube": "https://www.redtube.com",
            "Tube8": "https://www.tube8.com",
            "SpankBang": "https://spankbang.com",
            "HClips": "https://hclips.com",
            "TNAFlix": "https://www.tnaflix.com",
            "DrTuber": "https://www.drtuber.com",
            "HotMovs": "https://hotmovs.com",
            "VideoSZ": "https://videosz.com",
            "NuVid": "https://www.nuvid.com",
            "VoyeurHit": "https://voyeurhit.com",
            "AnalVids": "https://analvids.com",
            "BigPorn": "https://bigporn.com",
            "OK.XXX": "https://ok.xxx",
            "4Tube": "https://www.4tube.com",
            "FreeOnes": "https://www.freeones.com",
            "GotPorn": "https://www.gotporn.com",
            "EPorner": "https://www.eporner.com",
            "PornRabbit": "https://www.pornrabbit.com"
        }
        domain = domain_map.get(source_site_name)
        if domain:
            return domain + original_embed_url_o_pagina
    
    # Si no se pudo generar una URL válida, intentar obtener una URL de embed
    embed_url = get_embed_url(source_site_name, original_embed_url_o_pagina)
    if embed_url:
        return embed_url
    
    # Si todo lo demás falla, usar la URL original
    return original_embed_url_o_pagina

def get_embed_url(source, url):
    """Obtiene la URL de embed real de una URL de video."""
    try:
        if not url:
            return None
            
        # URLs conocidas de embed con sus respectivos parámetros
        embed_patterns = {
            'pornhub': {
                'pattern': r'https?://(?:www\.)?pornhub\.com/embed/([a-zA-Z0-9]+)',
                'base': 'https://www.pornhub.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'xvideos': {
                'pattern': r'https?://(?:www\.)?xvideos\.com/video([0-9]+)/',
                'base': 'https://www.xvideos.com/embedframe/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'xhamster': {
                'pattern': r'https?://(?:www\.)?xhamster\.com/videos/([^/]+)/',
                'base': 'https://embed.xhamster.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'redtube': {
                'pattern': r'https?://(?:www\.)?redtube\.com/([0-9]+)',
                'base': 'https://embed.redtube.com/?video_id={}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'youporn': {
                'pattern': r'https?://(?:www\.)?youporn\.com/watch/([0-9]+)/',
                'base': 'https://www.youporn.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'tube8': {
                'pattern': r'https?://(?:www\.)?tube8\.com/video/([0-9]+)/',
                'base': 'https://embed.tube8.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'dr-tuber': {
                'pattern': r'https?://(?:www\.)?dr-tuber\.com/video/([0-9]+)/',
                'base': 'https://embed.dr-tuber.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'tnaflix': {
                'pattern': r'https?://(?:www\.)?tnaflix\.com/([^/]+)/([0-9]+)/',
                'base': 'https://embed.tnaflix.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'spankbang': {
                'pattern': r'https?://(?:www\.)?spankbang\.com/([a-zA-Z0-9]+)/',
                'base': 'https://embed.spankbang.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'okxxx': {
                'pattern': r'https?://(?:www\.)?okxxx\.com/video/([0-9]+)/',
                'base': 'https://embed.okxxx.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'hclips': {
                'pattern': r'https?://(?:www\.)?hclips\.com/video/([0-9]+)/',
                'base': 'https://embed.hclips.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'voyeurhit': {
                'pattern': r'https?://(?:www\.)?voyeurhit\.com/video/([0-9]+)/',
                'base': 'https://embed.voyeurhit.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'gotporn': {
                'pattern': r'https?://(?:www\.)?gotporn\.com/video/([0-9]+)/',
                'base': 'https://embed.gotporn.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'videosz': {
                'pattern': r'https?://(?:www\.)?videosz\.com/video/([0-9]+)/',
                'base': 'https://embed.videosz.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'bigporn': {
                'pattern': r'https?://(?:www\.)?bigporn\.com/video/([0-9]+)/',
                'base': 'https://embed.bigporn.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'analvids': {
                'pattern': r'https?://(?:www\.)?analvids\.com/video/([0-9]+)/',
                'base': 'https://embed.analvids.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            '4tube': {
                'pattern': r'https?://(?:www\.)?4tube\.com/video/([0-9]+)/',
                'base': 'https://embed.4tube.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'freeones': {
                'pattern': r'https?://(?:www\.)?freeones\.com/video/([0-9]+)/',
                'base': 'https://embed.freeones.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'hotmovs': {
                'pattern': r'https?://(?:www\.)?hotmovs\.com/video/([0-9]+)/',
                'base': 'https://embed.hotmovs.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            },
            'nuvid': {
                'pattern': r'https?://(?:www\.)?nuvid\.com/video/([0-9]+)/',
                'base': 'https://embed.nuvid.com/embed/{}',
                'params': {
                    'autoplay': '0',
                    'controls': '1',
                    'mute': '0',
                    'loop': '0',
                    'show_title': '1',
                    'show_byline': '1',
                    'show_portrait': '0',
                    'color': 'ffffff'
                }
            }
        }
        
        # Primero intentar con los patrones conocidos
        for site, config in embed_patterns.items():
            match = re.search(config['pattern'], url)
            if match:
                video_id = match.group(1)
                embed_url = config['base'].format(video_id)
                
                # Añadir parámetros estándar
                query_params = urlencode(config['params'])
                if '?' not in embed_url:
                    embed_url += f'?{query_params}'
                else:
                    embed_url += f'&{query_params}'
                
                # Asegurarse que la URL es HTTPS
                if not embed_url.startswith('https://'):
                    embed_url = embed_url.replace('http://', 'https://')
                
                return embed_url
        
        # Si no se encontró con los patrones conocidos, intentar con patrones específicos
        if source == "YouPorn":
            patterns = [
                r'/watch/([0-9]+)/',
                r'/embed/([0-9]+)/'
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    embed_url = f"https://www.youporn.com/embed/{video_id}/"
                    
                    # Añadir parámetros estándar
                    params = {
                        'autoplay': '0',
                        'controls': '1',
                        'mute': '0',
                        'loop': '0',
                        'show_title': '1',
                        'show_byline': '1',
                        'show_portrait': '0',
                        'color': 'ffffff'
                    }
                    query_params = urlencode(params)
                    embed_url += f'?{query_params}'
                    
                    return embed_url
            logger.warning(f"No se pudo extraer el ID del video de la URL de YouPorn: {url}")
            return url

        elif source == "Pornhub":
            patterns = [
                r'viewkey=([a-zA-Z0-9]+)',
                r'/embed/([a-zA-Z0-9]+)(?:/|$)'
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    embed_url = f"https://www.pornhub.com/embed/{video_id}"
                    
                    # Añadir parámetros estándar
                    params = {
                        'autoplay': '0',
                        'controls': '1',
                        'mute': '0',
                        'loop': '0',
                        'show_title': '1',
                        'show_byline': '1',
                        'show_portrait': '0',
                        'color': 'ffffff'
                    }
                    query_params = urlencode(params)
                    embed_url += f'?{query_params}'
                    
                    return embed_url
            logger.warning(f"No se pudo extraer el ID del video de la URL de Pornhub: {url}")
            return url

        elif source == "Xvideos":
            patterns = [
                r'/video([0-9]+)/',
                r'/embedframe/([0-9]+)/'
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    embed_url = f"https://www.xvideos.com/embedframe/{video_id}"
                    
                    # Añadir parámetros estándar
                    params = {
                        'autoplay': '0',
                        'controls': '1',
                        'mute': '0',
                        'loop': '0',
                        'show_title': '1',
                        'show_byline': '1',
                        'show_portrait': '0',
                        'color': 'ffffff'
                    }
                    query_params = urlencode(params)
                    embed_url += f'?{query_params}'
                    
                    return embed_url
            logger.warning(f"No se pudo extraer el ID del video de la URL de Xvideos: {url}")
            return url

        logger.debug(f"Fuente '{source}' no tiene un patrón de URL de embed definido en get_embed_url.")
        return url

    except Exception as e:
        logger.error(f"Error convirtiendo URL de página a URL de embed para {source} ({url}): {e}")
        return None

def normalize_embed_url(embed_url, source):
    if embed_url is None: return None
    if embed_url.startswith("//"): return "https:" + embed_url
    if embed_url.startswith("/"):
        domain_map = {
            "YouPorn": "https://www.youporn.com", "Pornhub": "https://www.pornhub.com",
            "Xvideos": "https://www.xvideos.com", "RedTube": "https://www.redtube.com",
            "Tube8": "https://www.tube8.com", "SpankBang": "https://spankbang.com",
            "HClips": "https://hclips.com", "TNAFlix": "https://www.tnaflix.com",
            "DrTuber": "https://www.drtuber.com", "HotMovs": "https://hotmovs.com",
            "VideoSZ": "https://videosz.com", "NuVid": "https://www.nuvid.com",
            "VoyeurHit": "https://voyeurhit.com", "AnalVids": "https://analvids.com",
            "BigPorn": "https://bigporn.com", "OK.XXX": "https://ok.xxx",
            "4Tube": "https://www.4tube.com", "FreeOnes": "https://www.freeones.com",
            "GotPorn": "https://www.gotporn.com",
            "EPorner": "https://www.eporner.com", "PornRabbit": "https://www.pornrabbit.com",
        }
        domain = domain_map.get(source)
        if domain: return domain + embed_url
        else: logger.warning(f"No se pudo normalizar URL relativa de embed para fuente desconocida '{source}': {embed_url}")
    return embed_url

def extract_category_from_iframe(driver, iframe_url):
    try:
        current_window = driver.current_window_handle
        driver.switch_to.new_window('tab')
        driver.get(iframe_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        category_selectors = [".category", "a.category-link", "span.category", "div.video-category", ".tags .tag", ".metadata .category"]
        category_text = "General"
        for selector in category_selectors:
            try:
                category_element = driver.find_element(By.CSS_SELECTOR, selector)
                cat = category_element.text.strip()
                if cat: category_text = cat; break
            except NoSuchElementException: continue
        
        driver.close()
        driver.switch_to.window(current_window)
        return category_text
    except Exception as e:
        logger.warning(f"Error extrayendo categoría del iframe {iframe_url}: {e}")
        if driver.current_window_handle != current_window:
            try: driver.close()
            except: pass
            driver.switch_to.window(current_window)
        return "General"

def scrape_site(driver, site_name, url_template, css_selector, link_selector, thumb_selector, title_selector, limit_per_site, max_pages=30, max_retries=3, age_verification_selectors=None, global_seen_video_page_urls=None):
    collected_this_site = 0
    videos_data_from_site = []
    page = 1
    consecutive_empty_pages = 0
    retry_delay = 5  # Tiempo base de espera entre reintentos

    if global_seen_video_page_urls is None: global_seen_video_page_urls = set()
    
    # Configurar el tiempo de espera explícito para elementos
    driver.implicitly_wait(10)

    while collected_this_site < limit_per_site and page <= max_pages:
        current_page_list_url = url_template.format(page=page) if "{page}" in url_template else url_template
        logger.info(f"SCRAPE_SITE [{site_name}]: Page {page}/{max_pages}: {current_page_list_url}")
        retry_count = 0
        page_loaded_successfully = False

        while retry_count < max_retries:
            try:
                # Limpiar cookies y caché antes de cargar la página
                driver.delete_all_cookies()
                
                # Agregar headers aleatorios
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                })

                # Cargar la página con reintento progresivo
                driver.get(current_page_list_url)
                time.sleep(random.uniform(2, 4))  # Aumentar tiempo de espera inicial
                
                # Manejar redirección y verificación de edad
                final_page_url_after_load = handle_redirection(driver, current_page_list_url)
                
                if not handle_age_verification(driver, final_page_url_after_load, age_verification_selectors):
                    logger.error(f"SCRAPE_SITE [{site_name}]: Falló verificación de edad en {final_page_url_after_load}. Reintentando con delay.")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Incrementar el tiempo de espera para el próximo reintento
                    continue  # Reintentar en lugar de saltar la página 
                
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(2, 4))
                
                WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector)))
                page_loaded_successfully = True
                break
            except TimeoutException:
                retry_count += 1
                logger.warning(f"SCRAPE_SITE [{site_name}]: Timeout en {current_page_list_url} (intento {retry_count}/{max_retries})")
                if retry_count == max_retries:
                    logger.error(f"SCRAPE_SITE [{site_name}]: Fallo final por Timeout en {current_page_list_url}. Saltando página.")
                    break 
                time.sleep(random.uniform(2, 4))
            except WebDriverException as e:
                logger.error(f"SCRAPE_SITE [{site_name}]: WebDriver error en {current_page_list_url}: {e}. Terminando scrape para este sitio.")
                return videos_data_from_site

        if not page_loaded_successfully:
            page += 1
            consecutive_empty_pages+=1
            if consecutive_empty_pages >=2: break
            continue

        items_on_page = driver.find_elements(By.CSS_SELECTOR, css_selector)
        logger.info(f"SCRAPE_SITE [{site_name}]: Encontró {len(items_on_page)} elementos con selector '{css_selector}' en {driver.current_url}")
        
        if not items_on_page:
            consecutive_empty_pages += 1
            if consecutive_empty_pages >= 2:
                logger.info(f"SCRAPE_SITE [{site_name}]: {consecutive_empty_pages} páginas vacías consecutivas. Parando scrape para este sitio.")
                break
            page += 1
            time.sleep(random.uniform(1, 2))
            continue
        
        consecutive_empty_pages = 0

        for item_element in items_on_page:
            if collected_this_site >= limit_per_site: break
            try:
                video_page_link_element = item_element.find_element(By.CSS_SELECTOR, link_selector)
                original_video_page_url = video_page_link_element.get_attribute("href")

                if not original_video_page_url or not original_video_page_url.startswith('http'):
                    logger.warning(f"SCRAPE_SITE [{site_name}]: URL de página de video inválida o no encontrada. Saltando item.")
                    continue

                cleaned_video_page_url_for_seen_check = clean_original_url(original_video_page_url)
                if not cleaned_video_page_url_for_seen_check: continue

                if cleaned_video_page_url_for_seen_check in global_seen_video_page_urls:
                    logger.debug(f"SCRAPE_SITE [{site_name}]: URL de página de video '{original_video_page_url}' (limpia: {cleaned_video_page_url_for_seen_check}) ya vista en esta sesión. Saltando.")
                    continue
                
                title = item_element.find_element(By.CSS_SELECTOR, title_selector).text.strip()
                thumbnail_url = item_element.find_element(By.CSS_SELECTOR, thumb_selector).get_attribute("src")

                if not title or not thumbnail_url:
                    logger.warning(f"SCRAPE_SITE [{site_name}]: Elemento sin título o miniatura en {driver.current_url} para link {original_video_page_url}. Saltando.")
                    continue

                real_embed_url_from_source = get_embed_url(site_name, original_video_page_url)
                real_embed_url_normalized = normalize_embed_url(real_embed_url_from_source, site_name)
                player_url_for_db = generate_video_player_url(real_embed_url_normalized if real_embed_url_normalized else original_video_page_url, site_name)
                category = "General"

                video_data_item = {
                    'title': title[:250],
                    'embed_url_for_player': player_url_for_db,
                    'original_video_page_url': original_video_page_url,
                    'original_embed_url': real_embed_url_normalized,
                    'thumbnail': thumbnail_url,
                    'preview_url': None,
                    'source': site_name,
                    'category': category
                }
                videos_data_from_site.append(video_data_item)
                global_seen_video_page_urls.add(cleaned_video_page_url_for_seen_check)
                collected_this_site += 1
                logger.info(f"SCRAPE_SITE [{site_name}]: Video recolectado ({collected_this_site}/{limit_per_site}): '{title}'")

            except NoSuchElementException as e_nse:
                logger.debug(f"SCRAPE_SITE [{site_name}]: Elemento faltante en un item (link, title o thumb): {e_nse}. Saltando item.")
            except Exception as e_item:
                logger.warning(f"SCRAPE_SITE [{site_name}]: Error procesando un item en {driver.current_url}: {e_item}", exc_info=False)
                continue
        
        page += 1
        if collected_this_site < limit_per_site:
            time.sleep(random.uniform(2, 4))

    logger.info(f"SCRAPE_SITE [{site_name}]: Total recolectado de '{site_name}': {collected_this_site} videos.")
    return videos_data_from_site

def scrape_videos_multisite(max_videos=50):
    driver = None
    all_results_collected = []
    global_seen_video_page_urls_this_session = set()
    
    try:
        driver = init_driver()
        if not driver:
            logger.error("MULTISITE: Falló inicialización de WebDriver. Abortando.")
            return []

        total_videos_collected_in_session = 0
        
        configs = [
            ("Xvideos", "https://www.xvideos.com/new/{page}", "div.thumb-block, div.mozaique, .video-item", "a[href*='/video']", "img[data-src], img[src]", "p.title, a.title", ["button.btn-primary.btn-confirm"]),
            ("EPorner", "https://www.eporner.com/latest-updates/{page}/", "div.mb", "div.mbimg a", "div.mbimg a img", "p.mbtit a", []),
            ("PornRabbit", "https://www.pornrabbit.com/videos?page={page}", "div.item", "a[href*='/videos/']", "a[href*='/videos/'] img.thumb", "a[href*='/videos/'] strong.title", ["button.age-verify-yes"]),
            ("SpankBang", "https://spankbang.com/s/newest/{page}/", "div.video-item, .thumb", "a[href*='/video/']", "img[data-src], img[src]", ".n, .title", ["button.accept-age"]),
            ("YouPorn", "https://www.youporn.com/?page={page}", "div.video-box, div.video-item, div.grid-item", "a[href*='/watch/']", "img[data-src], img[src]", "h3, span.title, a.title, div.title", ["button.enter-site", "button#age-gate-button"]),
            ("Pornhub", "https://www.pornhub.com/video?page={page}", "li.pcVideoListItem, li.videoBox", "a[href*='/view_video']", "img[src], img[data-src]", "span.title, a.title", ["button#age-verification-ok", "button.agree-button"]),
            ("RedTube", "https://www.redtube.com/?page={page}", "li.video_item, div.video_item", "a.video_link, a[href*='/video']", "img[data-src], img[src]", ".title, h3", ["button.accept-age"]),
            ("Tube8", "https://www.tube8.com/latest/?page={page}", "div.video-box, .thumb, .video-item, div.thumbnail", "a[href*='/videos/']", "img[data-src], img[src], img[data-thumb]", ".title, .video-title, h3", ["button.confirm-btn"]),
        ]

        valid_configs = [cfg for cfg in configs if len(cfg) == 7]
        num_valid_sites = len(valid_configs)
        if num_valid_sites == 0:
            logger.warning("MULTISITE: No hay configuraciones de sitios válidas. Terminando.")
            return []

        target_per_site = max(1, (max_videos + num_valid_sites -1) // num_valid_sites)
        logger.info(f"MULTISITE: Objetivo global: {max_videos} videos. Intentando hasta {target_per_site} por sitio desde {num_valid_sites} sitios.")

        random.shuffle(valid_configs)

        for site_idx, (name, url_tpl, css_s, link_s, thumb_s, title_s, age_s) in enumerate(valid_configs):
            if total_videos_collected_in_session >= max_videos:
                logger.info(f"MULTISITE: Meta global de {max_videos} videos alcanzada. Deteniendo scrape.")
                break
            
            remaining_needed_globally = max_videos - total_videos_collected_in_session
            current_site_limit = min(target_per_site, remaining_needed_globally)
            if current_site_limit <=0: continue

            logger.info(f"MULTISITE: Procesando sitio {site_idx+1}/{num_valid_sites}: {name}. Intentando obtener hasta {current_site_limit} videos.")
            
            try:
                videos_from_this_site = scrape_site(driver, name, url_tpl, css_s, link_s, thumb_s, title_s, 
                                                    current_site_limit, 
                                                    max_pages=3, 
                                                    age_verification_selectors=age_s,
                                                    global_seen_video_page_urls=global_seen_video_page_urls_this_session)
                
                if videos_from_this_site:
                    added_from_site = 0
                    for video_data in videos_from_this_site:
                        if total_videos_collected_in_session < max_videos:
                            all_results_collected.append(video_data)
                            total_videos_collected_in_session += 1
                            added_from_site +=1
                        else: break
                    logger.info(f"MULTISITE: Añadidos {added_from_site} videos de {name}. Total actual: {total_videos_collected_in_session}/{max_videos}")
                else:
                    logger.info(f"MULTISITE: No se recolectaron videos de {name} en esta pasada.")

            except Exception as e_site_scrape:
                logger.error(f"MULTISITE: Error crítico al scrapear el sitio {name}: {e_site_scrape}", exc_info=True)
                logger.info(f"MULTISITE: Intentando reiniciar WebDriver después de error en {name}.")
                if driver:
                    try:
                        driver.quit()
                    except Exception as e_quit_restart: # CORREGIDO AQUI
                        logger.warning(f"Error al intentar quitar driver durante reinicio para {name}: {e_quit_restart}")
                driver = init_driver()
                if not driver: 
                    logger.error("MULTISITE: Falló RE-inicialización de WebDriver. Abortando scrape general.")
                    return all_results_collected[:max_videos] 
                logger.info(f"MULTISITE: WebDriver reiniciado. Continuando con el siguiente sitio.")
                continue 

        source_counts = Counter(video['source'] for video in all_results_collected)
        logger.info(f"MULTISITE: Scrape finalizado. Total videos recolectados en sesión: {total_videos_collected_in_session}.")
        logger.info(f"MULTISITE: Distribución por fuente: {dict(source_counts)}")
        
        return all_results_collected[:max_videos]

    except Exception as e_global:
        logger.critical(f"MULTISITE: Error crítico global en scrape_videos_multisite: {e_global}", exc_info=True)
        return all_results_collected[:max_videos] 
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("MULTISITE: WebDriver cerrado al finalizar.")
            except Exception as e_quit_final: # CORREGIDO AQUI (nombre de variable)
                logger.warning(f"MULTISITE: Error final cerrando WebDriver: {e_quit_final}")

def save_videos_to_db(videos_data_list):
    if not videos_data_list:
        logger.info("SAVE_DB: No hay videos para guardar.")
        return 0
    
    newly_saved_count = 0
    try:
        logger.info(f"SAVE_DB: Procesando {len(videos_data_list)} videos para guardar.")
    except Exception as e_fetch: 
        logger.error(f"SAVE_DB: Error inicial (ej. al intentar pre-cargar URLs de BD): {e_fetch}. ")

    for video_data in videos_data_list:
        original_page_url = video_data.get('original_video_page_url')
        original_embed_url = video_data.get('original_embed_url')
        
        # Asegurarse de que embed_url_for_player sea una URL válida
        if not video_data.get('embed_url_for_player'):
            video_data['embed_url_for_player'] = generate_video_player_url(original_embed_url, video_data.get('source'))
            if not video_data['embed_url_for_player']:
                video_data['embed_url_for_player'] = generate_video_player_url(original_page_url, video_data.get('source'))
        
        # Verificar que tenemos una URL válida para reproducción
        if not video_data.get('embed_url_for_player'):
            logger.warning(f"SAVE_DB: No se pudo generar URL de reproducción válida para '{video_data.get('title')}'. Saltando.")
            continue
        
        url_to_clean_for_db_check = None
        if original_embed_url:
            url_to_clean_for_db_check = original_embed_url
        elif original_page_url:
            url_to_clean_for_db_check = original_page_url
        else:
            logger.warning(f"SAVE_DB: Video '{video_data.get('title')}' no tiene URL original (página o embed). Saltando.")
            continue
            
        cleaned_url_for_db = clean_original_url(url_to_clean_for_db_check)
        if not cleaned_url_for_db:
            logger.warning(f"SAVE_DB: Falló la limpieza de URL '{url_to_clean_for_db_check}' para video '{video_data.get('title')}'. Saltando.")
            continue

        try:
            existing_video = Video.query.filter_by(original_cleaned_url=cleaned_url_for_db).first()
        except Exception as e_query_dupe:
            logger.error(f"SAVE_DB: Error al consultar la BD por duplicados para URL '{cleaned_url_for_db}': {e_query_dupe}. "
                         "Asegúrate que el campo 'original_cleaned_url' existe en el modelo 'Video'. Saltando este video.")
            continue

        if existing_video:
            logger.info(f"SAVE_DB: Video '{video_data.get('title')}' (URL limpia: {cleaned_url_for_db}) ya existe en la BD con ID {existing_video.id}. Saltando.")
            continue
        
        try:
            new_video = Video(
                title=video_data['title'],
                embed_url=video_data['embed_url_for_player'],
                thumbnail=video_data['thumbnail'],
                preview_url=video_data.get('preview_url'),
                source=video_data['source'],
                category=video_data['category'],
                original_cleaned_url=cleaned_url_for_db,
                original_page_url=original_page_url
            )
            db.session.add(new_video)
            newly_saved_count += 1
        except Exception as e_orm:
            logger.error(f"SAVE_DB: Error creando objeto Video ORM para '{video_data.get('title')}': {e_orm}", exc_info=True)
            
    if newly_saved_count > 0:
        try:
            db.session.commit()
            logger.info(f"SAVE_DB: Confirmados {newly_saved_count} nuevos videos en la BD.")
        except Exception as e_commit:
            db.session.rollback()
            logger.error(f"SAVE_DB: Error al hacer commit a la BD: {e_commit}. Cambios revertidos.", exc_info=True)
            return 0 
    else:
        logger.info("SAVE_DB: No hay videos nuevos o válidos para añadir a la BD en este lote.")
            
    return newly_saved_count

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s [%(name)s] %(message)s')
    logger.info("Iniciando script de scrapeo (ejemplo standalone)...")
    logger.warning("Ejecución __main__ de scraper.py está comentada. Descomenta y ajusta el contexto de app Flask para probar.")
    logger.info("Script de scrapeo (ejemplo standalone) finalizado.")
