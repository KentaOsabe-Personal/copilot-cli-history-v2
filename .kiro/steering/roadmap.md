# Roadmap

## Overview

Rails API + MySQL で構成されていた backend を、Python 3.14 + Django 5.2 + BigQuery の構成へ段階移行する。主目的は新規技術の習得であり、単純な置換速度よりも Django の API 実装、Python の型付き開発、BigQuery の read model / query / load job / MERGE の学習を段階的に得られる進め方を優先する。

Frontend は現行 React SPA を維持し、利用者から見える API contract は原則として維持する。Copilot CLI の raw files は引き続き一次ソースとし、BigQuery は MySQL と同じく再生成可能な read model として扱う。

現在の worktree には Rails runtime が存在しないため、Rails backend と Django backend を live 並行稼働する parity validation は active plan から外す。Rails 由来の `api-contract-fixtures` を契約正本として Django API を検証し、React からの runtime 確認や残存 artifact 整理は、必要な範囲で直接実装・検証として扱う。

## Approach Decision

- **Chosen**: 互換 contract 固定を起点にした段階的 Django / BigQuery 移行。API contract fixture、Django backend の土台、BigQuery schema、Python reader、Django presenter、BigQuery repository、Django API を独立 spec として進める。
- **Why**: 現行機能を壊さず学習単位を明確にでき、API shape の互換性、raw file 正本、BigQuery の analytical datastore としての扱いを spec ごとに検証できるため。Rails runtime は既に削除済みのため、live Rails parity ではなく Rails 由来 fixture と React + Django smoke を切替判断の正本にする。
- **Rejected alternatives**: 一括置換は backend runtime、datastore、reader 移植、API contract、Docker / docs 更新が混在してレビュー境界が大きすぎるため採用しない。Django ORM 用 BigQuery backend を通常 DB として使う案は、ORM 機能差や transaction 前提が学習目的と read model 用途に合わないため初期移行では採用しない。Frontend も同時に作り直す案は、API contract 互換性の検証を難しくするため採用しない。

## Scope

- **In**: 現行 API fixture 固定、Django backend foundation、Python 3.14 runtime、Django settings / routing / health endpoint、Python 品質ツール、BigQuery dataset / table schema、schema 初期化 script、raw file reader / normalizer の Python 移植、summary / detail presenter と error envelope の Python 実装、BigQuery query / detail / upsert repository、`POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/<session_id>`、Rails 由来 fixture に対する Django API 検証、README と steering 更新。
- **Out**: Rails runtime の復元、Rails / Django live payload 差分検証、Frontend の全面刷新、Django admin / auth / session の導入、BigQuery を Django ORM の通常 DB として扱うこと、background job / file watch / 自動同期、raw files を一次ソースから外すこと、semantic search、外部公開向け hardening、本番 GCP 運用設計。

## Constraints

- raw files は一次ソース、BigQuery は再生成可能な補助 read model として扱う。
- Docker Compose を開発環境の正本として維持する。
- Frontend の `VITE_API_BASE_URL` と現行 API URL / JSON shape は原則維持する。
- Django admin / auth / 組み込み session は初期スコープ外とし、API は stateless に保つ。
- BigQuery schema は Django migration ではなく SQL または Python script で管理する。
- BigQuery への保存は session ごとの細かな OLTP 更新ではなく、staging table + MERGE を基本にする。
- BigQuery 実接続なしで主要 unit / API tests を実行できるよう fake repository を用意し、実 dataset を使う integration test は opt-in にする。
- テストコードを作成・更新するときは、各 `it` / test case の直前に `概要・目的`、`テストケース`、`期待値` のコメントを残す。
- Django 5.2 は LTS 系として採用し、Python 3.14 は stable release として扱う。ただし依存 package の Python 3.14 対応は spec / implementation 時に個別確認する。

## Boundary Strategy

- **Why this split**: API fixture は利用者から見える契約、Django foundation は runtime と開発品質、BigQuery schema は datastore contract、Python reader は raw file 正規化、Django presenter は response payload 互換、BigQuery repository は datastore access、Django API は HTTP orchestration に責務を分けられる。Rails runtime がない現状では、live Rails parity を復元せず、Rails 由来 fixture と必要な runtime smoke を検証対象にする。
- **Shared seams to watch**: Rails 由来 fixture と Django response の JSON shape、`summary_payload` / `detail_payload`、root failure と degraded session の error envelope、日付 range と検索 query の互換性、BigQuery partition filter と scan cost、sync run の status / count / failure summary、Docker Compose の port と env vars、frontend の API base URL、残存 Rails / MySQL artifact の誤用。

## Specs (dependency order)

- [x] api-contract-fixtures -- Rails API と frontend 型を基準に list / detail / sync / error の request / response fixture を固定する。Dependencies: none
- [x] django-backend-foundation -- Django 5.2 backend の起動、health endpoint、Python 3.14 Docker runtime、品質ツール、pytest 基盤を作る。Dependencies: none
- [x] bigquery-read-model-schema -- BigQuery dataset / table schema と初期化 script、環境変数、fake repository 前提を定義する。Dependencies: django-backend-foundation
- [x] copilot-history-python-reader -- Rails の raw file reader / normalizer / projection を Python に移植し、normalized session を作れるようにする。Dependencies: django-backend-foundation, api-contract-fixtures
- [x] django-presenters-contract -- Python presenter で summary / detail payload と error envelope を現行 API fixture に一致させる。Dependencies: copilot-history-python-reader, api-contract-fixtures
- [x] bigquery-session-repository -- BigQuery の sessions query / detail query / staging + MERGE upsert repository を実装する。Dependencies: bigquery-read-model-schema, django-presenters-contract
- [x] django-history-api -- Django で sync / list / detail API を実装し、現行 frontend が使う URL と JSON shape を返す。Dependencies: bigquery-session-repository

## Retired / Replaced Specs

- `rails-django-parity-validation` -- Rails runtime が current worktree に存在せず、Rails / Django live payload diff の前提が成立しないため retired。検証責務は Rails 由来 fixture と必要な runtime smoke に寄せ、独立 spec は置かない。
- `remove-rails-mysql-stack` -- Rails / MySQL stack の削除は一部先行済みで、残っている作業は live stack removal ではなく小さな artifact cleanup として直接扱うため retired。

## Previous Roadmap: MySQL Read Model Migration

### Previous Overview

画面表示用のセッション履歴取得を MySQL 上の read model に寄せ、Copilot CLI の raw files 読取を明示的な履歴同期操作へ閉じ込めた。raw files は一次ソース、DB は再生成可能な index / read model として扱う方針を確立した。

### Previous Specs

- [x] history-db-read-model -- Copilot セッション履歴を DB read model として保存する schema / model / payload builder を定義する。Dependencies: none
- [x] history-sync-api -- raw files を読み取り、DB read model へ同期する service と明示同期 API を追加する。Dependencies: history-db-read-model
- [x] frontend-history-sync-ui -- frontend に履歴最新化ボタン、DB 空状態、同期中・成功・失敗表示を追加する。Dependencies: history-sync-api
- [x] session-api-db-query -- 既存 session list/detail API を DB query に切り替え、日付範囲指定を DB 側で処理する。Dependencies: history-db-read-model, history-sync-api, frontend-history-sync-ui
- [x] session-date-filtering -- セッション一覧に日付フィルタ UI を追加し、初期表示を直近 1 週間へ絞る。Dependencies: session-api-db-query, frontend-session-ui, frontend-history-sync-ui
- [x] session-full-text-search -- セッション一覧に全文検索を追加し、保存済み read model から会話本文・関連メタ情報に一致するセッションを探せるようにする。Dependencies: session-api-db-query, session-date-filtering, history-sync-api
- [x] cwd-session-tabs -- セッション一覧に作業ディレクトリ別タブを追加し、取得済み一覧を cwd ごとに切り替えて確認できるようにする。Dependencies: session-api-db-query, session-date-filtering, session-full-text-search, session-execution-directory-search
