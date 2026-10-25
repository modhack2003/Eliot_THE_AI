"use strict";
/*
 * Eliot cinematic core — a multi-pass WebGL2 renderer for the agent's presence.
 *
 * Decorative only. The visualization expresses *recorded* backend state
 * (idle / thinking / talking / working / alert). It never exposes model
 * internals, prompts, evidence or provider data.
 *
 * Design notes
 * ------------
 * - No external libraries, no network, no eval. All shader source is inline,
 *   so the app's strict Content-Security-Policy (script-src 'self') is never
 *   relaxed and nothing is added to the Python wheel but this flat file.
 * - Pipeline: volumetric scene -> bright extract -> separable blur -> grade.
 *   That is a real post-processing chain (bloom, chromatic aberration, film
 *   grain, scanlines, glitch), which is what gives the frame its filmic feel.
 * - Emotion is a smoothed vector, not a switch. Every expressive parameter is
 *   critically damped toward its target so the entity eases between feelings
 *   instead of snapping, which is what reads as "alive".
 * - Quality degrades automatically on slow GPUs and all motion obeys the
 *   pause control and prefers-reduced-motion.
 */
window.EliotCinematicCore = (() => {
  // ---------------------------------------------------------------- shaders
  // A single full-screen triangle generated from gl_VertexID. No attribute
  // buffers or geometry uploads are needed for any pass.
  const VERT = `#version 300 es
void main(){
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

  const COMMON = `
precision highp float;
uniform vec2  uRes;
uniform float uTime;
uniform float uEnergy;   // overall intensity           0..1
uniform float uThink;    // inward, convergent streams  0..1
uniform float uTalk;     // outward waveform ripples    0..1
uniform float uAlert;    // angular warning + glitch    0..1
uniform float uPulse;    // speech rhythm driver        0..1
uniform vec3  uColor;    // primary emission
uniform vec3  uAccent;   // secondary emission
uniform float uQuality;  // 1 = full, 0 = reduced

float hash11(float p){ return fract(sin(p * 127.1) * 43758.5453); }
float hash21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float hash31(vec3 p){
  p = fract(p * 0.3183099 + 0.1); p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float noise3(vec3 x){
  vec3 i = floor(x), f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash31(i + vec3(0,0,0)), hash31(i + vec3(1,0,0)), f.x),
                 mix(hash31(i + vec3(0,1,0)), hash31(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash31(i + vec3(0,0,1)), hash31(i + vec3(1,0,1)), f.x),
                 mix(hash31(i + vec3(0,1,1)), hash31(i + vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p){
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++){ s += a * noise3(p); p *= 2.03; a *= 0.5; }
  return s;
}
// Ridged noise. Inverting each octave turns smooth blobs into bright veins,
// which is what gives the volume its neural, filamentary structure.
float ridged(vec3 p){
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++){
    float n = 1.0 - abs(noise3(p) * 2.0 - 1.0);
    s += a * n * n;
    p *= 2.07;
    a *= 0.5;
  }
  return s;
}
mat2 rot(float a){ float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
const float PI = 3.14159265;
`;

  // Pass 1 — the entity itself, raymarched as a volume, plus its environment.
  const SCENE = `#version 300 es
${COMMON}
out vec4 frag;

const float R = 1.0;

// Volumetric density of the core at a point in its local space.
float density(vec3 p, float t){
  float r = length(p);
  float shell = smoothstep(R, R * 0.62, r);        // confine to the sphere
  if (shell <= 0.0) return 0.0;

  vec3 q = p;
  q.xz *= rot(t * 0.21);                            // slow self rotation
  q.yz *= rot(0.42);

  // Filamentary plasma. Flow is pulled along -y so the volume feels convective.
  float n = ridged(q * 3.1 + vec3(0.0, -t * 0.34, t * 0.15));

  // Thinking: energy spirals inward, concentrating toward the center.
  float spiral = sin(atan(q.z, q.x) * 3.0 + r * 9.0 - t * 2.4) * 0.5 + 0.5;
  n = mix(n, n * 0.55 + spiral * 0.5 * smoothstep(0.95, 0.15, r), uThink);

  // Talking: concentric shells travel outward in time with the cadence.
  // Modulating the existing field, rather than adding to it, keeps the mean
  // brightness steady so speech reads as rhythm instead of a white flare.
  float ripple = sin(r * 15.0 - t * 7.0 - uPulse * 6.2831) * 0.5 + 0.5;
  n = mix(n, n * (0.5 + ripple * 0.85), uTalk * 0.9);

  // Alert: angular wedges flicker like a fault indicator.
  float wedge = step(0.62, fract(atan(q.z, q.x) / PI * 3.0 + t * 0.7));
  n = mix(n, max(n, wedge * 0.75), uAlert * 0.5);

  // A power curve keeps the veins crisp instead of hazing into a solid blob.
  float d = pow(max(n - 0.30, 0.0), 1.5) * 4.6;
  d += (1.0 - smoothstep(0.0, 0.34, r)) * (0.35 + uEnergy * 0.95); // hot nucleus
  return d * shell;
}

// Emission colour for a sample, warmer and brighter toward the nucleus.
vec3 emission(vec3 p, float d, float t){
  float r = length(p);
  vec3 c = mix(uAccent, uColor, smoothstep(0.0, 0.85, r));
  // A restrained white nucleus. Pushing this harder desaturates the whole
  // volume after tone mapping and Eliot loses its colour identity.
  c = mix(c, vec3(1.0), (1.0 - smoothstep(0.0, 0.22, r)) * 0.42);
  c = mix(c, vec3(1.0, 0.33, 0.22), uAlert * 0.45 * step(0.5, hash11(floor(t * 11.0))));
  return c * (0.3 + d * 0.8);
}

void main(){
  vec2 uv = (gl_FragCoord.xy - 0.5 * uRes) / min(uRes.x, uRes.y);
  float t = uTime;
  vec3 col = vec3(0.0);

  // ---- background: parallax data motes + falling glyph columns ----------
  for (int L = 0; L < 3; L++){
    float fl = float(L);
    float depth = 1.0 + fl * 0.85;
    vec2 g = uv * (3.2 + fl * 2.1) + vec2(t * 0.025 * depth, -t * 0.045 * depth);
    vec2 id = floor(g);
    vec2 f = fract(g) - 0.5;
    float h = hash21(id + fl * 31.0);
    if (h > 0.90){
      float tw = 0.55 + 0.45 * sin(t * 2.4 + h * 40.0);
      col += uColor * exp(-dot(f, f) * 150.0) * tw * (0.5 / depth);
    }
  }
  // Glyph rain, kept very low contrast so it reads as texture, not noise.
  {
    vec2 g = vec2(uv.x * 26.0, uv.y * 15.0);
    vec2 id = floor(g);
    float colPhase = hash11(id.x);
    float fall = fract(colPhase + t * (0.18 + colPhase * 0.3));
    // Softened deliberately: a hard glyph mask leaves visible rectangular
    // blocks that read as compression artifacts rather than falling code.
    float band = smoothstep(0.5, 0.0, abs(fract(g.y * 0.07 + fall) - 0.5));
    float glyph = smoothstep(0.55, 0.9, hash21(id + floor(t * 7.0)));
    float cell = smoothstep(0.5, 0.15, length(fract(g) - 0.5));
    col += uColor * band * glyph * cell * 0.022 * (0.4 + uEnergy * 0.8);
  }

  // ---- the entity: ray / sphere intersection, then march the volume -----
  vec3 ro = vec3(0.0, 0.0, -3.1);
  vec3 rd = normalize(vec3(uv * 1.34, 1.0));
  float b = dot(ro, rd), c2 = dot(ro, ro) - R * R;
  float h2 = b * b - c2;
  if (h2 > 0.0){
    float sh = sqrt(h2);
    float t0 = max(-b - sh, 0.0), t1 = -b + sh;
    int steps = uQuality > 0.5 ? 46 : 22;
    float dt = (t1 - t0) / float(steps);
    float trans = 1.0;
    // Dithering the entry point breaks the regular sampling grid, which would
    // otherwise show as concentric banding across the silhouette.
    float jitter = hash21(gl_FragCoord.xy);
    for (int i = 0; i < 46; i++){
      if (i >= steps || trans < 0.02) break;
      vec3 p = ro + rd * (t0 + dt * (float(i) + jitter));
      float d = density(p, t);
      if (d > 0.001){
        col += emission(p, d, t) * d * dt * trans * (0.8 + uEnergy * 1.5);
        trans *= exp(-d * dt * 2.3);                 // absorption
      }
    }
    // Fresnel rim. Deliberately thin and restrained: a thicker shell reads as
    // a blown-out white ring once bloom is applied and hides the interior.
    float edge = 1.0 - clamp(sh / R, 0.0, 1.0);
    col += mix(uColor, uAccent, 0.35) * pow(edge, 4.0) * (0.22 + uEnergy * 0.4);
  }

  // ---- HUD: targeting rings with tick marks, and a scan sweep -----------
  float r = length(uv);
  float baseAng = atan(uv.y, uv.x);
  for (int i = 0; i < 3; i++){
    float fi = float(i);
    float rad = 0.46 + fi * 0.085;                  // tighter, closer to the core
    float ring = smoothstep(0.0025, 0.0, abs(r - rad));
    float ang = baseAng + t * (0.22 - fi * 0.13) * (i == 1 ? -1.0 : 1.0);
    // A faint continuous ring carries coarse tick marks, so it reads as an
    // instrument bezel rather than a scatter of unrelated dashes.
    float ticks = smoothstep(0.35, 0.5, fract(ang / PI * (5.0 + fi * 4.0)));
    float arc = smoothstep(0.05, 0.45, fract(ang / (2.0 * PI) + 0.5));
    vec3 rc = mix(uColor, uAccent, fi * 0.5);
    col += rc * ring * arc * (0.1 + 0.42 * ticks) * (0.4 + uEnergy * 0.5);
  }
  // Orbiting beads ride the inner ring.
  for (int i = 0; i < 2; i++){
    float fi = float(i);
    float a = t * (0.85 - fi * 0.4) + fi * 3.0;
    vec2 bp = vec2(cos(a), sin(a)) * (0.46 + fi * 0.085);
    col += mix(uColor, uAccent, fi) * exp(-pow(length(uv - bp) * 46.0, 2.0)) * 0.85 * (0.4 + uEnergy);
  }
  // Scan sweep: a soft wide band, not a hard line, so it grades the frame
  // instead of looking like a tear.
  float sweep = fract(t * 0.14) * 1.7 - 0.85;
  col += uColor * smoothstep(0.16, 0.0, abs(uv.y - sweep)) * 0.05 * uEnergy;

  frag = vec4(col, 1.0);
}`;

  // Pass 2 — extract bright regions and blur them on one axis.
  const BLUR = `#version 300 es
precision highp float;
uniform sampler2D uTex;
uniform vec2 uTexel;
uniform vec2 uDir;
uniform float uExtract;   // 1 on the first pass, 0 afterwards
out vec4 frag;
void main(){
  vec2 uv = gl_FragCoord.xy * uTexel;
  float w[5]; w[0]=0.2270; w[1]=0.1946; w[2]=0.1216; w[3]=0.0540; w[4]=0.0162;
  vec3 sum = vec3(0.0);
  for (int i = -4; i <= 4; i++){
    vec3 s = texture(uTex, uv + uDir * uTexel * float(i) * 1.6).rgb;
    if (uExtract > 0.5) s = max(s - 0.62, 0.0) * 1.05;  // bright pass
    sum += s * w[abs(i)];
  }
  frag = vec4(sum, 1.0);
}`;

  // Pass 3 — composite and grade to the screen.
  const GRADE = `#version 300 es
${COMMON}
uniform sampler2D uScene;
uniform sampler2D uBloom;
out vec4 frag;

void main(){
  vec2 uv = gl_FragCoord.xy / uRes;
  vec2 cuv = uv - 0.5;
  float t = uTime;

  // Glitch: horizontal blocks tear during alert states and speech peaks.
  float gAmt = uAlert * 0.65 + uTalk * 0.12;
  float blk = floor(uv.y * 34.0);
  float gate = step(0.80, hash21(vec2(blk, floor(t * 13.0))));
  float shift = (hash21(vec2(blk, floor(t * 13.0) + 7.0)) - 0.5) * 0.07 * gAmt * gate;
  vec2 suv = vec2(clamp(uv.x + shift, 0.0, 1.0), uv.y);

  // Chromatic aberration grows toward the edges. Kept subtle; heavy fringing
  // on thin HUD strokes reads as a rendering fault, not as cinematography.
  float ca = (0.0006 + 0.0014 * uEnergy + 0.006 * gAmt) * length(cuv) * 2.0;
  vec3 col;
  col.r = texture(uScene, suv + cuv * ca).r;
  col.g = texture(uScene, suv).g;
  col.b = texture(uScene, suv - cuv * ca).b;
  col += texture(uBloom, suv).rgb * (0.42 + uEnergy * 0.38);

  // Filmic tone map, then a gentle lift.
  col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
  col = pow(max(col, 0.0), vec3(0.92));

  col *= 1.0 - 0.55 * dot(cuv, cuv);                              // vignette
  col *= 1.0 - 0.055 * step(0.5, fract(gl_FragCoord.y * 0.5));    // scanlines
  col += (hash21(gl_FragCoord.xy + fract(t) * 97.0) - 0.5) * 0.035; // grain

  float a = clamp(max(col.r, max(col.g, col.b)) * 1.45, 0.0, 1.0);
  frag = vec4(max(col, 0.0), a);
}`;

  // ------------------------------------------------------------- utilities
  function build(gl, src) {
    const sh = (type, source) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, source);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        gl.deleteShader(s);
        return null;
      }
      return s;
    };
    const vs = sh(gl.VERTEX_SHADER, VERT);
    const fs = sh(gl.FRAGMENT_SHADER, src);
    if (!vs || !fs) return null;
    const p = gl.createProgram();
    gl.attachShader(p, vs);
    gl.attachShader(p, fs);
    gl.linkProgram(p);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return null;
    return p;
  }

  function makeTarget(gl, w, h) {
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return { tex, fbo, w, h };
  }

  // ---------------------------------------------------------------- public
  // Returns null when WebGL2 or the shader pipeline is unavailable, so the
  // caller can fall back to its 2D renderer.
  function create(canvas) {
    const gl = canvas.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "high-performance",
    });
    if (!gl) return null;

    const scene = build(gl, SCENE);
    const blur = build(gl, BLUR);
    const grade = build(gl, GRADE);
    if (!scene || !blur || !grade) return null;

    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);

    const loc = (p, names) => {
      const o = {};
      for (const n of names) o[n] = gl.getUniformLocation(p, n);
      return o;
    };
    const FEEL = ["uRes", "uTime", "uEnergy", "uThink", "uTalk", "uAlert", "uPulse", "uColor", "uAccent", "uQuality"];
    const uScene = loc(scene, FEEL);
    const uBlur = loc(blur, ["uTex", "uTexel", "uDir", "uExtract"]);
    const uGrade = loc(grade, [...FEEL, "uScene", "uBloom"]);

    let sceneRT = null, blurA = null, blurB = null;
    let vw = 1, vh = 1;

    const applyFeel = (u, feel, w, h) => {
      gl.uniform2f(u.uRes, w, h);
      gl.uniform1f(u.uTime, feel.time);
      gl.uniform1f(u.uEnergy, feel.energy);
      gl.uniform1f(u.uThink, feel.think);
      gl.uniform1f(u.uTalk, feel.talk);
      gl.uniform1f(u.uAlert, feel.alert);
      gl.uniform1f(u.uPulse, feel.pulse);
      gl.uniform3fv(u.uColor, feel.color);
      gl.uniform3fv(u.uAccent, feel.accent);
      gl.uniform1f(u.uQuality, feel.quality);
    };

    return {
      kind: "webgl2-cinematic",
      resize(w, h, dpr) {
        vw = Math.max(1, Math.round(w * dpr));
        vh = Math.max(1, Math.round(h * dpr));
        for (const t of [sceneRT, blurA, blurB]) {
          if (t) { gl.deleteTexture(t.tex); gl.deleteFramebuffer(t.fbo); }
        }
        sceneRT = makeTarget(gl, vw, vh);
        const bw = Math.max(1, vw >> 1), bh = Math.max(1, vh >> 1);
        blurA = makeTarget(gl, bw, bh);
        blurB = makeTarget(gl, bw, bh);
      },
      draw(feel) {
        if (!sceneRT) return;
        gl.bindVertexArray(vao);
        gl.disable(gl.BLEND);

        // 1. volumetric scene
        gl.bindFramebuffer(gl.FRAMEBUFFER, sceneRT.fbo);
        gl.viewport(0, 0, vw, vh);
        gl.useProgram(scene);
        applyFeel(uScene, feel, vw, vh);
        gl.drawArrays(gl.TRIANGLES, 0, 3);

        // 2. bright extract + horizontal blur, then vertical blur
        gl.useProgram(blur);
        gl.uniform1i(uBlur.uTex, 0);
        gl.activeTexture(gl.TEXTURE0);

        gl.bindFramebuffer(gl.FRAMEBUFFER, blurA.fbo);
        gl.viewport(0, 0, blurA.w, blurA.h);
        gl.bindTexture(gl.TEXTURE_2D, sceneRT.tex);
        gl.uniform2f(uBlur.uTexel, 1 / blurA.w, 1 / blurA.h);
        gl.uniform2f(uBlur.uDir, 1, 0);
        gl.uniform1f(uBlur.uExtract, 1);
        gl.drawArrays(gl.TRIANGLES, 0, 3);

        gl.bindFramebuffer(gl.FRAMEBUFFER, blurB.fbo);
        gl.viewport(0, 0, blurB.w, blurB.h);
        gl.bindTexture(gl.TEXTURE_2D, blurA.tex);
        gl.uniform2f(uBlur.uDir, 0, 1);
        gl.uniform1f(uBlur.uExtract, 0);
        gl.drawArrays(gl.TRIANGLES, 0, 3);

        // 3. composite + grade to the screen
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        gl.viewport(0, 0, vw, vh);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.useProgram(grade);
        applyFeel(uGrade, feel, vw, vh);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, sceneRT.tex);
        gl.uniform1i(uGrade.uScene, 0);
        gl.activeTexture(gl.TEXTURE1);
        gl.bindTexture(gl.TEXTURE_2D, blurB.tex);
        gl.uniform1i(uGrade.uBloom, 1);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      },
    };
  }

  return { create };
})();
