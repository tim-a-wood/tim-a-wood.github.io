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

    const boundsCache = new Map();
    const staticDisplayCache = new Map();
    const animatedDisplayCache = new Map();

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
        if (boundsCache.has(src)) return boundsCache.get(src);
        const image = await loadImage(src);
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d", { willReadFrequently: true });
        if (!context) {
            const fallback = {
                image,
                bounds: { x: 0, y: 0, width: image.naturalWidth, height: image.naturalHeight, bottomPad: 0 },
            };
            boundsCache.set(src, fallback);
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
        boundsCache.set(src, result);
        return result;
    }

    async function getStaticDisplay(src) {
        if (staticDisplayCache.has(src)) return staticDisplayCache.get(src);
        const { image, bounds } = await getBounds(src);
        const width = Math.max(1, bounds.width);
        const height = Math.max(1, bounds.height);
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        canvas.width = width;
        canvas.height = height;
        if (context) {
            context.clearRect(0, 0, width, height);
            context.imageSmoothingEnabled = false;
            context.drawImage(
                image,
                bounds.x,
                bounds.y,
                bounds.width,
                bounds.height,
                0,
                0,
                width,
                height
            );
        }
        const result = {
            width,
            height,
            displayUrl: canvas.toDataURL("image/png"),
        };
        staticDisplayCache.set(src, result);
        return result;
    }

    async function getAnimatedDisplay(frameSources) {
        const key = frameSources.join("|");
        if (animatedDisplayCache.has(key)) return animatedDisplayCache.get(key);
        const prepared = await Promise.all(frameSources.map((src) => getBounds(src)));
        const width = Math.max(...prepared.map((item) => Math.max(1, item.bounds.width)));
        const height = Math.max(...prepared.map((item) => Math.max(1, item.bounds.height)));
        const frames = prepared.map(({ image, bounds }) => {
            const canvas = document.createElement("canvas");
            const context = canvas.getContext("2d");
            canvas.width = width;
            canvas.height = height;
            if (context) {
                context.clearRect(0, 0, width, height);
                context.imageSmoothingEnabled = false;
                const dx = Math.round((width - bounds.width) / 2);
                const dy = height - bounds.height;
                context.drawImage(
                    image,
                    bounds.x,
                    bounds.y,
                    bounds.width,
                    bounds.height,
                    dx,
                    dy,
                    bounds.width,
                    bounds.height
                );
            }
            return canvas.toDataURL("image/png");
        });
        const result = { width, height, frames };
        animatedDisplayCache.set(key, result);
        return result;
    }

    async function applyFit(node) {
        const stage = node.closest(".marketing-stage");
        if (!stage) return;
        const sourceWidth = Number(node.dataset.displayWidth || "0");
        const sourceHeight = Number(node.dataset.displayHeight || "0");
        if (!sourceWidth || !sourceHeight) return;

        try {
            const stageWidth = stage.clientWidth;
            const stageHeight = stage.clientHeight;
            if (!stageWidth || !stageHeight) return;

            const fitHeight = Math.max(0.4, Math.min(0.95, Number(node.dataset.fitHeight || "0.82")));
            const availableHeight = stageHeight * fitHeight;
            const availableWidth = stageWidth * 0.68;
            const scale = Math.min(availableHeight / sourceHeight, availableWidth / sourceWidth);
            const renderedWidth = Math.round(sourceWidth * scale);
            const renderedHeight = Math.round(sourceHeight * scale);
            const left = Math.round((stageWidth - renderedWidth) / 2);

            node.style.width = `${renderedWidth}px`;
            node.style.height = `${renderedHeight}px`;
            node.style.left = `${left}px`;
            node.style.bottom = `0px`;
        } catch (error) {
            console.warn("Marketing sprite fit failed", node.currentSrc || node.src, error);
        }
    }

    function refreshFits() {
        spriteNodes.forEach((node) => applyFit(node));
    }

    const animatedNodes = Array.from(document.querySelectorAll("[data-frame-prefix]"));
    const animatedNodeSet = new Set(animatedNodes);

    Promise.all(spriteNodes.map(async (node) => {
        if (animatedNodeSet.has(node)) return;
        const src = node.dataset.fitReference || node.currentSrc || node.src;
        if (!src) return;
        const prepared = await getStaticDisplay(src);
        node.dataset.displayWidth = String(prepared.width);
        node.dataset.displayHeight = String(prepared.height);
        node.src = prepared.displayUrl;
    })).then(refreshFits).catch((error) => {
        console.warn("Marketing sprite prep failed", error);
    });

    animatedNodes.forEach(async (node) => {
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

        try {
            const prepared = await getAnimatedDisplay(frameSources);
            node.dataset.displayWidth = String(prepared.width);
            node.dataset.displayHeight = String(prepared.height);
            node.src = prepared.frames[0];
            applyFit(node);
            let frameIndex = 0;
            window.setInterval(() => {
                frameIndex = (frameIndex + 1) % prepared.frames.length;
                node.src = prepared.frames[frameIndex];
            }, frameDelay);
        } catch (error) {
            console.warn("Marketing animation prep failed", frameSources, error);
        }
    });

    window.addEventListener("resize", refreshFits);
})();
