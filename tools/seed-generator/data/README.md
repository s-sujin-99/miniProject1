# 원본 공공데이터 (ROADMAP T-07)

이 디렉토리에 원본 파일을 넣으면 `build_master_seed.py`가 자동으로 합성 데이터 대신
실제 데이터를 사용한다. 파일이 없으면 기존 synthetic 데이터로 조용히 폴백한다.

## 넣어야 할 파일

### `pharmacy_raw.csv` — 약국 원본 데이터
- 출처: [국립중앙의료원_전국 약국 정보 조회 서비스](https://www.data.go.kr/data/15000576/openapi.do)
  또는 [심평원_전국 병의원 및 약국 현황](https://www.data.go.kr/data/15051059/fileData.do) (파일 데이터 권장)
- 인코딩: UTF-8(BOM 있어도 무방) CSV
- 필요한 컬럼(헤더 이름이 달라도 `build_master_seed.py`의 `_PHARMACY_COLUMN_ALIASES`에
  등록된 별칭과 일치하면 자동 인식): 기관종별(약국 구분용, 선택), 요양기관명, 시도명, 시군구명,
  도로명주소/지번주소, 전화번호, 위도, 경도
- 실제 헤더가 별칭 목록에 없으면 스크립트가 **명확한 에러**로 어떤 컬럼을 못 찾았는지 알려준다.
  그때 `build_master_seed.py`의 `_PHARMACY_COLUMN_ALIASES`에 실제 헤더명을 추가한다.
- 서울/경기 일부 외 지역, 좌표 0/빈 값인 행은 자동으로 제외된다.
- 필터링 후 300건 미만이면 자동으로 synthetic 데이터로 폴백한다(경고 출력).

### `drug_raw.json` — 의약품 원본 데이터
- `DATA_GO_KR_API_KEY` 환경변수를 설정하고 `python fetch_drug_api.py`를 실행하면 자동 생성된다.
  파일을 직접 여기 넣어도 된다.
- 이 파일이 생기면 실제 필드를 보고 `build_master_seed.py`의 `generate_drugs()`에
  매핑 로직을 채운다(현재는 아직 미구현 — 추측 매핑을 박아넣지 않기 위해 의도적으로 비워둠).

## 실행 순서

```bash
# 1) 의약품 API 원본 캐싱 (data.go.kr에서 발급받은 서비스키를 넣는다 — 이 파일에 직접 적어두지 말 것)
DATA_GO_KR_API_KEY=발급받은키 python fetch_drug_api.py

# 2) pharmacy_raw.csv를 이 디렉토리에 넣은 뒤
python build_master_seed.py
```
