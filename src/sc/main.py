'''
Created on Sep 7, 2023

@author: immanueltrummer
'''
import argparse
import json
import openai
import sc.compress
import sc.llm
import sc.schema
import sc.translate


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str, help='Path to schema file')
    parser.add_argument('schema', type=str, help='Name of target schema')
    parser.add_argument('question', type=str, help='Question about data')
    parser.add_argument('aikey', type=str, help='API key of OpenAI')
    args = parser.parse_args()
    
    openai.api_key = args.aikey
    model = 'gpt-3.5-turbo'
    llm = sc.llm.LLM(model)
    with open(args.file) as file:
        spider = json.load(file)
    
    spider_db = spider[args.schema]
    schema = sc.schema.parse_spider(spider_db)
    original = schema.text()
    #compressed = sc.compress.compress_schema(llm, schema)
    
    original = \
"""stadium(Stadium_ID:number;primary key,Location:text,Name:text,Capacity:number,Highest:number,Lowest:number,Average:number)
singer(Singer_ID:number;primary key,Name:text,Country:text,Song_Name:text,Song_release_year:text,Age:number,Is_male:others)
concert(concert_ID:number;primary key,concert_Name:text,Theme:text,Stadium_ID:text,Year:text)
singer_in_concert(concert_ID:number;primary key,Singer_ID:text)"""
    compressed = \
"""Default:number
stadium(ID,Location:text,Name:text,Capacity,Highest,Lowest,Average)
Default:text
singer(ID:number,Name,Country,Song_Name,Song_year,Age:number,male:others)
concert(ID:number,Name,Theme,Stadium_ID,Year)
singer_in_concert(concert:number,Singer)"""
    
    original_length = sc.llm.nr_tokens(model, original)
    compressed_length = sc.llm.nr_tokens(model, compressed)
    print(llm(compressed + '\nWhat is the type of stadium.ID?'))

    print(original)
    print(compressed)
    
    print(f'Original length: \t{original_length}')
    print(f'Compressed length: \t{compressed_length}')
    
    tosql1 = sc.translate.Translator(llm, original)
    tosql2 = sc.translate.Translator(llm, compressed)
    question = "Show name, country, age for all singers ordered by age from the oldest to the youngest."
    query_1 = tosql1.translate(question)
    query_2 = tosql2.translate(question)
    print(query_1)
    print(query_2)