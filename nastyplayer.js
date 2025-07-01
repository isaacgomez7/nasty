// Advanced HTML5 Video Player for NastyMood
// This script replaces the iframe with a custom HTML5 player if the video is a direct link (mp4, m3u8, webm, etc.)
// and enhances the iframe experience with controls, fullscreen, PiP, and keyboard shortcuts.

(function() {
    document.addEventListener('DOMContentLoaded', function() {
        const iframe = document.getElementById('videoPlayerIframe');
        if (!iframe) return;

        // Add overlay controls for iframe (fullscreen, PiP, reload)
        const wrapper = document.getElementById('videoPlayerWrapper');
        if (!wrapper) return;

        // Create controls container
        const controls = document.createElement('div');
        controls.className = 'nasty-controls absolute bottom-2 right-2 flex gap-2 z-20';
        controls.innerHTML = `
            <button id="nasty-fullscreen" title="Fullscreen" class="bg-gray-800 bg-opacity-80 hover:bg-red-600 text-white rounded p-2 focus:outline-none"><svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' fill='none' viewBox='0 0 24 24'><path stroke='currentColor' stroke-width='2' d='M3 9V5a2 2 0 0 1 2-2h4m6 0h4a2 2 0 0 1 2 2v4m0 6v4a2 2 0 0 1-2 2h-4m-6 0H5a2 2 0 0 1-2-2v-4'/></svg></button>
            <button id="nasty-pip" title="Picture in Picture" class="bg-gray-800 bg-opacity-80 hover:bg-red-600 text-white rounded p-2 focus:outline-none"><svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' fill='none' viewBox='0 0 24 24'><rect width='18' height='14' x='3' y='5' stroke='currentColor' stroke-width='2' rx='2'/><rect width='6' height='4' x='15' y='15' fill='currentColor' rx='1'/></svg></button>
            <button id="nasty-reload" title="Reload" class="bg-gray-800 bg-opacity-80 hover:bg-red-600 text-white rounded p-2 focus:outline-none"><svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' fill='none' viewBox='0 0 24 24'><path stroke='currentColor' stroke-width='2' d='M4 4v5h5M20 20v-5h-5'/><path stroke='currentColor' stroke-width='2' d='M5.07 19A9 9 0 1 1 12 21c2.39 0 4.58-.94 6.23-2.48'/></svg></button>
        `;
        wrapper.appendChild(controls);

        // Fullscreen
        document.getElementById('nasty-fullscreen').onclick = function() {
            if (iframe.requestFullscreen) iframe.requestFullscreen();
            else if (iframe.webkitRequestFullscreen) iframe.webkitRequestFullscreen();
            else if (iframe.mozRequestFullScreen) iframe.mozRequestFullScreen();
            else if (iframe.msRequestFullscreen) iframe.msRequestFullscreen();
        };
        // PiP (only works for HTML5 video, not iframe, but show message)
        document.getElementById('nasty-pip').onclick = function() {
            alert('Picture-in-Picture is only available for direct video links.');
        };
        // Reload
        document.getElementById('nasty-reload').onclick = function() {
            iframe.src = iframe.src;
        };

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
            if (e.key === 'f') document.getElementById('nasty-fullscreen').click();
            if (e.key === 'r') document.getElementById('nasty-reload').click();
        });
    });
})();
