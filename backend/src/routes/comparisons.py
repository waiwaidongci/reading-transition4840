from fastapi import APIRouter,Depends
from ..config.database import db_session
from ..schemas.comparison import ComparisonInput
from ..services.auth import current_user,writer
from ..services.export import comparison_csv
from ..controllers.comparisons import ComparisonsController as C
router=APIRouter()
@router.get('/comparisons')
def all_comparisons(db=Depends(db_session),u=Depends(current_user)):return C.list(db)
@router.post('/comparisons')
def create(data:ComparisonInput,db=Depends(db_session),u=Depends(writer)):return C.create(db,u,data)
@router.get('/comparisons/{id}')
def detail(id:int,db=Depends(db_session),u=Depends(current_user)):return C.get(db,id)
@router.get('/comparisons/{id}/export')
def export(id:int,db=Depends(db_session),u=Depends(current_user)):return comparison_csv(db,id)
