"use strict";
// Local, decorative geometry. The animation represents activity, never model internals.
// A GPU (WebGL2) neural core renders when available; it falls back to an equivalent
// 2D canvas renderer so the workspace looks the same everywhere. Both honor the pause
// control, the reduced-motion preference, tab visibility and viewport intersection.
// No external libraries, network access or eval — the shader source is inline and the
// Content-Security-Policy (script-src 'self') is never relaxed.
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
    last = 0,
    phase = 0.42,
    intensity = 0.4; // smoothed activity energy, 0..1

  // Activity → target energy and palette. Cyan rest, ice when working, amber on attention.
  const PALETTE = {
    idle: { energy: 0.36, color: [0.57, 0.86, 0.93], accent: [0.85, 0.71, 0.52] },
    working: { energy: 1.0, color: [0.74, 0.94, 1.0], accent: [0.62, 0.9, 0.98] },
    attention: { energy: 0.62, color: [0.9, 0.73, 0.46], accent: [0.98, 0.84, 0.55] },
  };
  const target = () => PALETTE[document.body.dataset.activity] || PALETTE.idle;

  // ---- Renderer selection: WebGL2 first, 2D canvas fallback ----------------
  let renderer = null;
  try {
    renderer = createGLRenderer(canvas);
  } catch {
    renderer = null;
  }
  if (!renderer) {
    try {
      renderer = create2DRenderer(canvas);
    } catch {
      renderer = null;
    }
  }
  if (!renderer) {
    canvas.hidden = true;
    control.hidden = true;
    return;
  }
  // If the GL context is lost at runtime, drop to the 2D renderer transparently.
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    if (renderer && renderer.kind === "gl") {
      try {
        renderer = create2DRenderer(canvas) || renderer;
      } catch {}
      resize();
    }
  });

  // =========================================================================
  // WebGL2 renderer — a procedural, raymarched particle core drawn in a single
  // full-screen fragment pass (no vertex buffers to manage, no geometry upload).
  // =========================================================================
  function createGLRenderer(cv) {
    const gl = cv.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "high-performance",
      failIfMajorPerformanceCaveat: false,
    });
    if (!gl) return null;

    const vertSrc = `#version 300 es
void main(){
  // Full-screen triangle generated from gl_VertexID; no attributes needed.
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

    const fragSrc = `#version 300 es
precision highp float;
out vec4 frag;
uniform vec2 uRes;
uniform float uTime;
uniform float uEnergy;   // 0..1 smoothed activity
uniform vec3 uColor;     // primary emission
uniform vec3 uAccent;    // secondary emission

float hash(vec3 p){ p = fract(p * 0.3183099 + 0.1); p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float noise(vec3 x){
  vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash(i+vec3(0,0,0)),hash(i+vec3(1,0,0)),f.x),
                 mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
             mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),
                 mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y), f.z);
}
mat2 rot(float a){ float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
const float PI = 3.14159265;

void main(){
  vec2 uv = (gl_FragCoord.xy - 0.5 * uRes) / min(uRes.x, uRes.y);
  float t = uTime;
  float energy = 0.5 + uEnergy * 0.85;
  vec3 col = vec3(0.0);

  float R = 0.4;
  float r = length(uv);

  // Soft atmospheric bloom behind the core.
  col += uColor * exp(-max(r - R * 0.15, 0.0) * 3.0) * 0.12 * energy;

  // The particle sphere itself.
  if (r < R) {
    float z = sqrt(max(R * R - r * r, 0.0));
    vec3 n = vec3(uv, z) / R;
    n.xz *= rot(t * 0.16);
    n.yz *= rot(0.5);
    float lat = asin(clamp(n.y, -1.0, 1.0));
    float lon = atan(n.z, n.x);

    // Flowing surface field drives the living shimmer.
    vec3 sp = vec3(lon * 2.0, lat * 3.0, t * 0.35);
    float field = noise(sp * 2.4) + 0.5 * noise(sp * 5.0 + 3.0);

    // Latitude / longitude wireframe.
    float g1 = smoothstep(0.03, 0.0, abs(fract(lat * 6.0 / PI + 0.5) - 0.5) - 0.015);
    float g2 = smoothstep(0.03, 0.0, abs(fract(lon * 8.0 / PI + 0.5) - 0.5) - 0.015);
    float grid = max(g1, g2) * 0.3;

    // Node points that twinkle in and out.
    vec2 cell = vec2(lon * 9.0, lat * 9.0);
    vec2 cid = floor(cell), cf = fract(cell) - 0.5;
    float twinkle = hash(vec3(cid, floor(t * 0.6)));
    float node = smoothstep(0.2, 0.0, length(cf)) * smoothstep(0.45, 0.95, twinkle);

    float fres = pow(1.0 - z / R, 2.4);
    float shade = 0.1 + field * 0.22 * energy + grid + node * energy + fres * 1.15;
    vec3 base = mix(uColor, uAccent, clamp(smoothstep(0.35, 0.95, field) * 0.5 + fres * 0.35, 0.0, 1.0));
    col += base * shade * (0.6 + 0.4 * z / R);
  }

  // Two offset orbital rings, each carrying a bright bead.
  for (int i = 0; i < 2; i++) {
    float fi = float(i);
    vec2 p = uv * rot(-0.42 + fi * 1.1);
    float rx = 0.6 + fi * 0.07, ry = 0.22 + fi * 0.32;
    float e = length(vec2(p.x / rx, p.y / ry)) - 1.0;
    vec3 rc = mix(uColor, uAccent, fi);
    col += rc * smoothstep(0.015, 0.0, abs(e)) * 0.45 * (0.6 + 0.4 * energy);
    float ang = t * (0.5 - fi * 0.22) + fi * 2.0;
    vec2 bead = vec2(cos(ang) * rx, sin(ang) * ry);
    col += rc * exp(-pow(length(p - bead) * 24.0, 2.0)) * 1.5 * energy;
  }

  col *= smoothstep(1.15, 0.2, r);            // vignette
  col = col / (1.0 + col);                     // Reinhard tone map
  col = pow(col, vec3(0.85));                  // gentle gamma lift
  float a = clamp(max(col.r, max(col.g, col.b)) * 1.35, 0.0, 1.0);
  frag = vec4(col, a);                         // straight alpha over dark stage
}`;

    const compile = (type, src) => {
      const sh = gl.createShader(type);
      gl.shaderSource(sh, src);
      gl.compileShader(sh);
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
        gl.deleteShader(sh);
        return null;
      }
      return sh;
    };
    const vs = compile(gl.VERTEX_SHADER, vertSrc),
      fs = compile(gl.FRAGMENT_SHADER, fragSrc);
    if (!vs || !fs) return null;
    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
    gl.useProgram(program);
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const u = {
      res: gl.getUniformLocation(program, "uRes"),
      time: gl.getUniformLocation(program, "uTime"),
      energy: gl.getUniformLocation(program, "uEnergy"),
      color: gl.getUniformLocation(program, "uColor"),
      accent: gl.getUniformLocation(program, "uAccent"),
    };
    gl.clearColor(0, 0, 0, 0);

    return {
      kind: "gl",
      resize(w, h, dpr) {
        gl.viewport(0, 0, Math.round(w * dpr), Math.round(h * dpr));
      },
      draw(ph, energy, w, h, dpr) {
        const tgt = target();
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.uniform2f(u.res, w * dpr, h * dpr);
        gl.uniform1f(u.time, ph);
        gl.uniform1f(u.energy, energy);
        gl.uniform3fv(u.color, tgt.color);
        gl.uniform3fv(u.accent, tgt.accent);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      },
    };
  }

  // =========================================================================
  // 2D canvas fallback — the original instrument-like core, retained verbatim
  // so environments without WebGL2 keep an equivalent, tasteful animation.
  // =========================================================================
  function create2DRenderer(cv) {
    const ctx = cv.getContext("2d");
    if (!ctx) return null;
    const rows = 28,
      cols = 52,
      points = [];
    for (let row = 0; row <= rows; row++)
      for (let col = 0; col < cols; col++) {
        const phi = (Math.PI * row) / rows,
          theta = (2 * Math.PI * col) / cols;
        points.push({ phi, theta, row, col });
      }
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
    return {
      kind: "2d",
      resize() {},
      draw(ph) {
        ctx.clearRect(0, 0, width, height);
        const radius = Math.min(width * 0.34, height * 0.33),
          cx = width * 0.51,
          cy = height * 0.49;
        const glow = ctx.createRadialGradient(cx, cy, radius * 0.13, cx, cy, radius * 1.6);
        glow.addColorStop(0, "#4babc019");
        glow.addColorStop(0.55, "#67bbdf0d");
        glow.addColorStop(1, "#4eabce00");
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, width, height);
        const positions = points.map((p) => {
          const ripple =
            1 +
            0.038 * Math.sin(p.theta * 5 + p.phi * 3 + ph) +
            0.018 * Math.sin(p.phi * 12 - ph * 0.7);
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
          const p = screen(positions[i]),
            front = (1.4 - positions[i].z) / 2.6;
          ctx.fillStyle = `rgba(166,222,241,${0.15 + front * 0.65})`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 0.35 + front * 0.65, 0, Math.PI * 2);
          ctx.fill();
        }
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
        const orbit = ph * 0.22;
        ctx.fillStyle = "#d5edfa";
        ctx.shadowColor = "#8cd5ee";
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.arc(Math.cos(orbit) * radius * 1.31, Math.sin(orbit) * radius * 0.47, 2, 0, Math.PI * 2);
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
        ctx.arc(Math.cos(2.8) * radius * 1.15, Math.sin(2.8) * radius * 0.86, 1.6, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      },
    };
  }

  // ---- Shared animation loop & controls ------------------------------------
  function render() {
    renderer.draw(phase, intensity, width, height, ratio);
  }
  function animate(now) {
    frame = 0;
    if (paused || document.hidden || !visible) return;
    const dt = Math.min(now - last || 32, 64);
    const tgt = target();
    const speed = tgt.energy >= 1 ? 1.6 : tgt.energy > 0.4 ? 0.9 : 0.55;
    phase += dt * 0.001 * speed;
    intensity += (tgt.energy - intensity) * Math.min(dt * 0.004, 1);
    last = now;
    render();
    frame = requestAnimationFrame(animate);
  }
  function schedule() {
    cancelAnimationFrame(frame);
    frame = 0;
    render();
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
      const ctx = canvas.getContext("2d");
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
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
  window.addEventListener("pagehide", () => cancelAnimationFrame(frame));
  resize();
  motion();
})();
