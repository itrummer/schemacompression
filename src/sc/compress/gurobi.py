'''
Created on Sep 20, 2023

@author: immanueltrummer
'''
'''
Created on Sep 13, 2023

@author: immanueltrummer
'''
import collections
import gurobipy as gp
import logging
import sc.llm
from gurobipy import GRB


class IlpCompression():
    """ Compresses schemata via integer linear programming. """
    
    def __init__(
            self, schema, max_depth=1, llm_name='gpt-3.5-turbo', 
            upper_bound=None, context_k=5, short2text={},
            timeout_s=5*60):
        """ Initializes for given schema. 
        
        Args:
            schema: a schema to compress.
            max_depth: maximal context depth.
            llm_name: name of LLM to use.
            upper_bound: upper bound on cost.
            context_k: consider k most frequent tokens for context.
            short2text: maps candidate shortcuts to text.
            timeout_s: timeout for optimization in seconds.
        """
        self.schema = schema
        self.max_depth = max_depth
        self.llm_name = llm_name
        self.upper_bound = upper_bound
        self.context_k = context_k
        self.short2text = short2text
        self.ids = schema.get_identifiers()
        self.tokens = self.ids + ['(', ')']
        
        logging.debug(f'IDs: {self.ids}')
        logging.debug(f'Tokens: {self.tokens}')
        
        self.true_facts, self.false_facts = schema.get_facts()
        self.facts = self.true_facts + self.false_facts
        self.max_length = round(2*len(self.true_facts))
        
        self.model = gp.Model('Compression')
        self.model.Params.TimeLimit = timeout_s
        self.decision_vars, self.context_vars, self.fact_vars, \
            self.representation_vars, self.shortcut_vars = self._variables()
        
        logging.debug(f'True facts: {self.true_facts}')
        logging.debug(f'False facts: {self.false_facts}')
        
        self._add_constraints()
        self._add_pruning()
        self._add_objective()
        self._add_mips_start()
        print(self.model)

    def compress(self):
        """ Solve compression problem and return solution.
        
        Returns:
            Compressed representation of schema.
        """
        self.model.optimize()
        # Extract solution
        
        # Introduce shortcuts, if any
        parts = []
        for short, short_text in self.short2text.items():
            short_var = self.shortcut_vars[short]
            if short_var.X >= 0.5:
                intro_text = f'{short} substitutes {short_text} '
                parts.append(intro_text)

        # Concatenate selected representations
        for pos in range(self.max_length):
            for token in self.ids:
                for short, rep_var in \
                    self.representation_vars[pos][token].items():
                    if rep_var.X >= 0.5:
                        short_text = self.short2text[short] if short else ''
                        rep_text = token.replace(short_text, short)
                        parts.append(rep_text)
            
            nr_separators = 0
            for token in ['(', ')']:
                if self.decision_vars[pos][token].X >= 0.5:
                    parts += [token]
                    nr_separators += 1
            
            if nr_separators == 0:
                parts += [' ']
        
        joined = ''.join(parts)
        
        # Remove spaces before closing parenthesis and at the end
        polished = joined.replace(' )', ')').rstrip()

        return polished

    def _add_constraints(self):
        """ Adds constraints to internal model. """
        # Introduce auxiliary variables representing emptiness
        is_empties = []
        for pos in range(self.max_length):
            name = f'P{pos}_empty'
            is_empty = self.model.addVar(vtype=GRB.BINARY, name=name)
            is_empties.append(is_empty)
        
        # Cannot have opening and closing parentheses and empty!
        for pos in range(self.max_length):
            opening = self.decision_vars[pos]['(']
            closing = self.decision_vars[pos][')']
            empty = is_empties[pos]
            self.model.addConstr(opening + closing + empty <= 1)

        # Ensure correct value for emptiness variables
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
        
        # Enclose column groups between parentheses
        merged_cols = [c.name for c in self.schema.get_columns() if c.merged]
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1+1
            opening_1 = self.decision_vars[pos_1]['(']
            closing_2 = self.decision_vars[pos_2][')']
            col_vars = [self.decision_vars[pos_2][c] for c in merged_cols]
            self.model.addConstr(opening_1 >= gp.quicksum(col_vars))
            self.model.addConstr(closing_2 >= gp.quicksum(col_vars))
        
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
                name = f'Activate_P{pos}_{token[:200]}'
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
        
        # Link facts to nested tokens
        for fact_key in self.fact_vars.keys():
            token_1 = min(fact_key)
            token_2 = max(fact_key)
            # Sum over possible mentions
            mention_vars = []
            for pos in range(self.max_length):
                mention_var_1 = self._get_mention_var(token_1, token_2, pos)
                mention_var_2 = self._get_mention_var(token_2, token_1, pos)
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
            self.model.addConstr(fact_var == 1)
        
        # Ensure that wrong facts are not mentioned
        for token_1, token_2 in self.false_facts:
            fact_key = frozenset({token_1, token_2})
            fact_var = self.fact_vars[fact_key]
            self.model.addConstr(fact_var == 0)
        
        # Select exactly one representation for selected token
        for pos in range(self.max_length):
            for token in self.ids:
                decision_var = self.decision_vars[pos][token]
                rep_vars = self.representation_vars[pos][token].values()
                self.model.addConstr(gp.quicksum(rep_vars) == decision_var)
                
        # Need to introduce used shortcuts
        for short, short_var in self.shortcut_vars.items():
            for pos in range(self.max_length):
                for token in self.ids:
                    if short in self.representation_vars[pos][token]:
                        rep_var = self.representation_vars[pos][token][short]
                        self.model.addConstr(rep_var <= short_var)

    def _add_mips_start(self):
        """ Add naive solution as starting point. """
        parts = []
        for table in self.schema.tables:
            parts += [table.as_predicate()]
            parts += ['(']
            for column in table.columns:
                if column.merged:
                    for annotation in column.annotations:
                        parts += [annotation]
                        parts += ['(']
                        parts += [column.name]
                        parts += [')']
                else:
                    parts += [column.name]
                    parts += ['(']
                    for annotation in column.annotations:
                        parts += [annotation]
                    parts += [')']
            parts += [')']
        print(f"Naive solution: {' '.join(parts)}")

        for pos in range(self.max_length):
            for token in self.ids:
                self.decision_vars[pos][token].Start = 0
                for depth in range(self.max_depth):
                    self.context_vars[pos][depth][token].Start = 0
        
        tokens_by_pos = []
        last_pos_tokens = []
        for part in parts:
            if part == '(':
                last_pos_tokens.append('(')
            elif part == ')':
                if ')' not in last_pos_tokens:
                    last_pos_tokens.append(')')
                else:
                    tokens_by_pos.append(last_pos_tokens)
                    last_pos_tokens = [part]
            else:
                tokens_by_pos.append(last_pos_tokens)
                last_pos_tokens = [part]
        tokens_by_pos.append(last_pos_tokens)
        tokens_by_pos = tokens_by_pos[1:]
        
        for pos, tokens in enumerate(tokens_by_pos):
            for token in tokens:
                self.decision_vars[pos][token].Start = 1
        
        contexts = [[]]
        for tokens in tokens_by_pos:
            last_context = contexts[-1]
            new_context = last_context.copy()
            if '(' in tokens:
                new_context += [tokens[0]]
            elif ')' in tokens:
                new_context.pop()
            contexts += [new_context]
        print(contexts)
        
        for pos, context in enumerate(contexts):
            for depth, token in enumerate(context):
                self.context_vars[pos][depth][token].Start = 1
        #
        # next_pos = 0
        # context = []
        # prior_part = None
        # for part in parts:
            # self.decision_vars[next_pos][part].Start = 1
            # if part not in ['(', ')']:
                # next_pos += 1
                #
            # if part == '(':
                # context.append(prior_part)
            # elif part == ')':
                # context.pop()
                #
            # for depth, token in enumerate(context):
                # self.context_vars[next_pos][depth][token].Start = 1
                #
            # prior_part = part

    def _add_objective(self):
        """ Add optimization objective. """
        terms = []
        
        # Sum up representation length over all selections
        for pos in range(self.max_length):
            # Sum up over ID tokens
            for token in self.ids:
                for short, rep_var in \
                    self.representation_vars[pos][token].items():
                    if not short:
                        short_text = ''
                    else:
                        short_text = self.short2text[short]
                    shortened = token.replace(short_text, short)
                    weight = sc.llm.nr_tokens(self.llm_name, shortened)
                    terms.append(weight * rep_var)
            
            # Sum over auxiliary tokens
            for token in ['(', ')']:
                terms.append(1 * self.decision_vars[pos][token])
        
        # Count space for introducing shortcuts
        for short, short_text in self.short2text.items():
            short_var = self.shortcut_vars[short]
            intro_text = f'{short} substitutes {short_text} '
            weight = sc.llm.nr_tokens(self.llm_name, intro_text)
            terms.append(weight * short_var)
        
        # Optimization goal is to minimize sum of terms
        self.model.setObjective(gp.quicksum(terms), GRB.MINIMIZE)
        
        # Set upper cost bound if available
        if self.upper_bound is not None:
            self.model.addConstr(gp.quicksum(terms) <= self.upper_bound)
    
    def _add_pruning(self):
        """ Add constraints to restrict search space size. """
        logging.info('Pruning search space ...')
        counter = collections.Counter()
        for id_1, id_2 in self.true_facts:
            counter.update([id_1, id_2])
        
        common_counts = counter.most_common(self.context_k)
        common_ids = set([ic[0] for ic in common_counts])
        logging.info(f'Restricting inner context to {common_ids}')
        
        # Heuristically prune context with depth > 1
        for depth in range(1, self.max_depth):
            for token in self.ids:
                if token not in common_ids:
                    for pos in range(self.max_length):
                        context_var = self.context_vars[pos][depth][token]
                        self.model.addConstr(context_var == 0)
        
        # Avoid nesting mutually exclusive facts
        for pos in range(self.max_length):
            table_vars = []
            for depth in range(self.max_depth):
                for table in self.schema.tables:
                    pred = table.as_predicate()
                    table_var = self.context_vars[pos][depth][pred]
                    table_vars.append(table_var)
            self.model.addConstr(gp.quicksum(table_vars) <= 1)
            
            col_vars = []
            for col in self.schema.get_column_names():
                for depth in range(self.max_depth):
                    col_var = self.context_vars[pos][depth][col]
                    col_vars.append(col_var)
            self.model.addConstr(gp.quicksum(col_vars) <= 1)        
        
        # Start with description of table columns
        first_table_pred = self.schema.tables[0].as_predicate()
        self.model.addConstr(self.decision_vars[0][first_table_pred] == 1)
        self.model.addConstr(self.decision_vars[0]['('] == 1)
    
    def _get_mention_var(self, outer_token, inner_token, pos):
        """ Generate variable representing fact mention.
        
        Args:
            outer_token: token that appears in context.
            inner_token: token that appears within context.
            pos: position at which mention occurs.
        """
        outer_vars = [self.context_vars[pos][d][outer_token] 
                      for d in range(self.max_depth)]
        inner_var = self.decision_vars[pos][inner_token]
        name = f'Mention_P{pos}_{outer_token[:100]}_{inner_token[:100]}'
        mention_var = self.model.addVar(vtype=GRB.BINARY, name=name)
        self.model.addConstr(mention_var <= gp.quicksum(outer_vars))
        self.model.addConstr(mention_var <= inner_var)
        self.model.addConstr(
            mention_var >= -1 + gp.quicksum(outer_vars) + inner_var)
        return mention_var
    
    def _variables(self):
        """ Returns variables for input schema. 
        
        Returns:
            decisions, context, facts, representation, shortcuts.
        """
        # Access by decision_vars[position][token]
        decision_vars = []
        for pos in range(self.max_length):
            cur_pos_vars = {}
            for token in self.tokens:
                name = f'P{pos}_{token[:200]}'
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
                    name = f'P{pos}_D{depth}_{context_id[:200]}'
                    context_var = self.model.addVar(
                        vtype=GRB.BINARY, name=name)
                    cur_depth_vars[context_id] = context_var
        
        # Access by fact_vars[frozenset([id_1, id_2])]
        fact_keys = set([frozenset([id_1, id_2]) for id_1, id_2 in self.facts])
        fact_vars = {}
        for fact_key in fact_keys:
            id_1 = min(fact_key)
            id_2 = max(fact_key)
            fact_name = f'{id_1[:100]}_{id_2[:100]}'
            fact_var = self.model.addVar(
                vtype=GRB.BINARY, name=fact_name)
            ids = frozenset({id_1, id_2})
            fact_vars[ids] = fact_var
        
        # Access by representation_vars[pos][token][short]
        representation_vars = []
        for pos in range(self.max_length):
            cur_pos_vars = {}
            for token in self.ids:
                cur_token_vars = {}
                
                name = f'Rep_P{pos}_{token[:200]}'
                empty_short_var = self.model.addVar(
                    vtype=GRB.BINARY, name=name)
                cur_token_vars[''] = empty_short_var
                
                for short, text in self.short2text.items():
                    if text in token:
                        name = f'Rep_P{pos}_{token[:200]}_{short}'
                        short_var = self.model.addVar(
                            vtype=GRB.BINARY, name=name)
                        cur_token_vars[short] = short_var
                cur_pos_vars[token] = cur_token_vars
            representation_vars.append(cur_pos_vars)
        
        # Access by shortcuts[short]
        shortcut_vars = {}
        for short in self.short2text.keys():
            name = f'Shortcut_{short}'
            shortcut_var = self.model.addVar(vtype=GRB.BINARY, name=name)
            shortcut_vars[short] = shortcut_var
        
        logging.debug(f'Fact variable keys: {fact_vars.keys()}')
        return decision_vars, context_vars, \
            fact_vars, representation_vars, shortcut_vars
        

if __name__ == '__main__':
    
    import sc.schema
    logging.basicConfig(level=logging.DEBUG)
    column = sc.schema.Column('testcolumn', 'testtype', [], False)
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