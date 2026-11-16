# Studio document and font notices

The personal document exporter uses the following Python packages. These components retain their original licenses; the application's MIT license does not replace them. Copies below are taken unchanged from the installed official wheel distributions.

| Component | Version | License metadata | Included notice |
|---|---|---|---|
| [python-docx](https://pypi.org/project/python-docx/1.2.0/) |1.2.0|MIT|[LICENSE](studio-documents/python-docx-LICENSE)|
| [ReportLab](https://pypi.org/project/reportlab/5.1.0/) |5.1.0|BSD-style ReportLab license|[LICENSE](studio-documents/reportlab-LICENSE)|
| [lxml](https://pypi.org/project/lxml/6.1.3/) |6.1.3|BSD-3-Clause, with included dependency notices|[LICENSE](studio-documents/lxml-LICENSE.txt), [additional licenses](studio-documents/lxml-LICENSES.txt)|
| [Pillow](https://pypi.org/project/Pillow/13.0.0/) |13.0.0|MIT-CMU and included notices|[LICENSE](studio-documents/Pillow-LICENSE)|
| [typing extensions](https://pypi.org/project/typing_extensions/4.16.0/) |4.16.0|PSF-2.0|[LICENSE](studio-documents/typing-extensions-LICENSE)|
| [charset-normalizer](https://pypi.org/project/charset-normalizer/3.5.2/) |3.5.2|MIT|[LICENSE](studio-documents/charset-normalizer-LICENSE)|

## Embedded DejaVu fonts

PDF output embeds subsets of unmodified DejaVu Sans, DejaVu Serif or DejaVu Sans Mono 2.37. The [full font license](studio-documents/DejaVu-LICENSE.txt) preserves Bitstream Vera and Arev attribution and the DejaVu public-domain changes. No Windows system-font file is copied or redistributed, and no system font is installed.

Official project: [DejaVu fonts](https://dejavu-fonts.github.io/). Distribution: [official 2.37 GitHub release](https://github.com/dejavu-fonts/dejavu-fonts/releases/tag/version_2_37). The downloaded ZIP SHA-256 matches the [publisher's checksum](https://dejavu-fonts.github.io/Download.html): `7576310b219e04159d35ff61dd4a4ec4cdba4f35c00e002a136f00e96a908b0a`.

| Unmodified font file | SHA-256 |
|---|---|
|DejaVuSans.ttf|`7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954`|
|DejaVuSerif.ttf|`42d1edeb7952f31b1f96d767ed7030b08a39e0c372b0071641518864e2bffb51`|
|DejaVuSansMono.ttf|`b4a6c3e4faab8773f4ff761d56451646409f29abedd68f05d38c2df667d3c582`|

[Machine-readable provenance](studio-documents/provenance.json) records exact wheel download URLs/hashes, unchanged license-copy hashes and font files. The source archive itself is a development acquisition artifact, rather than an additional application runtime download. The exporter verifies the bundled font identities before embedding them.

DOCX is generated as editable text; it selects a named local font family with application fallbacks and does not embed proprietary Windows fonts. Romanian selectable text and the recorded Latin examples were tested. This notice does not assert certified shaping for every script.

pypdf 7.1.0 and pypdfium2 5.15.2 were used only for extraction/render verification. They are not required by the application exporter and need not be included in the runtime package.
