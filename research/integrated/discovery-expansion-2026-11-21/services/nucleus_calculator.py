#!/usr/bin/env python3
"""Run the common funded cash engine with NUCLEUS inputs.

Keep newgen_calculator.py beside this script. Both use only the Python standard library.
Run: python3 nucleus_calculator.py [nucleus_inputs.json] [nucleus_outputs.json]
"""
import sys
from pathlib import Path
from newgen_calculator import main

if __name__ == '__main__':
    here = Path(__file__).resolve().parent
    if len(sys.argv) == 1:
        sys.argv.extend([str(here / 'nucleus_inputs.json'), str(here / 'nucleus_outputs.json')])
    elif len(sys.argv) == 2:
        sys.argv.append(str(here / 'nucleus_outputs.json'))
    main()
