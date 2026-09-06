#!/usr/bin/env python3
from pathlib import Path
import argparse,json
from scode.compiler import compile_file
from scode.numerals import NumeralProfile,parse_number,format_number

def main():
    ap=argparse.ArgumentParser(prog='scode')
    sub=ap.add_subparsers(dest='cmd',required=True)
    c=sub.add_parser('compile'); c.add_argument('file'); c.add_argument('-o','--output')
    n=sub.add_parser('number'); n.add_argument('value'); n.add_argument('--profile','default')
    a=ap.parse_args()
    if a.cmd=='compile':
        ir=compile_file(a.file); text=json.dumps(ir,indent=2,ensure_ascii=False)+'\n'
        if a.output: Path(a.output).write_text(text,encoding='utf-8')
        else: print(text,end='')
    else:
        p=NumeralProfile() if a.profile=='default' else NumeralProfile.load(a.profile)
        print(parse_number(a.value,p))
if __name__=='__main__': main()
