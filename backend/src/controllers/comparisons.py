from ..services import comparisons
from ..utils.serialization import row
class ComparisonsController:
    list=staticmethod(comparisons.list_comparisons)
    create=staticmethod(comparisons.create_comparison)
    @staticmethod
    def get(db,id):return row(comparisons.get_comparison(db,id))
