import React from "react";
import * as ReactDOMClient from "react-dom/client";
import "@fortawesome/fontawesome-free/css/all.min.css";
import "./index.css";   

window.React = React;
window.ReactDOM = { createRoot: ReactDOMClient.createRoot };

await import("./liveness-widget.js");
await import("./results-react.js");
await import("./stage-details.js");   // ← NEW
await import("./app.js");

document.dispatchEvent(new Event("DOMContentLoaded", { bubbles: true }));