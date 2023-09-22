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


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str, help='Path to schema file')
    parser.add_argument('aikey', type=str, help='API key of OpenAI')
    args = parser.parse_args()
    
    #logging.basicConfig(level=logging.DEBUG)
    openai.api_key = args.aikey
    model = 'gpt-3.5-turbo'
    with open(args.file) as file:
        spider = json.load(file)
    
    raw_total = 0
    compressed_total = 0
    db_name = 'body_builder'
    spider_db = spider[db_name]
    # for db_name, spider_db in spider.items():
    
# CREATE TABLE nation
# (
    # n_nationkey  INTEGER not null,
    # n_name       CHAR(25) not null,
    # n_regionkey  INTEGER not null,
    # n_comment    VARCHAR(152)
# );
#
# CREATE TABLE region
# (
    # r_regionkey  INTEGER not null,
    # r_name       CHAR(25) not null,
    # r_comment    VARCHAR(152)
# );
#
# CREATE TABLE part
# (
    # p_partkey     BIGINT not null,
    # p_name        VARCHAR(55) not null,
    # p_mfgr        CHAR(25) not null,
    # p_brand       CHAR(10) not null,
    # p_type        VARCHAR(25) not null,
    # p_size        INTEGER not null,
    # p_container   CHAR(10) not null,
    # p_retailprice DOUBLE PRECISION not null,
    # p_comment     VARCHAR(23) not null
# );
#
# CREATE TABLE supplier
# (
    # s_suppkey     BIGINT not null,
    # s_name        CHAR(25) not null,
    # s_address     VARCHAR(40) not null,
    # s_nationkey   INTEGER not null,
    # s_phone       CHAR(15) not null,
    # s_acctbal     DOUBLE PRECISION not null,
    # s_comment     VARCHAR(101) not null
# );
#
# CREATE TABLE partsupp
# (
    # ps_partkey     BIGINT not null,
    # ps_suppkey     BIGINT not null,
    # ps_availqty    BIGINT not null,
    # ps_supplycost  DOUBLE PRECISION  not null,
    # ps_comment     VARCHAR(199) not null
# );
#
# CREATE TABLE customer
# (
    # c_custkey     BIGINT not null,
    # c_name        VARCHAR(25) not null,
    # c_address     VARCHAR(40) not null,
    # c_nationkey   INTEGER not null,
    # c_phone       CHAR(15) not null,
    # c_acctbal     DOUBLE PRECISION   not null,
    # c_mktsegment  CHAR(10) not null,
    # c_comment     VARCHAR(117) not null
# );
#
# CREATE TABLE orders
# (
    # o_orderkey       BIGINT not null,
    # o_custkey        BIGINT not null,
    # o_orderstatus    CHAR(1) not null,
    # o_totalprice     DOUBLE PRECISION not null,
    # o_orderdate      DATE not null,
    # o_orderpriority  CHAR(15) not null,  
    # o_clerk          CHAR(15) not null, 
    # o_shippriority   INTEGER not null,
    # o_comment        VARCHAR(79) not null
# );

    
    ddl = """
CREATE TABLE lineitem
(
    l_orderkey    BIGINT not null,
    l_partkey     BIGINT not null,
    l_suppkey     BIGINT not null,
    l_linenumber  BIGINT not null,
    l_quantity    DOUBLE PRECISION not null,
    l_extendedprice  DOUBLE PRECISION not null,
    l_discount    DOUBLE PRECISION not null,
    l_tax         DOUBLE PRECISION not null,
    l_returnflag  CHAR(1) not null,
    l_linestatus  CHAR(1) not null,
    l_shipdate    DATE not null,
    l_commitdate  DATE not null,
    l_receiptdate DATE not null,
    l_shipinstruct CHAR(25) not null,
    l_shipmode     CHAR(10) not null,
    l_comment      VARCHAR(44) not null
);
    """
    parser = sc.parser.SchemaParser()    
    schema = parser.parse(ddl)
    # schema = sc.schema.parse_spider(spider_db)

    raw_description = schema.text()
    raw_size = sc.llm.nr_tokens(model, raw_description)
    raw_total += raw_size
    
    #compressed_1 = sc.compress.types.compress_schema(schema)
    compressed_2 = sc.compress.default_types.compress_schema(schema)
    #compressed_1_size = sc.llm.nr_tokens(model, compressed_1)
    compressed_2_size = sc.llm.nr_tokens(model, compressed_2)
    
    splits = schema.split()
    for split in splits:
        split.merge_columns()
        ilpCompression = sc.compress.gurobi.IlpCompression(split)
        result = ilpCompression.compress()
        print(result)
    
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