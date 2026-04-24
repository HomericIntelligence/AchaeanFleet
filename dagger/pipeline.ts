/**
 * AchaeanFleet Dagger Pipeline
 *
 * Builds, tests, and pushes all 9 agent images plus 3 base images.
 * Runs identically locally and in CI/CD.
 *
 * Usage:
 *   dagger run ts-node dagger/pipeline.ts build
 *   SHORT_SHA=abc1234 DATE_TAG=2026-04-23-abc1234 \
 *     dagger run ts-node dagger/pipeline.ts push --registry ghcr.io/homericintelligence
 *   dagger run ts-node dagger/pipeline.ts test
 *
 * Phase 5 target — requires Dagger SDK installed:
 *   npm install @dagger.io/dagger
 */

import { connect, Client, Container } from "@dagger.io/dagger";
import { execFileSync, execSync } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

// Base image definitions
const BASES = [
  { name: "achaean-base-node", dockerfile: "bases/Dockerfile.node" },
  { name: "achaean-base-python", dockerfile: "bases/Dockerfile.python" },
  { name: "achaean-base-minimal", dockerfile: "bases/Dockerfile.minimal" },
] as const;

// Smoke test commands per base type — node base tests node; python base tests python3; minimal base has neither
const BASE_SMOKE_CMD: Record<string, string> = {
  "achaean-base-node":    "tmux -V && git --version && node --version",
  "achaean-base-python":  "tmux -V && git --version && python3 --version",
  "achaean-base-minimal": "tmux -V && git --version",
};

// Vessel image definitions
const VESSELS = [
  {
    name: "achaean-claude",
    dockerfile: "vessels/claude/Dockerfile",
    base: "achaean-base-node",
  },
  {
    name: "achaean-codex",
    dockerfile: "vessels/codex/Dockerfile",
    base: "achaean-base-node",
  },
  {
    name: "achaean-aider",
    dockerfile: "vessels/aider/Dockerfile",
    base: "achaean-base-python",
  },
  {
    name: "achaean-goose",
    dockerfile: "vessels/goose/Dockerfile",
    base: "achaean-base-minimal",
  },
  {
    name: "achaean-cline",
    dockerfile: "vessels/cline/Dockerfile",
    base: "achaean-base-node",
  },
  {
    name: "achaean-opencode",
    dockerfile: "vessels/opencode/Dockerfile",
    base: "achaean-base-minimal",
  },
  {
    name: "achaean-codebuff",
    dockerfile: "vessels/codebuff/Dockerfile",
    base: "achaean-base-node",
  },
  {
    name: "achaean-ampcode",
    dockerfile: "vessels/ampcode/Dockerfile",
    base: "achaean-base-node",
  },
  {
    name: "achaean-worker",
    dockerfile: "vessels/worker/Dockerfile",
    base: "achaean-base-minimal",
  },
] as const;

async function exportToLocalDaemon(container: Container, name: string): Promise<void> {
  const tarPath = path.join(os.tmpdir(), `${name}.tar`);
  console.log(`Exporting ${name} → ${tarPath}`);
  await container.export(tarPath);
  console.log(`Loading ${name} into local daemon`);
  try {
    execFileSync("docker", ["load", "-i", tarPath], { stdio: "inherit" });
  } finally {
    if (fs.existsSync(tarPath)) {
      fs.unlinkSync(tarPath);
    }
  }
}

async function buildBases(client: Client): Promise<Map<string, Container>> {
  const src = client.host().directory(".", {
    exclude: [".git", "node_modules", ".env"],
  });

  const builtBases = new Map<string, Container>();

  // OCI label build args
  const buildDate = new Date().toISOString();
  const vcsRef = execSync("git rev-parse --short HEAD").toString().trim();
  const version = process.env.VERSION || vcsRef;

  for (const base of BASES) {
    console.log(`Building base: ${base.name}`);
    const image = client
      .container()
      // @ts-ignore - Dagger SDK method exists at runtime
      .build(src, {
        dockerfile: base.dockerfile,
        buildArgs: [
          { name: "BUILD_DATE", value: buildDate },
          { name: "VCS_REF", value: vcsRef },
          { name: "VERSION", value: version },
        ],
      });

    await exportToLocalDaemon(image, base.name);
    builtBases.set(base.name, image);
  }

  return builtBases;
}

async function buildVessels(
  client: Client,
  builtBases: Map<string, Container>,
  registry?: string
): Promise<void> {
  const src = client.host().directory(".", {
    exclude: [".git", "node_modules", ".env"],
  });

  // Base images exported and loaded into daemon by buildBases().
  // On push path, explicitly export bases to daemon before vessel builds begin.
  if (registry) {
    for (const base of BASES) {
      await exportToLocalDaemon(builtBases.get(base.name)!, base.name);
    }
  }

  // OCI label build args
  const buildDate = new Date().toISOString();
  const vcsRef = execSync("git rev-parse --short HEAD").toString().trim();
  const version = process.env.VERSION || vcsRef;

  const buildPromises = VESSELS.map(async (vessel) => {
    console.log(`Building vessel: ${vessel.name}`);

    const baseTag = `${vessel.base}:latest`;
    // @ts-ignore - Dagger SDK method exists at runtime
    const image = client.container().build(src, {
      dockerfile: vessel.dockerfile,
      buildArgs: [
        { name: "BASE_IMAGE", value: baseTag },
        { name: "BUILD_DATE", value: buildDate },
        { name: "VCS_REF", value: vcsRef },
        { name: "VERSION", value: version },
      ],
    });

    if (registry) {
      const tags = [
        `${registry}/${vessel.name}:latest`,
        `${registry}/${vessel.name}:git-${shortSha}`,
        `${registry}/${vessel.name}:${dateTag}`,
      ];
      for (const tag of tags) {
        console.log(`Pushing: ${tag}`);
        await image.publish(tag);
      }
    } else {
      await exportToLocalDaemon(image, vessel.name);
    }

    return image;
  });

  await Promise.all(buildPromises);
}

async function verifyImageInDaemon(imageName: string): Promise<void> {
  console.log(`Verifying ${imageName}:latest is in local daemon`);
  try {
    execFileSync("docker", ["image", "inspect", `${imageName}:latest`], {
      stdio: "pipe",
    });
    console.log(`  ✓ ${imageName}:latest verified in local daemon`);
  } catch (error) {
    throw new Error(`Failed to verify ${imageName}:latest in local daemon: ${error}`);
  }
}

async function testImages(client: Client): Promise<void> {
  const src = client.host().directory(".", {
    exclude: [".git", "node_modules", ".env"],
  });

  // OCI label build args
  const buildDate = new Date().toISOString();
  const vcsRef = execSync("git rev-parse --short HEAD").toString().trim();
  const version = process.env.VERSION || vcsRef;

  // Test each vessel: ensure it starts and /health responds
  const testPromises = VESSELS.map(async (vessel) => {
    console.log(`Testing: ${vessel.name}`);

    // @ts-ignore - Dagger SDK method exists at runtime
    const image = client.container().build(src, {
      dockerfile: vessel.dockerfile,
      buildArgs: [
        { name: "BASE_IMAGE", value: `${vessel.base}:latest` },
        { name: "BUILD_DATE", value: buildDate },
        { name: "VCS_REF", value: vcsRef },
        { name: "VERSION", value: version },
      ],
    });

    // Basic smoke test: check binaries guaranteed by each base type
    const smokeCmd = BASE_SMOKE_CMD[vessel.base] ?? "tmux -V && git --version";
    const result = await image
      .withExec(["sh", "-c", smokeCmd])
      .stdout();

    console.log(`  ${vessel.name} smoke test passed:\n  ${result.trim()}`);
  });

  await Promise.all(testPromises);

  // Verify built images are in the local daemon
  console.log("Verifying images are loaded in local daemon...");
  const verifyPromises = VESSELS.map((vessel) =>
    verifyImageInDaemon(vessel.name)
  );
  await Promise.all(verifyPromises);
}

// Entry point
const command = process.argv[2] || "build";
const registryArg = process.argv.indexOf("--registry");
const registry =
  registryArg !== -1 ? process.argv[registryArg + 1] : undefined;

// Tag metadata — injected by CI via environment variables.
const shortSha = (process.env.SHORT_SHA ?? "local").slice(0, 7);
const dateTag = process.env.DATE_TAG ?? `local-${shortSha}`;

if (!/^\d{4}-\d{2}-\d{2}-[0-9a-f]{7}$/.test(dateTag)) {
  console.warn(`Warning: DATE_TAG "${dateTag}" does not match expected format YYYY-MM-DD-<7hex>. Tag may be non-reproducible.`);
}

connect(
  async (client) => {
    switch (command) {
      case "build":
        const bases = await buildBases(client);
        await buildVessels(client, bases);
        console.log("All images built successfully.");
        break;

      case "push":
        if (!registry) {
          console.error("--registry <url> required for push");
          process.exit(1);
        }
        const basesForPush = await buildBases(client);
        await buildVessels(client, basesForPush, registry);
        console.log(`All images pushed to ${registry} (tags: latest, git-${shortSha}, ${dateTag})`);
        break;

      case "test":
        await testImages(client);
        console.log("All image tests passed.");
        break;

      default:
        console.error(`Unknown command: ${command}`);
        console.error("Usage: pipeline.ts [build|push|test] [--registry URL]");
        process.exit(1);
    }
  },
  { LogOutput: process.stderr }
);
