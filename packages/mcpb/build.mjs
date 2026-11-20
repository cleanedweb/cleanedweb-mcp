// Builds ../../dist/cleanedweb.mcpb: bundles the @cleanedweb/mcp proxy into one file, stages it with
// the manifest and icon, validates the manifest and packs it with the official mcpb CLI.
import { build } from "esbuild";
import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..");
const npmPkg = join(repo, "packages", "npm");
const stage = join(here, ".stage");
const out = join(repo, "dist", "cleanedweb.mcpb");
const { version } = JSON.parse(readFileSync(join(npmPkg, "package.json"), "utf8"));

rmSync(stage, { recursive: true, force: true });
mkdirSync(join(stage, "server"), { recursive: true });
mkdirSync(dirname(out), { recursive: true });

// One self-contained file: the bundle needs no node_modules.
await build({
  entryPoints: [join(npmPkg, "src", "cli.ts")],
  outfile: join(stage, "server", "index.js"),
  bundle: true,
  platform: "node",
  format: "esm",
  target: "node18",
  minify: false,
  legalComments: "none",
  banner: { js: 'import { createRequire as __cr } from "node:module"; const require = __cr(import.meta.url);' },
  // The proxy reads its version from ../package.json next to server/; the stage has one.
  logLevel: "warning",
});
// The CLI shebang from src/cli.ts is kept by esbuild at the top; drop it, the host runs `node index.js`.
const entry = join(stage, "server", "index.js");
writeFileSync(entry, readFileSync(entry, "utf8").replace(/^#!.*\n/, ""));

writeFileSync(join(stage, "package.json"), JSON.stringify({ name: "cleanedweb-mcpb", version, type: "module", license: "MIT" }, null, 2) + "\n");
const manifest = JSON.parse(readFileSync(join(here, "manifest.json"), "utf8"));
manifest.version = version;
writeFileSync(join(stage, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
cpSync(join(repo, ".claude-plugin", "icon.png"), join(stage, "icon.png"));
cpSync(join(repo, "LICENSE"), join(stage, "LICENSE"));

const mcpb = join(here, "node_modules", ".bin", "mcpb");
execFileSync(mcpb, ["validate", join(stage, "manifest.json")], { stdio: "inherit" });
rmSync(out, { force: true });
execFileSync(mcpb, ["pack", stage, out], { stdio: "inherit" });
rmSync(stage, { recursive: true, force: true });
console.log(`built ${out} (${(statSync(out).size / 1024).toFixed(0)} kB)`);
