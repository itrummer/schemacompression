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


def benchmark(ddl, solver, model, timeout_s):
    """ Benchmarks given prompt generation method.
    
    Args:
        ddl: schema description of database.
        solver: solves prompt generation problem.
        model: name of model that is prompted.
        timeout_s: timeout in seconds.
    """
    start_s = time.time()
    result = solver(ddl, model, timeout_s)
    total_s = time.time() - start_s
    result['total_s'] = total_s
    solution = result['solution']
    size = sc.llm.nr_tokens(model, solution)
    result['size'] = size
    return result


def solver_greedy(ddl, _, _):
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


def solver_gurobi(ddl, model, timeout_s):
    """ Compress schema via integer linear programming.
    
    Args:
        ddl: database schema description in SQL.
        model: name of model to optimize for.
        timeout_s: timeout measured in seconds.
    
    Returns:
        result dictionary containing solution and statistics.
    """
    parser = sc.parser.SchemaParser()
    schema = parser.parse(ddl)
    ilpCompression = sc.compress.gurobi.IlpCompression(
        schema, llm_name=model, max_depth=3, 
        context_k=10, timeout_s=timeout_s)
    return ilpCompression.compress()


def solver_pretty(ddl, _, _):
    """ Pretty formating of DDL SQL commands.
    
    Args:
        ddl: the (unformatted) DDL schema description.
    
    Returns:
        result dictionary containing solution.
    """
    parser = sc.parser.SchemaParser()
    solution = parser.format(ddl)
    return {'solution':solution}


def solver_promptbase(ddl, _, _):
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
    
    model = 'text-davinci-003'
    
    ddls = read_schemata(args.inputdir)
    nr_ddls = len(ddls)
    print(f'Read {nr_ddls} schemata.')
    
    results = []
    for ddl in ddls:
        greedy_result = benchmark(ddl, solver_greedy, model, args.timeout_s)
        gurobi_result = benchmark(ddl, solver_gurobi, model, args.timeout_s)
        pretty_result = benchmark(ddl, solver_pretty, model, args.timeout_s)
        prompt_result = benchmark(ddl, solver_promptbase, model, args.timeout_s)
        result = {
            'greedy':greedy_result, 'gurobi':gurobi_result, 
            'pretty':pretty_result, 'prompt':prompt_result}
        results.append(result)
        
        with open(args.outpath, 'w') as file:
            json.dump(results, file)