import uuid
from sqlalchemy import inspect, text


class SQLDataOps:
    '''
    SQLDataOps is a class that provides methods for performing SQL operations, specifically 
    for executing upsert (merge) operations across various SQL dialects including MSSQL, 
    Oracle, MySQL, and PostgreSQL.

    Attributes:
        connection_string (str): The connection string used to connect to the database.

    Methods:
        __init__(connection_string: str):
            Initializes the SQLDataOps instance with the provided connection string.

        _quote_identifier(name):
            Quotes a SQL identifier to prevent SQL injection and handle special characters.

        _quote_table(name):
            Quotes a table name, including schema if provided, to ensure proper SQL syntax.

        merge_upsert(conn, table_name, df, key_cols, dialect=None):
            Performs an upsert (merge) operation on the specified table using the provided DataFrame.
            The method checks if the target table exists, creates a staging table, and constructs 
            the appropriate SQL MERGE statement based on the specified SQL dialect.
            
            Parameters:
                conn: The database connection object.
                table_name (str): The name of the target table for the upsert operation.
                df: The DataFrame containing the data to be upserted.
                key_cols (list): A list of column names to be used as keys for the upsert operation.
                dialect (str, optional): The SQL dialect to use (e.g., 'mssql', 'oracle', 'mysql', 'postgresql').
            
            Raises:
                ValueError: If no key columns are found in the DataFrame.
                NotImplementedError: If the specified dialect is not supported for merge upsert.
    '''
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def _quote_identifier(self, name):
        return f"[{name.replace(']', ']]')}]"


    def _quote_table(self, name):
        return ".".join(self._quote_identifier(part) for part in name.split("."))

    def merge_upsert(self, conn, table_name, df, key_cols, dialect=None):
        """
        Perform an upsert (merge) operation for MSSQL, Oracle, MySQL, and PostgreSQL.
        """
        if dialect is None:
            dialect = conn.engine.dialect.name

        print(f"Performing MERGE upsert into {table_name} using keys: {key_cols} (dialect: {dialect})")
        inspector = inspect(conn)
        if not inspector.has_table(table_name):
            df.to_sql(table_name, conn, if_exists='replace', index=False, method=None, chunksize=100)
            return

        stg_table = f"stg_{table_name.replace('.', '_')}_{uuid.uuid4().hex}"
        df.to_sql(stg_table, conn, if_exists='replace', index=False, method=None, chunksize=100)

        quoted_target = self._quote_table(table_name)
        quoted_stg = self._quote_table(stg_table)
        key_cols = [c for c in key_cols if c in df.columns]
        if not key_cols:
            raise ValueError("Nenhuma coluna de chave encontrada para MERGE.")

        update_cols = [c for c in df.columns if c not in key_cols]
        on_clause = " AND ".join([f"tgt.{self._quote_identifier(c)} = src.{self._quote_identifier(c)}" for c in key_cols])
        set_clause = ", ".join([f"tgt.{self._quote_identifier(c)} = src.{self._quote_identifier(c)}" for c in update_cols])
        insert_cols = ", ".join([self._quote_identifier(c) for c in df.columns])
        insert_vals = ", ".join([f"src.{self._quote_identifier(c)}" for c in df.columns])

        if dialect in ("mssql", "sqlserver"):
            update_sql = f"WHEN MATCHED THEN UPDATE SET {set_clause}" if update_cols else ""
            merge_sql = f"""
            MERGE INTO {quoted_target} AS tgt
            USING {quoted_stg} AS src
            ON {on_clause}
            {update_sql}
            WHEN NOT MATCHED BY TARGET THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals});
            """
            conn.execute(text(merge_sql))
            conn.execute(text(f"DROP TABLE {quoted_stg}"))

        elif dialect == "oracle":
            update_sql = f"WHEN MATCHED THEN UPDATE SET {set_clause}" if update_cols else ""
            merge_sql = f"""
            MERGE INTO {quoted_target} tgt
            USING {quoted_stg} src
            ON ({on_clause})
            {update_sql}
            WHEN NOT MATCHED THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals})
            """
            conn.execute(text(merge_sql))
            conn.execute(text(f"DROP TABLE {quoted_stg}"))

        elif dialect == "postgresql":
            # Postgres: Use INSERT ... ON CONFLICT
            pk = [self._quote_identifier(c) for c in key_cols]
            update_set = ", ".join([f"{self._quote_identifier(c)} = EXCLUDED.{self._quote_identifier(c)}" for c in update_cols])
            insert_sql = f"""
            INSERT INTO {quoted_target} ({insert_cols})
            SELECT {insert_vals} FROM {quoted_stg}
            ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {update_set};
            """
            conn.execute(text(insert_sql))
            conn.execute(text(f"DROP TABLE {quoted_stg}"))

        elif dialect == "mysql":
            # MySQL: Use INSERT ... ON DUPLICATE KEY UPDATE
            update_set = ", ".join([f"{self._quote_identifier(c)} = VALUES({self._quote_identifier(c)})" for c in update_cols])
            insert_sql = f"""
            INSERT INTO {quoted_target} ({insert_cols})
            SELECT {insert_vals} FROM {quoted_stg}
            ON DUPLICATE KEY UPDATE {update_set};
            """
            conn.execute(text(insert_sql))
            conn.execute(text(f"DROP TABLE {quoted_stg}"))

        else:
            conn.execute(text(f"DROP TABLE {quoted_stg}"))
            raise NotImplementedError(f"Dialect '{dialect}' not supported for merge upsert.")