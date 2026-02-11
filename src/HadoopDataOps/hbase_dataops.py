import happybase
import requests
import json

from HadoopDataOps.dataops_utils import Utils
from typing import Iterable, List, Dict, Any


class HBaseRestClient:
    def __init__(
        self,
        base_url: str = "http://hbase-api:8080",
        verify_ssl: bool = False,
        timeout: tuple = (5, 60),  # (connect_timeout, read_timeout)
        default_cf: str = "d",
        cf_mode: str = "single",   # "single" => d:field | "per_field" => field:value (seu padrão antigo)
        hbase_host: str = "hbase-thrift",
        thrift_port: int = 9090
    ):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.default_cf = default_cf
        self.cf_mode = cf_mode
        self.hbase_host = hbase_host
        self.thrift_port = thrift_port

    def hbase_connect(self):
        return happybase.Connection(
            host=self.hbase_host,
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
        
    def get_hbase_rows_rest(self, table, batch = 500) -> Iterable[Dict[str, Any]]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
        # Create scanner
        r = requests.post(
            f"{self.base_url}/{table}/scanner",
            headers=headers,
            json={"batch": batch, "maxVersions": 1}
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
    
    def get_hbase_rows_thrift(self, table_name):
        
        hbase_conn = self.hbase_connect()
        table = hbase_conn.table(table_name)
        rows = []

        for key, data in table.scan():
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