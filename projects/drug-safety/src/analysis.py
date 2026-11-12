"""Freeze aggregate openFDA query totals and calculate reporting odds."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = 'https://api.fda.gov/drug/event.json'
DRUG = 'patient.drug.openfda.generic_name.exact:"IBUPROFEN"'
TERMS = ('NAUSEA', 'HEADACHE')
YEARS = (2023, 2024)


def query_url(*clauses):
    return f'{BASE}?{urlencode({"search": " AND ".join(clauses), "limit": 1})}'


def fetch_count(url):
    try:
        with urlopen(url, timeout=30) as response:
            data = json.load(response)
    except HTTPError as exc:
        body = json.load(exc)
        if exc.code == 404 and body.get('error', {}).get('code') == 'NOT_FOUND':
            return 0, None
        raise
    return int(data['meta']['results']['total']), data['meta'].get('last_updated')


def refresh():
    queries = {}
    for year in YEARS:
        window = f'receivedate:[{year}0101 TO {year}1231]'
        queries[(year, 'total')] = query_url(window)
        queries[(year, 'drug')] = query_url(window, DRUG)
        for term in TERMS:
            event = f'patient.reaction.reactionmeddrapt.exact:"{term}"'
            queries[(year, f'{term}_all')] = query_url(window, event)
            queries[(year, f'{term}_drug')] = query_url(window, event, DRUG)
    with ThreadPoolExecutor(max_workers=4) as executor:
        result = list(executor.map(fetch_count, queries.values()))
    dates = {updated for _, updated in result if updated}
    if len(dates) != 1:
        raise RuntimeError('Source update stamp is missing or differs across requests')
    return {
        'retrieved_utc': datetime.now(timezone.utc).date().isoformat(),
        'source_last_updated': dates.pop(),
        'counts': [
            {'year': key[0], 'key': key[1], 'count': count, 'url': url}
            for (key, url), (count, _) in zip(queries.items(), result, strict=True)
        ],
    }


def reporting_odds(total, drug, event, both):
    values = (total, drug, event, both)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError('Expected non-negative integer counts')
    a, b, c, d = both, drug - both, event - both, total - drug - event + both
    if min(a, b, c, d) < 0:
        raise ValueError('Inconsistent marginal or intersection counts')
    result = {'cells': [a, b, c, d], 'ror': None, 'interval': None}
    if min(a, b, c, d) > 0:
        ratio = (a * d) / (b * c)
        margin = 1.96 * math.sqrt(sum(1 / count for count in (a, b, c, d)))
        result.update(ror=ratio, interval=[ratio * math.exp(-margin), ratio * math.exp(margin)])
    return result


def analyze(snapshot):
    counts = {(row['year'], row['key']): row['count'] for row in snapshot['counts']}
    if len(counts) != len(snapshot['counts']):
        raise ValueError('Duplicate query in snapshot')
    return {
        'retrieved_utc': snapshot['retrieved_utc'],
        'source_last_updated': snapshot['source_last_updated'],
        'results': [
            {'year': year, 'term': term, 'total': counts[year, 'total'],
             **reporting_odds(counts[year, 'total'], counts[year, 'drug'],
                              counts[year, f'{term}_all'], counts[year, f'{term}_drug'])}
            for year in YEARS for term in TERMS
        ],
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Replace the fixed snapshot using the live API')
    parser.add_argument('--output', type=Path, default=root / 'outputs' / 'drug_summary.json')
    args = parser.parse_args()
    snapshot_path = root / 'data' / 'openfda_counts.json'
    snapshot = refresh() if args.refresh else json.loads(snapshot_path.read_text(encoding='utf-8'))
    output = analyze(snapshot)
    if args.refresh:
        write_json(snapshot_path, snapshot)
    write_json(args.output, output)
