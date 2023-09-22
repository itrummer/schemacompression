'''
Created on Sep 7, 2023

@author: immanueltrummer
'''
from collections import Counter, defaultdict
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
    
    def merge_columns(self):
        """ Merge columns with same annotations. """
        key2cols = defaultdict(lambda:[])
        for col in self.columns:
            col_key = ','.join(col.annotations) + col.type
            key2cols[col_key].append(col)
        
        new_columns = []
        for col_key, cols in key2cols.items():
            names = [c.name for c in cols]
            group_name = ' '.join(names)
            first_col = cols[0]
            group_type = first_col.type
            group_annotations = first_col.annotations
            new_col = Column(group_name, group_type, group_annotations)
            new_columns.append(new_col)
        
        self.columns = new_columns

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


class Schema():
    """ A schema is defined by tables and constraints. """
    
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
        
        self.column_count = Counter()
        for table in self.tables:
            for column in table.columns:
                col_name = column.name
                self.column_count.update([col_name])
        
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
        """ Returns all column names as list. """
        columns = []
        for table in self.tables:
            for column in table.columns:
                full_name = self._full_name(table, column)
                columns.append(full_name)
        
        return columns
    
    def get_facts(self):
        """ Returns tuple with true facts and false facts. """
        true_facts = []
        false_facts = []
        
        # Which columns belong to which tables?
        for table in self.tables:
            for column in table.columns:
                col_name = self._full_name(table, column)
                for tbl_name in self.get_tables():
                    predicate = f'table {tbl_name} column'
                    if tbl_name == table.name:
                        true_fact = (predicate, col_name)
                        true_facts.append(true_fact)
                    else:
                        false_fact = (predicate, col_name)
                        false_facts.append(false_fact)
        
        # Which annotations belong to which columns?
        for annotation in self.get_annotations():
            for table in self.tables:
                for column in table.columns:
                    col_name = self._full_name(table, column)
                    if annotation in column.annotations:
                        true_fact = (col_name, annotation)
                        true_facts.append(true_fact)
                    else:
                        false_fact = (col_name, annotation)
                        false_facts.append(false_fact)

        # Tables have no annotations
        # for annotation in self.get_annotations():
            # false_facts.append((annotation, 'table'))
            # for table in self.get_tables():
                # false_facts.append((table, annotation))

        return true_facts, false_facts
    
    def get_identifiers(self):
        """ Retrieve all identifiers that appear in facts. 
        
        Returns:
            list of identifiers.
        """
        true_facts, false_facts = self.get_facts()
        facts = true_facts + false_facts
        identifiers = set()
        for id_1, id_2 in facts:
            identifiers.add(id_1)
            identifiers.add(id_2)
        return list(identifiers)
    
    def get_tables(self):
        """ Returns all table names as list. """
        return [t.name for t in self.tables]

    def merge_columns(self):
        """ Group columns in all tables. """
        for table in self.tables:
            table.merge_columns()

    def split(self):
        """ Splits schema into multiple parts. 
        
        Returns:
            list of component schemata.
        """
        assert not self.pkeys, 'Cannot split with explicit primary keys!'
        assert not self.fkeys, 'Cannot split with explicit foreign keys!'
        schemas = []
        for table in self.tables:
            schema = Schema([table], [], [])
            schemas.append(schema)
        
        return schemas

    def sql(self):
        """ DDL commands for creating schema. 
        
        Returns:
            a string consisting of DDL commands.
        """
        return '\n'.join([t.sql() for t in self.tables])
    
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
    
    def _full_name(self, table, column):
        """ Returns fully qualified column name.
        
        Args:
            table: column belongs to this table.
            column: return name for this column.
        
        Returns:
            column with added table name (if ambiguous).
        """
        col_name = column.name
        if self._is_ambiguous(col_name):
            tbl_name = table.name
            return f'{tbl_name}.{col_name}'
        else:
            return col_name
    
    def _is_ambiguous(self, col_name):
        """ Checks if column name is ambiguous.
        
        Args:
            col_name: name of column to test.
        
        Returns:
            True if the column appears in multiple tables.
        """
        return (self.column_count[col_name] > 1)


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