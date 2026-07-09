from pydantic import BaseModel, Field


class BaseProduct(BaseModel):
    name: str
    category: str
    base_price_eur: float = Field(..., gt=0)
    description: str = ""
    variant_axis: str = "aucun"  # couleur | taille | capacité | aucun


class CityEntry(BaseModel):
    city: str
    zip: str


class Pools(BaseModel):
    base_products: list[BaseProduct]
    first_names: list[str]
    last_names: list[str]
    cities: list[CityEntry]
    carriers: list[str]
