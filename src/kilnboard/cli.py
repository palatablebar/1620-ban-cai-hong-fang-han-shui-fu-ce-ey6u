from argparse import ArgumentParser
from json import dumps
from pathlib import Path
import sys

from .settings import DEFAULT_BUDGET, SAMPLE_NAME, TITLE
from .cycle_anchors.contracts import Windows
from .stack_cards.service import inspect_path, isolation_counts
from .probe_windows.contracts import Scenario
from .stack_disposition.service import history, latest, manifest, publish
from .process import load_path, preview
from .comparison import inspect_tradeoff


def parser() -> ArgumentParser:
    cli = ArgumentParser(description=TITLE)
    cli.add_argument('--source',type=Path,default=Path(f'sample_data/{SAMPLE_NAME}'))
    cli.add_argument('--store',type=Path,default=Path('state'))
    commands = cli.add_subparsers(dest='command',required=True)
    commands.add_parser('validate',help='清点可导入和隔离数据')
    for name, help_text in [('preview','生成待办与半开排班窗'),('replay','输出拟合、校准和近窗回放'),
                            ('manifest','输出当前处置 CSV'),('publish','按预览摘要发布')]:
        params = commands.add_parser(name,help=help_text)
        params.add_argument('--budget',type=int,default=DEFAULT_BUDGET)
        params.add_argument('--reserve',type=int,default=0)
        params.add_argument('--region')
        params.add_argument('--start',type=int,default=360)
        params.add_argument('--stop',type=int,default=1005)
        params.add_argument('--asof',type=int,default=126)
        if name=='manifest':
            params.add_argument('--output',type=Path)
        if name=='publish':
            params.add_argument('--expected-revision',type=int,required=True)
            params.add_argument('--id',required=True)
    comparison = commands.add_parser('compare',help='复算两套预算并列明受影响的处置')
    comparison.add_argument('--from-budget',type=int,default=DEFAULT_BUDGET)
    comparison.add_argument('--to-budget',type=int,required=True)
    comparison.add_argument('--reserve',type=int,default=0)
    comparison.add_argument('--region')
    ledger = commands.add_parser('ledger',help='读取已发布版本')
    ledger.add_argument('--latest',action='store_true')
    return cli


def as_json(value) -> str:
    return dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)


def run(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command=='validate':
            source = inspect_path(args.source)
            print(as_json({**source.counts(),'reasons':isolation_counts(source),'sha256':source.dataset_hash}))
            return 0
        if args.command=='ledger':
            print(as_json(latest(args.store) if args.latest else history(args.store)))
            return 0
        if args.command=='compare':
            original = Scenario(args.from_budget,args.reserve,args.region)
            proposed = Scenario(args.to_budget,args.reserve,args.region)
            print(as_json(inspect_tradeoff(load_path(args.source),original,proposed)))
            return 0
        scenario = Scenario(args.budget,args.reserve,args.region,args.start,args.stop)
        result = preview(load_path(args.source),scenario,Windows(asof=args.asof))
        if args.command=='publish':
            if args.id!=result.identifier:
                raise ValueError('预览摘要与待发布参数不一致')
            print(as_json(publish(args.store,result,args.expected_revision)))
        elif args.command=='manifest':
            text = manifest(result.payload)
            if args.output is None:
                print(text,end='')
            else:
                args.output.write_text('\ufeff'+text,encoding='utf-8')
        elif args.command=='replay':
            body = result.payload
            print(as_json({key:body[key] for key in ('cohorts','model','replay','holdout_points','drift')}))
        else:
            print(as_json({'id':result.identifier,'plan':result.payload}))
    except (ValueError,OSError) as error:
        print(str(error),file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(run())
