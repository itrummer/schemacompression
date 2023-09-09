'''
Created on Sep 8, 2023

@author: immanueltrummer
'''
class Translator():
    """ Translates questions to SQL queries. """
    
    def __init__(self, llm, db_description):
        """ Initialize with given schema description.
        
        Args:
            llm: large language model.
            db_description: describes database schema.
        """
        self.llm = llm
        self.db_description = db_description
    
    def translate(self, question):
        """ Translates question into an SQL query.
        
        Args:
            question: translate this into SQL query.
        
        Returns:
            SQl query translating question.
        """
        prompt = self._prompt(question)
        query = self.llm(prompt)
        return query
    
    def _prompt(self, question):
        """ Generate instructions for question translation. 
        
        Args:
            question: question to translate into SQL.
        
        Returns:
            text instructions for translation.
        """
        return f'{self.db_description}\nQuestion:{question}\nSQL:'