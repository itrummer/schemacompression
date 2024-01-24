'''
Created on Sep 21, 2023

@author: immanueltrummer
'''
import sc.schema
import sqlglot.parser
import sqlglot.tokens


class SchemaParser():
    """ Parses schema definitions in SQL. """
    
    def __init__(self):
        """ Initialize tokenizer and internal parser. """
        self.tokenizer = sqlglot.tokens.Tokenizer()
        self.parser = sqlglot.parser.Parser()
    
    def parse(self, ddl):
        """ Generates schema description from SQL.
        
        Args:
            ddl: SQL commands defining schema (as text).
        
        Returns:
            schema representation for optimizer.
        """
        tokens = self.tokenizer.tokenize(ddl)
        ast = self.parser.parse(tokens)
        tables = [self._handle(n) for n in ast]
        return sc.schema.Schema(tables, [], [])
    
    def format(self, ddl):
        """ Returns schema with pretty formatting.
        
        Args:
            ddl: SQL commands defining schema (as text).
        
        Returns:
            re-formatted schema as text.
        """
        return sqlglot.transpile(ddl, pretty=True)[0]
        # tokens = self.tokenizer.tokenize(ddl)
        # ast = self.parser.parse(tokens)
        # return str(ast)
    
    def _columndef(self, node):
        """ Process column definition.
        
        Args:
            node: SQL node representing column definition.
        
        Returns:
            column definition for compression.
        """
        col_name = self._handle(node.args['this'])
        col_type = str(node.args['kind'])
        annotations = [str(c) for c in node.args['constraints']]
        annotations.append(col_type)
        return sc.schema.Column(col_name, col_type, annotations, False)
    
    def _create(self, node):
        """ Handles a create statement.
        
        Args:
            node: represents a create statement.
        """
        return self._handle(node.args['this'])
    
    def _handle(self, node):
        """ Dispatches node to specialized handler. 
        
        Args:
            node: handle this node.
        
        Returns:
            result of specialized handling.
        """
        handler = f'_{node.key.lower()}'
        return getattr(self, handler)(node)
    
    def _identifier(self, node):
        """ Extracts an identifier.
        
        Args:
            node: represents an identifier.
        
        Returns:
            extracted identifier.
        """
        return node.args['this']
    
    def _schema(self, node):
        """ Handles a schema statement within create.
        
        Args:
            node: handles a schema node.
        
        Returns:
            result of processing schema content.
        """
        tbl_name = self._handle(node.args['this'])
        columns = []
        for col_node in node.args['expressions']:
            col_def = self._handle(col_node)
            columns.append(col_def)
        return sc.schema.Table(tbl_name, columns)
    
    def _table(self, node):
        """ Handles table definition.
        
        Args:
            node: definition of table.
        
        Returns:
            table object.
        """
        return self._handle(node.args['this'])


if __name__ == '__main__':
    
    ddl = """
CREATE TABLE nation
(
    n_nationkey  INTEGER not null,
    n_name       CHAR(25) not null,
    n_regionkey  INTEGER not null,
    n_comment    VARCHAR(152)
);

CREATE TABLE region
(
    r_regionkey  INTEGER not null,
    r_name       CHAR(25) not null,
    r_comment    VARCHAR(152)
);

CREATE TABLE part
(
    p_partkey     BIGINT not null,
    p_name        VARCHAR(55) not null,
    p_mfgr        CHAR(25) not null,
    p_brand       CHAR(10) not null,
    p_type        VARCHAR(25) not null,
    p_size        INTEGER not null,
    p_container   CHAR(10) not null,
    p_retailprice DOUBLE PRECISION not null,
    p_comment     VARCHAR(23) not null
);

CREATE TABLE supplier
(
    s_suppkey     BIGINT not null,
    s_name        CHAR(25) not null,
    s_address     VARCHAR(40) not null,
    s_nationkey   INTEGER not null,
    s_phone       CHAR(15) not null,
    s_acctbal     DOUBLE PRECISION not null,
    s_comment     VARCHAR(101) not null
);

CREATE TABLE partsupp
(
    ps_partkey     BIGINT not null,
    ps_suppkey     BIGINT not null,
    ps_availqty    BIGINT not null,
    ps_supplycost  DOUBLE PRECISION  not null,
    ps_comment     VARCHAR(199) not null
);

CREATE TABLE customer
(
    c_custkey     BIGINT not null,
    c_name        VARCHAR(25) not null,
    c_address     VARCHAR(40) not null,
    c_nationkey   INTEGER not null,
    c_phone       CHAR(15) not null,
    c_acctbal     DOUBLE PRECISION   not null,
    c_mktsegment  CHAR(10) not null,
    c_comment     VARCHAR(117) not null
);

CREATE TABLE orders
(
    o_orderkey       BIGINT not null,
    o_custkey        BIGINT not null,
    o_orderstatus    CHAR(1) not null,
    o_totalprice     DOUBLE PRECISION not null,
    o_orderdate      DATE not null,
    o_orderpriority  CHAR(15) not null,  
    o_clerk          CHAR(15) not null, 
    o_shippriority   INTEGER not null,
    o_comment        VARCHAR(79) not null
);

CREATE TABLE lineitem
(
    l_orderkey    BIGINT not null,
    l_partkey     BIGINT not null,
    l_suppkey     BIGINT not null,
    l_linenumber  BIGINT not null,
    l_quantity    DOUBLE PRECISION not null,
    l_extendedprice  DOUBLE PRECISION not null,
    l_discount    DOUBLE PRECISION not null,
    l_tax         DOUBLE PRECISION not null,
    l_returnflag  CHAR(1) not null,
    l_linestatus  CHAR(1) not null,
    l_shipdate    DATE not null,
    l_commitdate  DATE not null,
    l_receiptdate DATE not null,
    l_shipinstruct CHAR(25) not null,
    l_shipmode     CHAR(10) not null,
    l_comment      VARCHAR(44) not null
);
    """
    parser = SchemaParser()
    sql = parser.format(ddl)
    print(sql)