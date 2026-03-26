(function initSiteNav() {
    const VIEWS = { home: "view-home", workbench: "view-workbench", docs: "view-docs" };

    function activateView(name) {
        const viewId = VIEWS[name] || VIEWS.workbench;
        document.querySelectorAll(".site-view").forEach((el) => el.classList.remove("active"));
        document.querySelectorAll(".site-nav-link").forEach((el) => el.classList.remove("active"));
        const view = document.getElementById(viewId);
        if (view) view.classList.add("active");
        document.querySelectorAll(`[data-nav="${name}"]`).forEach((el) => {
            if (el.classList.contains("site-nav-link")) el.classList.add("active");
        });
        window.scrollTo({ top: 0, behavior: "instant" });
    }

    document.addEventListener("click", (e) => {
        const el = e.target.closest("[data-nav]");
        if (!el) return;
        e.preventDefault();
        activateView(el.dataset.nav);
    });
})();

(function initMarketingSprites() {
    const spriteNodes = Array.from(document.querySelectorAll("[data-marketing-fit-sprite]"));
    if (!spriteNodes.length) return;

    const cache = new Map();

    function loadImage(src) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            image.addEventListener("load", () => resolve(image), { once: true });
            image.addEventListener("error", reject, { once: true });
            image.src = src;
            if (image.complete && image.naturalWidth > 0) {
                resolve(image);
            }
        });
    }

    async function getBounds(src) {
        if (cache.has(src)) return cache.get(src);
        const image = await loadImage(src);
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d", { willReadFrequently: true });
        if (!context) {
            const fallback = {
                image,
                bounds: { x: 0, y: 0, width: image.naturalWidth, height: image.naturalHeight, bottomPad: 0 },
            };
            cache.set(src, fallback);
            return fallback;
        }

        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0);
        const { data } = context.getImageData(0, 0, canvas.width, canvas.height);

        let minX = canvas.width;
        let minY = canvas.height;
        let maxX = -1;
        let maxY = -1;

        for (let y = 0; y < canvas.height; y += 1) {
            for (let x = 0; x < canvas.width; x += 1) {
                const alpha = data[(y * canvas.width + x) * 4 + 3];
                if (alpha > 0) {
                    if (x < minX) minX = x;
                    if (y < minY) minY = y;
                    if (x > maxX) maxX = x;
                    if (y > maxY) maxY = y;
                }
            }
        }

        const bounds = (maxX < minX || maxY < minY)
            ? { x: 0, y: 0, width: canvas.width, height: canvas.height, bottomPad: 0 }
            : {
                x: minX,
                y: minY,
                width: maxX - minX + 1,
                height: maxY - minY + 1,
                bottomPad: canvas.height - maxY - 1,
            };
        const result = { image, bounds };
        cache.set(src, result);
        return result;
    }

    async function applyFit(node) {
        const stage = node.closest(".marketing-stage");
        if (!stage) return;
        const referenceSrc = node.dataset.fitReference || node.currentSrc || node.src;
        if (!referenceSrc) return;

        try {
            const { image, bounds } = await getBounds(referenceSrc);
            const stageWidth = stage.clientWidth;
            const stageHeight = stage.clientHeight;
            if (!stageWidth || !stageHeight) return;

            const targetVisibleHeight = stageHeight * Math.max(0.4, Math.min(0.95, Number(node.dataset.fitHeight || "0.82")));
            const scale = targetVisibleHeight / bounds.height;
            const renderedWidth = image.naturalWidth * scale;
            const renderedHeight = image.naturalHeight * scale;
            const visibleWidth = bounds.width * scale;
            const left = ((stageWidth - visibleWidth) / 2) - (bounds.x * scale);
            const bottom = -(bounds.bottomPad * scale);

            node.style.width = `${renderedWidth}px`;
            node.style.height = `${renderedHeight}px`;
            node.style.left = `${left}px`;
            node.style.bottom = `${bottom}px`;
        } catch (error) {
            console.warn("Marketing sprite fit failed", referenceSrc, error);
        }
    }

    function refreshFits() {
        spriteNodes.forEach((node) => applyFit(node));
    }

    spriteNodes.forEach((node) => {
        if (!node.complete) {
            node.addEventListener("load", () => applyFit(node), { once: true });
        }
    });

    const animatedNodes = Array.from(document.querySelectorAll("[data-frame-prefix]"));
    animatedNodes.forEach((node) => {
        const prefix = node.dataset.framePrefix || "";
        const suffix = node.dataset.frameSuffix || "";
        const frameStart = Math.max(0, Number(node.dataset.frameStart || "0"));
        const frameCount = Math.max(1, Number(node.dataset.frameCount || "1"));
        const framePad = Math.max(0, Number(node.dataset.framePad || "2"));
        const frameDelay = Math.max(120, Number(node.dataset.frameDelay || "700"));
        const frameSources = Array.from({ length: frameCount }, (_, index) => {
            const frameId = String(frameStart + index).padStart(framePad, "0");
            return `${prefix}${frameId}${suffix}`;
        });

        frameSources.forEach((src) => {
            const preload = new Image();
            preload.src = src;
        });

        let frameIndex = 0;
        window.setInterval(() => {
            frameIndex = (frameIndex + 1) % frameSources.length;
            node.src = frameSources[frameIndex];
        }, frameDelay);
    });

    refreshFits();
    window.addEventListener("resize", refreshFits);
})();
