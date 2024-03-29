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
import sc.compress.greedy
import sc.llm
from dataclasses import dataclass
from gurobipy import GRB
from typing import Any, Dict, List


@dataclass
class CompressionVars():
    """ Variables used for compression problem. """
    decision_vars: List[Any]
    """ decision_vars[pos][token]==1 iff token selected at position pos. """
    context_vars: List[Any]
    """ context_vars[pos][depth][token]==1 iff token activated. """
    fact_vars: Dict[Any, Any]
    """ fact_vars[fact_key]==1 iff the corresponding fact is mentioned. """
    representation_vars: List[Any]
    """ representation_vars[pos][token][short]==1 iff shortcut used. """
    shortcut_vars: Dict[Any, Any]
    """ shortcut_vars[short]==1 if corresponding shortcut is used. """


class IlpCompression():
    """ Compresses schemata via integer linear programming. """
    
    def __init__(
            self, schema, start, hints, merge, 
            max_depth=1, llm_name='gpt-3.5-turbo', 
            upper_bound=None, context_k=5, timeout_s=5*60):
        """ Initializes for given schema. 
        
        Args:
            schema: a schema to compress.
            start: whether to use greedy MIPS start.
            hints: whether to use value hints for variables.
            merge: whether to merge columns with same annotations.
            max_depth: maximal context depth.
            llm_name: name of LLM to use.
            upper_bound: upper bound on cost.
            context_k: consider k most frequent tokens for context.
            timeout_s: timeout for optimization in seconds.
        """
        self.schema = schema
        self.max_depth = max_depth
        self.llm_name = llm_name
        self.upper_bound = upper_bound
        self.context_k = context_k
        # Important: generate candidates before merging columns!
        self.short2text = self._shortcut_candidates(schema, llm_name)
        if merge:
            self.schema.merge_columns()
        self.ids = schema.get_identifiers()
        self.tokens = self.ids + ['(', ')']
        self.timeout_s = timeout_s
        self.start = start
        self.hints = hints
        self.merge = merge
        logging.debug(f'IDs: {self.ids}')
        logging.debug(f'Tokens: {self.tokens}')
        
        self.true_facts, self.false_facts = schema.get_facts()
        self.facts = self.true_facts + self.false_facts
        self.naive_solution = self._naive_solution()
        self.max_length = len(self.naive_solution)
        logging.debug(f'True facts: {self.true_facts}')
        logging.debug(f'False facts: {self.false_facts}')

    def compress(self):
        """ Solve compression problem and return solution.
        
        Returns:
            Compressed representation of schema.
        """
        with gp.Env() as env:
            with gp.Model(env=env) as model:
                model.Params.TimeLimit = self.timeout_s
                all_vars = self._variables(model)
                self._add_constraints(model, all_vars)
                self._add_pruning(model, all_vars)
                self._add_objective(model, all_vars)
                if self.hints:
                    self._add_hints(all_vars)
                if self.start:
                    self._add_mips_start(self.naive_solution, all_vars)
                model.optimize()
                
                if model.SolCount > 0:
                    solution = self._extract_solution(all_vars)
                    solved = True
                else:
                    solution = ''
                    solved = False
                nr_variables = model.NumVars
                nr_constraints = model.NumConstrs
                mip_gap = model.MIPGap
                result = {
                    'solution':solution, 'nr_variables':nr_variables, 
                    'nr_constraints':nr_constraints, 'mip_gap':mip_gap,
                    'max_length':self.max_length, 'max_depth':self.max_depth,
                    'timeout_s':self.timeout_s, 'context_k':self.context_k,
                    'start':self.start, 'hints':self.hints, 'merge':self.merge,
                    'solved':solved}
                return result

    def _add_constraints(self, model, cvars):
        """ Adds constraints to internal model.
        
        Args:
            model: add constraints to this model.
            cvars: contains all groups of variables.
        """
        # Introduce auxiliary variables representing emptiness
        is_empties = []
        for pos in range(self.max_length):
            name = f'P{pos}_empty'
            is_empty = model.addVar(vtype=GRB.BINARY, name=name)
            is_empties.append(is_empty)
        
        # Cannot have opening and closing parentheses and empty!
        for pos in range(self.max_length):
            opening = cvars.decision_vars[pos]['(']
            closing = cvars.decision_vars[pos][')']
            empty = is_empties[pos]
            name = f'P{pos}_OpeningClosingEmpty'
            model.addConstr(opening + closing + empty <= 1, name=name)

        # Ensure correct value for emptiness variables
        for pos in range(self.max_length):
            is_empty = is_empties[pos]
            token_vars = [cvars.decision_vars[pos][t] for t in self.tokens]
            token_sum = gp.quicksum(token_vars)
            name = f'P{pos}_EmptynessGe'
            model.addConstr(is_empty >= 1 - token_sum, name=name)
            for token_var in token_vars:
                name = f'P{pos}_EmptynessLe'
                model.addConstr(is_empty <= 1 - token_var, name=name)
        
        # Can only have empty slots at the end of description
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            empty_1 = is_empties[pos_1]
            empty_2 = is_empties[pos_2]
            name = f'P{pos_1}_EndEmpty'
            model.addConstr(empty_1 <= empty_2, name=name)
            
        # Select at most one ID token per position
        for pos in range(self.max_length):
            token_vars = [cvars.decision_vars[pos][token] for token in self.ids]
            name = f'P{pos}_AtMostOneID'
            model.addConstr(gp.quicksum(token_vars) <= 1, name=name)
        
        # Must connect opening parenthesis with token
        for pos in range(self.max_length):
            opening = cvars.decision_vars[pos]['(']
            token_vars = [cvars.decision_vars[pos][token] for token in self.ids]
            name = f'P{pos}_OpenWithToken'
            model.addConstr(opening <= gp.quicksum(token_vars), name=name)
            
        # Balance opening and closing parentheses
        opening = [decisions['('] for decisions in cvars.decision_vars]
        closing = [decisions[')'] for decisions in cvars.decision_vars]
        opening_sum = gp.quicksum(opening)
        closing_sum = gp.quicksum(closing)
        name = f'BalanceOpeningAndClosingParentheses'
        model.addConstr(opening_sum == closing_sum, name=name)
        
        # Never more closing than opening parenthesis!
        for pos in range(self.max_length):
            opening = [ds['('] for ds in cvars.decision_vars[:pos+1]]
            closing = [ds[')'] for ds in cvars.decision_vars[:pos+1]]
            opening_sum = gp.quicksum(opening)
            closing_sum = gp.quicksum(closing)
            name = f'P{pos}_NoMoreClosingThanOpeningParentheses'
            model.addConstr(opening_sum >= closing_sum, name=name)
        
        # Enclose column groups between parentheses
        # merged_cols = [c.name for c in self.schema.get_columns() if c.merged]
        # for pos_1 in range(self.max_length-1):
            # pos_2 = pos_1+1
            # opening_1 = cvars.decision_vars[pos_1]['(']
            # closing_2 = cvars.decision_vars[pos_2][')']
            # col_vars = [cvars.decision_vars[pos_2][c] for c in merged_cols]
            # name = f'P{pos_1}_NeedOpeningBeforeColumnGroup'
            # model.addConstr(opening_1 >= gp.quicksum(col_vars), name=name)
            # name = f'P{pos_1}_NeedClosingAfterColumnGroup'
            # model.addConstr(closing_2 >= gp.quicksum(col_vars), name=name)
        
        # Do not select tokens already in context (required for correctness!)
        # Otherwise: selects any token in context after re-activating token.
        for pos in range(self.max_length):
            for token in self.ids:
                context_vars = []
                for depth in range(self.max_depth):
                    context_var = cvars.context_vars[pos][depth][token]
                    context_vars.append(context_var)
                ctx_sum = gp.quicksum(context_vars)
                decision_var = cvars.decision_vars[pos][token]
                name = f'P{pos}_{token[:200]}_NoContextOverlap'
                model.addConstr(ctx_sum + decision_var <= 1, name=name)
            
        # Each context layer fixes at most one token
        for pos in range(self.max_length):
            for depth in range(self.max_depth):
                name = f'P{pos}_D{depth}_OneTokenPerContextLayer'
                cur_context_vars = cvars.context_vars[pos][depth].values()
                context_sum = gp.quicksum(cur_context_vars)
                model.addConstr(context_sum <= 1, name=name)
                    
        # Context layers are used consecutively
        for pos in range(self.max_length):
            for depth_1 in range(self.max_depth-1):
                depth_2 = depth_1 + 1
                sum_1 = gp.quicksum(cvars.context_vars[pos][depth_1].values())
                sum_2 = gp.quicksum(cvars.context_vars[pos][depth_2].values())
                name = f'P{pos}_D{depth_1}_ConsecutiveContext'
                model.addConstr(sum_1 >= sum_2, name=name)
        
        # Collect all context variables per position
        context_by_pos = []
        for pos in range(self.max_length):
            pos_vars = []
            for depth in range(self.max_depth):
                pos_vars += list(cvars.context_vars[pos][depth].values())
            context_by_pos.append(pos_vars)
        
        # Initial context is empty
        name = f'NoInitialContext'
        model.addConstr(gp.quicksum(context_by_pos[0]) == 0, name=name)
        
        # Ensure correct number of context tokens
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            sum_1 = gp.quicksum(context_by_pos[pos_1])
            sum_2 = gp.quicksum(context_by_pos[pos_2])
            opening = cvars.decision_vars[pos_1]['(']
            closing = cvars.decision_vars[pos_1][')']
            name = f'P{pos_1}_NrContextTokens'
            model.addConstr(sum_1 + opening - closing == sum_2, name=name)
        
        # Create activation variables
        activations = []
        for pos in range(self.max_length):
            opening = cvars.decision_vars[pos]['(']
            cur_activations = {}
            for token in self.ids:
                token_var = cvars.decision_vars[pos][token]
                name = f'Activate_P{pos}_{token[:200]}'
                activation = model.addVar(vtype=GRB.BINARY, name=name)
                name = f'P{pos}_{token[:200]}_ActivationRequiresOpening'
                model.addConstr(activation <= opening, name=name)
                name = f'P{pos}_{token[:200]}_ActivationRequiresToken'
                model.addConstr(activation <= token_var, name=name)
                name = f'P{pos}_{token[:200]}_MustActivateIfOpeningAndToken'
                activation_lb = opening + token_var - 1
                model.addConstr(activation >= activation_lb, name=name)
                cur_activations[token] = activation
            activations.append(cur_activations)
        
        # Set context variables as function of activation
        for pos_1 in range(self.max_length-1):
            pos_2 = pos_1 + 1
            for token in self.ids:
                activation_var = activations[pos_1][token]
                token_vars = [
                    cvars.context_vars[pos_2][d][token]
                    for d in range(self.max_depth)]
                name = f'P{pos_1}_{token[:200]}_SetContextAfterActivation'
                token_sum = gp.quicksum(token_vars)
                model.addConstr(token_sum >= activation_var, name=name)
        
        # Restrict context changes, compared to prior context
        for pos_1 in range(self.max_length-1):
            opening = cvars.decision_vars[pos_1]['(']
            closing = cvars.decision_vars[pos_1][')']
            pos_2 = pos_1 + 1
            for depth in range(self.max_depth):
                for token in self.ids:
                    var_1 = cvars.context_vars[pos_1][depth][token]
                    var_2 = cvars.context_vars[pos_2][depth][token]
                    name = f'P{pos_1}_D{depth}_CannotDropContextWithoutClosing'
                    model.addConstr(var_2 >= var_1 - closing, name=name)
                    name = f'P{pos_1}_D{depth}_CannotAddContextWithoutOpening'
                    model.addConstr(var_2 <= var_1 + opening, name=name)
        
        # Link facts to nested tokens
        for fact_key in cvars.fact_vars.keys():
            token_1 = min(fact_key)
            token_2 = max(fact_key)
            # Sum over possible mentions
            mention_vars = []
            for pos in range(self.max_length):
                mention_var_1 = self._get_mention_var(
                    model, cvars, token_1, token_2, pos)
                mention_var_2 = self._get_mention_var(
                    model, cvars, token_2, token_1, pos)
                mention_vars += [mention_var_1, mention_var_2]
                    
            fact_key = frozenset({token_1, token_2})
            fact_var = cvars.fact_vars[fact_key]
            mention_sum = gp.quicksum(mention_vars)
            name = f'F{token_1[:100]}_{token_2[:100]}_NoFactUntilMentioned'
            model.addConstr(fact_var <= mention_sum, name=name)
            for var_idx, mention_var in enumerate(mention_vars):
                name = f'F{token_1[:100]}_{token_2[:100]}_{var_idx}_MentionImpliesFact'
                model.addConstr(fact_var >= mention_var, name=name)
        
        # Make sure that true facts are mentioned
        for token_1, token_2 in self.true_facts:
            fact_key = frozenset({token_1, token_2})
            fact_var = cvars.fact_vars[fact_key]
            name = f'DefinitelyMention_{token_1[:100]}_{token_2[:100]}'
            model.addConstr(fact_var == 1, name=name)
        
        # Ensure that wrong facts are not mentioned
        for token_1, token_2 in self.false_facts:
            fact_key = frozenset({token_1, token_2})
            fact_var = cvars.fact_vars[fact_key]
            name = f'NeverMention_{token_1[:100]}_{token_2[:100]}'
            model.addConstr(fact_var == 0, name=name)
        
        # Select exactly one representation for selected token
        for pos in range(self.max_length):
            for token in self.ids:
                decision_var = cvars.decision_vars[pos][token]
                rep_vars = cvars.representation_vars[pos][token].values()
                rep_sum = gp.quicksum(rep_vars)
                name = f'P{pos}_{token[:200]}_OneRepresentationForSelected'
                model.addConstr(rep_sum == decision_var, name=name)
                
        # Need to introduce used shortcuts
        for short, short_var in cvars.shortcut_vars.items():
            for pos in range(self.max_length):
                for token in self.ids:
                    if short in cvars.representation_vars[pos][token]:
                        rep_var = cvars.representation_vars[pos][token][short]
                        name = f'P{pos}_{token[:200]}_{short}_NeedShortcutForRep'
                        model.addConstr(rep_var <= short_var, name=name)

    def _add_hints(self, cvars):
        """ Add hints about variable values.
        
        Args:
            cvars: all decision variables for compression.
        """
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
                        context_var = cvars.context_vars[pos][depth][token]
                        context_var.VarHintVal = 0

    def _add_mips_start(self, solution, cvars):
        """ Add naive solution as starting point (assumes no shortcuts).
        
        Args:
            solution: list with one entry per position (token list).
            cvars: all decision variables for compression.
        """
        # Set all variables to zero by default
        for pos in range(self.max_length):
            for token in self.ids:
                cvars.decision_vars[pos][token].Start = 0
                # for rep_var in cvars.representation_vars[pos][token].values():
                    # rep_var.Start = 0
                for depth in range(self.max_depth):
                    cvars.context_vars[pos][depth][token].Start = 0
        
        # Select tokens that appear in solution
        for pos, tokens in enumerate(solution):
            for token in tokens:
                cvars.decision_vars[pos][token].Start = 1
                # Assumption: given solution does not use shortcuts
                # if token not in ['(', ')']:
                    # cvars.representation_vars[pos][token][''].Start = 1
        
        # Create sequence of contexts
        contexts = [[]]
        for tokens in solution:
            last_context = contexts[-1]
            new_context = last_context.copy()
            if '(' in tokens:
                new_context += [tokens[0]]
            elif ')' in tokens:
                new_context.pop()
            contexts += [new_context]
        
        # Set context tokens that appear in solution
        for pos, context in enumerate(contexts):
            for depth, token in enumerate(context):
                cvars.context_vars[pos][depth][token].Start = 1

    def _add_objective(self, model, cvars):
        """ Add optimization objective.
        
        Args:
            model: add optimization objective to this model.
            cvars: all decision variables for compression.
        """
        terms = []
        
        # Sum up representation length over all selections
        for pos in range(self.max_length):
            # Sum up over ID tokens
            for token in self.ids:
                for short, rep_var in \
                    cvars.representation_vars[pos][token].items():
                    if not short:
                        short_text = ''
                    else:
                        short_text = self.short2text[short]
                    shortened = token.replace(short_text, short)
                    weight = sc.llm.nr_tokens(self.llm_name, shortened)
                    terms.append(weight * rep_var)
            
            # Sum over auxiliary tokens
            for token in ['(', ')']:
                terms.append(1 * cvars.decision_vars[pos][token])
        
        # Count space for introducing shortcuts
        for short, short_text in self.short2text.items():
            short_var = cvars.shortcut_vars[short]
            intro_text = f'{short} means {short_text} '
            weight = sc.llm.nr_tokens(self.llm_name, intro_text)
            terms.append(weight * short_var)
        
        # Optimization goal is to minimize sum of terms
        model.setObjective(gp.quicksum(terms), GRB.MINIMIZE)
        
        # Set upper cost bound if available
        if self.upper_bound is not None:
            cost = gp.quicksum(terms)
            name = 'UpperBoundOnCost'
            model.addConstr(cost <= self.upper_bound, name=name)
    
    def _add_pruning(self, model, cvars):
        """ Add constraints to restrict search space size.
        
        Args:
            model: add constraints for pruning to this model.
            cvars: all decision variables for schema compression.
        """
        logging.info('Pruning search space ...')
        
        # Avoid nesting mutually exclusive facts
        for pos in range(self.max_length):
            table_vars = []
            for depth in range(self.max_depth):
                for table in self.schema.tables:
                    pred = table.as_predicate()
                    table_var = cvars.context_vars[pos][depth][pred]
                    table_vars.append(table_var)
            name = f'P{pos}_AtMostOneTableInContext'
            model.addConstr(gp.quicksum(table_vars) <= 1, name=name)
            
            col_vars = []
            for col in self.schema.get_column_names():
                for depth in range(self.max_depth):
                    col_var = cvars.context_vars[pos][depth][col]
                    col_vars.append(col_var)
            name = f'P{pos}_AtMostOneColumnInContext'
            model.addConstr(gp.quicksum(col_vars) <= 1, name=name)
        
        # Start with description of table columns
        first_table_pred = self.schema.tables[0].as_predicate()
        first_table_var = cvars.decision_vars[0][first_table_pred]
        name = 'StartWithTablePredicate'
        model.addConstr(first_table_var == 1, name=name)
        name = 'StartWithOpeningParenthesis'
        first_opening_var = cvars.decision_vars[0]['(']
        model.addConstr(first_opening_var == 1, name=name)
    
    def _extract_solution(self, cvars):
        """ Extract compressed schema from model solution.
        
        Args:
            cvars: all decision variables for compression.
        
        Returns:
            compressed schema as string.
        """
        # Introduce shortcuts, if any
        parts = []
        for short, short_text in self.short2text.items():
            short_var = cvars.shortcut_vars[short]
            if short_var.X >= 0.5:
                intro_text = f'{short} substitutes {short_text} '
                parts.append(intro_text)

        # Concatenate selected representations
        for pos in range(self.max_length):
            for token in self.ids:
                for short, rep_var in \
                    cvars.representation_vars[pos][token].items():
                    if rep_var.X >= 0.5:
                        short_text = self.short2text[short] if short else ''
                        rep_text = token.replace(short_text, short)
                        parts.append(rep_text)
            
            nr_separators = 0
            for token in ['(', ')']:
                if cvars.decision_vars[pos][token].X >= 0.5:
                    parts += [token]
                    nr_separators += 1
            
            if nr_separators == 0:
                parts += [' ']
        
        joined = ''.join(parts)
        
        # Remove spaces before closing parenthesis and at the end
        polished = joined.replace(' )', ')').rstrip()
        return polished
    
    def _get_mention_var(self, model, cvars, outer_token, inner_token, pos):
        """ Generate variable representing fact mention.
        
        Args:
            model: add mention variable to this Gurobi model.
            cvars: all decision variables for compression.
            outer_token: token that appears in context.
            inner_token: token that appears within context.
            pos: position at which mention occurs.
        """
        outer_vars = [cvars.context_vars[pos][d][outer_token] 
                      for d in range(self.max_depth)]
        inner_var = cvars.decision_vars[pos][inner_token]
        outer_short = outer_token[:100]
        inner_short = inner_token[:100]
        name = f'Mention_P{pos}_{outer_short}_{inner_short}'
        mention_var = model.addVar(vtype=GRB.BINARY, name=name)
        name = f'P{pos}_{outer_short}_{inner_short}_MentionRequiresOuter'
        model.addConstr(mention_var <= gp.quicksum(outer_vars), name=name)
        name = f'P{pos}_{outer_short}_{inner_short}_MentionRequiresInner'
        model.addConstr(mention_var <= inner_var, name=name)
        name = f'P{pos}_{outer_short}_{inner_short}_OuterAndInnerImplesMention'
        lb_mention_var = -1 + gp.quicksum(outer_vars) + inner_var
        model.addConstr(mention_var >= lb_mention_var, name=name)
        return mention_var
    
    def _naive_solution(self):
        """ Generate a naive solution.
        
        Returns:
            List of activated tokens per position.
        """
        parts = sc.compress.greedy.greedy_parts(self.schema, full_names=True)
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
        return tokens_by_pos
    
    def _shortcut_candidates(self, schema, model):
        """ Generate candidates for shortcuts.
        
        Args:
            schema: generate shortcuts for this schema.
            model: count tokens for this model.
        
        Returns:
            dictionary mapping candidate shortcuts to their text.
        """
        prefixes = schema.prefixes(model)
        placeholders = ['PA', 'PB', 'PC', 'PD', 'PE', 'PF', 'PG', 'PH', 'PI']
        nr_placeholders = len(placeholders)
        nr_prefixes = len(prefixes)
        nr_shortcuts = min(nr_placeholders, nr_prefixes)
        prefixes = prefixes[:nr_shortcuts]
        return {placeholders[i]:prefixes[i] for i in range(nr_shortcuts)}

    def _variables(self, model):
        """ Returns variables for input schema. 
        
        Args:
            model: add variables to this model.
        
        Returns:
            Object containing all groups of variables.
        """
        # Access by decision_vars[position][token]
        decision_vars = []
        for pos in range(self.max_length):
            cur_pos_vars = {}
            for token in self.tokens:
                name = f'P{pos}_{token[:200]}'
                decision_var = model.addVar(vtype=GRB.BINARY, name=name)
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
                    context_var = model.addVar(
                        vtype=GRB.BINARY, name=name)
                    cur_depth_vars[context_id] = context_var
        
        # Access by fact_vars[frozenset([id_1, id_2])]
        fact_keys = set([frozenset([id_1, id_2]) for id_1, id_2 in self.facts])
        fact_vars = {}
        for fact_key in fact_keys:
            id_1 = min(fact_key)
            id_2 = max(fact_key)
            fact_name = f'{id_1[:100]}_{id_2[:100]}'
            fact_var = model.addVar(
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
                empty_short_var = model.addVar(
                    vtype=GRB.BINARY, name=name)
                cur_token_vars[''] = empty_short_var
                
                for short, text in self.short2text.items():
                    if text in token:
                        name = f'Rep_P{pos}_{token[:200]}_{short}'
                        short_var = model.addVar(
                            vtype=GRB.BINARY, name=name)
                        cur_token_vars[short] = short_var
                cur_pos_vars[token] = cur_token_vars
            representation_vars.append(cur_pos_vars)
        
        # Access by shortcuts[short]
        shortcut_vars = {}
        for short in self.short2text.keys():
            name = f'Shortcut_{short}'
            shortcut_var = model.addVar(vtype=GRB.BINARY, name=name)
            shortcut_vars[short] = shortcut_var
        
        logging.debug(f'Fact variable keys: {fact_vars.keys()}')
        return CompressionVars(
            decision_vars, context_vars, fact_vars, 
            representation_vars, shortcut_vars)
        

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