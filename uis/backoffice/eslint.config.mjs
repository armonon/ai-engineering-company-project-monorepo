// eslint-config-next 16 ships native flat-config entry points. Loading them
// through @eslint/eslintrc's FlatCompat (the create-next-app default) makes
// the validator walk the plugin graph and throw "Converting circular
// structure to JSON" before a single file is linted, so they are imported
// directly.
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    "node_modules/**",
    ".next/**",
    ".test-dist/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);
