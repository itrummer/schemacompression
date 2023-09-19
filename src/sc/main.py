'''
Created on Sep 7, 2023

@author: immanueltrummer
'''
import argparse
import json
import openai
import sc.compress.types
import sc.compress.default_types
import sc.llm
import sc.schema


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str, help='Path to schema file')
    parser.add_argument('aikey', type=str, help='API key of OpenAI')
    args = parser.parse_args()
    
    openai.api_key = args.aikey
    model = 'gpt-3.5-turbo'
    with open(args.file) as file:
        spider = json.load(file)
    
    raw_total = 0
    compressed_total = 0
    for db_name, spider_db in spider.items():
        schema = sc.schema.parse_spider(spider_db)

        raw_description = schema.text()
        raw_size = sc.llm.nr_tokens(model, raw_description)
        raw_total += raw_size
        
        #compressed_1 = sc.compress.types.compress_schema(schema)
        compressed_2 = sc.compress.default_types.compress_schema(schema)
        #compressed_1_size = sc.llm.nr_tokens(model, compressed_1)
        compressed_2_size = sc.llm.nr_tokens(model, compressed_2)
        
        print(f'Original\n{raw_description}')
        print(f'Compressed\n{compressed_2}')
        
        #compressed_size = min(compressed_1_size, compressed_2_size)
        compressed_size = compressed_2_size
        compressed_total += compressed_size
        
        # if raw_size < compressed_size:
            # print(raw_description)
            # print(compressed_description)

    print(f'Total size: {raw_total}')
    print(f'Compressed size: {compressed_total}')
    
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