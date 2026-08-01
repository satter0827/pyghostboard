# pyghostboard

[![CI](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml/badge.svg)](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

pyghostboardは、永続化しやすい型付きGeister domain、別プロセスAI protocol、Rich CUIを提供します。

[English README](README.md)

## インストールと対局

Python 3.11から3.14に対応します。

```shell
pip install pyghostboard
pyghostboard play --seed 7
```

同梱ランダムAIは別プロセスで動作し、担当プレイヤーから見える情報だけを受け取ります。外部AI、
対局記録、再生、ルール検証は`pyghostboard --help`で確認できます。

## domainの利用

```python
from uuid import uuid4

from pyghostboard.domain import Match, Placement, Player, RuleSet

rules = RuleSet.standard()
one = rules.start_squares(Player.ONE)
two = rules.start_squares(Player.TWO)
match = Match.start(
    uuid4(),
    rules,
    {
        Player.ONE: Placement(good=one[:4], bad=one[4:]),
        Player.TWO: Placement(good=two[:4], bad=two[4:]),
    },
)
view = match.view_for(Player.ONE)
match = match.play(Player.ONE, view.legal_actions[0]).match
```

信頼済みアプリは`PrivateMatchSnapshot`を直接保存するか、非同期の`MatchService`と
`MatchStore`を利用できます。公開JSON形式のJSON Schemaもwheelへ同梱します。`RuleSet`で
変更できるのは盤面、配置領域、出口、全駒共通の移動ベクトル、駒数、既定3勝利条件の組合せ
だけであり、任意のPythonコードは実行しません。

実行時制限は`PYGHOSTBOARD_` prefixの環境変数から注入できます。たとえば
`PYGHOSTBOARD_AGENT_TIMEOUT=5`でAI応答期限を変更できます。メッセージサイズ、保持する
標準エラー、最大手数、ログレベルも`RuntimeSettings`の対応項目で設定できます。

## 開発

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
uv sync --locked --group dev
uv run pytest
```

信頼境界と依存方向は[アーキテクチャ](docs/architecture.md)、完全な検証手順とブランチ運用は
[コントリビューションガイド](CONTRIBUTING.md)を参照してください。

## 0.1.0の範囲

ローカルの人間対AI、再利用可能なdomain API、秘密情報を含む対局記録、外部AIプロセスを対象とします。
GUI、ネットワーク対戦、アカウント、実運用向けDB adapterは対象外です。

本プロジェクトは非公式実装です。市販製品の画像や説明書本文は同梱しません。

## ライセンス

[MIT License](LICENSE)で公開します。
