import argparse
from pathlib import Path
from .analysis.note_velocity_max import NoteVelocityMaxDetector


def main(argv=None):
    ap = argparse.ArgumentParser(description='PA800 full per-note velocity/MAX detector — analysis only, NO DNA')
    ap.add_argument('input', help='Input MIDI')
    ap.add_argument('--report', help='Detailed JSON output. Default: <input>.velocity_max.json')
    ap.add_argument('--csv', help='Flat per-note CSV output. Default: <input>.velocity_max.csv')
    ns = ap.parse_args(argv)
    inp = Path(ns.input)
    report_path = Path(ns.report) if ns.report else inp.with_suffix('.velocity_max.json')
    csv_path = Path(ns.csv) if ns.csv else inp.with_suffix('.velocity_max.csv')

    det = NoteVelocityMaxDetector()
    report = det.analyze(str(inp))
    det.write_json(report, str(report_path))
    det.write_csv(report, str(csv_path))

    s = report['summary']
    print('PASS — NOTE/VELOCITY MAX DETECTION')
    print('Input:', inp)
    print('Notes:', s['notes'])
    print('With profile:', s['with_profile'])
    print('Protected:', s['protected'])
    print('Velocity 127:', s['velocity_127'])
    print('Over contextual max:', s['over_contextual_max'])
    print('JSON:', report_path)
    print('CSV:', csv_path)


if __name__ == '__main__':
    main()