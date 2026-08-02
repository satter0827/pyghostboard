# pyghostboard

[![CI](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml/badge.svg)](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/satter0827/pyghostboard/blob/main/LICENSE)

pyghostboardは、Geisterを遊ぶ、domainを組み込む、別プロセスAIを作る、再現可能なAI対局を
分析するための型付きPython packageです。

[English README](README.md)

## 遊ぶ

Python 3.11から3.14に対応します。domain APIはPython対応環境で利用できます。CLI、AIの
別プロセス隔離、非公開の対局記録は、POSIXのプロセス終了とファイル処理を使うためmacOSと
Linuxに対応します。

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
python -m pip install .
pyghostboard play --seed 7
```

既定の対戦相手はMCTSです。再現可能な比較用AIは`--agent random`で選べます。行動は表示された
番号、`b2 c2`、`b2 exit`のいずれかで入力します。日本語表示は`--language ja`または
`PYGHOSTBOARD_LANGUAGE=ja`で選べます。

![決定的なCLI対局画面](docs/images/cli.svg)

対応するTTYでは1画面をRichで更新します。redirectされた出力、`NO_COLOR`、`TERM=dumb`では
追記型のplain textへ切り替わります。非公開の対局記録は、どちらかのプレイヤー視点を選び、
一手送りまたは自動送りで再生できます。

```shell
pyghostboard replay match.jsonl --view two --step
pyghostboard replay match.jsonl --view one --delay 0.5
```

非公開の対局記録には両プレイヤーの駒種と配置が含まれます。secretとして保存してください。
既存の記録先は、`--overwrite-record`を明示した場合だけ置き換えます。

## domain APIを使う

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

信頼済みアプリはimmutableなdomain値を直接使うか、`MatchService`、`MatchRunner`、注入した
`MatchStore`と`PlayerController` portで永続化した対局を進行できます。公開facadeには型があり、
versioned JSON Schemaをwheelへ同梱します。

## AIを作る

最小の外部AIは公開policy runnerを再利用できます。

```python
import sys

from pyghostboard.agents import RandomAgent, run_agent

run_agent(sys.stdin.buffer, sys.stdout, RandomAgent)
```

`agent.py`として保存し、lifecycle全体を検証してから対局します。commandの各引数は繰り返して
指定し、shellを介さず直接渡します。

```shell
pyghostboard agent check --command python --command agent.py
pyghostboard play --command python --command agent.py
```

hostが送るのは公開ルール、担当プレイヤーのview、合法手、seed、lifecycle messageだけです。
AI wire schema 0.1.0にprivate snapshot、private event、相手の生存駒種は入りません。実行可能な
例は[`examples/external_agent.py`](examples/external_agent.py)を参照してください。

## 分析する

[`examples/arena.toml`](examples/arena.toml)には2つ以上のAI、AI別の探索設定、対戦組ごとのround数、
root seed、ルール、記録方針、実行上限を明記しています。

```shell
pyghostboard arena watch examples/arena.toml --agent mcts --opponent random
pyghostboard arena run examples/arena.toml --output results/
pyghostboard arena analyze results/
pyghostboard arena analyze results/ --format json
# 中断後
pyghostboard arena resume results/
```

設定した全AIの組合せについて、各roundで先後を入れ替えた2局を行います。seedはroot seed、
対戦組、round、AI識別子からSHA-256で導出します。権限`0700`の非公開result directoryには、
1局ごとのattempt directoryを原子的に保存し、中断後は未実行分だけを再開します。分析はrun、
AI、先後、対戦組、paired round、勝因、失敗code、手数の集計を返し、command、local path、
process詳細、非公開記録は含めません。これは記述統計であり、順位や統計的有意性は主張しません。

## 開発

```shell
uv sync --locked --group dev
uv run python scripts/release_gate.py check all
```

要件、architecture、interface、品質、delivery、operationsは[ドキュメント](docs/README.md)、
reviewとbranchの運用は[コントリビューションガイド](CONTRIBUTING.md)を参照してください。

## 0.1 seriesの範囲

ローカルの人間対AI、再利用可能なdomain・application API、外部AI process、非公開の対局記録、
決定的なarena、記述分析を対象とします。GUI、network matchmaking、account、実運用向けDB
adapter、package registryへの公開は対象外です。

本プロジェクトは非公式実装です。市販製品の画像や説明書本文は同梱しません。

## ライセンス

[MIT License](LICENSE)で提供します。
