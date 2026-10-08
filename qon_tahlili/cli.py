"""Terminaldan sinash uchun:

    python -m qon_tahlili.cli --jins m --yosh 45 "Gemoglobin 98, MCV 74, glyukoza 6.4, LDL 4.1"
    python -m qon_tahlili.cli --jins f --yosh 30 < natijalar.txt
"""
import argparse
import re
import sys

from qon_tahlili.analyzer import analyze
from qon_tahlili.parser import parse_text
from qon_tahlili.report import render


def main() -> None:
    ap = argparse.ArgumentParser(description="Qon tahlili natijalarini baholash")
    ap.add_argument("--jins", choices=["m", "f"], required=True, help="m — erkak, f — ayol")
    ap.add_argument("--yosh", type=int, help="yosh (to'liq yillar)")
    ap.add_argument("matn", nargs="?", help="natijalar matni (berilmasa stdin'dan o'qiladi)")
    args = ap.parse_args()

    text = args.matn if args.matn is not None else sys.stdin.read()
    values = parse_text(text)
    if not values:
        sys.exit("Birorta ham ko'rsatkich tanilmadi.")
    for message in render(analyze(values, args.jins, args.yosh)):
        print(re.sub(r"</?(b|i|code)>", "", message).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
        print("-" * 60)


if __name__ == "__main__":
    main()
