import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import {installFrontendConsoleLogger} from "./utils/logger";
import "./styles.css";

installFrontendConsoleLogger();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
