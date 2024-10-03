self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('coffee-doctor-cache').then((cache) => {
            return cache.addAll([
                '/',
                '/tools.html',
                '/resource.html',
                '/static/assets/css/header.css',
                '/static/assets/css/main.css',
                '/static/assets/css/tools.css',
                '/static/assets/images/logo.png',
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
