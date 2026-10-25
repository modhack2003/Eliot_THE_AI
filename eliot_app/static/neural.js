"use strict";
// Local, decorative geometry. The animation represents activity, never model internals.
(() => {
  const canvas = document.getElementById("neural-canvas"),
    ctx = canvas.getContext("2d"),
    control = document.getElementById("motion-toggle");
  if (!ctx) {
    canvas.hidden = true;
    control.hidden = true;
    return;
  }
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let preference = null;
  try {
    preference = localStorage.getItem("eliot-motion");
  } catch {}
  let paused = preference ? preference === "paused" : reduced.matches;
  let width = 1,
    height = 1,
    visible = true,
    frame = 0,
    last = 0,
    phase = 0.42;
  const rows = 28,
    cols = 52,
    points = [];
  for (let row = 0; row <= rows; row++)
    for (let col = 0; col < cols; col++) {
      const phi = (Math.PI * row) / rows,
        theta = (2 * Math.PI * col) / cols;
      points.push({ phi, theta, row, col });
    }
  function project(x, y, z) {
    const a = phase * 0.12,
      ca = Math.cos(a),
      sa = Math.sin(a),
      rx = x * ca - z * sa,
      rz = x * sa + z * ca,
      tilt = 0.27,
      ry = y * Math.cos(tilt) - rz * Math.sin(tilt),
      depth = y * Math.sin(tilt) + rz * Math.cos(tilt);
    const scale = 2.9 / (2.9 + depth);
    return {
      x: width * 0.51 + rx * scale,
      y: height * 0.49 + ry * scale,
      z: depth,
    };
  }
  function draw() {
    ctx.clearRect(0, 0, width, height);
    const radius = Math.min(width * 0.34, height * 0.33),
      cx = width * 0.51,
      cy = height * 0.49;
    const glow = ctx.createRadialGradient(
      cx,
      cy,
      radius * 0.13,
      cx,
      cy,
      radius * 1.6,
    );
    glow.addColorStop(0, "#4babc019");
    glow.addColorStop(0.55, "#67bbdf0d");
    glow.addColorStop(1, "#4eabce00");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, height);
    const positions = points.map((p) => {
      const ripple =
        1 +
        0.038 * Math.sin(p.theta * 5 + p.phi * 3 + phase) +
        0.018 * Math.sin(p.phi * 12 - phase * 0.7);
      return project(
        Math.sin(p.phi) * Math.cos(p.theta) * ripple,
        Math.cos(p.phi) * ripple,
        Math.sin(p.phi) * Math.sin(p.theta) * ripple,
      );
    });
    const screen = (p) => ({
      x: cx + (p.x - cx) * radius,
      y: cy + (p.y - cy) * radius,
    });
    for (let row = 1; row < rows; row++) {
      ctx.beginPath();
      for (let col = 0; col <= cols; col++) {
        const point = positions[row * cols + (col % cols)],
          p = screen(point);
        if (!col) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.strokeStyle = row % 3 === 0 ? "#95cfdf2b" : "#76b7d416";
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }
    for (let col = 0; col < cols; col += 3) {
      ctx.beginPath();
      for (let row = 0; row <= rows; row++) {
        const p = screen(positions[row * cols + col]);
        if (!row) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.strokeStyle = "#76b7d422";
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }
    for (let i = 0; i < positions.length; i++) {
      const point = positions[i],
        p = screen(point),
        front = (1.4 - point.z) / 2.6;
      ctx.fillStyle = `rgba(166,222,241,${0.15 + front * 0.65})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 0.35 + front * 0.65, 0, Math.PI * 2);
      ctx.fill();
    }
    // Two offset orbital paths supply the instrument-like silhouette.
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-0.43);
    ctx.strokeStyle = "#7fa9bc30";
    ctx.lineWidth = 0.7;
    ctx.beginPath();
    ctx.ellipse(0, 0, radius * 1.31, radius * 0.47, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([1, 7]);
    ctx.beginPath();
    ctx.ellipse(0, 0, radius * 1.42, radius * 1.15, 0.1, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    const orbit = phase * 0.22;
    ctx.fillStyle = "#d5edfa";
    ctx.shadowColor = "#8cd5ee";
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(
      Math.cos(orbit) * radius * 1.31,
      Math.sin(orbit) * radius * 0.47,
      2,
      0,
      Math.PI * 2,
    );
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(0.66);
    ctx.strokeStyle = "#d7ae7066";
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.ellipse(0, 0, radius * 1.15, radius * 0.86, 0, 1.25, 2.8);
    ctx.stroke();
    ctx.fillStyle = "#e3bc82";
    ctx.beginPath();
    ctx.arc(
      Math.cos(2.8) * radius * 1.15,
      Math.sin(2.8) * radius * 0.86,
      1.6,
      0,
      Math.PI * 2,
    );
    ctx.fill();
    ctx.restore();
  }
  function animate(now) {
    frame = 0;
    if (paused || document.hidden || !visible) return;
    if (now - last > 32) {
      phase +=
        Math.min(now - last || 32, 64) *
        0.001 *
        (document.body.dataset.activity === "working" ? 1.6 : 0.55);
      last = now;
      draw();
    }
    frame = requestAnimationFrame(animate);
  }
  function schedule() {
    cancelAnimationFrame(frame);
    frame = 0;
    draw();
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
    const ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
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
  window.addEventListener("pagehide", () => cancelAnimationFrame(frame));
  resize();
  motion();
})();
