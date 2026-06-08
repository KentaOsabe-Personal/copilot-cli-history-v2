# 実装計画

- [ ] 1. Django backend の active runtime 基盤を用意する
- [x] 1.1 Python project と依存管理の入口を定義する
  - backend が Python 3.14 / Django 5.2 系として識別できる dependency と dev dependency を宣言する。
  - pytest-django、ruff、mypy、django-stubs を後続 task が同じ前提で使えるようにする。
  - Docker build または Compose 実行時に依存解決が再現でき、失敗時は dependency resolution failure として非ゼロ終了する状態にする。
  - _Requirements: 1.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2_

- [x] 1.2 Django 用 Docker image を構成する
  - backend service が Python 3.14 runtime で起動する image を作る。
  - dependency install は project dependency と dev dependency を含む backend 開発 image として再実行可能にする。
  - image build 後に `python --version` と Django import で runtime line を確認できる状態にする。
  - _Requirements: 1.1, 1.2, 3.2_

- [x] 1.3 Compose の backend service を Django 起動に切り替える
  - backend service の host port `30000` と frontend の API base URL を維持する。
  - backend command は Django development server を `0.0.0.0:30000` で起動する。
  - backend は MySQL healthcheck を起動前提にせず、Django startup failure を Compose logs または非ゼロ終了で識別できる状態にする。
  - _Requirements: 1.1, 1.3, 1.4, 3.2_

- [x] 1.4 Active backend と競合する Rails entrypoint を置換する
  - Django foundation と同じ active backend path で Rails server、Rails binstub、Ruby dependency が誤って実行されないよう整理する。
  - Rails / MySQL stack の全面削除は完了宣言せず、この spec の active runtime だけを Django に切り替える。
  - backend 起動時に古い Rails pid や database prepare に依存しないことを確認できる状態にする。
  - _Requirements: 1.1, 1.4, 2.4, 6.2_

- [ ] 2. Django project と settings の最小構成を作る
- [x] 2.1 Django project package と management entrypoint を用意する
  - development / test で同じ settings module を読み込める Django project を用意する。
  - local development default を持ちつつ、空文字や明示的な invalid secret は設定不足として失敗させる。
  - settings import は BigQuery、MySQL、raw Copilot files を必須条件にせず、sqlite の最小 database で Django system check が通る状態にする。
  - _Requirements: 3.3, 3.4, 3.5, 6.3, 6.4_

- [x] 2.2 ASGI / WSGI の起動入口を用意する
  - Django application entrypoint が settings module を読み込めるようにする。
  - development server 以外の標準 Django entrypoint からも app registry を初期化できる状態にする。
  - `python -m django check` 相当の確認で entrypoint と settings の import 問題を検出できる状態にする。
  - _Requirements: 1.4, 3.3, 6.3_

- [ ] 3. Health endpoint と routing contract を実装する
- [ ] 3.1 Health endpoint の最小 response を実装する
  - `GET /up` が HTTP 200 を返す health response を提供する。
  - response は status 以外の backend 詳細、local path、履歴件数、environment 値を含めない。
  - Django test client または curl で `{"status":"ok"}` 相当の最小 JSON を確認できる状態にする。
  - _Requirements: 1.3, 2.1, 2.2_

- [ ] 3.2 Root routing を health endpoint に接続する
  - root URLconf で `/up` を health endpoint に解決する。
  - `/api/history/sync`、`/api/sessions`、`/api/sessions/:id` は foundation の提供 route として追加しない。
  - route inventory で `/up` のみがこの spec の API 完了条件として確認できる状態にする。
  - _Requirements: 2.1, 2.4, 6.3_

- [ ] 4. Backend の test / lint / type check 入口を作る
- [ ] 4.1 pytest と smoke test の実行入口を用意する
  - backend test command が `python -m pytest` を実行する。
  - pytest-django が Django test settings を読み込み、Django integration test を実行できるようにする。
  - backend test command の結果に `/up` の smoke test が含まれる状態にする。
  - _Requirements: 2.3, 4.1, 4.2, 4.3_

- [ ] 4.2 Health endpoint の契約テストを追加する
  - `GET /up` の HTTP 200 と最小 JSON response を pytest で検証する。
  - health response に backend 詳細、local path、履歴情報が含まれないことを検証する。
  - 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントがあり、プロジェクトのテストコメント規約を満たす状態にする。
  - _Requirements: 2.1, 2.2, 2.3, 4.3, 4.4_

- [ ] 4.3 Settings / routing 境界のテストを追加する
  - Django settings import が BigQuery、MySQL、raw Copilot files を必要としないことを検証する。
  - URL resolver が `/up` を解決し、対象外 API route を foundation 完了条件として期待しないことを検証する。
  - テスト実行結果から settings、routing、health contract の成立を確認できる状態にする。
  - _Requirements: 1.3, 2.4, 3.3, 3.5, 6.3, 6.4_

- [ ] 4.4 Lint command を用意する
  - backend lint command が Python backend に対して ruff check を実行する。
  - lint 失敗時は lint command の失敗として確認種別を識別できる。
  - backend lint command を Compose 経由で実行できる状態にする。
  - _Requirements: 5.1, 5.4_

- [ ] 4.5 Type check command を用意する
  - backend type check command が Python backend に対して mypy を実行する。
  - Django settings と Django app code を型検査対象として扱えるようにする。
  - type check 失敗時は type check command の失敗として確認種別を識別できる。
  - _Requirements: 5.2, 5.4_

- [ ] 4.6 Quality command を用意する
  - quality command が lint、type check、test を順に実行する。
  - 途中で失敗した確認種別が command output または終了箇所から分かるようにする。
  - backend quality command を Compose 経由で実行し、全確認が通ると zero exit になる状態にする。
  - _Depends: 4.1, 4.4, 4.5_
  - _Requirements: 5.3, 5.4_

- [ ] 5. Compose 上で Django backend foundation を統合検証する
- [ ] 5.1 Backend service の起動と health check を確認する
  - `docker compose up --build backend` で backend service が Django backend として起動する。
  - host の `localhost:30000/up` から HTTP 200 の最小 health response を取得できる。
  - startup failure の場合は Django / dependency / port bind のどこで失敗したかをログまたは終了状態から識別できる。
  - _Depends: 1.3, 3.2_
  - _Requirements: 1.1, 1.3, 1.4, 2.1, 2.2_

- [ ] 5.2 Backend quality commands を Compose 経由で検証する
  - `bin/test`、`bin/lint`、`bin/typecheck`、`bin/quality` が backend container で実行できる。
  - test、lint、type check の各失敗種別を個別 command と quality command の両方で識別できる。
  - quality command が settings / routing / health tests を含む backend foundation の完了確認として使える状態にする。
  - _Depends: 4.6_
  - _Requirements: 2.3, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4_

- [ ] 5.3 Frontend 接続先との互換性を確認する
  - frontend の API base URL を不必要に変更せず backend port `30000` に接続できる。
  - frontend から設定済み base URL の `/up` へ到達できる前提を Compose 設定で確認できる。
  - history API は未提供のままでも、foundation の完了条件が `/up` に限定されていることを確認できる。
  - _Depends: 5.1_
  - _Requirements: 1.3, 2.4, 6.2_

- [ ] 6. 後続 spec へ runtime と対象外範囲を引き継ぐ
- [ ] 6.1 Backend README を Django foundation 前提へ更新する
  - backend の起動、health check、test、lint、type check、quality check の実行方法を確認できるようにする。
  - BigQuery 接続、履歴 reader、history API、Django admin / auth / session 機能がこの spec の対象外であることを明記する。
  - 後続 spec が追加先と検証入口を迷わず確認できる状態にする。
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 6.2 (P) Root README の stack と開発コマンドを更新する
  - root の stack table と backend command reference を Django / Python 前提に更新する。
  - frontend、backend port、MySQL の扱いについて、この foundation で維持するものと対象外のものを区別して説明する。
  - root README から backend health、test、lint、type check、quality の Compose command を確認できる状態にする。
  - _Requirements: 1.2, 1.3, 6.1, 6.2_
  - _Boundary: Backend Documentation_

- [ ] 6.3 Completion validation と仕様境界の最終確認を行う
  - 全 requirement ID が実装、テスト、command、docs のいずれかで確認可能であることを照合する。
  - raw Copilot 履歴 files を一次ソースとする原則が settings、docs、route scope のどこでも変更されていないことを確認する。
  - quality command と manual health check の結果をもって、後続 spec が Django project と test 入口を利用できる状態になっていることを確認する。
  - _Depends: 5.2, 6.1, 6.2_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4_
