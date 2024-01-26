'''
Created on Sep 27, 2023

@author: immanueltrummer
'''
import argparse
import json
import pathlib
import sc.parser
import sc.compress.greedy
import sc.compress.gurobi
import sc.llm
import time


def decompose_ddl(ddl):
    """ Decomposes DDL script into DDL statements.
    
    Args:
        ddl: DDL script.
    
    Returns:
        list of DDL statements.
    """
    ddl = ddl.strip()
    parts = ddl.split(';')
    parts = [p for p in parts if p]
    return parts
    
    
def benchmark(ddl, solver, **kwargs):
    """ Benchmarks given prompt generation method.
    
    Args:
        ddl: schema description of database.
        solver: solves prompt generation problem.
        kwargs: keyword arguments for solver.
    """
    start_s = time.time()
    result = solver(ddl, **kwargs)
    total_s = time.time() - start_s
    result['total_s'] = total_s
    
    solution = result['solution']
    size = sc.llm.nr_tokens(model, solution)
    result['size'] = size    
    
    return result


def solver_greedy(ddl, **kwargs):
    """ Compress input schema greedily.
    
    Args:
        ddl: schema description in SQL.
    
    Returns:
        dictionary mapping to solution.
    """
    parser = sc.parser.SchemaParser()
    original_ddls = decompose_ddl(ddl)
    compressed_ddls = []
    for original_ddl in original_ddls:
        schema = parser.parse(original_ddl)
        schema.merge_columns()
        parts = sc.compress.greedy.greedy_parts(schema)
        compressed_ddl = ''.join(parts)
        compressed_ddls += [compressed_ddl]
    
    solution = '\n'.join(compressed_ddls)
    return {'solution':solution}


def solver_gurobi(ddl, **kwargs):
    """ Compress schema via integer linear programming.
    
    Args:
        ddl: database schema description in SQL.
        kwargs: keyword arguments for solver.
    
    Returns:
        result dictionary containing solution and statistics.
    """
    parser = sc.parser.SchemaParser()
    original_ddls = decompose_ddl(ddl)
    compression_results = []
    for original_ddl in original_ddls:
        schema = parser.parse(original_ddl)
        ilpCompression = sc.compress.gurobi.IlpCompression(
            schema, max_depth=3, context_k=10, **kwargs)
        compression_result = ilpCompression.compress()
        compression_results += [compression_result]
    
    solution = '\n'.join([c['solution'] for c in compression_results])
    return {'solution':solution, 'results_by_table':compression_results}

def solver_pretty(ddl, **kwargs):
    """ Pretty formating of DDL SQL commands.
    
    Args:
        ddl: the (unformatted) DDL schema description.
    
    Returns:
        result dictionary containing solution.
    """
    parser = sc.parser.SchemaParser()
    original_ddls = decompose_ddl(ddl)
    compressed_ddls = []
    for original_ddl in original_ddls:
        print(original_ddl)
        compressed_ddl = parser.format(original_ddl)
        compressed_ddls += [compressed_ddl]
    
    solution = '\n'.join(compressed_ddls)
    return {'solution':solution}


def solver_promptbase(ddl, **kwargs):
    """ Use prompt proposed at promptbase.com.
    
    This corresponds to the schema description used
    in the following prompt template:
    https://promptbase.com/prompt/generate-sql-based-on-your-schema
    
    Args:
        ddl: schema description as SQL DDL commands.
    
    Returns:
        dictionary mapping containing solution attribute.
    """
    parser = sc.parser.SchemaParser()
    original_ddls = decompose_ddl(ddl)
    compressed_ddls = []
    for original_ddl in original_ddls:
        schema = parser.parse(original_ddl)
        compressed_ddl = schema.text()
        compressed_ddls += [compressed_ddl]
    
    solution = '\n'.join(compressed_ddls)
    return {'solution':solution}


def read_schemata(input_path):
    """ Returns list of schemata read from disk.
    
    Args:
        input_path: path to input directory.
    
    Returns:
        tuple: list of file names and list of schema descriptions.
    """
    file_names = []
    ddls = []
    input_dir = pathlib.Path(input_path)
    for file_name in input_dir.iterdir():
        if str(file_name).endswith('.sql'):
            file_path = input_dir.joinpath(file_name)
            print(f'Reading file {file_path} ...')
            file_names.append(str(file_name))
            with open(file_path) as file:
                ddl = file.read()
                ddls.append(ddl)
    
    return file_names, ddls


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('inputdir', type=str, help='Path of input directory')
    parser.add_argument('timeout_s', type=int, help='Timeout seconds per test')
    parser.add_argument('outpath', type=str, help='Path to output file')
    parser.add_argument(
        '--nostart', action='store_true', help='Greedy solution as start')
    parser.add_argument(
        '--nohints', action='store_true', help='Hints for variable values')
    parser.add_argument(
        '--nomerge', action='store_true', help='Merge columns by annotations')
    parser.add_argument(
        '--noilp', action='store_true', help='Do not execute ILP approach')
    args = parser.parse_args()
    print(args)
    
    model = 'text-davinci-003'
    
    file_names, ddls = read_schemata(args.inputdir)
    nr_ddls = len(ddls)
    print(f'Read {nr_ddls} schemata.')
    
    results = []
    for file_name, ddl in zip(file_names, ddls):
        pretty_result = benchmark(ddl, solver_pretty)
        greedy_result = benchmark(ddl, solver_greedy)
        prompt_result = benchmark(ddl, solver_promptbase)
        result = {
            'file_name':file_name, 'greedy':greedy_result, 
            'pretty':pretty_result, 'prompt':prompt_result}

        if not args.noilp:
            gurobi_args = {
                'llm_name':model, 'timeout_s':args.timeout_s, 
                'start':not args.nostart, 'hints':not args.nohints, 
                'merge':not args.nomerge}
            gurobi_result = benchmark(ddl, solver_gurobi, **gurobi_args)
            result['gurobi'] = gurobi_result
        
        results.append(result)
        
        with open(args.outpath, 'w') as file:
            json.dump(results, file)