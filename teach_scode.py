#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from scode.language_pack import load_language_pack, save_language_pack, teach, teach_numeral

DEFAULT=Path(__file__).with_name("scode_language")/"language_pack.json"

def main():
    ap=argparse.ArgumentParser(description="Teach sCodeOS your language without rebuilding the OS.")
    ap.add_argument("--pack",default=str(DEFAULT))
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("validate")
    show=sub.add_parser("show")
    t=sub.add_parser("word"); t.add_argument("section",choices=["keywords","operators","domain_words","aliases"]); t.add_argument("concept"); t.add_argument("spelling")
    n=sub.add_parser("numeral"); n.add_argument("value",type=int); n.add_argument("glyph"); n.add_argument("--key",action="append",default=[])
    args=ap.parse_args()
    pack=load_language_pack(args.pack)
    if args.cmd=="validate":
        print("language pack valid:",args.pack); return 0
    if args.cmd=="show":
        print(json.dumps(pack,indent=2,ensure_ascii=False)); return 0
    if args.cmd=="word":
        pack=teach(pack,args.section,args.concept,args.spelling)
    elif args.cmd=="numeral":
        pack=teach_numeral(pack,args.value,args.glyph,args.key)
    save_language_pack(pack,args.pack)
    print("taught and saved:",args.pack)
    return 0
if __name__=="__main__": raise SystemExit(main())
