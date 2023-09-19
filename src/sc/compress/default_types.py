'''
Created on Sep 10, 2023

@author: immanueltrummer
'''
import collections


def compress_table(table, default_type, mark_type):
    """ Generate concise description of table.
    
    Args:
        table: describe this table.
        default_type: omit this column type.
        mark_type: replace this type by *.
    
    Returns:
        compressed table description.
    """
    col_items = []
    for col in table.columns:
        if col.type == default_type:
            col_item = col.name
        elif col.type == mark_type:
            col_item = f'{col.name}-'
        else:
            col_item = f'{col.name}:{col.type}'
        
        for a in col.annotations:
            if a.startswith('foreign key references '):
                shortened = a.replace('foreign key references ', '->')
                col_item = f'{col_item}{shortened}'
        
        if [a for a in col.annotations if a == 'primary key']:
            col_item = f'{col_item}*'
        
        col_items.append(col_item)
    
    col_list = ','.join(col_items)
    return f'{table.name}({col_list})'


def compress_schema(schema):
    """ Generate concise description of schema.
    
    Args:
        schema: compress this schema.
    
    Returns:
        compressed schema description.
    """
    counter = collections.Counter()
    for table in schema.tables:
        types = [c.type for c in table.columns]
        counter.update(types)
    
    common_types = counter.most_common(2)
    default_type = common_types[0][0]
    context = f'Default type:{default_type};*:primary key;->:foreign key'
    if len(common_types) > 1:
        mark_type = common_types[1][0]
        context = f'{context};-:{mark_type}'
    else:
        mark_type = None
    
    parts = [context]
    for table in schema.tables:
        table_description = compress_table(table, default_type, mark_type)
        parts.append(table_description)
    
    return '\n'.join(parts)