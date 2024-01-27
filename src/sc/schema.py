'''
Created on Sep 7, 2023

@author: immanueltrummer
'''
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import List
from sc.llm import nr_tokens


@dataclass
class Column():
    """ Represents a typed table column. """
    name: str
    """ The column name. """
    type: str
    """ The column data type. """
    annotations: List[str]
    """ All applicable column annotations. """
    merged: bool
    """ Whether this is a merged column group. """
    
    def sql(self):
        """ DDL description of column with type. """
        annotation_list = ' '.join(self.annotations)
        return f'{self.name} {annotation_list}'


@dataclass
class Table():
    """ A table is characterized by a column list. """
    name: str
    columns: List[Column]
    
    def as_predicate(self):
        """ Returns string snippet to express association. """
        return f'table {self.name}'
    
    def merge_columns(self):
        """ Merge columns with same annotations. """
        key2cols = defaultdict(lambda:[])
        for col in self.columns:
            col_key = ','.join(col.annotations) + col.type
            key2cols[col_key].append(col)
        
        new_columns = []
        for col_key, cols in key2cols.items():
            group_size = len(cols)
            names = [c.name for c in cols]
            group_name = ' '.join(names)
            if group_size > 1:
                group_name = f'[{group_name}]'
            first_col = cols[0]
            group_type = first_col.type
            group_annotations = first_col.annotations
            merged = True if group_size > 1 else False
            new_col = Column(group_name, group_type, group_annotations, merged)
            new_columns.append(new_col)
        
        self.columns = new_columns

    def sql(self):
        """ DDL description of table. """
        columns_sql = ','.join([c.sql() for c in self.columns])
        return f'create table {self.name}({columns_sql});'
    
    def text(self):
        """ Text description of table. """
        columns_text = ', '.join([c.sql() for c in self.columns])
        return f'{self.name}({columns_text});'


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
                annotation = \
                    f'foreign key ({from_col}) references {to_tbl}({to_col})'
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
        """ Returns list of all columns. """
        return [c for t in self.tables for c in t.columns]
    
    def get_column_names(self):
        """ Returns all column names as list. """
        columns = []
        for table in self.tables:
            for column in table.columns:
                full_name = self._full_name(table, column)
                columns.append(full_name)
        
        return columns
    
    def get_facts(self):
        """ Returns tuple with true facts and false facts.
        
        Attention: we assume that columns are only mentioned
        within the context of their respective tables! Otherwise,
        equal column names across tables could lead to ambiguity.
        """
        false_facts = set()
        true_facts = set()
        
        # Table-column associations are false by default
        for table in self.tables:
            for column in self.get_columns():
                predicate = table.as_predicate()
                col_name = column.name
                false_fact = (predicate, col_name)
                false_facts.add(false_fact)
        
        # Consider actual table-column associations
        for table in self.tables:
            for column in table.columns:
                predicate = table.as_predicate()
                col_name = column.name
                true_fact = (predicate, col_name)
                true_facts.add(true_fact)
                false_facts.remove(true_fact)
        
        # Which annotations belong to which columns?
        for annotation in self.get_annotations():
            for table in self.tables:
                for column in table.columns:
                    col_name = column.name
                    if annotation in column.annotations:
                        true_fact = (col_name, annotation)
                        true_facts.add(true_fact)
                    else:
                        false_fact = (col_name, annotation)
                        false_facts.add(false_fact)

        return list(true_facts), list(false_facts)
    
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
    
    def prefixes(self, llm_name):
        """ Returns good prefix candidates for shortcuts.
        
        Args:
            llm_name: select prefixes for this LLM.
        
        Returns:
            shortcut candidates, sorted by benefit (descending).
        """
        prefix2count = self._prefix_frequency()
        pruned2count = self._prune_prefixes(prefix2count, llm_name)
        sorted_items = sorted(
            pruned2count.items(), key=lambda i:i[1], reverse=True)
        sorted_prefixes = [i[0] for i in sorted_items]
        return sorted_prefixes
    
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
    
    def _count_prefixes(self, counter, identifier):
        """ Count prefixes of given identifier.
        
        Args:
            counter: update this counter object.
            identifier: consider prefixes of this identifier.
        """
        id_length = len(identifier)
        for prefix_length in range(2, id_length+1):
            prefix = identifier[:prefix_length]
            counter.update([prefix])
    
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
    
    def _prefix_frequency(self):
        """ Returns prefixes and associated frequencies.
        
        Returns:
            counter mapping prefixes to frequencies.
        """
        counter = Counter()
        for table in self.tables:
            self._count_prefixes(counter, table.name)
            for column in table.columns:
                self._count_prefixes(counter, column.name)
                for annotation in column.annotations:
                    self._count_prefixes(counter, annotation)
        
        return counter
    
    def _prune_prefixes(self, prefix2count, llm_name):
        """ Prune prefixes dominated by others.
        
        Args:
            prefix2count: maps prefixes to counts.
            llm_name: prune prefixes for this LLM.
        
        Returns:
            pruned dictionary mapping prefixes to counts.
        """
        pruned = {
            k:c for k, c in prefix2count.items() \
            if c>1 and nr_tokens(llm_name, k)>1}
        for prefix in prefix2count.keys():
            for sub_length in range(len(prefix)):
                sub_prefix = prefix[:sub_length]
                if sub_prefix in pruned:
                    pre_count = prefix2count[prefix]
                    sub_count = prefix2count[sub_prefix]
                    if sub_count <= pre_count:
                        del pruned[sub_prefix]
        
        return pruned