# ROADMAP — 태스크 분해 (Shrimp Task Manager 용)

| 항목 | 내용 |
|---|---|
| 문서 버전 | v3.0 (1인 구현 · 기능 슬라이스 재편 · Docker 제거) |
| 태스크 관리 | [mcp-shrimp-task-manager](https://github.com/cjo4m06/mcp-shrimp-task-manager) |
| 총 태스크 | 37 (P0 27 / P1 6 / P2 4) |
| 진행 방식 | **팀 프로젝트지만 구현은 1인 단위.** 각자 자기 Claude Code로 전체를 처음부터 끝까지 만든다 |
| 실행 환경 | 로컬 PostgreSQL 17 + `./mvnw spring-boot:run` + `npm run dev` (**Docker 미사용**) |
| 관련 문서 | [PRD.md](./PRD.md) · [DATABASE.md](./DATABASE.md) · [API.md](./API.md) |

---

## 0. 이 문서 사용법

### 0.1 Shrimp 스키마 대응

각 태스크 카드는 `split_tasks` 스키마와 1:1로 대응한다.

| 카드 항목 | Shrimp 필드 | 비고 |
|---|---|---|
| 제목 `T-xx. 이름` | `name` | 100자 이내 |
| **목적** | `description` | 10자 이상 |
| **구현 가이드** | `implementationGuide` | |
| **선행 태스크** | `dependencies` | 태스크 **이름** 문자열 배열 |
| **관련 파일** | `relatedFiles` | `type`: `CREATE` \| `TO_MODIFY` \| `REFERENCE` |
| **완료 판정** | `verificationCriteria` | |
| **메모** | `notes` | |

### 0.2 투입 순서

1. `plan_task` 에 [PRD.md](./PRD.md) + 이 문서를 컨텍스트로 넣는다
2. `split_tasks` 를 `updateMode: "clearAllTasks"` 로 첫 투입, 이후 보정은 `"selective"` 로
3. **한 번에 37개를 다 넣지 말고 슬라이스(FS) 단위로 나눠 투입**한다. 한 번에 넣으면 `implementationGuide` 가 뭉개진다
4. `execute_task` → `verify_task` 루프, 점수 80점 미만이면 재작업

> `dependencies` 는 같은 배치 안의 태스크는 **이름**으로, 이전 배치의 태스크는 **task ID(UUID)** 로 참조해야 한다. 슬라이스를 나눠 투입할 때는 `list_tasks` 로 앞 배치의 ID를 먼저 확보할 것.

### 0.3 왜 레이어가 아니라 기능 슬라이스인가

"백엔드 전부 → 프론트 전부" 순서로 가면 나흘째까지 화면에 아무것도 안 나온다. 혼자 만들 때 이건 동기부여 문제이자 **통합 리스크**다. API를 다 만들어놓고 나서야 응답 형태가 화면에 안 맞는다는 걸 알게 된다.

그래서 **FS-2를 끝내면 "검색해서 최저가를 본다"가 끝에서 끝까지 동작**하도록 잘랐다. 각 슬라이스가 끝날 때마다 눈으로 확인할 수 있는 결과가 나온다.

인증을 FS-4까지 미룬 것도 같은 이유다. 검색은 비로그인으로 동작하므로, 인증을 앞에 두면 보이는 것 없이 하루를 태우게 된다.

---

## 1. 슬라이스 구성

| 슬라이스 | 끝나면 되는 것 | 태스크 | 예상 |
|---|---|---|---|
| **FS-0** 셋업 | 빈 프로젝트가 로컬에서 뜬다 | T-01 ~ T-04 | 2d |
| **FS-1** 데이터 | DB에 약국·약품·가격 3,000건이 들어있다 | T-05 ~ T-08 | 3d |
| **FS-2** 최저가 검색 | **검색창에 약 이름 → 최저가 약국 목록** | T-09 ~ T-18 | 5.75d |
| **FS-3** 약국 상세 | 약국을 눌러 가격표·이력·지도를 본다 | T-19 ~ T-22 | 2.5d |
| **FS-4** 인증 + 제보 | 로그인하고 가격을 제보하면 순위가 바뀐다 | T-23 ~ T-30 | 4.5d |
| **FS-5** 관리자 (P2) | 지역별 통계와 이상치 제보 관리 | T-31 ~ T-34 | 2.5d |
| **FS-6** 마감 | 예외 처리, 반응형, README | T-35 ~ T-37 | 1.5d |

### 의존성 그래프

```
FS-0   T-01 ─┬─> T-02 ──> T-03 ──> T-05 ──> T-06 ──> T-07 ──> T-08
             └─> T-04                          │                │
                   │                            │                │
FS-2               │                     T-06 ──┘         T-08 ──┼──> T-09 ──┐
                   │                                              ├──> T-10 ──┼──> T-11 ──> T-12
                   │                                              ├──> T-13   │
                   │                                              └──> T-14 ──┴──> T-15
                   │                                                             │
                   └──> T-16 ──> T-17 ──────────────────────────────────────────> T-18

FS-3   T-09 ──> T-19 ──> T-20 ──> T-21        T-18 ──> T-22
                                    ↑            │
                                    └────────────┘

FS-4   T-06 ──> T-23 ──> T-24 ─┬─> T-25 ──────────────┐
                                └─> T-26 ─┬─> T-27     ├─> T-29 ──> T-30
                                          └─> T-28     │
                                     T-21 ─────────────┘

FS-5   T-24, T-10 ──> T-31 ──> T-32 ──> T-33 ──> T-34

FS-6   T-15, T-26 ──> T-35 ─┐
       T-21, T-30 ──> T-36 ─┴─> T-37  (+ T-02)
```

**임계 경로**: `T-03 → T-05 → T-06 → T-07 → T-08 → T-10 → T-11 → T-15 → T-18`

**T-07(공공데이터 변환)이 가장 위험한 구간이다.** 여기가 막히면 뒤가 전부 막힌다.

### 일정 현실성

P0 27개의 예상 합계는 약 **13일**이다. 1인이 1~2주에 전부 끝내기는 빠듯하므로, 잘라낼 순서를 미리 정해둔다.

1. **FS-5 관리자 전체** (P2 · 2.5d) — 가장 먼저 버린다
2. **T-22 카카오맵** (P1 · 1d) — 리스트만으로도 데모가 된다
3. **T-27 영수증 업로드** (P1 · 0.5d)
4. **T-30 내 제보 목록** (P1 · 0.25d)
5. **T-20 + T-21의 가격 이력 차트** (P1 · 0.5d)

**FS-2까지만 끝나도 발표는 된다.** "검색 → 최저가 추천"이 이 서비스의 전부이기 때문이다.

---

# FS-0. 셋업

## T-01. 프로젝트 구조 및 개발 컨벤션 셋업

**우선순위** P0 · **예상** 0.5d

**목적**
디렉터리 구조와 코드 컨벤션을 확정해 이후 모든 태스크가 같은 규칙 위에서 돌아가게 한다.

**구현 가이드**

1. 루트 구조를 다음과 같이 만든다.
   ```
   miniProject1/
   ├─ PRD.md
   ├─ DATABASE.md
   ├─ API.md
   ├─ ROADMAP.md
   ├─ README.md
   ├─ .env.example
   ├─ .editorconfig
   ├─ .gitignore
   ├─ miniProject1_frontEnd/     Next.js 16 + React 19.3
   ├─ miniProject1_backEnd/      Spring Boot 4.1 + Java 21 + Maven
   │   ├─ pom.xml
   │   ├─ mvnw, mvnw.cmd, .mvn/  Maven Wrapper (커밋함)
   │   └─ src/main/{java,resources}
   └─ tools/seed-generator/      공공데이터 → 시드 SQL 변환 (Python)
       └─ data/                  원본 CSV
   ```
   **문서 4종은 루트에 평평하게 둔다** (`docs/` 하위 아님). 태스크 카드의 `relatedFiles` 경로도 이 기준이다.

2. 백엔드 패키지 구조를 도메인 기준으로 고정한다.
   ```
   com.pharmaprice
     ├─ common          예외, 응답 포맷, 설정
     ├─ auth            인증
     ├─ pharmacy        약국, 지역
     ├─ drug            의약품
     ├─ report          가격 제보, 파일 업로드
     ├─ recommendation  거리, 통계, Score, 검색
     └─ admin           관리자
   ```
   각 도메인 안은 `controller` / `service` / `repository` / `domain` / `dto`.

3. 프론트 구조를 고정한다.
   ```
   miniProject1_frontEnd/
     ├─ app/            라우트 (App Router)
     ├─ components/     UI 컴포넌트
     ├─ hooks/          커스텀 훅
     ├─ lib/            api 클라이언트, 유틸
     └─ types/          openapi-typescript 생성 타입
   ```

4. 커밋 컨벤션: `feat(T-09): 거리 계산 컴포넌트 추가`. 태스크 번호를 넣어 추적 가능하게 한다.

5. `.editorconfig`: Java 4칸, TS/JS 2칸, LF, UTF-8, 파일 끝 개행.

6. `.gitignore`: `.env*`, `miniProject1_backEnd/target/`, `miniProject1_frontEnd/.next/`, `miniProject1_frontEnd/node_modules/`, `uploads/`, `tools/seed-generator/__pycache__/`.
   ⚠️ **Maven Wrapper(`mvnw`, `.mvn/wrapper/`)는 커밋한다.** `.mvn/` 을 통째로 무시하는 템플릿이 흔한데, 그러면 빌드가 안 된다.

7. `.env.example` 에 필요한 키를 전부 나열한다.
   ```
   # PostgreSQL (로컬 설치, T-02 참고)
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=pharmaprice
   POSTGRES_USER=pharmaprice
   POSTGRES_PASSWORD=changeme
   # 백엔드
   JWT_SECRET=                    # 최소 32바이트 랜덤 문자열
   TZ=Asia/Seoul
   # 프론트
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
   NEXT_PUBLIC_KAKAO_MAP_KEY=     # 카카오 개발자 콘솔 JavaScript 키
   ```

**선행 태스크** 없음

**관련 파일**
- `README.md` — `CREATE` — 프로젝트 개요 (T-37에서 완성)
- `.editorconfig` — `CREATE` — 에디터 공통 설정
- `.gitignore` — `CREATE` — 무시 목록
- `.env.example` — `CREATE` — 환경변수 목록
- `PRD.md` — `REFERENCE` — 요구사항 원본

**완료 판정**
- 위 디렉터리가 모두 존재한다
- `.env` 가 git에 추적되지 않고 `.mvn/` 은 추적된다
- `.env.example` 만 보고 필요한 키를 전부 파악할 수 있다

**메모**
실제 API 키 값은 절대 커밋하지 않는다. 카카오맵 키는 T-22에서 필요하니 그 전까지는 비워둬도 된다.

---

## T-02. 로컬 PostgreSQL 17 설치 및 데이터베이스 준비

**우선순위** P0 · **예상** 0.5d

**목적**
로컬에 PostgreSQL 17을 띄우고, 애플리케이션이 붙을 데이터베이스·계정·타임존을 준비한다. Docker를 쓰지 않으므로 이 태스크가 DB 환경의 전부다.

**구현 가이드**

1. PostgreSQL 17을 설치한다.
   - **macOS**: `brew install postgresql@17` → `brew services start postgresql@17`
     PATH 추가 필요: `echo 'export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"' >> ~/.zshrc`
   - **Windows**: [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) 설치 프로그램. 설치 중 Locale은 `C` 또는 `en_US.UTF-8` 로 둔다.
   - **Linux**: 배포판 패키지 또는 PGDG 저장소.

2. 데이터베이스와 계정을 만든다. `.env.example` 의 값과 일치시킨다.
   ```sql
   CREATE USER pharmaprice WITH PASSWORD 'changeme';
   CREATE DATABASE pharmaprice OWNER pharmaprice ENCODING 'UTF8';
   \c pharmaprice
   GRANT ALL ON SCHEMA public TO pharmaprice;
   ```

3. **타임존을 `Asia/Seoul` 로 설정한다.**
   ```sql
   ALTER DATABASE pharmaprice SET timezone TO 'Asia/Seoul';
   ```
   확인: 재접속 후 `SHOW timezone;` 이 `Asia/Seoul`, `SELECT now();` 가 `+09` 오프셋.
   UTC로 두면 한국 시간 오전 9시 이전에 `CURRENT_DATE` 가 전날로 잡혀 중복 제보 방지와 180일 검증이 하루씩 어긋난다 ([DATABASE.md](./DATABASE.md) §8).

4. 확장 설치 권한을 확인한다. `pg_trgm` 은 `V1__init.sql` 이 `CREATE EXTENSION` 으로 설치하는데, **일반 유저는 권한이 없어 실패할 수 있다.** 미리 슈퍼유저로 한 번 실행해 두는 편이 안전하다.
   ```sql
   \c pharmaprice postgres
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```

5. 접속을 확인한다.
   ```bash
   psql -h localhost -p 5432 -U pharmaprice -d pharmaprice -c "SELECT version();"
   ```

6. 설치·설정 절차를 `README.md` 의 "로컬 환경 준비" 절에 그대로 적는다. **나중에 다시 세팅할 때 이 문서만 보고 되어야 한다.**

**선행 태스크** T-01

**관련 파일**
- `README.md` — `TO_MODIFY` — 로컬 환경 준비 절 추가
- `.env.example` — `REFERENCE` — DB 접속 정보

**완료 판정**
- `psql` 로 `pharmaprice` DB에 `pharmaprice` 계정으로 접속된다
- `SHOW timezone;` 이 `Asia/Seoul` 을 반환한다
- `SELECT * FROM pg_extension WHERE extname = 'pg_trgm';` 이 1행을 반환한다
- README의 절차만 따라 해도 같은 상태가 재현된다

**메모**
포트 5432가 이미 쓰이고 있으면(다른 PostgreSQL 설치본 등) 충돌한다. `lsof -i :5432` 로 확인하고, 필요하면 5433을 쓰되 `.env` 에도 반영한다.

---

## T-03. Spring Boot + Maven 프로젝트 초기화

**우선순위** P0 · **예상** 0.5d

**목적**
백엔드 골격을 세우고 Flyway로 스키마 관리를 고정한다.

**구현 가이드**

1. [start.spring.io](https://start.spring.io) 에서 생성하거나 직접 `pom.xml` 을 작성한다.
   - **Maven**, Spring Boot 4.1.x, **Java 21**, 패키징 jar
   - `pom.xml` 의 `<properties>` 에 `<java.version>21</java.version>` 명시
   - **Maven 3.6.3 이상** 필요. `mvnw`(Maven Wrapper)를 함께 커밋한다

2. 의존성: `spring-boot-starter-web`, `spring-boot-starter-data-jpa`, `spring-boot-starter-validation`, `spring-boot-starter-security`, `spring-boot-starter-actuator`, `postgresql`(runtime), `flyway-core`, `flyway-database-postgresql`, `springdoc-openapi-starter-webmvc-ui`, `lombok`(optional), `spring-boot-starter-test`, `spring-boot-testcontainers` + `testcontainers:postgresql`(test).

   > `flyway-database-postgresql` 을 빼먹으면 Flyway가 PostgreSQL을 인식하지 못한다. Flyway 10부터 DB별 모듈이 분리됐다.

3. `application.yml` 을 작성한다.
   ```yaml
   spring:
     datasource:
       url: jdbc:postgresql://${POSTGRES_HOST:localhost}:${POSTGRES_PORT:5432}/${POSTGRES_DB:pharmaprice}
       username: ${POSTGRES_USER:pharmaprice}
       password: ${POSTGRES_PASSWORD:changeme}
     jpa:
       hibernate:
         ddl-auto: validate       # update/create 절대 금지
       open-in-view: false
       properties:
         hibernate:
           jdbc:
             time_zone: Asia/Seoul
     flyway:
       enabled: true
       locations: classpath:db/migration
     servlet:
       multipart:
         max-file-size: 5MB
         max-request-size: 6MB

   springdoc:
     swagger-ui:
       path: /swagger-ui.html

   app:
     upload-dir: ${UPLOAD_DIR:./uploads}

   recommendation:
     weights:
       price: 0.60
       distance: 0.25
       freshness: 0.15
     freshness-half-life-days: 30
     price-window-days: 90
     price-window-fallback-days: 180
     outlier:
       iqr-multiplier: 1.5
       min-samples: 4
   ```
   `ddl-auto: validate` 로 두어 Flyway 스키마와 엔티티 불일치를 기동 시점에 잡는다.

4. `recommendation.*` 를 `@ConfigurationProperties` 로 바인딩한다.
   ```java
   @ConfigurationProperties(prefix = "recommendation")
   public record RecommendationProperties(
       Weights weights,
       int freshnessHalfLifeDays,
       int priceWindowDays,
       int priceWindowFallbackDays,
       Outlier outlier
   ) {
       public record Weights(double price, double distance, double freshness) {}
       public record Outlier(double iqrMultiplier, int minSamples) {}
   }
   ```
   `@EnableConfigurationProperties(RecommendationProperties.class)` 를 메인 클래스에 붙인다.

5. JVM 타임존을 고정한다. 실행 시 `-Duser.timezone=Asia/Seoul`, 또는 메인 클래스에서:
   ```java
   @PostConstruct
   void initTimezone() { TimeZone.setDefault(TimeZone.getTimeZone("Asia/Seoul")); }
   ```

6. 실행 확인: `./mvnw spring-boot:run`

**선행 태스크** T-02

**관련 파일**
- `miniProject1_backEnd/pom.xml` — `CREATE` — 의존성 정의
- `miniProject1_backEnd/src/main/resources/application.yml` — `CREATE` — 설정
- `miniProject1_backEnd/src/main/java/com/pharmaprice/common/config/RecommendationProperties.java` — `CREATE` — Score 가중치 바인딩
- `API.md` — `REFERENCE` — 설정 키 목록

**완료 판정**
- `./mvnw spring-boot:run` 으로 기동되고 `/actuator/health` 가 `{"status":"UP"}` 반환
- `/swagger-ui.html` 이 열린다
- `RecommendationProperties` 가 yml 값을 실제로 읽는 테스트 통과

**메모**
`ddl-auto` 를 `update` 로 두면 엔티티와 Flyway 스키마가 조용히 어긋난다. 반드시 `validate`. 아직 테이블이 없으므로 이 태스크에서는 `validate` 가 통과하지 않을 수 있다 — T-05 이후 재확인한다.

---

## T-04. Next.js 프로젝트 초기화 및 공통 기반

**우선순위** P0 · **예상** 0.5d

**목적**
프론트 골격, 레이아웃, API 클라이언트, 공통 컴포넌트를 만들어 이후 화면 태스크가 바로 착수 가능하게 한다.

**구현 가이드**

1. `npx create-next-app@latest miniProject1_frontEnd` — App Router, TypeScript strict, Tailwind CSS, ESLint. **React 19.3** (Next.js 16 기본). Tailwind 위에 shadcn/ui 설치.

2. 루트 레이아웃: 헤더(로고 · 위치 표시 · 로그인) / 메인 / 푸터.
   **헤더 하단과 푸터에 고정 고지 배너**를 넣는다 — "본 서비스의 가격은 학습용 예시 데이터입니다" (PRD §9). 모든 페이지에 노출되어야 한다.

3. `lib/api.ts` 에 fetch 래퍼를 만든다.
   ```typescript
   export class ApiError extends Error {
     constructor(
       public status: number,
       public code: string,
       message: string,
       public fieldErrors?: { field: string; reason: string }[],
       public traceId?: string,
     ) { super(message) }
   }

   export async function apiFetch<T>(
     path: string,
     init?: RequestInit & { auth?: boolean },
   ): Promise<T>
   ```
   - 베이스 URL은 `process.env.NEXT_PUBLIC_API_BASE_URL`
   - 4xx/5xx면 [API.md](./API.md) §1.2 에러 바디를 파싱해 `ApiError` 로 던진다. **파싱에 실패해도 `ApiError` 를 던진다** (HTML 에러 페이지가 올 수 있다)
   - `204 No Content` 는 `undefined` 를 반환한다. **`res.json()` 을 무조건 호출하면 터진다**
   - `auth: true` 면 `Authorization` 헤더를 붙인다 (토큰 연결은 T-25)

4. 타입 생성: `openapi-typescript` 를 devDependency로 넣고 `npm run gen:api` 스크립트로 `/v3/api-docs` 에서 `types/api.ts` 를 뽑는다. **수기 타입 정의 금지.**

5. 공통 컴포넌트와 포맷 유틸을 만든다.
   - `PriceTag` — 천단위 콤마 (`2,800원`)
   - `DistanceBadge` — 1000m 미만은 `340m`, 이상은 `1.2km`
   - `EmptyState`, `ErrorState`(재시도 버튼 포함), `LoadingSkeleton`
   - `lib/format.ts` — `formatPrice`, `formatDistance`, `formatRelativeDate`("3일 전")

6. 서버/클라이언트 컴포넌트 경계 규칙을 `miniProject1_frontEnd/README.md` 에 적는다.
   - 데이터 조회 → 서버 컴포넌트
   - 지도 · 폼 · 훅 · 브라우저 API → `"use client"`

**선행 태스크** T-01

**관련 파일**
- `miniProject1_frontEnd/app/layout.tsx` — `CREATE` — 루트 레이아웃 + 고지 배너
- `miniProject1_frontEnd/lib/api.ts` — `CREATE` — API 클라이언트
- `miniProject1_frontEnd/lib/format.ts` — `CREATE` — 포맷 유틸
- `miniProject1_frontEnd/package.json` — `CREATE` — `gen:api` 스크립트 포함
- `API.md` — `REFERENCE` — 에러 포맷

**완료 판정**
- `npm run dev` 로 레이아웃이 렌더링되고 고지 배너가 모든 페이지에 보인다
- `apiFetch` 단위 테스트 4종 통과 — 정상 / JSON 에러 / 비-JSON 에러 / 204
- 375px 폭에서 레이아웃이 깨지지 않는다

**메모**
백엔드가 준비되기 전까지는 MSW로 목 응답을 세우면 병렬 진행이 가능하다. 다만 1인 작업이면 순서대로 가는 편이 단순하다.

---

# FS-1. 데이터

## T-05. DB 스키마 마이그레이션 작성 (V1__init.sql)

**우선순위** P0 · **예상** 0.5d

**목적**
[DATABASE.md](./DATABASE.md) §3의 테이블 8개와 인덱스를 Flyway 마이그레이션으로 구현한다.

**구현 가이드**

1. `V1__init.sql` 을 작성한다. 순서: 확장 → 테이블 → 인덱스 → 제약.

2. 맨 위에 `CREATE EXTENSION IF NOT EXISTS pg_trgm;` (약국명·약품명 부분검색용). T-02에서 미리 설치해뒀다면 no-op으로 지나간다.

3. 테이블 8개를 FK 순서대로 생성한다.
   `region` → `app_user` → `refresh_token` → `pharmacy` → `drug` → `uploaded_file` → `price_report` → `pharmacy_drug_price_stat`
   **`uploaded_file` 은 반드시 `price_report` 보다 먼저** (FK 참조 대상).

4. [DATABASE.md](./DATABASE.md)의 인덱스를 전부 생성한다. 성능 핵심 셋:
   - `idx_pharmacy_lat_lng` — 바운딩 박스 선필터
   - `idx_report_pair_active` — 부분 인덱스, 통계 재계산 경로
   - `idx_stat_drug_price` — 검색 경로

5. 중복 제보 방지용 부분 유니크 인덱스를 만든다.
   ```sql
   CREATE UNIQUE INDEX uq_report_user_pair_day
     ON price_report (
       user_id, pharmacy_id, drug_id,
       ((created_at AT TIME ZONE 'Asia/Seoul')::date)
     )
     WHERE user_id IS NOT NULL AND status = 'ACTIVE';
   ```
   ⚠️ 표현식을 `(created_at::date)` 로 쓰면 **인덱스 생성이 실패한다.** `timestamptz → date` 캐스트는 세션 `TimeZone` 에 의존해 `STABLE` 이고, PostgreSQL 인덱스 표현식은 `IMMUTABLE` 만 받는다.

6. `CHECK (price BETWEEN 100 AND 200000)` 등 제약을 DB 레벨에도 건다. 애플리케이션 검증만 믿지 않는다.

**선행 태스크** T-03

**관련 파일**
- `miniProject1_backEnd/src/main/resources/db/migration/V1__init.sql` — `CREATE` — 초기 스키마
- `DATABASE.md` — `REFERENCE` — §3 테이블 정의

**완료 판정**
- 빈 DB에 Flyway 마이그레이션이 에러 없이 적용된다 (특히 `uq_report_user_pair_day` 생성 성공)
- `\d+` 로 8개 테이블과 모든 인덱스가 확인된다
- `price` 에 `50` 을 INSERT하면 CHECK 제약으로 거부된다
- `flyway_schema_history` 에 V1이 `success = true` 로 기록된다

**메모**
`user` 는 PostgreSQL 예약어라 `app_user` 를 쓴다. 엔티티 클래스명도 `AppUser` 로 맞춘다.

---

## T-06. JPA 엔티티 및 리포지토리 매핑

**우선순위** P0 · **예상** 1d

**목적**
스키마에 대응하는 엔티티와 리포지토리를 만들고 `ddl-auto: validate` 를 통과시켜 스키마-엔티티 정합성을 보장한다.

**구현 가이드**

1. 엔티티 8개를 작성한다. 모든 연관관계는 `FetchType.LAZY`.

2. enum은 전부 `@Enumerated(EnumType.STRING)`. **ORDINAL 금지** — 순서가 바뀌면 기존 데이터가 깨진다.
   - `UserRole` (USER, ADMIN)
   - `UserStatus` (ACTIVE, SUSPENDED)
   - `ReportSource` (FORM, SEED, RECEIPT_OCR, PARTNER)
   - `ReportStatus` (ACTIVE, HIDDEN, REJECTED)
   - `FlagReason` (OUTLIER_HIGH, OUTLIER_LOW, DUPLICATE, MANUAL)

3. `pharmacy.business_hours` 는 Hibernate 6 기본 지원으로 매핑한다. 별도 컨버터 불필요.
   ```java
   @JdbcTypeCode(SqlTypes.JSON)
   @Column(columnDefinition = "jsonb")
   private Map<String, List<String>> businessHours;
   ```

4. `@EnableJpaAuditing` + `@CreatedDate` / `@LastModifiedDate` 로 감사 컬럼을 자동화한다. 공통 `BaseTimeEntity` 를 `@MappedSuperclass` 로 두면 반복이 줄어든다.

5. 리포지토리는 Spring Data JPA 인터페이스로 만들되, **검색 쿼리는 이후 태스크에서 native query + DTO projection** 으로 별도 작성한다. JPQL로는 Haversine을 표현할 수 없다.

6. 테스트 베이스 클래스를 만든다.
   ```java
   @SpringBootTest
   @Testcontainers
   public abstract class AbstractIntegrationTest {
       @Container
       @ServiceConnection
       static PostgreSQLContainer<?> postgres =
           new PostgreSQLContainer<>("postgres:17-alpine")
               .withEnv("TZ", "Asia/Seoul");
   }
   ```
   > 테스트에만 Testcontainers를 쓴다 — 개발·실행은 로컬 PostgreSQL이다. **Docker가 없으면** 이 방식 대신 로컬에 테스트용 DB(`pharmaprice_test`)를 따로 만들고 `application-test.yml` 로 붙인다. 그 경우 테스트마다 `@Transactional` 롤백으로 격리한다.

**선행 태스크** T-05

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/*/domain/` — `CREATE` — 엔티티
- `miniProject1_backEnd/src/main/java/com/pharmaprice/*/repository/` — `CREATE` — 리포지토리
- `miniProject1_backEnd/src/test/java/com/pharmaprice/AbstractIntegrationTest.java` — `CREATE` — 테스트 베이스
- `DATABASE.md` — `REFERENCE` — §3 컬럼 타입, §7 JPA 주의점

**완료 판정**
- `ddl-auto: validate` 로 기동 성공 (엔티티-스키마 불일치 0)
- 각 엔티티 저장·조회 테스트 통과
- `business_hours` JSONB 가 `Map` 으로 왕복 변환된다
- enum이 DB에 문자열로 저장된다 (`SELECT status FROM price_report` 가 `ACTIVE`)

---

## T-07. 공공데이터 → 마스터 시드 변환 스크립트

**우선순위** P0 · **예상** 1d ⚠️ **임계 경로 최대 리스크**

**목적**
공공데이터를 내려받아 `region` / `pharmacy` / `drug` 시드 SQL로 변환한다. 런타임 API 호출은 하지 않는다.

**구현 가이드**

1. 데이터를 확보한다.
   - 약국: [국립중앙의료원_전국 약국 정보 조회 서비스](https://www.data.go.kr/data/15000576/openapi.do) 또는 [심평원_전국 병의원 및 약국 현황](https://www.data.go.kr/data/15051059/fileData.do) (파일 데이터가 다루기 쉽다)
   - 의약품: [식약처_의약품개요정보(e약은요)](https://www.data.go.kr/data/15075057/openapi.do)
   - 행정구역 코드: 행정안전부 표준 코드

2. `tools/seed-generator/build_master_seed.py` 를 작성한다. **일회성 수작업이 아니라 재실행 가능한 스크립트로 만든다.**

3. 약국 필터링:
   - **대상 지역을 좁힌다** (기본: 서울 + 경기 일부). 전국에 300개를 흩뿌리면 반경 2km 안에 약국이 2~3개밖에 안 잡혀 **가격 비교 자체가 성립하지 않는다**
   - 좌표(위경도)가 비어 있거나 0인 행 제거
   - 300~500건 샘플링. 같은 행정구역에 몰리도록 뽑는다

4. 의약품: 일반의약품 30~50종 추출.
   - **`package_unit` 을 반드시 채운다.** 타이레놀 8정과 16정을 같은 `drug` 로 묶으면 가격 비교가 무의미해진다. 포장 단위가 다르면 **별개의 행**이다
   - `category` 는 `해열진통` / `소화제` / `감기약` / `연고` / `소독약` / `비타민` / `기타` 중 하나로 매핑
   - `base_price` 는 시중 가격을 참고해 수기 입력 (시드 생성용, 운영 시 미사용)

5. 관리자 계정과 더미 제보자를 함께 생성한다.
   - `admin@example.com` — 비밀번호 BCrypt 해시를 미리 만들어 넣는다 (예: `Admin1234!`)
   - 더미 제보자 20명 (`user01@example.com` ~)

6. 결과를 `V2__seed_master.sql` 로 출력한다. `ON CONFLICT (hira_code) DO NOTHING` 으로 멱등하게 작성한다.

7. 원본 CSV는 `tools/seed-generator/data/` 에 커밋해 재현성을 확보한다 (용량이 크면 필터링 후 저장).

**선행 태스크** T-06

**관련 파일**
- `tools/seed-generator/build_master_seed.py` — `CREATE` — 변환 스크립트
- `tools/seed-generator/data/` — `CREATE` — 원본 데이터
- `miniProject1_backEnd/src/main/resources/db/migration/V2__seed_master.sql` — `CREATE` — 마스터 시드
- `DATABASE.md` — `REFERENCE` — §6 시드 전략

**완료 판정**
- `region` ≥ 20건, `pharmacy` ≥ 300건, `drug` ≥ 30종 적재
- 모든 `pharmacy` 행에 `lat`, `lng`, `region_code` 가 NULL이 아니다
- 마이그레이션을 두 번 돌려도 중복이 생기지 않는다
- `admin@example.com` 의 BCrypt 해시가 들어있다 (T-24 이후 로그인으로 검증)
- **임의의 좌표 하나를 골라 반경 2km 안에 약국이 5개 이상** 잡힌다

**메모**
이 태스크가 임계 경로에서 가장 위험하다. **착수 첫날 저녁에 CSV 확보만이라도 먼저 끝내라.** 마지막 완료 판정이 실패하면 지역 범위가 너무 넓다는 뜻이니 되돌아가 좁힌다.

---

## T-08. 가격 제보 목데이터 생성 스크립트

**우선순위** P0 · **예상** 0.5d

**목적**
`price_report` 3,000건 이상을 현실적인 분포로 생성하고, 이상치 필터 데모를 위한 오타 데이터를 의도적으로 섞는다.

**구현 가이드**

1. [DATABASE.md](./DATABASE.md) §6.2의 생성 규칙을 구현한다.
   ```python
   random.seed(20260915)                       # 반드시 고정
   factor = {p.id: uniform(0.85, 1.25) for p in pharmacies}
   for p, d in product(pharmacies, drugs):
       if random() > 0.60: continue            # 커버리지 60%
       for _ in range(randint(1, 6)):
           price = round(d.base_price * factor[p.id] * gauss(1, 0.05), -1)
           age   = int(120 * random() ** 1.6)  # 최근 쪽에 몰리게
           purchased_at = today - timedelta(days=age)
           source = 'SEED'
   # 전체의 2%는 price를 base_price * choice(0.3, 3.0) 으로 덮어씀
   ```

2. **난수 시드를 고정한다.** 실행할 때마다 데이터가 달라지면 버그 재현이 불가능하다.

3. `purchased_at` 분포를 **최근 쪽에 몰리게** 한다. 전부 균등이면 신선도 점수 차이가 데모에서 안 드러난다.

4. `V3__seed_prices.sql` 로 출력하고, **같은 파일 끝에서 `pharmacy_drug_price_stat` 초기 계산 INSERT까지 수행한다.** T-10과 동일한 SQL([DATABASE.md](./DATABASE.md) §5.2)을 쓴다.

5. 이상치는 대부분 `flagged = false` 로 넣는다 — T-10의 IQR 필터가 걸러내는 걸 보여주는 게 목적이다. 일부만 `flagged = true` 로 두어 관리자 화면(T-32)에 보일 데이터도 만든다.

**선행 태스크** T-07

**관련 파일**
- `tools/seed-generator/build_price_seed.py` — `CREATE` — 제보 생성 스크립트
- `miniProject1_backEnd/src/main/resources/db/migration/V3__seed_prices.sql` — `CREATE` — 가격 시드
- `DATABASE.md` — `REFERENCE` — §6.2 생성 규칙, §5.2 통계 쿼리

**완료 판정**
- `price_report` ≥ 3,000건, 그중 약 2%가 이상치 범위
- `pharmacy_drug_price_stat` 이 채워져 있고 `rep_price` 가 NULL인 행이 없다
- 같은 스크립트를 두 번 돌리면 **동일한 데이터**가 나온다 (시드 고정 확인)
- 임의의 약품에 대해 반경 2km 검색 시 후보 약국이 5개 이상
- 같은 약품에 대해 약국별 `rep_price` 가 실제로 다르다 (전부 같으면 factor가 안 먹은 것)

---

# FS-2. 최저가 검색 (핵심 슬라이스)

> 이 슬라이스가 끝나면 **"검색창에 약 이름을 넣으면 최저가 약국 목록이 나온다"** 가 끝에서 끝까지 동작한다. 여기까지가 이 프로젝트의 본체다.

## T-09. 거리 계산 컴포넌트 (Haversine + 바운딩 박스)

**우선순위** P0 · **예상** 0.5d

**목적**
PostGIS 없이 반경 검색을 수행하는 거리 계산기를 만든다. 나중에 PostGIS로 교체 가능하도록 인터페이스 뒤에 둔다.

**구현 가이드**

1. 인터페이스를 정의한다.
   ```java
   public interface DistanceCalculator {
       BoundingBox boundingBox(double lat, double lng, int radiusM);
       double distanceMeters(double lat1, double lng1, double lat2, double lng2);
   }

   public record BoundingBox(double minLat, double maxLat, double minLng, double maxLng) {}
   ```

2. `HaversineDistanceCalculator` 를 구현한다.
   ```
   latDelta = radiusM / 111_320.0
   lngDelta = radiusM / (111_320.0 * cos(toRadians(lat)))
   ```
   ⚠️ **경도 델타에 `cos(lat)` 보정을 빼먹으면** 위도가 높을수록 반경이 과도하게 넓어진다. 한국 위도(37도)에서 약 25% 오차다.

3. Haversine 거리:
   ```java
   double R = 6_371_000;
   double dLat = toRadians(lat2 - lat1), dLng = toRadians(lng2 - lng1);
   double a = pow(sin(dLat / 2), 2)
            + cos(toRadians(lat1)) * cos(toRadians(lat2)) * pow(sin(dLng / 2), 2);
   return R * 2 * asin(sqrt(a));
   ```

4. 바운딩 박스는 정사각형이라 모서리에 반경 밖 약국이 섞인다. **반드시 정확 거리로 2차 필터링한다.**

5. `radiusM` 허용값은 500 / 1000 / 2000 / 5000. 그 외는 `IllegalArgumentException` → `400 INVALID_RADIUS` 로 변환한다(T-35).

6. 좌표 유효성 검증 유틸도 함께 둔다 — 위도 33~39, 경도 124~132 (대한민국 범위).

**선행 태스크** T-08

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/distance/DistanceCalculator.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/distance/HaversineDistanceCalculator.java` — `CREATE`
- `DATABASE.md` — `REFERENCE` — §4 거리 계산

**완료 판정**
- 강남역(37.4979, 127.0276) ↔ 역삼역(37.5006, 127.0366)의 거리가 실제값(약 850m) 대비 오차 1% 이내
- 바운딩 박스가 반경 원을 완전히 포함한다 (북/남/동/서 경계 좌표 4방향 테스트)
- 위도 33도와 38도에서 `lngDelta` 가 다르게 계산된다 (cos 보정 확인)
- 허용 밖 반경에 예외가 발생한다

---

## T-10. 대표가격 재계산 서비스 (IQR + 중앙값)

**우선순위** P0 · **예상** 1d

**목적**
(약국, 약품) 조합의 대표가격을 산출해 `pharmacy_drug_price_stat` 에 반영한다. 추천 품질의 토대다.

**구현 가이드**

1. [PRD.md](./PRD.md) §F3.1 절차를 그대로 구현한다.
   ```
   1) 대상: status='ACTIVE' AND flagged=false AND purchased_at >= CURRENT_DATE - 90일
   2) 0건이면 창을 180일로 확대 재시도. 그래도 0건이면 stat 행 삭제
   3) 4건 이상이면 IQR 이상치 제거 (Q1-1.5×IQR ~ Q3+1.5×IQR)
   4) 남은 값의 중앙값 → rep_price
   5) min/max/avg/count/last_reported_at/window_days 함께 저장
   ```

2. **평균이 아니라 중앙값을 쓴다.** 제보가 3~5건일 때 오타 하나가 평균을 크게 흔들기 때문이다. 평균은 표시용으로만 저장한다.

3. **4건 미만이면 IQR 계산을 생략한다.** 표본이 적으면 사분위수 자체가 무의미하고, 3건 중 1건이 제거되는 일이 생긴다.

4. 인터페이스:
   ```java
   public interface PriceStatService {
       /** 해당 조합의 통계를 재계산해 upsert하고, 유효 제보가 0이면 삭제한다. */
       Optional<PriceStat> recalculate(long pharmacyId, long drugId);
   }
   ```

5. 계산 SQL은 [DATABASE.md](./DATABASE.md) §5.2를 사용한다 (`percentile_cont`). upsert는 `INSERT ... ON CONFLICT (pharmacy_id, drug_id) DO UPDATE`.

6. `@Transactional` 로 묶는다. 호출 지점: 제보 생성 직후(T-26), 관리자 상태 변경(T-32).

7. 유효 제보가 0이 되면 stat 행을 **삭제**한다. 그래야 검색 결과에서 자동으로 빠진다.

**선행 태스크** T-08

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/service/PriceStatService.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/repository/PriceStatRepository.java` — `CREATE`
- `PRD.md` — `REFERENCE` — §F3.1
- `DATABASE.md` — `REFERENCE` — §5.2 재계산 쿼리

**완료 판정**
- 제보 5건 중 극단값 1건이 있을 때 `rep_price` 가 그 값에 흔들리지 않는다
- 제보 3건일 때 IQR 제거 없이 중앙값이 나온다
- 90일 내 제보가 없으면 180일 창으로 확대되고 `window_days = 180` 으로 기록된다
- 유효 제보가 0이면 stat 행이 삭제된다
- 같은 조합에 두 번 호출해도 결과가 동일하다 (멱등)

---

## T-11. 추천 Score 계산 엔진

**우선순위** P0 · **예상** 1d

**목적**
가격·거리·신선도를 가중 합산해 최종 순위를 산출한다. **이 서비스의 핵심 로직이다.**

**구현 가이드**

1. [API.md](./API.md) §5 "Score 계산 명세" 를 그대로 구현한다.
   ```
   priceScore_i     = (P_max == P_min) ? 1.0 : (P_max - rep_i) / (P_max - P_min)
   distanceScore_i  = clamp(1 - dist_i / R, 0, 1)
   freshnessScore_i = 0.5 ^ (ageDays_i / 30)
   score_i = 0.60*price + 0.25*distance + 0.15*freshness
   ```

2. **Score 계산과 정렬은 SQL이 아니라 Java 서비스 레이어에서 한다.** 후보가 수백 건 수준이라 성능 차이가 없고, 단위 테스트 작성이 비교할 수 없이 쉬워진다. SQL은 거리와 통계만 가져온다.

3. 순수 함수로 분리해 DB 없이 테스트 가능하게 만든다.
   ```java
   public record Candidate(
       long pharmacyId, int repPrice, double distanceM,
       LocalDate lastReportedAt, int reportCount
   ) {}

   public record ScoredCandidate(
       Candidate candidate, double score, ScoreBreakdown breakdown, List<Badge> badges
   ) {}

   public interface ScoreCalculator {
       List<ScoredCandidate> rank(List<Candidate> candidates, int radiusM, LocalDate today);
   }
   ```

4. **`P_max == P_min` 분기를 반드시 넣는다.** 빼먹으면 후보가 1개일 때 0으로 나누기가 발생한다.

5. 가중치와 반감기는 `RecommendationProperties` 에서 주입받는다. **하드코딩 금지.**

6. 정렬 타이브레이커: `score DESC → repPrice ASC → distanceM ASC → pharmacyId ASC`.
   **마지막 `pharmacyId` 가 결정성을 보장한다** — 없으면 같은 입력에 순서가 흔들려 테스트가 깨진다.

7. 뱃지 판정: `LOWEST_PRICE`(1위), `LOW_CONFIDENCE`(reportCount == 1), `STALE_DATA`(ageDays > 30), `NEAREST`(최단거리).

8. 모든 점수는 소수점 4자리로 반올림해 응답한다.

**선행 태스크** T-09, T-10

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/service/ScoreCalculator.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/dto/ScoreBreakdown.java` — `CREATE`
- `API.md` — `REFERENCE` — §5 Score 계산 명세

**완료 판정**
- 수식이 [PRD.md](./PRD.md) §F3.2 및 [API.md](./API.md) §5와 완전히 일치
- 후보 1개일 때 예외 없이 `priceScore = 1.0`
- 가중치를 yml에서 바꾸면 순위가 실제로 바뀐다
- `scoreBreakdown` 이 항상 채워져 순위 근거를 설명할 수 있다

**메모**
가중치 튜닝은 여기서 하지 않는다. 수식을 문서에 고정하고, 조정은 전체가 돌아간 뒤에 한다.

---

## T-12. 추천 엔진 단위 테스트 스위트

**우선순위** P0 · **예상** 0.5d

**목적**
각 요인이 순위에 미치는 영향을 테스트로 고정한다. 리팩터링 안전망이자 데모 설명 근거다.

**구현 가이드**

`ScoreCalculator` 테스트 (DB 불필요):

| # | 테스트 | 기대 |
|---|---|---|
| 1 | 거리·신선도 동일, 가격만 다름 | 싼 쪽이 상위 |
| 2 | 가격·신선도 동일, 거리만 다름 | 가까운 쪽이 상위 |
| 3 | 가격·거리 동일, 신선도만 다름 | 최근 쪽이 상위 |
| 4 | 후보 1개 | `priceScore = 1.0`, 예외 없음 |
| 5 | 모든 후보 가격 동일 | 전원 `priceScore = 1.0` (0 나누기 없음) |
| 6 | 동일 입력 2회 호출 | 순서 완전 일치 (결정성) |
| 7 | 가장 싼 약국이 반경 경계, 2위가 코앞 | 거리 가중치로 순위 역전 — **의도된 동작으로 고정** |
| 8 | reportCount 1, ageDays 40 | `LOW_CONFIDENCE` + `STALE_DATA` 뱃지 |

`PriceStatService` 테스트 (DB 필요):

| # | 테스트 | 기대 |
|---|---|---|
| 9 | 5건 중 극단값 1건 | `rep_price` 가 흔들리지 않음 |
| 10 | 3건 (4건 미만) | IQR 제거 생략, 중앙값 반환 |
| 11 | 90일 내 0건, 180일 내 존재 | 확대 창으로 계산, `window_days = 180` |
| 12 | 유효 제보 0건 | stat 행 삭제 |

**절대 점수값이 아니라 상대 순위를 검증한다.** 가중치를 바꿔도 테스트가 의미를 유지해야 한다.

**선행 태스크** T-11

**관련 파일**
- `miniProject1_backEnd/src/test/java/com/pharmaprice/recommendation/ScoreCalculatorTest.java` — `CREATE`
- `miniProject1_backEnd/src/test/java/com/pharmaprice/recommendation/PriceStatServiceTest.java` — `CREATE`
- `PRD.md` — `REFERENCE` — §10 성공 지표

**완료 판정**
- 12개 테스트 전부 통과
- `miniProject1_backEnd/` 에서 `./mvnw test` 로 재현 가능

**메모**
7번 테스트가 중요하다. "제일 싼 곳이 1위가 아닌 게 버그 아니냐"는 질문이 데모에서 반드시 나온다. 테스트가 그 답이다.

---

## T-13. 의약품 검색 API

**우선순위** P0 · **예상** 0.5d

**목적**
`GET /api/v1/drugs` 와 `GET /api/v1/drugs/{drugId}` 를 구현한다. 자동완성의 백엔드다.

**구현 가이드**

1. `q` 는 `display_name` 과 `name` 에 대한 부분 일치. `pg_trgm` GIN 인덱스를 타도록 `ILIKE '%' || :q || '%'` 를 쓴다.
2. **`otc_flag = true` 인 것만 반환한다.** 전문의약품은 어떤 경로로도 노출되면 안 된다 (PRD F1-6).
3. `nationalAvgPrice`, `pharmacyCount` 는 `pharmacy_drug_price_stat` 집계. **서브쿼리 N+1이 나지 않게 조인 한 번으로** 처리한다.
4. 페이지네이션 래퍼는 [API.md](./API.md) §1.1 포맷. `size` 는 최대 50으로 clamp.
5. 상세 조회는 `priceStats` 객체(전국 평균·최저·최고·약국 수·제보 수) 포함.

**선행 태스크** T-08

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/drug/controller/DrugController.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/drug/repository/DrugQueryRepository.java` — `CREATE` — native query
- `API.md` — `REFERENCE` — §3

**완료 판정**
- `GET /api/v1/drugs?q=타이레놀` 이 200과 함께 1건 이상 반환
- 응답 필드가 [API.md](./API.md) §3 과 정확히 일치
- 전문의약품 `item_seq` 로 조회해도 결과에 없다
- `size=8` 로 호출 시 응답 200ms 이내

---

## T-14. 지역 목록 API

**우선순위** P0 · **예상** 0.25d

**목적**
`GET /api/v1/regions` — 위치 권한 거부 시 폴백 드롭다운용 데이터를 제공한다.

**구현 가이드**

1. 시도별로 그룹핑한 트리 구조로 반환한다 ([API.md](./API.md) §7).
2. 각 시군구에 `pharmacyCount` 를 포함해, **약국 데이터가 없는 지역은 프론트에서 비활성 처리**할 수 있게 한다.
3. 전체 ~250건이므로 페이지네이션 없음. `Cache-Control: max-age=3600` 을 붙인다.

**선행 태스크** T-08

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/pharmacy/controller/RegionController.java` — `CREATE`
- `API.md` — `REFERENCE` — §7

**완료 판정**
- 시도별 그룹 구조로 반환되고 `centerLat`/`centerLng` 가 모두 채워져 있다
- `pharmacyCount` 가 실제 약국 수와 일치한다

---

## T-15. 최저가 검색 API (`GET /api/v1/search`)

**우선순위** P0 · **예상** 1d

**목적**
서비스의 핵심 엔드포인트를 완성한다. 위치 + 약품 → 추천 결과.

**구현 가이드**

1. 파라미터 검증: `drugId` 필수, `lat`+`lng` 조합 **또는** `regionCode` 중 하나 필수. 둘 다 없으면 `400 VALIDATION_FAILED`.
2. `regionCode` 로 들어오면 해당 `region.center_lat/lng` 를 좌표로 쓰고 `query.locationSource = "REGION"` 으로 표시한다.
3. 흐름: 후보 조회(바운딩 박스, T-09) → 정확 거리 필터 → `Candidate` 변환 → `ScoreCalculator.rank()`(T-11) → 응답 조립.
4. `sort` 파라미터: `SCORE`(기본) / `PRICE` / `DISTANCE`. **Score는 항상 계산해 응답에 넣되 정렬 기준만 바꾼다.**
5. `summary`: `candidateAvgPrice`, `candidateMinPrice`, `candidateMaxPrice`, `maxSaving = max - min`.
6. `dataSource`: 결과에 포함된 제보의 `source` 를 보고 `SEED` / `MIXED` / `USER` 판정. **프론트 고지 배너 제어에 쓰인다.**
7. 결과 0건이면 `suggestion` 을 채운다 — **반경을 한 단계 넓혔을 때의 예상 건수를 실제로 계산해서** 내려준다 (PRD F3-9).
8. Score 계산 결과를 DEBUG 레벨로 로깅한다 (순위 근거 추적용).

**선행 태스크** T-11, T-14

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/controller/SearchController.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/service/SearchService.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/recommendation/repository/SearchQueryRepository.java` — `CREATE`
- `API.md` — `REFERENCE` — §5 전체

**완료 판정**
- 응답 구조가 [API.md](./API.md) §5 예시와 필드 단위로 일치 (`scoreBreakdown`, `badges`, `summary`, `dataSource` 포함)
- 반경 2km 검색 p95 < 500ms
- 결과 0건일 때 `suggestion.estimatedCount` 가 실제 확대 반경의 건수와 일치
- `sort=PRICE` 로 바꾸면 순위가 실제로 달라진다
- 제보가 0건인 약국은 결과에 나타나지 않는다
- `regionCode` 만으로도 검색된다

---

## T-16. 위치 획득 및 지역 폴백

**우선순위** P0 · **예상** 0.5d

**목적**
브라우저 GPS로 좌표를 얻고, 실패 시 시·군·구 선택으로 매끄럽게 폴백한다. **이게 막히면 핵심 흐름 전체가 막힌다.**

**구현 가이드**

1. `useUserLocation()` 훅을 만든다.
   ```typescript
   type LocationState =
     | { status: 'idle' | 'requesting' }
     | { status: 'granted'; lat: number; lng: number; source: 'GPS' }
     | { status: 'fallback'; lat: number; lng: number; source: 'REGION'; regionCode: string }
     | { status: 'denied' | 'unavailable' }
   ```

2. `navigator.geolocation.getCurrentPosition` 을 `{ enableHighAccuracy: false, timeout: 8000 }` 으로 호출한다.
   **고정밀을 켜면 실내에서 8초를 넘겨 사용자가 이탈한다.**

3. 거부/타임아웃/미지원 시 즉시 `RegionPicker` 모달을 띄운다 — `GET /api/v1/regions` 로 시도 → 시군구 2단 선택, 선택하면 `centerLat/centerLng` 를 좌표로 쓴다.

4. 선택한 위치를 `sessionStorage` 에 보관해 페이지 이동마다 다시 묻지 않는다.
   **접근 실패를 대비해 try/catch로 감싼다** — 시크릿 모드나 사이트 데이터 차단 시 접근 자체가 예외를 던진다.

5. 헤더에 현재 위치를 표시하고 클릭하면 다시 고를 수 있게 한다. GPS/지역 출처를 구분해 보여준다.

6. `pharmacyCount = 0` 인 지역은 드롭다운에서 비활성화한다.

**선행 태스크** T-04, T-14

**관련 파일**
- `miniProject1_frontEnd/hooks/use-user-location.ts` — `CREATE`
- `miniProject1_frontEnd/components/region-picker.tsx` — `CREATE`
- `miniProject1_frontEnd/components/location-indicator.tsx` — `CREATE`

**완료 판정**
- 권한 허용 시 좌표 획득 후 헤더에 표시
- 권한 **거부** 시 지역 선택 모달이 뜨고, 선택 후 검색이 정상 동작
- 8초 타임아웃 시에도 폴백이 뜬다
- 페이지를 이동해도 위치가 유지된다
- 시크릿 모드(스토리지 차단)에서도 크래시 없이 동작

**메모**
발표 중 권한 팝업이 뜨면 흐름이 끊긴다. 미리 허용해 두거나 지역 폴백으로 진행한다.

---

## T-17. 홈 화면 + 약품 자동완성

**우선순위** P0 · **예상** 0.5d

**목적**
서비스 진입점. 약품을 고르고 검색으로 넘기는 흐름을 만든다.

**구현 가이드**

1. 중앙에 큰 검색창, 아래에 인기 약품 칩 6~8개(타이레놀, 게보린, 판콜에이, 베아제 등).
2. 자동완성: `GET /api/v1/drugs?q=&size=8`, **300ms 디바운스**. 입력마다 호출하면 서버가 시끄럽다.
3. 결과 항목에 `displayName` + `packageUnit` 을 **함께** 보여준다.
   "타이레놀 500mg"만으로는 8정인지 16정인지 알 수 없어 사용자가 엉뚱한 걸 고른다.
4. 키보드 내비게이션: ↑↓ 이동, Enter 선택, Esc 닫기. `role="combobox"` + `aria-activedescendant`.
5. 선택 시 `/search?drugId={id}&lat=&lng=&radius=2000` 으로 이동.
6. 위치가 아직 없으면 T-16 훅을 먼저 태운다.

**선행 태스크** T-16

**관련 파일**
- `miniProject1_frontEnd/app/page.tsx` — `TO_MODIFY` — 홈 화면
- `miniProject1_frontEnd/components/drug-autocomplete.tsx` — `CREATE`

**완료 판정**
- 한글 2글자 입력 시 8건 이내 후보가 300ms 내 표시
- 각 후보에 포장 단위가 보인다
- 키보드만으로 검색 완료 가능
- 결과 없을 때 빈 상태 메시지 표시

---

## T-18. 검색 결과 화면

**우선순위** P0 · **예상** 1d

**목적**
`/search` 결과를 Score 순으로 보여준다. **데모의 핵심 화면이다.**

**구현 가이드**

1. 서버 컴포넌트에서 `GET /api/v1/search` 를 호출해 SSR한다. 정렬·반경 변경은 **URL 쿼리로 처리**해 공유와 뒤로가기가 동작하게 한다.
2. 상단 요약: "반경 2km 내 7곳 · 최대 1,300원 절약 가능".
3. 1위 카드는 시각적으로 강하게 구분한다 — 강조 테두리 + "최저가 추천" 뱃지.
4. 각 카드 구성:
   - 약국명, 도로명 주소
   - **대표가격(크게)**, 최저가(작게)
   - 거리 뱃지, 제보 수, "3일 전 갱신"
   - `savingVsCandidateAvg` 가 양수면 "평균보다 540원 저렴"
   - `LOW_CONFIDENCE` → "정보 부족", `STALE_DATA` → "오래된 정보" 뱃지
5. 정렬 토글: 추천순 / 가격순 / 거리순. 반경 필터: 500m / 1km / 2km / 5km.
6. 결과 0건이면 `suggestion` 을 읽어 "반경을 5km로 넓히면 12곳이 있습니다" + 확대 버튼.
7. `dataSource` 가 `SEED` 또는 `MIXED` 면 결과 상단에 목데이터 고지를 한 번 더 노출한다.
8. 레이아웃: 모바일은 카드 리스트 전체 폭, 데스크톱은 좌측 리스트 + 우측 지도 자리(T-22에서 채움).

**선행 태스크** T-15, T-17

**관련 파일**
- `miniProject1_frontEnd/app/search/page.tsx` — `CREATE`
- `miniProject1_frontEnd/components/pharmacy-result-card.tsx` — `CREATE`
- `miniProject1_frontEnd/components/sort-toggle.tsx` — `CREATE`
- `API.md` — `REFERENCE` — §5 응답 구조

**완료 판정**
- 실제 좌표로 검색 시 Score 순 결과가 렌더링됨
- 정렬을 "가격순"으로 바꾸면 1위가 바뀐다 (URL도 함께 변함)
- 0건일 때 반경 확대 제안이 뜨고 클릭하면 실제로 결과가 나온다
- 375px 폭에서 카드가 깨지지 않는다
- 뒤로가기 시 이전 검색 조건이 복원된다

**메모**
✅ **여기까지가 FS-2다. 이 시점에 "검색 → 최저가 확인"이 끝에서 끝까지 동작해야 한다.** 안 되면 다음 슬라이스로 넘어가지 말고 여기서 잡는다.

---

# FS-3. 약국 상세

## T-19. 약국 검색·상세 API

**우선순위** P0 · **예상** 0.5d

**목적**
`GET /api/v1/pharmacies` (제보 폼의 약국 선택용) 와 `GET /api/v1/pharmacies/{pharmacyId}` (약국 상세) 를 구현한다.

**구현 가이드**

1. 목록: `q`(이름·주소 부분 일치) 또는 `lat`+`lng`(반경 검색) 중 최소 하나 필수. 둘 다 없으면 `400 VALIDATION_FAILED`.
2. `lat`/`lng` 가 있으면 `distanceM` 을 채우고, 없으면 `null`.
   거리 계산은 **T-09 컴포넌트를 재사용한다 — 여기서 Haversine을 중복 구현하지 말 것.**
3. 상세: `businessHours` JSONB, `region`, `drugPrices` 배열(`repPrice` 오름차순).
4. `drugPrices` 의 `diffFromNationalAvg` 는 `repPrice - nationalAvgPrice`.
5. 좌표 유효성: 대한민국 범위 밖이면 `400 INVALID_COORDINATE`.

**선행 태스크** T-09

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/pharmacy/controller/PharmacyController.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/pharmacy/repository/PharmacyQueryRepository.java` — `CREATE`
- `API.md` — `REFERENCE` — §4

**완료 판정**
- 이름 검색과 좌표 검색이 각각 동작하고, 둘 다 없으면 400
- 약국 상세의 `drugPrices` 가 가격 오름차순으로 정렬됨
- 대한민국 범위 밖 좌표로 호출 시 `400 INVALID_COORDINATE`

---

## T-20. 가격 이력 API

**우선순위** P1 · **예상** 0.25d

**목적**
`GET /api/v1/pharmacies/{pharmacyId}/drugs/{drugId}/history` — 약국 상세의 가격 추이 차트용 데이터.

**구현 가이드**

1. `days` 파라미터 (기본 180, 최대 365) 범위의 `{purchasedAt, price, flagged}` 배열을 `purchasedAt` 오름차순으로 반환한다.
2. **`flagged: true` 인 점도 포함한다.** 프론트가 회색 점선으로 표시해 "이 값은 통계에서 빠졌다"를 보여줄 수 있어야 한다. 이상치 처리를 사용자에게 드러내는 유일한 지점이다.
3. `status = 'HIDDEN'` 인 제보는 제외한다.

**선행 태스크** T-19

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/pharmacy/controller/PharmacyController.java` — `TO_MODIFY`
- `API.md` — `REFERENCE` — §4 history

**완료 판정**
- 응답에 `flagged` 항목이 포함된다
- `days=30` 으로 좁히면 결과가 줄어든다
- 이력이 0건이어도 빈 배열과 200을 반환한다 (404 아님)

---

## T-21. 약국 상세 화면 + 가격 이력

**우선순위** P0 · **예상** 0.75d

**목적**
약국의 취급 약품별 가격과 이력을 보여주고 제보로 연결한다.

**구현 가이드**

1. 상단: 약국명, 주소, 전화(`tel:` 링크), 영업시간, 거리. 카카오맵 길찾기 링크.
2. `drugPrices` 테이블: 약품명 + 포장단위, 대표가격, 제보 수, 최근 갱신일, 전국 평균 대비 차이(음수면 초록, 양수면 회색).
3. 약품 행을 펼치면 T-20으로 가격 이력 스파크라인을 그린다 (Recharts).
4. **`flagged: true` 인 점은 회색 점선으로 표시**하고 툴팁에 "통계에서 제외된 제보"라고 쓴다.
5. "이 약국에 가격 제보하기" 버튼 → `/reports/new?pharmacyId={id}` (FS-4에서 동작. 그 전에는 버튼만 두고 비활성 처리해도 된다).
6. 차트 색상은 시리즈당 1색, 강조는 1개만. 수치 라벨을 병기해 **색상만으로 정보를 전달하지 않는다.**
7. 이력이 1건뿐일 때도 차트가 깨지지 않게 한다 (점 하나만 찍힘).

**선행 태스크** T-20, T-18

**관련 파일**
- `miniProject1_frontEnd/app/pharmacies/[id]/page.tsx` — `CREATE`
- `miniProject1_frontEnd/components/price-history-chart.tsx` — `CREATE`

**완료 판정**
- 약품별 가격표가 가격 오름차순으로 표시됨
- 이력 차트에서 flagged 점이 시각적으로 구분되고 툴팁이 뜬다
- 검색 결과 카드에서 약국 상세로 이동된다
- 이력 데이터가 1건일 때도 차트가 깨지지 않는다

---

## T-22. 카카오맵 연동

**우선순위** P1 · **예상** 1d

**목적**
검색 결과를 지도에 표시하고 리스트와 상호 연동한다.

**구현 가이드**

1. 카카오맵 JS SDK를 `next/script` 의 `strategy="afterInteractive"` 로 로드한다. 키는 `NEXT_PUBLIC_KAKAO_MAP_KEY`.
2. **반드시 `"use client"` 컴포넌트**로 만든다. 서버 컴포넌트에서 SDK를 건드리면 터진다.
3. 마커: 사용자 위치(별도 아이콘) + 후보 약국. 1위는 다른 색·크기로 구분.
4. **마커에 가격을 라벨로 띄운다** (`CustomOverlay`). 지도만 봐도 가격 비교가 되는 게 핵심이다.
5. 리스트 ↔ 마커 연동: 카드 hover/click 시 마커 강조 + 지도 중심 이동, 마커 클릭 시 리스트 스크롤.
6. 결과 전체가 보이도록 `LatLngBounds` 로 초기 줌을 자동 조정한다.
7. **SDK 로드 실패 시 지도 영역을 숨기고 리스트만 보여준다.** 지도가 없어도 서비스는 동작해야 한다.

**선행 태스크** T-18

**관련 파일**
- `miniProject1_frontEnd/components/pharmacy-map.tsx` — `CREATE`
- `miniProject1_frontEnd/app/search/page.tsx` — `TO_MODIFY` — 지도 영역 채우기
- `.env.example` — `REFERENCE` — 카카오 키

**완료 판정**
- 후보 약국이 전부 보이도록 지도 범위가 자동 조정됨
- 마커에 가격이 표시되고 1위가 구분된다
- 카드↔마커 양방향 연동 동작
- **SDK 로드를 강제로 실패시켜도 리스트는 정상 동작** (스크립트 URL을 틀리게 해서 확인)

**메모**
카카오 개발자 콘솔에서 플랫폼 도메인에 `http://localhost:3000` 을 등록해야 한다. 안 하면 인증 오류로 지도가 안 뜬다. **시간이 부족하면 가장 먼저 잘라낼 태스크다.**

---

# FS-4. 인증 + 제보

> 검색은 비로그인으로 동작하므로 인증을 여기까지 미뤘다. 이 슬라이스가 끝나면 **"제보하면 순위가 바뀐다"** 는 데모의 하이라이트가 가능해진다.

## T-23. Spring Security + JWT 기반 구성

**우선순위** P0 · **예상** 1d

**목적**
JWT 발급·검증 인프라와 URL별 접근 제어를 세운다.

**구현 가이드**

1. `JwtTokenProvider`: HS256 서명, access 30분 / refresh 14일. 시크릿은 `JWT_SECRET` 환경변수 (최소 32바이트).
   발급한 refresh 토큰은 **원문이 아니라 SHA-256 해시**를 `refresh_token` 테이블에 저장한다.

2. `JwtAuthenticationFilter` 를 `UsernamePasswordAuthenticationFilter` 앞에 등록한다.

3. `SecurityFilterChain`:
   - `csrf` 비활성 (stateless JWT), `sessionCreationPolicy: STATELESS`
   - `permitAll`: `/api/v1/auth/**`, `GET /api/v1/drugs/**`, `GET /api/v1/pharmacies/**`, `GET /api/v1/search`, `GET /api/v1/regions`, `/swagger-ui/**`, `/v3/api-docs/**`, `/actuator/health`
   - `hasRole('ADMIN')`: `/api/v1/admin/**`
   - 나머지 `authenticated()`

4. CORS: `http://localhost:3000` 허용, `allowCredentials: true`.

5. `PasswordEncoder` 는 `BCryptPasswordEncoder(10)`.

6. `@EnableMethodSecurity` 를 켜서 `@PreAuthorize` 를 쓸 수 있게 한다.

7. **인증 실패 응답을 [API.md](./API.md) §1.2 포맷으로 맞춘다.** `AuthenticationEntryPoint` 와 `AccessDeniedHandler` 를 커스터마이즈하지 않으면 기본 Spring 에러 페이지가 나가서 프론트가 파싱하지 못한다.

**선행 태스크** T-06

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/auth/security/` — `CREATE` — JWT 프로바이더·필터
- `miniProject1_backEnd/src/main/java/com/pharmaprice/common/config/SecurityConfig.java` — `CREATE` — 필터 체인
- `API.md` — `REFERENCE` — §1.3 인증 방식, §1.2 에러 포맷

**완료 판정**
- 토큰 없이 `POST /api/v1/price-reports` 호출 시 `401` + `{"code":"UNAUTHENTICATED"}` (JSON)
- USER 토큰으로 `/api/v1/admin/**` 호출 시 `403` + `{"code":"FORBIDDEN"}`
- 만료된 토큰으로 호출 시 `401`
- `GET /api/v1/search` 는 토큰 없이 `200`

---

## T-24. 인증 API (가입 · 로그인 · 갱신 · 로그아웃 · 내정보)

**우선순위** P0 · **예상** 0.5d

**목적**
[API.md](./API.md) §2의 인증 엔드포인트 5개를 구현한다.

**구현 가이드**

1. `POST /auth/signup` — 이메일 유니크 검사 → BCrypt 해시 → 저장. 중복이면 `409 EMAIL_ALREADY_EXISTS`.
2. `POST /auth/login` — 자격 검증 후 access + refresh 발급.
   **이메일이 틀렸는지 비밀번호가 틀렸는지 구분해 응답하지 않는다** (계정 존재 여부 노출 방지). 둘 다 `401 UNAUTHENTICATED`.
3. `POST /auth/refresh` — `revoked_at IS NULL AND expires_at > now()` 검증 후 **기존 토큰을 revoke하고 새로 발급(rotation)**. 탈취된 토큰이 14일간 유효한 상태를 막는다.
4. `POST /auth/logout` 🔐 — 전달받은 refresh 토큰의 `revoked_at` 설정 후 `204`.
   **이미 revoke됐거나 없는 토큰이어도 `204`** — 로그아웃은 멱등해야 한다.
5. `GET /auth/me` — 현재 사용자 + `reportCount`.
6. 검증 규칙: 이메일 형식, 비밀번호 8~64자 영문+숫자 포함, 닉네임 2~30자.
7. **응답에 `passwordHash` 가 절대 포함되지 않도록** DTO를 분리한다. 엔티티를 그대로 반환하지 않는다.

**선행 태스크** T-23

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/auth/controller/AuthController.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/auth/dto/` — `CREATE` — 요청·응답 DTO
- `API.md` — `REFERENCE` — §2 전체

**완료 판정**
- 5개 엔드포인트가 [API.md](./API.md) §2 명세와 요청·응답이 정확히 일치
- 중복 이메일 가입 시 `409`
- 응답 JSON 어디에도 비밀번호 해시가 없다
- 통합 테스트: 가입 → 로그인 → `/me` → 로그아웃 → 같은 refresh 토큰으로 `/refresh` 시 `401`
- 로그아웃을 두 번 호출해도 둘 다 `204`
- 시드로 넣은 `admin@example.com` 으로 로그인되고 `role = ADMIN` 이다

---

## T-25. 프론트 인증 화면 및 세션 관리

**우선순위** P0 · **예상** 1d

**목적**
로그인·회원가입 화면과 토큰 보관·자동 갱신을 구현하고 보호 라우트를 건다.

**구현 가이드**

1. `/login`, `/signup` 페이지. `react-hook-form` + `zod` 로 클라이언트 검증 (서버 규칙과 동일하게).
2. 토큰 보관: refresh 토큰은 Next.js Route Handler를 경유해 **httpOnly 쿠키**에, access 토큰은 메모리(Context)에.
   **localStorage에 refresh 토큰을 넣지 않는다.**
3. `lib/api.ts` 에 401 인터셉터를 붙인다 — 401이면 refresh 1회 시도 후 재요청, 그래도 실패하면 로그인으로.
   **무한 재시도 루프에 빠지지 않도록 재시도 플래그를 둔다.**
4. `AuthProvider` 컨텍스트로 `user`, `login()`, `logout()`, `isLoading` 제공.
   `logout()` 은 `POST /auth/logout` 을 호출한 뒤(실패해도 무시) 쿠키와 메모리 토큰을 비운다.
5. 보호 경로(`/reports/new`, `/me`, `/admin`)는 미들웨어 또는 서버 컴포넌트에서 검사해 미로그인 시 `/login?next=` 로 리다이렉트.
6. 서버 에러를 폼 필드 에러로 매핑한다 (`fieldErrors` 활용).

**선행 태스크** T-24

**관련 파일**
- `miniProject1_frontEnd/app/(auth)/login/page.tsx` — `CREATE`
- `miniProject1_frontEnd/app/(auth)/signup/page.tsx` — `CREATE`
- `miniProject1_frontEnd/lib/auth-context.tsx` — `CREATE`
- `miniProject1_frontEnd/lib/api.ts` — `TO_MODIFY` — 401 인터셉터
- `miniProject1_frontEnd/middleware.ts` — `CREATE` — 보호 라우트

**완료 판정**
- 가입 → 로그인 → 헤더에 닉네임 표시 → 로그아웃 흐름 동작
- 미로그인으로 `/reports/new` 접근 시 로그인으로 가고, 로그인 후 원래 경로로 복귀
- access 토큰 만료 후 API 호출 시 자동 갱신되어 흐름이 끊기지 않는다
- 새로고침해도 로그인 상태가 유지된다

---

## T-26. 가격 제보 생성 API

**우선순위** P0 · **예상** 1d

**목적**
`POST /api/v1/price-reports` — 사용자 제보를 저장하고 통계를 즉시 재계산한다.

**구현 가이드**

1. 검증:
   - `price` 100~200,000 정수
   - `purchasedAt` 미입력 시 오늘(KST). 미래이거나 180일 초과 과거면 `400 INVALID_DATE_RANGE`
   - `drugId` 가 `otc_flag = false` 면 `422 DRUG_NOT_OTC`
   - 약국·약품 미존재 시 각각 `404`

2. 중복 방지: DB의 부분 유니크 인덱스 위반(`DataIntegrityViolationException`)을 잡아 `409 DUPLICATE_REPORT` 로 변환한다.
   **애플리케이션 락 대신 DB 제약에 맡기는 편이 단순하고 확실하다.**

3. 이상치 판정: 해당 약품 전체 중앙값의 0.3배 미만 또는 3배 초과면 `flagged = true`, `flagReason = OUTLIER_LOW/HIGH`.
   **저장은 하되 통계에서만 제외한다** — 거부하면 사용자는 왜 실패했는지 모른다. `warning` 메시지를 응답에 넣는다.

4. **저장 + `PriceStatService.recalculate()` + `app_user.report_count` 증가**를 하나의 `@Transactional` 안에서 처리한다.
   `report_count` 는 `GET /auth/me` 와 `/me` 화면이 쓰는 값이라 여기서 갱신하지 않으면 영원히 0으로 남는다.

5. 응답에 `updatedStat` 을 포함해 프론트가 즉시 화면을 갱신할 수 있게 한다.

**선행 태스크** T-24, T-10

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/report/controller/PriceReportController.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/report/service/PriceReportService.java` — `CREATE`
- `API.md` — `REFERENCE` — §6

**완료 판정**
- 정상 제보 → `201` + `updatedStat` 반영
- 같은 날 같은 (약국, 약품) 재제보 → `409 DUPLICATE_REPORT`
- 이상치 제보 → `201` + `flagged: true` + `warning`, 그리고 **`rep_price` 는 변하지 않음**
- 전문의약품 제보 시도 → `422 DRUG_NOT_OTC`
- 제보 직후 `/search` 결과에 즉시 반영됨
- 제보 후 `GET /auth/me` 의 `reportCount` 가 1 증가

---

## T-27. 영수증 파일 업로드 API

**우선순위** P1 · **예상** 0.5d

**목적**
`POST /api/v1/uploads` — 영수증 이미지를 저장하고 파일 ID를 반환한다. **OCR은 하지 않는다.**

**구현 가이드**

1. `multipart/form-data`. `file` + `purpose=RECEIPT`.
2. 검증: `image/jpeg` / `image/png` / `image/webp` 만(`415`), 5MB 이하(`413`).
   **확장자가 아니라 실제 매직 바이트로 판정한다.**
3. 저장 경로: `${app.upload-dir}/{yyyy}/{MM}/{uuid}.{ext}`. 기본값은 프로젝트 루트의 `uploads/`.
   **원본 파일명을 경로에 쓰지 않는다** (경로 조작 방지).
   Docker를 안 쓰므로 볼륨 마운트가 없다 — 경로는 `application.yml` 의 `app.upload-dir` 로 빼고 `.gitignore` 에 넣는다.
4. `uploaded_file` 레코드를 생성하고 id를 반환한다.
5. `GET /api/v1/uploads/{fileId}` — 업로더 본인 또는 ADMIN만. 그 외 `403`.
6. `FileStorageService` 인터페이스로 분리한다 — S3 전환 시 구현체만 교체.

**선행 태스크** T-26

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/report/controller/UploadController.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/report/service/FileStorageService.java` — `CREATE`
- `API.md` — `REFERENCE` — §6 업로드

**완료 판정**
- 5MB 초과 → `413 FILE_TOO_LARGE`
- 확장자를 `.jpg` 로 위장한 PDF → `415 UNSUPPORTED_FILE_TYPE`
- 타인의 파일 조회 시 `403`
- 서버 재시작 후에도 업로드된 파일이 남아 있다

---

## T-28. 제보 목록 조회 API

**우선순위** P1 · **예상** 0.25d

**목적**
`GET /api/v1/price-reports` — 약국별·약품별·본인별 제보 목록.

**구현 가이드**

1. 필터: `pharmacyId`, `drugId`, `mine`(true면 인증 필요), 페이지네이션.
2. **`reporter` 는 닉네임만 노출한다.** id·이메일을 내려주면 개인정보 노출이다.
3. `hasReceipt` 는 boolean으로만 (파일 id를 일반 사용자에게 주지 않는다).

**선행 태스크** T-26

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/report/controller/PriceReportController.java` — `TO_MODIFY`
- `API.md` — `REFERENCE` — §6 목록

**완료 판정**
- 응답에 제보자 이메일·id가 없다
- `mine=true` 를 비로그인으로 호출 시 `401`

---

## T-29. 가격 제보 폼

**우선순위** P0 · **예상** 1d

**목적**
30초 안에 끝나는 제보 폼을 만든다. **입력이 길면 사용자는 이탈한다** (PRD 페르소나 P2).

**구현 가이드**

1. **단일 페이지 폼**으로 만든다. 스텝 마법사는 이 정보량에 과하다.
2. 필드 순서: 약국 → 약품 → 가격 → (접힘) 구매일 · 영수증 · 메모.
   **선택 항목은 기본으로 접어둔다.** 펼쳐두면 필수처럼 보여 심리적 부담이 커진다.
3. 약국 선택: 이름 검색 자동완성 + "지도에서 고르기". `?pharmacyId=` 쿼리가 있으면 미리 채운다.
4. 약품 선택: T-17의 `DrugAutocomplete` 재사용. **마스터에 없는 약품은 선택 불가** — 자유 입력을 허용하지 않는다.
5. 가격: `inputMode="numeric"`, 천단위 콤마 자동 포맷, 100~200,000 범위 검증.
6. 구매일: 기본 오늘, 미래 불가, 180일 이전 불가.
7. 제출 결과 처리:
   - 정상 → 성공 토스트 + 약국 상세로 이동 (`updatedStat` 으로 즉시 반영)
   - `flagged: true` → **경고 모달**로 `warning` 을 보여주되 "그래도 제보되었습니다"를 명확히
   - `409 DUPLICATE_REPORT` → "오늘 이미 이 약국의 해당 약품 가격을 제보하셨습니다"
8. 비로그인 진입 시 로그인으로 보내고, 복귀 시 **입력값을 잃지 않게** 한다.

**선행 태스크** T-26, T-25, T-21

**관련 파일**
- `miniProject1_frontEnd/app/reports/new/page.tsx` — `CREATE`
- `miniProject1_frontEnd/components/pharmacy-picker.tsx` — `CREATE`
- `API.md` — `REFERENCE` — §6 요청 스키마

**완료 판정**
- 약국 상세에서 진입 시 약국이 미리 채워져 있다
- `0`, `-100`, `abc` 입력 시 제출이 막히고 필드 에러가 뜬다
- 이상치 가격 제출 시 경고 모달이 뜨지만 제보는 성공 처리된다
- 중복 제보 시 409 메시지가 사용자 언어로 표시된다
- 제출 후 약국 상세의 대표가격이 즉시 갱신되어 보인다
- **제보 후 같은 약품으로 재검색하면 순위가 바뀐다** (데모 하이라이트)

---

## T-30. 내 제보 목록

**우선순위** P1 · **예상** 0.25d

**목적**
`/me` — 사용자가 자신의 제보 기여를 확인한다.

**구현 가이드**

1. `GET /api/v1/price-reports?mine=true`, 최신순.
2. 각 항목: 약국명, 약품명+포장단위, 가격, 구매일, 상태 뱃지.
3. 상태 표시: `ACTIVE` → "반영됨", `flagged` → "검토 중", `HIDDEN` → "숨김 처리됨".
4. 상단에 총 제보 수(`reportCount`).
5. 0건이면 빈 상태 + "첫 가격을 제보해보세요" CTA.

**선행 태스크** T-29

**관련 파일**
- `miniProject1_frontEnd/app/me/page.tsx` — `CREATE`

**완료 판정**
- 본인 제보만 보인다
- 상태 뱃지가 실제 `status`/`flagged` 와 일치
- 빈 상태 화면이 정상 표시

---

# FS-5. 관리자 (P2)

> **이 슬라이스 전체가 P2다.** FS-0~FS-4의 P0가 끝나지 않았다면 착수하지 말고 잘라낸다.

## T-31. 관리자 통계 API

**우선순위** P2 · **예상** 1d

**목적**
`/admin/stats/**` 4개 엔드포인트를 구현한다.

**구현 가이드**

1. `GET /admin/stats/overview` — 총계(약국·약품·제보·사용자·커버 조합), 최근 7일 제보 추이, `flaggedReportCount`, `coverageRate`.
2. `GET /admin/stats/regions` — [DATABASE.md](./DATABASE.md) §5.3 쿼리. 필터 `regionCode`, `drugId`, `sido`.
3. `GET /admin/stats/drugs/{drugId}` — 가격 히스토그램(500원 버킷) + 지역별 평균 + 전국 통계(avg/median/min/max/stdDev).
4. `GET /admin/stats/price-gaps` — [DATABASE.md](./DATABASE.md) §5.4 쿼리. **지역 간 가격 격차가 큰 약품 Top N.**
   서비스의 존재 이유를 가장 잘 보여주는 지표라 데모 첫 화면으로 쓴다.
5. 전부 `@PreAuthorize("hasRole('ADMIN')")`.
6. **표본이 3건 미만인 지역은 통계에서 제외한다** — 1건짜리 지역이 "최저가 지역"으로 뜨면 통계가 우스워진다.

**선행 태스크** T-24, T-10

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/admin/controller/AdminStatsController.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/admin/repository/AdminStatsRepository.java` — `CREATE`
- `DATABASE.md` — `REFERENCE` — §5.3, §5.4
- `API.md` — `REFERENCE` — §8

**완료 판정**
- 4개 엔드포인트가 [API.md](./API.md) §8 명세와 일치
- USER 토큰으로 호출 시 전부 `403`
- `price-gaps` 의 `gapPct` 가 수기 검산과 일치

---

## T-32. 제보 관리 API

**우선순위** P2 · **예상** 0.5d

**목적**
관리자가 이상치 제보를 확인하고 숨김/복구한다.

**구현 가이드**

1. `GET /admin/price-reports` — 필터 `flagged`, `status`, `pharmacyId`, `drugId`. 일반 목록과 달리 `reporter.id`, `reporter.email`, `flagReason`, `receiptFileId` 포함.
2. `PATCH /admin/price-reports/{reportId}` — `status`, `flagged`, `reason` 중 넘어온 필드만 변경.
3. 상태 변경 시 `PriceStatService.recalculate()` 를 **동기적으로** 호출하고 결과를 `recalculatedStat` 으로 응답에 넣는다. 관리자가 조치 결과를 바로 확인해야 한다.
   `REJECTED` 로 바꾸는 경우 제보자의 `report_count` 도 1 차감한다.

**선행 태스크** T-31

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/admin/controller/AdminReportController.java` — `CREATE`
- `API.md` — `REFERENCE` — §8 제보 관리

**완료 판정**
- 제보를 `HIDDEN` 으로 바꾸면 `rep_price` 가 즉시 재계산된다
- `flagged` 를 false로 풀면 해당 제보가 통계에 다시 포함된다
- `recalculatedStat` 이 실제 DB 값과 일치

---

## T-33. 관리자 대시보드 화면

**우선순위** P2 · **예상** 0.5d

**목적**
`/admin` — 요약 지표와 제보 추이.

**구현 가이드**

1. 상단 KPI 카드 5개: 약국 수, 약품 수, 제보 수, 커버리지(%), 이상치 제보 수.
2. 최근 7일 제보 추이 라인 차트 (Recharts).
3. `/admin/reports` — 이상치 제보 목록. 각 행에 숨김/복구 버튼, 영수증 썸네일.
4. **숨김 버튼에 `window.confirm` 을 쓰지 않는다** — 모달 컴포넌트로 확인받는다.
5. ADMIN이 아니면 404 또는 홈 리다이렉트. **관리자 메뉴의 존재 자체를 일반 사용자에게 노출하지 않는다.**

**선행 태스크** T-32, T-25

**관련 파일**
- `miniProject1_frontEnd/app/admin/page.tsx` — `CREATE`
- `miniProject1_frontEnd/app/admin/reports/page.tsx` — `CREATE`

**완료 판정**
- KPI 수치가 API 응답과 일치
- 제보 숨김 처리 후 목록과 KPI가 갱신된다
- USER 계정으로 `/admin` 접근 시 차단됨

---

## T-34. 관리자 통계 차트 화면

**우선순위** P2 · **예상** 0.5d

**목적**
`/admin/stats` — 지역별·약품별 가격 통계 시각화.

**구현 가이드**

1. 탭 3개: 지역별 통계 / 약품별 분포 / 가격 격차 Top 10.
2. 지역별: 시도·시군구·약품 필터 + 정렬 가능한 테이블.
3. 약품별: 약품 선택 → 가격 히스토그램 + 지역별 평균 막대 차트.
4. 가격 격차 Top 10: 가로 막대로 `gapPct`. **최저가 지역과 최고가 지역 이름을 함께 보여준다** — 숫자만으로는 의미가 전달되지 않는다.
5. 차트 색상은 시리즈당 1색, 강조색 1개만. 수치 라벨 병기.
6. 테이블은 `overflow-x: auto` 컨테이너에 넣어 모바일에서 가로 스크롤되게 한다. **페이지 자체는 가로 스크롤되면 안 된다.**

**선행 태스크** T-33

**관련 파일**
- `miniProject1_frontEnd/app/admin/stats/page.tsx` — `CREATE`
- `miniProject1_frontEnd/components/charts/` — `CREATE`

**완료 판정**
- 3개 탭이 모두 데이터를 렌더링
- 필터 변경 시 테이블·차트가 갱신됨
- 375px 폭에서 테이블만 가로 스크롤되고 페이지는 그대로다

---

# FS-6. 마감

## T-35. 전역 예외 처리 및 에러 응답 표준화

**우선순위** P0 · **예상** 0.5d

**목적**
모든 에러가 [API.md](./API.md) §1.2 포맷으로 나가게 한다. 프론트의 에러 처리가 여기에 의존한다.

**구현 가이드**

1. `@RestControllerAdvice` 로 전역 핸들러를 만든다.
2. 처리 대상:
   - `MethodArgumentNotValidException` → 400 + `fieldErrors`
   - `ConstraintViolationException` → 400
   - 커스텀 `BusinessException` → 각자의 상태·코드
   - `DataIntegrityViolationException` → 409
   - `MaxUploadSizeExceededException` → 413
   - 그 외 → 500 `INTERNAL_ERROR`
3. `traceId` 는 MDC에서 꺼내 **응답과 로그에 동일하게** 넣는다. 사용자가 traceId를 알려주면 로그에서 바로 찾을 수 있어야 한다.
4. 검증 메시지를 한글로 작성한다 — 프론트가 그대로 보여준다. `messages.properties` 로 분리.
5. **5xx 응답에 스택트레이스나 SQL이 노출되지 않게** 한다. 로그에만 남긴다.
6. [API.md](./API.md) §1.3의 에러 코드 표를 `ErrorCode` enum으로 구현해 코드와 문서가 어긋나지 않게 한다.

**선행 태스크** T-15, T-26

**관련 파일**
- `miniProject1_backEnd/src/main/java/com/pharmaprice/common/exception/GlobalExceptionHandler.java` — `CREATE`
- `miniProject1_backEnd/src/main/java/com/pharmaprice/common/exception/ErrorCode.java` — `CREATE`
- `miniProject1_backEnd/src/main/resources/messages.properties` — `CREATE`
- `API.md` — `REFERENCE` — §1.2, §1.3

**완료 판정**
- 문서의 모든 에러 코드가 `ErrorCode` enum에 존재
- 검증 실패 시 `fieldErrors` 가 채워진다
- 의도적으로 500을 발생시켜도 스택트레이스가 응답에 없다
- 응답의 `traceId` 로 로그를 검색하면 해당 요청이 나온다

---

## T-36. 프론트 상태 처리 및 반응형 점검

**우선순위** P1 · **예상** 0.5d

**목적**
모든 화면의 로딩·빈·에러 상태를 채우고 모바일에서 깨지지 않게 한다.

**구현 가이드**

1. 화면별 점검표를 만들어 3상태를 전부 확인한다: 로딩(스켈레톤) / 빈 상태 / 에러 상태 + 재시도 버튼.
2. `ApiError` 를 사용자 언어로 매핑하는 공통 함수를 만든다.
   **"Request failed with status 409" 같은 게 화면에 뜨면 안 된다.**
3. 375px / 768px / 1280px 세 폭에서 전 화면 확인. 가로 스크롤이 생기는 페이지가 없어야 한다 (테이블·차트는 자체 컨테이너 스크롤 허용).
4. 접근성 최소선: 폼 라벨-입력 연결, 에러 메시지 `aria-describedby`, 포커스 표시, 뱃지에 색상 외 텍스트 병기.
5. 느린 네트워크(DevTools Slow 3G)에서 스켈레톤이 실제로 보이는지 확인.

**선행 태스크** T-21, T-30

**관련 파일**
- `miniProject1_frontEnd/components/ui/empty-state.tsx` — `TO_MODIFY`
- `miniProject1_frontEnd/components/ui/error-state.tsx` — `TO_MODIFY`
- `miniProject1_frontEnd/lib/error-message.ts` — `CREATE` — 에러 코드 → 한글 메시지

**완료 판정**
- 전 화면에서 3상태가 모두 확인됨
- 375px에서 가로 스크롤이 발생하는 페이지 0개
- 영문 에러 원문이 노출되는 지점 0개
- 키보드만으로 검색 → 제보 흐름 완주 가능

---

## T-37. 통합 검증 및 실행 문서

**우선순위** P0 · **예상** 0.5d

**목적**
클린 환경에서 실행이 재현되는지 확인하고 데모 시나리오를 확정한다.

**구현 가이드**

1. **새 디렉터리에 클론**해서 `README.md` 절차만 따라 기동되는지 확인한다.
   기존 작업 디렉터리에서 테스트하면 이미 설치된 것들 때문에 항상 성공한다.
   ```bash
   git clone <repo> && cd miniProject1
   cp .env.example .env              # 값 채우기
   # PostgreSQL 준비 (T-02 절차)
   cd miniProject1_backEnd && ./mvnw spring-boot:run
   # 새 터미널
   cd miniProject1_frontEnd && npm install && npm run dev
   ```

2. DB를 완전히 비우고(`DROP DATABASE` → 재생성 → 타임존·확장 재설정) 재기동해 마이그레이션·시드가 처음부터 도는지 확인한다.

3. 핵심 흐름을 손으로 완주한다: 검색 → 결과 → 상세 → 로그인 → 제보 → 재검색(순위 변동 확인).

4. `README.md` 를 완성한다.
   - 프로젝트 소개 + **목데이터 고지**
   - 요구 사항: JDK 21, Node 22, PostgreSQL 17
   - **로컬 환경 준비** (T-02의 설치·DB·타임존 절차)
   - 실행 명령 (백엔드 / 프론트 각각, 터미널 2개)
   - 환경변수 표
   - 기본 계정 (`admin@example.com`)
   - 문서 링크 (PRD / DATABASE / API / ROADMAP)
   - 트러블슈팅: 포트 5432·8080·3000 충돌, `pg_trgm` 권한 오류, 카카오 키 도메인 미등록, Flyway 체크섬 불일치, JDK 버전 불일치, `ddl-auto: validate` 실패

5. 데모 시나리오를 `DEMO.md` 로 확정한다.
   1. 가격 격차 Top 10 화면으로 문제 제기
   2. 타이레놀 검색 → 반경 2km → 결과
   3. 1위 근거를 `scoreBreakdown` 으로 설명 (가격 60% + 거리 25% + 신선도 15%)
   4. "가격순"으로 전환 → 1위가 바뀜 → "가장 싼 곳이 3km 밖이면 추천이 아니다"
   5. 2위 약국에 더 싼 가격 제보 → 재검색 → 순위 변동
   6. 50,000원 오타 제보 → 대표가격이 안 흔들림
   7. 관리자에서 해당 제보 확인·숨김
   8. 한계(목데이터)와 다음 단계

6. 리허설 1회 이상. **위치 권한은 미리 허용해 둔다.**

**선행 태스크** T-35, T-36, T-02

**관련 파일**
- `README.md` — `TO_MODIFY` — 실행 가이드 완성
- `DEMO.md` — `CREATE` — 데모 시나리오
- `.env.example` — `REFERENCE`

**완료 판정**
- 클린 클론 + README 절차만으로 전체 기동
- DB를 비우고 재기동해도 마이그레이션·시드가 정상 적용
- 핵심 흐름 8단계 무중단 완주
- README만 보고 외부인이 실행할 수 있다

---

## 2. 우선순위 요약

| 우선순위 | 태스크 | 예상 합계 |
|---|---|---|
| **P0 (27)** | T-01 ~ T-19, T-21, T-23 ~ T-26, T-29, T-35, T-37 | 약 13d |
| **P1 (6)** | T-20, T-22, T-27, T-28, T-30, T-36 | 약 2.75d |
| **P2 (4)** | T-31 ~ T-34 | 약 2.5d |

**잘라내는 순서** (§1 "일정 현실성" 참고): FS-5 전체 → T-22 지도 → T-27 업로드 → T-30 내 제보 → T-20/T-21 이력 차트.

---

## 3. `split_tasks` 투입 예시 (FS-0)

이 형식으로 슬라이스 단위 변환해 투입한다.

```json
{
  "updateMode": "clearAllTasks",
  "globalAnalysisResult": "크라우드소싱 기반 약국별 일반의약품 최저가 추천 웹 서비스. 루트는 miniProject1/, 프론트는 miniProject1_frontEnd (Next.js 16 + React 19.3), 백엔드는 miniProject1_backEnd (Spring Boot 4.1 + Java 21 + Maven), DB는 로컬 PostgreSQL 17 (Docker 미사용). 1인이 전체를 구현한다. 상세 요구사항은 PRD.md, 스키마는 DATABASE.md, API 계약은 API.md 참조.",
  "tasks": [
    {
      "name": "T-01. 프로젝트 구조 및 개발 컨벤션 셋업",
      "description": "디렉터리 구조와 코드 컨벤션을 확정해 이후 모든 태스크가 같은 규칙 위에서 돌아가게 한다.",
      "implementationGuide": "1) miniProject1/ 루트에 md 문서 4종을 평평하게 두고 miniProject1_frontEnd/, miniProject1_backEnd/, tools/seed-generator/ 생성 2) 백엔드 패키지는 도메인 기준(common, auth, pharmacy, drug, report, recommendation, admin), 각 안에 controller/service/repository/domain/dto 3) 프론트는 app/, components/, hooks/, lib/, types/ 4) 커밋 컨벤션 feat(T-09): ... 5) .editorconfig (Java 4칸, TS 2칸, LF) 6) .gitignore에 .env*, miniProject1_backEnd/target/, .next/, node_modules/, uploads/ — Maven Wrapper(mvnw, .mvn/)는 반드시 커밋 7) .env.example에 POSTGRES_*, JWT_SECRET, TZ=Asia/Seoul, NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_KAKAO_MAP_KEY 나열",
      "dependencies": [],
      "relatedFiles": [
        { "path": "README.md", "type": "CREATE", "description": "프로젝트 개요" },
        { "path": ".gitignore", "type": "CREATE", "description": "무시 목록" },
        { "path": ".env.example", "type": "CREATE", "description": "환경변수 목록" },
        { "path": "PRD.md", "type": "REFERENCE", "description": "요구사항 원본" }
      ],
      "verificationCriteria": "위 디렉터리가 모두 존재한다. .env가 git에 추적되지 않고 .mvn/은 추적된다. .env.example만 보고 필요한 키를 전부 파악할 수 있다.",
      "notes": "실제 API 키 값은 절대 커밋하지 않는다."
    },
    {
      "name": "T-02. 로컬 PostgreSQL 17 설치 및 데이터베이스 준비",
      "description": "로컬에 PostgreSQL 17을 띄우고 애플리케이션이 붙을 데이터베이스, 계정, 타임존을 준비한다. Docker를 쓰지 않으므로 이 태스크가 DB 환경의 전부다.",
      "implementationGuide": "1) PostgreSQL 17 설치 (macOS: brew install postgresql@17 + brew services start / Windows: 공식 설치 프로그램, Locale은 C 또는 en_US.UTF-8) 2) CREATE USER pharmaprice WITH PASSWORD 'changeme'; CREATE DATABASE pharmaprice OWNER pharmaprice ENCODING 'UTF8'; GRANT ALL ON SCHEMA public TO pharmaprice; 3) ALTER DATABASE pharmaprice SET timezone TO 'Asia/Seoul' — UTC로 두면 오전 9시 이전에 CURRENT_DATE가 전날로 잡혀 중복 제보 방지와 180일 검증이 어긋남 4) 슈퍼유저로 CREATE EXTENSION IF NOT EXISTS pg_trgm (일반 유저는 권한이 없어 V1 마이그레이션이 실패할 수 있음) 5) psql로 접속 확인 6) 절차를 README.md의 '로컬 환경 준비' 절에 그대로 기록",
      "dependencies": ["T-01. 프로젝트 구조 및 개발 컨벤션 셋업"],
      "relatedFiles": [
        { "path": "README.md", "type": "TO_MODIFY", "description": "로컬 환경 준비 절 추가" },
        { "path": ".env.example", "type": "REFERENCE", "description": "DB 접속 정보" }
      ],
      "verificationCriteria": "psql로 pharmaprice DB에 pharmaprice 계정 접속 성공. SHOW timezone이 Asia/Seoul 반환. pg_extension에 pg_trgm 존재. README 절차만 따라 해도 같은 상태가 재현된다.",
      "notes": "포트 5432가 이미 쓰이면 lsof -i :5432로 확인하고 5433 사용 시 .env에도 반영한다."
    }
  ]
}
```

---

*태스크를 추가·분할했다면 이 문서를 먼저 고치고 `split_tasks` 를 `selective` 모드로 재투입한다. Score 수식이나 스키마가 바뀌면 [PRD.md](./PRD.md)·[DATABASE.md](./DATABASE.md)·[API.md](./API.md)를 함께 갱신할 것.*
