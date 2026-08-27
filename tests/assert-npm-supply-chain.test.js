"use strict";

const assert = require("node:assert/strict");
const {
  chmodSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");
const test = require("node:test");

const guardPath =
  process.env.NPM_SUPPLY_CHAIN_GUARD_PATH ||
  path.resolve(__dirname, "../bases/scripts/assert-npm-supply-chain.js");
const { DEFAULT_PATHS, inspectNpmSupplyChain } = require(guardPath);

const cases = [
  { name: "version below floor", version: "7.5.20", accepted: false },
  { name: "prerelease at floor", version: "7.5.21-rc.1", accepted: false },
  { name: "malformed version", version: "7.5.21-", accepted: false },
  { name: "stable version at floor", version: "7.5.21", accepted: true },
  { name: "stable version above floor", version: "7.5.22", accepted: true },
];

test("production paths point to the installed npm supply chain", () => {
  assert.deepEqual(DEFAULT_PATHS, {
    npmPackagePath: "/usr/local/lib/node_modules/npm/package.json",
    tarPackagePath:
      "/usr/local/lib/node_modules/npm/node_modules/tar/package.json",
    npmExecutablePath: "/usr/local/bin/npm",
  });
});

test("tar version validation follows strict SemVer precedence", () => {
  const fixtureRoot = mkdtempSync(
    path.join(tmpdir(), "achaean-npm-supply-chain-test-"),
  );
  const npmPackagePath = path.join(fixtureRoot, "npm", "package.json");
  const tarPackagePath = path.join(fixtureRoot, "tar", "package.json");
  const npmExecutablePath = path.join(fixtureRoot, "npm-cli");

  try {
    mkdirSync(path.dirname(npmPackagePath), { recursive: true });
    mkdirSync(path.dirname(tarPackagePath), { recursive: true });
    writeFileSync(npmPackagePath, '{"version":"11.19.1"}\n');
    writeFileSync(
      npmExecutablePath,
      "#!/bin/sh\nprintf '%s\\n' '11.19.1'\n",
    );
    chmodSync(npmExecutablePath, 0o755);

    for (const testCase of cases) {
      writeFileSync(
        tarPackagePath,
        `${JSON.stringify({ version: testCase.version })}\n`,
      );

      let result;
      let error;
      try {
        result = inspectNpmSupplyChain({
          npmPackagePath,
          tarPackagePath,
          npmExecutablePath,
        });
      } catch (caughtError) {
        error = caughtError;
      }

      assert.equal(
        error === undefined,
        testCase.accepted,
        `${testCase.name} (${testCase.version}) produced ${error || "success"}`,
      );
      if (testCase.accepted) {
        assert.equal(result.tar, testCase.version);
      }
    }
  } finally {
    rmSync(fixtureRoot, { recursive: true, force: true });
  }
});
