"""NZ Q1 release sensitivity, preserving the original target and every raw identity.

Run from the repository with the configured Python environment. Default writes a
new, non-overwriting output directory only after all checks pass; --check-only
performs the same calculations without writing; --verify-only compares a fresh
calculation with the existing artefacts. No download or exposure estimation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
SHEET = 'Table 1.1 All results'
IDS = {'Q1': '65331', 'Q2': '66750', 'Q3': '70426', 'Q4': '70430'}
LABELS = {'Q1': 'Q1-only container / 65331', 'Q2': 'Q2-only container / 66750',
          'Q3': 'Q1+Q3 container / 70426', 'Q4': 'Q2+Q4 container / 70430'}
SWEETCORN_RAW = 'sweetcorn, frozen and canned'
SWEETCORN_MATCH = 'Sweetcorn, frozen and canned'
DIRECTIONS = {'BRAND1_ABOVE', 'BRAND1_BELOW'}
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ABS_TOL, REL_TOL = D('1e-12'), D('1e-10')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def config():
    # paths.yaml uses quoted scalar paths; reject unsupported or missing values.
    cfg = {k: json.loads(v.strip()) for k, v in
           (line.split(':', 1) for line in (ROOT / '00_admin/paths.yaml').read_text().splitlines()
            if re.match(r'^[a-z_]+:\s*"', line))}
    assert Path(cfg['project_root']).resolve() == ROOT
    return cfg


def normalized_key(key):
    """One documented food-label substitution; never lowercase arbitrary keys."""
    return (SWEETCORN_MATCH if key[0] == SWEETCORN_RAW else key[0],) + key[1:]


def text(value):
    return '' if value is None else str(value)


def number(value):
    v = D(str(value).strip().replace(',', '.'))
    assert v.is_finite() and v >= 0, value
    return v


def interval(value):
    v = str(value).strip()
    assert value is not None and v
    if v in ('N/R', 'N/A'):
        return v, None
    if v.startswith('<'):
        limit = number(v[1:])
        assert limit > 0
        return 'BELOW_LOQ', (D(0), limit)
    n = number(value)
    return 'VAL', (n, n)


def evaluate(values):
    a_state, a = interval(values[0])
    b_state, b = interval(values[1])
    result = dict(brand1_state=a_state, brand2_state=b_state,
                  difference_LB='', difference_UB='', mean_LB='', mean_UB='')
    if a is None or b is None:
        result['decision'] = 'HOLD_NO_VALID_RESULT'
    else:
        lo, hi = a[0] - b[1], a[1] - b[0]
        assert lo <= hi
        result.update(difference_LB=str(lo), difference_UB=str(hi),
                      mean_LB=str((a[0] + b[0]) / 2), mean_UB=str((a[1] + b[1]) / 2),
                      decision=('BRAND1_ABOVE' if lo > 0 else 'BRAND1_BELOW' if hi < 0
                                else 'EXACT_RECORDED_TIE' if lo == hi == 0
                                else 'UNRESOLVED_CENSORING'))
    return result


def read_openpyxl(path, sheet=SHEET):
    book = load_workbook(path, read_only=True, data_only=False)
    ws = book[sheet]
    it = ws.iter_rows(values_only=True)
    header = tuple(next(it))
    unit = header.index('Unit')
    grouped = defaultdict(list)
    for rn, row in enumerate(it, 2):
        if not row[0] or not row[2]:
            continue
        assert row[unit] == 'mg/kg'
        key = tuple(row[:3]) + (row[unit],)
        grouped[key].append(dict(row=rn, key=key, full_row=tuple(row[:unit + 1]),
                                 values=tuple(row[3:unit])))
    anchors = []
    if sheet == SHEET:
        # Contents has a styled, very wide used range. Read only relevant column A.
        for rn, row in enumerate(book['Contents'].iter_rows(min_row=1, max_row=65,
                                                           max_col=1, values_only=True), 1):
            if row[0] is not None:
                anchors.append(dict(sheet='Contents', cell=f'A{rn}', value=row[0]))
    book.close()
    return header, dict(grouped), anchors


def read_xml(path, sheet):
    """Direct OOXML reader, independent of openpyxl and primary interval parsing."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(t.text or '' for t in e.iter() if t.tag.endswith('}t'))
                      for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        rels = {e.attrib['Id']: e.attrib['Target']
                for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets = ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS)
        found = next(e for e in sheets if e.attrib['name'] == sheet)
        rid = found.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        target = rels[rid]
        target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        result = {}
        with z.open(target) as stream:
            for _, element in ET.iterparse(stream, events=['end']):
                if not element.tag.endswith('}row'):
                    continue
                row = {}
                for cell in element.findall('s:c', NS):
                    assert cell.find('s:f', NS) is None, 'Formula in audited source sheet'
                    val = cell.find('s:v', NS)
                    typ = cell.attrib.get('t')
                    value = (''.join(t.text or '' for t in cell.iter() if t.tag.endswith('}t'))
                             if typ == 'inlineStr' else shared[int(val.text)]
                             if typ == 's' and val is not None else val.text if val is not None else None)
                    row[re.sub(r'\d', '', cell.attrib['r'])] = value
                result[int(element.attrib['r'])] = row
                element.clear()
        return result


def xml_calculation(row):
    """Separate Decimal arithmetic on the stored numeric lexemes."""
    bounds = []
    states = []
    for col in ('D', 'E'):
        source = row[col].strip()
        if source == 'N/R' or source == 'N/A':
            states.append(source)
            bounds.append(None)
        elif source[:1] == '<':
            limit = D(source[1:].strip().replace(',', '.'))
            assert limit.is_finite() and limit > 0
            states.append('BELOW_LOQ')
            bounds.append([D(0), limit])
        else:
            v = D(source.replace(',', '.'))
            assert v.is_finite() and v >= 0
            states.append('VAL')
            bounds.append([v, v])
    out = {'brand1_state': states[0], 'brand2_state': states[1], 'difference_LB': '',
           'difference_UB': '', 'mean_LB': '', 'mean_UB': ''}
    if None in bounds:
        out['decision'] = 'HOLD_NO_VALID_RESULT'
    else:
        low = bounds[0][0] - bounds[1][1]
        high = bounds[0][1] - bounds[1][0]
        out.update(difference_LB=str(low), difference_UB=str(high),
                   mean_LB=str(sum(v[0] for v in bounds) / D(2)),
                   mean_UB=str(sum(v[1] for v in bounds) / D(2)))
        if low > 0:
            out['decision'] = 'BRAND1_ABOVE'
        elif high < 0:
            out['decision'] = 'BRAND1_BELOW'
        elif low == 0 and high == 0:
            out['decision'] = 'EXACT_RECORDED_TIE'
        else:
            out['decision'] = 'UNRESOLVED_CENSORING'
    return out


def close(a, b):
    return abs(D(a) - D(b)) <= max(ABS_TOL, abs(D(a)) * REL_TOL)


def csv_string(rows):
    stream = io.StringIO(newline='')
    w = csv.DictWriter(stream, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return stream.getvalue()


def build(cfg):
    raw = Path(cfg['raw_data_root'])
    baseline = Path(cfg['outputs_root']) / 'diagnostics/depth_feasibility_20261015/source_provenance.json'
    known = {Path(r['path']).name: r for r in json.loads(baseline.read_text())}
    manifest_bytes = (ROOT / '00_admin/download_manifest.csv').read_bytes()
    manifest = list(csv.DictReader(io.StringIO(manifest_bytes.decode('utf-8-sig'))))
    sources, anchors, tables, xml_tables, headers = [], [], {}, {}, {}
    raw_roundoffs, max_raw_roundoff, raw_cells_verified = 0, D(0), 0
    for q, source_id in IDS.items():
        path = raw / f'new_zealand_mpi_total_diet_study/2024_{q}/NZTDS_2024_{q}_{source_id}.xlsx'
        record = known[path.name]
        digest = sha(path)
        assert digest == record['sha256'] and path.stat().st_size == record['size']
        matches = [r for r in manifest if r['local_file_path'] == str(path)
                   and r['sha256'] == digest and int(r['bytes']) == path.stat().st_size]
        assert matches
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
        header, table, notes = read_openpyxl(path)
        xml = read_xml(path, SHEET)
        unit_col = get_column_letter(header.index('Unit') + 1)
        xml_records = {rn: row for rn, row in xml.items() if rn > 1 and row.get('A') and row.get('C')}
        assert len(xml_records) == sum(len(v) for v in table.values())
        for key, entries in table.items():
            for entry in entries:
                x = xml_records[entry['row']]
                assert key == (x['A'], x['B'], x['C'], x[unit_col])
                for i, val in enumerate(entry['full_row'], 1):
                    vxml = x.get(get_column_letter(i))
                    if isinstance(val, (int, float)):
                        diff = abs(D(str(val)) - D(vxml))
                        assert close(str(val), vxml)
                        raw_roundoffs += int(diff > 0)
                        max_raw_roundoff = max(max_raw_roundoff, diff)
                    else:
                        assert val == vxml, (q, entry['row'], i, val, vxml)
                    raw_cells_verified += 1
        xml_contents = read_xml(path, 'Contents')
        for note in notes:
            assert xml_contents[int(note['cell'][1:])]['A'] == note['value']
            anchors.append(dict(source=q, source_label=LABELS[q], source_sha256=digest, **note))
        sources.append(dict(source=q, label=LABELS[q], path=str(path), bytes=path.stat().st_size,
                            sha256=digest, official_url=record['url'], filename=record['filename'],
                            sheet=SHEET, rows=sum(map(len, table.values())), distinct_raw_keys=len(table),
                            result_column_labels=list(header[3:header.index('Unit')]), zip_integrity='PASS'))
        tables[q], xml_tables[q], headers[q] = table, xml_records, header

    # Both Q1 containers describe the same Q1 republication date. No authority ranking.
    a12 = {q: next(a['value'] for a in anchors if a['source'] == q and a['cell'] == 'A12')
           for q in ('Q1', 'Q3')}
    assert a12['Q1'] == a12['Q3'] and '26 August 2025' in a12['Q1']
    normalized = {}
    normalization = []
    for q in ('Q1', 'Q3'):
        table = tables[q]
        assert all(len(v) == 1 for v in table.values())
        norm = {}
        for key, entries in table.items():
            new = normalized_key(key)
            assert new not in norm, ('FOOD_IDENTITY_COLLISION', q, key)
            norm[new] = entries[0]
            if new != key:
                normalization.append(dict(source=q, source_row=entries[0]['row'],
                                          raw_key_json=json.dumps(key, ensure_ascii=False),
                                          match_key_json=json.dumps(new, ensure_ascii=False),
                                          operation='EXACT_SWEETCORN_INITIAL_CASE_ONLY'))
        normalized[q] = norm
    assert len(tables['Q1']) == 19422
    assert set(normalized['Q1']).issubset(normalized['Q3'])

    old_csv = Path(cfg['intermediate_data_root']) / 'tds_semantics_challenge_20261013/nz_brand_record_ordering.csv'
    historical = {(r['commodity'], r['group'], r['compound'], r['unit']): r
                  for r in csv.DictReader(old_csv.open(encoding='utf-8-sig'))}
    assert set(historical) == set(tables['Q1'])
    pairs, conflicts, source_counts, cross_counts = [], [], {'Q1': Counter(), 'Q3': Counter()}, Counter()
    source_states = {'Q1': Counter(), 'Q3': Counter()}
    stable_direction_counts = Counter()
    endpoint_roundoffs, max_endpoint_roundoff, endpoint_checks = 0, D(0), 0
    mean_equal = mean_held = original_reconciled = 0
    for key, entries in tables['Q1'].items():
        left = entries[0]
        right = normalized['Q3'][normalized_key(key)]
        evaluations = {q: evaluate(entry['values'][:2]) for q, entry in [('Q1', left), ('Q3', right)]}
        for q, entry in [('Q1', left), ('Q3', right)]:
            src = evaluations[q]
            check = xml_calculation(xml_tables[q][entry['row']])
            for field in src:
                if field.endswith(('_LB', '_UB')) and src[field] != '':
                    delta = abs(D(src[field]) - D(check[field]))
                    assert close(src[field], check[field]), (q, key, field)
                    endpoint_roundoffs += int(delta > 0)
                    max_endpoint_roundoff = max(max_endpoint_roundoff, delta)
                    endpoint_checks += 1
                else:
                    assert src[field] == check[field], (q, key, field)
            source_counts[q][src['decision']] += 1
            source_states[q].update([src['brand1_state'], src['brand2_state']])
            if src['decision'] == 'HOLD_NO_VALID_RESULT':
                assert 'N/R' in (src['brand1_state'], src['brand2_state'])
                assert 'N/A' not in (src['brand1_state'], src['brand2_state'])
        original = historical[key]
        assert int(original['source_row']) == left['row']
        for field in ['brand1_source', 'brand2_source']:
            assert original[field] == text(left['values'][0 if field == 'brand1_source' else 1])
        assert all(original[f] == evaluations['Q1'][f] for f in ['difference_LB', 'difference_UB', 'decision'])
        original_reconciled += 1
        da, db = evaluations['Q1']['decision'], evaluations['Q3']['decision']
        stability = ('DIRECTION_STABLE' if da == db and da in DIRECTIONS
                     else 'SOURCE_VERSION_CONFLICT' if da != db
                     else 'HOLD_NO_VALID_RESULT' if da == 'HOLD_NO_VALID_RESULT'
                     else 'EXACT_RECORDED_TIE' if da == 'EXACT_RECORDED_TIE'
                     else 'UNRESOLVED_CENSORING')
        cross_counts[stability] += 1
        if stability == 'DIRECTION_STABLE':
            stable_direction_counts[da] += 1
        mean_state = ('HOLD_NO_VALID_RESULT' if da == 'HOLD_NO_VALID_RESULT' or db == 'HOLD_NO_VALID_RESULT'
                      else 'UNCHANGED' if all(D(evaluations['Q1'][f]) == D(evaluations['Q3'][f])
                                             for f in ('mean_LB', 'mean_UB')) else 'CHANGED')
        mean_equal += int(mean_state == 'UNCHANGED')
        mean_held += int(mean_state == 'HOLD_NO_VALID_RESULT')
        pair = dict(target_index=len(pairs) + 1, commodity_q1=key[0], commodity_q1q3=right['key'][0],
                    group=key[1], compound=key[2], unit=key[3],
                    raw_key_q1_json=json.dumps(key, ensure_ascii=False), raw_key_q1q3_json=json.dumps(right['key'], ensure_ascii=False),
                    match_key_json=json.dumps(normalized_key(key), ensure_ascii=False),
                    identity_match='EXACT_RAW_KEY' if key == right['key'] else 'EXACT_SWEETCORN_INITIAL_CASE_ONLY',
                    q1_source_id='65331', q1q3_source_id='70426', source_sheet=SHEET,
                    q1_row=left['row'], q1q3_row=right['row'],
                    q1_brand1_cell=f'D{left["row"]}', q1_brand2_cell=f'E{left["row"]}',
                    q1q3_brand1_cell=f'D{right["row"]}', q1q3_brand2_cell=f'E{right["row"]}',
                    q1_brand1_source=text(left['values'][0]), q1_brand2_source=text(left['values'][1]),
                    q1q3_brand1_source=text(right['values'][0]), q1q3_brand2_source=text(right['values'][1]),
                    **{f'{"q1" if q == "Q1" else "q1q3"}_{field}': val
                       for q, ev in evaluations.items() for field, val in ev.items()},
                    cross_source_status=stability, mean_endpoint_comparison=mean_state)
        pairs.append(pair)
        for i, col in enumerate(('D', 'E')):
            if left['values'][i] != right['values'][i]:
                conflicts.append(dict(target_index=pair['target_index'], commodity=key[0], group=key[1], compound=key[2],
                                      unit=key[3], sheet=SHEET, brand=i + 1,
                                      q1_source_id='65331', q1_cell=f'{col}{left["row"]}',
                                      q1_value=text(left['values'][i]), q1_xml_lexeme=xml_tables['Q1'][left['row']][col],
                                      q1q3_source_id='70426', q1q3_cell=f'{col}{right["row"]}',
                                      q1q3_value=text(right['values'][i]), q1q3_xml_lexeme=xml_tables['Q3'][right['row']][col],
                                      q1_decision=da, q1q3_decision=db, source_version_status=stability,
                                      mean_endpoint_comparison=mean_state,
                                      q1_mean_LB=evaluations['Q1']['mean_LB'], q1_mean_UB=evaluations['Q1']['mean_UB'],
                                      q1q3_mean_LB=evaluations['Q3']['mean_LB'], q1q3_mean_UB=evaluations['Q3']['mean_UB']))
    assert original_reconciled == len(pairs) == 19422
    assert len(normalization) == 285
    assert len(conflicts) == 2 and len({r['target_index'] for r in conflicts}) == 1
    assert all(r['commodity'] == 'Jam' and r['compound'] == 'Captan (sum of residues expressed as captan)' for r in conflicts)
    assert all(sum(c[d] for d in DIRECTIONS) == 61 and c['UNRESOLVED_CENSORING'] == 19246
               and c['HOLD_NO_VALID_RESULT'] == 115 and sum(c.values()) == 19422 for c in source_counts.values())
    assert cross_counts == Counter(DIRECTION_STABLE=60, SOURCE_VERSION_CONFLICT=1,
                                  UNRESOLVED_CENSORING=19246, HOLD_NO_VALID_RESULT=115)

    extras = [dict(source='Q3', source_label=LABELS['Q3'], source_row=e['row'],
                   raw_key_json=json.dumps(e['key'], ensure_ascii=False), full_row_json=json.dumps(e['full_row']),
                   exclusion='OUTSIDE_ORIGINAL_Q1_TARGET_NOT_ADDED_TO_DENOMINATOR')
              for k, e in normalized['Q3'].items() if k not in normalized['Q1']]
    assert len(extras) == 1

    # Separate regional identity ledger; neither a denominator extension nor a repair.
    holds = []
    q4_path = Path(next(r['path'] for r in sources if r['source'] == 'Q4'))
    _, q4_others, _ = read_openpyxl(q4_path, '1.19 Others')
    duplicates = {k: v for k, v in tables['Q4'].items() if len(v) > 1}
    missing = {k: v for k, v in tables['Q2'].items() if k not in tables['Q4']}
    for k, entries in duplicates.items():
        assert 'Spinetoram' in k[2] and all(e['full_row'] == entries[0]['full_row'] for e in entries)
        assert len(q4_others[k]) == 2
        for e in entries:
            holds.append(dict(issue='DUPLICATE_RAW_IDENTITY_HOLD', source='Q4', sheet=SHEET,
                              source_row=e['row'], raw_key_json=json.dumps(k, ensure_ascii=False),
                              full_row_json=json.dumps(e['full_row'], ensure_ascii=False),
                              related_same_file_sheet_rows=json.dumps([v['row'] for v in q4_others[k]]),
                              disposition='PRESERVE_ALL_ROWS_NO_COLLAPSE_NO_CHEMICAL_RELABEL', in_q1_target=False))
    for k, entries in missing.items():
        assert 'Spinosad' in k[2]
        for e in entries:
            holds.append(dict(issue='Q2_SPINOSAD_IDENTITY_ABSENT_IN_Q2Q4_HOLD', source='Q2', sheet=SHEET,
                              source_row=e['row'], raw_key_json=json.dumps(k, ensure_ascii=False),
                              full_row_json=json.dumps(e['full_row'], ensure_ascii=False), related_same_file_sheet_rows='',
                              disposition='NO_INFERRED_REPLACEMENT_OR_RELABEL', in_q1_target=False))
    q2_safe = {k: v[0] for k, v in tables['Q2'].items() if len(v) == 1}
    q4_safe = {k: v[0] for k, v in tables['Q4'].items() if len(v) == 1}
    common = set(q2_safe) & set(q4_safe)
    assert all(q2_safe[k]['values'][:4] == q4_safe[k]['values'][:4] for k in common)
    assert len(duplicates) == 4 and sum(map(len, duplicates.values())) == 8 and len(missing) == 2
    assert len(common) == 11734
    mirror = [{'sheet': '1.19 Others', 'key': k, 'records': v} for k, v in q4_others.items() if k in duplicates]
    # Check mirror table with the separate reader as well.
    xothers = read_xml(q4_path, '1.19 Others')
    for group in mirror:
        for e in group['records']:
            assert tuple(text(v) for v in e['full_row']) == tuple(xothers[e['row']].get(get_column_letter(i), '') or ''
                                                               for i in range(1, len(e['full_row']) + 1))
    for source in sources:
        assert sha(Path(source['path'])) == source['sha256']
        source['raw_sha_after_equal'] = True

    conflict_pair = next(p for p in pairs if p['cross_source_status'] == 'SOURCE_VERSION_CONFLICT')
    # Exact symmetry: swapping the two inputs reverses the contrast, preserves its mean.
    assert D(conflict_pair['q1_difference_LB']) == -D(conflict_pair['q1q3_difference_UB'])
    assert D(conflict_pair['q1_difference_UB']) == -D(conflict_pair['q1q3_difference_LB'])
    assert [conflict_pair['q1_brand1_source'], conflict_pair['q1_brand2_source']] == [
        conflict_pair['q1q3_brand2_source'], conflict_pair['q1q3_brand1_source']]
    xc1 = xml_calculation(xml_tables['Q1'][conflict_pair['q1_row']])
    xc3 = xml_calculation(xml_tables['Q3'][conflict_pair['q1q3_row']])
    assert xc1['mean_LB'] == xc3['mean_LB'] and xc1['mean_UB'] == xc3['mean_UB']
    mean_check = dict(food='Jam', chemical='Captan (sum of residues expressed as captan)', unit='mg/kg',
                      definition='Unweighted arithmetic mean of the two recorded Q1 brand composites; not exposure',
                      q1_difference=[conflict_pair['q1_difference_LB'], conflict_pair['q1_difference_UB']],
                      q1q3_difference=[conflict_pair['q1q3_difference_LB'], conflict_pair['q1q3_difference_UB']],
                      both_sources_mean_display_decimal=[conflict_pair['q1_mean_LB'], conflict_pair['q1_mean_UB']],
                      both_sources_mean_xml_decimal=[xc1['mean_LB'], xc1['mean_UB']],
                      exact_xml_decimal_swap_and_mean_check=True,
                      precision_note='XML stores 0.041 as 0.041000000000000002. Extra digits are serialization precision, not analytical precision.',
                      display='mean in [0.0205, 0.0255] mg/kg; contrast changes from [-0.041, -0.031] to [0.031, 0.041] mg/kg')
    categories = ['BRAND1_ABOVE', 'BRAND1_BELOW', 'UNRESOLVED_CENSORING', 'HOLD_NO_VALID_RESULT']
    joint = Counter((r['q1_decision'], r['q1q3_decision']) for r in pairs)
    assert all(a in categories and b in categories for a, b in joint)
    joint_rows = [dict(q1_65331_decision=a, q1_in_70426_decision=b,
                       target_keys=19422, keys=joint[a, b], row_order=i, column_order=j)
                  for i, a in enumerate(categories, 1) for j, b in enumerate(categories, 1)]
    assert len(joint_rows) == 16 and sum(r['keys'] for r in joint_rows) == 19422
    endpoint_rows = []
    for q, prefix, xmlcheck in [('Q1', 'q1', xc1), ('Q3', 'q1q3', xc3)]:
        for estimand in ('difference', 'mean'):
            endpoint_rows.append(dict(food='Jam', compound=mean_check['chemical'], source_id=IDS[q],
                                      source_label=LABELS[q], quarter_comparison='Q1 only', sheet=SHEET,
                                      brand1_cell='D2644', brand2_cell='E2644',
                                      brand1_source=conflict_pair[f'{prefix}_brand1_source'],
                                      brand2_source=conflict_pair[f'{prefix}_brand2_source'],
                                      estimand='Brand 1 minus Brand 2' if estimand == 'difference' else 'Unweighted two-brand mean',
                                      lower=conflict_pair[f'{prefix}_{estimand}_LB'],
                                      upper=conflict_pair[f'{prefix}_{estimand}_UB'], unit='mg/kg',
                                      xml_lower=xmlcheck[f'{estimand}_LB'], xml_upper=xmlcheck[f'{estimand}_UB'],
                                      source_decision=conflict_pair[f'{prefix}_decision'],
                                      cross_source_status='SOURCE_VERSION_CONFLICT' if estimand == 'difference' else 'UNCHANGED',
                                      uncertainty='RECORDED_CENSORING_ENDPOINTS_NOT_CONFIDENCE_INTERVALS'))
    summary = dict(scope='RETROSPECTIVE_SOURCE_STABILITY_SENSITIVITY_NOT_NEW_EXPOSURE',
                   original_target_keys=19422, raw_key_matches=19422 - len(normalization),
                   explicit_case_only_food_matches=len(normalization), normalization_identity_collisions=0,
                   unmatched_original_keys=0, extra_q1q3_keys_excluded=len(extras), compared_q1_cells=38844,
                   changed_cells=len(conflicts), changed_food_chemical_keys=1,
                   source_specific_counts={LABELS[q]: dict(c) for q, c in source_counts.items()},
                   source_cell_state_counts={LABELS[q]: dict(c) for q, c in source_states.items()},
                   cross_source_counts=dict(cross_counts), source_specific_directions=61, source_stable_directions=60,
                   source_stable_direction_counts=dict(stable_direction_counts),
                   loss_of_source_stable_directions=1, percent_of_source_specific_directions_stable=str(D(60) / 61 * 100),
                   mean_endpoint_pairs_unchanged=mean_equal, mean_endpoint_pairs_held=mean_held,
                   mean_endpoint_pairs_changed=len(pairs) - mean_equal - mean_held,
                   q4_separate_identity=dict(duplicate_key_groups=4, duplicate_rows_preserved=8,
                                            q2_spinosad_keys_absent_in_q2q4=2, q2_unambiguous_repeated_keys=11734,
                                            q2_repeated_cells_unchanged=46936, included_in_q1_denominator=0),
                   publication_authority='UNRESOLVED: both Q1 containers carry identical Q1 republication wording',
                   new_exposure_estimates=0, new_downloads=0, raw_files_modified=0)
    verification = dict(scope='INTERNAL_SEPARATE_READER_COMPUTATIONAL_REPLICATION_NOT_HUMAN_VALIDATION',
                        primary='openpyxl with Decimal(str(value)), unchanged historical classification rules',
                        second='Direct OOXML with separate Decimal calculation from stored numeric strings',
                        source_rows_verified={q: len(x) for q, x in xml_tables.items()},
                        raw_cells_verified=raw_cells_verified, primary_to_xml_numeric_roundoff_cells=raw_roundoffs,
                        max_raw_numeric_roundoff=str(max_raw_roundoff), q1_source_classifications_verified=38844,
                        endpoint_checks=endpoint_checks, endpoint_representation_roundoff_checks=endpoint_roundoffs,
                        max_endpoint_roundoff=str(max_endpoint_roundoff),
                        numeric_tolerance=f'max(absolute {ABS_TOL}, relative {REL_TOL}); identities and classifications exact',
                        historical_q1_records_reconciled=original_reconciled, raw_source_sha_preservation='4/4 PASS',
                        normalization_collision_check='PASS', exact_conflict_swap_and_mean_check='PASS',
                        q4_other_sheet_duplicate_rows_verified=8, overall='PASS')
    old_vs_stable = [dict(category='Recorded directions', q1_only=61, q1_repeated_in_q1q3=61, across_both=60),
                     dict(category='Source-version conflict', q1_only=0, q1_repeated_in_q1q3=0, across_both=1),
                     dict(category='Censoring unresolved', q1_only=19246, q1_repeated_in_q1q3=19246, across_both=19246),
                     dict(category='Method HOLD', q1_only=115, q1_repeated_in_q1q3=115, across_both=115)]
    metadata = dict(protocol_sha256=sha(ROOT / '01_protocol/manuscript_source_stability_v35_20261015.md'),
                    audit_provenance_sha256=sha(baseline), historical_q1_csv_sha256=sha(old_csv),
                    manifest_snapshot_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                    code_sha256=sha(Path(__file__)), sources=sources)
    return dict(pairs=pairs, conflicts=conflicts, normalization=normalization, extras=extras, holds=holds,
                q4_mirrors=mirror, summary=summary, verification=verification, mean_check=mean_check,
                old_vs_stable=old_vs_stable, provenance=metadata, anchors=anchors,
                joint_decisions=joint_rows, jam_endpoints=endpoint_rows)


def narrative(data):
    s = data['summary']
    return f"""# NZ Q1 source-stability sensitivity, v35

## Methods

This retrospective extension retains all 19,422 food–group–chemical-expression–unit keys from the Q1-only container (MPI document 65331). It compares only the two repeated Q1 brand columns in the Q1+Q3 container (70426). It does not use Q3 brand columns as additional Q1 observations. Existing raw files and historical results are unchanged. Four units per brand were composited for analysis; display rows are not independent sample replicates. Source-specific claims concern recorded composite results under censoring, not true concentrations or population brand effects.

Exact raw identities match for {s['raw_key_matches']:,} keys. A single, explicitly enumerated food-label replacement, `sweetcorn, frozen and canned` → `Sweetcorn, frozen and canned`, matches the remaining {s['explicit_case_only_food_matches']} keys. Neither arbitrary case folding nor chemical-name harmonisation is applied. Raw keys and source row/cell locators remain in the per-key file. Both source tables have unique raw and comparison keys; the normalization causes zero identity collisions. The one additional key in 70426 is excluded and recorded separately. No original key is dropped.

For each source, `<LOQ` retains the historical conservative endpoint envelope [0, LOQ]; a reported numeric value is [x, x]. These are censoring endpoints, not distributional imputations. `N/R` (methodological nonreporting) and `N/A` (not tested) remain distinct source states; either prevents a valid numeric comparison. For Brand 1 minus Brand 2, [L1−U2, U1−L2] supports a direction only when its lower endpoint is positive or its upper endpoint is negative. A zero-spanning interval is censoring-unresolved. The source-stable layer requires the same supported direction in both containers. It does not select a preferred source or alter the historical source-specific classification.

The primary reader and Decimal calculations reproduce the historical Q1 CSV exactly for all 19,422 keys. A separate direct OOXML reader independently parses all four workbook main tables and recalculates the two Q1 sets with separate Decimal arithmetic. Numeric endpoints allow the historical floating-representation tolerance of max(1e−12 absolute, 1e−10 relative); keys, row counts, source states, and decisions agree exactly. Tiny openpyxl versus stored XML numeric differences are quantified in `separate_reader_verification.json`. The swap and equal-mean checks also pass exactly with XML Decimal values. Four source hashes match the earlier audit and current acquisition manifest and remain unchanged after reading. This is internal computational verification by the same AI-assisted project, not external scientific or human validation.

## Results

Both Q1 source sets support 61 recorded directions, 19,246 censoring-unresolved contrasts, and 115 method HOLDs, summing to 19,422. Of the 61 supported directions, 60 agree across both available containers; one is source-version unresolved. Thus the full-target source-stability partition is **60 direction-stable, 1 source-version conflict, 19,246 censoring-unresolved, and 115 method HOLD**. The 60/61 fraction is conditional on the source-specific direction set, not an overall success proportion or population estimate.

The only changed repeated Q1 cells are D2644 and E2644 in `Table 1.1 All results` of both workbooks. For Jam / Captan (sum of residues expressed as captan), 65331 reports Brand 1 `<0.01`, Brand 2 `0.041`; 70426 reports Brand 1 `0.041`, Brand 2 `<0.01` mg/kg. The Brand 1 minus Brand 2 interval therefore changes from [−0.041, −0.031] to [0.031, 0.041] mg/kg. This is one record with a brand-value swap and two changed cells. Both containers give the same unweighted two-brand mean endpoints, [0.0205, 0.0255] mg/kg. Across the target, all {s['mean_endpoint_pairs_unchanged']:,} evaluable pairs have identical mean endpoints; {s['mean_endpoint_pairs_held']} remain held. These arithmetic checks do not estimate dietary exposure.

The two Contents!A12 cells contain identical wording: Q1 released 25 September 2024, republished 26 August 2025 to correct errors. The combined container additionally lists Q3 released 26 August 2025. Container number, quarter coverage, and file location do not establish which conflicting assignment is correct. The official authority of the conflicting assignment remains unresolved.

## Separate Q2/Q4 identity HOLDs

This auxiliary ledger does not change the Q1 denominator. The Q2+Q4 main sheet has 12,878 rows and 12,874 raw four-field keys: four Spinetoram keys each appear twice (eight preserved rows; four excess rows). The foods are Nectarines and peaches, Noodle dish, takeaway, Strawberry, and Tomato. The same duplicates appear in `1.19 Others`; that within-file repetition does not adjudicate identity. Two Q2 Spinosad keys (Noodle dish, takeaway; Tomato) are absent from the combined Q2+Q4 table. No missing Spinosad label is inferred from a duplicate Spinetoram label. All records and source locators remain in the HOLD ledger and JSON. The 11,734 nonambiguous repeated Q2 keys have 46,936 unchanged Q2 values; ambiguous and absent identities are excluded from that auxiliary comparison.

## Limitations and permitted use

This is a retrospective sensitivity layer motivated by an already known conflict, not preregistration, unseen validation, or a new independent study. Agreement across the two available containers is bounded evidence of source stability, not verification against an external true value. The containers repeat the same quarter rather than supply independent samples. Case-only food matching is restricted to this exact documented label pair. Censoring envelopes do not include sampling, measurement, laboratory, or population uncertainty. Source-defined chemical expressions are retained without toxicological reconstruction. The separate identity HOLDs require source clarification. No source is declared correct, no raw data are corrected, no frozen figure is overwritten, and no exposure, PAF, DALY, organic-transition effect, or clinical effect is re-estimated.

## Files

- `nz_q1_per_key_source_stability.csv`: complete fixed target, both raw identities, source values, row/cell locators, interval endpoints, source decisions, stability and arithmetic-mean check.
- `nz_conflicting_cells.csv` and `nz_same_mean_arithmetic_check.json`: exact swap locations and bounded arithmetic consequences.
- `nz_old_vs_source_stable_summary.csv`, `nz_source_stability_summary.json`: figure-ready disjoint counts with explicit scope.
- `nz_q1_joint_decision_matrix.csv`: all 16 cells of the 4 × 4 source-decision matrix, including zero counts; total 19,422 keys. Exact recorded ties are absent in both sources.
- `nz_jam_captan_plot_endpoints.csv`: four source/estimand rows for the brand difference and two-brand mean; endpoints are censoring bounds, not confidence intervals.
- `nz_food_label_normalization.csv`, `nz_q1q3_extra_keys_excluded.csv`: full identity decisions.
- `nz_q4_identity_hold_ledger.csv`, `nz_q4_duplicate_mirror_records.json`: preserved, separate regional identity issues.
- `source_instruction_anchors.csv`, `source_provenance.json`, `separate_reader_verification.json`, `run_receipt.json`: source semantics, hashes, checks, and output integrity.

Reproduction: run `python3 05_code/utilities/check_paths.py`, then `python3 05_code/analysis/nz_source_stability_v35.py --check-only` to inspect without writing, or `--verify-only` to compare fresh calculations with existing outputs. Default execution refuses to overwrite an existing output directory. Required library: openpyxl. Paths load from `00_admin/paths.yaml`; raw data must remain on the configured external drive.
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--check-only', action='store_true')
    group.add_argument('--verify-only', action='store_true')
    args = p.parse_args()
    check = subprocess.run([sys.executable, str(ROOT / '05_code/utilities/check_paths.py')],
                           cwd=ROOT, capture_output=True, text=True)
    if check.returncode:
        raise RuntimeError(check.stdout + check.stderr)
    cfg = config()
    out = Path(cfg['outputs_root']) / 'manuscript_source_stability_v35/nz'
    if not args.check_only and not args.verify_only:
        assert not out.exists(), 'Output exists; use --verify-only or --check-only. Never overwrite.'
    data = build(cfg)
    csvs = {'nz_q1_per_key_source_stability.csv': 'pairs', 'nz_conflicting_cells.csv': 'conflicts',
            'nz_food_label_normalization.csv': 'normalization', 'nz_q1q3_extra_keys_excluded.csv': 'extras',
            'nz_q4_identity_hold_ledger.csv': 'holds', 'nz_old_vs_source_stable_summary.csv': 'old_vs_stable',
            'source_instruction_anchors.csv': 'anchors', 'nz_q1_joint_decision_matrix.csv': 'joint_decisions',
            'nz_jam_captan_plot_endpoints.csv': 'jam_endpoints'}
    jsons = {'nz_source_stability_summary.json': 'summary', 'separate_reader_verification.json': 'verification',
             'nz_same_mean_arithmetic_check.json': 'mean_check', 'source_provenance.json': 'provenance',
             'nz_q4_duplicate_mirror_records.json': 'q4_mirrors'}
    payloads = {name: csv_string(data[key]) for name, key in csvs.items()}
    payloads.update({name: json.dumps(data[key], ensure_ascii=False, indent=2) + '\n' for name, key in jsons.items()})
    payloads['methods_results_limitations.md'] = narrative(data)
    if args.verify_only:
        assert out.is_dir()
        for name, content in payloads.items():
            if name == 'source_provenance.json':
                # The current acquisition ledger may grow; fixed sources are still verified.
                saved = json.loads((out / name).read_text())
                current = json.loads(content)
                for key in current:
                    if key not in ('manifest_snapshot_sha256', 'code_sha256'):
                        assert saved[key] == current[key], (name, key)
            else:
                assert (out / name).read_bytes() == content.encode('utf-8'), name
        receipt = json.loads((out / 'run_receipt.json').read_text())
        assert all(sha(out / f['file']) == f['sha256'] for f in receipt['outputs'])
        print(json.dumps({'verification': 'PASS', 'files': len(payloads), 'summary': data['summary']}, indent=2))
        return
    if not args.check_only:
        out.mkdir(parents=True)
        for name, content in payloads.items():
            (out / name).write_bytes(content.encode('utf-8'))
        receipt = dict(finished_utc=datetime.now(timezone.utc).isoformat(), status='PASS',
                       path_check='PASS', analysis_scope=data['summary']['scope'],
                       code_sha256=sha(Path(__file__)), raw_sources_preserved=4,
                       historical_q1_rows_reproduced=19422,
                       outputs=[dict(file=name, bytes=(out / name).stat().st_size, sha256=sha(out / name))
                                for name in sorted(payloads)])
        (out / 'run_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'written': not args.check_only,
                      'summary': data['summary'], 'verification': data['verification'], 'conflict': data['mean_check']}, indent=2))


if __name__ == '__main__':
    main()
