'''
Created on Sep 13, 2023

@author: immanueltrummer
'''
from pulp import LpMinimize, LpProblem, LpStatus, lpSum, LpVariable, get_solver


class IlpCompression():
    """ Compresses schemata via integer linear programming. """
    
    def __init__(self, schema, max_depth=3):
        """ Initializes for given schema. 
        
        Args:
            schema: a schema to compress.
            max_depth: maximal context depth.
        """
        self.schema = schema
        self.max_depth = max_depth
        self.tables = schema.tables()
        self.columns = schema.columns()
        self.annotations = schema.annotations()
        self.ids = self.tables + self.columns + self.annotations
        self.tokens = self.ids + ['(', ')']
        self.facts = schema.facts()
        self.max_length = 3 * len(self.facts)
        self.decision_vars, self.context_vars, self.fact_vars = self._variables()
        self.model = LpProblem(name='Schema compression', sense=LpMinimize)

    def _add_constraints(self):
        """ Adds constraints to internal model. """
        # Cannot have both: opening and closing parentheses!
        for pos in range(self.max_length):
            opening = self.decision_vars[pos]['(']
            closing = self.decision_vars[pos][')']
            self.model += opening + closing <= 1
        
        # Select at most one ID token per position
        for pos in range(self.max_length):
            token_vars = [self.decision_vars[pos][token] for token in self.ids]
            self.model += lpSum(token_vars) <= 1
        
        # Balance opening and closing parentheses
        opening = [decisions['('] for decisions in self.decision_vars]
        closing = [decisions[')'] for decisions in self.decision_vars]
        self.model += lpSum(opening) == lpSum(closing)
        
        # Never more closing than opening parenthesis!
        for pos in range(self.max_length):
            opening = [ds['('] for ds in self.decision_vars[:pos]]
            closing = [ds[')'] for ds in self.decision_vars[:pos]]
            self.model += lpSum(opening) >= lpSum(closing)
        
        # Each context layer fixes at most one token
        for pos in range(self.max_length):
            for depth in range(self.max_depth):
                self.model += lpSum(
                    self.context_vars[pos][depth].values()) <= 1
        
        # Context layers are used consecutively
        for pos in range(self.max_length):
            for depth_1 in range(self.max_depth-1):
                depth_2 = depth_1 + 1
                sum_1 = lpSum(self.context_vars[pos][depth_1].values())
                sum_2 = lpSum(self.context_vars[pos][depth_2].values())
                self.model += sum_1 >= sum_2
        
        # Collect all context variables per position
        context_by_pos = []
        for pos in range(self.max_length):
            pos_vars = []
            context_by_pos.append(pos_vars)
            for depth in range(self.max_depth):
                pos_vars += self.context_vars[pos][depth].values()
        
        # Initial context is empty
        self.model += lpSum(context_by_pos[0]) == 0
        
        # Ensure correct number of context tokens
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            sum_1 = lpSum(context_by_pos[pos_1])
            sum_2 = lpSum(context_by_pos[pos_2])
            opening = self.decision_vars[pos_1]['(']
            closing = self.decision_vars[pos_1][')']
            self.model += sum_1 + opening - closing == sum_2
        
        # Create activation variables
        activations = []
        for pos in range(self.max_length):
            opening = self.decision_vars[pos]['(']
            cur_activations = {}
            activations.append(cur_activations)
            for token in self.ids:
                token_var = self.decision_var[pos][token]
                name = f'Activate_P{pos}_{token}'
                activation = LpVariable(
                    name=name, lowBound=0, 
                    highBound=1, cat='Integer')
                self.model += activation <= opening
                self.model += activation <= token_var
                self.model += activation >= opening + token_var - 1
                cur_activations[token] = activation
        
        # Set context variables as function of prior context and activation
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            for depth in range(self.max_depth):
                for token in self.ids:
                    prior = self.context_vars[pos_1][depth][token]
                    activation = activations[pos_1][token]
                    cur = self.context_vars[pos_2][depth][token]
                    self.model += cur == prior + activation
        
        # Link facts to nested tokens
        for token_1 in self.ids:
            for token_2 in self.ids:
                if token_1 < token_2:
                    # Sum over possible mentions
                    mentions = []
                    for pos in range(self.max_length):
                        for depth in range(self.max_depth):
                            context_var = self.context_vars[pos][depth][token_1]
                    fact_key = frozenset({token_1, token_2})
                    fact_var = self.fact_vars[fact_key]
                
                scaling = 1.0 / (self.max_length * self.max_depth)

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
                decision_var = LpVariable(
                    name=name, lowBound=0, 
                    highBound=1, cat='Integer')
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
                    context_var = LpVariable(
                        name=name, lowBound=0,
                        highBound=1, cat='Integer')
                    cur_depth_vars[context_id] = context_var
        
        # Access by fact_vars[frozenset([id_1, id_2])]
        fact_vars = {}
        for id_1 in self.ids:
            for id_2 in self.ids:
                if id_1 < id_2:
                    fact_name = f'{id_1}_{id_2}'
                    fact_var = LpVariable(
                        name=fact_name, lowBound=0, 
                        highBound=1, cat='Integer')
                    ids = frozenset(id_1, id_2)
                    fact_vars[ids] = fact_var
        
        return decision_vars, context_vars, fact_vars
        

# Create the model
model = LpProblem(name="small-problem", sense=LpMinimize)

# Initialize the decision variables
x = LpVariable(name="x", lowBound=0)
y = LpVariable(name="y", lowBound=0)

# Add the constraints to the model
model += (2 * x + y <= 20, "red_constraint")
model += (4 * x - 5 * y >= -10, "blue_constraint")
model += (-x + 2 * y >= -2, "yellow_constraint")
model += (-x + 5 * y == 15, "green_constraint")

# Add the objective function to the model
model += lpSum([x, 2 * y])

# Solve the problem
solver = get_solver('GLPK_CMD', path='/opt/homebrew/bin/glpsol')
status = model.solve(solver=solver)