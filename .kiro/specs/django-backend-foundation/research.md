# Research & Design Decisions

## Summary
- **Feature**: `django-backend-foundation`
- **Discovery Scope**: Complex Integration / Full Discovery
- **Key Findings**:
  - Django 5.2 系で Python 3.14 を使う場合は、公式互換表に従い Django 5.2.8 以降を下限にする必要がある。
  - 既存 frontend は `VITE_API_BASE_URL=http://localhost:30000` を明示しており、backend service の host port と `/up` の到達性を維持すれば frontend 側の接続先変更は不要である。
  - 現行 backend は Rails / MySQL / RSpec 前提だが、この spec は Django 起動基盤、health endpoint、pytest / ruff / mypy の入口だけを所有し、履歴 API や BigQuery 接続は後続 spec に残す。

## Research Log

### 既存 backend と Compose 境界
- **Context**: Rails API + MySQL から Django / BigQuery へ段階移行する最初の土台として、どこまで置き換えるかを確認した。
- **Sources Consulted**: `docker-compose.yml`, `Dockerfile.backend`, `backend/config/routes.rb`, `backend/spec/requests/health_spec.rb`, `.kiro/steering/product.md`, `.kiro/steering/tech.md`, `.kiro/steering/structure.md`
- **Findings**:
  - Compose の backend service は `Dockerfile.backend` を使い、host port `30000` を公開している。
  - frontend service は `VITE_API_BASE_URL=http://localhost:30000` を使うため、port と `/up` の維持が接続互換の最小条件である。
  - 現行 `/up` は Rails health route で、履歴 API route も同じ Rails app に存在する。
- **Implications**:
  - Django foundation は backend service command と runtime を Python / Django に切り替え、frontend 接続先は維持する。
  - MySQL service の削除や Rails 履歴 API の Django 移植はこの spec に含めない。

### Django 5.2 と Python 3.14 互換性
- **Context**: 要件が Python 3.14 runtime と Django 5.2 系を指定しているため、互換範囲を確認した。
- **Sources Consulted**:
  - Django 5.2 documentation via Context7: `/websites/djangoproject_en_5_2`
  - Django FAQ: https://docs.djangoproject.com/en/6.1/faq/install/
  - Python 3.14 documentation: https://docs.python.org/3.14/
- **Findings**:
  - Django 公式 FAQ は Django 5.2 の対応 Python として 3.10, 3.11, 3.12, 3.13, 3.14 を示し、3.14 は Django 5.2.8 で追加された扱いである。
  - Python 公式ドキュメントは 3.14 系の標準ライブラリ、typing、packaging 参照を提供している。
- **Implications**:
  - 依存指定は `Django>=5.2.8,<5.3` とし、Python は `>=3.14,<3.15` に固定する。
  - Docker base image は Python 3.14 系を使い、runtime 識別を `python --version` と `django-admin --version` で確認できる入口を残す。

### Python toolchain 設定方式
- **Context**: pytest / pytest-django、ruff、型チェックを後続 spec が再利用できる入口として設計する必要がある。
- **Sources Consulted**:
  - pytest-django configuration: https://pytest-django.readthedocs.io/en/stable/configuring_django.html
  - Ruff configuration: https://docs.astral.sh/ruff/configuration/
  - mypy configuration: https://mypy.readthedocs.io/en/stable/config_file.html
  - pytest configuration: https://docs.pytest.org/en/latest/reference/customize.html
- **Findings**:
  - pytest-django は `pyproject.toml` の `DJANGO_SETTINGS_MODULE` を設定入口として扱える。
  - Ruff は `pyproject.toml` の `requires-python` から target version を推論できる。
  - mypy は `pyproject.toml` の `[tool.mypy]` を設定ファイルとして利用できる。
- **Implications**:
  - backend の Python dependency、pytest、ruff、mypy 設定は `backend/pyproject.toml` に集約する。
  - 実行入口は Docker Compose の `backend` service 経由の `python -m pytest`、`ruff check`、`mypy`、`bin/quality` に統一する。

### 既存 spec との移行関係
- **Context**: 後続 spec が Django foundation に積み上がるため、所有境界と再検証条件を明確にする必要がある。
- **Sources Consulted**: `.kiro/specs/api-contract-fixtures/design.md`, `.kiro/specs/backend-session-api/design.md`, `.kiro/specs/history-sync-api/design.md`
- **Findings**:
  - 既存 specs は Rails API contract、read model、reader、sync API を個別境界として扱っている。
  - `api-contract-fixtures` は Django presenter / API / parity validation の正本候補であり、この spec が API shape を再定義すると後続境界を壊す。
- **Implications**:
  - この spec は `/up` 以外の API を提供しないことを明示し、既存 API contract の移植は `django-history-api` と関連 specs に委譲する。
  - 後続 spec は `backend/pyproject.toml`、Django project package、pytest / quality command を前提として参照できる。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Rails と Django の併存 | 既存 Rails app を残し、別 port または別 path で Django を追加する | 移行中に既存 API を温存しやすい | backend service 境界が曖昧になり、frontend 接続先や品質入口が二重化する | この spec の「backend service を Django backend として起動」に合わない |
| Django foundation への置換 | backend service の active runtime を Django に切り替え、Rails / MySQL の削除は後続へ残す | 起動基盤と品質入口が単一化し、後続 Python specs が積み上げやすい | 既存 Rails API はこの段階で提供されない | 採用 |
| フル API 移植込み | Django 起動基盤と履歴 API 移植を同時に行う | 動作差分を一度に解消できる | spec が大きくなり、BigQuery / reader / presenter 境界が混ざる | 要件の out of scope に反する |

## Design Decisions

### Decision: backend service の active runtime を Django に切り替える
- **Context**: 要件 1 は Docker Compose の backend service が Django backend として起動することを求めている。
- **Alternatives Considered**:
  1. Rails app に Django を sidecar として追加する。
  2. backend service の runtime を Django に置き換える。
- **Selected Approach**: `Dockerfile.backend` と Compose backend command を Python 3.14 / Django 5.2.8+ に切り替え、host port `30000` と `/up` を維持する。
- **Rationale**: frontend の API base URL を維持しながら、後続 Python 実装の前提を単一 backend service に固定できる。
- **Trade-offs**: Rails API はこの段階で active backend から外れるが、履歴 API 移植は後続 spec の責務として明示する。
- **Follow-up**: 実装時に `docker compose up --build backend` と `curl http://localhost:30000/up` で確認する。

### Decision: Python 設定は `backend/pyproject.toml` に集約する
- **Context**: dependency、pytest、ruff、型チェックの入口を後続 spec が再利用できる必要がある。
- **Alternatives Considered**:
  1. `requirements.txt` と個別 config files を使う。
  2. `pyproject.toml` に project metadata と tool config を集約する。
- **Selected Approach**: `backend/pyproject.toml` に `Django>=5.2.8,<5.3`、pytest / pytest-django、ruff、mypy、django-stubs を定義する。
- **Rationale**: Python packaging と主要 tool configuration の標準入口を一箇所に置ける。
- **Trade-offs**: 完全 lock file はこの spec では導入しない。再現性は Docker base image と version range / command entrypoint で担保する。
- **Follow-up**: 依存 lock が必要になった時点で別 spec か steering 更新で導入判断する。

### Decision: health endpoint は framework 最小 view として実装する
- **Context**: `/up` は backend 詳細や履歴情報を返さない最小成功応答である必要がある。
- **Alternatives Considered**:
  1. Django REST Framework を導入する。
  2. Django の `JsonResponse` または `HttpResponse` で最小 view を実装する。
- **Selected Approach**: 追加依存なしで `GET /up` を Django URLconf から `health.views.up` に接続し、HTTP 200 と最小 JSON を返す。
- **Rationale**: この spec の API surface は health のみであり、DRF 導入は履歴 API 移植時に判断できる。
- **Trade-offs**: API framework 共通機能はまだない。後続 `django-history-api` が必要に応じて導入する。
- **Follow-up**: `/api/history/sync`、`/api/sessions`、`/api/sessions/:id` をこの spec で実装しないことを smoke test と docs に残す。

### Decision: 品質入口は小さな shell wrapper で統一する
- **Context**: lint、型チェック、テスト、まとめ実行の結果種別を識別できる必要がある。
- **Alternatives Considered**:
  1. README に個別コマンドだけを列挙する。
  2. `backend/bin/test`, `backend/bin/lint`, `backend/bin/typecheck`, `backend/bin/quality` を用意する。
- **Selected Approach**: shell wrapper を backend 配下に置き、Compose から同じ入口を実行する。
- **Rationale**: 失敗種別が command 名で分かり、後続 spec も同じ入口に test を追加できる。
- **Trade-offs**: wrapper の保守が必要だが、独自 runner や複雑な task system は導入しない。
- **Follow-up**: 各 wrapper は `set -euo pipefail` を使い、失敗時にその command が非ゼロ終了することを検証する。

## Risks & Mitigations
- Django 5.2 と Python 3.14 の micro version 互換が不足する — `Django>=5.2.8,<5.3` を指定し、Docker runtime で `python --version` / `django-admin --version` を確認する。
- 既存 Rails API が foundation 完了時点で使えないことを移行バグと誤解する — design、README、smoke test で `/up` 以外の API は対象外と明記する。
- MySQL service が残ることで Django が DB を使うと誤解される — backend の Compose dependency から MySQL を外し、settings は sqlite test/dev の最小構成に留める。
- テストコメント規約が Python tests で抜ける — `tests/test_health.py` の各 test function 直前に `概要・目的`、`テストケース`、`期待値` コメントを必須例として置く。

## References
- [Django 5.2 documentation](https://docs.djangoproject.com/en/5.2/) — Django URL routing、settings、runtime の公式資料。
- [Django installation FAQ](https://docs.djangoproject.com/en/6.1/faq/install/) — Django と Python version compatibility の公式表。
- [Python 3.14 documentation](https://docs.python.org/3.14/) — Python 3.14 runtime と typing / packaging の公式資料。
- [pytest-django configuration](https://pytest-django.readthedocs.io/en/stable/configuring_django.html) — `DJANGO_SETTINGS_MODULE` を pytest config へ置く方法。
- [Ruff configuration](https://docs.astral.sh/ruff/configuration/) — `pyproject.toml` と `requires-python` による設定。
- [mypy configuration](https://mypy.readthedocs.io/en/stable/config_file.html) — `pyproject.toml` の `[tool.mypy]` 設定。
