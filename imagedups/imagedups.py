import argparse
import os.path
import subprocess
import sys
import time
import json
from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from imagedups.imagehash import ImageHash, DctImageHash, compute_hash
from imagedups.hashdb import HashDB


class ImageDups:

    """Finds duplicate images using pHash library

    Algorithm has two parts:
        * compute hashes of images
        * compare hashes

    To compute hashes, use '--hash' command. Computed hashes are written
    to hash database in '~/.imagedups' directory.
    Use '-r' option for recursive search of images in subdirectories.

    To compare hashes and search for duplicates, use '--search' command.
    This reads hash database, compares each hash with each other
    and prints out pairs of images with hash distance up to threshold.

    Both phases are run in succession if no command is given.

    """

    FORMATS = ['.png', '.jpeg', '.jpg', '.tiff', '.tif']

    def __init__(self):
        self.path = None
        self.imagehash_class = DctImageHash
        self.threshold = 90.0
        self.samplefile = None
        self.recursive = False
        self.extviewer = False
        self.program = 'gthumb'
        self.dbpath = '~/.imagedups'
        self.dbfile = '.imagehash'
        self.parser = argparse.ArgumentParser(
            description=self.__doc__.strip(),
            formatter_class=argparse.RawDescriptionHelpFormatter)
        self.parser.add_argument('path', nargs='?', help='Target directory with images to hash')
        self.parser.add_argument('--hash', action='store_true', help='Compute hashes of images')
        self.parser.add_argument('--search', action='store_true', help='Compare hashes, find similar images')
        self.parser.add_argument('-a', '--algorithm', default='dct', help='Image hash algorithm. Options: dct | mh | radial. Default: %(default)s')
        self.parser.add_argument('-t', '--threshold', type=float, default=self.threshold, help='Minimal similarity ratio of compared images. Default: %(default)s%%')
        self.parser.add_argument('-f', '--samplefile', help='Search for duplicates of this file')
        self.parser.add_argument('-r', '--recursive', action='store_true', help='Walk subdirectories recursively')
        self.parser.add_argument('-x', '--extviewer', action='store_true', help='Use external program to view matching images')
        self.parser.add_argument('-p', '--program', default=self.program, help='External program to view images. See -x. Default: %(default)s')
        self.parser.add_argument('--dbpath', default=self.dbpath, help='Path where database file will be written and read from. Default: %(default)s')

    def main(self):
        # Process program args
        args = self.parser.parse_args()
        self.path = args.path
        self.threshold = args.threshold
        self.samplefile = args.samplefile
        self.recursive = args.recursive
        self.extviewer = args.extviewer
        self.program = args.program
        self.dbpath = os.path.expanduser(args.dbpath)
        self.dbfile += '_' + args.algorithm
        self.imagehash_class = ImageHash.get_subclass(args.algorithm)
        # Execute commands
        if args.hash:
            self.cmd_hash()
        elif args.search:
            self.cmd_search()
        else:
            self.cmd_hash()
            self.cmd_search()

    def cmd_hash(self):
        if not self.path:
            print('Path must be specified')
            return
        hashdb = self.load_database()
        try:
            for dirpath, filenames in self.all_directories_with_filenames():
                self.update_db(hashdb, dirpath, filenames)
        finally:
            self.save_database(hashdb)

    def cmd_search(self):
        hashdb = self.load_database()
        # If path was specified, search for duplicates only in path
        # Otherwise, all hashed images in database are searched
        if self.path:
            hashdb.filter_by_path(os.path.realpath(self.path))
        # If sample file was specified, search for similar images
        # Otherwise, search whole database for groups of similar images
        if self.samplefile:
            self.compare_with_db(hashdb, self.samplefile)
        else:
            self.show_binary_dupes(hashdb)
            self.search_db_for_dupes(hashdb)

    def load_database(self) -> HashDB:
        try:
            with open(self.dbpath, 'r', encoding='utf8') as f:
                dbitems = json.load(f)
            return HashDB.load(dbitems)
        except IOError:
            return HashDB()

    def save_database(self, hashdb: HashDB):
        dbitems = hashdb.dump()
        with open(self.dbpath, 'w', encoding='utf8') as f:
            json.dump(dbitems, f, indent='\t')

    def all_directories(self):
        path = os.path.abspath(self.path)
        if self.recursive:
            for dirpath, _dirnames, _filenames in os.walk(path):
                yield dirpath
        else:
            yield path

    def all_directories_with_filenames(self):
        path = os.path.abspath(self.path)
        if self.recursive:
            for dirpath, _dirnames, filenames in os.walk(path):
                filenames = [fname for fname in filenames
                             if self.is_image(fname)]
                filenames.sort()
                yield dirpath, filenames
        else:
            filenames = [fname for fname in os.listdir(path)
                         if self.is_image(fname)]
            filenames.sort()
            yield path, filenames

    def is_image(self, fname):
        _root, ext = os.path.splitext(fname)
        if ext.lower() in self.FORMATS:
            return True

    def update_db(self, hashdb, path, filenames):
        print('Hashing', path)
        with PoolExecutor(max_workers=os.cpu_count() or 4) as executor:
            # Compute hashes for new or updated files
            hashes = []
            hash_name = self.imagehash_class.algorithm()
            for fname in filenames:
                filepath = os.path.join(path, fname)
                file_hash = hashdb.add(filepath, fast_compare=False)
                if hash_name not in file_hash.image_hash:
                    # Not seen before -> compute image hash
                    future_imghash = executor.submit(compute_hash,
                                                     self.imagehash_class,
                                                     filepath)
                    hashes.append((file_hash, future_imghash))
            # Write results back into HashItem objects
            for file_hash, future_imghash in hashes:
                imghash = future_imghash.result(timeout=60)
                file_hash.image_hash[hash_name] = imghash

    def show_binary_dupes(self, hashdb):
        i = 1
        for item in hashdb.items:
            if len(item.file_names) > 1:
                print('--- binary equal', i, '---')
                for fname in item.file_names:
                    print(fname)
                if self.view(list(item.file_names), test_stop=True):
                    break
                i += 1

    def search_db_for_dupes(self, hashdb):
        last_fname = None
        i = 1
        file_list = []
        threshold = 1.0 - (self.threshold / 100)
        hash_name = self.imagehash_class.algorithm()
        for fname_a, fname_b, distance in \
                hashdb.find_all_dups_without_derived(threshold, hash_name):
            if fname_a != last_fname:
                if self.view(file_list, test_stop=True):
                    file_list = []
                    break
                print('---', i, '---')
                print(fname_a)
                file_list = [fname_a]
                last_fname = fname_a
                i += 1
            file_list.append(fname_b)
            self.print_out(fname_b, distance)
        self.view(file_list)

    def compare_with_db(self, hashdb, samplefile):
        imghash = self.imagehash_class(samplefile)
        print(samplefile)
        file_list = [samplefile]
        threshold = 1.0 - (self.threshold / 100)
        hash_name = self.imagehash_class.algorithm()
        for fname, distance in hashdb.query(imghash, threshold, hash_name):
            self.print_out(fname, distance)
            file_list.append(fname)
        self.view(file_list)

    def print_out(self, fname, distance):
        if distance is None:
            print(fname, '(100%% bitwise)')
        else:
            similarity = (1.0 - distance) * 100.0
            print(fname, '(%.0f%%)' % similarity)

    def view(self, file_list, test_stop=False):
        """Display files from `file_list` using external program.

        Waits for external program to exit before continuing.

        """
        if file_list and self.extviewer:
            print('* Waiting for subprocess...', end='')
            sys.stdout.flush()
            with open(os.devnull, "w") as devnull:
                subprocess.call([self.program] + file_list, stdout=devnull, stderr=devnull)
            print('\r' + ' '*30 + '\r', end='')
            if test_stop and self.test_stop():
                return True

    def test_stop(self):
        print('* Press Ctrl-C to stop', end='')
        sys.stdout.flush()
        try:
            for _i in range(3):
                time.sleep(0.5)
                print('.', end='')
                sys.stdout.flush()
        except KeyboardInterrupt:
            print()
            return True
        print('\r' + ' '*30 + '\r', end='')

