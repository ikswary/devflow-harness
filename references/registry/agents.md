## 3. 에이전트 8

| 에이전트 | role | model | tools | short | required_tools | has_def_version |
| --- | --- | --- | --- | --- | --- | --- |
| requirements-writer | writer | opus | Read, Grep, Glob, Bash, Write, Edit | req | — | — |
| cause-writer | writer | fable | Read, Grep, Glob, Bash, Write, Edit | cause | — | — |
| design-writer | writer | opus | Read, Grep, Glob, Bash, Write, Edit | design | — | — |
| code-writer | writer | opus | Read, Grep, Glob, Bash, Write, Edit | code | — | — |
| verify-writer | writer | opus | Read, Grep, Glob, Bash, Write, Edit | verify | — | — |
| release-writer | writer | sonnet | Read, Grep, Glob, Bash, Write, Edit | release | — | — |
| read-judge | judge | opus | Read, Grep, Glob, Bash, Write | rjudge | Write | 예 |
| run-judge | judge | sonnet | Read, Grep, Glob, Bash, Edit, Write | xjudge | Write | 예 |

