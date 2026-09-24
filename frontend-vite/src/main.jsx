import React from "react";
import * as ReactDOMClient from "react-dom/client";
import "@fortawesome/fontawesome-free/css/all.min.css";


window.React = React;
window.ReactDOM = { createRoot: ReactDOMClient.createRoot };

await import("./liveness-widget.js");
await import("./results-react.js");
await import("./app.js");

// app.js and liveness-widget.js both expect DOMContentLoaded to have fired.
document.dispatchEvent(new Event("DOMContentLoaded", { bubbles: true }));