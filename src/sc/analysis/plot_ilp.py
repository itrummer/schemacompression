'''
Created on Oct 3, 2023

@author: immanueltrummer
'''
import argparse
import json
import os.path
import pathlib
import pandas


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('indir', type=str, help='Path to input directory')
    args = parser.parse_args()
    
    results = []
    for file_name in [
        'result5min.json', 'result20min.json', 'result60min.json']:
        file_path = pathlib.Path(args.indir).joinpath(file_name)
        with open(file_path) as file:
            raw_result = json.load(file)
            result = {}
            for cur_raw in raw_result:
                file_name = os.path.basename(cur_raw['file_name'])
                result[file_name] = cur_raw
            results.append(result)
    
    file_order = [
        'MulheresMil_1.table.sql', 
        'IUBLibrary_1.table.sql', 
        'HashTags_1.table.sql', 
        'Corporations_1.table.sql', 
        'Redfin4_1.table.sql', 
        'IGlocations1_1.table.sql', 
        'Food_1.table.sql', 
        'Eixo_1.table.sql', 
        'Hatred_1.table.sql', 
        'Telco_1.table.sql', 
        'Arade_1.table.sql', 
        'MedPayment1_1.table.sql', 
        'Physicians_1.table.sql', 
        'Euro2016_1.table.sql', 
        'MedPayment2_1.table.sql', 
        'Bimbo_1.table.sql', 
        'Uberlandia_1.table.sql', 
        'CityMaxCapita_1.table.sql', 
        'Medicare3_1.table.sql', 
        'PanCreactomy1_1.table.sql']
    
    rows = []
    for file_name in file_order:
        row = [file_name]
        for result in results:
            row.append(result[file_name]['gurobi']['size'])
            row.append(result[file_name]['gurobi']['mip_gap'])
            row.append(result[file_name]['gurobi']['total_s'])
            
        row.append(result[file_name]['gurobi']['nr_variables'])
        row.append(result[file_name]['gurobi']['nr_constraints'])
        row.append(result[file_name]['gurobi']['max_length'])
        rows.append(row)
    
    df = pandas.DataFrame(rows)
    df.columns = [
        'filename', '5msize', '5mgap', '5ms', 
        '20msize', '20mgap', '20ms', 
        '60msize', '60mgap', '60ms', 
        'nrvars', 'nrconstraints', 'maxlength']
    df.to_csv('ilpplot.csv')