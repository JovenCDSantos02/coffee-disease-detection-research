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
    });
}

// Listen for the beforeinstallprompt event
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault(); // Prevent the mini-info bar from appearing on mobile
    deferredPrompt = e; // Stash the event so it can be triggered later
});

// Function to prompt the user to install the app
function downloadApp() {
    if (deferredPrompt) {
        deferredPrompt.prompt(); // Show the install prompt
        deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                console.log('User accepted the A2HS prompt');
            } else {
                console.log('User dismissed the A2HS prompt');
            }
            deferredPrompt = null; // Clear the prompt once it's been used
        });
    } else {
        alert('This app cannot be installed. Please try again later.');
    }
}
