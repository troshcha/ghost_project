async function updateData() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();
        
        // 1. КЕРУВАННЯ СТОРІНКАМИ (МОДАМИ)
        const body = document.getElementById('main-body');
        if (body) {
            const pageMap = { 
                "1": "mode-one", 
                "2": "mode-two", 
                "3": "mode-three", 
                "4": "mode-four" 
            };
            // Встановлюємо клас залежно від значення data.page (дефолт - mode-one)
            body.className = pageMap[data.page] || "mode-one";
        }

        // 2. КЕРУВАННЯ ДЗЕРКАЛОМ (MIRROR)
        const wrapper = document.querySelector('.mirror-wrapper');
        if (wrapper) {
            // Перевіряємо і булеве значення, і рядок (на випадок помилок у JSON)
            if (data.mirror === true || data.mirror === "true") {
                wrapper.classList.add('active-mirror');
            } else {
                wrapper.classList.remove('active-mirror');
            }
        }

        // 3. ДОПОМІЖНА ФУНКЦІЯ ДЛЯ ОНОВЛЕННЯ ТЕКСТУ
        const updateEl = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.innerText = val;
        };

        // 4. ОНОВЛЕННЯ ДАНИХ ДЛЯ ВСІХ СТОРІНОК
        // Сторінка 1
        updateEl('p1-name', data.name);
        updateEl('p1-time', data.time);
        updateEl('p1-stats', `${data.cpu} | ${data.ram}`);

        // Сторінка 2
        updateEl('p2-time', data.time);

        // Сторінка 3 (Консоль)
        updateEl('p3-name', data.name);
        updateEl('p3-time', data.time);
        updateEl('p3-cpu', data.cpu);
        updateEl('p3-ram', data.ram);

       // 5. ЛОГІКА ДЛЯ PAGE 4 (МЕДІА: ФОТО/ВІДЕО/YOUTUBE)
            if (data.page === "4") {
                const mediaContainer = document.getElementById('media-container');
                if (mediaContainer) {
                    const currentUrl = mediaContainer.getAttribute('data-current-url');

                    if (currentUrl !== data.content_url) {
                        mediaContainer.innerHTML = ''; 
                        mediaContainer.setAttribute('data-current-url', data.content_url);

                        if (data.content_type === "image") {
                            mediaContainer.innerHTML = `<img src="${data.content_url}" style="max-width:100%; max-height:100%;">`;
                        } 
                        else if (data.content_type === "video") {
                            // muted: true — гарантує автозапуск без помилок
                            const video = document.createElement('video');
                            video.src = data.content_url;
                            video.autoplay = true;
                            video.loop = true;
                            video.muted = true; 
                            video.style.maxWidth = "100%";
                            mediaContainer.appendChild(video);
                        }
                        else if (data.content_type === "youtube") {
                            const iframe = document.createElement('iframe');
                            // Додаємо playlist=${data.content_url}, щоб loop=1 реально працював
                            iframe.src = `https://www.youtube.com/embed/${data.content_url}?autoplay=1&mute=1&controls=0&loop=1&playlist=${data.content_url}&modestbranding=1&iv_load_policy=3`;
                            iframe.style.width = "100vw";
                            iframe.style.height = "100vh";
                            iframe.style.border = "none";
                            mediaContainer.appendChild(iframe);
                        }
                    }
                }
            }

    } catch (e) {
        console.error("Помилка оновлення даних:", e);
    }
}

// Запуск циклу: кожну секунду (1000 мс)
setInterval(updateData, 1000);

// Перший запуск одразу при завантаженні сторінки
updateData();