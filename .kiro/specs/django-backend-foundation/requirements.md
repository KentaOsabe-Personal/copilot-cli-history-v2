# 要件ドキュメント

## 導入

Rails API + MySQL から Django / BigQuery へ段階移行するために、まず `backend/` を Django backend として起動・検証できる開発基盤へ切り替える。  
この spec は、後続の reader、BigQuery read model、history API 移植が同じ Python backend 上に安全に積み上がるよう、Docker Compose runtime、health endpoint、依存管理、settings、routing、テスト、品質確認、基本ドキュメントの土台を整える。

## 境界コンテキスト

- **In scope**: Django 5.2 backend の起動基盤、Python 3.14 runtime、backend service の Docker Compose 起動、`GET /up` health endpoint、Python dependency 管理、Django settings / routing の最小構成、pytest / pytest-django、ruff、型チェック、backend 向け README / コマンド更新。
- **Out of scope**: BigQuery schema / 接続、Copilot 履歴 reader の Python 移植、`POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/:id`、Rails / MySQL stack の削除、frontend の機能改修、Django admin / auth / session 機能。
- **Adjacent expectations**: frontend は既存の API base URL 設定から backend へ接続できることを期待する。後続の `bigquery-read-model-schema`、`copilot-history-python-reader`、`django-history-api` は、この spec が用意する backend runtime と品質確認入口にコードを追加する。

## 要件

### Requirement 1: Django backend の起動基盤
**Objective:** As a 移行開発者, I want backend service を Django backend として起動できる, so that 後続の Python 実装を Rails 環境差分から切り離して進められる

#### 受け入れ基準
1. When 開発者が Docker Compose で backend service を起動したとき, the Django Backend Foundation shall Django backend を外部から到達可能な状態で起動する。
2. When backend service が起動する, the Django Backend Foundation shall Python 3.14 runtime と Django 5.2 系を利用する backend として識別できる状態にする。
3. When frontend が設定済み API base URL へ接続するとき, the Django Backend Foundation shall 既存の backend 接続先を不必要に変更せずに health endpoint へ到達できるようにする。
4. If backend service の起動に失敗したとき, the Django Backend Foundation shall 開発者が起動失敗として識別できる終了状態またはログを残す。

### Requirement 2: Health endpoint と最小 routing
**Objective:** As a 開発者, I want backend の生存確認を単純な HTTP endpoint で確認したい, so that runtime と routing が成立しているかをすぐ検証できる

#### 受け入れ基準
1. When クライアントが `GET /up` を要求したとき, the Django Backend Foundation shall HTTP 200 の health response を返す。
2. When `GET /up` が成功するとき, the Django Backend Foundation shall backend の詳細データやローカル履歴情報を含まない最小の成功 response を返す。
3. When 開発者が smoke test を実行したとき, the Django Backend Foundation shall `GET /up` が成功することを検証対象に含める。
4. The Django Backend Foundation shall この spec の完了条件として履歴同期 API、セッション一覧 API、セッション詳細 API を提供しない。

### Requirement 3: Python dependency と設定管理
**Objective:** As a バックエンド開発者, I want Python backend の依存関係と実行設定が明示されていてほしい, so that 後続 spec が同じ前提で機能を追加できる

#### 受け入れ基準
1. The Django Backend Foundation shall backend の Python dependency と開発用 dependency をプロジェクト内の標準ファイルで確認できるようにする。
2. When 開発者が backend dependency を導入するとき, the Django Backend Foundation shall Docker Compose 経由で再現できる依存解決入口を提供する。
3. The Django Backend Foundation shall Django settings が開発環境とテスト環境で利用できる状態を提供する。
4. If 必須の runtime 設定が不足して backend が起動できないとき, the Django Backend Foundation shall 開発者が設定不足として識別できる失敗を返す。
5. The Django Backend Foundation shall BigQuery を通常の Django 永続化先として設定することをこの spec の対象に含めない。

### Requirement 4: テスト基盤
**Objective:** As a バックエンド開発者, I want Django backend のテストを実行できる, so that 後続実装の安全性を最初から確認できる

#### 受け入れ基準
1. When 開発者が backend test command を実行したとき, the Django Backend Foundation shall pytest ベースのテストを実行する。
2. When Django integration が必要なテストを実行するとき, the Django Backend Foundation shall Django のテスト設定を読み込んだ状態で検証できるようにする。
3. When health endpoint のテストを実行したとき, the Django Backend Foundation shall `GET /up` の成功契約を検証する。
4. Where backend のテストコードが作成または更新される場合, the Django Backend Foundation shall 各 test case の直前に `概要・目的`、`テストケース`、`期待値` のコメントを残すプロジェクトルールに従う。

### Requirement 5: 品質確認入口
**Objective:** As a レビュー担当者, I want backend の lint と型チェックを同じ入口から確認できる, so that Django 移行の土台が後続変更に耐えるか判断できる

#### 受け入れ基準
1. When 開発者が backend lint command を実行したとき, the Django Backend Foundation shall Python backend の style / lint 違反を検出できるようにする。
2. When 開発者が backend type check command を実行したとき, the Django Backend Foundation shall Python backend の型検査を実行できるようにする。
3. When 開発者が backend quality command を実行したとき, the Django Backend Foundation shall lint、型チェック、テストをまとめて確認できる入口を提供する。
4. If 品質確認で違反または失敗が見つかったとき, the Django Backend Foundation shall 開発者が失敗した確認種別を識別できる結果を返す。

### Requirement 6: ドキュメントと後続 spec への引き継ぎ
**Objective:** As a 後続 spec の実装者, I want Django backend の起動・検証方法と対象外範囲を確認できる, so that reader や API 移植を正しい土台へ追加できる

#### 受け入れ基準
1. The Django Backend Foundation shall backend の起動、health check、test、lint、type check、quality check の実行方法をドキュメントで確認できるようにする。
2. The Django Backend Foundation shall Rails / MySQL 削除、BigQuery 接続、履歴 API 移植がこの spec の対象外であることをドキュメントまたは仕様境界で確認できるようにする。
3. When 後続 spec が backend にコードを追加するとき, the Django Backend Foundation shall 追加先となる Django project とテスト実行入口を利用できる状態にする。
4. The Django Backend Foundation shall raw Copilot 履歴 files を一次ソースとして扱うプロダクト原則を変更しない。
