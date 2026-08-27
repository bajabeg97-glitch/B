import csv,json

from tools.create_hardware_campaign import generate
from tools.evaluate_hardware_campaign import load


def test_campaign_generator_contains_all_required_rows(tmp_path):
    output=generate(tmp_path/'campaign');manifest=json.loads((output/'CAMPAIGN.json').read_text(encoding='utf-8'));rows=list(csv.DictReader((output/'RESULTS.csv').open(encoding='utf-8-sig')))
    assert manifest['schema']=='PA800_HARDWARE_CAMPAIGN_V1';assert len(rows)==383
    assert manifest['protocol']['strict_case_ids'] and len({row['case_id'] for row in rows})==383
    assert all(row['blind_order'] in ('A_REFERENCE_B_OPTIMIZED','A_OPTIMIZED_B_REFERENCE') for row in rows)
    assert sum(row['kind']=='voice' for row in rows)==210 and sum(row['kind']=='fx' for row in rows)==150 and sum(row['kind']=='dnc' for row in rows)==23
    loaded=load(output/'CAMPAIGN.json',output/'RESULTS.csv');assert len(loaded['records'])==383