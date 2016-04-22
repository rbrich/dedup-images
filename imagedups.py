#!/usr/bin/env python3

from imagedups.imagedups import ImageDups
from imagedups.config import Config

cfg = Config()
cfg.try_load()
prog = ImageDups(cfg)
try:
    prog.main()
except KeyboardInterrupt:
    print('Interrupted...')
