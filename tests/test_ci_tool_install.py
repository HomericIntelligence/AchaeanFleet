"""Check checksum and extraction boundaries for native CI tooling."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class CIToolInstallTests(unittest.TestCase):
    def test_only_verified_regular_executable_is_installed(self):
        path = ROOT / "ci/install_tools.py"
        self.assertTrue(path.is_file(), "native CI tools need a checksum-verifying installer")
        spec = importlib.util.spec_from_file_location("ci_install_tools", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("raw", "tar.gz", "zip"):
                with self.subTest(kind=kind):
                    data = b"synthetic executable bytes"
                    buffer = io.BytesIO()
                    if kind == "tar.gz":
                        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
                            member = tarfile.TarInfo("tool")
                            member.size = len(data)
                            archive.addfile(member, io.BytesIO(data))
                        encoded = buffer.getvalue()
                    elif kind == "zip":
                        with zipfile.ZipFile(buffer, "w") as archive:
                            archive.writestr("tool", data)
                        encoded = buffer.getvalue()
                    else:
                        encoded = data
                    source = root / "archive"
                    source.write_bytes(encoded)
                    destination = root / (kind + ".executable")
                    with self.assertRaisesRegex(ValueError, "checksum"):
                        module.install_archive(source, "0" * 64, kind, "tool", destination)
                    self.assertFalse(destination.exists())
                    module.install_archive(source, hashlib.sha256(encoded).hexdigest(), kind, "tool", destination)
                    self.assertEqual(destination.read_bytes(), data)
                    self.assertEqual(destination.stat().st_mode & 0o777, 0o755)
            source = root / "link.tar.gz"
            with tarfile.open(source, "w:gz") as archive:
                member = tarfile.TarInfo("tool")
                member.type = tarfile.SYMTYPE
                member.linkname = "/outside"
                archive.addfile(member)
            with self.assertRaisesRegex(ValueError, "regular"):
                module.install_archive(source, hashlib.sha256(source.read_bytes()).hexdigest(), "tar.gz", "tool", root / "rejected")


if __name__ == "__main__":
    unittest.main()
