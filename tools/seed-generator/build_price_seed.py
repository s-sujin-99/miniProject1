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


def generate_price_reports(pharmacies, drugs, users) -> list[dict]:
    """DATABASE.md §6.2 규칙 그대로: 약국별 price_factor, 60% 커버리지, 2% 오타 시뮬레이션."""
    reporter_ids = [u.id for u in users if u.role == "USER"]
    factor = {p.id: random.uniform(0.85, 1.25) for p in pharmacies}

    reports: list[dict] = []
    # uq_report_user_pair_day(V1__init.sql)가 "같은 사용자·같은 (약국,약품)·같은 날"을 막는다 —
    # 시드도 실제 앱과 같은 규칙을 지켜야 한다. user_id가 있는 제보만 (pharmacy, drug, user, day) 단위로 추적한다.
    seen_user_pair_day: set[tuple[int, int, int, int]] = set()
    next_id = 1
    for p in pharmacies:
        for d in drugs:
            if random.random() > 0.60:  # 커버리지 60% — 전부 채우면 현실감이 없다
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
