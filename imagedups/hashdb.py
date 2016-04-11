import hashlib
import os
from itertools import combinations

from .imagehash import ImageHash


class HashItem:

    """Files are indexed by content properties:

    - file size
    - first 512 bytes hashed
    - whole content hashed
    - perceptual image hashes

    Same content can bear one or more filenames.

    """

    def __init__(self, filename=None):
        self.file_names = {filename} if filename else set()
        self.file_size = 0
        self.first_512_sha256 = None
        self._content_sha256 = None
        self.image_hash = {}
        self._partial_hash = None
        self._file = None
        if filename:
            self._file = open(filename, 'rb')
            self.file_size = os.fstat(self._file.fileno()).st_size
            data = self._file.read(512)
            self._partial_hash = hashlib.sha256(data)
            self.first_512_sha256 = self._partial_hash.hexdigest()

    def binary_equal(self, other: 'HashItem', fast=False):
        """Compare binary content.

        File names don't matter.
        Neither image hashes matter, they should be same when binary content is.

        Fast compare checks only file size and first 512 bytes.

        """
        return (self.file_size == other.file_size and
                self.first_512_sha256 == other.first_512_sha256 and
                (fast or self.content_sha256 == other.content_sha256))

    def check_file_names(self, fast=False):
        """Check files referenced by file names.

        Remove file name if file no longer exists or was modified.

        """
        file_names_ok = set()
        for filename in self.file_names:
            # Open and check content
            try:
                file_hash = HashItem(filename)
                if self.binary_equal(file_hash, fast=fast):
                    file_names_ok.add(filename)
            except IOError:
                pass
        self.file_names = file_names_ok

    @property
    def content_sha256(self):
        """Content hash is coputed lazily"""
        if self._file and self._partial_hash:
            while True:
                data = self._file.read(32 * 1024)
                if data:
                    self._partial_hash.update(data)
                else:
                    break
            self._content_sha256 = self._partial_hash.hexdigest()
            self._file.close()
            self._file = None
            self._partial_hash = None
        return self._content_sha256

    def dump(self) -> dict:
        """Dump the attributes into dict for easy serialization."""
        d = {
            'names': tuple(self.file_names),
            'size': self.file_size,
            'first_512b_sha256': self.first_512_sha256,
            'sha256': self.content_sha256,
        }
        for name, value in self.image_hash.items():
            d['ph_' + name] = str(value)
        return d

    @classmethod
    def load(cls, d: dict) -> 'HashItem':
        """Load the attributes from dict into new instance."""
        i = cls()
        i.file_names = set(d['names'])
        i.file_size = d['size']
        i.first_512_sha256 = d['first_512b_sha256']
        i._content_sha256 = d['sha256']
        for name, value in d.items():
            if name.startswith('ph_'):
                name = name[3:]
                i.image_hash[name] = ImageHash.get_subclass(name).load(value)
        return i


class HashDB:

    def __init__(self):
        # List of HashItem objects
        self.items = []

    def add(self, filename, fast_compare=False):
        """Add `filename` to database.

        First, binary content hash is computed, then it's compared to all items
        in database. If the content is equal to existing item, then the filename
        is added to this item. Otherwise new item is created.

        If `fast_compare` is requested, only hash of first 512 bytes and file
        size are compared.

        Returns HashItem object (added or found) with the filename.

        """
        file_hash = HashItem(filename)
        for item in self.items:
            if item.binary_equal(file_hash, fast=fast_compare):
                item.file_names.add(filename)
                return item
        self.items.append(file_hash)
        return file_hash

    def prune(self):
        """Remove items without file names."""
        for item in self.items[:]:
            if not item.file_names:
                self.items.remove(item)

    def filter_by_path(self, path):
        """Keep items with filename in `path`, drop the rest."""
        filtered_items = []
        for item in self.items:
            filtered_names = {name for name in item.file_names
                              if name.startswith(path)}
            if filtered_names:
                item.file_names = filtered_names
                filtered_items.append(item)
        self.items = filtered_items

    def find_all_dups(self, threshold, hash_name):
        """Find similar images in database.

        Returns generator of tuples (fname_a, fname_b, distance):

        * fname_a, fname_b: File names of pair of similar images.
        * distance: Normalized distance of hashes.

        Returned pairs are sorted by fname_a.

        """
        for item_a, item_b in combinations(self.items, 2):
            # Need file names for report
            if not item_a.file_names or not item_b.file_names:
                continue
            # Need hashes to compare
            hash_a = item_a.image_hash.get(hash_name)
            hash_b = item_b.image_hash.get(hash_name)
            if not hash_a or not hash_b:
                continue
            # Compare and report with one of file names
            distance = hash_a.distance(hash_b)
            if distance <= threshold:
                fname_a = sorted(item_a.file_names)[0]
                fname_b = sorted(item_b.file_names)[0]
                yield fname_a, fname_b, distance

    def find_all_dups_without_derived(self, threshold, hash_name):
        """Find similar images in database, skipping derived pairs.

        This is variant of :meth:`find_all_dups`, which avoids
        reporting subsets of already reported groups.
        For example: (x,a), (x,b), ... avoids (a,b) later.

        """
        reported = dict()
        for fname_a, fname_b, distance in self.find_all_dups(threshold, hash_name):
            for key in reported:
                if fname_a in reported[key] and fname_b in reported[key]:
                    # If both A and B were reported before as duplicates of X,
                    # skip this pair
                    break
            else:
                yield fname_a, fname_b, distance
                if fname_a not in reported:
                    reported[fname_a] = set()
                reported[fname_a].add(fname_b)

    def query(self, imghash, threshold, hash_name):
        """Find images close to given hash."""
        for item in self.items:
            item_hash = item.image_hash.get(hash_name)
            distance = imghash.distance(item_hash)
            if distance <= threshold:
                fname = sorted(item.file_names)[0]
                yield fname, distance

    def dump(self) -> list:
        return [item.dump() for item in self.items]

    @classmethod
    def load(cls, l: list) -> 'HashDB':
        i = cls()
        i.items = [HashItem.load(d) for d in l]
        return i


if __name__ == "__main__":
    # Self test
    hashdb = HashDB()
    hashdb.add(__file__)
    dumped = hashdb.dump()
    print(dumped)
    i2 = HashDB.load(dumped)
    print(i2.dump())
