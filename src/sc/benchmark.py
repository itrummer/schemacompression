'''
Created on Sep 27, 2023

@author: immanueltrummer
'''
import argparse
import pathlib
import sc.parser
import sc.compress.gurobi
import sc.llm
import time


def benchmark(ddl, solver, model):
    """ Benchmarks given prompt generation method.
    
    Args:
        ddl: schema description of database.
        solver: solves prompt generation problem.
        model: name of model that is prompted.
    """
    start_s = time.time()
    result = solver(ddl)
    total_s = time.time() - start_s
    result['total_s'] = total_s
    
    
    
def read_schemata(input_path):
    """ Returns list of schemata read from disk.
    
    Args:
        input_path: path to input directory.
    
    Returns:
        list of schema descriptions in SQL.
    """
    ddls = []
    input_dir = pathlib.Path(input_path)
    for file_name in input_dir.iterdir():
        if str(file_name).endswith('.sql'):
            file_path = input_dir.joinpath(file_name)
            print(f'Reading file {file_path} ...')
            with open(file_path) as file:
                ddl = file.read()
                ddls.append(ddl)
    
    return ddls


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('inputdir', type=str, help='Path of input directory')
    parser.add_argument('timeout_s', type=int, help='Timeout seconds per test')
    parser.add_argument('outpath', type=str, help='Path to output file')
    args = parser.parse_args()
    
    ddls = read_schemata(args.inputdir)
    nr_ddls = len(ddls)
    print(f'Read {nr_ddls} schemata.')
    
    for ddl in ddls:
        result = {}
        parser = sc.parser.SchemaParser()
        schema = parser.parse(ddl)
        pretty_sql = parser.format(ddl)
        print(pretty_sql)
        