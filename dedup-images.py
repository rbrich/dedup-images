#!/usr/bin/env python3

from dedupimages.dedupimages import DedupImages
from dedupimages.config import Config

cfg = Config()
cfg.try_load()
prog = DedupImages(cfg)
try:
    prog.main()
except KeyboardInterrupt:
    print('Interrupted...')
