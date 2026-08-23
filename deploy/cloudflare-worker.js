const BINANCE_ORIGINS = [
  "https://data-api.binance.vision",
  "https://api-gcp.binance.com",
  "https://api1.binance.com",
  "https://api2.binance.com",
  "https://api3.binance.com",
  "https://api4.binance.com",
];

async function fetchBinance(pathAndQuery) {
  const attempts = [];

  for (const origin of BINANCE_ORIGINS) {
    const target = new URL(pathAndQuery, origin);

    try {
      const response = await fetch(target, {
        method: "GET",
        headers: {
          Accept: "application/json",
          "User-Agent": "trade-bot-sim/1.0",
        },
        redirect: "manual",
      });

      attempts.push({ origin, status: response.status });
      if (response.status !== 403 && response.status !== 451) {
        return { response, origin };
      }
    } catch (error) {
      attempts.push({
        origin,
        error: error instanceof Error ? error.message : "Fetch failed",
      });
    }
  }

  return {
    diagnostic: new Response(
      JSON.stringify({
        error: "All approved Binance upstreams rejected the request",
        attempts,
      }),
      {
        status: 502,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      },
    ),
  };
}

export default {
  async fetch(request, env) {
    const suppliedToken = request.headers.get("X-Proxy-Token");
    if (!env.PROXY_TOKEN || suppliedToken !== env.PROXY_TOKEN) {
      return new Response("Unauthorized", { status: 401 });
    }

    const incoming = new URL(request.url);
    if (incoming.pathname.startsWith("/binance/")) {
      if (request.method !== "GET") {
        return new Response("Method not allowed", { status: 405 });
      }
      const path = incoming.pathname.slice("/binance".length);
      if (!path.startsWith("/api/v3/")) {
        return new Response("Forbidden path", { status: 403 });
      }

      const result = await fetchBinance(`${path}${incoming.search}`);
      if (result.diagnostic) {
        result.diagnostic.headers.set("Cache-Control", "no-store");
        return result.diagnostic;
      }

      const responseHeaders = new Headers();
      responseHeaders.set(
        "Content-Type",
        result.response.headers.get("Content-Type") || "application/json",
      );
      responseHeaders.set("Cache-Control", "no-store");
      responseHeaders.set("X-Proxy-Upstream", new URL(result.origin).hostname);
      responseHeaders.set(
        "X-Proxy-Upstream-Status",
        String(result.response.status),
      );

      return new Response(result.response.body, {
        status: result.response.status,
        headers: responseHeaders,
      });
    } else if (incoming.pathname === "/pushbullet/v2/pushes") {
      if (request.method !== "POST") {
        return new Response("Method not allowed", { status: 405 });
      }

      const target = new URL("https://api.pushbullet.com/v2/pushes");
      const headers = new Headers();
      headers.set("Access-Token", request.headers.get("Access-Token") || "");
      headers.set("Content-Type", "application/json");

      const upstream = await fetch(target, {
        method: request.method,
        headers,
        body: request.body,
        redirect: "manual",
      });

      return new Response(upstream.body, {
        status: upstream.status,
        headers: {
          "Content-Type":
            upstream.headers.get("Content-Type") || "application/json",
          "Cache-Control": "no-store",
          "X-Proxy-Upstream": target.hostname,
          "X-Proxy-Upstream-Status": String(upstream.status),
        },
      });
    } else {
      return new Response("Not found", { status: 404 });
    }
  },
};
