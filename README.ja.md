# pyghostboard

[![CI](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml/badge.svg)](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/satter0827/pyghostboard/blob/main/LICENSE)

pyghostboardは、永続化しやすい型付きGeister domain、別プロセスAI protocol、Rich CUIを提供します。

[English README](https://github.com/satter0827/pyghostboard/blob/main/README.md)

## インストールと対局

Python 3.11から3.14に対応します。domain APIはPython対応環境で利用できます。CUI、AIの
別プロセス隔離、秘密対局記録は、プロセス終了とファイル昇格にPOSIXの保証を利用するため
macOSとLinuxに対応します。

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
python -m pip install .
pyghostboard play --seed 7
```

標準形式のwheelとsource archiveを構築しますが、package registryには公開しません。
現在の`main` commitへ付けた`vX.Y.Z` tagから、厳密に同じ版の成果物をGitHub Actionsで
構築します。

同梱ランダムAIは別プロセスで動作し、担当プレイヤーから見える情報だけを受け取ります。対局記録、
再生、ルール検証は`pyghostboard --help`で確認できます。外部AIのcommandはshellを介さず、
次のように引数ごとに指定します。

```shell
pyghostboard play --ai python --ai /path/to/agent.py
```

秘密対局記録には両プレイヤーの駒種と配置が含まれます。secretとして保護してください。既存の
記録先は、`--overwrite-record`を明示しない限り置き換えません。

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

実行時制限は`PYGHOSTBOARD_` prefixの環境変数から注入できます。変数名は`LOG_LEVEL`、
`AGENT_TIMEOUT`、`AGENT_MAX_MESSAGE_BYTES`、`AGENT_MAX_STDERR_BYTES`、`MAX_PLIES`です。
たとえば`PYGHOSTBOARD_AGENT_TIMEOUT=5`でAI応答期限を変更できます。

## 開発

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
uv sync --locked --group dev
uv run pytest
```

信頼境界と依存方向は[アーキテクチャ](https://github.com/satter0827/pyghostboard/blob/main/docs/architecture.md)、
外部連携は[AI protocol](https://github.com/satter0827/pyghostboard/blob/main/docs/ai-protocol.md)と
[integration guide](https://github.com/satter0827/pyghostboard/blob/main/docs/integration.md)、検証手順と
ブランチ運用は[コントリビューションガイド](https://github.com/satter0827/pyghostboard/blob/main/CONTRIBUTING.md)を参照してください。

## 0.1.0の範囲

ローカルの人間対AI、再利用可能なdomain API、秘密情報を含む対局記録、外部AIプロセスを対象とします。
GUI、ネットワーク対戦、アカウント、実運用向けDB adapterは対象外です。

本プロジェクトは非公式実装です。市販製品の画像や説明書本文は同梱しません。

## ライセンス

[MIT License](https://github.com/satter0827/pyghostboard/blob/main/LICENSE)で提供します。
