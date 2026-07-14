/* ============================================================
   贡柑病虫害检测 — Service Worker
   缓存策略：
   - 静态资源（CSS/JS/图标）：Cache First（安装时预缓存）
   - 页面本身：Network First（保证最新）
   - API 请求：Network Only（不缓存模型结果）
   ============================================================ */

const CACHE_NAME = 'gonggan-v1.0';
const STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/main.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/manifest.json',
];

// ── 安装：预缓存静态资源 ──
self.addEventListener('install', (event) => {
    console.log('[SW] 安装中，缓存静态资源...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch((err) => {
                console.warn('[SW] 部分资源缓存失败（可忽略）:', err);
            });
        })
    );
    // 立即激活，不等旧 SW 释放
    self.skipWaiting();
});

// ── 激活：清理旧缓存 ──
self.addEventListener('activate', (event) => {
    console.log('[SW] 激活');
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
            );
        })
    );
    // 立即接管所有页面
    self.clients.claim();
});

// ── 请求拦截：不同资源不同策略 ──
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API 请求：Network Only（模型推理结果不缓存）
    if (url.pathname.startsWith('/predict') || url.pathname.startsWith('/diseases')) {
        return; // 不拦截，浏览器默认行为 = 直接请求网络
    }

    // 静态资源：Cache First
    if (
        url.pathname.startsWith('/static/') ||
        url.pathname.endsWith('.css') ||
        url.pathname.endsWith('.js') ||
        url.pathname.endsWith('.png')
    ) {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                return cached || fetch(event.request).then((response) => {
                    // 顺便更新缓存
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    return response;
                });
            })
        );
        return;
    }

    // HTML 页面：Network First（保证最新），离线时降级到缓存
    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});

console.log('[SW] 贡柑病虫害检测 — Service Worker 已就绪');
