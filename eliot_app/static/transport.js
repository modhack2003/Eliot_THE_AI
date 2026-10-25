"use strict";
// Browser transport is independent of the DOM so recovery can be regression-tested.
const EliotTransport = (() => {
  class Client {
    constructor({
      fetch: send = globalThis.fetch.bind(globalThis),
      setTimeout: later = globalThis.setTimeout.bind(globalThis),
      clearTimeout: clear = globalThis.clearTimeout.bind(globalThis),
    } = {}) {
      this.send = send;
      this.later = later;
      this.clear = clear;
      this.token = "";
      this.refreshing = null;
    }
    async request(path, method = "GET", body, retryToken = true) {
      const controller = new AbortController();
      const timer = this.later(
        () => controller.abort(),
        method === "GET" ? 15000 : 90000,
      );
      const options = {
        method,
        signal: controller.signal,
        cache: "no-store",
        headers: { "X-Eliot-Token": this.token },
      };
      if (body !== undefined) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
      }
      let response, value;
      try {
        response = await this.send(path, options);
        value = await response.json();
      } catch (error) {
        throw new Error(
          controller.signal.aborted
            ? "The request timed out. Refresh the record before retrying."
            : "Cannot read a response from Eliot. Check that the backend is running.",
        );
      } finally {
        this.clear(timer);
      }
      // Only replay after an explicit rejection BEFORE the request reaches its handler.
      if (
        response.status === 403 &&
        value?.code === "invalid_request_token" &&
        retryToken
      ) {
        if (!this.refreshing) {
          this.refreshing = this.request(
            "/api/bootstrap",
            "GET",
            undefined,
            false,
          ).finally(() => {
            this.refreshing = null;
          });
        }
        await this.refreshing;
        return this.request(path, method, body, false);
      }
      if (!response.ok) {
        const error = new Error(
          typeof value?.detail === "string"
            ? value.detail
            : "The request could not be completed.",
        );
        error.status = response.status;
        throw error;
      }
      if (path === "/api/bootstrap" && typeof value?.token === "string")
        this.token = value.token;
      return value;
    }
  }
  class RunWatch {
    constructor(
      id,
      {
        request,
        onUpdate,
        onConnection = () => {},
        onMissing = () => {},
        EventSource: Stream = globalThis.EventSource,
        setTimeout: later = globalThis.setTimeout.bind(globalThis),
        clearTimeout: clear = globalThis.clearTimeout.bind(globalThis),
      },
    ) {
      Object.assign(this, {
        id,
        request,
        onUpdate,
        onConnection,
        onMissing,
        Stream,
        later,
        clear,
      });
      this.closed = false;
      this.stream = null;
      this.timer = null;
      this.failures = 0;
      this.connect();
    }
    close() {
      this.closed = true;
      this.clear(this.timer);
      this.stream?.close();
      this.stream = null;
    }
    accept(run) {
      if (this.closed) return;
      this.failures = 0;
      this.onConnection(true);
      this.onUpdate(run);
      if (!["queued", "running"].includes(run.status)) this.close();
    }
    connect() {
      if (this.closed) return;
      const stream = (this.stream = new this.Stream(
        `/api/runs/${this.id}/events`,
      ));
      stream.onmessage = (event) => {
        if (this.closed || this.stream !== stream) return;
        let run;
        try {
          run = JSON.parse(event.data);
          if (!run || typeof run.status !== "string") throw new Error();
        } catch {
          this.recover();
          return;
        }
        this.accept(run);
      };
      stream.onerror = () => {
        if (!this.closed && this.stream === stream) this.recover();
      };
    }
    recover() {
      this.stream?.close();
      this.stream = null;
      this.clear(this.timer);
      if (this.closed) return;
      this.onConnection(false);
      const delay = Math.min(15000, 1000 * 2 ** Math.min(this.failures++, 4));
      this.timer = this.later(async () => {
        try {
          const run = await this.request(`/api/runs/${this.id}`);
          if (this.closed) return;
          this.accept(run);
          if (!this.closed) this.connect();
        } catch (error) {
          if (this.closed) return;
          if (error.status === 404) {
            this.close();
            this.onConnection(true);
            this.onMissing();
          } else this.recover();
        }
      }, delay);
    }
  }
  return { Client, RunWatch };
})();
if (typeof module !== "undefined" && module.exports)
  module.exports = EliotTransport;
