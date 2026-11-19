from pydantic import BaseModel,Field
class ComparisonInput(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    group_a_source_id:int
    group_b_source_id:int
