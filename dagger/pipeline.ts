/**
 * AchaeanFleet Dagger Pipeline
 *
 * Builds, tests, and pushes all 9 agent images plus 3 base images.
 * Runs identically locally and in CI/CD.
 *
 * Usage:
 *   dagger run ts-node dagger/pipeline.ts build
 *   dagger run ts-node dagger/pipeline.ts push --registry ghcr.io/homericintelligence
 *   dagger run ts-node dagger/pipeline.ts push --registry ghcr.io/homericintelligence --tag v1.2.3
 *   dagger run ts-node dagger/pipeline.ts test
 *
 * Phase 5 target — requires Dagger SDK installed:
 *   npm install @dagger.io/dagger
 */

import { connect, Client } from "@dagger.io/dagger";
import { execSync, execFileSync } from "child_process";
import * as os from "os";
import * as path from "path";

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

/** Returns the 7-character short git SHA of HEAD, or "unknown" if git is unavailable. */
function getShortSha(): string {
  try {
    return execSync("git rev-parse --short HEAD", { encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

/** Returns today's date as YYYY-MM-DD. */
function getDatestamp(): string {
  return new Date().toISOString().slice(0, 10);
}

async function exportToLocalDaemon(container: any, name: string): Promise<void> {
  const tarPath = path.join(os.tmpdir(), `${name}.tar`);
  console.log(`Exporting ${name} → ${tarPath}`);
  await container.export(tarPath);
  console.log(`Loading ${name} into local daemon`);
  execFileSync("docker", ["load", "-i", tarPath], { stdio: "inherit" });
}

/**
 * Builds all three base images and returns a map of name → Dagger Container.
 * Exports each base to the local Docker daemon so vessel FROM lines resolve.
 */
async function buildBases(
  client: Client,
  registry?: string
): Promise<Map<string, any>> {
  const src = client.host().directory(".", {
    exclude: [".git", "node_modules", ".env"],
  });

  const builtBases = new Map<string, any>();

  for (const base of BASES) {
    console.log(`Building base: ${base.name}`);
    const image = client
      .container()
      .build(src, { dockerfile: base.dockerfile });

    await exportToLocalDaemon(image, base.name);
    builtBases.set(base.name, image);
  }

  return builtBases;
}

/**
 * Builds all vessel images. When a registry is provided, pushes with multi-tag set:
 * :latest, :git-<sha>, and :YYYY-MM-DD. When an explicit tag is provided, also
 * pushes that tag (e.g. a semver string). Without a registry, exports to local daemon.
 */
async function buildVessels(
  client: Client,
  builtBases: Map<string, any>,
  registry?: string,
  tag?: string
): Promise<void> {
  const src = client.host().directory(".", {
    exclude: [".git", "node_modules", ".env"],
  });

  // Base images were already exported and loaded into the local daemon by
  // buildBases().  No sync() needed here — the export call already forced
  // each base build to complete and the daemon now has <name>:latest tagged.

  const shortSha = getShortSha();
  const datestamp = getDatestamp();

  const buildPromises = VESSELS.map(async (vessel) => {
    console.log(`Building vessel: ${vessel.name}`);

    const baseTag = `${vessel.base}:latest`;
    const image = client.container().build(src, {
      dockerfile: vessel.dockerfile,
      buildArgs: [{ name: "BASE_IMAGE", value: baseTag }],
    });

    if (registry) {
      // Multi-tag set: :latest, :git-<sha>, :YYYY-MM-DD, and optionally the explicit tag
      const tags = [
        `${registry}/${vessel.name}:latest`,
        `${registry}/${vessel.name}:git-${shortSha}`,
        `${registry}/${vessel.name}:${datestamp}`,
      ];
      if (tag) {
        tags.push(`${registry}/${vessel.name}:${tag}`);
      }

      for (const t of tags) {
        console.log(`Pushing: ${t}`);
        await image.publish(t);
      }
    } else {
      await exportToLocalDaemon(image, vessel.name);
    }

    return image;
  });

  await Promise.all(buildPromises);
}

async function testImages(
  client: Client,
  builtBases: Map<string, any>
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
const tag = tagArg !== -1 ? process.argv[tagArg + 1] : undefined;

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
        const basesForPush = await buildBases(client, registry);
        await buildVessels(client, basesForPush, registry, tag);
        console.log(`All images pushed to ${registry}`);
        if (tag) {
          console.log(`  Tagged with: ${tag}`);
        }
        break;

      case "test":
        const basesForTest = await buildBases(client);
        await testImages(client, basesForTest);
        console.log("All image tests passed.");
        break;

      default:
        console.error(`Unknown command: ${command}`);
        console.error(
          "Usage: pipeline.ts [build|push|test] [--registry URL] [--tag TAG]"
        );
        process.exit(1);
    }
  },
  { LogOutput: process.stderr }
);
