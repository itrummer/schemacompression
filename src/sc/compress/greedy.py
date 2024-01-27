'''
Created on Sep 27, 2023

@author: immanueltrummer
'''
def greedy_parts(schema, full_names=False):
    """ Greedily compress schema and return parts.
    
    Args:
        schema: compress this schema greedily.
        full_names: whether to add table as prefix.
    
    Returns:
        list of parts of greedy compression.
    """
    parts = []
    for table in schema.tables:
        parts += [table.as_predicate()]
        parts += ['(']
        for column in table.columns:
            if full_names:
                col_name = schema.full_name(table, column)
            else:
                col_name = column.name
            
            parts += [col_name]
            parts += ['(']
            for annotation in column.annotations:
                parts += [annotation]
            parts += [')']
        parts += [')']
    return parts