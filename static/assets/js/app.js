let deferredPrompt;

// Register the service worker when the page loads
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/service-worker.js')
            .then((registration) => {
                console.log('Service Worker registered with scope:', registration.scope);
            })
            .catch((error) => {
                console.error('Service Worker registration failed:', error);
            });

        // Check if the app is in standalone mode on load
        if (window.matchMedia('(display-mode: standalone)').matches) {
            // If in standalone mode, hide the download circle
            const downloadCircle = document.querySelector('.download-circle');
            if (downloadCircle) {
                downloadCircle.style.display = 'none';
            }
        }
    });
}

// Handle the beforeinstallprompt event
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault(); 
    deferredPrompt = e;

    // Show the download circle when ready to install
    const downloadCircle = document.querySelector('.download-circle');
    if (downloadCircle) {
        downloadCircle.style.display = 'flex'; // Show download circle
    }
});

// Function to download the app
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

            // Optionally hide the download circle after installation
            const downloadCircle = document.querySelector('.download-circle');
            if (downloadCircle) {
                downloadCircle.style.display = 'none'; // Hide download circle
            }
        });
    } else {
        alert('This app cannot be installed. Please try again later.');
    }
}
