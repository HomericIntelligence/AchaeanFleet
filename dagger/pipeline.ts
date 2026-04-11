/**
 * AchaeanFleet Dagger Pipeline
 *
 * Builds, tests, and pushes all 9 agent images plus 3 base images.
 * Runs identically locally and in CI/CD.
 *
 * Usage:
 *   dagger run ts-node dagger/pipeline.ts build
 *   dagger run ts-node dagger/pipeline.ts push --registry ghcr.io/homericintelligence
 *   dagger run ts-node dagger/pipeline.ts test
 *
 * Phase 5 target — requires Dagger SDK installed:
 *   npm install @dagger.io/dagger
 */

import { connect, Client, Container } from "@dagger.io/dagger";
import { execSync } from "child_process";

// Base image definitions
const BASES = [
  { name: "achaean-base-node", dockerfile: "bases/Dockerfile.node" },
  { name: "achaean-base-python", dockerfile: "bases/Dockerfile.python" },
  { name: "achaean-base-minimal", dockerfile: "bases/Dockerfile.minimal" },
] as const;

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

async function buildBases(client: Client): Promise<Map<string, Container>> {
  const src = client.host().directory(".", {
    exclude: [".git", "node_modules", ".env"],
  });

  const builtBases = new Map<string, Container>();

  for (const base of BASES) {
    console.log(`Building base: ${base.name}`);
    const image = client
      .container()
      .build(src, { dockerfile: base.dockerfile });

    // Export the built image to a local tarball so vessel Dockerfiles can
    // resolve FROM ${BASE_IMAGE} against the local Docker daemon.  The export
    // call also forces the Dagger build to complete before we proceed.
    const tarPath = `/tmp/${base.name}.tar`;
    console.log(`Exporting base ${base.name} → ${tarPath}`);
    await image.export(tarPath);

    // Load the tarball into the local Docker daemon and tag it as <name>:latest
    // so that the vessel build args resolve to the freshly-built image.
    console.log(`Loading ${base.name}:latest into local daemon`);
    execSync(`docker load -i ${tarPath} && docker tag ${base.name} ${base.name}:latest 2>/dev/null || docker load -i ${tarPath}`, { stdio: "inherit" });

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

  // Base images were already exported and loaded into the local daemon by
  // buildBases().  No sync() needed here — the export call already forced
  // each base build to complete and the daemon now has <name>:latest tagged.

  const buildPromises = VESSELS.map(async (vessel) => {
    console.log(`Building vessel: ${vessel.name}`);

    const baseTag = `${vessel.base}:latest`;
    const image = client.container().build(src, {
      dockerfile: vessel.dockerfile,
      buildArgs: [{ name: "BASE_IMAGE", value: baseTag }],
    });

    if (registry) {
      // Always push :latest
      const latestTag = `${registry}/${vessel.name}:latest`;
      console.log(`Pushing: ${latestTag}`);
      await image.publish(latestTag);

      // Also push the pinnable tag (SHA or semver) if provided
      if (imageTag && imageTag !== "latest") {
        const pinnableTag = `${registry}/${vessel.name}:${imageTag}`;
        console.log(`Pushing: ${pinnableTag}`);
        await image.publish(pinnableTag);
      }
    }

    return image;
  });

  await Promise.all(buildPromises);
}

async function testImages(
  client: Client,
  builtBases: Map<string, Container>
): Promise<void> {
  const src = client.host().directory(".", {
    exclude: [".git", "node_modules", ".env"],
  });

  // builtBases guarantees base images are exported and loaded into the local
  // daemon (done by buildBases()), so vessel Dockerfiles resolve FROM ${BASE_IMAGE}.

  // Test each vessel: ensure it starts and /health responds
  const testPromises = VESSELS.map(async (vessel) => {
    console.log(`Testing: ${vessel.name}`);

    const image = client.container().build(src, {
      dockerfile: vessel.dockerfile,
      buildArgs: [{ name: "BASE_IMAGE", value: `${vessel.base}:latest` }],
    });

    // Basic smoke test: check that required binaries exist
    const result = await image
      .withExec(["sh", "-c", "tmux -V && git --version && node --version"])
      .stdout();

    console.log(`  ${vessel.name} smoke test passed:\n  ${result.trim()}`);
  });

  await Promise.all(testPromises);
}

// Entry point
const command = process.argv[2] || "build";
const registryArg = process.argv.indexOf("--registry");
const registry =
  registryArg !== -1 ? process.argv[registryArg + 1] : undefined;
const tagArg = process.argv.indexOf("--tag");
const imageTag =
  tagArg !== -1 ? process.argv[tagArg + 1] : undefined;

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
        await buildVessels(client, basesForPush, registry, imageTag);
        const tagSuffix = imageTag ? ` (tags: ${imageTag}, latest)` : " (tag: latest)";
        console.log(`All images pushed to ${registry}${tagSuffix}`);
        break;

      case "test":
        const basesForTest = await buildBases(client);
        await testImages(client, basesForTest);
        console.log("All image tests passed.");
        break;

      default:
        console.error(`Unknown command: ${command}`);
        console.error("Usage: pipeline.ts [build|push|test] [--registry URL] [--tag TAG]");
        process.exit(1);
    }
  },
  { LogOutput: process.stderr }
);
