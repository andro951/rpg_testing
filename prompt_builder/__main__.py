"""Build/export the selected suite; no model inference or network calls."""
import argparse
import json
from pathlib import Path
from .builder import ROOT, build, discover, install

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--templates',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=Path('build/prompt-suite'))
    parser.add_argument('--install',action='store_true',help='Activate generated definitions in this repository after archiving previous managed tests')
    parser.add_argument('--list',action='store_true',help='List discovered case and format folders without generating tests')
    parser.add_argument('--input-formats',nargs='+')
    parser.add_argument('--output-formats',nargs='+')
    parser.add_argument('--cases',nargs='+')
    parser.add_argument('--repetitions',type=int,default=3)
    args=parser.parse_args()
    if args.list:result=discover(args.templates)
    else:
        result=build(args.output,root=args.templates,input_formats=args.input_formats,output_formats=args.output_formats,cases=args.cases,repetitions=args.repetitions)
        result={k:result[k]for k in('version','prompt_count','observations_per_model','unsupported','model_runs_started_by_builder')}
        result['output']=str(args.output)
        if args.install:result['installation']=install(args.output)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
