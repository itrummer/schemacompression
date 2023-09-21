'''
Created on Sep 20, 2023

@author: immanueltrummer
'''
'''
Created on Sep 13, 2023

@author: immanueltrummer
'''
import gurobipy as gp
import logging
import sc.llm
from gurobipy import GRB

class IlpCompression():
    """ Compresses schemata via integer linear programming. """
    
    def __init__(self, schema, max_depth=1, llm_name='gpt-3.5-turbo'):
        """ Initializes for given schema. 
        
        Args:
            schema: a schema to compress.
            max_depth: maximal context depth.
            llm_name: name of LLM to use.
        """
        self.schema = schema
        self.max_depth = max_depth
        self.llm_name = llm_name
        self.tables = schema.get_tables()
        self.columns = schema.get_columns()
        self.annotations = schema.get_annotations()
        self.ids = self.tables + self.columns + \
            self.annotations + ['table', 'column']
        self.tokens = self.ids + ['(', ')', ',']
        
        logging.debug(f'Tables: {self.tables}')
        logging.debug(f'Columns: {self.columns}')
        logging.debug(f'Annotations: {self.annotations}')
        logging.debug(f'IDs: {self.ids}')
        logging.debug(f'Tokens: {self.tokens}')
        
        self.true_facts, self.false_facts = schema.get_facts()
        self.max_length = 2*len(self.true_facts)
        
        self.model = gp.Model('Compression')
        self.decision_vars, self.context_vars, self.fact_vars = self._variables()
        
        logging.debug(f'True facts: {self.true_facts}')
        logging.debug(f'False facts: {self.false_facts}')
        
        # print(self.decision_vars)
        # print(self.context_vars)
        # print(self.fact_vars)
        
        self._add_constraints()
        self._add_objective()
        # print(self.model)

    def compress(self):
        """ Solve compression problem and return solution.
        
        Returns:
            Compressed representation of schema.
        """
        self.model.optimize()
        # Extract solution
        parts = []
        for pos in range(self.max_length):
            for token in self.ids:
                if self.decision_vars[pos][token].X >= 0.5:
                    parts += [token]
            
            for token in ['(', ')', ',']:
                if self.decision_vars[pos][token].X >= 0.5:
                    parts += [token]
        
        # for pos in range(self.max_length):
            # for token in self.tokens:
                # decision_var = self.decision_vars[pos][token]
                # print(f'{decision_var.name} = {decision_var.varValue}')
                #
        # for fact_var in self.fact_vars.values():
            # print(f'{fact_var.name} = {fact_var.varValue}')
            #
        # for pos in range(self.max_length):
            # for depth in range(self.max_depth):
                # for context_var in self.context_vars[pos][depth].values():
                    # print(f'{context_var.name} = {context_var.varValue}')
        
        return ''.join(parts)

    def _add_constraints(self):
        """ Adds constraints to internal model. """
        # Cannot have both: opening and closing parentheses!
        for pos in range(self.max_length):
            opening = self.decision_vars[pos]['(']
            closing = self.decision_vars[pos][')']
            comma = self.decision_vars[pos][',']
            self.model.addConstr(opening + closing + comma <= 1)
        
        # Introduce auxiliary variables representing emptiness
        is_empties = []
        for pos in range(self.max_length):
            name = f'P{pos}_empty'
            is_empty = self.model.addVar(vtype=GRB.BINARY, name=name)
            is_empties.append(is_empty)

        # Ensure correct value for auxiliary variables
        for pos in range(self.max_length):
            is_empty = is_empties[pos]
            token_vars = [self.decision_vars[pos][t] for t in self.tokens]
            self.model.addConstr(is_empty >= 1 - gp.quicksum(token_vars))
            for token_var in token_vars:
                self.model.addConstr(is_empty <= 1 - token_var)
        
        # Can only have empty slots at the end of description
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            empty_1 = is_empties[pos_1]
            empty_2 = is_empties[pos_2]
            self.model.addConstr(empty_1 <= empty_2)
        
        # Must separate consecutive tokens
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            token_vars_1 = [self.decision_vars[pos_1][t] for t in self.ids]
            token_vars_2 = [self.decision_vars[pos_2][t] for t in self.ids]
            specials_1 = [self.decision_vars[pos_1][t] for t in ['(', ')', ',']]
            self.model.addConstr(
                gp.quicksum(token_vars_1) + gp.quicksum(token_vars_2) \
                - gp.quicksum(specials_1) <= 1)
            
        # Select at most one ID token per position
        for pos in range(self.max_length):
            token_vars = [self.decision_vars[pos][token] for token in self.ids]
            self.model.addConstr(gp.quicksum(token_vars) <= 1)
        
        # Must connect opening parenthesis with token
        for pos in range(self.max_length):
            opening = self.decision_vars[pos]['(']
            token_vars = [self.decision_vars[pos][token] for token in self.ids]
            self.model.addConstr(opening <= gp.quicksum(token_vars))
            
        # Balance opening and closing parentheses
        opening = [decisions['('] for decisions in self.decision_vars]
        closing = [decisions[')'] for decisions in self.decision_vars]
        self.model.addConstr(gp.quicksum(opening) == gp.quicksum(closing))
        
        # Never more closing than opening parenthesis!
        for pos in range(self.max_length):
            opening = [ds['('] for ds in self.decision_vars[:pos+1]]
            closing = [ds[')'] for ds in self.decision_vars[:pos+1]]
            self.model.addConstr(gp.quicksum(opening) >= gp.quicksum(closing))
        
        # Do not select tokens already in context (required for correctness!)
        # Otherwise: selects any token in context after re-activating token.
        for pos in range(self.max_length):
            for token in self.ids:
                context_vars = []
                for depth in range(self.max_depth):
                    context_var = self.context_vars[pos][depth][token]
                    context_vars.append(context_var)
                decision_var = self.decision_vars[pos][token]
                self.model.addConstr(gp.quicksum(context_vars) + decision_var <= 1)
            
        # Each context layer fixes at most one token
        for pos in range(self.max_length):
            for depth in range(self.max_depth):
                self.model.addConstr(
                    gp.quicksum(self.context_vars[pos][depth].values()) <= 1)
                    
        # Context layers are used consecutively
        for pos in range(self.max_length):
            for depth_1 in range(self.max_depth-1):
                depth_2 = depth_1 + 1
                sum_1 = gp.quicksum(self.context_vars[pos][depth_1].values())
                sum_2 = gp.quicksum(self.context_vars[pos][depth_2].values())
                self.model.addConstr(sum_1 >= sum_2)
        
        # Collect all context variables per position
        context_by_pos = []
        for pos in range(self.max_length):
            pos_vars = []
            for depth in range(self.max_depth):
                pos_vars += list(self.context_vars[pos][depth].values())
            context_by_pos.append(pos_vars)
        
        # Initial context is empty
        self.model.addConstr(gp.quicksum(context_by_pos[0]) == 0)
        
        # Ensure correct number of context tokens
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            sum_1 = gp.quicksum(context_by_pos[pos_1])
            sum_2 = gp.quicksum(context_by_pos[pos_2])
            opening = self.decision_vars[pos_1]['(']
            closing = self.decision_vars[pos_1][')']
            self.model.addConstr(sum_1 + opening - closing == sum_2)
        
        # Create activation variables
        activations = []
        for pos in range(self.max_length):
            opening = self.decision_vars[pos]['(']
            cur_activations = {}
            for token in self.ids:
                token_var = self.decision_vars[pos][token]
                name = f'Activate_P{pos}_{token}'
                activation = self.model.addVar(vtype=GRB.BINARY, name=name)
                self.model.addConstr(activation <= opening)
                self.model.addConstr(activation <= token_var)
                self.model.addConstr(activation >= opening + token_var - 1)
                cur_activations[token] = activation
            activations.append(cur_activations)
        
        # Set context variables as function of activation
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            for token in self.ids:
                activation_var = activations[pos_1][token]
                token_vars = [
                    self.context_vars[pos_2][d][token]
                    for d in range(self.max_depth)]
                self.model.addConstr(gp.quicksum(token_vars) >= activation_var)
        
        # Restrict context changes, compared to prior context
        for pos_1 in range(self.max_length-1):
            opening = self.decision_vars[pos_1]['(']
            closing = self.decision_vars[pos_1][')']
            pos_2 = pos_1 + 1
            for depth in range(self.max_depth):
                for token in self.ids:
                    var_1 = self.context_vars[pos_1][depth][token]
                    var_2 = self.context_vars[pos_2][depth][token]
                    self.model.addConstr(var_2 >= var_1 - closing)
                    self.model.addConstr(var_2 <= var_1 + opening)
        
        def get_mention_var(outer_token, inner_token, pos, depth):
            """ Generate variable representing fact mention.
            
            Args:
                outer_token: token that appears in context.
                inner_token: token that appears within context.
                pos: position at which mention occurs.
                depth: depth of relevant context.
            """
            outer_var = self.context_vars[pos][depth][outer_token]
            inner_var = self.decision_vars[pos][inner_token]
            name = f'Mention_P{pos}_D{depth}_{outer_token}_{inner_token}'
            mention_var = self.model.addVar(vtype=GRB.BINARY, name=name)
            self.model.addConstr(mention_var <= outer_var)
            self.model.addConstr(mention_var <= inner_var)
            self.model.addConstr(mention_var >= -1 + outer_var + inner_var)
            return mention_var

        # Link facts to nested tokens
        for token_1 in self.ids:
            for token_2 in self.ids:
                if token_1 < token_2:
                    # Sum over possible mentions
                    mention_vars = []
                    for pos in range(self.max_length):
                        for depth in range(self.max_depth):
                            mention_var_1 = get_mention_var(
                                token_1, token_2, pos, depth)
                            mention_var_2 = get_mention_var(
                                token_2, token_1, pos, depth)
                            mention_vars += [mention_var_1, mention_var_2]
                            
                    fact_key = frozenset({token_1, token_2})
                    fact_var = self.fact_vars[fact_key]
                    self.model.addConstr(fact_var <= gp.quicksum(mention_vars))
                    for mention_var in mention_vars:
                        self.model.addConstr(fact_var >= mention_var)
        
        # Make sure that true facts are mentioned
        for token_1, token_2 in self.true_facts:
            fact_key = frozenset({token_1, token_2})
            fact_var = self.fact_vars[fact_key]
            self.model.addConstr(fact_var >= 1)
        
        # Ensure that wrong facts are not mentioned
        for token_1, token_2 in self.false_facts:
            fact_key = frozenset({token_1, token_2})
            fact_var = self.fact_vars[fact_key]
            self.model.addConstr(fact_var <= 0)

    def _add_objective(self):
        """ Add optimization objective. """
        token_vars = []
        for pos in range(self.max_length):
            for token in self.tokens:
                token_var = self.decision_vars[pos][token]
                weight = sc.llm.nr_tokens(self.llm_name, token)
                token_vars.append(weight * token_var)
        self.model.setObjective(gp.quicksum(token_vars), GRB.MINIMIZE)
    
    def _variables(self):
        """ Returns variables for input schema. 
        
        Returns:
            decision variables, context variables, and fact variables.
        """
        # Access by decision_vars[position][token]
        decision_vars = []
        for pos in range(self.max_length):
            cur_pos_vars = {}
            for token in self.tokens:
                name = f'P{pos}_{token}'
                decision_var = self.model.addVar(vtype=GRB.BINARY, name=name)
                cur_pos_vars[token] = decision_var
            decision_vars.append(cur_pos_vars)
        
        # Access by context_vars[position][depth][token]
        context_vars = []
        for pos in range(self.max_length):
            cur_pos_vars = []
            context_vars.append(cur_pos_vars)
            for depth in range(self.max_depth):
                cur_depth_vars = {}
                cur_pos_vars.append(cur_depth_vars)
                for context_id in self.ids:
                    name = f'P{pos}_D{depth}_{context_id}'
                    context_var = self.model.addVar(
                        vtype=GRB.BINARY, name=name)
                    cur_depth_vars[context_id] = context_var
        
        # Access by fact_vars[frozenset([id_1, id_2])]
        fact_vars = {}
        for id_1 in self.ids:
            for id_2 in self.ids:
                if id_1 < id_2:
                    fact_name = f'{id_1}_{id_2}'
                    fact_var = self.model.addVar(
                        vtype=GRB.BINARY, name=fact_name)
                    ids = frozenset({id_1, id_2})
                    fact_vars[ids] = fact_var
        
        logging.debug(f'Fact variable keys: {fact_vars.keys()}')
        return decision_vars, context_vars, fact_vars
        

if __name__ == '__main__':
    
    import sc.schema
    logging.basicConfig(level=logging.DEBUG)
    column = sc.schema.Column('testcolumn', 'testtype', [])
    table = sc.schema.Table('testtable', [column])
    schema = sc.schema.Schema([table], [], [])
    compressor = IlpCompression(schema)
    compressed = compressor.compress()
    print(compressed)
# Create the model
# model = LpProblem(name="small-problem", sense=LpMinimize)
#
# # Initialize the decision variables
# x = LpVariable(name="x", lowBound=0)
# y = LpVariable(name="y", lowBound=0)
#
# # Add the constraints to the model
# model += (2 * x + y <= 20, "red_constraint")
# model += (4 * x - 5 * y >= -10, "blue_constraint")
# model += (-x + 2 * y >= -2, "yellow_constraint")
# model += (-x + 5 * y == 15, "green_constraint")
#
# # Add the objective function to the model
# model += lpSum([x, 2 * y])
#
# # Solve the problem
# solver = get_solver('GLPK_CMD', path='/opt/homebrew/bin/glpsol')
# status = model.solve(solver=solver)