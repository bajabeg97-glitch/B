"""Materialize the canonical visible CI matrix into GitHub's hidden path."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]

def main():
    source=ROOT/'CI_RELEASE_MATRIX.yml';target=ROOT/'.github'/'workflows'/'release.yml';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);print(target);return 0

if __name__=='__main__':raise SystemExit(main())