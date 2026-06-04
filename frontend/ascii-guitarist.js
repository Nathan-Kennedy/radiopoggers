(() => {
  "use strict";

  const config = window.RADIOPOGGERS_CONFIG || {};
  const colorMode = config.asciiColorMode === "mono" ? "mono" : "color";

  const CELL = 6;
  const FRAME_MS = 100;
  const PLAY_FRAMES_URL = "assets/ascii-frames.json";
  const IDLE_FRAMES_URL = "assets/ascii-frames%20sentado.json";
  const OFF_FRAMES_URL = "assets/ascii-frames%20off.json";
  const MIKU_FRAMES_URL = "assets/ascii-frames%20falando.json";
  const HOSHINO_CAPTION_FRAMES_URL = "assets/ascii-frames%20hoshino%20falando.json";
  const PICKER_MIKU_FRAMES_URL = "assets/ascii-frames%20miku.json";
  const PICKER_HOSHINO_FRAMES_URL = "assets/ascii-frames%20hoshino.json";
  const OFF_GIF_URL = "assets/ascii-animation%20off.gif";
  const MIKU_CELL = 3;
  const PICKER_CELL = 4;

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

  const CHIBI = {
    outline: "#d62882",
    accent: "#ff5ca8",
    fill: "#ffb6c1",
    highlight: "#fff8ff",
    soft: "#ff9ecf"
  };

  let playAnimator = null;
  let idleAnimator = null;
  let offAnimator = null;
  let mikuAnimator = null;
  let hoshinoCaptionAnimator = null;
  let pickerMikuAnimator = null;
  let pickerHoshinoAnimator = null;
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
    const height = cropped[0].length;
    const width = cropped[0].reduce((max, row) => Math.max(max, row.length), 0);
    const frames = cropped.map((grid) =>
      grid.map((row) => {
        if (row.length < width) {
          return row.concat(Array(width - row.length).fill(" "));
        }
        return row;
      })
    );

    return { frames, width, height };
  }

  function colorMono(ch, tick) {
    const lum = LUM[ch];
    if (lum === undefined || lum < 0.05) {
      return null;
    }

    const pulse = Math.sin(tick * 0.06) * 2;
    const light = 18 + lum * 72 + pulse;
    const hue = 312 + lum * 8;
    return `hsl(${hue}, ${28 + lum * 22}%, ${light}%)`;
  }

  function colorChibi(ch) {
    const lum = LUM[ch];
    if (lum === undefined || lum < 0.05) {
      return null;
    }

    if (lum >= 0.84) {
      return CHIBI.outline;
    }
    if (lum >= 0.72) {
      return CHIBI.outline;
    }
    if (lum >= 0.58) {
      return CHIBI.accent;
    }
    if (lum >= 0.44) {
      return CHIBI.soft;
    }
    if (lum >= 0.28) {
      return CHIBI.fill;
    }
    return CHIBI.highlight;
  }

  function colorForChar(ch, tick) {
    return colorMode === "mono" ? colorMono(ch, tick) : colorChibi(ch);
  }

  function buildAnimator(rawFrames, cellSize = CELL) {
    const { frames, width, height } = normalizeFrames(rawFrames);
    const font = `${cellSize}px "Cascadia Mono","Consolas","Courier New",monospace`;

    function paint(canvas, tick) {
      if (!canvas || !frames.length) {
        return;
      }

      const frameIndex = tick % frames.length;
      const grid = frames[frameIndex];
      const canvasW = width * cellSize;
      const canvasH = height * cellSize;
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
      ctx.font = font;
      ctx.textBaseline = "top";

      for (let y = 0; y < height; y += 1) {
        for (let x = 0; x < width; x += 1) {
          const ch = grid[y][x];
          const color = colorForChar(ch, tick);
          if (!color) {
            continue;
          }
          ctx.fillStyle = color;
          ctx.fillText(ch, x * cellSize, y * cellSize);
        }
      }
    }

    return { paint, frames };
  }

  async function loadFrames(url, cellSize = CELL) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`${url} HTTP ${response.status}`);
    }

    const data = await response.json();
    if (!Array.isArray(data) || !data.length) {
      throw new Error(`${url} vazio ou invalido`);
    }

    return buildAnimator(data, cellSize);
  }

  async function loadArt() {
    if (playAnimator && idleAnimator && offAnimator && mikuAnimator) {
      return;
    }

    if (loadPromise) {
      return loadPromise;
    }

    loadPromise = Promise.all([
      loadFrames(PLAY_FRAMES_URL),
      loadFrames(IDLE_FRAMES_URL),
      loadFrames(OFF_FRAMES_URL),
      loadFrames(MIKU_FRAMES_URL, MIKU_CELL),
      loadFrames(HOSHINO_CAPTION_FRAMES_URL, MIKU_CELL),
      loadFrames(PICKER_MIKU_FRAMES_URL, PICKER_CELL),
      loadFrames(PICKER_HOSHINO_FRAMES_URL, PICKER_CELL)
    ]).then(([play, idle, off, miku, hoshinoCaption, pickerMiku, pickerHoshino]) => {
      playAnimator = play;
      idleAnimator = idle;
      offAnimator = off;
      mikuAnimator = miku;
      hoshinoCaptionAnimator = hoshinoCaption;
      pickerMikuAnimator = pickerMiku;
      pickerHoshinoAnimator = pickerHoshino;
    });

    return loadPromise;
  }

  function paintPlay(canvas, tick) {
    if (playAnimator) {
      playAnimator.paint(canvas, tick);
    }
  }

  function paintIdle(canvas, tick) {
    if (idleAnimator) {
      idleAnimator.paint(canvas, tick);
    }
  }

  function paintOff(canvas, tick) {
    if (offAnimator) {
      offAnimator.paint(canvas, tick);
    }
  }

  function paintMiku(canvas, tick) {
    if (mikuAnimator) {
      mikuAnimator.paint(canvas, tick);
    }
  }

  function paintHoshinoCaption(canvas, tick) {
    if (hoshinoCaptionAnimator) {
      hoshinoCaptionAnimator.paint(canvas, tick);
    }
  }

  function paintPickerMiku(canvas, tick) {
    if (pickerMikuAnimator) {
      pickerMikuAnimator.paint(canvas, tick);
    }
  }

  function paintPickerHoshino(canvas, tick) {
    if (pickerHoshinoAnimator) {
      pickerHoshinoAnimator.paint(canvas, tick);
    }
  }

  window.RADIOPOGGERS_ASCII_FRAMES = [];
  window.RADIOPOGGERS_ASCII_FRAME_MS = FRAME_MS;
  window.RADIOPOGGERS_ASCII_COLOR_MODE = colorMode;
  window.RADIOPOGGERS_ASCII_OFF_GIF_URL = OFF_GIF_URL;
  window.RADIOPOGGERS_ASCII_INIT = loadArt;
  window.RADIOPOGGERS_ASCII_PAINT = paintPlay;
  window.RADIOPOGGERS_ASCII_PLAY_PAINT = paintPlay;
  window.RADIOPOGGERS_ASCII_IDLE_PAINT = paintIdle;
  window.RADIOPOGGERS_ASCII_OFF_PAINT = paintOff;
  window.RADIOPOGGERS_ASCII_MIKU_PAINT = paintMiku;
  window.RADIOPOGGERS_ASCII_HOSHINO_CAPTION_PAINT = paintHoshinoCaption;
  window.RADIOPOGGERS_ASCII_PICKER_MIKU_PAINT = paintPickerMiku;
  window.RADIOPOGGERS_ASCII_PICKER_HOSHINO_PAINT = paintPickerHoshino;
  window.RADIOPOGGERS_ASCII_MIKU_FRAME_MS = FRAME_MS;
  window.RADIOPOGGERS_ASCII_GENERATE = null;
})();
