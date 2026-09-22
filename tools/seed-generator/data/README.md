# 원본 공공데이터 (ROADMAP T-07)

이 디렉토리에 원본 파일을 넣으면 `build_master_seed.py`가 자동으로 합성 데이터 대신
실제 데이터를 사용한다. 파일이 없으면 우선순위대로 다음 소스로 폴백하고, 전부 없으면
synthetic 데이터로 조용히 폴백한다.

## 약국·지역 — 우선순위

1. **`2.약국정보서비스(2026.6.).xlsx`** — 심평원 전국 약국 현황 원본(전국, ~25,760건).
   현재 이 파일을 사용 중이며, 전국 데이터가 그대로 들어간다. `region.code`는 이 파일의
   시군구코드(행정표준코드)를 그대로 쓰고, `region.center_lat/lng`은 그 시군구 소속 약국들의
   평균 좌표로 근사한다. **openpyxl**이 필요하다(`pip install openpyxl`).
2. `pharmacy_raw.json` — 국립중앙의료원 API(`fetch_pharmacy_api.py`)로 32개 지역만 받은 실데이터.
3. `pharmacy_raw.csv` — 심평원류 CSV 원본(수동으로 넣은 경우). 필요한 컬럼은
   `build_master_seed.py`의 `_PHARMACY_COLUMN_ALIASES`에 등록된 별칭과 일치해야 자동 인식된다.
4. 위 셋 다 없으면 synthetic 데이터(서울 25구 + 경기 일부, 상호·주소는 전부 가상)로 폴백한다.

## 의약품 — 우선순위

1. **`drug_raw.json`** — 식약처 e약은요 API(`fetch_drug_api.py`) 원본을 전량(~4,779건) 적재한다.
   `category`/`package_unit`/`base_price`/`otc_flag`은 이 API 제공 범위 밖이라 채워 넣는
   값이다(`category="기타"` 고정, `package_unit`/`base_price`는 임의, `otc_flag`는 전문/일반
   구분 필드가 없어 **전부 true** — F1-6(전문의약품 제외)을 온전히 만족하지 못한다).
   `item_seq`/`maker`/`name`/`image_url`(itemImage)은 실제 API 값 그대로다.
2. 없으면 `_DRUG_SEED`(30종, 실존 상품명 수기 큐레이션)로 폴백한다.

## 가격 제보(`price_report`) 볼륨 주의

`build_price_seed.py`는 약국×의약품을 전수 대조하지 않는다 — 전국 약국(최대 25,760) ×
전체 의약품(최대 4,779)을 그대로 곱하면 조합이 억 단위가 되어 마이그레이션 SQL 파일이
git에 커밋 불가능한 크기가 된다(GitHub 파일당 100MB 한도). 대신 가격 데이터를 가질 약국을
최대 `_MAX_PRICED_PHARMACIES`(5,000)곳만 무작위로 뽑고, 뽑힌 약국마다 전체 카탈로그가
아니라 무작위 부분집합(`_ASSORTMENT_RANGE`, 15~35개)만 대조한다. 나머지 약국은 실주소·
전화번호는 그대로 유지한 채 "아직 제보가 없는" 상태로 남는다(크라우드소싱 서비스에서
실제로 벌어지는 정상 상태이며, 앱은 이미 "정보 부족"/빈 검색 결과로 이를 처리한다).

## 실행 순서

```bash
# 1) 의약품 API 원본 캐싱 (data.go.kr에서 발급받은 서비스키를 넣는다 — 이 파일에 직접 적어두지 말 것)
DATA_GO_KR_API_KEY=발급받은키 python fetch_drug_api.py

# 2) 약국 xlsx/csv를 이 디렉토리에 넣은 뒤
pip install openpyxl
python build_master_seed.py
python build_price_seed.py
```

마이그레이션 내용이 바뀌면(V2/V3를 재생성하면) 로컬 DB에 이미 적용된 체크섬과 어긋나
Flyway가 다음 기동 때 실패한다 — `pharmaprice` 스키마를 지우고 다시 만든 뒤 백엔드를
재기동해야 한다:

```sql
DROP SCHEMA IF EXISTS pharmaprice CASCADE;
CREATE SCHEMA pharmaprice AUTHORIZATION pharmaprice;
```
