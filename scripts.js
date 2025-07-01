console.log("NastyMood scripts loaded");

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM loaded, initializing NastyMood functionality");

    // === NAVEGACIÓN DE VIDEOS ===
    // Mejorar la experiencia de navegación de videos
    document.querySelectorAll('.video-link').forEach(link => {
        link.addEventListener('click', (e) => {
            // Agregar indicador de carga visual
            const card = link.closest('.video-card');
            if (card) {
                card.style.opacity = '0.7';
                card.style.transform = 'scale(0.98)';
            }
            
            // Precargar el video en el background (opcional)
            const videoUrl = link.href;
            if (videoUrl) {
                // Crear un prefetch link para mejorar la carga
                const prefetchLink = document.createElement('link');
                prefetchLink.rel = 'prefetch';
                prefetchLink.href = videoUrl;
                document.head.appendChild(prefetchLink);
            }
        });

        // Efecto hover mejorado
        link.addEventListener('mouseenter', (e) => {
            const img = link.querySelector('img');
            if (img) {
                img.style.transform = 'scale(1.05)';
                img.style.transition = 'transform 0.3s ease';
            }
        });

        link.addEventListener('mouseleave', (e) => {
            const img = link.querySelector('img');
            if (img) {
                img.style.transform = 'scale(1)';
            }
        });
    });

    // === FUNCIONALIDAD DE BÚSQUEDA ===
    const searchInput = document.querySelector('.search-input');
    const searchBtn = document.querySelector('.search-btn');
    
    if (searchInput && searchBtn) {
        // Función para realizar búsqueda
        const performSearch = () => {
            const searchTerm = searchInput.value.trim();
            if (searchTerm) {
                // Mostrar indicador de carga
                searchBtn.textContent = 'Buscando...';
                searchBtn.disabled = true;
                
                // Construir URL de búsqueda correctamente
                const currentUrl = new URL(window.location);
                currentUrl.searchParams.set('search', searchTerm);
                currentUrl.searchParams.delete('page'); // Resetear página al buscar
                
                window.location.href = currentUrl.toString();
            } else {
                // Si no hay término, limpiar búsqueda
                const currentUrl = new URL(window.location);
                currentUrl.searchParams.delete('search');
                currentUrl.searchParams.delete('page');
                window.location.href = currentUrl.toString();
            }
        };

        // Evento click del botón
        searchBtn.addEventListener('click', performSearch);

        // Evento Enter en el input
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });

        // Limpiar búsqueda con Escape
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                searchInput.value = '';
                searchInput.blur();
            }
        });

        // Auto-completar/sugerencias (opcional)
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();
            
            if (query.length >= 2) {
                searchTimeout = setTimeout(() => {
                    // Aquí podrías implementar sugerencias de búsqueda
                    console.log('Searching for:', query);
                }, 300);
            }
        });
    }

    // === PAGINACIÓN MEJORADA ===
    const paginationLinks = document.querySelectorAll('.pagination a');
    paginationLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            // Agregar efecto de carga
            link.style.opacity = '0.6';
            link.textContent = 'Cargando...';
        });
    });

    // === LAZY LOADING PARA IMÁGENES ===
    const lazyImages = document.querySelectorAll('img[data-src]');
    if (lazyImages.length > 0) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    observer.unobserve(img);
                }
            });
        });

        lazyImages.forEach(img => imageObserver.observe(img));
    }

    // === MANEJO DE ERRORES DE IMÁGENES ===
    document.querySelectorAll('img').forEach(img => {
        img.addEventListener('error', (e) => {
            console.warn('Error loading image:', e.target.src);
            // Imagen placeholder por defecto
            e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNHB4IiBmaWxsPSIjOTk5OTk5IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+SW1hZ2VuIG5vIGRpc3BvbmlibGU8L3RleHQ+PC9zdmc+';
            e.target.alt = 'Imagen no disponible';
        });
    });

    // === SMOOTH SCROLLING ===
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // === BACK TO TOP BUTTON ===
    const createBackToTopButton = () => {
        const button = document.createElement('button');
        button.innerHTML = '⬆️';
        button.className = 'back-to-top';
        button.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            color: white;
            border: none;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            font-size: 20px;
            cursor: pointer;
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 1000;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        `;
        
        document.body.appendChild(button);
        
        // Mostrar/ocultar botón según scroll
        window.addEventListener('scroll', () => {
            if (window.pageYOffset > 300) {
                button.style.opacity = '1';
                button.style.transform = 'scale(1)';
            } else {
                button.style.opacity = '0';
                button.style.transform = 'scale(0.8)';
            }
        });
        
        // Función de scroll hacia arriba
        button.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    };
    
    createBackToTopButton();

    // === TECLADO SHORTCUTS ===
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K para enfocar búsqueda
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        
        // Escape para cerrar modales o limpiar búsqueda
        if (e.key === 'Escape') {
            if (searchInput && document.activeElement === searchInput) {
                searchInput.blur();
            }
        }
    });

    // === ANALYTICS Y TRACKING (OPCIONAL) ===
    const trackVideoClick = (videoTitle, videoSource) => {
        console.log('Video clicked:', videoTitle, 'from', videoSource);
        // Aquí podrías enviar datos a Google Analytics o tu sistema de tracking
        // gtag('event', 'video_click', { video_title: videoTitle, source: videoSource });
    };

    // Agregar tracking a los enlaces de video
    document.querySelectorAll('.video-link').forEach(link => {
        link.addEventListener('click', (e) => {
            const videoTitle = link.querySelector('img')?.alt || 'Unknown';
            const videoSource = link.dataset.source || 'Unknown';
            trackVideoClick(videoTitle, videoSource);
        });
    });

    // === PERFORMANCE MONITORING ===
    console.log('NastyMood scripts fully initialized');
    
    // Reportar tiempo de carga usando la API moderna
    window.addEventListener('load', () => {
        const [entry] = performance.getEntriesByType('navigation');
        if (entry) {
            console.log(`Page loaded in ${entry.duration.toFixed(2)}ms`);
        } else {
            // Fallback para navegadores antiguos
            const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
            console.log(`Page loaded in ${loadTime}ms`);
        }
    });
});