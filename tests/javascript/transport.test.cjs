const { test } = require("node:test");
const assert = require("node:assert/strict");
const { Client, RunWatch } = require("../../eliot_app/static/transport.js");
const reply = (status, value) => ({
  status,
  ok: status < 400,
  json: async () => value,
});
function clock() {
  let id = 0;
  const pending = new Map();
  return {
    pending,
    setTimeout(fn, delay) {
      pending.set(++id, { fn, delay });
      return id;
    },
    clearTimeout(key) {
      pending.delete(key);
    },
    async next() {
      const [key, task] = pending.entries().next().value;
      pending.delete(key);
      await task.fn();
      return task.delay;
    },
  };
}

test("expired mutation token refreshes once and retries exactly the rejected request", async () => {
  const calls = [];
  const client = new Client({
    fetch: async (path, options) => {
      calls.push({ path, ...options });
      if (path === "/api/bootstrap") return reply(200, { token: "new" });
      if (options.headers["X-Eliot-Token"] !== "new")
        return reply(403, { code: "invalid_request_token" });
      return reply(200, { id: "created-once" });
    },
  });
  client.token = "old";
  assert.deepEqual(
    await client.request("/api/tasks", "POST", { objective: "review" }),
    { id: "created-once" },
  );
  assert.deepEqual(
    calls.map((c) => c.path),
    ["/api/tasks", "/api/bootstrap", "/api/tasks"],
  );
  assert.equal(calls[0].body, calls[2].body);
  assert.equal(client.token, "new");
});
test("concurrent token failures share one refresh", async () => {
  let refreshes = 0,
    release;
  const wait = new Promise((r) => (release = r));
  const client = new Client({
    fetch: async (path, options) => {
      if (path === "/api/bootstrap") {
        refreshes++;
        await wait;
        return reply(200, { token: "new" });
      }
      return options.headers["X-Eliot-Token"] === "new"
        ? reply(200, {})
        : reply(403, { code: "invalid_request_token" });
    },
  });
  const one = client.request("/one", "POST", {}),
    two = client.request("/two", "POST", {});
  await new Promise((r) => setImmediate(r));
  release();
  await Promise.all([one, two]);
  assert.equal(refreshes, 1);
});
test("unrelated denial and ambiguous network failures never replay mutations", async () => {
  for (const result of [
    () => reply(403, { detail: "Cross-origin requests are not allowed." }),
    () => {
      throw new Error("offline");
    },
  ]) {
    let calls = 0;
    const client = new Client({
      fetch: async () => {
        calls++;
        return result();
      },
    });
    await assert.rejects(client.request("/api/tasks", "POST", {}));
    assert.equal(calls, 1);
  }
});
test("token refresh retry is bounded even when the replacement is rejected", async () => {
  let calls = 0;
  const client = new Client({
    fetch: async (path) => {
      calls++;
      return path === "/api/bootstrap"
        ? reply(200, { token: "new" })
        : reply(403, { code: "invalid_request_token" });
    },
  });
  await assert.rejects(client.request("/api/tasks", "POST", {}));
  assert.equal(calls, 3);
});
test("stalled requests abort and release their timer", async () => {
  const timers = clock();
  const client = new Client({
    ...timers,
    fetch: async (path, { signal }) =>
      new Promise((resolve, reject) =>
        signal.addEventListener("abort", () => reject(new Error("aborted"))),
      ),
  });
  const request = client.request("/api/tasks");
  const rejected = assert.rejects(request, /timed out/);
  await timers.next();
  await rejected;
  assert.equal(timers.pending.size, 0);
});
function watcher(request) {
  const streams = [],
    updates = [],
    connections = [],
    timers = clock();
  let missing = 0;
  class Stream {
    constructor(url) {
      this.url = url;
      streams.push(this);
    }
    close() {
      this.closed = true;
    }
  }
  const watch = new RunWatch("run-1", {
    request,
    EventSource: Stream,
    ...timers,
    onUpdate: (r) => updates.push(r),
    onConnection: (c) => connections.push(c),
    onMissing: () => missing++,
  });
  return {
    watch,
    streams,
    updates,
    connections,
    timers,
    get missing() {
      return missing;
    },
  };
}
test("dropped stream fetches terminal status without resending a chat", async () => {
  const paths = [];
  const w = watcher(async (path) => {
    paths.push(path);
    return { status: "completed", text: "saved" };
  });
  w.streams[0].onerror();
  assert.equal(w.streams[0].closed, true);
  await w.timers.next();
  assert.deepEqual(paths, ["/api/runs/run-1"]);
  assert.equal(w.updates[0].text, "saved");
  assert.equal(w.watch.closed, true);
  assert.equal(w.timers.pending.size, 0);
});
test("active stream recovery reconnects and ignores stale stream events", async () => {
  const w = watcher(async () => ({ status: "running", text: "partial" }));
  const old = w.streams[0];
  old.onerror();
  await w.timers.next();
  assert.equal(w.streams.length, 2);
  old.onmessage({
    data: JSON.stringify({ status: "completed", text: "stale" }),
  });
  assert.equal(w.updates.length, 1);
  w.streams[1].onmessage({
    data: JSON.stringify({ status: "completed", text: "done" }),
  });
  assert.equal(w.updates.at(-1).text, "done");
});
test("closing a watch while a recovery request is in flight ignores the late reply", async () => {
  let release;
  const w = watcher(() => new Promise((r) => (release = r)));
  w.streams[0].onerror();
  const pending = w.timers.next();
  w.watch.close();
  release({ status: "running" });
  await pending;
  assert.equal(w.updates.length, 0);
  assert.equal(w.streams.length, 1);
  assert.equal(w.timers.pending.size, 0);
});
test("repeated outages back off and a missing run terminates recovery", async () => {
  const w = watcher(async () => {
    throw new Error("offline");
  });
  w.streams[0].onerror();
  const delays = [];
  for (let i = 0; i < 6; i++) delays.push(await w.timers.next());
  assert.deepEqual(delays, [1000, 2000, 4000, 8000, 15000, 15000]);
  w.watch.close();
  assert.equal(w.timers.pending.size, 0);
  const gone = watcher(async () => {
    const e = new Error("gone");
    e.status = 404;
    throw e;
  });
  gone.streams[0].onerror();
  await gone.timers.next();
  assert.equal(gone.missing, 1);
  assert.equal(gone.watch.closed, true);
});
test("malformed stream messages recover through the recorded run", async () => {
  const w = watcher(async () => ({ status: "cancelled", text: "partial" }));
  w.streams[0].onmessage({ data: "not json" });
  await w.timers.next();
  assert.equal(w.updates[0].status, "cancelled");
});

test("default browser fetch retains its global receiver", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = function () {
    assert.equal(this, globalThis);
    return Promise.resolve({
      ok: true,
      status: 200,
      json: async () => ({ ready: true }),
    });
  };
  try {
    assert.deepEqual(await new Client().request("/api/bootstrap"), {
      ready: true,
    });
  } finally {
    globalThis.fetch = original;
  }
});
