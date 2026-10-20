# Node · TypeScript 체크 포인트

- `await` 누락된 Promise(떠 있는 Promise), `forEach` 안의 `async` 콜백
- 처리되지 않은 reject, try/catch가 동기 코드만 감쌈
- `any`/타입 단언(`as`)으로 검증 우회, 외부 입력을 스키마(zod 등) 검증 없이 사용
- `==` 비교, falsy 값(0, '') 검사 실수
- 경로 조합에 사용자 입력(경로 순회), 템플릿 문자열 SQL, `child_process.exec`에 외부 입력
- React: 의존성 배열 누락·과다, 렌더 중 상태 변경, key로 인덱스 사용 후 재정렬
- 환경 변수를 클라이언트 번들에 노출(`NEXT_PUBLIC_`, `VITE_` 접두사 확인)
- 테스트: 타이머·네트워크 모킹 누락, 스냅샷만 있는 테스트
