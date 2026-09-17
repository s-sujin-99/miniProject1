"""국립중앙의료원 전국 약국 정보 조회 서비스에서 원본 응답을 내려받아 캐싱한다 (ROADMAP T-07).

실행 전: 공공데이터포털에서 활용신청 후 발급받은 서비스키를 환경변수 DATA_GO_KR_API_KEY 에 넣는다.
  발급: https://www.data.go.kr/data/15000576/openapi.do

실행: DATA_GO_KR_API_KEY=발급받은키 python fetch_pharmacy_api.py
  → tools/seed-generator/data/pharmacy_raw.json 에 build_master_seed.py의 _REGION_SEED 32개
  지역(Q0=시도/Q1=시군구)별 약국 목록을 모아 저장한다. Q0/Q1로 이미 지역을 좁혀 받으므로
  ROADMAP T-07 §3의 "대상 지역을 좁힌다" 필터를 API 호출 단계에서 만족시킨다.

엔드포인트: getParmacyListInfoInqire (data.go.kr 활용신청 페이지에서 확인한 실제 오퍼레이션명).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from build_master_seed import _REGION_SEED  # 지역 목록 재사용(ladder) — 중복 정의하지 않는다.

_SERVICE_KEY_ENV = "DATA_GO_KR_API_KEY"
_BASE_URL = "https://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyListInfoInqire"
_OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "pharmacy_raw.json"
_NUM_OF_ROWS = 300


def fetch_region(service_key: str, sido: str, sigungu: str) -> list[dict]:
    """한 시군구의 약국 전체를 페이지네이션으로 모아 반환한다."""
    items: list[dict] = []
    page_no = 1
    while True:
        params = urllib.parse.urlencode({
            "Q0": sido, "Q1": sigungu, "pageNo": str(page_no), "numOfRows": str(_NUM_OF_ROWS), "_type": "json",
        })
        url = f"{_BASE_URL}?serviceKey={service_key}&{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        header = data["response"]["header"]
        if header["resultCode"] != "00":
            raise RuntimeError(f"API 오류: {header['resultMsg']}")

        body = data["response"]["body"]
        total = body.get("totalCount", 0)
        page_items = (body.get("items") or {}).get("item", [])
        if isinstance(page_items, dict):  # 결과 1건이면 배열이 아니라 객체로 온다
            page_items = [page_items]
        items.extend(page_items)

        if not page_items or page_no * _NUM_OF_ROWS >= total:
            break
        page_no += 1
    return items


def main() -> None:
    service_key = os.environ.get(_SERVICE_KEY_ENV)
    if not service_key:
        print(f"환경변수 {_SERVICE_KEY_ENV} 가 없다. "
              f"https://www.data.go.kr/data/15000576/openapi.do 에서 발급받은 서비스키를 설정하라.",
              file=sys.stderr)
        sys.exit(1)

    result: dict[str, list[dict]] = {}
    for sido, sigungu, _lat, _lng in _REGION_SEED:
        key = f"{sido} {sigungu}"
        try:
            items = fetch_region(service_key, sido, sigungu)
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as e:
            print(f"{key}: 실패 - {e}", file=sys.stderr)
            continue
        result[key] = items
        print(f"{key}: {len(items)}건")

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in result.values())
    print(f"저장 완료: {_OUTPUT_PATH} (총 {total}건, {len(result)}개 지역)")


if __name__ == "__main__":
    main()
