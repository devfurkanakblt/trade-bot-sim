export default {
  async fetch(request, env) {
    const suppliedToken = request.headers.get("X-Proxy-Token");
    if (!env.PROXY_TOKEN || suppliedToken !== env.PROXY_TOKEN) {
      return new Response("Unauthorized", { status: 401 });
    }

    const incoming = new URL(request.url);
    let target;
    const headers = new Headers();

    if (incoming.pathname.startsWith("/binance/")) {
      if (request.method !== "GET") {
        return new Response("Method not allowed", { status: 405 });
      }
      const path = incoming.pathname.slice("/binance".length);
      if (!path.startsWith("/api/v3/")) {
        return new Response("Forbidden path", { status: 403 });
      }
      target = new URL(`https://data-api.binance.vision${path}${incoming.search}`);
      headers.set("Accept", "application/json");
    } else if (incoming.pathname === "/pushbullet/v2/pushes") {
      if (request.method !== "POST") {
        return new Response("Method not allowed", { status: 405 });
      }
      target = new URL("https://api.pushbullet.com/v2/pushes");
      headers.set("Access-Token", request.headers.get("Access-Token") || "");
      headers.set("Content-Type", "application/json");
    } else {
      return new Response("Not found", { status: 404 });
    }

    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : request.body,
      redirect: "manual",
    });

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") || "application/json",
        "Cache-Control": "no-store",
      },
    });
  },
};
