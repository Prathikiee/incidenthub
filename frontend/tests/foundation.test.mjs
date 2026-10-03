import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test("IncidentHub Frontend Foundation - Project Structure", () => {
  const root = path.resolve(__dirname, "..");

  // Verify essential directories exist
  assert.ok(fs.existsSync(path.join(root, "app")), "app directory must exist");
  assert.ok(fs.existsSync(path.join(root, "components")), "components directory must exist");
  assert.ok(fs.existsSync(path.join(root, "lib")), "lib directory must exist");
  assert.ok(fs.existsSync(path.join(root, "public")), "public directory must exist");

  // Verify configuration files exist
  assert.ok(fs.existsSync(path.join(root, "package.json")), "package.json must exist");
  assert.ok(fs.existsSync(path.join(root, "tsconfig.json")), "tsconfig.json must exist");
  assert.ok(fs.existsSync(path.join(root, "next.config.ts")), "next.config.ts must exist");
  assert.ok(fs.existsSync(path.join(root, ".prettierrc")), ".prettierrc must exist");
});

test("IncidentHub Frontend Foundation - Page Configuration", () => {
  const pageFile = path.resolve(__dirname, "..", "app", "page.tsx");
  assert.ok(fs.existsSync(pageFile), "Landing page file must exist");

  const content = fs.readFileSync(pageFile, "utf-8");
  assert.match(content, /IncidentHub/, "Landing page must identify the project as IncidentHub");
});
