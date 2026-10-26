import deckyPlugin from "@decky/rollup";
import url from "@rollup/plugin-url";

// Fonts are inlined so the plugin never loads anything from the network
// and does not depend on how Decky serves static files.
export default deckyPlugin({
  plugins: [url({ include: ["**/*.woff2"], limit: Infinity })],
});
