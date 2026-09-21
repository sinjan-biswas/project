import React from "react";
import * as ReactDOMClient from "react-dom/client";
import "@fortawesome/fontawesome-free/css/all.min.css";
import "../css/styles.css";

window.React = React;
window.ReactDOM = { createRoot: ReactDOMClient.createRoot };

await import("./camera-capture.js");
await import("./results-react.js");
await import("./app.js");

// app.js registered its DOMContentLoaded listener during import; the real
// event already fired, so fire a synthetic one now.
document.dispatchEvent(new Event("DOMContentLoaded", { bubbles: true }));