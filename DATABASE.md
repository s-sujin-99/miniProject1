# DATABASE — 데이터베이스 스키마 설계

| 항목 | 내용 |
|---|---|
| 문서 버전 | v1.3 (1인 구현 · Docker 제거) |
| DBMS | PostgreSQL 17 |
| 마이그레이션 | Flyway (`V1__init.sql`, `V2__seed_master.sql`, `V3__seed_prices.sql`) |
| 관련 문서 | [PRD.md](./PRD.md) · [API.md](./API.md) · [ROADMAP.md](./ROADMAP.md) |

---

## 1. 설계 원칙

1. **모든 PK는 `BIGSERIAL`** — UUID는 이번 규모에서 인덱스 비용만 늘린다.
2. **삭제는 소프트 삭제** — 제보는 물리 삭제하지 않고 `status` 로 관리한다. 통계 재현성이 필요하기 때문이다.
3. **집계는 캐시 테이블에 둔다** — 검색 경로에서 수천 건의 제보를 매번 집계하지 않는다.
4. **공간 확장 없이 시작** — `lat`/`lng` 는 `DOUBLE PRECISION`. 바운딩 박스 선필터 + Haversine으로 계산한다.
5. **시각은 모두 `TIMESTAMPTZ`, 서버·DB 타임존은 `Asia/Seoul`** — 아래 §8 참고. `CURRENT_DATE` 가 사용자가 체감하는 "오늘"과 일치해야 중복 제보 방지와 날짜 검증이 어긋나지 않는다.
6. **금액은 `INTEGER` (원 단위)** — KRW는 소수점이 없으므로 `NUMERIC` 불필요.

---

## 2. ERD

```
┌──────────────┐          ┌─────────────────────┐      ┌──────────────────┐
│    region    │          │       app_user      │      │  refresh_token   │
│──────────────│          │─────────────────────│      │──────────────────│
│ code     PK  │          │ id              PK  │ 1  N │ id           PK  │
│ sido         │          │ email        UNIQUE ├──────┤ user_id      FK  │
│ sigungu      │          │ password_hash       │      │ token_hash UNIQUE│
│ center_lat   │          │ nickname            │      │ expires_at       │
│ center_lng   │          │ role                │      │ revoked_at       │
└──────┬───────┘          │ status              │      └──────────────────┘
       │                  │ report_count        │
       │                  └──────────┬──────────┘
       │ 1                           │ 1
       │                             │
       │ N                           │ N
┌──────┴───────────────┐      ┌──────┴──────────────────────┐
│      pharmacy        │      │       price_report          │
│──────────────────────│      │─────────────────────────────│
│ id               PK  │ 1  N │ id                      PK  │
│ hira_code     UNIQUE ├──────┤ pharmacy_id             FK  │
│ name                 │      │ drug_id                 FK  │
│ address_road         │      │ user_id                 FK  │
│ address_jibun        │      │ price                       │
│ region_code      FK  │      │ purchased_at                │
│ lat                  │      │ source                      │
│ lng                  │      │ status                      │
│ phone                │      │ flagged                     │
│ business_hours JSONB │      │ receipt_file_id         FK  │
│ is_active            │      │ created_at                  │
└──────┬───────────────┘      └──────┬──────────────────────┘
       │                             │ N
       │ 1                           │
       │                             │ 1
       │      ┌──────────────────────┴──────┐
       │      │           drug              │
       │    N │─────────────────────────────│
       │      │ id                      PK  │
       │      │ item_seq             UNIQUE │
       │      │ name                        │
       │      │ maker                       │
       │      │ category                    │
       │      │ form                        │
       │      │ package_unit                │
       │      │ otc_flag                    │
       │      │ base_price                  │
       │      │ image_url                   │
       │      └──────────┬──────────────────┘
       │                 │ 1
       │ 1               │
       │                 │ N
┌──────┴─────────────────┴─────────────┐   ┌──────────────────┐
│     pharmacy_drug_price_stat         │   │  uploaded_file   │
│──────────────────────────────────────│   │──────────────────│
│ id                              PK   │   │ id           PK  │
│ pharmacy_id  FK ┐                    │   │ original_name    │
│ drug_id      FK ┘ UNIQUE(pair)       │   │ stored_path      │
│ rep_price                            │   │ content_type     │
│ min_price / max_price / avg_price    │   │ size_bytes       │
│ report_count                         │   │ uploaded_by  FK  │
│ last_reported_at                     │   │ created_at       │
│ calculated_at                        │   └──────────────────┘
└──────────────────────────────────────┘
```

---

## 3. 테이블 정의

### 3.1 `region` — 행정구역

시·군·구 단위. 위치 권한이 거부됐을 때 폴백 좌표로 사용한다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `code` | `VARCHAR(10)` | PK | 행정표준코드 (예: `11680` 강남구) |
| `sido` | `VARCHAR(20)` | NOT NULL | 시도명 (예: `서울특별시`) |
| `sigungu` | `VARCHAR(30)` | NOT NULL | 시군구명 (예: `강남구`) |
| `center_lat` | `DOUBLE PRECISION` | NOT NULL | 구역 중심 위도 |
| `center_lng` | `DOUBLE PRECISION` | NOT NULL | 구역 중심 경도 |

---

### 3.2 `app_user` — 사용자

`user` 는 PostgreSQL 예약어라 `app_user` 를 쓴다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `email` | `VARCHAR(255)` | UNIQUE, NOT NULL | 로그인 ID |
| `password_hash` | `VARCHAR(100)` | NOT NULL | BCrypt (strength 10) |
| `nickname` | `VARCHAR(30)` | NOT NULL | 제보자 표시명 |
| `role` | `VARCHAR(20)` | NOT NULL, DEFAULT `'USER'` | `USER` \| `ADMIN` |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT `'ACTIVE'` | `ACTIVE` \| `SUSPENDED` |
| `report_count` | `INTEGER` | NOT NULL, DEFAULT 0 | 누적 제보 수 (비정규화). **제보 생성 트랜잭션에서 `+1`, 관리자가 `REJECTED` 처리 시 `-1`.** `GET /auth/me` 응답에 쓰인다 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |

**인덱스**: `email` (UNIQUE 제약으로 자동 생성)

> 향후 확장: `trust_score NUMERIC(3,2)` 를 추가하면 대표가격을 신뢰도 가중 평균으로 전환할 수 있다.

---

### 3.2-1 `refresh_token` — 리프레시 토큰

로그아웃 시 서버에서 토큰을 무효화하기 위해 발급분을 보관한다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `user_id` | `BIGINT` | FK → `app_user.id`, NOT NULL | |
| `token_hash` | `VARCHAR(64)` | UNIQUE, NOT NULL | 토큰 원문의 SHA-256. **원문은 저장하지 않는다** |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | 발급 + 14일 |
| `revoked_at` | `TIMESTAMPTZ` | | 로그아웃 시각. NULL이면 유효 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |

**인덱스**

```sql
CREATE INDEX idx_refresh_token_user ON refresh_token (user_id) WHERE revoked_at IS NULL;
```

**동작**

- 로그인 → 행 생성
- `/auth/refresh` → `revoked_at IS NULL AND expires_at > now()` 검증 후 **기존 행을 revoke하고 새 행 발급** (rotation)
- `/auth/logout` → 해당 행 `revoked_at = now()`
- 만료 행 정리는 이번 범위 밖 (`expires_at < now()` 배치 삭제는 향후 확장)

> 토큰 회전(rotation)까지 하는 이유: 탈취된 refresh 토큰이 14일 내내 유효하면 로그아웃이 무의미해진다. 회전은 구현 비용이 거의 없다.

---

### 3.3 `pharmacy` — 약국

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `hira_code` | `VARCHAR(30)` | UNIQUE | 심평원 요양기관기호. 공공데이터 재적재 시 멱등성 키 |
| `name` | `VARCHAR(100)` | NOT NULL | 약국명 |
| `address_road` | `VARCHAR(255)` | | 도로명 주소 |
| `address_jibun` | `VARCHAR(255)` | | 지번 주소 |
| `region_code` | `VARCHAR(10)` | FK → `region.code` | |
| `lat` | `DOUBLE PRECISION` | NOT NULL | 위도 (WGS84) |
| `lng` | `DOUBLE PRECISION` | NOT NULL | 경도 (WGS84) |
| `phone` | `VARCHAR(20)` | | |
| `business_hours` | `JSONB` | | `{"mon":["09:00","19:00"], ..., "holiday":null}` |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT `true` | 폐업 시 false |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |

**인덱스**

```sql
CREATE INDEX idx_pharmacy_lat_lng   ON pharmacy (lat, lng);      -- 바운딩 박스 선필터
CREATE INDEX idx_pharmacy_region    ON pharmacy (region_code);
CREATE INDEX idx_pharmacy_name_trgm ON pharmacy USING gin (name gin_trgm_ops);  -- 이름 부분검색
```

> `pg_trgm` 확장 필요: `CREATE EXTENSION IF NOT EXISTS pg_trgm;` (PostgreSQL 기본 contrib, 별도 설치 불필요)

---

### 3.4 `drug` — 일반의약품 마스터

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `item_seq` | `VARCHAR(20)` | UNIQUE | 식약처 품목기준코드 |
| `name` | `VARCHAR(200)` | NOT NULL | 품목명 (예: `타이레놀정500밀리그람`) |
| `display_name` | `VARCHAR(100)` | NOT NULL | 검색·표시용 짧은 이름 (예: `타이레놀 500mg`) |
| `maker` | `VARCHAR(100)` | | 제조/수입사 |
| `category` | `VARCHAR(50)` | NOT NULL | `해열진통` \| `소화제` \| `감기약` \| `연고` \| `소독약` \| `비타민` \| `기타` |
| `form` | `VARCHAR(50)` | | 제형 (정제, 캡슐, 시럽, 연고 등) |
| `package_unit` | `VARCHAR(50)` | NOT NULL | 판매 단위 (예: `8정`, `10ml`). **가격 비교의 전제라 필수** |
| `otc_flag` | `BOOLEAN` | NOT NULL, DEFAULT `true` | 일반의약품 여부. `false` 는 적재하지 않음 |
| `base_price` | `INTEGER` | | 시드 생성용 기준가. 운영 시 미사용 |
| `image_url` | `VARCHAR(500)` | | 낱알 이미지 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |

**인덱스**

```sql
CREATE INDEX idx_drug_display_name_trgm ON drug USING gin (display_name gin_trgm_ops);
CREATE INDEX idx_drug_category          ON drug (category);
CREATE INDEX idx_drug_otc               ON drug (otc_flag) WHERE otc_flag = true;
```

> **`package_unit` 이 중요한 이유**: 타이레놀 8정과 16정을 같은 약품으로 묶으면 가격 비교가 무의미해진다. 포장 단위가 다르면 **별개의 `drug` 행**으로 취급한다.

---

### 3.5 `price_report` — 가격 제보 (핵심 테이블)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `pharmacy_id` | `BIGINT` | FK → `pharmacy.id`, NOT NULL | |
| `drug_id` | `BIGINT` | FK → `drug.id`, NOT NULL | |
| `user_id` | `BIGINT` | FK → `app_user.id` | 시드 데이터는 NULL 허용 |
| `price` | `INTEGER` | NOT NULL, CHECK (`price BETWEEN 100 AND 200000`) | 원 단위 |
| `purchased_at` | `DATE` | NOT NULL | 구매일. 미입력 시 제출일 |
| `source` | `VARCHAR(20)` | NOT NULL, DEFAULT `'FORM'` | `FORM` \| `SEED` \| `RECEIPT_OCR`(예약) \| `PARTNER`(예약) |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT `'ACTIVE'` | `ACTIVE` \| `HIDDEN` \| `REJECTED` |
| `flagged` | `BOOLEAN` | NOT NULL, DEFAULT `false` | 이상치 자동 탐지 결과 |
| `flag_reason` | `VARCHAR(100)` | | `OUTLIER_HIGH` \| `OUTLIER_LOW` \| `DUPLICATE` \| `MANUAL` |
| `receipt_file_id` | `BIGINT` | FK → `uploaded_file.id` | 영수증 (선택) |
| `memo` | `VARCHAR(200)` | | 사용자 자유 입력 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |

**인덱스**

```sql
-- 통계 재계산 시 가장 많이 타는 경로
CREATE INDEX idx_report_pair_active
  ON price_report (pharmacy_id, drug_id, purchased_at DESC)
  WHERE status = 'ACTIVE' AND flagged = false;

CREATE INDEX idx_report_drug      ON price_report (drug_id, purchased_at DESC);
CREATE INDEX idx_report_user      ON price_report (user_id, created_at DESC);
CREATE INDEX idx_report_flagged   ON price_report (flagged) WHERE flagged = true;
```

**중복 제보 방지 (F2-8)**

```sql
-- 같은 사용자가 같은 (약국, 약품)에 같은 날 중복 제보 차단
CREATE UNIQUE INDEX uq_report_user_pair_day
  ON price_report (
    user_id, pharmacy_id, drug_id,
    ((created_at AT TIME ZONE 'Asia/Seoul')::date)
  )
  WHERE user_id IS NOT NULL AND status = 'ACTIVE';
```

> ⚠️ **`(created_at::date)` 로 쓰면 인덱스 생성 자체가 실패한다.** `timestamptz → date` 캐스트는 세션 `TimeZone` 설정에 의존하므로 `STABLE` 이지 `IMMUTABLE` 이 아니고, PostgreSQL은 인덱스 표현식에 `IMMUTABLE` 함수만 허용한다. `AT TIME ZONE 'Asia/Seoul'` 로 타임존을 고정하면 `timestamp` 가 되어 `IMMUTABLE` 캐스트가 된다.

> 엄밀히 "24시간"이 아니라 "같은 날짜(KST)"로 구현한다. 부분 유니크 인덱스로 DB 레벨에서 막는 편이 애플리케이션 락보다 단순하고 확실하다.

---

### 3.6 `pharmacy_drug_price_stat` — 가격 통계 캐시

검색 경로에서 읽는 유일한 집계 테이블. `price_report` 가 변경될 때마다 해당 행만 재계산한다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `pharmacy_id` | `BIGINT` | FK, NOT NULL | |
| `drug_id` | `BIGINT` | FK, NOT NULL | |
| `rep_price` | `INTEGER` | NOT NULL | **대표가격 = 유효 제보의 중앙값** |
| `min_price` | `INTEGER` | NOT NULL | 유효 제보 최저가 |
| `max_price` | `INTEGER` | NOT NULL | 유효 제보 최고가 |
| `avg_price` | `INTEGER` | NOT NULL | 유효 제보 평균 (표시용) |
| `report_count` | `INTEGER` | NOT NULL | 유효 제보 수 |
| `last_reported_at` | `DATE` | NOT NULL | 가장 최근 유효 제보의 `purchased_at`. 신선도 계산 입력 |
| `window_days` | `SMALLINT` | NOT NULL | 계산에 사용한 창 크기 (90 또는 180) |
| `calculated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |

**제약 / 인덱스**

```sql
ALTER TABLE pharmacy_drug_price_stat
  ADD CONSTRAINT uq_stat_pair UNIQUE (pharmacy_id, drug_id);

-- 검색 핵심 경로: 특정 약품의 통계 전체를 훑고 약국과 조인
CREATE INDEX idx_stat_drug_price ON pharmacy_drug_price_stat (drug_id, rep_price);
CREATE INDEX idx_stat_pharmacy   ON pharmacy_drug_price_stat (pharmacy_id);
```

**재계산 트리거 시점**
- `price_report` INSERT 성공 직후
- 관리자가 제보를 `HIDDEN`/`ACTIVE` 로 전환할 때
- (선택) 일 1회 배치로 전체 재계산 — 신선도 창이 지나 유효 제보가 0이 된 행을 정리

유효 제보가 0건이 되면 해당 stat 행을 **삭제**한다. 검색 결과에서 자동으로 빠진다.

---

### 3.7 `uploaded_file` — 업로드 파일

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `original_name` | `VARCHAR(255)` | NOT NULL | |
| `stored_path` | `VARCHAR(500)` | NOT NULL | `/app/uploads/2026/09/{uuid}.jpg` |
| `content_type` | `VARCHAR(100)` | NOT NULL | `image/jpeg` 등 |
| `size_bytes` | `BIGINT` | NOT NULL | 5MB 이하 |
| `uploaded_by` | `BIGINT` | FK → `app_user.id` | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | |

> S3 전환 시 `stored_path` 를 객체 키로 쓰고 `storage_type` 컬럼만 추가하면 된다.

---

## 4. 거리 계산

PostGIS 없이 두 단계로 처리한다.

### 4.1 바운딩 박스 선필터

```
lat_delta = R / 111_320                                  (m → 위도 도)
lng_delta = R / (111_320 × cos(radians(lat_u)))          (m → 경도 도)

WHERE p.lat BETWEEN :lat_u - :lat_delta AND :lat_u + :lat_delta
  AND p.lng BETWEEN :lng_u - :lng_delta AND :lng_u + :lng_delta
```

`idx_pharmacy_lat_lng` 로 인덱스를 탄다.

### 4.2 Haversine 정확 거리

```sql
6371000 * 2 * asin(sqrt(
    power(sin(radians(p.lat - :lat_u) / 2), 2)
  + cos(radians(:lat_u)) * cos(radians(p.lat))
  * power(sin(radians(p.lng - :lng_u) / 2), 2)
)) AS distance_m
```

바운딩 박스는 정사각형이므로 모서리에 반경 밖 약국이 섞인다. `HAVING distance_m <= :radius` 로 잘라낸다.

> 애플리케이션에서는 `DistanceCalculator` 인터페이스 뒤에 두어, 나중에 PostGIS `ST_DWithin` 구현체로 교체 가능하게 한다.

---

## 5. 핵심 쿼리

### 5.1 최저가 추천 검색 (F3)

```sql
WITH nearby AS (
  SELECT
    p.id, p.name, p.address_road, p.lat, p.lng, p.phone,
    s.rep_price, s.min_price, s.avg_price, s.report_count, s.last_reported_at,
    6371000 * 2 * asin(sqrt(
        power(sin(radians(p.lat - :latU) / 2), 2)
      + cos(radians(:latU)) * cos(radians(p.lat))
      * power(sin(radians(p.lng - :lngU) / 2), 2)
    )) AS distance_m
  FROM pharmacy_drug_price_stat s
  JOIN pharmacy p ON p.id = s.pharmacy_id
  WHERE s.drug_id = :drugId
    AND p.is_active = true
    AND p.lat BETWEEN :latMin AND :latMax
    AND p.lng BETWEEN :lngMin AND :lngMax
),
filtered AS (
  SELECT * FROM nearby WHERE distance_m <= :radius
),
bounds AS (
  SELECT MIN(rep_price) AS p_min, MAX(rep_price) AS p_max FROM filtered
)
SELECT
  f.*,
  CASE WHEN b.p_max = b.p_min THEN 1.0
       ELSE (b.p_max - f.rep_price)::numeric / (b.p_max - b.p_min)
  END AS price_score,
  GREATEST(0, LEAST(1, 1 - f.distance_m / :radius)) AS distance_score,
  power(0.5, (CURRENT_DATE - f.last_reported_at)::numeric / 30) AS freshness_score
FROM filtered f CROSS JOIN bounds b
ORDER BY
  (:wPrice * (CASE WHEN b.p_max = b.p_min THEN 1.0
                   ELSE (b.p_max - f.rep_price)::numeric / (b.p_max - b.p_min) END)
 + :wDist  * GREATEST(0, LEAST(1, 1 - f.distance_m / :radius))
 + :wFresh * power(0.5, (CURRENT_DATE - f.last_reported_at)::numeric / 30)) DESC,
  f.rep_price ASC,
  f.distance_m ASC
LIMIT :limit;
```

> 가중치(`:wPrice` = 0.60, `:wDist` = 0.25, `:wFresh` = 0.15)는 `application.yml` 의 `recommendation.weights.*` 에서 바인딩한다.
> **대안**: 후보 수가 수백 건 수준이면 SQL로는 거리·통계만 가져오고 Score 계산·정렬은 Java 서비스 레이어에서 하는 편이 테스트하기 훨씬 쉽다. 단위 테스트 작성이 목표라면 이쪽을 권장한다.

### 5.2 대표가격 재계산 (IQR 이상치 제거 포함)

```sql
WITH valid AS (
  SELECT price
  FROM price_report
  WHERE pharmacy_id = :pharmacyId
    AND drug_id = :drugId
    AND status = 'ACTIVE'
    AND flagged = false
    AND purchased_at >= CURRENT_DATE - :windowDays
),
q AS (
  SELECT
    percentile_cont(0.25) WITHIN GROUP (ORDER BY price) AS q1,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY price) AS q3,
    count(*) AS n
  FROM valid
),
trimmed AS (
  SELECT v.price
  FROM valid v CROSS JOIN q
  WHERE q.n < 4                                        -- 4건 미만이면 이상치 제거 생략
     OR v.price BETWEEN q.q1 - 1.5 * (q.q3 - q.q1)
                    AND q.q3 + 1.5 * (q.q3 - q.q1)
)
SELECT
  percentile_cont(0.5) WITHIN GROUP (ORDER BY price)::int AS rep_price,
  MIN(price)::int  AS min_price,
  MAX(price)::int  AS max_price,
  AVG(price)::int  AS avg_price,
  COUNT(*)::int    AS report_count
FROM trimmed;
```

`last_reported_at` 은 같은 조건의 `MAX(purchased_at)` 으로 별도 조회한다.

### 5.3 관리자 — 지역별 가격 통계 (F4-3)

```sql
SELECT
  r.sido, r.sigungu, d.display_name,
  ROUND(AVG(s.rep_price))::int AS avg_price,
  MIN(s.rep_price)             AS min_price,
  MAX(s.rep_price)             AS max_price,
  COUNT(DISTINCT s.pharmacy_id) AS pharmacy_count,
  SUM(s.report_count)          AS report_count
FROM pharmacy_drug_price_stat s
JOIN pharmacy p ON p.id = s.pharmacy_id
JOIN region   r ON r.code = p.region_code
JOIN drug     d ON d.id = s.drug_id
WHERE (:regionCode IS NULL OR p.region_code = :regionCode)
  AND (:drugId     IS NULL OR s.drug_id = :drugId)
GROUP BY r.sido, r.sigungu, d.display_name
ORDER BY r.sido, r.sigungu, d.display_name;
```

### 5.4 관리자 — 지역 간 가격 격차 큰 약품 Top 10 (권장 지표)

```sql
WITH by_region AS (
  SELECT s.drug_id, p.region_code, AVG(s.rep_price) AS region_avg
  FROM pharmacy_drug_price_stat s
  JOIN pharmacy p ON p.id = s.pharmacy_id
  GROUP BY s.drug_id, p.region_code
  HAVING COUNT(*) >= 3                 -- 표본이 너무 적은 지역은 제외
)
SELECT
  d.display_name,
  ROUND(MIN(b.region_avg))::int AS cheapest_region_avg,
  ROUND(MAX(b.region_avg))::int AS priciest_region_avg,
  ROUND(MAX(b.region_avg) - MIN(b.region_avg))::int AS gap,
  ROUND((MAX(b.region_avg) - MIN(b.region_avg)) / MIN(b.region_avg) * 100, 1) AS gap_pct
FROM by_region b
JOIN drug d ON d.id = b.drug_id
GROUP BY d.display_name
HAVING COUNT(*) >= 3
ORDER BY gap_pct DESC
LIMIT 10;
```

---

## 6. 시드 데이터 전략

| 단계 | 파일 | 내용 |
|---|---|---|
| 1 | `V1__init.sql` | 확장(`pg_trgm`) + 전체 DDL + 인덱스 |
| 2 | `V2__seed_master.sql` | `region` (시군구 ~250건), `pharmacy` (≥300건), `drug` (≥30종), `app_user` (관리자 1 + 더미 제보자 20) |
| 3 | `V3__seed_prices.sql` | `price_report` ≥3,000건 + `pharmacy_drug_price_stat` 초기 계산 |

### 6.1 마스터 데이터 준비 절차 (개발 초기 1회)

1. 공공데이터포털에서 **국립중앙의료원_전국 약국 정보 조회 서비스** 또는 **심평원_전국 병의원 및 약국 현황** CSV 다운로드
2. 대상 지역(기본: 서울·경기 일부)으로 필터, 좌표가 비어 있는 행 제거
3. 300~500건 샘플링 → `pharmacy` INSERT 문으로 변환
4. 식약처 **의약품개요정보(e약은요)** 에서 일반의약품 30~50종 추출 → `drug` INSERT 문으로 변환, `base_price` 는 시중 가격을 참고해 수기 입력
5. 변환 스크립트는 `tools/seed-generator/` 에 Python 또는 Node 스크립트로 보관 (재현 가능하게)

### 6.2 가격 제보 생성 규칙

```
각 약국 p 에 price_factor(p) = uniform(0.85, 1.25)   # 약국 고유 가격대
각 (약국, 약품) 조합 중 60% 만 데이터 보유           # 커버리지 현실감
  제보 수 n = randint(1, 6)
  각 제보:
    price       = round(drug.base_price × price_factor(p) × normal(1, 0.05), -1)
    purchased_at= today - randint(0, 120)
    source      = 'SEED'
    user_id     = NULL 또는 더미 제보자 중 랜덤
전체의 2% 는 price 를 base_price × choice(0.3, 3.0) 로 덮어씀   # 오타 시뮬레이션
```

이렇게 하면 IQR 필터와 `flagged` 처리 동작을 데모로 보여줄 수 있다.

> 시드는 `source = 'SEED'` 로 표시되므로, 나중에 실제 제보와 구분해 통째로 걷어낼 수 있다.

---

## 7. JPA 매핑 시 주의점

| 항목 | 지침 |
|---|---|
| `business_hours` (JSONB) | Hibernate 6의 `@JdbcTypeCode(SqlTypes.JSON)` 사용. 별도 컨버터 불필요 |
| 연관관계 | 모두 `FetchType.LAZY`. 검색 쿼리는 엔티티 대신 **projection DTO** 로 받는다 |
| 검색 쿼리 | JPQL로는 Haversine을 표현하기 어렵다. **native query + DTO 매핑** 사용 |
| `price_report` 의 `status` | `@Enumerated(EnumType.STRING)`. ORDINAL은 절대 쓰지 않는다 |
| N+1 | 검색 결과 조립 시 `pharmacy` + `stat` 을 한 번에 조인해 가져온다 |
| 감사 컬럼 | `@EnableJpaAuditing` + `@CreatedDate` / `@LastModifiedDate` |
| 트랜잭션 | 제보 저장 + 통계 재계산은 하나의 `@Transactional` 안에서 처리 |

---

## 8. 타임존

서버·DB 타임존을 모두 **`Asia/Seoul`** 로 통일한다.

| 지점 | 설정 |
|---|---|
| PostgreSQL (로컬 설치) | `ALTER DATABASE pharmaprice SET timezone TO 'Asia/Seoul';` |
| `postgresql.conf` | `timezone = 'Asia/Seoul'` (DB 단위 설정으로 충분하지만 서버 전체에 걸려면 여기도) |
| 백엔드 프로세스 | 환경변수 `TZ=Asia/Seoul` |
| JVM | `-Duser.timezone=Asia/Seoul` |
| Hibernate | `spring.jpa.properties.hibernate.jdbc.time_zone: Asia/Seoul` |

**왜 UTC가 아닌가**

`purchased_at` 은 `DATE` 이고, 중복 제보 방지 인덱스와 "180일 초과 과거" 검증이 `CURRENT_DATE` 를 기준으로 동작한다. 서버가 UTC면 한국 시간 오전 9시 이전에는 `CURRENT_DATE` 가 **전날**로 잡혀서,

- 사용자가 아침 8시에 제보하면 어제 날짜로 기록되고
- 같은 날 두 번째 제보가 중복으로 막히지 않는다 (날짜 경계가 달라서)

미니 프로젝트는 국내 단일 타임존이므로 전체를 KST로 두는 편이 단순하고 안전하다.

> 다국가 확장 시에는 저장을 UTC로 되돌리고 날짜 연산만 사용자 타임존으로 변환하는 구조로 바꾼다. 그때 바뀌는 지점은 위 표의 5곳과 `uq_report_user_pair_day` 인덱스 하나뿐이다.

---

## 9. 마이그레이션 실행

```yaml
# application.yml
spring:
  jpa:
    hibernate:
      ddl-auto: validate      # 절대 update/create 쓰지 않는다
    properties:
      hibernate:
        jdbc:
          time_zone: Asia/Seoul
  flyway:
    enabled: true
    baseline-on-migrate: true
    locations: classpath:db/migration
```

`ddl-auto: validate` 로 두어 Flyway 스키마와 엔티티 불일치를 기동 시점에 잡는다.

---

*테이블·컬럼명은 [API.md](./API.md) 의 응답 필드와 1:1로 대응한다. 스키마를 바꾸면 API 문서도 함께 갱신할 것.*
