'''
Created on Sep 25, 2023

@author: immanueltrummer
'''
import argparse
import json
import os.path
import pathlib
from sc.schema import Column, Table, PrimaryKey, ForeignKey, Schema


def parse_spider(spider_db):
    """ Parse schema from Spider representation.
    
    Args:
        spider_db: database in SPIDER format.
    
    Returns:
        a database schema.
    """
    spider_tables = spider_db['table_names_original']
    spider_columns = spider_db['column_names_original']
    spider_types = spider_db['column_types']
    spider_pkeys = spider_db['primary_keys']
    spider_fkeys = spider_db['foreign_keys']
    
    type_map = {'text':'varchar(255)', 'number':'numeric(8, 2)'}
    tables = [Table(name, []) for name in spider_tables]
    for (table_idx, col_name), col_type in zip(spider_columns, spider_types):
        if not col_name == '*':
            if col_type in type_map:
                col_type = type_map[col_type]
            column = Column(col_name, col_type, [col_type, 'NOT NULL'])
            table = tables[table_idx]
            table.columns.append(column)
    
    pkeys = []
    for table_name, col_idx in zip(spider_tables, spider_pkeys):
        col_name = spider_columns[col_idx][1]
        pkey = PrimaryKey(table_name, [col_name])
        pkeys.append(pkey)
    
    fkeys = []
    for col_1_idx, col_2_idx in spider_fkeys:
        table_1_idx, col_1_name = spider_columns[col_1_idx]
        table_2_idx, col_2_name = spider_columns[col_2_idx]
        table_1_name = spider_tables[table_1_idx]
        table_2_name = spider_tables[table_2_idx]
        fkey = ForeignKey(
            table_1_name, [col_1_name], 
            table_2_name, [col_2_name])
        fkeys.append(fkey)
    
    return Schema(tables, pkeys, fkeys)


def select_databases(spider, k):
    """ Select given number of SPIDER databases.
    
    Args:
        spider: data for SPIDER.
        k: select k databases from SPIDER.
    
    Returns:
        names of databases with largest tables.
    """
    def table_size(db):
        """ Calculate average table size for database. """
        return len(db['column_names'])/len(db['table_names'])
    
    by_table_size = sorted(
        spider.items(), key=lambda i:table_size(i[1]), 
        reverse=True)
    sorted_db_names = [i[0] for i in by_table_size]
    return sorted_db_names[:k]


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('inpath', type=str, help='Path to input file')
    parser.add_argument('top_k', type=int, help='Number of output databases')
    parser.add_argument('outdir', type=str, help='Path to output folder')
    args = parser.parse_args()
    
    with open(args.inpath) as file:
        spider = json.load(file)
    
    db_names = select_databases(spider, args.top_k)
    for db_name in db_names:
        spider_db = spider[db_name]
        schema = parse_spider(spider_db)
        sql_ddl = schema.sql()
        
        out_dir = pathlib.Path(args.outdir)
        out_file = f'{db_name}.sql'
        out_path = os.path.join(out_dir, out_file)
        
        with open(out_path, 'w') as file:
            file.write(sql_ddl)