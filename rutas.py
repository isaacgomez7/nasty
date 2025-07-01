from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from app.modelos import Video, User
from app import db, csrf # <--- Importa csrf aquí
from app.scraper import scrape_videos_multisite, save_videos_to_db, generate_video_player_url
from werkzeug.security import check_password_hash
from sqlalchemy.sql.expression import func
from sqlalchemy import or_, and_
from datetime import datetime, timedelta
import logging
# from flask_wtf.csrf import generate_csrf # Ya no es necesario aquí

logger = logging.getLogger(__name__)

rutas_bp = Blueprint('rutas', __name__)

VIDEOS_PER_PAGE = 60

# --- Funciones de Ayuda ---
def is_admin():
    return session.get('admin')

# --- Rutas Públicas (con verificación de edad) ---
@rutas_bp.route('/')
def index():
    if not session.get('age_verified'):
        return redirect(url_for('rutas.age_gate'))
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('search', '').strip().lower()
    try:
        videos_query = Video.query.order_by(Video.date_added.desc())
        if search_term:
            search_condition = or_(Video.title.ilike(f'%{search_term}%'), Video.category.ilike(f'%{search_term}%'))
            videos_query = videos_query.filter(search_condition)
        total_videos = videos_query.count()
        videos = videos_query.offset((page - 1) * VIDEOS_PER_PAGE).limit(VIDEOS_PER_PAGE).all()
        total_pages = (total_videos + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE
        categories_db = db.session.query(Video.category).distinct().order_by(Video.category).all()
        categories = [cat[0] for cat in categories_db if cat[0]]
    except Exception as e:
        logger.error(f"Error loading videos for the main page: {e}", exc_info=True)
        flash('Error loading videos. Please try again later.', 'error')
        return render_template('index.html', videos=[], categories=[], page=1, total_pages=1, search_term=search_term)
    return render_template('index.html', 
                           videos=videos, 
                           categories=categories, 
                           page=page, 
                           total_pages=total_pages, 
                           current_category=None, 
                           search_term=search_term)

@rutas_bp.route('/age_gate', methods=['GET', 'POST'])
@csrf.exempt  # <--- LÍNEA AÑADIDA TEMPORALMENTE PARA DIAGNÓSTICO
def age_gate():
    if session.get('age_verified'):
        return redirect(url_for('rutas.index'))
        
    if request.method == 'POST':
        session['age_verified'] = True
        next_url = request.args.get('next') or url_for('rutas.index')
        return redirect(next_url)
    return render_template('age_gate.html')

@rutas_bp.route('/terms')
def terms():
    return render_template('terms.html')

@rutas_bp.route('/cookies')
def cookies():
    return render_template('cookies.html')

@rutas_bp.route('/dmca')
def dmca():
    return render_template('dmca.html')

@rutas_bp.route('/category/<category_name>')
def category(category_name):
    if not session.get('age_verified'):
        return redirect(url_for('rutas.age_gate', next=request.url))
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('search', '').strip().lower()
    try:
        videos_query = Video.query.filter(Video.category.ilike(f'%{category_name}%'))
        if search_term:
            videos_query = videos_query.filter(Video.title.ilike(f'%{search_term}%'))
            
        videos_query = videos_query.order_by(Video.date_added.desc())
        total_videos = videos_query.count()
        if total_videos == 0 and not search_term:
            flash(f'No videos found in the "{category_name}" category.', 'info')
            
        videos = videos_query.offset((page - 1) * VIDEOS_PER_PAGE).limit(VIDEOS_PER_PAGE).all()
        total_pages = (total_videos + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE
        
        categories_db = db.session.query(Video.category).distinct().order_by(Video.category).all()
        categories = [cat[0] for cat in categories_db if cat[0]]

    except Exception as e:
        logger.error(f"Error loading videos for category '{category_name}': {e}", exc_info=True)
        flash(f'Error loading videos for category "{category_name}".', 'error')
        categories = []
        return render_template('index.html', videos=[], categories=categories, current_category=category_name, page=1, total_pages=1, search_term=search_term)
        
    return render_template('index.html', 
                           videos=videos, 
                           categories=categories, 
                           current_category=category_name, 
                           page=page, 
                           total_pages=total_pages,
                           search_term=search_term)

@rutas_bp.route('/quality/<quality_filter>')
def filter_by_quality(quality_filter):
    if not session.get('age_verified'):
        return redirect(url_for('rutas.age_gate', next=request.url))
    
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('search', '').strip().lower()
    
    try:
        videos_query = Video.query
        quality_conditions = []

        if quality_filter == '4k':
            quality_conditions = [Video.title.ilike(term) for term in ['%4K%', '%2160p%', '%UHD%', '%Ultra HD%']]
        elif quality_filter == '1080p':
            quality_conditions = [Video.title.ilike(term) for term in ['%1080p%', '%Full HD%', '%FHD%']]
        elif quality_filter == '720p':
            quality_conditions = [Video.title.ilike(term) for term in ['%720p%', '%HD%']] # Simplificado
        elif quality_filter == 'hd': # 'hd' puede ser 720p o 1080p o una categoría
             quality_conditions = [
                Video.category.ilike('%HD%'), Video.title.ilike('%HD%'),
                Video.title.ilike('%720p%'), Video.title.ilike('%1080p%')
            ]
        # Añadir más filtros o mejorar la lógica si es necesario

        if quality_conditions:
            videos_query = videos_query.filter(or_(*quality_conditions))
        else: # Si el filtro de calidad no es reconocido, no aplicar filtro de calidad
            flash(f'Quality filter "{quality_filter}" not recognized.', 'warning')

        if search_term: # Permitir búsqueda combinada con filtro de calidad
             videos_query = videos_query.filter(Video.title.ilike(f'%{search_term}%'))

        videos_query = videos_query.order_by(Video.date_added.desc())
        total_videos = videos_query.count()
        videos = videos_query.offset((page - 1) * VIDEOS_PER_PAGE).limit(VIDEOS_PER_PAGE).all()
        total_pages = (total_videos + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE
        
        categories_db = db.session.query(Video.category).distinct().order_by(Video.category).all()
        categories = [cat[0] for cat in categories_db if cat[0]]
        
        if total_videos == 0:
            flash(f'No videos found for quality "{quality_filter.upper()}"' + (f' with search term "{search_term}"' if search_term else '.'), 'info')
            
    except Exception as e:
        logger.error(f"Error filtering by quality '{quality_filter}': {e}", exc_info=True)
        flash(f'Error filtering videos by quality: {str(e)}', 'error')
        return redirect(url_for('rutas.index')) # Redirigir en caso de error grave
    
    return render_template('index.html', 
                           videos=videos, 
                           categories=categories, 
                           page=page, 
                           total_pages=total_pages,
                           current_filter=f'Quality: {quality_filter.upper()}',
                           search_term=search_term)


@rutas_bp.route('/duration/<duration_filter>')
def filter_by_duration(duration_filter):
    if not session.get('age_verified'):
        return redirect(url_for('rutas.age_gate', next=request.url))
    
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('search', '').strip().lower()

    duration_names = {'short': 'Short (0-10 min)', 'medium': 'Medium (10-30 min)', 'long': 'Long (30+ min)'}
    current_filter_name = duration_names.get(duration_filter, duration_filter.capitalize())

    try:
        videos_query = Video.query
        duration_conditions = []

        if duration_filter == 'short':
            duration_conditions = [Video.title.ilike(term) for term in ['%short%', '%quick%', '%clip%', '%brief%', '%mini%', '%teaser%']]
        elif duration_filter == 'long':
            duration_conditions = [Video.title.ilike(term) for term in ['%long%', '%full%', '%complete%', '%extended%', '%compilation%', '%movie%']]
        elif duration_filter == 'medium':
            # Excluir short y long para 'medium' es complejo con solo ILIKE.
            # Esta es una aproximación, idealmente tendrías un campo de duración.
            all_terms = ['%short%', '%quick%', '%clip%', '%brief%', '%mini%', '%teaser%', '%long%', '%full%', '%complete%', '%extended%', '%compilation%', '%movie%']
            videos_query = videos_query.filter(and_(*[~Video.title.ilike(term) for term in all_terms]))
        
        if duration_conditions: # Solo aplicar si hay condiciones (evita error con 'medium')
            videos_query = videos_query.filter(or_(*duration_conditions))
        
        if search_term:
            videos_query = videos_query.filter(Video.title.ilike(f'%{search_term}%'))

        videos_query = videos_query.order_by(Video.date_added.desc())
        total_videos = videos_query.count()
        videos = videos_query.offset((page - 1) * VIDEOS_PER_PAGE).limit(VIDEOS_PER_PAGE).all()
        total_pages = (total_videos + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE
        
        categories_db = db.session.query(Video.category).distinct().order_by(Video.category).all()
        categories = [cat[0] for cat in categories_db if cat[0]]
        
        if total_videos == 0:
            flash(f'No videos found for duration "{current_filter_name}"' + (f' with search term "{search_term}"' if search_term else '.'), 'info')

    except Exception as e:
        logger.error(f"Error filtering by duration '{duration_filter}': {e}", exc_info=True)
        flash(f'Error filtering videos by duration: {str(e)}', 'error')
        return redirect(url_for('rutas.index'))

    return render_template('index.html', 
                           videos=videos, 
                           categories=categories, 
                           page=page, 
                           total_pages=total_pages,
                           current_filter=f'Duration: {current_filter_name}',
                           search_term=search_term)

@rutas_bp.route('/trending/<period>')
def trending_videos(period):
    if not session.get('age_verified'):
        return redirect(url_for('rutas.age_gate', next=request.url))
    
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('search', '').strip().lower()
    
    period_names = {'today': 'Today', 'week': 'This Week', 'month': 'This Month', 'all': 'All Time'}
    current_filter_name = period_names.get(period, period.capitalize())
    
    try:
        videos_query = Video.query
        now = datetime.utcnow() # Usar utcnow para consistencia con default=datetime.utcnow en el modelo

        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            videos_query = videos_query.filter(Video.date_added >= start_date)
        elif period == 'week':
            start_date = now - timedelta(days=7)
            videos_query = videos_query.filter(Video.date_added >= start_date)
        elif period == 'month':
            start_date = now - timedelta(days=30) # O usar relativedelta para meses exactos
            videos_query = videos_query.filter(Video.date_added >= start_date)
        elif period != 'all':
            flash(f'Trending period "{period}" not recognized.', 'warning')
            # No aplicar filtro de fecha si el período no es válido, o redirigir

        if search_term:
            videos_query = videos_query.filter(Video.title.ilike(f'%{search_term}%'))
            
        videos_query = videos_query.order_by(Video.date_added.desc()) # O por popularidad si tuvieras ese dato
        
        total_videos = videos_query.count()
        videos = videos_query.offset((page - 1) * VIDEOS_PER_PAGE).limit(VIDEOS_PER_PAGE).all()
        total_pages = (total_videos + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE
        
        categories_db = db.session.query(Video.category).distinct().order_by(Video.category).all()
        categories = [cat[0] for cat in categories_db if cat[0]]
        
        if total_videos == 0:
            flash(f'No trending videos found for "{current_filter_name}"' + (f' with search term "{search_term}"' if search_term else '.'), 'info')
            
    except Exception as e:
        logger.error(f"Error loading trending videos for '{period}': {e}", exc_info=True)
        flash(f'Error loading trending videos: {str(e)}', 'error')
        return redirect(url_for('rutas.index'))
    
    return render_template('index.html', 
                           videos=videos, 
                           categories=categories, 
                           page=page, 
                           total_pages=total_pages,
                           current_filter=f'Trending: {current_filter_name}',
                           search_term=search_term)

@rutas_bp.route('/random')
def random_video():
    if not session.get('age_verified'):
        return redirect(url_for('rutas.age_gate', next=request.url))
    
    try:
        random_video = Video.query.order_by(func.random()).first() # func.random() puede ser ineficiente en BD grandes
        if random_video:
            return redirect(url_for('rutas.ver_video', video_id=random_video.id))
        else:
            flash('No videos available to display a random one.', 'info')
            return redirect(url_for('rutas.index'))
    except Exception as e:
        logger.error(f"Error getting random video: {e}", exc_info=True)
        flash('Error trying to get a random video.', 'error')
        return redirect(url_for('rutas.index'))

@rutas_bp.route('/video/<int:video_id>')
def ver_video(video_id):
    if not session.get('age_verified'):
        return redirect(url_for('rutas.age_gate', next=request.url))
    
    try:
        video = db.session.get(Video, video_id) # Usar db.session.get() es más directo para PK
        if not video:
            flash('Video not found.', 'error')
            return redirect(url_for('rutas.index')) # O render_template('errors/404.html'), 404

        related_videos_query = Video.query.filter(
            Video.category == video.category,
            Video.id != video.id
        ).order_by(Video.date_added.desc()).limit(6)
        related_videos = related_videos_query.all()
        
        categories_db = db.session.query(Video.category).distinct().order_by(Video.category).all()
        categories = [cat[0] for cat in categories_db if cat[0]]
        
    except Exception as e:
        logger.error(f"Error loading video page for ID {video_id}: {e}", exc_info=True)
        flash('Error loading video page.', 'error')
        return redirect(url_for('rutas.index'))
        
    return render_template('ver_video.html', 
                           video=video,
                           related_videos=related_videos,
                           categories=categories)

# --- Admin Routes ---
@rutas_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if is_admin():
        return redirect(url_for('rutas.admin_panel'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('admin_login.html') 
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['admin'] = True
            session.permanent = True
            flash('Login successful.', 'success')
            return redirect(url_for('rutas.admin_panel'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('admin_login.html')


@rutas_bp.route('/admin/logout')
def admin_logout():
    if not is_admin():
        return redirect(url_for('rutas.index'))
    session.pop('admin', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('rutas.admin_login'))

@rutas_bp.route('/admin')
def admin_panel():
    if not is_admin():
        return redirect(url_for('rutas.admin_login'))
    try:
        videos = Video.query.order_by(Video.date_added.desc()).all()
        current_year = datetime.utcnow().year
    except Exception as e:
        logger.error(f"Error loading admin panel: {e}", exc_info=True)
        flash('Error loading data for admin panel.', 'error')
        videos = []
        current_year = datetime.utcnow().year
    return render_template('admin_panel.html', videos=videos, now={'year': current_year})


@rutas_bp.route('/admin/scrape', methods=['POST'])
def admin_scrape():
    if not is_admin():
        flash('Unauthorized access.', 'error')
        return redirect(url_for('rutas.admin_login'))
    try:
        max_videos_str = request.form.get('max_videos', '20')
        if not max_videos_str.isdigit() or not (1 <= int(max_videos_str) <= 200) :
            flash('Maximum videos must be an integer between 1 and 200.', 'error')
            return redirect(url_for('rutas.admin_panel'))
        max_videos = int(max_videos_str)
    except ValueError:
        flash('Invalid value for maximum videos.', 'error')
        return redirect(url_for('rutas.admin_panel'))
    logger.info(f"ADMIN: Starting scrape for up to {max_videos} videos.")
    try:
        videos_data = scrape_videos_multisite(max_videos=max_videos)
        if videos_data:
            saved_count = save_videos_to_db(videos_data)
            if saved_count > 0: flash(f'{saved_count} new videos collected and saved successfully!', 'success')
            elif len(videos_data) > 0 : flash(f'{len(videos_data)} videos were collected, but no new videos were saved (possibly duplicates or already existing).', 'info')
            else: flash('No videos were collected in this session.', 'info')
        else: flash('Could not collect videos. Check logs for more details.', 'warning')
    except Exception as e:
        logger.error(f"ADMIN: Error during scraping process: {e}", exc_info=True)
        flash(f'Critical error during scraping: {str(e)}. Check logs.', 'error')
    return redirect(url_for('rutas.admin_panel'))

@rutas_bp.route('/admin/fix-video-urls', methods=['POST'])
def admin_fix_video_urls():
    if not is_admin():
        flash('Acceso no autorizado.', 'error')
        return redirect(url_for('rutas.admin_login'))
    
    try:
        videos = Video.query.all()
        fixed_count = 0
        error_count = 0
        
        for video in videos:
            try:
                # Intentar generar una URL válida usando la URL de embed original
                if video.original_cleaned_url:
                    new_url = generate_video_player_url(video.original_cleaned_url, video.source)
                    if new_url:
                        video.embed_url = new_url
                        fixed_count += 1
                        continue
                
                # Si no funciona, intentar con la URL de la página original
                if video.original_page_url:
                    new_url = generate_video_player_url(video.original_page_url, video.source)
                    if new_url:
                        video.embed_url = new_url
                        fixed_count += 1
                        continue
                
                error_count += 1
                logger.warning(f"No se pudo generar una URL válida para el video ID {video.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error al procesar video ID {video.id}: {e}")
        
        if fixed_count > 0:
            db.session.commit()
            flash(f'Se corrigieron {fixed_count} URLs de videos. {error_count} videos no pudieron ser corregidos.', 'success')
        else:
            flash(f'No se pudieron corregir URLs. {error_count} videos con error.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al corregir URLs de videos: {e}")
        flash('Error al intentar corregir las URLs de los videos.', 'error')
    
    return redirect(url_for('rutas.admin_panel'))

@rutas_bp.route('/admin/delete-videos', methods=['POST'])
def admin_delete_videos():
    if not is_admin():
        flash('Unauthorized access.', 'error')
        return redirect(url_for('rutas.admin_login'))
    video_ids_to_delete = request.form.getlist('video_ids')
    if not video_ids_to_delete:
        flash('No videos selected for deletion.', 'warning')
        return redirect(url_for('rutas.admin_panel'))
    try:
        deleted_count = 0
        for video_id_str in video_ids_to_delete:
            try:
                video_id = int(video_id_str)
                video = db.session.get(Video, video_id)
                if video:
                    db.session.delete(video)
                    deleted_count += 1
            except ValueError: logger.warning(f"ADMIN: Invalid video ID received for deletion: {video_id_str}")
        if deleted_count > 0:
            db.session.commit()
            flash(f'{deleted_count} video(s) deleted successfully.', 'success')
        else: flash('No videos were deleted (IDs might be invalid or already deleted).', 'info')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ADMIN: Error deleting videos: {e}", exc_info=True)
        flash(f'Error deleting videos: {str(e)}', 'error')
    return redirect(url_for('rutas.admin_panel'))

@rutas_bp.route('/admin/delete-single-video', methods=['POST'])
def admin_delete_single_video():
    if not is_admin():
        flash('Unauthorized access.', 'error')
        return redirect(url_for('rutas.admin_login'))
    video_id_str = request.form.get('video_id')
    if not video_id_str:
        flash('No video ID provided for deletion.', 'error')
        return redirect(url_for('rutas.admin_panel'))
    try:
        video_id = int(video_id_str)
        video = db.session.get(Video, video_id)
        if video:
            video_title = video.title
            db.session.delete(video)
            db.session.commit()
            flash(f'Video "{video_title}" deleted successfully.', 'success')
        else: flash(f'Video with ID {video_id} not found. Could not delete.', 'warning')
    except ValueError:
        logger.warning(f"ADMIN: Invalid video ID received for single deletion: {video_id_str}")
        flash('Invalid video ID.', 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ADMIN: Error deleting single video (ID: {video_id_str}): {e}", exc_info=True)
        flash(f'Error deleting video: {str(e)}', 'error')
    return redirect(url_for('rutas.admin_panel'))

@rutas_bp.route('/admin/debug/videos')
def debug_videos():
    if not is_admin(): return redirect(url_for('rutas.admin_login'))
    try:
        sample_videos = Video.query.limit(20).all()
        debug_info = [{'id': v.id, 'title': v.title, 'embed_url': v.embed_url, 'category': v.category, 'source': v.source, 'date_added': v.date_added} for v in sample_videos]
        unique_categories_db = db.session.query(Video.category).distinct().order_by(Video.category).all()
        unique_categories = [cat[0] for cat in categories_db if cat[0]]
        total_video_count = Video.query.count()
        # Make sure you have a template at 'app/templates/debug/videos_debug.html'
        return render_template('debug/videos_debug.html', 
                               sample_videos=debug_info,
                               unique_categories=unique_categories,
                               total_videos=total_video_count)
    except Exception as e:
        logger.error(f"Error in video debug route: {e}", exc_info=True)
        flash(f"Error generating debug data: {str(e)}. Check logs.", "error")
        return redirect(url_for('rutas.admin_panel'))

@rutas_bp.route('/admin/test/filter/<filter_type>/<filter_value>')
def test_filter(filter_type, filter_value):
    if not is_admin(): return redirect(url_for('rutas.admin_login'))
    try:
        query = Video.query
        if filter_type == 'quality':
            if filter_value == 'hd': query = query.filter(or_(Video.category.ilike('%HD%'), Video.title.ilike('%HD%'), Video.title.ilike('%720p%'), Video.title.ilike('%1080p%')))
            else: query = query.filter(Video.title.ilike(f'%{filter_value}%'))
        elif filter_type == 'category': query = query.filter(Video.category.ilike(f'%{filter_value}%'))
        videos_found = query.limit(10).all()
        result = [{'id': v.id, 'title': v.title, 'category': v.category, 'source': v.source} for v in videos_found]
        return f"""<h2>Test Filter: {filter_type} = {filter_value}</h2><p>Results (max 10): {len(result)}</p><pre>{result if result else 'No videos found.'}</pre><p><a href="{url_for('rutas.admin_panel')}">Back to admin</a></p>"""
    except Exception as e:
        logger.error(f"Error in test_filter ({filter_type}/{filter_value}): {e}", exc_info=True)
        return f"Error in test filter: {str(e)} <br><a href='{url_for('rutas.admin_panel')}'>Back to admin</a>", 500

