/* --------------------------------------------------------
   GLOBAL STATE TRACKED IN JS
   (prevents unnecessary DOM rewrites and memory leaks)
--------------------------------------------------------- */

let lastPage    = null;
let lastP4Url   = null;
let lastP5Id    = null;

const SKEW_DEG = 8;

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
        "4": "mode-four",
        "5": "mode-five"
    };

    const mode = map[page] || "mode-one";
    document.getElementById("main-body").className = mode;
    lastPage = page;
}

function applyTransform(mirror) {
    const wrapper = document.querySelector(".mirror-wrapper");
    if (!wrapper) return;

    const isMirror = mirror === true || mirror === "true";

    if (!isMirror) {
        wrapper.style.transform = "";
        return;
    }

    wrapper.style.transform = `perspective(1200px) rotateY(${SKEW_DEG}deg) rotate(180deg) scaleX(-1)`;
}

/* --------------------------------------------------------
   MEDIA HANDLING
--------------------------------------------------------- */

function updatePage4Media(type, url) {
    if (lastP4Url === url) return;
    const container = document.getElementById("p4-media");
    if (!container) return;
    lastP4Url = url;
    clearNode(container);
    if (!url) return;
    if (type === "image") {
        const img = document.createElement("img");
        img.src = url;
        img.style.height = "640px";
        img.style.width = "auto";
        img.style.maxWidth = "100%";
        container.appendChild(img);
    } else if (type === "video") {
        const video = document.createElement("video");
        video.src = url;
        video.autoplay = true;
        video.loop = true;
        video.muted = true;
        video.style.maxWidth = "100%";
        video.style.maxHeight = "100%";
        container.appendChild(video);
    }
}

function updatePage5(ytId) {
    if (lastP5Id === ytId) return;
    const container = document.getElementById("p5-media");
    if (!container) return;
    lastP5Id = ytId;
    clearNode(container);
    if (!ytId) return;
    const iframe = document.createElement("iframe");
    iframe.src = `https://www.youtube.com/embed/${ytId}?autoplay=1&mute=1&controls=1&loop=1&playlist=${ytId}&modestbranding=1`;
    iframe.allow = "autoplay; fullscreen";
    container.appendChild(iframe);
}

/* --------------------------------------------------------
   METRIC CARD HELPER (page 3)
   percent      — 0-100 for bar width
   warnAt/critAt — percent thresholds for color change
--------------------------------------------------------- */

function setMetric(valId, barId, label, percent, warnAt, critAt) {
    const color = percent >= critAt ? "#ff3333"
                : percent >= warnAt ? "#ffcc00"
                : "#00ff88";

    const valEl = document.getElementById(valId);
    const barEl = document.getElementById(barId);

    if (valEl) {
        valEl.innerText = label;
        valEl.style.color = color;
    }
    if (barEl) {
        barEl.style.width   = Math.min(percent, 100) + "%";
        barEl.style.background = color;
    }
}

/* --------------------------------------------------------
   MAIN UI UPDATE
--------------------------------------------------------- */

function updateUI(data) {
    applyPage(data.page);
    applyTransform(data.mirror);

    /* PAGE 1 */
    setText("p1-name", data.name);
    setText("p1-time", data.time);
    setText("p1-stats", `CPU: ${data.cpu}%  |  RAM: ${data.ram}%`);

    /* PAGE 2 */
    setText("p2-time", data.time);

    /* PAGE 3 — monitoring dashboard */
    setText("p3-name", data.name);
    setText("p3-date", data.date);
    setText("p3-clock", data.time);
    setText("p3-uptime", data.uptime);
    setText("p3-ip", data.ip);

    setMetric("p3-cpu-val",  "p3-cpu-bar",  `${data.cpu}%`,   data.cpu,              60, 80);
    setMetric("p3-ram-val",  "p3-ram-bar",  `${data.ram}%`,   data.ram,              70, 85);
    setMetric("p3-temp-val", "p3-temp-bar", `${data.temp}°C`, (data.temp / 85) * 100, 76, 88);
    setMetric("p3-disk-val", "p3-disk-bar", `${data.disk}%`,  data.disk,             70, 85);

    /* PAGE 4 */
    if (data.page === "4") {
        const [hh, mm] = data.time.split(":");
        setText("p4-hour", hh);
        setText("p4-min",  mm);
        setMetric("p4-cpu-val", "p4-cpu-bar", `${data.cpu}%`, data.cpu,              60, 80);
        setMetric("p4-ram-val", "p4-ram-bar", `${data.ram}%`, data.ram,              70, 85);
        setMetric("p4-temp-val", "p4-temp-bar", `${data.temp}°C`, (data.temp / 85) * 100, 76, 88);
        setText("p4-uptime", data.uptime);
        updatePage4Media(data.content_type, data.content_url);
    }

    /* PAGE 5 */
    if (data.page === "5") {
        updatePage5(data.yt_id);
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
