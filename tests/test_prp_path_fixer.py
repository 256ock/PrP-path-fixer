import gzip
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prp_path_fixer as f  # noqa: E402

NFC_PATH = "/Volumes/素材/ガイドライン/パーティー_ヴォーカル.mov"
NFD_PATH = unicodedata.normalize("NFD", NFC_PATH)
WIN_NFC = "D:\\素材\\ガイドライン\\パーティー_ヴォーカル.mov"


def make_xml(path: str, name: str = "パーティー") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" ?>\n'
        '<PremiereData Version="3">\n'
        '  <Media ObjectUID="1">\n'
        f"    <ActualMediaFilePath>{path}</ActualMediaFilePath>\n"
        f"    <FilePath>{path}</FilePath>\n"
        f"    <RelativePath>..{path}</RelativePath>\n"
        f"    <Title>{unicodedata.normalize('NFD', name)}</Title>\n"
        "  </Media>\n"
        "</PremiereData>\n"
    )


class NormalizeTest(unittest.TestCase):
    def test_nfd_differs_from_nfc(self):
        self.assertNotEqual(NFC_PATH, NFD_PATH)

    def test_roundtrip(self):
        self.assertEqual(f.normalize_text(NFD_PATH, "NFC"), NFC_PATH)
        self.assertEqual(f.normalize_text(NFC_PATH, "NFD"), NFD_PATH)

    def test_cjk_compat_ideograph_is_kept(self):
        # U+FA11 (﨑) は通常の NFC/NFD だと U+5D0E (崎) に化けてしまう
        s = "\uFA11" + unicodedata.normalize("NFD", "が")
        self.assertEqual(f.normalize_text(s, "NFC"), "\uFA11が")
        self.assertEqual(f.normalize_text("\uFA11が", "NFD"), s)


class XmlTest(unittest.TestCase):
    def test_mac_to_win_only_paths(self):
        xml, res = f.fix_xml_text(make_xml(NFD_PATH), "NFC")
        self.assertIn(f"<ActualMediaFilePath>{NFC_PATH}</ActualMediaFilePath>", xml)
        self.assertIn(f"<RelativePath>..{NFC_PATH}</RelativePath>", xml)
        self.assertEqual(res.count, 3)
        # クリップ名は既定では変更しない
        self.assertIn(unicodedata.normalize("NFD", "パーティー"), xml)

    def test_all_option(self):
        xml, _ = f.fix_xml_text(make_xml(NFD_PATH), "NFC", all_text=True)
        self.assertTrue(unicodedata.is_normalized("NFC", xml))

    def test_win_to_mac(self):
        xml, res = f.fix_xml_text(make_xml(WIN_NFC), "NFD")
        self.assertIn(unicodedata.normalize("NFD", WIN_NFC), xml)
        self.assertEqual(res.count, 3)

    def test_attributes_and_no_change(self):
        src = '<PremiereData><FilePath Version="1">abc.mov</FilePath></PremiereData>'
        xml, res = f.fix_xml_text(src, "NFC")
        self.assertEqual(xml, src)
        self.assertEqual(res.count, 0)
        src2 = f'<PremiereData><FilePath Version="1">{NFD_PATH}</FilePath></PremiereData>'
        xml2, _ = f.fix_xml_text(src2, "NFC")
        self.assertEqual(xml2, f'<PremiereData><FilePath Version="1">{NFC_PATH}</FilePath></PremiereData>')


class FileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, xml, compress=True):
        p = self.dir / name
        data = xml.encode("utf-8")
        p.write_bytes(gzip.compress(data) if compress else data)
        return p

    def test_gzip_file(self):
        src = self.write("proj.prproj", make_xml(NFD_PATH))
        self.assertEqual(f.process([src], "win"), 0)
        out = self.dir / "proj_win.prproj"
        raw = out.read_bytes()
        self.assertEqual(raw[:2], b"\x1f\x8b")
        self.assertIn(NFC_PATH, gzip.decompress(raw).decode("utf-8"))
        # 元ファイルは変更しない
        self.assertIn(NFD_PATH, gzip.decompress(src.read_bytes()).decode("utf-8"))

    def test_uncompressed_inplace(self):
        src = self.write("proj.prproj", make_xml(WIN_NFC), compress=False)
        self.assertEqual(f.process([src], "mac", inplace=True), 0)
        self.assertTrue((self.dir / "proj.prproj.bak").exists())
        text = src.read_text("utf-8")
        self.assertIn(unicodedata.normalize("NFD", WIN_NFC), text)

    def test_folder(self):
        self.write("a.prproj", make_xml(NFD_PATH))
        self.write("b.prproj", make_xml(NFC_PATH))
        self.assertEqual(f.process([self.dir], "win"), 0)
        # 修正不要な b は出力しない
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["a.prproj", "a_win.prproj", "b.prproj"])

    def test_not_premiere(self):
        src = self.write("x.prproj", "<foo/>")
        self.assertEqual(f.process([src], "win"), 1)


if __name__ == "__main__":
    unittest.main()
