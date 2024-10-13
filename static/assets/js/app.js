let deferredPrompt;

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/service-worker.js')
            .then((registration) => {
                console.log('Service Worker registered with scope:', registration.scope);
            })
            .catch((error) => {
                console.error('Service Worker registration failed:', error);
            });

        if (window.matchMedia('(display-mode: standalone)').matches) {
            const downloadCircle = document.querySelector('.download-circle');
            if (downloadCircle) {
                downloadCircle.style.display = 'none';
            }
        }
    });
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault(); 
    deferredPrompt = e;

    const downloadCircle = document.querySelector('.download-circle');
    if (downloadCircle) {
        downloadCircle.style.display = 'flex';
    }
});

function downloadApp() {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                console.log('User accepted the A2HS prompt');
            } else {
                console.log('User dismissed the A2HS prompt');
            }
            deferredPrompt = null;

            const downloadCircle = document.querySelector('.download-circle');
            if (downloadCircle) {
                downloadCircle.style.display = 'none';
            }
        });
    } else {
        alert('This app cannot be installed. Please try again later.');
    }
}
