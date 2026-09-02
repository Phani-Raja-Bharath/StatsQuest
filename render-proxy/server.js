const http = require("http");
const httpProxy = require("http-proxy");

const port = Number(process.env.PORT || 10000);
const target = "https://statsquestformands.streamlit.app";
const publicHost = process.env.PUBLIC_HOST || "urban-digital-twin-lab.com";

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

proxy.on("proxyReq", rewriteOrigin);
proxy.on("proxyReqWs", rewriteOrigin);

proxy.on("proxyRes", (proxyResponse) => {
  const location = proxyResponse.headers.location;
  if (location) {
    proxyResponse.headers.location = location.replace(
      "https://statsquestformands.streamlit.app",
      `https://${publicHost}`,
    );
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