'''
Created on Oct 6, 2023

@author: immanueltrummer
'''
import argparse
import json
import pandas
import pathlib


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('indir', type=str, help='Input directory')
    args = parser.parse_args()
    
    raw_results = []
    for file_name in [
        'ablationNoStart.json', 'ablationNoStartNoHints.json', 
        'ablationNoStartNoHintsNoMerge.json']:
        full_path = pathlib.Path(args.indir).joinpath(file_name)
        with open(full_path) as file:
            raw_result = json.load(file)
            raw_results.append(raw_result)
    
    columns = []
    for raw_result in raw_results:
        column = [r['file_name'] for r in raw_result]
        columns.append(column)

    for field_name in ['solved', 'size', 'total_s', 'mip_gap']:
        for raw_result in raw_results:
            column = [r['gurobi'][field_name] for r in raw_result]
            columns.append(column)
    
    column_headers = []
    scenarios = ['NoStart', 'NoStartNoHints', 'Nothing']
    for field_name in [
        'file_name', 'solved', 'size', 'total_s', 'mip_gap']:
        for scenario in scenarios:
            column_header = f'{field_name}_{scenario}'
            column_headers.append(column_header)
    
    rows = [[c[i] for c in columns] for i in range(len(columns[0]))]
    df = pandas.DataFrame(rows)
    df.columns = column_headers
    df.to_csv('ablation.csv')