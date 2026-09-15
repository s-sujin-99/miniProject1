# 계획: PRD.md 기반 프로젝트 루트 CLAUDE.md 작성

## Context (배경)

사용자의 전역 `~/.claude/CLAUDE.md` 는 프로젝트마다 채워 넣도록 만들어진 **템플릿**이다 (섹션 제목이 모두 "[프로젝트별 추가]", "[TODO]" 로 되어 있음). 지금 `D:\claude\miniProject1` 루트에는 이 파일이 아직 없다. `docs\PRD.md` 에 이미 요구사항·기술스택·아키텍처 결정이 상세히 정의되어 있으므로, 이 내용을 바탕으로 템플릿의 빈 항목을 채워 **프로젝트 루트에 `CLAUDE.md`** 를 새로 만든다.

확인 결과 이 저장소는 아직 스캐폴딩 단계다 (백엔드는 Spring Initializr 기본 패키지 `com.example`, 프론트엔드는 `create-next-app` 직후 상태, 루트 git 저장소 없음). 따라서 CLAUDE.md는 "이미 구현된 코드 설명"이 아니라 **PRD가 정한 결정사항 + 실제 스캐폴딩 상태**를 기준으로 작성하고, 아직 안 된 부분(Flyway 미설치, 테스트 프레임워크 미구성 등)은 TODO로 명시한다.

## 조사로 확인한 사실

- 루트: `API.md`, `DATABASE.md` 는 루트에 있음. `docs/PRD.md`, `docs/ROADMAP.md` 는 `docs/` 하위에 있음.
  - **불일치 발견**: `docs/ROADMAP.md` T-01 규칙(줄 137)은 "문서 4종은 루트에 평평하게 둔다 (`docs/` 하위 아님)" 이라고 명시하는데, 실제로는 2종만 루트에 있고 2종은 `docs/` 안에 있다. PRD 본문의 상대링크(`./DATABASE.md` 등)도 PRD 위치 기준으로는 어긋난다. → CLAUDE.md에 "주의사항"으로 기록만 하고, 문서 재배치는 이번 작업 범위 밖(사용자가 요청 안 함, ponytail 원칙상 unrequested scope 확장 금지).
- `miniproject1-backend/pom.xml`: Spring Boot 4.1.1, Java 21, Maven, JWT(jjwt 0.12.6), PostgreSQL 드라이버, Spring Security(+OAuth2 client 지만 PRD 비목표에 소셜로그인 없음 — 스타터만 들어있고 미사용 추정), Lombok. **Flyway 의존성 없음** (PRD는 Flyway 요구).
- `miniproject1-frontend/package.json`: Next.js 16.3.5, React 19.2.8, Tailwind 4, shadcn, ESLint 9. **Vitest 없음** (PRD가 언급하는 FE 테스트 도구 미설치).
- 루트에 `.env.example`, `.editorconfig`, `README.md` 없음 (PRD 구조도에는 있어야 함).
- 루트는 git 저장소 아님(`Is a git repository: false`); `miniproject1-frontend/.git` 만 존재. 커밋 규칙 적용 시 어느 저장소 기준인지 주의 필요.

## 작성할 CLAUDE.md 구조 (전역 템플릿 섹션을 그대로 따르되 내용을 채움)

1. **개발 명령어** — 설치/개발서버/빌드/테스트/lint를 백엔드(`./mvnw ...`, Windows는 `mvnw.cmd`)와 프론트엔드(`npm run dev/build/lint`)로 나눠 기재. PostgreSQL 17 로컬 설치가 선행 조건임을 명시. 아직 없는 것(Flyway, Vitest, 백엔드 lint)은 "TODO(아직 미구성)"로 남김.
2. **프로젝트 구조** — 실제 디렉토리(`docs/`, `miniproject1-backend/`, `miniproject1-frontend/`, 루트의 `API.md`/`DATABASE.md`)를 있는 그대로 기록. PRD 4.1의 이상적 구조(`miniProject1_frontEnd` 등 카멜케이스, `tools/seed-generator/`)와 실제 폴더명(kebab-case)이 다르다는 점도 짧게 표시.
3. **핵심 기술 스택** — PRD §4 표를 실제 확인된 버전으로 채움(Spring Boot 4.1.1 / Java 21 / Next.js 16.3.5 / React 19.2.8 / PostgreSQL 17 / Maven / Flyway(예정) / JUnit5+Testcontainers / Vitest / Kakao Maps SDK).
4. **프로젝트 아키텍처** — PRD §4.2, §5, §6(F1~F3), §3.2 흐름을 요약: SSR 검색결과 + 클라이언트 지도/폼 구조, PostGIS 미사용(bounding box + Haversine, `DistanceCalculator` 인터페이스로 분리), 통계 캐시 테이블(`pharmacy_drug_price_stat`) 패턴과 재계산 트리거, `source`(SEED/FORM) 컬럼으로 확장성 확보. 주요 파일은 아직 없으므로 "참고 문서 경로"로 대체.
5. **개발 시 참고사항** — 변수/함수명 영어·주석/문서 한국어(전역 규칙), 테스트는 전면 커버리지가 아니라 Score 로직(F3) 중심(PRD §10 성공지표: 단위 테스트 ≥6개), 배포는 로컬 실행만(Docker 미사용, README만으로 재현 가능해야 함 — §8).
6. **자주 사용되는 개발 작업** — 새 기능/버그 수정 시 `docs/ROADMAP.md` 의 해당 태스크(T-xx) → `docs/PRD.md` 의 F-ID 요구사항/수용기준 → `DATABASE.md`/`API.md` 계약 순으로 대조 후 구현하라는 절차 명시.
7. **주의사항** — PRD §9 리스크 요약(목데이터 고지 배너 필수, `dataSource: "SEED"` 노출, 카카오맵 키는 `.env.local`로 관리·커밋 금지, 서버/DB 타임존 `Asia/Seoul` 고정), 위에서 발견한 문서 경로 불일치, Flyway·Vitest 미설치 상태 기록.
8. **Git 규칙** — 전역 규칙(한글 커밋, `feature/기능명`·`fix/버그명`, 작은 단위 커밋) 유지 + 루트 미초기화 상태 주석 추가.

## 언어 규칙 섹션 처리

전역 `~/.claude/CLAUDE.md` 에 이미 있는 "언어 및 커뮤니케이션 규칙" 섹션은 프로젝트 루트 CLAUDE.md에 **중복 포함하지 않는다** (전역 설정이 이미 모든 프로젝트에 적용됨). 대신 프로젝트 CLAUDE.md 맨 위에는 프로젝트명/한 줄 설명만 두고 바로 본문 섹션으로 들어간다.

## 검증

- 파일 작성 후 `Read` 로 최종 내용을 다시 확인해 표/링크가 깨지지 않았는지 확인.
- 마크다운이므로 별도 빌드/실행 검증은 불필요.
