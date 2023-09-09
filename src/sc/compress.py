'''
Created on Sep 7, 2023

@author: immanueltrummer
'''
def get_prompt(schema):
    """ Generate prompt for schema compression.
    
    Args:
        schema: schema to compress.
    
    Returns:
        a prompt instructing language model for compression.
    """
    parts = []
    parts.append(f'Shorten the following schema description:')
    parts.append(schema.sql())
    parts.append(f'Shortened schema:')
    return '\n'.join(parts)


def compress_schema(llm, schema):
    """ Try to make the input schema more concise. 
    
    Args:
        llm: large language model wrapper.
        schema: schema to compress.
    
    Returns:
        compressed string representation.
    """
    prompt = get_prompt(schema)
    compressed = llm(prompt)
    return compressed