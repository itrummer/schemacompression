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
    """ The column name. """
    type: str
    """ The column data type. """
    annotations: List[str]
    """ All applicable column annotations. """
    
    def sql(self):
        """ DDL description of column with type. """
        annotation_list = ' '.join(self.annotations)
        return f'{self.name}:{annotation_list}'


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


#@dataclass
class Schema():
    """ A schema is defined by tables and constraints. """
    # tables: List[Table]
    # pkeys: List[PrimaryKey]
    # fkeys: List[ForeignKey]
    
    def __init__(self, tables, pkeys, fkeys):
        """ Initialize for given tables, primary, and foreign keys.
        
        Args:
            tables: list of database tables.
            pkeys: list of primary key constraints.
            fkeys: list of foreign key constraints.
        """
        self.tables = tables
        self.pkeys = []
        self.fkeys = []
        
        print(pkeys)
        for pkey in pkeys:
            if len(pkey.columns) == 1:
                tbl_name = pkey.table
                col_name = pkey.columns[0]
                self._add_annotation(tbl_name, col_name, 'primary key')
            else:
                self.pkeys.append(pkey)
                        
        for fkey in fkeys:
            if len(fkey.from_columns) == 1:
                from_tbl = fkey.from_table
                from_col = fkey.from_columns[0]
                to_tbl = fkey.to_table
                to_col = fkey.to_columns[0]
                annotation = f'foreign key references {to_tbl}({to_col})'
                self._add_annotation(from_tbl, from_col, annotation)
            else:
                self.fkeys.append(fkey)
    
    def get_annotations(self):
        """ Returns all annotations. """
        tags = set()
        for table in self.tables:
            for column in table.columns:
                tags.update(column.annotations)
        
        return list(tags)
    
    def get_columns(self):
        """ Returns all columns. """
        columns = set()
        for table in self.tables:
            for column in table.columns:
                col_name = column.name
                if col_name in columns:
                    tbl_name = table.name
                    full_name = f'{tbl_name}.{col_name}'
                    columns.add(full_name)
                else:
                    columns.add(col_name)
        
        return list(columns)
    
    def get_facts(self):
        """ Returns tuple with true facts and false facts. """
        facts = []
        for table in self.tables:
            tbl_name = table.name
            facts += [(tbl_name, 'table')]
            for column in table.columns:
                col_name = column.name
                facts += [(col_name, 'column')]
                facts += [(col_name, tbl_name)]
                for annotation in column.annotations:
                    facts += [(col_name, annotation)]
        
        return facts, []
    
    def sql(self):
        """ DDL commands for creating schema. 
        
        Returns:
            a string consisting of DDL commands.
        """
        return '\n'.join([t.sql() for t in self.tables])
    
    def get_tables(self):
        """ Returns all table names. """
        return [t.name for t in self.tables]
    
    def text(self):
        """ Returns text representation of schema. """
        return '\n'.join([t.text() for t in self.tables])

    def _add_annotation(self, tbl_name, col_name, annotation):
        """ Add column annotation.
        
        Args:
            tbl_name: name of table containing column.
            col_name: name of column to annotate.
            annotation: add this annotation.
        """
        for table in self.tables:
            if table.name == tbl_name:
                for column in table.columns:
                    if column.name == col_name:
                        column.annotations.append(annotation)
                        break
                break


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
            column = Column(col_name, col_type, [col_type])
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