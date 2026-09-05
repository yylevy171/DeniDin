import { createRoot } from "react-dom/client";
import { AppRegistry, I18nManager } from "react-native";
import App from "./App";

// Hebrew UI — lay everything out right-to-left. Combined with <html dir="rtl"> this makes
// flexDirection:"row" containers flow from the right.
I18nManager.allowRTL(true);
I18nManager.forceRTL(true);
try {
  document.documentElement.setAttribute("dir", "rtl");
} catch {
  /* non-browser render */
}

AppRegistry.registerComponent("webapp", () => App);
const root = createRoot(document.getElementById("root")!);
// react-native-web can also mount via AppRegistry.runApplication, but a plain React root
// keeps hot-reload simple and is all we need for a web-only target.
root.render(<App />);
