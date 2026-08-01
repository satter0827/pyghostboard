# pyghostboard

[![CI](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml/badge.svg)](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

pyghostboardは、不完全情報ゲームと公平なAIのための型付きPythonエンジンです。

> [!IMPORTANT]
> 現在はリポジトリ基盤を構築した段階です。ゲームルール、AI、CLIはまだ実装していません。

[English README](README.md)

## 目標

- ゲームエンジンをUIやAIの実装から独立させる。
- AIには担当プレイヤーが知り得る情報だけを渡す。
- seedを固定した実行を再現可能にし、テストと評価に利用できるようにする。
- 必須の実行時依存を持たない、型付きでインストール可能なPythonパッケージを提供する。

## 初回リリースに含めないもの

- GUIまたはWeb UI
- ネットワーク対戦やマッチメイキング
- 対局の保存
- PyPIへの自動公開

## 必要な環境

- Python 3.11から3.14
- 開発時は[uv](https://docs.astral.sh/uv/)を使用

## 開発環境の構築

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
uv sync --locked --group dev
```

開発手順、ブランチ規則、品質確認コマンドは
[コントリビューションガイド](CONTRIBUTING.md)を参照してください。

## リポジトリ構成

```text
src/pyghostboard/  インストール対象のパッケージ
tests/unit/        独立した振る舞いのテスト
tests/integration/ 配布物と境界のテスト
docs/              アーキテクチャ文書
```

依存関係の方針は[アーキテクチャ](docs/architecture.md)、開発手順は
[コントリビューションガイド](CONTRIBUTING.md)を参照してください。

## 開発状況

次の開発対象は型付きドメインモデルです。製品機能は`develop`向けの小さなPull Requestで追加し、
`main`は安定した統合点として維持します。

## セキュリティ

脆弱性は[セキュリティポリシー](SECURITY.md)に従って報告してください。公開Issueには記載しないで
ください。

## ライセンス

[MIT License](LICENSE)で公開します。
