/**
 * Claude Code PostToolUse 훅 — 편집 직후 자동 서식 교정
 *
 * 목적:
 *   Claude가 파일을 쓴 "그 순간" 서식을 맞춰두면, 잘못된 서식이 여러 파일에
 *   누적된 뒤 커밋 시점에 한꺼번에 터지는 일이 없어진다.
 *   즉 pre-commit 훅보다 한 단계 앞선 방어선이다.
 *
 * Node로 구현한 이유:
 *   Claude Code 훅은 stdin으로 JSON을 받는다. 흔히 jq로 파싱하지만
 *   Git for Windows에는 jq가 기본 포함되지 않는다. Node는 이 프로젝트에
 *   반드시 존재하므로(Next.js) 이식성 면에서 Node가 확실하다.
 *
 * 실패해도 절대 작업을 막지 않는다(항상 exit 0).
 * 서식은 편의 기능이고, 진짜 게이트는 pre-commit 훅과 CI다.
 */

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

/** stdin을 끝까지 읽어 문자열로 반환한다. */
async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

// Prettier가 처리할 수 있고, 자동 교정이 안전한 확장자만 대상으로 한다.
const FORMATTABLE = new Set([".ts", ".tsx", ".mts", ".js", ".mjs", ".cjs", ".json", ".css", ".md"]);
// ESLint까지 돌릴 대상(타입스크립트/자바스크립트).
const LINTABLE = new Set([".ts", ".tsx", ".mts", ".js", ".mjs", ".cjs"]);

// 프론트엔드 저장소 루트. 이 훅 파일 위치(.claude/hooks/)를 기준으로 역산한다.
const PROJECT_ROOT = path.resolve(import.meta.dirname, "..", "..");
const FRONTEND_ROOT = path.join(PROJECT_ROOT, "todo-frontend");

function run(command, args, cwd) {
  execFileSync(command, args, {
    cwd,
    stdio: "ignore",
    // Windows에서 npx/prettier는 .cmd 배치 파일이라 셸이 필요하다.
    shell: process.platform === "win32",
    timeout: 30_000,
  });
}

async function main() {
  const raw = await readStdin();
  if (!raw.trim()) return;

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return; // 예상과 다른 입력이면 조용히 종료한다.
  }

  const filePath = payload?.tool_response?.filePath ?? payload?.tool_input?.file_path;
  if (typeof filePath !== "string" || !filePath) return;

  const absolute = path.resolve(filePath);
  if (!existsSync(absolute)) return;

  // 프론트엔드 저장소 바깥의 파일은 다루지 않는다.
  // 자바 파일은 대상에서 제외한다 — Spotless는 JVM을 띄워야 해서
  // 편집 한 번마다 수 초가 걸리며, 커밋 훅에서 처리하는 편이 낫다.
  const relative = path.relative(FRONTEND_ROOT, absolute);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return;

  // 빌드 산출물·의존성은 건드리지 않는다.
  const normalized = relative.split(path.sep).join("/");
  if (/^(node_modules|\.next|out|build|coverage)\//.test(normalized)) return;

  const ext = path.extname(absolute).toLowerCase();
  if (!FORMATTABLE.has(ext)) return;

  try {
    run("npx", ["--no-install", "prettier", "--write", "--ignore-unknown", absolute], FRONTEND_ROOT);
  } catch {
    // 서식 실패는 무시한다(예: 문법 오류가 있는 중간 상태).
  }

  if (LINTABLE.has(ext)) {
    try {
      run("npx", ["--no-install", "eslint", "--fix", "--no-warn-ignored", absolute], FRONTEND_ROOT);
    } catch {
      // 자동수정으로 해결되지 않는 린트 오류는 여기서 막지 않는다.
      // 커밋 시점(pre-commit)에 정식으로 차단된다.
    }
  }
}

main()
  .catch(() => {})
  .finally(() => process.exit(0));
