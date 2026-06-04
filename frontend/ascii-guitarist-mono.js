(() => {
  "use strict";

  // Versao monocromatica salva (transparente, paleta HSL rosa suave).
  // Ative com asciiColorMode: "mono" em config.js

  const CELL = 4;
  const FRAME_MS = 100;
  const FONT = `${CELL}px "Cascadia Mono","Consolas","Courier New",monospace`;

  const LUM = {
    " ": 0,
    ".": 0.12,
    ":": 0.22,
    "-": 0.34,
    "=": 0.44,
    "+": 0.48,
    "*": 0.62,
    "#": 0.82,
    "%": 0.88,
    "@": 0.96
  };

  let frames = [];
  let width = 0;
  let height = 0;
  let loadPromise = null;

  function computeCropBox(allFrames) {
    let top = Infinity;
    let bottom = -1;
    let left = Infinity;
    let right = -1;

    allFrames.forEach((frame) => {
      frame.forEach((line, y) => {
        for (let x = 0; x < line.length; x += 1) {
          if (line[x] !== " ") {
            top = Math.min(top, y);
            bottom = Math.max(bottom, y);
            left = Math.min(left, x);
            right = Math.max(right, x);
          }
        }
      });
    });

    if (top === Infinity) {
      return { left: 0, top: 0, right: 0, bottom: 0 };
    }

    return { left, top, right, bottom };
  }

  function cropFrame(frame, box) {
    const cropped = [];
    for (let y = box.top; y <= box.bottom; y += 1) {
      const line = frame[y] || "";
      cropped.push(line.slice(box.left, box.right + 1).split(""));
    }
    return cropped;
  }

  function normalizeFrames(rawFrames) {
    const box = computeCropBox(rawFrames);
    const cropped = rawFrames.map((frame) => cropFrame(frame, box));
    height = cropped[0].length;
    width = cropped[0].reduce((max, row) => Math.max(max, row.length), 0);

    return cropped.map((grid) =>
      grid.map((row) => {
        if (row.length < width) {
          return row.concat(Array(width - row.length).fill(" "));
        }
        return row;
      })
    );
  }

  function colorForChar(ch, tick) {
    const lum = LUM[ch];
    if (lum === undefined || lum < 0.05) {
      return null;
    }

    const pulse = Math.sin(tick * 0.06) * 2;
    const light = 18 + lum * 72 + pulse;
    const hue = 312 + lum * 8;
    return `hsl(${hue}, ${28 + lum * 22}%, ${light}%)`;
  }

  function paintCanvas(canvas, tick) {
    if (!canvas || !frames.length) {
      return;
    }

    const frameIndex = tick % frames.length;
    const grid = frames[frameIndex];
    const canvasW = width * CELL;
    const canvasH = height * CELL;
    const dpr = window.devicePixelRatio || 1;

    if (canvas.width !== canvasW * dpr || canvas.height !== canvasH * dpr) {
      canvas.width = canvasW * dpr;
      canvas.height = canvasH * dpr;
      canvas.style.width = `${canvasW}px`;
      canvas.style.height = `${canvasH}px`;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvasW, canvasH);
    ctx.font = FONT;
    ctx.textBaseline = "top";

    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const ch = grid[y][x];
        const color = colorForChar(ch, tick);
        if (!color) {
          continue;
        }
        ctx.fillStyle = color;
        ctx.fillText(ch, x * CELL, y * CELL);
      }
    }
  }

  async function loadArt() {
    if (frames.length) {
      return;
    }
    if (loadPromise) {
      return loadPromise;
    }

    loadPromise = fetch("assets/ascii-frames.json")
      .then((res) => {
        if (!res.ok) {
          throw new Error(`ascii-frames.json HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        if (!Array.isArray(data) || !data.length) {
          throw new Error("ascii-frames.json vazio ou invalido");
        }
        frames = normalizeFrames(data);
      });

    return loadPromise;
  }

  window.RADIOPOGGERS_ASCII_FRAMES = [];
  window.RADIOPOGGERS_ASCII_FRAME_MS = FRAME_MS;
  window.RADIOPOGGERS_ASCII_INIT = loadArt;
  window.RADIOPOGGERS_ASCII_PAINT = paintCanvas;
  window.RADIOPOGGERS_ASCII_GENERATE = null;
})();
