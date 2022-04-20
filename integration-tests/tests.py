import sys
import tempfile
import unittest
import os
import subprocess
import hashlib


TESTS_DIR = os.path.join(os.getcwd(), 'integration-tests', 'data')


def find_tool():
    name = 'huffman-tool' if sys.platform.lower() != 'windows' else 'huffman-tool.exe'
    for root, dirs, files in os.walk(os.getcwd()):
        if name in files:
            return os.path.join(root, name)


def file_checksum(filename):
    checksum = hashlib.md5()
    with open(filename, 'rb') as file:
        for chunk in iter(lambda: file.read(1024 * 8), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def create_command(args, profiling=False):
    # TODO windows?
    command = ['time', '-f', '%e'] if profiling else []

    # TODO find an executable with this name
    command += [find_tool()] + args
    return command


def run_command(command):
    with subprocess.Popen(command, stderr=subprocess.PIPE) as sub:
        output = sub.stderr.read()
        sub.wait()
        return_code = sub.returncode
    return output, return_code


class TestCaseBase(unittest.TestCase):
    orig = None
    comp = None
    decomp = None

    @classmethod
    def setUpClass(cls):
        cls.comp = cls.orig + '.huf'
        orig, ext = os.path.split(cls.orig)
        cls.decomp = orig + '_decompressed' + ext

    def run_tool(self, mode, expect_error=False, profiling=False, limit=100., more_args=None):
        if more_args is None:
            more_args = []
        fi, fo = (self.orig, self.comp) if (mode == 'compress') else (self.comp, self.decomp)

        command = create_command(['--{}'.format(mode), '--input', fi, '--output', fo], profiling=profiling) + more_args

        output, return_code = run_command(command)
        # print(output)
        # print(return_code)
        self.assertNotEqual(expect_error, return_code == 0, 'Program exit code did not match expected')

        if profiling:
            elapsed = float(output.split(b'\n')[-2])  # TODO: guaranteed?
            self.assertLessEqual(elapsed, limit, 'Command in {} mode took too much time'.format(mode))

        if not expect_error:
            self.assertTrue(os.path.exists(fo), 'Output file in {} mode was not created'.format(mode))

    def run_correctness(self):
        self.run_tool('compress')
        self.run_tool('decompress')
        with open(self.orig, 'rb') as original:
            with open(self.decomp, 'rb') as decompressed:
                self.assertEqual(original.read(), decompressed.read(), 'Original and decompressed files do not match')

    def run_speed(self, comp_limit, decomp_limit):
        self.run_tool('compress', profiling=True, limit=comp_limit)
        self.run_tool('decompress', profiling=True, limit=decomp_limit)

    def run_compression_ratio(self, expected_ratio):
        self.run_tool('compress')
        self.run_tool('decompress')
        original_size = os.path.getsize(self.orig)
        compressed_size = os.path.getsize(self.comp)
        decompressed_size = os.path.getsize(self.decomp)
        self.assertEqual(original_size, decompressed_size)
        self.assertGreaterEqual(original_size / compressed_size, expected_ratio)

    @classmethod
    def tearDownClass(cls):
        if (cls.comp is not None) and os.path.exists(cls.comp):
            os.remove(cls.comp)
        if (cls.decomp is not None) and os.path.exists(cls.decomp):
            os.remove(cls.decomp)


class TestSimpleFile(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'simple.txt')
        super().setUpClass()

    def test_correctness(self):
        self.run_correctness()

    def test_speed(self):
        self.run_speed(0.01, 0.01)

    def test_compression_ratio(self):
        self.run_compression_ratio(1.6)

    def test_wrong_args(self):
        self.run_tool('compress', more_args=['1337'], expect_error=True)
        self.run_tool('compress', more_args=['--decompress'], expect_error=True)


class TestRealFile(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'war_and_peace.txt')
        super().setUpClass()

    def test_correctness(self):
        self.run_correctness()

    def test_speed(self):
        self.run_speed(0.54, 0.7)


class TestMissingFile(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'i_do_not_exist.txt')
        super().setUpClass()

    def test_error(self):
        self.run_tool('compress', expect_error=True)


class TestRestrictedFile(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'restricted.txt')
        os.chmod(cls.orig, 0o000)
        super().setUpClass()

    def test_error(self):
        self.skipTest('Can not change permissions on CI because it runs in root')
        self.run_tool('compress', expect_error=True)

    @classmethod
    def tearDownClass(cls):
        os.chmod(cls.orig, 0o644)


class TestNotArchiveDecompress(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'simple.txt')
        super().setUpClass()
        cls.comp = cls.orig

    def test_error(self):
        self.run_tool('decompress', expect_error=True)

    @classmethod
    def tearDownClass(cls):
        cls.comp = None
        super().tearDownClass()


class TestEmptyFile(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'empty.txt')
        super().setUpClass()

    def test_correctness(self):
        self.run_correctness()

    def test_compression_ratio(self):
        # compressed empty file must hold the tree, so it must not be empty
        self.run_compression_ratio(0.)


class TestRandomBytesFile(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'random_bytes')
        super().setUpClass()

    def test_correctness(self):
        self.run_correctness()

    def test_speed(self):
        self.run_speed(0.01, 0.01)

    def test_compression_ratio(self):
        # compressing random bytes is really bad
        self.run_compression_ratio(0.85)


class TestSomePDF(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'basov.pdf')
        super().setUpClass()

    def test_big(self):
        self.run_tool('compress', profiling=True, limit=4.)
        self.run_tool('decompress', profiling=True, limit=6.)

        original_size = os.path.getsize(self.orig)
        compressed_size = os.path.getsize(self.comp)
        decompressed_size = os.path.getsize(self.decomp)
        self.assertEqual(original_size, decompressed_size)
        self.assertEqual(file_checksum(self.orig), file_checksum(self.decomp))

        # pdf is binary and compresses not so good as well
        self.assertGreaterEqual(original_size / compressed_size, 1.2)


class TestSome8KJPG(TestCaseBase):
    @classmethod
    def setUpClass(cls):
        cls.orig = os.path.join(TESTS_DIR, 'buggati.jpg')
        super().setUpClass()

    def test_big(self):
        self.run_tool('compress', profiling=True, limit=1.2)
        self.run_tool('decompress', profiling=True, limit=0.8)

        original_size = os.path.getsize(self.orig)
        compressed_size = os.path.getsize(self.comp)
        decompressed_size = os.path.getsize(self.decomp)
        self.assertEqual(original_size, decompressed_size)
        self.assertEqual(file_checksum(self.orig), file_checksum(self.decomp))

        # jpg is binary and compresses not so good as well
        self.assertGreaterEqual(original_size / compressed_size, 1.0001)


class TestRandomDirectories(unittest.TestCase):
    def run_dir(self, dir):
        for (dir, _, filenames) in os.walk(dir):
            for filename in filenames:
                path = os.path.join(dir, filename)
                if not os.access(path, os.R_OK):
                    continue
                if dir.endswith(os.path.join('integration-tests', 'data')):
                    continue

                comp = path + '.huf'
                decomp = path + '.dehuf'

                command = create_command(['--compress', '--input', path, '--output', comp])
                _, rc = run_command(command)
                if rc != 0:
                    continue
                self.assertTrue(os.path.exists(comp), 'Output compressed file not created')

                command = create_command(['--decompress', '--input', comp, '--output', decomp])
                _, rc = run_command(command)
                self.assertEqual(rc, 0, 'Return code of decompress is not zero, while compress succeeded')
                self.assertTrue(os.path.exists(decomp), 'Output decompressed file not created')

                # TODO: maybe check content?
                # TODO: may fail because tmp may change!
                self.assertEqual(file_checksum(path), file_checksum(decomp), 'Checksum not matched')

                os.remove(comp)
                os.remove(decomp)

    def test_tmp(self):
        self.run_dir(tempfile.gettempdir())

    def test_source(self):
        self.run_dir(os.path.abspath(os.getcwd()))


if __name__ == '__main__':
    unittest.main()
