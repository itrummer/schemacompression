'''
Created on Sep 7, 2023

@author: immanueltrummer
'''
from dataclasses import dataclass
from typing import List


@dataclass
class Column():
    """ Represents a typed table column. """
    name: str
    type: str
    
    def sql(self):
        """ DDL description of column with type. """
        return f'{self.name}:{self.type}'


@dataclass
class Table():
    """ A table is characterized by a column list. """
    name: str
    columns: List[Column]
    
    def sql(self):
        """ DDL description of table. """
        columns_sql = ','.join([c.sql() for c in self.columns])
        return f'create table {self.name}({columns_sql});'
    
    def text(self):
        """ Text description of table. """
        columns_text = ','.join([c.sql() for c in self.columns])
        return f'{self.name}({columns_text})'


@dataclass
class PrimaryKey():
    """ Represents primary key constraint. """
    table: str
    columns: List[str]


@dataclass
class ForeignKey():
    """ Represents foreign key constraint. """
    from_table: str
    from_columns: List[str]
    to_table: str
    to_columns: List[str]


@dataclass
class Schema():
    """ A schema is defined by tables and constraints. """
    tables: List[Table]
    pkeys: List[PrimaryKey]
    fkeys: List[ForeignKey]
    
    def sql(self):
        """ DDL commands for creating schema. 
        
        Returns:
            a string consisting of DDL commands.
        """
        return '\n'.join([t.sql() for t in self.tables])
    
    def text(self):
        """ Returns text representation of schema. """
        return '\n'.join([t.text() for t in self.tables])


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
    
    tables = [Table(name, []) for name in spider_tables]
    for (table_idx, col_name), col_type in zip(spider_columns, spider_types):
        if not col_name == '*':
            column = Column(col_name, col_type)
            table = tables[table_idx]
            table.columns.append(column)
    
    pkeys = []
    for table_name, col_idx in zip(spider_tables, spider_pkeys):
        col_name = spider_columns[col_idx][1]
        pkey = PrimaryKey(table_name, col_name)
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