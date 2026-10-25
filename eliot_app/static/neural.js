"use strict";
/*
 * Eliot's presence — emotional state machine and renderer selection.
 *
 * Decorative only. Every expressive parameter is derived from *recorded*
 * backend state that the workspace already displays. Nothing here reveals
 * model internals, prompt text, evidence or provider data.
 *
 * Renderers, in order of preference:
 *   1. the cinematic multi-pass WebGL2 core (eliot-core.js)
 *   2. the original 2D canvas core, retained verbatim as a fallback
 *
 * The pause control, prefers-reduced-motion, tab visibility and viewport
 * intersection are all honoured, exactly as before.
 */
(() => {
  const canvas = document.getElementById("neural-canvas"),
    control = document.getElementById("motion-toggle");
  if (!canvas || !control) return;

  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let preference = null;
  try {
    preference = localStorage.getItem("eliot-motion");
  } catch {}
  let paused = preference ? preference === "paused" : reduced.matches;

  let width = 1,
    height = 1,
    ratio = 1,
    visible = true,
    frame = 0,
    last = 0;

  // -------------------------------------------------------------- emotions
  // Each state is a complete expressive pose. Transitions are smoothed, so
  // Eliot eases between feelings rather than snapping between them.
  const EMOTIONS = {
    // Calm, cool, slow. Waiting without appearing inert.
    idle: {
      energy: 0.3, think: 0.0, talk: 0.0, alert: 0.0, speed: 0.55,
      color: [0.42, 0.78, 0.9], accent: [0.2, 0.45, 0.7],
      label: "IDLE · AWAITING INPUT",
    },
    // Inward and concentrated: streams spiral toward the nucleus.
    thinking: {
      energy: 0.66, think: 1.0, talk: 0.0, alert: 0.0, speed: 1.05,
      color: [0.55, 0.62, 0.98], accent: [0.42, 0.3, 0.85],
      label: "THINKING · FORMING RESPONSE",
    },
    // Outward and rhythmic: shells pulse in time with the response.
    talking: {
      energy: 0.84, think: 0.22, talk: 1.0, alert: 0.0, speed: 1.0,
      color: [0.76, 0.95, 1.0], accent: [0.35, 0.78, 0.95],
      label: "RESPONDING · STREAMING",
    },
    // Hot, fast, driven. Sustained investigation.
    working: {
      energy: 1.0, think: 0.45, talk: 0.15, alert: 0.12, speed: 1.75,
      color: [0.85, 0.97, 1.0], accent: [0.3, 0.72, 0.95],
      label: "ACTIVE · PROCESSING SIGNALS",
    },
    // Unsettled: angular wedges and tearing. Something needs a human.
    alert: {
      energy: 0.8, think: 0.2, talk: 0.0, alert: 1.0, speed: 1.3,
      color: [0.98, 0.72, 0.36], accent: [0.95, 0.4, 0.26],
      label: "PAUSED · INPUT REQUIRED",
    },
  };

  // Live, smoothed pose handed to the renderer each frame.
  const feel = {
    time: 0.42, energy: 0.3, think: 0, talk: 0, alert: 0, pulse: 0,
    color: [0.42, 0.78, 0.9], accent: [0.2, 0.45, 0.7], quality: 1,
  };
  let speed = 0.55,
    // Null so the very first frame publishes the idle pose, label and tint
    // rather than assuming the document already reflects it.
    current = null;

  // Emotion is derived from state the workspace already records:
  //   data-activity : idle | working | attention   (missions and runs)
  //   data-speech   : thinking | talking           (the active response)
  function intended() {
    const body = document.body;
    const activity = body.dataset.activity || "idle";
    const speech = body.dataset.speech || "";
    if (activity === "attention") return "alert";
    if (speech === "talking") return "talking";
    if (speech === "thinking") return "thinking";
    if (activity === "working") return "working";
    return "idle";
  }

  function approach(now) {
    const name = intended();
    if (name !== current) {
      current = name;
      const state = document.getElementById("core-state");
      if (state) state.textContent = EMOTIONS[name].label;
      document.body.dataset.emotion = name;
    }
    const want = EMOTIONS[name];
    // Critically damped easing. Colour eases more slowly than motion, which
    // keeps hue shifts from looking like a hard cut.
    const k = Math.min(now * 0.0042, 1);
    const kc = Math.min(now * 0.0022, 1);
    feel.energy += (want.energy - feel.energy) * k;
    feel.think += (want.think - feel.think) * k;
    feel.talk += (want.talk - feel.talk) * k;
    feel.alert += (want.alert - feel.alert) * k;
    speed += (want.speed - speed) * k;
    for (let i = 0; i < 3; i++) {
      feel.color[i] += (want.color[i] - feel.color[i]) * kc;
      feel.accent[i] += (want.accent[i] - feel.accent[i]) * kc;
    }
  }

  // ------------------------------------------------- renderer construction
  let renderer = null;
  function selectRenderer() {
    if (window.EliotCinematicCore) {
      try {
        renderer = window.EliotCinematicCore.create(canvas);
      } catch {
        renderer = null;
      }
    }
    if (!renderer) {
      try {
        renderer = create2DRenderer(canvas);
      } catch {
        renderer = null;
      }
    }
    return renderer;
  }
  if (!selectRenderer()) {
    canvas.hidden = true;
    control.hidden = true;
    return;
  }
  // A lost GL context must never leave a blank stage.
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    if (renderer && renderer.kind !== "2d") {
      try {
        renderer = create2DRenderer(canvas) || renderer;
      } catch {}
      resize();
    }
  });

  // ============================================================ 2D fallback
  // The original instrument-like core, kept so environments without WebGL2
  // still show an equivalent, tasteful animation.
  function create2DRenderer(cv) {
    const ctx = cv.getContext("2d");
    if (!ctx) return null;
    const rows = 28,
      cols = 52,
      points = [];
    for (let row = 0; row <= rows; row++)
      for (let col = 0; col < cols; col++)
        points.push({ phi: (Math.PI * row) / rows, theta: (2 * Math.PI * col) / cols });
    function project(x, y, z, ph) {
      const a = ph * 0.12,
        ca = Math.cos(a),
        sa = Math.sin(a),
        rx = x * ca - z * sa,
        rz = x * sa + z * ca,
        tilt = 0.27,
        ry = y * Math.cos(tilt) - rz * Math.sin(tilt),
        depth = y * Math.sin(tilt) + rz * Math.cos(tilt),
        scale = 2.9 / (2.9 + depth);
      return { x: 0.51 + rx * scale, y: 0.49 + ry * scale, z: depth };
    }
    const css = (c, a) =>
      `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${a})`;
    return {
      kind: "2d",
      resize() {},
      draw(f) {
        const ph = f.time;
        ctx.clearRect(0, 0, width, height);
        const radius = Math.min(width * 0.34, height * 0.33),
          cx = width * 0.51,
          cy = height * 0.49;
        const glow = ctx.createRadialGradient(cx, cy, radius * 0.13, cx, cy, radius * 1.6);
        glow.addColorStop(0, css(f.color, 0.12 + f.energy * 0.1));
        glow.addColorStop(0.55, css(f.color, 0.05));
        glow.addColorStop(1, css(f.color, 0));
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, width, height);
        const positions = points.map((p) => {
          const ripple =
            1 +
            0.038 * Math.sin(p.theta * 5 + p.phi * 3 + ph) +
            0.018 * Math.sin(p.phi * 12 - ph * 0.7) +
            0.03 * f.talk * Math.sin(p.phi * 9 - ph * 6);
          return project(
            Math.sin(p.phi) * Math.cos(p.theta) * ripple,
            Math.cos(p.phi) * ripple,
            Math.sin(p.phi) * Math.sin(p.theta) * ripple,
            ph,
          );
        });
        const screen = (p) => ({ x: cx + (p.x - cx) * radius, y: cy + (p.y - cy) * radius });
        for (let row = 1; row < rows; row++) {
          ctx.beginPath();
          for (let col = 0; col <= cols; col++) {
            const p = screen(positions[row * cols + (col % cols)]);
            col ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y);
          }
          ctx.strokeStyle = css(f.color, row % 3 === 0 ? 0.17 : 0.09);
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
        for (let col = 0; col < cols; col += 3) {
          ctx.beginPath();
          for (let row = 0; row <= rows; row++) {
            const p = screen(positions[row * cols + col]);
            row ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y);
          }
          ctx.strokeStyle = css(f.color, 0.13);
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
        for (let i = 0; i < positions.length; i++) {
          const p = screen(positions[i]),
            front = (1.4 - positions[i].z) / 2.6;
          ctx.fillStyle = css(f.color, 0.15 + front * 0.6);
          ctx.beginPath();
          ctx.arc(p.x, p.y, 0.35 + front * 0.65, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(-0.43);
        ctx.strokeStyle = css(f.color, 0.19);
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.ellipse(0, 0, radius * 1.31, radius * 0.47, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([1, 7]);
        ctx.beginPath();
        ctx.ellipse(0, 0, radius * 1.42, radius * 1.15, 0.1, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        const orbit = ph * 0.22;
        ctx.fillStyle = css(f.color, 0.95);
        ctx.shadowColor = css(f.color, 1);
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.arc(Math.cos(orbit) * radius * 1.31, Math.sin(orbit) * radius * 0.47, 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.restore();
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(0.66);
        ctx.strokeStyle = css(f.accent, 0.4);
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.ellipse(0, 0, radius * 1.15, radius * 0.86, 0, 1.25, 2.8);
        ctx.stroke();
        ctx.fillStyle = css(f.accent, 0.9);
        ctx.beginPath();
        ctx.arc(Math.cos(2.8) * radius * 1.15, Math.sin(2.8) * radius * 0.86, 1.6, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      },
    };
  }

  // --------------------------------------------------------- the main loop
  // Frame cost is sampled; sustained slow frames drop the shader quality tier
  // once rather than letting the whole workspace feel heavy.
  let slow = 0;
  function animate(now) {
    frame = 0;
    if (paused || document.hidden || !visible) return;
    const dt = Math.min(now - last || 32, 64);
    last = now;
    if (feel.quality > 0.5 && renderer.kind !== "2d") {
      slow = dt > 34 ? slow + 1 : Math.max(0, slow - 1);
      if (slow > 90) feel.quality = 0;
    }
    approach(dt);
    feel.time += dt * 0.001 * speed;
    // Speech cadence: a breathing rhythm that only exists while talking.
    feel.pulse = (feel.pulse + dt * 0.001 * (0.9 + feel.talk * 1.8)) % 1;
    renderer.draw(feel);
    frame = requestAnimationFrame(animate);
  }
  function schedule() {
    cancelAnimationFrame(frame);
    frame = 0;
    approach(16);
    renderer.draw(feel);
    if (!paused && !document.hidden && visible) {
      last = performance.now();
      frame = requestAnimationFrame(animate);
    }
  }
  function resize() {
    const box = canvas.getBoundingClientRect();
    if (!box.width || !box.height) return;
    width = box.width;
    height = box.height;
    ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    if (renderer.kind === "2d") {
      canvas.getContext("2d").setTransform(ratio, 0, 0, ratio, 0, 0);
    }
    renderer.resize(width, height, ratio);
    schedule();
  }
  function motion() {
    document.body.classList.toggle("motion-paused", paused);
    control.textContent = paused ? "Resume motion" : "Pause motion";
    control.setAttribute("aria-pressed", String(paused));
    schedule();
  }
  control.onclick = () => {
    paused = !paused;
    try {
      localStorage.setItem("eliot-motion", paused ? "paused" : "running");
    } catch {}
    motion();
  };
  reduced.addEventListener("change", () => {
    paused = reduced.matches;
    motion();
  });
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
    schedule();
  }).observe(canvas);
  document.addEventListener("visibilitychange", schedule);
  document.addEventListener("eliot-view", resize);
  // Emotion changes are pushed by the workspace; repaint promptly when paused.
  document.addEventListener("eliot-emotion", () => {
    if (paused || document.hidden || !visible) schedule();
  });
  window.addEventListener("pagehide", () => cancelAnimationFrame(frame));
  resize();
  motion();
})();
