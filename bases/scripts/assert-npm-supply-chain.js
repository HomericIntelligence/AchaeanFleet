#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const { readFileSync } = require("node:fs");
const semver = require("/usr/local/lib/node_modules/npm/node_modules/semver");

const DEFAULT_PATHS = Object.freeze({
  npmPackagePath: "/usr/local/lib/node_modules/npm/package.json",
  tarPackagePath:
    "/usr/local/lib/node_modules/npm/node_modules/tar/package.json",
  npmExecutablePath: "/usr/local/bin/npm",
});
const minimumTarVersion = "7.5.21";

function inspectNpmSupplyChain(paths = DEFAULT_PATHS) {
  const npmPackage = JSON.parse(readFileSync(paths.npmPackagePath, "utf8"));
  const tarPackage = JSON.parse(readFileSync(paths.tarPackagePath, "utf8"));
  const npmCliVersion = execFileSync(paths.npmExecutablePath, ["--version"], {
    encoding: "utf8",
  }).trim();

  if (npmCliVersion !== npmPackage.version) {
    throw new Error(
      `npm CLI ${npmCliVersion} does not match installed package ${npmPackage.version}`,
    );
  }

  const validTarVersion = semver.valid(tarPackage.version);
  if (validTarVersion === null) {
    throw new Error(`Invalid tar semantic version: ${tarPackage.version}`);
  }

  if (!semver.gte(validTarVersion, minimumTarVersion)) {
    throw new Error(
      `npm ${npmPackage.version} bundles tar ${tarPackage.version}; ` +
        `required tar >=${minimumTarVersion}`,
    );
  }

  return {
    npm: npmPackage.version,
    tar: tarPackage.version,
    minimumTar: minimumTarVersion,
  };
}

if (require.main === module) {
  console.log(JSON.stringify(inspectNpmSupplyChain()));
}

module.exports = { DEFAULT_PATHS, inspectNpmSupplyChain };
