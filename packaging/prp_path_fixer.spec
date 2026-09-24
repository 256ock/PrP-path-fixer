# PyInstaller spec: Mac は .app、Windows は単体 .exe を作る
#   pyinstaller packaging/prp_path_fixer.spec
import sys

a = Analysis([os.path.join(SPECPATH, "..", "prp_path_fixer.py")], excludes=["unittest"])
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PrP Path Fixer", console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="PrP Path Fixer")
    app = BUNDLE(
        coll,
        name="PrP Path Fixer.app",
        bundle_identifier="io.github.256ock.prp-path-fixer",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            # .prproj をアプリアイコンにドロップできるようにする
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "Premiere Pro Project",
                    "CFBundleTypeExtensions": ["prproj"],
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Alternate",
                }
            ],
        },
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="PrP-Path-Fixer", console=False)
