import happybase
import requests
import json

from DataOpsClasses.dataops_utils import Utils
from typing import Iterable, List, Dict, Any


class HBaseOps:
    """
    HBaseOps is a class that provides operations for interacting with HBase using both REST and Thrift protocols.
    Attributes:
        base_url (str): The base URL for the HBase REST API.
        verify_ssl (bool): Flag to verify SSL certificates.
        timeout (tuple): A tuple specifying the connection and read timeout values.
        default_cf (str): The default column family to use for operations.
        cf_mode (str): The mode for column family handling, either 'single' or 'per_field'.
        thrift_host (str): The hostname for the HBase Thrift server.
        thrift_port (int): The port for the HBase Thrift server.
    Methods:
        hbase_connect(): Establishes a connection to the HBase Thrift server.
        create_hbase_table(table_name: str, column_families: List[str]) -> bool:
            Creates a new HBase table with the specified name and column families.
        prepare_rows(df) -> Dict[str, Any]:
            Prepares the rows from a DataFrame for insertion into HBase.
        insert_row(table: str, row: str, payload: Dict[str, Any], verbose: bool = False) -> bool:
            Inserts a row into the specified HBase table.
        get_hbase_rows_rest(table: str, batch: int = 500, filter_expression: Optional[str] = None) -> Iterable[Dict[str, Any]]:
            Retrieves rows from an HBase table using the REST API.
        get_hbase_rows_thrift(table_name: str, filter_expression: Optional[str] = None) -> List[Dict[str, Any]]:
            Retrieves rows from an HBase table using the Thrift API.
        put_hbase_row_thrift(table_name: str, row_key: str, data: Dict[str, Any]):
            Inserts a row into an HBase table using the Thrift API.
    """
    def __init__(
        self,
        base_url: str = "http://hbase-api:8080",
        verify_ssl: bool = False,
        timeout: tuple = (5, 60),  # (connect_timeout, read_timeout)
        default_cf: str = "d",
        cf_mode: str = "single",   # "single" => d:field | "per_field" => field:value (seu padrão antigo)
        thrift_host: str = "hbase-thrift",
        thrift_port: int = 9090
    ):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.default_cf = default_cf
        self.cf_mode = cf_mode
        self.thrift_host = thrift_host
        self.thrift_port = thrift_port

    def hbase_connect(self):
        return happybase.Connection(
            host=self.thrift_host,
            port=self.thrift_port,
            autoconnect=True
        )

    def create_hbase_table(self, table_name: str, column_families: List[str]) -> bool:
        url = f"{self.base_url}/{table_name}/schema"
        schema = {
            "name": table_name,
            "ColumnSchema": [{"cf":cf,"name": cf} for cf in column_families],
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
        r = requests.put(
            url,
            data=json.dumps(schema),
            headers=headers,
            verify=self.verify_ssl,
            timeout=self.timeout,
        )
    
        if r.status_code >= 400:
            print("CREATE status:", r.status_code)
            print("CREATE body:", r.text)
            r.raise_for_status()
    
        return True

    
    def prepare_rows(self, df) -> Dict[str, Any]:
        payloads = {}

        for row in df.collect():
            cells = []
        
            for col in df.columns:
                if col != 'uuid':
                    cells.append({
                        "column": Utils.b64(f"{col}:value"),
                        "$": Utils.b64(str(getattr(row, col)))
                    })
                else:
                    row = getattr(row, col)
        
            payloads[row] = {
                "Row": [
                    {
                        "Cell": cells
                    }
                ]
            }

        return payloads
    
    def insert_row(self, table, row, payload, verbose=False):

        endpoint = f"{self.base_url}/{table}/{row}"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if verbose:
            print('endpoint ',endpoint,' payload ',payload) 
        
        try:
            r = requests.put(
                endpoint,
                json=payload,
                headers=headers
            )

            return True
        except:
            return False
        
    def get_hbase_rows_rest(self, table, batch=500, filter_expression=None) -> Iterable[Dict[str, Any]]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
        # Create scanner
        payload = {"batch": batch, "maxVersions": 1}
        if filter_expression:
            payload["filter"] = filter_expression
        
        r = requests.post(
            f"{self.base_url}/{table}/scanner",
            headers=headers,
            json=payload
        )
    
        scanner_url = r.headers["Location"]
    
        try:
            while True:
                r = requests.get(scanner_url, headers={"Accept": "application/json"})
    
                if r.status_code == 204:
                    break
    
                r.raise_for_status()
                data = r.json()
    
                for row in data.get("Row", []):
                    row_key = Utils.b64d(row["key"])
                    record = {"row_key": row_key}
    
                    for cell in row.get("Cell", []):
                        column = Utils.b64d(cell["column"])
                        value = Utils.b64d(cell["$"])
    
                        cf, qualifier = column.split(":", 1)
                        record[f"{cf}_{qualifier}"] = value
    
                    yield record
    
        finally:
            requests.delete(scanner_url)
    
    def get_hbase_rows_thrift(self, table_name, filter_expression=None):
        
        hbase_conn = self.hbase_connect()
        table = hbase_conn.table(table_name)
        rows = []

        scan_params = {}
        if filter_expression:
            scan_params['filter'] = filter_expression

        for key, data in table.scan(**scan_params):
            record = {
                "row_key": key.decode()
            }
            # Convert column family qualifiers
            for col, value in data.items():
                record[col.decode().replace(":", "_")] = value.decode(errors="ignore")
            rows.append(record)
        hbase_conn.close()
        return rows
    
    def put_hbase_row_thrift(self, table_name, row_key, data):
        hbase_conn = self.hbase_connect()
        table = hbase_conn.table(table_name)
        table.put(row_key.encode(), {f"{self.default_cf}:{k}".encode(): str(v).encode() for k, v in data.items()})
        hbase_conn.close()