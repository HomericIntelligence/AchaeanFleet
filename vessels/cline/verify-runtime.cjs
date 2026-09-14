"use strict";

const assert = require("node:assert/strict");
const sharp = require("sharp");

async function verify() {
  assert.equal(sharp.versions.sharp, "0.35.4");
  assert.equal(sharp.versions.heif, "1.23.2");

  // Exercise the metadata/resize/raw-buffer API used by ink-picture 1.3.x.
  // This generated input requires no network, files, model call or credentials.
  const png = await sharp({
    create: {
      width: 4,
      height: 4,
      channels: 4,
      background: { r: 40, g: 80, b: 120, alpha: 1 },
    },
  }).png().toBuffer();
  const image = sharp(png, { failOn: "none" });
  const metadata = await image.metadata();
  assert.equal(metadata.width, 4);
  assert.equal(metadata.height, 4);
  const result = await image.resize(2, 2, { fit: "fill" }).raw().toBuffer({ resolveWithObject: true });
  assert.equal(result.info.width, 2);
  assert.equal(result.info.height, 2);
  assert.equal(result.info.channels, 4);
  assert.equal(result.data.length, 16);
  console.log(JSON.stringify({ sharp: sharp.versions, imageApiProbe: "passed" }));
}

verify().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
