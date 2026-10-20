#!/usr/bin/env bash
# 사용법: bash detect-stack.sh <프로젝트 경로>
# 프로젝트의 스택, 빌드·테스트 명령, 품질 도구, 배포 단서를 Markdown으로 출력한다.
# node_modules, build, .gradle 등은 건너뛴다(큰 저장소에서 느려지지 않도록 깊이 3으로 제한).
set -u
P="${1:-.}"
cd "$P" 2>/dev/null || { echo "경로 없음: $P"; exit 1; }

PRUNE='-name node_modules -o -name build -o -name .gradle -o -name target -o -name dist -o -name .venv -o -name venv -o -name .git -o -name .idea -o -name out'
f() { find . -maxdepth "${2:-3}" \( $PRUNE \) -prune -o -type f -name "$1" -print 2>/dev/null | sed 's|^\./||' | sort; }
# 목록은 20줄까지만 출력한다(00_recon.md는 모든 블록 담당이 읽으므로 모노레포에서 수백 줄이 되지 않게).
lim() { awk -v n="${1:-20}" 'NR<=n{print} END{if(NR>n) print "  - … 외 " NR-n "개"}'; }
has() { [ -n "$(f "$1" "${2:-3}")" ]; }

echo "# 프로젝트 정찰: $(pwd)"
echo
echo "## Git"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "- 브랜치: $(git branch --show-current 2>/dev/null)"
  echo "- 기본 브랜치 추정: $(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo '알 수 없음')"
  echo "- 커밋 안 된 변경: $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')개 파일"
  echo "- 최근 커밋 스타일:"
  git log --oneline -8 2>/dev/null | sed 's/^/  - /'
else
  echo "- git 저장소 아님"
fi
echo

echo "## 스택과 명령"
GW=""; [ -f gradlew ] && GW="./gradlew"
if has 'build.gradle*'; then
  echo "### Gradle"
  echo "- 빌드 파일:"; f 'build.gradle*' | sed 's/^/  - /' | lim
  mods=$(grep -hoE "include\s*\(?[^)]*" settings.gradle* 2>/dev/null)
  [ -n "$mods" ] && { echo "- 모듈(settings):"; echo "$mods" | sed 's/^/  - /' | lim; }
  [ ! -f settings.gradle ] && [ ! -f settings.gradle.kts ] && [ "$(f 'build.gradle*' | wc -l)" -gt 1 ] && echo "- 주의: 루트 settings 없음 — 모듈별 독립 빌드일 수 있음"
  lang="Java"; has '*.kt' 5 && lang="Kotlin$(has '*.java' 5 && echo ' + Java')"
  echo "- 언어: $lang"
  grep -qlE "org.springframework.boot" $(f 'build.gradle*') 2>/dev/null && echo "- 프레임워크: Spring Boot"
  cmd="${GW:-gradle}"
  echo "- 빌드: \`$cmd build -x test\`"
  echo "- 테스트: \`$cmd test\` (모듈 단위: \`$cmd :{모듈}:test\`, 단일: \`--tests '패키지.클래스'\`)"
  grep -lE "ktlint|detekt|checkstyle|spotless" $(f 'build.gradle*') 2>/dev/null | head -3 | while read -r x; do echo "- 품질 도구 설정 발견: $x ($(grep -oE 'ktlint|detekt|checkstyle|spotless' "$x" | sort -u | tr '\n' ' '))"; done
  if [ -z "$GW" ]; then sub=$(f gradlew 3); if [ -n "$sub" ]; then echo "- 모듈별 gradlew(해당 모듈 디렉터리에서 실행):"; echo "$sub" | sed "s/^/  - /" | lim; else echo "- 주의: gradlew 없음 — 전역 gradle 필요"; fi; fi
fi
if has 'pom.xml' 2; then
  echo "### Maven"
  mv="./mvnw"; [ -f mvnw ] || mv="mvn"
  echo "- 빌드: \`$mv -q package -DskipTests\`, 테스트: \`$mv test\`"
fi
if has 'pyproject.toml' 2 || has 'requirements*.txt' 2 || has 'setup.py' 2; then
  echo "### Python"
  { f 'pyproject.toml' 2; f 'requirements*.txt' 2; } | sed 's/^/- /'
  grep -qs "poetry" pyproject.toml && echo "- 패키지 관리: poetry (\`poetry run pytest\`)"
  grep -qs "\[tool.uv\]\|uv.lock" pyproject.toml || [ -f uv.lock ] && echo "- 패키지 관리: uv (\`uv run pytest\`)"
  { has 'test_*.py' 5 || has '*_test.py' 5; } && echo "- 테스트: \`python -m pytest\`" || echo "- 테스트 파일 못 찾음"
  grep -qs "ruff" pyproject.toml && echo "- 린트: \`ruff check .\`"
  grep -qs "mypy" pyproject.toml && echo "- 타입 검사: \`mypy .\`"
fi
if has 'package.json' 2; then
  echo "### Node"
  f 'package.json' 2 | sed 's/^/- /' | lim
  pm="npm"; [ -f pnpm-lock.yaml ] && pm="pnpm"; [ -f yarn.lock ] && pm="yarn"; [ -f bun.lockb ] && pm="bun"
  echo "- 패키지 관리: $pm"
  [ -f package.json ] && { echo "- scripts:"; sed -n '/"scripts"/,/}/p' package.json | grep -E '^\s*"' | grep -v '"scripts"' | sed 's/^\s*/  - /' | lim; }
  has 'tsconfig.json' 2 && echo "- TypeScript: \`npx tsc --noEmit\`"
fi
has 'go.mod' 2 && echo "### Go" && echo "- 빌드: \`go build ./...\`, 테스트: \`go test ./...\`"
echo

echo "## 테스트 디렉터리"
find . -maxdepth 5 \( $PRUNE \) -prune -o -type d \( -name test -o -name tests -o -name __tests__ \) -print 2>/dev/null | sed 's|^\./|- |' | head -15
echo

echo "## 컨벤션 단서"
for x in .editorconfig CLAUDE.md AGENTS.md CONTRIBUTING.md .eslintrc* eslint.config.* .prettierrc* ruff.toml .pre-commit-config.yaml detekt.yml; do
  ls $x 2>/dev/null | sed 's/^/- /'
done
echo

echo "## 배포 단서"
ls -d .github/workflows/* Jenkinsfile .gitlab-ci.yml Dockerfile* docker-compose*.y*ml serverless.y*ml template.y*ml cdk.json Procfile appspec.yml 2>/dev/null | sed 's/^/- /' | lim
find . -maxdepth 3 \( $PRUNE \) -prune -o \( -name 'Chart.yaml' -o -name 'kustomization.y*ml' -o -name 'deploy*.sh' \) -print 2>/dev/null | sed 's|^\./|- |' | lim
echo "- (없으면 배포 방식 미확인 — 배포 블록에서 사용자에게 확인)"
