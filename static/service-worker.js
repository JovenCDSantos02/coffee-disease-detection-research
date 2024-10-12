self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('coffee-doctor-cache').then((cache) => {
            return cache.addAll([
                '/', 
                '/tools.html', 
                '/resource.html', 
                '/recordedResults.html', 
                '/admin.html',
                '/detail/', 
                '/search', 
                
                '/static/assets/css/nav.css',

                '/static/assets/images/logo.png',
                '/static/assets/images/anthracnose.png',
                '/static/assets/images/brown_eye.png',
                '/static/assets/images/download-icon.png',
                '/static/assets/images/healthy.png',
                '/static/assets/images/leaf_rust.png',
                '/static/assets/images/leaf_scale.png',
                '/static/assets/images/mealy_bug.png',
                '/static/assets/images/menu-icon.png',
                '/static/assets/images/twig_borer.png',

                
                '/static/assets/js/circle-menu.js',
                
            ]);
        })
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
