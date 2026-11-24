#!/usr/bin/env python3
"""Převodník JMHZ: PDF tisk z Money S3 -> XML/ZIP pro ePortál ČSSZ."""
import sys

from jmhz.cli import main

if __name__ == "__main__":
    sys.exit(main())
