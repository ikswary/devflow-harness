# Spring · Kotlin/Java 체크 포인트

## 트랜잭션·JPA
- `@Transactional`이 같은 클래스 내부 호출(self-invocation)로 적용되지 않는 경우
- `readOnly = true` 서비스에서 쓰기 발생, 쓰기 메서드에 트랜잭션 누락
- 지연 로딩 연관을 트랜잭션 밖(컨트롤러, 직렬화)에서 접근 → `LazyInitializationException` 또는 N+1
- `@ManyToOne`/`@OneToMany` 기본 fetch, 컬렉션 fetch join + 페이지네이션(메모리 페이징 경고)
- 더티 체킹에 기대는 수정이 영속 상태가 아닌 엔티티에 일어남
- 낙관적 락(`@Version`) 필요한 동시 수정, 재고·잔액 같은 경합 자원
- `equals/hashCode`를 가변 필드나 연관으로 구현한 엔티티, Kotlin `data class` 엔티티

## 웹·API
- 요청 DTO 검증(`@Valid`, 제약 어노테이션) 누락, Kotlin에서 `@field:` 사용 대상 누락
- 예외가 전역 핸들러(`@RestControllerAdvice`)의 기존 규약과 다른 응답을 만듦
- 엔티티를 그대로 응답으로 반환(순환 참조, 내부 필드 노출)
- 인가: 경로·메서드 보안 설정 누락, 리소스 소유자 확인 누락(IDOR)

## Kotlin
- `!!` 남용, 플랫폼 타입(Java 반환값) null 처리
- `lateinit` 초기화 전 접근 가능 경로
- 코루틴: 블로킹 호출을 `Dispatchers.Default`에서 실행, 구조적 동시성 밖 `GlobalScope`
- `open`/all-open 플러그인 없이 프록시 대상 클래스

## Java
- `Optional.get()` 무검사, 컬렉션 반환에 null
- 가변 static 상태, 스레드 안전하지 않은 필드를 가진 싱글톤 빈

## 테스트
- `@SpringBootTest` 남용으로 느린 테스트 — 슬라이스(`@WebMvcTest`, `@DataJpaTest`)로 충분한가
- MockK/Mockito로 검증 대상 자체를 모킹
- H2로만 테스트해 실제 DB 방언 차이(JSON, 락, 네이티브 쿼리)를 놓침
- 시간 의존 로직에 `Clock` 주입 없음
