#!/usr/bin/env python3
import sys
from pathlib import Path
from scode.runtime import run_program
if __name__=='__main__':
    program=Path(__file__).with_name('MasterGrooveboxStudio.scode')
    raise SystemExit(run_program(program,sys.argv))
