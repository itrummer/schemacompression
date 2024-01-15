'''
Created on Jan 15, 2024

@author: immanueltrummer
'''
import argparse
import json
import openai
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
    db_path = str(db_path)
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            table_rows = cursor.fetchall()
            nr_rows = len(table_rows)
            return True if nr_rows == 0 else False
        except:
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
    sql_1 = f'select * from {gold_sql} except {sql}'
    sql_2 = f'select * from {sql} except {gold_sql}'
    count_sql = f'(select count(*) from {sql})'
    count_gold = f'(select count(*) from {gold_sql})'
    sql_3 = f'select * from {count_sql} except {count_gold}'
    
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
    return success
    
    
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('schemas', type=str, help='Path to schema file')
    parser.add_argument('data_dir', type=str, help='Path to SPIDER data')
    parser.add_argument('queries', type=str, help='Path to query file')
    parser.add_argument('ai_key', type=str, help='OpenAI access key')
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
        compressed = schema['compressed']['solution']
        db_name = original['pretty']['file_name'][:-4]
        db2original[db_name] = original
        db2compressed[db_name] = compressed
    
    results = []
    for db_name, db_queries in queries.items():
        for db_query in db_queries:
            original = db2original[db_name]
            compressed = db2compressed[db_name]
            db_path = Path(args.data_dir) / db_name / f'{db_name}.sqlite'
            question = db_query['question']
            gold = db_query['query']
            
            db_results = {'db_name':db_name, 'db_query':db_query}
            tests = [('original', original), ('compressed', compressed)]
            for test_name, schema in tests:
                success = nlqi_success(original, question, gold, db_path)
                db_results[test_name] = success
            
            results.append(db_results)