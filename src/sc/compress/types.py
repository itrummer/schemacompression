'''
Created on Sep 10, 2023

@author: immanueltrummer
'''
import collections


def compress_table(table):
    """ Returns compressed description of one table.
    
    Args:
        table: compress this table.
    
    Returns:
        compressed description.
    """
    type2cols = collections.defaultdict(lambda:[])
    for col in table.columns:
        type2cols[col.type].append(col.name)
    
    parts = [table.name]
    parts.append('(')
    for col_type, col_names in type2cols.items():
        parts.append(col_type)
        parts.append(':')
        col_list = ','.join(col_names)
        parts.append(col_list)
        parts.append(';')
    
    parts.pop()
    parts.append(')')
    return ''.join(parts)


def compress_schema(schema):
    """ Returns compressed text description of schema.
    
    Args:
        schema: a relational database schema.
    
    Returns:
        compressed schema description.
    """
    parts = [compress_table(t) for t in schema.tables]
    return '\n'.join(parts)