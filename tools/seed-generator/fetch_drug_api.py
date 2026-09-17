"""식약처 의약품개요정보(e약은요) OpenAPI 원본 응답을 내려받아 캐싱한다 (ROADMAP T-07).

실행 전: 공공데이터포털(data.go.kr)에서 활용신청 후 발급받은 서비스키(디코딩 키)를
환경변수 DATA_GO_KR_API_KEY 에 넣는다.
  발급: https://www.data.go.kr/data/15075057/openapi.do

실행: DATA_GO_KR_API_KEY=발급받은키 python fetch_drug_api.py
  → tools/seed-generator/data/drug_raw.json 에 원본 응답을 그대로 저장한다.

주의: 이 스크립트는 원본을 "있는 그대로" 캐싱만 한다. 응답 필드 구조(category/package_unit
같은 build_master_seed.py의 Drug 필드에 대응하는 실제 키 이름)는 API 문서만으로 확신할 수
없으므로, drug_raw.json이 생긴 뒤 실제 필드를 보고 build_master_seed.py의 매핑 로직을
채워 넣는다 — 추측으로 먼저 매핑을 박아넣지 않는다(ponytail).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_SERVICE_KEY_ENV = "DATA_GO_KR_API_KEY"
# ponytail: 정확한 엔드포인트/오퍼레이션명은 실제 활용신청 화면에서 재확인 필요.
# 응답이 404/오류코드면 여기 URL을 data.go.kr 문서에 나온 값으로 바로 고친다.
_BASE_URL = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
_OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "drug_raw.json"
_NUM_OF_ROWS = 500  # API가 허용하는 페이지당 최대 건수(에러 메시지로 확인됨)


def fetch_page(service_key: str, page_no: int, num_of_rows: int = _NUM_OF_ROWS) -> dict:
    # 공공데이터포털 서비스키는 이미 URL-인코딩된("Encoding" 방식) 채로 발급되는 경우가 많다.
    # urlencode()에 그대로 넣으면 %가 %25로 다시 인코딩되는 이중 인코딩 버그가 생기므로,
    # serviceKey만 인코딩 없이 직접 붙이고 나머지 파라미터만 urlencode한다.
    other_params = urllib.parse.urlencode({
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "type": "json",
    })
    url = f"{_BASE_URL}?serviceKey={service_key}&{other_params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(service_key: str) -> list[dict]:
    """totalCount를 보고 페이지를 끝까지 순회해 전체 items를 모은다."""
    first = fetch_page(service_key, page_no=1)
    if first["header"]["resultCode"] != "00":
        raise RuntimeError(f"API 오류: {first['header']['resultMsg']}")

    total = first["body"]["totalCount"]
    items = list(first["body"]["items"])
    page_count = -(-total // _NUM_OF_ROWS)  # ceil division
    for page_no in range(2, page_count + 1):
        page = fetch_page(service_key, page_no=page_no)
        items.extend(page["body"]["items"])
    return items


def main() -> None:
    service_key = os.environ.get(_SERVICE_KEY_ENV)
    if not service_key:
        print(f"환경변수 {_SERVICE_KEY_ENV} 가 없다. "
              f"https://www.data.go.kr/data/15075057/openapi.do 에서 발급받은 서비스키를 설정하라.",
              file=sys.stderr)
        sys.exit(1)

    try:
        items = fetch_all(service_key)
    except urllib.error.HTTPError as e:
        print(f"API 호출 실패: HTTP {e.code} {e.reason}. 엔드포인트/서비스키를 확인하라.",
              file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"API 호출 실패: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {_OUTPUT_PATH} ({len(items)}건)")
    print("다음 단계: drug_raw.json의 실제 필드를 확인하고 "
          "build_master_seed.py의 실데이터 매핑 로직을 채운다.")


if __name__ == "__main__":
    main()
