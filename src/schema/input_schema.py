from typing import List
from pydantic import BaseModel


class ProductInput(BaseModel):
    product_id: str
    image_urls: List[str]
