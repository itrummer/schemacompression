'''
Created on Sep 27, 2023

@author: immanueltrummer
'''
def greedy_parts(schema):
    """ Greedily compress schema and return parts.
    
    Args:
        schema: compress this schema greedily.
    
    Returns:
        list of parts of greedy compression.
    """
    parts = []
    for table in schema.tables:
        parts += [table.as_predicate()]
        parts += ['(']
        for column in table.columns:
            parts += [column.name]
            parts += ['(']
            for annotation in column.annotations:
                parts += [annotation]
            parts += [')']
        parts += [')']
    return parts