"""Build the immutable Factory/Gold neural evidence manifest."""
import argparse
import json
from pathlib import Path

from pa800_optimizer.neural.corpus_router import build_corpus_manifest, validate_corpus_manifest


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--factory', default=str(root / 'corpus' / 'Factory Styles.zip'))
    parser.add_argument('--gold', default=str(root / 'corpus' / 'Gold DNA.zip'))
    parser.add_argument('--output', default=str(root / 'corpus' / 'FACTORY_GOLD_CORPUS_MANIFEST.json'))
    args = parser.parse_args(argv)
    manifest = build_corpus_manifest(args.factory, args.gold)
    audit = validate_corpus_manifest(manifest)
    if not audit['pass']: raise SystemExit('Corpus audit failed: ' + repr(audit['errors']))
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__': raise SystemExit(main())
