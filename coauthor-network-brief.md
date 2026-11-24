# 개인 공저자 네트워크 구현 요청

Kwan-Young Bak이 본인만 열어 보는 공저자 네트워크를 새 private 저장소 `kybak90/coauthor-network`에 구현해 줘. 평소처럼 연구실 홈페이지의 논문 목록을 고치면 그래프가 자동으로 갱신되어야 한다. 실제 데이터 수집, 인터랙티브 화면, 테스트, 자동 배포 workflow를 하나의 PR로 준비해 줘. 로컬에서 실행하는 명령과 배포 시 계정 소유자가 한 번 설정할 사항을 README에 적어 줘.

이 작업지시서는 저장소 최상위에서 `README.md` 옆에 `coauthor-network-brief.md`라는 파일로 보관해 줘. 내가 첫 작업 메시지로 본문을 붙여넣어 전달했다면 해당 파일도 첫 PR에 포함해 줘.

## 1. 홈페이지에서 읽을 데이터

연구실 홈페이지 저장소 `kybak90/kybak90.github.io`의 `main`이 기준이다. 두 파일은 같은 커밋에서 읽고, 공개 저장소에는 읽기 권한만 사용해 줘. 현재 홈페이지가 공개하는 범위는 selected publications와 work in progress다. [연구실 Research 페이지](https://kybak90.github.io/publications/)

| 입력 | 집계 규칙 |
| --- | --- |
| [게재 실적 원본](https://github.com/kybak90/kybak90.github.io/blob/main/_bibliography/papers.bib) | 학술지 논문과 AAAI 같은 정규 학술대회에 채택된 논문을 포함한다. Accepted/in press, online first, 최종 게재는 모두 첫 번째 보기에 포함한다. 별도의 상태가 명시되지 않은 홈페이지 게재 논문은 이 그룹에 둔다. |
| [진행 중 원고 원본](https://github.com/kybak90/kybak90.github.io/blob/main/_pages/publications.md) | Work in Progress 섹션에서 원고별 영문 제목과 전체 저자 목록을 읽는다. 일부 저자는 클릭할 때 보여 주는 문자열에 있으므로 실행 없이 텍스트만 추출한다. `1 more author`나 `et al.`을 사람으로 만들지 않는다. |

두 보기와 논문 표에 같은 포함 기준을 적용한다. 책, 보고서(연구·기술보고서 포함), 패키지 릴리스(CRAN·PyPI 등), arXiv에만 공개된 프리프린트는 모두 제외한다. 이 구분은 BibTeX 항목 유형이 `@article`이어도 적용한다. SoftwareX나 The R Journal에 실린 소프트웨어 논문은 포함한다. arXiv 버전이 있는 연구가 학술지나 정규 학술대회에 채택되면 정식 논문만 한 편으로 센다.

사람마다 내부 ID 하나와 대표 영문 이름을 둔다. 주인공의 그래프 표기는 `Kwan-Young Bak`이다. 본인이 사용하는 이름 `Kwanyoung Park`도 같은 사람에 연결하며 BibTeX의 `Bak, Kwan-Young`, `Park, Kwanyoung` 순서도 인식한다. 홈페이지에 싣지 않은 원고나 확인된 별칭은 private 저장소의 작은 수동 보완 파일에 기록할 수 있게 해 줘. 외부 색인의 동명이인 후보는 ORCID, 기존 논문 DOI 또는 확인된 제목·공저자 조합으로 식별한다.

HSSC 논문 DOI `10.1057/s41599-026-08463-7`은 이름 처리의 실제 사례다. 홈페이지에서는 다섯 번째 저자가 `Bak, Kwan-Young`이고 출판사 표기는 `Kwanyoung Park`다. 이 DOI의 다섯 번째 저자에 출판 표기를 보관해 표에서 `Kwanyoung Park`로 보여 주고, 그래프와 편수 계산에는 `Kwan-Young Bak`의 내부 ID를 사용해 줘. 같은 DOI가 누락 후보 목록에 다시 나타나도 한 논문이다. [출판사 저자 목록](https://www.nature.com/articles/s41599-026-08463-7)

같은 논문은 상태가 바뀌거나 온라인 출판 뒤 권·호가 붙어도 한 편이다. DOI가 있으면 우선 사용하고, 없으면 정규화한 제목과 저자 정보를 대조한다. 제목이 바뀌어 판정이 모호한 경우 보완 파일에서 같은 논문으로 지정할 수 있어야 한다. 실제 원본에서 `bak2025RKHS-lb`는 서로 다른 두 논문의 BibTeX 키다. 파서가 같은 키의 두 번째 레코드를 버리는 경우까지 테스트해 줘.

## 2. 네트워크와 화면

- 무방향 그래프로 그린다. 한 논문에 A, B, C가 참여하면 A–B, A–C, B–C에 각각 1을 더한다. 같은 두 사람은 한 개의 선으로 연결하고 선 굵기는 선택한 모드의 고유 논문 편수에 따라 증가한다. 단독 논문은 한 편으로 집계하고 저자 노드는 유지하며 자기 자신으로 연결되는 선은 만들지 않는다.
- 첫 버전의 모집단은 Kwan-Young Bak이 참여한 논문이다. 그 안에 함께 등장하는 공저자들 간의 선도 모두 만든다. 교수님이 참여하지 않은 공저자들의 다른 논문은 향후 확장 범위로 둔다.
- 첫 화면에서 Kwan-Young Bak을 중앙에 둔다. 노드를 직접 끌어 옮길 수 있고, 사람을 선택해 그 사람을 중심으로 다시 볼 수 있어야 한다. 드래그한 좌표는 같은 브라우저에서 복원하고 기본 배치로 돌아갈 수 있게 한다.
- 상단 스위치는 `Accepted & published`와 `Include ongoing` 두 상태로 한다. 바꾸면 해당 모드의 저자, 선, 편수, 논문 표가 함께 갱신된다. 두 모드에 공통인 사람들의 위치는 가급적 유지한다. 열어 둔 탭에서도 다시 활성화될 때와 가벼운 주기 확인 시 새 데이터 버전을 불러온다. 사용자가 잡아 놓은 좌표와 현재 모드를 보존한다.
- 밝은 배경, 읽기 쉬운 영문 이름, 한 가지 강조색을 사용한다. 다기관 임상 논문처럼 저자가 많은 경우에는 선택한 사람의 연결을 강조하고 나머지 선은 옅게 그린다. 화면 대부분은 그래프에 쓴다.
- 서버에서 매번 그래프를 계산할 필요는 없다. 빌드 시 데이터 파일을 생성하고, 브라우저에서 Cytoscape.js 등으로 렌더링하는 정적 앱이면 충분하다.

### 그래프 아래의 논문 표

그래프와 표는 같은 논문 ID와 저자 ID를 공유한다. 그래프 바로 아래에 기본으로 펼쳐진 `Papers` 패널을 두고, 현재 모드에 포함된 모든 연구를 한 편당 한 행으로 표시한다. 단독 논문도 한 행을 차지한다. 표의 본문만 스크롤할 수 있게 해 마지막 행을 선택해도 위의 그래프가 눈에 들어오도록 한다. 패널은 접을 수 있고, 작은 화면에서도 선택 결과와 그래프를 함께 볼 수 있게 높이를 조정한다.

| 열 | 표시 내용 |
| --- | --- |
| Title | 연구의 전체 영문 제목 |
| Journal / Venue | 학술지명 또는 정규 학술대회명. 진행 중 원고의 셀에는 `Ongoing`을 표시 |
| Authors | 논문에 실린 순서대로 적은 전체 영문 저자명. 줄바꿈을 허용하고, 게재 논문에는 확인된 출판 표기, 진행 중 원고에는 홈페이지 원고의 표기를 사용 |

표의 행을 클릭하면 선택된 행과 해당 논문의 저자 노드 전부, 그 저자들 사이에서 이 논문이 기여한 모든 선을 동시에 강조한다. 다른 노드와 선은 옅어지고 현재 모드의 편수를 나타내는 선 굵기와 사용자가 잡아 놓은 노드 위치는 유지된다. 단독 논문은 해당 저자 노드만 강조한다. 다른 행을 누르면 선택이 교체되고, 현재 선택을 해제하면 전체 그래프로 돌아간다. 모드를 바꿔도 해당 논문이 남아 있으면 선택을 유지하고, 목록에서 빠지면 강조도 해제한다.

반대로 그래프에서 선을 클릭하면 같은 패널에 해당 두 사람이 같이 쓴 논문들을 모아 보여 준다. `All papers`로 현재 모드의 전체 목록에 바로 돌아갈 수 있게 한다.

## 3. 모니터링과 비공개 배포

| 계기 | 동작 |
| --- | --- |
| 홈페이지의 두 원본 파일 변경 | 홈페이지 저장소의 `main`에 해당 경로가 push되면 private 저장소의 `workflow_dispatch`를 호출한다. 홈페이지 쪽에 설치할 짧은 workflow는 이 PR에 예시 파일로 제공한다. 소유자가 연결할 때 대상 저장소에만 유효한 `Actions: write` 토큰을 홈페이지 저장소의 Actions secret에 둔다. |
| 예비 점검과 수동 실행 | private 저장소에서 하루 한 번 두 원본을 다시 확인한다. 홈페이지 쪽 통지를 설치하기 전에도 작동해야 한다. GitHub Actions의 `Run workflow`로 즉시 재실행할 수도 있어야 한다. |
| 앱 또는 데이터 변경 | private 저장소의 기본 브랜치에서 앱·수동 보완 데이터가 변경되거나 홈페이지의 집계 결과가 실질적으로 바뀌면 테스트한 정적 앱을 자동 배포한다. 동일 입력 재시도 시 논문 수가 늘지 않아야 한다. 수집·검증에 실패하면 직전 정상 배포를 유지하고 Actions에 원인을 남긴다. |
| 홈페이지 누락 후보 확인 | Crossref에 주 1회 ORCID `0000-0002-4541-160X`로 등록 실적을 조회한다. ORCID가 없는 실적도 찾을 수 있도록 저자명 `Kwan-Young Bak`과 `Kwanyoung Park`로도 검색하고, 제목과 공저자를 대조해 후보를 추린다. Google Scholar는 최초 프로필 BibTeX 내보내기와 이후 공식 새 논문 알림, ResearchGate는 실제 수신한 저자·논문 관련 알림이나 직접 제공한 제목·DOI를 입력으로 지원한다. 같은 DOI는 한 건으로 합치고, 홈페이지에 없는 후보만 출처와 함께 모아 확인 후 반영한다. |

메일 자동 연동을 위해 지정한 Gmail 라벨의 공식 알림에서 서지정보만 읽어 private workflow로 보내는 선택형 Apps Script와 설치 절차를 제공해 줘. 수신함 권한 연결은 계정 소유자가 선택한다. 메일 연동 전에는 Scholar BibTeX와 수동 후보 입력도 쓸 수 있어야 한다. Scholar와 ResearchGate의 계정 로그인이나 프로필 스크래핑에 의존하지 않는다. ResearchGate 대조 범위는 실제로 전달된 항목까지다. 홈페이지 갱신과 배포는 외부 색인이나 메일 연동의 가용성과 독립적으로 작동해야 한다. [Scholar 알림](https://scholar.google.com/intl/en/scholar/help.html#alerts) · [ResearchGate 이용약관](https://www.researchgate.net/terms-of-service) · [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)

배포 대상은 Cloudflare Workers Static Assets로 한다. 최초 설정은 빈 Worker에 Cloudflare Access를 먼저 적용하고, 운영 URL 및 미리보기 URL 전체에 본인의 정확한 이메일 한 개만 허용하는 순서로 안내해 줘. 미리보기 URL은 꺼 두어도 된다. HTML과 그래프 JSON 모두 비로그인 요청에 로그인 화면 또는 접근 거절을 반환하는지 확인한 뒤 실데이터를 배포한다. 배포 토큰 `CLOUDFLARE_API_TOKEN`은 private 저장소의 GitHub Actions secret, `CLOUDFLARE_ACCOUNT_ID`는 Actions variable로 읽는다. 같은 저장소에서 별도의 공개 Pages 배포는 만들지 않는다. [Cloudflare Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/) · [GitHub Actions 배포](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)

## 4. 실제 데이터로 확인할 예

2026-11-24에 홈페이지 두 원본을 확인했다. 아래 값은 해당 커밋에서 재현할 점검값이다. 운영은 항상 최신 원본을 읽으므로 새 논문이 들어오면 정상적으로 달라져야 한다. [검증에 사용한 홈페이지 스냅샷](https://github.com/kybak90/kybak90.github.io/tree/be7b4065287dd801c2070506dc53b80d0dc23558)

| 항목 | Accepted & published | Include ongoing |
| --- | ---: | ---: |
| 집계한 논문·원고 수 | 39 | 56 |
| Kwan-Young Bak — Woojoo Lee | 3 | 7 |
| Jiwoong Yu — Woojoo Lee | 1 | 2 |

원본 BibTeX 47건 중 제외 대상 8건을 뺐고, 진행 원고는 17건이다. 표의 전체 목록도 각각 39행과 56행이어야 한다. 실제 데이터에서 다음 동작을 확인해 줘.

- HSSC 논문은 한 행이며 저자 열에 `Kwanyoung Park`가 다섯 번째로 나온다. 행을 누르면 `Kwan-Young Bak`을 포함한 6개 노드와 이들 사이의 15개 선이 강조된다. 이 논문 때문에 두 번째 본인 노드가 생기지 않아야 한다.
- AAAI의 `ALTBI` 논문은 양쪽 보기에 들어가고 표에 학회명이 나온다. `arXiv:2605.22030` 기술보고서와 FastKRR의 CRAN 배포물은 양쪽 보기에서 제외한다. 진행 중인 FastKRR 패키지 **논문**은 두 번째 보기에서 `Ongoing`으로 표시한다. 이 원고의 접힌 다섯 번째 저자가 Kwan-Young Bak이다.
- 단독 원고를 선택하면 노드 하나가 강조된다. 진행 원고를 선택한 뒤 게재 확정 보기로 전환하면 그 행과 강조가 함께 사라진다. 별도 예시로 arXiv 프리프린트나 진행 원고가 정식 학회·학술지 논문으로 채택된 뒤 최종 게재되어도 한 행과 한 편으로 유지되는지 검증한다.

첫 PR에는 위 예의 실제 집계 결과와 그래프 화면을 포함하고, 계정 연결이 필요한 배포 설정은 README에서 소유자가 그대로 따라 할 수 있게 정리해 줘. 운영 중 홈페이지의 일반적인 변경은 PR 승인 없이 자동 반영한다.
