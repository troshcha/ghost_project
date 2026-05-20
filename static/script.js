/* --------------------------------------------------------
   GLOBAL STATE TRACKED IN JS
   (prevents unnecessary DOM rewrites and memory leaks)
--------------------------------------------------------- */

let lastPage = null;
let lastMediaUrl = null;
let lastMirror = null;

/* --------------------------------------------------------
   UPDATE LOOP
--------------------------------------------------------- */

async function fetchStatus() {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("Network error");
    return await res.json();
}

/* --------------------------------------------------------
   DOM HELPERS
--------------------------------------------------------- */

function setText(id, text) {
    const el = document.getElementById(id);
    if (el && el.innerText !== text) {
        el.innerText = text;
    }
}

function clearNode(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
}

/* --------------------------------------------------------
   PAGE + MIRROR LOGIC
--------------------------------------------------------- */

function applyPage(page) {
    if (page === lastPage) return;

    const map = {
        "1": "mode-one",
        "2": "mode-two",
        "3": "mode-three",
        "4": "mode-four"
    };

    const mode = map[page] || "mode-one";
    document.getElementById("main-body").className = mode;
    lastPage = page;
}

function applyMirror(mirror) {
    if (mirror === lastMirror) return;

    const wrapper = document.querySelector(".mirror-wrapper");
    if (!wrapper) return;

    if (mirror === true || mirror === "true") {
        wrapper.classList.add("active-mirror");
    } else {
        wrapper.classList.remove("active-mirror");
    }

    lastMirror = mirror;
}

/* --------------------------------------------------------
   MEDIA HANDLING (PAGE 4)
--------------------------------------------------------- */

function updateMedia(type, url) {
    if (lastMediaUrl === url) return;

    const container = document.getElementById("media-container");
    if (!container) return;

    lastMediaUrl = url;

    clearNode(container);

    if (!url) return;

    if (type === "image") {
        const img = document.createElement("img");
        img.src = url;
        container.appendChild(img);
    }

    else if (type === "video") {
        const video = document.createElement("video");
        video.src = url;
        video.autoplay = true;
        video.loop = true;
        video.muted = true;
        container.appendChild(video);
    }

    else if (type === "youtube") {
        const iframe = document.createElement("iframe");
        iframe.src = `https://www.youtube.com/embed/${url}?autoplay=1&mute=1&controls=0&loop=1&playlist=${url}&modestbranding=1`;
        iframe.allow = "autoplay";
        container.appendChild(iframe);
    }
}

/* --------------------------------------------------------
   MAIN UI UPDATE
--------------------------------------------------------- */

function updateUI(data) {
    applyPage(data.page);
    applyMirror(data.mirror);

    /* PAGE 1 */
    setText("p1-name", data.name);
    setText("p1-time", data.time);
    setText("p1-stats", `${data.cpu} | ${data.ram}`);

    /* PAGE 2 */
    setText("p2-time", data.time);

    /* PAGE 3 */
    setText("p3-name", data.name);
    setText("p3-time", data.time);
    setText("p3-cpu", data.cpu);
    setText("p3-ram", data.ram);

    /* PAGE 4 */
    if (data.page === "4") {
        updateMedia(data.content_type, data.content_url);
    }
}

/* --------------------------------------------------------
   SAFE UPDATE LOOP
--------------------------------------------------------- */

async function updateLoop() {
    try {
        const data = await fetchStatus();
        updateUI(data);
    } catch (err) {
        console.error("Update error:", err);
    }
}

setInterval(updateLoop, 1000);
updateLoop();
