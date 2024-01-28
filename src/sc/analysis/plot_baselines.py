'''
Created on Sep 28, 2023

@author: immanueltrummer
'''
import argparse
import json
import pandas as pd


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('inpath', type=str, help='Path to input file')
    parser.add_argument('outpath', type=str, help='Path to output directory')
    args = parser.parse_args()
    
    with open(args.inpath) as file:
        raw_results = json.load(file)
    
    for raw_result in raw_results:
        if not raw_result['gurobi']['solved']:
            raw_result['gurobi']['size'] = raw_result['greedy']['size']
    
    results = []
    for raw_result in raw_results:
        cur_result = []
        cur_result.append(raw_result['file_name'])
        cur_result.append(raw_result['pretty']['size'])
        cur_result.append(raw_result['prompt']['size'])
        cur_result.append(raw_result['greedy']['size'])
        cur_result.append(raw_result['gurobi']['size'])
        
        sizes = cur_result[1:]
        min_size = min(sizes)
        scaled_sizes = [s / min_size for s in sizes]
        cur_result += scaled_sizes
        
        cur_result.append(raw_result['pretty']['total_s'])
        cur_result.append(raw_result['prompt']['total_s'])
        cur_result.append(raw_result['greedy']['total_s'])
        cur_result.append(raw_result['gurobi']['total_s'])
        
        # cur_result.append(raw_result['gurobi']['nr_variables'])
        # cur_result.append(raw_result['gurobi']['nr_constraints'])
        # cur_result.append(raw_result['gurobi']['mip_gap'])
        results.append(cur_result)
    
    result_df = pd.DataFrame(results)
    result_df.columns = [
        'filename', 'sqlsize', 'pbsize', 'greedysize', 'gurobisize',
        'sqlrelsize', 'pbrelsize', 'greedyrelsize', 'gurobirelsize',
        'sqltime', 'pbtime', 'greedytime', 'gurobitime',
        # 'nr_variables', 'nr_constraints', 'mip_gap'
        ]
    result_df.to_csv(args.outpath)