# API — REST 엔드포인트 명세

| 항목 | 내용 |
|---|---|
| 문서 버전 | v1.3 (1인 구현 · Docker 제거) |
| Base URL | `http://localhost:8080` |
| API Prefix | `/api/v1` |
| 인증 | Bearer JWT (`Authorization: Bearer {accessToken}`) |
| 직렬화 | `application/json; charset=UTF-8`, 필드는 `camelCase` |
| 시각 포맷 | `TIMESTAMPTZ` → ISO-8601 KST 오프셋 (`2026-09-15T13:12:33+09:00`), `DATE` → `2026-09-15` |
| 타임존 | 서버·DB 모두 `Asia/Seoul`. 모든 날짜 연산("오늘", "N일 전")은 KST 기준 ([DATABASE.md](./DATABASE.md) §8) |
| 관련 문서 | [PRD.md](./PRD.md) · [DATABASE.md](./DATABASE.md) · [ROADMAP.md](./ROADMAP.md) |

---

## 1. 공통 규약

### 1.1 응답 포맷

성공 응답은 **데이터 객체를 그대로** 반환한다. (래핑하지 않는다)

목록 응답은 페이지네이션 래퍼를 쓴다.

```json
{
  "content": [ ... ],
  "page": 0,
  "size": 20,
  "totalElements": 137,
  "totalPages": 7,
  "hasNext": true
}
```

### 1.2 에러 포맷

```json
{
  "code": "VALIDATION_FAILED",
  "message": "가격은 100원 이상 200,000원 이하여야 합니다.",
  "fieldErrors": [
    { "field": "price", "reason": "must be between 100 and 200000" }
  ],
  "traceId": "9f3a1c2e",
  "timestamp": "2026-09-15T13:12:33+09:00"
}
```

`fieldErrors` 는 검증 실패일 때만 존재한다.

### 1.3 에러 코드

| HTTP | `code` | 상황 |
|---|---|---|
| 400 | `VALIDATION_FAILED` | Bean Validation 실패 |
| 400 | `INVALID_COORDINATE` | 위경도가 대한민국 범위(위도 33~39, 경도 124~132) 밖 |
| 400 | `INVALID_DATE_RANGE` | 구매일이 미래이거나 180일 초과 과거 (KST 기준) |
| 400 | `INVALID_RADIUS` | `radius` 가 허용값(500/1000/2000/5000) 밖 |
| 401 | `UNAUTHENTICATED` | 토큰 없음 / 만료 / 서명 불일치 |
| 403 | `FORBIDDEN` | 권한 부족 (ADMIN 전용 접근 등) |
| 404 | `PHARMACY_NOT_FOUND` / `DRUG_NOT_FOUND` / `REPORT_NOT_FOUND` | 리소스 없음 |
| 409 | `EMAIL_ALREADY_EXISTS` | 회원가입 이메일 중복 |
| 409 | `DUPLICATE_REPORT` | 같은 날 같은 (약국, 약품) 중복 제보 |
| 413 | `FILE_TOO_LARGE` | 5MB 초과 |
| 415 | `UNSUPPORTED_FILE_TYPE` | jpg/png/webp 외 |
| 422 | `DRUG_NOT_OTC` | 전문의약품에 대한 제보 시도 |
| 500 | `INTERNAL_ERROR` | 그 외 |

### 1.4 인증 방식

- 로그인 시 `accessToken`(30분) + `refreshToken`(14일) 발급
- `accessToken` 은 `Authorization: Bearer` 헤더로 전송
- `refreshToken` 은 응답 바디로 반환하고 프론트에서 httpOnly 쿠키로 보관 (Next.js Route Handler 경유). 서버는 원문이 아니라 **SHA-256 해시를 `refresh_token` 테이블에 저장**한다
- `/auth/refresh` 는 토큰을 회전시킨다 — 기존 토큰을 revoke하고 새로 발급
- `/auth/logout` 은 해당 refresh 토큰을 revoke한다. access 토큰은 만료까지 유효하다 (블랙리스트는 범위 밖)
- 권한: `USER`(제보·조회), `ADMIN`(전체 + 관리자 API)

각 엔드포인트의 🔓 = 비로그인 허용, 🔐 = `USER` 이상, 👑 = `ADMIN` 전용

---

## 2. 인증

### `POST /api/v1/auth/signup` 🔓

**Request**

```json
{
  "email": "minji@example.com",
  "password": "Password123!",
  "nickname": "민지"
}
```

| 필드 | 규칙 |
|---|---|
| `email` | 이메일 형식, 최대 255자, 유니크 |
| `password` | 8~64자, 영문 + 숫자 포함 |
| `nickname` | 2~30자 |

**Response `201 Created`**

```json
{
  "id": 42,
  "email": "minji@example.com",
  "nickname": "민지",
  "role": "USER",
  "createdAt": "2026-09-15T13:12:33+09:00"
}
```

**Errors**: `409 EMAIL_ALREADY_EXISTS`, `400 VALIDATION_FAILED`

---

### `POST /api/v1/auth/login` 🔓

**Request**

```json
{ "email": "minji@example.com", "password": "Password123!" }
```

**Response `200 OK`**

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "refreshToken": "eyJhbGciOiJIUzI1NiIs...",
  "expiresIn": 1800,
  "user": { "id": 42, "nickname": "민지", "role": "USER" }
}
```

**Errors**: `401 UNAUTHENTICATED` (이메일·비밀번호 불일치 — 어느 쪽이 틀렸는지 구분하지 않는다)

---

### `POST /api/v1/auth/refresh` 🔓

**Request**: `{ "refreshToken": "..." }`

**Response `200 OK`**: `login` 과 동일한 형태 (access + refresh 모두 새로 발급)

검증 조건: `refresh_token` 테이블에 해당 토큰 해시가 있고, `revoked_at IS NULL` 이며 `expires_at > now()`.
검증에 성공하면 **기존 토큰을 즉시 revoke하고 새 토큰을 발급한다(rotation)**.

**Errors**: `401 UNAUTHENTICATED` (없음 / 만료 / 이미 revoke됨)

---

### `POST /api/v1/auth/logout` 🔐

서버에 저장된 refresh 토큰을 무효화한다.

**Request**

```json
{ "refreshToken": "eyJhbGciOiJIUzI1NiIs..." }
```

**Response `204 No Content`**

- 해당 토큰의 `revoked_at` 을 `now()` 로 설정한다
- 이미 revoke됐거나 존재하지 않는 토큰이어도 **`204` 를 반환한다.** 로그아웃은 멱등해야 하고, 실패를 알려줄 이유가 없다
- access 토큰은 만료(최대 30분)까지 유효하다. 즉시 무효화가 필요하면 블랙리스트가 필요하지만 이번 범위 밖이다
- 프론트는 이 호출과 별개로 httpOnly 쿠키와 메모리 토큰을 즉시 비운다

**Errors**: `401 UNAUTHENTICATED` (access 토큰이 없거나 유효하지 않음)

---

### `GET /api/v1/auth/me` 🔐

**Response `200 OK`**

```json
{
  "id": 42,
  "email": "minji@example.com",
  "nickname": "민지",
  "role": "USER",
  "reportCount": 7,
  "createdAt": "2026-09-15T13:12:33+09:00"
}
```

---

## 3. 의약품

### `GET /api/v1/drugs` 🔓

일반의약품 검색 / 자동완성.

**Query Parameters**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|---|---|---|---|---|
| `q` | string | N | | 품목명 부분 일치 (`display_name`, `name` 대상) |
| `category` | string | N | | `해열진통` \| `소화제` \| `감기약` \| `연고` \| `소독약` \| `비타민` \| `기타` |
| `page` | int | N | 0 | |
| `size` | int | N | 20 | 최대 50 |

**Response `200 OK`**

```json
{
  "content": [
    {
      "id": 1,
      "itemSeq": "196800050",
      "displayName": "타이레놀 500mg",
      "name": "타이레놀정500밀리그람",
      "maker": "한국얀센",
      "category": "해열진통",
      "form": "정제",
      "packageUnit": "8정",
      "imageUrl": "https://nedrug.mfds.go.kr/pbp/cmn/itemImageDownload/1NEt1Qb2Jp",
      "nationalAvgPrice": 3120,
      "pharmacyCount": 184
    }
  ],
  "page": 0, "size": 20, "totalElements": 1, "totalPages": 1, "hasNext": false
}
```

- `nationalAvgPrice`: 전국 `pharmacy_drug_price_stat.rep_price` 평균 (없으면 `null`)
- `pharmacyCount`: 가격 정보가 있는 약국 수

> **자동완성 용도**로 쓸 때는 `size=8` 로 호출하고 300ms 디바운스를 건다.

---

### `GET /api/v1/drugs/{drugId}` 🔓

**Response `200 OK`**

```json
{
  "id": 1,
  "itemSeq": "196800050",
  "displayName": "타이레놀 500mg",
  "name": "타이레놀정500밀리그람",
  "maker": "한국얀센",
  "category": "해열진통",
  "form": "정제",
  "packageUnit": "8정",
  "imageUrl": "...",
  "priceStats": {
    "nationalAvg": 3120,
    "nationalMin": 2200,
    "nationalMax": 4800,
    "pharmacyCount": 184,
    "reportCount": 412
  }
}
```

---

## 4. 약국

### `GET /api/v1/pharmacies` 🔓

약국 검색 (제보 폼의 약국 선택용).

**Query Parameters**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|---|---|---|---|---|
| `q` | string | N | | 약국명·주소 부분 일치 |
| `lat` | double | N | | 위도 |
| `lng` | double | N | | 경도 |
| `radius` | int | N | 2000 | 미터. `lat`·`lng` 가 있을 때만 유효. 최대 10000 |
| `page` / `size` | int | N | 0 / 20 | |

`q` 와 `lat`/`lng` 중 최소 하나는 필요하다. 둘 다 없으면 `400 VALIDATION_FAILED`.

**Response `200 OK`**

```json
{
  "content": [
    {
      "id": 101,
      "name": "가온약국",
      "addressRoad": "서울특별시 강남구 테헤란로 123",
      "lat": 37.5012,
      "lng": 127.0396,
      "phone": "02-555-1234",
      "distanceM": 340,
      "region": { "code": "11680", "sido": "서울특별시", "sigungu": "강남구" }
    }
  ],
  "page": 0, "size": 20, "totalElements": 12, "totalPages": 1, "hasNext": false
}
```

`distanceM` 은 `lat`/`lng` 를 넘겼을 때만 채워지고, 아니면 `null`.

---

### `GET /api/v1/pharmacies/{pharmacyId}` 🔓

**Query Parameters**: `lat`, `lng` (선택 — 거리 표시용)

**Response `200 OK`**

```json
{
  "id": 101,
  "name": "가온약국",
  "addressRoad": "서울특별시 강남구 테헤란로 123",
  "addressJibun": "서울특별시 강남구 역삼동 823",
  "lat": 37.5012,
  "lng": 127.0396,
  "phone": "02-555-1234",
  "businessHours": {
    "mon": ["09:00", "19:00"],
    "tue": ["09:00", "19:00"],
    "wed": ["09:00", "19:00"],
    "thu": ["09:00", "19:00"],
    "fri": ["09:00", "19:00"],
    "sat": ["09:00", "13:00"],
    "sun": null,
    "holiday": null
  },
  "distanceM": 340,
  "region": { "code": "11680", "sido": "서울특별시", "sigungu": "강남구" },
  "drugPrices": [
    {
      "drugId": 1,
      "displayName": "타이레놀 500mg",
      "packageUnit": "8정",
      "repPrice": 2800,
      "minPrice": 2700,
      "maxPrice": 3000,
      "avgPrice": 2830,
      "reportCount": 4,
      "lastReportedAt": "2026-09-10",
      "nationalAvgPrice": 3120,
      "diffFromNationalAvg": -320
    }
  ]
}
```

`drugPrices` 는 `repPrice` 오름차순 정렬.

---

### `GET /api/v1/pharmacies/{pharmacyId}/drugs/{drugId}/history` 🔓

가격 이력 (약국 상세의 스파크라인용).

**Query Parameters**: `days` (기본 180, 최대 365)

**Response `200 OK`**

```json
{
  "pharmacyId": 101,
  "drugId": 1,
  "points": [
    { "purchasedAt": "2026-06-02", "price": 2700, "flagged": false },
    { "purchasedAt": "2026-07-18", "price": 2800, "flagged": false },
    { "purchasedAt": "2026-08-01", "price": 9900, "flagged": true },
    { "purchasedAt": "2026-09-10", "price": 2800, "flagged": false }
  ]
}
```

`flagged: true` 인 점은 차트에서 회색 점선으로 표시하고 대표가격 계산에서 빠졌음을 툴팁으로 알린다.

---

## 5. 최저가 추천 (핵심)

### `GET /api/v1/search` 🔓

위치 기준 최저가 추천. **이 서비스의 핵심 엔드포인트다.**

**Query Parameters**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|---|---|---|---|---|
| `drugId` | long | **Y** | | 검색할 의약품 |
| `lat` | double | Y* | | 사용자 위도 |
| `lng` | double | Y* | | 사용자 경도 |
| `regionCode` | string | Y* | | 위치 권한 거부 시 대체. 해당 구역 `center_lat/lng` 를 사용 |
| `radius` | int | N | 2000 | 미터. 허용값 `500` \| `1000` \| `2000` \| `5000` |
| `sort` | string | N | `SCORE` | `SCORE` \| `PRICE` \| `DISTANCE` |
| `limit` | int | N | 20 | 최대 50 |

\* `lat`+`lng` 조합 **또는** `regionCode` 중 하나는 반드시 있어야 한다. 둘 다 없으면 `400 VALIDATION_FAILED`.

**Response `200 OK`**

```json
{
  "drug": {
    "id": 1,
    "displayName": "타이레놀 500mg",
    "packageUnit": "8정",
    "imageUrl": "..."
  },
  "query": {
    "lat": 37.4979,
    "lng": 127.0276,
    "radius": 2000,
    "sort": "SCORE",
    "locationSource": "GPS"
  },
  "summary": {
    "resultCount": 7,
    "candidateAvgPrice": 3140,
    "candidateMinPrice": 2600,
    "candidateMaxPrice": 3900,
    "maxSaving": 1300
  },
  "dataSource": "SEED",
  "results": [
    {
      "rank": 1,
      "recommended": true,
      "pharmacy": {
        "id": 101,
        "name": "가온약국",
        "addressRoad": "서울특별시 강남구 테헤란로 123",
        "lat": 37.5012,
        "lng": 127.0396,
        "phone": "02-555-1234"
      },
      "price": {
        "repPrice": 2600,
        "minPrice": 2500,
        "avgPrice": 2640,
        "savingVsCandidateAvg": 540,
        "reportCount": 4,
        "lastReportedAt": "2026-09-10",
        "daysSinceLastReport": 5
      },
      "distanceM": 340,
      "score": 0.9124,
      "scoreBreakdown": {
        "priceScore": 1.0,
        "distanceScore": 0.83,
        "freshnessScore": 0.891,
        "weights": { "price": 0.6, "distance": 0.25, "freshness": 0.15 }
      },
      "badges": ["LOWEST_PRICE"]
    },
    {
      "rank": 2,
      "recommended": false,
      "pharmacy": { "id": 118, "name": "새봄약국", "addressRoad": "...", "lat": 37.4991, "lng": 127.0301, "phone": "02-555-5678" },
      "price": {
        "repPrice": 2900,
        "minPrice": 2900,
        "avgPrice": 2900,
        "savingVsCandidateAvg": 240,
        "reportCount": 1,
        "lastReportedAt": "2026-06-20",
        "daysSinceLastReport": 87
      },
      "distanceM": 180,
      "score": 0.7208,
      "scoreBreakdown": {
        "priceScore": 0.769,
        "distanceScore": 0.91,
        "freshnessScore": 0.132,
        "weights": { "price": 0.6, "distance": 0.25, "freshness": 0.15 }
      },
      "badges": ["LOW_CONFIDENCE", "STALE_DATA"]
    }
  ]
}
```

**필드 설명**

| 필드 | 설명 |
|---|---|
| `query.locationSource` | `GPS` \| `REGION` — 사용자 좌표 출처 |
| `summary.maxSaving` | `candidateMaxPrice - candidateMinPrice` |
| `dataSource` | `SEED` \| `MIXED` \| `USER` — 결과에 포함된 제보의 출처. **UI 고지 배너 제어용** |
| `price.savingVsCandidateAvg` | `candidateAvgPrice - repPrice` (양수면 평균보다 저렴) |
| `scoreBreakdown` | 순위 근거. 관리자·디버깅용이지만 응답에 항상 포함해 설명 가능성을 확보한다 |
| `badges` | `LOWEST_PRICE`(1위) \| `LOW_CONFIDENCE`(제보 1건) \| `STALE_DATA`(30일 초과) \| `NEAREST`(최단거리) |

**빈 결과 `200 OK`**

```json
{
  "drug": { ... },
  "query": { ... },
  "summary": { "resultCount": 0, "candidateAvgPrice": null, "candidateMinPrice": null, "candidateMaxPrice": null, "maxSaving": null },
  "dataSource": "SEED",
  "results": [],
  "suggestion": { "type": "EXPAND_RADIUS", "recommendedRadius": 5000, "estimatedCount": 12 }
}
```

반경 확대 시 몇 건이 나오는지 미리 계산해 `suggestion` 으로 내려준다. (F3-9)

**Errors**: `400 VALIDATION_FAILED`, `400 INVALID_COORDINATE`, `404 DRUG_NOT_FOUND`

---

### Score 계산 명세 (구현 기준)

```
입력: 후보군 C = { i | dist(i) <= R, stat(i, drugId) 존재, pharmacy.is_active }

P_min = min{ repPrice_i | i ∈ C }
P_max = max{ repPrice_i | i ∈ C }

priceScore_i     = (P_max == P_min) ? 1.0
                                    : (P_max - repPrice_i) / (P_max - P_min)

distanceScore_i  = clamp(1 - dist_i / R, 0, 1)

ageDays_i        = CURRENT_DATE - lastReportedAt_i
freshnessScore_i = 0.5 ^ (ageDays_i / 30)

score_i = 0.60 * priceScore_i + 0.25 * distanceScore_i + 0.15 * freshnessScore_i

정렬: score DESC → repPrice ASC → dist ASC → pharmacyId ASC
```

- 모든 score는 소수점 4자리로 반올림해 응답한다.
- 마지막 `pharmacyId ASC` 타이브레이커 덕분에 **같은 입력은 항상 같은 순서**를 반환한다. (테스트 안정성)
- 가중치는 `application.yml` 에서 주입한다.

```yaml
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

---

## 6. 가격 제보

### `POST /api/v1/price-reports` 🔐

**Request**

```json
{
  "pharmacyId": 101,
  "drugId": 1,
  "price": 2800,
  "purchasedAt": "2026-09-14",
  "receiptFileId": 55,
  "memo": "1+1 행사 아님, 정가"
}
```

| 필드 | 필수 | 규칙 |
|---|---|---|
| `pharmacyId` | Y | 존재하는 활성 약국 |
| `drugId` | Y | 존재하고 `otcFlag = true` |
| `price` | Y | 100 ~ 200000 정수 |
| `purchasedAt` | N | 미입력 시 오늘. 미래 불가, 180일 초과 과거 불가 |
| `receiptFileId` | N | `POST /uploads` 로 먼저 업로드한 파일 id |
| `memo` | N | 최대 200자 |

**Response `201 Created`**

```json
{
  "id": 4821,
  "pharmacyId": 101,
  "drugId": 1,
  "price": 2800,
  "purchasedAt": "2026-09-14",
  "status": "ACTIVE",
  "flagged": false,
  "flagReason": null,
  "createdAt": "2026-09-15T13:12:33+09:00",
  "updatedStat": {
    "repPrice": 2800,
    "minPrice": 2700,
    "avgPrice": 2830,
    "reportCount": 5,
    "lastReportedAt": "2026-09-14"
  }
}
```

`updatedStat` 은 제보 반영 후 재계산된 통계다. 프론트는 이 값으로 화면을 즉시 갱신한다.

**이상치 제보 시 `201 Created`** — 저장은 되지만 통계에서 제외된다.

```json
{
  "id": 4822,
  "price": 50000,
  "status": "ACTIVE",
  "flagged": true,
  "flagReason": "OUTLIER_HIGH",
  "warning": "입력하신 가격이 이 약품의 일반적인 가격대(2,200~4,800원)와 크게 달라 통계에 반영되지 않았습니다. 관리자 확인 후 반영됩니다.",
  "updatedStat": { "repPrice": 2800, "reportCount": 4, ... }
}
```

**Errors**: `400 VALIDATION_FAILED`, `400 INVALID_DATE_RANGE`, `401 UNAUTHENTICATED`, `404 PHARMACY_NOT_FOUND` / `DRUG_NOT_FOUND`, `409 DUPLICATE_REPORT`, `422 DRUG_NOT_OTC`

---

### `GET /api/v1/price-reports` 🔓

**Query Parameters**

| 이름 | 타입 | 설명 |
|---|---|---|
| `pharmacyId` | long | |
| `drugId` | long | |
| `mine` | boolean | `true` 면 본인 제보만 (🔐 필요) |
| `page` / `size` | int | 기본 0 / 20 |

**Response `200 OK`**

```json
{
  "content": [
    {
      "id": 4821,
      "pharmacy": { "id": 101, "name": "가온약국" },
      "drug": { "id": 1, "displayName": "타이레놀 500mg", "packageUnit": "8정" },
      "price": 2800,
      "purchasedAt": "2026-09-14",
      "reporter": { "nickname": "민지" },
      "source": "FORM",
      "status": "ACTIVE",
      "flagged": false,
      "hasReceipt": true,
      "createdAt": "2026-09-15T13:12:33+09:00"
    }
  ],
  "page": 0, "size": 20, "totalElements": 5, "totalPages": 1, "hasNext": false
}
```

`reporter` 는 닉네임만 노출한다. 이메일·id는 내려주지 않는다.

---

### `POST /api/v1/uploads` 🔐

영수증 이미지 업로드. `multipart/form-data`.

**Request**

| 파트 | 타입 | 규칙 |
|---|---|---|
| `file` | file | `image/jpeg` \| `image/png` \| `image/webp`, 5MB 이하 |
| `purpose` | text | `RECEIPT` (현재 유일값) |

**Response `201 Created`**

```json
{
  "id": 55,
  "originalName": "IMG_0421.jpg",
  "contentType": "image/jpeg",
  "sizeBytes": 1284213,
  "url": "/api/v1/uploads/55",
  "createdAt": "2026-09-15T13:10:00+09:00"
}
```

**Errors**: `413 FILE_TOO_LARGE`, `415 UNSUPPORTED_FILE_TYPE`

> **OCR은 하지 않는다.** 업로드된 이미지는 관리자가 제보 검증 시 참고하는 용도다. (PRD §2.2)

---

### `GET /api/v1/uploads/{fileId}` 🔐

파일 바이너리를 반환한다. 업로더 본인 또는 `ADMIN` 만 접근 가능.

---

## 7. 지역

### `GET /api/v1/regions` 🔓

위치 권한 거부 시 폴백 드롭다운용.

**Response `200 OK`**

```json
[
  {
    "sido": "서울특별시",
    "sigungus": [
      { "code": "11680", "sigungu": "강남구", "centerLat": 37.4959, "centerLng": 127.0664, "pharmacyCount": 42 }
    ]
  }
]
```

시도별로 그룹핑해 반환한다. 페이지네이션 없음 (전체 ~250건).

---

## 8. 관리자 (👑 ADMIN 전용)

모든 엔드포인트는 `@PreAuthorize("hasRole('ADMIN')")`. 권한 없으면 `403 FORBIDDEN`.

### `GET /api/v1/admin/stats/overview` 👑

**Response `200 OK`**

```json
{
  "totals": {
    "pharmacyCount": 342,
    "drugCount": 36,
    "reportCount": 3218,
    "userCount": 21,
    "coveredPairCount": 2140
  },
  "recentTrend": [
    { "date": "2026-09-09", "reportCount": 12 },
    { "date": "2026-09-10", "reportCount": 18 }
  ],
  "flaggedReportCount": 64,
  "coverageRate": 0.62
}
```

`coverageRate` = 가격 정보가 있는 (약국 × 약품) 조합 비율.

---

### `GET /api/v1/admin/stats/regions` 👑

지역별 가격 통계. (F4-3)

**Query Parameters**: `regionCode`, `drugId`, `sido` (모두 선택)

**Response `200 OK`**

```json
{
  "rows": [
    {
      "region": { "code": "11680", "sido": "서울특별시", "sigungu": "강남구" },
      "drug": { "id": 1, "displayName": "타이레놀 500mg" },
      "avgPrice": 3240,
      "minPrice": 2600,
      "maxPrice": 3900,
      "pharmacyCount": 24,
      "reportCount": 71
    }
  ]
}
```

---

### `GET /api/v1/admin/stats/drugs/{drugId}` 👑

특정 약품의 전국 가격 분포. (F4-4)

**Response `200 OK`**

```json
{
  "drug": { "id": 1, "displayName": "타이레놀 500mg", "packageUnit": "8정" },
  "distribution": [
    { "bucketFrom": 2000, "bucketTo": 2500, "count": 8 },
    { "bucketFrom": 2500, "bucketTo": 3000, "count": 42 },
    { "bucketFrom": 3000, "bucketTo": 3500, "count": 61 }
  ],
  "byRegion": [
    { "sido": "서울특별시", "sigungu": "강남구", "avgPrice": 3240, "pharmacyCount": 24 },
    { "sido": "서울특별시", "sigungu": "노원구", "avgPrice": 2810, "pharmacyCount": 19 }
  ],
  "national": { "avg": 3120, "median": 3050, "min": 2200, "max": 4800, "stdDev": 412 }
}
```

---

### `GET /api/v1/admin/stats/price-gaps` 👑

지역 간 가격 격차가 큰 약품 Top N. **서비스의 존재 이유를 가장 잘 보여주는 지표.**

**Query Parameters**: `limit` (기본 10, 최대 50)

**Response `200 OK`**

```json
{
  "rows": [
    {
      "drug": { "id": 7, "displayName": "겔포스엠 현탁액" },
      "cheapestRegion": { "sido": "서울특별시", "sigungu": "노원구", "avgPrice": 4200 },
      "priciestRegion": { "sido": "서울특별시", "sigungu": "서초구", "avgPrice": 6800 },
      "gap": 2600,
      "gapPct": 61.9
    }
  ]
}
```

---

### `GET /api/v1/admin/price-reports` 👑

제보 관리 목록. (F4-5)

**Query Parameters**: `flagged`(boolean), `status`, `pharmacyId`, `drugId`, `page`, `size`

**Response**: `GET /api/v1/price-reports` 와 동일하되 `reporter` 에 `id`, `email` 포함, `flagReason`·`receiptFileId` 포함.

---

### `PATCH /api/v1/admin/price-reports/{reportId}` 👑

제보 숨김 / 복구 / 이상치 플래그 해제.

**Request**

```json
{ "status": "HIDDEN", "flagged": false, "reason": "약국 확인 결과 오기재" }
```

세 필드 모두 선택이며, 넘긴 필드만 변경한다.

**Response `200 OK`**

```json
{
  "id": 4822,
  "status": "HIDDEN",
  "flagged": false,
  "updatedAt": "2026-09-15T14:00:00+09:00",
  "recalculatedStat": {
    "pharmacyId": 101,
    "drugId": 1,
    "repPrice": 2800,
    "reportCount": 4
  }
}
```

상태 변경 시 해당 (약국, 약품) 통계가 **동기적으로** 재계산된다.

---

## 9. 엔드포인트 요약

| Method | Path | 권한 | 우선순위 |
|---|---|---|---|
| POST | `/api/v1/auth/signup` | 🔓 | P0 |
| POST | `/api/v1/auth/login` | 🔓 | P0 |
| POST | `/api/v1/auth/refresh` | 🔓 | P1 |
| POST | `/api/v1/auth/logout` | 🔐 | P1 |
| GET | `/api/v1/auth/me` | 🔐 | P0 |
| GET | `/api/v1/drugs` | 🔓 | P0 |
| GET | `/api/v1/drugs/{drugId}` | 🔓 | P1 |
| GET | `/api/v1/pharmacies` | 🔓 | P0 |
| GET | `/api/v1/pharmacies/{pharmacyId}` | 🔓 | P0 |
| GET | `/api/v1/pharmacies/{pharmacyId}/drugs/{drugId}/history` | 🔓 | P1 |
| **GET** | **`/api/v1/search`** | 🔓 | **P0 (핵심)** |
| POST | `/api/v1/price-reports` | 🔐 | P0 |
| GET | `/api/v1/price-reports` | 🔓 | P1 |
| POST | `/api/v1/uploads` | 🔐 | P1 |
| GET | `/api/v1/uploads/{fileId}` | 🔐 | P1 |
| GET | `/api/v1/regions` | 🔓 | P0 |
| GET | `/api/v1/admin/stats/overview` | 👑 | P2 |
| GET | `/api/v1/admin/stats/regions` | 👑 | P2 |
| GET | `/api/v1/admin/stats/drugs/{drugId}` | 👑 | P2 |
| GET | `/api/v1/admin/stats/price-gaps` | 👑 | P2 |
| GET | `/api/v1/admin/price-reports` | 👑 | P2 |
| PATCH | `/api/v1/admin/price-reports/{reportId}` | 👑 | P2 |

---

## 10. OpenAPI

`springdoc-openapi-starter-webmvc-ui` 를 추가해 `/swagger-ui.html` 에서 확인한다.

```yaml
springdoc:
  swagger-ui:
    path: /swagger-ui.html
    tags-sorter: alpha
  api-docs:
    path: /v3/api-docs
```

프론트 타입은 `openapi-typescript` 로 `/v3/api-docs` 에서 생성해 수기 동기화 비용을 없앤다.

---

*필드명은 [DATABASE.md](./DATABASE.md) 의 컬럼과 대응한다(`snake_case` → `camelCase`). Score 수식은 [PRD.md](./PRD.md) §F3.2와 동일해야 하며, 어느 한쪽을 바꾸면 반드시 양쪽을 함께 수정할 것.*
