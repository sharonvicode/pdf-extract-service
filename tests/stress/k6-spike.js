// Spike test of POST /extract, reproducing the professor's profile:
// 0 -> 100 VUs in 10 s, 20 s at 100 VUs, 100 -> 0 VUs in 10 s.
//
// Usage (from the repo root, with the service running):
//   docker run --rm -v "$PWD/tests/stress:/scripts" -e BASE_URL=http://host.docker.internal:8080 \
//     grafana/k6 run /scripts/k6-spike.js
// PDF_SET picks the documents: "profesor" (default, the TP's official set) or "sinteticos".
import http from "k6/http";
import { check } from "k6";
import exec from "k6/execution";
import { open, SeekMode } from "k6/experimental/fs";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const PDF_SETS = {
  profesor: {
    dir: "./pdfs",
    names: [
      "2020-Scrum-Guide-Spanish-Latin-South-American.pdf",
      "Essential-Kanban-Condensed-Spanish.pdf",
      "Filosofia Lean.pdf",
      "scrum_manager_historias_usuario.pdf",
    ],
  },
  sinteticos: {
    dir: "./pdfs-sinteticos",
    names: ["largo.pdf", "liviano.pdf", "mediano.pdf", "pesado.pdf"],
  },
};
const PDF_SET = PDF_SETS[__ENV.PDF_SET || "profesor"];

// k6/experimental/fs keeps one copy of each file shared by all VUs. The classic
// open() would load a copy per VU: 100 VUs x 13.7 MB of PDFs = ~1.4 GB of RAM.
const pdfs = await Promise.all(
  PDF_SET.names.map(async (name) => ({ name, file: await open(`${PDF_SET.dir}/${name}`) })),
);

export const options = {
  scenarios: {
    spike: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 100 },
        { duration: "20s", target: 100 },
        { duration: "10s", target: 0 },
      ],
    },
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "max"],
};

async function readWhole(file) {
  const { size } = await file.stat();
  const buffer = new Uint8Array(size);
  await file.seek(0, SeekMode.Start);
  let offset = 0;
  while (offset < size) {
    const bytesRead = await file.read(buffer.subarray(offset));
    if (bytesRead === null) break;
    offset += bytesRead;
  }
  return buffer.buffer;
}

export default async function () {
  // Rotate the 4 PDFs in order, so every run sends the same mix.
  const pdf = pdfs[exec.scenario.iterationInTest % pdfs.length];
  const body = { file: http.file(await readWhole(pdf.file), pdf.name, "application/pdf") };

  const response = http.post(`${BASE_URL}/extract`, body, { tags: { pdf: pdf.name } });

  check(response, { "status 200": (r) => r.status === 200 });
}
