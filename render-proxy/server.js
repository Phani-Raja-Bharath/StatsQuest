const http = require("http");
const httpProxy = require("http-proxy");

const port = Number(process.env.PORT || 10000);
const target = "https://statsquestformands.streamlit.app";
const publicHost = process.env.PUBLIC_HOST || "urban-digital-twin-lab.com";
const targetUrl = new URL(target);

const proxy = httpProxy.createProxyServer({
  target,
  changeOrigin: true,
  secure: true,
  xfwd: true,
  ws: true,
});

function rewriteOrigin(proxyRequest) {
  proxyRequest.setHeader("origin", target);
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

proxy.on("proxyReq", rewriteOrigin);
proxy.on("proxyReqWs", rewriteOrigin);

proxy.on("proxyRes", (proxyResponse, request) => {
  const location = proxyResponse.headers.location;
  if (location) {
    proxyResponse.headers.location = rewriteLocation(location, request);
  }
});

proxy.on("error", (error, request, response) => {
  console.error("Proxy error:", error.message);
  if (response && !response.headersSent) {
    response.writeHead(502, { "content-type": "text/plain" });
    response.end("The application is temporarily unavailable.");
  }
});

const server = http.createServer((request, response) => {
  proxy.web(request, response);
});

server.on("upgrade", (request, socket, head) => {
  proxy.ws(request, socket, head);
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Streamlit proxy listening on port ${port}`);
});
