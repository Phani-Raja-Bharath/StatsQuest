const http = require("http");
const httpProxy = require("http-proxy");

const port = Number(process.env.PORT || 10000);
const target = "https://statsquestformands.streamlit.app";
const publicHost = process.env.PUBLIC_HOST || "urban-digital-twin-lab.com";
const targetUrl = new URL(target);
const proxyVersion = "2026-09-02-url-rewrite-v2";

const proxy = httpProxy.createProxyServer({
  target,
  changeOrigin: true,
  secure: true,
  xfwd: true,
  ws: true,
  selfHandleResponse: true,
});

function rewriteOrigin(proxyRequest) {
  proxyRequest.setHeader("origin", target);
  proxyRequest.setHeader("referer", `${target}/`);
  proxyRequest.setHeader("accept-encoding", "identity");
}

function getPublicOrigin(request) {
  const forwardedProto = request.headers["x-forwarded-proto"];
  const forwardedHost = request.headers["x-forwarded-host"];
  const proto = Array.isArray(forwardedProto)
    ? forwardedProto[0]
    : forwardedProto || "https";
  const host = Array.isArray(forwardedHost)
    ? forwardedHost[0]
    : forwardedHost || request.headers.host || publicHost;

  return `${proto.split(",")[0]}://${host.split(",")[0]}`;
}

function rewriteLocation(location, request) {
  if (!location) {
    return location;
  }

  const publicOrigin = getPublicOrigin(request);

  if (location.startsWith("//")) {
    return location.replace(`//${targetUrl.host}`, publicOrigin);
  }

  try {
    const parsed = new URL(location);
    if (parsed.host === targetUrl.host) {
      return `${publicOrigin}${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    return location;
  }

  return location;
}

function rewriteHeaderValue(value, request) {
  if (Array.isArray(value)) {
    return value.map((item) => rewriteHeaderValue(item, request));
  }

  if (typeof value !== "string") {
    return value;
  }

  const publicOrigin = getPublicOrigin(request);
  const publicHostName = new URL(publicOrigin).host;

  return value
    .replaceAll(target, publicOrigin)
    .replaceAll(targetUrl.host, publicHostName)
    .replaceAll(`Domain=${targetUrl.host}`, `Domain=${publicHostName}`);
}

proxy.on("proxyReq", rewriteOrigin);
proxy.on("proxyReqWs", rewriteOrigin);

proxy.on("proxyRes", (proxyResponse, request, response) => {
  const location = proxyResponse.headers.location;
  if (location) {
    proxyResponse.headers.location = rewriteLocation(location, request);
  }

  Object.entries(proxyResponse.headers).forEach(([name, value]) => {
    proxyResponse.headers[name] = rewriteHeaderValue(value, request);
  });

  proxyResponse.headers["x-statsquest-proxy"] = proxyVersion;

  const chunks = [];

  proxyResponse.on("data", (chunk) => {
    chunks.push(chunk);
  });

  proxyResponse.on("end", () => {
    if (!response || response.destroyed) {
      return;
    }

    const body = Buffer.concat(chunks);
    const contentType = proxyResponse.headers["content-type"] || "";
    const isTextResponse =
      contentType.includes("text/") ||
      contentType.includes("javascript") ||
      contentType.includes("json");

    let responseBody = body;
    const publicOrigin = getPublicOrigin(request);

    if (isTextResponse && body.length > 0) {
      responseBody = Buffer.from(
        body
          .toString("utf8")
          .replaceAll(target, publicOrigin)
          .replaceAll(targetUrl.host, new URL(publicOrigin).host),
        "utf8",
      );
      proxyResponse.headers["content-length"] = Buffer.byteLength(responseBody);
    }

    delete proxyResponse.headers["content-encoding"];
    delete proxyResponse.headers["content-security-policy"];
    delete proxyResponse.headers["content-security-policy-report-only"];
    response.writeHead(proxyResponse.statusCode || 200, proxyResponse.headers);
    response.end(responseBody);
  });
});

proxy.on("error", (error, request, response) => {
  console.error("Proxy error:", error.message);
  if (response && !response.headersSent) {
    response.writeHead(502, { "content-type": "text/plain" });
    response.end("The application is temporarily unavailable.");
  }
});

const server = http.createServer((request, response) => {
  if (request.url === "/__proxy_health") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        ok: true,
        service: "statsquest-streamlit-proxy",
        version: proxyVersion,
        target,
        host: request.headers.host,
        forwardedHost: request.headers["x-forwarded-host"],
        forwardedProto: request.headers["x-forwarded-proto"],
      }),
    );
    return;
  }

  proxy.web(request, response);
});

server.on("upgrade", (request, socket, head) => {
  proxy.ws(request, socket, head);
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Streamlit proxy listening on port ${port}`);
});
