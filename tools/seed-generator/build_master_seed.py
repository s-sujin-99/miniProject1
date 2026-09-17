"""마스터 시드(region/pharmacy/drug/app_user) 생성 스크립트 (ROADMAP T-07).

실행: python build_master_seed.py
  → miniproject1-backend/src/main/resources/db/migration/V2__seed_master.sql 생성.

약국(pharmacy)은 우선순위대로 데이터 소스를 고른다:
  1) data/pharmacy_raw.json — 국립중앙의료원 전국 약국 정보 API(fetch_pharmacy_api.py)로
     32개 지역(Q0/Q1)을 이미 필터링해 받은 실데이터.
  2) data/pharmacy_raw.csv — 심평원류 CSV 원본(수동으로 이 자리에 넣은 경우).
  3) 위 둘 다 없으면 현실적인 분포의 합성 데이터로 폴백 — 이 경우 상호·주소는 전부 가상이며
     실존 업체와 무관하다.
region의 code는 통계청 행정표준코드가 아닌 이 스크립트만의 합성 값이다(행정구역명·구청 근사
좌표는 공개 정보).

의약품(drug)은 _DRUG_SEED가 실존 일반의약품 상품명이며, item_seq는 data.go.kr e약은요 API
(fetch_drug_api.py)로 실제 조회해 확인한 식약처 품목기준코드다(매칭 안 된 일부는 MOCKDRUG-
코드로 폴백). category/package_unit/base_price는 e약은요 API에 없는 필드라 ROADMAP T-07 §4
지침대로 수기 입력이다 — 이건 공공데이터 미비가 아니라 애초에 그 API의 제공 범위 밖이다.

재실행해도 같은 결과가 나오도록 random.seed를 모듈 로드 시 한 번만 고정한다.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

random.seed(20260915)

# 서울 25구 + 경기 일부(대상 지역을 좁혀야 반경 2km 안에 약국이 충분히 잡힌다 — ROADMAP T-07 §3).
# (sido, sigungu, center_lat, center_lng) — 구청/시청 근사 좌표(공개 정보).
_REGION_SEED = [
    ("서울특별시", "강남구", 37.5172, 127.0473),
    ("서울특별시", "강동구", 37.5301, 127.1238),
    ("서울특별시", "강북구", 37.6396, 127.0257),
    ("서울특별시", "강서구", 37.5509, 126.8495),
    ("서울특별시", "관악구", 37.4784, 126.9516),
    ("서울특별시", "광진구", 37.5384, 127.0822),
    ("서울특별시", "구로구", 37.4954, 126.8874),
    ("서울특별시", "금천구", 37.4519, 126.9020),
    ("서울특별시", "노원구", 37.6542, 127.0568),
    ("서울특별시", "도봉구", 37.6688, 127.0471),
    ("서울특별시", "동대문구", 37.5744, 127.0396),
    ("서울특별시", "동작구", 37.5124, 126.9393),
    ("서울특별시", "마포구", 37.5663, 126.9019),
    ("서울특별시", "서대문구", 37.5791, 126.9368),
    ("서울특별시", "서초구", 37.4837, 127.0324),
    ("서울특별시", "성동구", 37.5633, 127.0371),
    ("서울특별시", "성북구", 37.5894, 127.0167),
    ("서울특별시", "송파구", 37.5145, 127.1059),
    ("서울특별시", "양천구", 37.5170, 126.8664),
    ("서울특별시", "영등포구", 37.5264, 126.8963),
    ("서울특별시", "용산구", 37.5324, 126.9900),
    ("서울특별시", "은평구", 37.6027, 126.9291),
    ("서울특별시", "종로구", 37.5730, 126.9794),
    ("서울특별시", "중구", 37.5636, 126.9976),
    ("서울특별시", "중랑구", 37.6063, 127.0925),
    ("경기도", "수원시", 37.2636, 127.0286),
    ("경기도", "성남시", 37.4201, 127.1267),
    ("경기도", "고양시", 37.6584, 126.8320),
    ("경기도", "용인시", 37.2411, 127.1776),
    ("경기도", "부천시", 37.5034, 126.7660),
    ("경기도", "안양시", 37.3943, 126.9568),
    ("경기도", "화성시", 37.1996, 126.8312),
]

_PHARMACY_MODIFIERS = ["행복", "온누리", "365", "정성", "튼튼", "새싹", "하나로", "미소", "참사랑", "우리"]

_BUSINESS_HOURS_TEMPLATES = [
    {"mon": ["09:00", "19:00"], "tue": ["09:00", "19:00"], "wed": ["09:00", "19:00"],
     "thu": ["09:00", "19:00"], "fri": ["09:00", "19:00"], "sat": ["09:00", "14:00"], "sun": None, "holiday": None},
    {"mon": ["09:00", "20:00"], "tue": ["09:00", "20:00"], "wed": ["09:00", "20:00"],
     "thu": ["09:00", "20:00"], "fri": ["09:00", "20:00"], "sat": ["09:00", "18:00"], "sun": ["10:00", "17:00"], "holiday": None},
    {"mon": ["08:30", "18:30"], "tue": ["08:30", "18:30"], "wed": ["08:30", "18:30"],
     "thu": ["08:30", "18:30"], "fri": ["08:30", "18:30"], "sat": None, "sun": None, "holiday": None},
]


# 국내에 실제로 알려진 일반의약품 상품명(공개 정보) —
# (name, display_name, maker, category, form, package_unit, base_price, item_seq).
# 같은 상품이라도 포장 단위가 다르면 별개 행이다(DATABASE.md §3.4) — 1·2번이 그 예.
#
# item_seq는 data.go.kr e약은요 API(fetch_drug_api.py)로 실제 조회해 채운 식약처 품목기준코드다.
# 매칭 안 된 항목은 None(→ generate_drugs()가 MOCKDRUG- 코드로 폴백). e약은요는 "품목"(성분+제형)
# 단위라 포장 규격(8정/16정)별 별도 코드가 없어, item_seq가 UNIQUE(DATABASE.md §3.4)인 스키마와
# 충돌한다 — 실제 코드에 포장단위 접미사를 붙인 파생 키로 우회했다(타이레놀 두 행이 예).
_DRUG_SEED = [
    ("타이레놀정500밀리그람", "타이레놀 500mg", "한국얀센", "해열진통", "정제", "8정", 2000, "202106092-8"),
    ("타이레놀정500밀리그람", "타이레놀 500mg", "한국얀센", "해열진통", "정제", "16정", 3500, "202106092-16"),
    ("게보린정", "게보린", "삼진제약", "해열진통", "정제", "10정", 2500, "197900277"),
    ("펜잘큐정", "펜잘큐", "종근당", "해열진통", "정제", "10정", 2500, "200810700"),
    ("부루펜정400밀리그람", "부루펜 400mg", "삼일제약", "해열진통", "정제", "10정", 3000, None),
    ("베아제정", "베아제", "대웅제약", "소화제", "정제", "30정", 4500, "198700405"),
    ("훼스탈골드정", "훼스탈골드", "한독", "소화제", "정제", "30정", 4200, "199900926"),
    ("까스활명수큐액", "까스활명수큐", "동화약품", "소화제", "액상", "75mlx3", 3200, "198900667"),
    ("백초시럽", "백초시럽", "동아제약", "소화제", "시럽", "80ml", 3800, None),
    ("겔포스엠현탁액", "겔포스엠", "보령제약", "소화제", "액상", "20mlx3", 3000, "199400883"),
    ("판콜에이내복액", "판콜에이", "동화약품", "감기약", "액상", "30ml", 1500, "196800036"),
    ("판피린큐액", "판피린큐", "동아제약", "감기약", "액상", "20ml", 1200, "200700547"),
    ("콜대원콜드에스시럽", "콜대원콜드에스", "대원제약", "감기약", "액상", "15mlx3", 3500, "201603301"),
    ("챔프시럽", "챔프시럽", "대원제약", "감기약", "시럽", "90ml", 4000, "201206715"),
    ("타이레놀콜드에스정", "타이레놀콜드에스", "한국얀센", "감기약", "정제", "10정", 3200, None),
    ("마데카솔케어연고", "마데카솔케어", "동국제약", "연고", "연고", "5g", 4500, "200903973"),
    ("후시딘연고", "후시딘", "동화약품", "연고", "연고", "10g", 5500, "197900171"),
    ("안티프라민", "안티프라민", "녹십자", "연고", "연고", "76g", 6000, None),
    ("신신파스아렉스", "신신파스아렉스", "신신제약", "연고", "파스", "10매", 3000, "200501321"),
    ("제놀쿨파스", "제놀쿨파스", "삼일제약", "연고", "파스", "8매", 2800, None),
    ("포비돈요오드액", "포비돈요오드", "퍼슨", "소독약", "액상", "50ml", 2000, None),
    ("옥시풀과산화수소수", "과산화수소수", "동화약품", "소독약", "액상", "100ml", 1500, None),
    ("생리식염수", "생리식염수", "대한약품", "소독약", "액상", "500ml", 2500, None),
    # 제조사 정정: API 조회 결과 '일양약품'이 아니라 '일동제약'이다.
    ("아로나민골드정", "아로나민골드", "일동제약", "비타민", "정제", "100정", 15000, "197000037"),
    ("센트룸실버정", "센트룸실버", "한국화이자", "비타민", "정제", "30정", 12000, None),
    ("삐콤씨정", "삐콤씨", "유한양행", "비타민", "정제", "100정", 13000, "201206997"),
    ("임팩타민정", "임팩타민", "한국콜마", "비타민", "정제", "90정", 20000, "200709544"),
    ("비오비타정", "비오비타", "일양약품", "비타민", "정제", "100정", 9000, None),
    ("대일밴드스팟터치", "대일밴드", "대일화학", "기타", "밴드", "10매", 2000, None),
    ("쿨파워시원한젤", "쿨파워젤", "동아제약", "기타", "젤", "80g", 4500, None),
]

# BCryptPasswordEncoder(strength 10, 프로젝트 SecurityConfig와 동일)로 미리 계산한 해시.
# 원문 비밀번호는 여기 주석에만 남긴다(커밋에 값이 아닌 해시만 남도록) — 관리자: Admin1234!, 더미 20명: User1234!
_ADMIN_PASSWORD_HASH = "$2a$10$voyHX.q1C3aQ9kv25DvDKedc6Z7MtzFHSimk7Dg4q0.DXyhno1HsW"
_DUMMY_PASSWORD_HASH = "$2a$10$CaIq8zBByEYmbyVIyfncH.kZJsD3Jyn1S59uN4M8KyZlU1xRfEXn."


@dataclass
class Region:
    code: str
    sido: str
    sigungu: str
    center_lat: float
    center_lng: float


@dataclass
class Pharmacy:
    id: int
    hira_code: str
    name: str
    address_road: str
    address_jibun: str | None
    region_code: str
    lat: float
    lng: float
    phone: str
    business_hours: dict
    is_active: bool = True


@dataclass
class Drug:
    id: int
    item_seq: str
    name: str
    display_name: str
    maker: str
    category: str
    form: str
    package_unit: str
    base_price: int


@dataclass
class AppUserSeed:
    id: int
    email: str
    password_hash: str
    nickname: str
    role: str
    provider: str = "LOCAL"


def generate_regions() -> list[Region]:
    return [
        Region(code=f"R{idx:02d}", sido=sido, sigungu=sigungu, center_lat=lat, center_lng=lng)
        for idx, (sido, sigungu, lat, lng) in enumerate(_REGION_SEED, start=1)
    ]


_PHARMACY_CSV_PATH = Path(__file__).resolve().parent / "data" / "pharmacy_raw.csv"

# 심사평가원 "병원정보서비스" 계열 공공데이터에서 흔히 쓰이는 컬럼명 후보들.
# 실제 파일을 받으면 헤더를 확인하고 필요한 별칭을 추가한다(모르는 컬럼을 추측해서 맞추지 않는다).
_PHARMACY_COLUMN_ALIASES: dict[str, list[str]] = {
    "category": ["종별코드명", "기관종별", "구분"],
    "name": ["요양기관명", "약국명", "사업장명", "기관명", "명칭"],
    "sido": ["시도코드명", "시도명", "시도"],
    "sigungu": ["시군구코드명", "시군구명", "시군구"],
    "address_road": ["도로명주소", "소재지도로명주소"],
    "address_jibun": ["지번주소", "소재지지번주소", "주소"],
    "phone": ["전화번호", "연락처"],
    "lat": ["위도", "좌표(Y)", "Y좌표", "y좌표"],
    "lng": ["경도", "좌표(X)", "X좌표", "x좌표"],
}
# category는 약국 전용 파일이면 아예 없을 수 있으므로 필수 컬럼에서 제외한다.
_PHARMACY_REQUIRED_FIELDS = [f for f in _PHARMACY_COLUMN_ALIASES if f != "category"]


def _resolve_columns(header: list[str]) -> dict[str, str]:
    """표준 필드명 → 실제 CSV 헤더 컬럼명 매핑. 필수 컬럼을 못 찾으면 즉시 에러로 알린다."""
    resolved: dict[str, str] = {}
    for field, aliases in _PHARMACY_COLUMN_ALIASES.items():
        match = next((h for h in header if h.strip() in aliases), None)
        if match is None and field in _PHARMACY_REQUIRED_FIELDS:
            raise ValueError(
                f"pharmacy_raw.csv에서 '{field}' 컬럼을 찾을 수 없다. 헤더: {header}. "
                f"_PHARMACY_COLUMN_ALIASES에 실제 컬럼명을 추가하라."
            )
        if match is not None:
            resolved[field] = match
    return resolved


def _match_region(sido: str, sigungu: str, regions: list[Region]) -> Region | None:
    """CSV의 시도/시군구 문자열을 _REGION_SEED 32개 행정구역과 매칭한다(대상 지역 밖이면 None)."""
    sido, sigungu = sido.strip(), sigungu.strip()
    for region in regions:
        if region.sido == sido and sigungu.startswith(region.sigungu):
            return region
    return None


def _load_real_pharmacies(regions: list[Region]) -> list[Pharmacy] | None:
    """data/pharmacy_raw.csv가 있으면 실제 공공데이터를 파싱한다. 없으면 None(합성 데이터로 폴백)."""
    if not _PHARMACY_CSV_PATH.exists():
        return None

    with _PHARMACY_CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = _resolve_columns(reader.fieldnames or [])

        candidates: list[Pharmacy] = []
        next_id = 1
        for row in reader:
            if "category" in cols and "약국" not in row[cols["category"]]:
                continue

            region = _match_region(row[cols["sido"]], row[cols["sigungu"]], regions)
            if region is None:
                continue  # 대상 지역(서울+경기 일부) 밖 — ROADMAP T-07 §3

            try:
                lat, lng = float(row[cols["lat"]]), float(row[cols["lng"]])
            except (KeyError, ValueError):
                continue
            if lat == 0 or lng == 0:
                continue  # 좌표 빈 값/0 — ROADMAP T-07 §3

            address_road = row.get(cols.get("address_road", ""), "").strip()
            address_jibun = row.get(cols.get("address_jibun", ""), "").strip() or None
            candidates.append(Pharmacy(
                id=next_id,
                hira_code=f"REAL-{next_id:05d}",
                name=row[cols["name"]].strip(),
                address_road=address_road or (address_jibun or "주소 미상"),
                address_jibun=address_jibun,
                region_code=region.code,
                lat=lat,
                lng=lng,
                phone=row.get(cols.get("phone", ""), "").strip(),
                business_hours=random.choice(_BUSINESS_HOURS_TEMPLATES),
            ))
            next_id += 1

    if len(candidates) < 300:
        print(f"실제 데이터로 필터링한 약국이 {len(candidates)}건뿐이다(300건 미만) — synthetic으로 폴백한다.",
              file=sys.stderr)
        return None

    if len(candidates) > 500:
        candidates = random.sample(candidates, 500)
        for idx, p in enumerate(candidates, start=1):
            p.id = idx

    return candidates


_PHARMACY_JSON_PATH = Path(__file__).resolve().parent / "data" / "pharmacy_raw.json"
# 국립중앙의료원 API의 dutyTime1~7이 월~일 순서다(E-Gen 계열 API의 표준 필드 관례).
_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_duty_hhmm(value) -> str | None:
    if not value:
        return None
    digits = str(value).zfill(4)
    return f"{digits[:2]}:{digits[2:]}"


def _business_hours_from_api(item: dict) -> dict:
    hours: dict[str, list[str] | None] = {}
    for i, key in enumerate(_WEEKDAY_KEYS, start=1):
        start, close = _parse_duty_hhmm(item.get(f"dutyTime{i}s")), _parse_duty_hhmm(item.get(f"dutyTime{i}c"))
        hours[key] = [start, close] if start and close else None
    holiday_start = _parse_duty_hhmm(item.get("dutyTime8s"))
    holiday_close = _parse_duty_hhmm(item.get("dutyTime8c"))
    hours["holiday"] = [holiday_start, holiday_close] if holiday_start and holiday_close else None
    return hours


def _load_real_pharmacies_from_api(regions: list[Region]) -> list[Pharmacy] | None:
    """data/pharmacy_raw.json(fetch_pharmacy_api.py의 출력)이 있으면 그걸 쓴다. 없으면 None."""
    if not _PHARMACY_JSON_PATH.exists():
        return None

    raw: dict[str, list[dict]] = json.loads(_PHARMACY_JSON_PATH.read_text(encoding="utf-8"))
    region_by_key = {f"{r.sido} {r.sigungu}": r for r in regions}

    candidates: list[Pharmacy] = []
    next_id = 1
    seen_hira_codes: set[str] = set()
    for key, items in raw.items():
        region = region_by_key.get(key)
        if region is None:
            continue  # _REGION_SEED에 없는 지역(API 응답 키가 어긋난 경우) — 건너뛴다

        # 완전 무작위로 뽑으면 넓은 구(강남구 등)에서는 결과가 중심좌표 반경 2km 밖까지 흩어져
        # T-07 §3("같은 행정구역에 몰리도록 뽑는다") 완료판정을 못 채운다 — 중심좌표에 가까운
        # 순으로 정렬해 상위 k개만 취해서 밀집시킨다.
        items_sorted = sorted(
            items,
            key=lambda it: (float(it.get("wgs84Lat") or 0) - region.center_lat) ** 2
            + (float(it.get("wgs84Lon") or 0) - region.center_lng) ** 2,
        )
        picked = items_sorted[:random.randint(8, 15)]
        for it in picked:
            name = (it.get("dutyName") or "").strip()
            lat, lng = it.get("wgs84Lat"), it.get("wgs84Lon")
            hira_code = (it.get("hpid") or "").strip()
            if not name or not lat or not lng:
                continue
            if not hira_code or hira_code in seen_hira_codes:
                hira_code = f"REAL-{next_id:05d}"  # hpid 없음/중복 시에만 합성 코드로 대체
            seen_hira_codes.add(hira_code)

            candidates.append(Pharmacy(
                id=next_id,
                hira_code=hira_code,
                name=name,
                address_road=(it.get("dutyAddr") or "").strip() or "주소 미상",
                address_jibun=None,
                region_code=region.code,
                lat=float(lat),
                lng=float(lng),
                phone=(it.get("dutyTel1") or "").strip(),
                business_hours=_business_hours_from_api(it),
            ))
            next_id += 1

    if len(candidates) < 300:
        print(f"API 실데이터로 뽑은 약국이 {len(candidates)}건뿐이다(300건 미만) — synthetic으로 폴백한다.",
              file=sys.stderr)
        return None
    return candidates


def generate_pharmacies(regions: list[Region]) -> list[Pharmacy]:
    real = _load_real_pharmacies_from_api(regions) or _load_real_pharmacies(regions)
    if real is not None:
        return real

    pharmacies: list[Pharmacy] = []
    next_id = 1
    for region in regions:
        count = random.randint(8, 15)
        for i in range(count):
            modifier = random.choice(_PHARMACY_MODIFIERS)
            name = f"{region.sigungu}{modifier}약국"
            lat = region.center_lat + random.uniform(-0.01, 0.01)
            lng = region.center_lng + random.uniform(-0.01, 0.01)
            phone = f"02-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
            pharmacies.append(Pharmacy(
                id=next_id,
                hira_code=f"MOCK-{next_id:05d}",
                name=name,
                address_road=f"{region.sido} {region.sigungu} {modifier}로 {random.randint(1, 200)}",
                address_jibun=None,
                region_code=region.code,
                lat=lat,
                lng=lng,
                phone=phone,
                business_hours=random.choice(_BUSINESS_HOURS_TEMPLATES),
            ))
            next_id += 1
    return pharmacies


def generate_drugs() -> list[Drug]:
    return [
        Drug(id=idx, item_seq=item_seq or f"MOCKDRUG-{idx:03d}", name=name, display_name=display_name,
             maker=maker, category=category, form=form, package_unit=package_unit, base_price=base_price)
        for idx, (name, display_name, maker, category, form, package_unit, base_price, item_seq)
        in enumerate(_DRUG_SEED, start=1)
    ]


def generate_users() -> list[AppUserSeed]:
    users = [AppUserSeed(id=1, email="admin@example.com", password_hash=_ADMIN_PASSWORD_HASH,
                          nickname="관리자", role="ADMIN")]
    users += [
        AppUserSeed(id=i + 1, email=f"user{i:02d}@example.com", password_hash=_DUMMY_PASSWORD_HASH,
                    nickname=f"제보자{i:02d}", role="USER")
        for i in range(1, 21)
    ]
    return users


def _sql_str(value: str) -> str:
    """SQL 문자열 리터럴로 변환한다(작은따옴표만 이중화하면 되는 단순 케이스)."""
    return "'" + value.replace("'", "''") + "'"


def _render_sql(regions: list[Region], pharmacies: list[Pharmacy], drugs: list[Drug],
                users: list[AppUserSeed]) -> str:
    lines = [
        "-- 마스터 시드(ROADMAP T-07). 실제 공공데이터 API 인증키가 없어 합성 데이터로 생성했다.",
        "-- 약국 상호·주소는 가상이며 실존 업체와 무관하다.",
        "-- 각 테이블의 자연키(region.code, pharmacy.hira_code, drug.item_seq, app_user.email)에",
        "-- ON CONFLICT DO NOTHING을 걸어 재실행해도 중복이 생기지 않는다(ROADMAP T-07 완료 판정).",
        "-- id를 직접 지정하므로(BIGSERIAL은 SERIAL 컬럼이라 명시적 insert가 그대로 된다) 파일 끝에서 시퀀스를 맞춘다.",
        "",
    ]

    lines.append("-- region")
    lines.append("INSERT INTO region (code, sido, sigungu, center_lat, center_lng) VALUES")
    lines.append(",\n".join(
        f"    ({_sql_str(r.code)}, {_sql_str(r.sido)}, {_sql_str(r.sigungu)}, {r.center_lat}, {r.center_lng})"
        for r in regions
    ) + "\nON CONFLICT (code) DO NOTHING;")
    lines.append("")

    lines.append("-- pharmacy")
    lines.append("INSERT INTO pharmacy (id, hira_code, name, address_road, address_jibun, region_code, "
                  "lat, lng, phone, business_hours, is_active, created_at) VALUES")
    lines.append(",\n".join(
        f"    ({p.id}, {_sql_str(p.hira_code)}, {_sql_str(p.name)}, {_sql_str(p.address_road)}, NULL, "
        f"{_sql_str(p.region_code)}, {p.lat}, {p.lng}, {_sql_str(p.phone)}, "
        f"{_sql_str(json.dumps(p.business_hours, ensure_ascii=False))}::jsonb, {str(p.is_active).lower()}, now())"
        for p in pharmacies
    ) + "\nON CONFLICT (hira_code) DO NOTHING;")
    lines.append("")

    lines.append("-- drug")
    lines.append("INSERT INTO drug (id, item_seq, name, display_name, maker, category, form, package_unit, "
                  "otc_flag, base_price, created_at) VALUES")
    lines.append(",\n".join(
        f"    ({d.id}, {_sql_str(d.item_seq)}, {_sql_str(d.name)}, {_sql_str(d.display_name)}, "
        f"{_sql_str(d.maker)}, {_sql_str(d.category)}, {_sql_str(d.form)}, {_sql_str(d.package_unit)}, "
        f"true, {d.base_price}, now())"
        for d in drugs
    ) + "\nON CONFLICT (item_seq) DO NOTHING;")
    lines.append("")

    lines.append("-- app_user (관리자 1 + 더미 제보자 20명)")
    lines.append("INSERT INTO app_user (id, email, password_hash, nickname, role, status, provider, "
                  "report_count, created_at, updated_at) VALUES")
    lines.append(",\n".join(
        f"    ({u.id}, {_sql_str(u.email)}, {_sql_str(u.password_hash)}, {_sql_str(u.nickname)}, "
        f"{_sql_str(u.role)}, 'ACTIVE', {_sql_str(u.provider)}, 0, now(), now())"
        for u in users
    ) + "\nON CONFLICT (email) DO NOTHING;")
    lines.append("")

    lines.append("-- BIGSERIAL 컬럼에 id를 직접 넣었으니 다음 nextval()이 겹치지 않게 시퀀스를 맞춘다.")
    for table in ("pharmacy", "drug", "app_user"):
        lines.append(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}));"
        )
    lines.append("")

    return "\n".join(lines)


_OUTPUT_PATH = (Path(__file__).resolve().parents[2]
                / "miniproject1-backend" / "src" / "main" / "resources" / "db" / "migration"
                / "V2__seed_master.sql")


def _self_check() -> None:
    """ponytail: 이 모듈이 옳게 동작하는지 확인하는 최소 실행 체크(프레임워크 없음)."""
    regions = generate_regions()
    pharmacies = generate_pharmacies(regions)
    drugs = generate_drugs()
    users = generate_users()

    assert 30 <= len(regions) <= 34, f"region 개수가 예상 밖: {len(regions)}"
    assert len(pharmacies) >= 300, f"pharmacy가 300건 미만: {len(pharmacies)}"
    assert all(p.lat != 0 and p.lng != 0 for p in pharmacies), "좌표가 0인 행이 있다"
    assert len({p.id for p in pharmacies}) == len(pharmacies), "pharmacy id가 중복된다"
    assert len({p.hira_code for p in pharmacies}) == len(pharmacies), "pharmacy hira_code가 중복된다(UNIQUE 제약 위반)"
    assert 30 <= len(drugs) <= 50, f"drug 개수가 예상 밖: {len(drugs)}"
    assert len({d.item_seq for d in drugs}) == len(drugs), "drug item_seq가 중복된다(UNIQUE 제약 위반)"
    assert len(users) == 21, f"app_user가 21명이 아니다: {len(users)}"

    print(f"region {len(regions)}건, pharmacy {len(pharmacies)}건, drug {len(drugs)}건, "
          f"app_user {len(users)}건 생성 확인.")
    return regions, pharmacies, drugs, users


if __name__ == "__main__":
    regions, pharmacies, drugs, users = _self_check()
    sql = _render_sql(regions, pharmacies, drugs, users)
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(sql, encoding="utf-8", newline="\n")
    print(f"작성 완료: {_OUTPUT_PATH}")
