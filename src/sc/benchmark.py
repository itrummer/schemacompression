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


def benchmark(ddl, solver, **kwargs):
    """ Benchmarks given prompt generation method.
    
    Args:
        ddl: schema description of database.
        solver: solves prompt generation problem.
        kwargs: keyword arguments for solver.
    """
    start_s = time.time()
    try:
        result = solver(ddl, **kwargs)
        error = False
    except:
        error = True
    
    total_s = time.time() - start_s
    result['total_s'] = total_s
    result['error'] = error
    
    if not error:
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
    schema = parser.parse(ddl)
    schema.merge_columns()
    parts = sc.compress.greedy.greedy_parts(schema)
    solution = ''.join(parts)
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
    schema = parser.parse(ddl)
    ilpCompression = sc.compress.gurobi.IlpCompression(
        schema, max_depth=3, context_k=10, **kwargs)
    return ilpCompression.compress()


def solver_pretty(ddl, **kwargs):
    """ Pretty formating of DDL SQL commands.
    
    Args:
        ddl: the (unformatted) DDL schema description.
    
    Returns:
        result dictionary containing solution.
    """
    parser = sc.parser.SchemaParser()
    solution = parser.format(ddl)
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
    schema = parser.parse(ddl)
    solution = schema.text()
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
        '--start', type=bool, default=True, 
        help='Greedy solution as start')
    parser.add_argument(
        '--hints', type=bool, default=True, 
        help='Hints for variable values')
    parser.add_argument(
        '--merge', type=bool, default=True, 
        help='Merge columns by annotations')
    args = parser.parse_args()
    print(args)
    
    model = 'text-davinci-003'
    
    file_names, ddls = read_schemata(args.inputdir)
    nr_ddls = len(ddls)
    print(f'Read {nr_ddls} schemata.')
    
    results = []
    for file_name, ddl in zip(file_names, ddls):
        greedy_result = benchmark(ddl, solver_greedy)
        gurobi_args = {
            'llm_name':model, 'timeout_s':args.timeout_s, 
            'start':args.start, 'hints':args.hints, 
            'merge':args.merge}
        gurobi_result = benchmark(ddl, solver_gurobi, **gurobi_args)
        pretty_result = benchmark(ddl, solver_pretty)
        prompt_result = benchmark(ddl, solver_promptbase)
        result = {
            'file_name':file_name, 'greedy':greedy_result, 
            'gurobi':gurobi_result, 'pretty':pretty_result, 
            'prompt':prompt_result}
        results.append(result)
        
        with open(args.outpath, 'w') as file:
            json.dump(results, file)