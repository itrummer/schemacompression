'''
Created on Jan 25, 2024

@author: immanueltrummer
'''
import argparse
import pathlib
import sqlite3


def extract_schema(db_file):
    """ Extract schema from SQLite database.
    
    Args:
        db_file: SQLite database file.
    
    Returns:
        DDL commands as string.
    """
    with sqlite3.connect(db_file) as connection:
        cursor = connection.cursor()
        result = cursor.execute("select sql from sqlite_master where type = 'table'")
        ddl_statements = [r[0] for r in result]
        ddl = ';\n'.join(ddl_statements)
        return ddl


def write_schema(ddl, out_dir, db_name):
    """ Write DDL commands into .sql file.
    
    Args:
        ddl: commands for creating schema.
        out_dir: output directory.
        db_name: name of database.
    """
    out_name = f'{db_name}.sql'
    out_path = pathlib.Path(out_dir).joinpath(out_name)
    print(out_path)
    with open(out_path, 'w') as file:
        file.write(ddl)


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('datadir', type=str, help='Data directory')
    parser.add_argument('outdir', type=str, help='Output directory')
    args = parser.parse_args()
    
    root_dir = pathlib.Path(args.datadir)
    for sub_dir in root_dir.iterdir():
        if sub_dir.is_dir():
            for db_file in sub_dir.glob('*.sqlite'):
                db_name = db_file.name[:-7]
                ddl = extract_schema(db_file)
                write_schema(ddl, args.outdir, db_name)