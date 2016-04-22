import os.path

DEFAULT_DB_PATH = '~/.cache/imagedups.hashdb'
DEFAULT_CONF_PATH = '~/.config/imagedups.conf'


class Config:

    def __init__(self):
        self.algorithm = 'mh'
        self.threshold = 90.0
        self.viewer = 'xdg-open'
        self.dbpath = DEFAULT_DB_PATH

    def try_load(self, path=DEFAULT_CONF_PATH):
        path = os.path.expanduser(path)
        try:
            self.load(path)
        except IOError:
            print("Creating default config at %r" % path)
            self.write_defaults(path)

    def load(self, path):
        with open(path, 'rt', encoding='utf8') as f:
            d = {}
            exec(f.read(), d, d)
            for key, value in d.items():
                key = key.lower()
                if key in self.__dict__:
                    setattr(self, key, value)

    def write_defaults(self, path):
        with open(path, 'wt', encoding='utf8') as f:
            for key, value in self.__dict__.items():
                print('# %s = %r' % (key, value), file=f)
