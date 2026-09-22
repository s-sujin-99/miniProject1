"""가격 제보 시드(price_report) 생성 스크립트 (ROADMAP T-08).

build_master_seed.py가 만드는 pharmacy/drug/app_user 데이터를 그대로 재구성해서 쓴다
(DB에 접속하지 않고 같은 랜덤 시드로 동일한 id를 재현한다).

purchased_at은 "오늘로부터 며칠 전"(age)만 계산하고, 실제 날짜는 SQL의 CURRENT_DATE - age로 미룬다.
Python에서 오늘 날짜를 박아 넣으면 이 파일을 만든 날짜가 아니라 나중에 Flyway로 적용하는 날짜를
기준으로 "최근 분포"가 만들어져야 한다는 취지(ROADMAP T-08 §3)가 깨진다.

실행: python build_price_seed.py
  → miniproject1-backend/src/main/resources/db/migration/V3__seed_prices.sql 생성.
"""
from __future__ import annotations

import random
from pathlib import Path

from build_master_seed import generate_drugs, generate_pharmacies, generate_regions, generate_users

_OUTPUT_PATH = (Path(__file__).resolve().parents[2]
                / "miniproject1-backend" / "src" / "main" / "resources" / "db" / "migration"
                / "V3__seed_prices.sql")

# 통계 초기 계산에 쓸 창 크기(DATABASE.md §3.6). T-10 재계산 서비스는 요청마다 90/180을 고를 수 있지만,
# 시드 초기값은 더 넉넉한 180으로 한 번만 채운다.
_WINDOW_DAYS = 180


def _clamp_price(price: float) -> int:
    """DATABASE.md CHECK(price BETWEEN 100 AND 200000)을 절대 어기지 않도록 방어적으로 자른다."""
    return max(100, min(200000, int(price)))


# 홈 화면 인기 약품 칩(app/page.tsx POPULAR_DRUGS)과 맞춘 목록 — 전국 어디서 이 이름으로
# 검색해도 결과가 나오게 별도로 두껍게 채운다(카탈로그 전체에서 뽑는 무작위 배분은 인기
# 브랜드를 우대하지 않아, 데모 때 실제로 쳐볼 법한 이름이 빈 결과로 나올 수 있다).
_POPULAR_DRUG_KEYWORDS = ["타이레놀", "게보린", "판콜에이", "베아제", "부루펜", "챔프시럽", "훼스탈골드", "판피린큐"]
_POPULAR_TOTAL_REPORTS = 20_000


def _make_reports_for_pairs(pairs, factor, reporter_ids, seen_user_pair_day, next_id, keep_prob=1.0):
    """(약국, 약품) 쌍마다 1~6건의 제보를 만든다. price_report id 카운터를 이어받아 반환한다."""
    reports: list[dict] = []
    for p, d in pairs:
        if keep_prob < 1.0 and random.random() > keep_prob:
            continue
        for _ in range(random.randint(1, 6)):
            user_id = random.choice([None] + reporter_ids)
            age = int(120 * random.random() ** 1.6)  # 최근 쪽에 몰리게(ROADMAP T-08 §3)
            if user_id is not None:
                key = (p.id, d.id, user_id, age)
                if key in seen_user_pair_day:
                    continue  # 실제 앱이라면 중복 제보로 막혔을 조합 — 시드에도 만들지 않는다
                seen_user_pair_day.add(key)

            price = _clamp_price(round(d.base_price * factor[p.id] * random.gauss(1, 0.05), -1))
            reports.append({
                "id": next_id,
                "pharmacy_id": p.id,
                "drug_id": d.id,
                "user_id": user_id,
                "price": price,
                "age": age,
                "flagged": False,
                "flag_reason": None,
            })
            next_id += 1
    return reports, next_id


def generate_price_reports(pharmacies, drugs, users) -> list[dict]:
    """DATABASE.md §6.2 규칙 그대로: 약국별 price_factor, 60% 커버리지, 2% 오타 시뮬레이션.

    약국(전국 확장 시 최대 25,760건) × 의약품(전량 적재 시 최대 4,779건)을 전수 대조하면
    조합이 수천만~수억 건으로 폭발해 마이그레이션 SQL 파일이 커밋 불가능한 크기가 된다
    (GitHub 파일당 100MB 한도). 그래서 (1) 가격 데이터를 가질 약국을 최대 _MAX_PRICED_PHARMACIES
    곳만 무작위로 뽑고, (2) 뽑힌 약국마다 전체 카탈로그가 아니라 무작위 부분집합(취급 품목)만
    대조한다. 나머지 약국은 실제 주소·전화번호는 그대로 유지한 채 "아직 제보가 없는" 상태로
    남는다 — 크라우드소싱 서비스에서 실제로 벌어지는 정상적인 상태이며, 앱은 이미 이 상태를
    "정보 부족"/빈 검색 결과로 처리한다(PRD F3-8, F3-9).

    이어서 _POPULAR_DRUG_KEYWORDS에 해당하는 약은 위 무작위 배분과 별개로, 훨씬 많은 약국에
    걸쳐 추가로 채운다(총 _POPULAR_TOTAL_REPORTS건 목표) — 데모에서 실제로 검색해볼 이름은
    전국 어디서든 결과가 나와야 하기 때문이다.
    """
    reporter_ids = [u.id for u in users if u.role == "USER"]
    factor = {p.id: random.uniform(0.85, 1.25) for p in pharmacies}
    seen_user_pair_day: set[tuple[int, int, int, int]] = set()
    next_id = 1

    _MAX_PRICED_PHARMACIES = 5000
    _ASSORTMENT_RANGE = (15, 35)  # 약국 한 곳이 가격 정보를 가질 법한 취급 품목 수
    priced_pharmacies = random.sample(pharmacies, k=min(len(pharmacies), _MAX_PRICED_PHARMACIES))
    pairs = [
        (p, d)
        for p in priced_pharmacies
        for d in random.sample(drugs, min(len(drugs), random.randint(*_ASSORTMENT_RANGE)))
    ]
    reports, next_id = _make_reports_for_pairs(
        pairs, factor, reporter_ids, seen_user_pair_day, next_id, keep_prob=0.60,
    )

    popular_drugs = [d for d in drugs if any(k in d.display_name for k in _POPULAR_DRUG_KEYWORDS)]
    if popular_drugs:
        # 평균 3.5건/쌍(1~6건 균등분포)을 가정해 목표 건수에 맞춰 약품당 약국 수를 역산한다.
        pharmacies_per_drug = min(len(pharmacies), round(_POPULAR_TOTAL_REPORTS / len(popular_drugs) / 3.5))
        popular_pairs = [
            (p, d)
            for d in popular_drugs
            for p in random.sample(pharmacies, pharmacies_per_drug)
        ]
        popular_reports, next_id = _make_reports_for_pairs(
            popular_pairs, factor, reporter_ids, seen_user_pair_day, next_id,
        )
        reports += popular_reports

    # 전체의 2%는 오타를 낸 것처럼 price를 덮어쓴다 — T-10의 IQR 필터가 걸러내는 걸 보여주는 게 목적이라
    # 대부분은 flagged=false로 남기고, 관리자 화면(T-32) 데모용으로 일부만 flagged=true로 표시한다.
    drug_by_id = {d.id: d for d in drugs}
    outlier_count = round(len(reports) * 0.02)
    for idx in random.sample(range(len(reports)), k=outlier_count):
        r = reports[idx]
        d = drug_by_id[r["drug_id"]]
        multiplier = random.choice([0.3, 3.0])
        r["price"] = _clamp_price(round(d.base_price * multiplier, -1))
        if random.random() < 0.2:
            r["flagged"] = True
            r["flag_reason"] = "OUTLIER_HIGH" if multiplier > 1 else "OUTLIER_LOW"

    return reports


def _render_sql(reports: list[dict]) -> str:
    lines = [
        "-- 가격 제보 시드(ROADMAP T-08). V2__seed_master.sql의 pharmacy/drug/app_user id를 그대로 참조한다.",
        "-- purchased_at은 CURRENT_DATE 기준 상대 일수로 넣는다 — 이 파일을 언제 만들었는지가 아니라",
        "-- 언제 적용하는지를 기준으로 '최근 제보가 많다'는 분포가 만들어져야 한다.",
        "",
        "-- price_report",
        "-- created_at/updated_at은 BaseEntity의 NOT NULL 감사 컬럼 — SEED 제보는 구매일에 제출됐다고 본다.",
        "INSERT INTO price_report (id, pharmacy_id, drug_id, user_id, price, purchased_at, source, "
        "status, flagged, flag_reason, created_at, updated_at) VALUES",
    ]
    rows = []
    for r in reports:
        user_id = "NULL" if r["user_id"] is None else str(r["user_id"])
        flag_reason = "NULL" if r["flag_reason"] is None else f"'{r['flag_reason']}'"
        submitted_at = f"(CURRENT_DATE - {r['age']})::timestamptz"
        rows.append(
            f"    ({r['id']}, {r['pharmacy_id']}, {r['drug_id']}, {user_id}, {r['price']}, "
            f"CURRENT_DATE - {r['age']}, 'SEED', 'ACTIVE', {str(r['flagged']).lower()}, {flag_reason}, "
            f"{submitted_at}, {submitted_at})"
        )
    lines.append(",\n".join(rows) + ";")
    lines.append("")
    lines.append("SELECT setval(pg_get_serial_sequence('price_report', 'id'), "
                  "(SELECT MAX(id) FROM price_report));")
    lines.append("")

    # DATABASE.md §5.2 IQR+중앙값 쿼리를 (pharmacy_id, drug_id) 전체에 대해 한 번에 계산하는 형태로 그대로 쓴다
    # — T-10 재계산 서비스와 로직이 갈라지지 않도록 별도 구현을 만들지 않는다.
    lines.append("-- pharmacy_drug_price_stat 초기 계산 (DATABASE.md §5.2, 전체 쌍에 대해 GROUP BY로 확장)")
    lines.append(f"""INSERT INTO pharmacy_drug_price_stat
    (pharmacy_id, drug_id, rep_price, min_price, max_price, avg_price, report_count,
     last_reported_at, window_days, calculated_at)
WITH valid AS (
    SELECT pharmacy_id, drug_id, price, purchased_at
    FROM price_report
    WHERE status = 'ACTIVE' AND flagged = false AND deleted_at IS NULL
      AND purchased_at >= CURRENT_DATE - {_WINDOW_DAYS}
),
q AS (
    SELECT pharmacy_id, drug_id,
           percentile_cont(0.25) WITHIN GROUP (ORDER BY price) AS q1,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY price) AS q3,
           count(*) AS n
    FROM valid
    GROUP BY pharmacy_id, drug_id
),
trimmed AS (
    SELECT v.pharmacy_id, v.drug_id, v.price, v.purchased_at
    FROM valid v
    JOIN q ON q.pharmacy_id = v.pharmacy_id AND q.drug_id = v.drug_id
    WHERE q.n < 4  -- 4건 미만이면 이상치 제거 생략
       OR v.price BETWEEN q.q1 - 1.5 * (q.q3 - q.q1) AND q.q3 + 1.5 * (q.q3 - q.q1)
)
SELECT
    pharmacy_id, drug_id,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price)::int AS rep_price,
    MIN(price)::int AS min_price,
    MAX(price)::int AS max_price,
    AVG(price)::int AS avg_price,
    COUNT(*)::int AS report_count,
    MAX(purchased_at) AS last_reported_at,
    {_WINDOW_DAYS}::smallint AS window_days,
    now() AS calculated_at
FROM trimmed
GROUP BY pharmacy_id, drug_id;
""")
    return "\n".join(lines)


def _self_check() -> list[dict]:
    """ponytail: 최소 실행 체크. random.seed는 build_master_seed 모듈이 import 시점에 한 번 고정한다."""
    random.seed(20260915)  # 마스터 데이터 재구성용 — 값 자체는 build_master_seed와 동일해야 한다.
    regions = generate_regions()
    pharmacies = generate_pharmacies(regions)
    drugs = generate_drugs()
    users = generate_users()

    random.seed(20260915)  # 가격 생성은 마스터 재구성과 독립된 지점에서 다시 고정한다.
    reports = generate_price_reports(pharmacies, drugs, users)

    assert len(reports) >= 3000, f"price_report가 3000건 미만: {len(reports)}"
    assert len(reports) < 1_000_000, (
        f"price_report가 {len(reports)}건 — 마이그레이션 파일이 git에 커밋하기엔 너무 커진다. "
        "assortment 범위/_MAX_PRICED_PHARMACIES를 줄여라."
    )
    outlier_ratio = sum(1 for r in reports if r["flagged"]) / len(reports)
    assert 0 <= outlier_ratio < 0.02, f"flagged 비율이 예상 밖: {outlier_ratio}"
    assert all(100 <= r["price"] <= 200000 for r in reports), "CHECK(price) 범위를 벗어난 행이 있다"

    print(f"price_report {len(reports)}건 생성 확인 (flagged {sum(1 for r in reports if r['flagged'])}건).")
    return reports


if __name__ == "__main__":
    reports = _self_check()
    sql = _render_sql(reports)
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(sql, encoding="utf-8", newline="\n")
    print(f"작성 완료: {_OUTPUT_PATH}")
