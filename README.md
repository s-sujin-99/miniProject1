# 약값알림

> **이 문서는 초안입니다.** 아직 클린 환경(새 디렉터리에 처음부터 클론)에서 전체 절차를 재현 검증하지 않았습니다. 인증·제보 CRUD 등 핵심 기능이 구현되고 나면(ROADMAP.md T-37) 데모 시나리오(DEMO.md)와 함께 완성본으로 갱신합니다.

약국별 일반의약품(OTC) 가격을 크라우드소싱으로 모아 사용자 위치 기준 최저가를 추천하는 미니 프로젝트입니다. 자세한 배경과 목표는 [PRD.md](./PRD.md)를 참고하세요.

> ⚠️ **본 서비스의 가격은 학습용 예시 데이터입니다.** 데이터는 대부분 목데이터(시드)이며 실제 판매가가 아닙니다.

## 요구 사항

- JDK 21
- Node 22
- PostgreSQL 17

## 저장소 구조

이 프로젝트는 **독립된 git 저장소 3개**로 구성됩니다(하나를 clone한다고 전체가 딸려오지 않습니다).

```
miniProject1/              ← 저장소 ① 문서 + .claude 설정 (이 저장소)
├─ PRD.md · API.md · DATABASE.md · ROADMAP.md · shrimp-rules.md
├─ miniproject1-frontend/   ← 저장소 ② Next.js 16
└─ miniproject1-backend/    ← 저장소 ③ Spring Boot 4.1.1
```

세 저장소를 각각 준비합니다(원격이 나뉘어 있다면 각자 clone, 지금처럼 한 디렉터리 아래 배치돼 있다면 그대로 사용).

## 로컬 환경 준비

1. PostgreSQL 17을 설치하고 실행합니다.
2. `pharmaprice` 계정과 `postgres` 데이터베이스 안에 `pharmaprice` 스키마를 준비합니다.
   ```sql
   CREATE USER pharmaprice WITH PASSWORD 'changeme';
   CREATE SCHEMA IF NOT EXISTS pharmaprice AUTHORIZATION pharmaprice;
   GRANT ALL ON SCHEMA pharmaprice TO pharmaprice;
   ```
3. 테스트용 스키마도 함께 준비합니다.
   ```sql
   CREATE SCHEMA IF NOT EXISTS pharmaprice_test AUTHORIZATION pharmaprice;
   ```
4. `pg_trgm` 확장을 슈퍼유저(`postgres` 계정)로 한 번 설치합니다(일반 계정은 권한이 없어 실패합니다).
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```
5. 타임존을 `Asia/Seoul`로 맞춥니다(UTC로 두면 한국 시간 기준 날짜 계산이 하루씩 어긋납니다).
   ```sql
   ALTER DATABASE postgres SET timezone TO 'Asia/Seoul';
   ```
6. 접속을 확인합니다.
   ```bash
   psql -h localhost -p 5432 -U pharmaprice -d postgres -c "SELECT version();"
   ```

## 실행 명령

두 개의 터미널이 필요합니다.

```bash
# 터미널 1 — backend (:8080)
cd miniproject1-backend
./mvnw spring-boot:run

# 터미널 2 — frontend (:3000)
cd miniproject1-frontend
npm install
npm run dev
```

## 환경변수

각 저장소의 `.env.example`을 `.env`로 복사해 값을 채웁니다.

```bash
cp miniproject1-backend/.env.example miniproject1-backend/.env
cp miniproject1-frontend/.env.example miniproject1-frontend/.env
```

**backend**

| 키 | 설명 |
|---|---|
| `DB_URL` | `jdbc:postgresql://localhost:5432/postgres?currentSchema=pharmaprice` |
| `DB_USERNAME` / `DB_PASSWORD` | DB 접속 계정 |
| `JWT_SECRET` | 32바이트 이상 랜덤 문자열 |
| `JWT_EXPIRATION_MS` | 토큰 만료 시간(ms), 기본 24시간 |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth2 (아직 미구현) |
| `FRONTEND_URL` | CORS·OAuth 리다이렉트용 |
| `UPLOAD_DIR` | 영수증 이미지 등 로컬 업로드 경로 |

**frontend**

| 키 | 설명 |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | 백엔드 API 주소 |
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | 카카오 지도 JavaScript 키 |

## 문서

- [PRD.md](./PRD.md) — 요구사항
- [API.md](./API.md) — API 명세
- [DATABASE.md](./DATABASE.md) — DB 스키마
- [ROADMAP.md](./ROADMAP.md) — 개발 로드맵
- [shrimp-rules.md](./shrimp-rules.md) — AI 에이전트용 개발 규칙 (위 문서들과 충돌 시 이 문서가 우선)

## 트러블슈팅

- **포트 충돌**: 5432(PostgreSQL) · 8080(backend) · 3000(frontend) 중 하나가 이미 쓰이고 있다면 해당 프로세스를 종료하거나 포트를 바꿉니다.
- **`pg_trgm` 확장 설치 권한 오류**: 일반 계정(`pharmaprice`)으로 `CREATE EXTENSION`을 실행하면 "만들 권한이 없습니다" 에러가 납니다. `postgres` 슈퍼유저 계정으로 실행해야 합니다.
- **JDK 버전 불일치**: `./mvnw compile` 시 Maven이 `[21,22)` 범위를 벗어난 JDK를 감지하면 빌드 시작 단계(`validate`)에서 바로 실패 메시지를 냅니다. `java -version`으로 21인지 확인하세요.

## TODO

다음 항목은 아직 구현되지 않아 이 README에 채우지 않았습니다. 관련 기능이 완성되면(ROADMAP.md T-35~T-37) 추가합니다.

- 기본 계정 정보(회원가입/로그인 기능 구현 후)
- 데모 시나리오(`DEMO.md`)
- 클린 클론 환경에서의 전체 재현 검증
