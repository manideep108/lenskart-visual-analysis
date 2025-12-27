from __future__ import annotations

from typing import Iterator
import pandas as pd

from src.schema.input_schema import ProductInput


class DatasetLoader:
    def load_products(self, file_path: str) -> Iterator[ProductInput]:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}. Only .csv, .xlsx, and .xls are supported.")
        
        df = df.fillna("")
        
        for _, row in df.iterrows():
            product_id = str(row["Product Id"])
            
            image_urls = []
            for col in df.columns:
                if col.startswith("Image"):
                    url = str(row[col]).strip()
                    if url:
                        image_urls.append(url)
            
            if image_urls:
                yield ProductInput(
                    product_id=product_id,
                    image_urls=image_urls
                )
