import base64
import pandas as pd
import numpy as np

class Utils:
    """
    Classe Utils que fornece métodos utilitários para codificação e manipulação de dados.
    Métodos:
    - b64(v: str) -> str: 
        Codifica uma string em Base64.
    - b64d(v: str) -> str: 
        Decodifica uma string codificada em Base64.
    - create_fake_dataset(num_rows: int, num_cols: int) -> pd.DataFrame: 
        Cria um DataFrame com dados aleatórios. O DataFrame terá o número de linhas e colunas especificado.
        Os dados são gerados a partir de uma escolha aleatória entre um número aleatório (float), 
        um número inteiro aleatório entre 0 e 100, e uma string formatada com um número inteiro aleatório.
    """
    @staticmethod
    def b64(v: str) -> str:
        return base64.b64encode(v.encode()).decode()
    
    @staticmethod
    def b64d(v: str) -> str:
        return base64.b64decode(v).decode()
    
    @staticmethod
    def create_fake_dataset(num_rows: int, num_cols: int):
        df = pd.DataFrame(
            np.random.choice(
            [np.random.randn(), np.random.randint(0, 100), f'str_{np.random.randint(0, 100)}'],
            size=(num_rows, num_cols)
            ).reshape(num_rows, num_cols),
            columns=[f'col_{i}' for i in range(num_cols)]
        )
        return df