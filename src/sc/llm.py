'''
Created on Sep 8, 2023

@author: immanueltrummer
'''
import openai
import tiktoken
import time


def nr_tokens(model, text):
    """ Counts the number of tokens in text.
    
    Args:
        model: use tokenizer of this model.
        text: count tokens for this text.
    
    Returns:
        number of tokens in input text.
    """
    tokenizer = tiktoken.encoding_for_model(model)
    tokens = tokenizer.encode(text)
    return len(tokens)


class LLM():
    """ Represents large language model. """
    
    def __init__(self, name):
        """ Initializes for OpenAI model.
        
        Args:
            name: name of OpenAI model.
        """
        self.name = name

    def __call__(self, prompt):
        """ Retrieves answer from LLM. 
        
        Args:
            prompt: input prompt.
        
        Returns:
            model output.
        """
        for retry_nr in range(1, 4):
            try:
                response = openai.ChatCompletion.create(
                    model=self.name,
                    messages=[
                        {'role':'user', 'content':prompt}
                        ]
                    )
                return response['choices'][0]['message']['content']
            except:
                time.sleep(2 * retry_nr)
        raise Exception('Cannot reach OpenAI model!')