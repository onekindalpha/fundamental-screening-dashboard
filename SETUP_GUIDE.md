# 📊 투자 스크리닝 대시보드 설정 가이드

자동화된 피터린치 + 그레이엄 스타일 투자 스크리닝 시스템을 설정하는 방법입니다.

## 🚀 빠른 시작 (5분)

### 1단계: GitHub Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions

**다음 정보를 추가하세요:**

```
DART_API_KEY: 당신의_DART_API_키
```

> **DART API 키 얻기:**
> 1. https://opendart.fss.or.kr/ 방문
> 2. 회원가입 및 로그인
> 3. 공시정보 > API > API 신청
> 4. API 키 발급받기

### 2단계: 파일 업로드

저장소 최상위에 다음 파일들을 업로드:

```
repository/
├── .github/
│   └── workflows/
│       └── screening.yml          # GitHub Actions 워크플로우
├── kr_lynch_screener_one_shot_powerfix_rulefit_mirae_capadj_lynch333_v3_graham_fixed3_narrowdebt.py
├── add_pykrx_timing_checks_bookstyle_preserve_all_tsv_merged.py
├── kospi_codes_manual.txt
├── kosdaq_codes_manual.txt
├── process_screening.py           # 정렬/필터링 스크립트
├── dashboard.py                   # Streamlit 대시보드
└── requirements.txt               # 의존성
```

### 3단계: GitHub Actions 활성화

1. 저장소 → Actions 탭
2. "I understand my workflows, go ahead and enable them" 클릭
3. 성공! ✅

## 📅 실행 스케줄

자동 실행 시간 (한국 시간):

| 시간 | 목적 |
|------|------|
| **오전 6시** | 아침 장 전 스크리닝 |
| **정오 12시** | 점심시간 중간 체크 |
| **저녁 6시** | 저녁 장 마감 후 정리 |

> 모두 공개 저장소 기준으로 **무제한 실행 가능** ✅

## 📊 Streamlit 대시보드 배포

### 로컬에서 먼저 테스트

```bash
# 의존성 설치
pip install -r requirements.txt

# 대시보드 실행
streamlit run dashboard.py
```

브라우저에서 http://localhost:8501 열기

### Streamlit Cloud에 배포 (권장)

1. **Streamlit 계정 생성:** https://streamlit.io/
2. **GitHub와 연동**
3. **대시보드 배포:**
   - Streamlit Cloud 대시보드
   - "New app" 클릭
   - Repository 선택
   - Main file: `dashboard.py`
   - Deploy!

**배포 URL:** `https://[username]-screening.streamlit.app`

### 또는 GitHub Pages (정적)

GitHub Actions에서 HTML 대시보드 자동 생성:

```bash
# requirements.txt에 추가
jupyter-nbconvert
plotly
```

## 🎯 필터링 옵션

대시보드에서 사용 가능한 필터:

### 1. 주당순현금
- **음수:** 위험한 신호 ⚠️
- **필터 기본값:** 0원 이상

### 2. FCF (자유현금흐름)
- **음수:** 현금 흐름 악화
- **필터 기본값:** 0억원 이상

### 3. 단기부채
- **높음:** 단기 유동성 위험
- **필터 기본값:** 제한 없음 (직접 조절)

### 4. 하드웨어 여부
- **Y:** 하드웨어 관련 기업
- **N:** 소프트웨어/서비스 기업
- **필터 기본값:** 전체

## 📈 정렬 우선순위

결과가 다음 순서로 정렬됩니다:

1. **Lynch P/E 배수** ↑ (낮을수록 좋음)
2. **배당감안점수** ↓ (높을수록 좋음)
3. **연간영업이익증가율(3년)** ↓ (높을수록 좋음)
4. **그레이엄 괴리율(3년)** ↓ (낮을수록 좋음)

## 🔧 커스터마이징

### 코스피/코스닥 종목 수정

**kospi_codes_manual.txt:**
```
005930  # 삼성전자
000660  # SK하이닉스
...
```

**kosdaq_codes_manual.txt:**
```
196170  # 캔싱
247540  # 에코프로비엠
...
```

### 실행 시간 변경

**.github/workflows/screening.yml:**
```yaml
schedule:
  - cron: '0 6 * * *'   # 오전 6시 (UTC 21시)
  - cron: '0 12 * * *'  # 정오 12시 (UTC 03시)
  - cron: '0 18 * * *'  # 저녁 6시 (UTC 09시)
```

Cron 변환: https://crontab.guru/

### 필터링 로직 수정

**process_screening.py:**
- `apply_filters()` 함수 수정
- 새로운 필터 조건 추가
- 정렬 우선순위 변경

## 🐛 문제 해결

### 1. GitHub Actions 실패

**로그 확인:**
1. Actions 탭 → 실패한 워크플로우
2. 상세 에러 메시지 확인

**일반적인 원인:**
- DART API 키 잘못됨
- 종목 코드 오류
- 네트워크 타임아웃

### 2. Streamlit 데이터 안 보임

```bash
# 캐시 삭제
rm -rf ~/.streamlit/cache

# 다시 실행
streamlit run dashboard.py
```

### 3. pykrx 타이밍 체크 실패

```bash
# pykrx 재설치
pip install --upgrade pykrx
```

## 📊 데이터 구조

### 입력 데이터 (TSV)

```
종목코드 | 종목명 | 그룹 | Lynch P/E | 배당감안점수 | ... | 비고
005930 | 삼성전자 | 반도체 | 8.5 | 75 | ... | 
```

### 정렬된 출력 (TSV)

```
# 가장 좋은 평가 순서대로 정렬됨
순위 | 종목코드 | 종목명 | Lynch P/E | ... | 주당순현금⚠️ 
1 | 005930 | 삼성전자 | 8.5 | ...
```

## 🔐 보안

### GitHub Secrets 관리

✅ **안전한 방법:**
- GitHub Secrets에만 저장
- 절대 코드에 직접 입력하지 말 것
- 정기적으로 키 교체

❌ **위험한 방법:**
- 코드에 하드코딩
- 환경변수 파일을 커밋
- 공개 채널에 공유

## 📞 지원

문제가 있으면:

1. **GitHub Issues 열기**
2. **에러 메시지 포함**
3. **로그 첨부**

## 🎓 학습 자료

- [Peter Lynch 투자법](https://en.wikipedia.org/wiki/Peter_Lynch)
- [Benjamin Graham 가치투자](https://en.wikipedia.org/wiki/Benjamin_Graham)
- [GitHub Actions 자동화](https://docs.github.com/en/actions)
- [Streamlit 문서](https://docs.streamlit.io)

---

**행운을 빕니다! 🚀**

투자는 신중하게, 분석은 철저하게! 📈
