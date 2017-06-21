from pm_bibtex import fetch
import sys
import logging


logging.getLogger().setLevel(logging.DEBUG)
res = fetch(sys.argv[1])
