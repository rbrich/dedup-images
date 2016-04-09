from argparse import ArgumentParser, RawDescriptionHelpFormatter
import os.path
import subprocess
import sys
import time
import json
import gzip
from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from imagedups.imagehash import ImageHash, DctImageHash, compute_hash
from imagedups.hashdb import HashDB


class ImageDups:

    """Finds duplicate images using pHash library

    Algorithm has two parts:
        * compute hashes of images
        * compare hashes

    To compute hashes, use '--hash' command. Computed hashes are written
    to hash database in '~/.imagedups' file.
    Use '-r' option for recursive search of images in subdirectories.

    To compare hashes and search for duplicates, use '--search' command.
    This reads hash database, compares each hash with each other
    and prints out groups of images with hash distance lesser than a threshold.

    When original image files are moved, modified or deleted, their hashes
    stay in database and '--search' would still report them. Use '--cleanup'
    command to remove dead references from database. This removes the file
    references, so they are no longer reported, but keeps actual hashes.
    When the same file is found elsewhere by '--hash', it just adds the file
    name to this dead item, thus handling file renames.

    Use '--prune' command to remove any items without file references
    from database. This is not needed unless the database grows too much.

    Order of the phases if fixed:

    1. hash
    2. cleanup
    3. prune
    4. search

    By default, if no command is specified, hash, cleanup and search are run.

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
        self.hashdb = HashDB()

    def process_args(self):
        # Process program args
        ap = ArgumentParser(description=self.__doc__.strip(),
                            formatter_class=RawDescriptionHelpFormatter)
        ap.add_argument('path', nargs='?',
                        help='Target directory to be hashed / searched')
        ap.add_argument('--hash', action='store_true',
                        help=self.cmd_hash.__doc__)
        ap.add_argument('--search', action='store_true',
                        help=self.cmd_search.__doc__)
        ap.add_argument('--cleanup', action='store_true',
                        help=self.cmd_cleanup.__doc__)
        ap.add_argument('--prune', action='store_true',
                        help=self.cmd_prune.__doc__)
        ap.add_argument('-a', '--algorithm', default='dct',
                        help='Perceptual hash algorithm. '
                             'Options: dct | mh | radial. Default: %(default)s')
        ap.add_argument('-t', '--threshold', type=float, default=self.threshold,
                        help='Minimal similarity ratio for image comparison. '
                             'Default: %(default)s%%')
        ap.add_argument('-f', '--samplefile',
                        help='Search for duplicates of this file')
        ap.add_argument('-r', '--recursive', action='store_true',
                        help='Recursively traverse into subdirectories')
        ap.add_argument('-x', '--extviewer', action='store_true',
                        help='Use external program to view matching images')
        ap.add_argument('-p', '--program', default=self.program,
                        help='External program used to view images by -x. '
                             'Default: %(default)s')
        ap.add_argument('--dbpath', default=self.dbpath,
                        help='Path to database file. Default: %(default)s')
        return ap.parse_args()

    def main(self):
        args = self.process_args()
        self.path = args.path
        self.threshold = args.threshold
        self.samplefile = args.samplefile
        self.recursive = args.recursive
        self.extviewer = args.extviewer
        self.program = args.program
        self.dbpath = os.path.expanduser(args.dbpath)
        self.dbfile += '_' + args.algorithm
        self.imagehash_class = ImageHash.get_subclass(args.algorithm)
        cmd_specified = (args.hash or args.cleanup or args.prune or args.search)
        self.load_database(must_exist=cmd_specified and not args.hash)
        # Execute commands
        if args.hash:
            self.cmd_hash()
        if args.cleanup:
            self.cmd_cleanup()
        if args.prune:
            self.cmd_prune()
        if args.search:
            self.cmd_search()
        if not cmd_specified:
            self.cmd_hash()
            self.cmd_cleanup()
            self.cmd_search()

    def cmd_hash(self):
        """Walk through `path` and add or update image hashes in database"""
        if not self.path:
            print('Path must be specified')
            return
        try:
            for dirpath, filenames in self.all_directories_with_filenames():
                self.update_db(dirpath, filenames)
        finally:
            self.save_database()

    def cmd_search(self):
        """Search database for similar images"""
        # If path was specified, search for duplicates only in path
        # Otherwise, all hashed images in database are searched
        if self.path:
            self.hashdb.filter_by_path(os.path.realpath(self.path))
        # If sample file was specified, search for similar images
        # Otherwise, search whole database for groups of similar images
        if self.samplefile:
            self.compare_with_db(self.samplefile)
        else:
            self.show_binary_dupes()
            self.search_db_for_dupes()

    def cmd_cleanup(self):
        """Check files in database, remove references
        to deleted or modified files from the database"""
        for item in self.hashdb.items:
            original_file_names = item.file_names
            item.check_file_names(fast=True)
            for filename in original_file_names.difference(item.file_names):
                print("Removing dead file reference", filename)
        self.save_database()

    def cmd_prune(self):
        """Check items in database, remove those without any references to files
        (when all references were removed by --cleanup)"""
        original_items_len = len(self.hashdb.items)
        self.hashdb.prune()
        pruned = original_items_len - len(self.hashdb.items)
        print("Pruned", pruned, "hashed files without any file names")
        self.save_database()

    def load_database(self, must_exist=False):
        try:
            with gzip.open(self.dbpath, 'rt', encoding='utf8') as f:
                dbitems = json.load(f)
            self.hashdb = HashDB.load(dbitems)
        except IOError:
            if must_exist:
                raise
            print("Could not read %r, "
                  "using new empty database..." % self.dbpath,
                  file=sys.stderr)

    def save_database(self):
        dbitems = self.hashdb.dump()
        with gzip.open(self.dbpath, 'wt', encoding='utf8') as f:
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

    def update_db(self, path, filenames):
        print('Hashing', path)
        with PoolExecutor(max_workers=os.cpu_count() or 4) as executor:
            # Compute hashes for new or updated files
            hashes = []
            hash_name = self.imagehash_class.algorithm()
            for fname in filenames:
                filepath = os.path.join(path, fname)
                file_hash = self.hashdb.add(filepath, fast_compare=False)
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

    def show_binary_dupes(self):
        i = 1
        for item in self.hashdb.items:
            if len(item.file_names) > 1:
                print('--- Files with same binary content (%s) ---' % i)
                for fname in item.file_names:
                    print(fname)
                if self.view(list(item.file_names), test_stop=True):
                    break
                i += 1

    def search_db_for_dupes(self):
        last_fname = None
        i = 1
        file_list = []
        threshold = 1.0 - (self.threshold / 100)
        hash_name = self.imagehash_class.algorithm()
        for fname_a, fname_b, distance in \
                self.hashdb.find_all_dups_without_derived(threshold, hash_name):
            if fname_a != last_fname:
                if self.view(file_list, test_stop=True):
                    file_list = []
                    break
                print('--- Perceptually similar images (%s) ---' % i)
                print(fname_a)
                file_list = [fname_a]
                last_fname = fname_a
                i += 1
            file_list.append(fname_b)
            self.print_out(fname_b, distance)
        self.view(file_list)

    def compare_with_db(self, samplefile):
        imghash = self.imagehash_class(samplefile)
        print(samplefile)
        file_list = [samplefile]
        threshold = 1.0 - (self.threshold / 100)
        hash_name = self.imagehash_class.algorithm()
        for fname, distance in self.hashdb.query(imghash, threshold, hash_name):
            self.print_out(fname, distance)
            file_list.append(fname)
        self.view(file_list)

    def print_out(self, fname, distance):
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
                subprocess.call([self.program] + file_list,
                                stdout=devnull, stderr=devnull)
            print('\r' + ' '*30 + '\r', end='')
            if test_stop:
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
                print('\r' + ' ' * 30 + '\r', end='')
