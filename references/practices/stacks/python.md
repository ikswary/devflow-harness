# Python 체크 포인트

- 가변 기본 인자(`def f(x=[])`)
- 넓은 `except Exception:`/`except:`로 오류 삼킴, `pass`만 있는 except
- 파일·네트워크 자원을 `with` 없이 열기, 타임아웃 없는 `requests` 호출
- 문자열 조합 SQL, `subprocess(..., shell=True)`에 외부 입력, `eval`/`pickle.loads` 외부 데이터
- 타임존 없는 `datetime.now()` 비교·저장
- pandas: 체인 인덱싱 대입(`SettingWithCopyWarning`), 행 단위 `iterrows` 대량 처리, dtype 추론으로 인한 코드값 앞자리 0 손실
- 외부 API·스프레드시트 응답 스키마를 검증 없이 인덱싱
- 시크릿을 코드·로그에 기록, `.env`를 커밋 대상에 포함
- 테스트: 실제 외부 API 호출, 시간·난수 고정 안 함, fixture 간 상태 공유
