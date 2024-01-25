'''
Created on Jan 15, 2024

@author: immanueltrummer
'''
import argparse
import json
import openai
import pathlib
import sqlite3
import time

from pathlib import Path


def text_to_sql(schema, question):
    """ Translate question to SQL query.
    
    Args:
        schema: text description of schema.
        question: translate this question.
    
    Returns:
        an SQL query translating the question.
    """
    prompt = f'Schema:{schema}\nQuestion:{question}\nSQL:'
    for nr_retries in range(1, 4):
        try:
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[
                    {'role':'user', 'content':prompt}
                    ]
                )
            return response['choices'][0]['message']['content']
        except:
            time.sleep(nr_retries * 2)
    raise Exception('Cannot translate query!')


def result_is_empty(db_path, sql):
    """ Ensures that query result is empty.
    
    Args:
        db_path: path to SQLite database.
        sql: verify result of this SQL query.
    
    Returns:
        True iff the query executes and its result is empty.
    """
    print(f'SQL: {sql}')
    db_path = str(db_path)
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            table_rows = cursor.fetchall()
            nr_rows = len(table_rows)
            return True if nr_rows == 0 else False
        except Exception as e:
            print(e)
            return False

    
def validate(db_path, gold_sql, sql):
    """ Ensure that two queries yield the same result.
    
    Args:
        db_path: path to SQLite database.
        gold_sql: ground truth SQL query.
        sql: possibly equivalent SQL query.
    
    Returns:
        True iff both input queries yield the same result.
    """
    sql_1 = f'{gold_sql} except {sql}'
    sql_2 = f'{sql} except {gold_sql}'
    count_sql = f'select count(*) from ({sql})'
    count_gold = f'select count(*) from ({gold_sql})'
    sql_3 = f'{count_sql} except {count_gold}'
    
    for sql in [sql_1, sql_2, sql_3]:
        if not result_is_empty(db_path, sql):
            return False
    
    return True


def nlqi_success(schema, question, gold_sql, db_path):
    """ Check whether text-to-SQL translation succeeds.
    
    Args:
        schema: text description of schema.
        question: a natural language question.
        gold_sql: ground truth SQL translation.
        db_path: path to SQLite database.
    
    Returns:
        True iff translated query seems correct.
    """
    sql = text_to_sql(schema, question)
    success = validate(db_path, gold_sql, sql)
    print(f'Success: {success}')
    return success
    
    
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('schemas', type=str, help='Path to schema file')
    parser.add_argument('data_dir', type=str, help='Path to SPIDER data')
    parser.add_argument('queries', type=str, help='Path to query file')
    parser.add_argument('limit', type=int, help='Maximal number of queries')
    parser.add_argument('method', type=str, help='Compression method to test')
    parser.add_argument('ai_key', type=str, help='OpenAI access key')
    parser.add_argument('outpath', type=str, help='Path to result file')
    args = parser.parse_args()
    
    with open(args.schemas) as file:
        schemas = json.load(file)
    with open(args.queries) as file:
        queries = json.load(file)
    openai.api_key = args.ai_key

    db2original = {}
    db2compressed = {}
    for schema in schemas:
        original = schema['pretty']['solution']
        compressed = schema[args.method]['solution']
        file_path = schema['file_name']
        file_name = pathlib.Path(file_path).name
        db_name = file_name[:-4]
        db2original[db_name] = original
        db2compressed[db_name] = compressed
    
    
    print(db2original.keys())
    
    queries = [q for q in queries if q['db_id'] in db2original]
    queries = queries[:args.limit]
    
    results = []
    for query_idx, query in enumerate(queries, 1):
        print(f'Processing query nr. {query_idx} ...')
        db_name = query['db_id']
        print(f'DB name: {db_name}')
        original = db2original[db_name]
        compressed = db2compressed[db_name]
        db_path = Path(args.data_dir) / db_name / f'{db_name}.sqlite'
        question = query['question']
        gold = query['query']
        
        db_results = {'db_name':db_name, 'db_query':query}
        tests = [('original', original), ('compressed', compressed)]
        for test_name, schema in tests:
            success = nlqi_success(original, question, gold, db_path)
            db_results[test_name] = success
        
        results.append(db_results)
    
    with open(args.outpath, 'w') as file:
        json.dump(results, file)