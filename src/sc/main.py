'''
Created on Sep 7, 2023

@author: immanueltrummer
'''
import argparse
import json
import logging
import openai
import sc.parser
import sc.compress.gurobi
import sc.compress.types
import sc.compress.default_types
import sc.llm
import sc.schema
import sc.spider


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str, help='Path to DDL file')
    args = parser.parse_args()
    
    #logging.basicConfig(level=logging.INFO)
    model = 'text-davinci-003'
    with open(args.file) as file:
        ddl = file.read()

    
    schema_parser = sc.parser.SchemaParser()
    schema = schema_parser.parse(ddl)
    prefixes = schema.prefixes(model)
    print(f'Sorted prefixes: {prefixes}')
    placeholders = ['*', '&', '$']
    nr_placeholders = len(placeholders)
    nr_prefixes = len(prefixes)
    nr_shortcuts = min(nr_placeholders, nr_prefixes)
    prefixes = prefixes[:nr_shortcuts]
    short2text = {
        placeholders[i]:prefixes[i] \
        for i in range(nr_shortcuts)}

    raw_description = schema.text()
    raw_size = sc.llm.nr_tokens(model, raw_description)
    
    #compressed_1 = sc.compress.types.compress_schema(schema)
    #compressed_2 = sc.compress.default_types.compress_schema(schema)
    #compressed_1_size = sc.llm.nr_tokens(model, compressed_1)
    #compressed_2_size = sc.llm.nr_tokens(model, compressed_2)
    
    # {'*':'buildUpPlay', '&':'player_'}
    
    compressed_parts = []
    splits = schema.split()
    for split in splits:
        split.merge_columns()
        ilpCompression = sc.compress.gurobi.IlpCompression(
            split, llm_name=model, max_depth=2, 
            context_k=10, short2text=short2text)
        compressed = ilpCompression.compress()
        print(compressed)
        compressed_parts.append(compressed)
    
    print(f'Original\n{raw_description}')
    all_compressed = '\n'.join(compressed_parts)
    print(f'Compressed\n{all_compressed}')
    
    #compressed_size = min(compressed_1_size, compressed_2_size)
    # compressed_size = compressed_2_size
    # compressed_total += compressed_size
        
        # if raw_size < compressed_size:
            # print(raw_description)
            # print(compressed_description)

    raw_size = sc.llm.nr_tokens(model, raw_description)
    compressed_size = sc.llm.nr_tokens(model, all_compressed) 
    print(f'Original size: \t{raw_size}')
    print(f'Compressed size: \t{compressed_size}')
    
    # spider_db = spider[args.schema]
    # schema = sc.schema.parse_spider(spider_db)
    # original = schema.text()
    # compressed = sc.compress.types.compress_schema(schema)
    # original_length = sc.llm.nr_tokens(model, original)
    # compressed_length = sc.llm.nr_tokens(model, compressed)
    # print(llm(compressed + '\nWhat is the type of stadium.ID?'))
    #
    # print(original)
    # print(compressed)
    #
    # print(f'Original length: \t{original_length}')
    # print(f'Compressed length: \t{compressed_length}')
    #
    # tosql1 = sc.translate.Translator(llm, original)
    # tosql2 = sc.translate.Translator(llm, compressed)
    # question = "Show name, country, age for all singers ordered by age from the oldest to the youngest."
    # query_1 = tosql1.translate(question)
    # query_2 = tosql2.translate(question)
    # print(query_1)
    # print(query_2)