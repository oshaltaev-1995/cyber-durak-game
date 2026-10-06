import { readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const htmlPath = join(root, process.argv[2] ?? 'src/index.html');
const imagePath = join(root, process.argv[3] ?? 'public/assets/kiba-social-preview-v2.jpg');
const html = readFileSync(htmlPath, 'utf8');
const description =
  'A tactical card game inspired by Durak, with arithmetic combinations, transfers, advanced throw-ins and real-time PvP.';

const readAttribute = (tag, name) => tag.match(new RegExp(`\\b${name}="([^"]*)"`))?.[1];
const metaTags = [...html.matchAll(/<meta\s+[^>]*>/g)].map((match) => match[0]);
const linkTags = [...html.matchAll(/<link\s+[^>]*>/g)].map((match) => match[0]);

const expectedMeta = new Map([
  ['description', description],
  ['og:type', 'website'],
  ['og:site_name', 'KIBA'],
  ['og:title', 'KIBA — Arithmetic Durak'],
  ['og:description', description],
  ['og:url', 'https://cyberdurak.com/'],
  ['og:image', 'https://cyberdurak.com/assets/kiba-social-preview-v2.jpg'],
  ['og:image:secure_url', 'https://cyberdurak.com/assets/kiba-social-preview-v2.jpg'],
  ['og:image:type', 'image/jpeg'],
  ['og:image:width', '1200'],
  ['og:image:height', '630'],
  ['og:image:alt', 'KIBA arithmetic card game table'],
  ['og:locale', 'en_US'],
  ['og:locale:alternate', 'ru_RU'],
  ['twitter:card', 'summary_large_image'],
  ['twitter:title', 'KIBA — Arithmetic Durak'],
  ['twitter:description', description],
  ['twitter:image', 'https://cyberdurak.com/assets/kiba-social-preview-v2.jpg'],
  ['twitter:image:alt', 'KIBA arithmetic card game table'],
]);

const titleMatches = [...html.matchAll(/<title>([^<]+)<\/title>/g)];
if (titleMatches.length !== 1 || titleMatches[0][1] !== 'KIBA — Arithmetic Durak') {
  throw new Error('The exact document title must appear exactly once.');
}

const canonicalTags = linkTags.filter((tag) => readAttribute(tag, 'rel') === 'canonical');
if (
  canonicalTags.length !== 1 ||
  readAttribute(canonicalTags[0], 'href') !== 'https://cyberdurak.com/'
) {
  throw new Error('The exact canonical URL must appear exactly once.');
}

for (const [key, content] of expectedMeta) {
  const attribute = key.startsWith('og:') ? 'property' : 'name';
  const matches = metaTags.filter((tag) => readAttribute(tag, attribute) === key);
  if (matches.length !== 1 || readAttribute(matches[0], 'content') !== content) {
    throw new Error(`${key} must appear exactly once with exact content.`);
  }
}

if (html.includes('kiba-social-preview-v1.jpg')) {
  throw new Error('Initial HTML must not retain an active v1 social preview reference.');
}

const image = readFileSync(imagePath);
if (image[0] !== 0xff || image[1] !== 0xd8) throw new Error('Preview asset is not a JPEG.');

let offset = 2;
let dimensions;
while (offset < image.length - 9) {
  if (image[offset] !== 0xff) {
    offset += 1;
    continue;
  }
  const marker = image[offset + 1];
  const length = image.readUInt16BE(offset + 2);
  if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb].includes(marker)) {
    dimensions = {
      height: image.readUInt16BE(offset + 5),
      width: image.readUInt16BE(offset + 7),
    };
    break;
  }
  offset += 2 + length;
}

if (dimensions?.width !== 1200 || dimensions.height !== 630) {
  throw new Error(`Preview dimensions must be 1200×630; found ${JSON.stringify(dimensions)}`);
}
const size = statSync(imagePath).size;
if (size >= 300 * 1024) throw new Error(`Preview must stay below 300 KiB; found ${size} bytes.`);

console.log(
  `Social metadata valid; preview=${dimensions.width}x${dimensions.height}, ${size} bytes.`,
);
