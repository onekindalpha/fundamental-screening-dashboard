# 📈 피터린치 + 그레이엄 투자 스크리닝 자동화 시스템

> **매일 자동으로 KOSPI 200 & KOSDAQ 150의 유망주를 스크리닝하는 대시보드**

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ 주요 특징

### 🤖 자동화
- **GitHub Actions**: 매일 오전 6시, 정오 12시, 저녁 6시 자동 실행
- **Zero Manual Work**: 한번 설정 후 매일 자동 갱신
- **공개 저장소**: 무제한 실행 가능 ✅

### 📊 분석 엔진
- **피터린치 스타일**: P/E 배수, 배당금, 영업이익 증가율
- **그레이엄 스타일**: 내재가치, 괴리율, 안전마진
- **하이브리드 정렬**: 두 가지 방식을 결합한 우선순위

### 🎯 실시간 대시보드
- **Streamlit 웹 대시보드**: 아름다운 UI로 언제든 확인
- **탭 분리**: KOSPI / KOSDAQ 별도 분석
- **동적 필터링**: 주당순현금, FCF, 단기부채, 하드웨어 필터
- **기업 상세정보**: 클릭 후 재무 지표 한눈에 보기

### 📈 똑똑한 필터링
```
정렬 우선순위:
1️⃣  Lynch P/E 배수 (낮을수록 좋음 ↑)
2️⃣  배당감안점수 (높을수록 좋음 ↓)
3️⃣  영업이익증가율 3년 (높을수록 좋음 ↓)
4️⃣  그레이엄 괴리율 3년 (낮을수록 좋음 ↓)

필터링 로직:
⚠️  주당순현금 < 0: 비고에 표시
⚠️  FCF < 0: 비고에 표시
🔍  단기부채: 별도 필터 (종합판정 제외)
🏭 하드웨어: 종합판정에 포함
```

---

## 🚀 5분 안에 시작하기

### 1단계: 저장소 클론

```bash
git clone https://github.com/당신의계정/stock-screening.git
cd stock-screening
```

### 2단계: GitHub Secrets 설정

1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **"New repository secret"** 클릭
3. 다음 정보 입력:

```
Name:  DART_API_KEY
Value: 당신의_DART_API_키
```

> **DART API 키 얻기:** https://opendart.fss.or.kr/ → 회원가입 → API 신청

### 3단계: GitHub Actions 활성화

1. 저장소 → **Actions** 탭
2. "I understand my workflows, go ahead and enable them" 클릭
3. ✅ 완료!

### 4단계: Streamlit 대시보드 배포

**로컬 테스트:**
```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

**클라우드 배포:**
1. https://streamlit.io/ → 계정 생성
2. GitHub와 연동
3. "New app" → repository 선택 → `dashboard.py` 배포
4. 완료! 🎉

---

## 📅 자동 실행 스케줄

| 시간 | 타임존 | 용도 |
|------|--------|------|
| **오전 6시** | KST (UTC+9) | 아침 장 전 스크리닝 |
| **정오 12시** | KST (UTC+9) | 점심시간 중간 체크 |
| **저녁 6시** | KST (UTC+9) | 저녁 장 마감 후 정리 |

> 💡 **팁**: 시간을 변경하려면 `.github/workflows/screening.yml` 수정

---

## 📂 파일 구조

```
repository/
├── .github/workflows/
│   └── screening.yml                          # GitHub Actions 워크플로우
│
├── kr_lynch_screener_one_shot_powerfix_...py  # 피터린치+그레이엄 스크리너
├── add_pykrx_timing_checks_bookstyle_...py    # 타이밍 체크 (Ma30, 저항선, 거래량)
├── process_screening.py                       # 정렬/필터링 처리
├── dashboard.py                               # Streamlit 대시보드
│
├── kospi_codes_manual.txt                     # KOSPI 200 종목 코드
├── kosdaq_codes_manual.txt                    # KOSDAQ 150 종목 코드
│
├── results/                                   # 스크리닝 결과 저장
│   ├── kospi_screening_20240427_120000.tsv
│   └── kosdaq_screening_20240427_120000.tsv
│
├── requirements.txt                           # Python 의존성
├── SETUP_GUIDE.md                             # 상세 설정 가이드
└── README.md                                  # 이 파일
```

---

## 🎯 사용 방법

### 기본 사용법

1. **대시보드 열기**: https://[username]-screening.streamlit.app
2. **시장 선택**: KOSPI 또는 KOSDAQ
3. **필터 적용**: 원하는 조건으로 필터링
4. **기업 클릭**: 상세 재무 정보 보기

### 필터링 옵션

#### 주당순현금 필터
```
- 양수: 건강한 현금 흐름
- 음수: 위험한 신호 ⚠️
기본값: 0원 이상
```

#### FCF (자유현금흐름) 필터
```
- 양수: 순이익 + 감가상각 - 투자 > 0
- 음수: 현금 흐름 악화 ⚠️
기본값: 0억원 이상
```

#### 단기부채 필터
```
- 높음: 단기 유동성 위험
- 낮음: 안정적
기본값: 제한 없음
```

#### 하드웨어 필터
```
- Y: 하드웨어 관련 기업
- N: 소프트웨어/서비스
- 전체: 상관없음
```

---

## 🔍 스크리닝 로직

### 1단계: 피터린치 + 그레이엄 평가

```
입력 데이터:
├─ OpenDART (재무제표)
│  └─ 매출, 영업이익, 순이익
├─ Yahoo Finance (주가)
│  └─ 현재가
└─ 배당금
   └─ 연간 배당금

계산:
├─ Lynch P/E = 현재가 / EPS
├─ 배당감안점수 = 배당수익률 + 성장률
├─ 영업이익증가율(3년) = (현재 - 3년전) / 3년전
└─ Graham 괴리율 = 시가 / 내재가치
```

### 2단계: 타이밍 체크 (pykrx)

```
시장상승세 확인 (KOSPI/KOSDAQ)
├─ 시장 MA30 상향식 (주간)
└─ 주간 고점 경신

섹터상승세 확인 (동일 그룹 바스켓)
├─ 그룹 내 평균 MA30 상향식
└─ 그룹 내 평균 고점 경신

종목 타이밍 확인
├─ MA30 위 거래 ✅
├─ MA30 우상향 ✅
├─ 저항선 돌파 (최근 스윙 고점)
├─ 거래량 급증 ✅
└─ 늦은 진입 아님 ✅
```

### 3단계: 정렬 & 필터링

```
정렬:
1. Lynch P/E ↑
2. 배당감안점수 ↓
3. 영업이익증가율 ↓
4. Graham 괴리율 ↓

필터링:
⚠️  주당순현금 < 0 → 비고
⚠️  FCF < 0 → 비고
🔍  단기부채 → 별도 필터
🏭 하드웨어 → 포함/제외
```

---

## 📊 출력 데이터 형식

### TSV 구조

```
종목코드 | 종목명 | 그룹 | Lynch P/E | 배당감안점수 | 영업이익증가율(3년) | Graham괴리율(3년) | ... | 비고
─────────────────────────────────────────────────────────────────────────────────────────────────
005930 | 삼성전자 | 반도체 | 8.5 | 75 | 12.3 | 0.85 | ... | 
000660 | SK하이닉스 | 반도체 | 9.2 | 68 | 8.5 | 0.92 | ... | 주당순현금⚠️
```

### 비고 필드 의미

```
⚠️  주당순현금⚠️   → 주당순현금이 음수 (위험)
⚠️  FCF⚠️          → 자유현금흐름이 음수
✅  깨끗함           → 특별한 주의사항 없음
🔍  [타이밍]        → MA30/저항선/거래량 분석 결과
```

---

## 🛠️ 커스터마이징

### 1. 종목 추가/제거

**kospi_codes_manual.txt:**
```
005930  # 삼성전자
000660  # SK하이닉스
...
```

### 2. 실행 시간 변경

**.github/workflows/screening.yml:**
```yaml
schedule:
  - cron: '0 6 * * *'   # 오전 6시
  - cron: '0 12 * * *'  # 정오
  - cron: '0 18 * * *'  # 저녁
```

Cron 도움: https://crontab.guru/

### 3. 필터 로직 수정

**process_screening.py:**
```python
# 예: FCF 음수 필터 추가
if fcf < 0:
    flags.append('FCF⚠️')
```

---

## 🐛 문제 해결

### GitHub Actions 실패

**확인 사항:**
1. ✅ DART API 키가 맞나?
2. ✅ 종목 코드가 유효한가?
3. ✅ 네트워크 연결이 되나?

**로그 보기:**
- Actions 탭 → 워크플로우 → 상세 로그

### Streamlit 데이터 안 보임

```bash
# 캐시 삭제 후 재실행
rm -rf ~/.streamlit/cache
streamlit run dashboard.py
```

### pykrx 오류

```bash
# 최신 버전으로 업그레이드
pip install --upgrade pykrx
```

---

## 📈 성능 최적화

### API 호출 최소화
- ✅ 캐싱 (24시간)
- ✅ 배치 처리
- ✅ Rate limiting

### 대시보드 속도
- ✅ Streamlit 캐싱
- ✅ 청크 로딩
- ✅ 인덱스 최적화

---

## 📚 학습 자료

### 피터린치 (Peter Lynch)
- 📖 "Beating the Street" (주식에서 이기는 방법)
- 📖 "One Up on Wall Street"
- 🎯 핵심: 저 P/E + 배당금 + 성장성

### 벤자민 그레이엄 (Benjamin Graham)
- 📖 "The Intelligent Investor"
- 📖 "Security Analysis"
- 🎯 핵심: 내재가치 < 시가 + 안전마진

### 기술 자료
- 🔗 [GitHub Actions Docs](https://docs.github.com/en/actions)
- 🔗 [Streamlit Docs](https://docs.streamlit.io)
- 🔗 [DART API](https://opendart.fss.or.kr/)
- 🔗 [pykrx](https://github.com/sharebook-kr/pykrx)

---

## ⚖️ 면책 조항

> 📢 **이 도구는 정보 제공 목적입니다.**
>
> - 투자 조언이 아닙니다
> - 과거 성과는 미래를 보장하지 않습니다
> - 항상 본인의 분석과 판단으로 투자 결정하세요
> - 손실 위험이 있습니다
> - 전문가 상담을 권장합니다

---

## 📞 지원

문제나 제안이 있으시면:

1. **GitHub Issues 열기**
2. **에러 메시지 포함**
3. **재현 방법 설명**

---

## 📜 라이선스

MIT License - 자유롭게 사용하세요! 🎉

---

## 🙏 감사의 말

- **DART**: 한국 기업 재무 데이터
- **Yahoo Finance**: 국제 주가 데이터
- **pykrx**: 한국 주식 시장 데이터
- **Streamlit**: 아름다운 대시보드 플랫폼

---

**Happy Investing! 📈**

```
 ____  _             _    _____           _____
|  _ \| |           | |  |  ___|         |  ___|
| |_) | | ___   ___ | |  | |___ ___  ___| |___ ___
|  _ <| |/ _ \ / _ \| |  |  ___|/ __|/ _ \  ___|/ _ \
| |_) | | (_) | (_) | |  | |___| (__| (_) | |___| (_) |
|____/|_|\___/ \___/|_|  |_____|\___|\___|_____|\___|

+ Graham Value Screening = 🚀
```

**Start investing smarter today!** 🎯
