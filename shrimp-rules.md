# Development Guidelines — 약값알림 (miniProject1)

AI Agent 전용 프로젝트 규칙. 일반 지식은 담지 않는다.
**우선순위: 이 문서 > `PRD.md` · `API.md` · `DATABASE.md` · `ROADMAP.md`.** 충돌 지점은 §2에 정리했다.

---

## 1. 저장소 구조

### 1.1 독립된 git 저장소 3개

```
D:\claude\miniProject1\              ← 저장소 ① 문서 + .claude 설정
├─ PRD.md · API.md · DATABASE.md · docs/ROADMAP.md
├─ shrimp-rules.md · .gitignore (하위 두 저장소 제외)
├─ miniproject1-frontend/            ← 저장소 ② Next.js 16
└─ miniproject1-backend/             ← 저장소 ③ Spring Boot 4.1.1
```

- 작업 전 `git rev-parse --show-toplevel`로 현재 저장소를 확인한다.
- 서로 다른 저장소의 변경을 한 커밋에 섞지 않는다. 커밋 요청 시 대상 저장소가 모호하면 확인한다.
- 루트 `.gitignore`에서 `miniproject1-frontend/`, `miniproject1-backend/` 항목을 **삭제하지 않는다** (삭제 시 gitlink로 깨져 커밋됨).
- GitHub 원격은 아직 없다. `git push`는 사용자 요청 시에만.

### 1.2 백엔드 — `com.example` 레이어 구조 (확정)

```
src/main/java/com/example/
├─ domain/       엔티티 + Repository
├─ service/      비즈니스 로직, @Transactional 경계
├─ controller/   REST API (@RestController)
├─ dto/          요청/응답 DTO
├─ config/       SecurityConfig, CorsConfig, OpenApiConfig, JPA Auditing
└─ exception/    GlobalExceptionHandler, ErrorCode, BusinessException
```

- **도메인별 패키지(`com.pharmaprice.auth` 등)를 만들지 않는다.** ROADMAP의 `com.pharmaprice.*` 경로는 모두 위 레이어 구조로 치환해 읽는다 (예: `recommendation/service/ScoreCalculator` → `service/ScoreCalculator`).
- 파일이 많아지면 레이어 **안에서** 하위 폴더를 쓴다 (`dto/auth/`, `dto/report/`). 레이어를 뒤집지 않는다.

#### ⚠️ Jackson 3 (Spring Boot 4.1의 breaking change, 실제로 겪은 문제)

Spring Boot 4.1은 **Jackson 3**을 기본 JSON 엔진으로 쓴다. Jackson 3는 groupId/패키지가 `com.fasterxml.jackson.*`이 아니라 **`tools.jackson.*`로 완전히 바뀐 별개의 라이브러리**다 (`tools.jackson.databind.ObjectMapper` 등). Spring이 자동 등록하는 `ObjectMapper` 빈은 이 Jackson 3 타입이다.

- **`com.fasterxml.jackson.databind.ObjectMapper`를 주입받으려 하면 "No qualifying bean" 에러가 난다.** 반드시 `tools.jackson.databind.ObjectMapper`를 import한다.
- 예외: `jjwt-jackson`(JWT 라이브러리)은 아직 구식 Jackson 2(`com.fasterxml.jackson.core:jackson-databind`)를 내부적으로 쓴다 — 이건 jjwt 자체 용도이고 Spring 빈이 아니므로 그대로 둔다. 두 Jackson이 클래스패스에 공존하는 것은 정상이다.
- DTO의 `@JsonProperty`, `@JsonIgnore` 등 애노테이션도 Jackson 3 기준(`tools.jackson.databind.annotation.*` 또는 호환 애노테이션 위치)을 확인하고 쓴다. 확신이 없으면 실제로 `./mvnw compile`을 돌려 import 오류로 확인한다 — 추측하지 않는다.
- 이 문제는 `docs/guides/nextjs-16.md`가 프론트에 대해 경고하는 것과 같은 종류다: **Spring Boot 4.x도 학습 데이터 시점 지식과 다른 breaking change가 있을 수 있다.** Jackson뿐 아니라 다른 라이브러리에서도 비슷한 groupId/API 이동이 있을 수 있으니, 컴파일 에러가 나면 "버전이 이상하다"고 넘기지 말고 실제 `dependency:tree`로 무엇이 들어와 있는지 먼저 확인한다.

### 1.3 프론트엔드

```
miniproject1-frontend/
├─ app/                  App Router 라우트
├─ components/ui/        shadcn 원본 (npx shadcn@latest add 로만 추가, 직접 수정 최소화)
├─ components/           기능 컴포넌트 (pagination.tsx, empty-state.tsx 등)
├─ hooks/                React Query 훅 (use-reports.ts 등)
├─ lib/                  api.ts(fetch 래퍼), query-client.ts, format.ts, utils.ts
└─ types/                API 타입
```

- import는 `@/` 별칭만 쓴다 (`tsconfig.json`에 `"@/*": ["./*"]` 설정됨). `src/` 폴더를 만들지 않는다.
- `docs/guides/*.md`, `.claude/agents/docs/guides/*.md`는 **다른 프로젝트(todo-project) 템플릿**이다. 경로·도구 설정을 인용하지 않는다.

---

## 2. 기존 문서와 충돌 — 이 문서가 이긴다

| 항목 | 기존 문서 | **현재 규칙** |
|---|---|---|
| 패키지 | `com.pharmaprice` 도메인별 | `com.example` 레이어별 (§1.2) |
| Access Token | 30분 + Refresh 14일 회전 | **24시간, Refresh Token 없음.** `refresh_token` 테이블·`/auth/refresh` 구현하지 않음. 로그아웃 = 프론트 토큰 삭제 |
| 비밀번호 | 8~64자, 영문+숫자 | **6자 이상** (`@Size(min = 6, max = 64)`) |
| 소셜 로그인 | 비목표 | **Google OAuth2 필수** (§5.3) |
| Soft Delete | `status` 컬럼 | **`deleted_at TIMESTAMPTZ NULL`** (§4.3). `price_report.status`(ACTIVE/HIDDEN)는 삭제가 아닌 노출 상태로 유지 |
| DB | database `pharmaprice` | database `postgres` 안의 **schema `pharmaprice`** (현재 `application.properties` 기준) |
| 테스트 DB | Testcontainers | **Docker 미사용 → Testcontainers 금지.** 로컬 PostgreSQL의 `pharmaprice_test` 스키마 |
| 배포 | 비목표 | 로컬 완성 후 AWS (§8) |
| 프론트 상태 | 미정 | React Query + Framer Motion + Tiptap |

- 기존 문서는 **수정하지 않고 그대로 둔다.** 위 항목은 기존 문서 내용을 무시하고 이 표를 따른다.
- 표에 없는 새 충돌을 발견하면 임의로 정하지 말고 사용자에게 확인한다.

---

## 3. 코딩 컨벤션

### 3.1 공통

- **주석은 한글.** 무엇을 하는지가 아니라 왜 그런지만 적는다.
- 커밋 메시지 한글: `기능 추가: 가격 제보 페이지네이션 API`. 브랜치 `feature/기능명`, `fix/버그명`.

### 3.2 Java

| 대상 | 규칙 | 예 |
|---|---|---|
| 엔티티 | 단수 PascalCase, 접미사 없음 | `PriceReport`, `AppUser` (`user`는 PG 예약어) |
| Repository | `{Entity}Repository` | `PriceReportRepository` |
| Service | `{Entity}Service` 구체 클래스 (구현체 1개면 인터페이스 금지) | `PriceReportService` |
| DTO | `{동작}{대상}Request` / `{대상}Response` — Java `record` | `CreateReportRequest`, `ReportResponse` |
| 테이블/컬럼 | `snake_case` | `price_report.deleted_at` |
| enum | `@Enumerated(EnumType.STRING)` 만. **ORDINAL 금지** | `ReportStatus` |

- **엔티티를 컨트롤러 반환 타입으로 쓰지 않는다.** 항상 DTO로 변환 (`ReportResponse.from(entity)` 정적 팩토리).
- 엔티티에 `@Setter`, `@Data` 금지. 상태 변경은 의미 있는 메서드로 (`report.hide()`, `report.softDelete()`).
- 연관관계는 전부 `FetchType.LAZY`. 목록 조회는 fetch join 또는 DTO projection으로 N+1 차단.
- 금액 `int`(원 단위), 시각 `OffsetDateTime`/`TIMESTAMPTZ`, 타임존 `Asia/Seoul` 고정.

### 3.3 TypeScript / React

| 대상 | 규칙 | 예 |
|---|---|---|
| 파일명 | kebab-case | `report-card.tsx`, `use-reports.ts` |
| 컴포넌트 | PascalCase, named export (페이지만 default) | `export function ReportCard` |
| 훅 | `use` 접두사 | `useReports`, `useDeleteReport` |
| Query key | 배열, 첫 요소는 리소스 복수형 | `['reports', { page, size }]` |
| 타입 | `any` 금지, API 응답은 `types/`에 정의 | `ReportResponse` |

- 서버 데이터는 **React Query로만** 다룬다. `useEffect + fetch + useState` 조합 금지.
- 모든 API 호출은 `lib/api.ts`의 `apiFetch`를 거친다 (토큰 헤더·에러 파싱 일원화).
- 브라우저 API·폼·React Query·Framer Motion·Tiptap 사용 컴포넌트는 `"use client"`.

---

## 4. 백엔드 구현 규칙

### 4.1 CRUD 대상 리소스

- **"pharmaprice CRUD" = 로그인 사용자의 가격 제보(`price_report`) CRUD.** 요구사항의 "할 일 CRUD"·"완료 토글"은 각각 제보 CRUD·제보 노출 상태 토글(`ACTIVE ↔ HIDDEN`)로 대응한다. (확정)
- 토글 API: `PATCH /api/v1/price-reports/{id}/status` — 본인 제보만, `ACTIVE ↔ HIDDEN` 전환 후 통계 재계산.
- 약국(`pharmacy`)·의약품(`drug`)은 시드 마스터 데이터 — 일반 사용자 쓰기 API 없음, 조회만.

### 4.2 페이지네이션

- 컨트롤러는 `Pageable`을 받되 `size` 최대 50으로 제한 (`spring.data.web.pageable.max-page-size=50`).
- **Spring `Page` 객체를 그대로 반환하지 않는다.** `dto/PageResponse<T>` 로 변환:
  ```java
  public record PageResponse<T>(List<T> content, int page, int size,
                                long totalElements, int totalPages, boolean hasNext) {}
  ```
- 목록 기본 정렬 `createdAt DESC`, 마지막 타이브레이커로 `id DESC` 추가 (페이지 경계 중복 방지).

### 4.3 Soft Delete

- 대상 테이블: `app_user`, `price_report` (+ 사용자가 삭제할 수 있는 모든 테이블).
- 엔티티에 다음 조합을 쓴다:
  ```java
  @SQLDelete(sql = "UPDATE pharmaprice.price_report SET deleted_at = now() WHERE id = ?")
  @SQLRestriction("deleted_at IS NULL")
  ```
- 삭제는 `repository.delete(entity)` 호출로 통일 (위 어노테이션이 UPDATE로 바꾼다). 네이티브 쿼리를 쓰면 **`deleted_at IS NULL` 조건을 직접 넣는다** — `@SQLRestriction`은 네이티브 쿼리에 적용되지 않는다.
- 소프트 삭제된 제보도 통계 재계산 대상에서 제외한다 (`pharmacy_drug_price_stat` 재계산 트리거).
- 중복 제보 유니크 인덱스 조건에 `AND deleted_at IS NULL` 을 포함한다.

### 4.4 소유권 검증

- 제보 조회(단건)/수정/삭제/토글은 **Service에서** `findByIdAndUserId(id, currentUserId)` 로 조회한다. 컨트롤러에서 검증하지 않는다.
- 타인 리소스 접근은 **`404 REPORT_NOT_FOUND`** 로 응답한다 (403은 리소스 존재를 노출한다).
- `ADMIN`만 소유권 검사를 우회한다.
- `currentUserId`는 `@AuthenticationPrincipal`에서만 얻는다. **요청 바디/쿼리의 `userId`를 신뢰하지 않는다.**

### 4.5 에러 처리

- `exception/GlobalExceptionHandler` (`@RestControllerAdvice`) 하나에서 모든 예외를 응답으로 변환한다. 컨트롤러에 try-catch 금지.
- 응답 포맷 고정 (API.md §1.2): `{ code, message, fieldErrors?, traceId, timestamp }`.
- 비즈니스 예외는 `BusinessException(ErrorCode)` 하나로 던진다. `ErrorCode` enum이 HTTP 상태·코드·한글 메시지를 가진다.
- 반드시 매핑: `MethodArgumentNotValidException`→400 `VALIDATION_FAILED`, `AuthenticationException`→401, `AccessDeniedException`→403, `OptimisticLockingFailureException`→409 `CONFLICT`, 그 외→500 `INTERNAL_ERROR` (스택트레이스는 로그에만).
- 401/403은 필터 단계에서 발생하므로 `AuthenticationEntryPoint`·`AccessDeniedHandler`에서도 **같은 포맷**으로 응답한다.

### 4.6 도메인 로직 (기존 문서 유지)

- Score 가중치·반감기는 `@ConfigurationProperties(prefix = "recommendation")`로 주입. 하드코딩 금지.
- Score 계산·정렬은 Java 서비스 레이어 순수 함수. `P_max == P_min`이면 `priceScore = 1.0`.
- 정렬: `score DESC → repPrice ASC → distanceM ASC → pharmacyId ASC`.
- 대표가격은 중앙값, 제보 4건 미만이면 IQR 생략. 제보 저장 + 통계 재계산은 한 트랜잭션.
- `drug.otc_flag = false` 데이터는 어떤 응답에도 포함 금지.
- Score 수식은 `PRD.md §F3` · `API.md §5` · `DATABASE.md §5` 기준으로 구현하고 임의로 바꾸지 않는다.

---

## 5. 보안 · 인증

### 5.1 비밀번호 · 입력값

- 비밀번호는 `BCryptPasswordEncoder` 로만 해시. 평문·가역 암호화 저장 금지.
- 모든 요청 DTO에 Bean Validation + 컨트롤러 `@Valid`. 회원가입: `@Email @NotBlank email`, `@Size(min = 6, max = 64) password`, `@Size(min = 2, max = 30) nickname`.
- 클라이언트 검증은 UX용. 서버 검증을 생략하지 않는다.
- 로그인 실패 메시지는 이메일/비밀번호 중 무엇이 틀렸는지 구분하지 않는다.

### 5.2 JWT (Spring Security)

- `SecurityFilterChain`: `sessionCreationPolicy(STATELESS)`, `csrf.disable()` (헤더 토큰 방식이므로), `JwtAuthenticationFilter`를 `UsernamePasswordAuthenticationFilter` 앞에 등록.
- 라이브러리는 설치된 `jjwt 0.12.6` 사용. 서명 키는 `JWT_SECRET` 환경변수(32바이트 이상), 만료 `86400000`ms(24h).
- 토큰 클레임: `sub`=userId, `email`, `role`. 비밀번호·개인정보 넣지 않는다.
- 공개 경로: `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`, `/oauth2/**`, `/login/oauth2/**`, `GET /api/v1/drugs/**`, `GET /api/v1/pharmacies/**`, `GET /api/v1/search`, `GET /api/v1/regions`, `/swagger-ui/**`, `/v3/api-docs/**`. 나머지는 인증 필요, `/api/v1/admin/**`는 `ADMIN`.
- CORS는 `FRONTEND_URL` 하나만 허용. `*` 금지.

### 5.3 Google OAuth2

- `spring-boot-starter-security-oauth2-client` (이미 pom에 있음) + `oauth2Login()`.
- 흐름: Google 로그인 성공 → `OAuth2SuccessHandler`가 JWT 발급 → `${FRONTEND_URL}/oauth/callback#token={jwt}` 로 리다이렉트 → 프론트가 fragment에서 토큰을 읽어 저장 후 `history.replaceState`로 URL에서 제거.
  - **쿼리스트링(`?token=`)이 아니라 fragment(`#`)** 를 쓴다 — fragment는 서버 로그·Referer에 남지 않는다.
- `app_user`에 `provider VARCHAR(20) NOT NULL DEFAULT 'LOCAL'` (`LOCAL` | `GOOGLE`), `password_hash`는 NULL 허용으로 바꾼다. GOOGLE 사용자는 비밀번호 로그인 불가.
- 같은 이메일의 LOCAL 계정이 있으면 Google의 `email_verified = true`일 때만 그 계정으로 로그인시킨다.
- OAuth 실패 시 `${FRONTEND_URL}/login?error=oauth` 로 리다이렉트.

### 5.4 프론트 토큰 보관

- 토큰은 `localStorage`(키 `accessToken`)에 보관하고 `apiFetch`가 `Authorization: Bearer` 헤더를 붙인다.
  - ponytail: localStorage는 XSS에 노출된다. AWS 배포 시 FE/BE를 같은 상위 도메인으로 묶으면 httpOnly 쿠키로 전환 검토.
- 그래서 XSS 차단 규칙이 필수다: `dangerouslySetInnerHTML` 금지, **Tiptap 내용은 HTML이 아니라 JSON(`editor.getJSON()`)으로 저장하고 읽기 전용 Tiptap으로 렌더**한다. 백엔드는 JSON 크기 상한(예: 10KB)을 검증한다.
- 401 응답을 받으면 토큰 삭제 → `/login?redirect={현재경로}` 이동.
- 인증 필요 페이지는 `app/(protected)/layout.tsx`에서 토큰 유무를 확인해 리다이렉트한다.

### 5.5 비밀값

- `application.properties`에는 `${DB_PASSWORD}` 같은 참조만 둔다. **현재 파일의 `password=changeme` 하드코딩은 인증 구현 작업 시 환경변수 참조로 바꾼다.**
- `.env*`, `application-local.properties`는 커밋 금지. 키 목록은 `.env.example`에 둔다.

---

## 6. 프론트엔드 구현 규칙

### 6.1 UI 스타일 — 심플 & 모던

- **베이스**: shadcn `neutral`/`zinc` 계열 무채색 + **포인트 컬러 1개(emerald 계열, "절약·건강" 연상)**. 포인트 컬러는 최저가 배지·주요 CTA·절약액에만 쓴다.
- **폰트**: Pretendard (한글 가독성). 숫자(가격)는 `tabular-nums`.
- **표면**: 그림자 대신 `border` + `rounded-2xl` 카드, 넉넉한 여백(`p-5`~`p-6`, `gap-4`). 배경 `bg-muted/40` 위에 흰 카드.
- **레이아웃**: 모바일 우선. 모바일은 하단 고정 CTA·바텀시트, 데스크톱은 `lg:` 2열(지도 | 리스트). 관리자 대시보드는 bento 그리드.
- **다크모드**: shadcn CSS 변수(`globals.css`)로만 색을 정의. 컴포넌트에 `bg-white`·`text-black` 같은 고정색 금지.
- **모션(Framer Motion)**: 리스트 진입 stagger, 카드 hover 살짝 들림, 낙관적 삭제 시 `AnimatePresence` 퇴장. 지속시간 150~250ms. `useReducedMotion()`이면 끈다.
- 아이콘은 `lucide-react`만.
- 모든 레이아웃에 "본 서비스의 가격은 학습용 예시 데이터입니다" 고지 배너 노출 (PRD §9).

### 6.2 상태 3종 — 모든 데이터 화면 필수

- **로딩**: shadcn `Skeleton`으로 실제 레이아웃 모양을 흉내 낸다. 전체 화면 스피너 금지.
- **빈 상태**: `components/empty-state.tsx` (아이콘 + 한 줄 설명 + 다음 행동 버튼).
- **에러**: `components/error-state.tsx` (에러 `message` 표시 + 재시도 버튼 → `refetch`). `fieldErrors`는 해당 폼 필드 아래에 표시.
- 뮤테이션 성공/실패 알림은 shadcn `sonner` 토스트.

### 6.3 페이지네이션 컴포넌트

- `components/pagination.tsx` 하나를 모든 목록에서 재사용한다. shadcn `pagination` 프리미티브 기반.
- props는 백엔드 `PageResponse`와 대응: `page`(0-base), `totalPages`, `onPageChange`.
- 화면 표시는 1-base, API 전송은 0-base. **변환은 이 컴포넌트 안에서만** 한다.
- 현재 페이지는 URL `?page=` 쿼리로 관리 (새로고침·뒤로가기 유지). React Query는 `placeholderData: keepPreviousData`로 페이지 전환 시 깜빡임 방지.
- 페이지 번호가 많으면 `1 … 4 5 6 … 20` 형태로 줄인다.

### 6.4 낙관적 업데이트 (React Query)

- 대상: 제보 **상태 토글**, **삭제**. 생성은 낙관적 업데이트하지 않는다 (서버가 `updatedStat` 등 계산값을 반환하므로).
- 패턴 고정: `onMutate`에서 `cancelQueries` → 이전 캐시 스냅샷 → `setQueryData`로 즉시 반영 → `onError`에서 스냅샷 복원 + 에러 토스트 → `onSettled`에서 `invalidateQueries`.
- 삭제로 현재 페이지가 비면 이전 페이지로 이동한다.

---

## 7. 명령어 · 환경변수

### 7.1 명령어

| 위치 | 명령 | 용도 |
|---|---|---|
| backend | `./mvnw spring-boot:run` (Windows: `mvnw.cmd spring-boot:run`) | 개발 서버 :8080 |
| backend | `./mvnw test` | 단위 + 통합 테스트 |
| backend | `./mvnw clean package -DskipTests` | 배포용 jar |
| frontend | `npm run dev` | 개발 서버 :3000 |
| frontend | `npm run build` | 프로덕션 빌드 (검증 체크리스트 3) |
| frontend | `npm run lint` / `lint:fix` / `typecheck` / `format` | 품질 검사 |

- 프론트 파일을 수정한 뒤에는 `npm run lint:fix && npm run format`을 직접 실행한다. **`.claude/hooks/format-on-edit.mjs`는 `todo-frontend` 경로를 가리키고 settings에 등록도 안 돼 있어 동작하지 않는다.**
- 커밋 시 husky pre-commit(lint-staged), push 시 pre-push(typecheck)가 frontend 저장소에서 실행된다.

### 7.2 환경변수

| 저장소 | 키 | 예 / 설명 |
|---|---|---|
| backend | `DB_URL` | `jdbc:postgresql://localhost:5432/postgres?currentSchema=pharmaprice` |
| backend | `DB_USERNAME` / `DB_PASSWORD` | `pharmaprice` / (비밀) |
| backend | `JWT_SECRET` | 32바이트 이상 랜덤 |
| backend | `JWT_EXPIRATION_MS` | `86400000` |
| backend | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Cloud Console |
| backend | `FRONTEND_URL` | `http://localhost:3000` (CORS·OAuth 리다이렉트) |
| backend | `UPLOAD_DIR` | `./uploads` (배포 시 S3로 교체) |
| frontend | `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8080` |
| frontend | `NEXT_PUBLIC_KAKAO_MAP_KEY` | 카카오 JavaScript 키 |

- 새 환경변수를 추가하면 `.env.example`(frontend) / `application.properties`의 `${KEY:기본값}` 참조(backend)와 이 표를 함께 갱신한다.
- Google OAuth 리디렉션 URI: `http://localhost:8080/login/oauth2/code/google`.

---

## 8. 배포 (나중 단계)

- **지금은 로컬 개발만 한다.** 사용자가 요청하기 전까지 AWS 설정 파일·IaC를 만들지 않는다.
- **Docker 사용 금지** (Dockerfile, docker-compose, Testcontainers 모두).
- 목표 구성: Frontend → AWS Amplify (Next.js SSR) / Backend → EC2 (jar + systemd) / DB → RDS PostgreSQL (`pharmaprice` 스키마) / 영수증 이미지 → S3.
- 배포를 막지 않도록 지금 지킬 것: 모든 URL·키는 환경변수로, 파일 저장 경로는 `UPLOAD_DIR`로만 접근, `ddl-auto=update`는 RDS 반영 전에 `validate` + 마이그레이션 스크립트로 전환(사용자 확인 후).

---

## 9. 테스트 · 검증

### 9.1 통합 테스트

- `@SpringBootTest` + `MockMvc`, 프로필 `test` (`application-test.properties` → 로컬 PostgreSQL `pharmaprice_test` 스키마). 각 테스트 `@Transactional` 롤백.
- 필수 시나리오 (검증 체크리스트와 1:1):
  1. 회원가입 → 201 + 사용자 생성 (비밀번호 해시 저장 확인)
  2. 로그인 → 200 + 유효한 JWT
  3. 토큰 없이 보호 엔드포인트 → 401, 잘못된 토큰 → 401
  4. 제보 CRUD + 페이지네이션 (`page`, `size`, `totalElements` 검증)
  5. 삭제 후 DB의 `deleted_at` 이 NOT NULL, 목록·단건 조회에서 제외
  6. 사용자 A의 제보를 사용자 B가 조회/수정/삭제 → 404
- Score 로직은 DB 없는 단위 테스트 (ROADMAP T-12 표 유지).

### 9.2 작업 완료 전 확인

- 백엔드 수정 시: `./mvnw test` 통과 + `./mvnw spring-boot:run` 기동 오류 없음.
- 프론트 수정 시: `npm run typecheck && npm run lint && npm run build` 통과.
- UI 수정 시: 375px / 768px / 1280px 폭에서 레이아웃 확인.
- **검증하지 않은 것을 완료라고 보고하지 않는다.** 실행 못 한 검증은 명시한다.

---

## 10. AI 의사결정 기준

- 요구사항 충돌 → §2 표 → 없으면 사용자 확인.
- ROADMAP 태스크 수행 시 → 구현 순서·완료 판정은 ROADMAP을 따르되, 패키지 경로·인증 방식·Soft Delete는 이 문서로 치환.
- 새 라이브러리가 필요해 보이면 → 이미 설치된 것(§ 기술 스택)으로 가능한지 먼저 확인. 추가가 필요하면 이유를 밝히고 추가.
- API 필드 추가/변경 → 백엔드 DTO → 프론트 `types/` 순서. 기존 문서(`API.md` 등)는 수정하지 않는다.
- 스키마 변경 → 엔티티 → DTO 순서. `DATABASE.md`는 수정하지 않는다.
- 커밋 → 대상 저장소 확인 → 저장소별로 따로 커밋.

---

## 11. 금지 사항

- 엔티티를 API 응답으로 직접 반환
- Spring `Page` 객체 직접 반환
- 요청 파라미터의 `userId`로 소유권 판단
- 소유권 없는 리소스에 403 응답 (404 사용)
- 물리 삭제(`DELETE FROM`) — 사용자 데이터는 전부 soft delete
- 네이티브 쿼리에서 `deleted_at IS NULL` 누락
- 컨트롤러 try-catch, 제각각의 에러 응답 포맷
- `EnumType.ORDINAL`, 엔티티 `@Setter`/`@Data`
- 비밀번호 평문 저장, 비밀값 하드코딩·커밋, CORS `*`
- JWT를 URL 쿼리스트링으로 전달
- `dangerouslySetInnerHTML`, Tiptap HTML 원문 저장/렌더
- `useEffect` 기반 데이터 페칭, `any` 타입
- 전체 화면 스피너, 고정 색상 클래스(`bg-white` 등)
- Refresh Token 구현, Docker, Testcontainers, PostGIS, OCR, rate limiting
- `com.example` 외 패키지 루트, 도메인별 패키지 구조
- 전문의약품(`otc_flag = false`) 노출
- 루트 `.gitignore`에서 하위 저장소 제외 항목 삭제, 저장소 간 커밋 혼합
