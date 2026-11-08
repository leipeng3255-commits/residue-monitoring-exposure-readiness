"""Check saved derived-table structure and ADI conversions; no exposure estimation."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def verify(base):
    counts = {'cell_diagnostics.csv': 19, 'strict_37_ledger.csv': 37,
              'admission_decision_ledger.csv': 262, 'dietary_strata.csv': 88,
              'chronic_exposure_master.csv': 1672}
    tables = {}
    hashes = {}
    for name, expected in counts.items():
        path = base / 'tables' / name
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != expected:
            raise ValueError(f'{name}: expected {expected} rows, found {len(rows)}')
        tables[name] = rows
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    n = 0
    max_error = 0.0
    for row in tables['chronic_exposure_master.csv']:
        adi = float(row['adi_mg_kg_bw_day'])
        if not math.isfinite(adi) or adi <= 0:
            raise ValueError('ADI must be finite and positive')
        for stat in ('mean', 'HRP'):
            for bound in ('LB', 'UB'):
                exposure = float(row[f'exposure_{stat}_{bound}_ug_kg_bw_day'])
                observed = float(row[f'percent_ADI_{stat}_{bound}'])
                expected = exposure / (10 * adi)
                if not all(math.isfinite(x) and x >= 0 for x in (exposure, observed)):
                    raise ValueError('Invalid exposure or percent ADI')
                if not math.isclose(observed, expected, rel_tol=1e-10, abs_tol=1e-12):
                    raise ValueError(f'Inconsistent {stat}/{bound} percent ADI')
                n += 1
                max_error = max(max_error, abs(observed - expected))
    return {'status': 'PASS', 'table_rows': counts, 'adi_conversion_checks': n,
            'max_absolute_error': max_error, 'input_sha256': hashes,
            'new_exposure_calculations': 0,
            'scope': 'Internal saved-result arithmetic checks; not independent assessor validation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.data.resolve()), indent=2))
